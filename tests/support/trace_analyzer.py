from __future__ import annotations

import builtins
import dataclasses
import glob
import json
import re
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache
from os import path
from typing import Callable, Dict, List, Optional, Set, Tuple, TypeVar, Union

import web3

ROOT_DIR = path.join(path.dirname(__file__), "../../")

LIBRARY_PLACEHOLDER = re.compile(r"__\$[a-zA-Z0-9_]+\$__")
ZERO_ADDRESS = "0" * 40
PUSH1 = 0x60
PUSH32 = 0x7F
CALL_OPS = ("CALL", "DELEGATECALL", "STATICCALL")


class JumpType(Enum):
    In = "i"
    Out = "o"
    Regular = "-"

    @classmethod
    def from_raw(cls, value: str) -> JumpType:
        return {"i": cls.In, "o": cls.Out, "-": cls.Regular}[value]


@dataclass
class Location:
    source_index: str
    offset: int
    length: int
    jump_type: JumpType = JumpType.Regular
    modifier_depth: int = 0

    @property
    def end(self):
        return self.offset + self.length

    def is_within(self, location: Location):
        return self.offset >= location.offset and self.end <= location.end

    def to_list(self) -> list:
        return [
            self.offset,
            self.length,
            self.source_index,
            self.jump_type.value,
            self.modifier_depth,
        ]

    @classmethod
    def from_raw_ast(cls, raw: str) -> Location:
        offset, length, source = raw.split(":")
        return Location(source_index=source, offset=int(offset), length=int(length))

    @classmethod
    def from_raw_bytecode(
        cls, raw: str, previous: Optional[Location] = None
    ) -> Location:
        if previous is None:
            previous = Location(source_index="", offset=0, length=0)
        merged = []
        splitted = raw.split(":")
        splitted = splitted + [""] * (5 - len(splitted))
        previous_list = previous.to_list()
        for i in range(5):
            merged.append(splitted[i] if splitted[i] else previous_list[i])
        return cls(
            source_index=merged[2],
            offset=int(merged[0]),
            length=int(merged[1]),
            jump_type=JumpType.from_raw(merged[3]),
            modifier_depth=int(merged[4]),
        )


@dataclass
class Definition:
    name: str
    location: Location


@dataclass
class ContractDefinition(Definition):
    @classmethod
    def from_ast_node(cls, node: dict) -> ContractDefinition:
        return cls(
            name=node["name"],
            location=Location.from_raw_ast(node["src"]),
        )


@dataclass
class FunctionDefinition(Definition):
    contract_name: str

    @property
    def qualified_name(self) -> str:
        return f"{self.contract_name}.{self.name}"

    @classmethod
    def from_ast_node(cls, node: dict, contract_name: str) -> FunctionDefinition:
        return FunctionDefinition(
            name=node["name"],
            contract_name=contract_name,
            location=Location.from_raw_ast(node["src"]),
        )


@dataclass
class SourceData:
    D = TypeVar("D", bound=Definition)

    path: str
    ast: dict
    index: str
    contracts: List[ContractDefinition]
    functions: List[FunctionDefinition]
    instruction_mapping: Dict[int, int]
    content: str
    source_map: List[Location]
    bytecode: bytes

    def has_contract(self, name: str) -> bool:
        return any(name == c.name for c in self.contracts)

    def get_pc_location(self, pc: int) -> Location:
        instruction_index = self.instruction_mapping[pc]
        return self.source_map[instruction_index]

    def _find_container_at(self, loc: Location, containers: List[D]) -> Optional[D]:
        for container in containers:
            if loc.is_within(container.location):
                return container

    def find_function_at(self, location: Location) -> Optional[FunctionDefinition]:
        return self._find_container_at(location, self.functions)

    def find_contract_at(self, location: Location) -> Optional[ContractDefinition]:
        return self._find_container_at(location, self.contracts)

    @classmethod
    def from_build(cls, build_data) -> SourceData:
        ast = build_data["ast"]
        index = Location.from_raw_ast(ast["src"]).source_index
        with open(path.join(ROOT_DIR, build_data["sourcePath"])) as f:
            content = f.read()
        contracts, functions = find_definitions(ast)
        bytecode = parse_bytecode(build_data["deployedBytecode"])
        return cls(
            path=build_data["sourcePath"],
            ast=ast,
            index=index,
            contracts=contracts,
            instruction_mapping=compute_pc_mapping(bytecode),
            functions=functions,
            content=content,
            source_map=parse_source_map(build_data["deployedSourceMap"].split(";")),
            bytecode=bytecode,
        )

    def __repr__(self):
        return f"SourceData(path={self.path})"


class Sources:
    D = TypeVar("D", bound=Definition)

    def __init__(self, sources: Dict[str, SourceData]):
        self._sources = sources

    @lru_cache()
    def find_contract(self, name: str) -> SourceData:
        for source in self._sources.values():
            if source.has_contract(name):
                return source
        raise ValueError(f"No contract found with name {name}")

    def _get_location_container(
        self, location: Location, f: Callable[[SourceData], List[D]]
    ) -> Optional[D]:
        if location.source_index == "-1":
            return
        source = self._sources[location.source_index]
        for container in f(source):
            if location.is_within(container.location):
                return container

    def get_location_function(self, location: Location) -> Optional[FunctionDefinition]:
        return self._get_location_container(location, lambda s: s.functions)

    def get_location_contract(self, location: Location) -> Optional[ContractDefinition]:
        return self._get_location_container(location, lambda s: s.contracts)

    def get_location_code(self, location: Location) -> str:
        content = self._sources[location.source_index].content
        return content[location.offset : location.end]

    def get_pc_code(self, contract_name: str, pc: int) -> str:
        source = self.find_contract(contract_name)
        instruction_index = source.instruction_mapping[pc]
        return self.get_location_code(source.source_map[instruction_index])

    @classmethod
    def load(cls):
        build_files = glob.glob(path.join(ROOT_DIR, "build", "contracts", "*.json"))
        sources: Dict[str, SourceData] = {}
        for build_file in build_files:
            with open(build_file) as f:
                data = json.load(f)
            source_data = SourceData.from_build(data)
            sources[source_data.index] = source_data
        return cls(sources)


def parse_bytecode(bytecode: Union[str, bytes]) -> bytes:
    if isinstance(bytecode, str):
        if bytecode.startswith("0x"):
            bytecode = bytecode[2:]
        bytecode = bytes.fromhex(LIBRARY_PLACEHOLDER.sub(ZERO_ADDRESS, bytecode))
    return bytecode


def compute_pc_mapping(bytecode: bytes):
    mapping = {}
    instruction_offset, pc = 0, 0
    while pc < len(bytecode):
        opcode = bytecode[pc]
        mapping[pc] = instruction_offset
        instruction_offset += 1
        pc += 1
        if PUSH1 <= opcode <= PUSH32:
            pc += opcode - PUSH1 + 1
    return mapping


def find_definitions(root) -> Tuple[List[ContractDefinition], List[FunctionDefinition]]:
    function_definitions = []
    contract_definitions = []

    def _find_definitions(node, contract_name):
        node_type = node.get("nodeType")

        if node_type == "ContractDefinition":
            contract_name = node["name"]
            contract_definitions.append(ContractDefinition.from_ast_node(node))

        if node_type == "FunctionDefinition":
            function_definitions.append(
                FunctionDefinition.from_ast_node(node, contract_name)
            )

        for child in node.get("nodes", []):
            _find_definitions(child, contract_name)

    _find_definitions(root, "")

    return contract_definitions, function_definitions


def generate_deployments():
    import brownie
    from brownie.network.contract import ContractContainer

    deployments = {}
    for name in builtins.dir(brownie):
        value = getattr(brownie, name)
        if isinstance(value, ContractContainer):
            deployments[value._name] = [v.address for v in value]
    return deployments


def parse_source_map(source_map) -> List[Location]:
    result = []
    current_source_map = None
    for location in source_map:
        current_source_map = Location.from_raw_bytecode(location, current_source_map)
        result.append(current_source_map)
    return result


class CallType(Enum):
    CALL = "CALL"
    DELEGATE = "DELEGATECALL"
    STATIC = "STATICCALL"
    INTERNAL = "INTERNAL_CALL"

    @classmethod
    def from_op(cls, op: str) -> CallType:
        return {
            "CALL": cls.CALL,
            "DELEGATECALL": cls.DELEGATE,
            "STATICCALL": cls.STATIC,
        }[op]

    @property
    def char(self):
        return {
            self.CALL: "C",
            self.DELEGATE: "D",
            self.STATIC: "S",
            self.INTERNAL: "I",
        }[self]


@dataclass
class Context:
    contract_name: str
    function_name: str
    initial_gas: int
    final_gas: int = 0
    children: List[Tuple[CallType, Context]] = field(default_factory=list)

    @property
    def total_gas_consumed(self):
        return self.initial_gas - self.final_gas if self.final_gas else 0

    @property
    def gas_consumed(self):
        return self.total_gas_consumed - sum(
            child.total_gas_consumed for _, child in self.children
        )

    @property
    def qualified_function_name(self):
        if self.contract_name:
            return f"{self.contract_name}.{self.function_name}"
        else:
            return self.function_name

    def __repr__(self):
        return self._format([])

    @property
    def summary(self):
        return f"{self.qualified_function_name} ({self.gas_consumed:,} / {self.total_gas_consumed:,})"

    def format(self, maxlvl=None):
        return self._format([], maxlvl=maxlvl)

    def _format(
        self,
        prefixes: List[bool],
        transition_type: Optional[CallType] = None,
        is_last: bool = False,
        maxlvl=None,
        lvl=1,
    ):
        format_prefix = lambda x: "│   " if x else "    "
        prefix = "".join(map(format_prefix, prefixes[:-1]))
        pipe = "└" if is_last else "│"
        prefix += f"{pipe}─({transition_type.char})─" if transition_type else ""
        line = f"{prefix} {self.summary}\n"
        if maxlvl is not None and lvl >= maxlvl:
            children = ""
            # childprefix = "".join(map(format_prefix, prefixes[:])) + "└─"
            # children = childprefix + " [...]\n"
        else:
            children = "".join(
                child._format(
                    prefixes + [i < len(self.children) - 1],
                    t,
                    i == len(self.children) - 1,
                    maxlvl,
                    lvl + 1,
                )
                for i, (t, child) in enumerate(self.children)
            )
        return line + children

    def update_names(self, sources: Sources, location: Location):
        if not self.contract_name:
            contract = sources.get_location_contract(location)
            if contract:
                self.contract_name = contract.name

        if not self.function_name:
            function = sources.get_location_function(location)
            if function:
                self.function_name = function.name


def normalize_address(address: str) -> str:
    return web3.Web3.toChecksumAddress(
        int.from_bytes(bytes.fromhex(address), "big").to_bytes(20, "big").hex()
    )


class Tracer:
    def __init__(self, sources: Sources, deployments: Dict[str, List[str]]):
        self.sources = sources
        self.deployments = deployments

    def find_contract_name(self, address: str) -> str:
        for contract_name, addresses in self.deployments.items():
            if address in addresses:
                return contract_name

        return "<Unknown>"

    def trace_tx(self, tx) -> Context:
        return self.trace(tx.contract_name, tx.trace)

    def trace(self, contract_name: str, traces: List[dict]) -> Context:
        root_context = Context(
            contract_name=contract_name,
            function_name="",
            initial_gas=traces[0]["gas"],
        )

        call_stack = [(root_context, [])]

        for i, trace in enumerate(traces):
            context, internal_call_stack = call_stack[-1]
            source = self.sources.find_contract(context.contract_name)
            location = source.get_pc_location(trace["pc"])
            if location.source_index == "-1":
                continue

            context.update_names(self.sources, location)

            op = trace["op"]

            if op in CALL_OPS:
                target_address = normalize_address(trace["stack"][-2])
                contract_name = self.find_contract_name(target_address)
                new_context = Context(
                    contract_name=contract_name,
                    function_name="",
                    initial_gas=traces[i + 1]["gas"],
                )
                context.children.append((CallType.from_op(op), new_context))
                call_stack.append((new_context, []))

            elif op in ("RETURN", "REVERT"):
                context.final_gas = trace["gas"]
                call_stack.pop()

            elif op == "JUMP" and location.jump_type == JumpType.In:
                next_location = source.get_pc_location(traces[i + 1]["pc"])
                func = self.sources.get_location_function(next_location)
                parent_context = (
                    internal_call_stack[-1] if internal_call_stack else context
                )
                if (
                    not func
                    or func.qualified_name == parent_context.qualified_function_name
                ):
                    continue
                new_context = Context(
                    contract_name=func.contract_name,
                    function_name=func.name,
                    initial_gas=trace["gas"],
                )
                parent_context.children.append((CallType.INTERNAL, new_context))
                internal_call_stack.append(new_context)

            elif op == "JUMP" and location.jump_type == JumpType.Out:
                if internal_call_stack:
                    internal_call_stack[-1].final_gas = trace["gas"]
                    internal_call_stack.pop()

        root_context.final_gas = traces[-1]["gas"]

        return root_context

    @classmethod
    def load(cls):
        sources = Sources.load()
        deployments = generate_deployments()
        return cls(sources, deployments)

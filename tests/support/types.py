from dataclasses import field
from typing import NamedTuple, Tuple, Iterable

from tests.support.quantized_decimal import DecimalLike
from brownie import accounts


address = str

DEFAULT_CAP_MANAGER = "0x66aB6D9362d4F35596279692F0251Db635165871"
DEFAULT_PAUSE_MANAGER = "0x66aB6D9362d4F35596279692F0251Db635165871"


class SwapKind:
    GivenIn = 0
    GivenOut = 1


class CallJoinPoolGyroParams(NamedTuple):
    pool: address
    poolId: bytes
    sender: address
    recipient: address
    currentBalances: Tuple[int, ...]
    lastChangeBlock: int
    protocolSwapFeePercentage: int
    amountIn: Iterable[int]
    bptOut: int


class SwapRequest(NamedTuple):
    kind: int
    tokenIn: address
    tokenOut: address
    amount: int
    poolId: bytes
    lastChangeBlock: int
    from_aux: address
    to: address
    userData: bytes


class TwoPoolBaseParams(NamedTuple):
    vault: str
    name: str
    symbol: str
    token0: str
    token1: str
    swapFeePercentage: DecimalLike
    pauseWindowDuration: DecimalLike
    bufferPeriodDuration: DecimalLike
    oracleEnabled: bool
    owner: str


class CapParams(NamedTuple):
    cap_enabled: bool = False
    per_address_cap: int = 0
    global_cap: int = 0


class TwoPoolFactoryCreateParams(NamedTuple):
    name: str
    symbol: str
    tokens: list[str]
    sqrts: list[int]
    swapFeePercentage: DecimalLike
    oracleEnabled: bool
    owner: address
    cap_manager: address = DEFAULT_CAP_MANAGER
    cap_params: CapParams = CapParams()
    pause_manager: address = DEFAULT_PAUSE_MANAGER


class TwoPoolParams(NamedTuple):
    baseParams: TwoPoolBaseParams
    sqrtAlpha: DecimalLike  # should already be upscaled
    sqrtBeta: DecimalLike  # Should already be upscaled
    cap_manager: address = DEFAULT_CAP_MANAGER
    cap_params: CapParams = CapParams()
    pauseManager: address = DEFAULT_PAUSE_MANAGER


class Vector2(NamedTuple):
    x: DecimalLike
    y: DecimalLike


class CEMMMathParams(NamedTuple):
    alpha: DecimalLike
    beta: DecimalLike
    c: DecimalLike
    s: DecimalLike
    l: DecimalLike


class CEMMMathQParams(NamedTuple):
    a: DecimalLike
    b: DecimalLike
    c: DecimalLike


class CEMMMathDerivedParams(NamedTuple):
    tauAlpha: Vector2
    tauBeta: Vector2
    u: DecimalLike
    v: DecimalLike
    w: DecimalLike
    z: DecimalLike
    dSq: DecimalLike


class ThreePoolFactoryCreateParams(NamedTuple):
    name: str
    symbol: str
    tokens: list[str]
    swapFeePercentage: DecimalLike
    root3Alpha: DecimalLike
    owner: address
    cap_manager: address = DEFAULT_CAP_MANAGER
    cap_params: CapParams = CapParams()
    pause_manager: address = DEFAULT_PAUSE_MANAGER


class ThreePoolParams(NamedTuple):
    vault: str
    config_address: address
    config: ThreePoolFactoryCreateParams
    pauseWindowDuration: int
    bufferPeriodDuration: int


# Legacy Aliases
GyroCEMMMathParams = CEMMMathParams
GyroCEMMMathDerivedParams = CEMMMathDerivedParams


class CEMMPoolParams(NamedTuple):
    baseParams: TwoPoolBaseParams
    cemmParams: GyroCEMMMathParams
    derivedCEMMParams: GyroCEMMMathDerivedParams

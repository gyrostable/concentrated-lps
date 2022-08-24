from contextlib import contextmanager
from dataclasses import dataclass
from unicodedata import decimal

from hypothesis import strategies as st, assume

from tests.support.types import Vector2
from tests.support.utils import qdecimals
from tests.support.quantized_decimal import QuantizedDecimal as D


@dataclass
class BasicPoolParameters:
    min_price_separation: D
    max_in_ratio: D
    max_out_ratio: D
    min_balance_ratio: D
    min_fee: D
    max_balances: int = 100_000_000_000  # Max balances to test


billion_balance_strategy = st.integers(min_value=0, max_value=100_000_000_000)


@st.composite
def gen_balances(draw, n: int, bparams: BasicPoolParameters):
    """Draw n balances respecting max_balances and min_balance_ratio. Only implemented for n = 1, 2, 3"""
    mbr = bparams.min_balance_ratio
    mbr2 = D("1e-18") if mbr == 0 else mbr
    x = D(draw(qdecimals(1, bparams.max_balances)))
    if n == 1:
        return [x]

    y = draw(qdecimals(x * mbr, min(x / mbr2, bparams.max_balances)))
    if n == 2:
        return [x, y]

    z = draw(qdecimals(max(x, y) * mbr, min(min(x, y) / mbr2, bparams.max_balances)))
    if n == 3:
        return [x, y, z]

    raise NotImplementedError("generating > 3 assets is not implemented")


def gen_balances_vector(bparams: BasicPoolParameters):
    return gen_balances(2, bparams).map(lambda args: Vector2(*args))


@contextmanager
def debug_postmortem_on_exc(use_pdb=True):
    """When use_pdb is True, enter the debugger if an exception is raised."""
    try:
        yield
    except Exception as e:
        if not use_pdb:
            raise
        import sys
        import traceback
        import pdb

        info = sys.exc_info()
        traceback.print_exception(*info)
        pdb.post_mortem(info[2])

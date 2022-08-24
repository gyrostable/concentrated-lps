import hypothesis.strategies as st
import pytest
from brownie.test import given
from tests.support.quantized_decimal import QuantizedDecimal as D
from tests.support.utils import scale

billion_balance_strategy = st.integers(min_value=0, max_value=1_000_000_000)

from tests.cpmmv2 import math_implementation as cp

# this is a multiplicative separation
# This is consistent with tightest price range of 0.9999 - 1.0001
MIN_SQRTPARAM_SEPARATION = D("1.0001")


@given(
    balances=st.tuples(billion_balance_strategy, billion_balance_strategy),
    sqrt_alpha=st.decimals(min_value="0.2", max_value="0.9999", places=4),
    sqrt_beta=st.decimals(min_value="0.2", max_value="1.8", places=4),
)
def test_calc_spot_price(mock_gyro_two_oracle_math, balances, sqrt_alpha, sqrt_beta):
    balances = tuple(D(str(b)) for b in balances)
    if balances[0] == 0 and balances[1] == 0:
        return
    if sqrt_beta <= sqrt_alpha * MIN_SQRTPARAM_SEPARATION:
        return

    invariant = cp.calculateInvariant(balances, sqrt_alpha, sqrt_beta)
    a = cp.calculateVirtualParameter0(invariant, sqrt_beta)
    b = cp.calculateVirtualParameter1(invariant, sqrt_alpha)

    scaleBalances = scale(balances)
    # calculate price of asset 0 in asset 1
    result = mock_gyro_two_oracle_math.calcSpotPrice(
        scaleBalances[1], scale(b), scaleBalances[0], scale(a)
    )
    expected = (balances[1] + b).div_up(balances[0] + a)

    # also compare for consistency to the calculateSqrtPrice function
    # but there might be small error from mulUp etc
    expected2 = cp.calculateSqrtPrice(invariant, balances[0] + a) ** 2
    assert result == scale(expected)
    assert int(result) == pytest.approx(scale(expected2).raw)


# Note: the rest of the functions in mock_gyro_two_oracle_math are rather trivial
# given spot prices and the original Balancer codebase

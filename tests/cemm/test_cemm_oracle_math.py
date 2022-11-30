import functools
from decimal import Decimal
from math import pi, sin, cos
from typing import Tuple

import hypothesis.strategies as st
from _pytest.python_api import ApproxDecimal
from brownie.test import given
from brownie import reverts
from hypothesis import assume, settings
from tests.cemm import cemm as mimpl
from tests.support.utils import scale, to_decimal, qdecimals, unscale
from tests.support.types import *
from tests.support.quantized_decimal import QuantizedDecimal as D

billion_balance_strategy = st.integers(min_value=0, max_value=10_000_000_000)
price_strategy = st.decimals(min_value="1e-6", max_value="1e6")

# this is a multiplicative separation
# This is consistent with tightest price range of beta - alpha >= MIN_PRICE_SEPARATION
MIN_PRICE_SEPARATION = to_decimal("0.0001")
MAX_IN_RATIO = to_decimal("0.3")
MAX_OUT_RATIO = to_decimal("0.3")

MIN_BALANCE_RATIO = to_decimal("1e-5")
MIN_FEE = D("0.0001")


def gen_balances():
    return st.tuples(billion_balance_strategy, billion_balance_strategy)


@given(
    spot_price=price_strategy,
)
def test_log_spot_price(gyro_cemm_oracle_math_testing, spot_price):
    log_spot_price = spot_price.ln()
    log_spot_price_sol = gyro_cemm_oracle_math_testing.calcLogSpotPrice(
        scale(spot_price)
    )

    # note: balancer logarithm returns int with 4 decimal places
    assert log_spot_price == (to_decimal(log_spot_price_sol) / D("1e4")).approxed(
        abs=1e-4
    )


@given(
    balances=gen_balances(),
    spot_price=price_strategy,
    bpt_supply=qdecimals(min_value=1, max_value=10_000_000_000, places=4),
)
def test_log_bpt_price(gyro_cemm_oracle_math_testing, balances, spot_price, bpt_supply):
    assume(balances[0] != 0 and balances[1] != 0)

    log_bpt_supply = to_decimal(bpt_supply).raw.ln()
    # scaled to have 4 decimals precision, but still needs to be scaled by 1e18 later)
    log_bpt_supply_scaled = log_bpt_supply / D("1e14")
    log_bpt_price_sol = gyro_cemm_oracle_math_testing.calcLogBPTPrice(
        scale(balances[0]),
        scale(balances[1]),
        scale(spot_price),
        scale(log_bpt_supply_scaled),
    )

    log_bpt_price = ((balances[0] * spot_price + balances[1]) / bpt_supply).raw.ln()
    log_bpt_price2 = (balances[0] * spot_price + balances[1]).ln() - log_bpt_supply

    assert log_bpt_price == (to_decimal(log_bpt_price_sol) / D("1e4")).approxed(
        abs=5e-4
    )
    assert log_bpt_price2 == (to_decimal(log_bpt_price_sol) / D("1e4")).approxed(
        abs=5e-4
    )


@given(
    invariant=st.decimals(min_value="0.001", max_value="1e11"),
    bpt_supply=qdecimals(min_value=1, max_value=10_000_000_000, places=4),
)
def test_log_invariant_div_supply(gyro_cemm_oracle_math_testing, invariant, bpt_supply):
    log_bpt_supply = to_decimal(bpt_supply).raw.ln()
    # scaled to have 4 decimals precision, but still needs to be scaled by 1e18 later)
    log_bpt_supply_scaled = log_bpt_supply / D("1e14")

    log_invariant_div_supply_sol = (
        gyro_cemm_oracle_math_testing.calcLogInvariantDivSupply(
            scale(invariant), scale(log_bpt_supply_scaled)
        )
    )

    log_invariant_div_supply = (invariant / bpt_supply).raw.ln()
    log_invariant_div_supply2 = invariant.ln() - log_bpt_supply

    assert log_invariant_div_supply == (
        to_decimal(log_invariant_div_supply_sol) / D("1e4")
    ).approxed(abs=5e-4)
    assert log_invariant_div_supply2 == (
        to_decimal(log_invariant_div_supply_sol) / D("1e4")
    ).approxed(abs=5e-4)

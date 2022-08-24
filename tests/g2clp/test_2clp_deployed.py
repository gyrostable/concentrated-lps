from decimal import Decimal
from typing import Tuple

import hypothesis.strategies as st
from brownie.test import given
from brownie import reverts
from hypothesis import assume, settings, event
from tests.g2clp import math_implementation
from tests.libraries import pool_math_implementation
from tests.support.util_common import BasicPoolParameters
from tests.support.utils import scale, to_decimal, qdecimals, unscale

from tests.support.quantized_decimal import QuantizedDecimal as D

billion_balance_strategy = st.integers(min_value=0, max_value=100_000_000_000)

# this is a multiplicative separation
# This is consistent with tightest price range of 0.9999 - 1.0001
sqrt_alpha = D("0.2236067977")
sqrt_beta = D("0.2915475947")
fee = D("0.0025")

MIN_SQRTPARAM_SEPARATION = to_decimal("1.0001")
MIN_BAL_RATIO = to_decimal("0")
MIN_FEE = D(fee)
MAX_RATIO = D("0.299")


def faulty_params(balances, sqrt_alpha, sqrt_beta):
    balances = [to_decimal(b) for b in balances]
    if balances[0] == 0 and balances[1] == 0:
        return True
    return sqrt_beta <= sqrt_alpha * MIN_SQRTPARAM_SEPARATION


@st.composite
def gen_params_liquidityUpdate(draw):
    balances = draw(st.tuples(billion_balance_strategy, billion_balance_strategy))
    assume(sum(balances) != 0)
    bpt_supply = draw(qdecimals(D("1e-4") * max(balances), D("1e6") * max(balances)))
    isIncrease = draw(st.booleans())
    if isIncrease:
        dsupply = draw(qdecimals(D("1e-5"), D("1e4") * bpt_supply))
    else:
        dsupply = draw(qdecimals(D("1e-5"), D("0.99") * bpt_supply))
    return balances, bpt_supply, isIncrease, dsupply


################################################################################
### parameter selection


def gen_balances_raw():
    return st.tuples(billion_balance_strategy, billion_balance_strategy)


@st.composite
def gen_balances(draw):
    balances = draw(gen_balances_raw())
    assume(balances[0] > 0 and balances[1] > 0)
    assume(balances[0] / balances[1] > 1e-5)
    assume(balances[1] / balances[0] > 1e-5)
    return balances


@st.composite
def gen_params_dinvariant(draw):
    balances = draw(gen_balances())
    assume(balances[0] > 0 and balances[1] > 0)
    invariant = math_implementation.calculateInvariant(balances, sqrt_alpha, sqrt_beta)
    dinvariant = draw(
        qdecimals(-invariant, 2 * invariant)
    )  # Upper bound kinda arbitrary
    assume(abs(dinvariant) > D("1E-10"))  # Only relevant updates
    return dinvariant


################################################################################
### test invariant underestimated
@given(
    balances=gen_balances(),
)
def test_invariant_match(gyro_two_math_testing, balances):
    mtest_invariant_match(
        gyro_two_math_testing,
        balances,
        sqrt_alpha,
        sqrt_beta,
    )


################################################################################
### test calcInGivenOut for invariant change
# @settings(max_examples=1_000)
@given(
    balances=gen_balances(),
    amount_out=st.decimals(min_value="1", max_value="1000000"),
)
def test_invariant_across_calcInGivenOut(
    gyro_two_math_testing, amount_out, balances: Tuple[int, int]
):
    # check_sol_inv set to false, which is ok as long as the 'truer' invariant calculated in python doesn't decrease
    invariant_after, invariant = mtest_invariant_across_calcInGivenOut(
        gyro_two_math_testing, amount_out, balances, sqrt_alpha, sqrt_beta, False
    )
    assert invariant_after >= invariant


################################################################################
### test calcOutGivenIn for invariant change


# @given(
@given(
    balances=gen_balances(),
    amount_in=st.decimals(min_value="1", max_value="1000000"),
)
def test_invariant_across_calcOutGivenIn(
    gyro_two_math_testing, amount_in, balances: Tuple[int, int]
):
    # check_sol_inv set to false, which is ok as long as the 'truer' invariant calculated in python doesn't decrease
    invariant_after, invariant = mtest_invariant_across_calcOutGivenIn(
        gyro_two_math_testing, amount_in, balances, sqrt_alpha, sqrt_beta, False
    )
    assert invariant_after >= invariant


################################################################################
### test liquidity invariant update for invariant change


@given(params_invariantUpdate=gen_params_liquidityUpdate())
def test_invariant_across_liquidityInvariantUpdate(
    gyro_two_math_testing, params_invariantUpdate
):
    params = (sqrt_alpha, sqrt_beta)
    mtest_invariant_across_liquidityInvariantUpdate(
        gyro_two_math_testing, params, params_invariantUpdate
    )


################################################################################
### mtests


def mtest_invariant_across_calcInGivenOut(
    gyro_two_math_testing,
    amount_out,
    balances: Tuple[int, int],
    sqrt_alpha,
    sqrt_beta,
    check_sol_inv: bool,
    check_price_impact_direction: bool = True,
):
    assume(amount_out <= (balances[1]))
    assume(balances[0] > 0 and balances[1] > 0)

    assume(not faulty_params(balances, sqrt_alpha, sqrt_beta))

    invariant = math_implementation.calculateInvariant(
        to_decimal(balances), to_decimal(sqrt_alpha), to_decimal(sqrt_beta)
    )

    invariant_sol = gyro_two_math_testing.calculateInvariant(
        scale(balances), scale(sqrt_alpha), scale(sqrt_beta)
    )

    # assert unscale(D(invariant_sol)) <= invariant

    virtual_param_in = math_implementation.calculateVirtualParameter0(
        unscale(D(invariant_sol)), to_decimal(sqrt_beta)
    )

    virtual_param_out = math_implementation.calculateVirtualParameter1(
        unscale(D(invariant_sol)), to_decimal(sqrt_alpha)
    )

    in_amount = math_implementation.calcInGivenOut(
        to_decimal(balances[0]),
        to_decimal(balances[1]),
        to_decimal(amount_out),
        to_decimal(virtual_param_in),
        to_decimal(virtual_param_out),
    )

    in_amount_sol = unscale(
        gyro_two_math_testing.calcInGivenOut(
            scale(balances[0]),
            scale(balances[1]),
            scale(amount_out),
            scale(virtual_param_in),
            scale(virtual_param_out),
        )
    )

    event("2Pool-InGivenOut-NoErr")

    # Sanity check.
    assert in_amount_sol == in_amount.approxed()

    if check_price_impact_direction:
        # Price of out-asset in units of in-asset
        px = (balances[0] + virtual_param_in) / (balances[1] + virtual_param_out)
        assert amount_out * px <= in_amount_sol / (1 - MIN_FEE)

    balances_after = (
        balances[0] + in_amount_sol / (1 - MIN_FEE),
        balances[1] - amount_out,
    )
    invariant_after = math_implementation.calculateInvariant(
        to_decimal(balances_after), to_decimal(sqrt_alpha), to_decimal(sqrt_beta)
    )

    if check_sol_inv:
        invariant_sol_after = gyro_two_math_testing.calculateInvariant(
            scale(balances_after), scale(sqrt_alpha), scale(sqrt_beta)
        )
        assert invariant_sol_after >= invariant_sol

    return invariant_after, invariant


def mtest_invariant_across_calcOutGivenIn(
    gyro_two_math_testing,
    amount_in,
    balances: Tuple[int, int],
    sqrt_alpha,
    sqrt_beta,
    check_sol_inv: bool,
    check_price_impact_direction: bool = True,
):
    assume(balances[0] > 0 and balances[1] > 0)

    assume(not faulty_params(balances, sqrt_alpha, sqrt_beta))

    fees = MIN_FEE * amount_in
    amount_in -= fees

    invariant = math_implementation.calculateInvariant(
        to_decimal(balances), to_decimal(sqrt_alpha), to_decimal(sqrt_beta)
    )

    invariant_sol = gyro_two_math_testing.calculateInvariant(
        scale(balances), scale(sqrt_alpha), scale(sqrt_beta)
    )

    # assert unscale(D(invariant_sol)) <= invariant

    virtual_param_in = math_implementation.calculateVirtualParameter0(
        unscale(D(invariant_sol)), to_decimal(sqrt_beta)
    )

    virtual_param_out = math_implementation.calculateVirtualParameter1(
        unscale(D(invariant_sol)), to_decimal(sqrt_alpha)
    )

    out_amount = math_implementation.calcOutGivenIn(
        to_decimal(balances[0]),
        to_decimal(balances[1]),
        to_decimal(amount_in),
        to_decimal(virtual_param_in),
        to_decimal(virtual_param_out),
    )

    if out_amount <= balances[1] and out_amount >= 0:
        out_amount_sol = gyro_two_math_testing.calcOutGivenIn(
            scale(balances[0]),
            scale(balances[1]),
            scale(amount_in),
            scale(virtual_param_in),
            scale(virtual_param_out),
        )
    elif out_amount < 0:
        with reverts("BAL#001"):  # subtraction overflow when ~ 0 and rounding down
            gyro_two_math_testing.calcOutGivenIn(
                scale(balances[0]),
                scale(balances[1]),
                scale(amount_in),
                scale(virtual_param_in),
                scale(virtual_param_out),
            )
        return 0, 0
    else:
        with reverts("GYR#357"):  # ASSET_BOUNDS_EXCEEDED
            gyro_two_math_testing.calcOutGivenIn(
                scale(balances[0]),
                scale(balances[1]),
                scale(amount_in),
                scale(virtual_param_in),
                scale(virtual_param_out),
            )
        return 0, 0

    event("2Pool-OutGivenIn-NoErr")

    # sanity check.
    assert to_decimal(out_amount_sol) == scale(out_amount).approxed()

    if check_price_impact_direction:
        # Price of out-asset in units of in-asset
        px = (balances[0] + virtual_param_in) / (balances[1] + virtual_param_out)
        assert unscale(out_amount_sol) * px <= amount_in + fees

    balances_after = (
        balances[0] + amount_in + fees,
        balances[1] - unscale(out_amount_sol),
    )
    invariant_after = math_implementation.calculateInvariant(
        to_decimal(balances_after), to_decimal(sqrt_alpha), to_decimal(sqrt_beta)
    )

    if check_sol_inv:
        invariant_sol_after = gyro_two_math_testing.calculateInvariant(
            scale(balances_after), scale(sqrt_alpha), scale(sqrt_beta)
        )

    # assert invariant_after >= invariant
    if check_sol_inv:
        assert invariant_sol_after >= invariant_sol

    return invariant_after, invariant


def mtest_invariant_match(
    gyro_two_math_testing,
    balances: Tuple[int, int],
    sqrt_alpha,
    sqrt_beta,
):
    assume(not faulty_params(balances, sqrt_alpha, sqrt_beta))

    invariant = math_implementation.calculateInvariant(
        to_decimal(balances), to_decimal(sqrt_alpha), to_decimal(sqrt_beta)
    )

    invariant_sol = gyro_two_math_testing.calculateInvariant(
        scale(balances), scale(sqrt_alpha), scale(sqrt_beta)
    )

    assert unscale(D(invariant_sol)) == invariant.approxed(abs=D("2e-18"))


def mtest_invariant_across_liquidityInvariantUpdate(
    gyro_two_math_testing, params, params_invariantUpdate
):
    sqrt_alpha, sqrt_beta = params
    balances, bpt_supply, isIncrease, dsupply = params_invariantUpdate
    invariant_before = math_implementation.calculateInvariant(
        balances, sqrt_alpha, sqrt_beta
    )
    if isIncrease:
        dBalances = pool_math_implementation.calcAllTokensInGivenExactBptOut(
            balances, dsupply, bpt_supply
        )
        new_balances = [
            balances[0] + dBalances[0],
            balances[1] + dBalances[1],
        ]
    else:
        dBalances = pool_math_implementation.calcTokensOutGivenExactBptIn(
            balances, dsupply, bpt_supply
        )
        new_balances = [
            balances[0] - dBalances[0],
            balances[1] - dBalances[1],
        ]

    invariant_updated = unscale(
        gyro_two_math_testing.liquidityInvariantUpdate(
            scale(invariant_before), scale(dsupply), scale(bpt_supply), isIncrease
        )
    )

    invariant_after = math_implementation.calculateInvariant(
        new_balances, sqrt_alpha, sqrt_beta
    )
    if isIncrease and invariant_updated < invariant_after:
        loss = calculate_loss(
            invariant_updated - invariant_after, invariant_after, new_balances
        )
    elif not isIncrease and invariant_updated > invariant_after:
        loss = calculate_loss(
            invariant_after - invariant_updated, invariant_after, new_balances
        )
    else:
        loss = (D(0), D(0))
    loss_ub = loss[0] * sqrt_beta**2 + loss[1]
    assert abs(loss_ub) < D("1e-5")


def calculate_loss(delta_invariant, invariant, balances):
    # delta_balance_A = delta_invariant / invariant * balance_A
    factor = to_decimal(delta_invariant / invariant)
    return (to_decimal(balances[0]) * factor, to_decimal(balances[1]) * factor)


def test_calc_out_given_in_tob(gyro_two_math_testing):
    """One specific test by ToB that failed at some earlier point due to rounding issues.

    Adapted to fit the changed call signature of calcOutGivenIn()."""
    balanceIn = 3
    balanceOut = 200847740110042258154349940970401
    amountIn = 0  # token0

    sqrtAlpha = 0.97
    sqrtBeta = 1.02

    currentInvariant = gyro_two_math_testing.calculateInvariant(
        [balanceIn, balanceOut],  # balances
        sqrtAlpha * 10**18,  # sqrtAlpha
        sqrtBeta * 10**18,  # sqrtBeta
    )

    virtualParamIn = currentInvariant / sqrtBeta
    virtualParamOut = currentInvariant * sqrtAlpha

    result = gyro_two_math_testing.calcOutGivenIn(
        balanceIn,  # balanceIn,
        balanceOut,  # balanceOut,
        amountIn * 10**18,  # amountIn,
        virtualParamIn,  # virtualParamIn,
        virtualParamOut,  # virtualParamOut,
    )

    assert result < 10**18

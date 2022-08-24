from decimal import Decimal
from typing import Tuple

import hypothesis.strategies as st
from brownie.test import given
from brownie import reverts
from hypothesis import assume, settings, event
from tests.cpmmv2 import math_implementation
from tests.libraries import pool_math_implementation
from tests.support.util_common import BasicPoolParameters
from tests.support.utils import scale, to_decimal, qdecimals, unscale

from tests.support.quantized_decimal import QuantizedDecimal as D

billion_balance_strategy = st.integers(min_value=0, max_value=100_000_000_000)

# this is a multiplicative separation
# This is consistent with tightest price range of 0.9999 - 1.0001
MIN_SQRTPARAM_SEPARATION = to_decimal("1.0001")
MIN_BAL_RATIO = to_decimal("0")
MIN_FEE = D("0.0002")


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


@st.composite
def gen_params(draw):
    sqrt_alpha = draw(qdecimals("0.05", "19"))
    sqrt_beta = draw(qdecimals(sqrt_alpha.raw, "20.0"))
    assume(sqrt_beta.raw >= sqrt_alpha.raw * D("1.001"))
    return (sqrt_alpha, sqrt_beta)


@st.composite
def gen_params_stable(draw):
    sqrt_alpha = draw(qdecimals("0.9", "1.0"))
    sqrt_beta = draw(qdecimals(sqrt_alpha.raw, "1.1"))
    assume(sqrt_beta.raw >= sqrt_alpha.raw * MIN_SQRTPARAM_SEPARATION)
    return (sqrt_alpha, sqrt_beta)


@st.composite
def gen_params_eth_btc(draw):
    sqrt_alpha = draw(qdecimals("0.1", "0.31"))  # alpha in [0.01, 0.1]
    sqrt_beta = draw(qdecimals(sqrt_alpha.raw, "0.45"))  # beta in [alpha, 0.2]
    assume(sqrt_beta.raw >= sqrt_alpha.raw * D("1.1"))
    return (sqrt_alpha, sqrt_beta)


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
    sqrt_alpha, sqrt_beta = draw(gen_params())
    balances = draw(gen_balances())
    assume(balances[0] > 0 and balances[1] > 0)
    invariant = math_implementation.calculateInvariant(balances, sqrt_alpha, sqrt_beta)
    dinvariant = draw(
        qdecimals(-invariant, 2 * invariant)
    )  # Upper bound kinda arbitrary
    assume(abs(dinvariant) > D("1E-10"))  # Only relevant updates
    return sqrt_alpha, sqrt_beta, dinvariant


################################################################################
### test invariant underestimated
@given(
    balances=gen_balances(),
    params=gen_params(),
)
def test_invariant_match(gyro_two_math_testing, balances, params):
    sqrt_alpha, sqrt_beta = params
    mtest_invariant_match(
        gyro_two_math_testing,
        balances,
        sqrt_alpha,
        sqrt_beta,
    )


@given(
    balances=gen_balances(),
    params=gen_params_stable(),
)
def test_invariant_match_stable(gyro_two_math_testing, balances, params):
    sqrt_alpha, sqrt_beta = params
    mtest_invariant_match(
        gyro_two_math_testing,
        balances,
        sqrt_alpha,
        sqrt_beta,
    )


@given(
    balances=gen_balances(),
    params=gen_params_eth_btc(),
)
def test_invariant_match_eth_btc(gyro_two_math_testing, balances, params):
    sqrt_alpha, sqrt_beta = params
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
    amount_out=st.decimals(min_value="1", max_value="1000000", places=4),
    params=gen_params(),
)
def test_invariant_across_calcInGivenOut(
    gyro_two_math_testing, amount_out, balances: Tuple[int, int], params
):
    sqrt_alpha, sqrt_beta = params
    # check_sol_inv set to false, which is ok as long as the 'truer' invariant calculated in python doesn't decrease
    invariant_after, invariant = mtest_invariant_across_calcInGivenOut(
        gyro_two_math_testing, amount_out, balances, sqrt_alpha, sqrt_beta, False
    )
    assert invariant_after >= invariant


######
@given(
    balances=gen_balances(),
    amount_out=st.decimals(min_value="1", max_value="1000000", places=4),
    params=gen_params_stable(),
)
def test_invariant_across_calcInGivenOut_stable(
    gyro_two_math_testing, amount_out, balances: Tuple[int, int], params
):
    sqrt_alpha, sqrt_beta = params
    invariant_after, invariant = mtest_invariant_across_calcInGivenOut(
        gyro_two_math_testing, amount_out, balances, sqrt_alpha, sqrt_beta, False
    )
    assert invariant_after >= invariant


######
@given(
    balances=gen_balances(),
    amount_out=st.decimals(min_value="1", max_value="1000000", places=4),
    params=gen_params_eth_btc(),
)
def test_invariant_across_calcInGivenOut_eth_btc(
    gyro_two_math_testing, amount_out, balances: Tuple[int, int], params
):
    sqrt_alpha, sqrt_beta = params
    amount_out_1 = amount_out * (sqrt_beta ** 2 + sqrt_alpha ** 2) / 2
    invariant_after, invariant = mtest_invariant_across_calcInGivenOut(
        gyro_two_math_testing, amount_out_1, balances, sqrt_alpha, sqrt_beta, False
    )
    assert invariant_after >= invariant

    # test the transpose case also
    sqrt_alpha_t, sqrt_beta_t = (D(1) / sqrt_beta, D(1) / sqrt_alpha)
    amount_out_2 = amount_out * (sqrt_beta_t ** 2 + sqrt_alpha_t ** 2) / 2
    invariant_after, invariant = mtest_invariant_across_calcInGivenOut(
        gyro_two_math_testing, amount_out_2, balances, sqrt_alpha_t, sqrt_beta_t, False
    )
    assert invariant_after >= invariant


################################################################################
### test calcOutGivenIn for invariant change


# @given(
@given(
    balances=gen_balances(),
    amount_in=st.decimals(min_value="1", max_value="1000000", places=4),
    params=gen_params(),
)
def test_invariant_across_calcOutGivenIn(
    gyro_two_math_testing, amount_in, balances: Tuple[int, int], params
):
    sqrt_alpha, sqrt_beta = params
    # check_sol_inv set to false, which is ok as long as the 'truer' invariant calculated in python doesn't decrease
    invariant_after, invariant = mtest_invariant_across_calcOutGivenIn(
        gyro_two_math_testing, amount_in, balances, sqrt_alpha, sqrt_beta, False
    )
    assert invariant_after >= invariant


######
@given(
    balances=gen_balances(),
    amount_in=st.decimals(min_value="1", max_value="1000000", places=4),
    params=gen_params_stable(),
)
def test_invariant_across_calcOutGivenIn_stable(
    gyro_two_math_testing, amount_in, balances: Tuple[int, int], params
):
    sqrt_alpha, sqrt_beta = params
    invariant_after, invariant = mtest_invariant_across_calcOutGivenIn(
        gyro_two_math_testing, amount_in, balances, sqrt_alpha, sqrt_beta, False
    )
    assert invariant_after >= invariant


######
@given(
    balances=gen_balances(),
    amount_in=st.decimals(min_value="1", max_value="1000000", places=4),
    params=gen_params_eth_btc(),
)
def test_invariant_across_calcOutGivenIn_eth_btc(
    gyro_two_math_testing, amount_in, balances: Tuple[int, int], params
):
    sqrt_alpha, sqrt_beta = params
    amount_in_1 = amount_in * (sqrt_beta ** 2 + sqrt_beta ** 2) / 2
    invariant_after, invariant = mtest_invariant_across_calcOutGivenIn(
        gyro_two_math_testing, amount_in_1, balances, sqrt_alpha, sqrt_beta, False
    )
    assert invariant_after >= invariant

    # test the transpose case also
    sqrt_alpha_t, sqrt_beta_t = (D(1) / sqrt_beta, D(1) / sqrt_alpha)
    amount_in_2 = amount_in * (sqrt_beta_t ** 2 + sqrt_alpha_t ** 2) / 2
    invariant_after, invariant = mtest_invariant_across_calcOutGivenIn(
        gyro_two_math_testing, amount_in_2, balances, sqrt_alpha_t, sqrt_beta_t, False
    )
    assert invariant_after >= invariant


################################################################################
### test liquidity invariant update for invariant change


@given(params_invariantUpdate=gen_params_liquidityUpdate(), params=gen_params())
def test_invariant_across_liquidityInvariantUpdate(
    gyro_two_math_testing, params, params_invariantUpdate
):
    mtest_invariant_across_liquidityInvariantUpdate(
        gyro_two_math_testing, params, params_invariantUpdate
    )


@given(params_invariantUpdate=gen_params_liquidityUpdate(), params=gen_params_stable())
def test_invariant_across_liquidityInvariantUpdate_stable(
    gyro_two_math_testing, params, params_invariantUpdate
):
    mtest_invariant_across_liquidityInvariantUpdate(
        gyro_two_math_testing, params, params_invariantUpdate
    )


@given(params_invariantUpdate=gen_params_liquidityUpdate(), params=gen_params_eth_btc())
def test_invariant_across_liquidityInvariantUpdate_eth_btc(
    gyro_two_math_testing, params, params_invariantUpdate
):
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
    check_price_impact_direction: bool = True
):
    assume(amount_out <= to_decimal("0.3") * (balances[1]))
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

    bal_out_new, bal_in_new = (balances[0] + in_amount, balances[1] - amount_out)
    if bal_out_new > bal_in_new:
        within_bal_ratio = bal_in_new / bal_out_new > MIN_BAL_RATIO
    else:
        within_bal_ratio = bal_out_new / bal_in_new > MIN_BAL_RATIO

    if in_amount <= to_decimal("0.3") * balances[0] and within_bal_ratio:
        in_amount_sol = unscale(
            gyro_two_math_testing.calcInGivenOut(
                scale(balances[0]),
                scale(balances[1]),
                scale(amount_out),
                scale(virtual_param_in),
                scale(virtual_param_out),
            )
        )
    elif not within_bal_ratio:
        with reverts("BAL#357"):  # MIN_BAL_RATIO
            gyro_two_math_testing.calcInGivenOut(
                scale(balances[0]),
                scale(balances[1]),
                scale(amount_out),
                scale(virtual_param_in),
                scale(virtual_param_out),
            )
        return D(0), D(0)
    else:
        with reverts("BAL#304"):  # MAX_IN_RATIO
            gyro_two_math_testing.calcInGivenOut(
                scale(balances[0]),
                scale(balances[1]),
                scale(amount_out),
                scale(virtual_param_in),
                scale(virtual_param_out),
            )
        return D(0), D(0)

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
    assume(amount_in <= to_decimal("0.3") * (balances[0]))
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

    bal_out_new, bal_in_new = (balances[0] + amount_in, balances[1] - out_amount)
    if bal_out_new > bal_in_new:
        within_bal_ratio = bal_in_new / bal_out_new > MIN_BAL_RATIO
    else:
        within_bal_ratio = bal_out_new / bal_in_new > MIN_BAL_RATIO

    if (
        out_amount <= to_decimal("0.3") * balances[1]
        and within_bal_ratio
        and out_amount >= 0
    ):
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
        return
    elif not within_bal_ratio:
        with reverts("BAL#357"):  # MIN_BAL_RATIO
            gyro_two_math_testing.calcOutGivenIn(
                scale(balances[0]),
                scale(balances[1]),
                scale(amount_in),
                scale(virtual_param_in),
                scale(virtual_param_out),
            )
        return 0, 0
    else:
        with reverts("BAL#305"):  # MAX_OUT_RATIO
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
    loss_ub = loss[0] * sqrt_beta ** 2 + loss[1]
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
        sqrtAlpha * 10 ** 18,  # sqrtAlpha
        sqrtBeta * 10 ** 18,  # sqrtBeta
    )

    virtualParamIn = currentInvariant / sqrtBeta
    virtualParamOut = currentInvariant * sqrtAlpha

    result = gyro_two_math_testing.calcOutGivenIn(
        balanceIn,  # balanceIn,
        balanceOut,  # balanceOut,
        amountIn * 10 ** 18,  # amountIn,
        virtualParamIn,  # virtualParamIn,
        virtualParamOut,  # virtualParamOut,
    )

    assert result < 10 ** 18
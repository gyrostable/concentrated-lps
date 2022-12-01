from math import sin, cos

import hypothesis.strategies as st

# from pyrsistent import Invariant
from brownie.test import given
from hypothesis import assume, example, settings, HealthCheck
import pytest

from tests.geclp import eclp as mimpl
from tests.geclp import eclp_prec_implementation as prec_impl
from tests.geclp import util
from tests.support.quantized_decimal import QuantizedDecimal as D
from tests.support.types import *
from tests.support.util_common import BasicPoolParameters, gen_balances
from tests.support.utils import qdecimals, unscale


# this is a multiplicative separation
# This is consistent with tightest price range of beta - alpha >= MIN_PRICE_SEPARATION
MIN_PRICE_SEPARATION = D("0.001")
MAX_IN_RATIO = D("0.3")
MAX_OUT_RATIO = D("0.3")

MIN_BALANCE_RATIO = D(0)  # D("1e-5")
MIN_FEE = D(0)  # D("0.0002")

# this determines whether derivedParameters are calculated in solidity or not
DP_IN_SOL = False


bpool_params = BasicPoolParameters(
    MIN_PRICE_SEPARATION,
    MAX_IN_RATIO,
    MAX_OUT_RATIO,
    MIN_BALANCE_RATIO,
    MIN_FEE,
    int(D("1e11")),
)


################################################################################
### parameter selection


@st.composite
def gen_params(draw):
    phi = 0
    # The range of prices is relatively tight b/c we otherwise generate a lot of invalid examples where the price
    # range is small and offset from 1, in which case Aχ * Aχ is too close to 1 in the invariant computation formula.
    # In practice, this can be prevented by rescaling.
    alpha = draw(qdecimals("0.2", "4.0"))
    beta = draw(qdecimals(alpha.raw + MIN_PRICE_SEPARATION, "5.0"))
    s = sin(phi)
    c = cos(phi)
    l = D(1)
    return ECLPMathParams(alpha, beta, D(c), D(s), l)


@st.composite
def gen_params_eclp_liquidityUpdate(draw):
    params = draw(gen_params())
    balances = draw(gen_balances(2, bpool_params))
    bpt_supply = draw(qdecimals(D("1e-4") * max(balances), D("1e6") * max(balances)))
    isIncrease = draw(st.booleans())
    if isIncrease:
        dsupply = draw(qdecimals(D("1e-5"), D("1e4") * bpt_supply))
    else:
        dsupply = draw(qdecimals(D("1e-5"), D("0.99") * bpt_supply))
    return params, balances, bpt_supply, isIncrease, dsupply


@st.composite
def gen_params_swap_given_in(draw):
    params = draw(gen_params())
    balances = draw(gen_balances(2, bpool_params))
    tokenInIsToken0 = draw(st.booleans())
    i = 0 if tokenInIsToken0 else 1
    amountIn = draw(
        qdecimals(
            min_value=min(1, D("0.2") * balances[i]),
            max_value=D("0.3") * balances[i],
        )
    )
    return params, balances, tokenInIsToken0, amountIn


@st.composite
def gen_params_swap_given_out(draw):
    params = draw(gen_params())
    balances = draw(gen_balances(2, bpool_params))
    tokenInIsToken0 = draw(st.booleans())
    i = 1 if tokenInIsToken0 else 0
    amountOut = draw(
        qdecimals(
            min_value=min(1, D("0.2") * balances[i]),
            max_value=D("0.3") * balances[i],
        )
    )
    return params, balances, tokenInIsToken0, amountOut


################################################################################
### test calcOutGivenIn for invariant change
# @settings(max_examples=1_000)
@settings(suppress_health_check=[HealthCheck.filter_too_much])
@given(params_swap_given_in=gen_params_swap_given_in())
def test_invariant_across_calcOutGivenIn(params_swap_given_in, gyro_eclp_math_testing):
    params, balances, tokenInIsToken0, amountIn = params_swap_given_in
    # the difference is whether invariant is calculated in python or solidity, but swap calculation still in solidity
    loss_py, loss_sol = util.mtest_invariant_across_calcOutGivenIn(
        params,
        balances,
        amountIn,
        tokenInIsToken0,
        DP_IN_SOL,
        bpool_params,
        gyro_eclp_math_testing,
    )

    # compare upper bound on loss in y terms
    loss_py_ub = -loss_py[0] * params.beta - loss_py[1]
    loss_sol_ub = -loss_sol[0] * params.beta - loss_sol[1]
    assert loss_py_ub == 0  # < D("5e-4")
    assert loss_sol_ub == 0  # < D("5e-4")


################################################################################
### test calcInGivenOut for invariant change
@settings(suppress_health_check=[HealthCheck.filter_too_much])
@given(
    params_swap_given_out=gen_params_swap_given_out(),
)
def test_invariant_across_calcInGivenOut(params_swap_given_out, gyro_eclp_math_testing):
    params, balances, tokenInIsToken0, amountOut = params_swap_given_out
    # the difference is whether invariant is calculated in python or solidity, but swap calculation still in solidity
    loss_py, loss_sol = util.mtest_invariant_across_calcInGivenOut(
        params,
        balances,
        amountOut,
        tokenInIsToken0,
        DP_IN_SOL,
        bpool_params,
        gyro_eclp_math_testing,
    )

    # compare upper bound on loss in y terms
    loss_py_ub = -loss_py[0] * params.beta - loss_py[1]
    loss_sol_ub = -loss_sol[0] * params.beta - loss_sol[1]
    assert loss_py_ub == 0  # < D("5e-4")
    assert loss_sol_ub == 0  # < D("5e-4")


################################################################################
### test for zero tokens in
@given(params=gen_params(), balances=gen_balances(2, bpool_params))
def test_zero_tokens_in(gyro_eclp_math_testing, params, balances):
    util.mtest_zero_tokens_in(gyro_eclp_math_testing, params, balances)


################################################################################
### test liquidityInvariantUpdate for L change


@given(params_eclp_invariantUpdate=gen_params_eclp_liquidityUpdate())
def test_invariant_across_liquidityInvariantUpdate(
    gyro_eclp_math_testing, params_eclp_invariantUpdate
):
    util.mtest_invariant_across_liquidityInvariantUpdate(
        params_eclp_invariantUpdate, gyro_eclp_math_testing
    )


@pytest.mark.skip(reason="Not needed if MIN_BAL_RATIO=1e-5")
def test_subtract_overflow_example(gyro_eclp_math_testing):
    params = ECLPMathParams(
        alpha=D("10.591992670000000000"),
        beta=D("10.593727349591836734"),
        c=D("1.000000000000000000"),
        s=D("0E-18"),
        l=D("1.000000000000000000"),
    )
    balances = (13849421, 1022)
    amountIn = D("1.000000000000000000")
    tokenInIsToken0 = False

    invariant_py, invariant_sol = util.mtest_calculateInvariant(
        params, balances, DP_IN_SOL, gyro_eclp_math_testing
    )
    balanceInNew = D(balances[1]) + amountIn
    x, x_sol = util.mtest_calcXGivenY(
        params, balanceInNew, unscale(invariant_sol), DP_IN_SOL, gyro_eclp_math_testing
    )
    util.mtest_maxBalances(params, unscale(invariant_sol), gyro_eclp_math_testing)
    # assert D(balances[0]) > unscale(D(x_sol))
    util.mtest_calcOutGivenIn(
        params, balances, amountIn, tokenInIsToken0, DP_IN_SOL, gyro_eclp_math_testing
    )

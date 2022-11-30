from math import pi, sin, cos

import hypothesis.strategies as st
import pytest

# from pyrsistent import Invariant
from brownie.test import given
from hypothesis import assume, settings, HealthCheck
import pytest

from tests.cemm import cemm as mimpl
from tests.cemm import cemm_prec_implementation as prec_impl
from tests.cemm import util
from tests.support.quantized_decimal import QuantizedDecimal as D
from tests.support.types import *
from tests.support.util_common import BasicPoolParameters, gen_balances
from tests.support.utils import qdecimals


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
    phi_degrees = draw(st.floats(45, 50))
    phi = phi_degrees / 360 * 2 * pi

    # Price bounds. Choose s.t. the 'peg' lies approximately within the bounds (within 30%).
    # It'd be nonsensical if this was not the case: Why are we using an ellipse then?!
    peg = D(1)  # = price where the flattest point of the ellipse lies.
    alpha = draw(qdecimals("0.05", "0.999"))
    beta = draw(qdecimals("1.001", "1.1"))
    s = sin(phi)
    c = cos(phi)
    l = draw(qdecimals("5", "1e8"))
    return CEMMMathParams(alpha, beta, D(c), D(s), l)


@st.composite
def gen_params_cemm_liquidityUpdate(draw):
    params = draw(gen_params())
    balances = draw(gen_balances(2, bpool_params))
    bpt_supply = draw(qdecimals(D("1e-1") * max(balances), D("1e4") * max(balances)))
    isIncrease = draw(st.booleans())
    if isIncrease:
        dsupply = draw(qdecimals(D("1e-5"), D("1e2") * bpt_supply))
    else:
        dsupply = draw(qdecimals(D("1e-5"), D("0.5") * bpt_supply))
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
@given(
    params_swap_given_in=gen_params_swap_given_in(),
)
def test_invariant_across_calcOutGivenIn(params_swap_given_in, gyro_cemm_math_testing):
    params, balances, tokenInIsToken0, amountIn = params_swap_given_in
    # the difference is whether invariant is calculated in python or solidity, but swap calculation still in solidity
    loss_py, loss_sol = util.mtest_invariant_across_calcOutGivenIn(
        params,
        balances,
        amountIn,
        tokenInIsToken0,
        DP_IN_SOL,
        bpool_params,
        gyro_cemm_math_testing,
    )

    # compare upper bound on loss in y terms
    loss_py_ub = -loss_py[0] - loss_py[1]
    loss_sol_ub = -loss_sol[0] - loss_sol[1]
    assert loss_py_ub == 0  # < D("5e-3")
    assert loss_sol_ub == 0  # < D("5e-3")


################################################################################
### test calcInGivenOut for invariant change
@settings(suppress_health_check=[HealthCheck.filter_too_much])
@given(
    params_swap_given_out=gen_params_swap_given_out(),
)
def test_invariant_across_calcInGivenOut(params_swap_given_out, gyro_cemm_math_testing):
    params, balances, tokenInIsToken0, amountOut = params_swap_given_out
    # the difference is whether invariant is calculated in python or solidity, but swap calculation still in solidity
    loss_py, loss_sol = util.mtest_invariant_across_calcInGivenOut(
        params,
        balances,
        amountOut,
        tokenInIsToken0,
        DP_IN_SOL,
        bpool_params,
        gyro_cemm_math_testing,
    )

    # compare upper bound on loss in y terms
    loss_py_ub = -loss_py[0] - loss_py[1]
    loss_sol_ub = -loss_sol[0] - loss_sol[1]
    assert loss_py_ub == 0  # < D("5e-3")
    assert loss_sol_ub == 0  # < D("5e-3")


################################################################################
### test for zero tokens in
@given(params=gen_params(), balances=gen_balances(2, bpool_params))
def test_zero_tokens_in(gyro_cemm_math_testing, params, balances):
    util.mtest_zero_tokens_in(gyro_cemm_math_testing, params, balances)


################################################################################
### test liquidityInvariantUpdate for L change


@given(params_cemm_invariantUpdate=gen_params_cemm_liquidityUpdate())
def test_invariant_across_liquidityInvariantUpdate(
    gyro_cemm_math_testing, params_cemm_invariantUpdate
):
    util.mtest_invariant_across_liquidityInvariantUpdate(
        params_cemm_invariantUpdate, gyro_cemm_math_testing
    )

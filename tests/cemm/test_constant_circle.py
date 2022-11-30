import functools
from decimal import Decimal
from math import pi, sin, cos
from typing import Tuple
from unicodedata import decimal

import hypothesis.strategies as st
from _pytest.python_api import ApproxDecimal

# from pyrsistent import Invariant
from brownie.test import given
from brownie import reverts
from hypothesis import assume, settings, event, example
from tests.cemm import cemm as mimpl
from tests.cemm import util
from tests.support.utils import scale, to_decimal, qdecimals, unscale
from tests.support.types import *
from tests.support.quantized_decimal import QuantizedDecimal as D

billion_balance_strategy = st.integers(min_value=0, max_value=10_000_000_000)

# this is a multiplicative separation
# This is consistent with tightest price range of beta - alpha >= MIN_PRICE_SEPARATION
MIN_PRICE_SEPARATION = D("0.001")
MAX_IN_RATIO = D("0.3")
MAX_OUT_RATIO = D("0.3")

MIN_BALANCE_RATIO = D("1e-5")
MIN_FEE = D("0.0002")

# this determines whether derivedParameters are calculated in solidity or not
DP_IN_SOL = False


bpool_params = util.Basic_Pool_Parameters(
    MIN_PRICE_SEPARATION, MAX_IN_RATIO, MAX_OUT_RATIO, MIN_BALANCE_RATIO, MIN_FEE
)


################################################################################
### parameter selection


@st.composite
def gen_params(draw):
    phi = 0
    alpha = draw(qdecimals("0.05", "19.0"))
    beta = draw(qdecimals(alpha.raw, "20.0"))
    assume(beta.raw - alpha.raw >= MIN_PRICE_SEPARATION)
    s = sin(phi)
    c = cos(phi)
    l = D(1)
    return CEMMMathParams(alpha, beta, D(c), D(s), l)


@st.composite
def gen_params_cemm_dinvariant(draw):
    params = draw(gen_params())
    mparams = util.params2MathParams(params)
    balances = draw(util.gen_balances())
    assume(balances[0] > 0 and balances[1] > 0)
    cemm = mimpl.CEMM.from_x_y(balances[0], balances[1], mparams)
    dinvariant = draw(
        qdecimals(-cemm.r.raw, 2 * cemm.r.raw)
    )  # Upper bound kinda arbitrary
    assume(abs(dinvariant) > D("1E-10"))  # Only relevant updates
    return params, cemm, dinvariant


################################################################################
### test calcOutGivenIn for invariant change
# @settings(max_examples=1_000)
@given(
    params=gen_params(),
    balances=util.gen_balances(),
    amountIn=qdecimals(min_value=1, max_value=1_000_000_000, places=4),
    tokenInIsToken0=st.booleans(),
)
@example(
    params=CEMMMathParams(
        alpha=D("10.591992670000000000"),
        beta=D("10.593727349591836734"),
        c=D("1.000000000000000000"),
        s=D("0E-18"),
        l=D("1.000000000000000000"),
    ),
    balances=(13849421, 1022),
    amountIn=D("1.000000000000000000"),
    tokenInIsToken0=False,
)
def test_invariant_across_calcOutGivenIn(
    params, balances, amountIn, tokenInIsToken0, gyro_cemm_math_testing
):
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
    loss_py_ub = -loss_py[0] * params.beta - loss_py[1]
    loss_sol_ub = -loss_sol[0] * params.beta - loss_sol[1]
    assert loss_py_ub < D("5e-4")
    assert loss_sol_ub < D("5e-4")


################################################################################
### test calcInGivenOut for invariant change
@given(
    params=gen_params(),
    balances=util.gen_balances(),
    amountOut=qdecimals(min_value=1, max_value=1_000_000_000, places=4),
    tokenInIsToken0=st.booleans(),
)
def test_invariant_across_calcInGivenOut(
    params, balances, amountOut, tokenInIsToken0, gyro_cemm_math_testing
):
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
    loss_py_ub = -loss_py[0] * params.beta - loss_py[1]
    loss_sol_ub = -loss_sol[0] * params.beta - loss_sol[1]
    assert loss_py_ub < D("5e-4")
    assert loss_sol_ub < D("5e-4")


################################################################################
### test liquidityInvariantUpdate for L change


@given(params_cemm_dinvariant=gen_params_cemm_dinvariant())
def test_invariant_across_liquidityInvariantUpdate(
    gyro_cemm_math_testing, params_cemm_dinvariant
):
    util.mtest_invariant_across_liquidityInvariantUpdate(
        gyro_cemm_math_testing, params_cemm_dinvariant, DP_IN_SOL
    )


def test_subtract_overflow_example(gyro_cemm_math_testing):
    params = CEMMMathParams(
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
        params, balances, DP_IN_SOL, gyro_cemm_math_testing
    )
    balanceInNew = D(balances[1]) + amountIn
    x, x_sol = util.mtest_calcXGivenY(
        params, balanceInNew, unscale(invariant_sol), DP_IN_SOL, gyro_cemm_math_testing
    )
    util.mtest_maxBalances(params, unscale(invariant_sol), gyro_cemm_math_testing)
    # assert D(balances[0]) > unscale(D(x_sol))
    util.mtest_calcOutGivenIn(
        params, balances, amountIn, tokenInIsToken0, DP_IN_SOL, gyro_cemm_math_testing
    )

import os

import hypothesis.strategies as st
import pytest
from brownie.test import given
from hypothesis import assume, settings, example

from tests.cemm import cemm as mimpl
from tests.cemm import util
from tests.support.quantized_decimal import QuantizedDecimal as D
from tests.support.quantized_decimal import QuantizedDecimal as Decimal
from tests.support.types import *
from tests.support.util_common import (
    gen_balances,
    gen_balances_vector,
    BasicPoolParameters,
)

# from tests.cemm.util import params2MathParams, mathParams2DerivedParams, gen_params, gen_balances, gen_balances_vector, \
#    gen_params_cemm_dinvariant
from tests.support.utils import scale, to_decimal, qdecimals, unscale

# this is a multiplicative separation
# This is consistent with tightest price range of beta - alpha >= MIN_PRICE_SEPARATION
MIN_PRICE_SEPARATION = to_decimal("0.0001")

bpool_params = BasicPoolParameters(
    MIN_PRICE_SEPARATION, D("0.3"), D("0.3"), D(0), D(0), int(D("1e11"))
)

# this determines whether derivedParameters are calculated in solidity or not
DP_IN_SOL = True

MAX_EXAMPLES = 100 if "CI" in os.environ else 1_000


def faulty_params(balances, params: CEMMMathParams):
    balances = [to_decimal(b) for b in balances]
    if balances[0] == 0 and balances[1] == 0:
        return True
    return 0 >= params.beta - params.alpha >= MIN_PRICE_SEPARATION


# Sry monkey patching...
# Default absolute tolerance is 1e-12 but we're scaled by 1e18, so we actually want 1e6.
# Note that the relative threshold should *not* be scaled, but it still needs to be mentioned, o/w it's assumed to be equal to 0.
# For some calculations, we choose laxer bounds of abs=1e-3 (scaled: 1e15) and rel=1e-6.
D.approxed_scaled = lambda self: self.approxed(abs=D("1E6"), rel=D("1E-6"))
D.our_approxed_scaled = lambda self: self.approxed(abs=D("1E15"), rel=D("1E-6"))


@pytest.mark.skip(reason="No longer implemented")
@given(params=util.gen_params(), t=gen_balances_vector(bpool_params))
def test_mulAinv(params: CEMMMathParams, t: Vector2, gyro_cemm_math_testing):
    util.mtest_mulAinv(params, t, gyro_cemm_math_testing)


@given(params=util.gen_params(), t=gen_balances_vector(bpool_params))
def test_mulA(params: CEMMMathParams, t: Vector2, gyro_cemm_math_testing):
    util.mtest_mulA(params, t, gyro_cemm_math_testing)


@st.composite
def gen_params_px(draw):
    params = draw(util.gen_params())
    px = draw(qdecimals(params.alpha.raw, params.beta.raw))
    return params, px


@given(params_px=gen_params_px())
def test_zeta(params_px, gyro_cemm_math_testing):
    util.mtest_zeta(params_px, gyro_cemm_math_testing)


@given(pxc=qdecimals("-1E16", "1E16"))
def test_eta(pxc, gyro_cemm_math_testing):
    # eta is very precise in the grand scheme of things, but of course we can't be more precise than sqrt() across the range of values we care about.
    # Note that eta does *not* depend on params.
    res_sol = gyro_cemm_math_testing.eta(scale(pxc))
    res_math = mimpl.eta(pxc)
    assert int(res_sol[0]) == scale(res_math[0]).approxed(abs=D("1e5"), rel=D("1e-16"))
    assert int(res_sol[1]) == scale(res_math[1]).approxed(abs=D("1e5"), rel=D("1e-16"))


@given(params_px=gen_params_px())
def test_tau(params_px, gyro_cemm_math_testing):
    util.mtest_tau(params_px, gyro_cemm_math_testing)


@pytest.mark.skip(reason="Needs refactor")
@given(params=util.gen_params())
def test_mkDerivedParams(params, gyro_cemm_math_testing):
    util.mtest_mkDerivedParams(params, gyro_cemm_math_testing)


@pytest.mark.skip(reason="Needs refactor")
@given(params=util.gen_params())
def test_validateParamsAll(params, gyro_cemm_math_testing):
    util.mtest_validateParamsAll(params, gyro_cemm_math_testing)


### Virtual Offsets and Max Balances ###


@pytest.mark.skip(reason="Needs refactor")
@given(params=util.gen_params(), invariant=util.gen_synthetic_invariant())
@example(
    params=CEMMMathParams(
        alpha=Decimal("0.302137159231720000"),
        beta=Decimal("1.005000000000000000"),
        c=Decimal("0.836049436859842232"),
        s=Decimal("0.548654116111727208"),
        l=Decimal("2.960000000000000000"),
    ),
    invariant=Decimal("32034653686.598895308700000000"),
)
def test_virtualOffsets_noderived(params, invariant, gyro_cemm_math_testing):
    util.mtest_virtualOffsets_noderived(params, invariant, gyro_cemm_math_testing)


@pytest.mark.skip(reason="Needs refactor")
@settings(max_examples=MAX_EXAMPLES)
@given(params=util.gen_params(), invariant=util.gen_synthetic_invariant())
@example(
    params=CEMMMathParams(
        alpha=Decimal("0.302137159231720000"),
        beta=Decimal("1.005000000000000000"),
        c=Decimal("0.836049436859842232"),
        s=Decimal("0.548654116111727208"),
        l=Decimal("2.960000000000000000"),
    ),
    invariant=Decimal("32034653686.598895308700000000"),
)
def test_virtualOffsets_with_derived(params, invariant, gyro_cemm_math_testing):
    util.mtest_virtualOffsets_with_derived(params, invariant, gyro_cemm_math_testing)


@settings(max_examples=MAX_EXAMPLES)
@given(params=util.gen_params(), invariant=util.gen_synthetic_invariant())
def test_maxBalances(params, invariant, gyro_cemm_math_testing):
    util.mtest_maxBalances(params, invariant, gyro_cemm_math_testing)


# We don't test chi b/c there is no separate function for it in the math implementation. This is tested in
# calculateInvariant()

# NOTE: This test FAILS when the parameters can be arbitrary. However, these functions *are* tested the way they're
# actually used below.

# @given(
#     qparams=st.builds(CEMMMathQParams, qdecimals(), qdecimals(), qdecimals())
# )
# def test_solveQuadratic(qparams: CEMMMathQParams, gyro_cemm_math_testing):
#     a, b, c = qparams
#     assume(a != 0)
#
#     d = b*b - D(4)*a*c
#     if d < 0:
#         with reverts("SafeCast: value must be positive"):
#             gyro_cemm_math_testing.solveQuadraticPlus(scale(qparams))
#         with reverts("SafeCast: value must be positive"):
#             gyro_cemm_math_testing.solveQuadraticMinus(scale(qparams))
#         return
#
#     # We don't compare to the real solutions (see commented-out below). Accuracy is hard to check here. Instead, we
#     # check against 0.
#     xplus_sol = gyro_cemm_math_testing.solveQuadraticPlus(scale(qparams))
#     xminus_sol = gyro_cemm_math_testing.solveQuadraticMinus(scale(qparams))
#
#     xplus = (-b + d.sqrt()) / (D(2)*a)
#     xminus = (-b - d.sqrt()) / (D(2)*a)
#
#     # abs tolerances are what we use for the CPMMv3 to test calculating the invariant. It's kinda
#     # hard to test this in isolation without knowledge how big the coefficients are gonna be.
#     assert int(xplus_sol) == scale(xplus).approxed(abs=1e15)
#     assert int(xminus_sol) == scale(xminus).approxed(abs=1e15)


@pytest.mark.skip(reason="Needs refactor, see new prec calcs")
@settings(max_examples=MAX_EXAMPLES)
@given(params=util.gen_params(), balances=gen_balances(2, bpool_params))
def test_calculateInvariant(params, balances, gyro_cemm_math_testing):
    invariant_py, invariant_sol = util.mtest_calculateInvariant(
        params, balances, DP_IN_SOL, gyro_cemm_math_testing
    )

    # We now require that the invariant is underestimated and allow ourselves a bit of slack in the other direction.
    assert invariant_sol <= scale(invariant_py)
    assert invariant_sol == scale(invariant_py).approxed(abs=D(5))


@pytest.mark.skip(reason="Error bounds need refactor for wider parameter set")
@settings(max_examples=MAX_EXAMPLES)
@given(params=util.gen_params(), balances=gen_balances(2, bpool_params))
def test_calculatePrice(params, balances, gyro_cemm_math_testing):
    assume(balances != (0, 0))
    price_py, price_sol = util.mtest_calculatePrice(
        params, balances, DP_IN_SOL, gyro_cemm_math_testing
    )

    assert price_sol == scale(price_py).approxed_scaled()


# checkAssetBounds() not tested.


@settings(max_examples=MAX_EXAMPLES)
@given(
    params=util.gen_params(),
    x=qdecimals(0, 100_000_000_000),
    invariant=util.gen_synthetic_invariant(),
)
def test_calcYGivenX(params, x, invariant, gyro_cemm_math_testing):
    # just pick something for overestimate
    r = (D(invariant) * (D(1) + D("1e-15")), invariant)
    y_py, y_sol = util.mtest_calcYGivenX(
        params, x, r, DP_IN_SOL, gyro_cemm_math_testing
    )
    assert y_sol == scale(y_py).approxed_scaled()


@settings(max_examples=MAX_EXAMPLES)
@given(
    params=util.gen_params(),
    y=qdecimals(0, 100_000_000_000),
    invariant=util.gen_synthetic_invariant(),
)
def test_calcXGivenY(params, y, invariant, gyro_cemm_math_testing):
    # just pick something for overestimate
    r = (D(invariant) * (D(1) + D("1e-15")), invariant)
    x_py, x_sol = util.mtest_calcXGivenY(
        params, y, r, DP_IN_SOL, gyro_cemm_math_testing
    )
    assert x_sol == scale(x_py).approxed_scaled()


@st.composite
def gen_args_calcOutGivenIn(draw):
    params = draw(util.gen_params())
    balances = draw(gen_balances(2, bpool_params))
    tokenInIsToken0 = draw(st.booleans())

    mparams = util.params2MathParams(params)
    cemm = mimpl.CEMM.from_x_y(*balances, mparams)

    if tokenInIsToken0:
        amountInMax = cemm.xmax - cemm.x
    else:
        amountInMax = cemm.ymax - cemm.y
    assume(amountInMax >= 1)

    amountIn = draw(qdecimals(1, amountInMax, places=4))

    return params, balances, amountIn, tokenInIsToken0


@settings(max_examples=100)
@given(
    args=gen_args_calcOutGivenIn()
)
def test_calcOutGivenIn(
    args, gyro_cemm_math_testing
):
    params, balances, amountIn, tokenInIsToken0 = args

    ixIn = 0 if tokenInIsToken0 else 1
    ixOut = 1 - ixIn
    amount_out_py, amount_out_sol = util.mtest_calcOutGivenIn(
        params, balances, amountIn, tokenInIsToken0, DP_IN_SOL, gyro_cemm_math_testing
    )

    assert amount_out_sol == scale(
        amount_out_py
    ).our_approxed_scaled() or amount_out_sol == scale(amount_out_py).approxed(
        abs=D("1E6") * balances[ixOut]
    )
    # ^ The second case catches some pathological test cases where an error on the order of 1e-3 occurs in
    # an extremely unbalanced pool with reserves on the order of (100M, 1).
    # Differences smaller than 1e-12 * balances are ignored.


@settings(max_examples=MAX_EXAMPLES)
@given(
    params=util.gen_params(),
    balances=gen_balances(2, bpool_params),
    amountOut=qdecimals(min_value=1, max_value=1_000_000_000, places=4),
    tokenInIsToken0=st.booleans(),
)
def test_calcInGivenOut(
    params, balances, amountOut, tokenInIsToken0, gyro_cemm_math_testing
):
    ixIn = 0 if tokenInIsToken0 else 1
    ixOut = 1 - ixIn

    amount_in_py, amount_in_sol = util.mtest_calcInGivenOut(
        params, balances, amountOut, tokenInIsToken0, DP_IN_SOL, gyro_cemm_math_testing
    )

    assert amount_in_sol == scale(
        amount_in_py
    ).our_approxed_scaled() or amount_in_sol == scale(amount_in_py).approxed(
        abs=D("1E6") * balances[ixOut]
    )


@pytest.mark.skip(reason="Needs refactor")
@settings(max_examples=MAX_EXAMPLES)
@given(params_cemm_dinvariant=util.gen_params_cemm_dinvariant())
def test_liquidityInvariantUpdate(params_cemm_dinvariant, gyro_cemm_math_testing):
    rnew_py, rnew_sol = util.mtest_liquidityInvariantUpdate(
        params_cemm_dinvariant, gyro_cemm_math_testing
    )

    assert unscale(rnew_sol) == rnew_py.approxed()


@pytest.mark.skip(reason="Needs refactor")
@settings(max_examples=MAX_EXAMPLES)
@given(params_cemm_dinvariant=util.gen_params_cemm_dinvariant())
def test_liquidityInvariantUpdateEquivalence(
    params_cemm_dinvariant, gyro_cemm_math_testing
):
    util.mtest_liquidityInvariantUpdateEquivalence(
        params_cemm_dinvariant, gyro_cemm_math_testing
    )


# BPT token and protocol fee calculations are not tested b/c they're exactly the same as for the other pools.

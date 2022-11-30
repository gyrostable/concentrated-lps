from decimal import Decimal
from decimal import Decimal
from math import pi, sin, cos

import hypothesis.strategies as st
import pytest

# from pyrsistent import Invariant
from brownie.test import given
from hypothesis import assume, example

from tests.support.util_common import (
    BasicPoolParameters,
    gen_balances,
    gen_balances_vector,
)
from tests.cemm import cemm as mimpl
from tests.cemm import util
from tests.support.quantized_decimal import QuantizedDecimal as D
from tests.support.types import *
from tests.support.utils import scale, to_decimal, qdecimals, unscale

billion_balance_strategy = st.integers(min_value=0, max_value=10_000_000_000)

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


D.approxed_scaled = lambda self: self.approxed(abs=D("1E6"), rel=D("1E-9"))
D.our_approxed_scaled = lambda self: self.approxed(abs=D("1E15"), rel=D("1E-9"))


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
    l = draw(qdecimals("5", "500"))
    return CEMMMathParams(alpha, beta, D(c), D(s), l)


@st.composite
def gen_params_cemm_dinvariant(draw):
    params = draw(gen_params())
    mparams = util.params2MathParams(params)
    balances = draw(gen_balances(2, bpool_params))
    assume(balances[0] > 0 and balances[1] > 0)
    cemm = mimpl.CEMM.from_x_y(balances[0], balances[1], mparams)
    dinvariant = draw(
        qdecimals(-cemm.r.raw, 2 * cemm.r.raw)
    )  # Upper bound kinda arbitrary
    assume(abs(dinvariant) > D("1E-10"))  # Only relevant updates
    return params, cemm, dinvariant


################################################################################


@given(params=gen_params(), t=gen_balances_vector(bpool_params))
def test_mulA(params: CEMMMathParams, t: Vector2, gyro_cemm_math_testing):
    util.mtest_mulA(params, t, gyro_cemm_math_testing)


@st.composite
def gen_params_px(draw):
    params = draw(gen_params())
    px = draw(qdecimals(params.alpha.raw, params.beta.raw))
    return params, px

@pytest.mark.skip(reason="Function currently removed")
@given(params_px=gen_params_px())
def test_zeta(params_px, gyro_cemm_math_testing):
    util.mtest_zeta(params_px, gyro_cemm_math_testing)

@pytest.mark.skip(reason="Function currently removed")
@given(params_px=gen_params_px())
def test_tau(params_px, gyro_cemm_math_testing):
    util.mtest_tau(params_px, gyro_cemm_math_testing)


@pytest.mark.skip(reason="Needs refactor, see new prec calcs")
@given(params=gen_params(), invariant=util.gen_synthetic_invariant())
def test_virtualOffsets_noderived(params, invariant, gyro_cemm_math_testing):
    util.mtest_virtualOffsets_noderived(params, invariant, gyro_cemm_math_testing)


@given(params=gen_params(), invariant=util.gen_synthetic_invariant())
def test_maxBalances(params, invariant, gyro_cemm_math_testing):
    util.mtest_maxBalances(params, invariant, gyro_cemm_math_testing)


@given(params=gen_params(), balances=gen_balances(2, bpool_params))
def test_calculateInvariant(params, balances, gyro_cemm_math_testing):
    invariant_py, invariant_sol = util.mtest_calculateInvariant(
        params, balances, DP_IN_SOL, gyro_cemm_math_testing
    )

    # We now require that the invariant is underestimated and allow ourselves a bit of slack in the other direction.
    assert invariant_sol.approxed_scaled() <= scale(invariant_py).approxed_scaled()
    assert invariant_sol == scale(invariant_py).approxed(abs=D(5))


@given(params=gen_params(), balances=gen_balances(2, bpool_params))
def test_calculatePrice(params, balances, gyro_cemm_math_testing):
    assume(balances != (0, 0))
    price_py, price_sol = util.mtest_calculatePrice(
        params, balances, DP_IN_SOL, gyro_cemm_math_testing
    )

    assert price_sol == scale(price_py).approxed_scaled()


@given(
    params=gen_params(),
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


@given(
    params=gen_params(),
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


@pytest.mark.skip(reason="Imprecision error to fix")
@given(
    params=gen_params(),
    balances=gen_balances(2, bpool_params),
    amountIn=qdecimals(min_value=1, max_value=1_000_000_000, places=4),
    tokenInIsToken0=st.booleans(),
)
def test_calcOutGivenIn(
    params, balances, amountIn, tokenInIsToken0, gyro_cemm_math_testing
):
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


@pytest.mark.skip(reason="Imprecision error to fix")
@given(
    params=gen_params(),
    balances=gen_balances(2, bpool_params),
    amountOut=qdecimals(min_value=1, max_value=1_000_000_000, places=4),
    tokenInIsToken0=st.booleans(),
)
@example(
    params=CEMMMathParams(
        alpha=Decimal("0.050000000000000000"),
        beta=Decimal("1.001000000000000000"),
        c=Decimal("0.683561140728226824"),
        s=Decimal("0.729893257186504774"),
        l=Decimal("408.000000000000000000"),
    ),
    balances=(7396878, 97),
    amountOut=Decimal("1.000000000000000000"),
    tokenInIsToken0=False,
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
@given(params_cemm_dinvariant=gen_params_cemm_dinvariant())
def test_liquidityInvariantUpdate(params_cemm_dinvariant, gyro_cemm_math_testing):
    rnew_py, rnew_sol = util.mtest_liquidityInvariantUpdate(
        params_cemm_dinvariant, gyro_cemm_math_testing
    )

    assert unscale(rnew_sol) == rnew_py.approxed()


@pytest.mark.skip(reason="Needs refactor")
@given(params_cemm_dinvariant=gen_params_cemm_dinvariant())
def test_liquidityInvariantUpdateEquivalence(
    params_cemm_dinvariant, gyro_cemm_math_testing
):
    util.mtest_liquidityInvariantUpdateEquivalence(
        params_cemm_dinvariant, gyro_cemm_math_testing
    )

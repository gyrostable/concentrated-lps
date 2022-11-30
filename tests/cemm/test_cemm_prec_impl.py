import decimal
from decimal import Decimal
from decimal import Decimal
from math import pi, sin, cos

import hypothesis.strategies as st
import pytest

# from pyrsistent import Invariant
from brownie.test import given
from hypothesis import assume, example, settings, HealthCheck

from tests.support.quantized_decimal import QuantizedDecimal as D
from tests.support.quantized_decimal_38 import QuantizedDecimal as D2

from tests.support.util_common import (
    BasicPoolParameters,
    gen_balances,
    gen_balances_vector,
)
from tests.cemm import cemm_100 as mimpl
from tests.cemm import cemm_prec_implementation as prec_impl
from tests.support.quantized_decimal_100 import QuantizedDecimal as D3
from tests.support.types import *
from tests.support.utils import scale, to_decimal, qdecimals, unscale, apply_deep

from math import pi, sin, cos, tan, acos

from tests.support.types import Vector2

MIN_PRICE_SEPARATION = to_decimal("0.0001")
MAX_IN_RATIO = to_decimal("0.3")
MAX_OUT_RATIO = to_decimal("0.3")

MIN_BALANCE_RATIO = to_decimal("0")  # to_decimal("5e-5")
MIN_FEE = D(0)  # D("0.0002")


def test_dummy():
    print(decimal.getcontext().prec)


def convd(x, totype, dofloat=True, dostr=True):
    """totype: one of D, D2, D3, i.e., some QuantizedDecimal implementation.

    `dofloat`: Also convert floats.

    `dostr`: Also convert str.

    Example: convd(x, D3)"""

    def go(y):
        if isinstance(y, decimal.Decimal):
            return totype(y)
        elif isinstance(y, (D, D2, D3)):
            return totype(y.raw)
        elif dofloat and isinstance(y, float):
            return totype(y)
        elif dostr and isinstance(y, str):
            return totype(y)
        else:
            return y

    return apply_deep(x, go)


def paramsTo100(params: CEMMMathParams) -> CEMMMathParams:
    """Convert params to a high-precision version. This is more than just type conversion, we also re-normalize!"""
    params = convd(params, D3)
    pd = params._asdict()
    d = (params.s**2 + params.c**2).sqrt()
    pd["s"] /= d
    pd["c"] /= d
    return CEMMMathParams(**pd)


def params2MathParams(params: CEMMMathParams) -> mimpl.Params:
    """Map 100-decimal CEMMMathParams to 100-decimal mimpl.Params.
    This is equal to .util.params2MathParams() but has to be re-written to use the right cemm impl module."""
    return mimpl.Params(params.alpha, params.beta, params.c, -params.s, params.l)


bpool_params = BasicPoolParameters(
    MIN_PRICE_SEPARATION,
    MAX_IN_RATIO,
    MAX_OUT_RATIO,
    MIN_BALANCE_RATIO,
    MIN_FEE,
    int(D("1e11")),
)

bpool_params_conservative = BasicPoolParameters(
    MIN_PRICE_SEPARATION,
    MAX_IN_RATIO,
    MAX_OUT_RATIO,
    to_decimal("1e-5"),
    MIN_FEE,
    int(D("1e8")),
)


@st.composite
def gen_params(draw):
    phi_degrees = draw(st.floats(10, 80))
    phi = phi_degrees / 360 * 2 * pi

    # Price bounds. Choose s.t. the 'peg' lies approximately within the bounds (within 30%).
    # It'd be nonsensical if this was not the case: Why are we using an ellipse then?!
    peg = tan(phi)  # = price where the flattest point of the ellipse lies.
    peg = D(peg)
    alpha_high = peg * D("1.3")
    beta_low = peg * D("0.7")
    alpha = draw(qdecimals("0.05", alpha_high.raw))
    beta = draw(
        qdecimals(max(beta_low.raw, (alpha + MIN_PRICE_SEPARATION).raw), "20.0")
    )

    s = sin(phi)
    c = cos(phi)
    l = draw(qdecimals(min_value="1", max_value="1e8", places=3))
    return CEMMMathParams(alpha, beta, D(c), D(s), l)


@st.composite
def gen_params_conservative(draw):
    phi_degrees = draw(st.floats(10, 80))
    phi = phi_degrees / 360 * 2 * pi

    # Price bounds. Choose s.t. the 'peg' lies approximately within the bounds (within 30%).
    # It'd be nonsensical if this was not the case: Why are we using an ellipse then?!
    peg = tan(phi)  # = price where the flattest point of the ellipse lies.
    peg = D(peg)
    alpha_high = peg * D("1.3")
    beta_low = peg * D("0.7")
    alpha = draw(qdecimals("0.05", alpha_high.raw))
    beta = draw(
        qdecimals(max(beta_low.raw, (alpha + MIN_PRICE_SEPARATION).raw), "20.0")
    )

    s = sin(phi)
    c = cos(phi)
    l = draw(qdecimals("1", "10"))
    return CEMMMathParams(alpha, beta, D(c), D(s), l)


# def params2MathParams(params: CEMMMathParams) -> mimpl.Params:
#     """The python math implementation is a bit older and uses its own data structures. This function converts."""
#     c, s = convert_deep_decimals([D(params.c), D(params.s)], D3)
#     # c, s = (D3(D(params.c).raw), D3(D(params.s).raw))
#     d = (c ** 2 + s ** 2).sqrt()
#     c, s = (c / d, s / d)
#     return mimpl.Params(D3(params.alpha), D3(params.beta), c, -s, D3(params.l))


######################################################################################
# @given(params=gen_params())
# def test_calcAChiAChi(gyro_cemm_math_testing, params):
#     mparams = params2MathParams(paramsTo100(params))
#     derived_m = mparams  # Legacy fix

#     derived = prec_impl.calc_derived_values(params)
#     derived_scaled = prec_impl.scale_derived_values(derived)

#     result_py = prec_impl.calcAChiAChi(params, derived)
#     result_sol = gyro_cemm_math_testing.calcAChiAChi(scale(params), derived_scaled)
#     assert result_py == unscale(result_sol)
#     assert result_py > 1

#     # test against the old (imprecise) implementation
#     chi = (
#         mparams.Ainv_times(derived_m.tauBeta[0], derived_m.tauBeta[1])[0],
#         mparams.Ainv_times(derived_m.tauAlpha[0], derived_m.tauAlpha[1])[1],
#     )
#     AChi = mparams.A_times(chi[0], chi[1])
#     AChiAChi = AChi[0] ** 2 + AChi[1] ** 2
#     assert result_py == convd(AChiAChi, D).approxed()


@given(params=gen_params())
def test_calcAChiAChiInXp(gyro_cemm_math_testing, params):
    mparams = params2MathParams(paramsTo100(params))
    derived_m = mparams  # Legacy fix

    derived = prec_impl.calc_derived_values(params)
    derived_scaled = prec_impl.scale_derived_values(derived)

    result_py = prec_impl.calcAChiAChiInXp(params, derived)
    result_sol = gyro_cemm_math_testing.calcAChiAChiInXp(scale(params), derived_scaled)
    assert result_py == D2((D3(result_sol) / D3("1e38")).raw)
    assert result_py > 1

    # test against the old (imprecise) implementation
    chi = (
        mparams.Ainv_times(derived_m.tauBeta[0], derived_m.tauBeta[1])[0],
        mparams.Ainv_times(derived_m.tauAlpha[0], derived_m.tauAlpha[1])[1],
    )
    AChi = mparams.A_times(chi[0], chi[1])
    AChiAChi = AChi[0] ** 2 + AChi[1] ** 2
    # Note: expect to agree to 1e-22 if lambda=1e8
    err_tol = D2(D(params.l).raw) ** 2 * D2("2e-37")
    assert result_py == convd(AChiAChi, D2).approxed(abs=err_tol)


@given(
    params=gen_params(),
    balances=gen_balances(2, bpool_params),
)
def test_calcAtAChi(gyro_cemm_math_testing, params, balances):
    derived = prec_impl.calc_derived_values(params)
    derived_scaled = prec_impl.scale_derived_values(derived)
    result_py = prec_impl.calcAtAChi(balances[0], balances[1], params, derived)
    result_sol = gyro_cemm_math_testing.calcAtAChi(
        scale(balances[0]),
        scale(balances[1]),
        scale(params),
        derived_scaled,
    )
    assert result_py == unscale(result_sol)


@given(
    params=gen_params(),
    balances=gen_balances(2, bpool_params),
)
def test_calcAtAChi_sense_check(params, balances):
    mparams = params2MathParams(paramsTo100(params))
    derived_m = mparams  # Legacy fix

    derived = prec_impl.calc_derived_values(params)
    result_py = prec_impl.calcAtAChi(balances[0], balances[1], params, derived)

    # test against the old (imprecise) implementation
    At = mparams.A_times(*convd((balances[0], balances[1]), D3))
    chi = (
        mparams.Ainv_times(derived_m.tauBeta[0], derived_m.tauBeta[1])[0],
        mparams.Ainv_times(derived_m.tauAlpha[0], derived_m.tauAlpha[1])[1],
    )
    AChi = mparams.A_times(chi[0], chi[1])
    AtAChi = At[0] * AChi[0] + At[1] * AChi[1]
    assert AtAChi == convd(result_py, D).approxed(abs=D("5e-18"))


@given(
    params=gen_params(),
    balances=gen_balances(2, bpool_params),
)
def test_calcMinAtxAChiySqPlusAtxSq(gyro_cemm_math_testing, params, balances):
    derived = prec_impl.calc_derived_values(params)
    derived_scaled = prec_impl.scale_derived_values(derived)
    result_py = prec_impl.calcMinAtxAChiySqPlusAtxSq(
        balances[0], balances[1], params, derived
    )
    result_sol = gyro_cemm_math_testing.calcMinAtxAChiySqPlusAtxSq(
        scale(balances[0]), scale(balances[1]), scale(params), derived_scaled
    )
    assert result_py == unscale(result_sol)


@given(
    params=gen_params(),
    balances=gen_balances(2, bpool_params),
)
def test_calcMinAtxAChiySqPlusAtxSq_sense_check(params, balances):
    mparams = params2MathParams(paramsTo100(params))
    derived_m = mparams  # Legacy fix

    derived = prec_impl.calc_derived_values(params)
    result_py = prec_impl.calcMinAtxAChiySqPlusAtxSq(
        balances[0], balances[1], params, derived
    )
    # test against the old (imprecise) implementation
    At = mparams.A_times(*convd((balances[0], balances[1]), D3))
    chi = (
        mparams.Ainv_times(derived_m.tauBeta[0], derived_m.tauBeta[1])[0],
        mparams.Ainv_times(derived_m.tauAlpha[0], derived_m.tauAlpha[1])[1],
    )
    AChi = mparams.A_times(chi[0], chi[1])
    val_sense = At[0] * At[0] * (1 - AChi[1] * AChi[1])
    assert result_py == convd(val_sense, D).approxed(abs=D("1e-15"))


@given(
    params=gen_params(),
    balances=gen_balances(2, bpool_params),
)
def test_calc2AtxAtyAChixAChiy(gyro_cemm_math_testing, params, balances):
    derived = prec_impl.calc_derived_values(params)
    derived_scaled = prec_impl.scale_derived_values(derived)

    result_py = prec_impl.calc2AtxAtyAChixAChiy(
        balances[0], balances[1], params, derived
    )
    result_sol = gyro_cemm_math_testing.calc2AtxAtyAChixAChiy(
        scale(balances[0]), scale(balances[1]), scale(params), derived_scaled
    )
    assert result_py == unscale(result_sol)


@given(
    params=gen_params(),
    balances=gen_balances(2, bpool_params),
)
def test_calc2AtxAtyAChixAChiy_sense_check(params, balances):
    mparams = params2MathParams(paramsTo100(params))
    derived_m = mparams  # Legacy fix

    derived = prec_impl.calc_derived_values(params)
    result_py = prec_impl.calc2AtxAtyAChixAChiy(
        balances[0], balances[1], params, derived
    )
    # test against the old (imprecise) implementation
    At = mparams.A_times(*convd((balances[0], balances[1]), D3))
    chi = (
        mparams.Ainv_times(derived_m.tauBeta[0], derived_m.tauBeta[1])[0],
        mparams.Ainv_times(derived_m.tauAlpha[0], derived_m.tauAlpha[1])[1],
    )
    AChi = mparams.A_times(chi[0], chi[1])
    val_sense = D3(2) * At[0] * At[1] * AChi[0] * AChi[1]
    assert result_py == convd(val_sense, D).approxed(abs=D("1e-15"))


@given(
    params=gen_params(),
    balances=gen_balances(2, bpool_params),
)
def test_calcMinAtyAChixSqPlusAtySq(gyro_cemm_math_testing, params, balances):
    derived = prec_impl.calc_derived_values(params)
    derived_scaled = prec_impl.scale_derived_values(derived)
    result_py = prec_impl.calcMinAtyAChixSqPlusAtySq(
        balances[0], balances[1], params, derived
    )
    result_sol = gyro_cemm_math_testing.calcMinAtyAChixSqPlusAtySq(
        scale(balances[0]), scale(balances[1]), scale(params), derived_scaled
    )
    assert result_py == unscale(result_sol)


@given(
    params=gen_params(),
    balances=gen_balances(2, bpool_params),
)
def test_calcMinAtyAChixSqPlusAtySq_sense_check(params, balances):
    mparams = params2MathParams(paramsTo100(params))
    derived_m = mparams  # Legacy fix

    derived = prec_impl.calc_derived_values(params)
    result_py = prec_impl.calcMinAtyAChixSqPlusAtySq(
        balances[0], balances[1], params, derived
    )
    # test against the old (imprecise) implementation
    At = mparams.A_times(*convd((balances[0], balances[1]), D3))
    chi = (
        mparams.Ainv_times(derived_m.tauBeta[0], derived_m.tauBeta[1])[0],
        mparams.Ainv_times(derived_m.tauAlpha[0], derived_m.tauAlpha[1])[1],
    )
    AChi = mparams.A_times(chi[0], chi[1])
    val_sense = At[1] * At[1] * (D3(1) - AChi[0] * AChi[0])
    assert result_py == convd(val_sense, D).approxed(abs=D("1e-15"))


@given(
    params=gen_params(),
    balances=gen_balances(2, bpool_params),
)
@example(
    params=CEMMMathParams(
        alpha=D("0.050000000000020290"),
        beta=D("0.397316269897841178"),
        c=D("0.869675796261884515"),
        s=D("0.493623347701723947"),
        l=D("30098365.475000000000000000"),
    ),
    balances=[D("60138484034.385962001000000000"), D("1.404490000000000000")],
)
def test_calcInvariantSqrt(gyro_cemm_math_testing, params, balances):
    derived = prec_impl.calc_derived_values(params)
    derived_scaled = prec_impl.scale_derived_values(derived)
    result_py, err_py = prec_impl.calcInvariantSqrt(
        balances[0], balances[1], params, derived
    )
    result_sol, err_sol = gyro_cemm_math_testing.calcInvariantSqrt(
        scale(balances[0]), scale(balances[1]), scale(params), derived_scaled
    )
    assert result_py == unscale(result_sol).approxed(abs=D("5e-18"))  # (rel=D("1e-13"))
    assert err_py == unscale(err_sol)


@given(
    params=gen_params(),
    balances=gen_balances(2, bpool_params),
)
@example(
    params=CEMMMathParams(
        alpha=D("0.050000000000020290"),
        beta=D("0.397316269897841178"),
        c=D("0.869675796261884515"),
        s=D("0.493623347701723947"),
        l=D("30098365.475000000000000000"),
    ),
    balances=[D("60138484034.385962001000000000"), D("1.404490000000000000")],
)
def test_calculateInvariant(gyro_cemm_math_testing, params, balances):
    derived = prec_impl.calc_derived_values(params)
    derived_scaled = prec_impl.scale_derived_values(derived)
    result_py, err_py = prec_impl.calculateInvariantWithError(balances, params, derived)
    result_sol, err_sol = gyro_cemm_math_testing.calculateInvariantWithError(
        scale(balances), scale(params), derived_scaled
    )
    # denominator = prec_impl.calcAChiAChi(params, derived) - D(1)
    # err = D("5e-18") if denominator > 1 else D("5e-18") / D(denominator)
    denominator = prec_impl.calcAChiAChiInXp(params, derived) - D2(1)
    err = D2("5e-18") if denominator > 1 else D2("5e-18") / D2(denominator)
    err = D(err.raw)
    assert result_py == unscale(result_sol).approxed(abs=(err + D("500e-18")))
    assert err_py == unscale(err_sol).approxed(abs=D("500e-18"))
    # assert result_py == (result_py + err_py).approxed(rel=D("1e-12"), abs=D("1e-12"))


@settings(suppress_health_check=[HealthCheck.filter_too_much])
@given(
    params=gen_params(),
    balances=gen_balances(2, bpool_params),
)
def test_calculateInvariant_sense_check(params, balances):
    mparams = params2MathParams(paramsTo100(params))

    derived = prec_impl.calc_derived_values(params)
    denominator = prec_impl.calcAChiAChiInXp(params, derived) - D2(1)
    assume(denominator > D2("1E-5"))  # if this is not the case, error can blow up

    result_py, err_py = prec_impl.calculateInvariantWithError(balances, params, derived)
    # test against the old (imprecise) implementation
    cemm = mimpl.CEMM.from_x_y(*convd(balances, D3), mparams)
    assert convd(cemm.r, D) == result_py.approxed()
    assert convd(cemm.r, D) == D(result_py + err_py).approxed(abs=D(err_py))


@settings(suppress_health_check=[HealthCheck.filter_too_much])
@given(
    params=gen_params(),
    balances=gen_balances(2, bpool_params),
)
def test_calculateInvariant_error_not_too_bad(gyro_cemm_math_testing, params, balances):
    derived = prec_impl.calc_derived_values(params)
    denominator = prec_impl.calcAChiAChiInXp(params, derived) - D2(1)
    assume(denominator > D2("1E-5"))  # if this is not the case, error can blow up
    result_py, err_py = prec_impl.calculateInvariantWithError(balances, params, derived)
    assert err_py < D("3e-8")
    if result_py < D(1):
        assert err_py / result_py < D("1e-8")


@given(
    params=gen_params(),
    invariant=st.decimals(min_value="1e-5", max_value="1e12", places=4),
)
def test_virtualOffsets(gyro_cemm_math_testing, params, invariant):
    derived = prec_impl.calc_derived_values(params)
    derived_scaled = prec_impl.scale_derived_values(derived)

    r = (prec_impl.invariantOverestimate(invariant), invariant)
    a_py = prec_impl.virtualOffset0(params, derived, r)
    b_py = prec_impl.virtualOffset1(params, derived, r)
    a_sol = gyro_cemm_math_testing.virtualOffset0(
        scale(params), derived_scaled, scale(r)
    )
    b_sol = gyro_cemm_math_testing.virtualOffset1(
        scale(params), derived_scaled, scale(r)
    )
    assert a_py == unscale(a_sol)
    assert b_py == unscale(b_sol)


@settings(suppress_health_check=[HealthCheck.filter_too_much])
@given(
    params=gen_params(),
    invariant=st.decimals(min_value="1e-5", max_value="1e12", places=4),
)
def test_virtualOffsets_sense_check(params, invariant):
    derived = prec_impl.calc_derived_values(params)

    denominator = prec_impl.calcAChiAChiInXp(params, derived) - D2(1)
    assume(denominator > D2("1E-5"))  # if this is not the case, error can blow up

    # test w/o error in invariant
    r = (invariant, invariant)

    a_py = prec_impl.virtualOffset0(params, derived, r)
    b_py = prec_impl.virtualOffset1(params, derived, r)

    # test against the old (imprecise) implementation
    mparams = params2MathParams(paramsTo100(params))
    midprice = (mparams.alpha + mparams.beta) / D3(2)
    cemm = mimpl.CEMM.from_px_r(midprice, convd(invariant, D3), mparams)
    assert a_py == convd(cemm.a, D).approxed(abs=D("1e-17"))
    assert b_py == convd(cemm.b, D).approxed(abs=D("1e-17"))


@given(params=gen_params(), balances=gen_balances(2, bpool_params))
def test_calcXpXpDivLambdaLambda(gyro_cemm_math_testing, params, balances):
    derived = prec_impl.calc_derived_values(params)
    derived_scaled = prec_impl.scale_derived_values(derived)

    invariant, err = prec_impl.calculateInvariantWithError(balances, params, derived)
    r = (invariant + 2 * D(err), invariant)

    XpXp_py = prec_impl.calcXpXpDivLambdaLambda(
        balances[0], r, params.l, params.s, params.c, derived.tauBeta, derived.dSq
    )
    XpXp_sol = gyro_cemm_math_testing.calcXpXpDivLambdaLambda(
        scale(balances[0]),
        scale(r),
        scale(params.l),
        scale(params.s),
        scale(params.c),
        derived_scaled.tauBeta,
        derived_scaled.dSq,
    )
    assert XpXp_py == unscale(XpXp_sol)


@settings(suppress_health_check=[HealthCheck.filter_too_much])
@given(
    params=gen_params(),
    balances=gen_balances(2, bpool_params),
)
def test_calcXpXpDivLambdaLambda_sense_check(params, balances):
    derived = prec_impl.calc_derived_values(params)

    denominator = prec_impl.calcAChiAChiInXp(params, derived) - D2(1)
    assume(denominator > D2("1E-5"))  # if this is not the case, error can blow up

    invariant, err = prec_impl.calculateInvariantWithError(balances, params, derived)
    r = (invariant + 2 * D(err), invariant)

    XpXp_py = prec_impl.calcXpXpDivLambdaLambda(
        balances[0], r, params.l, params.s, params.c, derived.tauBeta, derived.dSq
    )

    # sense test
    a_py_under = prec_impl.virtualOffset0(params, derived, r)
    a_py_over = prec_impl.virtualOffset0(params, derived, (r[1], r[0]))
    # first calculate overestimate
    a_for_over = a_py_under - D("1e-17") if a_py_under >= 0 else a_py_over + D("1e-17")
    XpXp_over = (
        D3(D(balances[0]).raw - D(a_for_over).raw)
        * D3(D(balances[0]).raw - D(a_for_over).raw)
        / D3(D(params.l).raw)
        / D3(D(params.l).raw)
    )
    # next calculate underestimate
    a_for_under = a_py_over + D("1e-17") if a_py_over >= 0 else a_py_under - D("1e-17")
    XpXp_under = (
        D3(D(balances[0]).raw - D(a_for_under).raw)
        * D3(D(balances[0]).raw - D(a_for_under).raw)
        / D3(D(params.l).raw)
        / D3(D(params.l).raw)
    )
    # assert D(XpXp_under.raw) <= XpXp_py
    # assert XpXp_py <= D(XpXp_over.raw)
    # Note: something is wrong with the under and overestimates, which is why the abs is needed in err_tol
    # this means this might not be the right error tolerance (which is why *1000)
    err_tol = 1000 * abs(D((XpXp_over - XpXp_under).raw)) + D("1e-16")
    assert D(XpXp_under.raw) == XpXp_py.approxed(abs=err_tol)


@given(params=gen_params(), balances=gen_balances(2, bpool_params))
def test_calcYpYpDivLambdaLambda(gyro_cemm_math_testing, params, balances):
    derived = prec_impl.calc_derived_values(params)
    derived_scaled = prec_impl.scale_derived_values(derived)

    invariant, err = prec_impl.calculateInvariantWithError(balances, params, derived)
    r = (invariant + 2 * D(err), invariant)

    tau_beta = Vector2(-derived.tauAlpha[0], derived.tauAlpha[1])
    tau_beta_scaled = Vector2(-derived_scaled.tauAlpha[0], derived_scaled.tauAlpha[1])
    YpYp_py = prec_impl.calcXpXpDivLambdaLambda(
        balances[1], r, params.l, params.c, params.s, tau_beta, derived.dSq
    )
    YpYp_sol = gyro_cemm_math_testing.calcXpXpDivLambdaLambda(
        scale(balances[1]),
        scale(r),
        scale(params.l),
        scale(params.c),
        scale(params.s),
        tau_beta_scaled,
        derived_scaled.dSq,
    )
    assert YpYp_py == unscale(YpYp_sol)


@settings(suppress_health_check=[HealthCheck.filter_too_much])
@given(
    params=gen_params(),
    balances=gen_balances(2, bpool_params),
)
def test_calcYpYpDivLambdaLambda_sense_check(params, balances):
    derived = prec_impl.calc_derived_values(params)

    denominator = prec_impl.calcAChiAChiInXp(params, derived) - D2(1)
    assume(denominator > D2("1E-5"))  # if this is not the case, error can blow up

    invariant, err = prec_impl.calculateInvariantWithError(balances, params, derived)
    r = (invariant + 2 * D(err), invariant)

    tau_beta = Vector2(-derived.tauAlpha[0], derived.tauAlpha[1])
    YpYp_py = prec_impl.calcXpXpDivLambdaLambda(
        balances[1], r, params.l, params.c, params.s, tau_beta, derived.dSq
    )

    # sense test
    b_py_under = prec_impl.virtualOffset1(params, derived, r)
    b_py_over = prec_impl.virtualOffset1(params, derived, (r[1], r[0]))
    # first calculate overestimate
    b_for_over = b_py_under - D("1e-17") if b_py_under >= 0 else b_py_over + D("1e-17")
    YpYp_over = (
        D3(D(balances[1]).raw - D(b_for_over).raw)
        * D3(D(balances[1]).raw - D(b_for_over).raw)
        / D3(D(params.l).raw)
        / D3(D(params.l).raw)
    )
    # next calculate underestimate
    b_for_under = b_py_over + D("1e-17") if b_py_over >= 0 else b_py_under - D("1e-17")
    YpYp_under = (
        D3(D(balances[1]).raw - D(b_for_under).raw)
        * D3(D(balances[1]).raw - D(b_for_under).raw)
        / D3(D(params.l).raw)
        / D3(D(params.l).raw)
    )
    # assert D(YpYp_under.raw) <= YpYp_py
    # assert YpYp_py <= D(YpYp_over.raw)
    # Note: something is wrong with the under and overestimates, which is why the abs is needed in err_tol
    # this means this might not be the right error tolerance (which is why *1000)
    err_tol = 1000 * abs(D((YpYp_over - YpYp_under).raw)) + D("1e-16")
    assert D(YpYp_under.raw) == YpYp_py.approxed(abs=err_tol)


@given(params=gen_params(), balances=gen_balances(2, bpool_params))
@example(
    params=CEMMMathParams(
        alpha=Decimal("0.050000000000000000"),
        beta=Decimal("0.123428886495925482"),
        c=Decimal("0.984807753012208020"),
        s=Decimal("0.173648177666930331"),
        l=Decimal("17746.178000000000000000"),
    ),
    balances=[1, 1],
)
def test_solveQuadraticSwap(gyro_cemm_math_testing, params, balances):
    derived = prec_impl.calc_derived_values(params)
    derived_scaled = prec_impl.scale_derived_values(derived)

    invariant, err = prec_impl.calculateInvariantWithError(balances, params, derived)
    r = (invariant + 2 * D(err), invariant)
    a = prec_impl.virtualOffset0(params, derived, r)
    b = prec_impl.virtualOffset1(params, derived, r)
    # the error comes from the square root and from the square root in r (in the offset)
    # these are amplified by the invariant, lambda, and/or balances
    # note that r can be orders of magnitude greater than balances
    # error_tolx = max(
    #     invariant * params.l * params.s, invariant, balances[0] / params.l / params.l
    # ) * D("5e-13")
    # error_toly = max(
    #     invariant * params.l * params.c, invariant, balances[1] / params.l / params.l
    # ) * D("5e-13")

    val_py = prec_impl.solveQuadraticSwap(
        params.l,
        balances[0],
        params.s,
        params.c,
        r,
        [a, b],
        derived.tauBeta,
        derived.dSq,
    )
    val_sol = gyro_cemm_math_testing.solveQuadraticSwap(
        scale(params.l),
        scale(balances[0]),
        scale(params.s),
        scale(params.c),
        scale(r),
        scale([a, b]),
        derived_scaled.tauBeta,
        derived_scaled.dSq,
    )
    assert val_py <= unscale(val_sol)
    assert val_py == unscale(val_sol).approxed(
        abs=D("5e-18")
    )  # .approxed(abs=error_tolx)

    tau_beta = Vector2(-derived.tauAlpha[0], derived.tauAlpha[1])
    tau_beta_scaled = Vector2(-derived_scaled.tauAlpha[0], derived_scaled.tauAlpha[1])
    val_y_py = prec_impl.solveQuadraticSwap(
        params.l, balances[1], params.c, params.s, r, [b, a], tau_beta, derived.dSq
    )
    val_y_sol = gyro_cemm_math_testing.solveQuadraticSwap(
        scale(params.l),
        scale(balances[1]),
        scale(params.c),
        scale(params.s),
        scale(r),
        scale([b, a]),
        tau_beta_scaled,
        derived_scaled.dSq,
    )
    assert val_y_py <= unscale(val_y_sol)
    assert val_y_py == unscale(val_y_sol).approxed(
        abs=D("5e-18")
    )  # .approxed(abs=error_toly)


# note: only test this for conservative parameters b/c old implementation is so imprecise
@settings(suppress_health_check=[HealthCheck.filter_too_much])
@given(
    params=gen_params(),
    balances=gen_balances(2, bpool_params),
)
def test_solveQuadraticSwap_sense_check(params, balances):
    derived = prec_impl.calc_derived_values(params)

    denominator = prec_impl.calcAChiAChiInXp(params, derived) - D2(1)
    assume(denominator > D2("1E-5"))  # if this is not the case, error can blow up
    assume(sum(balances) > D(100))

    invariant, err = prec_impl.calculateInvariantWithError(balances, params, derived)
    r = (invariant + 2 * D(err), invariant)
    a = prec_impl.virtualOffset0(params, derived, r)
    b = prec_impl.virtualOffset1(params, derived, r)

    val_py = prec_impl.solveQuadraticSwap(
        params.l,
        balances[0],
        params.s,
        params.c,
        r,
        [a, b],
        derived.tauBeta,
        derived.dSq,
    )
    tau_beta = Vector2(-derived.tauAlpha[0], derived.tauAlpha[1])
    val_y_py = prec_impl.solveQuadraticSwap(
        params.l, balances[1], params.c, params.s, r, [b, a], tau_beta, derived.dSq
    )

    mparams = params2MathParams(paramsTo100(params))
    # sense test against old implementation
    midprice = (mparams.alpha + mparams.beta) / D3(2)
    cemm = mimpl.CEMM.from_px_r(
        midprice, convd(invariant, D3), mparams
    )  # Price doesn't matter.
    y = cemm._compute_y_for_x(convd(balances[0], D3))
    assume(y is not None)  # O/w out of bounds for this invariant
    assume(balances[0] > 0 and y > 0)
    assert convd(y, D) == val_py.approxed(abs=D("1e-8"))

    # sense test against old implementation
    midprice = (mparams.alpha + mparams.beta) / D3(2)
    cemm = mimpl.CEMM.from_px_r(
        midprice, convd(invariant, D3), mparams
    )  # Price doesn't matter.
    x = cemm._compute_x_for_y(convd(balances[1], D3))
    assume(x is not None)  # O/w out of bounds for this invariant
    assume(balances[1] > 0 and x > 0)
    assert convd(x, D) == val_y_py.approxed(abs=D("1e-8"))


# also tests calcXGivenY
@given(params=gen_params(), balances=gen_balances(2, bpool_params))
def test_calcYGivenX(gyro_cemm_math_testing, params, balances):
    derived = prec_impl.calc_derived_values(params)
    derived_scaled = prec_impl.scale_derived_values(derived)
    invariant, err = prec_impl.calculateInvariantWithError(balances, params, derived)
    r = (invariant + 2 * D(err), invariant)

    # error_tolx = max(
    #     invariant * params.l * params.s, invariant, balances[0] / params.l / params.l
    # ) * D("5e-13")
    # error_toly = max(
    #     invariant * params.l * params.c, invariant, balances[1] / params.l / params.l
    # ) * D("5e-13")

    y_py = prec_impl.calcYGivenX(balances[0], params, derived, r)
    y_sol = gyro_cemm_math_testing.calcYGivenX(
        scale(balances[0]), scale(params), derived_scaled, scale(r)
    )
    assert y_py <= unscale(y_sol)
    assert y_py == unscale(y_sol).approxed(abs=D("5e-18"))  # .approxed(abs=error_tolx)

    x_py = prec_impl.calcXGivenY(balances[1], params, derived, r)
    x_sol = gyro_cemm_math_testing.calcXGivenY(
        scale(balances[1]), scale(params), derived_scaled, scale(r)
    )
    assert x_py <= unscale(x_sol)
    assert x_py == unscale(x_sol).approxed(abs=D("5e-18"))  # .approxed(abs=error_toly)


# @settings(max_examples=1000)
@given(params=gen_params(), balances=gen_balances(2, bpool_params))
def test_calcYGivenX_property(params, balances):
    derived = prec_impl.calc_derived_values(params)
    invariant, err = prec_impl.calculateInvariantWithError(balances, params, derived)
    r = (invariant + 2 * D(err), invariant)

    # calculate swap error tolerance
    swap_err_xy, swap_err_yx = calculate_swap_error(params, balances, r, derived)

    y_py = prec_impl.calcYGivenX(balances[0], params, derived, r)
    assert y_py >= balances[1]
    assert y_py == D(balances[1]).approxed(abs=swap_err_xy)

    x_py = prec_impl.calcXGivenY(balances[1], params, derived, r)
    assert x_py >= balances[0]
    assert x_py == D(balances[0]).approxed(abs=swap_err_yx)


def calculate_swap_error(params, balances, r, derived):
    a = prec_impl.virtualOffset0(params, derived, r)
    b = prec_impl.virtualOffset1(params, derived, r)
    swap_sqrt = prec_impl.solveQuadraticSwap(
        params.l,
        balances[0],
        params.s,
        params.c,
        r,
        [a, b],
        derived.tauBeta,
        derived.dSq,
    )
    x, y = (balances[0], balances[1])
    inv_err = r[0] - r[1]
    denominator = D(1) - D(params.s) ** 2 + D(params.s) ** 2 / params.l / params.l
    sqrt_err = (
        (r[0] + x) * D(inv_err)
        + D(r[0]) * (r[0] + x / params.l) / D("1e38")
        + D(x) ** 2 / D(params.l) ** 2 / D("1e38")
    )
    if swap_sqrt > 0:
        sqrt_err = sqrt_err / (2 * D(swap_sqrt))
    else:
        sqrt_err = D(sqrt_err).sqrt()
    swap_err_xy = 1000 * (params.l * inv_err + sqrt_err) / denominator

    # now do the other direction swap as well
    swap_sqrt = prec_impl.solveQuadraticSwap(
        params.l,
        balances[1],
        params.c,
        params.s,
        r,
        [b, a],
        [-derived.tauAlpha[0], derived.tauAlpha[1]],
        derived.dSq,
    )
    denominator = D(1) - D(params.c) ** 2 + D(params.c) ** 2 / params.l / params.l
    sqrt_err = (
        (r[0] + y) * D(inv_err)
        + D(r[0]) * (r[0] + y / params.l) / D("1e38")
        + D(y) ** 2 / D(params.l) ** 2 / D("1e38")
    )
    if swap_sqrt > 0:
        sqrt_err = sqrt_err / (2 * D(swap_sqrt))
    else:
        sqrt_err = D(sqrt_err).sqrt()
    swap_err_yx = 1000 * (params.l * inv_err + sqrt_err) / denominator

    return swap_err_xy, swap_err_yx


@settings(suppress_health_check=[HealthCheck.filter_too_much])
@given(params=gen_params(), balances=gen_balances(2, bpool_params))
def test_calcYGivenX_error_not_too_bad(params, balances):
    derived = prec_impl.calc_derived_values(params)
    denominator = prec_impl.calcAChiAChiInXp(params, derived) - D2(1)
    assume(denominator > D2("1E-5"))  # if this is not the case, error can blow up
    assume(sum(balances) > D(100))

    invariant, err = prec_impl.calculateInvariantWithError(balances, params, derived)
    r = (invariant + 2 * D(err), invariant)

    # calculate swap error tolerance
    swap_err_xy, swap_err_yx = calculate_swap_error(params, balances, r, derived)

    y_py = prec_impl.calcYGivenX(balances[0], params, derived, r)
    # assert swap_err_xy < D("1e-3")
    assert (y_py - balances[1]) < D("1e-8")

    x_py = prec_impl.calcXGivenY(balances[1], params, derived, r)
    # assert swap_err_yx < D("1e-3")
    assert (x_py - balances[0]) < D("1e-8")


@settings(suppress_health_check=[HealthCheck.filter_too_much])
@given(
    params=gen_params(),
    balances=gen_balances(2, bpool_params),
)
def test_calcYGivenX_sense_check(params, balances):
    derived = prec_impl.calc_derived_values(params)
    denominator = prec_impl.calcAChiAChiInXp(params, derived) - D2(1)
    assume(denominator > D2("1E-5"))  # if this is not the case, error can blow up
    assume(sum(balances) > D(100))

    invariant, err = prec_impl.calculateInvariantWithError(balances, params, derived)
    r = (invariant + 2 * D(err), invariant)

    y_py = prec_impl.calcYGivenX(balances[0], params, derived, r)
    x_py = prec_impl.calcXGivenY(balances[1], params, derived, r)

    mparams = params2MathParams(paramsTo100(params))
    # sense test against old implementation
    midprice = (mparams.alpha + mparams.beta) / D3(2)
    cemm = mimpl.CEMM.from_px_r(
        midprice, convd(invariant, D3), mparams
    )  # Price doesn't matter.
    y = cemm._compute_y_for_x(convd(balances[0], D3))
    assume(y is not None)  # O/w out of bounds for this invariant
    assume(balances[0] > 0 and y > 0)
    assert convd(y, D3) == y_py.approxed(abs=D("1e-8"))

    # sense test against old implementation
    midprice = (mparams.alpha + mparams.beta) / D3(2)
    cemm = mimpl.CEMM.from_px_r(
        midprice, convd(invariant, D3), mparams
    )  # Price doesn't matter.
    x = cemm._compute_x_for_y(convd(balances[1], D3))
    assume(x is not None)  # O/w out of bounds for this invariant
    assume(balances[1] > 0 and x > 0)
    assert convd(x, D3) == x_py.approxed(abs=D("1e-8"))


@given(params=gen_params(), balances=gen_balances(2, bpool_params))
def test_maxBalances(gyro_cemm_math_testing, params, balances):
    derived = prec_impl.calc_derived_values(params)
    derived_scaled = prec_impl.scale_derived_values(derived)
    invariant, err = prec_impl.calculateInvariantWithError(balances, params, derived)
    r = (invariant + 2 * D(err), invariant)

    xp_py = prec_impl.maxBalances0(params, derived, r)
    yp_py = prec_impl.maxBalances1(params, derived, r)
    xp_sol = gyro_cemm_math_testing.maxBalances0(
        scale(params), derived_scaled, scale(r)
    )
    yp_sol = gyro_cemm_math_testing.maxBalances1(
        scale(params), derived_scaled, scale(r)
    )
    assert xp_py == unscale(xp_sol)
    assert yp_py == unscale(yp_sol)


@given(
    params=gen_params(),
    balances=gen_balances(2, bpool_params),
)
def test_maxBalances_sense_check(params, balances):
    derived = prec_impl.calc_derived_values(params)

    denominator = prec_impl.calcAChiAChiInXp(params, derived) - D2(1)
    assume(denominator > D2("1E-5"))  # if this is not the case, error can blow up

    invariant, err = prec_impl.calculateInvariantWithError(balances, params, derived)
    r = (invariant + 2 * D(err), invariant)
    xp_py = prec_impl.maxBalances0(params, derived, r)
    yp_py = prec_impl.maxBalances1(params, derived, r)
    # sense test against old implementation
    mparams = params2MathParams(paramsTo100(params))
    midprice = (mparams.alpha + mparams.beta) / D3(2)
    cemm = mimpl.CEMM.from_px_r(midprice, convd(invariant, D3), mparams)

    err_tol = D(err) * params.l * 5
    assert xp_py == convd(cemm.xmax, D3).approxed(abs=err_tol)
    assert yp_py == convd(cemm.ymax, D3).approxed(abs=err_tol)

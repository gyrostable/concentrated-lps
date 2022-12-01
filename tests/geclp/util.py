from math import pi, sin, cos, tan, acos

from hypothesis import strategies as st, assume, event

from brownie import reverts

from tests.geclp import eclp as mimpl
from tests.geclp import eclp_prec_implementation as prec_impl
from tests.libraries import pool_math_implementation
from tests.support.quantized_decimal import QuantizedDecimal as D
from tests.support.quantized_decimal_38 import QuantizedDecimal as D2
from tests.support.types import ECLPMathParams, ECLPMathDerivedParams, Vector2
from tests.support.util_common import BasicPoolParameters, gen_balances
from tests.support.utils import qdecimals, scale, to_decimal, unscale

MIN_PRICE_SEPARATION = D("0.001")
MIN_BALANCE_RATIO = D(0)  # D("1e-5")

bpool_params = BasicPoolParameters(
    MIN_PRICE_SEPARATION,
    D("0.3"),
    D("0.3"),
    MIN_BALANCE_RATIO,
    D("0.0001"),
    int(D("1e11")),
)


def params2MathParams(params: ECLPMathParams) -> mimpl.Params:
    """The python math implementation is a bit older and uses its own data structures. This function converts."""
    return mimpl.Params(params.alpha, params.beta, params.c, -params.s, params.l)


def mathParams2DerivedParams(mparams: mimpl.Params) -> ECLPMathDerivedParams:
    return prec_impl.calc_derived_values(
        mparams
    )  # Type mismatch but "duck" compatible.


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
    l = draw(qdecimals("1", "1e8"))
    return ECLPMathParams(alpha, beta, D(c), D(s), l)


@st.composite
def gen_params_eclp_dinvariant(draw):
    params = draw(gen_params())
    derived = prec_impl.calc_derived_values(params)
    balances = draw(gen_balances(2, bpool_params))
    # assume(balances[0] > 0 and balances[1] > 0)
    r = prec_impl.calculateInvariant(balances, params, derived)
    dinvariant = draw(
        qdecimals(-r * (D(1) - D("1e-5")), 2 * r)
    )  # Upper bound kinda arbitrary
    # assume(abs(dinvariant) > D("1E-10"))  # Only relevant updates
    return params, balances, dinvariant


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


def get_derived_parameters(params, is_solidity: bool, gyro_eclp_math_testing):
    if is_solidity:
        derived_sol = mk_ECLPMathDerivedParams_from_brownie(
            gyro_eclp_math_testing.mkDerivedParams(scale(params))
        )
        derived = ECLPMathDerivedParams(
            Vector2(unscale(derived_sol[0][0]), unscale(derived_sol[0][1])),
            Vector2(unscale(derived_sol[1][0]), unscale(derived_sol[1][1])),
        )
        return derived_sol
    else:
        mparams = params2MathParams(params)
        derived = ECLPMathDerivedParams(
            Vector2(mparams.tau_alpha[0], mparams.tau_alpha[1]),
            Vector2(mparams.tau_beta[0], mparams.tau_beta[1]),
        )
        return derived


#####################################################################
### helper functions for testing math library


def mtest_mulA(params: ECLPMathParams, t: Vector2, gyro_eclp_math_testing):
    mparams = params2MathParams(params)
    res_sol = gyro_eclp_math_testing.mulA(scale(params), scale(t))
    res_math = mparams.A_times(t.x, t.y)
    # For some reason we need to convert here, o/w the test fails even when they are equal.
    assert int(res_sol[0]) == scale(res_math[0])
    assert int(res_sol[1]) == scale(res_math[1])


def mtest_zeta(params_px, gyro_eclp_math_testing):
    (
        params,
        px,
    ) = params_px  # Annoying manual unpacking b/c hypothesis is oddly limited at dependent arguments.
    mparams = params2MathParams(params)

    # DEBUG: WEIRD IMPORT ERROR!
    # Problem: mimpl is actually eclp_100.py, not geclp.py, which leads to problems.
    assert isinstance(mparams, mimpl.Params)  # Catch weird type error
    assert str(type(mparams)) == "<class 'tests.geclp.geclp.Params'>"

    res_sol = gyro_eclp_math_testing.zeta(scale(params), scale(px))
    res_math = mparams.zeta(px)
    assert int(res_sol) == scale(res_math)


def mtest_tau(params_px, gyro_eclp_math_testing):
    # tau is as precise as eta.
    params, px = params_px
    mparams = params2MathParams(params)
    res_sol = gyro_eclp_math_testing.tau(scale(params), scale(px))
    res_math = mparams.tau(px)
    assert int(res_sol[0]) == scale(res_math[0]).approxed(abs=D("1e5"), rel=D("1e-16"))
    assert int(res_sol[1]) == scale(res_math[1]).approxed(abs=D("1e5"), rel=D("1e-16"))


# TODO: this is out of date with new refactor
def mk_ECLPMathDerivedParams_from_brownie(args):
    apair, bpair = args
    return ECLPMathDerivedParams(Vector2(*apair), Vector2(*bpair))


# TODO: this is out of date with new refactor
def mtest_mkDerivedParams(params, gyro_eclp_math_testing):
    # Accuracy of the derived params is that of tau.
    mparams = params2MathParams(params)
    derived_sol = mk_ECLPMathDerivedParams_from_brownie(
        gyro_eclp_math_testing.mkDerivedParams(scale(params))
    )
    assert int(derived_sol.tauAlpha.x) == scale(mparams.tau_alpha[0]).approxed(
        abs=D("1e5"), rel=D("1e-16")
    )
    assert int(derived_sol.tauAlpha.y) == scale(mparams.tau_alpha[1]).approxed(
        abs=D("1e5"), rel=D("1e-16")
    )
    assert int(derived_sol.tauBeta.x) == scale(mparams.tau_beta[0]).approxed(
        abs=D("1e5"), rel=D("1e-16")
    )
    assert int(derived_sol.tauBeta.y) == scale(mparams.tau_beta[1]).approxed(
        abs=D("1e5"), rel=D("1e-16")
    )


# TODO: this is out of date with new refactor
def mtest_validateParamsAll(params, gyro_eclp_math_testing):
    mparams = params2MathParams(params)
    derived = mathParams2DerivedParams(mparams)

    # Don't revert on the values computed by python
    gyro_eclp_math_testing.validateDerivedParams(scale(params), scale(derived))
    gyro_eclp_math_testing.validateParams(scale(params))

    # Revert for distorted values: Params
    offset = D("2E-8")
    bad_params = params._replace(c=params.c + offset)
    with reverts("BAL#356"):
        gyro_eclp_math_testing.validateParams(scale(bad_params))

    # Revert for distorted values: Derived params
    # Non-normed:
    bad_derived = ECLPMathDerivedParams(
        Vector2(derived.tauAlpha.x + offset, derived.tauAlpha.y + offset),
        derived.tauBeta,
    )
    with reverts("BAL#358"):
        gyro_eclp_math_testing.validateDerivedParams(scale(params), scale(bad_derived))

    bad_derived = ECLPMathDerivedParams(
        derived.tauAlpha,
        Vector2(derived.tauBeta.x + offset, derived.tauBeta.y + offset),
    )
    with reverts("BAL#358"):
        gyro_eclp_math_testing.validateDerivedParams(scale(params), scale(bad_derived))

    # Normed but zeta doesn't match
    angle = acos(float(derived.tauAlpha.x))
    offset = 1e-6
    bad_derived = ECLPMathDerivedParams(
        Vector2(D(cos(angle + offset)), D(sin(angle + offset))),
        derived.tauBeta,
    )
    with reverts("BAL#359"):
        gyro_eclp_math_testing.validateDerivedParams(scale(params), scale(bad_derived))

    angle = acos(float(derived.tauBeta.x))
    bad_derived = ECLPMathDerivedParams(
        derived.tauAlpha,
        Vector2(D(cos(angle + offset)), D(sin(angle + offset))),
    )
    with reverts("BAL#359"):
        gyro_eclp_math_testing.validateDerivedParams(scale(params), scale(bad_derived))


def gen_synthetic_invariant():
    """Generate invariant for cases where it *doesn't* have to match any balances."""
    return qdecimals(1, 100_000_000_000)


# TODO: this is out of date with new refactor
def gtest_virtualOffsets(params, invariant, derived, gyro_eclp_math_testing, abs, rel):
    mparams = params2MathParams(params)
    a_sol = gyro_eclp_math_testing.virtualOffset0(
        scale(params), scale(derived), scale(invariant)
    )
    b_sol = gyro_eclp_math_testing.virtualOffset1(
        scale(params), scale(derived), scale(invariant)
    )

    # The python implementation has this function part of the pool structure even though it only needs the invariant.
    a_py = prec_impl.virtualOffset0(params, derived, invariant)
    b_py = prec_impl.virtualOffset1(params, derived, invariant)

    assert int(a_sol) == scale(a_py).approxed(abs=abs, rel=rel)
    assert int(b_sol) == scale(b_py).approxed(abs=abs, rel=rel)


# TODO: this is out of date with new refactor
def mtest_virtualOffsets_noderived(params, invariant, gyro_eclp_math_testing):
    """Test Calculation of just the virtual offsets, not including the derived params calculation. This is exact."""
    derived = mathParams2DerivedParams(params2MathParams(params))
    return gtest_virtualOffsets(
        params, invariant, derived, gyro_eclp_math_testing, 0, 0
    )


# TODO: this is out of date with new refactor
def mtest_virtualOffsets_with_derived(params, invariant, gyro_eclp_math_testing):
    """Test Calculation of just the virtual offsets, not including the derived params calculation. This is exact."""
    derived_scaled = mk_ECLPMathDerivedParams_from_brownie(
        gyro_eclp_math_testing.mkDerivedParams(scale(params))
    )
    derived = ECLPMathDerivedParams(
        Vector2(unscale(derived_scaled[0][0]), unscale(derived_scaled[0][1])),
        Vector2(unscale(derived_scaled[1][0]), unscale(derived_scaled[1][1])),
    )
    return gtest_virtualOffsets(
        params, invariant, derived, gyro_eclp_math_testing, D("1e5"), D("1e-16")
    )


def mtest_maxBalances(params, invariant, gyro_eclp_math_testing):
    derived = prec_impl.calc_derived_values(params)
    derived_scaled = prec_impl.scale_derived_values(derived)
    # just pick something for overestimate
    r = (D(invariant) * (D(1) + D("1e-15")), invariant)
    x_plus_sol = gyro_eclp_math_testing.maxBalances0(
        scale(params), derived_scaled, scale(r)
    )
    y_plus_sol = gyro_eclp_math_testing.maxBalances1(
        scale(params), derived_scaled, scale(r)
    )
    xp_py = prec_impl.maxBalances0(params, derived, r)
    yp_py = prec_impl.maxBalances1(params, derived, r)

    assert int(x_plus_sol) == scale(xp_py)
    assert int(y_plus_sol) == scale(yp_py)


#####################################################################
### for testing the main math library functions
# note in new implementation, derivedparams_is_sol is not possible


def mtest_calculateInvariant(
    params, balances, derivedparams_is_sol: bool, gyro_eclp_math_testing
):
    derived = prec_impl.calc_derived_values(params)
    derived_scaled = prec_impl.scale_derived_values(derived)

    uinvariant_sol = gyro_eclp_math_testing.calculateInvariant(
        scale(balances), scale(params), derived_scaled
    )
    result_py = prec_impl.calculateInvariant(balances, params, derived)

    return (
        result_py,
        D(int(uinvariant_sol)),
    )


def mtest_calculatePrice(
    params, balances, derivedparams_is_sol: bool, gyro_eclp_math_testing
):
    assume(balances != (0, 0))

    mparams = params2MathParams(params)
    derived = prec_impl.calc_derived_values(params)
    derived_scaled = prec_impl.scale_derived_values(derived)

    eclp = mimpl.ECLP.from_x_y(balances[0], balances[1], mparams)

    price_sol = gyro_eclp_math_testing.calculatePrice(
        scale(balances), scale(params), derived_scaled, scale(eclp.r)
    )

    return eclp.px, to_decimal(price_sol)


# note r argument is tuple
def mtest_calcYGivenX(params, x, r, derivedparams_is_sol: bool, gyro_eclp_math_testing):
    assume(x == 0 if r[1] == 0 else True)

    derived = prec_impl.calc_derived_values(params)
    derived_scaled = prec_impl.scale_derived_values(derived)

    y = prec_impl.calcYGivenX(x, params, derived, r)
    y_plus = prec_impl.maxBalances1(params, derived, r)

    assume(y < y_plus)  # O/w out of bounds for this invariant
    assume(x > 0 and y > 0)

    y_sol = gyro_eclp_math_testing.calcYGivenX(
        scale(x), scale(params), derived_scaled, scale(r)
    )
    return y, to_decimal(y_sol)


# note r argument is tuple
def mtest_calcXGivenY(params, y, r, derivedparams_is_sol: bool, gyro_eclp_math_testing):
    assume(y == 0 if r[1] == 0 else True)

    derived = prec_impl.calc_derived_values(params)
    derived_scaled = prec_impl.scale_derived_values(derived)

    x = prec_impl.calcXGivenY(y, params, derived, r)
    x_plus = prec_impl.maxBalances0(params, derived, r)

    assume(x < x_plus)  # O/w out of bounds for this invariant
    assume(x > 0 and y > 0)

    x_sol = gyro_eclp_math_testing.calcXGivenY(
        scale(y), scale(params), derived_scaled, scale(r)  # scale(geclp.r)
    )
    return x, to_decimal(x_sol)


def mtest_calcOutGivenIn(
    params,
    balances,
    amountIn,
    tokenInIsToken0,
    derivedparams_is_sol: bool,
    gyro_eclp_math_testing,
):
    ixIn = 0 if tokenInIsToken0 else 1
    ixOut = 1 - ixIn

    derived = prec_impl.calc_derived_values(params)
    derived_scaled = prec_impl.scale_derived_values(derived)

    invariant, inv_err = prec_impl.calculateInvariantWithError(
        balances, params, derived
    )
    r = (invariant + 2 * D(inv_err), invariant)
    if tokenInIsToken0:
        mamountOut = (
            prec_impl.calcYGivenX(balances[0] + amountIn, params, derived, r)
            - balances[1]
        )
    else:
        mamountOut = (
            prec_impl.calcXGivenY(balances[1] + amountIn, params, derived, r)
            - balances[0]
        )
    x_plus = prec_impl.maxBalances0(params, derived, r)
    y_plus = prec_impl.maxBalances1(params, derived, r)

    # calculate balanceOut after swap to determine if a revert could happen
    if ixOut == 0:
        x, balOutNew_sol = mtest_calcXGivenY(
            params,
            balances[ixIn] + amountIn,
            r,
            derivedparams_is_sol,
            gyro_eclp_math_testing,
        )
    else:
        y, balOutNew_sol = mtest_calcYGivenX(
            params,
            balances[ixIn] + amountIn,
            r,
            derivedparams_is_sol,
            gyro_eclp_math_testing,
        )

    revertCode = None
    if amountIn + balances[ixIn] > (x_plus if tokenInIsToken0 else y_plus):
        revertCode = "GYR#357"  # ASSET_BONDS_EXCEEDED
    elif unscale(balOutNew_sol) > balances[ixOut]:
        revertCode = "BAL#001"  # subtraction underflow

    if revertCode is not None:
        with reverts(revertCode):
            gyro_eclp_math_testing.calcOutGivenIn(
                scale(balances),
                scale(amountIn),
                tokenInIsToken0,
                scale(params),
                derived_scaled,
                scale(r),
            )
        return 0, 0

    amountOut = -mamountOut

    amountOut_sol = gyro_eclp_math_testing.calcOutGivenIn(
        scale(balances),
        scale(amountIn),
        tokenInIsToken0,
        scale(params),
        derived_scaled,
        scale(r),
    )

    return amountOut, to_decimal(amountOut_sol)


def mtest_calcInGivenOut(
    params,
    balances,
    amountOut,
    tokenInIsToken0,
    derivedparams_is_sol: bool,
    gyro_eclp_math_testing,
):
    ixIn = 0 if tokenInIsToken0 else 1
    ixOut = 1 - ixIn

    assume(amountOut <= balances[ixOut])

    derived = prec_impl.calc_derived_values(params)
    derived_scaled = prec_impl.scale_derived_values(derived)

    invariant, inv_err = prec_impl.calculateInvariantWithError(
        balances, params, derived
    )
    r = (invariant + 2 * D(inv_err), invariant)
    if tokenInIsToken0:
        amountIn = (
            prec_impl.calcXGivenY(balances[1] - amountOut, params, derived, r)
            - balances[0]
        )
    else:
        amountIn = (
            prec_impl.calcYGivenX(balances[0] - amountOut, params, derived, r)
            - balances[1]
        )
    x_plus = prec_impl.maxBalances0(params, derived, r)
    y_plus = prec_impl.maxBalances1(params, derived, r)

    # calculate balanceIn after swap to determine if a revert could happen
    if ixIn == 0:
        x, balInNew_sol = mtest_calcXGivenY(
            params,
            balances[ixOut] - amountOut,
            r,
            derivedparams_is_sol,
            gyro_eclp_math_testing,
        )
    else:
        y, balInNew_sol = mtest_calcYGivenX(
            params,
            balances[ixOut] - amountOut,
            r,
            derivedparams_is_sol,
            gyro_eclp_math_testing,
        )

    revertCode = None
    if amountIn is None:
        revertCode = "GYR#357"  # ASSET_BOUNDS_EXCEEDED
    elif unscale(balInNew_sol) > (x_plus if tokenInIsToken0 else y_plus):
        revertCode = "GYR#357"  # ASSET_BOUNDS_EXCEEDED
    elif unscale(balInNew_sol) < balances[ixIn]:
        revertCode = "BAL#001"  # subtraction underflow

    if revertCode is not None:
        with reverts(revertCode):
            gyro_eclp_math_testing.calcInGivenOut(
                scale(balances),
                scale(amountOut),
                tokenInIsToken0,
                scale(params),
                derived_scaled,
                scale(r),
            )
        return 0, 0

    amountIn_sol = gyro_eclp_math_testing.calcInGivenOut(
        scale(balances),
        scale(amountOut),
        tokenInIsToken0,
        scale(params),
        derived_scaled,
        scale(r),
    )
    return amountIn, to_decimal(amountIn_sol)


# TODO: needs refactor
def mtest_liquidityInvariantUpdate(params_eclp_dinvariant, gyro_eclp_math_testing):
    params, balances, dinvariant = params_eclp_dinvariant
    derived = prec_impl.calc_derived_values(params)
    derived_scaled = prec_impl.scale_derived_values(derived)
    invariant = prec_impl.calculateInvariant(balances, params, derived)
    deltaBalances = (
        dinvariant / invariant * balances[0],
        dinvariant / invariant * balances[1],
    )
    deltaBalances = (
        abs(deltaBalances[0]),
        abs(deltaBalances[1]),
    )  # b/c solidity function takes uint inputs for this

    rnew = invariant + dinvariant
    rnew_sol = gyro_eclp_math_testing.liquidityInvariantUpdate(
        scale(balances),
        scale(invariant),
        scale(deltaBalances),
        (dinvariant >= 0),
    )

    return rnew, to_decimal(rnew_sol)


# def mtest_liquidityInvariantUpdateEquivalence(
#     params_eclp_dinvariant, gyro_eclp_math_testing
# ):
#     """Tests a mathematical fact. Doesn't test solidity."""
#     params, balances, dinvariant = params_eclp_dinvariant
#     mparams = params2MathParams(params)
#     derived = mathParams2DerivedParams(mparams)
#     invariant = prec_impl.calculateInvariant(balances, params, derived)

#     dx, dy = deltaBalances = (
#         dinvariant / invariant * balances[0],
#         dinvariant / invariant * balances[1],
#     )

#     # To try it out even
#     assert dx == (dinvariant / r * geclp.x).approxed(abs=1e-5)
#     assert dy == (dinvariant / r * geclp.y).approxed(abs=1e-5)


#####################################################################
### for testing invariant changes across swaps


def faulty_params(balances, params: ECLPMathParams, bpool_params: BasicPoolParameters):
    balances = [to_decimal(b) for b in balances]
    if balances[0] == 0 and balances[1] == 0:
        return True
    return 0 >= params.beta - params.alpha >= bpool_params.min_price_separation


def calculate_loss(delta_invariant, invariant, balances):
    # delta_balance_A = delta_invariant / invariant * balance_A
    factor = to_decimal(delta_invariant / invariant)
    return (to_decimal(balances[0]) * factor, to_decimal(balances[1]) * factor)


def mtest_invariant_across_calcOutGivenIn(
    params,
    balances,
    amountIn,
    tokenInIsToken0,
    derivedparams_is_sol: bool,
    bpool_params,
    gyro_eclp_math_testing,
):
    ixIn = 0 if tokenInIsToken0 else 1
    ixOut = 1 - ixIn

    fees = bpool_params.min_fee * amountIn
    amountIn -= fees

    derived = prec_impl.calc_derived_values(params)
    derived_scaled = prec_impl.scale_derived_values(derived)

    invariant_before = prec_impl.calculateInvariant(balances, params, derived)
    invariant_sol, inv_err_sol = gyro_eclp_math_testing.calculateInvariantWithError(
        scale(balances), scale(params), derived_scaled
    )
    r = (unscale(invariant_sol) + 2 * D(unscale(inv_err_sol)), unscale(invariant_sol))

    if tokenInIsToken0:
        mamountOut = (
            prec_impl.calcYGivenX(balances[0] + amountIn, params, derived, r)
            - balances[1]
        )
    else:
        mamountOut = (
            prec_impl.calcXGivenY(balances[1] + amountIn, params, derived, r)
            - balances[0]
        )
    x_plus = prec_impl.maxBalances0(params, derived, r)
    y_plus = prec_impl.maxBalances1(params, derived, r)

    # calculate balanceOut after swap to determine if a revert could happen
    if ixOut == 0:
        x, balOutNew_sol = mtest_calcXGivenY(
            params,
            balances[ixIn] + amountIn,
            r,
            derivedparams_is_sol,
            gyro_eclp_math_testing,
        )
    else:
        y, balOutNew_sol = mtest_calcYGivenX(
            params,
            balances[ixIn] + amountIn,
            r,
            derivedparams_is_sol,
            gyro_eclp_math_testing,
        )

    revertCode = None
    if amountIn + balances[ixIn] > (x_plus if tokenInIsToken0 else y_plus):
        revertCode = "GYR#357"  # ASSET_BOUNDS_EXCEEDED
    elif unscale(balOutNew_sol) > balances[ixOut]:
        revertCode = "BAL#001"  # subtraction underflow

    if revertCode is not None:
        with reverts(revertCode):
            gyro_eclp_math_testing.calcOutGivenIn(
                scale(balances),
                scale(amountIn),
                tokenInIsToken0,
                scale(params),
                derived_scaled,
                scale(r),
            )
        return (0, 0), (0, 0)

    amountOut = -mamountOut

    amountOut_sol = gyro_eclp_math_testing.calcOutGivenIn(
        scale(balances),
        scale(amountIn),
        tokenInIsToken0,
        scale(params),
        derived_scaled,
        scale(r),
    )

    if tokenInIsToken0:
        new_balances = (
            balances[0] + amountIn + fees,
            balances[1] - unscale(to_decimal(amountOut_sol)),
        )
    else:
        new_balances = (
            balances[0] - unscale(to_decimal(amountOut_sol)),
            balances[1] + amountIn + fees,
        )

    invariant_after = prec_impl.calculateInvariant(
        [new_balances[0], new_balances[1]], params, derived
    )

    invariant_sol_after = gyro_eclp_math_testing.calculateInvariant(
        scale(new_balances), scale(params), derived_scaled
    )

    # Event to tell these apart from (checked) error cases.
    event("full check")

    if invariant_after < invariant_before:
        loss_py = calculate_loss(
            invariant_after - invariant_before, invariant_before, balances
        )
    else:
        loss_py = (D(0), D(0))

    if invariant_sol_after < invariant_sol:
        loss_sol = calculate_loss(
            unscale(invariant_sol_after - invariant_sol),
            unscale(invariant_sol),
            balances,
        )
    else:
        loss_sol = (D(0), D(0))

    return loss_py, loss_sol


def mtest_invariant_across_calcInGivenOut(
    params,
    balances,
    amountOut,
    tokenInIsToken0,
    derivedparams_is_sol: bool,
    bpool_params,
    gyro_eclp_math_testing,
):
    ixIn = 0 if tokenInIsToken0 else 1
    ixOut = 1 - ixIn

    assume(amountOut <= balances[ixOut])

    derived = prec_impl.calc_derived_values(params)
    derived_scaled = prec_impl.scale_derived_values(derived)

    invariant_before = prec_impl.calculateInvariant(balances, params, derived)
    invariant_sol, inv_err_sol = gyro_eclp_math_testing.calculateInvariantWithError(
        scale(balances), scale(params), derived_scaled
    )
    r = (unscale(invariant_sol) + 2 * D(unscale(inv_err_sol)), unscale(invariant_sol))

    if tokenInIsToken0:
        amountIn = (
            prec_impl.calcXGivenY(balances[1] - amountOut, params, derived, r)
            - balances[0]
        )
    else:
        amountIn = (
            prec_impl.calcYGivenX(balances[0] - amountOut, params, derived, r)
            - balances[1]
        )
    x_plus = prec_impl.maxBalances0(params, derived, r)
    y_plus = prec_impl.maxBalances1(params, derived, r)

    # calculate balanceIn after swap to determine if a revert could happen
    if ixIn == 0:
        x, balInNew_sol = mtest_calcXGivenY(
            params,
            balances[ixOut] - amountOut,
            r,
            derivedparams_is_sol,
            gyro_eclp_math_testing,
        )
    else:
        y, balInNew_sol = mtest_calcYGivenX(
            params,
            balances[ixOut] - amountOut,
            r,
            derivedparams_is_sol,
            gyro_eclp_math_testing,
        )

    revertCode = None
    if amountIn is None:
        revertCode = "GYR#357"  # ASSET_BOUNDS_EXCEEDED
    elif unscale(balInNew_sol) > (x_plus if tokenInIsToken0 else y_plus):
        revertCode = "GYR#357"  # ASSET_BOUNDS_EXCEEDED
    elif unscale(balInNew_sol) < balances[ixIn]:
        revertCode = "BAL#001"  # subtraction underflow

    ## this is already tested in other functions anyway
    if revertCode is not None:
        with reverts(revertCode):
            gyro_eclp_math_testing.calcInGivenOut(
                scale(balances),
                scale(amountOut),
                tokenInIsToken0,
                scale(params),
                derived_scaled,
                scale(r),
            )
        return (0, 0), (0, 0)

    amountIn_sol = gyro_eclp_math_testing.calcInGivenOut(
        scale(balances),
        scale(amountOut),
        tokenInIsToken0,
        scale(params),
        derived_scaled,
        scale(r),
    )

    if tokenInIsToken0:
        new_balances = (
            balances[0]
            + unscale(to_decimal(amountIn_sol)) * (D(1) + bpool_params.min_fee),
            balances[1] - amountOut,
        )
    else:
        new_balances = (
            balances[0] - amountOut,
            balances[1]
            + unscale(to_decimal(amountIn_sol)) * (D(1) + bpool_params.min_fee),
        )

    invariant_after = prec_impl.calculateInvariant(
        [new_balances[0], new_balances[1]], params, derived
    )
    invariant_sol_after = gyro_eclp_math_testing.calculateInvariant(
        scale(new_balances), scale(params), derived_scaled
    )

    if invariant_after < invariant_before:
        loss_py = calculate_loss(
            invariant_after - invariant_before, invariant_before, balances
        )
    else:
        loss_py = (D(0), D(0))

    if invariant_sol_after < invariant_sol:
        loss_sol = calculate_loss(
            unscale(invariant_sol_after - invariant_sol),
            unscale(invariant_sol),
            balances,
        )
    else:
        loss_sol = (D(0), D(0))

    return loss_py, loss_sol


def mtest_invariant_across_liquidityInvariantUpdate(
    params_eclp_invariantUpdate, gyro_eclp_math_testing
):
    params, balances, bpt_supply, isIncrease, dsupply = params_eclp_invariantUpdate
    derived = prec_impl.calc_derived_values(params)

    denominator = prec_impl.calcAChiAChiInXp(params, derived) - D2(1)
    # Debug code for debugging the tests (sample generation)
    # print("\nDEBUG AFTER fun start")
    assume(denominator > D2("1E-5"))  # if this is not the case, error can blow up
    # print("DEBUG AFTER denom check")
    assume(sum(balances) > D(100))
    # print("DEBUG AFTER balances check")

    derived_scaled = prec_impl.scale_derived_values(derived)
    invariant_before, err_before = prec_impl.calculateInvariantWithError(
        balances, params, derived
    )
    if isIncrease:
        dBalances = gyro_eclp_math_testing._calcAllTokensInGivenExactBptOut(
            scale(balances), scale(dsupply), scale(bpt_supply)
        )
        new_balances = [
            balances[0] + unscale(dBalances[0]),
            balances[1] + unscale(dBalances[1]),
        ]
    else:
        dBalances = gyro_eclp_math_testing._calcTokensOutGivenExactBptIn(
            scale(balances), scale(dsupply), scale(bpt_supply)
        )
        new_balances = [
            balances[0] - unscale(dBalances[0]),
            balances[1] - unscale(dBalances[1]),
        ]

    invariant_updated = unscale(
        gyro_eclp_math_testing.liquidityInvariantUpdate(
            scale(invariant_before), scale(dsupply), scale(bpt_supply), isIncrease
        )
    )
    invariant_after, err_after = prec_impl.calculateInvariantWithError(
        new_balances, params, derived
    )
    # abs_tol = D(2) * (
    #     D(err_before) + D(err_after) + (D("1e-18") * invariant_before) / bpt_supply
    # )
    # rel_tol = D("1e-16") / min(D(1), bpt_supply)
    # if D(invariant_updated) != D(invariant_after).approxed(abs=abs_tol, rel=rel_tol):
    if isIncrease and invariant_updated < invariant_after:
        loss = calculate_loss(
            invariant_updated - invariant_after, invariant_after, new_balances
        )
    elif not isIncrease and invariant_updated > invariant_after:
        # We use `err_after` to compensate for errors in the invariant calculation itself. We don't have to do this
        # above b/c calculateInvariantWithError() yields an underestimate and this is already the worst case there.
        loss = calculate_loss(
            invariant_after + err_after - invariant_updated,
            invariant_after + err_after,
            new_balances,
        )
    else:
        loss = (D(0), D(0))
    loss_ub = loss[0] * params.beta + loss[1]
    assert abs(loss_ub) < D("1e-1")


# def mtest_invariant_across_liquidityInvariantUpdate(
#     gyro_eclp_math_testing, params_eclp_dinvariant, derivedparams_is_sol: bool
# ):
#     params, balances, dinvariant = params_eclp_dinvariant

#     derived = prec_impl.calc_derived_values(params)
#     derived_scaled = prec_impl.scale_derived_values(derived)

#     invariant, inv_err = prec_impl.calculateInvariantWithError(
#         balances, params, derived
#     )
#     deltaBalances = (
#         dinvariant / invariant * balances[0],
#         dinvariant / invariant * balances[1],
#     )

#     deltaBalances = (
#         abs(deltaBalances[0]),
#         abs(deltaBalances[1]),
#     )  # b/c solidity function takes uint inputs for this

#     rnew = invariant + dinvariant
#     rnew_sol = gyro_eclp_math_testing.liquidityInvariantUpdate(
#         scale(balances),
#         scale(invariant),
#         scale(deltaBalances),
#         (dinvariant >= 0),
#     )

#     if dinvariant >= 0:
#         new_balances = (balances[0] + deltaBalances[0], balances[1] + deltaBalances[1])
#     else:
#         new_balances = (balances[0] - deltaBalances[0], balances[1] - deltaBalances[1])

#     rnew_sol2 = gyro_eclp_math_testing.calculateInvariant(
#         scale(new_balances), scale(params), derived_scaled
#     )

#     rnew2, rnew2_err = prec_impl.calculateInvariantWithError(
#         new_balances, params, derived
#     )

#     assert D(rnew).approxed(abs=D(inv_err)) == D(rnew2).approxed(abs=D(rnew2_err))
# assert D(rnew) >= D(rnew2) - D("5e-17")  # * (D(1) - D("1e-12"))
# assert D(rnew) == D(rnew2).approxed(
#     abs=D("5e-17"), rel=D("5e-16")
# )  # .approxed(rel=D("1e-16"))
# the following assertion can fail if square root in solidity has error, but consequence is small (some small protocol fees)
# assert unscale(D(rnew_sol)).approxed(rel=D("1e-10")) >= unscale(
#     D(rnew_sol2)
# ).approxed(rel=D("1e-10"))
# assert unscale(D(rnew_sol)) == unscale(D(rnew_sol2)).approxed(
#     abs=D("5e-17"), rel=D("5e-16")
# )


def mtest_zero_tokens_in(gyro_eclp_math_testing, params, balances):
    derived = prec_impl.calc_derived_values(params)
    derived_scaled = prec_impl.scale_derived_values(derived)

    invariant_sol, inv_err_sol = gyro_eclp_math_testing.calculateInvariantWithError(
        scale(balances), scale(params), derived_scaled
    )
    r = (unscale(invariant_sol) + 2 * D(unscale(inv_err_sol)), unscale(invariant_sol))

    y_sol = gyro_eclp_math_testing.calcYGivenX(
        scale(balances[0]), scale(params), derived_scaled, scale(r)
    )
    assert balances[1] <= unscale(y_sol)
    x_sol = gyro_eclp_math_testing.calcXGivenY(
        scale(balances[1]), scale(params), derived_scaled, scale(r)
    )
    assert balances[0] <= unscale(x_sol)

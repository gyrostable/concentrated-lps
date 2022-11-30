from contextlib import contextmanager
from math import pi, sin, cos, tan, acos
from unicodedata import decimal

from hypothesis import strategies as st, assume, event

from brownie import reverts

from tests.cemm import cemm as mimpl
from tests.support.quantized_decimal import QuantizedDecimal as D
from tests.support.types import CEMMMathParams, CEMMMathDerivedParams, Vector2
from tests.support.utils import qdecimals, scale, to_decimal, unscale

MIN_PRICE_SEPARATION = D("0.001")


billion_balance_strategy = st.integers(min_value=0, max_value=1_000_000_000)


def params2MathParams(params: CEMMMathParams) -> mimpl.Params:
    """The python math implementation is a bit older and uses its own data structures. This function converts."""
    return mimpl.Params(params.alpha, params.beta, params.c, -params.s, params.l)


def mathParams2DerivedParams(mparams: mimpl.Params) -> CEMMMathDerivedParams:
    return CEMMMathDerivedParams(
        tauAlpha=Vector2(*mparams.tau_alpha), tauBeta=Vector2(*mparams.tau_beta)
    )


class Basic_Pool_Parameters:
    def __init__(
        self, mps: decimal, mir: decimal, mor: decimal, mbr: decimal, mf: decimal
    ):
        self.min_price_separation = mps
        self.max_in_ratio = mir
        self.max_out_ratio = mor
        self.min_balance_ratio = mbr
        self.min_fee = mf


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
    l = draw(qdecimals("1", "10"))
    return CEMMMathParams(alpha, beta, D(c), D(s), l)


def gen_balances_raw():
    return st.tuples(billion_balance_strategy, billion_balance_strategy)


@st.composite
def gen_balances(draw):
    balances = draw(gen_balances_raw())
    assume(balances[0] > 0 and balances[1] > 0)
    assume(balances[0] / balances[1] > 1e-5)
    assume(balances[1] / balances[0] > 1e-5)
    return balances


def gen_balances_vector():
    return gen_balances().map(lambda args: Vector2(*args))


@st.composite
def gen_params_cemm_dinvariant(draw):
    params = draw(gen_params())
    mparams = params2MathParams(params)
    balances = draw(gen_balances())
    cemm = mimpl.CEMM.from_x_y(balances[0], balances[1], mparams)
    dinvariant = draw(
        qdecimals(-cemm.r.raw, 2 * cemm.r.raw)
    )  # Upper bound kinda arbitrary
    assume(abs(dinvariant) > D("1E-10"))  # Only relevant updates
    return params, cemm, dinvariant


def get_derived_parameters(params, is_solidity: bool, gyro_cemm_math_testing):
    if is_solidity:
        derived_sol = mk_CEMMMathDerivedParams_from_brownie(
            gyro_cemm_math_testing.mkDerivedParams(scale(params))
        )
        return derived_sol
    else:
        mparams = params2MathParams(params)
        derived = CEMMMathDerivedParams(
            Vector2(mparams.tau_alpha[0], mparams.tau_alpha[1]),
            Vector2(mparams.tau_beta[0], mparams.tau_beta[1]),
        )
        return scale(derived)


#####################################################################
### helper functions for testing math library


def mtest_mulAinv(params: CEMMMathParams, t: Vector2, gyro_cemm_math_testing):
    mparams = params2MathParams(params)
    res_sol = gyro_cemm_math_testing.mulAinv(scale(params), scale(t))
    res_math = mparams.Ainv_times(t.x, t.y)
    # For some reason we need to convert here, o/w the test fails even when they are equal.
    # Note: This is scaled, so tolerance 10 means the previous to last decimal must match, the last one can differ.
    # There's no relative tolerance.
    assert int(res_sol[0]) == scale(res_math[0])
    assert int(res_sol[1]) == scale(res_math[1])


def mtest_mulA(params: CEMMMathParams, t: Vector2, gyro_cemm_math_testing):
    mparams = params2MathParams(params)
    res_sol = gyro_cemm_math_testing.mulA(scale(params), scale(t))
    res_math = mparams.A_times(t.x, t.y)
    # For some reason we need to convert here, o/w the test fails even when they are equal.
    assert int(res_sol[0]) == scale(res_math[0])
    assert int(res_sol[1]) == scale(res_math[1])


def mtest_zeta(params_px, gyro_cemm_math_testing):
    (
        params,
        px,
    ) = params_px  # Annoying manual unpacking b/c hypothesis is oddly limited at dependent arguments.
    mparams = params2MathParams(params)
    res_sol = gyro_cemm_math_testing.zeta(scale(params), scale(px))
    res_math = mparams.zeta(px)
    assert int(res_sol) == scale(res_math)


def mtest_tau(params_px, gyro_cemm_math_testing):
    # tau is as precise as eta.
    params, px = params_px
    mparams = params2MathParams(params)
    res_sol = gyro_cemm_math_testing.tau(scale(params), scale(px))
    res_math = mparams.tau(px)
    assert int(res_sol[0]) == scale(res_math[0]).approxed(abs=D("1e5"), rel=D("1e-16"))
    assert int(res_sol[1]) == scale(res_math[1]).approxed(abs=D("1e5"), rel=D("1e-16"))


def mk_CEMMMathDerivedParams_from_brownie(args):
    apair, bpair = args
    return CEMMMathDerivedParams(Vector2(*apair), Vector2(*bpair))


def mtest_mkDerivedParams(params, gyro_cemm_math_testing):
    # Accuracy of the derived params is that of tau.
    mparams = params2MathParams(params)
    derived_sol = mk_CEMMMathDerivedParams_from_brownie(
        gyro_cemm_math_testing.mkDerivedParams(scale(params))
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


def mtest_validateParamsAll(params, gyro_cemm_math_testing):
    mparams = params2MathParams(params)
    derived = mathParams2DerivedParams(mparams)

    # Don't revert on the values computed by python
    gyro_cemm_math_testing.validateDerivedParams(scale(params), scale(derived))
    gyro_cemm_math_testing.validateParams(scale(params))

    # Revert for distorted values: Params
    offset = D("2E-8")
    bad_params = params._replace(c=params.c + offset)
    with reverts("BAL#356"):
        gyro_cemm_math_testing.validateParams(scale(bad_params))

    # Revert for distorted values: Derived params
    # Non-normed:
    bad_derived = CEMMMathDerivedParams(
        Vector2(derived.tauAlpha.x + offset, derived.tauAlpha.y + offset),
        derived.tauBeta,
    )
    with reverts("BAL#358"):
        gyro_cemm_math_testing.validateDerivedParams(scale(params), scale(bad_derived))

    bad_derived = CEMMMathDerivedParams(
        derived.tauAlpha,
        Vector2(derived.tauBeta.x + offset, derived.tauBeta.y + offset),
    )
    with reverts("BAL#358"):
        gyro_cemm_math_testing.validateDerivedParams(scale(params), scale(bad_derived))

    # Normed but zeta doesn't match
    angle = acos(float(derived.tauAlpha.x))
    offset = 1e-6
    bad_derived = CEMMMathDerivedParams(
        Vector2(D(cos(angle + offset)), D(sin(angle + offset))),
        derived.tauBeta,
    )
    with reverts("BAL#359"):
        gyro_cemm_math_testing.validateDerivedParams(scale(params), scale(bad_derived))

    angle = acos(float(derived.tauBeta.x))
    bad_derived = CEMMMathDerivedParams(
        derived.tauAlpha,
        Vector2(D(cos(angle + offset)), D(sin(angle + offset))),
    )
    with reverts("BAL#359"):
        gyro_cemm_math_testing.validateDerivedParams(scale(params), scale(bad_derived))


def gen_synthetic_invariant():
    """Generate invariant for cases where it *doesn't* have to match any balances."""
    return qdecimals(1, 100_000_000_000)


def gtest_virtualOffsets(
    params, invariant, derived_scaled, gyro_cemm_math_testing, abs, rel
):
    mparams = params2MathParams(params)
    ab_sol = gyro_cemm_math_testing.virtualOffsets(
        scale(params), derived_scaled, scale(invariant)
    )

    # The python implementation has this function part of the pool structure even though it only needs the invariant.
    midprice = (mparams.alpha + mparams.beta) / D(2)
    cemm = mimpl.CEMM.from_px_r(midprice, invariant, mparams)

    assert int(ab_sol[0]) == scale(cemm.a).approxed(abs=abs, rel=rel)
    assert int(ab_sol[1]) == scale(cemm.b).approxed(abs=abs, rel=rel)


def mtest_virtualOffsets_noderived(params, invariant, gyro_cemm_math_testing):
    """Test Calculation of just the virtual offsets, not including the derived params calculation. This is exact."""
    derived_scaled = scale(mathParams2DerivedParams(params2MathParams(params)))
    return gtest_virtualOffsets(
        params, invariant, derived_scaled, gyro_cemm_math_testing, 0, 0
    )


def mtest_virtualOffsets_with_derived(params, invariant, gyro_cemm_math_testing):
    """Test Calculation of just the virtual offsets, not including the derived params calculation. This is exact."""
    derived_scaled = mk_CEMMMathDerivedParams_from_brownie(
        gyro_cemm_math_testing.mkDerivedParams(scale(params))
    )
    return gtest_virtualOffsets(
        params, invariant, derived_scaled, gyro_cemm_math_testing, D("1e5"), D("1e-16")
    )


def mtest_maxBalances(params, invariant, gyro_cemm_math_testing):
    mparams = params2MathParams(params)
    derived_sol = mk_CEMMMathDerivedParams_from_brownie(
        gyro_cemm_math_testing.mkDerivedParams(scale(params))
    )
    xy_sol = gyro_cemm_math_testing.maxBalances(
        scale(params), derived_sol, scale(invariant)
    )

    # The python implementation has this function part of the pool structure even though it only needs the invariant.
    midprice = (mparams.alpha + mparams.beta) / D(2)
    cemm = mimpl.CEMM.from_px_r(midprice, invariant, mparams)

    assert int(xy_sol[0]) == scale(cemm.xmax).approxed()
    assert int(xy_sol[1]) == scale(cemm.ymax).approxed()


#####################################################################
### for testing the main math library functions


def mtest_calculateInvariant(
    params, balances, derivedparams_is_sol: bool, gyro_cemm_math_testing
):
    mparams = params2MathParams(params)
    derived = get_derived_parameters(
        params, derivedparams_is_sol, gyro_cemm_math_testing
    )

    uinvariant_sol = gyro_cemm_math_testing.calculateInvariant(
        scale(balances), scale(params), derived
    )

    cemm = mimpl.CEMM.from_x_y(balances[0], balances[1], mparams)

    return (
        cemm.r,
        D(int(uinvariant_sol)),
    )


def mtest_calculatePrice(
    params, balances, derivedparams_is_sol: bool, gyro_cemm_math_testing
):
    assume(balances != (0, 0))

    mparams = params2MathParams(params)
    derived = get_derived_parameters(
        params, derivedparams_is_sol, gyro_cemm_math_testing
    )

    cemm = mimpl.CEMM.from_x_y(balances[0], balances[1], mparams)

    price_sol = gyro_cemm_math_testing.calculatePrice(
        scale(balances), scale(params), derived, scale(cemm.r)
    )

    return cemm.px, to_decimal(price_sol)


def mtest_calcYGivenX(
    params, x, invariant, derivedparams_is_sol: bool, gyro_cemm_math_testing
):
    assume(x == 0 if invariant == 0 else True)

    mparams = params2MathParams(params)
    derived = get_derived_parameters(
        params, derivedparams_is_sol, gyro_cemm_math_testing
    )

    midprice = (params.alpha + params.beta) / 2
    cemm = mimpl.CEMM.from_px_r(midprice, invariant, mparams)  # Price doesn't matter.

    y = cemm._compute_y_for_x(x)
    assume(y is not None)  # O/w out of bounds for this invariant
    assume(x > 0 and y > 0)
    assume(x / y > D("1e-5"))
    assume(y / x > D("1e-5"))

    y_sol = gyro_cemm_math_testing.calcYGivenX(
        scale(x), scale(params), derived, scale(cemm.r)
    )
    return y, to_decimal(y_sol)


def mtest_calcXGivenY(
    params, y, invariant, derivedparams_is_sol: bool, gyro_cemm_math_testing
):
    assume(y == 0 if invariant == 0 else True)

    mparams = params2MathParams(params)
    derived = get_derived_parameters(
        params, derivedparams_is_sol, gyro_cemm_math_testing
    )

    midprice = (params.alpha + params.beta) / 2
    cemm = mimpl.CEMM.from_px_r(midprice, invariant, mparams)  # Price doesn't matter.

    x = cemm._compute_x_for_y(y)
    assume(x is not None)  # O/w out of bounds for this invariant
    assume(x > 0 and y > 0)
    assume(x / y > D("1e-5"))
    assume(y / x > D("1e-5"))

    x_sol = gyro_cemm_math_testing.calcXGivenY(
        scale(y), scale(params), derived, scale(invariant)  # scale(cemm.r)
    )
    return x, to_decimal(x_sol)


def mtest_calcOutGivenIn(
    params,
    balances,
    amountIn,
    tokenInIsToken0,
    derivedparams_is_sol: bool,
    gyro_cemm_math_testing,
):
    ixIn = 0 if tokenInIsToken0 else 1
    ixOut = 1 - ixIn

    assume(amountIn <= to_decimal("0.3") * balances[ixIn])

    mparams = params2MathParams(params)
    derived = get_derived_parameters(
        params, derivedparams_is_sol, gyro_cemm_math_testing
    )

    cemm = mimpl.CEMM.from_x_y(balances[0], balances[1], mparams)

    r = cemm.r

    f_trade = cemm.trade_x if tokenInIsToken0 else cemm.trade_y

    mamountOut = f_trade(amountIn)  # This changes the state of the cemm but whatever

    # calculate balanceOut after swap to determine if a revert could happen
    if ixOut == 0:
        x, balOutNew_sol = mtest_calcXGivenY(
            params,
            balances[ixIn] + amountIn,
            r,
            derivedparams_is_sol,
            gyro_cemm_math_testing,
        )
    else:
        y, balOutNew_sol = mtest_calcYGivenX(
            params,
            balances[ixIn] + amountIn,
            r,
            derivedparams_is_sol,
            gyro_cemm_math_testing,
        )

    revertCode = None
    if mamountOut is None:
        revertCode = "BAL#357"  # ASSET_BOUNDS_EXCEEDED
    elif amountIn + balances[ixIn] > (
        cemm.xmax * (D(1) - D("1e-5"))
        if tokenInIsToken0
        else cemm.ymax * (D(1) - D("1e-5"))
    ):
        revertCode = "BAL#357"
    elif unscale(balOutNew_sol) > balances[ixOut]:
        revertCode = "BAL#357"
    elif (balances[ixIn] + amountIn) / unscale(balOutNew_sol) < D("1e-5"):
        revertCode = "BAL#357"
    elif unscale(balOutNew_sol) / (balances[ixIn] + amountIn) < D("1e-5"):
        revertCode = "BAL#357"
    elif balances[ixOut] - unscale(balOutNew_sol) > to_decimal("0.3") * balances[ixOut]:
        revertCode = "BAL#305"  # MAX_OUT_RATIO

    if revertCode is not None:
        with reverts(revertCode):
            gyro_cemm_math_testing.calcOutGivenIn(
                scale(balances),
                scale(amountIn),
                tokenInIsToken0,
                scale(params),
                derived,
                scale(r),
            )
        return 0, 0

    amountOut = -mamountOut
    assert r == cemm.r  # just to be sure

    amountOut_sol = gyro_cemm_math_testing.calcOutGivenIn(
        scale(balances),
        scale(amountIn),
        tokenInIsToken0,
        scale(params),
        derived,
        scale(r),
    )

    return amountOut, to_decimal(amountOut_sol)


def mtest_calcInGivenOut(
    params,
    balances,
    amountOut,
    tokenInIsToken0,
    derivedparams_is_sol: bool,
    gyro_cemm_math_testing,
):
    ixIn = 0 if tokenInIsToken0 else 1
    ixOut = 1 - ixIn

    assume(amountOut <= to_decimal("0.3") * balances[ixOut])

    mparams = params2MathParams(params)
    derived = get_derived_parameters(
        params, derivedparams_is_sol, gyro_cemm_math_testing
    )

    cemm = mimpl.CEMM.from_x_y(balances[0], balances[1], mparams)

    r = cemm.r

    f_trade = cemm.trade_y if tokenInIsToken0 else cemm.trade_x

    amountIn = f_trade(-amountOut)  # This changes the state of the cemm but whatever

    # calculate balanceIn after swap to determine if a revert could happen
    if ixIn == 0:
        x, balInNew_sol = mtest_calcXGivenY(
            params,
            balances[ixOut] - amountOut,
            r,
            derivedparams_is_sol,
            gyro_cemm_math_testing,
        )
    else:
        y, balInNew_sol = mtest_calcYGivenX(
            params,
            balances[ixOut] - amountOut,
            r,
            derivedparams_is_sol,
            gyro_cemm_math_testing,
        )

    revertCode = None
    if amountIn is None:
        revertCode = "BAL#357"  # ASSET_BOUNDS_EXCEEDED
    elif unscale(balInNew_sol) > (
        cemm.xmax * (D(1) - D("1e-5"))
        if tokenInIsToken0
        else cemm.ymax * (D(1) - D("1e-5"))
    ):
        revertCode = "BAL#357"
    elif unscale(balInNew_sol) < balances[ixIn]:
        revertCode = "BAL#357"
    elif unscale(balInNew_sol) / (balances[ixOut] - amountOut) < D("1e-5"):
        revertCode = "BAL#357"
    elif (balances[ixOut] - amountOut) / unscale(balInNew_sol) < D("1e-5"):
        revertCode = "BAL#357"
    elif unscale(balInNew_sol) - balances[ixIn] > to_decimal("0.3") * balances[ixIn]:
        revertCode = "BAL#304"  # MAX_IN_RATIO

    if revertCode is not None:
        with reverts(revertCode):
            gyro_cemm_math_testing.calcInGivenOut(
                scale(balances),
                scale(amountOut),
                tokenInIsToken0,
                scale(params),
                derived,
                scale(r),
            )
        return 0, 0

    assert r == cemm.r  # just to be sure

    amountIn_sol = gyro_cemm_math_testing.calcInGivenOut(
        scale(balances),
        scale(amountOut),
        tokenInIsToken0,
        scale(params),
        derived,
        scale(r),
    )
    return amountIn, to_decimal(amountIn_sol)


def mtest_liquidityInvariantUpdate(params_cemm_dinvariant, gyro_cemm_math_testing):
    params, cemm, dinvariant = params_cemm_dinvariant
    assume(cemm.x != 0 or cemm.y != 0)

    balances = [cemm.x, cemm.y]
    deltaBalances = cemm.update_liquidity(dinvariant, mock=True)
    deltaBalances = (
        abs(deltaBalances[0]),
        abs(deltaBalances[1]),
    )  # b/c solidity function takes uint inputs for this

    rnew = cemm.r + dinvariant
    rnew_sol = gyro_cemm_math_testing.liquidityInvariantUpdate(
        scale(balances),
        scale(cemm.r),
        scale(deltaBalances),
        (dinvariant >= 0),
    )

    return rnew, to_decimal(rnew_sol)


def mtest_liquidityInvariantUpdateEquivalence(
    params_cemm_dinvariant, gyro_cemm_math_testing
):
    """Tests a mathematical fact. Doesn't test solidity."""
    params, cemm, dinvariant = params_cemm_dinvariant
    assume(cemm.x != 0 or cemm.y != 0)

    r = cemm.r
    dx, dy = cemm.update_liquidity(dinvariant, mock=True)

    # To try it out even
    assert dx == (dinvariant / r * cemm.x).approxed(abs=1e-5)
    assert dy == (dinvariant / r * cemm.y).approxed(abs=1e-5)


@contextmanager
def debug_postmortem_on_exc(use_pdb=True):
    """When use_pdb is True, enter the debugger if an exception is raised."""
    try:
        yield
    except Exception as e:
        if not use_pdb:
            raise
        import sys
        import traceback
        import pdb

        info = sys.exc_info()
        traceback.print_exception(*info)
        pdb.post_mortem(info[2])


#####################################################################
### for testing invariant changes across swaps


def faulty_params(
    balances, params: CEMMMathParams, bpool_params: Basic_Pool_Parameters
):
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
    gyro_cemm_math_testing,
):
    ixIn = 0 if tokenInIsToken0 else 1
    ixOut = 1 - ixIn

    assume(amountIn <= to_decimal("0.3") * balances[ixIn])

    fees = bpool_params.min_fee * amountIn
    amountIn -= fees

    mparams = params2MathParams(params)
    derived = get_derived_parameters(
        params, derivedparams_is_sol, gyro_cemm_math_testing
    )

    cemm = mimpl.CEMM.from_x_y(balances[0], balances[1], mparams)
    invariant_before = cemm.r
    invariant_sol = gyro_cemm_math_testing.calculateInvariant(
        scale(balances), scale(params), derived
    )

    f_trade = cemm.trade_x if tokenInIsToken0 else cemm.trade_y
    mamountOut = f_trade(amountIn)  # This changes the state of the cemm but whatever

    # calculate balanceOut after swap to determine if a revert could happen
    if ixOut == 0:
        x, balOutNew_sol = mtest_calcXGivenY(
            params,
            balances[ixIn] + amountIn,
            unscale(invariant_sol),
            derivedparams_is_sol,
            gyro_cemm_math_testing,
        )
    else:
        y, balOutNew_sol = mtest_calcYGivenX(
            params,
            balances[ixIn] + amountIn,
            unscale(invariant_sol),
            derivedparams_is_sol,
            gyro_cemm_math_testing,
        )

    revertCode = None
    if mamountOut is None:
        revertCode = "BAL#357"  # ASSET_BOUNDS_EXCEEDED
    elif amountIn + balances[ixIn] > (
        cemm.xmax * (D(1) - bpool_params.min_balance_ratio)
        if tokenInIsToken0
        else cemm.ymax * (D(1) - bpool_params.min_balance_ratio)
    ):
        revertCode = "BAL#357"
    elif unscale(balOutNew_sol) > balances[ixOut]:
        revertCode = "BAL#357"
    elif (balances[ixIn] + amountIn) / unscale(
        balOutNew_sol
    ) < bpool_params.min_balance_ratio:
        revertCode = "BAL#357"
    elif (
        unscale(balOutNew_sol) / (balances[ixIn] + amountIn)
        < bpool_params.min_balance_ratio
    ):
        revertCode = "BAL#357"
    elif balances[ixOut] - unscale(balOutNew_sol) > to_decimal("0.3") * balances[ixOut]:
        revertCode = "BAL#305"  # MAX_OUT_RATIO

    if revertCode is not None:
        with reverts(revertCode):
            gyro_cemm_math_testing.calcOutGivenIn(
                scale(balances),
                scale(amountIn),
                tokenInIsToken0,
                scale(params),
                derived,
                invariant_sol,
            )
        return (0, 0), (0, 0)

    if (
        balances[0] < balances[1] * bpool_params.min_balance_ratio
        or balances[1] < balances[0] * bpool_params.min_balance_ratio
    ):
        assume(False)

    amountOut = -mamountOut

    amountOut_sol = gyro_cemm_math_testing.calcOutGivenIn(
        scale(balances),
        scale(amountIn),
        tokenInIsToken0,
        scale(params),
        derived,
        invariant_sol,
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

    if (
        new_balances[0] < new_balances[1] * bpool_params.min_balance_ratio
        or new_balances[1] < new_balances[0] * bpool_params.min_balance_ratio
    ):
        assume(False)

    cemm = mimpl.CEMM.from_x_y(new_balances[0], new_balances[1], mparams)
    invariant_after = cemm.r
    invariant_sol_after = gyro_cemm_math_testing.calculateInvariant(
        scale(new_balances), scale(params), derived
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
    gyro_cemm_math_testing,
):
    ixIn = 0 if tokenInIsToken0 else 1
    ixOut = 1 - ixIn

    assume(amountOut <= to_decimal("0.3") * balances[ixOut])

    mparams = params2MathParams(params)
    derived = get_derived_parameters(
        params, derivedparams_is_sol, gyro_cemm_math_testing
    )

    cemm = mimpl.CEMM.from_x_y(balances[0], balances[1], mparams)
    invariant_before = cemm.r
    invariant_sol = gyro_cemm_math_testing.calculateInvariant(
        scale(balances), scale(params), derived
    )

    f_trade = cemm.trade_y if tokenInIsToken0 else cemm.trade_x
    amountIn = f_trade(-amountOut)  # This changes the state of the cemm but whatever

    # calculate balanceIn after swap to determine if a revert could happen
    if ixIn == 0:
        x, balInNew_sol = mtest_calcXGivenY(
            params,
            balances[ixOut] - amountOut,
            unscale(invariant_sol),
            derivedparams_is_sol,
            gyro_cemm_math_testing,
        )
    else:
        y, balInNew_sol = mtest_calcYGivenX(
            params,
            balances[ixOut] - amountOut,
            unscale(invariant_sol),
            derivedparams_is_sol,
            gyro_cemm_math_testing,
        )

    revertCode = None
    if amountIn is None:
        revertCode = "BAL#357"  # ASSET_BOUNDS_EXCEEDED
    elif unscale(balInNew_sol) > (
        cemm.xmax * (D(1) - bpool_params.min_balance_ratio)
        if tokenInIsToken0
        else cemm.ymax * (D(1) - bpool_params.min_balance_ratio)
    ):
        revertCode = "BAL#357"
    elif unscale(balInNew_sol) < balances[ixIn]:
        revertCode = "BAL#357"
    elif (
        unscale(balInNew_sol) / (balances[ixOut] - amountOut)
        < bpool_params.min_balance_ratio
    ):
        revertCode = "BAL#357"
    elif (balances[ixOut] - amountOut) / unscale(
        balInNew_sol
    ) < bpool_params.min_balance_ratio:
        revertCode = "BAL#357"
    elif unscale(balInNew_sol) - balances[ixIn] > to_decimal("0.3") * balances[ixIn]:
        revertCode = "BAL#304"  # MAX_IN_RATIO

    if revertCode is not None:
        with reverts(revertCode):
            gyro_cemm_math_testing.calcInGivenOut(
                scale(balances),
                scale(amountOut),
                tokenInIsToken0,
                scale(params),
                derived,
                invariant_sol,
            )
        return (0, 0), (0, 0)

    if (
        balances[0] < balances[1] * bpool_params.min_balance_ratio
        or balances[1] < balances[0] * bpool_params.min_balance_ratio
    ):
        assume(False)

    amountIn_sol = gyro_cemm_math_testing.calcInGivenOut(
        scale(balances),
        scale(amountOut),
        tokenInIsToken0,
        scale(params),
        derived,
        invariant_sol,
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

    cemm = mimpl.CEMM.from_x_y(new_balances[0], new_balances[1], mparams)
    invariant_after = cemm.r
    invariant_sol_after = gyro_cemm_math_testing.calculateInvariant(
        scale(new_balances), scale(params), derived
    )

    if (
        new_balances[0] < new_balances[1] * bpool_params.min_balance_ratio
        or new_balances[1] < new_balances[0] * bpool_params.min_balance_ratio
    ):
        assume(False)

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
    gyro_cemm_math_testing, params_cemm_dinvariant, derivedparams_is_sol: bool
):
    params, cemm, dinvariant = params_cemm_dinvariant
    assume(cemm.x != 0 or cemm.y != 0)

    mparams = params2MathParams(params)
    derived = get_derived_parameters(
        params, derivedparams_is_sol, gyro_cemm_math_testing
    )

    balances = [cemm.x, cemm.y]
    deltaBalances = cemm.update_liquidity(dinvariant, mock=True)
    deltaBalances = (
        abs(deltaBalances[0]),
        abs(deltaBalances[1]),
    )  # b/c solidity function takes uint inputs for this

    rnew = cemm.r + dinvariant
    rnew_sol = gyro_cemm_math_testing.liquidityInvariantUpdate(
        scale(balances),
        scale(cemm.r),
        scale(deltaBalances),
        (dinvariant >= 0),
    )

    if dinvariant >= 0:
        new_balances = (balances[0] + deltaBalances[0], balances[1] + deltaBalances[1])
    else:
        new_balances = (balances[0] - deltaBalances[0], balances[1] - deltaBalances[1])

    rnew_sol2 = gyro_cemm_math_testing.calculateInvariant(
        scale(new_balances), scale(params), derived
    )

    rnew2 = (mimpl.CEMM.from_x_y(new_balances[0], new_balances[1], mparams)).r

    assert D(rnew).approxed(abs=D("1e-8"), rel=D("1e-8")) >= D(rnew2).approxed(
        abs=D("1e-8"), rel=D("1e-8")
    )
    # the following assertion can fail if square root in solidity has error, but consequence is small (some small protocol fees)
    assert unscale(D(rnew_sol)).approxed(abs=D("1e-8"), rel=D("1e-8")) >= unscale(
        D(rnew_sol2)
    ).approxed(abs=D("1e-8"), rel=D("1e-8"))

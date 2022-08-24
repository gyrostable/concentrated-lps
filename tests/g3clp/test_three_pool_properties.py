from typing import Tuple

import hypothesis.strategies as st
from brownie.test import given
from brownie import reverts
from hypothesis import assume, settings, example, HealthCheck, event
import tests.g3clp.v3_math_implementation as math_implementation
from tests.libraries import pool_math_implementation
from tests.g3clp.util import (
    gen_synthetic_balances,
    gen_synthetic_balances_1asset,
    gen_synthetic_balances_2assets,
    equal_balances_at_invariant,
)
from tests.support.util_common import BasicPoolParameters
from tests.support.utils import scale, to_decimal, qdecimals, unscale

from tests.support.quantized_decimal import QuantizedDecimal as D

Decimal = D

billion_balance_strategy = st.integers(min_value=0, max_value=100_000_000_000)

ROOT_ALPHA_MAX = "0.99996666555"
ROOT_ALPHA_MIN = "0.2"
MIN_BAL_RATIO = D(0)  # to_decimal("1e-5")
MIN_FEE = D("0.0002")

bpool_params = BasicPoolParameters(
    D(ROOT_ALPHA_MAX) ** 3 - 1 / D(ROOT_ALPHA_MIN) ** 3,
    D("0.3"),
    D("0.3"),
    D(
        "1e-18"
    ),  # need min_bal_ratio > 0 for generating synthetic balances for testing calculateInvariant, but 0 ok elsewhere
    MIN_FEE,
)


def gen_balances_raw():
    return st.tuples(
        billion_balance_strategy, billion_balance_strategy, billion_balance_strategy
    )


@st.composite
def gen_balances(draw):
    balances = draw(gen_balances_raw())
    assume(balances[0] > 0 or balances[1] > 0 or balances[2] > 0)
    if balances[0] > 0:
        assume(min(balances[1], balances[2]) / balances[0] > MIN_BAL_RATIO)
    if balances[1] > 0:
        assume(min(balances[2], balances[0]) / balances[1] > MIN_BAL_RATIO)
    if balances[2] > 0:
        assume(min(balances[0], balances[1]) / balances[2] > MIN_BAL_RATIO)
    return balances


@st.composite
def gen_params_in_given_out(draw):
    balances = draw(gen_balances())
    amount_out = draw(qdecimals("0", to_decimal(balances[1])))
    return balances, amount_out


@st.composite
def gen_params_out_given_in(draw):
    balances = draw(gen_balances())
    amount_in = draw(qdecimals("0", to_decimal(balances[0])))
    return balances, amount_in


def gen_bounds():
    return st.decimals(min_value=ROOT_ALPHA_MIN, max_value=ROOT_ALPHA_MAX)


@st.composite
def gen_params_liquidityUpdate(draw):
    balances = draw(
        st.tuples(
            billion_balance_strategy, billion_balance_strategy, billion_balance_strategy
        )
    )
    assume(sum(balances) != 0)
    bpt_supply = draw(qdecimals(D("1e-4") * max(balances), D("1e6") * max(balances)))
    isIncrease = draw(st.booleans())
    if isIncrease:
        dsupply = draw(qdecimals(D("1e-5"), D("1e4") * bpt_supply))
    else:
        dsupply = draw(qdecimals(D("1e-5"), D("0.99") * bpt_supply))
    return balances, bpt_supply, isIncrease, dsupply


@st.composite
def gen_params_liquidityUpdate_large(draw):
    """A variant that only generates large balances."""
    balances = draw(
        st.sampled_from(
            [
                (D(0), bpool_params.max_balances, D(0)),
                (bpool_params.max_balances, bpool_params.max_balances, D(0)),
                (
                    bpool_params.max_balances,
                    bpool_params.max_balances,
                    bpool_params.max_balances,
                ),
            ]
        )
    )
    bpt_supply = draw(qdecimals(D("1e-4") * max(balances), D("1e6") * max(balances)))
    isIncrease = draw(st.booleans())
    if isIncrease:
        dsupply = draw(qdecimals(D("1e-5"), D("1e4") * bpt_supply))
    else:
        dsupply = draw(qdecimals(D("1e-5"), D("0.99") * bpt_supply))
    return balances, bpt_supply, isIncrease, dsupply


###############################################################################################
# Test invariant correctness via being an approximate root of a certain cubic polynomial.

# @settings(max_examples=1_000)
@given(
    balances=gen_balances(),
    root_three_alpha=gen_bounds(),
)
@example(balances=(D("1e10"), D(0), D(0)), root_three_alpha=D(ROOT_ALPHA_MAX))
@example(balances=(D("1e11"), D(0), D(0)), root_three_alpha=D(ROOT_ALPHA_MAX))
@example(balances=(D("1e11"), D("1e11"), D(0)), root_three_alpha=D(ROOT_ALPHA_MAX))
@example(balances=(D("1e11"), D("1e11"), D("1e11")), root_three_alpha=D(ROOT_ALPHA_MAX))
def test_sol_invariant_cubic(gyro_three_math_testing, balances, root_three_alpha):
    mtest_sol_invariant_cubic(gyro_three_math_testing, balances, root_three_alpha)


###############################################################################################
# test calcInGivenOut for invariant change
# This also ensures that the price impact goes in the right direction and, more specifically, no money can be extracted
# without putting any in.

# @settings(max_examples=1_000)
@given(
    setup=gen_params_in_given_out(),
    root_three_alpha=st.decimals(
        min_value=ROOT_ALPHA_MIN, max_value=ROOT_ALPHA_MAX, places=4
    ),
)
@example(
    setup=((99_000_000_000, 99_000_000_000, 99_000_000_000), 999_999_000),
    root_three_alpha=ROOT_ALPHA_MAX,
)
def test_invariant_across_calcInGivenOut(
    gyro_three_math_testing,
    root_three_alpha,
    setup,
):
    balances, amount_out = setup
    invariant_after, invariant = mtest_invariant_across_calcInGivenOut(
        gyro_three_math_testing,
        balances,
        amount_out,
        root_three_alpha,
        False,
        check_price_impact_direction=True,
    )
    assert invariant_after >= invariant


###############################################################################################
# test calcOutGivenIn for invariant change


# @settings(max_examples=1_000)
@given(
    setup=gen_params_out_given_in(),
    root_three_alpha=st.decimals(
        min_value=ROOT_ALPHA_MIN, max_value=ROOT_ALPHA_MAX, places=4
    ),
)
@example(
    setup=((99_000_000_000, 99_000_000_000, 99_000_000_000), 1_000_000_000),
    root_three_alpha=ROOT_ALPHA_MAX,
)
def test_invariant_across_calcOutGivenIn(
    gyro_three_math_testing, root_three_alpha, setup
):
    balances, amount_in = setup
    invariant_after, invariant = mtest_invariant_across_calcOutGivenIn(
        gyro_three_math_testing,
        balances,
        amount_in,
        root_three_alpha,
        False,
        check_price_impact_direction=True,
    )
    assert invariant_after >= invariant


# Explicitly test zero in-amounts.
# This is likely subsumed by test_invariant_across_calcOutGivenIn() but there doesn't seem to be an easy way to specify
# that `amount_in=0` should in particular be tested.
@settings(max_examples=10)
@given(
    balances=gen_balances(),
    root_three_alpha=st.decimals(min_value=ROOT_ALPHA_MIN, max_value=ROOT_ALPHA_MAX),
)
@example(balances=(bpool_params.max_balances,) * 3, root_three_alpha=ROOT_ALPHA_MAX)
def test_invariant_across_calcOutGivenIn_zeroin(
    gyro_three_math_testing, root_three_alpha, balances
):
    amount_in = 0
    invariant_after, invariant = mtest_invariant_across_calcOutGivenIn(
        gyro_three_math_testing,
        balances,
        amount_in,
        root_three_alpha,
        False,
        check_price_impact_direction=True,
    )
    assert invariant_after >= invariant


################################################################################
### test liquidity invariant update for invariant change


@given(
    params_invariantUpdate=st.one_of(
        gen_params_liquidityUpdate(), gen_params_liquidityUpdate_large()
    ),
    root_three_alpha=st.decimals(
        min_value=ROOT_ALPHA_MIN, max_value=ROOT_ALPHA_MAX, places=4
    ),
)
def test_invariant_across_liquidityInvariantUpdate(
    gyro_two_math_testing, root_three_alpha, params_invariantUpdate
):
    mtest_invariant_across_liquidityInvariantUpdate(
        gyro_two_math_testing, root_three_alpha, params_invariantUpdate
    )


###############################################################################################
# mtest functions


def mtest_sol_invariant_cubic(
    gyro_three_math_testing, balances: Tuple[int, int, int], root_three_alpha
):
    (a, mb, mc, md) = math_implementation.calculateCubicTerms(
        to_decimal(balances), to_decimal(root_three_alpha)
    )
    (b, c, d) = (-mb, -mc, -md)
    L = unscale(
        gyro_three_math_testing.calculateInvariant(
            scale(balances), scale(root_three_alpha)
        )
    )
    # f_L_float = calculate_f_L_float(L, balances, root_three_alpha)
    # f_L_prime_float = calculate_f_L_prime_float(L, balances, root_three_alpha)
    f_L_decimal = calculate_f_L_decimal(L, a, b, c, d)
    # assert f_L_float + f_L_prime_float * 1e-18 <= 0

    # NOTE That the function f has an extremely steep slope, so the following is already very good for an approximate
    # root. The coefficients a..d also have rounding errors attached, so this won't (and shouldn't) be very close to 0.
    # 2022-08-02 Had to increase this by ~2 orders of magnitude to pass for extreme balances.
    # Perhaps the right measure would be relative or something.
    assert abs(f_L_decimal) <= D("4.5e28")


def calculate_cubic_terms_float(balances: Tuple[int, int, int], root_three_alpha: D):
    x, y, z = balances
    x, y, z = (float(x), float(y), float(z))
    root_three_alpha = float(root_three_alpha)
    a = 1 - root_three_alpha**3
    b = -(x + y + z) * root_three_alpha**2
    c = -(x * y + y * z + x * z) * root_three_alpha
    d = -x * y * z
    return a, b, c, d


def calculate_f_L_float(L: D, balances: Tuple[int, int, int], root_three_alpha: D):
    a, b, c, d = calculate_cubic_terms_float(balances, root_three_alpha)
    L = float(L)
    return L**3 * a + L**2 * b + L * c + d


def calculate_f_L_prime_float(
    L: D, balances: Tuple[int, int, int], root_three_alpha: D
):
    a, b, c, d = calculate_cubic_terms_float(balances, root_three_alpha)
    L = float(L)
    return L**2 * a * 3 + L * b * 2 + c


def calculate_f_L_decimal(L: D, a: D, b: D, c: D, d: D):
    return L.mul_up(L).mul_up(L).mul_up(a) + L * L * b + L * c + d


# check_price_impact_direction: Test if the avg price is worse than the instantaneous price at the beginning of the trade.
# This also ensures that no money can be extracted without putting anything in.
def mtest_invariant_across_calcInGivenOut(
    gyro_three_math_testing,
    balances,
    amount_out,
    root_three_alpha,
    check_sol_inv,
    check_price_impact_direction=False,
):
    assume(amount_out < (balances[1]))

    invariant = math_implementation.calculateInvariant(
        to_decimal(balances), to_decimal(root_three_alpha)
    )

    invariant_sol = unscale(
        gyro_three_math_testing.calculateInvariant(
            scale(balances), scale(root_three_alpha)
        )
    )

    # assert invariant_sol_under <= invariant.approxed(abs=D('5e-18'))
    # assert invariant <= invariant_sol_over.approxed(abs=D('5e-18'))

    virtual_offset_sol = invariant_sol * to_decimal(root_three_alpha)
    virtual_offset = invariant * to_decimal(root_three_alpha)

    in_amount = math_implementation.calcInGivenOut(
        to_decimal(balances[0]),
        to_decimal(balances[1]),
        to_decimal(amount_out),
        virtual_offset,
    )

    in_amount_sol = unscale(
        gyro_three_math_testing.calcInGivenOut(
            scale(balances[0]),
            scale(balances[1]),
            scale(amount_out),
            scale(virtual_offset_sol),
        )
    )

    event("3Pool-InGivenOut-NoErr")

    # Sanity check.
    assert to_decimal(in_amount_sol) == in_amount.approxed()

    if check_price_impact_direction:
        # Price of out-asset in units of in-asset
        px = (balances[0] + virtual_offset) / (balances[1] + virtual_offset)
        in_amount_instprice = amount_out * px
        assert in_amount_instprice <= in_amount_sol / (1 - MIN_FEE)

    balances_after = (
        balances[0] + in_amount / (1 - MIN_FEE),
        balances[1] - amount_out,
        balances[2],
    )

    invariant_after = math_implementation.calculateInvariant(
        to_decimal(balances_after), to_decimal(root_three_alpha)
    )

    if check_sol_inv:
        invariant_sol_after = gyro_three_math_testing.calcualteInvariant(
            scale(balances_after), scale(root_three_alpha)
        )

        # Tolerance is taken from test_calculateInvariant_reconstruction().
        assert unscale(invariant_sol_after) >= invariant_sol.approxed(
            abs=D("6e-18"), rel=D("6e-18")
        )

    # return invariant_after, invariant
    partial_invariant_from_offsets = calculate_partial_invariant_from_offsets(
        balances, virtual_offset
    )
    partial_invariant_from_offsets_after = calculate_partial_invariant_from_offsets(
        balances_after, virtual_offset
    )

    # partial_invariant_from_sol = invariant_sol**3 / (D(balances[2]) + D(virtual_offset))
    # assert partial_invariant_from_offsets >= partial_invariant_from_sol
    # assert invariant_from_offsets >= invariant_sol
    return partial_invariant_from_offsets_after, partial_invariant_from_offsets


def mtest_invariant_across_calcOutGivenIn(
    gyro_three_math_testing,
    balances,
    amount_in,
    root_three_alpha,
    check_sol_inv,
    check_price_impact_direction=False,
):

    fees = MIN_FEE * amount_in
    amount_in -= fees

    invariant = math_implementation.calculateInvariant(
        to_decimal(balances), to_decimal(root_three_alpha)
    )

    invariant_sol = unscale(
        gyro_three_math_testing.calculateInvariant(
            scale(balances), scale(root_three_alpha)
        )
    )

    virtual_offset_sol = invariant_sol * to_decimal(root_three_alpha)
    virtual_offset = invariant * to_decimal(root_three_alpha)

    out_amount = math_implementation.calcOutGivenIn(
        to_decimal(balances[0]),
        to_decimal(balances[1]),
        to_decimal(amount_in),
        virtual_offset,
    )

    if out_amount <= balances[1] and out_amount >= 0:
        out_amount_sol = gyro_three_math_testing.calcOutGivenIn(
            scale(balances[0]),
            scale(balances[1]),
            scale(amount_in),
            scale(virtual_offset),
        )
    elif out_amount < 0:
        if out_amount >= D("-2e-18"):
            # Negative but insignificant
            return D(0), D(0)
        with reverts("BAL#001"):  # subtraction overflow when ~ 0 and rounding down
            gyro_three_math_testing.calcOutGivenIn(
                scale(balances[0]),
                scale(balances[1]),
                scale(amount_in),
                scale(virtual_offset_sol),
            )
        return D(0), D(0)
    else:
        with reverts("GYR#357"):  # ASSET_BOUNDS_EXCEEDED
            gyro_three_math_testing.calcOutGivenIn(
                scale(balances[0]),
                scale(balances[1]),
                scale(amount_in),
                scale(virtual_offset_sol),
            )
        return D(0), D(0)

    event("3Pool-OutGivenIn-NoErr")

    # Sanity check.
    assert unscale(to_decimal(out_amount_sol)) == out_amount.approxed()

    if check_price_impact_direction:
        # Price of out-asset in units of in-asset
        px = (balances[0] + virtual_offset) / (balances[1] + virtual_offset)
        assert unscale(out_amount_sol) * px <= amount_in + fees

    balances_after = (
        balances[0] + amount_in + fees,
        balances[1] - unscale(out_amount_sol),
        balances[2],
    )
    invariant_after = math_implementation.calculateInvariant(
        to_decimal(balances_after), to_decimal(root_three_alpha)
    )

    # assert invariant_after >= invariant
    if check_sol_inv:
        invariant_sol_after = gyro_three_math_testing.calcualteInvariant(
            scale(balances_after), scale(root_three_alpha)
        )
        # Tolerance is taken from test_calculateInvariant_reconstruction().
        assert unscale(invariant_sol_after) >= invariant_sol.approxed(
            abs=D("6e-18"), rel=D("6e-18")
        )

    # return invariant_after, invariant
    partial_invariant_from_offsets = calculate_partial_invariant_from_offsets(
        balances, virtual_offset
    )
    partial_invariant_from_offsets_after = calculate_partial_invariant_from_offsets(
        balances_after, virtual_offset
    )
    # partial_invariant_from_sol = invariant_sol**3 / (D(balances[2]) + D(virtual_offset))
    # assert partial_invariant_from_offsets >= partial_invariant_from_sol
    # assert invariant_from_offsets >= invariant_sol
    return partial_invariant_from_offsets_after, partial_invariant_from_offsets


def calculate_invariant_from_offsets(balances, virtual_offset):
    return (
        ((D(balances[0]) + D(virtual_offset)) ** D(1 / 3))
        .mul_up((D(balances[1]) + D(virtual_offset)) ** D(1 / 3))
        .mul_up((D(balances[2]) + D(virtual_offset)) ** D(1 / 3))
    )


def calculate_partial_invariant_from_offsets(balances, virtual_offset):
    # ignores the third balance b/c it is not changed in a swap.
    # this has better fixed point precision b/c the extra factor can otherwise be large
    return (D(balances[0]) + D(virtual_offset)).mul_up(
        D(balances[1] + D(virtual_offset))
    )


def mtest_invariant_across_liquidityInvariantUpdate(
    gyro_three_math_testing, root_three_alpha, params_invariantUpdate
):
    balances, bpt_supply, isIncrease, dsupply = params_invariantUpdate
    invariant_before = math_implementation.calculateInvariant(
        balances, root_three_alpha
    )
    if isIncrease:
        dBalances = pool_math_implementation.calcAllTokensInGivenExactBptOut(
            balances, dsupply, bpt_supply
        )
        new_balances = [
            balances[0] + dBalances[0],
            balances[1] + dBalances[1],
            balances[2] + dBalances[2],
        ]
    else:
        dBalances = pool_math_implementation.calcTokensOutGivenExactBptIn(
            balances, dsupply, bpt_supply
        )
        new_balances = [
            balances[0] - dBalances[0],
            balances[1] - dBalances[1],
            balances[2] - dBalances[2],
        ]

    invariant_updated = unscale(
        gyro_three_math_testing.liquidityInvariantUpdate(
            scale(invariant_before), scale(dsupply), scale(bpt_supply), isIncrease
        )
    )

    invariant_after = math_implementation.calculateInvariant(
        new_balances, root_three_alpha
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
        loss = (D(0), D(0), D(0))
    loss_ub = (
        loss[0] * (D(1) / (root_three_alpha**3))
        + loss[1] * (1 / (root_three_alpha**3))
        + loss[2]
    )
    assert abs(loss_ub) < D("1e-5")


def calculate_loss(delta_invariant, invariant, balances):
    # delta_balance_A = delta_invariant / invariant * balance_A
    factor = to_decimal(delta_invariant / invariant)
    return (D(balances[0]) * factor, D(balances[1]) * factor, D(balances[2]) * factor)


###############################################################################################
# Test reconstruction of synthetic invariant

# Balances are generated from a chosen invariant. Then we check if `calculateInvariant()` gets that invariant back.
@given(
    args=st.one_of(
        gen_synthetic_balances_1asset(
            bpool_params, ROOT_ALPHA_MIN, ROOT_ALPHA_MAX, min_balance=D(100)
        ),
        gen_synthetic_balances_2assets(
            bpool_params, ROOT_ALPHA_MIN, ROOT_ALPHA_MAX, min_balance=D(10)
        ),
        gen_synthetic_balances(
            bpool_params, ROOT_ALPHA_MIN, ROOT_ALPHA_MAX, min_balance=D(10)
        ),
    )
)
@example(
    args=(
        (
            D("16743757275.452039152786685295"),
            D("1967668306.780847696789534899"),
            D("396788946.610986231634363959"),
        ),
        D("3812260336.851356457000000000"),
        D("0.200000000181790486"),
    ),
)
@example(
    args=(
        (equal_balances_at_invariant(D("2.999899e15"), ROOT_ALPHA_MAX),) * 3,
        D("2.999899e15"),  # Close to and ≤ the theoretical maximum.
        ROOT_ALPHA_MAX,
    )
)
def test_calculateInvariant_reconstruction(args, gyro_three_math_testing):
    balances, invariant, root3Alpha = args

    invariant_re = unscale(
        gyro_three_math_testing.calculateInvariant(scale(balances), scale(root3Alpha))
    )

    assert invariant_re == invariant.approxed(abs=D("3e-18"), rel=D("3e-18"))

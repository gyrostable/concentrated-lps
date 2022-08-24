from decimal import Decimal
from typing import Tuple

import hypothesis.strategies as st
import numpy as np
from hypothesis import settings, assume, example

import tests.g3clp.v3_math_implementation as math_implementation
from brownie import reverts
from brownie.test import given
from pytest import mark

from tests.support.utils import scale, to_decimal, unscale, qdecimals

from tests.support.quantized_decimal import QuantizedDecimal as D

billion_balance_strategy = st.integers(min_value=0, max_value=100_000_000_000)

ROOT_ALPHA_MAX = "0.99996666555"
ROOT_ALPHA_MIN = "0.2"
MIN_BAL_RATIO = D(0)  # to_decimal("1e-5")


def faulty_params(balances, root_three_alpha):
    balances = [to_decimal(b) for b in balances]
    if balances[0] == 0 and balances[1] == 0 and balances[2] == 0:
        return True
    else:
        return False


@given(
    balances=st.tuples(
        billion_balance_strategy, billion_balance_strategy, billion_balance_strategy
    ),
    root_three_alpha=st.decimals(min_value=ROOT_ALPHA_MIN, max_value=ROOT_ALPHA_MAX),
)
def test_calculate_cubic_terms(
    gyro_three_math_testing, balances: Tuple[int, int], root_three_alpha: Decimal
):
    assume(not faulty_params(balances, root_three_alpha))

    (a, mb, mc, md) = math_implementation.calculateCubicTerms(
        to_decimal(balances), to_decimal(root_three_alpha)
    )

    (a_sol, mb_sol, mc_sol, md_sol) = gyro_three_math_testing.calculateCubicTerms(
        scale(balances), scale(root_three_alpha)
    )

    assert a_sol == scale(a)
    assert mb_sol == scale(mb)
    assert mc_sol == scale(mc)
    assert md_sol == scale(md)


# @given(
#     balances=st.tuples(billion_balance_strategy, billion_balance_strategy, billion_balance_strategy),
#     root_three_alpha=st.decimals(min_value="0.02", max_value="0.99995"),
# )
# def test_calculate_quadratic(gyro_three_math_testing, balances, root_three_alpha):
#     if faulty_params(balances, root_three_alpha):
#         return

#     (a, mb, mc) = math_implementation.calculateQuadraticTerms(
#         to_decimal(balances), to_decimal(root_three_alpha)
#     )

#     assert not any(v < 0 for v in [a, mb, mc])

#     root = math_implementation.calculateQuadratic(a, -mb, -mc)

#     root_sol = gyro_three_math_testing.calculateQuadratic(
#         scale(a), scale(mb), scale(mc)
#     )

#     assert int(root_sol) == scale(root).approxed()


def gen_balances_raw():
    return st.tuples(
        billion_balance_strategy, billion_balance_strategy, billion_balance_strategy
    )


@st.composite
def gen_balances(draw):
    balances = draw(gen_balances_raw())
    assume(balances[0] > 0 and balances[1] > 0 and balances[2] > 0)
    if balances[0] > 0:
        assume(min(balances[1], balances[2]) / balances[0] > MIN_BAL_RATIO)
    if balances[1] > 0:
        assume(min(balances[2], balances[0]) / balances[1] > MIN_BAL_RATIO)
    if balances[2] > 0:
        assume(min(balances[0], balances[1]) / balances[2] > MIN_BAL_RATIO)
    return balances


@st.composite
def gen_params_in_given_out(draw):
    balances = draw(gen_balances_raw())
    assume(balances[0] > 0 and balances[1] > 0 and balances[2] > 0)
    amount_out = draw(qdecimals("0", to_decimal(balances[1])))
    return balances, amount_out


@st.composite
def gen_params_out_given_in(draw):
    balances = draw(gen_balances_raw())
    assume(balances[0] > 0 and balances[1] > 0 and balances[2] > 0)
    amount_in = draw(qdecimals("0", to_decimal(balances[0])))
    return balances, amount_in


@given(
    setup=gen_params_in_given_out(),
    root_three_alpha=st.decimals(
        min_value=ROOT_ALPHA_MIN,
        max_value=ROOT_ALPHA_MAX,
    ),
)
@example(
    setup=((99_000_000_000, 99_000_000_000, 99_000_000_000), 999_999_000),
    root_three_alpha=ROOT_ALPHA_MAX,
)
def test_calc_in_given_out(
    gyro_three_math_testing,
    root_three_alpha,
    setup,
):
    balances, amount_out = setup

    # assume(not faulty_params)

    assume(amount_out < (balances[1]))

    invariant = unscale(
        gyro_three_math_testing.calculateInvariant(
            scale(balances), scale(root_three_alpha)
        )
    )

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
            scale(virtual_offset),
        )
    )

    # We don't get a truly exact match b/c of the safety margin used by the Solidity implementation. (this is not
    # implemented in python)
    assert in_amount_sol >= in_amount
    assert in_amount_sol == in_amount.approxed(abs=D("5e-18"), rel=D("5e-18"))


@given(
    setup=gen_params_out_given_in(),
    root_three_alpha=st.decimals(min_value=ROOT_ALPHA_MIN, max_value=ROOT_ALPHA_MAX),
)
@example(
    setup=((99_000_000_000, 99_000_000_000, 99_000_000_000), 1_000_000_000),
    root_three_alpha=ROOT_ALPHA_MAX,
)
def test_calc_out_given_in(gyro_three_math_testing, root_three_alpha, setup):
    balances, amount_in = setup

    # assume(not faulty_params)

    invariant = unscale(
        gyro_three_math_testing.calculateInvariant(
            scale(balances), scale(root_three_alpha)
        )
    )

    virtual_offset = invariant * to_decimal(root_three_alpha)

    out_amount = math_implementation.calcOutGivenIn(
        to_decimal(balances[0]),
        to_decimal(balances[1]),
        to_decimal(amount_in),
        virtual_offset,
    )

    if out_amount <= balances[1] and out_amount >= 0:
        out_amount_sol = unscale(
            gyro_three_math_testing.calcOutGivenIn(
                scale(balances[0]),
                scale(balances[1]),
                scale(amount_in),
                scale(virtual_offset),
            )
        )
    elif out_amount < 0:
        with reverts("BAL#001"):  # subtraction overflow when ~ 0 and rounding down
            gyro_three_math_testing.calcOutGivenIn(
                scale(balances[0]),
                scale(balances[1]),
                scale(amount_in),
                scale(virtual_offset),
            )
        return
    else:
        with reverts("GYR#357"):  # ASSET_BOUNDS_EXCEEDED
            gyro_three_math_testing.calcOutGivenIn(
                scale(balances[0]),
                scale(balances[1]),
                scale(amount_in),
                scale(virtual_offset),
            )
        return

    # We don't get a truly exact match b/c of the safety margin used by the Solidity implementation. (this is not
    # implemented in python)
    assert out_amount_sol <= out_amount
    assert out_amount_sol == out_amount.approxed(abs=D("5e-18"), rel=D("5e-18"))


@given(
    balances=st.tuples(
        billion_balance_strategy, billion_balance_strategy, billion_balance_strategy
    ),
    root_three_alpha=st.decimals(min_value="0.9", max_value=ROOT_ALPHA_MAX),
)
# regression
@example(
    balances=(5697, 1952, 28355454532),
    root_three_alpha=D("0.90000000006273494438051400077"),
)
@example(
    balances=(30192, 62250, 44794),
    root_three_alpha=D("0.9000000000651515151515152"),
)
@example(balances=[D("1e10"), D(0), D(0)], root_three_alpha=D(ROOT_ALPHA_MAX))
@example(balances=[D("1e11"), D("1e11"), D("1e11")], root_three_alpha=D(ROOT_ALPHA_MAX))
@example(balances=[D("1e11"), D(0), D("1e11")], root_three_alpha=D(ROOT_ALPHA_MAX))
@example(balances=[D("1e11"), D(0), D(0)], root_three_alpha=D(ROOT_ALPHA_MAX))
# L = Decimal('99993316741847.981485422976711167')
# This is also *approximately* computed by Solidity. Wtf.
# Crash on L^3, but why?!
# Reason is that this is really too large: It's ≈ 9.99e13 and we can only represent - and calculate - L^3 for like L ≤ 4.8e13. So it's not even close.
# - [ ] Why doesn't it crash for Ari??
def test_calculate_invariant(
    gyro_three_math_testing, balances: Tuple[int, int, int], root_three_alpha
):

    assume(not faulty_params(balances, root_three_alpha))

    invariant = math_implementation.calculateInvariant(
        to_decimal(balances), to_decimal(root_three_alpha)
    )

    (a, b, c, d) = math_implementation.calculateCubicTerms(
        to_decimal(balances), root_three_alpha
    )

    roots = np.roots([a, -b, -c, -d])

    invariant_sol = unscale(
        gyro_three_math_testing.calculateInvariant(
            scale(balances), scale(root_three_alpha)
        )
    )

    assert invariant_sol == invariant.approxed(rel=D("5e-18"), abs=D("5e-18"))


@given(
    balances=gen_balances(),
    root_three_alpha=qdecimals(min_value="0.9", max_value=ROOT_ALPHA_MAX),
    # rootEst=st.decimals(min_value="1", max_value="100000000000"),
)
# regression
@example(
    balances=(5697, 1952, 28355454532),
    root_three_alpha=D("0.90000000006273494438051400077"),
)
@example(
    balances=(30192, 62250, 44794),
    root_three_alpha=D("0.9000000000651515151515152"),
)
@example(balances=[D("1e10"), D(0), D(0)], root_three_alpha=D(ROOT_ALPHA_MAX))
@example(balances=[D("1e11"), D("1e11"), D("1e11")], root_three_alpha=D(ROOT_ALPHA_MAX))
@example(balances=[D("1e11"), D(0), D("1e11")], root_three_alpha=D(ROOT_ALPHA_MAX))
@example(balances=[D("1e11"), D(0), D(0)], root_three_alpha=D(ROOT_ALPHA_MAX))
def test_calcNewtonDelta(gyro_three_math_testing, balances, root_three_alpha):
    a, mb, mc, md = math_implementation.calculateCubicTerms(balances, root_three_alpha)
    l_lower = D("1.3") * math_implementation.calculateLocalMinimum(a, mb, mc)
    rootEst = math_implementation.calculateCubic(
        a, mb, mc, md, root_three_alpha, balances
    )
    delta_abs, delta_is_pos = math_implementation.calcNewtonDelta(
        a, mb, mc, md, root_three_alpha, rootEst
    )
    delta_abs_sol, delta_is_pos_sol = gyro_three_math_testing.calcNewtonDelta(
        scale(mb),
        scale(mc),
        scale(md),
        scale(root_three_alpha),
        scale(l_lower),
        scale(rootEst),
    )
    delta_abs_sol = unscale(delta_abs_sol)

    assert delta_abs_sol == delta_abs.approxed(abs=D("2e-18"))
    assert delta_is_pos == delta_is_pos_sol or delta_abs <= D("2e-18")

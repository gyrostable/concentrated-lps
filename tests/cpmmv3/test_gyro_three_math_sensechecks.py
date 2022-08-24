from operator import add

import hypothesis.strategies as st
from brownie import reverts  # type: ignore
from brownie.test import given

from tests.support.quantized_decimal import QuantizedDecimal as D
from tests.support.util_common import gen_balances, BasicPoolParameters
from tests.support.utils import qdecimals, scale, to_decimal, unscale

MAX_ALPHA=D("0.99996")

def triple_uniform_integers(min_value=0, max_value=1_000_000_000):
    g = st.integers(min_value=min_value, max_value=max_value)
    return st.tuples(g, g, g)


bpool_params = BasicPoolParameters(
    min_price_separation=D(1)/MAX_ALPHA - MAX_ALPHA,
    max_out_ratio=D('0.3'),
    max_in_ratio=D('0.3'),
    min_balance_ratio=D('1e-5'),
    min_fee=D('0.0001')
)


def gen_root3Alpha():
    return qdecimals(min_value="0.9", max_value=MAX_ALPHA)


@given(
    balances=gen_balances(3, bpool_params),
    root3Alpha=gen_root3Alpha(),
    addl_balances=triple_uniform_integers(500_000_000),
)
def test_calculateInvariant_growth(
    gyro_three_math_testing, balances, root3Alpha, addl_balances
):
    l_low = unscale(gyro_three_math_testing.calculateInvariant(
        scale(balances), scale(root3Alpha)
    ))

    balances_high = tuple(map(add, balances, addl_balances))

    l_high = unscale(gyro_three_math_testing.calculateInvariant(
        scale(balances_high), scale(root3Alpha)
    ))

    # Error bounds informed by the 'reconstruction' tests (see test_three_pool_properties.py)
    assert l_low <= l_high.approxed(abs=D('3e-18'), rel=D('3e-18'))


def test_calcInGivenOut_pricebounds(gyro_three_math_testing):
    run_test_calcInGivenOut_pricebounds(
        gyro_three_math_testing,
        [1_000_000, 2_000_000, 1_000_000],
        D("0.999") ** (D(1) / 3),
        100_000,
        0,
        2,
    )
    run_test_calcInGivenOut_pricebounds(
        gyro_three_math_testing,
        [10_000_000, 2_000_000, 10_000],
        D("0.9995"),
        100_000,
        1,
        0,
    )
    run_test_calcInGivenOut_pricebounds(
        gyro_three_math_testing,
        [10_000_000, 2_000_000, 10_000],
        D("0.9998"),
        2000,
        1,
        2,
    )
    run_test_calcInGivenOut_pricebounds(
        gyro_three_math_testing,
        [10_000_000, 2_000_000, 10_000_000_000],
        D("0.9997"),
        500_000,
        0,
        2,
    )
    run_test_calcInGivenOut_pricebounds(
        gyro_three_math_testing,
        [10_000_000, 2_000_000, 10_000_000_000],
        D("0.9999"),
        200,
        1,
        0,
    )
    with reverts():
        run_test_calcInGivenOut_pricebounds(
            gyro_three_math_testing,
            [10_000_000, 2_000_000, 10_000],
            D("0.9998"),
            5000,
            2,
            1,
        )
    with reverts():
        run_test_calcInGivenOut_pricebounds(
            gyro_three_math_testing,
            [10_000_000, 2_000_000, 10_000],
            D("0.9998"),
            5000,
            1,
            2,
        )


def test_calcOutGivenIn_pricebounds(gyro_three_math_testing):
    run_test_calcOutGivenIn_pricebounds(
        gyro_three_math_testing,
        [1_000_000, 2_000_000, 1_000_000],
        D("0.999") ** (D(1) / 3),
        100_000,
        0,
        2,
    )
    run_test_calcOutGivenIn_pricebounds(
        gyro_three_math_testing,
        [10_000_000, 2_000_000, 10_000],
        D("0.9995"),
        100_000,
        1,
        0,
    )
    run_test_calcOutGivenIn_pricebounds(
        gyro_three_math_testing,
        [10_000_000, 2_000_000, 10_000],
        D("0.9998"),
        2000,
        1,
        2,
    )
    run_test_calcOutGivenIn_pricebounds(
        gyro_three_math_testing,
        [10_000_000, 2_000_000, 10_000_000_000],
        D("0.9997"),
        500_000,
        0,
        2,
    )
    run_test_calcOutGivenIn_pricebounds(
        gyro_three_math_testing,
        [10_000_000, 2_000_000, 10_000_000_000],
        D("0.9999"),
        200,
        1,
        0,
    )
    with reverts():
        run_test_calcInGivenOut_pricebounds(
            gyro_three_math_testing,
            [10_000_000, 2_000_000, 10_000],
            D("0.9998"),
            5000,
            2,
            1,
        )
    with reverts():
        run_test_calcInGivenOut_pricebounds(
            gyro_three_math_testing,
            [10_000_000, 2_000_000, 10_000],
            D("0.9998"),
            5000,
            1,
            2,
        )


def test_InOut_inverse(gyro_three_math_testing):
    run_test_InOut_inverse(
        gyro_three_math_testing,
        [1_000_000, 2_000_000, 1_000_000],
        D("0.999") ** (D(1) / 3),
        100_000,
        0,
        2,
    )
    run_test_InOut_inverse(
        gyro_three_math_testing,
        [10_000_000, 2_000_000, 10_000],
        D("0.9995"),
        100_000,
        1,
        0,
    )
    run_test_InOut_inverse(
        gyro_three_math_testing,
        [10_000_000, 2_000_000, 10_000],
        D("0.9998"),
        2000,
        1,
        2,
    )
    run_test_InOut_inverse(
        gyro_three_math_testing,
        [10_000_000, 2_000_000, 10_000_000_000],
        D("0.9997"),
        500_000,
        0,
        2,
    )
    run_test_InOut_inverse(
        gyro_three_math_testing,
        [10_000_000, 2_000_000, 10_000_000_000],
        D("0.9999"),
        200,
        1,
        0,
    )


# Deactivated this test b/c generating suitable trading amounts has become a bit complicated recently.
# The trading procedures *are* checked, e.g., in `*_properties.py` and in `*_math_implementations_match.py`.
#
# @st.composite
# def gen_InOut_args(draw, bpool_params: BasicPoolParameters):
#     balances=draw(gen_balances(3, bpool_params))
#
#     root3Alpha = draw(gen_root3Alpha())
#
#     ixIn=draw(st.integers(0, 2))
#     ixOut=draw(st.sampled_from([i for i in range(3) if i != ixIn]))
#
#     # NOTE: the upper bound for amountIn is *not* complete! There are many aspects to it, like asset ratios etc.
#     amountIn=draw(qdecimals(0, balances[ixIn] * bpool_params.max_in_ratio).filter(lambda z: z > 0))
#     return balances, root3Alpha, ixIn, ixOut, amountIn
#
#
# @given(
#     args=gen_InOut_args(bpool_params)
# )
# def test_auto_InOut_inverse(gyro_three_math_testing, args):
#     balances, root3Alpha, ixIn, ixOut, amountIn = args
#     run_test_InOut_inverse(
#         gyro_three_math_testing, balances, root3Alpha, amountIn, ixIn, ixOut
#     )


def run_test_calcInGivenOut_pricebounds(
    gyro_three_math_testing, balances, root3Alpha, amountOut, ixIn, ixOut
):
    invariant = unscale(gyro_three_math_testing.calculateInvariant(
        scale(balances), scale(root3Alpha))
    )
    virtualOffset = invariant * root3Alpha

    amountIn = unscale(
        gyro_three_math_testing.calcInGivenOut(
            scale(balances[ixIn]),
            scale(balances[ixOut]),
            scale(amountOut),
            scale(virtualOffset)
        )
    )

    alpha = root3Alpha**3

    assert alpha <= amountOut / amountIn <= D(1) / alpha


def run_test_calcOutGivenIn_pricebounds(
    gyro_three_math_testing, balances, root3Alpha, amountIn, ixIn, ixOut
):
    invariant = unscale(gyro_three_math_testing.calculateInvariant(
        scale(balances), scale(root3Alpha))
    )
    virtualOffset = invariant * root3Alpha

    amountOut = unscale(
        gyro_three_math_testing.calcOutGivenIn(
            scale(balances[ixIn]),
            scale(balances[ixOut]),
            scale(amountIn),
            scale(virtualOffset)
        )
    )

    alpha = root3Alpha**3

    assert alpha <= amountOut / amountIn <= D(1) / alpha


def run_test_InOut_inverse(
    gyro_three_math_testing, balances, root3Alpha, amountIn, ixIn, ixOut
):
    invariant = unscale(gyro_three_math_testing.calculateInvariant(
        scale(balances), scale(root3Alpha)
    ))
    virtualOffset = invariant * root3Alpha

    amountOut = unscale(
        gyro_three_math_testing.calcOutGivenIn(
            scale(balances[ixIn]),
            scale(balances[ixOut]),
            scale(amountIn),
            scale(virtualOffset)
        )
    )
    amountIn1 = unscale(
        gyro_three_math_testing.calcInGivenOut(
            scale(balances[ixIn]),
            scale(balances[ixOut]),
            scale(amountOut),
            scale(virtualOffset)
        )
    )

    assert amountIn1 == to_decimal(amountIn).approxed()

    amountOut1 = unscale(
        gyro_three_math_testing.calcOutGivenIn(
            scale(balances[ixIn]),
            scale(balances[ixOut]),
            scale(amountIn1),
            scale(virtualOffset)
        )
    )

    assert amountOut1 == amountOut.approxed()

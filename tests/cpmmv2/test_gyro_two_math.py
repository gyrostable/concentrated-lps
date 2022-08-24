# from collections import namedtuple
import math

import pytest


def test_calculate_quadratic(gyro_two_math_testing):
    a = 1
    b = 1
    c = 1

    result = gyro_two_math_testing.calculateQuadratic(
        a * 10 ** 18,  # a
        b * 10 ** 18,  # b  < 0, this parameter is -b
        c * 10 ** 18,  # c < 0,  this parameter is -c
    )

    expected_result = ((b + math.sqrt(b * b + 4 * a * c)) / (2 * a)) * 10 ** 18
    # assert result == 1618033988749883666
    assert float(result) == pytest.approx(expected_result)
    fresult = result / 10 ** 18
    assert a * fresult ** 2 - b * fresult - c == pytest.approx(
        0
    )  # One should imply the other (up to approximation error), but let's double check.


def test_calculate_quadratic_terms(gyro_two_math_testing):
    sqrtAlpha = 0.97
    sqrtBeta = 1.02
    balance0 = 100
    balance1 = 200

    result = gyro_two_math_testing.calculateQuadraticTerms(
        [balance0 * 10 ** 18, balance1 * 10 ** 18],  # balances
        sqrtAlpha * 10 ** 18,  # sqrtAlpha
        sqrtBeta * 10 ** 18,  # sqrtBeta
    )

    a = (1 - (sqrtAlpha / sqrtBeta)) * 10 ** 18
    b = (balance1 / sqrtBeta + balance0 * sqrtAlpha) * 10 ** 18
    c = balance0 * balance1 * 10 ** 18

    assert float(result[0]) == pytest.approx(a)
    assert float(result[1]) == pytest.approx(b)
    assert float(result[2]) == pytest.approx(c)


def test_calculate_invariant(gyro_two_math_testing):

    sqrtAlpha = 0.97
    sqrtBeta = 1.02
    balance0 = 100
    balance1 = 200

    result = gyro_two_math_testing.calculateInvariant(
        [balance0 * 10 ** 18, balance1 * 10 ** 18],  # balances
        sqrtAlpha * 10 ** 18,  # sqrtAlpha
        sqrtBeta * 10 ** 18,  # sqrtBeta
    )

    a = 1 - (sqrtAlpha / sqrtBeta)
    b = balance1 / sqrtBeta + balance0 * sqrtAlpha
    c = balance0 * balance1

    expected_result = ((b + math.sqrt(b * b + 4 * a * c)) / (2 * a)) * 10 ** 18

    assert float(result) == pytest.approx(expected_result)


def test_liquidityInvariant_Update(gyro_two_math_testing):

    sqrtAlpha = 0.98
    sqrtBeta = 1.01
    balance0 = 200
    balance1 = 200
    incrY = 2
    lastInvariant = gyro_two_math_testing.calculateInvariant(
        [balance0 * 10 ** 18, balance1 * 10 ** 18],  # balances
        sqrtAlpha * 10 ** 18,  # sqrtAlpha
        sqrtBeta * 10 ** 18,  # sqrtBeta
    )

    for isIncreaseLiq in [
        True,
        False,
    ]:  # We test both increasing and decreasing liquidity.
        result = gyro_two_math_testing.liquidityInvariantUpdate(
            [balance0 * 10 ** 18, balance1 * 10 ** 18],  # balances
            sqrtAlpha * 10 ** 18,  # sqrtAlpha
            sqrtBeta * 10 ** 18,  # sqrtBeta
            lastInvariant,
            [
                None,  # Dummy, won't be used.
                incrY * 10 ** 18,
            ],
            isIncreaseLiq,
        )
        L = lastInvariant / 10 ** 18
        # sqrtPrice = L/(balance0+L/sqrtBeta)  # This is correct, but let's use the definition as an additional test:
        sqrtPrice = math.sqrt((balance1 + L * sqrtAlpha) / (balance0 + L / sqrtBeta))
        incrL = (incrY / (sqrtPrice - sqrtAlpha)) * 10 ** 18
        print(lastInvariant)
        print(L)
        print(incrL)
        if isIncreaseLiq:
            expected_result = lastInvariant + incrL
        else:
            expected_result = lastInvariant - incrL

        assert float(result) == pytest.approx(expected_result)


def test_calc_out_given_in(gyro_two_math_testing):
    balanceIn = 100
    balanceOut = 200
    amountIn = 10  # token0

    sqrtAlpha = 0.97
    sqrtBeta = 1.02

    currentInvariant = gyro_two_math_testing.calculateInvariant(
        [balanceIn * 10 ** 18, balanceOut * 10 ** 18],  # balances
        sqrtAlpha * 10 ** 18,  # sqrtAlpha
        sqrtBeta * 10 ** 18,  # sqrtBeta
    )

    virtualParamIn = currentInvariant / sqrtBeta
    virtualParamOut = currentInvariant * sqrtAlpha

    result = gyro_two_math_testing.calcOutGivenIn(
        balanceIn * 10 ** 18,  # balanceIn,
        balanceOut * 10 ** 18,  # balanceOut,
        amountIn * 10 ** 18,  # amountIn,
        virtualParamIn,  # virtualParamIn,
        virtualParamOut,  # virtualParamOut,
        currentInvariant,  # currentInvariant
    )
    virtualParamIn /= 10 ** 18
    virtualParamOut /= 10 ** 18
    ## - dY = y'- l^2 / (x'+dX)
    expected_result = (
        (balanceOut + virtualParamOut)
        - ((currentInvariant / (10 ** 18)) ** 2)
        / (balanceIn + virtualParamIn + amountIn)
    ) * 10 ** 18

    assert float(result) == pytest.approx(expected_result)


def test_calc_in_given_out(gyro_two_math_testing):
    balanceIn = 150
    balanceOut = 200
    amountOut = 2  # token0

    sqrtAlpha = 0.9
    sqrtBeta = 1.1

    currentInvariant = gyro_two_math_testing.calculateInvariant(
        [balanceIn * 10 ** 18, balanceOut * 10 ** 18],  # balances
        sqrtAlpha * 10 ** 18,  # sqrtAlpha
        sqrtBeta * 10 ** 18,  # sqrtBeta
    )

    virtualParamIn = currentInvariant / sqrtBeta
    virtualParamOut = currentInvariant * sqrtAlpha

    result = gyro_two_math_testing.calcInGivenOut(
        balanceIn * 10 ** 18,  # balanceIn,
        balanceOut * 10 ** 18,  # balanceOut,
        amountOut * 10 ** 18,  # amountIn,
        virtualParamIn,  # virtualParamIn,
        virtualParamOut,  # virtualParamOut,
        currentInvariant,  # currentInvariant
    )

    virtualParamIn /= 10 ** 18
    virtualParamOut /= 10 ** 18

    expected_result = (
        ((currentInvariant / (10 ** 18)) ** 2)
        / (balanceOut + virtualParamOut - amountOut)
        - (balanceIn + virtualParamIn)
    ) * 10 ** 18

    assert float(result) == pytest.approx(expected_result)


## TBD : BPT token Join/Exit calculations test

# def test_on_swap(gyro_two_pool):
#     tx = gyro_two_pool.onSwap()
#     tx.events # logs
#     tx.return_value #
#     tx.success #

from decimal import Decimal
from typing import Tuple

import hypothesis.strategies as st
from brownie import reverts
from brownie.test import given
from hypothesis import assume, settings
from tests.support.utils import scale, to_decimal, unscale

from tests.support.quantized_decimal import QuantizedDecimal as D
from tests.support.quantized_decimal_38 import QuantizedDecimal as D2
from tests.support.quantized_decimal_100 import QuantizedDecimal as D3
from tests.geclp import cemm_prec_implementation as prec_impl

billions_strategy = st.decimals(min_value="-1e12", max_value="1e12", places=4)
tens_strategy = st.decimals(min_value="-10", max_value="10", places=4)


@given(
    a=st.decimals(min_value="0", max_value="1e19"),
    b=st.decimals(min_value="0", max_value="1e19"),
)
def test_mulU(gyro_fixed_point_testing, a, b):
    (a, b) = (scale(D(a)), scale((b)))
    result_checked = gyro_fixed_point_testing.mulDown(a, b)
    result_unchecked = gyro_fixed_point_testing.mulDownU(a, b)
    assert result_checked == result_unchecked

    result_checked = gyro_fixed_point_testing.mulUp(a, b)
    result_unchecked = gyro_fixed_point_testing.mulUpU(a, b)
    assert result_checked == result_unchecked


@given(
    a=st.decimals(min_value="0", max_value="1e19"),
    b=st.decimals(min_value="1e-18", max_value="1e19"),
)
def test_divU(gyro_fixed_point_testing, a, b):
    (a, b) = (D(a), D(b))
    assume(b > D("1e-18"))
    (a, b) = (scale(a), scale(b))
    result_checked = gyro_fixed_point_testing.divDown(a, b)
    result_unchecked = gyro_fixed_point_testing.divDownU(a, b)
    assert result_checked == result_unchecked

    result_checked = gyro_fixed_point_testing.divUp(a, b)
    result_unchecked = gyro_fixed_point_testing.divUpU(a, b)
    assert result_checked == result_unchecked


@given(
    a=st.decimals(min_value="0", max_value="1e39"),
    b=st.decimals(min_value="0", max_value="10"),
)
def test_mulDownLargeSmallU(gyro_fixed_point_testing, a, b):
    (a, b) = (scale(D(a)), scale(D(b)))
    result_checked = gyro_fixed_point_testing.mulDownLargeSmall(a, b)
    result_unchecked = gyro_fixed_point_testing.mulDownLargeSmallU(a, b)
    assert result_checked == result_unchecked


@given(
    a=st.decimals(min_value="0", max_value="1e39"),
    b=st.decimals(min_value="1e-8", max_value="1e15"),
)
def test_divDownLargeU(gyro_fixed_point_testing, a, b):
    (a, b) = (scale(D(a)), scale(D(b)))
    result_checked = gyro_fixed_point_testing.divDownLarge(a, b)
    result_unchecked = gyro_fixed_point_testing.divDownLargeU(a, b)
    assert result_checked == result_unchecked


@given(
    a=st.decimals(min_value="0", max_value="1e39"),
    b=st.decimals(min_value="1e-8", max_value="1e15"),
    d=st.decimals(min_value="1e-18", max_value="1"),
)
def test_divDownLargeU_2(gyro_fixed_point_testing, a, b, d):
    (a, b) = (scale(D(a)), scale(D(b)))
    e = D(1) - D(d)
    (d, e) = (scale(D(d)), scale(D(e)))
    result_checked = gyro_fixed_point_testing.divDownLarge(a, b, d, e)
    result_unchecked = gyro_fixed_point_testing.divDownLargeU(a, b, d, e)
    assert result_checked == result_unchecked

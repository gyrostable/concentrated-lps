from decimal import Decimal
from typing import Tuple

import hypothesis.strategies as st
from brownie import reverts
from brownie.test import given
from hypothesis import assume, settings
from tests.libraries import signed_fixed_point
from tests.support.utils import scale, to_decimal, unscale

from tests.support.quantized_decimal import QuantizedDecimal as D
from tests.support.quantized_decimal_38 import QuantizedDecimal as D2
from tests.support.quantized_decimal_100 import QuantizedDecimal as D3
from tests.geclp import cemm_prec_implementation as prec_impl

billions_strategy = st.decimals(min_value="-1e12", max_value="1e12")
tens_strategy = st.decimals(min_value="-10", max_value="10")


@settings(max_examples=1000)
@given(
    a=st.decimals(min_value="1", max_value="1e24"),
    b=st.integers(min_value=int(D("1e16")), max_value=int(D("5e38"))),
)
def test_mulXpToNp(a, b):
    b_unscale = D2(b) / D2("1e38")
    prod_down_py = prec_impl.mulDownXpToNp(D(a), b_unscale)
    prod_up_py = prec_impl.mulUpXpToNp(D(a), b_unscale)

    assert prod_up_py >= prod_down_py
    assert prod_up_py == prod_down_py.approxed(abs=D("5e-18"))

    prod_true = D3(D(a).raw) * D3(b_unscale.raw)
    assert D3(prod_up_py.raw) >= prod_true
    assert D3(prod_down_py.raw) <= prod_true


@settings(max_examples=1000)
@given(
    a=st.decimals(min_value="1", max_value="1e24"),
    b=st.integers(min_value=int(D("1e16")), max_value=int(D("5e38"))),
)
def test_mulXpToNp_nega(a, b):
    a = -a
    b_unscale = D2(b) / D2("1e38")
    prod_down_py = prec_impl.mulDownXpToNp(D(a), b_unscale)
    prod_up_py = prec_impl.mulUpXpToNp(D(a), b_unscale)

    prod_true = D3(D(a).raw) * D3(b_unscale.raw)
    assert D3(prod_up_py.raw) >= prod_true
    assert D3(prod_down_py.raw) <= prod_true


@settings(max_examples=1000)
@given(
    a=st.decimals(min_value="1", max_value="1e24"),
    b=st.integers(min_value=int(D("1e16")), max_value=int(D("5e38"))),
)
def test_mulXpToNp_negb(a, b):
    b = -b
    b_unscale = D2(b) / D2("1e38")
    prod_down_py = prec_impl.mulDownXpToNp(D(a), b_unscale)
    prod_up_py = prec_impl.mulUpXpToNp(D(a), b_unscale)

    prod_true = D3(D(a).raw) * D3(b_unscale.raw)
    assert D3(prod_up_py.raw) >= prod_true
    assert D3(prod_down_py.raw) <= prod_true


@settings(max_examples=1000)
@given(
    a=st.decimals(min_value="-1e19", max_value="1e19"),
    b=st.decimals(min_value="-1e19", max_value="1e19"),
)
def test_mul(signed_math_testing, a, b):
    result_true = D3(D(a).raw) * D3(D(b).raw)
    (a, b) = (scale(D(a)), scale((b)))
    result_down = D(unscale(signed_math_testing.mulDown(a, b)))
    assert abs(D3(result_down.raw)) <= abs(result_true)

    result_up = D(unscale(signed_math_testing.mulUp(a, b)))
    assert abs(D3(result_up.raw)) >= abs(result_true)


@settings(max_examples=1000)
@given(
    a=st.decimals(min_value="-1e19", max_value="1e19"),
    b=st.decimals(min_value="-1e19", max_value="1e19"),
)
def test_div(signed_math_testing, a, b):
    (a, b) = (D(a), D(b))
    assume(b > D("1e-18") or -b > D("1e-18"))
    result_true = D3(a.raw) / D3(b.raw)
    (a, b) = (scale(a), scale(b))
    result_down = D(unscale(signed_math_testing.divDown(a, b)))
    assert abs(D3(result_down.raw)) <= abs(result_true)

    result_up = D(unscale(signed_math_testing.divUp(a, b)))
    assert abs(D3(result_up.raw)) >= abs(result_true)

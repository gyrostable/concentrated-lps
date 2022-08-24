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


# @settings(max_examples=1000)
@given(
    a=st.integers(min_value=100, max_value=int(D("2e38"))),
    b=st.integers(min_value=100, max_value=int(D("2e38"))),
)
def test_mulXpU(signed_math_testing, a, b):
    prod_py = prec_impl.mulXp(a, b)
    prod_sol = signed_math_testing.mulXpU(a, b)

    assert prod_py == prod_sol
    prod = (D2(a) / D2("1e38")) * (D2(b) / D2("1e38"))
    assert D2(prod_py) / D2("1e38") == prod


# @settings(max_examples=1000)
@given(
    a=st.integers(min_value=100, max_value=int(D("2e38"))),
    b=st.integers(min_value=100, max_value=int(D("2e38"))),
)
def test_divXpU(signed_math_testing, a, b):
    div_py = prec_impl.divXp(a, b)
    div_sol = signed_math_testing.divXpU(a, b)

    assert div_py == div_sol
    div = (D3(a) / D3("1e38")) / (D3(b) / D3("1e38"))
    assert D2(div_py) / D2("1e38") == D2(div.raw)


# @settings(max_examples=1000)
@given(
    a=st.decimals(min_value="1", max_value="1e24"),
    b=st.integers(min_value=int(D("1e16")), max_value=int(D("5e38"))),
)
def test_mulXpToNpU(signed_math_testing, a, b):
    b_unscale = D2(b) / D2("1e38")
    prod_down_py = prec_impl.mulDownXpToNp(D(a), b_unscale)
    prod_down_sol = signed_math_testing.mulDownXpToNpU(scale(D(a)), b)
    assert prod_down_py == unscale(prod_down_sol)

    prod_up_py = prec_impl.mulUpXpToNp(D(a), b_unscale)
    prod_up_sol = signed_math_testing.mulUpXpToNpU(scale(D(a)), b)
    assert prod_up_py == unscale(prod_up_sol)

    assert prod_up_py >= prod_down_py
    assert prod_up_py == prod_down_py.approxed(abs=D("5e-18"))

    prod_sense = D3(a) * D3(b_unscale.raw)
    prod_sense = D(prod_sense.raw)
    # prod_sense_fl = float(a) * float(b) / 1e38
    # assert float(prod_up_py) == pytest.approx(prod_sense_fl)
    assert prod_down_py == prod_sense.approxed(abs=D("5e-18"))


# @settings(max_examples=1000)
@given(
    a=st.decimals(min_value="1", max_value="1e24"),
    b=st.integers(min_value=int(D("1e16")), max_value=int(D("5e38"))),
)
def test_mulXpToNpU_nega(signed_math_testing, a, b):
    a = -a
    b_unscale = D2(b) / D2("1e38")
    prod_down_py = prec_impl.mulDownXpToNp(D(a), b_unscale)
    prod_down_sol = signed_math_testing.mulDownXpToNpU(scale(D(a)), b)
    assert prod_down_py == unscale(prod_down_sol)

    prod_up_py = prec_impl.mulUpXpToNp(D(a), b_unscale)
    prod_up_sol = signed_math_testing.mulUpXpToNpU(scale(D(a)), b)
    assert prod_up_py == unscale(prod_up_sol)

    assert prod_up_py >= prod_down_py
    assert prod_up_py == prod_down_py.approxed(abs=D("5e-18"))

    prod_sense = D3(a) * D3(b_unscale.raw)
    prod_sense = D(prod_sense.raw)
    # prod_sense_fl = float(a) * float(b) / 1e38
    # assert float(prod_up_py) == pytest.approx(prod_sense_fl)
    assert prod_down_py == prod_sense.approxed(abs=D("5e-18"))


# @settings(max_examples=1000)
@given(
    a=st.decimals(min_value="1", max_value="1e24"),
    b=st.integers(min_value=int(D("1e16")), max_value=int(D("5e38"))),
)
def test_mulXpToNpU_negb(signed_math_testing, a, b):
    b = -b
    b_unscale = D2(b) / D2("1e38")
    prod_down_py = prec_impl.mulDownXpToNp(D(a), b_unscale)
    prod_down_sol = signed_math_testing.mulDownXpToNpU(scale(D(a)), b)
    assert prod_down_py == unscale(prod_down_sol)

    prod_up_py = prec_impl.mulUpXpToNp(D(a), b_unscale)
    prod_up_sol = signed_math_testing.mulUpXpToNpU(scale(D(a)), b)
    assert prod_up_py == unscale(prod_up_sol)

    assert prod_up_py >= prod_down_py
    assert prod_up_py == prod_down_py.approxed(abs=D("5e-18"))

    prod_sense = D3(a) * D3(b_unscale.raw)
    prod_sense = D(prod_sense.raw)
    # prod_sense_fl = float(a) * float(b) / 1e38
    # assert float(prod_up_py) == pytest.approx(prod_sense_fl)
    assert prod_down_py == prod_sense.approxed(abs=D("5e-18"))


@given(
    a=st.decimals(min_value="-1e19", max_value="1e19"),
    b=st.decimals(min_value="-1e19", max_value="1e19"),
)
def test_mulU(signed_math_testing, a, b):
    (a, b) = (scale(D(a)), scale((b)))
    result_checked = signed_math_testing.mulDown(a, b)
    result_unchecked = signed_math_testing.mulDownU(a, b)
    assert result_checked == result_unchecked

    result_checked = signed_math_testing.mulUp(a, b)
    result_unchecked = signed_math_testing.mulUpU(a, b)
    assert result_checked == result_unchecked


@given(
    a=st.decimals(min_value="-1e19", max_value="1e19"),
    b=st.decimals(min_value="-1e19", max_value="1e19"),
)
def test_divU(signed_math_testing, a, b):
    (a, b) = (D(a), D(b))
    assume(b > D("1e-18") or -b > D("1e-18"))
    (a, b) = (scale(a), scale(b))
    result_checked = signed_math_testing.divDown(a, b)
    result_unchecked = signed_math_testing.divDownU(a, b)
    assert result_checked == result_unchecked

    result_checked = signed_math_testing.divUp(a, b)
    result_unchecked = signed_math_testing.divUpU(a, b)
    assert result_checked == result_unchecked

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
from tests.cemm import cemm_prec_implementation as prec_impl

billions_strategy = st.decimals(min_value="-1e12", max_value="1e12", places=4)
tens_strategy = st.decimals(min_value="-10", max_value="10", places=4)


@given(a=billions_strategy, b=st.decimals(min_value="0", max_value="1", places=4))
def test_addMag(signed_math_testing, a, b):
    a, b = (D(a), D(b))
    c_py = signed_fixed_point.add_mag(a, b)
    c_sol = signed_math_testing.addMag(scale(a), scale(b))
    assert c_py == unscale(c_sol)


# @settings(max_examples=1000)
@given(
    a=st.integers(min_value=100, max_value=int(D("2e38"))),
    b=st.integers(min_value=100, max_value=int(D("2e38"))),
)
def test_mulXp(signed_math_testing, a, b):
    prod_py = prec_impl.mulXp(a, b)
    prod_sol = signed_math_testing.mulXp(a, b)

    assert prod_py == prod_sol
    prod = (D2(a) / D2("1e38")) * (D2(b) / D2("1e38"))
    assert D2(prod_py) / D2("1e38") == prod


# @settings(max_examples=1000)
@given(
    a=st.integers(min_value=100, max_value=int(D("2e38"))),
    b=st.integers(min_value=100, max_value=int(D("2e38"))),
)
def test_divXp(signed_math_testing, a, b):
    div_py = prec_impl.divXp(a, b)
    div_sol = signed_math_testing.divXp(a, b)

    assert div_py == div_sol
    div = (D3(a) / D3("1e38")) / (D3(b) / D3("1e38"))
    assert D2(div_py) / D2("1e38") == D2(div.raw)


# @settings(max_examples=1000)
@given(
    a=st.decimals(min_value="1", max_value="1e24"),
    b=st.integers(min_value=int(D("1e16")), max_value=int(D("5e38"))),
)
def test_mulXpToNp(signed_math_testing, a, b):
    b_unscale = D2(b) / D2("1e38")
    prod_down_py = prec_impl.mulDownXpToNp(D(a), b_unscale)
    prod_down_sol = signed_math_testing.mulDownXpToNp(scale(D(a)), b)
    assert prod_down_py == unscale(prod_down_sol)

    prod_up_py = prec_impl.mulUpXpToNp(D(a), b_unscale)
    prod_up_sol = signed_math_testing.mulUpXpToNp(scale(D(a)), b)
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
def test_mulXpToNp_nega(signed_math_testing, a, b):
    a = -a
    b_unscale = D2(b) / D2("1e38")
    prod_down_py = prec_impl.mulDownXpToNp(D(a), b_unscale)
    prod_down_sol = signed_math_testing.mulDownXpToNp(scale(D(a)), b)
    assert prod_down_py == unscale(prod_down_sol)

    prod_up_py = prec_impl.mulUpXpToNp(D(a), b_unscale)
    prod_up_sol = signed_math_testing.mulUpXpToNp(scale(D(a)), b)
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
def test_mulXpToNp_negb(signed_math_testing, a, b):
    b = -b
    b_unscale = D2(b) / D2("1e38")
    prod_down_py = prec_impl.mulDownXpToNp(D(a), b_unscale)
    prod_down_sol = signed_math_testing.mulDownXpToNp(scale(D(a)), b)
    assert prod_down_py == unscale(prod_down_sol)

    prod_up_py = prec_impl.mulUpXpToNp(D(a), b_unscale)
    prod_up_sol = signed_math_testing.mulUpXpToNp(scale(D(a)), b)
    assert prod_up_py == unscale(prod_up_sol)

    assert prod_up_py >= prod_down_py
    assert prod_up_py == prod_down_py.approxed(abs=D("5e-18"))

    prod_sense = D3(a) * D3(b_unscale.raw)
    prod_sense = D(prod_sense.raw)
    # prod_sense_fl = float(a) * float(b) / 1e38
    # assert float(prod_up_py) == pytest.approx(prod_sense_fl)
    assert prod_down_py == prod_sense.approxed(abs=D("5e-18"))

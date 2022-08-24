from pprint import pprint
from typing import Iterable

import pytest
from hypothesis import given, settings, HealthCheck, example

from tests.support.util_common import gen_balances, BasicPoolParameters
from tests.support.utils import to_decimal, qdecimals

from tests.support.quantized_decimal import QuantizedDecimal as D
import tests.cpmmv3.v3_math_implementation as mimpl

from tests.cpmmv3.util import gen_synthetic_balances

from pytest import approx

ROOT_ALPHA_MAX = "0.99996666555"
ROOT_ALPHA_MIN = "0.2"
MIN_BAL_RATIO = to_decimal("1e-5")
MIN_FEE = to_decimal("0.0001")

bpool_params = BasicPoolParameters(
    D(1)/D(ROOT_ALPHA_MAX)**3 - D(ROOT_ALPHA_MAX)**3,
    D('0.3'), D('0.3'),
    MIN_BAL_RATIO,
    MIN_FEE,
    max_balances=100_000_000_000
)

@settings(max_examples=500)
@given(
    balances=gen_balances(3, bpool_params),
    root3Alpha=qdecimals(ROOT_ALPHA_MIN, ROOT_ALPHA_MAX)
)
def test_calculateInvariant_match(balances: Iterable[D], root3Alpha: D):
    """Compares out fixed-point implementation to an alternative, scipy-based, floating-point implementation."""
    invariant_fixedpoint = mimpl.calculateInvariant(balances, root3Alpha)
    res_floatpoint = mimpl.calculateInvariantAltFloatWithInfo(balances, root3Alpha)

    invariant_floatpoint = res_floatpoint['root']
    invariant_fixedpoint_float = float(invariant_fixedpoint)

    invariant_min = min(invariant_fixedpoint_float, invariant_floatpoint)

    # Estimated relative max loss to LPs if the true invariant is somewhere between the two estimates.
    diff = abs(invariant_fixedpoint_float - invariant_floatpoint) / invariant_min

    assert diff == pytest.approx(0.0, abs=1e-13)

@settings(max_examples=500)
@given(
    args=gen_synthetic_balances(bpool_params, ROOT_ALPHA_MIN, ROOT_ALPHA_MAX),
)
@example(args=(
    (D('16743757275.452039152786685295'),
     D('1967668306.780847696789534899'),
     D('396788946.610986231634363959')),
    D('3812260336.851356457000000000'),
    D('0.200000000181790486')),
)
def test_calculateInvariant_reconstruction(args):
    balances, invariant, root3Alpha = args

    invariant_re = mimpl.calculateInvariant(balances, root3Alpha)

    assert invariant_re == invariant.approxed(rel=D('5e-16'))


@settings(max_examples=500)
@given(
    args=gen_synthetic_balances(bpool_params, ROOT_ALPHA_MIN, ROOT_ALPHA_MAX),
)
def test_calculateInvariant_reconstruction_alt(args):
    balances, invariant, root3Alpha = args

    invariant_re = mimpl.calculateInvariantAltFloat(balances, root3Alpha)

    invariant = float(invariant)
    assert invariant_re == approx(invariant, rel=1e-12)

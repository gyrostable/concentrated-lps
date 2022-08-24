# DO NOT RUN these as tests. They (most likely) won't fail. These are only for data collection and are marked as tests
# b/c o/w it's really hard to use the test infrastructure -.-
#
# Run using `brownie test`.
from copy import copy
from typing import Union, Tuple

from brownie import *
from brownie.test import given
import pandas as pd
from hypothesis import settings, example
from hypothesis import strategies as st
from toolz import groupby, first, second, valmap

from tests.geclp import util
from tests.geclp import test_cemm_properties
from tests.geclp.util import gen_params
from tests.support.util_common import gen_balances, BasicPoolParameters
from tests.support.quantized_decimal import QuantizedDecimal as D
from tests.support.types import CEMMMathParams
from tests.support.utils import qdecimals

error_values: Union[None, list[dict]]  # None means disabled.
error_values = None

bpool_params = BasicPoolParameters(min_balance_ratio=D("1e-5"))  # Almost a dummy


def push_error_values(row: dict):
    global error_values
    if error_values is not None:
        error_values.append(row)


@settings(max_examples=1_000)
@given(
    params=gen_params(),
    balances=gen_balances(2, bpool_params),
    amountIn=qdecimals(min_value=1, max_value=1_000_000_000),
    tokenInIsToken0=st.booleans(),
)
@example(
    params=CEMMMathParams(
        alpha=D("0.978987854300000000"),
        beta=D("1.005000000000000000"),
        c=D("0.984807753012208020"),
        s=D("0.173648177666930331"),
        l=D("9.165121265207703869"),
    ),
    balances=(402159729, 579734344),
    amountIn=D("1.000000000000000000"),
    tokenInIsToken0=True,
)
def my_test_calcOutGivenIn(
    params, balances, amountIn, tokenInIsToken0, gyro_cemm_math_testing
):
    bpool_params = copy(test_cemm_properties.bpool_params)
    bpool_params.min_fee = D(
        0
    )  # For comparability with the other data, from `tests/geclp/test_python_decimals.py`
    loss_ub, loss_ub_sol = util.mtest_invariant_across_calcOutGivenIn(
        params,
        balances,
        amountIn,
        tokenInIsToken0,
        False,
        bpool_params,
        gyro_cemm_math_testing,
    )
    push_error_values(dict(loss_ub=float(loss_ub), loss_ub_sol=float(loss_ub_sol)))
    # Test always passes unless there's an issue with reverts


def test_main(gyro_cemm_math_testing):
    global error_values
    error_values = []
    my_test_calcOutGivenIn(gyro_cemm_math_testing)

    df = pd.DataFrame(error_values)
    df.to_feather("data/errors_solidity.feather")

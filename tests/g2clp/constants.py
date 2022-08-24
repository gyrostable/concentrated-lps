from collections import namedtuple
from tests.support.quantized_decimal import QuantizedDecimal as D


NUM_TOKENS = 2
NUM_USERS = 2
ADDRESS_0 = "0x0000000000000000000000000000000000000000"

# this is a multiplicative separation
# This is consistent with tightest price range of 0.9999 - 1.0001
MIN_SQRTPARAM_SEPARATION = D("1.0001")

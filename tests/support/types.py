from typing import NamedTuple

from tests.support.quantized_decimal import DecimalLike

address = str


class SwapKind:
    GivenIn = 0
    GivenOut = 1


class CallJoinPoolGyroParams(NamedTuple):
    gyroTwoPool: address
    poolId: bytes
    sender: address
    recipient: address
    currentBalances: int
    lastChangeBlock: int
    protocolSwapFeePercentage: int
    amountIn: int
    bptOut: int


class SwapRequest(NamedTuple):
    kind: int
    tokenIn: address
    tokenOut: address
    amount: int
    poolId: bytes
    lastChangeBlock: int
    from_aux: address
    to: address
    userData: bytes


class TwoPoolBaseParams(NamedTuple):
    vault: str
    name: str
    symbol: str
    token0: str
    token1: str
    normalizedWeight0: DecimalLike
    normalizedWeight1: DecimalLike
    swapFeePercentage: DecimalLike
    pauseWindowDuration: DecimalLike
    bufferPeriodDuration: DecimalLike
    oracleEnabled: bool
    owner: str


class TwoPoolParams(NamedTuple):
    baseParams: TwoPoolBaseParams
    sqrtAlpha: DecimalLike  # should already be upscaled
    sqrtBeta: DecimalLike  # Should already be upscaled


class CEMMMathParams(NamedTuple):
    alpha: DecimalLike
    beta: DecimalLike
    c: DecimalLike
    s: DecimalLike
    l: DecimalLike


class Vector2(NamedTuple):
    x: DecimalLike
    y: DecimalLike


class CEMMMathDerivedParams(NamedTuple):
    tauAlpha: Vector2
    tauBeta: Vector2


class CEMMMathQParams(NamedTuple):
    a: DecimalLike
    b: DecimalLike
    c: DecimalLike

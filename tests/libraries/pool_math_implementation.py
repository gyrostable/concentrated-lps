from typing import Iterable

from tests.support.quantized_decimal import QuantizedDecimal as D


def liquidityInvariantUpdate_deltaBalances(
    balances: Iterable[D],
    lastInvariant: D,
    deltaBalances: Iterable[D],
    isIncreaseLiq: bool,
) -> D:

    largest_balance = 0
    for balance in balances:
        if balance > largest_balance:
            largest_balance = balance

    index_of_largest_balance = balances.index(largest_balance)

    delta_invariant = (
        deltaBalances[index_of_largest_balance] / largest_balance * lastInvariant
    )

    if isIncreaseLiq == True:
        invariant = lastInvariant + delta_invariant
    else:
        invariant = lastInvariant - delta_invariant
    return invariant


def liquidityInvariantUpdate_deltaBptTokens(
    uinvariant: D, changeBptSupply: D, currentBptSupply: D, isIncreaseLiq: bool
) -> D:
    if isIncreaseLiq:
        dL = D(uinvariant).mul_up(changeBptSupply).div_up(currentBptSupply)
    else:
        dL = -D(uinvariant) * changeBptSupply / currentBptSupply
    return uinvariant + dL


def calcAllTokensInGivenExactBptOut(
    balances: Iterable[D], bptAmountOut: D, totalBPT: D
) -> Iterable[D]:
    bptRatio = bptAmountOut.div_up(totalBPT)
    amounts_in = [D(b).mul_up(bptRatio) for b in balances]
    return tuple(amounts_in)


def calcTokensOutGivenExactBptIn(
    balances: Iterable[D], bptAmountIn: D, totalBPT: D
) -> Iterable[D]:
    bptRatio = bptAmountIn / totalBPT
    amounts_out = [D(b) * bptRatio for b in balances]
    return tuple(amounts_out)


def calcProtocolFees(
    previousInvariant: D,
    currentInvariant: D,
    currentBptSupply: D,
    protocolSwapFeePerc: D,
    protocolFeeGyroPortion: D,
) -> Iterable[D]:
    if currentInvariant <= previousInvariant:
        return D(0), D(0)

    if protocolSwapFeePerc == 0:
        return D(0), D(0)

    numerator = (
        currentBptSupply * (currentInvariant - previousInvariant)
    ) * protocolSwapFeePerc
    diffInvariant = protocolSwapFeePerc * (currentInvariant - previousInvariant)
    denominator = currentInvariant - diffInvariant
    deltaS = numerator / denominator

    gyroFees = protocolFeeGyroPortion * deltaS
    balancerFees = deltaS - gyroFees
    return gyroFees, balancerFees

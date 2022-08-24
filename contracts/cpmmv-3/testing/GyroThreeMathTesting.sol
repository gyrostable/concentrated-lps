// SPDX-License-Identifier: UNLICENSE
pragma solidity ^0.7.0;

/// @dev We can't call the functions of the math library for testing b/c they're internal. That's why this contract forwards calls to the math library.

import "../GyroThreeMath.sol";
import "./GyroThreeMathDebug.sol";

contract GyroThreeMathTesting {
    function calculateInvariant(uint256[] memory balances, uint256 root3Alpha)
        external
        pure
        returns (uint256)
    {
        return GyroThreeMath._calculateInvariant(balances, root3Alpha);
    }

    function calculateCubicTerms(uint256[] memory balances, uint256 root3Alpha)
        external
        pure
        returns (
            uint256 a,
            uint256 mb,
            uint256 mc,
            uint256 md
        )
    {
        return GyroThreeMath._calculateCubicTerms(balances, root3Alpha);
    }

    function calculateCubic(
        uint256 a,
        uint256 mb,
        uint256 mc,
        uint256 md
    ) external pure returns (uint256 rootEst) {
        return GyroThreeMath._calculateCubic(a, mb, mc, md);
    }

    function calculateCubicStartingPoint(
        uint256 a,
        uint256 mb,
        uint256 mc,
        uint256 md
    ) external pure returns (uint256 l0) {
        return GyroThreeMath._calculateCubicStartingPoint(a, mb, mc, md);
    }

    function runNewtonIteration(
        uint256 a,
        uint256 mb,
        uint256 mc,
        uint256 md,
        uint256 rootEst
    ) external pure returns (uint256) {
        return GyroThreeMath._runNewtonIteration(a, mb, mc, md, rootEst);
    }

    function calcNewtonDelta(
        uint256 a,
        uint256 mb,
        uint256 mc,
        uint256 md,
        uint256 rootEst
    ) external pure returns (uint256 deltaAbs, bool deltaIsPos) {
        return GyroThreeMath._calcNewtonDelta(a, mb, mc, md, rootEst);
    }

    function liquidityInvariantUpdate(
        uint256[] memory lastBalances,
        uint256 root3Alpha,
        uint256 lastInvariant,
        uint256[] memory amountsIn,
        bool isIncreaseLiq
    ) external pure returns (uint256 invariant) {
        return
            GyroThreeMath._liquidityInvariantUpdate(
                lastBalances,
                root3Alpha,
                lastInvariant,
                amountsIn,
                isIncreaseLiq
            );
    }

    function calcOutGivenIn(
        uint256 balanceIn,
        uint256 balanceOut,
        uint256 amountIn,
        uint256 virtualOffsetInOut
    ) external pure returns (uint256 amountOut) {
        return GyroThreeMath._calcOutGivenIn(balanceIn, balanceOut, amountIn, virtualOffsetInOut);
    }

    function calcInGivenOut(
        uint256 balanceIn,
        uint256 balanceOut,
        uint256 amountOut,
        uint256 virtualOffsetInOut
    ) external pure returns (uint256 amountIn) {
        return GyroThreeMath._calcInGivenOut(balanceIn, balanceOut, amountOut, virtualOffsetInOut);
    }

    function calcAllTokensInGivenExactBptOut(
        uint256[] memory balances,
        uint256 bptAmountOut,
        uint256 totalBPT
    ) external pure returns (uint256[] memory) {
        return GyroThreeMath._calcAllTokensInGivenExactBptOut(balances, bptAmountOut, totalBPT);
    }

    function calcTokensOutGivenExactBptIn(
        uint256[] memory balances,
        uint256 bptAmountIn,
        uint256 totalBPT
    ) external pure returns (uint256[] memory) {
        return GyroThreeMath._calcTokensOutGivenExactBptIn(balances, bptAmountIn, totalBPT);
    }

    function calculateCbrtPrice(uint256 invariant, uint256 virtualZ)
        external
        pure
        returns (uint256)
    {
        return GyroThreeMath._calculateCbrtPrice(invariant, virtualZ);
    }

    function calcProtocolFees(
        uint256 previousInvariant,
        uint256 currentInvariant,
        uint256 currentBptSupply,
        uint256 protocolSwapFeePerc,
        uint256 protocolFeeGyroPortion
    ) external pure returns (uint256, uint256) {
        return
            GyroThreeMath._calcProtocolFees(
                previousInvariant,
                currentInvariant,
                currentBptSupply,
                protocolSwapFeePerc,
                protocolFeeGyroPortion
            );
    }

    // DEBUG
    // Must be declared here, otherwise we can't see it.
    // solhint-disable-next-line use-forbidden-name
    event NewtonStep(bool high, uint256 delta, uint256 l);

    function calculateInvariantDebug(uint256[] memory balances, uint256 root3Alpha)
        external
        pure
        returns (uint256)
    {
        return GyroThreeMathDebug._calculateInvariant(balances, root3Alpha);
    }

    function maxOtherBalances(uint256[] memory balances) external pure returns (uint8[] memory) {
        return GyroThreeMath.maxOtherBalances(balances);
    }
}

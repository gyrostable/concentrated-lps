// SPDX-License-Identifier: LicenseRef-Gyro-1.0
// for information on licensing please see the README in the GitHub repository <https://github.com/gyrostable/concentrated-lps>.
pragma solidity 0.7.6;

/// @dev We can't call the functions of the math library for testing b/c they're internal. That's why this contract forwards calls to the math library.

import "../Gyro3CLPMath.sol";
import "../../../libraries/GyroPoolMath.sol";

contract Gyro3CLPMathTesting {
    function calculateInvariant(uint256[] memory balances, uint256 root3Alpha) external pure returns (uint256 invariant) {
        return Gyro3CLPMath._calculateInvariant(balances, root3Alpha);
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
        return Gyro3CLPMath._calculateCubicTerms(balances, root3Alpha);
    }

    function calculateCubic(
        uint256 a,
        uint256 mb,
        uint256 mc,
        uint256 md,
        uint256 root3Alpha
    ) external pure returns (uint256 rootEst) {
        rootEst = Gyro3CLPMath._calculateCubic(a, mb, mc, md, root3Alpha);
    }

    function calculateCubicStartingPoint(
        uint256 a,
        uint256 mb,
        uint256 mc,
        uint256 md
    ) external pure returns (uint256 l0) {
        (, l0) = Gyro3CLPMath._calculateCubicStartingPoint(a, mb, mc, md);
    }

    function runNewtonIteration(
        uint256 mb,
        uint256 mc,
        uint256 md,
        uint256 root3Alpha,
        uint256 l_lower,
        uint256 rootEst
    ) external pure returns (uint256 rootEstOut) {
        rootEstOut = Gyro3CLPMath._runNewtonIteration(mb, mc, md, root3Alpha, l_lower, rootEst);
    }

    function calcNewtonDelta(
        uint256 mb,
        uint256 mc,
        uint256 md,
        uint256 root3Alpha,
        uint256 l_lower,
        uint256 rootEst
    ) external pure returns (uint256 deltaAbs, bool deltaIsPos) {
        return Gyro3CLPMath._calcNewtonDelta(mb, mc, md, root3Alpha, l_lower, rootEst);
    }

    function liquidityInvariantUpdate(
        uint256 uinvariant,
        uint256 changeBptSupply,
        uint256 currentBptSupply,
        bool isIncreaseLiq
    ) external pure returns (uint256 invariant) {
        return GyroPoolMath.liquidityInvariantUpdate(uinvariant, changeBptSupply, currentBptSupply, isIncreaseLiq);
    }

    function calcOutGivenIn(
        uint256 balanceIn,
        uint256 balanceOut,
        uint256 amountIn,
        uint256 virtualOffset
    ) external pure returns (uint256 amountOut) {
        return Gyro3CLPMath._calcOutGivenIn(balanceIn, balanceOut, amountIn, virtualOffset);
    }

    function calcInGivenOut(
        uint256 balanceIn,
        uint256 balanceOut,
        uint256 amountOut,
        uint256 virtualOffset
    ) external pure returns (uint256 amountIn) {
        return Gyro3CLPMath._calcInGivenOut(balanceIn, balanceOut, amountOut, virtualOffset);
    }

    function calcAllTokensInGivenExactBptOut(
        uint256[] memory balances,
        uint256 bptAmountOut,
        uint256 totalBPT
    ) external pure returns (uint256[] memory) {
        return GyroPoolMath._calcAllTokensInGivenExactBptOut(balances, bptAmountOut, totalBPT);
    }

    function calcTokensOutGivenExactBptIn(
        uint256[] memory balances,
        uint256 bptAmountIn,
        uint256 totalBPT
    ) external pure returns (uint256[] memory) {
        return GyroPoolMath._calcTokensOutGivenExactBptIn(balances, bptAmountIn, totalBPT);
    }

    function calcProtocolFees(
        uint256 previousInvariant,
        uint256 currentInvariant,
        uint256 currentBptSupply,
        uint256 protocolSwapFeePerc,
        uint256 protocolFeeGyroPortion
    ) external pure returns (uint256, uint256) {
        return GyroPoolMath._calcProtocolFees(previousInvariant, currentInvariant, currentBptSupply, protocolSwapFeePerc, protocolFeeGyroPortion);
    }
}

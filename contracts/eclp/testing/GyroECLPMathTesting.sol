// SPDX-License-Identifier: LicenseRef-Gyro-1.0
// for information on licensing please see the README in the GitHub repository <https://github.com/gyrostable/concentrated-lps>.

pragma solidity 0.7.6;
pragma experimental ABIEncoderV2;

import "../GyroECLPMath.sol";
import "../../../libraries/GyroPoolMath.sol";

contract GyroECLPMathTesting {
    function scalarProd(GyroECLPMath.Vector2 memory t1, GyroECLPMath.Vector2 memory t2) external pure returns (int256 ret) {
        ret = GyroECLPMath.scalarProd(t1, t2);
    }

    function mulA(GyroECLPMath.Params memory params, GyroECLPMath.Vector2 memory tp) external pure returns (GyroECLPMath.Vector2 memory t) {
        t = GyroECLPMath.mulA(params, tp);
    }

    function virtualOffset0(
        GyroECLPMath.Params memory params,
        GyroECLPMath.DerivedParams memory derived,
        GyroECLPMath.Vector2 memory r
    ) external pure returns (int256) {
        return GyroECLPMath.virtualOffset0(params, derived, r);
    }

    function virtualOffset1(
        GyroECLPMath.Params memory params,
        GyroECLPMath.DerivedParams memory derived,
        GyroECLPMath.Vector2 memory r
    ) external pure returns (int256) {
        return GyroECLPMath.virtualOffset1(params, derived, r);
    }

    function maxBalances0(
        GyroECLPMath.Params memory params,
        GyroECLPMath.DerivedParams memory derived,
        GyroECLPMath.Vector2 memory r
    ) external pure returns (int256) {
        return GyroECLPMath.maxBalances0(params, derived, r);
    }

    function maxBalances1(
        GyroECLPMath.Params memory params,
        GyroECLPMath.DerivedParams memory derived,
        GyroECLPMath.Vector2 memory r
    ) external pure returns (int256) {
        return GyroECLPMath.maxBalances1(params, derived, r);
    }

    function calculateInvariantWithError(
        uint256[] memory balances,
        GyroECLPMath.Params memory params,
        GyroECLPMath.DerivedParams memory derived
    ) external pure returns (int256, int256) {
        return GyroECLPMath.calculateInvariantWithError(balances, params, derived);
    }

    function calculateInvariant(
        uint256[] memory balances,
        GyroECLPMath.Params memory params,
        GyroECLPMath.DerivedParams memory derived
    ) external pure returns (uint256 uinvariant) {
        uinvariant = GyroECLPMath.calculateInvariant(balances, params, derived);
    }

    function calculatePrice(
        uint256[] memory balances,
        GyroECLPMath.Params memory params,
        GyroECLPMath.DerivedParams memory derived,
        int256 invariant
    ) external pure returns (uint256 px) {
        px = GyroECLPMath.calcSpotPrice0in1(balances, params, derived, invariant);
    }

    function checkAssetBounds(
        GyroECLPMath.Params memory params,
        GyroECLPMath.DerivedParams memory derived,
        GyroECLPMath.Vector2 memory invariant,
        int256 newBalance,
        uint8 assetIndex
    ) external pure {
        GyroECLPMath.checkAssetBounds(params, derived, invariant, newBalance, assetIndex);
    }

    function calcOutGivenIn(
        uint256[] memory balances,
        uint256 amountIn,
        bool tokenInIsToken0,
        GyroECLPMath.Params memory params,
        GyroECLPMath.DerivedParams memory derived,
        GyroECLPMath.Vector2 memory invariant
    ) external pure returns (uint256 amountOut) {
        amountOut = GyroECLPMath.calcOutGivenIn(balances, amountIn, tokenInIsToken0, params, derived, invariant);
    }

    function calcInGivenOut(
        uint256[] memory balances,
        uint256 amountOut,
        bool tokenInIsToken0,
        GyroECLPMath.Params memory params,
        GyroECLPMath.DerivedParams memory derived,
        GyroECLPMath.Vector2 memory invariant
    ) external pure returns (uint256 amountIn) {
        amountIn = GyroECLPMath.calcInGivenOut(balances, amountOut, tokenInIsToken0, params, derived, invariant);
    }

    function calcYGivenX(
        int256 x,
        GyroECLPMath.Params memory params,
        GyroECLPMath.DerivedParams memory derived,
        GyroECLPMath.Vector2 memory invariant
    ) external pure returns (int256 y) {
        y = GyroECLPMath.calcYGivenX(x, params, derived, invariant);
    }

    function calcXGivenY(
        int256 y,
        GyroECLPMath.Params memory params,
        GyroECLPMath.DerivedParams memory derived,
        GyroECLPMath.Vector2 memory invariant
    ) external pure returns (int256 x) {
        x = GyroECLPMath.calcXGivenY(y, params, derived, invariant);
    }

    function calcAtAChi(
        int256 x,
        int256 y,
        GyroECLPMath.Params memory p,
        GyroECLPMath.DerivedParams memory d
    ) external pure returns (int256) {
        return GyroECLPMath.calcAtAChi(x, y, p, d);
    }

    function calcAChiAChiInXp(GyroECLPMath.Params memory p, GyroECLPMath.DerivedParams memory d) external pure returns (int256) {
        return GyroECLPMath.calcAChiAChiInXp(p, d);
    }

    function calcMinAtxAChiySqPlusAtxSq(
        int256 x,
        int256 y,
        GyroECLPMath.Params memory p,
        GyroECLPMath.DerivedParams memory d
    ) external pure returns (int256) {
        return GyroECLPMath.calcMinAtxAChiySqPlusAtxSq(x, y, p, d);
    }

    function calc2AtxAtyAChixAChiy(
        int256 x,
        int256 y,
        GyroECLPMath.Params memory p,
        GyroECLPMath.DerivedParams memory d
    ) external pure returns (int256) {
        return GyroECLPMath.calc2AtxAtyAChixAChiy(x, y, p, d);
    }

    function calcMinAtyAChixSqPlusAtySq(
        int256 x,
        int256 y,
        GyroECLPMath.Params memory p,
        GyroECLPMath.DerivedParams memory d
    ) external pure returns (int256) {
        return GyroECLPMath.calcMinAtyAChixSqPlusAtySq(x, y, p, d);
    }

    function calcInvariantSqrt(
        int256 x,
        int256 y,
        GyroECLPMath.Params memory p,
        GyroECLPMath.DerivedParams memory d
    ) external pure returns (int256, int256) {
        return GyroECLPMath.calcInvariantSqrt(x, y, p, d);
    }

    function solveQuadraticSwap(
        int256 lambda,
        int256 x,
        int256 s,
        int256 c,
        GyroECLPMath.Vector2 memory r,
        GyroECLPMath.Vector2 memory ab,
        GyroECLPMath.Vector2 memory tauBeta,
        int256 dSq
    ) external pure returns (int256) {
        return GyroECLPMath.solveQuadraticSwap(lambda, x, s, c, r, ab, tauBeta, dSq);
    }

    function calcXpXpDivLambdaLambda(
        int256 x,
        GyroECLPMath.Vector2 memory r,
        int256 lambda,
        int256 s,
        int256 c,
        GyroECLPMath.Vector2 memory tauBeta,
        int256 dSq
    ) external pure returns (int256) {
        return GyroECLPMath.calcXpXpDivLambdaLambda(x, r, lambda, s, c, tauBeta, dSq);
    }

    function liquidityInvariantUpdate(
        uint256 uinvariant,
        uint256 changeBptSupply,
        uint256 currentBptSupply,
        bool isIncreaseLiq
    ) external pure returns (uint256 unewInvariant) {
        unewInvariant = GyroPoolMath.liquidityInvariantUpdate(uinvariant, changeBptSupply, currentBptSupply, isIncreaseLiq);
    }

    // function liquidityInvariantUpdate(
    //     uint256[] memory balances,
    //     uint256 uinvariant,
    //     uint256[] memory deltaBalances,
    //     bool isIncreaseLiq
    // ) external pure returns (uint256 unewInvariant) {
    //     unewInvariant = GyroPoolMath.liquidityInvariantUpdate(balances, uinvariant, deltaBalances, isIncreaseLiq);
    // }

    function _calcAllTokensInGivenExactBptOut(
        uint256[] memory balances,
        uint256 bptAmountOut,
        uint256 totalBPT
    ) external pure returns (uint256[] memory) {
        return GyroPoolMath._calcAllTokensInGivenExactBptOut(balances, bptAmountOut, totalBPT);
    }

    function _calcTokensOutGivenExactBptIn(
        uint256[] memory balances,
        uint256 bptAmountIn,
        uint256 totalBPT
    ) external pure returns (uint256[] memory) {
        return GyroPoolMath._calcTokensOutGivenExactBptIn(balances, bptAmountIn, totalBPT);
    }

    function _calcProtocolFees(
        uint256 previousInvariant,
        uint256 currentInvariant,
        uint256 currentBptSupply,
        uint256 protocolSwapFeePerc,
        uint256 protocolFeeGyroPortion
    ) external pure returns (uint256, uint256) {
        return GyroPoolMath._calcProtocolFees(previousInvariant, currentInvariant, currentBptSupply, protocolSwapFeePerc, protocolFeeGyroPortion);
    }
}

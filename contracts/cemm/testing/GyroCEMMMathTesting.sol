// SPDX-License-Identifier: LicenseRef-Gyro-1.0
// for information on licensing please see the README in the GitHub repository <https://github.com/gyrostable/concentrated-lps>.

pragma solidity ^0.7.0;
pragma experimental ABIEncoderV2;

import "../GyroCEMMMath.sol";
import "../../../libraries/GyroPoolMath.sol";

contract GyroCEMMMathTesting {
    function scalarProdUp(GyroCEMMMath.Vector2 memory t1, GyroCEMMMath.Vector2 memory t2) external pure returns (int256 ret) {
        ret = GyroCEMMMath.scalarProdUp(t1, t2);
    }

    function scalarProdDown(GyroCEMMMath.Vector2 memory t1, GyroCEMMMath.Vector2 memory t2) external pure returns (int256 ret) {
        ret = GyroCEMMMath.scalarProdDown(t1, t2);
    }

    function mulAinv(GyroCEMMMath.Params memory params, GyroCEMMMath.Vector2 memory t) external pure returns (GyroCEMMMath.Vector2 memory tp) {
        tp = GyroCEMMMath.mulAinv(params, t);
    }

    function mulA(GyroCEMMMath.Params memory params, GyroCEMMMath.Vector2 memory tp) external pure returns (GyroCEMMMath.Vector2 memory t) {
        t = GyroCEMMMath.mulA(params, tp);
    }

    function zeta(GyroCEMMMath.Params memory params, int256 px) external pure returns (int256 pxc) {
        pxc = GyroCEMMMath.zeta(params, px);
    }

    function tau(GyroCEMMMath.Params memory params, int256 px) external pure returns (GyroCEMMMath.Vector2 memory tpp) {
        tpp = GyroCEMMMath.tau(params, px);
    }

    function tau(
        GyroCEMMMath.Params memory params,
        int256 px,
        int256 sqrt
    ) external pure returns (GyroCEMMMath.Vector2 memory tpp) {
        return GyroCEMMMath.tau(params, px, sqrt);
    }

    function mkDerivedParams(GyroCEMMMath.Params memory params) external pure returns (GyroCEMMMath.DerivedParams memory derived) {
        derived = GyroCEMMMath.mkDerivedParams(params);
    }

    function eta(int256 pxc) external pure returns (GyroCEMMMath.Vector2 memory tpp) {
        tpp = GyroCEMMMath.eta(pxc);
    }

    function eta(int256 pxc, int256 z) external pure returns (GyroCEMMMath.Vector2 memory tpp) {
        tpp = GyroCEMMMath.eta(pxc, z);
    }

    function virtualOffsets(
        GyroCEMMMath.Params memory params,
        GyroCEMMMath.DerivedParams memory derived,
        int256 invariant
    ) external pure returns (GyroCEMMMath.Vector2 memory ab) {
        ab = GyroCEMMMath.virtualOffsets(params, derived, invariant);
    }

    function maxBalances(
        GyroCEMMMath.Params memory params,
        GyroCEMMMath.DerivedParams memory derived,
        int256 invariant
    ) external pure returns (GyroCEMMMath.Vector2 memory xy) {
        xy = GyroCEMMMath.maxBalances(params, derived, invariant);
    }

    function chi(GyroCEMMMath.Params memory params, GyroCEMMMath.DerivedParams memory derived)
        external
        pure
        returns (GyroCEMMMath.Vector2 memory ret)
    {
        ret = GyroCEMMMath.chi(params, derived);
    }

    function solveQuadraticPlus(GyroCEMMMath.QParams memory qparams) external pure returns (int256 x) {
        x = GyroCEMMMath.solveQuadraticPlus(qparams);
    }

    function solveQuadraticMinus(GyroCEMMMath.QParams memory qparams) external pure returns (int256 x) {
        x = GyroCEMMMath.solveQuadraticMinus(qparams);
    }

    function calculateInvariant(
        uint256[] memory balances,
        GyroCEMMMath.Params memory params,
        GyroCEMMMath.DerivedParams memory derived
    ) external pure returns (uint256 uinvariant) {
        uinvariant = GyroCEMMMath.calculateInvariant(balances, params, derived);
    }

    function calculatePrice(
        uint256[] memory balances,
        GyroCEMMMath.Params memory params,
        GyroCEMMMath.DerivedParams memory derived,
        int256 invariant
    ) external pure returns (uint256 px) {
        px = GyroCEMMMath.calculatePrice(balances, params, derived, invariant);
    }

    function checkAssetBounds(
        GyroCEMMMath.Params memory params,
        GyroCEMMMath.DerivedParams memory derived,
        int256 invariant,
        int256 newBalance,
        uint8 assetIndex
    ) external pure {
        GyroCEMMMath.checkAssetBounds(params, derived, invariant, newBalance, assetIndex);
    }

    function calcOutGivenIn(
        uint256[] memory balances,
        uint256 amountIn,
        bool tokenInIsToken0,
        GyroCEMMMath.Params memory params,
        GyroCEMMMath.DerivedParams memory derived,
        uint256 uinvariant
    ) external pure returns (uint256 amountOut) {
        amountOut = GyroCEMMMath.calcOutGivenIn(balances, amountIn, tokenInIsToken0, params, derived, uinvariant);
    }

    function calcInGivenOut(
        uint256[] memory balances,
        uint256 amountOut,
        bool tokenInIsToken0,
        GyroCEMMMath.Params memory params,
        GyroCEMMMath.DerivedParams memory derived,
        uint256 uinvariant
    ) external pure returns (uint256 amountIn) {
        amountIn = GyroCEMMMath.calcInGivenOut(balances, amountOut, tokenInIsToken0, params, derived, uinvariant);
    }

    function calcYGivenX(
        int256 x,
        GyroCEMMMath.Params memory params,
        GyroCEMMMath.DerivedParams memory derived,
        int256 invariant
    ) external pure returns (int256 y) {
        y = GyroCEMMMath.calcYGivenX(x, params, derived, invariant);
    }

    function calcXGivenY(
        int256 y,
        GyroCEMMMath.Params memory params,
        GyroCEMMMath.DerivedParams memory derived,
        int256 invariant
    ) external pure returns (int256 x) {
        x = GyroCEMMMath.calcXGivenY(y, params, derived, invariant);
    }

    function calculateSqrtOnePlusZetaSquared(
        uint256[] memory balances,
        GyroCEMMMath.Params memory params,
        GyroCEMMMath.DerivedParams memory derived,
        int256 invariant
    ) external pure returns (int256 sqrt) {
        sqrt = GyroCEMMMath.calculateSqrtOnePlusZetaSquared(balances, params, derived, invariant);
    }

    function liquidityInvariantUpdate(
        uint256[] memory balances,
        uint256 uinvariant,
        uint256[] memory deltaBalances,
        bool isIncreaseLiq
    ) external pure returns (uint256 unewInvariant) {
        unewInvariant = GyroCEMMMath.liquidityInvariantUpdate(balances, uinvariant, deltaBalances, isIncreaseLiq);
    }

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

// SPDX-License-Identifier: LicenseRef-Gyro-1.0
// for information on licensing please see the README in the GitHub repository <https://github.com/gyrostable/core-protocol>.

pragma solidity ^0.7.0;

import "../GyroTwoMath.sol";

contract GyroTwoMathTesting {
    function calculateQuadratic(
        uint256 a,
        uint256 b,
        uint256 c
    ) external pure returns (uint256) {
        return GyroTwoMath._calculateQuadratic(a, b, c);
    }

    function calculateQuadraticTerms(
        uint256[] memory balances,
        uint256 sqrtAlpha,
        uint256 sqrtBeta
    )
        external
        pure
        returns (
            uint256,
            uint256,
            uint256
        )
    {
        return GyroTwoMath._calculateQuadraticTerms(balances, sqrtAlpha, sqrtBeta);
    }

    function calculateInvariant(
        uint256[] memory balances,
        uint256 sqrtAlpha,
        uint256 sqrtBeta
    ) external pure returns (uint256 invariant) {
        return GyroTwoMath._calculateInvariant(balances, sqrtAlpha, sqrtBeta);
    }

    function liquidityInvariantUpdate(
        uint256[] memory balances,
        uint256 sqrtAlpha,
        uint256 sqrtBeta,
        uint256 lastInvariant,
        uint256[] memory deltaBalances,
        bool isIncreaseLiq
    ) external pure returns (uint256 invariant) {
        return
            GyroTwoMath._liquidityInvariantUpdate(
                balances,
                sqrtAlpha,
                sqrtBeta,
                lastInvariant,
                deltaBalances,
                isIncreaseLiq
            );
    }

    function calcOutGivenIn(
        uint256 balanceIn,
        uint256 balanceOut,
        uint256 amountIn,
        uint256 virtualParamIn,
        uint256 virtualParamOut,
        uint256 currentInvariant
    ) external pure returns (uint256) {
        return
            GyroTwoMath._calcOutGivenIn(
                balanceIn,
                balanceOut,
                amountIn,
                virtualParamIn,
                virtualParamOut,
                currentInvariant
            );
    }

    function calcInGivenOut(
        uint256 balanceIn,
        uint256 balanceOut,
        uint256 amountOut,
        uint256 virtualParamIn,
        uint256 virtualParamOut,
        uint256 currentInvariant
    ) external pure returns (uint256) {
        return
            GyroTwoMath._calcInGivenOut(
                balanceIn,
                balanceOut,
                amountOut,
                virtualParamIn,
                virtualParamOut,
                currentInvariant
            );
    }

    function calculateVirtualParameter0(uint256 invariant, uint256 sqrtBeta)
        external
        pure
        returns (uint256)
    {
        return GyroTwoMath._calculateVirtualParameter0(invariant, sqrtBeta);
    }

    function calculateVirtualParameter1(uint256 invariant, uint256 sqrtAlpha)
        external
        pure
        returns (uint256)
    {
        return GyroTwoMath._calculateVirtualParameter1(invariant, sqrtAlpha);
    }

    function calculateSqrtPrice(uint256 invariant, uint256 virtualX)
        external
        pure
        returns (uint256)
    {
        return GyroTwoMath._calculateSqrtPrice(invariant, virtualX);
    }

    function sqrt(uint256 input) external pure returns (uint256) {
        return GyroTwoMath._squareRoot(input);
    }

    function calcAllTokensInGivenExactBptOut(
        uint256[] memory balances,
        uint256 bptAmountOut,
        uint256 totalBPT
    ) external pure returns (uint256[] memory) {
        return GyroTwoMath._calcAllTokensInGivenExactBptOut(balances, bptAmountOut, totalBPT);
    }

    function calcTokensOutGivenExactBptIn(
        uint256[] memory balances,
        uint256 bptAmountIn,
        uint256 totalBPT
    ) external pure returns (uint256[] memory) {
        return GyroTwoMath._calcTokensOutGivenExactBptIn(balances, bptAmountIn, totalBPT);
    }

    function calcProtocolFees(
        uint256 previousInvariant,
        uint256 currentInvariant,
        uint256 currentBptSupply,
        uint256 protocolSwapFeePerc,
        uint256 protocolFeeGyroPortion
    ) external pure returns (uint256, uint256) {
        return
            GyroTwoMath._calcProtocolFees(
                previousInvariant,
                currentInvariant,
                currentBptSupply,
                protocolSwapFeePerc,
                protocolFeeGyroPortion
            );
    }
}

// SPDX-License-Identifier: GPL-3.0-or-later
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.

// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.

// You should have received a copy of the GNU General Public License
// along with this program.  If not, see <http://www.gnu.org/licenses/>.

pragma solidity ^0.7.0;
pragma experimental ABIEncoderV2;

import "@balancer-labs/v2-solidity-utils/contracts/math/FixedPoint.sol";

import "@balancer-labs/v2-pool-weighted/contracts/WeightedPoolUserDataHelpers.sol";
import "@balancer-labs/v2-pool-weighted/contracts/WeightedPool2TokensMiscData.sol";

import "../../libraries/GyroConfigKeys.sol";
import "../../interfaces/IGyroConfig.sol";

import "./ExtensibleWeightedPool2Tokens.sol";
import "./Gyro2PoolErrors.sol";
import "./GyroTwoMath.sol";
import "./GyroTwoOracleMath.sol";

contract GyroTwoPool is ExtensibleWeightedPool2Tokens, GyroTwoOracleMath {
    using FixedPoint for uint256;
    using WeightedPoolUserDataHelpers for bytes;
    using WeightedPool2TokensMiscData for bytes32;

    uint256 private _sqrtAlpha;
    uint256 private _sqrtBeta;

    IGyroConfig public gyroConfig;

    struct GyroParams {
        NewPoolParams baseParams;
        uint256 sqrtAlpha; // A: Should already be upscaled
        uint256 sqrtBeta; // A: Should already be upscaled. Could be passed as an array[](2)
    }

    constructor(GyroParams memory params, address configAddress)
        ExtensibleWeightedPool2Tokens(params.baseParams)
    {
        _require(params.sqrtAlpha < params.sqrtBeta, Gyro2PoolErrors.SQRT_PARAMS_WRONG);
        _sqrtAlpha = params.sqrtAlpha;
        _sqrtBeta = params.sqrtBeta;

        gyroConfig = IGyroConfig(configAddress);
    }

    // Returns sqrtAlpha and sqrtBeta (square roots of lower and upper price bounds of p_x respectively)

    function getSqrtParameters() external view returns (uint256[] memory) {
        return _sqrtParameters();
    }

    function _sqrtParameters() internal view virtual returns (uint256[] memory) {
        uint256[] memory virtualParameters = new uint256[](2);
        virtualParameters[0] = _sqrtParameters(true);
        virtualParameters[1] = _sqrtParameters(false);
        return virtualParameters;
    }

    function _sqrtParameters(bool parameter0) internal view virtual returns (uint256) {
        return parameter0 ? _sqrtAlpha : _sqrtBeta;
    }

    // Returns virtual offsets a and b for reserves x and y respectively, as in (x+a)*(y+b)=L^2

    function getvirtualParameters() external view returns (uint256[] memory) {
        return _getVirtualParameters();
    }

    function _getVirtualParameters() internal view returns (uint256[] memory) {
        uint256[] memory virtualParameters = new uint256[](2);

        uint256[] memory sqrtParams = _sqrtParameters();
        uint256 _invariant = _lastInvariant;

        virtualParameters[0] = _virtualParameters(true, sqrtParams[1], _invariant);
        virtualParameters[1] = _virtualParameters(false, sqrtParams[0], _invariant);
        return virtualParameters;
    }

    function _getVirtualParameters(uint256[] memory sqrtParams, uint256 invariant)
        internal
        view
        virtual
        returns (uint256[] memory)
    {
        uint256[] memory virtualParameters = new uint256[](2);

        virtualParameters[0] = _virtualParameters(true, sqrtParams[1], invariant);
        virtualParameters[1] = _virtualParameters(false, sqrtParams[0], invariant);
        return virtualParameters;
    }

    function _virtualParameters(
        bool parameter0,
        uint256 sqrtParam,
        uint256 invariant
    ) internal view virtual returns (uint256) {
        return
            parameter0
                ? (GyroTwoMath._calculateVirtualParameter0(invariant, sqrtParam))
                : (GyroTwoMath._calculateVirtualParameter1(invariant, sqrtParam));
    }

    /**
     * @dev Returns the current value of the invariant.
     */
    function getInvariant() public view override returns (uint256) {
        (, uint256[] memory balances, ) = getVault().getPoolTokens(getPoolId());
        uint256[] memory sqrtParams = _sqrtParameters();

        // Since the Pool hooks always work with upscaled balances, we manually
        // upscale here for consistency
        _upscaleArray(balances);

        return GyroTwoMath._calculateInvariant(balances, sqrtParams[0], sqrtParams[1]);
    }

    // Swap Hooks

    function onSwap(
        SwapRequest memory request,
        uint256 balanceTokenIn,
        uint256 balanceTokenOut
    ) public virtual override whenNotPaused onlyVault(request.poolId) returns (uint256) {
        bool tokenInIsToken0 = request.tokenIn == _token0;

        uint256 scalingFactorTokenIn = _scalingFactor(tokenInIsToken0);
        uint256 scalingFactorTokenOut = _scalingFactor(!tokenInIsToken0);

        // All token amounts are upscaled.
        balanceTokenIn = _upscale(balanceTokenIn, scalingFactorTokenIn);
        balanceTokenOut = _upscale(balanceTokenOut, scalingFactorTokenOut);

        // Update price oracle with the pre-swap balances
        _updateOracle(
            request.lastChangeBlock,
            tokenInIsToken0 ? balanceTokenIn : balanceTokenOut,
            tokenInIsToken0 ? balanceTokenOut : balanceTokenIn
        );

        // All the calculations in one function to avoid Error Stack Too Deep
        (
            uint256 currentInvariant,
            uint256 virtualParamIn,
            uint256 virtualParamOut
        ) = _calculateCurrentValues(balanceTokenIn, balanceTokenOut, tokenInIsToken0);

        if (request.kind == IVault.SwapKind.GIVEN_IN) {
            // Fees are subtracted before scaling, to reduce the complexity of the rounding direction analysis.
            // This is amount - fee amount, so we round up (favoring a higher fee amount).
            uint256 feeAmount = request.amount.mulUp(getSwapFeePercentage());
            request.amount = _upscale(request.amount.sub(feeAmount), scalingFactorTokenIn);

            uint256 amountOut = _onSwapGivenIn(
                request,
                balanceTokenIn,
                balanceTokenOut,
                virtualParamIn,
                virtualParamOut,
                currentInvariant
            );

            // amountOut tokens are exiting the Pool, so we round down.
            return _downscaleDown(amountOut, scalingFactorTokenOut);
        } else {
            request.amount = _upscale(request.amount, scalingFactorTokenOut);

            uint256 amountIn = _onSwapGivenOut(
                request,
                balanceTokenIn,
                balanceTokenOut,
                virtualParamIn,
                virtualParamOut,
                currentInvariant
            );

            // amountIn tokens are entering the Pool, so we round up.
            amountIn = _downscaleUp(amountIn, scalingFactorTokenIn);

            // Fees are added after scaling happens, to reduce the complexity of the rounding direction analysis.
            // This is amount + fee amount, so we round up (favoring a higher fee amount).
            return amountIn.divUp(getSwapFeePercentage().complement());
        }
    }

    function _onSwapGivenIn(
        SwapRequest memory swapRequest,
        uint256 currentBalanceTokenIn,
        uint256 currentBalanceTokenOut,
        uint256 virtualParamIn,
        uint256 virtualParamOut,
        uint256 invariant
    ) private pure returns (uint256) {
        // Swaps are disabled while the contract is paused.
        return
            GyroTwoMath._calcOutGivenIn(
                currentBalanceTokenIn,
                currentBalanceTokenOut,
                swapRequest.amount,
                virtualParamIn,
                virtualParamOut,
                invariant
            );
    }

    function _onSwapGivenOut(
        SwapRequest memory swapRequest,
        uint256 currentBalanceTokenIn,
        uint256 currentBalanceTokenOut,
        uint256 virtualParamIn,
        uint256 virtualParamOut,
        uint256 invariant
    ) private pure returns (uint256) {
        // Swaps are disabled while the contract is paused.
        return
            GyroTwoMath._calcInGivenOut(
                currentBalanceTokenIn,
                currentBalanceTokenOut,
                swapRequest.amount,
                virtualParamIn,
                virtualParamOut,
                invariant
            );
    }

    function calculateCurrentValues(
        uint256 balanceTokenIn,
        uint256 balanceTokenOut,
        bool tokenInIsToken0
    )
        public
        view
        returns (
            uint256 currentInvariant,
            uint256 virtualParamIn,
            uint256 virtualParamOut
        )
    {
        return _calculateCurrentValues(balanceTokenIn, balanceTokenOut, tokenInIsToken0);
    }

    function _calculateCurrentValues(
        uint256 balanceTokenIn,
        uint256 balanceTokenOut,
        bool tokenInIsToken0
    )
        internal
        view
        returns (
            uint256 currentInvariant,
            uint256 virtualParamIn,
            uint256 virtualParamOut
        )
    {
        // if we have more tokens we might need to get the balances from the Vault
        uint256[] memory balances = new uint256[](2);
        balances[0] = tokenInIsToken0 ? balanceTokenIn : balanceTokenOut;
        balances[1] = tokenInIsToken0 ? balanceTokenOut : balanceTokenIn;

        uint256[] memory sqrtParams = _sqrtParameters();

        currentInvariant = GyroTwoMath._calculateInvariant(balances, sqrtParams[0], sqrtParams[1]);

        uint256[] memory virtualParam = new uint256[](2);
        virtualParam = _getVirtualParameters(sqrtParams, currentInvariant);

        virtualParamIn = tokenInIsToken0 ? virtualParam[0] : virtualParam[1];
        virtualParamOut = tokenInIsToken0 ? virtualParam[1] : virtualParam[0];
    }

    //Note: is public visibility ok for the following function?

    /**
     * @dev Called when the Pool is joined for the first time; that is, when the BPT total supply is zero.
     *
     * Returns the amount of BPT to mint, and the token amounts the Pool will receive in return.
     *
     * Minted BPT will be sent to `recipient`, except for _MINIMUM_BPT, which will be deducted from this amount and sent
     * to the zero address instead. This will cause that BPT to remain forever locked there, preventing total BTP from
     * ever dropping below that value, and ensuring `_onInitializePool` can only be called once in the entire Pool's
     * lifetime.
     *
     * The tokens granted to the Pool will be transferred from `sender`. These amounts are considered upscaled and will
     * be downscaled (rounding up) before being returned to the Vault.
     */
    function _onInitializePool(
        bytes32,
        address,
        address,
        bytes memory userData
    ) internal override returns (uint256, uint256[] memory) {
        BaseWeightedPool.JoinKind kind = userData.joinKind();
        _require(kind == BaseWeightedPool.JoinKind.INIT, Errors.UNINITIALIZED);

        uint256[] memory amountsIn = userData.initialAmountsIn();
        InputHelpers.ensureInputLengthMatch(amountsIn.length, 2);
        _upscaleArray(amountsIn);

        uint256[] memory sqrtParams = _sqrtParameters();

        uint256 invariantAfterJoin = GyroTwoMath._calculateInvariant(
            amountsIn,
            sqrtParams[0],
            sqrtParams[1]
        );

        // Set the initial BPT to the value of the invariant times the number of tokens. This makes BPT supply more
        // consistent in Pools with similar compositions but different number of tokens.

        uint256 bptAmountOut = Math.mul(invariantAfterJoin, 2);

        _lastInvariant = invariantAfterJoin;

        return (bptAmountOut, amountsIn);
    }

    /**
     * @dev Called whenever the Pool is joined after the first initialization join (see `_onInitializePool`).
     *
     * Returns the amount of BPT to mint, the token amounts that the Pool will receive in return, and the number of
     * tokens to pay in protocol swap fees.
     *
     * Implementations of this function might choose to mutate the `balances` array to save gas (e.g. when
     * performing intermediate calculations, such as subtraction of due protocol fees). This can be done safely.
     *
     * Minted BPT will be sent to `recipient`.
     *
     * The tokens granted to the Pool will be transferred from `sender`. These amounts are considered upscaled and will
     * be downscaled (rounding up) before being returned to the Vault.
     *
     * Due protocol swap fees will be taken from the Pool's balance in the Vault (see `IBasePool.onJoinPool`). These
     * amounts are considered upscaled and will be downscaled (rounding down) before being returned to the Vault.
     *
     * protocolSwapFeePercentage argument is intentionally unused as protocol fees are handled in a different way
     */
    function _onJoinPool(
        bytes32,
        address,
        address,
        uint256[] memory balances,
        uint256,
        uint256, //protocolSwapFeePercentage,
        bytes memory userData
    )
        internal
        override
        returns (
            uint256,
            uint256[] memory,
            uint256[] memory
        )
    {
        // Due protocol swap fee amounts are computed by measuring the growth of the invariant between the previous join
        // or exit event and now - the invariant's growth is due exclusively to swap fees. This avoids spending gas
        // computing them on each individual swap

        uint256[] memory sqrtParams = _sqrtParameters();

        // Due protocol swap fee amounts are computed by measuring the growth of the invariant between the previous
        // join or exit event and now - the invariant's growth is due exclusively to swap fees. This avoids
        // spending gas calculating the fees on each individual swap.
        uint256 invariantBeforeAction = GyroTwoMath._calculateInvariant(
            balances,
            sqrtParams[0],
            sqrtParams[1]
        );

        _distributeFees(invariantBeforeAction);

        (uint256 bptAmountOut, uint256[] memory amountsIn) = _doJoin(balances, userData);

        // Since we pay fees in BPT, they have not changed the invariant and 'invariantBeforeAction' is still consistent with
        // 'balances'. Therefore, we can use a simplified method to update the invariant that does not require a full
        // re-computation.
        // Note: Should this be changed in the future, we also need to reduce the invariant proportionally by the total
        // protocol fee factor.
        _lastInvariant = GyroTwoMath._liquidityInvariantUpdate(
            balances,
            sqrtParams[0],
            sqrtParams[1],
            invariantBeforeAction,
            amountsIn,
            true
        );

        // returns a new uint256[](2) b/c Balancer vault is expecting a fee array, but fees paid in BPT instead
        return (bptAmountOut, amountsIn, new uint256[](2));
    }

    function _doJoin(uint256[] memory balances, bytes memory userData)
        internal
        view
        returns (uint256 bptAmountOut, uint256[] memory amountsIn)
    {
        BaseWeightedPool.JoinKind kind = userData.joinKind();

        // We do NOT currently support unbalanced update, i.e., EXACT_TOKENS_IN_FOR_BPT_OUT or TOKEN_IN_FOR_EXACT_BPT_OUT
        if (kind == BaseWeightedPool.JoinKind.ALL_TOKENS_IN_FOR_EXACT_BPT_OUT) {
            (bptAmountOut, amountsIn) = _joinAllTokensInForExactBPTOut(balances, userData);
        } else {
            _revert(Errors.UNHANDLED_JOIN_KIND);
        }
    }

    function _joinAllTokensInForExactBPTOut(uint256[] memory balances, bytes memory userData)
        internal
        view
        override
        returns (uint256, uint256[] memory)
    {
        uint256 bptAmountOut = userData.allTokensInForExactBptOut();
        // Note that there is no maximum amountsIn parameter: this is handled by `IVault.joinPool`.

        uint256[] memory amountsIn = GyroTwoMath._calcAllTokensInGivenExactBptOut(
            balances,
            bptAmountOut,
            totalSupply()
        );

        return (bptAmountOut, amountsIn);
    }

    /**
     * @dev Called whenever the Pool is exited.
     *
     * Returns the amount of BPT to burn, the token amounts for each Pool token that the Pool will grant in return, and
     * the number of tokens to pay in protocol swap fees.
     *
     * Implementations of this function might choose to mutate the `balances` array to save gas (e.g. when
     * performing intermediate calculations, such as subtraction of due protocol fees). This can be done safely.
     *
     * BPT will be burnt from `sender`.
     *
     * The Pool will grant tokens to `recipient`. These amounts are considered upscaled and will be downscaled
     * (rounding down) before being returned to the Vault.
     *
     * Due protocol swap fees will be taken from the Pool's balance in the Vault (see `IBasePool.onExitPool`). These
     * amounts are considered upscaled and will be downscaled (rounding down) before being returned to the Vault.
     *
     * protocolSwapFeePercentage argument is intentionally unused as protocol fees are handled in a different way
     */
    function _onExitPool(
        bytes32,
        address,
        address,
        uint256[] memory balances,
        uint256 lastChangeBlock,
        uint256, // protocolSwapFeePercentage,
        bytes memory userData
    )
        internal
        override
        returns (
            uint256 bptAmountIn,
            uint256[] memory amountsOut,
            uint256[] memory dueProtocolFeeAmounts
        )
    {
        // Exits are not completely disabled while the contract is paused: proportional exits (exact BPT in for tokens
        // out) remain functional.

        uint256[] memory sqrtParams = _sqrtParameters();

        // Note: If the contract is paused, swap protocol fee amounts are not charged and the oracle is not updated
        // to avoid extra calculations and reduce the potential for errors.
        if (_isNotPaused()) {
            // Update price oracle with the pre-exit balances
            _updateOracle(lastChangeBlock, balances[0], balances[1]);

            // Due protocol swap fee amounts are computed by measuring the growth of the invariant between the previous
            // join or exit event and now - the invariant's growth is due exclusively to swap fees. This avoids
            // spending gas calculating the fees on each individual swap.
            uint256 invariantBeforeAction = GyroTwoMath._calculateInvariant(
                balances,
                sqrtParams[0],
                sqrtParams[1]
            );

            _distributeFees(invariantBeforeAction);

            (bptAmountIn, amountsOut) = _doExit(balances, userData);

            // Since we pay fees in BPT, they have not changed the invariant and 'invariantBeforeAction' is still consistent with
            // 'balances'. Therefore, we can use a simplified method to update the invariant that does not require a full
            // re-computation.
            // Note: Should this be changed in the future, we also need to reduce the invariant proportionally by the total
            // protocol fee factor.
            _lastInvariant = GyroTwoMath._liquidityInvariantUpdate(
                balances,
                sqrtParams[0],
                sqrtParams[1],
                invariantBeforeAction,
                amountsOut,
                false
            );
        } else {
            // Note: If the contract is paused, swap protocol fee amounts are not charged and the oracle is not updated
            // to avoid extra calculations and reduce the potential for errors.
            (bptAmountIn, amountsOut) = _doExit(balances, userData);

            // We need to re-calculate the invariant with the updated balances from scratch in this case.
            _mutateAmounts(balances, amountsOut, FixedPoint.sub);
            _lastInvariant = GyroTwoMath._calculateInvariant(
                balances,
                sqrtParams[0],
                sqrtParams[1]
            );
        }

        // returns a new uint256[](2) b/c Balancer vault is expecting a fee array, but fees paid in BPT instead
        return (bptAmountIn, amountsOut, new uint256[](2));
    }

    function _doExit(uint256[] memory balances, bytes memory userData)
        internal
        view
        returns (uint256 bptAmountIn, uint256[] memory amountsOut)
    {
        BaseWeightedPool.ExitKind kind = userData.exitKind();

        // We do NOT support unbalanced exit at the moment, i.e., EXACT_BPT_IN_FOR_ONE_TOKEN_OUT or
        // BPT_IN_FOR_EXACT_TOKENS_OUT.
        if (kind == BaseWeightedPool.ExitKind.EXACT_BPT_IN_FOR_TOKENS_OUT) {
            (bptAmountIn, amountsOut) = _exitExactBPTInForTokensOut(balances, userData);
        } else {
            _revert(Errors.UNHANDLED_EXIT_KIND);
        }
    }

    function _exitExactBPTInForTokensOut(uint256[] memory balances, bytes memory userData)
        internal
        view
        override
        returns (uint256, uint256[] memory)
    {
        // This exit function is the only one that is not disabled if the contract is paused: it remains unrestricted
        // in an attempt to provide users with a mechanism to retrieve their tokens in case of an emergency.
        // This particular exit function is the only one that remains available because it is the simplest one, and
        // therefore the one with the lowest likelihood of errors.

        uint256 bptAmountIn = userData.exactBptInForTokensOut();
        // Note that there is no minimum amountOut parameter: this is handled by `IVault.exitPool`.

        uint256[] memory amountsOut = GyroTwoMath._calcTokensOutGivenExactBptIn(
            balances,
            bptAmountIn,
            totalSupply()
        );
        return (bptAmountIn, amountsOut);
    }

    // Helpers

    /**
     * @dev Computes and distributes fees between the Balancer and the Gyro treasury
     * The fees are computed and distributed in BPT rather than using the
     * Balancer regular distribution mechanism which would pay these in underlying
     */

    function _distributeFees(uint256 invariantBeforeAction) internal {
        // calculate Protocol fees in BPT
        // lastInvariant is the invariant logged at the end of the last liquidity update
        // protocol fees are calculated on swap fees earned between liquidity updates
        (
            uint256 gyroFees,
            uint256 balancerFees,
            address gyroTreasury,
            address balTreasury
        ) = _getDueProtocolFeeAmounts(_lastInvariant, invariantBeforeAction);

        // Pay fees in BPT
        _payFeesBpt(gyroFees, balancerFees, gyroTreasury, balTreasury);
    }

    /**
     * @dev this function overrides inherited function to make sure it is never used
     */
    function _getDueProtocolFeeAmounts(
        uint256[] memory, // balances,
        uint256[] memory, // normalizedWeights,
        uint256, // previousInvariant,
        uint256, // currentInvariant,
        uint256 // protocolSwapFeePercentage
    ) internal pure override returns (uint256[] memory) {
        revert("Not implemented");
    }

    /**
     * @dev Calculates protocol fee amounts in BPT terms
     * Overrides an inherited function and some arguments are intentionally not used (balances, normalizedWeights)
     * protocolSwapFeePercentage is not used b/c we take parameters from GyroConfig instead
     * Returns dueFees, where dueFees[0] = BPT due to Gyro, and dueFees[1] = BPT due to Balancer
     */
    function _getDueProtocolFeeAmounts(uint256 previousInvariant, uint256 currentInvariant)
        internal
        view
        returns (
            uint256,
            uint256,
            address,
            address
        )
    {
        (
            uint256 protocolSwapFeePerc,
            uint256 protocolFeeGyroPortion,
            address gyroTreasury,
            address balTreasury
        ) = _getFeesMetadata();

        // Early return if the protocol swap fee percentage is zero, saving gas.
        if (protocolSwapFeePerc == 0) {
            return (0, 0, gyroTreasury, balTreasury);
        }

        // Calculate fees in BPT
        (uint256 gyroFees, uint256 balancerFees) = GyroTwoMath._calcProtocolFees(
            previousInvariant,
            currentInvariant,
            totalSupply(),
            protocolSwapFeePerc,
            protocolFeeGyroPortion
        );

        return (gyroFees, balancerFees, gyroTreasury, balTreasury);
    }

    function _payFeesBpt(
        uint256 gyroFees,
        uint256 balancerFees,
        address gyroTreasury,
        address balTreasury
    ) internal {
        // Pay fees in BPT to gyro treasury
        if (gyroFees > 0) {
            _mintPoolTokens(gyroTreasury, gyroFees);
        }
        // Pay fees in BPT to bal treasury
        if (balancerFees > 0) {
            _mintPoolTokens(balTreasury, balancerFees);
        }
    }

    function _getFeesMetadata()
        internal
        view
        returns (
            uint256,
            uint256,
            address,
            address
        )
    {
        return (
            gyroConfig.getUint(GyroConfigKeys.PROTOCOL_SWAP_FEE_PERC_KEY),
            gyroConfig.getUint(GyroConfigKeys.PROTOCOL_FEE_GYRO_PORTION_KEY),
            gyroConfig.getAddress(GyroConfigKeys.GYRO_TREASURY_KEY),
            gyroConfig.getAddress(GyroConfigKeys.BAL_TREASURY_KEY)
        );
    }

    /**
     * @dev Updates the Price Oracle based on the Pool's current state (balances, BPT supply and invariant). Must be
     * called on *all* state-changing functions with the balances *before* the state change happens, and with
     * `lastChangeBlock` as the number of the block in which any of the balances last changed.
     */
    function _updateOracle(
        uint256 lastChangeBlock,
        uint256 balanceToken0,
        uint256 balanceToken1
    ) internal override {
        bytes32 miscData = _miscData;
        if (miscData.oracleEnabled() && block.number > lastChangeBlock) {
            uint256[] memory virtualParameters = new uint256[](2);
            virtualParameters = _getVirtualParameters();

            int256 logSpotPrice = GyroTwoOracleMath._calcLogSpotPrice(
                balanceToken0,
                virtualParameters[0],
                balanceToken1,
                virtualParameters[1]
            );

            int256 logBPTPrice = GyroTwoOracleMath._calcLogBPTPrice(
                balanceToken0,
                virtualParameters[0],
                balanceToken1,
                virtualParameters[1],
                miscData.logTotalSupply()
            );

            uint256 oracleCurrentIndex = miscData.oracleIndex();
            uint256 oracleCurrentSampleInitialTimestamp = miscData.oracleSampleCreationTimestamp();
            uint256 oracleUpdatedIndex = _processPriceData(
                oracleCurrentSampleInitialTimestamp,
                oracleCurrentIndex,
                logSpotPrice,
                logBPTPrice,
                miscData.logInvariant()
            );

            if (oracleCurrentIndex != oracleUpdatedIndex) {
                // solhint-disable not-rely-on-time
                miscData = miscData.setOracleIndex(oracleUpdatedIndex);
                miscData = miscData.setOracleSampleCreationTimestamp(block.timestamp);
                _miscData = miscData;
            }
        }
    }
}

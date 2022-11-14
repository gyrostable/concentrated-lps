// SPDX-License-Identifier: LicenseRef-Gyro-1.0
// for information on licensing please see the README in the GitHub repository <https://github.com/gyrostable/concentrated-lps>.

pragma solidity 0.7.6;
pragma experimental ABIEncoderV2;

// import "@balancer-labs/v2-solidity-utils/contracts/math/FixedPoint.sol";
import "../../libraries/GyroFixedPoint.sol";

import "@balancer-labs/v2-pool-weighted/contracts/WeightedPoolUserDataHelpers.sol";
import "@balancer-labs/v2-pool-weighted/contracts/WeightedPool2TokensMiscData.sol";

import "../../libraries/GyroConfigKeys.sol";
import "../../interfaces/IGyroConfig.sol";
import "../../libraries/GyroPoolMath.sol";
import "../../libraries/GyroErrors.sol";

import "../CappedLiquidity.sol";
import "../LocallyPausable.sol";
import "../ExtensibleWeightedPool2Tokens.sol";
import "./Gyro2CLPPoolErrors.sol";
import "./Gyro2CLPMath.sol";
import "./Gyro2CLPOracleMath.sol";

contract Gyro2CLPPool is ExtensibleWeightedPool2Tokens, Gyro2CLPOracleMath, CappedLiquidity, LocallyPausable {
    using GyroFixedPoint for uint256;
    using WeightedPoolUserDataHelpers for bytes;
    using WeightedPool2TokensMiscData for bytes32;

    uint256 private immutable _sqrtAlpha;
    uint256 private immutable _sqrtBeta;

    IGyroConfig public gyroConfig;

    struct GyroParams {
        NewPoolParams baseParams;
        uint256 sqrtAlpha; // A: Should already be upscaled
        uint256 sqrtBeta; // A: Should already be upscaled. Could be passed as an array[](2)
        address capManager;
        CapParams capParams;
        address pauseManager;
    }

    constructor(GyroParams memory params, address configAddress)
        ExtensibleWeightedPool2Tokens(params.baseParams)
        CappedLiquidity(params.capManager, params.capParams)
        LocallyPausable(params.pauseManager)
    {
        _grequire(params.sqrtAlpha < params.sqrtBeta, Gyro2CLPPoolErrors.SQRT_PARAMS_WRONG);
        _grequire(configAddress != address(0), GyroErrors.ZERO_ADDRESS);
        _sqrtAlpha = params.sqrtAlpha;
        _sqrtBeta = params.sqrtBeta;

        gyroConfig = IGyroConfig(configAddress);
    }

    /// @dev Returns sqrtAlpha and sqrtBeta (square roots of lower and upper price bounds of p_x respectively)
    function getSqrtParameters() external view returns (uint256[2] memory) {
        return _sqrtParameters();
    }

    function _sqrtParameters() internal view virtual returns (uint256[2] memory virtualParameters) {
        virtualParameters[0] = _sqrtParameters(true);
        virtualParameters[1] = _sqrtParameters(false);
        return virtualParameters;
    }

    function _sqrtParameters(bool parameter0) internal view virtual returns (uint256) {
        return parameter0 ? _sqrtAlpha : _sqrtBeta;
    }

    /// @dev Returns virtual offsets a and b for reserves x and y respectively, as in (x+a)*(y+b)=L^2
    function getVirtualParameters() external view returns (uint256[] memory virtualParams) {
        (, uint256[] memory balances, ) = getVault().getPoolTokens(getPoolId());
        _upscaleArray(balances);
        // _calculateCurrentValues() is defined in terms of an in/out pair, but we just map this to the 0/1 (x/y) pair.
        (, virtualParams[0], virtualParams[1]) = _calculateCurrentValues(balances[0], balances[1], true);
    }

    function _getVirtualParameters(uint256[2] memory sqrtParams, uint256 invariant)
        internal
        view
        virtual
        returns (uint256[2] memory virtualParameters)
    {
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
                ? (Gyro2CLPMath._calculateVirtualParameter0(invariant, sqrtParam))
                : (Gyro2CLPMath._calculateVirtualParameter1(invariant, sqrtParam));
    }

    /**
     * @dev Returns the current value of the invariant.
     */
    function getInvariant() public view override returns (uint256) {
        (, uint256[] memory balances, ) = getVault().getPoolTokens(getPoolId());
        uint256[2] memory sqrtParams = _sqrtParameters();

        // Since the Pool hooks always work with upscaled balances, we manually upscale here for consistency
        _upscaleArray(balances);

        return Gyro2CLPMath._calculateInvariant(balances, sqrtParams[0], sqrtParams[1]);
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

        // All the calculations in one function to avoid Error Stack Too Deep
        (uint256 currentInvariant, uint256 virtualParamIn, uint256 virtualParamOut) = _calculateCurrentValues(
            balanceTokenIn,
            balanceTokenOut,
            tokenInIsToken0
        );

        // Update price oracle with the pre-swap balances
        _updateOracle(
            request.lastChangeBlock,
            tokenInIsToken0 ? balanceTokenIn : balanceTokenOut,
            tokenInIsToken0 ? balanceTokenOut : balanceTokenIn,
            tokenInIsToken0 ? virtualParamIn : virtualParamOut,
            tokenInIsToken0 ? virtualParamOut : virtualParamIn
        );

        if (request.kind == IVault.SwapKind.GIVEN_IN) {
            // Fees are subtracted before scaling, to reduce the complexity of the rounding direction analysis.
            // This is amount - fee amount, so we round up (favoring a higher fee amount).
            uint256 feeAmount = request.amount.mulUp(getSwapFeePercentage());
            // subtract fee and upscale so request.amount is appropriate for the following pool math.
            request.amount = _upscale(request.amount.sub(feeAmount), scalingFactorTokenIn);

            uint256 amountOut = _onSwapGivenIn(request, balanceTokenIn, balanceTokenOut, virtualParamIn, virtualParamOut);

            // amountOut tokens are exiting the Pool, so we round down.
            return _downscaleDown(amountOut, scalingFactorTokenOut);
        } else {
            request.amount = _upscale(request.amount, scalingFactorTokenOut);

            uint256 amountIn = _onSwapGivenOut(request, balanceTokenIn, balanceTokenOut, virtualParamIn, virtualParamOut);

            // amountIn tokens are entering the Pool, so we round up.
            amountIn = _downscaleUp(amountIn, scalingFactorTokenIn);

            // Fees are added after scaling happens, to reduce the complexity of the rounding direction analysis.
            // This is amount + fee amount, so we round up (favoring a higher fee amount).
            return amountIn.divUp(getSwapFeePercentage().complement());
        }
    }

    // We assume all amounts to be upscaled correctly
    function _onSwapGivenIn(
        SwapRequest memory swapRequest,
        uint256 currentBalanceTokenIn,
        uint256 currentBalanceTokenOut,
        uint256 virtualParamIn,
        uint256 virtualParamOut
    ) internal pure override returns (uint256) {
        // NB: Swaps are disabled while the contract is paused.
        return Gyro2CLPMath._calcOutGivenIn(currentBalanceTokenIn, currentBalanceTokenOut, swapRequest.amount, virtualParamIn, virtualParamOut);
    }

    function _onSwapGivenOut(
        SwapRequest memory swapRequest,
        uint256 currentBalanceTokenIn,
        uint256 currentBalanceTokenOut,
        uint256 virtualParamIn,
        uint256 virtualParamOut
    ) internal pure override returns (uint256) {
        // NB: Swaps are disabled while the contract is paused.
        return Gyro2CLPMath._calcInGivenOut(currentBalanceTokenIn, currentBalanceTokenOut, swapRequest.amount, virtualParamIn, virtualParamOut);
    }

    /// @dev invariant and virtual offsets.
    function calculateCurrentValues(
        uint256 balanceTokenIn, // not scaled
        uint256 balanceTokenOut, // not scaled
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
        uint256 scalingFactorTokenIn = _scalingFactor(tokenInIsToken0);
        uint256 scalingFactorTokenOut = _scalingFactor(!tokenInIsToken0);
        balanceTokenIn = _upscale(balanceTokenIn, scalingFactorTokenIn);
        balanceTokenOut = _upscale(balanceTokenOut, scalingFactorTokenOut);
        return _calculateCurrentValues(balanceTokenIn, balanceTokenOut, tokenInIsToken0);
    }

    function _calculateCurrentValues(
        uint256 balanceTokenIn, // scaled
        uint256 balanceTokenOut, // scaled
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
        uint256[] memory balances = new uint256[](2);
        balances[0] = tokenInIsToken0 ? balanceTokenIn : balanceTokenOut;
        balances[1] = tokenInIsToken0 ? balanceTokenOut : balanceTokenIn;

        uint256[2] memory sqrtParams = _sqrtParameters();

        currentInvariant = Gyro2CLPMath._calculateInvariant(balances, sqrtParams[0], sqrtParams[1]);

        uint256[2] memory virtualParam = _getVirtualParameters(sqrtParams, currentInvariant);

        virtualParamIn = tokenInIsToken0 ? virtualParam[0] : virtualParam[1];
        virtualParamOut = tokenInIsToken0 ? virtualParam[1] : virtualParam[0];
    }

    /**
     * @dev Called when the Pool is joined for the first time; that is, when the BPT total supply is zero.
     *
     * Returns the amount of BPT to mint, and the token amounts the Pool will receive in return.
     *
     * Minted BPT will be sent to `recipient`, except for _MINIMUM_BPT, which will be deducted from this amount and sent
     * to the zero address instead. This will cause that BPT to remain forever locked there, preventing total BPT from
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

        uint256[2] memory sqrtParams = _sqrtParameters();

        uint256 invariantAfterJoin = Gyro2CLPMath._calculateInvariant(amountsIn, sqrtParams[0], sqrtParams[1]);

        // Set the initial BPT to the value of the invariant times the number of tokens. This makes BPT supply more
        // consistent in Pools with similar compositions but different number of tokens.
        // Note that the BPT supply also depends on the parameters of the pool.

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
     *
     * Responsibility for updating the oracle has been moved from `onJoinPool()` (without the underscore) to this
     * function. That is because both this function and `_updateOracle()` need access to the invariant and this way we
     * can share the computation.
     */
    function _onJoinPool(
        bytes32,
        address,
        address recipient,
        uint256[] memory balances,
        uint256 lastChangeBlock,
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
        // NB Joins are disabled when the pool is paused.

        uint256[2] memory sqrtParams = _sqrtParameters();

        // Due protocol swap fee amounts are computed by measuring the growth of the invariant between the previous
        // join or exit event and now - the invariant's growth is due exclusively to swap fees. This avoids
        // spending gas accounting for fees on each individual swap.
        uint256 invariantBeforeAction = Gyro2CLPMath._calculateInvariant(balances, sqrtParams[0], sqrtParams[1]);
        uint256[2] memory virtualParam = _getVirtualParameters(sqrtParams, invariantBeforeAction);

        // Update price oracle with pre-join balances
        _updateOracle(lastChangeBlock, balances[0], balances[1], virtualParam[0], virtualParam[1]);

        _distributeFees(invariantBeforeAction);

        (uint256 bptAmountOut, uint256[] memory amountsIn) = _doJoin(balances, userData);

        if (_capParams.capEnabled) {
            _ensureCap(bptAmountOut, balanceOf(recipient), totalSupply());
        }

        // Since we pay fees in BPT, they have not changed the invariant and 'invariantBeforeAction' is still consistent
        // with  'balances'. Therefore, we can use a simplified method to update the invariant that does not require a
        // full re-computation.
        // Note: Should this be changed in the future, we also need to reduce the invariant proportionally by the total
        // protocol fee factor.
        _lastInvariant = GyroPoolMath.liquidityInvariantUpdate(invariantBeforeAction, bptAmountOut, totalSupply(), true);

        // returns a new uint256[](2) b/c Balancer vault is expecting a fee array, but fees paid in BPT instead
        return (bptAmountOut, amountsIn, new uint256[](2));
    }

    function _doJoin(uint256[] memory balances, bytes memory userData) internal view returns (uint256 bptAmountOut, uint256[] memory amountsIn) {
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

        uint256[] memory amountsIn = GyroPoolMath._calcAllTokensInGivenExactBptOut(balances, bptAmountOut, totalSupply());

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

        uint256[2] memory sqrtParams = _sqrtParameters();

        if (_isNotPaused()) {
            // Due protocol swap fee amounts are computed by measuring the growth of the invariant between the previous
            // join or exit event and now - the invariant's growth is due exclusively to swap fees. This avoids
            // spending gas calculating the fees on each individual swap.
            uint256 invariantBeforeAction = Gyro2CLPMath._calculateInvariant(balances, sqrtParams[0], sqrtParams[1]);
            uint256[2] memory virtualParam = _getVirtualParameters(sqrtParams, invariantBeforeAction);

            // Update price oracle with the pre-exit balances
            _updateOracle(lastChangeBlock, balances[0], balances[1], virtualParam[0], virtualParam[1]);

            _distributeFees(invariantBeforeAction);

            (bptAmountIn, amountsOut) = _doExit(balances, userData);

            // Since we pay fees in BPT, they have not changed the invariant and 'invariantBeforeAction' is still
            // consistent with 'balances'. Therefore, we can use a simplified method to update the invariant that does
            // not require a full re-computation.
            // Note: Should this be changed in the future, we also need to reduce the invariant proportionally by the
            // total protocol fee factor.
            _lastInvariant = GyroPoolMath.liquidityInvariantUpdate(invariantBeforeAction, bptAmountIn, totalSupply(), false);
        } else {
            // Note: If the contract is paused, swap protocol fee amounts are not charged and the oracle is not updated
            // to avoid extra calculations and reduce the potential for errors.
            (bptAmountIn, amountsOut) = _doExit(balances, userData);

            // Invalidate _lastInvariant. We do not compute the invariant to reduce the potential for errors or lockup.
            // Instead, we set the invariant such that any following (non-paused) join/exit will ignore and recompute
            // it. (see GyroPoolMath._calcProtocolFees())
            _lastInvariant = type(uint256).max;
        }

        // returns a new uint256[](2) b/c Balancer vault is expecting a fee array, but fees paid in BPT instead
        return (bptAmountIn, amountsOut, new uint256[](2));
    }

    function _doExit(uint256[] memory balances, bytes memory userData) internal view returns (uint256 bptAmountIn, uint256[] memory amountsOut) {
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

        uint256[] memory amountsOut = GyroPoolMath._calcTokensOutGivenExactBptIn(balances, bptAmountIn, totalSupply());
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
        (uint256 gyroFees, uint256 balancerFees, address gyroTreasury, address balTreasury) = _getDueProtocolFeeAmounts(
            _lastInvariant,
            invariantBeforeAction
        );

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
     * @dev Calculates protocol fee amounts in BPT terms.
     * protocolSwapFeePercentage is not used here b/c we take parameters from GyroConfig instead.
     * Returns: BPT due to Gyro, BPT due to Balancer, receiving address for Gyro fees, receiving address for Balancer
     * fees.
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
        (uint256 protocolSwapFeePerc, uint256 protocolFeeGyroPortion, address gyroTreasury, address balTreasury) = _getFeesMetadata();

        // Early return if the protocol swap fee percentage is zero, saving gas.
        if (protocolSwapFeePerc == 0) {
            return (0, 0, gyroTreasury, balTreasury);
        }

        // Calculate fees in BPT
        (uint256 gyroFees, uint256 balancerFees) = GyroPoolMath._calcProtocolFees(
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
        uint256 balanceToken1,
        uint256 virtualParam0,
        uint256 virtualParam1
    ) internal {
        bytes32 miscData = _miscData;
        if (miscData.oracleEnabled() && block.number > lastChangeBlock) {
            int256 logSpotPrice = Gyro2CLPOracleMath._calcLogSpotPrice(balanceToken0, virtualParam0, balanceToken1, virtualParam1);

            int256 logBPTPrice = Gyro2CLPOracleMath._calcLogBPTPrice(
                balanceToken0,
                virtualParam0,
                balanceToken1,
                virtualParam1,
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

    /**
     * @dev this variant of the function, called from `onJoinPool()` and `onExitPool()`, which we inherit, is a no-op.
     * We instead have moved responsibility for updating the oracle to `_onJoinPool()` and `_onExitPool()` and the above
     * version is called from there.
     */
    function _updateOracle(
        uint256 lastChangeBlock,
        uint256 balanceToken0,
        uint256 balanceToken1
    ) internal override {
        // Do nothing.
    }

    function _setPausedState(bool paused) internal override {
        _setPaused(paused);
    }
}

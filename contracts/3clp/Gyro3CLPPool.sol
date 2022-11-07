pragma solidity 0.7.6;
pragma experimental ABIEncoderV2;

import "../../libraries/GyroConfigKeys.sol";
import "../../interfaces/IGyroConfig.sol";
import "../../libraries/GyroPoolMath.sol";
import "../../libraries/GyroErrors.sol";

import "./ExtensibleBaseWeightedPool.sol";
import "./Gyro3CLPMath.sol";
import "./Gyro3CLPPoolErrors.sol";

import "../CappedLiquidity.sol";
import "../LocallyPausable.sol";

/**
 * @dev Gyro Three Pool with immutable weights.
 */
// We derive from ExtensibleBaseWeightedPool and we override a large part of the functionality. In particular the
// weights are not used.
contract Gyro3CLPPool is ExtensibleBaseWeightedPool, CappedLiquidity, LocallyPausable {
    using GyroFixedPoint for uint256;
    using WeightedPoolUserDataHelpers for bytes;

    uint256 private immutable _root3Alpha;

    IGyroConfig public gyroConfig;

    uint256 private constant _MAX_TOKENS = 3;

    IERC20 internal immutable _token0;
    IERC20 internal immutable _token1;
    IERC20 internal immutable _token2;

    // All token balances are normalized to behave as if the token had 18 decimals. We assume a token's decimals will
    // not change throughout its lifetime, and store the corresponding scaling factor for each at construction time.
    // These factors are always greater than or equal to one: tokens with more than 18 decimals are not supported.
    uint256 internal immutable _scalingFactor0;
    uint256 internal immutable _scalingFactor1;
    uint256 internal immutable _scalingFactor2;

    struct NewPoolConfigParams {
        string name;
        string symbol;
        IERC20[] tokens;
        uint256 swapFeePercentage;
        uint256 root3Alpha;
        address owner;
        address capManager;
        CapParams capParams;
        address pauseManager;
    }

    struct NewPoolParams {
        IVault vault;
        address configAddress;
        NewPoolConfigParams config;
        uint256 pauseWindowDuration;
        uint256 bufferPeriodDuration;
    }

    constructor(NewPoolParams memory params)
        ExtensibleBaseWeightedPool(
            params.vault,
            params.config.name,
            params.config.symbol,
            params.config.tokens,
            new address[](3),
            params.config.swapFeePercentage,
            params.pauseWindowDuration,
            params.bufferPeriodDuration,
            params.config.owner
        )
        CappedLiquidity(params.config.capManager, params.config.capParams)
        LocallyPausable(params.config.pauseManager)
    {
        IERC20[] memory tokens = params.config.tokens;
        _grequire(tokens.length == 3, Gyro3CLPPoolErrors.TOKENS_LENGTH_MUST_BE_3);
        InputHelpers.ensureArrayIsSorted(tokens); // For uniqueness and required to make balance reconstruction work
        _grequire(params.configAddress != address(0), GyroErrors.ZERO_ADDRESS);

        _token0 = tokens[0];
        _token1 = tokens[1];
        _token2 = tokens[2];

        _scalingFactor0 = _computeScalingFactor(tokens[0]);
        _scalingFactor1 = _computeScalingFactor(tokens[1]);
        _scalingFactor2 = _computeScalingFactor(tokens[2]);

        // _require(params.config.root3Alpha < FixedPoint.ONE, Gyro3CLPPoolErrors.PRICE_BOUNDS_WRONG);
        _grequire(
            Gyro3CLPMath._MIN_ROOT_3_ALPHA <= params.config.root3Alpha && params.config.root3Alpha <= Gyro3CLPMath._MAX_ROOT_3_ALPHA,
            Gyro3CLPPoolErrors.PRICE_BOUNDS_WRONG
        );
        _root3Alpha = params.config.root3Alpha;
        gyroConfig = IGyroConfig(params.configAddress);
    }

    function getRoot3Alpha() external view returns (uint256) {
        return _root3Alpha;
    }

    // We don't support weights at the moment; in other words, all tokens are always weighted equally and thus their
    // normalized weights are all 1/3. This is what the functions return.

    function _getNormalizedWeight(IERC20) internal view virtual override returns (uint256) {
        return GyroFixedPoint.ONE / 3;
    }

    function _getNormalizedWeights() internal view virtual override returns (uint256[] memory) {
        uint256[] memory normalizedWeights = new uint256[](3);

        // prettier-ignore
        {
            normalizedWeights[0] = GyroFixedPoint.ONE/3;
            normalizedWeights[1] = GyroFixedPoint.ONE/3;
            normalizedWeights[2] = GyroFixedPoint.ONE/3;
        }

        return normalizedWeights;
    }

    /// @dev Since all weights are always the same, the max-weight token is arbitrary. We return token 0.
    function _getNormalizedWeightsAndMaxWeightIndex() internal view virtual override returns (uint256[] memory, uint256) {
        return (_getNormalizedWeights(), 0);
    }

    function _getMaxTokens() internal pure virtual override returns (uint256) {
        return _MAX_TOKENS;
    }

    function _getTotalTokens() internal pure virtual override returns (uint256) {
        return 3;
    }

    /**
     * @dev Returns the scaling factor for one of the Pool's tokens. Reverts if `token` is not a token registered by the
     * Pool.
     */
    function _scalingFactor(IERC20 token) internal view virtual override returns (uint256 scalingFactor) {
        if (token == _token0) {
            scalingFactor = _scalingFactor0;
        } else if (token == _token1) {
            scalingFactor = _scalingFactor1;
        } else if (token == _token2) {
            scalingFactor = _scalingFactor2;
        } else {
            _revert(Errors.INVALID_TOKEN);
        }
    }

    function _scalingFactors() internal view virtual override returns (uint256[] memory) {
        uint256 totalTokens = _getTotalTokens();
        uint256[] memory scalingFactors = new uint256[](totalTokens);

        // prettier-ignore
        {
            scalingFactors[0] = _scalingFactor0;
            scalingFactors[1] = _scalingFactor1;
            scalingFactors[2] = _scalingFactor2;
        }

        return scalingFactors;
    }

    // on{Swap,Join,Exit}() toplevel entry points are not overloaded and taken from ExtensibleBaseWeightedPool. We
    // override the lower-level functions.

    function _onSwapGivenIn(
        SwapRequest memory swapRequest,
        uint256 currentBalanceTokenIn,
        uint256 currentBalanceTokenOut
    ) internal view virtual override whenNotPaused returns (uint256) {
        uint256 virtualOffset = _calculateVirtualOffset(swapRequest, currentBalanceTokenIn, currentBalanceTokenOut);
        return _onSwapGivenIn(swapRequest, currentBalanceTokenIn, currentBalanceTokenOut, virtualOffset);
    }

    function _onSwapGivenOut(
        SwapRequest memory swapRequest,
        uint256 currentBalanceTokenIn,
        uint256 currentBalanceTokenOut
    ) internal view virtual override whenNotPaused returns (uint256) {
        uint256 virtualOffset = _calculateVirtualOffset(swapRequest, currentBalanceTokenIn, currentBalanceTokenOut);
        return _onSwapGivenOut(swapRequest, currentBalanceTokenIn, currentBalanceTokenOut, virtualOffset);
    }

    /** @dev Given two tokens x, y, return the third one among the pool tokens that is neither x nor y. x, y do *not*
     * have to be ordered, but they have to be among the tokens of this pool and they have to be different.
     */
    function _getThirdToken(IERC20 x, IERC20 y) internal view returns (IERC20 tokenOther, uint256 scalingFactorOther) {
        // Sort
        if (x > y) (x, y) = (y, x);

        // We exploit that the variables _token{0,1,2} are sorted.
        if (x == _token0) {
            if (y == _token1) return (_token2, _scalingFactor2);
            if (y != _token2) _grequire(false, Gyro3CLPPoolErrors.TOKENS_NOT_AMONG_POOL_TOKENS);
            return (_token1, _scalingFactor1);
        }
        if (!(x == _token1 && y == _token2)) _grequire(false, Gyro3CLPPoolErrors.TOKENS_NOT_AMONG_POOL_TOKENS);
        return (_token0, _scalingFactor0);
    }

    /** @dev Reads the balance of a token from the balancer vault and returns the scaled amount. Smaller storage access
     * compared to getVault().getPoolTokens().
     */
    function _getScaledTokenBalance(IERC20 token, uint256 scalingFactor) internal view returns (uint256 balance) {
        // Signature of getPoolTokenInfo(): (pool id, token) -> (cash, managed, lastChangeBlock, assetManager)
        // and total amount = cash + managed. See balancer repo, PoolTokens.sol and BalanceAllocation.sol
        (uint256 cash, uint256 managed, , ) = getVault().getPoolTokenInfo(getPoolId(), token);
        balance = cash + managed; // can't overflow, see BalanceAllocation.sol::total() in the Balancer repo.
        balance = balance.mulDown(scalingFactor);
    }

    /** @dev Calculate the offset that that takes real reserves to virtual reserves. Variant that uses the info given
     * during swaps to query less from the vault and save gas.
     */
    function _calculateVirtualOffset(
        SwapRequest memory swapRequest,
        uint256 currentBalanceTokenIn,
        uint256 currentBalanceTokenOut
    ) private view returns (uint256 virtualOffset) {
        // We exploit that everything is symmetric, so we don't have to know which balance is which here
        uint256[] memory balances = new uint256[](3);
        balances[0] = currentBalanceTokenIn;
        balances[1] = currentBalanceTokenOut;

        // Get the third token and query its balance.
        // This needs to be scaled up, like in BasePool._upscaleArray(). The other balances are already scaled up.
        (IERC20 token3, uint256 scalingFactor3) = _getThirdToken(swapRequest.tokenIn, swapRequest.tokenOut);
        balances[2] = _getScaledTokenBalance(token3, scalingFactor3);

        return _calculateVirtualOffset(balances);
    }

    /** @dev Calculate virtual offsets from scaled balances. Balances can be retrieved in the most gas-efficient way. */
    function _calculateVirtualOffset(
        uint256[] memory balances // Need to be already scaled up.
    ) private view returns (uint256 virtualOffset) {
        uint256 root3Alpha = _root3Alpha;
        uint256 invariant = Gyro3CLPMath._calculateInvariant(balances, root3Alpha);
        virtualOffset = invariant.mulDown(root3Alpha);
    }

    /** @dev Get all balances in the pool, scaled by the appropriate scaling factors, in a relatively gas-efficient way.
     */
    function _getAllBalances() private view returns (uint256[] memory balances) {
        // The below is more gas-efficient than the following line because the token slots don't have to be read in the
        // vault.
        // (, uint256[] memory balances, ) = getVault().getPoolTokens(getPoolId());
        balances = new uint256[](3);
        balances[0] = _getScaledTokenBalance(_token0, _scalingFactor0);
        balances[1] = _getScaledTokenBalance(_token1, _scalingFactor1);
        balances[2] = _getScaledTokenBalance(_token2, _scalingFactor2);
        return balances;
    }

    /** @dev Calculate the offset that that takes real reserves to virtual reserves. Uses only the info in the pool, but
     * is rather expensive because a lot has to be queried from the vault.
     */
    function _calculateVirtualOffset() private view returns (uint256 virtualOffset) {
        return _calculateVirtualOffset(_getAllBalances());
    }

    function _calculateInvariant() private view returns (uint256 invariant) {
        return Gyro3CLPMath._calculateInvariant(_getAllBalances(), _root3Alpha);
    }

    function _onSwapGivenIn(
        SwapRequest memory swapRequest,
        uint256 currentBalanceTokenIn,
        uint256 currentBalanceTokenOut,
        uint256 virtualOffset
    ) private pure returns (uint256) {
        return Gyro3CLPMath._calcOutGivenIn(currentBalanceTokenIn, currentBalanceTokenOut, swapRequest.amount, virtualOffset);
    }

    function _onSwapGivenOut(
        SwapRequest memory swapRequest,
        uint256 currentBalanceTokenIn,
        uint256 currentBalanceTokenOut,
        uint256 virtualOffset
    ) private pure returns (uint256) {
        return Gyro3CLPMath._calcInGivenOut(currentBalanceTokenIn, currentBalanceTokenOut, swapRequest.amount, virtualOffset);
    }

    /**
     * @dev Called when the Pool is joined for the first time; that is, when the BPT total supply is zero.
     *
     * Returns the amount of BPT to mint and the token amounts the Pool will receive in return.
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
        uint256[] memory scalingFactors,
        bytes memory userData
    ) internal override whenNotPaused returns (uint256, uint256[] memory) {
        BaseWeightedPool.JoinKind kind = userData.joinKind();
        _require(kind == BaseWeightedPool.JoinKind.INIT, Errors.UNINITIALIZED);

        uint256[] memory amountsIn = userData.initialAmountsIn();
        InputHelpers.ensureInputLengthMatch(amountsIn.length, 3);
        _upscaleArray(amountsIn, scalingFactors);

        uint256 invariantAfterJoin = Gyro3CLPMath._calculateInvariant(amountsIn, _root3Alpha);

        // Set the initial BPT to the value of the invariant times the number of tokens. This makes BPT supply more
        // consistent in Pools with similar compositions but different number of tokens.
        // Note that the BPT supply also depends on the parameters of the pool.
        uint256 bptAmountOut = Math.mul(invariantAfterJoin, 3);

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
     * protocolSwapFeePercentage argument is intentionally unused as protocol fees are handled in a different way
     */
    function _onJoinPool(
        bytes32,
        address,
        address recipient,
        uint256[] memory balances,
        uint256,
        uint256, // protocolSwapFeePercentage, not used
        uint256[] memory,
        bytes memory userData
    )
        internal
        override
        returns (
            uint256 bptAmountOut,
            uint256[] memory amountsIn,
            uint256[] memory dueProtocolFeeAmounts
        )
    {
        // Due protocol swap fee amounts are computed by measuring the growth of the invariant between the previous join
        // or exit event and now - the invariant's growth is due exclusively to swap fees. This avoids spending gas
        // accounting for them on each individual swap

        uint256 root3Alpha = _root3Alpha;

        uint256 invariantBeforeJoin = Gyro3CLPMath._calculateInvariant(balances, root3Alpha);

        _distributeFees(invariantBeforeJoin);

        (bptAmountOut, amountsIn) = _doJoin(balances, userData);

        if (_capParams.capEnabled) {
            _ensureCap(bptAmountOut, balanceOf(recipient), totalSupply());
        }

        // Since we pay fees in BPT, they have not changed the invariant and 'lastInvariant' is still consistent with
        // 'balances'. Therefore, we can use a simplified method to update the invariant that does not require a full
        // re-computation.
        // Note: Should this be changed in the future, we also need to reduce the invariant proportionally by the total
        // protocol fee factor.
        _lastInvariant = GyroPoolMath.liquidityInvariantUpdate(invariantBeforeJoin, bptAmountOut, totalSupply(), true);

        // returns a new uint256[](3) b/c Balancer vault is expecting a fee array, but fees paid in BPT instead
        return (bptAmountOut, amountsIn, new uint256[](3));
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
     * protocolSwapFeePercentage argument is intentionally unused as protocol fees are handled in a different way
     */
    function _onExitPool(
        bytes32,
        address,
        address,
        uint256[] memory balances,
        uint256,
        uint256, // protocolSwapFeePercentage
        uint256[] memory,
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

        uint256 root3Alpha = _root3Alpha;

        if (_isNotPaused()) {
            // Due protocol swap fee amounts are computed by measuring the growth of the invariant between the previous
            // join or exit event and now - the invariant's growth is due exclusively to swap fees. This avoids
            // spending gas calculating the fees on each individual swap.
            uint256 invariantBeforeExit = Gyro3CLPMath._calculateInvariant(balances, root3Alpha);

            _distributeFees(invariantBeforeExit);

            (bptAmountIn, amountsOut) = _doExit(balances, userData);

            // Since we pay fees in BPT, they have not changed the invariant and 'lastInvariant' is still consistent with
            // 'balances'. Therefore, we can use a simplified method to update the invariant that does not require a full
            // re-computation.
            // Note: Should this be changed in the future, we also need to reduce the invariant proportionally by the
            // total protocol fee factor.
            _lastInvariant = GyroPoolMath.liquidityInvariantUpdate(invariantBeforeExit, bptAmountIn, totalSupply(), false);
        } else {
            // Note: If the contract is paused, swap protocol fee amounts are not charged and the oracle is not updated
            // to avoid extra calculations and reduce the potential for errors.
            (bptAmountIn, amountsOut) = _doExit(balances, userData);

            // In the paused state, we do not recompute the invariant to reduce the potential for errors and to avoid
            // lock-up in case the pool is in a state where the involved numerical method does not converge.
            // Instead, we set the invariant such that any following (non-paused) join/exit will ignore and recompute it
            // (see GyroPoolMath._calcProtocolFees())
            _lastInvariant = type(uint256).max;
        }

        // returns a new uint256[](3) b/c Balancer vault is expecting a fee array, but fees paid in BPT instead
        return (bptAmountIn, amountsOut, new uint256[](3));
    }

    /**
     * @dev Returns the current value of the invariant.
     */
    function getInvariant() public view override returns (uint256 invariant) {
        return _calculateInvariant();
    }

    function _joinAllTokensInForExactBPTOut(uint256[] memory balances, bytes memory userData)
        internal
        view
        override
        returns (uint256, uint256[] memory)
    {
        uint256 bptAmountOut = userData.allTokensInForExactBptOut();

        uint256[] memory amountsIn = GyroPoolMath._calcAllTokensInGivenExactBptOut(balances, bptAmountOut, totalSupply());

        return (bptAmountOut, amountsIn);
    }

    function _doExit(uint256[] memory balances, bytes memory userData) internal view returns (uint256 bptAmountIn, uint256[] memory amountsOut) {
        BaseWeightedPool.ExitKind kind = userData.exitKind();

        // We do NOT support unbalanced exit at the moment, i.e., EXACT_BPT_IN_FOR_ONE_TOKEN_OUT or
        // BPT_IN_FOR_EXACT_TOKENS_OUT.
        if (kind == BaseWeightedPool.ExitKind.EXACT_BPT_IN_FOR_TOKENS_OUT) {
            return _exitExactBPTInForTokensOut(balances, userData);
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

    // Protocol Fee Helpers. These are the same functions as in Gyro2CLPPool.

    /**
     * @dev Computes and distributes fees between the Balancer and the Gyro treasury
     * The fees are computed and distributed in BPT rather than using the
     * Balancer regular distribution mechanism which would pay these in underlying
     */
    function _distributeFees(uint256 invariantBeforeAction) internal {
        // calculate Protocol fees in BPT
        // _lastInvariant is the invariant logged at the end of the last liquidity update
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
        uint256, // maxWeightTokenIndex,
        uint256, // previousInvariant,
        uint256, // currentInvariant,
        uint256 // protocolSwapFeePercentage
    ) internal pure override returns (uint256[] memory) {
        revert("Not implemented");
    }

    /**
     * @dev
     * Note: This function is identical to that used in Gyro2CLPPool.sol.
     * Calculates protocol fee amounts in BPT terms.
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

    // Note: This function is identical to that used in Gyro2CLPPool.sol
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

    // Note: This function is identical to that used in Gyro2CLPPool.sol
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

    function _setPausedState(bool paused) internal override {
        _setPaused(paused);
    }
}

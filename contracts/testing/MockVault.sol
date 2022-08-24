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

pragma solidity 0.7.6;
pragma experimental ABIEncoderV2;

import "@balancer-labs/v2-solidity-utils/contracts/openzeppelin/IERC20.sol";
import "@balancer-labs/v2-pool-utils/contracts/oracle/QueryProcessor.sol";

import "@balancer-labs/v2-vault/contracts/interfaces/IVault.sol";
import "@balancer-labs/v2-vault/contracts/interfaces/IBasePool.sol";
import "@balancer-labs/v2-vault/contracts/interfaces/IGeneralPool.sol";
import "@balancer-labs/v2-vault/contracts/interfaces/IPoolSwapStructs.sol";
import "@balancer-labs/v2-vault/contracts/interfaces/IMinimalSwapInfoPool.sol";

import "./WeightedPoolUserData.sol";

contract MockVault is IPoolSwapStructs {
    struct Pool {
        IERC20[] tokens;
        mapping(IERC20 => uint256) balances;
    }

    IAuthorizer private _authorizer;
    mapping(bytes32 => Pool) private pools;

    event Swap(bytes32 indexed poolId, IERC20 indexed tokenIn, IERC20 indexed tokenOut, uint256 amount);

    event PoolBalanceChanged(bytes32 indexed poolId, address indexed liquidityProvider, IERC20[] tokens, int256[] deltas, uint256[] protocolFees);

    constructor(IAuthorizer authorizer) {
        // NOTE: terrible workaround Brownie not adding library to current project
        // unless it is explicitly used somewhere
        QueryProcessor.findNearestSample;

        _authorizer = authorizer;
    }

    function getAuthorizer() external view returns (IAuthorizer) {
        return _authorizer;
    }

    function getPoolTokens(bytes32 poolId) external view returns (IERC20[] memory tokens, uint256[] memory balances) {
        Pool storage pool = pools[poolId];
        tokens = new IERC20[](pool.tokens.length);
        balances = new uint256[](pool.tokens.length);

        for (uint256 i = 0; i < pool.tokens.length; i++) {
            tokens[i] = pool.tokens[i];
            balances[i] = pool.balances[tokens[i]];
        }
        /*
        // DEBUG: Dummy values, no storage access
        tokens = new IERC20[](3);
        balances = new uint256[](3);
        balances[0] = 100e18;
        balances[1] = 100e18;
        balances[2] = 100e18;
        */
    }

    function getPoolTokenInfo(bytes32 poolId, IERC20 token)
        external
        view
        returns (
            uint256 cash,
            uint256 managed,
            uint256 lastChangeBlock,
            address assetManager
        )
    {
        Pool storage pool = pools[poolId];
        cash = pool.balances[token];
        // Dummy:
        managed = 0;
        lastChangeBlock = 0;
        assetManager = address(0x0);
    }

    function registerPool(IVault.PoolSpecialization) external view returns (bytes32) {
        // solhint-disable-previous-line no-empty-blocks
    }

    function registerTokens(
        bytes32 poolId,
        IERC20[] memory tokens,
        address[] memory
    ) external {
        Pool storage pool = pools[poolId];
        for (uint256 i = 0; i < tokens.length; i++) {
            pool.tokens.push(tokens[i]);
        }
    }

    function updateBalances(bytes32 poolId, uint256[] memory balances) external {
        Pool storage pool = pools[poolId];
        for (uint256 i = 0; i < balances.length; i++) {
            pool.balances[pool.tokens[i]] = balances[i];
        }
    }

    function callMinimalPoolSwap(
        address pool,
        SwapRequest memory request,
        uint256 balanceTokenIn,
        uint256 balanceTokenOut
    ) external {
        uint256 amount = IMinimalSwapInfoPool(pool).onSwap(request, balanceTokenIn, balanceTokenOut);
        emit Swap(request.poolId, request.tokenIn, request.tokenOut, amount);
    }

    function callGeneralPoolSwap(
        address pool,
        SwapRequest memory request,
        uint256[] memory balances,
        uint256 indexIn,
        uint256 indexOut
    ) external {
        uint256 amount = IGeneralPool(pool).onSwap(request, balances, indexIn, indexOut);
        emit Swap(request.poolId, request.tokenIn, request.tokenOut, amount);
    }

    struct CallJoinPoolGyroParams {
        IBasePool pool;
        bytes32 poolId;
        address sender;
        address recipient;
        uint256[] currentBalances;
        uint256 lastChangeBlock;
        uint256 protocolSwapFeePercentage;
        uint256[] amountsIn;
        uint256 bptOut;
    }

    // Join pool.
    // NOTE:
    // - CallJoinPoolGyroParams.amountsIn is only used upon initialization.
    // - CallJoinPoolGyroParams.bptOut is only used out of initialization.
    // This is an unfortunate accident and should in principle be refactored.
    function callJoinPoolGyro(CallJoinPoolGyroParams memory params)
        public
        returns (uint256[] memory amountsIn, uint256[] memory dueProtocolFeeAmounts)
    {
        //(, amountsIn, minBPTAmountOut) = abi.decode(self, (JoinKind, uint256[], uint256));

        WeightedPoolUserData.JoinKind kind;
        bytes memory userData;

        {
            bool isEmptyPool = true;
            for (uint256 i = 0; i < params.currentBalances.length; ++i) isEmptyPool = isEmptyPool && (params.currentBalances[i] == 0);
            if (isEmptyPool) {
                kind = WeightedPoolUserData.JoinKind.INIT;
                userData = abi.encode(kind, params.amountsIn, 1e7); //min Bpt
            } else {
                kind = WeightedPoolUserData.JoinKind.ALL_TOKENS_IN_FOR_EXACT_BPT_OUT;
                userData = abi.encode(kind, params.bptOut); // bptOut
            }
        }

        (amountsIn, dueProtocolFeeAmounts) = params.pool.onJoinPool(
            params.poolId,
            params.sender,
            params.recipient,
            params.currentBalances,
            params.lastChangeBlock,
            params.protocolSwapFeePercentage,
            userData
        );

        Pool storage pool = pools[params.poolId];

        for (uint256 i = 0; i < pool.tokens.length; i++) {
            pool.balances[pool.tokens[i]] += amountsIn[i];
        }

        IERC20[] memory tokens = new IERC20[](params.currentBalances.length);
        int256[] memory deltas = new int256[](amountsIn.length);
        for (uint256 i = 0; i < amountsIn.length; ++i) {
            deltas[i] = int256(amountsIn[i]);
        }

        emit PoolBalanceChanged(params.poolId, params.sender, tokens, deltas, dueProtocolFeeAmounts);
    }

    function callExitPoolGyro(
        IBasePool pool,
        bytes32 poolId,
        address sender,
        address recipient,
        uint256[] memory currentBalances,
        uint256 lastChangeBlock,
        uint256 protocolSwapFeePercentage,
        uint256 bptAmountIn
    ) public returns (uint256[] memory amountsOut, uint256[] memory dueProtocolFeeAmounts) {
        //(, amountsIn, minBPTAmountOut) = abi.decode(self, (JoinKind, uint256[], uint256));

        WeightedPoolUserData.ExitKind kind = WeightedPoolUserData.ExitKind.EXACT_BPT_IN_FOR_TOKENS_OUT;

        bytes memory userData = abi.encode(kind, bptAmountIn);

        (amountsOut, dueProtocolFeeAmounts) = pool.onExitPool(
            poolId,
            sender,
            recipient,
            currentBalances,
            lastChangeBlock,
            protocolSwapFeePercentage,
            userData
        );

        Pool storage _pool = pools[poolId];
        for (uint256 i = 0; i < _pool.tokens.length; i++) {
            _pool.balances[_pool.tokens[i]] -= amountsOut[i];
        }

        IERC20[] memory tokens = new IERC20[](currentBalances.length);
        int256[] memory deltas = new int256[](amountsOut.length);
        for (uint256 i = 0; i < amountsOut.length; ++i) {
            deltas[i] = int256(amountsOut[i]);
        }

        emit PoolBalanceChanged(poolId, sender, tokens, deltas, dueProtocolFeeAmounts);
    }

    function callMinimalGyroPoolSwap(
        address poolAddress,
        SwapRequest memory request, //with incomplete userData
        uint256 balanceTokenIn,
        uint256 balanceTokenOut
    ) external {
        // User Data not used in swap
        // bytes memory userData = abi.encode(kind,amountsOutStr,10 * 10 ** 25); //maxBPTAmountIn
        //request.userData  = userData;

        // Dummy to ensure storage is warm. We can't just call getPoolTokens() b/c it's external.
        // The following makes the two balances warm that the real vault will have warm.
        {
            Pool storage pool = pools[request.poolId];
            uint256 dummy;
            dummy = pool.balances[request.tokenIn] + pool.balances[request.tokenOut];
            // no-op to prevent the optimizer from removing this code:
            if (dummy == 0) return;
        }
        /*{
            Pool storage pool = pools[request.poolId];
            IERC20[] memory tokens = new IERC20[](pool.tokens.length);
            uint256[] memory balances = new uint256[](pool.tokens.length);

            for (uint256 i = 0; i < pool.tokens.length; i++) {
                tokens[i] = pool.tokens[i];
                balances[i] = pool.balances[tokens[i]];
            }
            // DEBUG noop
            if(balances[0] == 0 && balances[1] == 0 && balances[2] == 0) {
                return;
            }
        }
        {
            Pool storage pool = pools[request.poolId];
            IERC20[] memory tokens = new IERC20[](pool.tokens.length);
            uint256[] memory balances = new uint256[](pool.tokens.length);

            for (uint256 i = 0; i < pool.tokens.length; i++) {
                tokens[i] = pool.tokens[i];
                balances[i] = pool.balances[tokens[i]];
            }
            // DEBUG noop
            if(balances[0] == 0 && balances[1] == 0 && balances[2] == 0) {
                return;
            }
        }*/

        uint256 amount = IMinimalSwapInfoPool(poolAddress).onSwap(request, balanceTokenIn, balanceTokenOut);
        emit Swap(request.poolId, request.tokenIn, request.tokenOut, amount);

        Pool storage _pool = pools[request.poolId];
        _pool.balances[request.tokenIn] += request.amount;
        _pool.balances[request.tokenOut] -= amount;
    }

    function getPoolId() external view returns (bytes32) {
        // solhint-disable-previous-line no-empty-blocks
    }
}

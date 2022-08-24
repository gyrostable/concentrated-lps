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

import "@balancer-labs/v2-solidity-utils/contracts/math/FixedPoint.sol";
import "@balancer-labs/v2-solidity-utils/contracts/math/Math.sol";
import "@balancer-labs/v2-solidity-utils/contracts/helpers/InputHelpers.sol";

library GyroPoolMath {
    using FixedPoint for uint256;

    // Note: this function is identical to that in WeightedMath.sol audited by Balancer
    function _calcAllTokensInGivenExactBptOut(
        uint256[] memory balances,
        uint256 bptAmountOut,
        uint256 totalBPT
    ) internal pure returns (uint256[] memory) {
        /************************************************************************************
        // tokensInForExactBptOut                                                          //
        // (per token)                                                                     //
        // aI = amountIn (vec)             /   bptOut   \                                  //
        // b = balance (vec)     aI = b * | ------------ |                                 //
        // bptOut = bptAmountOut           \  totalBPT  /                                  //
        // bpt = totalBPT                                                                  //
        ************************************************************************************/

        // Tokens in, so we round up overall.
        uint256 bptRatio = bptAmountOut.divUp(totalBPT);

        uint256[] memory amountsIn = new uint256[](balances.length);
        for (uint256 i = 0; i < balances.length; i++) {
            amountsIn[i] = balances[i].mulUp(bptRatio);
        }

        return amountsIn;
    }

    // Note: this function is identical to that in WeightedMath.sol audited by Balancer
    function _calcTokensOutGivenExactBptIn(
        uint256[] memory balances,
        uint256 bptAmountIn,
        uint256 totalBPT
    ) internal pure returns (uint256[] memory) {
        /**********************************************************************************************
        // exactBPTInForTokensOut                                                                    //
        // (per token)                                                                               //
        // aO = amountOut                  /        bptIn         \                                  //
        // b = balance           a0 = b * | ---------------------  |                                 //
        // bptIn = bptAmountIn             \       totalBPT       /                                  //
        // bpt = totalBPT                                                                            //
        **********************************************************************************************/

        // Since we're computing an amount out, we round down overall. This means rounding down on both the
        // multiplication and division.

        uint256 bptRatio = bptAmountIn.divDown(totalBPT);

        uint256[] memory amountsOut = new uint256[](balances.length);
        for (uint256 i = 0; i < balances.length; i++) {
            amountsOut[i] = balances[i].mulDown(bptRatio);
        }

        return amountsOut;
    }

    /** @dev Calculates protocol fees due to Gyro and Balancer
     *   Note: we do this differently than normal Balancer pools by paying fees in BPT tokens
     *   b/c this is much more gas efficient than doing many transfers of underlying assets
     *   This function gets protocol fee parameters from GyroConfig
     */
    function _calcProtocolFees(
        uint256 previousInvariant,
        uint256 currentInvariant,
        uint256 currentBptSupply,
        uint256 protocolSwapFeePerc,
        uint256 protocolFeeGyroPortion
    ) internal pure returns (uint256, uint256) {
        /*********************************************************************************
        /*  Protocol fee collection should decrease the invariant L by
        *        Delta L = protocolSwapFeePerc * (currentInvariant - previousInvariant)
        *   To take these fees in BPT LP shares, the protocol mints Delta S new LP shares where
        *        Delta S = S * Delta L / ( currentInvariant - Delta L )
        *   where S = current BPT supply
        *   The protocol then splits the fees (in BPT) considering protocolFeeGyroPortion
        *   See also the write-up, Proposition 7.
        *********************************************************************************/

        if (currentInvariant <= previousInvariant) {
            // This shouldn't happen outside of rounding errors, but have this safeguard nonetheless to prevent the Pool
            // from entering a locked state in which joins and exits revert while computing accumulated swap fees.
            return (0, 0);
        }

        // Calculate due protocol fees in BPT terms
        // We round down to prevent issues in the Pool's accounting, even if it means paying slightly less in protocol
        // fees to the Vault.
        // For the numerator, we need to round down delta L. Also for the denominator b/c subtracted
        uint256 diffInvariant = protocolSwapFeePerc.mulDown(
            currentInvariant.sub(previousInvariant)
        );
        uint256 numerator = diffInvariant.mulDown(currentBptSupply);
        uint256 denominator = currentInvariant.sub(diffInvariant);
        uint256 deltaS = numerator.divDown(denominator);

        // Split fees between Gyro and Balancer
        uint256 gyroFees = protocolFeeGyroPortion.mulDown(deltaS);
        uint256 balancerFees = deltaS.sub(gyroFees);

        return (gyroFees, balancerFees);
    }
}

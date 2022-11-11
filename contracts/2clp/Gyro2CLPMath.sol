// SPDX-License-Identifier: for information on licensing please see the README in the GitHub repository <https://github.com/gyrostable/concentrated-lps>. 

pragma solidity 0.7.6;

// import "@balancer-labs/v2-solidity-utils/contracts/math/FixedPoint.sol";
import "../../libraries/GyroFixedPoint.sol";
import "@balancer-labs/v2-solidity-utils/contracts/math/Math.sol";
import "@balancer-labs/v2-solidity-utils/contracts/helpers/InputHelpers.sol";

import "../../libraries/GyroPoolMath.sol";
import "../../libraries/GyroErrors.sol";
import "./Gyro2CLPPoolErrors.sol";

// These functions start with an underscore, as if they were part of a contract and not a library. At some point this
// should be fixed.
// solhint-disable private-vars-leading-underscore

/** @dev Math routines for the 2CLP. Parameters are price bounds [alpha, beta] and sqrt(alpha), sqrt(beta) are used as
 * parameters.
 */
library Gyro2CLPMath {
    using GyroFixedPoint for uint256;

    // Invariant is used to calculate the virtual offsets used in swaps.
    // It is also used to collect protocol swap fees by comparing its value between two times.
    // So we can round always to the same direction. It is also used to initiate the BPT amount
    // and, because there is a minimum BPT, we round down the invariant.
    function _calculateInvariant(
        uint256[] memory balances,
        uint256 sqrtAlpha,
        uint256 sqrtBeta
    ) internal pure returns (uint256) {
        /**********************************************************************************************
        // Calculate with quadratic formula
        // 0 = (1-sqrt(alpha/beta)*L^2 - (y/sqrt(beta)+x*sqrt(alpha))*L - x*y)
        // 0 = a*L^2 + b*L + c
        // here a > 0, b < 0, and c < 0, which is a special case that works well w/o negative numbers
        // taking mb = -b and mc = -c:                               (1/2)
        //                                  mb + (mb^2 + 4 * a * mc)^                   //
        //                   L =    ------------------------------------------          //
        //                                          2 * a                               //
        //                                                                              //
        **********************************************************************************************/
        (uint256 a, uint256 mb, uint256 bSquare, uint256 mc) = _calculateQuadraticTerms(balances, sqrtAlpha, sqrtBeta);
        return _calculateQuadratic(a, mb, bSquare, mc);
    }

    /** @dev Prepares quadratic terms for input to _calculateQuadratic
     *   works with a special case of quadratic that works nicely w/o negative numbers
     *   assumes a > 0, b < 0, and c <= 0 and returns a, -b, -c
     */
    function _calculateQuadraticTerms(
        uint256[] memory balances,
        uint256 sqrtAlpha,
        uint256 sqrtBeta
    )
        internal
        pure
        returns (
            uint256 a,
            uint256 mb,
            uint256 bSquare,
            uint256 mc
        )
    {
        {
            a = GyroFixedPoint.ONE.sub(sqrtAlpha.divDown(sqrtBeta));
            uint256 bterm0 = balances[1].divDown(sqrtBeta);
            uint256 bterm1 = balances[0].mulDown(sqrtAlpha);
            mb = bterm0.add(bterm1);
            mc = balances[0].mulDown(balances[1]);
        }
        // For better fixed point precision, calculate in expanded form w/ re-ordering of multiplications
        // b^2 = x^2 * alpha + x*y*2*sqrt(alpha/beta) + y^2 / beta
        bSquare = (balances[0].mulDown(balances[0])).mulDown(sqrtAlpha).mulDown(sqrtAlpha);
        uint256 bSq2 = (balances[0].mulDown(balances[1])).mulDown(2 * GyroFixedPoint.ONE).mulDown(sqrtAlpha).divDown(sqrtBeta);
        uint256 bSq3 = (balances[1].mulDown(balances[1])).divDown(sqrtBeta.mulUp(sqrtBeta));
        bSquare = bSquare.add(bSq2).add(bSq3);
    }

    /** @dev Calculates quadratic root for a special case of quadratic
     *   assumes a > 0, b < 0, and c <= 0, which is the case for a L^2 + b L + c = 0
     *   where   a = 1 - sqrt(alpha/beta)
     *           b = -(y/sqrt(beta) + x*sqrt(alpha))
     *           c = -x*y
     *   The special case works nicely w/o negative numbers.
     *   The args use the notation "mb" to represent -b, and "mc" to represent -c
     *   Note that this calculates an underestimate of the solution
     */
    function _calculateQuadratic(
        uint256 a,
        uint256 mb,
        uint256 bSquare, // b^2 can be calculated separately with more precision
        uint256 mc
    ) internal pure returns (uint256 invariant) {
        uint256 denominator = a.mulUp(2 * GyroFixedPoint.ONE);
        // order multiplications for fixed point precision
        uint256 addTerm = (mc.mulDown(4 * GyroFixedPoint.ONE)).mulDown(a);
        // The minus sign in the radicand cancels out in this special case, so we add
        uint256 radicand = bSquare.add(addTerm);
        uint256 sqrResult = GyroPoolMath._sqrt(radicand, 5);
        // The minus sign in the numerator cancels out in this special case
        uint256 numerator = mb.add(sqrResult);
        invariant = numerator.divDown(denominator);
    }

    /** @dev Computes how many tokens can be taken out of a pool if `amountIn' are sent, given current balances
     *   balanceIn = existing balance of input token
     *   balanceOut = existing balance of requested output token
     *   virtualParamIn = virtual reserve offset for input token
     *   virtualParamOut = virtual reserve offset for output token
     *   Offsets are L/sqrt(beta) and L*sqrt(alpha) depending on what the `in' and `out' tokens are respectively
     *   Note signs are changed compared to Prop. 4 in Section 2.2.4 Trade (Swap) Exeuction to account for dy < 0
     *
     *   The virtualOffset argument depends on the computed invariant. We add a very small margin to ensure that
     *   potential small errors are not to the detriment of the pool.
     *
     *   This is the same function as the respective function for the 3CLP, except for we allow two
     *   different virtual offsets for the in- and out-asset, respectively, in that other function.
     *   SOMEDAY: This could be made literally the same function in the pool math library.
     */
    function _calcOutGivenIn(
        uint256 balanceIn,
        uint256 balanceOut,
        uint256 amountIn,
        uint256 virtualOffsetIn,
        uint256 virtualOffsetOut
    ) internal pure returns (uint256 amountOut) {
        /**********************************************************************************************
      // Described for X = `in' asset and Y = `out' asset, but equivalent for the other case       //
      // dX = incrX  = amountIn  > 0                                                               //
      // dY = incrY = amountOut < 0                                                                //
      // x = balanceIn             x' = x +  virtualParamX                                         //
      // y = balanceOut            y' = y +  virtualParamY                                         //
      // L  = inv.Liq                   /            x' * y'          \          y' * dX           //
      //                   |dy| = y' - |   --------------------------  |   = --------------  -     //
      //  x' = virtIn                   \          ( x' + dX)         /          x' + dX           //
      //  y' = virtOut                                                                             //
      // Note that -dy > 0 is what the trader receives.                                            //
      // We exploit the fact that this formula is symmetric up to virtualOffset{X,Y}.               //
      // We do not use L^2, but rather x' * y', to prevent a potential accumulation of errors.      //
      // We add a very small safety margin to compensate for potential errors in the invariant.     //
      **********************************************************************************************/

        {
            // The factors in total lead to a multiplicative "safety margin" between the employed virtual offsets
            // very slightly larger than 3e-18.
            uint256 virtInOver = balanceIn.add(virtualOffsetIn.mulUp(GyroFixedPoint.ONE + 2));
            uint256 virtOutUnder = balanceOut.add(virtualOffsetOut.mulDown(GyroFixedPoint.ONE - 1));

            amountOut = virtOutUnder.mulDown(amountIn).divDown(virtInOver.add(amountIn));
        }

        // This ensures amountOut < balanceOut.
        if (!(amountOut <= balanceOut)) _grequire(false, Gyro2CLPPoolErrors.ASSET_BOUNDS_EXCEEDED);
    }

    /** @dev Computes how many tokens must be sent to a pool in order to take `amountOut`, given current balances.
     * See also _calcOutGivenIn(). Adapted for negative values. */
    function _calcInGivenOut(
        uint256 balanceIn,
        uint256 balanceOut,
        uint256 amountOut,
        uint256 virtualOffsetIn,
        uint256 virtualOffsetOut
    ) internal pure returns (uint256 amountIn) {
        /**********************************************************************************************
      // dX = incrX  = amountIn  > 0                                                                 //
      // dY = incrY  = amountOut < 0                                                                 //
      // x = balanceIn             x' = x +  virtualParamX                                           //
      // y = balanceOut            y' = y +  virtualParamY                                           //
      // x = balanceIn                                                                               //
      // L  = inv.Liq               /            x' * y'          \                x' * dy           //
      //                     dx =  |   --------------------------  |  -  x'  = - -----------         //
      // x' = virtIn               \             y' + dy          /                y' + dy           //
      // y' = virtOut                                                                                //
      // Note that dy < 0 < dx.                                                                      //
      // We exploit the fact that this formula is symmetric up to virtualOffset{X,Y}.                //
      // We do not use L^2, but rather x' * y', to prevent a potential accumulation of errors.       //
      // We add a very small safety margin to compensate for potential errors in the invariant.      //
      **********************************************************************************************/
        if (!(amountOut <= balanceOut)) _grequire(false, Gyro2CLPPoolErrors.ASSET_BOUNDS_EXCEEDED);

        {
            // The factors in total lead to a multiplicative "safety margin" between the employed virtual offsets
            // very slightly larger than 3e-18.
            uint256 virtInOver = balanceIn.add(virtualOffsetIn.mulUp(GyroFixedPoint.ONE + 2));
            uint256 virtOutUnder = balanceOut.add(virtualOffsetOut.mulDown(GyroFixedPoint.ONE - 1));

            amountIn = virtInOver.mulUp(amountOut).divUp(virtOutUnder.sub(amountOut));
        }
    }

    /** @dev Calculate virtual offset a for reserves x, as in (x+a)*(y+b)=L^2
     */
    function _calculateVirtualParameter0(uint256 invariant, uint256 _sqrtBeta) internal pure returns (uint256) {
        return invariant.divDown(_sqrtBeta);
    }

    /** @dev Calculate virtual offset b for reserves y, as in (x+a)*(y+b)=L^2
     */
    function _calculateVirtualParameter1(uint256 invariant, uint256 _sqrtAlpha) internal pure returns (uint256) {
        return invariant.mulDown(_sqrtAlpha);
    }
}

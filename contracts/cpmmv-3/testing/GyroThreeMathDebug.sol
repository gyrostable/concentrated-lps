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

import "../GyroThreePoolErrors.sol";

import "../../../libraries/GyroPoolMath.sol";

// These functions start with an underscore, as if they were part of a contract and not a library. At some point this
// should be fixed.
// solhint-disable private-vars-leading-underscore

contract GyroThreeMathDebug {
    event NewtonStep(uint256 deltaAbs, bool deltaIsPos, uint256 rootEst);

    using FixedPoint for uint256;
    using GyroPoolMath for uint256;  // number._sqrt(tolerance)

    // Swap limits: amounts swapped may not be larger than this percentage of total balance.
    // _MAX_OUT_RATIO also ensures that we never compute swaps that take more out than is in the pool. (because
    // it's <= ONE)
    uint256 internal constant _MAX_IN_RATIO = 0.3e18;
    uint256 internal constant _MAX_OUT_RATIO = 0.3e18;
    uint256 internal constant _MIN_BAL_RATIO = 1e13; // 1e-5

    // Stopping criterion for the Newton iteration that computes the invariant:
    // - Stop if the step width doesn't shrink anymore by at least a factor _INVARIANT_SHRINKING_FACTOR_PER_STEP.
    // - ... but in any case, make at least _INVARIANT_MIN_ITERATIONS iterations. This is useful to compensate for a
    // less-than-ideal starting point, which is important when alpha is small.
    uint8 internal constant _INVARIANT_SHRINKING_FACTOR_PER_STEP = 8;
    uint8 internal constant _INVARIANT_MIN_ITERATIONS = 5;

    uint256 internal constant _SAFE_LARGE_POW3_THRESHOLD = 4.87e31; // 4.87e13 scaled; source: Theory
    uint256 internal constant MIDDECIMAL = 1e9;  // splits the fixed point decimals into two.

    // Invariant is used to collect protocol swap fees by comparing its value between two times.
    // So we can round always to the same direction. It is also used to initiate the BPT amount
    // and, because there is a minimum BPT, we round down the invariant.
    // Argument root3Alpha = cube root of the lower price bound (symmetric across assets)
    // Note: all price bounds for the pool are alpha and 1/alpha

    /** @dev This provides an underestimate of the invariant or else signals that a swap should revert
     *  Not getting an underestimate is highly unlikely as 2* newton step should be sufficient, but this isn't provable
     *  This gives an extra step to finding an underestimate but will revert swaps if it is not an underestimate
     *  but liquidity can still be added and removed from the pool, which will change the pool state to something workable again */
    function _calculateInvariant(uint256[] memory balances, uint256 root3Alpha) public returns (uint256 rootEst) {
        (uint256 a, uint256 mb, uint256 mc, uint256 md) = _calculateCubicTerms(balances, root3Alpha);
        return _calculateCubic(a, mb, mc, md, root3Alpha);
    }

    /** @dev Prepares quadratic terms for input to _calculateCubic
     *  assumes a > 0, b < 0, c <= 0, and d <= 0 and returns a, -b, -c, -d
     *  terms come from cubic in Section 3.1.1
     *  argument root3Alpha = cube root of alpha
     */
    function _calculateCubicTerms(uint256[] memory balances, uint256 root3Alpha)
        public
        returns (
            uint256 a,
            uint256 mb,
            uint256 mc,
            uint256 md
        )
    {
        a = FixedPoint.ONE.sub(root3Alpha.mulDown(root3Alpha).mulDown(root3Alpha));
        uint256 bterm = balances[0].add(balances[1]).add(balances[2]);
        mb = bterm.mulDown(root3Alpha).mulDown(root3Alpha);
        uint256 cterm = (balances[0].mulDown(balances[1])).add(balances[1].mulDown(balances[2])).add(balances[2].mulDown(balances[0]));
        mc = cterm.mulDown(root3Alpha);
        md = balances[0].mulDown(balances[1]).mulDown(balances[2]);
    }

    /** @dev Calculate the maximal root of the polynomial a L^3 - mb L^2 - mc L - md.
     *  This root is always non-negative, and it is the unique positive root unless mb == mc == md == 0.
     *  Returns: Overestimate (!) of the root, final step width; usually rootEst - deltaAbs is an underestimate. */
    function _calculateCubic(
        uint256 a,
        uint256 mb,
        uint256 mc,
        uint256 md,
        uint256 root3Alpha
    ) public returns (uint256 rootEst) {
        rootEst = _calculateCubicStartingPoint(a, mb, mc, md);
        rootEst = _runNewtonIteration(a, mb, mc, md, root3Alpha, rootEst);
    }

    /** @dev Starting point for Newton iteration. Safe with all cubic polynomials where the coefficients have the appropriate
     *   signs, but calibrated to the particular polynomial for computing the invariant. */
    function _calculateCubicStartingPoint(
        uint256 a,
        uint256 mb,
        uint256 mc,
        uint256 // md
    ) public returns (uint256 l0) {
        uint256 radic = mb.mulUp(mb).add(a.mulUp(mc).mulUp(3 * FixedPoint.ONE));
        uint256 lmin = mb.divUp(a * 3).add(radic._sqrt(5).divUp(a * 3));
        // This formula has been found experimentally. It is exact for alpha -> 1, where the factor is 1.5. All factors > 1 are safe.
        // For small alpha values, it is more efficient to fallback to a larger factor.
        uint256 alpha = FixedPoint.ONE.sub(a);  // We know that a is in [0, 1].
        uint256 factor = alpha >= 0.5e18 ? 1.5e18 : 2e18;
        l0 = lmin.mulUp(factor);
    }

    /** @dev Find a root of the given polynomial with the given starting point l.
     *   Safe iff l > the local minimum.
     *   Note that f(l) may be negative for the first iteration and will then be positive (up to rounding errors).
     *   f'(l) is always positive for the range of values we consider.
     *   See write-up, Appendix A.
     *   This returns an overestimate (!) of the true l and the step width deltaAbs. Usually, rootEst - deltaAbs will be an underestimate.
     *   Returns: overestimate l, final step width
     */
    function _runNewtonIteration(
        uint256 a,
        uint256 mb,
        uint256 mc,
        uint256 md,
        uint256 root3Alpha,
        uint256 rootEst
    ) public returns (uint256) {
        uint256 deltaAbsPrev = 0;
        for (uint256 iteration = 0; iteration < 255; ++iteration) {
            // The delta to the next step can be positive or negative, so we represent a positive and a negative part
            // separately. The signed delta is delta_plus - delta_minus, but we only ever consider its absolute value.
            (uint256 deltaAbs, bool deltaIsPos) = _calcNewtonDelta(a, mb, mc, md, root3Alpha, rootEst);
            // ^ Note: If we ever set _INVARIANT_MIN_ITERATIONS=0, the following should include `iteration >= 1`.
            emit NewtonStep(deltaAbs, deltaIsPos, rootEst);
            if (deltaAbs <= 1)
                return rootEst;
            if (iteration >= _INVARIANT_MIN_ITERATIONS && deltaIsPos)
                // numerical error dominates
                return rootEst;
            if (iteration >= _INVARIANT_MIN_ITERATIONS && deltaAbs >= deltaAbsPrev / _INVARIANT_SHRINKING_FACTOR_PER_STEP) {
                // stalled
                return rootEst;
            }
            deltaAbsPrev = deltaAbs;
            if (deltaIsPos) rootEst = rootEst.add(deltaAbs);
            else rootEst = rootEst.sub(deltaAbs);
        }
        _revert(GyroThreePoolErrors.INVARIANT_DIDNT_CONVERGE);
    }

    // -f(l)/f'(l), represented as an absolute value and a sign. Require that l is sufficiently large so that f is strictly increasing.
    function _calcNewtonDelta(
        uint256 a,
        uint256 mb,
        uint256 mc,
        uint256 md,
        uint256 root3Alpha,
        uint256 rootEst
    ) public returns (uint256 deltaAbs, bool deltaIsPos) {
        // The following is equal to dfRootEst^3 * a but with an order of operations optimized for precision.
        // Subtraction does not underflow since rootEst is chosen so that it's always above the (only) local minimum.
        uint256 dfRootEst;
        {
            uint256 rootEst2 = rootEst.mulDown(rootEst);
            dfRootEst = (3 * rootEst2).sub(
                (3 * rootEst2).mulDown(root3Alpha).mulDown(root3Alpha).mulDown(root3Alpha)
            );
            dfRootEst = dfRootEst.sub(rootEst.mulDown(mb) * 2).sub(mc);
        }

        // Note: We know that a * rootEst^2 / dfRootEst ~ 1. (see the Mathematica notebook).
        uint256 deltaMinus = _safeLargePow3ADown(rootEst, root3Alpha, dfRootEst);

        // NB: We could the order of operations here in much the same way we did above. But tests showed that
        // this has no significant effect, and it would lead to more complex code.
        uint256 deltaPlus = rootEst.mulDown(rootEst).mulDown(mb);
        deltaPlus = deltaPlus.add(rootEst.mulDown(mc)).divDown(dfRootEst);
        deltaPlus = deltaPlus.add(md.divDown(dfRootEst));

        deltaIsPos = (deltaPlus >= deltaMinus);
        deltaAbs = (deltaIsPos ? deltaPlus.sub(deltaMinus) : deltaMinus.sub(deltaPlus));
    }

    /** @dev Equal to l^3 * (1 - root3Alpha^3) / d. However, we ensure that (1) the order of
      * operations is such that rounding errors are minimized AND (2) this also works in a
      * scenario where these operations would overflow, i.e., when l^3 * 10^36 does not
      * fit into uint256.
      * We assume d >= ONE and, of course, root3Alpha < ONE. In practice, d ~ l^2 */
    function _safeLargePow3ADown(uint256 l, uint256 root3Alpha, uint256 d) public returns (uint256 ret) {
        if (l <= _SAFE_LARGE_POW3_THRESHOLD) {
            // Simple case where there is no overflow
            ret = l.mulDown(l).mulDown(l);
            ret = ret.sub(ret.mulDown(root3Alpha).mulDown(root3Alpha).mulDown(root3Alpha));
            ret = ret.divDown(d);
        } else {
            ret = l.mulDown(l);
            // These products split up the factors into different groups of decimal places to reduce temorary blowup.
            ret = Math.mul(ret, l / FixedPoint.ONE).add(ret.mulDown(l % FixedPoint.ONE));
            uint256 x = ret;
            x = Math.divDown(Math.mul(x, root3Alpha / MIDDECIMAL), MIDDECIMAL).add(
                x.mulDown(root3Alpha % MIDDECIMAL)
            );
            x = Math.divDown(Math.mul(x, root3Alpha / MIDDECIMAL), MIDDECIMAL).add(
                x.mulDown(root3Alpha % MIDDECIMAL)
            );
            x = Math.divDown(Math.mul(x, root3Alpha / MIDDECIMAL), MIDDECIMAL).add(
                x.mulDown(root3Alpha % MIDDECIMAL)
            );
            ret = ret.sub(x);

            // We perform half-precision division to reduce blowup.
            // In contrast to the above multiplications, this loses precision if d is small. However, tests show that,
            // for the l and d values considered here, the precision lost would be below the precision of the fixed
            // point type itself, so nothing is actually lost.
            ret = Math.divDown(Math.mul(ret, MIDDECIMAL), Math.divDown(d, MIDDECIMAL));
        }
    }

    /** @dev Computes how many tokens can be taken out of a pool if `amountIn` are sent, given the
     * current balances and weights.
     * Given an underestimated invariant L, the virtual offset is underestimated, which means that price impacts are greater than for an exact L
     * This combined with rounding directions ensures a swap is calculated in the pool's favor
     * Changed signs compared to original algorithm to account for amountOut < 0.
     * See Proposition 12 in 3.1.4.*/
    function _calcOutGivenIn(
        uint256 balanceIn,
        uint256 balanceOut,
        uint256 amountIn,
        uint256 virtualOffset
    ) public returns (uint256 amountOut) {
        /**********************************************************************************************
        // Described for X = `in' asset and Z = `out' asset, but equivalent for the other case       //
        // dX = incrX  = amountIn  > 0                                                               //
        // dZ = incrZ = amountOut < 0                                                                //
        // x = balanceIn             x' = x +  virtualOffset                                         //
        // z = balanceOut            z' = z +  virtualOffset                                         //
        // L  = inv.Liq                   /            x' * z'          \          z' * dX           //
        //                   |dZ| = z' - |   --------------------------  |   = -------------------   //
        //  x' = virtIn                   \          ( x' + dX)         /          x' + dX           //
        //  z' = virtOut                                                                             //
        // Note that -dz > 0 is what the trader receives.                                            //
        // We exploit the fact that this formula is symmetric up to virtualParam{X,Y,Z}.             //
        // We assume that the virtualOffset carries a relative +/- 3e-18 error due to the invariant  //
        // calculation add an appropriate safety margin.                                             //
        **********************************************************************************************/
        _require(amountIn <= balanceIn.mulDown(_MAX_IN_RATIO), Errors.MAX_IN_RATIO);

        {
            // The factors in total lead to a multiplicative "safety margin" between the employed virtual offsets
            // very slightly larger than 3e-18.
            uint256 virtInOver   = balanceIn.add(virtualOffset.mulUp(FixedPoint.ONE + 2));
            uint256 virtOutUnder = balanceOut.add(virtualOffset.mulDown(FixedPoint.ONE - 1));

            amountOut = virtOutUnder.mulUp(amountIn).divDown(virtInOver.add(amountIn));
        }

        _require(amountOut < balanceOut, GyroThreePoolErrors.ASSET_BOUNDS_EXCEEDED);
        (uint256 balOutNew, uint256 balInNew) = (balanceOut.sub(amountOut), balanceIn.add(amountIn));

        if (balOutNew >= balInNew) {
            _require(balInNew.divDown(balOutNew) > _MIN_BAL_RATIO, GyroThreePoolErrors.ASSET_BOUNDS_EXCEEDED);
        } else {
            _require(balOutNew.divDown(balInNew) > _MIN_BAL_RATIO, GyroThreePoolErrors.ASSET_BOUNDS_EXCEEDED);
        }

        // Note that this in particular reverts if amountOut > balanceOut, i.e., if the out-amount would be more than
        // the balance.
        _require(amountOut <= balanceOut.mulDown(_MAX_OUT_RATIO), Errors.MAX_OUT_RATIO);
    }

    /** @dev Computes how many tokens must be sent to a pool in order to take `amountOut`, given the
     * currhent balances and weights.
     * Given an underestimated invariant L, the virtual offset is underestimated, which means that price impacts are greater than for an exact L
     * This combined with rounding directions ensures a swap is calculated in the pool's favor
     * Similar to the one before but adapting bc negative values (amountOut would be negative).*/
    function _calcInGivenOut(
        uint256 balanceIn,
        uint256 balanceOut,
        uint256 amountOut,
        uint256 virtualOffset
    ) public returns (uint256 amountIn) {
        /**********************************************************************************************
        // Described for X = `in' asset and Z = `out' asset, but equivalent for the other case       //
        // dX = incrX  = amountIn  > 0                                                               //
        // dZ = incrZ = amountOut < 0                                                                //
        // x = balanceIn             x' = x +  virtualOffset                                         //
        // z = balanceOut            z' = z +  virtualOffset                                         //
        // L  = inv.Liq            /            x' * z'          \             x' * dZ               //
        //                   dX = |   --------------------------  | - x' = -------------------       //
        //  x' = virtIn            \          ( z' + dZ)         /             z' - dZ               //
        //  z' = virtOut                                                                             //
        // Note that dz < 0 < dx.                                                                    //
        // We exploit the fact that this formula is symmetric up to virtualParam{X,Y,Z}.             //
        // We use over/underestimated version of the virtualOffset to overestimate the in-amount.    //
        **********************************************************************************************/

        // Note that this in particular reverts if amountOut > balanceOut, i.e., if the trader tries to take more out of
        // the pool than is in it.
        _require(amountOut <= balanceOut.mulDown(_MAX_OUT_RATIO), Errors.MAX_OUT_RATIO);

        {
            // The factors in total lead to a multiplicative "safety margin" between the employed virtual offsets
            // very slightly larger than 3e-18.
            uint256 virtInOver   = balanceIn.add(virtualOffset.mulUp(FixedPoint.ONE + 2));
            uint256 virtOutUnder = balanceOut.add(virtualOffset.mulDown(FixedPoint.ONE - 1));

            amountIn = virtInOver.mulUp(amountOut).divUp(virtOutUnder.sub(amountOut));
        }

        (uint256 balOutNew, uint256 balInNew) = (balanceOut.sub(amountOut), balanceIn.add(amountIn));

        if (balOutNew >= balInNew) {
            _require(balInNew.divDown(balOutNew) > _MIN_BAL_RATIO, GyroThreePoolErrors.ASSET_BOUNDS_EXCEEDED);
        } else {
            _require(balOutNew.divDown(balInNew) > _MIN_BAL_RATIO, GyroThreePoolErrors.ASSET_BOUNDS_EXCEEDED);
        }

        _require(amountIn <= balanceIn.mulDown(_MAX_IN_RATIO), Errors.MAX_IN_RATIO);
    }
}

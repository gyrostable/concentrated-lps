// SPDX-License-Identifier: LicenseRef-Gyro-1.0
// for information on licensing please see the README in the GitHub repository <https://github.com/gyrostable/concentrated-lps>.

pragma solidity 0.7.6;

// import "@balancer-labs/v2-solidity-utils/contracts/math/FixedPoint.sol";
import "@balancer-labs/v2-solidity-utils/contracts/math/Math.sol";
import "@balancer-labs/v2-solidity-utils/contracts/helpers/InputHelpers.sol";

import "./Gyro3CLPPoolErrors.sol";

import "../../libraries/GyroFixedPoint.sol";
import "../../libraries/GyroPoolMath.sol";
import "../../libraries/GyroErrors.sol";

// These functions start with an underscore, as if they were part of a contract and not a library. At some point this
// should be fixed.
// solhint-disable private-vars-leading-underscore

/** @dev Math routines for the "symmetric" 3CLP, i.e., the price bounds are [alpha, 1/alpha] for all three asset
 * pairs. We pass the parameter root3Alpha = 3rd root of alpha. We don't need to compute root3Alpha; instead, we
 * take this as the fundamental parameter and compute alpha = root3Alpha^3 where needed.
 *
 * A large part of this code is concerned with computing the invariant L from the real reserves, via Newton's method.
 * This can be rather large and we need it to high precision. We apply various techniques to prevent an accumulation of
 * errors. See the 2-CLP/3-CLP math paper (especially Appendix A) for context.
 *
 * Most calculations are unchecked and instead we impose some global bounds to ensure that they don't overflow. See the
 * Overflow Analysis writeup for why this works.
 */
library Gyro3CLPMath {
    using GyroFixedPoint for uint256;
    using GyroPoolMath for uint256; // for the function number._sqrt(tolerance)

    // Stopping criterion for the Newton iteration that computes the invariant:
    // - Stop if the step width doesn't shrink anymore by at least a factor _INVARIANT_SHRINKING_FACTOR_PER_STEP.
    // - but in any case, make at least _INVARIANT_MIN_ITERATIONS iterations. This is useful to compensate for a
    //   less-than-ideal starting point, which is important when alpha is small.
    uint8 internal constant _INVARIANT_SHRINKING_FACTOR_PER_STEP = 8;
    uint8 internal constant _INVARIANT_MIN_ITERATIONS = 5;

    // Thresholds that prevent against numerical overflow and excessive inaccuracy:

    uint256 internal constant _MAX_BALANCES = 1e29; // 1e11 = 100 billion, scaled
    uint256 internal constant _MIN_ROOT_3_ALPHA = 0.15874010519681997e18; // 3rd root of 0.004, scaled
    uint256 internal constant _MAX_ROOT_3_ALPHA = 0.9999666655554938e18; // 3rd root of 0.9999, scaled

    // Threshold of l where the normal method of computing the newton step would overflow and we need a workaround.
    uint256 internal constant _L_THRESHOLD_SIMPLE_NUMERICS = 2e31; // 2e13, scaled

    // Threshold of l above which overflows may occur in the Newton iteration. This is far above the theoretically
    // maximum possible (starting or solution or intermediate) value of l, so it would only ever be reached due to some
    // other bug in the Newton iteration.
    uint256 internal constant _L_MAX = 1e34; // 1e16, scaled

    // Minimum value of l / L+, where L+ is the local minimum of the function f. This is significantly below the
    // theoretically minimum possible (starting or solution or intermediate) value of l / L+, so it would only ever be
    // reached due to a bug in the Newton iteration. We require this because otherwise, rounding errors in
    // `divDownLarge()` may become significant.
    uint256 internal constant _L_VS_LPLUS_MIN = 1.3e18; // 1.3, scaled

    /** @dev The invariant L corresponding to the given balances and alpha. */
    function _calculateInvariant(uint256[] memory balances, uint256 root3Alpha) internal pure returns (uint256 rootEst) {
        if (!(balances[0] <= _MAX_BALANCES)) _grequire(false, Gyro3CLPPoolErrors.BALANCES_TOO_LARGE);
        if (!(balances[1] <= _MAX_BALANCES)) _grequire(false, Gyro3CLPPoolErrors.BALANCES_TOO_LARGE);
        if (!(balances[2] <= _MAX_BALANCES)) _grequire(false, Gyro3CLPPoolErrors.BALANCES_TOO_LARGE);
        (uint256 a, uint256 mb, uint256 mc, uint256 md) = _calculateCubicTerms(balances, root3Alpha);
        return _calculateCubic(a, mb, mc, md, root3Alpha);
    }

    /** @dev Prepares cubic coefficients for input to _calculateCubic().
     *  We will have a > 0, b < 0, c <= 0, and d <= 0 and return a, -b, -c, -d, all >= 0
     *  Terms come from cubic in Section 3.1.1.*/
    function _calculateCubicTerms(uint256[] memory balances, uint256 root3Alpha)
        internal
        pure
        returns (
            uint256 a,
            uint256 mb,
            uint256 mc,
            uint256 md
        )
    {
        // Order of operations is chosen to minimize error amplification. This also duplicates some operations, but
        // minimizing error is more important than saving gas at this point.
        a = GyroFixedPoint.ONE - root3Alpha.mulDownU(root3Alpha).mulDownU(root3Alpha);
        uint256 bterm = balances[0] + balances[1] + balances[2];
        mb = bterm.mulDownU(root3Alpha).mulDownU(root3Alpha);
        uint256 cterm = balances[0].mulDownU(balances[1]) + balances[1].mulDownU(balances[2]) + balances[2].mulDownU(balances[0]);
        mc = cterm.mulDownU(root3Alpha);
        md = balances[0].mulDownU(balances[1]).mulDownU(balances[2]);
    }

    /** @dev Calculate the maximal root of the polynomial a L^3 - mb L^2 - mc L - md.
     *  This root is always non-negative, and it is the unique positive root unless mb == mc == md == 0.
     *  This function and all following ones require that a = 1 - root3Alpha^3 like in _calculateCubicTerms(), i.e.,
     *  this *cannot* be used for *any* cubic equation. We do this because `a` carries an error and to be able to
     *  rearrange operations to reduce error accumulation.*/
    function _calculateCubic(
        uint256 a,
        uint256 mb,
        uint256 mc,
        uint256 md,
        uint256 root3Alpha
    ) internal pure returns (uint256 rootEst) {
        uint256 l_lower;
        (l_lower, rootEst) = _calculateCubicStartingPoint(a, mb, mc, md);
        rootEst = _runNewtonIteration(mb, mc, md, root3Alpha, l_lower, rootEst);

        // Sanity check; the Newton iteration does not check its own final result, only intermediate results.
        if (!(rootEst <= _L_MAX)) _grequire(false, Gyro3CLPPoolErrors.INVARIANT_TOO_LARGE);
    }

    /** @dev (Minimum safe value, starting point for Newton iteration). Calibrated to the particular polynomial for
     * computing the invariant. For values < l_lower, errors from rounding can amplify too much when l is large. This
     * is only relevant for the branch of calcNewtonDelta() where rootEst > _L_THRESHOLD_SIMPLE_NUMERICS.
     */
    function _calculateCubicStartingPoint(
        uint256 a,
        uint256 mb,
        uint256 mc,
        uint256 // md
    ) internal pure returns (uint256 l_lower, uint256 l0) {
        uint256 radic = mb.mulUpU(mb) + a.mulUpU(mc * 3);
        uint256 lplus = (mb + radic._sqrt(5)).divUpU(a * 3); // Upper local minimum
        // This formula has been found computationally. It is exact for alpha -> 1, where the factor is 1.5. All
        // factors > 1 are safe. For small alpha values, it is more efficient to fallback to a larger factor.
        uint256 alpha = GyroFixedPoint.ONE - a; // We know that a is in [0, 1].
        l0 = lplus.mulUpU(alpha >= 0.5e18 ? 1.5e18 : 2e18);
        l_lower = lplus.mulUpU(_L_VS_LPLUS_MIN);
    }

    /** @dev Find a root of the given polynomial with the given starting point l.
     *   Safe iff l > the local minimum.
     *   Note that f(l) may be negative for the first iteration and will then be positive (up to rounding errors).
     *   f'(l) is always positive for the range of values we consider.
     *   See write-up, Appendix A.*/
    function _runNewtonIteration(
        uint256 mb,
        uint256 mc,
        uint256 md,
        uint256 root3Alpha,
        uint256 l_lower,
        uint256 rootEst
    ) internal pure returns (uint256) {
        uint256 deltaAbsPrev = 0;
        for (uint256 iteration = 0; iteration < 255; ++iteration) {
            // The delta to the next step can be positive or negative, and we represent its sign separately.
            (uint256 deltaAbs, bool deltaIsPos) = _calcNewtonDelta(mb, mc, md, root3Alpha, l_lower, rootEst);

            // Note: If we ever set _INVARIANT_MIN_ITERATIONS=0, the following should include `iteration >= 1`.
            if (deltaAbs <= 1) return rootEst;
            if (iteration >= _INVARIANT_MIN_ITERATIONS && deltaIsPos)
                // This should mathematically never happen. Thus, the numerical error dominates at this point.
                return rootEst;
            if (iteration >= _INVARIANT_MIN_ITERATIONS && deltaAbs >= deltaAbsPrev / _INVARIANT_SHRINKING_FACTOR_PER_STEP) {
                // The iteration has stalled and isn't making significant progress anymore.
                return rootEst;
            }
            deltaAbsPrev = deltaAbs;
            // Using checked versions of add/sub just to be extra sure
            if (deltaIsPos) rootEst = rootEst.add(deltaAbs);
            else rootEst = rootEst.sub(deltaAbs);
        }
        _grevert(Gyro3CLPPoolErrors.INVARIANT_DIDNT_CONVERGE);
    }

    /** @dev The Newton step -f(l)/f'(l), represented by its absolute value and its sign.
     * Requires that l is sufficiently large (right of the local minimum) so that f' > 0.*/
    function _calcNewtonDelta(
        uint256 mb,
        uint256 mc,
        uint256 md,
        uint256 root3Alpha,
        uint256 l_lower,
        uint256 rootEst
    ) internal pure returns (uint256 deltaAbs, bool deltaIsPos) {
        if (!(rootEst <= _L_MAX)) _grequire(false, Gyro3CLPPoolErrors.INVARIANT_TOO_LARGE);

        // Note: In principle, this check is only relevant for the `else` branch below. But if it's violated, this
        // points to severe problems anyways, so we keep it here.
        if (!(rootEst >= l_lower)) _grequire(false, Gyro3CLPPoolErrors.INVARIANT_UNDERFLOW);

        uint256 rootEst2 = rootEst.mulDownU(rootEst);

        // The following is equal to dfRootEst^3 * a but with the order of operations optimized for precision.
        // Subtraction does not underflow since rootEst is chosen so that it's always above the (only) local minimum.
        // SOMEDAY alternative with very slightly worse rounding and slightly lower gas:
        // uint256 dfRootEst = 3 * rootEst2;
        uint256 dfRootEst = (rootEst * 3).mulDown(rootEst);
        dfRootEst = dfRootEst - dfRootEst.mulDownU(root3Alpha).mulDownU(root3Alpha).mulDownU(root3Alpha);
        dfRootEst = dfRootEst - 2 * rootEst.mulDownU(mb) - mc;

        // We distinguish two cases: Relatively small values of rootEst, where we can use simple operations, and larger
        // values, where the simple operations may overflow and we need to use functions that compensate for that.
        uint256 deltaMinus;
        uint256 deltaPlus;
        if (rootEst <= _L_THRESHOLD_SIMPLE_NUMERICS) {
            // Calculations are ordered and grouped to minimize rounding error amplification.
            deltaMinus = rootEst2.mulDownU(rootEst);
            deltaMinus = deltaMinus - deltaMinus.mulDownU(root3Alpha).mulDownU(root3Alpha).mulDownU(root3Alpha);
            deltaMinus = deltaMinus.divDownU(dfRootEst);

            // NB: We could pull apart the different values here and reorder them in much the same way we did above to
            // reduce errors. But tests show that this has no significant effect, and it would lead to more complex code
            // and worse gas.
            deltaPlus = rootEst2.mulDownU(mb);
            deltaPlus = (deltaPlus + rootEst.mulDownU(mc)).divDownU(dfRootEst);
            deltaPlus = deltaPlus + md.divDownU(dfRootEst);
        } else {
            // Same operations as above, but we replace some of the operations with their variants that work for larger
            // numbers.
            deltaMinus = rootEst2.mulDownLargeSmallU(rootEst);
            deltaMinus = deltaMinus - deltaMinus.mulDownLargeSmallU(root3Alpha).mulDownLargeSmallU(root3Alpha).mulDownLargeSmallU(root3Alpha);
            // NB: `divDownLarge()` is not exact, but `dfRootEst` is large enough so that the error is on the order of
            // 1e-18. To see why, and why this doesn't overflow, see the Overflow Analysis writeup.
            deltaMinus = deltaMinus.divDownLargeU(dfRootEst);

            // We use mulDownLargeSmall() to prevent an overflow that can occur for large balances and alpha very
            // close to 1.
            deltaPlus = rootEst2.mulDownLargeSmallU(mb);
            // NB: `divDownLarge()` is not exact, but `dfRootEst` is large enough so that the error is on the order of
            // 1e-18. To see why, and why this doesn't overflow, see the Overflow Analysis writeup.
            deltaPlus = deltaPlus + mc.mulDownU(rootEst);
            deltaPlus = deltaPlus.divDownLargeU(dfRootEst, 1e12, 1e6);
            deltaPlus = deltaPlus + md.divDownU(dfRootEst);
        }

        deltaIsPos = (deltaPlus >= deltaMinus);
        deltaAbs = (deltaIsPos ? deltaPlus - deltaMinus : deltaMinus - deltaPlus);
    }

    /** @dev Computes how many tokens can be taken out of a pool if `amountIn` are sent, given the current balances and
     * price bounds.
     * See Proposition 13 in 3.1.4. In contrast to the proposition, we use two separate functions for trading given the
     * out-amount and the in-amount, respectively.
     * The virtualOffset argument depends on the computed invariant. While the calculation is very precise, small errors
     * can occur. We add a very small margin to ensure that such errors are not to the detriment of the pool. */
    function _calcOutGivenIn(
        uint256 balanceIn,
        uint256 balanceOut,
        uint256 amountIn,
        uint256 virtualOffset
    ) internal pure returns (uint256 amountOut) {
        /**********************************************************************************************
        // Described for X = `in' asset and Z = `out' asset, but equivalent for the other case       //
        // dX = incrX  = amountIn  > 0                                                               //
        // dZ = incrZ = amountOut < 0                                                                //
        // x = balanceIn             x' = x +  virtualOffset                                         //
        // z = balanceOut            z' = z +  virtualOffset                                         //
        // L  = inv.Liq                   /            x' * z'          \          z' * dX           //
        //                   |dZ| = z' - |   --------------------------  |   = ---------------       //
        //  x' = virtIn                   \          ( x' + dX)         /          x' + dX           //
        //  z' = virtOut                                                                             //
        // Note that -dz > 0 is what the trader receives.                                            //
        // We exploit the fact that this formula is symmetric and does not depend on which asset is  //
        // which.
        // We assume that the virtualOffset carries a relative +/- 3e-18 error due to the invariant  //
        // calculation add an appropriate safety margin.                                             //
        **********************************************************************************************/

        {
            // The factors in total lead to a multiplicative "safety margin" between the employed virtual offsets
            // very slightly larger than 3e-18, compensating for the maximum multiplicative error in the invariant
            // computation.
            // SOMEDAY These factors could further be adjusted to compensate for potential errors in the invariant when
            // the balances are very large. (likely not needed)
            uint256 virtInOver = balanceIn + virtualOffset.mulUpU(GyroFixedPoint.ONE + 2);
            uint256 virtOutUnder = balanceOut + virtualOffset.mulDownU(GyroFixedPoint.ONE - 1);

            // Note that the user can define amountIn so we have to check for overflows
            amountOut = virtOutUnder.mulDown(amountIn).divDown(virtInOver.add(amountIn));
        }

        // We need to ensure amountOut <= balanceOut manually
        if (!(amountOut <= balanceOut)) _grequire(false, Gyro3CLPPoolErrors.ASSET_BOUNDS_EXCEEDED);
    }

    /** @dev Computes how many tokens must be sent to a pool in order to take `amountOut`, given the current balances
     * and price bounds. See documentation for _calcOutGivenIn(), too. */
    function _calcInGivenOut(
        uint256 balanceIn,
        uint256 balanceOut,
        uint256 amountOut,
        uint256 virtualOffset
    ) internal pure returns (uint256 amountIn) {
        /**********************************************************************************************
        // Described for X = `in' asset and Z = `out' asset, but equivalent for the other case       //
        // dX = incrX  = amountIn  > 0                                                               //
        // dZ = incrZ = amountOut < 0                                                                //
        // x = balanceIn             x' = x +  virtualOffset                                         //
        // z = balanceOut            z' = z +  virtualOffset                                         //
        // L  = inv.Liq            /            x' * z'          \             x' * dZ               //
        //                   dX = |   --------------------------  | - x' = ---------------           //
        //  x' = virtIn            \          ( z' + dZ)         /             z' - dZ               //
        //  z' = virtOut                                                                             //
        // Note that dz < 0 < dx.                                                                    //
        // We exploit the fact that this formula is symmetric and does not depend on which asset is  //
        // which.
        // We assume that the virtualOffset carries a relative +/- 3e-18 error due to the invariant  //
        // calculation add an appropriate safety margin.                                             //
        **********************************************************************************************/

        // We need to ensure manually that amountOut <= balanceOut.
        if (!(amountOut <= balanceOut)) _grequire(false, Gyro3CLPPoolErrors.ASSET_BOUNDS_EXCEEDED);

        {
            // The factors in total lead to a multiplicative "safety margin" between the employed virtual offsets
            // very slightly larger than 3e-18, compensating for the maximum multiplicative error in the invariant
            // computation.
            // SOMEDAY These factors could further be adjusted to compensate for potential errors in the invariant when
            // the balances are very large. (likely not needed)
            uint256 virtInOver = balanceIn + virtualOffset.mulUpU(GyroFixedPoint.ONE + 2);
            uint256 virtOutUnder = balanceOut + virtualOffset.mulDownU(GyroFixedPoint.ONE - 1);

            // Note that the user can define amountOut so we have to check for overflows
            amountIn = virtInOver.mulUp(amountOut).divUp(virtOutUnder.sub(amountOut));
        }
    }

    /** @dev Computes relative spot prices of token0 and token1, respectively, in units of token2. */
    function _calcSpotPrice01in2(uint256[] memory balances, uint256 virtualOffset) internal pure returns (uint256 spotPrice0, uint256 spotPrice1) {
        uint256 virt2 = balances[2] + virtualOffset;
        spotPrice0 = virt2.divUp(balances[0].add(virtualOffset));
        spotPrice1 = virt2.divUp(balances[1].add(virtualOffset));
    }
}

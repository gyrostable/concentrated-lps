// SPDX-License-Identifier: LicenseRef-Gyro-1.0
// for information on licensing please see the README in the GitHub repository <https://github.com/gyrostable/core-protocol>.

pragma solidity ^0.7.0;

import "@balancer-labs/v2-solidity-utils/contracts/math/FixedPoint.sol";
import "@balancer-labs/v2-solidity-utils/contracts/math/Math.sol";
import "@balancer-labs/v2-solidity-utils/contracts/helpers/InputHelpers.sol";

import "./GyroThreePoolErrors.sol";

// These functions start with an underscore, as if they were part of a contract and not a library. At some point this
// should be fixed.
// solhint-disable private-vars-leading-underscore

library GyroThreeMath {
    using FixedPoint for uint256;

    // Swap limits: amounts swapped may not be larger than this percentage of total balance.
    // _MAX_OUT_RATIO also ensures that we never compute swaps that take more out than is in the pool. (because
    // it's <= ONE)
    uint256 internal constant _MAX_IN_RATIO = 0.3e18;
    uint256 internal constant _MAX_OUT_RATIO = 0.3e18;

    // Stopping criterion for the Newton iteration that computes the invariant:
    // - Stop if the step width doesn't shrink anymore by at least a factor _INVARIANT_SHRINKING_FACTOR_PER_STEP.
    // - ... but in any case, make at least _INVARIANT_MIN_ITERATIONS iterations. This is useful to compensate for a
    // less-than-ideal starting point, which is important when alpha is small.
    uint8 internal constant _INVARIANT_SHRINKING_FACTOR_PER_STEP = 10;
    uint8 internal constant _INVARIANT_MIN_ITERATIONS = 2;

    // Invariant is used to collect protocol swap fees by comparing its value between two times.
    // So we can round always to the same direction. It is also used to initiate the BPT amount
    // and, because there is a minimum BPT, we round down the invariant.
    // Argument root3Alpha = cube root of the lower price bound (symmetric across assets)
    // Note: all price bounds for the pool are alpha and 1/alpha
    function _calculateInvariant(uint256[] memory balances, uint256 root3Alpha)
        internal
        pure
        returns (uint256)
    {
        /**********************************************************************************************
        // Calculate root of cubic:
        // (1-alpha)L^3 - (x+y+z) * alpha^(2/3) * L^2 - (x*y + y*z + x*z) * alpha^(1/3) * L - x*y*z = 0
        // These coefficients are a,b,c,d respectively
        // here, a > 0, b < 0, c < 0, and d < 0
        // taking mb = -b and mc = -c
        /**********************************************************************************************/
        (uint256 a, uint256 mb, uint256 mc, uint256 md) = _calculateCubicTerms(
            balances,
            root3Alpha
        );
        return _calculateCubic(a, mb, mc, md);
    }

    /** @dev Prepares quadratic terms for input to _calculateCubic
     *  assumes a > 0, b < 0, c <= 0, and d <= 0 and returns a, -b, -c, -d
     *  terms come from cubic in Section 3.1.1
     *  argument root3Alpha = cube root of alpha
     */
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
        uint256 alpha23 = root3Alpha.mulDown(root3Alpha); // alpha to the power of (2/3)
        uint256 alpha = alpha23.mulDown(root3Alpha);
        a = FixedPoint.ONE.sub(alpha);
        uint256 bterm = balances[0].add(balances[1]).add(balances[2]);
        mb = bterm.mulDown(alpha23);
        uint256 cterm = (balances[0].mulDown(balances[1]))
            .add(balances[1].mulDown(balances[2]))
            .add(balances[2].mulDown(balances[0]));
        mc = cterm.mulDown(root3Alpha);
        md = balances[0].mulDown(balances[1]).mulDown(balances[2]);
    }

    /** @dev Calculate the maximal root of the polynomial a L^3 - mb L^2 - mc L - md.
     *   This root is always non-negative, and it is the unique positive root unless mb == mc == md == 0. */
    function _calculateCubic(
        uint256 a,
        uint256 mb,
        uint256 mc,
        uint256 md
    ) internal pure returns (uint256 rootEst) {
        if (md == 0) {
            // lower-order special case
            uint256 radic = mb.mulDown(mb).add(4 * a.mulDown(mc));
            rootEst = mb.add(radic.powDown(FixedPoint.ONE / 2)).divDown(2 * a);
        } else {
            rootEst = _calculateCubicStartingPoint(a, mb, mc, md);
            rootEst = _runNewtonIteration(a, mb, mc, md, rootEst);
        }
    }

    /** @dev Starting point for Newton iteration. Safe with all cubic polynomials where the coefficients have the appropriate
     *   signs, but calibrated to the particular polynomial for computing the invariant. */
    function _calculateCubicStartingPoint(
        uint256 a,
        uint256 mb,
        uint256 mc,
        uint256 // md
    ) internal pure returns (uint256 l0) {
        uint256 radic = mb.mulUp(mb).add(a.mulUp(mc).mulUp(3 * FixedPoint.ONE));
        uint256 lmin = mb.divUp(a * 3) + radic.powUp(FixedPoint.ONE / 2).divUp(a * 3);
        // The factor 3/2 is a magic number found experimentally for our invariant. All factors > 1 are safe.
        l0 = lmin.mulUp((3 * FixedPoint.ONE) / 2);
    }

    /** @dev Find a root of the given polynomial with the given starting point l.
     *   Safe iff l > the local minimum.
     *   Note that f(l) may be negative for the first iteration and will then be positive (up to rounding errors).
     *   f'(l) is always positive for the range of values we consider.
     *   See write-up, Appendix A. */
    function _runNewtonIteration(
        uint256 a,
        uint256 mb,
        uint256 mc,
        uint256 md,
        uint256 rootEst
    ) internal pure returns (uint256) {
        uint256 deltaAbsPrev = 0;
        for (uint256 iteration = 0; iteration < 255; ++iteration) {
            // The delta to the next step can be positive or negative, so we represent a positive and a negative part
            // separately. The signed delta is delta_plus - delta_minus, but we only ever consider its absolute value.
            (uint256 deltaAbs, bool deltaIsPos) = _calcNewtonDelta(a, mb, mc, md, rootEst);
            // ^ Note: If we ever set _INVARIANT_MIN_ITERATIONS=0, the following should include `iteration >= 1`.
            if (deltaAbs == 0 || (iteration >= _INVARIANT_MIN_ITERATIONS && deltaIsPos))
                // Iteration literally stopped or numerical error dominates
                return rootEst;
            if (
                iteration >= _INVARIANT_MIN_ITERATIONS &&
                deltaAbs >= deltaAbsPrev / _INVARIANT_SHRINKING_FACTOR_PER_STEP
            ) {
                // stalled
                // Move one more step to the left to ensure we're underestimating, rather than overestimating, L
                return rootEst - deltaAbs;
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
        uint256 rootEst
    ) internal pure returns (uint256 deltaAbs, bool deltaIsPos) {
        uint256 dfRootEst = (3 * a).mulUp(rootEst).sub(2 * mb).mulUp(rootEst).sub(mc); // Does not underflow since rootEst >> 0 by assumption.
        // We know that a rootEst^2 / dfRootEst ~ 1. (this is pretty exact actually, see the Mathematica notebook). We use this
        // multiplication order to prevent overflows that can otherwise occur when computing l^3 for very large
        // reserves.
        uint256 deltaMinus = a.mulUp(rootEst).mulUp(rootEst);
        deltaMinus = deltaMinus.divUp(dfRootEst).mulUp(rootEst);
        // use multiple statements to prevent 'stack too deep'. The order of operations is chosen to prevent overflows
        // for very large numbers.
        uint256 deltaPlus = mb.mulUp(rootEst).add(mc).divUp(dfRootEst);
        deltaPlus = deltaPlus.mulUp(rootEst).add(md.divUp(dfRootEst));

        deltaIsPos = (deltaPlus >= deltaMinus);
        deltaAbs = (deltaIsPos ? deltaPlus - deltaMinus : deltaMinus - deltaPlus);
    }

    /** @dev New invariant assuming that the balances increase from 'lastBalances', where the invariant was
     * 'lastInvariant', to some new value, where the 'z' component (asset index 2) changes by 'deltaZ' and the other
     * assets change, too, in such a way that the prices stay the same. 'isIncreaseLiq' captures the sign of the change
     * (true meaning positive).
     * We apply Proposition 10 from the writeup. */
    function _liquidityInvariantUpdate(
        uint256[] memory lastBalances,
        uint256 root3Alpha,
        uint256 lastInvariant,
        uint256[] memory deltaBalances,
        bool isIncreaseLiq
    ) internal pure returns (uint256 invariant) {
        /**********************************************************************************************
        // From Prop. 10 in Section 3.1.3 Liquidity Update                                           //
        // Assumed that the  liquidity provided is correctly balanced                                //
        // dL = change in L invariant, absolute value (sign information in isIncreaseLiq)            //
        // dZ = change in Z reserves, absolute value (sign information in isIncreaseLiq)             //
        // cbrtPxPy = Square root of (Price p_x * Price p_y)     cbrtPxPy =  z' / L                  //
        // x' = virtual reserves X (real reserves + offsets)                                         //
        //           /            dZ            \                                                    //
        //    dL =  | -------------------------- |                                                   //
        //           \ ( cbrtPxPy - root3Alpha) /                                                    //
        // Note: this calculation holds for reordering of assets {X,Y,Z}                             //
        // To ensure denominator is well-defined, we reorder to work with assets of largest balance  //
        **********************************************************************************************/

        // this reorders indices so that we know which has max balance
        // this is needed to ensure that cbrtPxPy - root3Alpha is not close to zero in denominator
        // we will want to use the largest two assets to represent x and y, smallest to represent z
        uint8[] memory indices = maxOtherBalances(lastBalances);

        // all offsets are L * root3Alpha b/c symmetric, see 3.1.4
        uint256 virtualOffset = lastInvariant.mulDown(root3Alpha);
        uint256 virtZ = lastBalances[indices[0]].add(virtualOffset);
        uint256 cbrtPrice = _calculateCbrtPrice(lastInvariant, virtZ);
        uint256 denominator = cbrtPrice.sub(root3Alpha);
        uint256 diffInvariant = deltaBalances[indices[0]].divDown(denominator);
        invariant = isIncreaseLiq
            ? lastInvariant.add(diffInvariant)
            : lastInvariant.sub(diffInvariant);
    }

    // Ensures balances[i] >= balances[j], balances[k] and i, j, k are pairwise distinct. Like sorting minus one
    // comparison. In particular, the 0th entry will be the maximum
    function maxOtherBalances(uint256[] memory balances)
        internal
        pure
        returns (uint8[] memory indices)
    {
        indices = new uint8[](3);
        if (balances[0] >= balances[1]) {
            if (balances[0] >= balances[2]) {
                indices[0] = 0;
                indices[1] = 1;
                indices[2] = 2;
            } else {
                indices[0] = 2;
                indices[1] = 0;
                indices[2] = 1;
            }
        } else {
            if (balances[1] >= balances[2]) {
                indices[0] = 1;
                indices[1] = 0;
                indices[2] = 2;
            } else {
                indices[0] = 2;
                indices[1] = 1;
                indices[2] = 0;
            }
        }
    }

    /** @dev Computes how many tokens can be taken out of a pool if `amountIn` are sent, given the
     * current balances and weights.
     * Changed signs compared to original algorithm to account for amountOut < 0.
     * See Proposition 12 in 3.1.4.*/
    function _calcOutGivenIn(
        uint256 balanceIn,
        uint256 balanceOut,
        uint256 amountIn,
        uint256 virtualOffsetInOut
    ) internal pure returns (uint256 amountOut) {
        /**********************************************************************************************
        // Described for X = `in' asset and Z = `out' asset, but equivalent for the other case       //
        // dX = incrX  = amountIn  > 0                                                               //
        // dZ = incrZ = amountOut < 0                                                                //
        // x = balanceIn             x' = x +  virtualOffset                                         //
        // z = balanceOut            z' = z +  virtualOffset                                         //
        // L  = inv.Liq                   /            x' * z'          \                            //
        //                   - dZ = z' - |   --------------------------  |                           //
        //  x' = virtIn                   \          ( x' + dX)         /                            //
        //  z' = virtOut                                                                             //
        // Note that -dz > 0 is what the trader receives.                                            //
        // We exploit the fact that this formula is symmetric up to virtualParam{X,Y,Z}.             //
        **********************************************************************************************/
        _require(amountIn <= balanceIn.mulDown(_MAX_IN_RATIO), Errors.MAX_IN_RATIO);

        uint256 virtIn = balanceIn.add(virtualOffsetInOut);
        uint256 virtOut = balanceOut.add(virtualOffsetInOut);
        uint256 denominator = virtIn.add(amountIn);
        uint256 subtrahend = virtIn.mulDown(virtOut).divDown(denominator);
        amountOut = virtOut.sub(subtrahend);

        // Note that this in particular reverts if amountOut > balanceOut, i.e., if the out-amount would be more than
        // the balance.
        _require(amountOut <= balanceOut.mulDown(_MAX_OUT_RATIO), Errors.MAX_OUT_RATIO);
    }

    /** @dev Computes how many tokens must be sent to a pool in order to take `amountOut`, given the
     * currhent balances and weights.
     * Similar to the one before but adapting bc negative values (amountOut would be negative).*/
    function _calcInGivenOut(
        uint256 balanceIn,
        uint256 balanceOut,
        uint256 amountOut,
        uint256 virtualOffsetInOut
    ) internal pure returns (uint256 amountIn) {
        /**********************************************************************************************
        // Described for X = `in' asset and Z = `out' asset, but equivalent for the other case       //
        // dX = incrX  = amountIn  > 0                                                               //
        // dZ = incrZ = amountOut < 0                                                                //
        // x = balanceIn             x' = x +  virtualOffset                                         //
        // z = balanceOut            z' = z +  virtualOffset                                         //
        // L  = inv.Liq            /            x' * z'          \                                   //
        //                   dX = |   --------------------------  | - x'                             //
        //  x' = virtIn            \          ( z' + dZ)         /                                   //
        //  z' = virtOut                                                                             //
        // Note that dz < 0 < dx.                                                                    //
        // We exploit the fact that this formula is symmetric up to virtualParam{X,Y,Z}.             //
        **********************************************************************************************/

        // Note that this in particular reverts if amountOut > balanceOut, i.e., if the trader tries to take more out of
        // the pool than is in it.
        _require(amountOut <= balanceOut.mulDown(_MAX_OUT_RATIO), Errors.MAX_OUT_RATIO);

        uint256 virtIn = balanceIn.add(virtualOffsetInOut);
        uint256 virtOut = balanceOut.add(virtualOffsetInOut);
        uint256 denominator = virtOut.sub(amountOut);
        uint256 minuend = virtIn.mulDown(virtOut).divDown(denominator);
        amountIn = minuend.sub(virtIn);

        _require(amountIn <= balanceIn.mulDown(_MAX_IN_RATIO), Errors.MAX_IN_RATIO);
    }

    /** @dev Cube root of the product of the prices of x and y (priced in z). Helper value.
     *   See pf to Prop 8 in 3.1.2, similarly see Lemma 6 in 3.3 */
    function _calculateCbrtPrice(uint256 invariant, uint256 virtualZ)
        internal
        pure
        returns (uint256)
    {
        /*********************************************************************************
         *  cbrtPrice =  z' / L
         ********************************************************************************/
        return virtualZ.divDown(invariant);
    }
}

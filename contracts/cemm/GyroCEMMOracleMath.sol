// SPDX-License-Identifier: LicenseRef-Gyro-1.0
// for information on licensing please see the README in the GitHub repository <https://github.com/gyrostable/concentrated-lps>.

pragma solidity ^0.7.0;

import "@balancer-labs/v2-solidity-utils/contracts/math/FixedPoint.sol";
import "@balancer-labs/v2-solidity-utils/contracts/helpers/LogCompression.sol";

contract GyroCEMMOracleMath {
    using FixedPoint for uint256;

    /**
     * @dev Calculates the logarithm of the spot price of token B in token A.
     *
     * The return value is a 4 decimal fixed-point number: use `LogCompression.fromLowResLog`
     * to recover the original value.
     *
     * The spot price is bounded by pool parameters due to virtual reserves. Aside from being instantaneously manipulable
     * within a block, it may also not be accurate if the true price is outside of these bounds.
     */
    function _calcLogSpotPrice(uint256 spotPrice) internal pure returns (int256) {
        return LogCompression.toLowResLog(spotPrice);
    }

    /**
     * @dev Calculates the (spot) price of BPT in token A. `logBptTotalSupply` should be the result of calling `toLowResLog`
     * with the current BPT supply.
     *
     * This uses the pool's spot price and so is also manipulable within a block and may not be accurate if the true price
     * is outside of the pool's price bounds.
     *
     * The return value is a 4 decimal fixed-point number: use `LogCompression.fromLowResLog`
     * to recover the original value.
     */
    function _calcLogBPTPrice(
        uint256 balanceA,
        uint256 balanceB,
        uint256 spotPriceA,
        int256 logBptTotalSupply
    ) internal pure returns (int256) {
        // BPT price = (balance of token A + balance of token B * spot price of token B in units of A) / total supply
        // Since we already have ln(total supply) and want to compute ln(BPT price), we perform the computation in log
        // space directly: ln(BPT price) = ln(portfolio value) - ln(total supply)

        // The rounding direction is irrelevant as we're about to introduce a much larger error when converting to log
        // space. We use `mulUp` as it prevents the result from being zero, which would make the logarithm revert. A
        // result of zero is therefore only possible with zero balances, which are prevented via other means.
        uint256 portfolioValue = balanceA.mulUp(spotPriceA).add(balanceB);
        int256 logPortfolioValue = LogCompression.toLowResLog(portfolioValue);

        // Because we're subtracting two values in log space, this value has a larger error (+-0.0001 instead of
        // +-0.00005), which results in a final larger relative error of around 0.1%.
        return logPortfolioValue - logBptTotalSupply;
    }

    /** @dev Calculates normalized invariant = invariant / BPT total supply
     *  Manipulation resistant BPT share pricing takes the form BPT price = (L/S) * f(p_x, p_y, alpha, beta)
     *  A time-weighted average of L/S enables BPT pricing that is resistant to donation attacks, in which L/S is manipulated */
    function _calcLogInvariantDivSupply(uint256 invariant, int256 logBptTotalSupply) internal pure returns (int256) {
        // Since we already have ln(S) and want to compute ln(L/S), we perform the computation in log
        // space directly: ln(L/S) = ln(L) - ln(S)
        int256 logInvariant = LogCompression.toLowResLog(invariant);

        // Because we're subtracting two values in log space, this value has a larger error (+-0.0001 instead of
        // +-0.00005), which results in a final larger relative error of around 0.1%.
        return logInvariant - logBptTotalSupply;
    }
}

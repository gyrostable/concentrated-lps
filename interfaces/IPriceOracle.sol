// SPDX-License-Identifier: LicenseRef-Gyro-1.0
// for information on licensing please see the README in the GitHub repository <https://github.com/gyrostable/concentrated-lps>.

pragma solidity 0.7.6;
pragma experimental ABIEncoderV2;

/**
 * @dev Interface for querying historical data from a Pool that can be used as a Price Oracle.
 *
 * This lets third parties retrieve average prices of tokens held by a Pool over a given period of time, as well as the
 * price of the Pool share token (BPT) and invariant. Since the invariant is a sensible measure of Pool liquidity, it
 * can be used to compare two different price sources, and choose the most liquid one.
 *
 * Once the oracle is fully initialized, all queries are guaranteed to succeed as long as they require no data that
 * is not older than the largest safe query window.
 */
interface IPriceOracle {
    // The three values that can be queried:
    //
    // - PAIR_PRICE: the price of the tokens in the Pool, expressed as the price of the second token in units of the
    //   first token. For example, if token A is worth $2, and token B is worth $4, the pair price will be 2.0.
    //   Note that the price is computed *including* the tokens decimals. This means that the pair price of a Pool with
    //   DAI and USDC will be close to 1.0, despite DAI having 18 decimals and USDC 6.
    //
    // - BPT_PRICE: the price of the Pool share token (BPT), in units of the first token.
    //   Note that the price is computed *including* the tokens decimals. This means that the BPT price of a Pool with
    //   USDC in which BPT is worth $5 will be 5.0, despite the BPT having 18 decimals and USDC 6.
    //
    // - INVARIANT: the value of the Pool's invariant, which serves as a measure of its liquidity.
    enum Variable {
        PAIR_PRICE,
        BPT_PRICE,
        INVARIANT
    }

    /**
     * @dev Returns the time average weighted price corresponding to each of `queries`. Prices are represented as 18
     * decimal fixed point values.
     */
    function getTimeWeightedAverage(OracleAverageQuery[] memory queries) external view returns (uint256[] memory results);

    /**
     * @dev Returns latest sample of `variable`. Prices are represented as 18 decimal fixed point values.
     */
    function getLatest(Variable variable) external view returns (uint256);

    /**
     * @dev Information for a Time Weighted Average query.
     *
     * Each query computes the average over a window of duration `secs` seconds that ended `ago` seconds ago. For
     * example, the average over the past 30 minutes is computed by settings secs to 1800 and ago to 0. If secs is 1800
     * and ago is 1800 as well, the average between 60 and 30 minutes ago is computed instead.
     */
    struct OracleAverageQuery {
        Variable variable;
        uint256 secs;
        uint256 ago;
    }

    /**
     * @dev Returns largest time window that can be safely queried, where 'safely' means the Oracle is guaranteed to be
     * able to produce a result and not revert.
     *
     * If a query has a non-zero `ago` value, then `secs + ago` (the oldest point in time) must be smaller than this
     * value for 'safe' queries.
     */
    function getLargestSafeQueryWindow() external view returns (uint256);

    /**
     * @dev Returns the accumulators corresponding to each of `queries`.
     */
    function getPastAccumulators(OracleAccumulatorQuery[] memory queries) external view returns (int256[] memory results);

    /**
     * @dev Information for an Accumulator query.
     *
     * Each query estimates the accumulator at a time `ago` seconds ago.
     */
    struct OracleAccumulatorQuery {
        Variable variable;
        uint256 ago;
    }
}

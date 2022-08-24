// SPDX-License-Identifier: LicenseRef-Gyro-1.0
// for information on licensing please see the README in the GitHub repository <https://github.com/gyrostable/core-protocol>.

pragma solidity 0.7.6;
pragma experimental ABIEncoderV2;

import "@balancer-labs/v2-solidity-utils/contracts/helpers/BalancerErrors.sol";

import "@balancer-labs/v2-pool-utils/contracts/interfaces/IPriceOracle.sol";
import "@balancer-labs/v2-pool-utils/contracts/interfaces/IPoolPriceOracle.sol";

import "@balancer-labs/v2-pool-utils/contracts/oracle/Buffer.sol";
import "@balancer-labs/v2-pool-utils/contracts/oracle/Samples.sol";
//import "./QueryProcessorMock.sol";

import "@balancer-labs/v2-solidity-utils/contracts/helpers/LogCompression.sol";

/**
 * @dev This module allows Pools to access historical pricing information.
 *
 * It uses a 1024 long circular buffer to store past data, where the data within each sample is the result of
 * accumulating live data for no more than two minutes. Therefore, assuming the worst case scenario where new data is
 * updated in every single block, the oldest samples in the buffer (and therefore largest queryable period) will
 * be slightly over 34 hours old.
 *
 * Usage of this module requires the caller to keep track of two variables: the latest circular buffer index, and the
 * timestamp when the index last changed. Aditionally, access to the latest circular buffer index must be exposed by
 * implementing `_getOracleIndex`.
 *
 * This contract relies on the `QueryProcessor` linked library to reduce bytecode size.
 */
abstract contract PoolPriceOracleMock is IPoolPriceOracle, IPriceOracle {
    using Buffer for uint256;
    using Samples for bytes32;
    using LogCompression for int256;

    // Each sample in the buffer accumulates information for up to 2 minutes. This is simply to reduce the size of the
    // buffer: small time deviations will not have any significant effect.
    // solhint-disable not-rely-on-time
    uint256 private constant _MAX_SAMPLE_DURATION = 2 minutes;

    // We use a mapping to simulate an array: the buffer won't grow or shrink, and since we will always use valid
    // indexes using a mapping saves gas by skipping the bounds checks.
    mapping(uint256 => bytes32) internal _samples;

    // IPoolPriceOracle

    // IPoolPriceOracle

    function getSample(uint256 index)
        external
        view
        override
        returns (
            int256 logPairPrice,
            int256 accLogPairPrice,
            int256 logBptPrice,
            int256 accLogBptPrice,
            int256 logInvariant,
            int256 accLogInvariant,
            uint256 timestamp
        )
    {
        _require(index < Buffer.SIZE, Errors.ORACLE_INVALID_INDEX);

        bytes32 sample = _getSample(index);
        return sample.unpack();
    }

    function getTotalSamples() external pure override returns (uint256) {
        return Buffer.SIZE;
    }

    /**
     * @dev Manually dirty oracle sample storage slots with dummy data, to reduce the gas cost of the future swaps
     * that will initialize them. This function is only useful before the oracle has been fully initialized.
     *
     * `endIndex` is non-inclusive.
     */
    function dirtyUninitializedOracleSamples(uint256 startIndex, uint256 endIndex) external {
        _require(startIndex < endIndex && endIndex <= Buffer.SIZE, Errors.OUT_OF_BOUNDS);

        // Uninitialized samples are identified by a zero timestamp -- all other fields are ignored,
        // so any non-zero value with a zero timestamp suffices.
        bytes32 initSample = Samples.pack(1, 0, 0, 0, 0, 0, 0);
        for (uint256 i = startIndex; i < endIndex; i++) {
            if (_samples[i].timestamp() == 0) {
                _samples[i] = initSample;
            }
        }
    }

    // IPriceOracle

    function getLargestSafeQueryWindow() external pure override returns (uint256) {
        return 34 hours;
    }

    function getLatest(Variable variable) external view override returns (uint256) {
        return getInstantValue(variable, _getOracleIndex());
    }

    function getTimeWeightedAverage(OracleAverageQuery[] memory queries) external view override returns (uint256[] memory results) {
        results = new uint256[](queries.length);
        uint256 latestIndex = _getOracleIndex();

        for (uint256 i = 0; i < queries.length; ++i) {
            results[i] = queryGetTimeWeightedAverage(_samples, queries[i], latestIndex);
        }
    }

    function getPastAccumulators(OracleAccumulatorQuery[] memory queries) external view override returns (int256[] memory results) {
        results = new int256[](queries.length);
        uint256 latestIndex = _getOracleIndex();

        OracleAccumulatorQuery memory query;
        for (uint256 i = 0; i < queries.length; ++i) {
            query = queries[i];
            results[i] = _getPastAccumulator(query.variable, latestIndex, query.ago);
        }
    }

    // Internal functions

    /**
     * @dev Processes new price and invariant data, updating the latest sample or creating a new one.
     *
     * Receives the new logarithms of values to store: `logPairPrice`, `logBptPrice` and `logInvariant`, as well the
     * index of the latest sample and the timestamp of its creation.
     *
     * Returns the index of the latest sample. If different from `latestIndex`, the caller should also store the
     * timestamp, and pass it on future calls to this function.
     */
    function _processPriceData(
        uint256 latestSampleCreationTimestamp,
        uint256 latestIndex,
        int256 logPairPrice,
        int256 logBptPrice,
        int256 logInvariant
    ) internal returns (uint256) {
        // Read latest sample, and compute the next one by updating it with the newly received data.
        bytes32 sample = _getSample(latestIndex).update(logPairPrice, logBptPrice, logInvariant, block.timestamp);

        // We create a new sample if more than _MAX_SAMPLE_DURATION seconds have elapsed since the creation of the
        // latest one. In other words, no sample accumulates data over a period larger than _MAX_SAMPLE_DURATION.
        bool newSample = block.timestamp - latestSampleCreationTimestamp >= _MAX_SAMPLE_DURATION;
        latestIndex = newSample ? latestIndex.next() : latestIndex;

        // Store the updated or new sample.
        _samples[latestIndex] = sample;

        return latestIndex;
    }

    function _getPastAccumulator(
        IPriceOracle.Variable variable,
        uint256 latestIndex,
        uint256 ago
    ) internal pure returns (int256) {
        return getPastAccumulator(variable, latestIndex, ago);
    }

    function _findNearestSample(
        uint256 lookUpDate,
        uint256 offset,
        uint256 length
    ) internal pure returns (bytes32 prev, bytes32 next) {
        return findNearestSample(lookUpDate, offset, length);
    }

    /**
     * @dev Returns the sample that corresponds to a given `index`.
     *
     * Using this function instead of accessing storage directly results in denser bytecode (since the storage slot is
     * only computed here).
     */
    function _getSample(uint256 index) internal view returns (bytes32) {
        return _samples[index];
    }

    /**
     * @dev Virtual function to be implemented by derived contracts. Must return the current index of the oracle
     * circular buffer.
     */
    function _getOracleIndex() internal view virtual returns (uint256);

    function getInstantValue(IPriceOracle.Variable, uint256) internal pure returns (uint256) {
        // MODIFIED TO FIX TESTING ERROR
        return 1;
    }

    /**
     * @dev Returns the time average weighted price corresponding to `query`.
     */
    function queryGetTimeWeightedAverage(
        mapping(uint256 => bytes32) storage,
        IPriceOracle.OracleAverageQuery memory query,
        uint256 latestIndex
    ) internal pure returns (uint256) {
        _require(query.secs != 0, Errors.ORACLE_BAD_SECS);

        int256 beginAccumulator = getPastAccumulator(query.variable, latestIndex, query.ago + query.secs);
        int256 endAccumulator = getPastAccumulator(query.variable, latestIndex, query.ago);
        return LogCompression.fromLowResLog((endAccumulator - beginAccumulator) / int256(query.secs));
    }

    /**
     * @dev Returns the value of the accumulator for `variable` `ago` seconds ago. `latestIndex` must be the index of
     * the latest sample in the buffer.
     *
     * Reverts under the following conditions:
     *  - if the buffer is empty.
     *  - if querying past information and the buffer has not been fully initialized.
     *  - if querying older information than available in the buffer. Note that a full buffer guarantees queries for the
     *    past 34 hours will not revert.
     *
     * If requesting information for a timestamp later than the latest one, it is extrapolated using the latest
     * available data.
     *
     * When no exact information is available for the requested past timestamp (as usually happens, since at most one
     * timestamp is stored every two minutes), it is estimated by performing linear interpolation using the closest
     * values. This process is guaranteed to complete performing at most 10 storage reads.
     */
    function getPastAccumulator(
        IPriceOracle.Variable,
        uint256,
        uint256
    ) public pure returns (int256) {
        return 0;
    }

    /**
     * @dev Finds the two samples with timestamps before and after `lookUpDate`. If one of the samples matches exactly,
     * both `prev` and `next` will be it. `offset` is the index of the oldest sample in the buffer. `length` is the size
     * of the samples list.
     *
     * Assumes `lookUpDate` is greater or equal than the timestamp of the oldest sample, and less or equal than the
     * timestamp of the latest sample.
     */
    function findNearestSample(
        uint256,
        uint256,
        uint256
    ) public pure returns (bytes32 prev, bytes32 next) {
        return (bytes32(0), bytes32(0));
    }
}

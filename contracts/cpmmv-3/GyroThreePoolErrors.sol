// SPDX-License-Identifier: LicenseRef-Gyro-1.0
// for information on licensing please see the README in the GitHub repository <https://github.com/gyrostable/core-protocol>.

pragma solidity ^0.7.0;

// solhint-disable

library GyroThreePoolErrors {
    // NOTE: we offset by 1000 to avoid clashing with Balancer errors
    // Math
    uint256 internal constant PRICE_BOUNDS_WRONG = 351;
    uint256 internal constant INVARIANT_DIDNT_CONVERGE = 352;
    uint256 internal constant ASSET_BOUNDS_EXCEEDED = 357; //NB this is the same as the CEMM
    uint256 internal constant UNDERESTIMATE_INVARIANT_FAILED = 360;

    // Input
    uint256 internal constant TOKENS_LENGTH_MUST_BE_3 = 353;
}

pragma solidity 0.7.6;

// solhint-disable

library Gyro3CLPPoolErrors {
    // Math
    uint256 internal constant PRICE_BOUNDS_WRONG = 351;
    uint256 internal constant INVARIANT_DIDNT_CONVERGE = 352;
    uint256 internal constant ASSET_BOUNDS_EXCEEDED = 357; //NB this is the same as the E-CLP and 2-CLP
    uint256 internal constant UNDERESTIMATE_INVARIANT_FAILED = 360;
    uint256 internal constant INVARIANT_TOO_LARGE = 361;
    uint256 internal constant BALANCES_TOO_LARGE = 362;
    uint256 internal constant INVARIANT_UNDERFLOW = 363;

    // Input
    uint256 internal constant TOKENS_LENGTH_MUST_BE_3 = 353;
    uint256 internal constant TOKENS_NOT_AMONG_POOL_TOKENS = 354;
}

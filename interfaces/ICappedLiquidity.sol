pragma solidity 0.7.6;
pragma experimental ABIEncoderV2;

interface ICappedLiquidity {
    event CapParamsUpdated(CapParams params);
    event CapManagerUpdated(address capManager);

    struct CapParams {
        bool capEnabled;
        uint120 perAddressCap;
        uint128 globalCap;
    }

    function setCapParams(CapParams memory params) external;

    function capParams() external view returns (CapParams memory);

    function capManager() external view returns (address);
}

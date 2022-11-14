// SPDX-License-Identifier: LicenseRef-Gyro-1.0
// for information on licensing please see the README in the GitHub repository <https://github.com/gyrostable/concentrated-lps>.

pragma solidity 0.7.6;

import "@balancer-labs/v2-solidity-utils/contracts/openzeppelin/ERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

contract SimpleERC20 is ERC20, Ownable {
    constructor() ERC20("MyToken", "MTK") {
        // solhint-disable-previous-line no-empty-blocks
    }

    function mint(address to, uint256 amount) public onlyOwner {
        _mint(to, amount);
    }
}

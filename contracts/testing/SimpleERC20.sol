// SPDX-License-Identifier: MIT
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

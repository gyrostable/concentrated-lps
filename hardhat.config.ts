import { HardhatUserConfig } from "hardhat/config";
import "@nomiclabs/hardhat-etherscan";
import "@nomiclabs/hardhat-waffle";
import "@typechain/hardhat";
import "hardhat-gas-reporter";
import "solidity-coverage";
import overrideQueryFunctions from "@balancer-labs/v2-helpers/plugins/overrideQueryFunctions";
import { task } from "hardhat/config";
import { TASK_COMPILE } from "hardhat/builtin-tasks/task-names";
import { hardhatBaseConfig } from "@balancer-labs/v2-common";

task(TASK_COMPILE).setAction(overrideQueryFunctions);

const config: HardhatUserConfig = {
  solidity: {
    compilers: hardhatBaseConfig.compilers,
    overrides: hardhatBaseConfig.overrides("xxx"),
  },
};

export default config;

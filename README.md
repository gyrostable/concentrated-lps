# Gyroscope Concentrated Liquidity Pools

Gyroscope concentrated liquidity pools based on Balancer V2. 2-CLPs and 3-CLPs.

For docs see: https://docs.gyro.finance/gyroscope-protocol/concentrated-liquidity-pools

## Repo Setup

This project uses Brownie as its main testing framework but is also
compatible with hardhat to be able to reuse some of the Balancer testing
infrastructure if needed.

## Dependencies

To install dependencies use

```bash
$ yarn
```

## Compiling and testing

The project can be compiled and tested using

```bash
$ brownie compile
$ brownie test
```

## Gas Testing

To analyze gas usage, the `Tracer` in `tests/support/analyze_trace.py` can be used in the following way:

```python
from tests.support.trace_analyzer import Tracer

tx = ... # transaction to analyze

tracer = Tracer.load()
print(tracer.trace_tx(tx))
```

For this to work, you may need to install a version of brownie where a bug has been fixed:
```bash
$ pip install -U git+https://github.com/danhper/brownie.git@avoid-removing-dependencies
```

Then you need to run your script with everything compiled *before* the script runs, i.e., you need something like

```bash
brownie compile; brownie run scripts/my_script.py
```

### Gas measurement scripts

There are gas measurement scripts at `scripts/show_gas_usage_*.py`. For example:

```bash
$ brownie run scripts/show_gas_usage_2clp.py
```

You can run all the ready-made gas measurements, and store their data, via
```bash
$ scripts/run_gas_measurements.sh
```

For this you need the `ansi2txt` utility installed. On Ubuntu you can get it via the `colorized-logs` package.

This writes log files to `analysis/gas/`.


## Licensing

Superluminal Labs Ltd. is the owner of this software and any accompanying files contained herein (collectively, this “Software”). This Software is not covered by the General Public License ("GPL") and does not confer any rights to the user thereunder. None of the code incorporated into the Software was GPL-licensed, and Superluminal Labs Ltd. has received prior custom licenses for all such code, including a special hybrid license between Superluminal Labs Ltd and Balancer Labs OÜ [Special Licence](https://github.com/gyrostable/concentrated-lps/license/GyroscopeBalancerLicense.pdf).
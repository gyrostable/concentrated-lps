#!/bin/bash

set -e  # exit on error

# Go to repo root
cd "$(dirname "$0")/../"

mkdir -p analysis/gas

# Clean build is important; saw some crashes without it
rm -r build/
brownie compile

for m in 2clp 3clp eclp; do
  echo "$m..." >&2
  brownie run scripts/show_gas_usage_$m.py --silent | ansi2txt > analysis/gas/gas_$m.log
done

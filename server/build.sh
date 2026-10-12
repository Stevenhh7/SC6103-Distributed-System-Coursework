#!/bin/sh
# Portable Java 17-target build. No network or third-party build dependencies.
set -eu
cd "$(dirname "$0")/.."
"${PYTHON:-python3}" -c 'from experiments.run_suite import compile_java; compile_java()'

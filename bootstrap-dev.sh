#!/usr/bin/env bash

set -e

python3 -m venv venv

source venv/bin/activate

python3 -m pip install -r requirements-dev.txt

git config --local core.hooksPath hooks

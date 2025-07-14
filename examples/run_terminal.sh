#!/bin/bash

# This script demonstrates how to run the terminal interface of TheMule Atomic HITL.
# It passes the sample data and configuration files to the terminal_main.py script.

# Ensure the script is run from the root of the repository
if [ ! -f "setup.py" ]; then
    echo "Please run this script from the root of the repository."
    exit 1
fi

# It's recommended to run the tool within a virtual environment
# with all the dependencies from requirements.txt installed.

# The main command
python3 src/themule_atomic_hitl/terminal_main.py \
    --data examples/sample_data.json \
    --config examples/config.json \
    --no-frontend

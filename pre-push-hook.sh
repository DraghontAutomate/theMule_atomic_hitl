#!/bin/bash
#
# Git pre-push hook to run the project's test suite.
#
# To install this hook:
# 1. Make sure this file is executable: chmod +x pre-push-hook.sh
# 2. Copy it to your .git/hooks directory: cp pre-push-hook.sh .git/hooks/pre-push

echo "--- Running pre-push hook: Executing test suite ---"

# Ensure dependencies are installed (optional, but good for robustness)
echo "Checking/installing dependencies..."
pip install . > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "Error: Failed to install dependencies with 'pip install .'. Aborting push."
    exit 1
fi

# Run the test script
python run_tests.py
TEST_RESULT=$?

if [ $TEST_RESULT -ne 0 ]; then
    echo "--------------------------------------------------------"
    echo " Pre-push hook failed: Test suite reported errors."
    echo " Please fix the tests before pushing."
    echo "--------------------------------------------------------"
    exit 1
else
    echo "--------------------------------------------------------"
    echo " Pre-push hook passed: All tests successful."
    echo "--------------------------------------------------------"
fi

exit 0

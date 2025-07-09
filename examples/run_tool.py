# examples/run_tool.py
import sys
import os
# json import removed as run_application now handles file loading internally

# Import the main runner function from the installed package
# Assuming 'themule_atomic_hitl' is installed or PYTHONPATH is set up correctly
# to find the src directory.
try:
    from themule_atomic_hitl import run_application
except ImportError:
    # Fallback for running directly from the repo root if not installed
    # (e.g., python examples/run_tool.py)
    # This adds the project's root directory (parent of 'examples') to sys.path
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, project_root)
    from src.themule_atomic_hitl import run_application


if __name__ == "__main__":
    # Define paths to data and config files relative to this script's location
    # This script is in 'examples/', so data.json and config.json are in the same directory.
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_file = os.path.join(current_dir, "data.json")
    config_file = os.path.join(current_dir, "config.json")

    # Check if files exist before attempting to run
    if not os.path.exists(data_file):
        print(f"Error: Data file not found at {data_file}")
        sys.exit(1)
    if not os.path.exists(config_file):
        print(f"Error: Config file not found at {config_file}")
        sys.exit(1)

    # run_application now expects paths to the data and config files
    run_application(data_file_path=data_file, config_file_path=config_file)

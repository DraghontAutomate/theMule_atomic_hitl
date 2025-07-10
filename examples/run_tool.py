# examples/run_tool.py
"""
This script serves as an example of how to launch the TheMule Atomic HITL application.

It demonstrates:
1. Importing the `run_application` function from the `themule_atomic_hitl` package.
   It includes a fallback mechanism to import from the `src` directory if the package
   is not installed, allowing the example to be run directly from the repository.
2. Constructing paths to the example `data.json` and `config.json` files,
   which are expected to be in the same directory as this script.
3. Performing basic checks to ensure these JSON files exist before launching.
4. Calling `run_application` with the paths to the data and configuration files.

To run this example:
- Ensure you have the necessary dependencies installed (e.g., from requirements.txt).
- Navigate to the root of the repository.
- Execute: `python examples/run_tool.py`
"""

import sys
import os
# The `json` import was removed as `run_application` (and its internal _load_json_file helper)
# now handles the file loading and JSON parsing internally.

# --- Import `run_application` ---
# This section attempts to import the main application runner.
# It first tries to import it as if `themule_atomic_hitl` is an installed package.
# If that fails (ImportError), it assumes the script is being run from within the
# repository structure and adjusts `sys.path` to find the `src` directory.

try:
    # Attempt to import from the installed package (standard way)
    from themule_atomic_hitl import run_application
except ImportError:
    # Fallback for running directly from the repository (e.g., `python examples/run_tool.py`)
    # This modification to sys.path allows Python to find the 'src' directory
    # when the package hasn't been formally installed (e.g., via pip install .).
    print("Package 'themule_atomic_hitl' not found as installed. Attempting to run from source...")
    # Get the directory containing this script (e.g., /path/to/repo/examples)
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    # Get the parent directory (e.g., /path/to/repo)
    project_root = os.path.dirname(current_script_dir)
    # Add the project root to sys.path so 'src.themule_atomic_hitl' can be found
    sys.path.insert(0, project_root)
    try:
        from src.themule_atomic_hitl import run_application
        print(f"Successfully imported 'run_application' from source directory: {project_root}")
    except ImportError as e:
        print(f"Failed to import 'run_application' from source directory: {project_root}")
        print(f"ImportError: {e}")
        print("Please ensure that the script is run from the project root or that the package is installed.")
        sys.exit(1)


if __name__ == "__main__":
    """
    Main execution block.
    This code runs when the script is executed directly.
    """

    # --- Define Paths to Data and Config Files ---
    # The example `data.json` and `config.json` are expected to be in the same
    # directory as this `run_tool.py` script (i.e., within the 'examples' folder).
    current_dir = os.path.dirname(os.path.abspath(__file__)) # Gets the directory of this script
    data_file = os.path.join(current_dir, "data.json")       # Path to examples/data.json
    config_file = os.path.join(current_dir, "config.json")   # Path to examples/config.json

    # --- File Existence Checks ---
    # It's good practice to check if the required files exist before trying to use them.
    if not os.path.exists(data_file):
        print(f"Error: Data file not found at the expected location: {data_file}")
        print("Please ensure 'data.json' is in the 'examples' directory.")
        sys.exit(1) # Exit if the data file is missing
    if not os.path.exists(config_file):
        print(f"Error: Config file not found at the expected location: {config_file}")
        print("Please ensure 'config.json' is in the 'examples' directory.")
        sys.exit(1) # Exit if the config file is missing

    print(f"Using data file: {data_file}")
    print(f"Using config file: {config_file}")

    # --- Run the Application ---
    # The `run_application` function from `themule_atomic_hitl.runner`
    # now expects the file paths to the data and configuration JSON files.
    # It will handle opening and parsing these files internally.
    run_application(data_file_path=data_file, config_file_path=config_file)

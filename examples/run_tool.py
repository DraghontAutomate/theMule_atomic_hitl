# examples/run_tool.py
import faulthandler
faulthandler.enable()
import sys # For flushing stdout
import logging

logging.basicConfig(filename='debug_tool_run.log', level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    filemode='w') # Overwrite log file each run

logging.debug("RUN_TOOL.PY: Script starting, faulthandler and logging enabled.")
print("RUN_TOOL.PY: Script starting", flush=True) # Keep print for immediate console feedback
"""

This script serves as an example of how to use the TheMule Atomic HITL tool
as a library, primarily through the `hitl_node_run` function.

It demonstrates:
1. Importing `hitl_node_run` and other necessary components from the
   `themule_atomic_hitl` package. It includes a fallback mechanism to adjust
   `sys.path` if the package is not installed, allowing the example to be run
   directly from the repository.
2. Running `hitl_node_run` with simple string content and default UI configuration.
3. Running `hitl_node_run` with dictionary content (loaded from `sample_data.json`)
   and default UI configuration.
4. Running `hitl_node_run` with string content and a custom UI configuration
   (loaded from `config.json`).

To run this example:
- Ensure you have the necessary dependencies installed (e.g., from requirements.txt).
- Navigate to the root of the repository.
- Execute: `python examples/run_tool.py`
"""

import sys
import os
import json # For loading data and printing results

# --- Adjust Python path for direct execution ---
# This section allows the script to find the 'src' directory when running
# directly from the repository, if the package hasn't been formally installed.
# When installed as a package, these imports should work directly.

try:
    # This will work if the package is installed (e.g., via pip install -e .)
    # or if the top-level project directory is in PYTHONPATH.
    from themule_atomic_hitl import hitl_node_run
    from themule_atomic_hitl.runner import _load_json_file
    from themule_atomic_hitl.config import Config # Though hitl_node_run handles Config internally
    logging.debug("Imported themule_atomic_hitl components directly.")
except ImportError as e_installed:
    logging.warning(f"Could not import from 'themule_atomic_hitl' directly (package not installed or not in PYTHONPATH?): {e_installed}")
    # Fallback for running script directly from repo, assuming 'src' is sibling to 'examples'
    # and project root needs to be in path for 'from src...' to work.
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
        logging.debug(f"Added project root to sys.path: {project_root}")

    try:
        from src.themule_atomic_hitl import hitl_node_run
        from src.themule_atomic_hitl.runner import _load_json_file # Helper for loading JSON data
        from src.themule_atomic_hitl.config import Config # Though hitl_node_run handles Config internally
        logging.debug("Successfully imported components via 'src.' prefix after path adjustment.")
    except ImportError as e_src:
        logging.error(f"Failed to import components via 'src.' prefix even after path adjustment: {e_src}")
        print(f"Failed to import components. Ensure 'themule_atomic_hitl' is installed or run from project root. Error: {e_src}", flush=True)
        sys.exit(1)


def main():
    current_dir = os.path.dirname(os.path.abspath(__file__)) # Directory of this script

    print("Starting HITL example demonstrations...", flush=True)

    # --- Example 1: Using hitl_node_run with a simple string content and default config ---
    print("\n--- Example 1: Running HITL with simple string content (default config) ---", flush=True)
    simple_text_content = "This is the initial text. It needs some review and potential edits from the user."

    # hitl_node_run handles QApplication internally if not provided
    print("RUN_TOOL.PY: About to call hitl_node_run for Example 1", flush=True)
    logging.debug("RUN_TOOL.PY: About to call hitl_node_run for Example 1")
    final_data_simple = hitl_node_run(content_to_review=simple_text_content)
    logging.debug(f"RUN_TOOL.PY: hitl_node_run for Example 1 returned: {type(final_data_simple)}")
    print("RUN_TOOL.PY: hitl_node_run for Example 1 returned", flush=True)

    if final_data_simple:
        logging.debug(f"RUN_TOOL.PY: Example 1 success, data: {final_data_simple}")
        print("\n--- Result from Example 1 (simple string) ---")
        print(json.dumps(final_data_simple, indent=2))
    else:
        print("Example 1: HITL tool run was cancelled or failed.")

    print("\n" + "="*50 + "\n")

    # --- Example 2: Using hitl_node_run with dictionary content from sample_data.json ---
    #    (This will use the default UI config unless a custom one is specified via hitl_node_run)
    print("\n--- Example 2: Running HITL with dictionary content from sample_data.json (default config) ---")
    sample_data_file_path = os.path.join(current_dir, "sample_data.json")

    if not os.path.exists(sample_data_file_path):
        print(f"Error: Sample data file not found at {sample_data_file_path}. Skipping Example 2.")
    else:
        print(f"Using sample data file: {sample_data_file_path}")
        loaded_dict_content = _load_json_file(sample_data_file_path) # Using the corrected helper from runner
        if loaded_dict_content:
            final_data_dict = hitl_node_run(content_to_review=loaded_dict_content)
            if final_data_dict:
                print("\n--- Result from Example 2 (dictionary input) ---")
                print(json.dumps(final_data_dict, indent=2))
            else:
                print("Example 2: HITL tool run was cancelled or failed.")
        else:
            print(f"Example 2: Failed to load data from {sample_data_file_path}.")

    print("\n" + "="*50 + "\n")

    # --- Example 3: Using hitl_node_run with string content and a custom config file ---
    print("\n--- Example 3: Running HITL with string content and custom config.json ---")
    custom_config_file_path = os.path.join(current_dir, "config.json") # The example custom config

    if not os.path.exists(custom_config_file_path):
        print(f"Error: Custom config file not found at {custom_config_file_path}. Skipping Example 3.")
    else:
        print(f"Using custom config file: {custom_config_file_path}")
        custom_text_content = "This text will be edited using a custom UI configuration defined in 'config.json'."
        final_data_custom_config = hitl_node_run(
            content_to_review=custom_text_content,
            custom_config_path=custom_config_file_path
        )
        if final_data_custom_config:
            print("\n--- Result from Example 3 (custom config) ---")
            print(json.dumps(final_data_custom_config, indent=2))
        else:
            print("Example 3: HITL tool run was cancelled or failed.")

    print("\nAll examples finished.")

if __name__ == "__main__":
    main()

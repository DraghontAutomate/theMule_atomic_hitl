# examples/run_tool.py
import sys
import os
import json # For loading data and printing results

# Adjust Python path to find the src directory if running directly
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    # Primary import for the new library entry point
    from src.themule_atomic_hitl import hitl_node_run
    # For loading data if needed, and Config class for specific scenarios
    from src.themule_atomic_hitl.runner import _load_data_file # if used for dict example
    from src.themule_atomic_hitl.config import Config
except ImportError as e:
    print(f"ImportError: {e}. Ensure the package structure is correct and PYTHONPATH is set if needed.")
    sys.exit(1)


if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # --- Example 1: Using hitl_node_run with a simple string content and default config ---
    print("\n--- Example 1: Running HITL with simple string content (default config) ---")
    simple_text_content = "This is the initial text. It needs some review and edits."

    # For this simple case, hitl_node_run handles QApplication internally
    final_data_simple = hitl_node_run(content_to_review=simple_text_content)

    if final_data_simple:
        print("\n--- Result from Example 1 (simple string) ---")
        print(json.dumps(final_data_simple, indent=2))
        # The key for the edited text would be config-dependent, e.g., 'editedText' by default
        # print(f"Edited text: {final_data_simple.get('editedText')}")
    else:
        print("Example 1: HITL tool run was cancelled or failed.")

    print("\n" + "="*50 + "\n")

    # --- Example 2: Using hitl_node_run with dictionary content from a JSON file ---
    #    (This will use the default config unless a custom one is specified)
    print("\n--- Example 2: Running HITL with dictionary content from sample_data.json (default config) ---")
    sample_data_file = os.path.join(current_dir, "sample_data.json") # data.json will be renamed

    if not os.path.exists(sample_data_file):
        print(f"Error: Sample data file not found at {sample_data_file}. Skipping Example 2.")
    else:
        loaded_dict_content = _load_data_file(sample_data_file)
        if loaded_dict_content:
            final_data_dict = hitl_node_run(content_to_review=loaded_dict_content)
            if final_data_dict:
                print("\n--- Result from Example 2 (dictionary input) ---")
                print(json.dumps(final_data_dict, indent=2))
            else:
                print("Example 2: HITL tool run was cancelled or failed.")
        else:
            print(f"Example 2: Failed to load data from {sample_data_file}.")

    print("\n" + "="*50 + "\n")

    # --- Example 3: Using hitl_node_run with custom config and string content ---
    print("\n--- Example 3: Running HITL with string content and custom config.json ---")
    custom_config_file = os.path.join(current_dir, "config.json") # The existing example config

    if not os.path.exists(custom_config_file):
        print(f"Error: Custom config file not found at {custom_config_file}. Skipping Example 3.")
    else:
        custom_text_content = "This text will be edited using a custom UI configuration defined in config.json."
        final_data_custom_config = hitl_node_run(
            content_to_review=custom_text_content,
            custom_config_path=custom_config_file
        )
        if final_data_custom_config:
            print("\n--- Result from Example 3 (custom config) ---")
            print(json.dumps(final_data_custom_config, indent=2))
        else:
            print("Example 3: HITL tool run was cancelled or failed.")

    print("\nAll examples finished.")

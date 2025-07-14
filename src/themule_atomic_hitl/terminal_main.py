import argparse
import logging
import os
import sys
import json
from typing import Dict, Any, Union

# It's good practice to set up logging at the very beginning.
# This will catch logs from all imported modules.
try:
    from .logging_config import setup_logging
except ImportError:
    from logging_config import setup_logging

setup_logging()

# Now, import your application-specific modules
try:
    from .config import Config
    from .runner import run_application, Backend
    # We will create this terminal_interface module in the next step
    # from .terminal_interface import run_terminal_interface
except ImportError:
    # This allows the script to be run from the root directory for development
    from config import Config
    from runner import run_application, Backend
    # from terminal_interface import run_terminal_interface


def _load_data_from_file(path: str) -> Union[Dict[str, Any], str]:
    """
    Helper function to load data from a file.
    It tries to load the file as JSON, but if it fails, it returns the content as a raw string.
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            try:
                # First, try to load as JSON
                return json.load(f)
            except json.JSONDecodeError:
                # If JSON decoding fails, reset cursor and read as plain text
                f.seek(0)
                return f.read()
    except FileNotFoundError:
        logging.error(f"Error: File not found at {path}")
        return "" # Return empty string for not found
    except Exception as e:
        logging.error(f"An unexpected error occurred while reading {path}: {e}")
        return "" # Return empty string for other errors

def main():
    """
    Main entry point for the application.
    Parses command-line arguments to determine which interface to run (GUI or Terminal).
    """
    parser = argparse.ArgumentParser(description="TheMule Atomic HITL Surgical Editor")
    parser.add_argument(
        '--no-frontend',
        action='store_true',
        help="Run the application in terminal mode without the GUI frontend."
    )
    parser.add_argument(
        '--config',
        type=str,
        default=None,
        help="Path to a custom JSON configuration file."
    )
    parser.add_argument(
        '--data',
        type=str,
        default=None,
        help="Path to the initial JSON data file."
    )

    args = parser.parse_args()

    # --- Configuration Loading ---
    if args.config:
        app_config = Config(custom_config_path=args.config)
    else:
        # Load default config if no path is provided
        # This assumes a default config can be found or is embedded in the Config class
        app_config = Config()

    # --- Initial Data Loading ---
    initial_app_data = "" # Default to empty string
    if args.data:
        initial_app_data = _load_data_from_file(args.data)

    if not initial_app_data:
        logging.warning("No initial data provided or file is empty. Using minimal default data.")
        # If the data is still empty (e.g., file not found, or empty file),
        # we create a default dictionary.
        # This part is tricky because the HITL node now expects either a string or a dict.
        # If we provide a dict, it will be used directly. If we provide a string, it will be wrapped.
        # For the terminal_main, let's decide if we want to proceed with a default string or a default dict.
        # A default dict is more structured and aligns with the previous behavior.
        m_field = app_config.main_editor_modified_field
        o_field = app_config.main_editor_original_field
        initial_app_data = {
            m_field: "Default content for main execution.",
            o_field: "Default content for main execution.",
            "status": "Initial Load"
        }

    # --- Application Mode Selection ---
    if args.no_frontend:
        logging.info("Starting in Terminal Mode...")
        # This function will be created in the next step
        # final_data = run_terminal_interface(initial_app_data, app_config)
        # logging.info("\n--- Terminal session finished ---")
        # if final_data:
        #     logging.info(json.dumps(final_data, indent=2))
        logging.warning("Terminal interface is not yet implemented.")

    else:
        from .hitl_node import hitl_node_run
        logging.info("Starting in GUI Mode...")
        # The hitl_node_run function now encapsulates the logic for preparing data and running the app
        final_data = hitl_node_run(
            content_to_review=initial_app_data,
            custom_config_path=args.config,
            # In terminal_main, we are not integrating into an existing Qt app,
            # so we pass None for existing_qt_app.
            existing_qt_app=None
        )

        logging.info("\n--- GUI session finished ---")
        if final_data:
            logging.info("Final data returned:")
            # We can use json.dumps to pretty-print the final dictionary
            logging.info(json.dumps(final_data, indent=2))

if __name__ == '__main__':
    main()

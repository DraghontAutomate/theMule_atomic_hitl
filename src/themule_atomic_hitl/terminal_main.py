import argparse
import logging
import os
import sys
import json
from typing import Dict, Any

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


def _load_json_file(path: str) -> Dict[str, Any]:
    """
    Helper function to load data from a JSON file.
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Error loading JSON from {path}: {e}")
        return {}

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
    initial_app_data = None
    if args.data:
        initial_app_data = _load_json_file(args.data)

    if not initial_app_data:
        logging.warning("No initial data file provided or file is empty. Using minimal default data.")
        # Use main_editor_modified_field from config to structure default data
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
        logging.info("Starting in GUI Mode...")
        # We need to get the config as a dictionary for the runner
        config_dict = app_config.get_config()
        # The run_application function from runner.py will handle the GUI
        final_data = run_application(initial_app_data, config_dict, qt_app=None)

        logging.info("\n--- GUI session finished ---")
        if final_data:
            logging.info("Final data returned:")
            logging.info(json.dumps(final_data, indent=2))

if __name__ == '__main__':
    main()

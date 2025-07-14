import argparse
import logging
import os
import sys
import json
from typing import Dict, Any

try:
    from .logging_config import setup_logging
except ImportError:
    from logging_config import setup_logging

setup_logging()

try:
    from .config import Config
    from .runner import run_application
    from .terminal_interface import run_terminal_interface
except ImportError:
    from config import Config
    from runner import run_application
    from terminal_interface import run_terminal_interface


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
        app_config = Config()

    # --- Initial Data Loading ---
    initial_app_data = None
    if args.data:
        initial_app_data = _load_json_file(args.data)

    if not initial_app_data:
        logging.warning("No initial data file provided or file is empty. Using minimal default data.")
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
        final_data = run_terminal_interface(initial_app_data, app_config)
        logging.info("\n--- Terminal session finished ---")
        if final_data:
            logging.info(json.dumps(final_data, indent=2))
    else:
        logging.info("Starting in GUI Mode...")
        config_dict = app_config.get_config()
        final_data = run_application(initial_app_data, config_dict, qt_app=None)

        logging.info("\n--- GUI session finished ---")
        if final_data:
            logging.info("Final data returned:")
            logging.info(json.dumps(final_data, indent=2))

if __name__ == '__main__':
    main()

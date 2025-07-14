# src/themule_atomic_hitl/hitl_node.py

import sys
import logging
from typing import Dict, Any, Optional, Union

from PyQt5.QtWidgets import QApplication, QMainWindow

from .config import Config
from .runner import run_application # Assuming run_application is in runner.py

def hitl_node_run(
    content_to_review: Union[str, Dict[str, Any]],
    custom_config_path: Optional[str] = None,
    existing_qt_app: Optional[QApplication] = None
) -> Optional[Dict[str, Any]]:
    """
    Provides a library entry point to run the HITL tool.

    This function initializes the configuration, prepares the data, and then
    launches the HITL UI. It can either create a new QApplication instance
    or use an existing one if provided (useful for integration into larger Qt apps).

    Args:
        content_to_review: The primary content to be reviewed.
                           Can be a string (which will be treated as the main text for editing)
                           or a dictionary (which should conform to the expected data structure,
                           including fields for original and modified text as per configuration).
        custom_config_path: Optional path to a custom JSON configuration file.
                            If None, default configuration is used.
        existing_qt_app: Optional existing QApplication instance. If None, a new one
                         will be created and managed by this function.

    Returns:
        A dictionary containing the final state of the data after user interaction,
        or None if the application could not be started or an error occurred.
    """
    logging.info("HITL_NODE_RUN_PYTHON: Entry point")
    final_data: Optional[Dict[str, Any]] = None # Initialize final_data
    try:
        logging.debug("HITL_NODE_RUN_PYTHON: Inside try block, before Config init")
        # 1. Initialize Configuration
        config_manager = Config(custom_config_path=custom_config_path)
        logging.debug(f"HITL_NODE_RUN_PYTHON: Config object initialized: {type(config_manager)}")
        config_dict = config_manager.get_config() # For easier access to keys
        logging.debug(f"HITL_NODE_RUN_PYTHON: config_dict obtained: {type(config_dict)}")

        # 2. Prepare Initial Data
        initial_data: Dict[str, Any] = {}
        main_editable_field = config_manager.main_editor_modified_field
        original_text_field = config_manager.main_editor_original_field

        if isinstance(content_to_review, str):
            # If content_to_review is a string, use it for both original and edited fields initially
            initial_data[main_editable_field] = content_to_review
            initial_data[original_text_field] = content_to_review
            # Add other potential metadata fields from default data if they are not set
            # This part depends on whether we want to merge with some default metadata structure
            # For now, we keep it simple: content_to_review is the focus.
            # Default fields from config (like 'status') might be populated by UI or SurgicalEditorLogic
            # based on config, not necessarily from here unless specified.
        elif isinstance(content_to_review, dict):
            initial_data = content_to_review.copy()
            # Ensure the necessary fields for the diff editor are present
            if main_editable_field not in initial_data:
                logging.warning(f"Main editable field '{main_editable_field}' not found in provided data dict. Initializing to empty string.")
                initial_data[main_editable_field] = ""
            if original_text_field not in initial_data:
                logging.warning(f"Original text field '{original_text_field}' not found in provided data dict. Initializing from '{main_editable_field}'.")
                initial_data[original_text_field] = initial_data[main_editable_field]
        else:
            logging.error("content_to_review must be a string or a dictionary.")
            return None

        # The old QApplication management logic (previously here) has been removed.
        # The new logic is integrated below using run_application's refined behavior.

        if existing_qt_app:
            logging.info("hitl_node_run: Using provided existing QApplication.")
            returned_value_from_runner = run_application(
                initial_data_param=initial_data,
                config_param_dict=config_dict, # Pass the dict
                qt_app=existing_qt_app
            )
            if isinstance(returned_value_from_runner, QMainWindow):
                main_window_instance = returned_value_from_runner
                logging.info("hitl_node_run: Existing QApplication mode. Waiting for session to terminate via local event loop...")
                local_event_loop = QApplication.QEventLoop()
                main_window_instance.backend.sessionTerminatedSignal.connect(local_event_loop.quit)
                if not main_window_instance.isVisible():
                    main_window_instance.show()
                local_event_loop.exec_()
                final_data = main_window_instance.backend.logic.get_final_data()
                logging.info("hitl_node_run: Session terminated, local event loop finished.")
            elif returned_value_from_runner is None:
                 logging.warning("hitl_node_run: run_application returned None with existing_qt_app.")
                 final_data = None
            else:
                logging.error(f"hitl_node_run: Unexpected return type {type(returned_value_from_runner)} from run_application with existing_qt_app.")
                final_data = None
        else: # No existing_qt_app provided
            logging.info("hitl_node_run: No existing QApplication provided. run_application will manage its own if needed.")
            returned_value_from_runner = run_application(
                initial_data_param=initial_data,
                config_param_dict=config_dict, # Pass the dict
                qt_app=None
            )
            if isinstance(returned_value_from_runner, dict):
                final_data = returned_value_from_runner
            elif returned_value_from_runner is None:
                 final_data = None
            else:
                logging.error(f"hitl_node_run: Unexpected return type {type(returned_value_from_runner)} from run_application when qt_app is None.")
                final_data = None

        return final_data

    except Exception as e:
        logging.error(f"Error in hitl_node_run: {e}", exc_info=True)
        return None

if __name__ == '__main__':
    # This is an example of how to use hitl_node_run
    # Ensure you are in the project root or PYTHONPATH is set correctly.
    logging.info("Running hitl_node_run example...")

    # Example 1: Simple string content, default config
    # test_content_string = "This is the initial string content for the HITL tool."
    # logging.info(f"\n--- Running with simple string: '{test_content_string}' ---")
    # result_string = hitl_node_run(test_content_string)
    # if result_string:
    #     logging.info("--- HITL tool finished (string input) ---")
    #     logging.info("Final data:")
    #     logging.info(json.dumps(result_string, indent=2))
    # else:
    #     logging.warning("HITL tool execution failed or was cancelled (string input).")

    # Example 2: Dictionary content, custom config
    # Create a dummy custom config for testing
    import json
    import os
    custom_config_example_path = "temp_custom_hitl_config.json"
    # Assuming this script is in src/themule_atomic_hitl/
    # For __main__ execution, current directory is where python is called.
    # Let's try to make path relative to this file if possible, or assume project root.
    # This path might be tricky depending on execution context.
    # For a robust example, create it in current working directory.

    # Get project root assuming this file is src/themule_atomic_hitl/hitl_node.py
    project_root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    custom_config_example_path = os.path.join(project_root_dir, "examples", "custom_config_for_hitl_node_test.json")
    sample_data_path = os.path.join(project_root_dir, "examples", "sample_data.json") # Assuming it will be renamed


    with open(custom_config_example_path, "w") as f:
        json.dump({
            "fields": [
                {"name": "status", "label": "Review Status", "type": "label", "placement": "header"},
                {"name": "custom_notes", "label": "Notes from HITL Node", "type": "textarea", "placement": "sidebar"},
                {
                  "name": "main_diff_editor",
                  "type": "diff-editor",
                  "placement": "mainbody",
                  "originalDataField": "originalContent", # Custom field names
                  "modifiedDataField": "currentContent"
                }
            ],
            "actions": [{ "name": "approve_and_close", "label": "Approve & Close", "placement": "header", "isPrimary": True }],
            "settings": {"defaultWindowTitle": "HITL Node Test Window"}
        }, f)

    test_content_dict = {
        "originalContent": "Initial content for the dictionary test.",
        "currentContent": "Slightly modified initial content for the dictionary test.",
        "custom_notes": "Pre-filled notes.",
        "status": "Pending Review via HITL Node"
    }

    logging.info(f"\n--- Running with dictionary input and custom config: {custom_config_example_path} ---")
    # Ensure QApplication instance exists for this example run if not managed by hitl_node_run internally
    # q_app = QApplication.instance() or QApplication(sys.argv)

    result_dict = hitl_node_run(test_content_dict, custom_config_path=custom_config_example_path) #, existing_qt_app=q_app)

    if result_dict:
        logging.info("--- HITL tool finished (dict input) ---")
        logging.info("Final data:")
        logging.info(json.dumps(result_dict, indent=2))
    else:
        logging.warning("HITL tool execution failed or was cancelled (dict input).")

    # Clean up dummy config
    if os.path.exists(custom_config_example_path):
        # os.remove(custom_config_example_path) # Keep for user to inspect
        logging.info(f"Test custom config kept at: {custom_config_example_path}")
        pass

    # Example with existing QApplication (more advanced, requires careful setup)
    # logging.info("\n--- Running with existing QApplication (simulated) ---")
    # existing_app_instance = QApplication.instance()
    # if not existing_app_instance:
    #     existing_app_instance = QApplication(sys.argv)
    #
    # test_content_string_for_existing_app = "Content for existing app test."
    # result_existing_app = hitl_node_run(
    #     test_content_string_for_existing_app,
    #     existing_qt_app=existing_app_instance
    # )
    # if result_existing_app:
    #     logging.info("--- HITL tool finished (existing app) ---")
    #     logging.info(json.dumps(result_existing_app, indent=2))
    # else:
    #     logging.warning("HITL tool execution failed or was cancelled (existing app scenario).")
    #
    # if existing_app_instance and not QApplication.instance().closingDown():
    #     # If we created it here for the test, we might need to exec and quit.
    #     # This part is tricky because the event loop management is external.
    #     # For this example, we'll assume this test instance of existing_app isn't part of a larger running app.
    #     # existing_app_instance.exec_() # This would start a new loop if one isn't running.
    #     pass

    logging.info("\n--- hitl_node_run example finished ---")

# To make sure the __init__.py is aware of this function for easier import
# (e.g., from themule_atomic_hitl import hitl_node_run)
# this would be done in __init__.py, not here.

logging.info("hitl_node.py created with hitl_node_run function.")

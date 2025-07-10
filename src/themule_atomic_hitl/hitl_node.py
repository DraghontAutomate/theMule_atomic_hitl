# src/themule_atomic_hitl/hitl_node.py

import sys
from typing import Dict, Any, Optional, Union

from PyQt5.QtWidgets import QApplication

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
    final_data: Optional[Dict[str, Any]] = None # Initialize final_data
    try:
        # 1. Initialize Configuration
        config_manager = Config(custom_config_path=custom_config_path)
        config_dict = config_manager.get_config() # For easier access to keys

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
                print(f"Warning: Main editable field '{main_editable_field}' not found in provided data dict. Initializing to empty string.")
                initial_data[main_editable_field] = ""
            if original_text_field not in initial_data:
                print(f"Warning: Original text field '{original_text_field}' not found in provided data dict. Initializing from '{main_editable_field}'.")
                initial_data[original_text_field] = initial_data[main_editable_field]
        else:
            print("Error: content_to_review must be a string or a dictionary.")
            return None

        # 3. Manage QApplication instance
        app = existing_qt_app
        app_created_here = False
        if app is None:
            app = QApplication.instance()
            if app is None:
                print("hitl_node_run: Creating new QApplication instance.")
                app = QApplication(sys.argv)
                app_created_here = True
            # else:
                # print("hitl_node_run: Using existing QApplication instance found by QApplication.instance().")
        # else:
            # print("hitl_node_run: Using provided existing QApplication instance.")

        if app is None: # Should not happen if QApplication(sys.argv) was successful
            print("Error: Could not obtain QApplication instance.")
            return None

        # 4. Run the application UI
        # run_application will handle its own loop if app_created_here is True (i.e., existing_qt_app was None)
        # and it will return the final data.
        # If existing_qt_app was provided, run_application returns the main_window,
        # and this function would need to become async or handle event loop differently.
        # For a synchronous library call, we want run_application to block until UI is done.

        # The refactored run_application is expected to return final_data if it manages the loop,
        # or the main_window if the loop is external.
        # For hitl_node_run to be a simple blocking call, it should ensure it passes None for qt_app
        # if it created the app, so run_application starts its own blocking event loop.

        if app_created_here:
            final_data = run_application(initial_data_param=initial_data, config_param=config_manager, qt_app=None)
            # QApplication.quit() # Ensure app quits if created here - run_application's exec_ should handle this.
        else:
            # If using an existing app, the caller manages the event loop.
            # This scenario makes hitl_node_run non-blocking by default with current run_application.
            # To make it blocking, we'd need to start a local event loop here,
            # or have run_application always block.
            # For LangGraph, a blocking call is usually preferred.
            # The run_application will return final_data IF qt_app is None
            print("hitl_node_run: Running with existing Qt app. The function will return after UI is shown.")
            print("The caller is responsible for the Qt event loop.")
            print("For a blocking call in this scenario, further adaptation of run_application or this function is needed.")
            # This is a tricky part: if the external app is running its loop, how do we get the result back *here*?
            # Option A: run_application is always blocking (e.g. uses QEventLoop locally if qt_app is passed)
            # Option B: hitl_node_run returns a future or uses callbacks if used with existing_qt_app
            # For now, let's assume if existing_qt_app is passed, the user knows what they're doing
            # and might not get an immediate return value in a simple synchronous way.
            # However, the plan implies this function returns the final data.
            # Let's adjust run_application to always try to be blocking or make this clear.
            # The current run_application returns final_data if qt_app is None.
            # If qt_app is not None, it returns main_window.
            # To make this function blocking and return data when existing_qt_app is provided:
            main_window_instance = run_application(initial_data_param=initial_data, config_param=config_manager, qt_app=app)
            print(f"DEBUG_HITL_NODE: main_window_instance from run_application is: {main_window_instance} (type: {type(main_window_instance)})")
            if main_window_instance:
                # If using an existing app, runner.run_application returns the MainWindow instance.
                # We must wait for it to finish using a QEventLoop tied to its sessionTerminatedSignal.
                print("hitl_node_run: Using existing QApplication. Waiting for session to terminate...")
                event_loop = QApplication.QEventLoop()
                main_window_instance.backend.sessionTerminatedSignal.connect(event_loop.quit)
                main_window_instance.show() # Ensure the window is shown so it can be interacted with / closed.
                event_loop.exec_() # This blocks until event_loop.quit() is called by the signal.
                final_data = main_window_instance.backend.logic.get_final_data()
            else: # If main_window_instance is None (e.g., run_application failed to return a window)
                final_data = None

        return final_data

    except Exception as e:
        print(f"Error in hitl_node_run: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == '__main__':
    # This is an example of how to use hitl_node_run
    # Ensure you are in the project root or PYTHONPATH is set correctly.
    print("Running hitl_node_run example...")

    # Example 1: Simple string content, default config
    # test_content_string = "This is the initial string content for the HITL tool."
    # print(f"\n--- Running with simple string: '{test_content_string}' ---")
    # result_string = hitl_node_run(test_content_string)
    # if result_string:
    #     print("--- HITL tool finished (string input) ---")
    #     print("Final data:")
    #     print(json.dumps(result_string, indent=2))
    # else:
    #     print("HITL tool execution failed or was cancelled (string input).")

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

    print(f"\n--- Running with dictionary input and custom config: {custom_config_example_path} ---")
    # Ensure QApplication instance exists for this example run if not managed by hitl_node_run internally
    # q_app = QApplication.instance() or QApplication(sys.argv)

    result_dict = hitl_node_run(test_content_dict, custom_config_path=custom_config_example_path) #, existing_qt_app=q_app)

    if result_dict:
        print("--- HITL tool finished (dict input) ---")
        print("Final data:")
        print(json.dumps(result_dict, indent=2))
    else:
        print("HITL tool execution failed or was cancelled (dict input).")

    # Clean up dummy config
    if os.path.exists(custom_config_example_path):
        # os.remove(custom_config_example_path) # Keep for user to inspect
        print(f"Test custom config kept at: {custom_config_example_path}")
        pass

    # Example with existing QApplication (more advanced, requires careful setup)
    # print("\n--- Running with existing QApplication (simulated) ---")
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
    #     print("--- HITL tool finished (existing app) ---")
    #     print(json.dumps(result_existing_app, indent=2))
    # else:
    #     print("HITL tool execution failed or was cancelled (existing app scenario).")
    #
    # if existing_app_instance and not QApplication.instance().closingDown():
    #     # If we created it here for the test, we might need to exec and quit.
    #     # This part is tricky because the event loop management is external.
    #     # For this example, we'll assume this test instance of existing_app isn't part of a larger running app.
    #     # existing_app_instance.exec_() # This would start a new loop if one isn't running.
    #     pass

    print("\n--- hitl_node_run example finished ---")

# To make sure the __init__.py is aware of this function for easier import
# (e.g., from themule_atomic_hitl import hitl_node_run)
# this would be done in __init__.py, not here.

print("hitl_node.py created with hitl_node_run function.")

# src/themule_atomic_hitl/runner.py
"""
This module is responsible for running the PyQt5 application,
which hosts the web-based UI for the Surgical Editor.
It sets up the main window, the web engine view, and the communication
channel (QWebChannel) between the Python backend (SurgicalEditorLogic)
and the JavaScript frontend.
"""

import sys
import os
import json # Still needed for final data dump
from typing import Dict, Any, Optional, Union # Optional added, Union added
from PyQt5.QtCore import QObject, pyqtSlot, QUrl, pyqtSignal
from PyQt5.QtWidgets import QApplication, QMainWindow

from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWebChannel import QWebChannel

from .core import SurgicalEditorLogic
from .config import Config # Import the new Config class

# Using main's _load_json_file for now as it's more robust with error handling

def _load_json_file(path: str) -> Dict[str, Any]:
    """
    Helper function to load data from a JSON file.

    Args:
        path (str): The path to the JSON file.

    Returns:
        Dict[str, Any]: The loaded JSON data as a dictionary, or an empty dictionary on error.
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading JSON from {path}: {e}")
        return {}

class Backend(QObject):
    """
    The Backend class acts as a bridge between the pure Python logic
    (SurgicalEditorLogic) and the JavaScript UI. It exposes Python methods (slots)
    to JavaScript and emits signals from Python that JavaScript can listen to.

    Signals:
        updateViewSignal: Emitted to tell the JS UI to refresh its display with new data.

                          Passes data dict, config dict, and queue_info dict.
        showDiffPreviewSignal: Emitted to show a diff preview to the user.
                               Passes original snippet, edited snippet, and context strings.
        requestClarificationSignal: Emitted when the core logic needs more input from the user for a task.
        showErrorSignal: Emitted to display an error message in the UI.
        promptUserToConfirmLocationSignal: Emitted to ask the user to confirm a located text snippet.
                                           Passes location details dict, original hint string, original instruction string.
        sessionTerminatedSignal: Emitted when the session is ended by the user, allowing graceful shutdown
                                 or data retrieval by a calling library.
    """

    # Signal to update the entire view in JavaScript
    updateViewSignal = pyqtSignal(dict, dict, dict, name="updateView")

    # Signal to show a diff preview in JavaScript

    showDiffPreviewSignal = pyqtSignal(str, str, str, str, name="showDiffPreview")

    # Signal to request clarification from the user for an active LLM task
    requestClarificationSignal = pyqtSignal(name="requestClarification")

    # Signal to show an error message in JavaScript
    showErrorSignal = pyqtSignal(str, name="showError")

    # Signal to prompt the user to confirm the location of a snippet found by the locator

    promptUserToConfirmLocationSignal = pyqtSignal(dict, str, str, name="promptUserToConfirmLocation")

    # Signal to indicate session termination, so the calling function can retrieve data
    sessionTerminatedSignal = pyqtSignal()

    def __init__(self, initial_data: Dict[str, Any], config_manager: Config, parent: Optional[QObject] = None):
        """
        Initializes the Backend object.

        Args:
            initial_data (Dict[str, Any]): The initial data for the editor.
            config_manager (Config): The Config object containing configuration settings.
            parent (Optional[QObject]): The parent QObject, if any.
        """
        super().__init__(parent)
        self.config_manager = config_manager # Store the Config object


        # Define callbacks that SurgicalEditorLogic will use to communicate back to this Backend
        logic_callbacks = {
            'update_view': self.on_update_view,
            'show_diff_preview': self.on_show_diff_preview,
            'request_clarification': self.on_request_clarification,
            'show_error': self.on_show_error,
            'confirm_location_details': self.on_confirm_location_details,
        }

        # Instantiate the core logic engine, passing the Config object
        self.logic = SurgicalEditorLogic(initial_data, self.config_manager, logic_callbacks)

    # --- Methods called by Core Logic (SurgicalEditorLogic) to signal the UI via this Backend ---

    def on_update_view(self, data: Dict[str, Any], config_dict: Dict[str, Any], queue_info: Dict[str, Any]):
        """
        Callback executed by SurgicalEditorLogic. Emits updateViewSignal to JS.
        Args:
            data: The current data state.
            config_dict: The configuration dictionary (from config_manager.get_config()).
            queue_info: Information about the task queue.
        """
        self.updateViewSignal.emit(data, config_dict, queue_info)


    def on_show_diff_preview(self, original_snippet: str, edited_snippet: str, before_context: str, after_context: str):
        """
        Callback executed by SurgicalEditorLogic. Emits showDiffPreviewSignal to JS.
        """
        self.showDiffPreviewSignal.emit(original_snippet, edited_snippet, before_context, after_context)

    def on_request_clarification(self):
        """
        Callback executed by SurgicalEditorLogic. Emits requestClarificationSignal to JS.
        """
        self.requestClarificationSignal.emit()

    def on_show_error(self, msg: str):
        """
        Callback executed by SurgicalEditorLogic. Emits showErrorSignal to JS.
        """
        self.showErrorSignal.emit(msg)

    def on_confirm_location_details(self, location_info: dict, original_hint: str, original_instruction: str):
        """
        Callback executed by SurgicalEditorLogic when a snippet has been located.
        Emits promptUserToConfirmLocationSignal to JS.
        """
        self.promptUserToConfirmLocationSignal.emit(location_info, original_hint, original_instruction)

    # --- Slots called by JavaScript UI to drive the Core Logic (SurgicalEditorLogic) ---

    @pyqtSlot(result=dict)
    def getInitialPayload(self) -> Dict[str, Any]:
        """
        Slot called by JS on startup to get the initial data and config.
        Returns:
            Dict[str, Any]: A dictionary containing the initial 'config' (as dict) and 'data'.
        """
        # Pass the raw dict from config manager
        return {"config": self.logic.config_manager.get_config(), "data": self.logic.data}


    @pyqtSlot()
    def startSession(self):
        """
        Slot called by JS to start the editing session in the core logic.
        """
        self.logic.start_session()

    @pyqtSlot(str, str)
    def submitEditRequest(self, hint: str, instruction: str):
        """
        Slot called by JS to submit a new edit request (hint and instruction).
        """
        self.logic.add_edit_request(hint, instruction)

    @pyqtSlot(dict, str)
    def submitConfirmedLocationAndInstruction(self, confirmed_location_details: Dict[str, Any], original_instruction: str):
        """
        Slot called by JS after the user has confirmed/adjusted the snippet location.
        """
        self.logic.proceed_with_edit_after_location_confirmation(confirmed_location_details, original_instruction)

    @pyqtSlot(str, str)
    def submitClarificationForActiveTask(self, new_hint: str, new_instruction: str):
        """
        Slot called by JS when providing new hint/instruction for a task awaiting clarification.
        """
        self.logic.update_active_task_and_retry(new_hint, new_instruction)

    @pyqtSlot(str, str, name="submitLLMTaskDecisionWithEdit")
    def submitLLMTaskDecisionWithEdit(self, decision: str, manually_edited_snippet: str):
        """
        Slot called by JS to submit the user's decision on an LLM-generated edit,
        potentially including a manually edited version of the snippet.
        """
        self.logic.process_llm_task_decision(decision, manually_edited_snippet if manually_edited_snippet else None)

    @pyqtSlot(str)
    def submitLLMTaskDecision(self, decision: str):
        """
        Slot called by JS to submit the user's decision (approve/reject/cancel)
        without any manual edits to the snippet.
        """
        self.logic.process_llm_task_decision(decision, None)

    @pyqtSlot(str, dict)
    def performAction(self, action_name: str, payload: Dict[str, Any]):
        """
        Slot called by JS to perform generic actions like 'approve_main_content', 'revert', etc.
        """
        self.logic.perform_action(action_name, payload)
        # Auto-termination for primary actions is removed here for cleaner runner.
        # The primary action in the UI should directly call terminateSession if that's desired.
        # Example: if self.config_manager.get_action_config(action_name).get("isPrimary", False):
        # self.terminateSession()

    @pyqtSlot()
    def terminateSession(self):
        """
        Slot called by JS when the user wants to terminate the session (e.g. final approval).
        Retrieves final data, prints it and audit trail to console, and emits sessionTerminatedSignal.
        """
        final_data = self.logic.get_final_data()

        print("\n--- SESSION TERMINATED BY USER ---")
        main_text_field = self.logic.main_text_field # from core logic via config
        if main_text_field and main_text_field in final_data:
             print(f"Final Content ({main_text_field}):\n{final_data[main_text_field]}")
        else:

            print("Final main text field not found or not configured in final_data.")
            
        print("\nFull Final Data:\n" + json.dumps(final_data, indent=2))
        print("\nAudit Trail (Edit Results):")
        print(json.dumps(self.logic.edit_results, indent=2))

        self.sessionTerminatedSignal.emit() # Emit signal for library use
        # Do not call QApplication.quit() here to allow external management



class MainWindow(QMainWindow):
    """
    The main application window, which hosts the QWebEngineView for the UI.
    It initializes the Backend, QWebChannel, and loads the frontend HTML.
    """
    def __init__(self,
                 initial_data: Dict[str, Any],
                 config_manager: Config, # Uses Config object
                 app_instance: QApplication, # Expects the QApplication instance
                 parent: Optional[QObject] = None):

        """
        Initializes the MainWindow.

        Args:
            initial_data (Dict[str, Any]): The initial data for the editor.

            config_manager (Config): The Config object for UI and behavior settings.
            app_instance (QApplication): The current QApplication instance.
            parent (Optional[QObject]): The parent QObject, if any.
        """
        super().__init__(parent)
        self.app = app_instance # Store the app instance
        self.config_manager = config_manager
        self.setWindowTitle(self.config_manager.window_title) # Use Config object for title
        self.setGeometry(100, 100, 1200, 800) # x, y, width, height

        self.view = QWebEngineView() # The widget that will display the HTML/JS UI
        self.channel = QWebChannel() # Facilitates communication between Python and JS

        # Create the Backend instance, passing the Config object
        self.backend = Backend(initial_data, self.config_manager, self) # Pass self as parent
        self.backend.sessionTerminatedSignal.connect(self.on_session_terminated) # Connect the signal


        # Register the backend object with the channel, making it accessible to JS
        self.channel.registerObject("backend", self.backend)
        # Set the web channel on the web page
        self.view.page().setWebChannel(self.channel)

        # Construct the path to the index.html file for the frontend

        # Assumes index.html is in a 'frontend' subdirectory relative to this script

        base_dir = os.path.dirname(os.path.abspath(__file__)) # Directory of runner.py
        html_path = os.path.join(base_dir, "frontend", "index.html")

        if not os.path.exists(html_path):

            # Attempt fallback similar to 'main' branch logic if primary path fails
            alt_html_path = os.path.join(base_dir, "..", "frontend", "index.html") # Assuming frontend might be one level up from package
            if os.path.exists(alt_html_path):
                html_path = alt_html_path
                print(f"Found index.html at fallback path: {html_path}")
            else:
                # More specific fallback if src is part of path
                alt_html_path_src = os.path.join(os.path.dirname(base_dir), "frontend", "index.html")
                if os.path.exists(alt_html_path_src):
                     html_path = alt_html_path_src
                     print(f"Found index.html at src fallback path: {html_path}")
                else:
                    print(f"ERROR: index.html not found at primary path {html_path} or common fallbacks.")
                    # Consider loading a placeholder or raising error if critical


        # Load the HTML file into the web view
        self.view.setUrl(QUrl.fromLocalFile(html_path))
        self.setCentralWidget(self.view) # Make the web view the main content of the window


    def on_session_terminated(self):
        """Closes the window when the backend signals termination."""
        print("MainWindow: Session terminated signal received, closing window.")
        self.close() # This will allow app.exec_() to return if this window is the main one.

# The _load_json_file helper is at the top of the file.
# It's renamed from _load_data_file (my version) to _load_json_file (main's version) for consistency.

def run_application(initial_data_param: Dict[str, Any],
                      config_param: Config,
                      qt_app: Optional[QApplication] = None) -> Optional[Union[Dict[str,Any], QMainWindow]]:
    """
    Main function to set up and run the PyQt5 application GUI.
    This version is designed for library usage, allowing an existing QApplication
    to be passed and returning data or the window instance.

    Args:
        initial_data_param (Dict[str, Any]): The initial data dictionary.
        config_param (Config): The Config object for UI and behavior settings.
        qt_app (Optional[QApplication]): Optional existing QApplication instance.
            If None, a new one is created and its event loop is executed.
            If provided, this function will not run the event loop.

    Returns:
        Optional[Union[Dict[str,Any], QMainWindow]]:
            - If `qt_app` is None (new app loop managed here): Returns the final data dictionary
              after the UI session, or None if an error occurred.
            - If `qt_app` is provided (external app loop): Returns the MainWindow instance,
              or None if an error occurred. The caller is responsible for the event loop.
    """
    if not initial_data_param:
        print(f"Error: Initial data is empty. Application cannot start.")
        return None

    app = qt_app
    created_new_app = False
    if app is None:
        app = QApplication.instance() # Check if an instance already exists
        if app is None:
            print("run_application: Creating new QApplication instance.")
            app = QApplication(sys.argv)
            created_new_app = True
        else:
            print("run_application: Using existing QApplication instance found by QApplication.instance().")
    else:
        print("run_application: Using provided existing QApplication instance.")

    if app is None: # Should not happen if QApplication(sys.argv) was successful
        print("Error: Could not obtain/create QApplication instance.")
        return None

    main_window = MainWindow(
        initial_data=initial_data_param,
        config_manager=config_param,
        app_instance=app
    )
    main_window.show() # Display the main window

    if created_new_app and qt_app is None: # Only run exec_ if we created the app AND no app was passed in
        print("run_application: Starting new QApplication event loop.")
        # exit_code = app.exec_() # This would block and wait for sys.exit
        # For library function, better to let it run and return data after close
        app.exec_() # Run event loop; MainWindow.close() will stop it.
        print(f"run_application: QApplication event loop finished.")
        return main_window.backend.logic.get_final_data() # Return final data after UI closes
    else: # Existing app instance was provided or found, or we are not to block here
        print("run_application: Not starting new event loop (or using existing), assuming external management for event loop if qt_app was provided.")
        return main_window # Return the window instance for the caller to manage


# Example of how to run this for standalone mode (illustrative, actual call from hitl_node.py or examples script)
if __name__ == '__main__':
    print("runner.py executed directly (for illustration of standalone-like execution).")

    # This example demonstrates how one might call run_application if it were
    # the primary entry point, similar to how hitl_node_run would use it.

    # 1. Create Config object (e.g., from a file or default)
    #    For this example, find examples/config.json relative to project root
    #    Assumes runner.py is in src/themule_atomic_hitl/
    project_root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    example_config_path = os.path.join(project_root_dir, "examples", "config.json")
    if not os.path.exists(example_config_path):
        print(f"Illustrative run: Example config not found at {example_config_path}, using default config.")
        app_config = Config() # Default config
    else:
        print(f"Illustrative run: Loading config from {example_config_path}")
        app_config = Config(custom_config_path=example_config_path)

    # 2. Load initial data (e.g., from a file or created in memory)
    example_data_path = os.path.join(project_root_dir, "examples", "sample_data.json") # Updated name
    initial_app_data = None
    if os.path.exists(example_data_path):
        print(f"Illustrative run: Loading initial data from {example_data_path}")
        initial_app_data = _load_json_file(example_data_path)

    if not initial_app_data:
        print("Illustrative run: Sample data file not found or empty. Using minimal default data.")
        # Use main_editor_modified_field from config to structure default data
        m_field = app_config.main_editor_modified_field
        o_field = app_config.main_editor_original_field
        initial_app_data = {
            m_field: "Default content for direct runner.py execution.",
            o_field: "Default content for direct runner.py execution.",
            "status": "Illustrative Run"
        }

    # 3. Run the application (managing its own QApplication loop by passing qt_app=None)
    final_run_data = run_application(initial_app_data, app_config, qt_app=None)

    if final_run_data and isinstance(final_run_data, dict): # Check if it's data
        print("\n--- run_application (standalone mode) returned final data ---")
        print(json.dumps(final_run_data, indent=2))
    elif final_run_data: # It's a MainWindow instance, meaning event loop wasn't run here
        print("\n--- run_application (library mode) returned MainWindow instance ---")
        print("Illustrative run: Event loop would need to be managed by caller.")
    else:
        print("run_application (standalone mode) did not return data as expected or failed.")


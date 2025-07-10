# src/themule_atomic_hitl/runner.py
import sys
import os
import json # Still needed for final data dump
from typing import Dict, Any, Optional # Optional added
from PyQt5.QtCore import QObject, pyqtSlot, QUrl, pyqtSignal
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWebChannel import QWebChannel

from .core import SurgicalEditorLogic
from .config import Config # Import the new Config class

# _load_json_file helper is no longer needed here if Config handles all JSON loading for config
# and data loading is handled before calling run_application or by the new library entry point.
# However, run_application still uses it for data_file_path.

class Backend(QObject):
    """The bridge between the pure Python logic (SurgicalEditorLogic) and the JS UI."""

    updateViewSignal = pyqtSignal(dict, dict, dict, name="updateView") # data, config_dict, queue_info
    showDiffPreviewSignal = pyqtSignal(str, str, str, str, name="showDiffPreview") # original, edited, before_context, after_context
    requestClarificationSignal = pyqtSignal(name="requestClarification")
    showErrorSignal = pyqtSignal(str, name="showError")
    promptUserToConfirmLocationSignal = pyqtSignal(dict, str, str, name="promptUserToConfirmLocation")

    # Signal to indicate session termination, so the calling function can retrieve data
    sessionTerminatedSignal = pyqtSignal()

    def __init__(self, initial_data: Dict[str, Any], config_manager: Config, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.config_manager = config_manager # Store the Config object
        logic_callbacks = {
            'update_view': self.on_update_view,
            'show_diff_preview': self.on_show_diff_preview,
            'request_clarification': self.on_request_clarification,
            'show_error': self.on_show_error,
            'confirm_location_details': self.on_confirm_location_details,
        }
        # Pass the Config object to SurgicalEditorLogic
        self.logic = SurgicalEditorLogic(initial_data, self.config_manager, logic_callbacks)

    # --- Methods called by Core Logic to signal the UI ---
    def on_update_view(self, data: Dict[str, Any], config: Dict[str, Any], queue_info: Dict[str, Any]):
        self.updateViewSignal.emit(data, config, queue_info)

    def on_show_diff_preview(self, original_snippet, edited_snippet, before_context, after_context):
        self.showDiffPreviewSignal.emit(original_snippet, edited_snippet, before_context, after_context)

    def on_request_clarification(self):
        self.requestClarificationSignal.emit()

    def on_show_error(self, msg: str):
        self.showErrorSignal.emit(msg)

    def on_confirm_location_details(self, location_info: dict, original_hint: str, original_instruction: str):
        """Called by core.SurgicalEditorLogic when a snippet has been located."""
        self.promptUserToConfirmLocationSignal.emit(location_info, original_hint, original_instruction)

    # --- Slots called by JavaScript UI to drive the Core Logic ---
    @pyqtSlot(result=dict)
    def getInitialPayload(self):
        # Pass the raw dict from config manager
        return {"config": self.logic.config_manager.get_config(), "data": self.logic.data}

    @pyqtSlot()
    def startSession(self):
        self.logic.start_session()

    @pyqtSlot(str, str)
    def submitEditRequest(self, hint: str, instruction: str):
        self.logic.add_edit_request(hint, instruction)

    @pyqtSlot(dict, str)
    def submitConfirmedLocationAndInstruction(self, confirmed_location_details: Dict[str, Any], original_instruction: str):
        self.logic.proceed_with_edit_after_location_confirmation(confirmed_location_details, original_instruction)

    @pyqtSlot(str, str)
    def submitClarificationForActiveTask(self, new_hint: str, new_instruction: str):
        self.logic.update_active_task_and_retry(new_hint, new_instruction)

    @pyqtSlot(str, str, name="submitLLMTaskDecisionWithEdit")
    def submitLLMTaskDecisionWithEdit(self, decision: str, manually_edited_snippet: str):
        self.logic.process_llm_task_decision(decision, manually_edited_snippet if manually_edited_snippet else None)

    @pyqtSlot(str)
    def submitLLMTaskDecision(self, decision: str):
        self.logic.process_llm_task_decision(decision, None)

    @pyqtSlot(str, dict)
    def performAction(self, action_name: str, payload: Dict[str, Any]):
        self.logic.perform_action(action_name, payload)
        # Check if this action should terminate the session (e.g. "approve_main_content")
        # This logic might be better placed within SurgicalEditorLogic or defined in config
        if action_name == self.config_manager.get_config().get("actions", [{}])[0].get("name", "approve_main_content"): #TODO improve this check
             if self.config_manager.get_action_config(action_name).get("isPrimary", False): # Assuming primary action also terminates
                self.terminateSession()


    @pyqtSlot()
    def terminateSession(self):
        final_data = self.logic.get_final_data()
        print("\n--- SESSION TERMINATED BY USER ---")
        main_text_field = self.logic.main_text_field # from core logic via config
        if main_text_field and main_text_field in final_data:
             print(f"Final Content ({main_text_field}):\n{final_data[main_text_field]}")
        else:
            print("Final main text field not found or not configured.")
        print("\nFull Final Data:\n" + json.dumps(final_data, indent=2))
        print("\nAudit Trail:")
        print(json.dumps(self.logic.edit_results, indent=2))

        self.sessionTerminatedSignal.emit() # Emit signal
        # QApplication.quit() # Do not quit here, let the caller manage app lifecycle

class MainWindow(QMainWindow):
    def __init__(self, initial_data: Dict[str, Any], config_manager: Config, app_instance: QApplication, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.app = app_instance # Store the app instance
        self.config_manager = config_manager
        self.setWindowTitle(self.config_manager.window_title) # Use config for title
        self.setGeometry(100, 100, 1200, 800)

        self.view = QWebEngineView()
        self.channel = QWebChannel()

        self.backend = Backend(initial_data, self.config_manager)
        self.backend.sessionTerminatedSignal.connect(self.on_session_terminated) # Connect the signal
        self.channel.registerObject("backend", self.backend)
        self.view.page().setWebChannel(self.channel)

        base_dir = os.path.dirname(os.path.abspath(__file__))
        html_path = os.path.join(base_dir, "frontend", "index.html")

        if not os.path.exists(html_path):
            print(f"ERROR: index.html not found at {html_path}")
            # Consider raising an exception or handling this more gracefully

        self.view.setUrl(QUrl.fromLocalFile(html_path))
        self.setCentralWidget(self.view)

    def on_session_terminated(self):
        """Closes the window when the backend signals termination."""
        print("MainWindow: Session terminated signal received, closing window.")
        self.close()


# Helper to load JSON data file (config is handled by Config class)
def _load_data_file(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading JSON data from {path}: {e}")
        return None

def run_application(initial_data_param: Dict[str, Any], # Changed from data_file_path
                      config_param: Config, # Changed from config_file_path to Config object
                      qt_app: Optional[QApplication] = None): # Allow passing existing QApplication
    """
    Runs the HITL application GUI.
    :param initial_data_param: The initial data dictionary.
    :param config_param: The Config object.
    :param qt_app: Optional existing QApplication instance. If None, a new one is created.
                   This is useful for library mode where the event loop might be managed externally.
    """
    if not initial_data_param:
        print(f"Error: Initial data is empty. Cannot start.")
        # Depending on how this is called, might raise error or return status
        return None # Or raise error

    app = qt_app
    if app is None:
        # Check if an instance already exists, otherwise create one
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        # else:
            # print("run_application: Using existing QApplication instance.")

    main_window = MainWindow(initial_data=initial_data_param, config_manager=config_param, app_instance=app)
    main_window.show()

    if qt_app is None: # Only run exec_ if we created the app here
        # print("run_application: Starting new QApplication event loop.")
        exit_code = app.exec_()
        # print(f"run_application: QApplication event loop finished with exit code {exit_code}.")
        return main_window.backend.logic.get_final_data() # Return final data after UI closes
    else:
        # print("run_application: Not starting new event loop, assuming external management.")
        # If called with an existing app, the caller is responsible for the event loop.
        # We might need a way to signal completion or make this call blocking.
        # For now, it returns the main_window, and the caller can connect to its signals.
        return main_window # Or potentially block here until main_window.closed() signal


# Example of how to run this for standalone mode (e.g. from examples/run_tool.py)
if __name__ == '__main__':
    # This is illustrative. Actual execution would be from a script that prepares these.
    print("runner.py executed directly (for illustration).")

    # 1. Create Config object (e.g., from a file or default)
    #    For this example, assume examples/config.json relative to project root
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    default_config_for_run = Config(os.path.join(project_root, "examples", "config.json"))

    # 2. Load initial data (e.g., from a file)
    sample_data_path = os.path.join(project_root, "examples", "data.json") # will be renamed
    loaded_initial_data = _load_data_file(sample_data_path)

    if loaded_initial_data:
        # 3. Run the application
        final_data_from_run = run_application(loaded_initial_data, default_config_for_run)
        if final_data_from_run:
            print("\n--- run_application returned final data ---")
            print(json.dumps(final_data_from_run, indent=2))
        else:
            print("run_application did not return data (e.g. error or external event loop).")
    else:
        print(f"Could not load sample data from {sample_data_path}")

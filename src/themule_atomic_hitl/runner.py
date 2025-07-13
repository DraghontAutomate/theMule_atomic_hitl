# src/themule_atomic_hitl/runner.py
"""
This module is responsible for running the PyQt5 application,
which hosts the web-based UI for the Surgical Editor.
It sets up the main window, the web engine view, and the communication
channel (QWebChannel) between the Python backend (SurgicalEditorLogic)
and the JavaScript frontend.
"""
import logging
logger = logging.getLogger(__name__)
# The first logger.debug will only appear if basicConfig was called before this module is imported.
# If examples/run_tool.py is the entry point and configures logging first, this is fine.
logger.debug("RUNNER.PY: Module imported/loaded")

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
    updateViewSignal = pyqtSignal(object, object, object, name="updateView") # dict -> object

    # Signal to show a diff preview in JavaScript

    showDiffPreviewSignal = pyqtSignal(str, str, str, str, name="showDiffPreview")

    # Signal to request clarification from the user for an active LLM task
    requestClarificationSignal = pyqtSignal(name="requestClarification")

    # Signal to show an error message in JavaScript
    showErrorSignal = pyqtSignal(str, name="showError")

    # Signal to prompt the user to confirm the location of a snippet found by the locator

    promptUserToConfirmLocationSignal = pyqtSignal(object, str, str, name="promptUserToConfirmLocation") # dict -> object

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

    @pyqtSlot(result=str)
    def getInitialPayload(self) -> str:
        """
        Slot called by JS on startup to get the initial data and config.
        Returns:
            str: A JSON string representing the config and data.
        """
        logger.debug("BACKEND (getInitialPayload): Called by JavaScript.")
        config_data = self.logic.config_manager.get_config() # This is already a dict
        data_data = self.logic.data # This is a dict
        logger.debug(f"BACKEND (getInitialPayload): Config type: {type(config_data)}, Data type: {type(data_data)}")
        payload = {"config": config_data, "data": data_data}
        try:
            json_payload = json.dumps(payload)
            logger.debug(f"BACKEND (getInitialPayload): Returning JSON string payload (length: {len(json_payload)}).")
            return json_payload
        except Exception as e:
            logger.error(f"BACKEND (getInitialPayload): Error during json.dumps: {e}")
            # Return a JSON string indicating an error, so JS can still parse it
            return json.dumps({"error": str(e), "message": "Failed to serialize payload in getInitialPayload"})


    @pyqtSlot()
    def startSession(self):
        """
        Slot called by JS to start the editing session in the core logic.
        """
        logger.debug("BACKEND (startSession): Called by JavaScript.")
        try:
            self.logic.start_session()
            logger.debug("BACKEND (startSession): self.logic.start_session() returned.")
        except Exception as e:
            logger.error(f"BACKEND (startSession): Error during self.logic.start_session(): {e}")
            # If self.showErrorSignal is available and connected, emit it
            if hasattr(self, 'showErrorSignal') and self.showErrorSignal is not None:
                 try:
                     self.showErrorSignal.emit(f"Error in startSession: {str(e)}")
                 except Exception as sig_e:
                     logger.error(f"BACKEND (startSession): Error emitting showErrorSignal: {sig_e}")


    @pyqtSlot(str) # Argument is now a single JSON string
    def submitEditRequest(self, request_payload_json: str):
        """
        Slot called by JS to submit a new edit request.
        The request_payload_json is a JSON string containing either:
        - { type: "hint_based", hint: "...", instruction: "..." }
        - { type: "selection_specific", selection_details: { text: "...", ...lines/cols... }, instruction: "..." }
        """
        try:
            payload = json.loads(request_payload_json)
            logger.debug(f"BACKEND (submitEditRequest): Received payload: {payload}")

            request_type = payload.get("type")
            instruction = payload.get("instruction")

            if not request_type or not instruction:
                logger.error(f"BACKEND (submitEditRequest): Invalid payload, missing type or instruction: {payload}")
                self.showErrorSignal.emit("Invalid edit request: type or instruction missing.")
                return

            if request_type == "hint_based":
                hint = payload.get("hint")
                if hint is None: # Check for None explicitly, as empty string might be valid for some reason
                    logger.error(f"BACKEND (submitEditRequest): Missing hint for hint_based request: {payload}")
                    self.showErrorSignal.emit("Invalid hint-based request: hint missing.")
                    return
                self.logic.add_edit_request(
                    instruction=instruction,
                    request_type=request_type,
                    hint=hint,
                    selection_details=None
                )
            elif request_type == "selection_specific":
                selection_details = payload.get("selection_details")
                if not selection_details or not isinstance(selection_details, dict):
                    logger.error(f"BACKEND (submitEditRequest): Missing or invalid selection_details for selection_specific request: {payload}")
                    self.showErrorSignal.emit("Invalid selection-specific request: selection_details missing or invalid.")
                    return
                self.logic.add_edit_request(
                    instruction=instruction,
                    request_type=request_type,
                    hint=None,
                    selection_details=selection_details
                )
            else:
                logger.error(f"BACKEND (submitEditRequest): Unknown request type: {request_type}")
                self.showErrorSignal.emit(f"Unknown edit request type: {request_type}")

        except json.JSONDecodeError as e:
            logger.error(f"BACKEND (submitEditRequest): JSONDecodeError: {e}. Payload was: {request_payload_json}")
            self.showErrorSignal.emit(f"Error decoding edit request: {e}")
        except Exception as e:
            logger.error(f"BACKEND (submitEditRequest): Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            self.showErrorSignal.emit(f"Internal error processing edit request: {e}")

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
                 config_dict_param: Dict[str, Any], # Changed
                 app_instance: QApplication, # Expects the QApplication instance
                 parent: Optional[QObject] = None):

        """
        Initializes the MainWindow.

        Args:
            initial_data (Dict[str, Any]): The initial data for the editor.
            config_dict_param (Dict[str, Any]): The configuration dictionary. # Changed
            app_instance (QApplication): The current QApplication instance.
            parent (Optional[QObject]): The parent QObject, if any.
        """
        super().__init__(parent)
        self.app = app_instance # Store the app instance

        # Create Config object from the dictionary
        self.config_manager = Config(custom_config_dict=config_dict_param) # Use custom_config_dict

        self.setWindowTitle(self.config_manager.window_title)
        self.setGeometry(100, 100, 1200, 800)

        self.view = QWebEngineView()
        self.channel = QWebChannel()

        # Create the Backend instance, passing the Config object
        self.backend = Backend(initial_data, self.config_manager, self)
        self.backend.sessionTerminatedSignal.connect(self.on_session_terminated)


        # Register the backend object with the channel, making it accessible to JS
        self.channel.registerObject("backend", self.backend)
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
                      config_param_dict: Dict[str, Any], # Changed
                      qt_app: Optional[QApplication] = None) -> Optional[Union[Dict[str,Any], QMainWindow]]:
    """
    Main function to set up and run the PyQt5 application GUI.
    This version is designed for library usage, allowing an existing QApplication
    to be passed and returning data or the window instance.

    Args:
        initial_data_param (Dict[str, Any]): The initial data dictionary.
        config_param_dict (Dict[str, Any]): The configuration dictionary. # Changed
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
    logger.debug("RUNNER.PY: run_application called.")
    logger.debug(f"RUNNER.PY: run_application initial_data type: {type(initial_data_param)}, config_param_dict type: {type(config_param_dict)}, qt_app type: {type(qt_app)}")
    if not initial_data_param:
        logger.error("RUNNER.PY: Initial data is empty. Application cannot start.")
        return None

    app = qt_app
    created_new_app = False
    app_instance_to_use = qt_app
    should_run_event_loop_here = False

    if app_instance_to_use is None:
        app_instance_to_use = QApplication.instance()
        if app_instance_to_use is None:
            logger.debug("RUNNER.PY: No existing QApplication found, creating new instance.")
            app_instance_to_use = QApplication([]) # Use empty list
            should_run_event_loop_here = True
        else:
            logger.debug("RUNNER.PY: Using existing QApplication instance found by QApplication.instance(). Event loop assumed managed externally or by prior call.")
            should_run_event_loop_here = False
    else:
        logger.debug("RUNNER.PY: Using provided existing QApplication instance. Event loop managed by caller.")
        should_run_event_loop_here = False

    if app_instance_to_use is None:
        logger.error("RUNNER.PY: Could not obtain/create QApplication instance.")
        return None

    logger.debug("RUNNER.PY: Creating MainWindow instance.")
    main_window = MainWindow(
        initial_data=initial_data_param,
        config_dict_param=config_param_dict, # Pass dict
        app_instance=app_instance_to_use
    )
    logger.debug("RUNNER.PY: MainWindow instance created. Calling show().")
    main_window.show()
    logger.debug("RUNNER.PY: MainWindow.show() called.")

    if should_run_event_loop_here:
        logger.debug("RUNNER.PY: Starting new QApplication event loop (blocking).")
        app_instance_to_use.exec_()
        logger.debug("RUNNER.PY: QApplication event loop finished.")
        return main_window.backend.logic.get_final_data()
    else:
        logger.debug("RUNNER.PY: Returning MainWindow instance; event loop managed by caller or already running.")
        return main_window

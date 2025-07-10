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
import json
from typing import Dict, Any
from PyQt5.QtCore import QObject, pyqtSlot, QUrl, pyqtSignal
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtWebEngineWidgets import QWebEngineView # For displaying web content
from PyQt5.QtWebChannel import QWebChannel # For Python-JS communication
from .core import SurgicalEditorLogic # The core application logic

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
        showDiffPreviewSignal: Emitted to show a diff preview to the user.
        requestClarificationSignal: Emitted when the core logic needs more input from the user for a task.
        showErrorSignal: Emitted to display an error message in the UI.
        promptUserToConfirmLocationSignal: Emitted to ask the user to confirm a located text snippet.
    """

    # Signal to update the entire view in JavaScript
    # Passes data, config, and queue_info dictionaries
    updateViewSignal = pyqtSignal(dict, dict, dict, name="updateView")

    # Signal to show a diff preview in JavaScript
    # Passes original snippet, edited snippet, and context before/after the snippet
    showDiffPreviewSignal = pyqtSignal(str, str, str, str, name="showDiffPreview")

    # Signal to request clarification from the user for an active LLM task
    requestClarificationSignal = pyqtSignal(name="requestClarification")

    # Signal to show an error message in JavaScript
    showErrorSignal = pyqtSignal(str, name="showError")

    # Signal to prompt the user to confirm the location of a snippet found by the locator
    # Passes location details, the original hint, and the original instruction
    promptUserToConfirmLocationSignal = pyqtSignal(dict, str, str, name="promptUserToConfirmLocation")

    def __init__(self, initial_data: Dict[str, Any], config: Dict[str, Any], parent=None):
        """
        Initializes the Backend object.

        Args:
            initial_data (Dict[str, Any]): The initial data for the editor.
            config (Dict[str, Any]): Configuration settings for the editor.
            parent (Optional[QObject]): The parent QObject, if any.
        """
        super().__init__(parent)
        # Define callbacks that SurgicalEditorLogic will use to communicate back to this Backend
        logic_callbacks = {
            'update_view': self.on_update_view,
            'show_diff_preview': self.on_show_diff_preview,
            'request_clarification': self.on_request_clarification,
            'show_error': self.on_show_error,
            'confirm_location_details': self.on_confirm_location_details,
        }
        # Instantiate the core logic engine
        self.logic = SurgicalEditorLogic(initial_data, config, logic_callbacks)

    # --- Methods called by Core Logic (SurgicalEditorLogic) to signal the UI via this Backend ---

    def on_update_view(self, data: Dict[str, Any], config: Dict[str, Any], queue_info: Dict[str, Any]):
        """
        Callback executed by SurgicalEditorLogic. Emits updateViewSignal to JS.
        """
        self.updateViewSignal.emit(data, config, queue_info)

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
            Dict[str, Any]: A dictionary containing the initial 'config' and 'data'.
        """
        return {"config": self.logic.config, "data": self.logic.data}

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

    @pyqtSlot()
    def terminateSession(self):
        """
        Slot called by JS when the user wants to terminate the session.
        Prints final data and audit trail to console, then quits the application.
        """
        print("\n--- SESSION TERMINATED BY USER ---")
        if self.logic.main_text_field and self.logic.main_text_field in self.logic.data:
             print(f"Final Content ({self.logic.main_text_field}):\n{self.logic.data[self.logic.main_text_field]}")
        else:
            print("Final main text field not found or not configured in self.logic.data.")
        print("\nFull Final Data:\n" + json.dumps(self.logic.data, indent=2))
        print("\nAudit Trail (Edit Results):")
        print(json.dumps(self.logic.edit_results, indent=2))
        QApplication.instance().quit() # type: ignore

class MainWindow(QMainWindow):
    """
    The main application window, which hosts the QWebEngineView for the UI.
    """
    def __init__(self, initial_data: Dict[str, Any], config: Dict[str, Any], parent=None):
        """
        Initializes the MainWindow.

        Args:
            initial_data (Dict[str, Any]): The initial data for the editor.
            config (Dict[str, Any]): Configuration settings for the editor.
            parent (Optional[QWidget]): The parent widget, if any.
        """
        super().__init__(parent)
        self.setWindowTitle("TheMule Atomic HITL (Enhanced UI)")
        self.setGeometry(100, 100, 1200, 800) # x, y, width, height

        self.view = QWebEngineView() # The widget that will display the HTML/JS UI
        self.channel = QWebChannel() # Facilitates communication between Python and JS

        # Create the Backend instance, which holds the core logic
        self.backend = Backend(initial_data, config, self) # Pass self as parent
        # Register the backend object with the channel, making it accessible to JS
        self.channel.registerObject("backend", self.backend)
        # Set the web channel on the web page
        self.view.page().setWebChannel(self.channel)

        # Construct the path to the index.html file for the frontend
        # Assumes index.html is in a 'frontend' subdirectory relative to this script
        base_dir = os.path.dirname(os.path.abspath(__file__)) # Directory of runner.py
        html_path = os.path.join(base_dir, "frontend", "index.html")

        if not os.path.exists(html_path):
            # Fallback for running from project root or different structures
            alt_base_dir = os.path.join(base_dir, "..", "src", "themule_atomic_hitl")
            alt_html_path = os.path.join(alt_base_dir, "frontend", "index.html")
            if os.path.exists(alt_html_path):
                html_path = alt_html_path
            else:
                print(f"ERROR: index.html not found at expected paths: {html_path} or {alt_html_path}")
                # Potentially exit or load a placeholder page
                # For now, it will try to load the original path and likely fail if not found.

        # Load the HTML file into the web view
        self.view.setUrl(QUrl.fromLocalFile(html_path))
        self.setCentralWidget(self.view) # Make the web view the main content of the window

def run_application(data_file_path: str, config_file_path: str):
    """
    Main function to set up and run the PyQt5 application.

    Args:
        data_file_path (str): Path to the JSON file containing the initial data.
        config_file_path (str): Path to the JSON file containing the configuration.
    """
    initial_data = _load_json_file(data_file_path)
    config = _load_json_file(config_file_path)

    if not initial_data:
        print(f"Error: Failed to load initial data from '{data_file_path}'. Application cannot start.")
        sys.exit(1) # Exit if essential data is missing
    if not config:
        print(f"Error: Failed to load configuration from '{config_file_path}'. Application cannot start.")
        sys.exit(1) # Exit if essential config is missing

    # Every PyQt application must have one QApplication instance.
    app = QApplication.instance() # Check if an instance already exists
    if not app: # Create QApplication if it doesn't exist
        app = QApplication(sys.argv)

    main_window = MainWindow(initial_data=initial_data, config=config)
    main_window.show() # Display the main window

    # Start the Qt event loop. Execution blocks here until the application is quit.
    sys.exit(app.exec_())

# src/themule_atomic_hitl/runner.py
import sys
import os
import json
from typing import Dict, Any
from PyQt5.QtCore import QObject, pyqtSlot, QUrl, pyqtSignal
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWebChannel import QWebChannel
from .core import SurgicalEditorLogic

# Helper to load JSON files
def _load_json_file(path: str) -> Dict[str, Any]:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading JSON from {path}: {e}")
        return {}


class Backend(QObject):
    """The bridge between the pure Python logic (SurgicalEditorLogic) and the JS UI."""

    # Signal to send data, config, and queue_info to UI
    # updateViewSignal = pyqtSignal(dict, dict, name="updateView") # Old: data, config
    updateViewSignal = pyqtSignal(dict, dict, dict, name="updateView") # New: data, config, queue_info

    # Signals for the atomic edit cycle remain useful
    showDiffPreviewSignal = pyqtSignal(str, str, str, str, name="showDiffPreview") # original, edited, before_context, after_context
    requestClarificationSignal = pyqtSignal(name="requestClarification") # For snippet editing
    showErrorSignal = pyqtSignal(str, name="showError")

    def __init__(self, initial_data: Dict[str, Any], config: Dict[str, Any], parent=None):
        super().__init__(parent)
        logic_callbacks = {
            'update_view': self.on_update_view, # Changed from 'show_main_view'
            'show_diff_preview': self.on_show_diff_preview,
            'request_clarification': self.on_request_clarification,
            'show_error': self.on_show_error,
        }
        # SurgicalEditorLogic now initialized with data and config
        self.logic = SurgicalEditorLogic(initial_data, config, logic_callbacks)

    # --- Methods called by Core Logic to signal the UI ---
    def on_update_view(self, data: Dict[str, Any], config: Dict[str, Any]):
        self.updateViewSignal.emit(data, config)

    def on_show_diff_preview(self, original_snippet, edited_snippet, before_context, after_context):
        self.showDiffPreviewSignal.emit(original_snippet, edited_snippet, before_context, after_context)

    def on_request_clarification(self):
        self.requestClarificationSignal.emit() # This is for the snippet clarification

    def on_show_error(self, msg: str):
        self.showErrorSignal.emit(msg)

    # --- Slots called by JavaScript UI to drive the Core Logic ---
    @pyqtSlot(result=dict)
    def getInitialPayload(self):
        """
        Called by JS on load to get both config and initial data.
        Mirrors the concept from the new main.py's Bridge.
        """
        return {"config": self.logic.config, "data": self.logic.data}

    @pyqtSlot()
    def startSession(self):
        """
        Starts the session. The core logic will call the 'update_view' callback,
        which in turn emits `updateViewSignal` with initial data and config.
        The JS side might call getInitialPayload first, then startSession, or
        startSession could be the primary trigger for the first updateViewSignal.
        Let's assume startSession triggers the first full update.
        """
        self.logic.start_session()


    # Methods for the atomic text editing cycle (largely unchanged in signature)
    @pyqtSlot(str, str)
    def submitHintAndInstruction(self, hint: str, instruction: str): # Renamed for clarity
        self.logic.start_edit_cycle(hint, instruction)

    @pyqtSlot(str, str)
    def submitClarificationForSnippet(self, hint: str, instruction: str): # Renamed for clarity
        self.logic.retry_edit_cycle_with_clarification(hint, instruction)

    @pyqtSlot(str)
    def submitSnippetDecision(self, decision: str): # Renamed for clarity
        # 'decision' is 'approve', 'reject', or 'cancel' for the snippet
        self.logic.process_user_decision_for_snippet(decision)

    # New generic action slot
    @pyqtSlot(str, dict)
    def performAction(self, action_name: str, payload: Dict[str, Any]):
        """
        Generic slot to trigger actions in SurgicalEditorLogic.
        Payload contains any additional data needed for the action.
        Example: action_name="approve_main_content", payload={"author": "User", "reviewNotes": "LGTM"}
        """
        self.logic.perform_action(action_name, payload)
        # Core logic's perform_action will call _notify_view_update,
        # which triggers on_update_view -> updateViewSignal.

    @pyqtSlot()
    def terminateSession(self):
        print("\n--- SESSION TERMINATED BY USER ---")
        # Accessing data through the property/structure in logic
        if self.logic.main_text_field and self.logic.main_text_field in self.logic.data:
             print("Final Text ("+ self.logic.main_text_field +"):\n" + self.logic.data[self.logic.main_text_field])
        else:
            print("Final main text field not found or not configured.")
        print("\nFull Final Data:\n" + json.dumps(self.logic.data, indent=2))
        print("\nAudit Trail:")
        print(json.dumps(self.logic.edit_results, indent=2))
        QApplication.quit()


class MainWindow(QMainWindow):
    """The main application window hosting the web view."""
    # Now needs initial_data and config for Backend
    def __init__(self, initial_data: Dict[str, Any], config: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.setWindowTitle("TheMule Atomic HITL (Enhanced)")
        self.setGeometry(100, 100, 1200, 800)

        self.view = QWebEngineView()
        self.channel = QWebChannel()

        # Backend now takes initial_data and config
        self.backend = Backend(initial_data, config)
        self.channel.registerObject("backend", self.backend) # Expose backend to JS under 'backend'
        self.view.page().setWebChannel(self.channel)

        # Construct path to index.html relative to this file's location
        # __file__ is src/themule_atomic_hitl/runner.py
        # We want src/themule_atomic_hitl/frontend/index.html
        base_dir = os.path.dirname(os.path.abspath(__file__))
        html_path = os.path.join(base_dir, "frontend", "index.html")

        if not os.path.exists(html_path):
            print(f"ERROR: index.html not found at {html_path}")
            # Fallback or error handling if HTML file is missing
            # For now, we'll let it proceed and QtWebEngineView will show an error.

        self.view.setUrl(QUrl.fromLocalFile(html_path))
        self.setCentralWidget(self.view)

# run_application now needs to load data and config
def run_application(data_file_path: str, config_file_path: str):
    """
    Loads data and config, then creates and runs the PyQt application.
    """
    initial_data = _load_json_file(data_file_path)
    config = _load_json_file(config_file_path)

    if not initial_data: # or check for essential keys
        print(f"Error: Failed to load initial data from {data_file_path}. Cannot start.")
        sys.exit(1)
    if not config: # or check for essential keys
        print(f"Error: Failed to load config from {config_file_path}. Cannot start.")
        sys.exit(1)

    app = QApplication(sys.argv)
    # Pass the loaded data and config to MainWindow
    main_window = MainWindow(initial_data=initial_data, config=config)
    main_window.show()
    sys.exit(app.exec_())

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

    updateViewSignal = pyqtSignal(dict, dict, dict, name="updateView") # data, config, queue_info

    showDiffPreviewSignal = pyqtSignal(str, str, str, str, name="showDiffPreview") # original, edited, before_context, after_context
    requestClarificationSignal = pyqtSignal(name="requestClarification") # For active LLM task clarification
    showErrorSignal = pyqtSignal(str, name="showError")

    # New signal for location confirmation step
    promptUserToConfirmLocationSignal = pyqtSignal(dict, str, str, name="promptUserToConfirmLocation") # location_info, original_hint, original_instruction

    def __init__(self, initial_data: Dict[str, Any], config: Dict[str, Any], parent=None):
        super().__init__(parent)
        logic_callbacks = {
            'update_view': self.on_update_view,
            'show_diff_preview': self.on_show_diff_preview,
            'request_clarification': self.on_request_clarification,
            'show_error': self.on_show_error,
            'confirm_location_details': self.on_confirm_location_details, # New callback from core
        }
        self.logic = SurgicalEditorLogic(initial_data, config, logic_callbacks)

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
        return {"config": self.logic.config, "data": self.logic.data}

    @pyqtSlot()
    def startSession(self):
        self.logic.start_session()

    @pyqtSlot(str, str)
    def submitEditRequest(self, hint: str, instruction: str):
        self.logic.add_edit_request(hint, instruction)

    @pyqtSlot(dict, str) # confirmed_location_details (dict), original_instruction (str)
    def submitConfirmedLocationAndInstruction(self, confirmed_location_details: Dict[str, Any], original_instruction: str):
        self.logic.proceed_with_edit_after_location_confirmation(confirmed_location_details, original_instruction)

    @pyqtSlot(str, str)
    def submitClarificationForActiveTask(self, new_hint: str, new_instruction: str):
        self.logic.update_active_task_and_retry(new_hint, new_instruction)

    @pyqtSlot(str, str, name="submitLLMTaskDecisionWithEdit") # decision, manually_edited_snippet (can be empty)
    def submitLLMTaskDecisionWithEdit(self, decision: str, manually_edited_snippet: str):
        self.logic.process_llm_task_decision(decision, manually_edited_snippet if manually_edited_snippet else None)

    @pyqtSlot(str)
    def submitLLMTaskDecision(self, decision: str):
        self.logic.process_llm_task_decision(decision, None)

    @pyqtSlot(str, dict)
    def performAction(self, action_name: str, payload: Dict[str, Any]):
        self.logic.perform_action(action_name, payload)

    @pyqtSlot()
    def terminateSession(self):
        print("\n--- SESSION TERMINATED BY USER ---")
        if self.logic.main_text_field and self.logic.main_text_field in self.logic.data:
             print(f"Final Content ({self.logic.main_text_field}):\n{self.logic.data[self.logic.main_text_field]}")
        else:
            print("Final main text field not found or not configured.")
        print("\nFull Final Data:\n" + json.dumps(self.logic.data, indent=2))
        print("\nAudit Trail:")
        print(json.dumps(self.logic.edit_results, indent=2))
        QApplication.quit()

class MainWindow(QMainWindow):
    def __init__(self, initial_data: Dict[str, Any], config: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.setWindowTitle("TheMule Atomic HITL (Enhanced)")
        self.setGeometry(100, 100, 1200, 800)

        self.view = QWebEngineView()
        self.channel = QWebChannel()

        self.backend = Backend(initial_data, config)
        self.channel.registerObject("backend", self.backend)
        self.view.page().setWebChannel(self.channel)

        base_dir = os.path.dirname(os.path.abspath(__file__))
        html_path = os.path.join(base_dir, "frontend", "index.html")

        if not os.path.exists(html_path):
            print(f"ERROR: index.html not found at {html_path}")

        self.view.setUrl(QUrl.fromLocalFile(html_path))
        self.setCentralWidget(self.view)

def run_application(data_file_path: str, config_file_path: str):
    initial_data = _load_json_file(data_file_path)
    config = _load_json_file(config_file_path)

    if not initial_data:
        print(f"Error: Failed to load initial data from {data_file_path}. Cannot start.")
        sys.exit(1)
    if not config:
        print(f"Error: Failed to load config from {config_file_path}. Cannot start.")
        sys.exit(1)

    app = QApplication(sys.argv)
    main_window = MainWindow(initial_data=initial_data, config=config)
    main_window.show()
    sys.exit(app.exec_())

# src/themule_atomic_hitl/core.py
import re
import uuid
import json
from typing import Callable, Dict, Any, Optional, Tuple
from collections import deque

class SurgicalEditorLogic:
    """
    Implements the queued, two-loop (Gatekeeper/Worker) editing logic.
    The core engine, UI-agnostic, communicating via callbacks.
    Manages a queue of edit requests and processes them atomically.
    """
    def __init__(self,
                 initial_data: Dict[str, Any],
                 config: Dict[str, Any],
                 callbacks: Dict[str, Callable]):
        """
        Initializes the logic engine.

        Args:
            initial_data: The starting dataset (e.g., from data.json).
            config: The configuration (e.g., from config.json).
            callbacks: A dictionary of functions to call for UI updates.
                       Expected keys: 'update_view', 'show_diff_preview',
                                      'request_clarification', 'show_error'.
        """
        self.data = initial_data
        self._initial_data_snapshot = json.loads(json.dumps(initial_data)) # Deep copy for revert
        self.config = config
        self.edit_results = []
        self.callbacks = callbacks

        self.edit_request_queue: deque[Tuple[str, str, str]] = deque() # (hint, instruction, original_content_snapshot_for_task)
        self.active_edit_task: Optional[Dict[str, Any]] = None # Stores current task being processed
        self.pending_llm_edit: Optional[Dict[str, Any]] = None # Stores provisional edit from LLM for active task

        self.main_text_field = None
        self.original_text_field = None
        if self.config.get('fields'):
            for field_config in self.config['fields']:
                if field_config.get('type') == 'diff-editor':
                    self.main_text_field = field_config.get('modifiedDataField')
                    self.original_text_field = field_config.get('originalDataField')
                    break
        if not self.main_text_field:
            print("Warning: No 'diff-editor' with 'modifiedDataField' found in config. Text editing might not work as expected.")
            self.main_text_field = "editedText"
            self.original_text_field = "originalText"

    @property
    def current_main_content(self) -> str:
        return self.data.get(self.main_text_field, "")

    @current_main_content.setter
    def current_main_content(self, value: str):
        self.data[self.main_text_field] = value

    def start_session(self):
        self._notify_view_update()
        self._process_next_edit_request()

    def _notify_view_update(self):
        queue_info = {"size": len(self.edit_request_queue), "is_processing": bool(self.active_edit_task)}
        self.callbacks['update_view'](self.data, self.config, queue_info)

    def add_edit_request(self, hint: str, instruction: str):
        print(f"CORE_LOGIC: Adding edit request. Hint='{hint}'")
        snapshot = self.current_main_content
        self.edit_request_queue.append((hint, instruction, snapshot))
        self._notify_view_update()
        if not self.active_edit_task:
            self._process_next_edit_request()

    def _process_next_edit_request(self):
        if self.active_edit_task:
            print("CORE_LOGIC: Already processing an active task. New task will wait.")
            return
        if not self.edit_request_queue:
            print("CORE_LOGIC: Edit request queue is empty.")
            self._notify_view_update()
            return

        hint, instruction, original_content_snapshot = self.edit_request_queue.popleft()
        self.active_edit_task = {
            "hint": hint,
            "instruction": instruction,
            "original_content_snapshot": original_content_snapshot
        }
        self.pending_llm_edit = None
        print(f"CORE_LOGIC: Starting processing of task. Hint='{hint}'")
        self._notify_view_update()
        self._execute_llm_attempt()

    def _execute_llm_attempt(self):
        if not self.active_edit_task:
            self.callbacks['show_error']("LLM attempt called without an active task.")
            return

        hint = self.active_edit_task['hint']
        instruction = self.active_edit_task['instruction']
        content_to_edit = self.active_edit_task['original_content_snapshot']

        location = self._mock_llm_locator(content_to_edit, hint)
        if not location:
            self.callbacks['show_error']("Locator failed to find a match for the hint.")
            self._notify_view_update()
            return

        edited_snippet = self._mock_llm_editor(location['snippet'], instruction)

        self.pending_llm_edit = {
            "start": location['start_idx'],
            "end": location['end_idx'],
            "original_snippet": location['snippet'],
            "edited_snippet": edited_snippet,
        }

        self.callbacks['show_diff_preview'](
            location['snippet'],
            edited_snippet,
            content_to_edit[max(0, location['start_idx']-50):location['start_idx']],
            content_to_edit[location['end_idx']:location['end_idx']+50]
        )
        self._notify_view_update()

    def process_llm_task_decision(self, decision: str):
        if not self.active_edit_task or self.pending_llm_edit is None:
            self.callbacks['show_error']("User decision received but no active task or pending edit.")
            return

        print(f"CORE_LOGIC: User decision for LLM task is '{decision}'")

        if decision == 'approve':
            start = self.pending_llm_edit['start']
            end = self.pending_llm_edit['end']
            original_content = self.active_edit_task['original_content_snapshot']
            edited_snippet = self.pending_llm_edit['edited_snippet']

            new_content = original_content[:start] + edited_snippet + original_content[end:]
            self.current_main_content = new_content

            self.edit_results.append({
                "id": str(uuid.uuid4()), "status": "task_approved",
                "message": f"Approved LLM edit for hint: '{self.active_edit_task['hint']}'"
            })
            self.active_edit_task = None
            self.pending_llm_edit = None
            self._notify_view_update()
            self._process_next_edit_request()

        elif decision == 'reject':
            self.pending_llm_edit = None
            self.callbacks['request_clarification']()
            self._notify_view_update()

        elif decision == 'cancel':
            self.edit_results.append({
                "id": str(uuid.uuid4()), "status": "task_cancelled",
                "message": f"User cancelled LLM edit task for hint: '{self.active_edit_task['hint']}'"
            })
            self.active_edit_task = None
            self.pending_llm_edit = None
            self._notify_view_update()
            self._process_next_edit_request()

        else:
            self.callbacks['show_error'](f"Unknown decision: {decision}")

    def update_active_task_and_retry(self, new_hint: str, new_instruction: str):
        if not self.active_edit_task:
            self.callbacks['show_error']("Clarification received, but no active task to update.")
            return

        print("CORE_LOGIC: Retrying active task with new clarification.")
        self.active_edit_task['hint'] = new_hint if new_hint else self.active_edit_task['hint']
        self.active_edit_task['instruction'] = new_instruction if new_instruction else self.active_edit_task['instruction']
        self.pending_llm_edit = None

        self._notify_view_update()
        self._execute_llm_attempt()

    def perform_action(self, action_name: str, payload: Optional[Dict[str, Any]] = None):
        if payload is None:
            payload = {}

        handler_method_name = f"handle_{action_name}"
        handler_method = getattr(self, handler_method_name, self.handle_unknown_action)

        print(f"CORE_LOGIC: Received generic action '{action_name}' with payload: {payload}")
        try:
            handler_method(payload)
            self.edit_results.append({
                "id": str(uuid.uuid4()), "status": f"action_{action_name}_success",
                "message": f"Action '{action_name}' performed."
            })
        except Exception as e:
            print(f"Error executing generic action {action_name}: {e}")
            self.callbacks['show_error'](f"Error during action '{action_name}': {str(e)}")
            self.edit_results.append({
                "id": str(uuid.uuid4()), "status": f"action_{action_name}_failed",
                "message": f"Action '{action_name}' failed: {str(e)}"
            })
        self._notify_view_update()

    def handle_approve_main_content(self, payload: Dict[str, Any]):
        print("CORE_LOGIC: Handling general approve_main_content action.")
        if self.main_text_field in payload:
            self.current_main_content = payload[self.main_text_field]
        for key, value in payload.items():
            if key != self.main_text_field and key in self.data:
                self.data[key] = value
        self.data["status"] = "Content Approved (General)"
        print(f"--- General content approval. Data: {self.data} ---")

    def handle_increment_version(self, payload: Dict[str, Any]):
        current_version = self.data.get("version", 0.0)
        if isinstance(current_version, (int, float)):
            self.data["version"] = round(current_version + 0.1, 1)
        else:
            try:
                self.data["version"] = round(float(current_version) + 0.1, 1)
            except ValueError:
                self.data["version"] = 0.1
                print(f"Warning: Could not parse version '{current_version}'. Resetting to 0.1.")
        self.data["status"] = "Version updated."

    def handle_revert_changes(self, payload: Dict[str, Any]):
        self.data = json.loads(json.dumps(self._initial_data_snapshot))
        self.data["status"] = "Changes Reverted."

    def handle_unknown_action(self, payload: Dict[str, Any]):
        print(f"Warning: Unknown generic action received by SurgicalEditorLogic.")
        self.callbacks['show_error']("Unknown generic action requested.")

    def _mock_llm_locator(self, text_to_search: str, hint: str) -> Dict[str, Any] | None:
        match = re.search(re.escape(hint), text_to_search, re.IGNORECASE)
        if match:
            start_idx, end_idx = match.span()
            return {"start_idx": start_idx, "end_idx": end_idx, "snippet": match.group(0)}
        return None

    def _mock_llm_editor(self, snippet_to_edit: str, instruction: str) -> str:
        return f"EDITED based on '{instruction}': [{snippet_to_edit.upper()}]"

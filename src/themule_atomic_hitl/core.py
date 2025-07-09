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
        self.data = initial_data
        self._initial_data_snapshot = json.loads(json.dumps(initial_data))
        self.config = config
        self.edit_results = []
        self.callbacks = callbacks

        self.edit_request_queue: deque[Tuple[str, str, str]] = deque()
        self.active_edit_task: Optional[Dict[str, Any]] = None

        self.main_text_field = None
        self.original_text_field = None
        if self.config.get('fields'):
            for field_config in self.config['fields']:
                if field_config.get('type') == 'diff-editor':
                    self.main_text_field = field_config.get('modifiedDataField')
                    self.original_text_field = field_config.get('originalDataField')
                    break
        if not self.main_text_field:
            print("Warning: No 'diff-editor' with 'modifiedDataField' found in config.")
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
        queue_info = {
            "size": len(self.edit_request_queue),
            "is_processing": bool(self.active_edit_task)
        }
        if self.active_edit_task:
            queue_info['active_task_status'] = self.active_edit_task.get('status')
            queue_info['active_task_hint'] = self.active_edit_task.get('user_hint')
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
            "user_hint": hint,
            "user_instruction": instruction,
            "original_content_snapshot": original_content_snapshot,
            "status": "locating_snippet",
            "location_info": None,
            "llm_generated_snippet_details": None
        }
        print(f"CORE_LOGIC: Starting processing of task. Hint='{hint}'")
        self._notify_view_update()
        self._execute_llm_attempt()

    def _execute_llm_attempt(self):
        if not self.active_edit_task:
            self.callbacks['show_error']("LLM attempt called without an active task.")
            return

        current_hint = self.active_edit_task['user_hint']
        content_to_edit = self.active_edit_task['original_content_snapshot']
        location = self._mock_llm_locator(content_to_edit, current_hint)

        if not location:
            self.callbacks['show_error'](f"Locator failed to find a match for the hint: '{current_hint}'")
            self.active_edit_task['status'] = 'location_failed'
            self._notify_view_update()
            # Consider how to handle this: auto-cancel task or await user action?
            # For now, it stays in this state until user cancels or provides new info for this task.
            return

        self.active_edit_task['location_info'] = location
        self.active_edit_task['status'] = 'awaiting_location_confirmation'
        self.callbacks['confirm_location_details'](
            location,
            self.active_edit_task['user_hint'],
            self.active_edit_task['user_instruction']
        )
        self._notify_view_update()

    def proceed_with_edit_after_location_confirmation(self, confirmed_hint_or_location_details: Dict, original_instruction: str):
        if not self.active_edit_task or self.active_edit_task['status'] != 'awaiting_location_confirmation':
            self.callbacks['show_error']("Proceed with edit called in an invalid state.")
            return

        # Assuming confirmed_hint_or_location_details is the validated/adjusted location_info
        # Potentially, if it's just a new hint string, we might need to re-run locator.
        # For now, we assume it's a dict with 'snippet' and its coordinates.
        location_to_use = confirmed_hint_or_location_details
        if not (isinstance(location_to_use, dict) and 'snippet' in location_to_use and
                'start_idx' in location_to_use and 'end_idx' in location_to_use):
            self.callbacks['show_error']("Invalid confirmed_location_details provided.")
            self.active_edit_task['status'] = 'error_in_location_confirmation' # new status
            self._notify_view_update()
            return

        self.active_edit_task['location_info'] = location_to_use # Store confirmed location

        snippet_to_edit = location_to_use['snippet']
        edited_snippet = self._mock_llm_editor(snippet_to_edit, original_instruction)

        self.active_edit_task['llm_generated_snippet_details'] = {
            "start": location_to_use['start_idx'],
            "end": location_to_use['end_idx'],
            "original_snippet": snippet_to_edit,
            "edited_snippet": edited_snippet
        }
        self.active_edit_task['status'] = 'awaiting_diff_approval'
        content_for_diff_context = self.active_edit_task['original_content_snapshot']
        self.callbacks['show_diff_preview'](
            snippet_to_edit,
            edited_snippet,
            content_for_diff_context[max(0, location_to_use['start_idx']-50) : location_to_use['start_idx']],
            content_for_diff_context[location_to_use['end_idx'] : location_to_use['end_idx']+50]
        )
        self._notify_view_update()

    def process_llm_task_decision(self, decision: str, manually_edited_snippet: Optional[str] = None):
        if not self.active_edit_task or self.active_edit_task['status'] != 'awaiting_diff_approval' or \
           self.active_edit_task.get('llm_generated_snippet_details') is None:
            self.callbacks['show_error']("User decision received but task is not in 'awaiting_diff_approval' state or has no snippet.")
            return

        print(f"CORE_LOGIC: User decision for LLM task is '{decision}'")
        snippet_details = self.active_edit_task['llm_generated_snippet_details']

        if decision == 'approve':
            start = snippet_details['start']
            end = snippet_details['end']
            original_content = self.active_edit_task['original_content_snapshot']
            snippet_to_apply = manually_edited_snippet if manually_edited_snippet is not None else snippet_details['edited_snippet']

            new_content = original_content[:start] + snippet_to_apply + original_content[end:]
            self.current_main_content = new_content

            self.edit_results.append({
                "id": str(uuid.uuid4()), "status": "task_approved",
                "message": f"Approved LLM edit for hint: '{self.active_edit_task['user_hint']}'"
            })
            self.active_edit_task = None
            self._notify_view_update()
            self._process_next_edit_request()

        elif decision == 'reject':
            self.active_edit_task['status'] = 'awaiting_clarification'
            self.callbacks['request_clarification']()
            self._notify_view_update()

        elif decision == 'cancel':
            self.edit_results.append({
                "id": str(uuid.uuid4()), "status": "task_cancelled",
                "message": f"User cancelled LLM edit task for hint: '{self.active_edit_task['user_hint']}'"
            })
            self.active_edit_task = None
            self._notify_view_update()
            self._process_next_edit_request()

        else:
            self.callbacks['show_error'](f"Unknown decision: {decision}")

    def update_active_task_and_retry(self, new_hint: str, new_instruction: str):
        if not self.active_edit_task or self.active_edit_task['status'] != 'awaiting_clarification':
            self.callbacks['show_error']("Clarification received, but no active task to update or not awaiting clarification.")
            return

        print("CORE_LOGIC: Retrying active task with new clarification.")
        self.active_edit_task['user_hint'] = new_hint if new_hint else self.active_edit_task['user_hint']
        self.active_edit_task['user_instruction'] = new_instruction if new_instruction else self.active_edit_task['user_instruction']
        self.active_edit_task['status'] = 'locating_snippet'
        self.active_edit_task['location_info'] = None
        self.active_edit_task['llm_generated_snippet_details'] = None
        self._notify_view_update()
        self._execute_llm_attempt()

    def perform_action(self, action_name: str, payload: Optional[Dict[str, Any]] = None):
        # ... (rest of the generic action methods remain the same as before) ...
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

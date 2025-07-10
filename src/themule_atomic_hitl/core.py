# src/themule_atomic_hitl/core.py
import re
import uuid
import json
from typing import Callable, Dict, Any, Optional, Tuple
from collections import deque
from .config import Config # Import the new Config class

class SurgicalEditorLogic:
    """
    Implements the queued, two-loop (Gatekeeper/Worker) editing logic.
    This class is the core engine, designed to be UI-agnostic, communicating
    with a user interface (or other front-end) through a set of callbacks.
    It manages a queue of edit requests and processes them atomically,
    allowing for human review and intervention at key stages.

    The "two-loop" refers to:
    1. Gatekeeper Loop: User provides a hint and instruction. System locates the snippet. User confirms/corrects location.
    2. Worker Loop: System generates an edit for the confirmed snippet. User reviews diff, can edit, approve, or reject.

    Attributes:
        data (Dict[str, Any]): The current state of the data being edited.
        _initial_data_snapshot (Dict[str, Any]): A deep copy of the initial data, used for revert functionality.
        config_manager (Config): The Config object holding configuration settings.
        edit_results (list): A log of completed edit tasks and their outcomes.
        callbacks (Dict[str, Callable]): A dictionary of callback functions to interact with the UI.
            Expected callbacks:
                - 'update_view': To refresh the UI with the current data, config, and queue status.
                - 'show_error': To display error messages to the user.
                - 'confirm_location_details': To ask the user to confirm the located snippet.
                - 'show_diff_preview': To show the user a diff of the original and edited snippet.
                - 'request_clarification': To ask the user for more information if an edit is rejected.
        edit_request_queue (deque[Tuple[str, str, str]]): A queue for pending edit requests.
            Each tuple contains (user_hint, user_instruction, content_snapshot_at_request_time).
        active_edit_task (Optional[Dict[str, Any]]): Stores details of the currently processed edit task.
        main_text_field (str): The key in `self.data` that holds the primary text content to be edited.
        original_text_field (str): The key in `self.data` that might hold an original version for diffing (if configured).
    """
    def __init__(self,
                 initial_data: Dict[str, Any],
                 config: Config, # Uses Config object
                 callbacks: Dict[str, Callable]):
        """
        Initializes the SurgicalEditorLogic.

        Args:
            initial_data (Dict[str, Any]): The initial data to be edited.
            config (Config): The Config object for the editor.
            callbacks (Dict[str, Callable]): Callbacks for UI interaction.
        """
        self.data = initial_data
        self._initial_data_snapshot = json.loads(json.dumps(initial_data)) # Deep copy for revert
        self.config_manager = config # Store the Config object
        self.edit_results = []  # Stores results of processed edits
        self.callbacks = callbacks

        # Queue for edit requests: (hint, instruction, original_content_snapshot)
        self.edit_request_queue: deque[Tuple[str, str, str]] = deque()
        self.active_edit_task: Optional[Dict[str, Any]] = None # Details of the current task being processed

        # Use properties from Config object to get field names
        self.main_text_field = self.config_manager.main_editor_modified_field
        self.original_text_field = self.config_manager.main_editor_original_field

        # Ensure initial data has the necessary fields if they are missing
        if self.main_text_field not in self.data:
            self.data[self.main_text_field] = "" # Initialize if not present
        if self.original_text_field not in self.data:
            # If original_text_field is not in initial_data,
            # initialize it with the content of main_text_field.
            # This ensures that the diff editor has a baseline if only one text field was provided.
            self.data[self.original_text_field] = self.data[self.main_text_field]


    @property
    def current_main_content(self) -> str:
        """
        Gets the current content of the main text field.

        Returns:
            str: The text content.
        """
        return self.data.get(self.main_text_field, "")

    @current_main_content.setter
    def current_main_content(self, value: str):
        """
        Sets the content of the main text field.

        Args:
            value (str): The new text content.
        """
        self.data[self.main_text_field] = value

    def get_final_data(self) -> Dict[str, Any]:
        """Returns the current state of the data, typically after session completion."""
        return self.data

    def start_session(self):
        """
        Starts the editing session.
        Initializes or verifies the original text field for diffing based on the snapshot
        of initial data. Notifies the view for an initial update and attempts to process
        the first edit request if any are queued.
        """
        # Ensure the original text field in data is correctly set from the snapshot
        # if it wasn't set from initial_data directly for the diff editor.
        # This is important if only 'editedText' (main_text_field) was provided initially.
        if self.original_text_field not in self._initial_data_snapshot:
             # If original_text_field wasn't in the explicit initial data,
             # its snapshot value should be based on the initial main_text_field.
             self._initial_data_snapshot[self.original_text_field] = self._initial_data_snapshot.get(self.main_text_field, "")

        # Update self.data's original_text_field to match the snapshot if it's different
        # or wasn't properly set up in __init__ (e.g., if original_text_field was initially absent).
        # This ensures the UI's diff editor gets the correct original baseline from the true initial state.
        current_original_in_data = self.data.get(self.original_text_field)
        snapshot_original = self._initial_data_snapshot.get(self.original_text_field, "") # Fallback to empty string

        if current_original_in_data != snapshot_original:
            self.data[self.original_text_field] = snapshot_original
            # Also ensure the snapshot reflects this if it was derived, for revert consistency.
            if self.original_text_field not in self._initial_data_snapshot:
                 self._initial_data_snapshot[self.original_text_field] = snapshot_original


        self._notify_view_update()
        self._process_next_edit_request()

    def _notify_view_update(self):
        """
        Notifies the UI to update its view by calling the 'update_view' callback.
        Passes current data, config (as dict), and information about the edit queue.
        """
        queue_info = {
            "size": len(self.edit_request_queue),
            "is_processing": bool(self.active_edit_task)
        }
        if self.active_edit_task:
            queue_info['active_task_status'] = self.active_edit_task.get('status')
            queue_info['active_task_hint'] = self.active_edit_task.get('user_hint')
        # Pass the raw dict from the config manager to the view
        self.callbacks['update_view'](self.data, self.config_manager.get_config(), queue_info)

    def add_edit_request(self, hint: str, instruction: str):
        """
        Adds a new edit request to the queue.

        An edit request consists of a 'hint' to locate the text snippet and an 'instruction'
        on how to modify it. A snapshot of the current main content is taken at the time of request.

        Args:
            hint (str): A user-provided string to help locate the snippet to be edited.
            instruction (str): User's instruction on how to edit the snippet.
        """
        print(f"CORE_LOGIC: Adding edit request. Hint='{hint}'")
        # Take a snapshot of the content AT THE TIME OF REQUEST.
        # This is crucial because subsequent edits might alter the content before this request is processed.
        # The locator should operate on this snapshot.
        snapshot = self.current_main_content
        self.edit_request_queue.append((hint, instruction, snapshot))
        self._notify_view_update()
        # If no task is currently active, start processing this new request.
        if not self.active_edit_task:
            self._process_next_edit_request()

    def _process_next_edit_request(self):
        """
        Processes the next edit request from the queue if no task is active and the queue is not empty.
        This is the entry point for the "Gatekeeper" loop.
        """
        if self.active_edit_task:
            print("CORE_LOGIC: Already processing an active task. New task will wait.")
            return
        if not self.edit_request_queue:
            print("CORE_LOGIC: Edit request queue is empty.")
            self._notify_view_update() # Ensure UI reflects empty queue status
            return

        hint, instruction, original_content_snapshot = self.edit_request_queue.popleft()
        self.active_edit_task = {
            "user_hint": hint,
            "user_instruction": instruction,
            "original_content_snapshot": original_content_snapshot, # Content when request was made
            "status": "locating_snippet", # Initial status
            "location_info": None, # To be filled by locator
            "llm_generated_snippet_details": None # To be filled by editor
        }
        print(f"CORE_LOGIC: Starting processing of task. Hint='{hint}'")
        self._notify_view_update()
        self._execute_llm_attempt() # Start the Gatekeeper loop

    def _execute_llm_attempt(self):
        """
        Executes the first part of an edit task: locating the snippet based on the user's hint.
        This uses a mock LLM locator for now.
        If successful, it asks for user confirmation of the location.
        """
        if not self.active_edit_task:
            self.callbacks['show_error']("LLM attempt called without an active task.")
            return

        current_hint = self.active_edit_task['user_hint']
        # IMPORTANT: Use the snapshot of content taken when the request was added to the queue.
        content_to_edit = self.active_edit_task['original_content_snapshot']
        location = self._mock_llm_locator(content_to_edit, current_hint)

        if not location:
            self.callbacks['show_error'](f"Locator failed to find a match for the hint: '{current_hint}'")
            self.active_edit_task['status'] = 'location_failed'
            self._notify_view_update()
            # The task remains in this failed state. User might cancel or a future feature
            # could allow providing a new hint for the *same* task.
            return

        self.active_edit_task['location_info'] = location
        self.active_edit_task['status'] = 'awaiting_location_confirmation'
        # Callback to UI to confirm the located snippet
        self.callbacks['confirm_location_details'](
            location, # Contains {'snippet', 'start_idx', 'end_idx'}
            self.active_edit_task['user_hint'],
            self.active_edit_task['user_instruction']
        )
        self._notify_view_update()

    def proceed_with_edit_after_location_confirmation(self,
                                                       confirmed_hint_or_location_details: Dict,
                                                       original_instruction: str):
        """
        Called by the UI after the user has confirmed (or corrected) the snippet location.
        This initiates the "Worker" loop: generating the edit for the confirmed snippet.

        Args:
            confirmed_hint_or_location_details (Dict): A dictionary containing the confirmed
                location details (e.g., 'snippet', 'start_idx', 'end_idx').
                This could be the original location or a corrected one from the user.
            original_instruction (str): The user's original instruction for the edit.
        """
        if not self.active_edit_task or self.active_edit_task['status'] != 'awaiting_location_confirmation':
            self.callbacks['show_error']("Proceed with edit called in an invalid state.")
            return

        location_to_use = confirmed_hint_or_location_details
        # Basic validation of the confirmed location details
        if not (isinstance(location_to_use, dict) and 'snippet' in location_to_use and
                'start_idx' in location_to_use and 'end_idx' in location_to_use):
            self.callbacks['show_error']("Invalid confirmed_location_details provided by UI.")
            self.active_edit_task['status'] = 'error_in_location_confirmation'
            self._notify_view_update()
            return

        self.active_edit_task['location_info'] = location_to_use # Store potentially adjusted location

        snippet_to_edit = location_to_use['snippet']
        # Use a mock LLM editor to generate the edited version of the snippet
        edited_snippet = self._mock_llm_editor(snippet_to_edit, original_instruction)

        self.active_edit_task['llm_generated_snippet_details'] = {
            "start": location_to_use['start_idx'],
            "end": location_to_use['end_idx'],
            "original_snippet": snippet_to_edit,
            "edited_snippet": edited_snippet
        }
        self.active_edit_task['status'] = 'awaiting_diff_approval'

        # Prepare context for the diff preview
        content_for_diff_context = self.active_edit_task['original_content_snapshot']
        context_before = content_for_diff_context[max(0, location_to_use['start_idx']-50) : location_to_use['start_idx']]
        context_after = content_for_diff_context[location_to_use['end_idx'] : location_to_use['end_idx']+50]

        # Callback to UI to show the diff and ask for approval/rejection/manual edit
        self.callbacks['show_diff_preview'](
            snippet_to_edit,
            edited_snippet,
            context_before,
            context_after
        )
        self._notify_view_update()

    def process_llm_task_decision(self, decision: str, manually_edited_snippet: Optional[str] = None):
        """
        Processes the user's decision on the LLM-generated edit.
        The user can 'approve', 'reject', or 'cancel' the task.
        If 'approve' and `manually_edited_snippet` is provided, that snippet is used.

        Args:
            decision (str): The user's decision ('approve', 'reject', 'cancel').
            manually_edited_snippet (Optional[str]): If the user manually edited the
                LLM's suggestion, this contains the user's version.
        """
        if not self.active_edit_task or self.active_edit_task['status'] != 'awaiting_diff_approval' or \
           self.active_edit_task.get('llm_generated_snippet_details') is None:
            self.callbacks['show_error']("User decision received but task is not in 'awaiting_diff_approval' state or has no snippet details.")
            return

        print(f"CORE_LOGIC: User decision for LLM task is '{decision}'")
        snippet_details = self.active_edit_task['llm_generated_snippet_details']
        # The content to modify is the snapshot taken when the request was made.
        original_content_for_this_task = self.active_edit_task['original_content_snapshot']

        if decision == 'approve':
            start = snippet_details['start']
            end = snippet_details['end']
            # Use manually edited snippet if provided, otherwise use the LLM's edited snippet
            snippet_to_apply = manually_edited_snippet if manually_edited_snippet is not None else snippet_details['edited_snippet']

            # Construct the new content based on the original snapshot for this task
            new_content_for_this_task = original_content_for_this_task[:start] + \
                                        snippet_to_apply + \
                                        original_content_for_this_task[end:]

            # IMPORTANT: Apply this change to the *current* main content.
            # This assumes that the start/end indices are still valid in the context of `original_content_for_this_task`.
            # If other edits have happened in parallel and significantly changed the structure,
            # this simple concatenation might be problematic. This system assumes atomic, sequential application
            # based on the snapshot, but applies the *result* to the live `self.current_main_content`.
            # For robust handling of concurrent edits, a more complex diff3/merge strategy would be needed
            # if the `original_content_snapshot` significantly differs from `self.current_main_content`
            # *before* this approved edit is applied.
            # However, given the queue processes one task at a time, `self.current_main_content` should
            # reflect the state *after* the previous task, and `original_content_snapshot` is the base for *this* task.
            # The critical part is that `start` and `end` relate to `original_content_snapshot`.

            # If `self.current_main_content` has changed since `original_content_snapshot` was taken
            # (e.g. due to a previously completed task), we need to be careful.
            # A simple approach: if `self.current_main_content` is *identical* to `original_content_snapshot`,
            # then we can just set `self.current_main_content = new_content_for_this_task`.
            # If it's different, it means another task completed and updated `self.current_main_content`.
            # This implies a sequential processing model where each task operates on the output of the previous.
            # The `original_content_snapshot` is primarily for the LLM's context for *this specific task*.
            # The application of the change should be to the most up-to-date `self.current_main_content`,
            # assuming the edit (snippet replacement) is still valid.
            # For this version, we'll apply the change directly to `self.current_main_content` using the
            # indices derived from `original_content_snapshot`. This is safe if the snippet identified by
            # those indices in `original_content_snapshot` is *still the same snippet* in `self.current_main_content`.
            # This is a strong assumption if other edits could modify the same areas.
            # Given the single active task model, this should be fine as `self.current_main_content`
            # would be the result of the *previous* task.

            # Let's refine: The edit was *calculated* based on `original_content_snapshot`.
            # The actual modification should be applied to `self.current_main_content`
            # by finding the *same original snippet* (if it still exists and is unique)
            # or by assuming indices are still valid if the content hasn't drifted too much.
            # For simplicity, we'll assume indices from `original_content_snapshot` are applied to it,
            # and this result becomes the new `self.current_main_content`.
            self.current_main_content = new_content_for_this_task # My version's logic

            self.edit_results.append({
                "id": str(uuid.uuid4()), "status": "task_approved",
                "message": f"Approved LLM edit for hint: '{self.active_edit_task['user_hint']}'"
            })
            self.active_edit_task = None # Clear current task
            self._notify_view_update()
            self._process_next_edit_request() # Process next in queue

        elif decision == 'reject':
            # User rejected the edit. Task status changes, and we ask for clarification.
            self.active_edit_task['status'] = 'awaiting_clarification'
            self.callbacks['request_clarification']() # UI should prompt user for new hint/instruction
            self._notify_view_update()

        elif decision == 'cancel':
            # User cancelled the task.
            self.edit_results.append({
                "id": str(uuid.uuid4()), "status": "task_cancelled",
                "message": f"User cancelled LLM edit task for hint: '{self.active_edit_task['user_hint']}'"
            })
            self.active_edit_task = None # Clear current task
            self._notify_view_update()
            self._process_next_edit_request() # Process next in queue

        else:
            self.callbacks['show_error'](f"Unknown decision: {decision}")
            # Task remains in 'awaiting_diff_approval' or could be moved to an error state.

    def update_active_task_and_retry(self, new_hint: str, new_instruction: str):
        """
        Called by the UI when the user provides clarification (new hint and/or instruction)
        for a task that was in 'awaiting_clarification' state (due to a reject).
        This effectively restarts the processing for the *active* task with new inputs.

        Args:
            new_hint (str): The new hint provided by the user.
            new_instruction (str): The new instruction provided by the user.
        """
        if not self.active_edit_task or self.active_edit_task['status'] != 'awaiting_clarification':
            self.callbacks['show_error']("Clarification received, but no active task to update or not awaiting clarification.")
            return

        print("CORE_LOGIC: Retrying active task with new clarification.")
        # Update task details with new information. The original_content_snapshot remains the same.
        self.active_edit_task['user_hint'] = new_hint if new_hint else self.active_edit_task['user_hint']
        self.active_edit_task['user_instruction'] = new_instruction if new_instruction else self.active_edit_task['user_instruction']
        self.active_edit_task['status'] = 'locating_snippet' # Reset status to start locator phase
        self.active_edit_task['location_info'] = None
        self.active_edit_task['llm_generated_snippet_details'] = None
        self._notify_view_update()
        self._execute_llm_attempt() # Retry the LLM location and edit process

    def perform_action(self, action_name: str, payload: Optional[Dict[str, Any]] = None):
        """
        Handles generic actions that are not part of the core LLM edit loop,
        such as 'approve_main_content', 'increment_version', 'revert_changes'.
        It dynamically calls a handler method based on `action_name`.

        Args:
            action_name (str): The name of the action to perform (e.g., "approve_main_content").
            payload (Optional[Dict[str, Any]]): Data associated with the action.
        """
        if payload is None:
            payload = {}
        handler_method_name = f"handle_{action_name}"
        # Get the handler method, or default to handle_unknown_action if not found
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
        self._notify_view_update() # Ensure UI reflects changes from the action

    def handle_approve_main_content(self, payload: Dict[str, Any]):
        """Handles the 'approve_main_content' action. Updates main text and other fields from payload."""
        print("CORE_LOGIC: Handling general approve_main_content action.")
        # Update the main text field if present in the payload
        if self.main_text_field in payload:
            self.current_main_content = payload[self.main_text_field]

        # Update other data fields present in the payload and also in self.data
        for key, value in payload.items():
            if key != self.main_text_field and key in self.data:
                self.data[key] = value
        self.data["status"] = "Content Approved (General)" # Example status update
        print(f"--- General content approval. Data: {self.data} ---")

    def handle_increment_version(self, payload: Dict[str, Any]):
        """Handles the 'increment_version' action. Increments a 'version' field in data."""
        current_version_str = str(self.data.get("version", "0.0")) # Ensure string for parsing
        try:
            current_version_float = float(current_version_str)
            self.data["version"] = round(current_version_float + 0.1, 1)
        except ValueError:
            self.data["version"] = 0.1 # Fallback if current version is not a valid number
            print(f"Warning: Could not parse version '{current_version_str}'. Resetting to 0.1.")
        self.data["status"] = "Version updated."

    def handle_revert_changes(self, payload: Dict[str, Any]):
        """Handles the 'revert_changes' action. Reverts data to its initial snapshot."""
        # Perform a deep copy from the snapshot to ensure no shared references
        self.data = json.loads(json.dumps(self._initial_data_snapshot))
        self.data["status"] = "Changes Reverted."

    def handle_unknown_action(self, payload: Dict[str, Any]):
        """Handles any action for which a specific handler method is not defined."""
        action_name = payload.get("action_name", "unknown") # Assuming action_name might be in payload
        print(f"Warning: Unknown generic action '{action_name}' received by SurgicalEditorLogic.")
        self.callbacks['show_error'](f"Unknown generic action '{action_name}' requested.")

    # --- Mock LLM Methods ---
    # These methods simulate interactions with an LLM for locating and editing text.
    # In a real application, these would involve calls to actual LLM services.

    def _mock_llm_locator(self, text_to_search: str, hint: str) -> Optional[Dict[str, Any]]:
        """
        Mocks an LLM call to locate a snippet of text based on a hint.
        Uses simple regex search for demonstration.

        Args:
            text_to_search (str): The text in which to search for the snippet.
            hint (str): The hint to guide the search.

        Returns:
            Optional[Dict[str, Any]]: A dictionary with 'start_idx', 'end_idx', and 'snippet'
                                      if found, otherwise None.
        """
        # Using re.escape on the hint to treat it as a literal string in the regex
        # IGNORECASE for case-insensitive matching
        match = re.search(re.escape(hint), text_to_search, re.IGNORECASE)
        if match:
            start_idx, end_idx = match.span()
            return {"start_idx": start_idx, "end_idx": end_idx, "snippet": match.group(0)}
        return None

    def _mock_llm_editor(self, snippet_to_edit: str, instruction: str) -> str:
        """
        Mocks an LLM call to edit a snippet of text based on an instruction.
        Performs a simple transformation for demonstration.

        Args:
            snippet_to_edit (str): The text snippet to be edited.
            instruction (str): The instruction on how to edit the snippet.

        Returns:
            str: The edited snippet.
        """
        # Example edit: Convert to uppercase and prepend instruction
        return f"EDITED based on '{instruction}': [{snippet_to_edit.upper()}]"

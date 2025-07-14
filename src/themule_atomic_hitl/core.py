# src/themule_atomic_hitl/core.py
"""
This module defines the core logic for the Surgical Editor.
It handles the state management, edit queuing, and interaction with a UI (via callbacks)
for a human-in-the-loop editing process.
"""

import re
import uuid
import json
from typing import Callable, Dict, Any, Optional, Tuple, Union
from collections import deque
from .config import Config
from .llm_service import LLMService # Import LLMService

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
        config (Dict[str, Any]): Configuration settings for the editor, potentially including field definitions.
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
                 initial_data: Union[Dict[str, Any], str],
                 config: Config, # Uses Config object
                 callbacks: Dict[str, Callable],
                 llm_service_instance: Optional[LLMService] = None): # Added for testing
        """
        Initializes the SurgicalEditorLogic.

        Args:
            initial_data (Union[Dict[str, Any], str]): The initial data to be edited.
            config (Config): The Config object for the editor.
            callbacks (Dict[str, Callable]): Callbacks for UI interaction.
        """
        # Use properties from Config object to get field names
        self.main_text_field = config.main_editor_modified_field
        self.original_text_field = config.main_editor_original_field

        if isinstance(initial_data, str):
            self.data = {
                self.main_text_field: initial_data,
                self.original_text_field: initial_data,
                 "status": "Loaded from raw text"
            }
        else:
            self.data = initial_data

        self._initial_data_snapshot = json.loads(json.dumps(self.data))
        self.config_manager = config # Store the Config object

        self.edit_results = []  # Stores results of processed edits
        self.callbacks = callbacks

        # Queue for structured edit requests
        self.edit_request_queue: deque[Dict[str, Any]] = deque()
        self.active_edit_task: Optional[Dict[str, Any]] = None # Details of the current task being processed

        # Initialize LLM Service
        if llm_service_instance:
            self.llm_service = llm_service_instance
        else:
            try:
                llm_actual_config = self.config_manager.get_llm_config()
                if not llm_actual_config: # Should not happen if defaults are in place
                    print("Warning: LLM configuration missing from main config. LLM features may fail.")
                    self.llm_service = None
                else:
                    self.llm_service = LLMService(llm_config=llm_actual_config)
            except Exception as e:
                print(f"Error initializing LLMService: {e}. LLM features will be disabled.")
                self.callbacks['show_error'](f"LLMService init failed: {e}. LLM features disabled.")
                self.llm_service = None # Ensure it's None if init fails

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
            # For display, use hint if available, otherwise selection text, or just ID
            display_identifier = "Task"
            if self.active_edit_task.get('user_hint'):
                display_identifier = self.active_edit_task['user_hint']
            elif self.active_edit_task.get('selection_details') and self.active_edit_task['selection_details'].get('text'):
                s_text = self.active_edit_task['selection_details']['text']
                display_identifier = s_text[:30] + "..." if len(s_text) > 30 else s_text
            elif self.active_edit_task.get('id'):
                display_identifier = f"Task ID: {self.active_edit_task['id']}"
            queue_info['active_task_hint'] = display_identifier # Reusing this field for general task ID

        # print(f"CORE_LOGIC (_notify_view_update): About to call update_view callback. Data: {self.data}, Config: {self.config_manager.get_config()}, QueueInfo: {queue_info}")
        self.callbacks['update_view'](self.data, self.config_manager.get_config(), queue_info)

    def add_edit_request(self,
                         instruction: str,
                         request_type: str,
                         hint: Optional[str] = None,
                         selection_details: Optional[Dict[str, Any]] = None):
        """
        Adds a new structured edit request to the queue.

        Args:
            instruction (str): User's instruction on how to edit.
            request_type (str): 'hint_based' or 'selection_specific'.
            hint (Optional[str]): Hint string if request_type is 'hint_based'.
            selection_details (Optional[Dict[str, Any]]): Dictionary with selection info
                (text, startLineNumber, startColumn, endLineNumber, endColumn)
                if request_type is 'selection_specific'.
        """
        if request_type not in ['hint_based', 'selection_specific']:
            self.callbacks['show_error'](f"Invalid request type: {request_type}")
            return

        if request_type == 'hint_based' and hint is None:
            self.callbacks['show_error']("Hint is required for hint_based requests.")
            return
        if request_type == 'selection_specific' and selection_details is None:
            self.callbacks['show_error']("Selection details are required for selection_specific requests.")
            return

        request_id = str(uuid.uuid4())
        new_request = {
            "id": request_id,
            "type": request_type,
            "instruction": instruction,
            "content_snapshot": self.current_main_content, # Snapshot at time of request
            "hint": hint,
            "selection_details": selection_details,
            "status": "queued" # Initial status of the request itself
        }
        # print(f"CORE_LOGIC: Adding edit request. ID='{request_id}', Type='{request_type}'")
        self.edit_request_queue.append(new_request)
        self._notify_view_update()

        if not self.active_edit_task:
            self._process_next_edit_request()

    def _process_next_edit_request(self):
        """
        Processes the next edit request from the queue if no task is active and the queue is not empty.
        Handles both 'hint_based' and 'selection_specific' requests.
        """
        if self.active_edit_task:
            # print("CORE_LOGIC: Already processing an active task. New task will wait.")
            return
        if not self.edit_request_queue:
            # print("CORE_LOGIC: Edit request queue is empty.")
            self._notify_view_update()
            return

        request_details = self.edit_request_queue.popleft()

        # Populate active_edit_task. Note: 'user_hint' and 'user_instruction' are legacy keys
        # kept for compatibility with existing UI update logic if needed, but new logic uses request_details directly.
        self.active_edit_task = {
            "id": request_details["id"],
            "type": request_details["type"],
            "user_instruction": request_details["instruction"],
            "original_content_snapshot": request_details["content_snapshot"],
            "user_hint": request_details.get("hint"), # Might be None for selection_specific
            "selection_details_from_request": request_details.get("selection_details"), # Original line/col based
            "status": "processing_started", # Generic initial status
            "location_info": None, # To be filled by locator or derived from selection_details
            "llm_generated_snippet_details": None
        }
        # print(f"CORE_LOGIC: Starting processing of task ID: {self.active_edit_task['id']}, Type: {self.active_edit_task['type']}")
        self._notify_view_update()

        if self.active_edit_task['type'] == 'hint_based':
            self.active_edit_task['status'] = 'locating_snippet'
            self._notify_view_update()
            self._execute_llm_locator_attempt() # Renamed for clarity
        elif self.active_edit_task['type'] == 'selection_specific':
            # Convert selection_details (line/col) to char offsets and populate location_info
            sel_details = self.active_edit_task['selection_details_from_request']
            snapshot = self.active_edit_task['original_content_snapshot']

            # Basic validation of selection_details structure
            if not sel_details or not all(k in sel_details for k in ['text', 'startLineNumber', 'startColumn', 'endLineNumber', 'endColumn']):
                self.callbacks['show_error'](f"Task {self.active_edit_task['id']}: Invalid selection_details provided.")
                self.active_edit_task['status'] = 'error_bad_selection_details'
                self.active_edit_task = None # Clear task
                self._notify_view_update()
                self._process_next_edit_request() # Try next
                return

            # Directly use the provided text and line/col info.
            # The _llm_editor will work with the provided snippet text.
            # For applying the change, we will need start/end char offsets later.
            # For now, the 'snippet' in location_info is the selected text itself.
            # We'll calculate precise start/end char offsets when applying the edit.
            # This simplifies the immediate flow.

            self.active_edit_task['location_info'] = {
                'snippet': sel_details['text'],
                # Store original line/col info, char offsets will be derived at point of modification if needed
                # or if we decide _llm_editor strictly needs them (currently it just takes the snippet text).
                'start_line': sel_details['startLineNumber'],
                'start_col': sel_details['startColumn'],
                'end_line': sel_details['endLineNumber'],
                'end_col': sel_details['endColumn'],
                'is_selection_based': True # Flag to indicate this location_info is from direct selection
            }

            # Directly proceed to editing this snippet
            self.active_edit_task['status'] = 'location_predefined' # Intermediate status
            self._notify_view_update()
            # Call a method similar to proceed_with_edit_after_location_confirmation, but without user confirm step
            self._initiate_llm_edit_for_task(self.active_edit_task)
        else:
            self.callbacks['show_error'](f"Task {self.active_edit_task['id']}: Unknown request type '{self.active_edit_task['type']}'")
            self.active_edit_task = None # Clear task
            self._notify_view_update()
            self._process_next_edit_request() # Try next

    def _execute_llm_locator_attempt(self):
        """
        Executes the first part of an edit task: locating the snippet based on the user's hint.
        This uses a mock LLM locator for now.
        If successful, it asks for user confirmation of the location.
        """
        if not self.active_edit_task: # Should have 'user_hint' and 'original_content_snapshot'
            self.callbacks['show_error']("LLM locator attempt called without a valid active task.")
            return

        current_hint = self.active_edit_task.get('user_hint')
        content_to_search = self.active_edit_task.get('original_content_snapshot')

        if not current_hint or content_to_search is None:
             self.callbacks['show_error'](f"Task {self.active_edit_task.get('id')}: Missing hint or content snapshot for location.")
             self.active_edit_task['status'] = 'error_missing_locator_data'
             # Potentially clear task and move to next, or leave for user to cancel
             self._notify_view_update()
             return

        location = self._llm_locator(content_to_search, current_hint)

        if not location:
            self.active_edit_task['status'] = 'location_failed'
            # _llm_locator calls show_error if it fails internally
            self._notify_view_update()
            return

        self.active_edit_task['location_info'] = location # Contains {'snippet', 'start_idx', 'end_idx'}
        self.active_edit_task['status'] = 'awaiting_location_confirmation'
        self.callbacks['confirm_location_details'](
            location,
            self.active_edit_task['user_hint'],
            self.active_edit_task['user_instruction']
        )
        self._notify_view_update()

    def _initiate_llm_edit_for_task(self, task: Dict[str, Any]):
        """
        Common method to call the LLM editor for a task that has confirmed/defined location_info.
        Updates the task with LLM output and triggers diff preview.
        """
        if not task or 'location_info' not in task or not task['location_info']:
            self.callbacks['show_error'](f"Task {task.get('id')}: Cannot initiate LLM edit, location_info missing or invalid.")
            if task: task['status'] = 'error_missing_location_for_edit'
            self._notify_view_update()
            return

        location_info = task['location_info']
        snippet_to_edit = location_info['snippet']
        instruction = task['user_instruction']

        # print(f"CORE_LOGIC (_initiate_llm_edit_for_task): Editing snippet for task {task.get('id')}. Snippet: '{snippet_to_edit[:50]}...'")

        edited_snippet = self._llm_editor(snippet_to_edit, instruction)

        task['llm_generated_snippet_details'] = {
            "original_snippet": snippet_to_edit, # This is from location_info
            "edited_snippet": edited_snippet,
            # If location_info contains start/end char indices, preserve them.
            # If it's selection-based with line/col, those are stored in location_info.
            "location_data_from_prior_step": location_info
        }
        task['status'] = 'awaiting_diff_approval'

        content_for_diff_context = task['original_content_snapshot']

        # Determine context_before and context_after. This requires start/end character indices.
        # If location_info has 'start_idx', use it. Otherwise, it's selection-based, and we might skip detailed context for now
        # or convert line/col to char offsets here if strictly needed for preview (less critical than for apply).
        # For now, let's assume 'start_idx' and 'end_idx' might be in location_info from the locator.
        # If not, context might be less precise for selection_specific previews.
        start_idx_for_context = location_info.get('start_idx', 0) # Default to 0 if not found
        end_idx_for_context = location_info.get('end_idx', len(snippet_to_edit)) # Default if not found

        context_before = content_for_diff_context[max(0, start_idx_for_context - 50) : start_idx_for_context]
        context_after = content_for_diff_context[end_idx_for_context : end_idx_for_context + 50]

        self.callbacks['show_diff_preview'](
            snippet_to_edit,
            edited_snippet,
            context_before,
            context_after
        )
        self._notify_view_update()

    def proceed_with_edit_after_location_confirmation(self,
                                                       confirmed_location_details: Dict, # This is the new, confirmed location_info
                                                       original_instruction: str): # Instruction is already in active_edit_task
        """
        Called by the UI after the user has confirmed (or corrected) the snippet location.
        This initiates the "Worker" loop: generating the edit for the confirmed snippet.

        Args:
            confirmed_location_details (Dict): A dictionary containing the confirmed
                location details (e.g., 'snippet', 'start_idx', 'end_idx').
                This could be the original location or a corrected one from the user.
            original_instruction (str): The user's original instruction for the edit.
                (Note: instruction is already in active_edit_task, this param might be redundant
                 if UI doesn't change it at this stage, but kept for now based on existing signature).
        """
        if not self.active_edit_task or self.active_edit_task['status'] != 'awaiting_location_confirmation':
            self.callbacks['show_error']("Proceed with edit (after location confirm) called in an invalid state.")
            return

        # Basic validation of the confirmed location details from UI
        if not (isinstance(confirmed_location_details, dict) and 'snippet' in confirmed_location_details and
                'start_idx' in confirmed_location_details and 'end_idx' in confirmed_location_details):
            self.callbacks['show_error']("Invalid confirmed_location_details structure provided by UI.")
            self.active_edit_task['status'] = 'error_in_location_confirmation'
            self._notify_view_update()
            return

        # Update the active task's location_info with the confirmed (potentially revised) details.
        self.active_edit_task['location_info'] = confirmed_location_details

        # If the original_instruction parameter differs from what's in active_edit_task,
        # the one from the parameter (presumably from UI if it allows changes at this step) should take precedence.
        # For now, assume active_edit_task['user_instruction'] is the one to use.
        # If UI can change instruction at location confirmation, then:
        # self.active_edit_task['user_instruction'] = original_instruction

        # print(f"CORE_LOGIC (proceed_with_edit_after_location_confirmation): Location confirmed for task {self.active_edit_task.get('id')}. Details: {confirmed_location_details}")
        self._initiate_llm_edit_for_task(self.active_edit_task)


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

        # print(f"CORE_LOGIC: User decision for LLM task is '{decision}'")
        snippet_details = self.active_edit_task['llm_generated_snippet_details']
        # The content to modify is the snapshot taken when the request was made.
        original_content_for_this_task = self.active_edit_task['original_content_snapshot']

        if decision == 'approve':
            start_offset: Optional[int] = None
            end_offset: Optional[int] = None

            location_data = snippet_details.get('location_data_from_prior_step', {})

            if self.active_edit_task.get('type') == 'selection_specific' and location_data.get('is_selection_based'):
                # print(f"CORE_LOGIC (Decision): Processing selection_specific task {self.active_edit_task.get('id')}. Location data: {location_data}")
                # Convert line/col to char offsets using the original_content_snapshot
                offsets = self._convert_line_col_to_char_offsets(
                    text_content=original_content_for_this_task, # Use the task's snapshot
                    start_line_1based=location_data['start_line'],
                    start_col_1based=location_data['start_col'],
                    end_line_1based=location_data['end_line'],
                    end_col_1based=location_data['end_col']
                )
                if offsets:
                    start_offset, end_offset = offsets
                    # Sanity check: does the snippet from selection_details match the text at these offsets in snapshot?
                    # This is an important validation.
                    expected_snippet = location_data.get('snippet', "")
                    actual_snippet_in_snapshot = original_content_for_this_task[start_offset:end_offset]
                    if expected_snippet != actual_snippet_in_snapshot:
                        print(f"WARNING: Mismatch between selection_specific snippet and text at calculated offsets.")
                        print(f"  Expected: '{expected_snippet}'")
                        print(f"  Actual in snapshot: '{actual_snippet_in_snapshot}'")
                        # Decide on error handling: could be an error, or proceed if offsets are trusted.
                        # For now, proceed but log warning. Could make this a hard error.
                        # self.callbacks['show_error']("Mismatch between selected text and snapshot content at derived offsets. Cannot apply.")
                        # self.active_edit_task['status'] = "error_apply_failed_offset_mismatch"
                        # self._notify_view_update()
                        # self.active_edit_task = None
                        # self._process_next_edit_request()
                        # return
                else:
                    self.callbacks['show_error'](f"Task {self.active_edit_task.get('id')}: Failed to convert line/col to char offsets. Cannot apply edit.")
                    self.active_edit_task['status'] = "error_apply_failed_offset_conversion"
                    self._notify_view_update() # Show error status
                    # Do not clear active_edit_task immediately, let user see error, perhaps they cancel.
                    # Or, clear and move to next:
                    self.active_edit_task = None
                    self._process_next_edit_request()
                    return
            elif self.active_edit_task.get('type') == 'hint_based':
                 # For hint_based, start/end should already be char offsets from the locator step
                 # and stored in llm_generated_snippet_details directly or via location_data_from_prior_step
                if 'start_idx' in location_data and 'end_idx' in location_data:
                    start_offset = location_data['start_idx']
                    end_offset = location_data['end_idx']
                else: # Legacy path if snippet_details had 'start'/'end' directly
                    start_offset = snippet_details.get('start')
                    end_offset = snippet_details.get('end')

            if start_offset is None or end_offset is None:
                self.callbacks['show_error'](f"Task {self.active_edit_task.get('id')}: Could not determine character offsets to apply edit.")
                self.active_edit_task['status'] = "error_apply_failed_no_offsets"
                self._notify_view_update()
                self.active_edit_task = None
                self._process_next_edit_request()
                return

            snippet_to_apply = manually_edited_snippet if manually_edited_snippet is not None else snippet_details['edited_snippet']

            # Construct the new content based on the original snapshot for this task
            new_content_for_this_task = original_content_for_this_task[:start_offset] + \
                                        snippet_to_apply + \
                                        original_content_for_this_task[end_offset:]

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

        # print("CORE_LOGIC: Retrying active task with new clarification.")
        # Update task details with new information. The original_content_snapshot remains the same.
        self.active_edit_task['user_hint'] = new_hint if new_hint else self.active_edit_task['user_hint']
        self.active_edit_task['user_instruction'] = new_instruction if new_instruction else self.active_edit_task['user_instruction']
        self.active_edit_task['status'] = 'locating_snippet' # Reset status to start locator phase
        self.active_edit_task['location_info'] = None
        self.active_edit_task['llm_generated_snippet_details'] = None
        self._notify_view_update()
        self._execute_llm_locator_attempt() # Corrected method name

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
        # print(f"CORE_LOGIC: Received generic action '{action_name}' with payload: {payload}")
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
        """
        Handler for 'approve_main_content' action.
        Updates the main text field and potentially other fields from the payload.

        Args:
            payload (Dict[str, Any]): Payload should contain the field designated as
                                      `self.main_text_field` and its new content.
                                      It can also contain other fields to update in `self.data`.
        """

        # print("CORE_LOGIC: Handling general approve_main_content action.")
        # Update the main text field if present in the payload
        if self.main_text_field in payload:
            self.current_main_content = payload[self.main_text_field]

        # Update other data fields if they are present in the payload and exist in self.data

        for key, value in payload.items():
            if key != self.main_text_field and key in self.data: # Check if key exists in self.data
                self.data[key] = value

        self.data["status"] = "Content Approved (General)" # Example status update
        # print(f"--- General content approval. Data: {self.data} ---")

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
        # Any active LLM task should probably be cancelled or handled here.
        if self.active_edit_task:
            # print("CORE_LOGIC: Reverting changes with an active task. Task will be cancelled.")
            self.edit_results.append({
                "id": str(uuid.uuid4()), "status": "task_cancelled_on_revert",
                "message": f"Task for hint '{self.active_edit_task['user_hint']}' cancelled due to revert."
            })
            self.active_edit_task = None
            # No need to call _process_next_edit_request here as revert is a major state change.
            # The UI should reflect the reverted state.
        # Clear the queue as well, as its snapshots may no longer be relevant.
        if self.edit_request_queue:
            # print("CORE_LOGIC: Clearing edit request queue due to revert.")
            self.edit_request_queue.clear()



    def handle_unknown_action(self, payload: Dict[str, Any]):
        """
        Handler for actions that don't have a specific `handle_...` method.

        Args:
            payload (Dict[str, Any]): Payload of the unknown action.
        """

        action_name = payload.get("action_name", "unknown") # Assuming action_name might be in payload
        print(f"Warning: Unknown generic action '{action_name}' received by SurgicalEditorLogic.")
        self.callbacks['show_error'](f"Unknown generic action '{action_name}' requested.")

    # --- Mock LLM Methods ---
    # These methods simulate interactions with an LLM for locating and editing text.

    # In a real application, these would involve calls to actual LLM services.

    def _llm_locator(self, text_to_search: str, hint: str) -> Optional[Dict[str, Any]]:
        """
        Uses LLMService to locate a snippet of text based on a hint.
        The LLM is prompted to return the exact snippet. This method then finds the snippet
        in the original text to determine start and end indices.

        Args:
            text_to_search (str): The text in which to search for the snippet.
            hint (str): The hint to guide the search (user prompt for the LLM).

        Returns:
            Optional[Dict[str, Any]]: A dictionary with 'start_idx', 'end_idx', and 'snippet'
                                      if found, otherwise None.
        """
        if not self.llm_service:
            self.callbacks['show_error']("LLMService is not available. Cannot locate snippet.")
            return None

        try:
            # The system prompt for "locator" is defined in config and fetched by LLMService
            # The user prompt for the locator task is the 'hint'.
            # We expect the LLM to return the *exact text of the snippet*.
            located_snippet_text = self.llm_service.invoke_llm(
                task_name="locator",
                user_prompt=f"Given the following text:\n\n---\n{text_to_search}\n---\n\nIdentify and return the exact text snippet that matches the hint: '{hint}'. Respond only with the identified snippet text and nothing else."
            )

            if not located_snippet_text or not located_snippet_text.strip():
                self.callbacks['show_error'](f"LLM locator returned an empty response for hint: '{hint}'")
                return None

            located_snippet_text = located_snippet_text.strip()

            # Now, find this located_snippet_text within the original text_to_search
            # This assumes the LLM returns a substring that exists in text_to_search.
            # For robustness, consider fuzzy matching or more advanced alignment if LLM slightly alters it.
            try:
                start_idx = text_to_search.index(located_snippet_text)
                end_idx = start_idx + len(located_snippet_text)
                return {"start_idx": start_idx, "end_idx": end_idx, "snippet": located_snippet_text}
            except ValueError:
                # Snippet returned by LLM not found verbatim in the original text.
                # This can happen if LLM reformats, summarizes, or hallucinates.
                # Try a more lenient search: case-insensitive and stripping whitespace from search text
                # This is a simple fallback. More advanced techniques might be needed.

                # Attempt a regex search for the snippet, escaping regex special characters
                # and allowing for minor variations in whitespace or case.
                # This is a common issue with LLMs not returning exact substrings.
                escaped_snippet = re.escape(located_snippet_text)
                match = re.search(escaped_snippet, text_to_search, re.IGNORECASE)
                if match:
                    start_idx, end_idx = match.span()
                    # Return the actual matched snippet from original text to ensure consistency
                    actual_matched_snippet = text_to_search[start_idx:end_idx]
                    print(f"LLM locator: Exact match failed for '{located_snippet_text}', but found '{actual_matched_snippet}' via regex.")
                    return {"start_idx": start_idx, "end_idx": end_idx, "snippet": actual_matched_snippet}
                else:
                    self.callbacks['show_error'](f"LLM locator returned: '{located_snippet_text}', which was not found in the original text, even with lenient search.")
                    return None

        except Exception as e:
            self.callbacks['show_error'](f"Error during LLM location: {str(e)}")
            print(f"LLM Locator Exception: {e}")
            return None

    def _llm_editor(self, snippet_to_edit: str, instruction: str) -> str:
        """
        Uses LLMService to edit a snippet of text based on an instruction.
        Performs a simple transformation for demonstration.

        Args:
            snippet_to_edit (str): The text snippet to be edited.
            instruction (str): The instruction on how to edit the snippet.

        Returns:
            str: The edited snippet.
        """
        if not self.llm_service:
            self.callbacks['show_error']("LLMService is not available. Cannot edit snippet.")
            # Return original snippet to indicate no change was made by LLM
            return snippet_to_edit

        try:
            # The system prompt for "editor" is defined in config and fetched by LLMService.
            # The user prompt combines the snippet and the instruction.
            user_prompt_for_editor = (
                f"Original Snippet:\n---\n{snippet_to_edit}\n---\n\n"
                f"Instruction: {instruction}\n\n"
                f"Return only the modified snippet text. If no changes are necessary based on the instruction, return the original snippet text exactly."
            )

            edited_snippet = self.llm_service.invoke_llm(
                task_name="editor",
                user_prompt=user_prompt_for_editor
            )

            if edited_snippet is None: # Check if LLM returned None (e.g. error in service)
                self.callbacks['show_error']("LLM editor returned None. Using original snippet.")
                return snippet_to_edit

            return edited_snippet.strip() # Clean whitespace

        except Exception as e:
            self.callbacks['show_error'](f"Error during LLM edit: {str(e)}")
            print(f"LLM Editor Exception: {e}")
            # Fallback to original snippet in case of error
            return snippet_to_edit

    def _convert_line_col_to_char_offsets(self, text_content: str, start_line_1based: int, start_col_1based: int, end_line_1based: int, end_col_1based: int) -> Optional[Tuple[int, int]]:
        """
        Converts 1-based line and column numbers to 0-based character offsets.

        Args:
            text_content (str): The text content where the selection was made.
            start_line_1based (int): The 1-based starting line number.
            start_col_1based (int): The 1-based starting column number.
            end_line_1based (int): The 1-based ending line number.
            end_col_1based (int): The 1-based ending column number.

        Returns:
            Optional[Tuple[int, int]]: A tuple (start_char_offset, end_char_offset), or None if conversion fails.
        """
        lines = text_content.splitlines(True) # Keep line endings for accurate offsets

        if not (1 <= start_line_1based <= len(lines) and 1 <= end_line_1based <= len(lines)):
            self.callbacks['show_error'](f"Line numbers out of bounds (1-{len(lines)}): Start {start_line_1based}, End {end_line_1based}")
            return None

        start_char_offset = 0
        for i in range(start_line_1based - 1):
            start_char_offset += len(lines[i])

        # Check column bounds for start line
        # len(lines[start_line_1based - 1]) includes newline, but Monaco col might be beyond text if on newline char itself
        start_line_content_len = len(lines[start_line_1based - 1].rstrip('\r\n'))
        if not (1 <= start_col_1based <= start_line_content_len + 1): # +1 to allow cursor after last char
             self.callbacks['show_error'](f"Start column {start_col_1based} out of bounds (1-{start_line_content_len + 1}) for line {start_line_1based}.")
             return None
        start_char_offset += (start_col_1based - 1)

        end_char_offset = 0
        for i in range(end_line_1based - 1):
            end_char_offset += len(lines[i])

        # Check column bounds for end line
        end_line_content_len = len(lines[end_line_1based - 1].rstrip('\r\n'))
        if not (1 <= end_col_1based <= end_line_content_len + 1):
            self.callbacks['show_error'](f"End column {end_col_1based} out of bounds (1-{end_line_content_len + 1}) for line {end_line_1based}.")
            return None
        end_char_offset += (end_col_1based - 1)

        if start_char_offset > end_char_offset:
            self.callbacks['show_error'](f"Start offset {start_char_offset} is greater than end offset {end_char_offset}.")
            return None

        # Validate that calculated offsets are within text_content bounds
        if not (0 <= start_char_offset <= len(text_content) and 0 <= end_char_offset <= len(text_content)):
            self.callbacks['show_error']("Calculated character offsets are out of text content bounds.")
            return None

        return start_char_offset, end_char_offset

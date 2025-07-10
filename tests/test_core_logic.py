# tests/test_core_logic.py
"""
This module contains unit tests for the SurgicalEditorLogic class from the core module.
It uses the `unittest` framework and `unittest.mock.MagicMock` to simulate UI callbacks
and verify the behavior of the core logic in isolation.

The tests cover:
- Initialization of the editor logic.
- Adding edit requests and processing them through various stages (location, diff, approval).
- Handling user decisions: approve, reject (leading to clarification), cancel.
- Queuing multiple edit requests.
- Performing generic actions like incrementing version and reverting changes.

A key aspect of this test setup is the attempt to import `SurgicalEditorLogic` directly
from `src.themule_atomic_hitl.core` to avoid pulling in PyQt5 dependencies, which are
not needed for testing the core logic itself. A fallback mechanism is in place if
the direct import fails due to `ModuleNotFoundError` related to PyQt5, attempting to
import `core` module directly after adjusting `sys.path`.
"""

import sys
import os

import unittest # Standard Python unit testing framework
from unittest.mock import MagicMock # For creating mock objects for callbacks
import json # Added for temp config file

# --- Path Adjustment for Importing from `src` ---
# This ensures that the `src` directory is in Python's import path,
# allowing modules from `src.themule_atomic_hitl` to be imported,
# especially when tests are run from the project root.
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # Gets /path/to/repo
sys.path.insert(0, project_root) # Add project root (e.g., /path/to/repo) to the start of sys.path

# --- Import SurgicalEditorLogic with PyQt5 Workaround ---
# The goal here is to test `SurgicalEditorLogic` without needing PyQt5 installed,
# as the core logic itself should be UI-agnostic.
# The `themule_atomic_hitl/__init__.py` might import `runner` which imports PyQt5.
# This try-except block attempts a direct import of `core.SurgicalEditorLogic`.
# If a ModuleNotFoundError occurs specifically because of PyQt5, it tries a more
# direct import of the `core.py` file itself.


try:
    # Standard way to import if project structure allows and __init__ is minimal
    from src.themule_atomic_hitl.core import SurgicalEditorLogic
    from src.themule_atomic_hitl.config import Config # Import Config class
except ModuleNotFoundError as e:

    if 'PyQt5' in str(e): # Check if PyQt5 is the cause of ModuleNotFoundError
        print("PyQt5 not found, or other import error. Attempting to adjust path for core logic testing...")
        # This path adjustment assumes tests are run from the project root or similar context
        # where 'src' is a direct subdirectory.
        # Construct path to `src/themule_atomic_hitl` directory
        core_module_path = os.path.join(project_root, "src")
        if core_module_path not in sys.path:
            sys.path.insert(0, core_module_path) # Add 'src' to path

        # Try importing again after path adjustment
        from themule_atomic_hitl.core import SurgicalEditorLogic
        from themule_atomic_hitl.config import Config
        print("Successfully imported SurgicalEditorLogic and Config after path adjustment.")
    else:
        # If the error is not related to PyQt5, re-raise it.
        print(f"Encountered an unexpected ImportError: {e}")
        raise e


class TestSurgicalEditorLogic(unittest.TestCase):
    """
    Test suite for the SurgicalEditorLogic class.
    Each method starting with `test_` is an individual test case.
    """

    def setUp(self):
        """
        Set up method called before each test case.
        Initializes mock callbacks, initial data, config, and the SurgicalEditorLogic instance.
        """
        # Mock callbacks that SurgicalEditorLogic will use to communicate with a hypothetical UI
        self.mock_callbacks = {
            'update_view': MagicMock(),
            'show_diff_preview': MagicMock(),
            'request_clarification': MagicMock(),
            'show_error': MagicMock(),
            'confirm_location_details': MagicMock() # For the location confirmation step
        }


        # Sample initial data for the editor
        self.sample_initial_data = { # Renamed for clarity
            "document_text": "This is the initial document content.", # This will be 'modifiedDataField'
            "original_doc": "This is the initial document content.", # This will be 'originalDataField'
        

        # This dictionary will be used to create a Config object
        self.sample_config_dict = {
            "fields": [
                # Ensure this matches what SurgicalEditorLogic expects via Config properties
                {"name": "diff_editor_main", "type": "diff-editor",
                 "originalDataField": "original_doc", "modifiedDataField": "document_text"},

                {"name": "author", "type": "text-input", "label": "Author"},
                {"name": "version", "type": "label", "label": "Version"}
            ],
            "actions": [ # Generic actions available in the UI
                {"name": "increment_version", "label": "Increment Version"},
                {"name": "revert_changes", "label": "Revert All Changes"}
            ],
            "settings": { # Add settings for completeness if Config expects it
                "defaultWindowTitle": "Test Window"
            }
        }

        # Create a temporary custom config file to initialize Config object properly
        self.temp_config_file_path = "temp_test_core_config.json"
        with open(self.temp_config_file_path, 'w') as f:
            json.dump(self.sample_config_dict, f)

        # Initialize Config object using the temporary file
        self.config_object = Config(custom_config_path=self.temp_config_file_path)

        self.editor_logic = SurgicalEditorLogic(
            initial_data=dict(self.sample_initial_data), # Pass a copy
            config=self.config_object,                   # Pass the Config object

            callbacks=self.mock_callbacks
        )
        # Reset mocks before each test to ensure clean state for call counts, etc.
        for mock_func in self.mock_callbacks.values():
            mock_func.reset_mock()

    def tearDown(self):
        """Clean up after each test."""
        if os.path.exists(self.temp_config_file_path):
            os.remove(self.temp_config_file_path)

    def test_01_initialization(self):
        """
        Tests the initial state of the SurgicalEditorLogic after instantiation.
        Verifies that data, config, and internal state (queue, active task) are correctly set up.
        """
        print("\nRunning test_01_initialization...")
        from collections import deque # Ensure deque is available for type checking
        # Check if the main content is correctly identified from initial_data and config
        self.assertEqual(self.editor_logic.current_main_content, "This is the initial document content.")
        self.assertEqual(self.editor_logic.data["version"], 1.0)
        # Check internal state
        self.assertTrue(isinstance(self.editor_logic.edit_request_queue, deque))
        self.assertEqual(len(self.editor_logic.edit_request_queue), 0) # Queue should be empty
        self.assertIsNone(self.editor_logic.active_edit_task) # No active task initially
        print("test_01_initialization PASSED")

    def test_02_add_edit_request_and_process_approve(self):
        """
        Tests the full lifecycle of an edit request:
        1. Add request (hint + instruction).
        2. System locates snippet (mocked) and asks for location confirmation.
        3. User confirms location.
        4. System generates edit (mocked) and asks for diff approval.
        5. User approves the edit.
        Verifies state changes, callback calls, and final content.
        """
        print("\nRunning test_02_add_edit_request_and_process_approve...")
        # Add an edit request
        self.editor_logic.add_edit_request("initial document", "make it uppercase")

        # After adding, queue should be empty (as it's processed immediately if no active task)
        self.assertEqual(len(self.editor_logic.edit_request_queue), 0)
        self.assertIsNotNone(self.editor_logic.active_edit_task) # Task should be active
        self.assertEqual(self.editor_logic.active_edit_task['user_hint'], "initial document")
        # Status should be awaiting location confirmation after mock_llm_locator runs
        self.assertEqual(self.editor_logic.active_edit_task['status'], "awaiting_location_confirmation")

        # Check if 'confirm_location_details' callback was called correctly
        self.mock_callbacks['confirm_location_details'].assert_called_once()
        loc_args, _ = self.mock_callbacks['confirm_location_details'].call_args
        location_info, original_hint, original_instruction = loc_args
        self.assertEqual(location_info['snippet'], "initial document") # Mock locator found this
        self.assertEqual(original_hint, "initial document")
        self.assertEqual(original_instruction, "make it uppercase")

        # Simulate user confirming the location
        self.editor_logic.proceed_with_edit_after_location_confirmation(location_info, original_instruction)
        self.assertEqual(self.editor_logic.active_edit_task['status'], "awaiting_diff_approval")

        # Check if 'show_diff_preview' callback was called correctly
        self.mock_callbacks['show_diff_preview'].assert_called_once()
        diff_args, _ = self.mock_callbacks['show_diff_preview'].call_args
        original_snippet, edited_snippet, _, _ = diff_args # Ignoring context_before/after for this assertion
        self.assertEqual(original_snippet, "initial document")
        # Based on _mock_llm_editor's behavior
        self.assertEqual(edited_snippet, "EDITED based on 'make it uppercase': [INITIAL DOCUMENT]")

        # Simulate user approving the edit
        self.editor_logic.process_llm_task_decision('approve')
        self.assertIsNone(self.editor_logic.active_edit_task) # Task should be completed and cleared
        # Verify the main content was updated correctly
        expected_content = "This is the EDITED based on 'make it uppercase': [INITIAL DOCUMENT] content."
        self.assertEqual(self.editor_logic.current_main_content, expected_content)
        self.assertTrue(self.mock_callbacks['update_view'].called) # View should be updated
        print("test_02_add_edit_request_and_process_approve PASSED")

    def test_03_process_reject_clarify_then_approve(self):
        """
        Tests the reject and clarification workflow:
        1. Add request, confirm location, show diff.
        2. User rejects the edit.
        3. System requests clarification.
        4. User provides new instruction.
        5. System re-processes (locate, edit, diff).
        6. User approves the second attempt.
        Verifies state changes and callback calls throughout.
        """
        print("\nRunning test_03_process_reject_clarify_then_approve...")
        self.editor_logic.add_edit_request("content", "change it") # Initial request

        # --- First attempt (locate and show diff) ---
        self.mock_callbacks['confirm_location_details'].assert_called_once()
        loc_args, _ = self.mock_callbacks['confirm_location_details'].call_args
        location_info, _, original_instruction = loc_args
        self.editor_logic.proceed_with_edit_after_location_confirmation(location_info, original_instruction)
        self.mock_callbacks['show_diff_preview'].assert_called_once()

        # --- User rejects the first attempt ---
        self.editor_logic.process_llm_task_decision('reject')
        self.mock_callbacks['request_clarification'].assert_called_once() # Should ask for clarification
        self.assertIsNotNone(self.editor_logic.active_edit_task)
        self.assertEqual(self.editor_logic.active_edit_task['status'], "awaiting_clarification")

        # --- User provides clarification and retries ---
        current_hint_for_retry = self.editor_logic.active_edit_task['user_hint']
        self.editor_logic.update_active_task_and_retry(current_hint_for_retry, "make it bold") # New instruction

        # --- Second attempt (locate and show diff) ---
        # confirm_location_details should be called again (total 2 times)
        self.assertEqual(self.mock_callbacks['confirm_location_details'].call_count, 2)
        loc_args_2, _ = self.mock_callbacks['confirm_location_details'].call_args # Get latest call args
        location_info_2, _, original_instruction_2 = loc_args_2
        self.editor_logic.proceed_with_edit_after_location_confirmation(location_info_2, original_instruction_2)

        # show_diff_preview should be called again (total 2 times)
        self.assertEqual(self.mock_callbacks['show_diff_preview'].call_count, 2)
        diff_args_2, _ = self.mock_callbacks['show_diff_preview'].call_args # Get latest call args
        self.assertEqual(diff_args_2[1], "EDITED based on 'make it bold': [CONTENT]") # Check new edited snippet

        # --- User approves the second attempt ---
        self.editor_logic.process_llm_task_decision('approve')
        self.assertIsNone(self.editor_logic.active_edit_task) # Task completed
        self.assertTrue("EDITED based on 'make it bold': [CONTENT]" in self.editor_logic.current_main_content)
        print("test_03_process_reject_clarify_then_approve PASSED")

    def test_04_process_cancel_task_after_location_confirm(self):
        """
        Tests cancelling a task after the location has been confirmed and diff shown.
        Verifies that the task is cleared and content remains unchanged.
        """
        print("\nRunning test_04_process_cancel_task_after_location_confirm...")
        initial_content = self.editor_logic.current_main_content # Snapshot before edit
        self.editor_logic.add_edit_request("document", "delete this part")

        # Process up to diff preview
        self.mock_callbacks['confirm_location_details'].assert_called_once()
        loc_args, _ = self.mock_callbacks['confirm_location_details'].call_args
        location_info, _, original_instruction = loc_args
        self.editor_logic.proceed_with_edit_after_location_confirmation(location_info, original_instruction)
        self.mock_callbacks['show_diff_preview'].assert_called_once()

        # User cancels the task
        self.editor_logic.process_llm_task_decision('cancel')
        self.assertIsNone(self.editor_logic.active_edit_task) # Task should be cleared
        self.assertEqual(self.editor_logic.current_main_content, initial_content) # Content should not change
        self.assertEqual(self.editor_logic.edit_results[-1]['status'], "task_cancelled") # Check audit trail
        print("test_04_process_cancel_task_after_location_confirm PASSED")

    def test_05_queue_multiple_requests(self):
        """
        Tests the queuing mechanism:
        1. Add first request; it becomes active.
        2. Add second request; it's added to the queue.
        3. First request is processed and approved.
        4. Second request becomes active and is then processed and approved.
        Verifies queue state and correct processing order.
        """
        print("\nRunning test_05_queue_multiple_requests...")
        # Add first request
        self.editor_logic.add_edit_request("initial", "uppercase it")
        self.assertEqual(len(self.editor_logic.edit_request_queue), 0) # First task becomes active immediately

        # Add second request while first is active (or about to be processed by locator)
        self.editor_logic.add_edit_request("content", "add exclamation")
        self.assertEqual(len(self.editor_logic.edit_request_queue), 1) # Second task goes into queue

        self.assertIsNotNone(self.editor_logic.active_edit_task)
        self.assertEqual(self.editor_logic.active_edit_task['user_hint'], "initial") # First task is active

        # --- Process and approve first task ---
        loc_args1, _ = self.mock_callbacks['confirm_location_details'].call_args
        self.editor_logic.proceed_with_edit_after_location_confirmation(loc_args1[0], loc_args1[2])
        self.editor_logic.process_llm_task_decision('approve')
        self.assertTrue("EDITED based on 'uppercase it': [INITIAL]" in self.editor_logic.current_main_content)

        # --- Second task should now be active ---
        self.assertIsNotNone(self.editor_logic.active_edit_task, "Second task did not start.")
        self.assertEqual(self.editor_logic.active_edit_task['user_hint'], "content")
        self.assertEqual(len(self.editor_logic.edit_request_queue), 0) # Queue should be empty again

        # --- Process and approve second task ---
        # Ensure confirm_location_details was called for the second task with correct args
        self.mock_callbacks['confirm_location_details'].assert_any_call(unittest.mock.ANY, "content", "add exclamation")
        loc_args2, _ = self.mock_callbacks['confirm_location_details'].call_args # Get the *last* call args
        self.editor_logic.proceed_with_edit_after_location_confirmation(loc_args2[0], loc_args2[2])
        self.editor_logic.process_llm_task_decision('approve')
        self.assertTrue("EDITED based on 'add exclamation': [CONTENT]" in self.editor_logic.current_main_content)
        self.assertIsNone(self.editor_logic.active_edit_task) # All tasks done
        print("test_05_queue_multiple_requests PASSED")

    def test_06_generic_action_increment_version(self):
        """
        Tests the 'increment_version' generic action.
        Verifies that the version in data is correctly incremented.
        """
        print("\nRunning test_06_generic_action_increment_version...")
        initial_version_str = self.editor_logic.data["version"] # Version might be string or float
        initial_version = float(initial_version_str) if isinstance(initial_version_str, str) else initial_version_str

        self.editor_logic.perform_action("increment_version")

        # Core logic now stores version as string after increment
        expected_version_str = str(round(initial_version + 0.1, 1))
        self.assertEqual(self.editor_logic.data["version"], expected_version_str)
        self.assertEqual(self.editor_logic.edit_results[-1]['status'], "action_increment_version_success")
        self.assertTrue(self.mock_callbacks['update_view'].called)
        print("test_06_generic_action_increment_version PASSED")

    def test_07_generic_action_revert_changes(self):
        """
        Tests the 'revert_changes' generic action.
        1. Makes some changes to content and version.
        2. Calls 'revert_changes'.
        3. Verifies that data is reverted to its initial state.
        """
        print("\nRunning test_07_generic_action_revert_changes...")
        # Capture initial state
        original_content_snapshot = str(self.editor_logic.current_main_content)
        original_version_snapshot = self.editor_logic.data["version"]

        # --- Make some changes ---
        self.editor_logic.add_edit_request("initial", "make it different")
        # Drive the edit to completion
        self.mock_callbacks['confirm_location_details'].assert_called_with(
            unittest.mock.ANY, # location_info can vary slightly if mock_locator changes
            "initial",
            "make it different"
        )
        loc_args, _ = self.mock_callbacks['confirm_location_details'].call_args
        location_info_for_proceed = loc_args[0]
        instruction_for_proceed = loc_args[2]

        # Debug print, can be removed after confirming test stability
        print(f"test_07_generic_action_revert_changes: location_info for proceed = {location_info_for_proceed}")
        self.editor_logic.proceed_with_edit_after_location_confirmation(location_info_for_proceed, instruction_for_proceed)

        self.assertEqual(self.editor_logic.active_edit_task['status'], "awaiting_diff_approval")
        self.assertIsNotNone(self.editor_logic.active_edit_task['llm_generated_snippet_details'])
        self.editor_logic.process_llm_task_decision('approve') # Approve the edit

        self.editor_logic.perform_action("increment_version") # Increment version

        # --- Verify changes were made ---
        self.assertNotEqual(self.editor_logic.current_main_content, original_content_snapshot)
        self.assertNotEqual(self.editor_logic.data["version"], original_version_snapshot)

        # --- Perform revert ---
        self.editor_logic.perform_action("revert_changes")

        # --- Verify data is reverted ---
        self.assertEqual(self.editor_logic.current_main_content, original_content_snapshot)
        self.assertEqual(self.editor_logic.data["version"], original_version_snapshot)
        self.assertEqual(self.editor_logic.edit_results[-1]['status'], "action_revert_changes_success")
        print("test_07_generic_action_revert_changes PASSED")

if __name__ == '__main__':
    """
    Standard entry point for running unittest tests from the command line.
    """
    unittest.main()

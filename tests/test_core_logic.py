# tests/test_core_logic.py
import sys
import os
import unittest # Using unittest for a more structured approach
from unittest.mock import MagicMock
import json # Added for temp config file

# Adjust path to import from src
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root) # Add project root for general imports

# To avoid PyQt5 dependency for core logic tests, we'll try to import core directly
# This is a workaround for the current package structure where __init__ imports runner.
try:
    from src.themule_atomic_hitl.core import SurgicalEditorLogic
    from src.themule_atomic_hitl.config import Config # Import Config class
except ModuleNotFoundError as e:
    if 'PyQt5' in str(e): # Check if PyQt5 is the cause of ModuleNotFoundError
        print("PyQt5 not found, or other import error. Attempting to adjust path for core logic testing...")
        # This path adjustment assumes tests are run from the project root or similar context
        # where 'src' is a direct subdirectory.
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

    def setUp(self):
        """Set up for each test."""
        self.mock_callbacks = {
            'update_view': MagicMock(),
            'show_diff_preview': MagicMock(),
            'request_clarification': MagicMock(),
            'show_error': MagicMock(),
            'confirm_location_details': MagicMock()
        }

        self.sample_initial_data = { # Renamed for clarity
            "document_text": "This is the initial document content.", # This will be 'modifiedDataField'
            "original_doc": "This is the initial document content.", # This will be 'originalDataField'
            "version": 1.0,
            "author": "TestUser"
        }

        # This dictionary will be used to create a Config object
        self.sample_config_dict = {
            "fields": [
                # Ensure this matches what SurgicalEditorLogic expects via Config properties
                {"name": "diff_editor_main", "type": "diff-editor",
                 "originalDataField": "original_doc", "modifiedDataField": "document_text"},
                {"name": "author", "type": "text-input", "label": "Author"},
                {"name": "version", "type": "label", "label": "Version"}
            ],
            "actions": [
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
        for mock_func in self.mock_callbacks.values():
            mock_func.reset_mock()

    def tearDown(self):
        """Clean up after each test."""
        if os.path.exists(self.temp_config_file_path):
            os.remove(self.temp_config_file_path)

    def test_01_initialization(self):
        print("\nRunning test_01_initialization...")
        from collections import deque
        self.assertEqual(self.editor_logic.current_main_content, "This is the initial document content.")
        self.assertEqual(self.editor_logic.data["version"], 1.0)
        self.assertTrue(isinstance(self.editor_logic.edit_request_queue, deque))
        self.assertEqual(len(self.editor_logic.edit_request_queue), 0)
        self.assertIsNone(self.editor_logic.active_edit_task)
        print("test_01_initialization PASSED")

    def test_02_add_edit_request_and_process_approve(self):
        print("\nRunning test_02_add_edit_request_and_process_approve...")
        self.editor_logic.add_edit_request("initial document", "make it uppercase")

        self.assertEqual(len(self.editor_logic.edit_request_queue), 0)
        self.assertIsNotNone(self.editor_logic.active_edit_task)
        self.assertEqual(self.editor_logic.active_edit_task['user_hint'], "initial document")
        self.assertEqual(self.editor_logic.active_edit_task['status'], "awaiting_location_confirmation")

        self.mock_callbacks['confirm_location_details'].assert_called_once()
        loc_args, _ = self.mock_callbacks['confirm_location_details'].call_args
        location_info, original_hint, original_instruction = loc_args
        self.assertEqual(location_info['snippet'], "initial document")
        self.assertEqual(original_hint, "initial document")
        self.assertEqual(original_instruction, "make it uppercase")

        self.editor_logic.proceed_with_edit_after_location_confirmation(location_info, original_instruction)
        self.assertEqual(self.editor_logic.active_edit_task['status'], "awaiting_diff_approval")

        self.mock_callbacks['show_diff_preview'].assert_called_once()
        diff_args, _ = self.mock_callbacks['show_diff_preview'].call_args
        original_snippet, edited_snippet, _, _ = diff_args
        self.assertEqual(original_snippet, "initial document")
        self.assertEqual(edited_snippet, "EDITED based on 'make it uppercase': [INITIAL DOCUMENT]")

        self.editor_logic.process_llm_task_decision('approve')
        self.assertIsNone(self.editor_logic.active_edit_task)
        self.assertEqual(self.editor_logic.current_main_content, "This is the EDITED based on 'make it uppercase': [INITIAL DOCUMENT] content.")
        self.assertTrue(self.mock_callbacks['update_view'].called)
        print("test_02_add_edit_request_and_process_approve PASSED")

    def test_03_process_reject_clarify_then_approve(self):
        print("\nRunning test_03_process_reject_clarify_then_approve...")
        self.editor_logic.add_edit_request("content", "change it")

        self.mock_callbacks['confirm_location_details'].assert_called_once()
        loc_args, _ = self.mock_callbacks['confirm_location_details'].call_args
        location_info, _, original_instruction = loc_args
        self.editor_logic.proceed_with_edit_after_location_confirmation(location_info, original_instruction)

        self.mock_callbacks['show_diff_preview'].assert_called_once()

        self.editor_logic.process_llm_task_decision('reject')
        self.mock_callbacks['request_clarification'].assert_called_once()
        self.assertIsNotNone(self.editor_logic.active_edit_task)
        self.assertEqual(self.editor_logic.active_edit_task['status'], "awaiting_clarification")

        current_hint_for_retry = self.editor_logic.active_edit_task['user_hint'] # Get current hint
        self.editor_logic.update_active_task_and_retry(current_hint_for_retry, "make it bold") # Pass hint

        self.assertEqual(self.mock_callbacks['confirm_location_details'].call_count, 2)
        loc_args_2, _ = self.mock_callbacks['confirm_location_details'].call_args
        location_info_2, _, original_instruction_2 = loc_args_2
        self.editor_logic.proceed_with_edit_after_location_confirmation(location_info_2, original_instruction_2)

        self.assertEqual(self.mock_callbacks['show_diff_preview'].call_count, 2)
        diff_args_2, _ = self.mock_callbacks['show_diff_preview'].call_args
        self.assertEqual(diff_args_2[1], "EDITED based on 'make it bold': [CONTENT]")

        self.editor_logic.process_llm_task_decision('approve')
        self.assertIsNone(self.editor_logic.active_edit_task)
        self.assertTrue("EDITED based on 'make it bold': [CONTENT]" in self.editor_logic.current_main_content)
        print("test_03_process_reject_clarify_then_approve PASSED")

    def test_04_process_cancel_task_after_location_confirm(self):
        print("\nRunning test_04_process_cancel_task_after_location_confirm...")
        initial_content = self.editor_logic.current_main_content
        self.editor_logic.add_edit_request("document", "delete this part")

        self.mock_callbacks['confirm_location_details'].assert_called_once()
        loc_args, _ = self.mock_callbacks['confirm_location_details'].call_args
        location_info, _, original_instruction = loc_args
        self.editor_logic.proceed_with_edit_after_location_confirmation(location_info, original_instruction)

        self.mock_callbacks['show_diff_preview'].assert_called_once()

        self.editor_logic.process_llm_task_decision('cancel')
        self.assertIsNone(self.editor_logic.active_edit_task)
        self.assertEqual(self.editor_logic.current_main_content, initial_content)
        self.assertEqual(self.editor_logic.edit_results[-1]['status'], "task_cancelled")
        print("test_04_process_cancel_task_after_location_confirm PASSED")

    def test_05_queue_multiple_requests(self):
        print("\nRunning test_05_queue_multiple_requests...")
        self.editor_logic.add_edit_request("initial", "uppercase it")
        self.assertEqual(len(self.editor_logic.edit_request_queue), 0)

        self.editor_logic.add_edit_request("content", "add exclamation")
        self.assertEqual(len(self.editor_logic.edit_request_queue), 1)

        self.assertIsNotNone(self.editor_logic.active_edit_task)
        self.assertEqual(self.editor_logic.active_edit_task['user_hint'], "initial")

        loc_args1, _ = self.mock_callbacks['confirm_location_details'].call_args
        self.editor_logic.proceed_with_edit_after_location_confirmation(loc_args1[0], loc_args1[2])
        self.editor_logic.process_llm_task_decision('approve')
        self.assertTrue("EDITED based on 'uppercase it': [INITIAL]" in self.editor_logic.current_main_content)

        self.assertIsNotNone(self.editor_logic.active_edit_task, "Second task did not start.")
        self.assertEqual(self.editor_logic.active_edit_task['user_hint'], "content")
        self.assertEqual(len(self.editor_logic.edit_request_queue), 0)

        # confirm_location_details mock was called once for first task, now it will be called for second.
        # We need to get the latest call_args for the second task.
        self.mock_callbacks['confirm_location_details'].assert_any_call(unittest.mock.ANY, "content", "add exclamation")
        loc_args2, _ = self.mock_callbacks['confirm_location_details'].call_args # This gets the *last* call
        self.editor_logic.proceed_with_edit_after_location_confirmation(loc_args2[0], loc_args2[2])
        self.editor_logic.process_llm_task_decision('approve')
        self.assertTrue("EDITED based on 'add exclamation': [CONTENT]" in self.editor_logic.current_main_content)
        self.assertIsNone(self.editor_logic.active_edit_task)
        print("test_05_queue_multiple_requests PASSED")

    def test_06_generic_action_increment_version(self):
        print("\nRunning test_06_generic_action_increment_version...")
        initial_version = self.editor_logic.data["version"]
        self.editor_logic.perform_action("increment_version")
        self.assertEqual(self.editor_logic.data["version"], round(initial_version + 0.1, 1))
        self.assertEqual(self.editor_logic.edit_results[-1]['status'], "action_increment_version_success")
        self.assertTrue(self.mock_callbacks['update_view'].called)
        print("test_06_generic_action_increment_version PASSED")

    def test_07_generic_action_revert_changes(self):
        print("\nRunning test_07_generic_action_revert_changes...")
        original_content_snapshot = str(self.editor_logic.current_main_content)
        original_version_snapshot = self.editor_logic.data["version"]

        self.editor_logic.add_edit_request("initial", "make it different")

        self.mock_callbacks['confirm_location_details'].assert_called_with(
            unittest.mock.ANY,
            "initial",
            "make it different"
        )
        loc_args, _ = self.mock_callbacks['confirm_location_details'].call_args
        location_info_for_proceed = loc_args[0]
        instruction_for_proceed = loc_args[2]

        print(f"test_07: location_info_for_proceed = {location_info_for_proceed}") # Debug print
        self.editor_logic.proceed_with_edit_after_location_confirmation(location_info_for_proceed, instruction_for_proceed)

        self.assertEqual(self.editor_logic.active_edit_task['status'], "awaiting_diff_approval")
        self.assertIsNotNone(self.editor_logic.active_edit_task['llm_generated_snippet_details'])

        self.editor_logic.process_llm_task_decision('approve')

        self.editor_logic.perform_action("increment_version")

        self.assertNotEqual(self.editor_logic.current_main_content, original_content_snapshot)
        self.assertNotEqual(self.editor_logic.data["version"], original_version_snapshot)

        self.editor_logic.perform_action("revert_changes")
        self.assertEqual(self.editor_logic.current_main_content, original_content_snapshot)
        self.assertEqual(self.editor_logic.data["version"], original_version_snapshot)
        self.assertEqual(self.editor_logic.edit_results[-1]['status'], "action_revert_changes_success")
        print("test_07_generic_action_revert_changes PASSED")

if __name__ == '__main__':
    unittest.main()

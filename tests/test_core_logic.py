# tests/test_core_logic.py
import sys
import os
import unittest # Using unittest for a more structured approach
from unittest.mock import MagicMock

# Adjust path to import from src
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root) # Add project root for general imports

# To avoid PyQt5 dependency for core logic tests, we'll try to import core directly
# This is a workaround for the current package structure where __init__ imports runner.
try:
    from src.themule_atomic_hitl.core import SurgicalEditorLogic
except ModuleNotFoundError as e:
    if 'PyQt5' in str(e):
        print("PyQt5 not found, attempting direct import of core.py for testing...")
        core_path = os.path.join(project_root, "src", "themule_atomic_hitl")
        if core_path not in sys.path:
             sys.path.insert(0, core_path)
        import core # Now core should be SurgicalEditorLogic from core.py
        SurgicalEditorLogic = core.SurgicalEditorLogic
    else:
        raise e


class TestSurgicalEditorLogic(unittest.TestCase):

    def setUp(self):
        """Set up for each test."""
        self.mock_callbacks = {
            'update_view': MagicMock(),
            'show_diff_preview': MagicMock(),
            'request_clarification': MagicMock(),
            'show_error': MagicMock()
        }

        self.initial_data = {
            "document_text": "This is the initial document content.",
            "version": 1.0,
            "author": "TestUser"
        }

        self.config = {
            "fields": [
                {"name": "document_text", "type": "diff-editor", "originalDataField": "original_doc", "modifiedDataField": "document_text"},
                {"name": "author", "type": "text-input", "label": "Author"},
                {"name": "version", "type": "label", "label": "Version"}
            ],
            "actions": [
                {"name": "increment_version", "label": "Increment Version"},
                {"name": "revert_changes", "label": "Revert All Changes"}
            ]
        }

        # Ensure main_text_field is correctly identified from config
        # In this test config, modifiedDataField is "document_text"
        self.editor_logic = SurgicalEditorLogic(
            initial_data=self.initial_data,
            config=self.config,
            callbacks=self.mock_callbacks
        )
        # Reset mocks for each test run, as they are instance variables on editor_logic.callbacks
        for mock_func in self.mock_callbacks.values():
            mock_func.reset_mock()

    def test_01_initialization(self):
        print("\nRunning test_01_initialization...")
        from collections import deque # Import deque for type checking
        self.assertEqual(self.editor_logic.current_main_content, "This is the initial document content.")
        self.assertEqual(self.editor_logic.data["version"], 1.0)
        self.assertTrue(isinstance(self.editor_logic.edit_request_queue, deque))
        self.assertEqual(len(self.editor_logic.edit_request_queue), 0)
        self.assertIsNone(self.editor_logic.active_edit_task)
        print("test_01_initialization PASSED")

    def test_02_add_edit_request_and_process_approve(self):
        print("\nRunning test_02_add_edit_request_and_process_approve...")
        self.editor_logic.add_edit_request("initial document", "make it uppercase")

        self.assertEqual(len(self.editor_logic.edit_request_queue), 0) # Should be popped by _process_next_edit_request
        self.assertIsNotNone(self.editor_logic.active_edit_task)
        self.assertEqual(self.editor_logic.active_edit_task['hint'], "initial document")

        # _execute_llm_attempt should have been called, leading to show_diff_preview
        self.mock_callbacks['show_diff_preview'].assert_called_once()
        args, _ = self.mock_callbacks['show_diff_preview'].call_args
        original_snippet, edited_snippet, _, _ = args
        self.assertEqual(original_snippet, "initial document")
        self.assertEqual(edited_snippet, "EDITED based on 'make it uppercase': [INITIAL DOCUMENT]")

        # Simulate user approving the LLM task
        self.editor_logic.process_llm_task_decision('approve')
        self.assertIsNone(self.editor_logic.active_edit_task)
        self.assertEqual(self.editor_logic.current_main_content, "This is the EDITED based on 'make it uppercase': [INITIAL DOCUMENT] content.")
        self.mock_callbacks['update_view'].assert_called() # Should be called after approval
        print("test_02_add_edit_request_and_process_approve PASSED")

    def test_03_process_reject_clarify_then_approve(self):
        print("\nRunning test_03_process_reject_clarify_then_approve...")
        self.editor_logic.add_edit_request("content", "change it")
        self.mock_callbacks['show_diff_preview'].assert_called_once() # First LLM attempt

        # User rejects (wants to clarify)
        self.editor_logic.process_llm_task_decision('reject')
        self.mock_callbacks['request_clarification'].assert_called_once()
        self.assertIsNotNone(self.editor_logic.active_edit_task) # Task still active, awaiting clarification
        self.assertIsNone(self.editor_logic.pending_llm_edit) # Provisional edit discarded

        # Frontend provides clarification
        self.editor_logic.update_active_task_and_retry("content", "make it bold")
        self.assertEqual(self.mock_callbacks['show_diff_preview'].call_count, 2) # Second LLM attempt
        args, _ = self.mock_callbacks['show_diff_preview'].call_args
        self.assertEqual(args[1], "EDITED based on 'make it bold': [CONTENT]") # New edited snippet

        # User approves the clarified edit
        self.editor_logic.process_llm_task_decision('approve')
        self.assertIsNone(self.editor_logic.active_edit_task)
        self.assertTrue("EDITED based on 'make it bold': [CONTENT]" in self.editor_logic.current_main_content)
        print("test_03_process_reject_clarify_then_approve PASSED")

    def test_04_process_cancel_task(self):
        print("\nRunning test_04_process_cancel_task...")
        initial_content = self.editor_logic.current_main_content
        self.editor_logic.add_edit_request("document", "delete this part")
        self.mock_callbacks['show_diff_preview'].assert_called_once()

        # User cancels the task
        self.editor_logic.process_llm_task_decision('cancel')
        self.assertIsNone(self.editor_logic.active_edit_task)
        self.assertEqual(self.editor_logic.current_main_content, initial_content) # Content should not have changed
        self.assertEqual(self.editor_logic.edit_results[-1]['status'], "task_cancelled")
        print("test_04_process_cancel_task PASSED")

    def test_05_queue_multiple_requests(self):
        print("\nRunning test_05_queue_multiple_requests...")
        self.editor_logic.add_edit_request("initial", "uppercase it") # Request 1
        self.editor_logic.add_edit_request("content", "add exclamation") # Request 2 - gets queued

        self.assertEqual(len(self.editor_logic.edit_request_queue), 1) # Req 2 is in queue
        self.assertIsNotNone(self.editor_logic.active_edit_task)
        self.assertEqual(self.editor_logic.active_edit_task['hint'], "initial")

        # Approve first request
        self.editor_logic.process_llm_task_decision('approve')
        self.assertTrue("EDITED based on 'uppercase it': [INITIAL]" in self.editor_logic.current_main_content)
        # self.assertIsNone(self.editor_logic.active_edit_task) # Momentarily None before next is picked - REMOVED as _process_next_edit_request is called immediately

        # Micro-delay or trigger to ensure _process_next_edit_request runs if it's not instant
        # In current design, approve should trigger _process_next_edit_request

        self.assertIsNotNone(self.editor_logic.active_edit_task, "Second task did not start processing.")
        self.assertEqual(self.editor_logic.active_edit_task['hint'], "content")
        self.assertEqual(len(self.editor_logic.edit_request_queue), 0)

        # Approve second request
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
        self.mock_callbacks['update_view'].assert_called()
        print("test_06_generic_action_increment_version PASSED")

    def test_07_generic_action_revert_changes(self):
        print("\nRunning test_07_generic_action_revert_changes...")
        original_content_snapshot = str(self.editor_logic.current_main_content) # Make a copy
        original_version_snapshot = self.editor_logic.data["version"]

        self.editor_logic.add_edit_request("initial", "make it different")
        self.editor_logic.process_llm_task_decision('approve') # Change content
        self.editor_logic.perform_action("increment_version") # Change version

        self.assertNotEqual(self.editor_logic.current_main_content, original_content_snapshot)
        self.assertNotEqual(self.editor_logic.data["version"], original_version_snapshot)

        self.editor_logic.perform_action("revert_changes")
        self.assertEqual(self.editor_logic.current_main_content, original_content_snapshot)
        self.assertEqual(self.editor_logic.data["version"], original_version_snapshot)
        self.assertEqual(self.editor_logic.edit_results[-1]['status'], "action_revert_changes_success")
        print("test_07_generic_action_revert_changes PASSED")

if __name__ == '__main__':
    unittest.main()

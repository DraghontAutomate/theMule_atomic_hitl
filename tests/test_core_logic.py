# tests/test_core_logic.py
"""
This module contains unit tests for the SurgicalEditorLogic class from the core module.
It uses the `unittest` framework and `unittest.mock.MagicMock` to simulate UI callbacks
and verify the behavior of the core logic in isolation.
"""

import sys
import os
import unittest
from unittest.mock import MagicMock # Only MagicMock needed
import json
import re

# We need the actual LLMService for spec'ing the mock
from src.themule_atomic_hitl.llm_service import LLMService
from src.themule_atomic_hitl.core import SurgicalEditorLogic
from src.themule_atomic_hitl.config import Config

# --- Path Adjustment ---
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# Ensure src is also in path if necessary, though direct imports from src should work if project_root is there.
src_dir = os.path.join(project_root, "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)


class TestSurgicalEditorLogic(unittest.TestCase):
    """
    Test suite for the SurgicalEditorLogic class.
    LLMService is mocked directly on the instance in setUp.
    """

    def setUp(self):
        """
        Set up method called before each test case.
        Initializes mock callbacks, initial data, config, and the SurgicalEditorLogic instance.
        LLMService is directly mocked on the editor_logic instance.
        """
        self.mock_callbacks = {
            'update_view': MagicMock(),
            'show_diff_preview': MagicMock(),
            'request_clarification': MagicMock(),
            'show_error': MagicMock(),
            'confirm_location_details': MagicMock()
        }

        self.sample_initial_data = {
            "document_text": "This is the initial document content.",
            "original_doc": "This is the initial document content.",
            "version": 1.0
        }

        self.sample_config_dict = {
            "fields": [
                {"name": "diff_editor_main", "type": "diff-editor",
                 "originalDataField": "original_doc", "modifiedDataField": "document_text"},
                {"name": "author", "type": "text-input", "label": "Author"},
                {"name": "version", "type": "label", "label": "Version"}
            ],
            "actions": [
                {"name": "increment_version", "label": "Increment Version"},
                {"name": "revert_changes", "label": "Revert All Changes"}
            ],
            "settings": {"defaultWindowTitle": "Test Window"},
            "llm_config": { # Ensure LLMService can be initialized by SurgicalEditorLogic
                "providers": {"mock_provider": {"model": "mock_model"}}, # Actual provider names like 'google' or 'local' might be needed if LLMService init checks them
                "task_llms": {"locator": "mock_provider", "editor": "mock_provider", "default": "mock_provider"},
                "system_prompts": {"locator": "mock_locator_prompt", "editor": "mock_editor_prompt"}
            }
        }
        self.temp_config_file_path = "temp_test_core_config.json"
        with open(self.temp_config_file_path, 'w') as f:
            json.dump(self.sample_config_dict, f)

        self.config_object = Config(custom_config_path=self.temp_config_file_path)

        # Instantiate SurgicalEditorLogic
        self.editor_logic = SurgicalEditorLogic(
            initial_data=dict(self.sample_initial_data),
            config=self.config_object,
            callbacks=self.mock_callbacks
            # llm_service_instance is not used with this strategy, rely on monkeypatching after init
        )

        # --- Direct instance mocking of LLMService ---
        # Replace the llm_service attribute on the instance with a MagicMock
        self.editor_logic.llm_service = MagicMock(spec=LLMService)

        # Define and set a default side_effect for invoke_llm for most tests
        def default_mock_invoke_llm_side_effect(task_name, user_prompt):
            if task_name == "locator":
                hint_match = re.search(r"hint: '([^']*)'", user_prompt)
                hint = hint_match.group(1) if hint_match else "UNKNOWN_HINT"
                # Simulate finding the hint as the snippet
                return hint
            elif task_name == "editor":
                snippet_match = re.search(r"Original Snippet:\n---\n(.*?)\n---", user_prompt, re.DOTALL)
                snippet_to_edit = snippet_match.group(1).strip() if snippet_match else "UNKNOWN_SNIPPET"
                instruction_match = re.search(r"Instruction: (.*)", user_prompt)
                instruction = instruction_match.group(1).strip() if instruction_match else "UNKNOWN_INSTRUCTION"
                # Specific logic for test_03's retry
                if "bold" in instruction and "content" in snippet_to_edit.lower(): # Make it more robust for test_03
                    return f"EDITED based on '{instruction}': [CONTENT]"
                return f"EDITED based on '{instruction}': [{snippet_to_edit.upper()}]"
            return "Unknown LLM task"

        self.editor_logic.llm_service.invoke_llm.side_effect = default_mock_invoke_llm_side_effect

        # Reset other mocks
        for mock_func in self.mock_callbacks.values():
            mock_func.reset_mock()

    def tearDown(self):
        if os.path.exists(self.temp_config_file_path):
            os.remove(self.temp_config_file_path)

    def test_01_initialization(self):
        from collections import deque
        self.assertEqual(self.editor_logic.current_main_content, "This is the initial document content.")
        self.assertEqual(self.editor_logic.data["version"], 1.0)
        self.assertTrue(isinstance(self.editor_logic.edit_request_queue, deque))
        self.assertEqual(len(self.editor_logic.edit_request_queue), 0)
        self.assertIsNone(self.editor_logic.active_edit_task)

    def test_02_add_edit_request_and_process_approve(self):
        self.editor_logic.add_edit_request(
            instruction="make it uppercase", request_type="hint_based", hint="initial document")
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
        expected_content = "This is the EDITED based on 'make it uppercase': [INITIAL DOCUMENT] content."
        self.assertEqual(self.editor_logic.current_main_content, expected_content)
        self.assertTrue(self.mock_callbacks['update_view'].called)

    def test_03_process_reject_clarify_then_approve(self):
        self.editor_logic.add_edit_request(instruction="change it", request_type="hint_based", hint="content")
        self.mock_callbacks['confirm_location_details'].assert_called_once()
        loc_args, _ = self.mock_callbacks['confirm_location_details'].call_args
        location_info, _, original_instruction = loc_args
        self.editor_logic.proceed_with_edit_after_location_confirmation(location_info, original_instruction)
        self.mock_callbacks['show_diff_preview'].assert_called_once()

        self.editor_logic.process_llm_task_decision('reject')
        self.mock_callbacks['request_clarification'].assert_called_once()
        self.assertIsNotNone(self.editor_logic.active_edit_task)
        self.assertEqual(self.editor_logic.active_edit_task['status'], "awaiting_clarification")

        current_hint_for_retry = self.editor_logic.active_edit_task['user_hint']
        self.editor_logic.update_active_task_and_retry(current_hint_for_retry, "make it bold")

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

    def test_04_process_cancel_task_after_location_confirm(self):
        initial_content = self.editor_logic.current_main_content
        self.editor_logic.add_edit_request(instruction="delete this part", request_type="hint_based", hint="document")
        self.mock_callbacks['confirm_location_details'].assert_called_once()
        loc_args, _ = self.mock_callbacks['confirm_location_details'].call_args
        location_info, _, original_instruction = loc_args
        self.editor_logic.proceed_with_edit_after_location_confirmation(location_info, original_instruction)
        self.mock_callbacks['show_diff_preview'].assert_called_once()

        self.editor_logic.process_llm_task_decision('cancel')
        self.assertIsNone(self.editor_logic.active_edit_task)
        self.assertEqual(self.editor_logic.current_main_content, initial_content)
        self.assertEqual(self.editor_logic.edit_results[-1]['status'], "task_cancelled")

    def test_05_queue_multiple_requests(self):
        self.editor_logic.add_edit_request(instruction="uppercase it", request_type="hint_based", hint="initial")
        self.assertEqual(len(self.editor_logic.edit_request_queue), 0)
        self.editor_logic.add_edit_request(instruction="add exclamation", request_type="hint_based", hint="content")
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

        # Default mock should provide 'content' as snippet for hint 'content'
        # And then 'EDITED based on 'add exclamation': [CONTENT]' for the edit
        self.mock_callbacks['confirm_location_details'].assert_any_call(unittest.mock.ANY, "content", "add exclamation")
        loc_args2, _ = self.mock_callbacks['confirm_location_details'].call_args
        self.editor_logic.proceed_with_edit_after_location_confirmation(loc_args2[0], loc_args2[2])
        self.editor_logic.process_llm_task_decision('approve')
        self.assertTrue("EDITED based on 'add exclamation': [CONTENT]" in self.editor_logic.current_main_content)
        self.assertIsNone(self.editor_logic.active_edit_task)

    def test_06_generic_action_increment_version(self):
        initial_version_str = self.editor_logic.data["version"]
        initial_version = float(initial_version_str) if isinstance(initial_version_str, str) else initial_version_str
        self.editor_logic.perform_action("increment_version")
        current_version_in_data = self.editor_logic.data["version"]
        if isinstance(current_version_in_data, str):
             current_version_in_data = float(current_version_in_data)
        self.assertAlmostEqual(current_version_in_data, initial_version + 0.1, places=1)
        self.assertEqual(self.editor_logic.edit_results[-1]['status'], "action_increment_version_success")
        self.assertTrue(self.mock_callbacks['update_view'].called)

    def test_07_generic_action_revert_changes(self):
        original_content_snapshot = str(self.editor_logic.current_main_content)
        original_version_snapshot = self.editor_logic.data["version"]

        self.editor_logic.add_edit_request(instruction="make it different", request_type="hint_based", hint="initial")
        self.mock_callbacks['confirm_location_details'].assert_called_with(
            unittest.mock.ANY, "initial", "make it different")
        loc_args, _ = self.mock_callbacks['confirm_location_details'].call_args
        location_info_for_proceed = loc_args[0]
        instruction_for_proceed = loc_args[2]
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

if __name__ == '__main__':
    unittest.main()

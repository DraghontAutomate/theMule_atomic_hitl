import unittest
from unittest.mock import patch, MagicMock
import sys
import os
import json
from typing import Dict, Any, Optional
import tempfile
import shutil

# Adjust path to import from src
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.themule_atomic_hitl.hitl_node import hitl_node_run
from src.themule_atomic_hitl.config import Config, DEFAULT_CONFIG

# Mock QApplication to prevent actual UI from launching during tests
# We need to be careful as hitl_node_run itself tries to manage QApplication
# We'll mock it at the earliest point of import for hitl_node or its dependencies (runner)

from PyQt5.QtWidgets import QMainWindow

@patch('src.themule_atomic_hitl.runner.QApplication', MagicMock())
@patch('src.themule_atomic_hitl.hitl_node.QApplication', MagicMock())

class TestHitlNodeRun(unittest.TestCase):

    def setUp(self):
        self.default_modified_field = DEFAULT_CONFIG['fields'][1]['modifiedDataField']
        self.default_original_field = DEFAULT_CONFIG['fields'][1]['originalDataField']

        self.test_dir = tempfile.mkdtemp()
        self.custom_config_data = {
            "fields": [{
                "name": "main_diff", "type": "diff-editor",
                "originalDataField": "origText", "modifiedDataField": "modText"
            }],
            "settings": {"defaultWindowTitle": "Custom Test Window"}
        }
        self.custom_config_path = os.path.join(self.test_dir, "test_hitl_node_custom_config.json")
        with open(self.custom_config_path, 'w') as f:
            json.dump(self.custom_config_data, f)

        self.mock_final_data = {"status": "approved", self.default_modified_field: "final content"}

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    @patch('src.themule_atomic_hitl.hitl_node.run_application')
    def test_run_with_string_content_default_config(self, mock_run_application):
        mock_run_application.return_value = self.mock_final_data
        test_string = "This is a test string."

        result = hitl_node_run(content_to_review=test_string)

        self.assertEqual(result, self.mock_final_data)
        mock_run_application.assert_called_once()
        args, kwargs = mock_run_application.call_args

        # Check initial_data_param
        expected_initial_data = {
            self.default_modified_field: test_string,
            self.default_original_field: test_string
        }
        self.assertEqual(kwargs['initial_data_param'], expected_initial_data)

        # Check config_param_dict (should be a dict with default config values)
        self.assertIsInstance(kwargs['config_param_dict'], dict)

        self.assertEqual(kwargs['config_param_dict'], DEFAULT_CONFIG)
        self.assertIsNone(kwargs['qt_app'])


    @patch('src.themule_atomic_hitl.hitl_node.run_application')
    def test_run_with_dict_content_default_config(self, mock_run_application):
        mock_run_application.return_value = self.mock_final_data
        input_dict = {
            self.default_modified_field: "modified from dict",
            self.default_original_field: "original from dict",
            "other_meta": "some value"
        }

        result = hitl_node_run(content_to_review=input_dict.copy())
        self.assertEqual(result, self.mock_final_data)
        mock_run_application.assert_called_once()
        args, kwargs = mock_run_application.call_args
        self.assertEqual(kwargs['initial_data_param'], input_dict)
        self.assertIsInstance(kwargs['config_param_dict'], dict)

        self.assertEqual(kwargs['config_param_dict'], DEFAULT_CONFIG) # it's the dict representation


    @patch('src.themule_atomic_hitl.hitl_node.run_application')
    def test_run_with_string_content_custom_config(self, mock_run_application):
        custom_mock_final_data = {"status": "approved", "modText": "final custom content"}
        mock_run_application.return_value = custom_mock_final_data
        test_string = "Test with custom config."

        result = hitl_node_run(content_to_review=test_string, custom_config_path=self.custom_config_path)
        self.assertEqual(result, custom_mock_final_data)

        mock_run_application.assert_called_once()
        args, kwargs = mock_run_application.call_args

        expected_initial_data = {
            "modText": test_string,
            "origText": test_string
        }
        self.assertEqual(kwargs['initial_data_param'], expected_initial_data)
        self.assertIsInstance(kwargs['config_param_dict'], dict)
        self.assertEqual(kwargs['config_param_dict']['settings']['defaultWindowTitle'], self.custom_config_data['settings']['defaultWindowTitle'])
        self.assertEqual(kwargs['config_param_dict']['fields'][0]['name'], self.custom_config_data['fields'][0]['name'])


    @patch('src.themule_atomic_hitl.hitl_node.run_application')
    def test_run_with_dict_content_missing_fields(self, mock_run_application):
        mock_run_application.return_value = self.mock_final_data
        input_dict = {"metadata": "only this"}

        result = hitl_node_run(content_to_review=input_dict.copy())
        self.assertEqual(result, self.mock_final_data)

        args, kwargs = mock_run_application.call_args
        expected_data = {
            "metadata": "only this",
            self.default_modified_field: "",
            self.default_original_field: ""
        }
        self.assertEqual(kwargs['initial_data_param'], expected_data)

    def test_invalid_content_type(self):
        with patch('logging.error') as mock_logging_error:
            result = hitl_node_run(content_to_review=12345)
            self.assertIsNone(result)
            mock_logging_error.assert_any_call("content_to_review must be a string or a dictionary.")

    @patch('src.themule_atomic_hitl.hitl_node.run_application')
    def test_run_with_existing_qt_app(self, mock_run_application):
        mock_existing_app_instance = MagicMock()
        mock_main_window = MagicMock(spec=QMainWindow)
        mock_main_window.backend = MagicMock()
        mock_main_window.backend.logic = MagicMock()
        mock_main_window.backend.logic.get_final_data.return_value = self.mock_final_data
        mock_main_window.isVisible.return_value = False
        mock_run_application.return_value = mock_main_window


        result = hitl_node_run(content_to_review="test for existing app", existing_qt_app=mock_existing_app_instance)

        self.assertEqual(result, self.mock_final_data)
        mock_run_application.assert_called_once()
        _, kwargs = mock_run_application.call_args
        self.assertEqual(kwargs['qt_app'], mock_existing_app_instance)
        mock_main_window.show.assert_called_once()

    @patch('src.themule_atomic_hitl.hitl_node.run_application', side_effect=Exception("Test Exception from run_app"))
    def test_exception_in_run_application(self, mock_run_application):
        with patch('logging.error') as mock_logging_error:
            result = hitl_node_run(content_to_review="test")
            self.assertIsNone(result)
            mock_logging_error.assert_any_call("Error in hitl_node_run: Test Exception from run_app", exc_info=True)


if __name__ == '__main__':
    unittest.main()

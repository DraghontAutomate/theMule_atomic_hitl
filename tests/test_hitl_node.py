import unittest
from unittest.mock import patch, MagicMock
import sys
import os
import json
from typing import Dict, Any, Optional

# Adjust path to import from src
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.themule_atomic_hitl.hitl_node import hitl_node_run
from src.themule_atomic_hitl.config import Config, DEFAULT_CONFIG

# Mock QApplication to prevent actual UI from launching during tests
# We need to be careful as hitl_node_run itself tries to manage QApplication
# We'll mock it at the earliest point of import for hitl_node or its dependencies (runner)

# --- Revised QApplication Mocking Strategy ---
# Create a single, configurable mock instance for QApplication class behavior
mock_q_application_class_for_tests = MagicMock(name="GlobalMockQApplicationClass")

# Configure its static/class methods and attributes that are used by the code
mock_q_application_class_for_tests.instance.return_value = None # Default for hitl_node_run to create app
mock_q_application_class_for_tests.loopLevel.return_value = 0

# QApplication.QEventLoop needs to be a mock constructor that returns a QEventLoop instance mock
mock_qeventloop_constructor_on_qapp_mock = MagicMock(name="QEventLoopConstructorOnQAppMock")
mock_q_application_class_for_tests.QEventLoop = mock_qeventloop_constructor_on_qapp_mock

# This function will be used by @patch's new_callable to provide the same mock instance
def get_configured_mock_q_application_class():
    # Reset parts of the mock that might carry state between tests if needed,
    # though unittest.mock usually handles this well for separate test methods.
    # For safety, reset what instance() returns and the QEventLoop constructor mock.
    mock_q_application_class_for_tests.instance.return_value = None
    mock_q_application_class_for_tests.QEventLoop.reset_mock(return_value=True, side_effect=True)
    # Ensure QEventLoop's own return_value (the event loop instance) is also reset if it was set directly
    if hasattr(mock_q_application_class_for_tests.QEventLoop, 'return_value') and \
       isinstance(mock_q_application_class_for_tests.QEventLoop.return_value, MagicMock):
        mock_q_application_class_for_tests.QEventLoop.return_value.reset_mock(return_value=True, side_effect=True)

    mock_q_application_class_for_tests.loopLevel.return_value = 0
    return mock_q_application_class_for_tests

from PyQt5.QtWidgets import QMainWindow # Import QMainWindow for isinstance checks

# Patch QApplication where it's imported by the modules under test
@patch('src.themule_atomic_hitl.hitl_node.QApplication', new_callable=get_configured_mock_q_application_class)
@patch('src.themule_atomic_hitl.runner.QApplication', new_callable=get_configured_mock_q_application_class)
class TestHitlNodeRun(unittest.TestCase):

    def setUp(self):
        # Ensure the global mock is reset for QApplication.instance() for typical test cases
        # where hitl_node_run is expected to try and create its own app.
        # The get_configured_mock_q_application_class callable does some resetting.
        # If a test needs QApplication.instance() to return a specific app, it can configure
        # mock_q_application_class_for_tests.instance.return_value directly.

        # For the QEventLoop constructor mock, ensure its return_value is not pre-set globally
        # unless that's a desired default. Tests needing specific QEventLoop instances
        # will set mock_q_application_class_for_tests.QEventLoop.return_value.
        mock_q_application_class_for_tests.QEventLoop.return_value = MagicMock(name="DefaultEventLoopInstanceOnSetup")


        self.default_modified_field = DEFAULT_CONFIG['fields'][1]['modifiedDataField']
        self.default_original_field = DEFAULT_CONFIG['fields'][1]['originalDataField']

        self.custom_config_data = {
            "fields": [{
                "name": "main_diff", "type": "diff-editor",
                "originalDataField": "origText", "modifiedDataField": "modText"
            }],
            "settings": {"defaultWindowTitle": "Custom Test Window"}
        }
        self.custom_config_path = "test_hitl_node_custom_config.json"
        with open(self.custom_config_path, 'w') as f:
            json.dump(self.custom_config_data, f)

        self.mock_final_data = {"status": "approved", self.default_modified_field: "final content"}

    def tearDown(self):
        if os.path.exists(self.custom_config_path):
            os.remove(self.custom_config_path)

    @patch('src.themule_atomic_hitl.hitl_node.run_application')
    def test_run_with_string_content_default_config(self, mock_run_application, mock_runner_qapp, mock_hitl_qapp): # Added mock args
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
        self.assertEqual(kwargs['config_param_dict'], DEFAULT_CONFIG) # it's the dict representation
        self.assertIsNone(kwargs['qt_app']) # No existing_qt_app passed

    @patch('src.themule_atomic_hitl.hitl_node.run_application')
    def test_run_with_dict_content_default_config(self, mock_run_application, mock_runner_qapp, mock_hitl_qapp): # Added mock args
        mock_run_application.return_value = self.mock_final_data
        input_dict = {
            self.default_modified_field: "modified from dict",
            self.default_original_field: "original from dict",
            "other_meta": "some value"
        }

        result = hitl_node_run(content_to_review=input_dict.copy()) # Pass a copy
        self.assertEqual(result, self.mock_final_data)
        mock_run_application.assert_called_once()
        args, kwargs = mock_run_application.call_args
        self.assertEqual(kwargs['initial_data_param'], input_dict)
        self.assertIsInstance(kwargs['config_param_dict'], dict)
        self.assertEqual(kwargs['config_param_dict'], DEFAULT_CONFIG) # it's the dict representation

    @patch('src.themule_atomic_hitl.hitl_node.run_application')
    def test_run_with_string_content_custom_config(self, mock_run_application, mock_runner_qapp, mock_hitl_qapp): # Added mock args
        custom_mock_final_data = {"status": "approved", "modText": "final custom content"}
        mock_run_application.return_value = custom_mock_final_data
        test_string = "Test with custom config."

        result = hitl_node_run(content_to_review=test_string, custom_config_path=self.custom_config_path)
        self.assertEqual(result, custom_mock_final_data)

        mock_run_application.assert_called_once()
        args, kwargs = mock_run_application.call_args

        expected_initial_data = {
            "modText": test_string, # Based on custom_config_data
            "origText": test_string  # Based on custom_config_data
        }
        self.assertEqual(kwargs['initial_data_param'], expected_initial_data)
        self.assertIsInstance(kwargs['config_param_dict'], dict)
        # For custom config, we check a specific value rather than the whole dict equality
        # as the hitl_node.py creates a Config object then passes its dict representation.
        # The Config object merges custom settings with defaults.
        self.assertEqual(kwargs['config_param_dict']['settings']['defaultWindowTitle'], self.custom_config_data['settings']['defaultWindowTitle'])
        # We also need to ensure that default fields/actions are present if not overridden by custom config
        self.assertEqual(kwargs['config_param_dict']['fields'][0]['name'], self.custom_config_data['fields'][0]['name'])


    @patch('src.themule_atomic_hitl.hitl_node.run_application')
    def test_run_with_dict_content_missing_fields(self, mock_run_application, mock_runner_qapp, mock_hitl_qapp): # Added mock args
        mock_run_application.return_value = self.mock_final_data
        # Dict is missing originalText and editedText
        input_dict = {"metadata": "only this"}

        result = hitl_node_run(content_to_review=input_dict.copy())
        self.assertEqual(result, self.mock_final_data)

        args, kwargs = mock_run_application.call_args
        expected_data = {
            "metadata": "only this",
            self.default_modified_field: "", # Should be initialized
            self.default_original_field: ""  # Should be initialized
        }
        self.assertEqual(kwargs['initial_data_param'], expected_data)

    def test_invalid_content_type(self, mock_runner_qapp, mock_hitl_qapp): # Added mock args
        with patch('builtins.print') as mock_print: # Suppress error print
            result = hitl_node_run(content_to_review=12345) # Invalid type
            self.assertIsNone(result)
            mock_print.assert_any_call("Error: content_to_review must be a string or a dictionary.")

    @patch('src.themule_atomic_hitl.hitl_node.run_application')
    def test_run_with_existing_qt_app(self, mock_run_application_in_test, mock_runner_qapp, mock_hitl_qapp_class_mock):
        mock_existing_app_instance = MagicMock(name="MockExistingAppInstance") # Replaced MockQApplicationInstance

        the_actual_mock_main_window = MagicMock(name="TheMockMainWindowInstance")
        # Make the mock appear as an instance of QMainWindow
        the_actual_mock_main_window.__class__ = QMainWindow
        the_actual_mock_main_window.backend = MagicMock(name="MockBackend")
        the_actual_mock_main_window.backend.sessionTerminatedSignal = MagicMock(name="MockSignal")
        the_actual_mock_main_window.backend.logic.get_final_data.return_value = self.mock_final_data
        # QMainWindow needs isVisible() and show() methods for the logic in hitl_node_run
        the_actual_mock_main_window.isVisible = MagicMock(return_value=False)
        the_actual_mock_main_window.show = MagicMock()


        mock_run_application_in_test.return_value = the_actual_mock_main_window

        # Call the function under test
        result = hitl_node_run(content_to_review="test for existing app", existing_qt_app=mock_existing_app_instance)

        mock_run_application_in_test.assert_called_once()
        call_args_info = mock_run_application_in_test.call_args

        self.assertIsNotNone(result, "hitl_node_run returned None unexpectedly.") # Check it's not None first
        self.assertEqual(result, self.mock_final_data)

        _, kwargs_run_app = call_args_info # Use the previously captured call_args_info
        self.assertEqual(kwargs_run_app['qt_app'], mock_existing_app_instance)

        # Get the instance of QEventLoop that was created when mock_hitl_qapp_class_mock.QEventLoop()
        # (the constructor for our QEventLoop mock class) was called inside hitl_node_run.
        # The .return_value of a mock that acts as a constructor refers to the instance it created.
        actual_event_loop_instance_created = mock_hitl_qapp_class_mock.QEventLoop.return_value

        the_actual_mock_main_window.backend.sessionTerminatedSignal.connect.assert_called_with(actual_event_loop_instance_created.quit)
        actual_event_loop_instance_created.exec_.assert_called_once()
        the_actual_mock_main_window.show.assert_called_once()

    @patch('src.themule_atomic_hitl.hitl_node.run_application', side_effect=Exception("Test Exception from run_app"))
    def test_exception_in_run_application(self, mock_run_application, mock_runner_qapp, mock_hitl_qapp): # Added mock args
         with patch('builtins.print') as mock_print: # Suppress error print
            result = hitl_node_run(content_to_review="test")
            self.assertIsNone(result)
            mock_print.assert_any_call("Error in hitl_node_run: Test Exception from run_app")


if __name__ == '__main__':
    unittest.main()

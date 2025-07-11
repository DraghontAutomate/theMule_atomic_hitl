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
    def test_run_with_string_content_default_config(self, mock_run_application, mock_runner_qapp, mock_hitl_qapp):
        """
        Tests hitl_node_run with simple string input and the default configuration.
        - What it tests: Correct preparation of initial_data for run_application
          when input is a string, and that the default Config object is used.
          It also verifies that no existing Qt app is passed.
        - Expected outcome: run_application is called with correctly structured
          initial_data (both original and modified fields set to the input string,
          based on default config field names) and a default Config instance.
          The result from run_application is returned. qt_app parameter should be None.
        - Reason for failure: Incorrect data transformation for string input,
          default config not being loaded or passed properly, issues in how
          run_application is called or its return value handled, or qt_app being
          unexpectedly passed.
        """
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

        # Check config_param (should be a Config instance with default config)
        self.assertIsInstance(kwargs['config_param'], Config)
        self.assertEqual(kwargs['config_param'].get_config(), DEFAULT_CONFIG)
        self.assertIsNone(kwargs['qt_app']) # No existing_qt_app passed

    @patch('src.themule_atomic_hitl.hitl_node.run_application')
    def test_run_with_dict_content_default_config(self, mock_run_application, mock_runner_qapp, mock_hitl_qapp):
        """
        Tests hitl_node_run with dictionary input and the default configuration.
        - What it tests: Ensures that when `content_to_review` is a dictionary containing
          the necessary fields (as per default config), it's passed directly as
          `initial_data_param` to `run_application`. Default config should be used.
        - Expected outcome: `run_application` is called with the input dictionary as
          `initial_data_param` and a default Config instance.
        - Reason for failure: The input dictionary might be unexpectedly altered,
          the default config might not be loaded/passed correctly, or `run_application`
          call is incorrect.
        """
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
        self.assertIsInstance(kwargs['config_param'], Config)
        self.assertEqual(kwargs['config_param'].get_config(), DEFAULT_CONFIG)

    @patch('src.themule_atomic_hitl.hitl_node.run_application')
    def test_run_with_string_content_custom_config(self, mock_run_application, mock_runner_qapp, mock_hitl_qapp):
        """
        Tests hitl_node_run with string input and a custom configuration file.
        - What it tests: Correct preparation of `initial_data` when input is a string,
          but using field names defined in a custom config. Ensures the custom
          Config object is created and passed to `run_application`.
        - Expected outcome: `run_application` is called with `initial_data` structured
          according to the custom config's main editor fields, and a Config instance
          loaded from the custom config path.
        - Reason for failure: Issues loading the custom config, incorrect `initial_data`
          keys based on custom config, or `run_application` not receiving the
          customized Config object.
        """
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
        self.assertIsInstance(kwargs['config_param'], Config)
        self.assertEqual(kwargs['config_param'].get_config()['settings']['defaultWindowTitle'], "Custom Test Window")

    @patch('src.themule_atomic_hitl.hitl_node.run_application')
    def test_run_with_dict_content_missing_fields(self, mock_run_application, mock_runner_qapp, mock_hitl_qapp):
        """
        Tests hitl_node_run with dictionary input that's missing main editor fields.
        - What it tests: Ensures that if `content_to_review` is a dictionary but lacks
          the main editor fields (original and modified text, as per default config),
          these fields are added to `initial_data` with empty strings.
        - Expected outcome: `run_application` is called with `initial_data` that includes
          the original dictionary's items plus the main editor fields initialized to "".
        - Reason for failure: The function might not correctly identify missing fields or
          fail to initialize them with empty strings, potentially leading to errors
          downstream or incorrect data being passed to `run_application`.
        """
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

    def test_invalid_content_type(self, mock_runner_qapp, mock_hitl_qapp):
        """
        Tests hitl_node_run with an invalid type for `content_to_review`.
        - What it tests: The function's error handling when `content_to_review` is
          neither a string nor a dictionary.
        - Expected outcome: The function should print an error message and return None.
          `run_application` should not be called.
        - Reason for failure: Type checking might be incorrect, or the error handling
          path (printing error, returning None) is not followed.
        """
        with patch('builtins.print') as mock_print: # Suppress error print
            result = hitl_node_run(content_to_review=12345) # Invalid type
            self.assertIsNone(result)
            mock_print.assert_any_call("Error: content_to_review must be a string or a dictionary.")

    @patch('src.themule_atomic_hitl.hitl_node.run_application')
    def test_run_with_existing_qt_app(self, mock_run_application_in_test, mock_runner_qapp, mock_hitl_qapp_class_mock):
        """
        Tests hitl_node_run when an existing QApplication instance is provided.
        - What it tests: The function's behavior when `existing_qt_app` is passed.
          It should use this existing app instance, create a new QEventLoop,
          connect the main window's termination signal to the loop's quit slot,
          show the window, and start the event loop.
        - Expected outcome: `run_application` is called with the `qt_app` parameter set
          to the provided `existing_qt_app`. A QEventLoop is created and executed.
          The main window's `show` method is called. The final data from the backend
          logic is returned.
        - Reason for failure: Failure to correctly use the existing Qt app, issues with
          QEventLoop creation or execution, problems connecting or handling the
          termination signal, or incorrect handling of the main window.
        """
        mock_existing_app_instance = MagicMock(name="MockExistingAppInstance") # Replaced MockQApplicationInstance

        the_actual_mock_main_window = MagicMock(name="TheMockMainWindowInstance")
        the_actual_mock_main_window.backend = MagicMock(name="MockBackend")
        the_actual_mock_main_window.backend.sessionTerminatedSignal = MagicMock(name="MockSignal")
        the_actual_mock_main_window.backend.logic.get_final_data.return_value = self.mock_final_data

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
    def test_exception_in_run_application(self, mock_run_application, mock_runner_qapp, mock_hitl_qapp):
        """
        Tests error handling when `run_application` itself raises an exception.
        - What it tests: The main try-except block in `hitl_node_run` that is
          meant to catch exceptions from `run_application`.
        - Expected outcome: An error message should be printed (containing the
          exception message), and the function should return None.
        - Reason for failure: The exception might not be caught correctly, the error
          message format could be wrong, or it might not return None as expected.
        """
         with patch('builtins.print') as mock_print: # Suppress error print
            result = hitl_node_run(content_to_review="test")
            self.assertIsNone(result)
            mock_print.assert_any_call("Error in hitl_node_run: Test Exception from run_app")


if __name__ == '__main__':
    unittest.main()

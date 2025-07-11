import unittest
from unittest.mock import MagicMock, patch, mock_open, call
import sys
import os
import json

# Adjust path to import from src
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# --- Mock PyQt5 Modules ---
# It's crucial to mock these *before* importing the runner module or any of its dependencies
# that might import PyQt5.

# Create mock classes for PyQt5 components
MockQObject = MagicMock(name="MockQObject")
MockQApplication = MagicMock(name="MockQApplication")
MockQMainWindow = MagicMock(name="MockQMainWindow")
MockQWebEngineView = MagicMock(name="MockQWebEngineView")
MockQWebChannel = MagicMock(name="MockQWebChannel")
MockQUrl = MagicMock(name="MockQUrl")
MockPyQtSignal = MagicMock(name="MockPyQtSignal")

# Apply patches to the places where these modules/classes would be imported from
# This uses a dictionary to simulate the module structure
pyqt_mocks = {
    'PyQt5.QtCore': MagicMock(QObject=MockQObject, QUrl=MockQUrl, pyqtSignal=MockPyQtSignal, pyqtSlot=lambda *args, **kwargs: lambda func: func), # Mock pyqtSlot as a decorator
    'PyQt5.QtWidgets': MagicMock(QApplication=MockQApplication, QMainWindow=MockQMainWindow),
    'PyQt5.QtWebEngineWidgets': MagicMock(QWebEngineView=MockQWebEngineView),
    'PyQt5.QtWebChannel': MagicMock(QWebChannel=MockQWebChannel)
}

# The `patch.dict(sys.modules, pyqt_mocks)` ensures that when `runner` or its
# dependencies try to `import PyQt5.QtCore`, etc., they get our mocks.
with patch.dict(sys.modules, pyqt_mocks):
    from src.themule_atomic_hitl.runner import Backend, MainWindow, run_application
    from src.themule_atomic_hitl.config import Config
    from src.themule_atomic_hitl.core import SurgicalEditorLogic


class TestBackend(unittest.TestCase):
    """Tests for the Backend class in runner.py."""

    def setUp(self):
        # Reset mocks used by Backend or its collaborators
        MockPyQtSignal.reset_mock(return_value=True, side_effect=True) # Ensure new signal mocks are created

        self.mock_initial_data = {"text": "initial text", "version": 1}
        self.mock_config_dict = {
            "fields": [{"name": "text", "type": "text-input"}],
            "settings": {"defaultWindowTitle": "Test Window"}
        }
        # Create a Config instance from the dict for Backend
        self.mock_config_manager = Config(custom_config_dict=self.mock_config_dict)

        # Mock SurgicalEditorLogic instance that Backend will create
        self.mock_editor_logic = MagicMock(spec=SurgicalEditorLogic)
        self.mock_editor_logic.config_manager = self.mock_config_manager # Attach a mock config_manager
        self.mock_editor_logic.data = self.mock_initial_data # Attach mock data
        self.mock_editor_logic.get_final_data.return_value = {"text": "final text", "status": "approved"}
        self.mock_editor_logic.edit_results = [{"action": "test"}]
        self.mock_editor_logic.main_text_field = "text"


        # Patch SurgicalEditorLogic within the runner module's scope for Backend's instantiation
        self.surgical_editor_logic_patcher = patch('src.themule_atomic_hitl.runner.SurgicalEditorLogic', return_value=self.mock_editor_logic)
        self.MockSurgicalEditorLogic_class = self.surgical_editor_logic_patcher.start()

        self.backend = Backend(initial_data=self.mock_initial_data, config_manager=self.mock_config_manager)

        # Assign fresh mocks for each signal after Backend instantiation
        self.backend.updateViewSignal = MockPyQtSignal()
        self.backend.showDiffPreviewSignal = MockPyQtSignal()
        self.backend.requestClarificationSignal = MockPyQtSignal()
        self.backend.showErrorSignal = MockPyQtSignal()
        self.backend.promptUserToConfirmLocationSignal = MockPyQtSignal()
        self.backend.sessionTerminatedSignal = MockPyQtSignal()


    def tearDown(self):
        self.surgical_editor_logic_patcher.stop()

    def test_init(self):
        """
        Tests Backend initialization.
        - What it tests: SurgicalEditorLogic is instantiated with correct parameters.
        - Expected outcome: SurgicalEditorLogic called with initial_data, config_manager, and callbacks.
        - Reason for failure: Incorrect instantiation of SurgicalEditorLogic.
        """
        self.MockSurgicalEditorLogic_class.assert_called_once()
        args, kwargs = self.MockSurgicalEditorLogic_class.call_args
        self.assertEqual(args[0], self.mock_initial_data)
        self.assertEqual(args[1], self.mock_config_manager) # Comparing Config instances
        self.assertIn('update_view', args[2]) # Check if callbacks dict is passed

    def test_on_update_view(self):
        """
        Tests the on_update_view callback.
        - What it tests: Emits updateViewSignal with correct data.
        - Expected outcome: updateViewSignal.emit called with data, config, queue_info.
        - Reason for failure: Signal not emitted or emitted with wrong arguments.
        """
        test_data = {"current": "data"}
        test_config = {"a": 1}
        test_queue = {"len": 0}
        self.backend.on_update_view(test_data, test_config, test_queue)
        self.backend.updateViewSignal.emit.assert_called_once_with(test_data, test_config, test_queue)

    def test_on_show_diff_preview(self):
        """Tests on_show_diff_preview callback."""
        self.backend.on_show_diff_preview("orig", "edit", "before", "after")
        self.backend.showDiffPreviewSignal.emit.assert_called_once_with("orig", "edit", "before", "after")

    def test_on_request_clarification(self):
        """Tests on_request_clarification callback."""
        self.backend.on_request_clarification()
        self.backend.requestClarificationSignal.emit.assert_called_once_with()

    def test_on_show_error(self):
        """Tests on_show_error callback."""
        self.backend.on_show_error("error msg")
        self.backend.showErrorSignal.emit.assert_called_once_with("error msg")

    def test_on_confirm_location_details(self):
        """Tests on_confirm_location_details callback."""
        loc_info = {"snippet": "found"}
        self.backend.on_confirm_location_details(loc_info, "hint", "instr")
        self.backend.promptUserToConfirmLocationSignal.emit.assert_called_once_with(loc_info, "hint", "instr")

    def test_getInitialPayload(self):
        """
        Tests the getInitialPayload slot.
        - What it tests: Returns a JSON string of config and data.
        - Expected outcome: Correct JSON string returned.
        - Reason for failure: Incorrect data retrieval or JSON serialization.
        """
        # self.mock_editor_logic.config_manager.get_config.return_value = self.mock_config_dict
        # self.mock_editor_logic.data = self.mock_initial_data

        # In setUp, self.mock_editor_logic is already configured with these.
        # We rely on the Config object associated with mock_editor_logic
        self.mock_editor_logic.config_manager.get_config.return_value = self.mock_config_dict # Ensure the mock logic's config manager returns the dict

        payload_str = self.backend.getInitialPayload()
        payload_dict = json.loads(payload_str)
        self.assertEqual(payload_dict["config"], self.mock_config_dict)
        self.assertEqual(payload_dict["data"], self.mock_initial_data)

    def test_startSession(self):
        """Tests startSession slot."""
        self.backend.startSession()
        self.mock_editor_logic.start_session.assert_called_once()

    def test_submitEditRequest(self):
        """Tests submitEditRequest slot."""
        self.backend.submitEditRequest("hint", "instruction")
        self.mock_editor_logic.add_edit_request.assert_called_once_with("hint", "instruction")

    def test_submitConfirmedLocationAndInstruction(self):
        """Tests submitConfirmedLocationAndInstruction slot."""
        loc = {"s": "text"}
        self.backend.submitConfirmedLocationAndInstruction(loc, "instr")
        self.mock_editor_logic.proceed_with_edit_after_location_confirmation.assert_called_once_with(loc, "instr")

    def test_submitClarificationForActiveTask(self):
        """Tests submitClarificationForActiveTask slot."""
        self.backend.submitClarificationForActiveTask("new_hint", "new_instr")
        self.mock_editor_logic.update_active_task_and_retry.assert_called_once_with("new_hint", "new_instr")

    def test_submitLLMTaskDecisionWithEdit(self):
        """Tests submitLLMTaskDecisionWithEdit slot."""
        self.backend.submitLLMTaskDecisionWithEdit("approve", "edited snippet")
        self.mock_editor_logic.process_llm_task_decision.assert_called_once_with("approve", "edited snippet")

    def test_submitLLMTaskDecision(self):
        """Tests submitLLMTaskDecision slot."""
        self.backend.submitLLMTaskDecision("reject")
        self.mock_editor_logic.process_llm_task_decision.assert_called_once_with("reject", None)

    def test_performAction(self):
        """Tests performAction slot."""
        payload = {"data": 1}
        self.backend.performAction("my_action", payload)
        self.mock_editor_logic.perform_action.assert_called_once_with("my_action", payload)

    @patch('builtins.print')
    def test_terminateSession(self, mock_print):
        """
        Tests terminateSession slot.
        - What it tests: Calls get_final_data, prints info, emits sessionTerminatedSignal.
        - Expected outcome: Correct calls and signal emission.
        - Reason for failure: Logic errors in termination process.
        """
        self.backend.terminateSession()
        self.mock_editor_logic.get_final_data.assert_called_once()
        # Check if print was called for final content, full data, and audit trail
        self.assertGreaterEqual(mock_print.call_count, 3)
        self.backend.sessionTerminatedSignal.emit.assert_called_once()

# MainWindow and run_application tests will need more setup for mocks
# For now, focusing on Backend.
# We need to ensure that the mocks for PyQt5 classes are effective for MainWindow tests.

class TestMainWindow(unittest.TestCase):
    """Tests for the MainWindow class in runner.py."""

    def setUp(self):
        # Reset global PyQt mocks
        MockQApplication.reset_mock()
        MockQMainWindow.reset_mock()
        MockQWebEngineView.reset_mock() # For self.view
        MockQWebEngineView.return_value.page.return_value.setWebChannel.reset_mock() # For setWebChannel
        MockQWebChannel.reset_mock() # For self.channel
        MockQUrl.reset_mock() # For QUrl.fromLocalFile
        MockPyQtSignal.reset_mock(return_value=True, side_effect=True) # For Backend signals

        self.initial_data = {"doc": "content"}
        self.config_dict = {
            "settings": {"defaultWindowTitle": "Test App"},
            "fields": [{"name": "doc", "type": "diff-editor", "originalDataField": "doc", "modifiedDataField": "doc"}]
        }
        self.mock_app_instance = MockQApplication() # Mock QApplication instance

        # Patch Backend within runner for MainWindow's instantiation
        self.backend_patcher = patch('src.themule_atomic_hitl.runner.Backend')
        self.MockBackendClass = self.backend_patcher.start()
        self.mock_backend_instance = self.MockBackendClass.return_value
        self.mock_backend_instance.sessionTerminatedSignal = MockPyQtSignal() # Give the instance a mock signal

        # Patch os.path.exists and QUrl.fromLocalFile for HTML loading
        self.os_path_exists_patcher = patch('src.themule_atomic_hitl.runner.os.path.exists')
        self.mock_os_path_exists = self.os_path_exists_patcher.start()
        self.mock_os_path_exists.return_value = True # Assume HTML file exists

        self.qurl_fromlocalfile_patcher = patch('PyQt5.QtCore.QUrl.fromLocalFile') # Patch where QUrl is defined
        self.mock_qurl_fromlocalfile = self.qurl_fromlocalfile_patcher.start()
        self.mock_qurl_fromlocalfile.return_value = "mocked_url_object"


        # Instantiate MainWindow
        # MainWindow's __init__ calls self.setCentralWidget(self.view)
        # MockQMainWindow needs to handle setCentralWidget call.
        # The actual MockQMainWindow class is already a MagicMock, so it will accept any method call.
        self.main_window = MainWindow(
            initial_data=self.initial_data,
            config_dict_param=self.config_dict,
            app_instance=self.mock_app_instance
        )

    def tearDown(self):
        self.backend_patcher.stop()
        self.os_path_exists_patcher.stop()
        self.qurl_fromlocalfile_patcher.stop()


    def test_init_basic_structure(self):
        """
        Tests MainWindow initialization: basic Qt components.
        - What it tests: Window title set, Backend instantiated, channel set up.
        - Expected outcome: Correct calls to Qt mocks and Backend.
        - Reason for failure: Incorrect setup of Qt components or Backend.
        """
        self.main_window.setWindowTitle.assert_called_with("Test App")
        self.MockBackendClass.assert_called_once() # Check Backend class was called
        # Check Config object was created correctly inside MainWindow and passed to Backend
        backend_args, _ = self.MockBackendClass.call_args
        backend_config_manager_arg = backend_args[1] # Second arg to Backend is config_manager
        self.assertIsInstance(backend_config_manager_arg, Config)
        self.assertEqual(backend_config_manager_arg.get_config()['settings']['defaultWindowTitle'], "Test App")

        self.main_window.view.page().setWebChannel.assert_called_once_with(self.main_window.channel)
        self.main_window.channel.registerObject.assert_called_once_with("backend", self.mock_backend_instance)
        self.mock_backend_instance.sessionTerminatedSignal.connect.assert_called_once_with(self.main_window.on_session_terminated)

    def test_init_html_loading(self):
        """
        Tests HTML loading logic in MainWindow initialization.
        - What it tests: Correct URL is set for the QWebEngineView.
        - Expected outcome: view.setUrl called with the correct local file URL.
        - Reason for failure: HTML path resolution or URL setting is incorrect.
        """
        # This test relies on os.path.exists being True (from setUp)
        # and QUrl.fromLocalFile returning "mocked_url_object"
        self.main_window.view.setUrl.assert_called_once_with("mocked_url_object")
        # Could add more specific checks for path if needed, by inspecting calls to os.path.join

    def test_on_session_terminated(self):
        """
        Tests the on_session_terminated method.
        - What it tests: Window's close method is called.
        - Expected outcome: self.main_window.close() is called.
        - Reason for failure: Close method not called on termination signal.
        """
        self.main_window.close = MagicMock() # Mock the close method directly on the instance
        self.main_window.on_session_terminated()
        self.main_window.close.assert_called_once()


class TestRunApplication(unittest.TestCase):
    """Tests for the run_application function in runner.py."""

    def setUp(self):
        # Reset global PyQt Mocks that run_application might interact with
        MockQApplication.reset_mock()
        MockQApplication.instance.reset_mock() # Reset calls to QApplication.instance()
        MockQApplication.return_value.exec_.reset_mock() # Reset calls to app.exec_()
        MockQMainWindow.reset_mock() # Reset MainWindow mock if it's used directly

        self.initial_data = {"data_key": "data_value"}
        self.config_dict = {"config_key": "config_value", "settings": {"defaultWindowTitle": "RunAppTest"}}

        # Patch MainWindow within runner's scope
        self.mainwindow_patcher = patch('src.themule_atomic_hitl.runner.MainWindow')
        self.MockMainWindowClass = self.mainwindow_patcher.start()
        self.mock_main_window_instance = self.MockMainWindowClass.return_value
        # Simulate the backend and logic structure needed for final data retrieval
        self.mock_main_window_instance.backend = MagicMock()
        self.mock_main_window_instance.backend.logic = MagicMock()
        self.mock_main_window_instance.backend.logic.get_final_data.return_value = {"final": "data"}

    def tearDown(self):
        self.mainwindow_patcher.stop()
        patch.stopall() # Stop any other patches that might have been started

    def test_run_application_creates_new_qapp(self):
        """
        Tests run_application creates a new QApplication if none exists.
        - What it tests: QApplication is instantiated and exec_ is called. MainWindow shown.
        - Expected outcome: Correct instantiation and method calls. Returns final data.
        - Reason for failure: QApplication handling or MainWindow interaction is incorrect.
        """
        MockQApplication.instance.return_value = None # No existing QApplication

        result = run_application(self.initial_data, self.config_dict, qt_app=None)

        MockQApplication.assert_called_once_with([]) # New app created
        self.MockMainWindowClass.assert_called_once() # MainWindow created
        self.mock_main_window_instance.show.assert_called_once() # MainWindow shown
        # The created app instance (MockQApplication.return_value) should have exec_ called
        MockQApplication.return_value.exec_.assert_called_once()
        self.assertEqual(result, {"final": "data"})

    def test_run_application_uses_existing_global_qapp(self):
        """
        Tests run_application uses an existing global QApplication.
        - What it tests: QApplication.instance() is used, exec_ is NOT called by run_application.
        - Expected outcome: Returns MainWindow instance.
        - Reason for failure: Incorrect handling of existing global QApplication.
        """
        mock_existing_global_app = MagicMock(spec=MockQApplication) # A mock that is an "instance"
        MockQApplication.instance.return_value = mock_existing_global_app

        result = run_application(self.initial_data, self.config_dict, qt_app=None)

        MockQApplication.assert_not_called() # No new app created with []
        self.MockMainWindowClass.assert_called_once()
        self.mock_main_window_instance.show.assert_called_once()
        mock_existing_global_app.exec_.assert_not_called() # exec_ not called by this function
        self.assertEqual(result, self.mock_main_window_instance)


    def test_run_application_uses_provided_qapp(self):
        """
        Tests run_application uses a provided QApplication instance.
        - What it tests: Provided qt_app is used, exec_ is NOT called by run_application.
        - Expected outcome: Returns MainWindow instance.
        - Reason for failure: Incorrect handling of provided QApplication.
        """
        mock_provided_app = MagicMock(spec=MockQApplication)

        result = run_application(self.initial_data, self.config_dict, qt_app=mock_provided_app)

        MockQApplication.instance.assert_not_called() # Shouldn't need to check for global instance
        MockQApplication.assert_not_called() # No new app created
        self.MockMainWindowClass.assert_called_once_with(
            initial_data=self.initial_data,
            config_dict_param=self.config_dict,
            app_instance=mock_provided_app # Check that the provided app is passed to MainWindow
        )
        self.mock_main_window_instance.show.assert_called_once()
        mock_provided_app.exec_.assert_not_called() # exec_ not called
        self.assertEqual(result, self.mock_main_window_instance)

    @patch('src.themule_atomic_hitl.runner.logger.error')
    def test_run_application_no_initial_data(self, mock_logger_error):
        """
        Tests run_application with no initial data.
        - What it tests: Returns None and logs an error if initial_data is empty/None.
        - Expected outcome: Returns None, logger.error called.
        - Reason for failure: Incorrect handling of missing initial data.
        """
        result = run_application(None, self.config_dict, qt_app=None)
        self.assertIsNone(result)
        mock_logger_error.assert_called_once_with("RUNNER.PY: Initial data is empty. Application cannot start.")

    @patch('src.themule_atomic_hitl.runner.logger.error')
    def test_run_application_cannot_get_qapp(self, mock_logger_error):
        """
        Tests run_application when QApplication cannot be obtained/created.
        - What it tests: Returns None and logs error if QApplication instance is None after attempts.
        - Expected outcome: Returns None, logger.error called.
        - Reason for failure: Error path for no QApplication not handled.
        """
        MockQApplication.instance.return_value = None
        MockQApplication.return_value = None # Simulate QApplication([]) also failing (highly unlikely but for test)

        # To make QApplication([]) effectively return None for the instance check
        # We need to make the constructor return None when called.
        # This is tricky because QApplication is already a mock.
        # Let's make the *class* itself return None when called.
        with patch('src.themule_atomic_hitl.runner.QApplication', return_value=None) as PatchedQAppAgain:
             PatchedQAppAgain.instance.return_value = None # Ensure .instance() also returns None
             result = run_application(self.initial_data, self.config_dict, qt_app=None)

        self.assertIsNone(result)
        mock_logger_error.assert_any_call("RUNNER.PY: Could not obtain/create QApplication instance.")


if __name__ == '__main__':
    unittest.main()

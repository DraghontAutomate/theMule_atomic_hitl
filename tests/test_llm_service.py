import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import sys

# Adjust path to import from src
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.themule_atomic_hitl.llm_service import LLMService

# Mock Langchain classes that would make external calls
MockChatGoogleGenerativeAI = MagicMock()
MockChatOpenAI = MagicMock()

# Sample LLM response content
SAMPLE_LLM_RESPONSE = "This is a mock LLM response."

class TestLLMService(unittest.TestCase):

    def setUp(self):
        """Set up basic configurations for tests."""
        self.valid_llm_config = {
            "providers": {
                "google": {
                    "model": "gemini-test",
                    "temperature": 0.5,
                    "api_key_env": "TEST_GOOGLE_API_KEY"
                },
                "local": {
                    "model": "local-test-model",
                    "temperature": 0.2,
                    "base_url_env": "TEST_LOCAL_LLM_BASE_URL",
                    "api_key": "test_local_key"
                }
            },
            "task_llms": {
                "locator": "google",
                "editor": "local",
                "another_task": "google",
                "unconfigured_llm_task": "non_existent_provider",
                "default": "google"
            },
            "system_prompts": {
                "locator": "System prompt for locator.",
                "editor": "System prompt for editor."
                # No prompt for 'another_task' to test generic fallback
                # No prompt for 'unconfigured_llm_task'
            }
        }
        self.env_vars = {
            "TEST_GOOGLE_API_KEY": "fake_google_key",
            "TEST_LOCAL_LLM_BASE_URL": "http://localhost:1234/v1"
        }

        # Reset mocks before each test
        MockChatGoogleGenerativeAI.reset_mock()
        MockChatOpenAI.reset_mock()

        # Mock the LLM's invoke method to return a MagicMock response object
        # that has a 'content' attribute.
        mock_response_obj = MagicMock()
        mock_response_obj.content = SAMPLE_LLM_RESPONSE
        MockChatGoogleGenerativeAI.return_value.invoke.return_value = mock_response_obj
        MockChatOpenAI.return_value.invoke.return_value = mock_response_obj


    @patch.dict(os.environ, {}, clear=True)
    def test_init_no_config(self):
        """
        Tests LLMService initialization with no configuration.
        - What it tests: Verifies that LLMService raises ValueError if llm_config is None or empty.
        - Expected outcome: ValueError is raised.
        - Reason for failure: Service initializes without config, or wrong error type is raised.
        """
        with self.assertRaisesRegex(ValueError, "LLM configuration is required for LLMService"):
            LLMService(llm_config=None)
        with self.assertRaisesRegex(ValueError, "LLM configuration is required for LLMService"):
            LLMService(llm_config={})

    @patch.dict(os.environ, {"TEST_GOOGLE_API_KEY": "fake_key"}, clear=True)
    @patch('src.themule_atomic_hitl.llm_service.ChatGoogleGenerativeAI', new=MockChatGoogleGenerativeAI)
    def test_init_google_llm_success(self):
        """
        Tests successful initialization of Google LLM.
        - What it tests: Ensures Google LLM client is created when config and API key are valid.
        - Expected outcome: self.google_llm is an instance of the mocked ChatGoogleGenerativeAI.
        - Reason for failure: Google LLM not initialized despite valid config/key, or incorrect parameters passed.
        """
        service = LLMService(llm_config=self.valid_llm_config)
        self.assertIsNotNone(service.google_llm)
        MockChatGoogleGenerativeAI.assert_called_once_with(
            model="gemini-test",
            api_key="fake_key",
            temperature=0.5
        )

    @patch.dict(os.environ, {}, clear=True) # No GOOGLE_API_KEY
    @patch('src.themule_atomic_hitl.llm_service.ChatGoogleGenerativeAI', new=MockChatGoogleGenerativeAI)
    @patch('builtins.print')
    def test_init_google_llm_missing_key(self, mock_print):
        """
        Tests Google LLM initialization when API key environment variable is missing.
        - What it tests: Verifies a warning is printed and Google LLM is not initialized.
        - Expected outcome: self.google_llm is None, print is called with a warning.
        - Reason for failure: Service attempts to initialize without key, no warning, or initializes incorrectly.
        """
        service = LLMService(llm_config=self.valid_llm_config)
        self.assertIsNone(service.google_llm)
        mock_print.assert_any_call("Warning: Environment variable 'TEST_GOOGLE_API_KEY' not found for Google LLM.")
        MockChatGoogleGenerativeAI.assert_not_called()

    @patch.dict(os.environ, {"TEST_LOCAL_LLM_BASE_URL": "http://fakehost/v1"}, clear=True)
    @patch('src.themule_atomic_hitl.llm_service.ChatOpenAI', new=MockChatOpenAI)
    def test_init_local_llm_success(self):
        """
        Tests successful initialization of Local LLM.
        - What it tests: Ensures Local LLM client is created when config and base URL are valid.
        - Expected outcome: self.local_llm is an instance of the mocked ChatOpenAI.
        - Reason for failure: Local LLM not initialized despite valid config/URL, or incorrect parameters passed.
        """
        service = LLMService(llm_config=self.valid_llm_config) # Google LLM might also init if key is in env
        self.assertIsNotNone(service.local_llm)
        MockChatOpenAI.assert_called_once_with(
            model_name="local-test-model",
            temperature=0.2,
            openai_api_base="http://fakehost/v1",
            openai_api_key="test_local_key"
        )

    @patch.dict(os.environ, {}, clear=True) # No LOCAL_LLM_BASE_URL
    @patch('src.themule_atomic_hitl.llm_service.ChatOpenAI', new=MockChatOpenAI)
    @patch('builtins.print')
    def test_init_local_llm_missing_url(self, mock_print):
        """
        Tests Local LLM initialization when base URL environment variable is missing.
        - What it tests: Verifies a warning is printed and Local LLM is not initialized.
        - Expected outcome: self.local_llm is None, print is called with a warning.
        - Reason for failure: Service attempts to initialize without URL, no warning, or initializes incorrectly.
        """
        service = LLMService(llm_config=self.valid_llm_config)
        self.assertIsNone(service.local_llm)
        mock_print.assert_any_call("Warning: Environment variable 'TEST_LOCAL_LLM_BASE_URL' not found for Local LLM.")
        MockChatOpenAI.assert_not_called()

    @patch.dict(os.environ, {"TEST_GOOGLE_API_KEY": "fake_google_key", "TEST_LOCAL_LLM_BASE_URL": "http://localhost:1234/v1"}, clear=True)
    @patch('src.themule_atomic_hitl.llm_service.ChatGoogleGenerativeAI', new=MockChatGoogleGenerativeAI)
    @patch('src.themule_atomic_hitl.llm_service.ChatOpenAI', new=MockChatOpenAI)
    def test_get_llm_for_task_google(self):
        """
        Tests selecting Google LLM for a task configured for Google.
        - What it tests: `get_llm_for_task` returns the Google LLM instance.
        - Expected outcome: Returns the google_llm instance.
        - Reason for failure: Incorrect LLM selection logic.
        """
        service = LLMService(llm_config=self.valid_llm_config)
        llm_instance = service.get_llm_for_task("locator")
        self.assertEqual(llm_instance, service.google_llm)

    @patch.dict(os.environ, {"TEST_GOOGLE_API_KEY": "fake_google_key", "TEST_LOCAL_LLM_BASE_URL": "http://localhost:1234/v1"}, clear=True)
    @patch('src.themule_atomic_hitl.llm_service.ChatGoogleGenerativeAI', new=MockChatGoogleGenerativeAI)
    @patch('src.themule_atomic_hitl.llm_service.ChatOpenAI', new=MockChatOpenAI)
    def test_get_llm_for_task_local(self):
        """
        Tests selecting Local LLM for a task configured for Local.
        - What it tests: `get_llm_for_task` returns the Local LLM instance.
        - Expected outcome: Returns the local_llm instance.
        - Reason for failure: Incorrect LLM selection logic.
        """
        service = LLMService(llm_config=self.valid_llm_config)
        llm_instance = service.get_llm_for_task("editor")
        self.assertEqual(llm_instance, service.local_llm)

    @patch.dict(os.environ, {"TEST_GOOGLE_API_KEY": "fake_google_key"}, clear=True) # Local LLM will not initialize
    @patch('src.themule_atomic_hitl.llm_service.ChatGoogleGenerativeAI', new=MockChatGoogleGenerativeAI)
    @patch('src.themule_atomic_hitl.llm_service.ChatOpenAI', new=MockChatOpenAI)
    def test_get_llm_for_task_fallback_to_default_google(self):
        """
        Tests fallback to default (Google) when task-specific (Local) LLM is not available.
        - What it tests: If 'editor' task (prefers 'local') cannot use local LLM (e.g., not initialized),
          it falls back to the 'default' LLM provider ('google').
        - Expected outcome: Returns the google_llm instance.
        - Reason for failure: Fallback logic is incorrect.
        """
        # Modify config so default is local, but local won't be initialized
        custom_config = self.valid_llm_config.copy()
        custom_config["task_llms"]["default"] = "local" # default is local
        # TEST_LOCAL_LLM_BASE_URL is NOT in environ, so local_llm will be None

        service = LLMService(llm_config=custom_config)
        self.assertIsNotNone(service.google_llm, "Google LLM should be initialized for this test")
        self.assertIsNone(service.local_llm, "Local LLM should NOT be initialized for this test")

        # 'editor' task prefers 'local', but local is None. 'default' is 'local', also None.
        # Should fall back to any available, which is google_llm.
        llm_instance = service.get_llm_for_task("editor")
        self.assertEqual(llm_instance, service.google_llm)


    @patch.dict(os.environ, {"TEST_LOCAL_LLM_BASE_URL": "http://localhost:1234/v1"}, clear=True) # Google LLM will not initialize
    @patch('src.themule_atomic_hitl.llm_service.ChatGoogleGenerativeAI', new=MockChatGoogleGenerativeAI)
    @patch('src.themule_atomic_hitl.llm_service.ChatOpenAI', new=MockChatOpenAI)
    def test_get_llm_for_task_fallback_to_available_local(self):
        """
        Tests fallback to available (Local) when preferred (Google) and default (Google) are not available.
        - What it tests: If 'locator' task (prefers 'google', default is 'google') cannot use Google LLM,
          it falls back to the available 'local' LLM.
        - Expected outcome: Returns the local_llm instance.
        - Reason for failure: Fallback logic to any available LLM is incorrect.
        """
        service = LLMService(llm_config=self.valid_llm_config)
        self.assertIsNone(service.google_llm, "Google LLM should NOT be initialized for this test")
        self.assertIsNotNone(service.local_llm, "Local LLM should be initialized for this test")

        llm_instance = service.get_llm_for_task("locator") # Prefers google (None), default is google (None)
        self.assertEqual(llm_instance, service.local_llm) # Should fallback to available local

    @patch.dict(os.environ, {}, clear=True) # No LLMs will initialize
    @patch('src.themule_atomic_hitl.llm_service.ChatGoogleGenerativeAI', new=MockChatGoogleGenerativeAI)
    @patch('src.themule_atomic_hitl.llm_service.ChatOpenAI', new=MockChatOpenAI)
    def test_get_llm_for_task_runtime_error_if_none_available(self):
        """
        Tests RuntimeError when no LLMs are initialized.
        - What it tests: `get_llm_for_task` raises RuntimeError if no LLMs could be initialized.
        - Expected outcome: RuntimeError with specific message.
        - Reason for failure: Error not raised or wrong error type/message.
        """
        service = LLMService(llm_config=self.valid_llm_config)
        self.assertIsNone(service.google_llm)
        self.assertIsNone(service.local_llm)
        with self.assertRaisesRegex(RuntimeError, "No LLM could be initialized or selected."):
            service.get_llm_for_task("locator")

    @patch.dict(os.environ, {"TEST_GOOGLE_API_KEY": "fake_google_key"}, clear=True)
    @patch('src.themule_atomic_hitl.llm_service.ChatGoogleGenerativeAI', new=MockChatGoogleGenerativeAI)
    @patch('src.themule_atomic_hitl.llm_service.ChatOpenAI', new=MockChatOpenAI) # Keep OpenAI mocked
    def test_invoke_llm_with_config_prompt(self):
        """
        Tests LLM invocation using system prompt from config.
        - What it tests: `invoke_llm` uses the system prompt defined in `llm_config` for the task.
        - Expected outcome: The mocked LLM's `invoke` method is called with messages
                         containing the system prompt from config and the user prompt.
                         Returns the mocked response content.
        - Reason for failure: Incorrect system prompt used, messages not constructed correctly,
                         or response not handled.
        """
        from langchain_core.messages import SystemMessage, HumanMessage
        service = LLMService(llm_config=self.valid_llm_config)
        user_prompt = "User query for locator."
        response = service.invoke_llm("locator", user_prompt)

        self.assertEqual(response, SAMPLE_LLM_RESPONSE)
        service.google_llm.invoke.assert_called_once()
        args, _ = service.google_llm.invoke.call_args
        messages = args[0]
        self.assertIsInstance(messages[0], SystemMessage)
        self.assertEqual(messages[0].content, self.valid_llm_config["system_prompts"]["locator"])
        self.assertIsInstance(messages[1], HumanMessage)
        self.assertEqual(messages[1].content, user_prompt)

    @patch.dict(os.environ, {"TEST_GOOGLE_API_KEY": "fake_google_key"}, clear=True)
    @patch('src.themule_atomic_hitl.llm_service.ChatGoogleGenerativeAI', new=MockChatGoogleGenerativeAI)
    @patch('src.themule_atomic_hitl.llm_service.ChatOpenAI', new=MockChatOpenAI)
    def test_invoke_llm_with_override_prompt(self):
        """
        Tests LLM invocation using an overridden system prompt.
        - What it tests: `invoke_llm` uses the `system_prompt_override` when provided.
        - Expected outcome: LLM `invoke` is called with the overridden system prompt.
        - Reason for failure: Override prompt not used, or config prompt used instead.
        """
        from langchain_core.messages import SystemMessage, HumanMessage
        service = LLMService(llm_config=self.valid_llm_config)
        user_prompt = "User query for locator with override."
        override_prompt = "This is an override system prompt."
        response = service.invoke_llm("locator", user_prompt, system_prompt_override=override_prompt)

        self.assertEqual(response, SAMPLE_LLM_RESPONSE)
        service.google_llm.invoke.assert_called_once()
        args, _ = service.google_llm.invoke.call_args
        messages = args[0]
        self.assertEqual(messages[0].content, override_prompt)
        self.assertEqual(messages[1].content, user_prompt)

    @patch.dict(os.environ, {"TEST_GOOGLE_API_KEY": "fake_google_key"}, clear=True)
    @patch('src.themule_atomic_hitl.llm_service.ChatGoogleGenerativeAI', new=MockChatGoogleGenerativeAI)
    @patch('src.themule_atomic_hitl.llm_service.ChatOpenAI', new=MockChatOpenAI)
    @patch('builtins.print')
    def test_invoke_llm_with_generic_fallback_prompt(self, mock_print):
        """
        Tests LLM invocation using generic fallback system prompt.
        - What it tests: When no system prompt is in config for the task and no override is given,
                         a generic fallback prompt is used.
        - Expected outcome: LLM `invoke` is called with the generic system prompt. A warning is printed.
        - Reason for failure: Generic prompt not used, or no warning printed.
        """
        from langchain_core.messages import SystemMessage, HumanMessage
        service = LLMService(llm_config=self.valid_llm_config)
        user_prompt = "User query for another_task." # 'another_task' has no system_prompts entry

        response = service.invoke_llm("another_task", user_prompt)

        self.assertEqual(response, SAMPLE_LLM_RESPONSE)
        mock_print.assert_any_call("Warning: No system prompt found for task 'another_task' in config and no override provided. Using a generic prompt.")
        service.google_llm.invoke.assert_called_once()
        args, _ = service.google_llm.invoke.call_args
        messages = args[0]
        self.assertEqual(messages[0].content, "You are a helpful AI assistant.") # Generic prompt
        self.assertEqual(messages[1].content, user_prompt)

    @patch.dict(os.environ, {}, clear=True) # No LLMs will initialize
    @patch('src.themule_atomic_hitl.llm_service.ChatGoogleGenerativeAI', new=MockChatGoogleGenerativeAI)
    @patch('src.themule_atomic_hitl.llm_service.ChatOpenAI', new=MockChatOpenAI)
    def test_invoke_llm_runtime_error_if_no_llm_for_task(self):
        """
        Tests RuntimeError from invoke_llm if get_llm_for_task fails.
        - What it tests: `invoke_llm` raises RuntimeError if `get_llm_for_task` can't find an LLM.
        - Expected outcome: RuntimeError with a specific message.
        - Reason for failure: Error not propagated or wrong error.
        """
        service = LLMService(llm_config=self.valid_llm_config)
        with self.assertRaisesRegex(RuntimeError, "Could not get an LLM for task 'locator'. Check initialization and config."):
            service.invoke_llm("locator", "test prompt")

    @patch.dict(os.environ, {"TEST_GOOGLE_API_KEY": "fake_google_key"}, clear=True)
    @patch('src.themule_atomic_hitl.llm_service.ChatGoogleGenerativeAI', new=MockChatGoogleGenerativeAI)
    def test_invoke_llm_exception_handling(self):
        """
        Tests exception handling during llm.invoke().
        - What it tests: If the llm's invoke method raises an exception, it's caught and re-raised by invoke_llm.
        - Expected outcome: The original exception from llm.invoke() is re-raised.
        - Reason for failure: Exception not handled or new/different exception raised.
        """
        service = LLMService(llm_config=self.valid_llm_config)
        MockChatGoogleGenerativeAI.return_value.invoke.side_effect = ConnectionError("LLM unavailable")

        with self.assertRaises(ConnectionError):
            service.invoke_llm("locator", "test prompt")

if __name__ == '__main__':
    unittest.main()

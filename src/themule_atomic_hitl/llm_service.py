import os
from typing import Optional, Dict, Any, List, Union, Callable, Type # Added typing imports
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI # Corrected import for newer Langchain versions
import yaml
from pydantic import BaseModel, create_model
from jsonschema_pydantic import jsonschema_to_pydantic

# --- Load environment variables ---
load_dotenv()

# This service now expects the LLM configuration to be passed to it,
# typically from the main Config object of the application.

class LLMService:
    def __init__(self, llm_config: Dict[str, Any]):
        """
        Initializes the LLMService with configuration.
        Args:
            llm_config (Dict[str, Any]): A dictionary containing LLM provider settings,
                                         task-to-LLM mappings, system prompts, and output schemas.
        """
        self.google_llm = None
        self.local_llm = None
        self.config = llm_config

        if not self.config:
            raise ValueError("LLM configuration is required for LLMService.")

        self._initialize_llms()

    def _initialize_llms(self):
        """Initializes the LLM clients based on the stored configuration."""

        providers_config = self.config.get("providers", {})

        # Initialize Google LLM
        google_config = providers_config.get("google")
        if google_config:
            api_key_env_var = google_config.get("api_key_env", "GOOGLE_API_KEY")
            google_api_key = os.getenv(api_key_env_var)
            if not google_api_key:
                print(f"Warning: Environment variable '{api_key_env_var}' not found for Google LLM.")
            else:
                try:
                    self.google_llm = ChatGoogleGenerativeAI(
                        model=google_config.get("model", "gemini-1.5-flash-latest"),
                        api_key=google_api_key,
                        temperature=google_config.get("temperature", 0.7)
                    )
                    print("Successfully initialized ChatGoogleGenerativeAI.")
                except Exception as e:
                    print(f"Error initializing Google LLM: {e}")

        # Initialize Local LLM (OpenAI compatible)
        local_config = providers_config.get("local")
        if local_config:
            base_url_env_var = local_config.get("base_url_env", "LOCAL_LLM_BASE_URL")
            local_base_url = os.getenv(base_url_env_var)
            if not local_base_url:
                print(f"Warning: Environment variable '{base_url_env_var}' not found for Local LLM.")
            else:
                try:
                    self.local_llm = ChatOpenAI(
                        model_name=local_config.get("model"),
                        temperature=local_config.get("temperature", 0.1),
                        openai_api_base=local_base_url,
                        openai_api_key=local_config.get("api_key", "unused"),
                    )
                    print(f"Successfully initialized Local LLM for model {local_config.get('model')}.")
                except Exception as e:
                    print(f"Error initializing Local LLM: {e}")

    def get_llm_for_task(self, task_name: str):
        """
        Selects the LLM based on the task name specified in the config.
        Falls back to a default LLM if the task-specific one is not configured or fails to initialize.
        """
        task_llms_map = self.config.get("task_llms", {})
        task_llm_preference = task_llms_map.get(task_name)

        if task_llm_preference == "google" and self.google_llm:
            # print(f"Using Google LLM for task: {task_name}") # Less verbose logging
            return self.google_llm
        elif task_llm_preference == "local" and self.local_llm:
            print(f"Using Local LLM for task: {task_name}")
            return self.local_llm

        # Fallback logic
        default_llm_preference = task_llms_map.get("default", "google") # Default provider is 'google'
        # print(f"Task '{task_name}' specific LLM ('{task_llm_preference}') not available or not configured. Falling back to default provider: '{default_llm_preference}'")

        if default_llm_preference == "google" and self.google_llm:
            # print(f"Using default Google LLM for task: {task_name}")
            return self.google_llm
        elif default_llm_preference == "local" and self.local_llm:
            # print(f"Using default Local LLM for task: {task_name}")
            return self.local_llm

        # Ultimate fallback if preferred default also not available
        if self.google_llm:
            print("Default LLM also not available, falling back to Google LLM if initialized.")
            return self.google_llm
        if self.local_llm:
            # print("Default LLM also not available, falling back to Local LLM if initialized.")
            return self.local_llm

        raise RuntimeError("No LLM could be initialized or selected. Please check your configuration and API keys.")

    def invoke_llm(self, task_name: str, user_prompt: str, system_prompt_override: Optional[str] = None, strict: bool = False) -> Union[str, Dict[str, Any]]:
        """
        Invokes the appropriate LLM for the given task with the specified prompts.
        The system prompt is retrieved from the configuration unless overridden.
        If an output schema is defined for the task, the LLM is invoked with structured output.

        Args:
            task_name (str): The name of the task (e.g., "locator", "editor").
            user_prompt (str): The user's input/query for the LLM.
            system_prompt_override (Optional[str]): An optional system prompt to use instead of the one from the config.
            strict (bool): If True, forces the LLM to use the specified schema.

        Returns:
            Union[str, Dict[str, Any]]: The LLM's response, either as a raw string or a parsed Pydantic model dictionary.
        """
        llm = self.get_llm_for_task(task_name)
        if not llm:
            raise RuntimeError(f"Could not get an LLM for task '{task_name}'. Check initialization and config.")

        system_prompt = system_prompt_override or self.config.get("system_prompts", {}).get(task_name)
        if not system_prompt:
            system_prompt = "You are a helpful AI assistant."
            print(f"Warning: No system prompt found for task '{task_name}'. Using a generic prompt.")

        from langchain_core.messages import SystemMessage, HumanMessage
        messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]

        output_schema_def = self.config.get("output_schemas", {}).get(task_name)

        try:
            if output_schema_def:
                # Dynamically create a Pydantic model from the schema definition
                pydantic_model = jsonschema_to_pydantic(output_schema_def, "StructuredOutputModel")
                structured_llm = llm.with_structured_output(pydantic_model, strict=strict)
                response = structured_llm.invoke(messages)
                return response.dict()
            else:
                response = llm.invoke(messages)
                return response.content
        except Exception as e:
            print(f"Error during LLM invocation for task '{task_name}': {e}")
            raise


# Example usage (for testing purposes, will be removed or moved later)
# To run this, you'd need to have the Config class from config.py available
# and provide a valid configuration dictionary.

if __name__ == "__main__":
    # This example assumes config.py is in the same directory or accessible in PYTHONPATH
    # And that you have a .env file with GOOGLE_API_KEY and LOCAL_LLM_BASE_URL (if testing local)

    # --- Create a dummy .env if it doesn't exist ---
    if not os.path.exists(".env"):
        with open(".env", "w") as f:
            f.write("GOOGLE_API_KEY=your_google_api_key_here # Replace with actual key\n")
            f.write("LOCAL_LLM_BASE_URL=http://localhost:1234/v1 # Replace if needed\n")
        print("Created a dummy .env file. Populate with GOOGLE_API_KEY and ensure local LLM is running for full tests.")

    # --- Define a sample LLM configuration (as would come from Config class) ---
    sample_llm_config_dict = {
        "providers": {
            "google": {
                "model": "gemini-1.5-flash-latest",
                "temperature": 0.7,
                "api_key_env": "GOOGLE_API_KEY"
            },
            "local": {
                "model": "deepseek/deepseek-r1-0528-qwen3-8b", # Ensure this model is served by your local LLM
                "temperature": 0.1,
                "base_url_env": "LOCAL_LLM_BASE_URL",
                "api_key": "unused"
            }
        },
        "task_llms": {
            "locator": "google",
            "editor": "local",
            "another_task": "google", # Example of a task that will use default prompt
            "default": "google"
        },
        "system_prompts": {
            "locator": "You are an HTML expert. Find the element.",
            "editor": "You are a code editor. Modify the code."
            # No prompt for 'another_task' to test fallback
        }
    }
    print("Attempting to initialize LLMService with sample config...")

    try:
        llm_service = LLMService(llm_config=sample_llm_config_dict)
        print("LLMService initialized.")

        # --- Test Google LLM for "locator" task ---
        if llm_service.google_llm:
            try:
                print("\n--- Testing Google LLM ('locator' task) ---")
                user_prompt_locator = "Find the button in <div><button>Click Me</button></div>"
                response_google = llm_service.invoke_llm("locator", user_prompt_locator)
                print(f"Google LLM Response (locator):\n{response_google}")
            except Exception as e:
                print(f"Error testing Google LLM (locator): {e}")
        else:
            print("\nGoogle LLM not initialized. Skipping Google LLM (locator) test.")

        # --- Test Local LLM for "editor" task ---
        if llm_service.local_llm:
            try:
                print("\n--- Testing Local LLM ('editor' task) ---")
                user_prompt_editor = "Change 'var_a' to 'var_b' in: `var_a = 1;`"
                response_local = llm_service.invoke_llm("editor", user_prompt_editor)
                print(f"Local LLM Response (editor):\n{response_local}")
            except Exception as e:
                print(f"Error testing Local LLM (editor): {e}")
                print("Ensure your local LLM server is running and configured correctly.")
        else:
            print("\nLocal LLM not initialized. Skipping Local LLM (editor) test.")

        # --- Test task with no specific system prompt (should use generic) ---
        if llm_service.google_llm: # Assuming 'another_task' defaults to google
            try:
                print("\n--- Testing Task with no specific system prompt ('another_task') ---")
                user_prompt_another = "What is the capital of France?"
                response_another = llm_service.invoke_llm("another_task", user_prompt_another)
                print(f"LLM Response (another_task with generic prompt):\n{response_another}")
            except Exception as e:
                print(f"Error testing 'another_task': {e}")

        # --- Test system prompt override ---
        if llm_service.google_llm: # Assuming 'locator' uses google
            try:
                print("\n--- Testing System Prompt Override ('locator' task) ---")
                user_prompt_locator_override = "Find the div in <div><button>Click Me</button></div>"
                override_prompt = "You are a helpful assistant. Just find the div."
                response_override = llm_service.invoke_llm("locator", user_prompt_locator_override, system_prompt_override=override_prompt)
                print(f"LLM Response (locator with override prompt):\n{response_override}")
            except Exception as e:
                print(f"Error testing system prompt override: {e}")

    except ValueError as ve:
        print(f"Initialization Error: {ve}")
    except Exception as ex:
        print(f"An unexpected error occurred during testing: {ex}")

    print("\nNote: If you created a dummy .env, please review or remove it.")
"""
Main changes in llm_service.py:
- Constructor `__init__` now takes an `llm_config` dictionary directly.
- Removed internal config loading (`_load_config`, `DEFAULT_LLM_CONFIG_PATH`).
- `_initialize_llms` now uses `self.config.get("providers", {})`.
- `get_llm_for_task` now uses `self.config.get("task_llms", {})`.
- `invoke_llm` now:
    - Takes `task_name` and `user_prompt`.
    - Optionally takes `system_prompt_override`.
    - Retrieves the system prompt from `self.config.get("system_prompts", {})` based on `task_name` if not overridden.
    - Falls back to a generic system prompt if a task-specific one is missing and not overridden.
- Updated the `if __name__ == "__main__":` block:
    - It now directly creates a `sample_llm_config_dict` that matches the structure expected from `config.Config().get_llm_config()`.
    - It initializes `LLMService` with this dictionary.
    - Tests are adjusted to reflect the new `invoke_llm` signature and system prompt logic.
"""

import os
import sys
import json
from dotenv import load_dotenv

# Adjust the Python path to include the project root
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.themule_atomic_hitl.llm_service import LLMService

# Load environment variables from .env file
load_dotenv()

def run_task_based_test(llm_service, test_config):
    """Runs a single task-based LLM test."""
    print(f"\n--- Running task-based test: {test_config['name']} ---")

    try:
        print(f"--- Testing task: {test_config['task_name']} ---")
        response = llm_service.invoke_llm(test_config['task_name'], test_config["user_prompt"])
        print(f"LLM Response:\n{response}")

    except Exception as e:
        print(f"An error occurred: {e}")

def run_bare_api_test(llm_service, test_config):
    """Runs a bare API call test, bypassing task-specific prompts."""
    print(f"\n--- Running bare API test: {test_config['name']} ---")

    try:
        print(f"--- Testing LLM: {test_config['llm']} ---")
        # For bare API calls, we can invent a temporary task name or use a default
        # The key is to override the system prompt.
        task_name = "bare_test"
        response = llm_service.invoke_llm(
            task_name,
            test_config["user_prompt"],
            system_prompt_override=test_config["system_prompt"]
        )
        print(f"LLM Response:\n{response}")

    except Exception as e:
        print(f"An error occurred: {e}")

def main():
    """Loads configurations and runs the tests."""
    config_path = os.path.join(os.path.dirname(__file__), 'test_config.json')
    with open(config_path, 'r') as f:
        config = json.load(f)

    llm_config = config.get("llm_config")
    if not llm_config:
        print("Error: 'llm_config' not found in test_config.json")
        return

    try:
        llm_service = LLMService(llm_config=llm_config)
        print("LLMService initialized.")

        test_cases_path = os.path.join(os.path.dirname(__file__), 'test_cases.json')
        with open(test_cases_path, 'r') as f:
            test_cases = json.load(f)

        for test in test_cases.get("task_based_tests", []):
            run_task_based_test(llm_service, test)

        for test in test_cases.get("bare_api_tests", []):
            # We need to temporarily adjust the llm_config to use the correct LLM for the bare API test
            original_task_llms = llm_config["task_llms"].copy()
            llm_config["task_llms"]["bare_test"] = test["llm"]
            run_bare_api_test(llm_service, test)
            llm_config["task_llms"] = original_task_llms


    except Exception as e:
        print(f"An error occurred during initialization or testing: {e}")


if __name__ == "__main__":
    main()

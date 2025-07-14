# Testing Guide

This document provides instructions on how to run the tests for this application.

## Running All Tests

To run all tests for both the `themule_atomic_hitl` and `llm_prompt_tool` modules, use the `run_tests.py` script located in the root directory.

```bash
python run_tests.py
```

This will execute all test files in the `tests` directory and print a detailed report to the console.

## Running Tests for a Specific Module

You can also run tests for a specific module by providing the module name as an argument to the `run_tests.py` script.

### `themule_atomic_hitl` Module

To run the tests for the `themule_atomic_hitl` module, which includes tests for the core logic, configuration, and HITL node, use the following command:

```bash
python run_tests.py themule_atomic_hitl
```

The test files related to this module are:
- `tests/test_config.py`: This file tests the `Config` class in `src/themule_atomic_hitl/config.py`. It ensures that the default configuration is loaded correctly, custom configurations are merged properly, and that individual configuration values can be retrieved as expected.
- `tests/test_core_logic.py`: This file contains unit tests for the `SurgicalEditorLogic` class from `src/themule_atomic_hitl/core.py`. It uses mock objects to simulate UI callbacks and verifies the behavior of the core logic in isolation, including handling of edit requests, approvals, rejections, and other user actions.
- `tests/test_hitl_node.py`: This file tests the `hitl_node_run` function in `src/themule_atomic_hitl/hitl_node.py`, which is the main entry point for the HITL component. It ensures that the function correctly handles different types of input content and custom configurations.

### `llm_prompt_tool` Module

To run the tests for the `llm_prompt_tool` module, use the following command:

```bash
python run_tests.py llm_prompt_tool
```

The test file related to this module is:
- `tests/test_llm_prompt_tool.py`: This file tests the main components of the `llm_prompt_tool`. It includes tests for the `LLMInterface` (ensuring it can connect to a mock LLM), the `ResponseEvaluator` (verifying scoring and suggestion logic), and the `main_loop` (testing the refinement cycle).

## Standalone LLM Module Testing

You can also test the `llm_prompt_tool` module in a standalone fashion by running the `main_loop.py` script directly. This allows you to provide custom prompts and observe the behavior of the LLM and the prompt refinement process.

### Basic Usage

To run the `llm_prompt_tool` with the default prompts, use the following command:

```bash
python src/llm_prompt_tool/main_loop.py
```

This will run the refinement cycle with a default system prompt and a list of default user prompts. The output will show the LLM's responses and the suggested prompt improvements for each iteration.

### Custom Prompts

You can provide your own system and user prompts using the `-s` and `-u` flags, respectively.

**Example with a custom system prompt and a single user prompt:**

```bash
python src/llm_prompt_tool/main_loop.py -s "You are a pirate." -u "What is the best way to find treasure?"
```

**Example with multiple user prompts:**

```bash
python src/llm_prompt_tool/main_loop.py -u "What is your name?" "Where are you from?"
```

### Other Options

- `-i, --iterations`: Set the number of refinement iterations for each prompt.
- `-m, --model-name`: Specify the LLM model to use (e.g., `mock-model`, `gpt-3.5-turbo`).
- `-o, --results-file`: Set the file to save the refinement log.

By default, the script uses a mock LLM that provides pre-defined responses. This is useful for testing the fallback logic and the overall flow of the refinement cycle without making actual API calls. To use a real LLM, you would need to provide the appropriate model name and have the necessary API keys configured.

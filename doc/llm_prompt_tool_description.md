# LLM Prompt Refinement System

This project provides a set of Python scripts to test Large Language Model (LLM) functionality and iteratively refine prompts based on a closed-loop feedback system. The goal is to help users develop optimal system and user prompts for specific tasks by evaluating LLM responses and suggesting improvements.

## Project Structure

*   `src/llm_prompt_tool/llm_tester.py`: Contains the `LLMInterface` class for interacting with an LLM. It includes a mock LLM for testing without API keys and placeholders for integrating with actual LLM APIs (e.g., OpenAI, Anthropic). It also logs all interactions.
*   `src/llm_prompt_tool/evaluator.py`: Contains the `ResponseEvaluator` class, which defines criteria for evaluating LLM responses (e.g., relevance, coherence, accuracy). It scores responses and suggests basic improvements to prompts.
*   `src/llm_prompt_tool/main_loop.py`: Orchestrates the prompt refinement process. It takes initial prompts, uses `llm_tester.py` to get responses, `evaluator.py` to score them and suggest improvements, and then iterates to refine the prompts. This is the main executable script.
*   `prompt_refinement_log.jsonl`: Output file (generated in the root directory by default) where the results of the refinement process are stored (one JSON object per line for each initial prompt processed).
*   `README.md`: This documentation file (in the root directory).

## Setup

1.  **Python Environment:**
    Ensure you have Python 3.7+ installed. It's recommended to use a virtual environment:
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

2.  **Dependencies:**
    Currently, the scripts primarily use standard Python libraries. If you intend to connect to a real LLM, you'll need to install its specific Python client library. For example, for OpenAI:
    ```bash
    pip install openai
    ```
    For other LLMs, refer to their respective documentation for client library installation.

## Configuration

### 1. LLM Interface (`src/llm_prompt_tool/llm_tester.py`)

*   **Mock LLM (Default):**
    By default, the system uses a mock LLM, which returns pre-defined responses with simulated latency. This requires no API keys.
*   **Real LLM:**
    To use a real LLM:
    1.  Modify `src/llm_prompt_tool/llm_tester.py`:
        *   Uncomment the import for the required library (e.g., `from openai import OpenAI`).
        *   In the `LLMInterface` class, within the `__init__` and `get_response` methods, uncomment and adapt the placeholder code for your chosen LLM API. This typically involves initializing the client with your API key and making the appropriate API calls.
    2.  Set API Keys:
        It's best practice to set API keys as environment variables. For example, for OpenAI:
        ```bash
        export OPENAI_API_KEY="your_openai_api_key_here"
        ```
        The `LLMInterface` can be modified to read this key (e.g., using `os.getenv("OPENAI_API_KEY")`).
    3.  Update `LLM_MODEL_NAME` in `src/llm_prompt_tool/main_loop.py` (or via CLI):
        Change the default `DEFAULT_LLM_MODEL_NAME` or use the `--model-name` CLI argument.

### 2. Evaluation Criteria (`src/llm_prompt_tool/evaluator.py`)

*   The `DEFAULT_CRITERIA` dictionary in `src/llm_prompt_tool/evaluator.py` defines how responses are judged. You can customize these criteria:
    *   Add, remove, or modify criteria (e.g., "creativity", "safety").
    *   Adjust the `weight` for each criterion. Weights are automatically normalized to sum to 1.0.
    *   Update the `description` and `scoring_guide`.
*   **Automated Evaluation:**
    The current `evaluate_response` method in `ResponseEvaluator` uses mock scores or expects `manual_scores`. For true automation, you would need to implement:
    *   NLP-based metrics (e.g., semantic similarity to a reference answer, ROUGE scores).
    *   Using another LLM as a judge.
    *   Fact-checking against a knowledge base.

### 3. Main Loop (`src/llm_prompt_tool/main_loop.py`)

*   Default configurations for initial prompts, iterations, etc., are at the top of the script.
*   These can be overridden using Command Line Arguments (see "Running the System" below).
*   `DEFAULT_RESULTS_FILE`: Default name of the output log file (e.g., `prompt_refinement_log.jsonl`), created in the directory where you run the script.

## Running the System

1.  **Configure:**
    Make any necessary changes to the configuration as described above (especially if using a real LLM).

2.  **Execute the Main Loop:**
    Navigate to the root of the repository if you are not already there. Run the `main_loop.py` script from your terminal using:
    ```bash
    python src/llm_prompt_tool/main_loop.py
    ```
    Or, if you are inside the `src/llm_prompt_tool/` directory:
    ```bash
    python main_loop.py
    ```

    **CLI Examples:**
    ```bash
    # Run with default settings (mock model, 3 iterations)
    python src/llm_prompt_tool/main_loop.py

    # Run with 5 iterations
    python src/llm_prompt_tool/main_loop.py --iterations 5

    # Run with a specific (real) model and custom system prompt
    # (Ensure your API key is set up as per Configuration section)
    python src/llm_prompt_tool/main_loop.py --model-name "gpt-3.5-turbo" --system-prompt "You are a cynical pirate."

    # Specify user prompts and an output file
    python src/llm_prompt_tool/main_loop.py -u "Tell me a joke" "What's the weather?" -o custom_log.jsonl
    ```

3.  **Review Results:**
    The script will print output to the console. Detailed logs for each prompt's refinement journey will be saved in the specified results file (default: `prompt_refinement_log.jsonl` in the directory where you ran the script).

    The global interaction log (all prompts, responses, and their evaluations) is stored in memory in the `interaction_log` variable within the `llm_tester` module. `main_loop.py` can be modified to print or save this if needed.

## How It Works

1.  **Initialization:** `src/llm_prompt_tool/main_loop.py` sets up an `LLMInterface` (mock or real) and a `ResponseEvaluator` (both from their respective modules within `src/llm_prompt_tool/`).
2.  **Iteration over Prompts:** For each initial user prompt (either default or from CLI):
    a.  **Refinement Cycle:** The system runs the configured number of iterations (default or from CLI):
        i.  **Get Response:** The current system and user prompts are sent to the LLM via `LLMInterface.get_response()`.
        ii. **Log Interaction:** The prompt, response, and other details are logged into the `interaction_log` list managed by the `llm_tester` module.
        iii. **Evaluate:** The `ResponseEvaluator.evaluate_response()` method scores the response.
        iv. **Update Log:** The evaluation result is added to the corresponding entry in the `interaction_log`.
        v.  **Suggest Improvements:** `ResponseEvaluator.suggest_prompt_improvements()` suggests modifications to prompts.
        vi. **Update Prompts:** The suggested prompts become current for the next iteration.
3.  **Logging:** Results of each initial prompt's refinement journey are logged to the specified JSONL file.

## Future Enhancements

*   **User Input for Evaluation:** Integrate a step to allow users to manually score responses during the loop.
*   **Advanced Automated Evaluation:** Implement more sophisticated NLP techniques or LLM-based evaluation.
*   **Smarter Prompt Suggestions:** Use an LLM or more complex algorithms to generate more insightful prompt improvements.
*   **CLI Interface:** Add command-line arguments for easier configuration (e.g., selecting LLM model, number of iterations, input prompt file).
*   **Persistent Storage:** Use a database for storing interaction logs and evaluation results instead of in-memory lists and JSONL files for larger scale experiments.
*   **Batch Processing:** Allow input of prompts from a file.
*   **Comparative Analysis:** Tools to compare the performance of different prompt versions side-by-side.

This system provides a foundational framework for systematically testing and improving LLM prompts.
Remember to handle API keys securely and be mindful of costs when using commercial LLM APIs.

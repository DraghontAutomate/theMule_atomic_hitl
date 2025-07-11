from llm_tester import LLMInterface, interaction_log # interaction_log for updating
from evaluator import ResponseEvaluator, DEFAULT_CRITERIA
import json
import os
import argparse
import time

# --- Default Configuration ---
DEFAULT_INITIAL_SYSTEM_PROMPT = "You are a helpful assistant. Your goal is to provide accurate and concise information."
DEFAULT_INITIAL_USER_PROMPTS = [
    "What is the primary function of a CPU in a computer?",
    "Explain the concept of photosynthesis in simple terms.",
    "Suggest three fun activities to do on a rainy day indoors."
]
DEFAULT_NUM_REFINEMENT_ITERATIONS = 3
DEFAULT_LLM_MODEL_NAME = "mock-model"
DEFAULT_RESULTS_FILE = "prompt_refinement_log.jsonl"
# LLM_API_KEY = os.getenv("OPENAI_API_KEY") # Example for OpenAI - handle in LLMInterface or pass if needed

def run_refinement_cycle(llm_interface: LLMInterface, evaluator: ResponseEvaluator,
                         current_system_prompt: str, current_user_prompt: str, iteration: int, num_total_iterations: int):
    """
    Runs a single cycle of getting LLM response, evaluating, and suggesting improvements.
    """
    print(f"\n--- Iteration {iteration + 1} for User Prompt: '{current_user_prompt[:50]}...' ---")
    print(f"Current System Prompt: {current_system_prompt}")

    # 1. Get LLM response
    response_text = llm_interface.get_response(current_system_prompt, current_user_prompt)

    # Retrieve the last interaction (which is the one we just created)
    # This is a bit of a hack due to global interaction_log. A better way would be for
    # get_response to return an ID or the interaction object itself.
    if not interaction_log:
        print("Error: Interaction log is empty after getting LLM response.")
        return current_system_prompt, current_user_prompt, None

    last_interaction_index = -1 # Assuming the last one added is the current one

    # 2. Evaluate the response
    # For this example, we'll simulate manual scoring or use the mock scores from the evaluator.
    # In a real scenario, you might pause here for user input or have automated metrics.
    print("Simulating evaluation (using mock/default scores if no manual input provided by evaluator's logic)...")
    # Example manual scores (could be dynamic or from user input)
    # For demonstration, let's make scores vary based on iteration to see prompt changes
    mock_manual_scores = {}
    if iteration < num_total_iterations / 2 : # First half of iterations, simulate lower scores
        mock_manual_scores = {"relevance": 3, "coherence": 3, "accuracy": 3, "completeness": 2}
    else: # Later iterations, simulate better scores
        mock_manual_scores = {"relevance": 4, "coherence": 4, "accuracy": 4, "completeness": 4}

    # If using evaluator's internal mock scoring, pass manual_scores=None
    # evaluation = evaluator.evaluate_response(current_user_prompt, response_text, manual_scores=None)
    evaluation = evaluator.evaluate_response(current_user_prompt, response_text, manual_scores=mock_manual_scores)


    # Update the interaction log with the evaluation
    # Note: interaction_log is imported from llm_tester
    if interaction_log:
      interaction_log[last_interaction_index]["evaluation"] = evaluation
      interaction_log[last_interaction_index]["system_prompt_ ennen_refinement"] = current_system_prompt
      interaction_log[last_interaction_index]["user_prompt_ennen_refinement"] = current_user_prompt


    # 3. Suggest prompt improvements
    new_system_prompt, new_user_prompt = evaluator.suggest_prompt_improvements(
        current_system_prompt, current_user_prompt, evaluation
    )

    # Log this cycle's result (before prompts are changed for the next iteration)
    cycle_log = {
        "iteration": iteration + 1,
        "original_user_prompt_for_cycle": current_user_prompt,
        "system_prompt_used": current_system_prompt,
        "llm_response": response_text,
        "evaluation": evaluation,
        "suggested_system_prompt": new_system_prompt,
        "suggested_user_prompt": new_user_prompt,
        "model_name": llm_interface.model_name
    }

    return new_system_prompt, new_user_prompt, cycle_log


def main(args):
    print("--- Starting Prompt Refinement Process ---")
    print(f"Configuration: Model='{args.model_name}', Iterations='{args.iterations}', System Prompt='{args.system_prompt[:50]}...'")

    # Initialize LLM interface and Evaluator
    # Pass API key if using a real LLM that requires it (e.g., from args or environment)
    # llm = LLMInterface(api_key=args.api_key, model_name=args.model_name)
    llm = LLMInterface(model_name=args.model_name) # Mock model doesn't need API key
    evaluator = ResponseEvaluator(criteria=DEFAULT_CRITERIA)

    overall_results = []

    # Use default user prompts or allow for future expansion (e.g., from a file)
    user_prompts_to_process = args.user_prompts if args.user_prompts else DEFAULT_INITIAL_USER_PROMPTS


    # Loop through each initial user prompt
    for i, initial_user_prompt in enumerate(user_prompts_to_process):
        print(f"\n===== Processing Initial User Prompt {i+1}/{len(user_prompts_to_process)}: '{initial_user_prompt}' =====")

        current_system_prompt = args.system_prompt
        current_user_prompt = initial_user_prompt

        prompt_specific_log = {
            "initial_user_prompt": initial_user_prompt,
            "initial_system_prompt": args.system_prompt,
            "refinement_cycles": []
        }

        # Refinement loop for the current user prompt
        for iteration in range(args.iterations):
            new_system_prompt, new_user_prompt, cycle_log_data = run_refinement_cycle(
                llm, evaluator, current_system_prompt, current_user_prompt, iteration, args.iterations
            )
            if cycle_log_data:
                 prompt_specific_log["refinement_cycles"].append(cycle_log_data)

            # Update prompts for the next iteration
            current_system_prompt = new_system_prompt
            current_user_prompt = new_user_prompt

            time.sleep(0.05) # Small delay to make output readable

        overall_results.append(prompt_specific_log)
        print(f"===== Finished processing for: '{initial_user_prompt}' =====")

    # Save results to a file
    try:
        with open(args.results_file, 'w') as f:
            for entry in overall_results:
                f.write(json.dumps(entry) + '\n')
        print(f"\n--- Refinement process complete. Results saved to {args.results_file} ---")
    except IOError as e:
        print(f"Error writing results to file: {e}")

    # Optionally, print the final state of the global interaction_log from llm_tester
    # print("\n--- Full Interaction Log (from llm_tester) ---")
    # for log_entry_idx, log_entry in enumerate(llm.get_interaction_log()):
    #    print(f"Log Entry {log_entry_idx}:")
    #    print(json.dumps(log_entry, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run LLM Prompt Refinement Cycles.")
    parser.add_argument(
        "-i", "--iterations",
        type=int,
        default=DEFAULT_NUM_REFINEMENT_ITERATIONS,
        help=f"Number of refinement iterations for each prompt (default: {DEFAULT_NUM_REFINEMENT_ITERATIONS})"
    )
    parser.add_argument(
        "-m", "--model-name",
        type=str,
        default=DEFAULT_LLM_MODEL_NAME,
        help=f"Name of the LLM model to use (e.g., 'mock-model', 'gpt-3.5-turbo') (default: {DEFAULT_LLM_MODEL_NAME})"
    )
    parser.add_argument(
        "-s", "--system-prompt",
        type=str,
        default=DEFAULT_INITIAL_SYSTEM_PROMPT,
        help=f"Initial system prompt (default: '{DEFAULT_INITIAL_SYSTEM_PROMPT}')"
    )
    parser.add_argument(
        "-u", "--user-prompts",
        nargs='*', # 0 or more user prompts
        default=None, # Will use DEFAULT_INITIAL_USER_PROMPTS if None
        help=f"List of initial user prompts. If not provided, defaults to internal list."
    )
    parser.add_argument(
        "-o", "--results-file",
        type=str,
        default=DEFAULT_RESULTS_FILE,
        help=f"File to save the refinement log (JSONL format) (default: {DEFAULT_RESULTS_FILE})"
    )
    # Potentially add --api-key if not relying solely on environment variables

    # The monkey-patching for mock_evaluate_response_with_variance is primarily for demonstration
    # when manual_scores are not explicitly passed to evaluator.evaluate_response within run_refinement_cycle.
    # Since run_refinement_cycle *does* pass mock_manual_scores, this patch may not be strictly necessary
    # for variance if those mock_manual_scores are sufficiently dynamic.
    # Keeping it here for now as it doesn't harm and shows a technique.

    # from evaluator import ResponseEvaluator
    # def mock_evaluate_response_with_variance(self, prompt_text: str, response_text: str, manual_scores: dict = None):
    #     # ... (implementation as before) ...
    # ResponseEvaluator.evaluate_response = mock_evaluate_response_with_variance

    parsed_args = parser.parse_args()
    main(parsed_args)

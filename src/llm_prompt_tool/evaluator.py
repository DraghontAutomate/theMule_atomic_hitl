import time

# --- Evaluation Criteria ---
# These can be expanded and made more sophisticated.
# For example, using NLP techniques for semantic similarity, or even another LLM for evaluation.
DEFAULT_CRITERIA = {
    "relevance": {
        "description": "How relevant is the response to the prompt?",
        "weight": 0.3,
        "scoring_guide": {
            1: "Not relevant at all.",
            3: "Somewhat relevant, but misses key aspects.",
            5: "Highly relevant and directly addresses the prompt."
        }
    },
    "coherence": {
        "description": "Is the response logically structured and easy to understand?",
        "weight": 0.25,
        "scoring_guide": {
            1: "Incoherent and difficult to understand.",
            3: "Mostly coherent, but some parts are unclear.",
            5: "Clear, well-structured, and easy to follow."
        }
    },
    "accuracy": { # This might require external knowledge or fact-checking tools for rigorous evaluation
        "description": "Is the information provided in the response accurate?",
        "weight": 0.3,
        "scoring_guide": {
            1: "Contains significant inaccuracies.",
            3: "Mostly accurate, but some minor errors.",
            5: "Completely accurate."
        }
    },
    "completeness": {
        "description": "Does the response cover the prompt adequately?",
        "weight": 0.15,
        "scoring_guide": {
            1: "Very incomplete, misses major parts of the prompt.",
            3: "Addresses some parts of the prompt but lacks depth or detail.",
            5: "Comprehensive and covers all aspects of the prompt well."
        }
    }
}

class ResponseEvaluator:
    def __init__(self, criteria=None):
        self.criteria = criteria if criteria else DEFAULT_CRITERIA
        self._validate_criteria_weights()

    def _validate_criteria_weights(self):
        total_weight = sum(details.get("weight", 0) for details in self.criteria.values())
        if abs(total_weight - 1.0) > 1e-9: # Using a small epsilon for float comparison
            # Normalize weights if they don't sum to 1
            print(f"Warning: Criteria weights do not sum to 1 (sum={total_weight}). Normalizing weights.")
            if total_weight == 0: # Avoid division by zero if all weights are zero
                 print("Error: All criteria weights are zero. Cannot normalize.")
                 # Fallback: assign equal weight if possible, or raise error
                 if self.criteria:
                    equal_weight = 1.0 / len(self.criteria)
                    for key in self.criteria:
                        self.criteria[key]['weight'] = equal_weight
                 else: # No criteria defined, nothing to do
                    return

            else:
                for key in self.criteria:
                    self.criteria[key]['weight'] /= total_weight

            # Re-check after normalization (optional, for verification)
            # new_total_weight = sum(details.get("weight", 0) for details in self.criteria.values())
            # print(f"New total weight after normalization: {new_total_weight}")


    def evaluate_response(self, prompt_text: str, response_text: str, manual_scores: dict = None):
        """
        Evaluates an LLM response based on the defined criteria.
        `manual_scores` is a dictionary like: {"relevance": 4, "accuracy": 5}
        If `manual_scores` is not provided, this function would ideally have automated metrics
        or prompt the user for scores. For now, it will calculate a weighted score
        based on provided manual_scores.
        """
        print(f"\n--- Evaluating Response ---")
        print(f"Prompt: {prompt_text[:100]}...")
        print(f"Response: {response_text[:100]}...")

        evaluation_details = {}
        total_weighted_score = 0.0

        if manual_scores:
            for criterion, details in self.criteria.items():
                score = manual_scores.get(criterion)
                if score is not None:
                    if not (1 <= score <= 5): # Assuming a 1-5 scale from scoring_guide
                        print(f"Warning: Score for {criterion} ({score}) is outside the typical 1-5 range.")

                    weighted_score = score * details["weight"]
                    evaluation_details[criterion] = {
                        "score": score,
                        "weight": details["weight"],
                        "weighted_score": weighted_score
                    }
                    total_weighted_score += weighted_score
                else:
                    print(f"Info: Manual score for criterion '{criterion}' not provided.")
                    evaluation_details[criterion] = {
                        "score": None,
                        "weight": details["weight"],
                        "weighted_score": 0 # Or handle as missing data
                    }
        else:
            # Placeholder for automated evaluation or interactive scoring
            print("Info: No manual scores provided. Automated evaluation not yet implemented.")
            # For demonstration, let's assign mock scores if none are given
            # In a real system, you'd prompt for input or use NLP metrics here.
            print("Using mock scores for demonstration as manual_scores were not provided.")
            mock_scores = {}
            for criterion, details in self.criteria.items():
                # Mocking a score, e.g., random or based on response length
                mock_score = len(response_text) % 5 + 1 # Simple mock score
                if criterion == "accuracy" and "not sure" in response_text.lower():
                    mock_score = 2 # Penalize if LLM is unsure for accuracy

                print(f"  Mock score for {criterion}: {mock_score} (out of 5)")
                weighted_score = mock_score * details["weight"]
                evaluation_details[criterion] = {
                    "score": mock_score,
                    "weight": details["weight"],
                    "weighted_score": weighted_score
                }
                total_weighted_score += weighted_score
            manual_scores = mock_scores # For logging purposes

        final_evaluation = {
            "timestamp": time.time(),
            "overall_score": total_weighted_score, # This is a score out of 5 if weights sum to 1
            "criteria_scores": evaluation_details,
            "raw_manual_scores": manual_scores # Store the input scores
        }

        # Simplified and corrected calculation for the max possible score
        max_score = 5.0
        if manual_scores:
            # Only consider criteria that were actually scored
            total_possible_weighted_score = sum(details["weight"] * max_score for crit, details in self.criteria.items() if crit in manual_scores)
        else: # If mock scores were used, all criteria were scored
            total_possible_weighted_score = sum(details["weight"] * max_score for details in self.criteria.values())

        print(f"Overall Weighted Score: {total_weighted_score:.2f} / {total_possible_weighted_score:.2f}")


        return final_evaluation

    def suggest_prompt_improvements(self, system_prompt: str, user_prompt: str, evaluation: dict) -> tuple[str, str]:
        """
        Suggests improvements to the system and user prompts based on evaluation scores.
        This is a very basic implementation. More advanced versions could use an LLM
        to generate suggestions or employ more sophisticated heuristics.
        """
        print("\n--- Suggesting Prompt Improvements ---")
        overall_score = evaluation.get("overall_score", 0)
        criteria_scores = evaluation.get("criteria_scores", {})

        new_system_prompt = system_prompt
        new_user_prompt = user_prompt

        # Basic heuristic: if overall score is low, suggest more clarity
        if overall_score < 2.5: # Assuming max score is 5
            if not "be very specific" in new_system_prompt.lower():
                new_system_prompt += " Try to be very specific and clear in your requests."
            if not "provide detailed examples" in new_user_prompt.lower():
                 new_user_prompt += " Please provide detailed examples if possible."
            print("Suggestion: Overall score is low. Consider making the prompts more specific or adding examples.")

        # Heuristics based on specific criteria
        for criterion, details in criteria_scores.items():
            score = details.get("score")
            if score is not None and score < 3: # If a specific criterion is weak
                if criterion == "relevance" and "relevant" not in new_system_prompt.lower():
                    new_system_prompt += " Ensure the answer is highly relevant to the user's query."
                    print(f"Suggestion (Relevance): Consider rephrasing the system prompt to emphasize relevance.")
                elif criterion == "accuracy" and "accurate" not in new_system_prompt.lower():
                    new_system_prompt += " Prioritize accuracy in your responses."
                    print(f"Suggestion (Accuracy): System prompt updated to emphasize accuracy.")
                elif criterion == "coherence" and "clear and well-structured" not in new_system_prompt.lower():
                    new_system_prompt += " Structure your answer clearly."
                    print(f"Suggestion (Coherence): Prompt for clearer structure.")
                elif criterion == "completeness" and "comprehensive" not in user_prompt.lower():
                    new_user_prompt += " Ensure your answer is comprehensive."
                    print(f"Suggestion (Completeness): User prompt updated to ask for comprehensiveness.")


        if new_system_prompt == system_prompt and new_user_prompt == user_prompt:
            print("No specific improvements suggested based on current heuristics, or scores are adequate.")
        else:
            print(f"New System Prompt Suggestion: {new_system_prompt}")
            print(f"New User Prompt Suggestion: {new_user_prompt}")

        return new_system_prompt, new_user_prompt

# --- Example Usage (for testing this script directly) ---
if __name__ == "__main__":
    evaluator = ResponseEvaluator()

    # Example 1: Good response (simulated manual scores)
    prompt1 = "What is the capital of France?"
    response1 = "The capital of France is Paris."
    manual_scores1 = {"relevance": 5, "coherence": 5, "accuracy": 5, "completeness": 5}
    evaluation1 = evaluator.evaluate_response(prompt1, response1, manual_scores=manual_scores1)
    print(f"Evaluation 1: {evaluation1}")
    evaluator.suggest_prompt_improvements("System: Be helpful.", prompt1, evaluation1)

    # Example 2: Poor response (simulated manual scores)
    prompt2 = "Explain quantum physics in simple terms."
    response2 = "It's about small stuff. Very complicated."
    manual_scores2 = {"relevance": 3, "coherence": 2, "accuracy": 3, "completeness": 1}
    evaluation2 = evaluator.evaluate_response(prompt2, response2, manual_scores=manual_scores2)
    print(f"Evaluation 2: {evaluation2}")
    evaluator.suggest_prompt_improvements("System: Be concise.", prompt2, evaluation2)

    # Example 3: No manual scores (will use mock scores)
    prompt3 = "Tell me a joke."
    response3 = "Why did the chicken cross the road? To get to the other side!" # A classic
    print("\n--- Evaluation with Mock Scores (No Manual Input) ---")
    evaluation3 = evaluator.evaluate_response(prompt3, response3)
    print(f"Evaluation 3: {evaluation3}")
    evaluator.suggest_prompt_improvements("System: Be a comedian.", prompt3, evaluation3)

    # Example 4: Testing weight normalization
    custom_criteria = {
        "clarity": {"description": "Is it clear?", "weight": 0.6, "scoring_guide": {1:"Bad", 5:"Good"}},
        "brevity": {"description": "Is it brief?", "weight": 0.6, "scoring_guide": {1:"Bad", 5:"Good"}} # Weights sum to 1.2
    }
    print("\n--- Testing Weight Normalization ---")
    custom_evaluator = ResponseEvaluator(criteria=custom_criteria)
    # Weights should have been normalized. Let's check:
    normalized_weights = {k: v['weight'] for k,v in custom_evaluator.criteria.items()}
    print(f"Normalized weights: {normalized_weights}") # Should be {"clarity": 0.5, "brevity": 0.5}

    evaluation4 = custom_evaluator.evaluate_response(
        "Prompt", "Response", manual_scores={"clarity": 4, "brevity": 3}
    )
    print(f"Evaluation 4 (Custom Criteria): {evaluation4}")

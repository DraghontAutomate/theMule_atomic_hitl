import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import json
import time

# Adjust path to import from src
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, 'src'))

from llm_prompt_tool.llm_tester import LLMInterface, interaction_log
from llm_prompt_tool.evaluator import ResponseEvaluator, DEFAULT_CRITERIA
from llm_prompt_tool.main_loop import run_refinement_cycle, main as main_loop_main
import argparse


class TestLLMPromptTool(unittest.TestCase):
    """Test suite for the LLM Prompt Tool module."""

    def setUp(self):
        """Set up for each test."""
        # Clear the global interaction log before each test
        interaction_log.clear()

    # --- Tests for llm_tester.py ---

    def test_llm_interface_init_mock(self):
        """Tests that LLMInterface initializes in mock mode by default."""
        llm_interface = LLMInterface()
        self.assertEqual(llm_interface.model_name, "mock-model", "Default model should be 'mock-model'.")

    def test_llm_interface_get_response_mock(self):
        """Tests that the mock LLMInterface returns a response and logs the interaction."""
        llm_interface = LLMInterface()
        system_prompt = "You are a test assistant."
        user_prompt = "Test prompt."

        start_time = time.time()
        response = llm_interface.get_response(system_prompt, user_prompt)
        end_time = time.time()

        self.assertIsInstance(response, str, "Response should be a string.")
        self.assertTrue(len(response) > 0, "Response string should not be empty.")

        # Check interaction log
        self.assertEqual(len(interaction_log), 1, "One entry should be added to the interaction log.")
        log_entry = interaction_log[0]
        self.assertEqual(log_entry["system_prompt"], system_prompt)
        self.assertEqual(log_entry["user_prompt"], user_prompt)
        self.assertEqual(log_entry["llm_response"], response)
        self.assertEqual(log_entry["model_name"], "mock-model")
        self.assertIsNone(log_entry["evaluation"], "Evaluation should be None initially.")
        self.assertGreaterEqual(log_entry["timestamp"], start_time)
        self.assertLessEqual(log_entry["timestamp"], end_time)

    # --- Tests for evaluator.py ---

    def test_evaluator_weight_normalization(self):
        """Tests that ResponseEvaluator normalizes weights that do not sum to 1."""
        custom_criteria = {
            "clarity": {"weight": 0.6},
            "brevity": {"weight": 0.6} # Total weight is 1.2
        }
        evaluator = ResponseEvaluator(criteria=custom_criteria)

        total_weight = sum(details["weight"] for details in evaluator.criteria.values())
        self.assertAlmostEqual(total_weight, 1.0, msg="Weights should be normalized to sum to 1.0.")
        self.assertAlmostEqual(evaluator.criteria["clarity"]["weight"], 0.5)
        self.assertAlmostEqual(evaluator.criteria["brevity"]["weight"], 0.5)

    def test_evaluate_response_with_manual_scores(self):
        """Tests the evaluator's scoring logic with provided manual scores."""
        evaluator = ResponseEvaluator() # Uses default criteria
        manual_scores = {"relevance": 5, "coherence": 4, "accuracy": 3, "completeness": 2}

        evaluation = evaluator.evaluate_response("prompt", "response", manual_scores=manual_scores)

        expected_score = (5 * 0.3) + (4 * 0.25) + (3 * 0.3) + (2 * 0.15) # Based on default weights
        self.assertAlmostEqual(evaluation["overall_score"], expected_score,
                               "Overall weighted score is calculated incorrectly.")
        self.assertEqual(evaluation["criteria_scores"]["relevance"]["score"], 5)

    def test_evaluate_response_mock_scores(self):
        """Tests the evaluator's fallback to mock scoring when no manual scores are given."""
        evaluator = ResponseEvaluator()
        evaluation = evaluator.evaluate_response("prompt", "response")

        self.assertIsNotNone(evaluation["overall_score"], "Overall score should be calculated.")
        self.assertIsNotNone(evaluation["criteria_scores"]["relevance"]["score"],
                             "Mock score for relevance should be generated.")

    def test_suggest_improvements_low_score(self):
        """Tests that prompt improvements are suggested for low-scoring evaluations."""
        evaluator = ResponseEvaluator()
        # Simulate a low-scoring evaluation
        low_score_eval = {
            "overall_score": 1.5,
            "criteria_scores": {
                "relevance": {"score": 1},
                "accuracy": {"score": 2}
            }
        }
        sys_prompt, user_prompt = "Be an assistant.", "Tell me stuff."

        new_sys, new_user = evaluator.suggest_prompt_improvements(sys_prompt, user_prompt, low_score_eval)

        self.assertNotEqual(sys_prompt, new_sys, "System prompt should be modified for low scores.")
        self.assertIn("specific", new_sys.lower(), "Suggestion should include being more specific.")
        self.assertIn("relevant", new_sys.lower(), "Suggestion should address low relevance score.")

    def test_suggest_improvements_high_score(self):
        """Tests that no prompt improvements are suggested for high-scoring evaluations."""
        evaluator = ResponseEvaluator()
        high_score_eval = {"overall_score": 4.5, "criteria_scores": {}}
        sys_prompt, user_prompt = "Be an assistant.", "Tell me stuff."

        new_sys, new_user = evaluator.suggest_prompt_improvements(sys_prompt, user_prompt, high_score_eval)

        self.assertEqual(sys_prompt, new_sys, "System prompt should not change for high scores.")
        self.assertEqual(user_prompt, new_user, "User prompt should not change for high scores.")


    # --- Tests for main_loop.py ---

    @patch('llm_prompt_tool.main_loop.LLMInterface')
    @patch('llm_prompt_tool.main_loop.ResponseEvaluator')
    def test_run_refinement_cycle_single_iteration(self, mock_evaluator, mock_llm_interface):
        """Tests a single iteration of the refinement cycle, including prompt, evaluation, and decision to exit."""
        # --- Setup Mocks ---
        mock_llm_instance = mock_llm_interface.return_value
        def mock_get_response(sys_prompt, user_prompt):
            interaction_log.append({
                "system_prompt": sys_prompt,
                "user_prompt": user_prompt,
                "llm_response": "Mocked LLM response.",
                "model_name": "mock-model",
                "timestamp": time.time(),
                "evaluation": None
            })
            return "Mocked LLM response."
        mock_llm_instance.get_response.side_effect = mock_get_response

        mock_evaluator_instance = mock_evaluator.return_value
        mock_evaluation_result = {
            "overall_score": 3.5,
            "criteria_scores": {"relevance": {"score": 5}, "coherence": {"score": 4}, "accuracy": {"score": 3}, "completeness": {"score": 2}},
            "feedback": "Mock feedback."
        }
        mock_evaluator_instance.evaluate_response.return_value = mock_evaluation_result
        # Make suggest_prompt_improvements return the same prompts to avoid complexity
        mock_evaluator_instance.suggest_prompt_improvements.side_effect = lambda sys_prompt, usr_prompt, eval_res: (sys_prompt, usr_prompt)

        # --- Run the function under test ---
        initial_sys_prompt = "Initial system prompt."
        initial_user_prompt = "Test user prompt."
        run_refinement_cycle(mock_llm_instance, mock_evaluator_instance, initial_sys_prompt, initial_user_prompt, 0, 1)

        # --- Assertions ---
        # 1. LLM was called with the correct prompts
        mock_llm_instance.get_response.assert_called_once_with(initial_sys_prompt, initial_user_prompt)

        # 2. Evaluator was called to evaluate the response
        mock_evaluator_instance.evaluate_response.assert_called_once()
        eval_args, eval_kwargs = mock_evaluator_instance.evaluate_response.call_args
        self.assertEqual(eval_args[0], initial_user_prompt)
        self.assertEqual(eval_args[1], 'Mocked LLM response.')
        self.assertIn('relevance', eval_kwargs['manual_scores'])

        # 3. Interaction log was updated with the evaluation
        self.assertEqual(len(interaction_log), 1, "Interaction log should have one entry.")
        self.assertEqual(interaction_log[0]['evaluation'], mock_evaluation_result, "Evaluation result not logged correctly.")

        # 4. Prompt improvement suggestion was attempted
        mock_evaluator_instance.suggest_prompt_improvements.assert_called_once()

if __name__ == '__main__':
    unittest.main()

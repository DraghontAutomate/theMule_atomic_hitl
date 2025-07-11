import time
import random

# In a real scenario, you would use a library like 'openai', 'anthropic', etc.
# from openai import OpenAI

# --- Mock LLM Configuration ---
MOCK_LLM_RESPONSE_LATENCY_SECONDS = (0.5, 2.0) # Simulate network delay
MOCK_LLM_RESPONSES = [
    "This is a insightful and relevant answer.",
    "The provided information is accurate and well-structured.",
    "This response directly addresses the query.",
    "Consider rephrasing the question for a more specific answer.",
    "The answer could be improved with more detail.",
    "I'm not sure I understand the question fully.",
    "This is a generic response.",
]

# --- Storage for prompts and responses ---
# This could be a database or a file in a real application
interaction_log = []

class LLMInterface:
    def __init__(self, api_key=None, model_name="mock-model"):
        """
        Initializes the LLM interface.
        For a real LLM, you'd set up the API client here.
        Example:
        if model_name != "mock-model":
            self.client = OpenAI(api_key=api_key)
        """
        self.model_name = model_name
        self.api_key = api_key # Store API key if provided, for real LLM usage

        if self.model_name == "mock-model":
            print("Using Mock LLM Interface.")
        else:
            # Placeholder for real LLM client initialization
            # For example, for OpenAI:
            # try:
            #     self.client = OpenAI(api_key=self.api_key)
            #     print(f"Initialized OpenAI client for model: {self.model_name}")
            # except Exception as e:
            #     print(f"Error initializing LLM client: {e}")
            #     raise
            print(f"Real LLM integration for '{self.model_name}' would be set up here.")
            print("Ensure you have the necessary libraries (e.g., 'openai') installed and API keys configured.")


    def get_response(self, system_prompt: str, user_prompt: str) -> str:
        """
        Sends a prompt to the LLM and returns the response.
        """
        full_prompt_for_logging = f"SYSTEM: {system_prompt}\nUSER: {user_prompt}"
        print(f"\n--- Sending to LLM ({self.model_name}) ---")
        print(f"System Prompt: {system_prompt}")
        print(f"User Prompt: {user_prompt}")

        if self.model_name == "mock-model":
            delay = random.uniform(MOCK_LLM_RESPONSE_LATENCY_SECONDS[0], MOCK_LLM_RESPONSE_LATENCY_SECONDS[1])
            time.sleep(delay)
            response_text = random.choice(MOCK_LLM_RESPONSES)
            print(f"Mock LLM Response (after {delay:.2f}s): {response_text}")
        else:
            # Placeholder for actual API call
            # Example for OpenAI ChatCompletion:
            # try:
            #     chat_completion = self.client.chat.completions.create(
            #         messages=[
            #             {"role": "system", "content": system_prompt},
            #             {"role": "user", "content": user_prompt},
            #         ],
            #         model=self.model_name,
            #     )
            #     response_text = chat_completion.choices[0].message.content
            # except Exception as e:
            #     print(f"Error getting response from LLM: {e}")
            #     response_text = "Error: Could not get response from LLM."
            response_text = f"Simulated response for '{self.model_name}' to prompt: '{user_prompt}'"
            print(f"LLM Response: {response_text}")


        # Log the interaction
        interaction_log.append({
            "timestamp": time.time(),
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "llm_response": response_text,
            "model_name": self.model_name,
            "evaluation": None # To be filled by the evaluator
        })

        return response_text

    def get_interaction_log(self):
        """
        Returns the log of all interactions.
        """
        return interaction_log

# --- Example Usage (for testing this script directly) ---
if __name__ == "__main__":
    # Example with Mock LLM
    mock_llm = LLMInterface() # Defaults to mock-model
    print("\n--- Testing Mock LLM ---")
    system_prompt_1 = "You are a helpful assistant."
    user_prompt_1 = "What is the capital of France?"
    response_1 = mock_llm.get_response(system_prompt_1, user_prompt_1)

    system_prompt_2 = "You are a creative writer."
    user_prompt_2 = "Suggest a plot for a sci-fi novel."
    response_2 = mock_llm.get_response(system_prompt_2, user_prompt_2)

    # Example with a placeholder for a real LLM
    # To run this, you'd need to set an API key environment variable
    # and potentially install the 'openai' library: pip install openai
    # For example, if you had OPENAI_API_KEY set:
    # real_llm = LLMInterface(api_key="YOUR_API_KEY_HERE_OR_READ_FROM_ENV", model_name="gpt-3.5-turbo")
    # print("\n--- Testing Real LLM (Placeholder) ---")
    # response_3 = real_llm.get_response("You are a factual bot.", "Explain quantum entanglement.")
    # print(f"Response from {real_llm.model_name}: {response_3}")


    print("\n--- Interaction Log ---")
    for entry in mock_llm.get_interaction_log():
        print(f"{entry['timestamp']}: P: '{entry['user_prompt'][:30]}...' R: '{entry['llm_response'][:30]}...'")

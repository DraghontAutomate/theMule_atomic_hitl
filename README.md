# theMule_atomic_hitl
Human-in-the-Loop for Close Guidance

## General Overview

`theMule_atomic_hitl` (Human-in-the-Loop) is a tool designed to facilitate precise, reviewed modifications to text-based data. It provides a PyQt5-based graphical user interface where a user can:

*   View content, often in a diff editor comparing original and modified versions.
*   Guide an automated or semi-automated editing process (currently using mock LLM interactions for locating and editing text snippets).
*   Review proposed changes.
*   Approve, reject, or refine these changes.

The tool is highly configurable via JSON, allowing users to define:
*   Data fields to be displayed (labels, text inputs, and a central diff editor).
*   Actions that can be performed (e.g., approve, increment version).

This makes it adaptable for various scenarios where careful, step-by-step oversight of textual changes is critical, such as data curation, content moderation, or guided document editing.

## Key Features

*   **Library First:** Designed to be easily integrated as a component (e.g., a node in a LangGraph workflow) or run standalone.
*   **Configurable UI:** Define displayed fields and actions via JSON configuration.
*   **Diff Editor:** Central component for reviewing changes to text.
*   **Queued Editing:** Manages edit requests in a queue, processing them atomically.
*   **Two-Loop Editing Logic (Conceptual):**
    *   *Gatekeeper Loop:* User confirms the location of the text to be edited.
    *   *Worker Loop:* User reviews and approves/rejects the proposed edit to the snippet.
*   **Metadata Display:** Show relevant metadata alongside the content being edited.
*   **Automated Testing**: Comes with a full test suite and a reporting script (`run_tests.py`).
*   **Git Pre-Push Hook**: Includes a pre-push hook script (`pre-push-hook.sh`) to ensure repository stability by running tests before every push.

## Testing and Quality Assurance

This project includes a comprehensive test suite to ensure stability and correctness.

### Running Tests

A custom script, `run_tests.py`, is provided to discover, run, and report on all unit tests in the repository.

1.  **Install Dependencies:** Ensure all project and development dependencies are installed.
    ```bash
    # This installs the package itself and all dependencies from requirements.txt
    pip install .
    ```

2.  **Run Full Test Suite:**
    ```bash
    python run_tests.py
    ```

3.  **Run Tests for a Specific Module:**
    The script can target specific modules within the `src` directory.
    ```bash
    # Run tests only for the themule_atomic_hitl module
    python run_tests.py themule_atomic_hitl

    # Run tests only for the llm_prompt_tool module
    python run_tests.py llm_prompt_tool
    ```
    
The script will output a detailed, human-readable report to the console, summarizing the results and detailing any failures or errors. For more detailed documentation on the `llm_prompt_tool`, please see [`doc/llm_prompt_tool_description.md`](doc/llm_prompt_tool_description.md).


### Pre-Push Hook (Recommended for Developers)

To automatically run the test suite before every `git push` and prevent pushing broken code, a pre-push hook is provided.

**Installation:**

1.  Make the hook script executable:
    ```bash
    chmod +x pre-push-hook.sh
    ```
2.  Copy the script into your local `.git/hooks` directory:
    ```bash
    cp pre-push-hook.sh .git/hooks/pre-push
    ```

Now, before you can push any changes, Git will automatically execute this script. If any tests fail, the push will be aborted, prompting you to fix the issues first.

## Using `theMule_atomic_hitl` as a Library

The primary way to use the tool is via the `hitl_node_run` function.

```python
from themule_atomic_hitl import hitl_node_run
from PyQt5.QtWidgets import QApplication # Optional, for existing Qt apps

# Example 1: Reviewing a simple string with default configuration
text_to_review = "This is the initial content that needs human oversight."
final_data = hitl_node_run(content_to_review=text_to_review)

if final_data:
    print("Review complete. Final data:", final_data)
else:
    print("Review session was cancelled or failed.")

# Example 2: Reviewing content from a dictionary, with a custom UI config
# Assumes 'my_custom_config.json' defines UI fields and actions
# and 'my_data_dict' contains fields like 'originalText', 'editedText', and other metadata.
# my_data_dict = {
# "originalText": "Old version of text.",
# "editedText": "New version to review.",
# "projectName": "Project X",
# "status": "Pending Review"
# }
# final_data_custom = hitl_node_run(
# content_to_review=my_data_dict,
# custom_config_path="path/to/my_custom_config.json"
# )

# Example 3: Integrating into an existing PyQt application
# my_qt_app = QApplication.instance() or QApplication(sys.argv)
# ... (your application setup) ...
# final_data_integrated = hitl_node_run(
# content_to_review="Some text for HITL within my app.",
# existing_qt_app=my_qt_app
# )
# ... (your application continues, event loop is managed by you) ...
```

### `hitl_node_run` Parameters:

*   `content_to_review (Union[str, Dict[str, Any]])`:
    *   If a `str`, it's treated as the main text for editing. The UI will show this string in both "original" and "modified" views of the diff editor initially.
    *   If a `Dict`, it's used as the initial data structure. It should contain keys that match the `originalDataField` and `modifiedDataField` specified in your configuration for the diff editor (e.g., `"originalText"`, `"editedText"` by default). Other keys can hold metadata displayed by other configured UI fields.
*   `custom_config_path (Optional[str])`: Path to a JSON file for custom UI configuration. If `None`, a default configuration is used. See `examples/config.json` for structure.
*   `existing_qt_app (Optional[QApplication])`: If you're integrating into an existing PyQt5 application, pass your `QApplication` instance here. The tool will use it instead of creating a new one. This allows `hitl_node_run` to be a blocking call that integrates into your app's event loop.

The function returns a dictionary with the final state of the data after the user closes the HITL window (e.g., by approving the content), or `None` if an error occurs.

## Configuration

The UI and behavior of the tool are controlled by a configuration JSON.

*   **Default Configuration:** A basic default configuration is built into the tool.
*   **Custom Configuration:** You can provide a path to your own JSON file (via `custom_config_path` in `hitl_node_run`) to override or extend the default.
    *   The `fields` array defines what UI elements appear (labels, text inputs, the diff editor).
    *   The `actions` array defines buttons and their associated backend handlers.
    *   The `settings` object can define things like the window title.

See `examples/config.json` for a detailed example of the configuration structure. The `src/themule_atomic_hitl/config.py` file also defines the default structure.

## Workflow (User Perspective)

1.  **Initialization:**
    *   The application loads with the provided content and UI configuration.
    *   The main interface displays the data according to the configured fields, often featuring a central diff editor.

2.  **Requesting an Edit (If applicable for the workflow):**
    *   The UI might allow users to specify a "Hint" (text to locate) and "Instruction" (change to make).
    *   This request is added to an internal processing queue.

3.  **Location Confirmation (Gatekeeper Loop - Mocked):**
    *   The system attempts to locate the text snippet (mock LLM).
    *   The user confirms if this is the correct snippet.

4.  **Edit Proposal & Review (Worker Loop - Mocked):**
    *   The system generates a proposed modification (mock LLM).
    *   The UI displays a diff view.

5.  **Decision & Iteration:**
    *   User actions: Approve, Reject/Refine (re-prompt for hint/instruction), Cancel.

6.  **General Actions & Session Management:**
    *   Users can perform general actions defined in the configuration (e.g., "Increment Version").
    *   A primary "Approve & End Session" action finalizes changes and closes the tool.

## Running Examples Locally

The `examples/run_tool.py` script demonstrates various ways to use `hitl_node_run` for GUI-based interaction.

For command-line usage, the `examples/run_terminal.sh` script shows how to start the application in terminal mode, passing data and configuration files directly.

### Dependencies

**1. Python:**
   - Ensure you have Python 3.6+ installed.

**2. System Dependencies (for Linux, especially headless):**
   - For PyQt5 to run in environments without a physical display (e.g., some CI/CD pipelines or Docker containers), you might need X11 client libraries and Xvfb (X Virtual FrameBuffer).
     ```bash
     # For Debian/Ubuntu:
     sudo apt-get update
     sudo apt-get install -y xvfb libxkbcommon-x11-0 libxcb-icccm4 libxcb-image0 \
     libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-xfixes0 \
     libxcb-xinerama0 libx11-xcb1 # Add other libxcb* as needed by your Qt version
     ```

**3. Python Packages:**
   - Install requirements:
     ```bash
     pip install -r requirements.txt
     ```
     This typically includes `PyQt5` and `PyQtWebEngine`.

### Launching the Example Script

Once dependencies are installed:

- Navigate to the repository root.
- **On a desktop environment (Windows, macOS, Linux with a display server):**
  ```bash
  python examples/run_tool.py
  ```
- **On a headless Linux environment (or if you encounter Qt platform errors):**
  You might need to use `xvfb-run`:
  ```bash
  xvfb-run -a python examples/run_tool.py
  ```

### Windows Installation and Setup

**1. Python:**
   - Download and install Python 3.6+ from [python.org](https://www.python.org/downloads/windows/).
   - **Important:** During installation, make sure to check the box that says "Add Python to PATH". This will make it easier to run Python and pip from the command line. If you forget this step, you may need to add it manually to your system's environment variables.

**2. Create a Virtual Environment (Recommended):**
   - Open Command Prompt (cmd) or PowerShell.
   - Navigate to your project directory:
     ```bash
     cd path\to\your\project
     ```
   - Create a virtual environment:
     ```bash
     python -m venv venv
     ```
   - Activate the virtual environment:
     ```bash
     venv\Scripts\activate
     ```
     Your command prompt should now show `(venv)` at the beginning.

**3. Install Python Packages:**
   - With the virtual environment activated, install the required packages using pip:
     ```bash
     pip install -r requirements.txt
     ```
     This will install `PyQt5`, `PyQtWebEngine`, and any other necessary dependencies.
     - If `pip` is not recognized, ensure Python's Scripts directory (e.g., `C:\Users\YourUser\AppData\Local\Programs\Python\Python3X\Scripts`) is in your PATH. If you used a virtual environment, `pip` should be available automatically when the environment is active.
     - `PyQt5` installation on Windows is usually straightforward via pip as it provides pre-compiled binaries (wheels).

**4. Running the Examples:**
   - Navigate to the repository root (if you're not already there).
   - Ensure your virtual environment is active.
   - Run the example script:
     ```bash
     python examples\run_tool.py
     ```
     Note the use of backslashes for paths in Windows command prompt, though forward slashes often work too, especially in PowerShell or when Python itself interprets the path.

**5. Potential Issues & Tips (Windows):**
    *   **Firewall/Antivirus:** Sometimes, security software can interfere with Python scripts or network access (e.g., if the Monaco editor CDN is blocked). If you encounter issues, try temporarily disabling them or adding exceptions for Python.
    *   **Long File Paths:** Windows has a historical limitation on file path lengths (MAX_PATH ~260 characters). While less common with modern Python versions and Windows 10/11 (if long path support is enabled), it can sometimes cause issues with deeply nested projects or long virtual environment paths. Keeping project paths relatively short is a good practice.
    *   **Environment Variables:** Ensure your `PATH` environment variable is set up correctly to find `python.exe` and `pip.exe` if you didn't add Python to PATH during installation or are not using a virtual environment.

The `examples/run_tool.py` script will execute several test cases, launching the HITL UI for each. You can find example data in `examples/sample_data.json` and an example configuration in `examples/config.json`.

The Monaco editor component used in the frontend is loaded from a CDN, so an active internet connection is generally required when running the application for the rich diff view.

## Library Usage: Processing In-Memory Text

A common use case is to process text that your application already has in memory, rather than loading it from a file within the HITL tool. `hitl_node_run` directly supports this.

When you pass a string to `content_to_review`, `theMule_atomic_hitl` uses this string for both the "original" and "modified" sides of the diff editor by default. The specific dictionary keys used are determined by the `originalDataField` and `modifiedDataField` settings in the configuration (defaulting to `"originalText"` and `"editedText"` respectively).

Here's how you can use it:

```python
from themule_atomic_hitl import hitl_node_run
import json

# Your application generates or holds some text
my_document_text = "This is the current version of a document generated by my application. It needs a human to review it and make necessary corrections."

print("Launching HITL tool for in-memory text review...")

# Pass the in-memory string directly
# This will use the default configuration.
final_data = hitl_node_run(content_to_review=my_document_text)

if final_data:
    print("\nReview complete. Final data received from HITL tool:")
    print(json.dumps(final_data, indent=2))

    # The edited text will be in final_data["editedText"] by default
    # (or whatever field is configured as modifiedDataField)
    edited_document_text = final_data.get("editedText") # Default key

    if edited_document_text:
        print(f"\nOriginal Text:\n{my_document_text}")
        print(f"\nEdited Text:\n{edited_document_text}")

        if my_document_text == edited_document_text:
            print("\nNo changes were made during the review.")
        else:
            print("\nChanges were made during the review.")
            # Your application can now use the edited_document_text
    else:
        print("Could not find the edited text in the returned data using the default key 'editedText'.")
else:
    print("\nHITL review session was cancelled or an error occurred.")

```

This example demonstrates how to seamlessly integrate `theMule_atomic_hitl` into a workflow where text is dynamically generated or managed within your Python application. The user can then edit this text, and the modified version is returned for further use.

## Integration with LangGraph (or similar Agentic Frameworks)

`theMule_atomic_hitl` is well-suited for integration into agentic workflows, such as those built with [LangGraph](https://langchain-ai.github.io/langgraph/), where human oversight is needed at specific steps. The `hitl_node_run` function acts as a synchronous, blocking call, making it straightforward to use as a node in a graph.

**Conceptual LangGraph Use Case:**

Imagine an AI agent tasked with drafting a technical report. The process might involve:

1.  **Content Generation Node:** An LLM generates a draft of a section of the report.
2.  **HITL Review Node:** The generated text is passed to `theMule_atomic_hitl` for human review.
    *   The `hitl_node_run` function is called with the generated text.
    *   The agent's execution pauses, and the HITL UI appears, allowing a human expert to:
        *   Correct factual inaccuracies.
        *   Improve clarity and style.
        *   Add missing information.
        *   Utilize the tool's hint/instruction feature for targeted edits if needed.
    *   Once the human approves the changes, the HITL UI closes, and `hitl_node_run` returns the refined text (and any other metadata).
3.  **Formatting/Storage Node:** The human-approved text is then passed to a subsequent node in the graph for final formatting, storage, or integration into the larger report.
4.  **Looping/Continuation:** Depending on the graph's logic, the process might loop to generate and review further sections, or conclude.

**Why it works well:**

*   **Blocking Call:** `hitl_node_run` only returns after the human has completed their review and closed the UI. This fits naturally into the sequential execution model of many LangGraph nodes.
*   **Data Passthrough:** The function takes data (string or dictionary) as input and returns the modified data, allowing seamless data flow within the agent's state.
*   **Configurability:** The HITL UI can be customized (via JSON config) to display relevant context or metadata from the agent's state, providing the human reviewer with necessary information. For example, you could display the agent's previous steps or the overall goal.

**Simplified Code Idea (Conceptual):**

```python
# (Conceptual - Assumes LangGraph setup)
# from langgraph.graph import StateGraph, END
# from themule_atomic_hitl import hitl_node_run
# from typing import TypedDict, Annotated, List
# import operator

# class AgentState(TypedDict):
#     raw_content: str
#     reviewed_content: str
#     log: List[str]

# def generate_content_node(state: AgentState):
#     # Replace with actual LLM call
#     generated_text = f"This is AI generated content based on: {state.get('topic', 'default topic')}."
#     print("AI Node: Generated content.")
#     return {"raw_content": generated_text, "log": state["log"] + ["Generated content."]}

# def human_review_node(state: AgentState):
#     print("HITL Node: Requesting human review...")
#     current_text = state["raw_content"]

#     # Call the HITL tool
#     # You could pass a custom config if needed, e.g., to display the 'topic'
#     hitl_result = hitl_node_run(content_to_review=current_text)

#     if hitl_result and "editedText" in hitl_result:
#         reviewed_text = hitl_result["editedText"]
#         print("HITL Node: Review complete.")
#         return {"reviewed_content": reviewed_text, "log": state["log"] + ["Content reviewed by human."]}
#     else:
#         print("HITL Node: Review cancelled or failed.")
#         # Handle cancellation, perhaps by re-routing or ending
#         return {"reviewed_content": current_text, "log": state["log"] + ["Human review cancelled/failed."]}

# def final_processing_node(state: AgentState):
#     print("Final Node: Processing reviewed content.")
#     # Do something with state["reviewed_content"]
#     print(f"Final content: {state['reviewed_content']}")
#     return {"log": state["log"] + [f"Processed: {state['reviewed_content']}"]}

# # Setup LangGraph (conceptual)
# # builder = StateGraph(AgentState)
# # builder.add_node("generator", generate_content_node)
# # builder.add_node("human_review", human_review_node)
# # builder.add_node("finalizer", final_processing_node)

# # builder.set_entry_point("generator")
# # builder.add_edge("generator", "human_review")
# # builder.add_edge("human_review", "finalizer")
# # builder.add_edge("finalizer", END)

# # graph = builder.compile()
# # inputs = {"topic": "The Future of AI", "log": []}
# # for event in graph.stream(inputs):
# #     print(event)
```

This integration pattern allows for powerful "human-in-the-loop" capabilities within autonomous agent systems, ensuring critical steps are validated or refined by human intelligence.

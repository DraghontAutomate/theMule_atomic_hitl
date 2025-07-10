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

The `examples/run_tool.py` script demonstrates various ways to use `hitl_node_run`.

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

The `examples/run_tool.py` script will execute several test cases, launching the HITL UI for each. You can find example data in `examples/sample_data.json` and an example configuration in `examples/config.json`.

The Monaco editor component used in the frontend is loaded from a CDN, so an active internet connection is generally required when running the application for the rich diff view.

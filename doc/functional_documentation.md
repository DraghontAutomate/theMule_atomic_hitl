```markdown
# Functional Documentation: TheMule Atomic HITL

This document provides a functional overview of the modules within the `themule_atomic_hitl` package.

## Core Modules (`src/themule_atomic_hitl/`)

### 1. `__init__.py`
*   **Purpose**: Serves as the main entry point for the `themule_atomic_hitl` package.
*   **Functionality**:
    *   Exposes key functions from other modules for easier access when the package is imported.
    *   Specifically, it makes `run_application` (from `runner.py`) and `hitl_node_run` (from `hitl_node.py`) available at the package level (e.g., `from themule_atomic_hitl import hitl_node_run`).
    *   Defines the package version (`__version__`).

### 2. `config.py`
*   **Purpose**: Manages all configuration settings for the HITL application.
*   **Key Class**: `Config`
*   **Functionality**:
    *   **Default Configuration**: Defines a `DEFAULT_CONFIG` dictionary containing fallback settings for UI elements (fields, actions), window appearance, and LLM provider details (models, API keys, system prompts).
    *   **Custom Configuration**:
        *   Can load custom settings from a user-provided JSON file.
        *   Can accept custom settings as a Python dictionary.
    *   **Merging**: Merges custom configurations with the default configuration. For dictionaries (like `settings` or `llm_config`), it performs a deep merge. For lists (like `fields` and `actions`), the custom configuration completely overrides the default.
    *   **Accessors**: Provides methods to retrieve the entire configuration (`get_config()`), specific field configurations (`get_field_config()`), action configurations (`get_action_config()`), LLM configurations (`get_llm_config()`), and system prompts (`get_system_prompt()`).
    *   **Properties**: Offers convenient properties like `main_editor_original_field`, `main_editor_modified_field`, and `window_title` to easily access commonly needed configuration values.

### 3. `core.py`
*   **Purpose**: Implements the central logic and state management for the Human-In-The-Loop (HITL) editing process. This module is designed to be UI-agnostic.
*   **Key Class**: `SurgicalEditorLogic`
*   **Functionality**:
    *   **State Management**: Holds the current data being edited (`self.data`) and an initial snapshot for revert functionality.
    *   **Two-Loop Editing Process**:
        *   **Gatekeeper Loop**: User provides a hint and instruction. The system (via `LLMService`) locates the relevant text snippet. The user is then asked to confirm or correct this location.
        *   **Worker Loop**: Once the location is confirmed, the system (via `LLMService`) generates an edited version of the snippet based on the user's instruction. The user reviews a diff, can manually edit the suggestion, approve it, or reject it.
    *   **Edit Request Queue**: Manages a `deque` of pending edit requests. Each request includes the user's hint, instruction, and a snapshot of the main content at the time the request was made (to ensure edits are based on the correct context).
    *   **Active Edit Task**: Tracks the currently processed edit task, including its status (e.g., `locating_snippet`, `awaiting_location_confirmation`, `awaiting_diff_approval`).
    *   **LLM Interaction**:
        *   Uses `LLMService` to perform:
            *   **Snippet Location**: (`_llm_locator`) Based on user hint and content snapshot.
            *   **Snippet Editing**: (`_llm_editor`) Based on user instruction and the located snippet.
    *   **Callbacks**: Communicates with a frontend (via the `Backend` in `runner.py`) through a dictionary of callback functions. These callbacks are used to:
        *   Update the UI view (`update_view`).
        *   Show error messages (`show_error`).
        *   Request user confirmation for located snippets (`confirm_location_details`).
        *   Display diff previews (`show_diff_preview`).
        *   Ask for clarification if an edit is rejected (`request_clarification`).
    *   **Action Handling**:
        *   `add_edit_request()`: Adds a new task to the queue.
        *   `proceed_with_edit_after_location_confirmation()`: Moves from location confirmation to generating the edit.
        *   `process_llm_task_decision()`: Handles user decisions (approve, reject, cancel) on LLM-generated edits.
        *   `update_active_task_and_retry()`: Allows retrying a task with new hints/instructions after a rejection.
        *   `perform_action()`: Handles generic UI actions (e.g., "approve main content," "revert changes") by dispatching to specific `handle_...` methods.
    *   **Data Integrity**: Aims to apply edits atomically and manages the content state throughout the session.

### 4. `hitl_node.py`
*   **Purpose**: Provides a simplified, high-level library interface for running the HITL tool.
*   **Key Function**: `hitl_node_run()`
*   **Functionality**:
    *   **Simplified Entry Point**: Makes it easy to integrate the HITL tool into other Python applications or scripts without needing to manage PyQt5 application setup directly.
    *   **Input Handling**:
        *   Accepts `content_to_review` as either a string (for simple text editing) or a dictionary (for more complex data structures that match the expected diff editor fields).
        *   Accepts an optional `custom_config_path` to a JSON file for UI and LLM customization.
        *   Accepts an optional `existing_qt_app` instance, allowing integration into larger, existing PyQt5 applications.
    *   **Configuration Management**: Initializes the `Config` object using the provided custom path or defaults.
    *   **Data Preparation**: Formats the input `content_to_review` into the `initial_data` dictionary expected by the `runner` and `core` modules.
    *   **Application Launch**: Calls `run_application` (from `runner.py`) to start the UI.
    *   **Return Value**:
        *   If managing its own `QApplication` loop, it returns the final state of the data as a dictionary after the UI session is closed.
        *   If an `existing_qt_app` is used, it returns the `QMainWindow` instance, and the caller is responsible for managing the event loop and retrieving data.
        *   Returns `None` on error.

### 5. `llm_service.py`
*   **Purpose**: Encapsulates all interactions with Large Language Models (LLMs).
*   **Key Class**: `LLMService`
*   **Functionality**:
    *   **Configuration-Driven**: Initialized with an `llm_config` dictionary (typically from the main `Config` object), which specifies provider details, API keys (via environment variables), model names, and default system prompts for different tasks.
    *   **Provider Support**:
        *   **Google**: Supports Google's Generative AI models (e.g., Gemini) via `ChatGoogleGenerativeAI` from `langchain_google_genai`.
        *   **Local (OpenAI-compatible)**: Supports LLMs served via an OpenAI-compatible API (e.g., Ollama, VLLM) using `ChatOpenAI` from `langchain_openai`.
    *   **LLM Initialization**: (`_initialize_llms`) Sets up LLM client instances based on the provided configuration and environment variables (for API keys and base URLs).
    *   **Task-Based LLM Selection**: (`get_llm_for_task`) Selects the appropriate LLM instance (Google or local) based on the `task_name` (e.g., "locator", "editor") as defined in the `task_llms` section of the configuration. Includes fallback to a default LLM.
    *   **Invocation**: (`invoke_llm`)
        *   Constructs messages (system prompt + user prompt) for the LLM.
        *   Retrieves the system prompt from the configuration based on `task_name` or uses an optional `system_prompt_override`. Falls back to a generic system prompt if none is found.
        *   Sends the request to the selected LLM and returns its content response as a string.
    *   **Environment Variables**: Uses `dotenv` to load API keys and other sensitive information from a `.env` file.

### 6. `runner.py`
*   **Purpose**: Manages the PyQt5 GUI application, including the main window, the web engine view for the HTML/JS frontend, and the communication bridge between Python and JavaScript.
*   **Key Classes**:
    *   `Backend(QObject)`: Acts as the bridge. Exposes Python methods to JavaScript (as `pyqtSlot`) and emits Python signals (`pyqtSignal`) that JavaScript can listen to.
    *   `MainWindow(QMainWindow)`: The main application window that hosts the `QWebEngineView`.
*   **Key Function**: `run_application()`
*   **Functionality**:
    *   **`Backend` Class**:
        *   **Initialization**: Takes initial data and a `Config` object. Instantiates `SurgicalEditorLogic` from `core.py`, providing it with callbacks that map to `Backend`'s signals.
        *   **Slots (JS to Python)**: Defines methods decorated with `@pyqtSlot` that are callable from JavaScript. These methods typically delegate actions to the `SurgicalEditorLogic` instance (e.g., `submitEditRequest`, `performAction`, `terminateSession`).
        *   **Signals (Python to JS)**: Defines `pyqtSignal`s (e.g., `updateViewSignal`, `showDiffPreviewSignal`, `showErrorSignal`) that are emitted by the `Backend` (often triggered by callbacks from `SurgicalEditorLogic`) to send data or trigger actions in the JavaScript frontend.
        *   **`getInitialPayload()`**: A slot called by JS on startup to fetch the initial data and configuration.
    *   **`MainWindow` Class**:
        *   **Initialization**: Sets up the window title (from `Config`), size, and creates a `QWebEngineView`.
        *   **Web Channel**: Creates a `QWebChannel`, registers the `Backend` object with it (making `backend` accessible in JS), and sets this channel on the web page.
        *   **HTML Loading**: Loads `frontend/index.html` into the `QWebEngineView`.
        *   **Session Termination**: Connects the `Backend`'s `sessionTerminatedSignal` to close the window.
    *   **`run_application()` Function**:
        *   **QApplication Management**:
            *   Can use an existing `QApplication` instance if one is passed via the `qt_app` argument.
            *   If `qt_app` is `None`, it checks for an existing instance using `QApplication.instance()`.
            *   If no instance exists, it creates a new `QApplication([])`.
        *   **Window Creation**: Instantiates and shows `MainWindow`.
        *   **Event Loop**:
            *   If it created a new `QApplication`, it runs the event loop (`app_instance_to_use.exec_()`) and returns the final data from `SurgicalEditorLogic` after the loop finishes.
            *   If using an existing/provided `QApplication`, it returns the `MainWindow` instance, and the caller is responsible for the event loop.
    *   **Helper**: `_load_json_file()` to load JSON data from files.

## Frontend Modules (`src/themule_atomic_hitl/frontend/`)

### 1. `index.html`
*   **Purpose**: Defines the structure and layout of the web-based user interface.
*   **Functionality**:
    *   Includes HTML elements for displaying data (labels, text areas, diff editor placeholder), action buttons, and input fields for hints/instructions.
    *   Links to `frontend.js` for dynamic behavior.
    *   Relies on the `QWebChannel` (initialized by `runner.py`) to communicate with the Python `Backend`. The `qt.webChannelTransport` object becomes available in JS, allowing access to the registered `backend` object.

### 2. `frontend.js`
*   **Purpose**: Contains the client-side JavaScript logic for the HITL tool's UI.
*   **Functionality**:
    *   **Initialization**:
        *   Waits for the `QWebChannel` to be ready.
        *   Connects to the Python `backend` object exposed through the channel.
        *   Calls `backend.getInitialPayload()` to fetch initial data and configuration.
        *   Dynamically renders UI elements (fields, actions) based on the received configuration.
    *   **Event Handling**:
        *   Attaches event listeners to buttons (e.g., "Submit Edit," "Approve," "Reject," "Cancel," custom actions) and input fields.
        *   When an event occurs (e.g., button click), it calls the corresponding `@pyqtSlot` on the Python `backend` object (e.g., `backend.submitEditRequest(...)`, `backend.performAction(...)`).
    *   **Signal Handling (Python to JS)**:
        *   Connects JavaScript functions to signals emitted by the Python `Backend` (e.g., `backend.updateViewSignal.connect(updateUIFunction)`).
        *   **`updateView`**: Refreshes the UI with new data from the backend (e.g., updates text fields, status messages, queue information).
        *   **`showDiffPreview`**: Displays the original and LLM-edited snippets in a diff view, often using a library like Monaco Diff Editor (though the specific library is an implementation detail within the JS).
        *   **`promptUserToConfirmLocation`**: Shows UI elements for the user to confirm or adjust the snippet location identified by the LLM.
        *   **`requestClarification`**: Prompts the user to provide a new hint or instruction if an LLM task was rejected.
        *   **`showError`**: Displays error messages received from the backend.
    *   **UI Updates**: Dynamically manipulates the DOM to reflect changes in data, state, and configuration.
    *   **Data Submission**: Collects data from UI fields (e.g., text from input boxes, selected options) and sends it to the Python backend when actions are triggered.

This documentation should provide a clear understanding of each module's role and how they contribute to the overall functionality of TheMule Atomic HITL tool.

## `llm_prompt_tool` Modules (`src/llm_prompt_tool/`)

### 1. `evaluator.py`
*   **Purpose**: To evaluate the quality of LLM responses based on a configurable set of criteria.
*   **Key Class**: `ResponseEvaluator`
*   **Functionality**:
    *   **Criteria-Based Evaluation**: Evaluates LLM responses against criteria like relevance, coherence, accuracy, and completeness. Each criterion has a description, weight, and a scoring guide.
    *   **Score Calculation**: Calculates a weighted score for each response.
    *   **Prompt Improvement Suggestions**: Suggests improvements to system and user prompts based on the evaluation scores.

### 2. `llm_tester.py`
*   **Purpose**: To provide an interface for interacting with an LLM, with support for both mock and real models.
*   **Key Class**: `LLMInterface`
*   **Functionality**:
    *   **Mock LLM**: Includes a mock LLM that returns pre-defined responses with simulated latency, for testing without API keys.
    *   **Real LLM Integration**: Contains placeholder code for integrating with actual LLM APIs (e.g., OpenAI, Anthropic).
    *   **Interaction Logging**: Logs all interactions with the LLM, including prompts, responses, and timestamps.

### 3. `main_loop.py`
*   **Purpose**: To orchestrate the prompt refinement process.
*   **Functionality**:
    *   **Refinement Cycles**: Runs a series of refinement cycles, where it gets a response from the LLM, evaluates it, and then refines the prompt for the next iteration.
    *   **Configuration**: Allows configuration of the initial prompts, number of iterations, and LLM model to use.
    *   **Results Logging**: Saves the results of the refinement process to a JSONL file.

## `main.py`
*   **Purpose**: Serves as the main entry point for the application.
*   **Functionality**:
    *   **Command-line Argument Parsing**: Parses command-line arguments to determine the application's mode (GUI or terminal) and to load custom configuration and initial data files.
    *   **Configuration and Data Loading**: Initializes the `Config` object and loads initial data from specified files.
    *   **Application Launch**: Launches either the GUI or terminal interface based on the parsed arguments.

## `terminal_interface.py`
*   **Purpose**: Provides a terminal-based interface for the Surgical Editor.
*   **Key Class**: `TerminalInterface`
*   **Functionality**:
    *   **User Interaction**: Handles user interaction in the terminal, including displaying menus, receiving input, and showing information from the core logic.
    *   **Core Logic Integration**: Instantiates and interacts with the `SurgicalEditorLogic` class, providing terminal-specific callbacks for UI updates.
    *   **Main Loop**: Runs a main loop to handle user input and display information when the core logic is idle.
```

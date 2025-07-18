```markdown
# Technical Documentation: TheMule Atomic HITL

This document provides detailed technical insight into the modules, classes, and functions within the `themule_atomic_hitl` package.

## `src/themule_atomic_hitl/config.py`

Manages application configuration.

### Class: `Config`

*   **Purpose**: To load, merge, and provide access to configuration settings.
*   **Initialization (`__init__(self, custom_config_path: Optional[str] = None, custom_config_dict: Optional[Dict[str, Any]] = None)`)**:
    *   Loads `DEFAULT_CONFIG` (a hardcoded dictionary).
    *   If `custom_config_dict` is provided, it's prioritized and deep-merged over the default.
    *   Else if `custom_config_path` (a JSON file path) is provided, it's loaded and deep-merged.
*   **Key Private Methods**:
    *   `_load_default_config() -> Dict[str, Any]`: Returns a deep copy of `DEFAULT_CONFIG`.
    *   `_load_custom_config(path: str) -> Optional[Dict[str, Any]]`: Loads JSON from the given path. Handles `FileNotFoundError` and `json.JSONDecodeError`.
    *   `_merge_configs(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]`:
        *   Recursively merges `override` into `base`.
        *   For dictionary values, it merges them.
        *   For list values (e.g., `fields`, `actions`), the `override` list completely replaces the `base` list.
        *   Other value types in `override` replace those in `base`.
*   **Key Public Methods**:
    *   `get_config() -> Dict[str, Any]`: Returns the fully resolved configuration dictionary.
    *   `get_field_config(field_name: str) -> Optional[Dict[str, Any]]`: Retrieves the configuration for a specific field by its `name`.
    *   `get_action_config(action_name: str) -> Optional[Dict[str, Any]]`: Retrieves the configuration for a specific action by its `name`.
    *   `get_llm_config() -> Dict[str, Any]`: Returns the `llm_config` section of the configuration.
    *   `get_system_prompt(task_name: str) -> Optional[str]`: Retrieves a specific system prompt from a file path specified in `llm_config.system_prompts`.
    *   `get_output_schema(task_name: str) -> Optional[Dict[str, Any]]`: Retrieves the JSON output schema for a given LLM task from `llm_config.output_schemas`.
*   **Key Properties**:
    *   `main_editor_original_field -> str`: Name of the data field for the original text in the main diff editor (from `fields` config). Defaults to `'originalText'`.
    *   `main_editor_modified_field -> str`: Name of the data field for the modified text in the main diff editor. Defaults to `'editedText'`.
    *   `window_title -> str`: The default window title from `settings.defaultWindowTitle`. Defaults to `"HITL Review Tool"`.

## `src/themule_atomic_hitl/core.py`

Contains the core business logic for the HITL editing process.

### Class: `SurgicalEditorLogic`

*   **Purpose**: Manages the state and lifecycle of edit requests, orchestrating LLM interactions and UI updates via callbacks.
*   **Initialization (`__init__(self, initial_data: Union[Dict[str, Any], str], config: Config, callbacks: Dict[str, Callable], llm_service_instance: Optional[LLMService] = None)`)**:
    *   `initial_data`: The starting data for the editing session, can be a string or dictionary.
    *   `config`: An instance of `themule_atomic_hitl.config.Config`.
    *   `callbacks`: A dictionary of functions provided by the `Backend`. Expected keys include `'update_view'`, `'show_error'`, `'confirm_location_details'`, `'show_diff_preview'`, `'request_clarification'`, and `'show_llm_disabled_warning'`.
    *   Initializes `llm_service` (an instance of `LLMService`) using `config.get_llm_config()`.
*   **State Attributes**:
    *   `data: Dict[str, Any]`: The current, live data being edited.
    *   `_initial_data_snapshot: Dict[str, Any]`: A deep copy of the initial data for revert functionality.
    *   `edit_request_queue: deque[Dict[str, Any]]`: A queue for pending edit requests. Each request is a dictionary containing `id`, `type` ('hint_based' or 'selection_specific'), `instruction`, `content_snapshot`, `hint`, and `selection_details`.
    *   `active_edit_task: Optional[Dict[str, Any]]`: Holds the details of the task currently being processed.
*   **Key Methods for Edit Lifecycle**:
    *   `add_edit_request(instruction: str, request_type: str, hint: Optional[str] = None, selection_details: Optional[Dict[str, Any]] = None)`: Adds a new structured edit request to the queue and triggers processing.
    *   `_process_next_edit_request()`:
        *   If no active task, pops the next request from the queue.
        *   If `hint_based`, calls `_execute_llm_locator_attempt()`.
        *   If `selection_specific`, it derives the location from selection details and calls `_initiate_llm_edit_for_task()`.
    *   `_execute_llm_locator_attempt()`: (Gatekeeper) Uses `_llm_locator()` and, on success, calls the `confirm_location_details` callback.
    *   `proceed_with_edit_after_location_confirmation(confirmed_location_details: Dict, original_instruction: str)`: (Worker) Called after user confirms location. Updates the task and calls `_initiate_llm_edit_for_task()`.
    *   `_initiate_llm_edit_for_task(task: Dict[str, Any])`: Calls `_llm_editor()` with the correct snippet and instruction, then calls the `show_diff_preview` callback.
    *   `process_llm_task_decision(decision: str, manually_edited_snippet: Optional[str] = None)`:
        *   Handles user's decision ('approve', 'reject', 'cancel').
        *   If 'approve', it calculates the correct character offsets (from locator or selection details) and applies the approved snippet to the content snapshot. The result updates the main content.
        *   If 'reject', it calls the `request_clarification` callback.
    *   `update_active_task_and_retry(new_hint: str, new_instruction: str)`: Restarts a rejected task with new user input.
    *   `_convert_line_col_to_char_offsets(...)`: A helper method to convert 1-based line/column selection data into 0-based character offsets for precise editing.
*   **LLM Interaction Methods**:
    *   `_llm_locator(text_to_search: str, hint: str) -> Optional[Dict[str, Any]]`:
        *   Uses `self.llm_service.invoke_llm()` with task "locator" and a structured output schema.
        *   Parses the JSON response from the LLM.
        *   Finds the returned snippet in `text_to_search` to get `start_idx`, `end_idx`. Includes a lenient regex fallback.
        *   Returns `{'start_idx', 'end_idx', 'snippet'}` or `None`.
    *   `_llm_editor(snippet_to_edit: str, instruction: str) -> str`:
        *   Uses `self.llm_service.invoke_llm()` with task "editor".
        *   Returns the edited snippet.
*   **Generic Action Handling**:
    *   `perform_action(action_name: str, payload: Optional[Dict[str, Any]] = None)`: Dynamically calls `handle_...` methods for actions like `approve_main_content` and `revert_changes`.

## `src/themule_atomic_hitl/llm_service.py`

Handles all communication with Large Language Models.

### Class: `LLMService`

*   **Purpose**: To abstract LLM interactions, manage different providers, and handle API calls.
*   **Initialization (`__init__(self, llm_config: dict)`)**:
    *   `llm_config`: A dictionary (from `Config.get_llm_config()`) containing `providers`, `task_llms`, `system_prompts`, and `output_schemas`.
*   **Private Method (`_initialize_llms()`)**:
    *   Iterates through providers in `self.config['providers']`.
    *   Initializes `langchain` clients (`ChatGoogleGenerativeAI`, `ChatOpenAI`) based on the configuration.
*   **Key Public Methods**:
    *   `get_llm_for_task(task_name: str)`:
        *   Determines which LLM client (`self.google_llm` or `self.local_llm`) to use based on `task_name` and the `task_llms` mapping.
        *   Includes robust fallback to a default provider and then to any available provider.
    *   `invoke_llm(task_name: str, user_prompt: str, system_prompt_override: Optional[str] = None, strict: bool = False) -> Union[str, Dict[str, Any]]`:
        *   Selects the LLM for the task.
        *   Retrieves the system prompt (from file via `Config` class or override).
        *   Checks `self.config['output_schemas']` for the given `task_name`.
        *   **If a schema exists**:
            *   Dynamically creates a Pydantic model from the JSON schema using `jsonschema_to_pydantic`.
            *   Binds the model to the LLM using `llm.with_structured_output(pydantic_model)`.
            *   Invokes the LLM and returns the parsed dictionary from the Pydantic model (`response.dict()`).
        *   **If no schema exists**:
            *   Invokes the LLM normally and returns the string content of the response.

## `src/themule_atomic_hitl/runner.py`

Manages the PyQt5 application, UI window, and Python-JavaScript communication.

### Class: `Backend(QObject)`

*   **Purpose**: Serves as the bridge between `SurgicalEditorLogic` (Python) and the JavaScript frontend. Registered with `QWebChannel` to be accessible from JS.
*   **Initialization (`__init__(self, initial_data: Dict[str, Any], config_manager: Config, parent: Optional[QObject] = None)`)**:
    *   Stores `config_manager`.
    *   Creates `logic_callbacks` dict, mapping core logic's callback needs to methods of this `Backend` instance (e.g., `logic_callbacks['update_view'] = self.on_update_view`).
    *   Instantiates `self.logic = SurgicalEditorLogic(initial_data, config_manager, logic_callbacks)`.
*   **Signals (Python to JS)**: These are `pyqtSignal` instances that, when emitted, trigger corresponding connected functions in JavaScript.
    *   `updateViewSignal = pyqtSignal(object, object, object, name="updateView")`: Emits `(data, config_dict, queue_info)`.
    *   `showDiffPreviewSignal = pyqtSignal(str, str, str, str, name="showDiffPreview")`: Emits `(original_snippet, edited_snippet, before_context, after_context)`.
    *   `requestClarificationSignal = pyqtSignal(name="requestClarification")`.
    *   `showErrorSignal = pyqtSignal(str, name="showError")`: Emits error message string.
    *   `promptUserToConfirmLocationSignal = pyqtSignal(object, str, str, name="promptUserToConfirmLocation")`: Emits `(location_info_dict, original_hint, original_instruction)`.
    *   `sessionTerminatedSignal = pyqtSignal()`: Emitted when the session ends, allowing the application or calling library to react.
*   **Callback Handler Methods (Called by `SurgicalEditorLogic`)**: These methods are invoked by `self.logic` and their primary role is to emit the corresponding signals to the frontend.
    *   `on_update_view(data, config_dict, queue_info)`: Emits `updateViewSignal`.
    *   `on_show_diff_preview(original_snippet, edited_snippet, before_context, after_context)`: Emits `showDiffPreviewSignal`.
    *   `on_request_clarification()`: Emits `requestClarificationSignal`.
    *   `on_show_error(msg: str)`: Emits `showErrorSignal`.
    *   `on_confirm_location_details(location_info, original_hint, original_instruction)`: Emits `promptUserToConfirmLocationSignal`.
*   **Slots (JS to Python)**: These methods are decorated with `@pyqtSlot` and are directly callable from JavaScript via the `QWebChannel`.
    *   `getInitialPayload() -> str`: Returns a JSON string containing `{"config": self.logic.config_manager.get_config(), "data": self.logic.data}`. Called by JS on startup.
    *   `startSession()`: Calls `self.logic.start_session()`.
    *   `submitEditRequest(hint: str, instruction: str)`: Calls `self.logic.add_edit_request(hint, instruction)`.
    *   `submitConfirmedLocationAndInstruction(confirmed_location_details: Dict[str, Any], original_instruction: str)`: Calls `self.logic.proceed_with_edit_after_location_confirmation(...)`.
    *   `submitClarificationForActiveTask(new_hint: str, new_instruction: str)`: Calls `self.logic.update_active_task_and_retry(...)`.
    *   `submitLLMTaskDecisionWithEdit(decision: str, manually_edited_snippet: str)`: Calls `self.logic.process_llm_task_decision(decision, manually_edited_snippet)`.
    *   `submitLLMTaskDecision(decision: str)`: Calls `self.logic.process_llm_task_decision(decision, None)`.
    *   `performAction(action_name: str, payload: Dict[str, Any])`: Calls `self.logic.perform_action(action_name, payload)`.
    *   `terminateSession()`:
        *   Retrieves final data using `self.logic.get_final_data()`.
        *   Prints final data and audit trail to console.
        *   Emits `sessionTerminatedSignal`.

### Class: `MainWindow(QMainWindow)`

*   **Purpose**: The main application window that hosts the web-based UI.
*   **Initialization (`__init__(self, initial_data, config_dict_param, app_instance, parent=None)`)**:
    *   `config_dict_param`: A dictionary representation of the configuration. It's used to create a new `Config` instance: `self.config_manager = Config(custom_config_dict=config_dict_param)`.
    *   Sets window title using `self.config_manager.window_title`.
    *   Creates `self.view = QWebEngineView()`.
    *   Creates `self.channel = QWebChannel()`.
    *   Instantiates `self.backend = Backend(initial_data, self.config_manager, self)`.
    *   Connects `self.backend.sessionTerminatedSignal` to `self.on_session_terminated`.
    *   Registers the backend: `self.channel.registerObject("backend", self.backend)`.
    *   Sets the channel on the web page: `self.view.page().setWebChannel(self.channel)`.
    *   Constructs path to `frontend/index.html` (relative to `runner.py`) and loads it: `self.view.setUrl(QUrl.fromLocalFile(html_path))`.
    *   Sets `self.view` as the central widget.
*   **Method `on_session_terminated()`**: Called when `backend.sessionTerminatedSignal` is emitted. Closes the window (`self.close()`).

### Function: `run_application(initial_data_param: Dict[str, Any], config_param_dict: Dict[str, Any], qt_app: Optional[QApplication] = None) -> Optional[Union[Dict[str,Any], QMainWindow]]`

*   **Purpose**: Entry point for setting up and running the PyQt5 application GUI. Designed for library usage.
*   **Parameters**:
    *   `initial_data_param`: Initial data dictionary.
    *   `config_param_dict`: Configuration dictionary.
    *   `qt_app`: Optional existing `QApplication`.
*   **QApplication Management**:
    *   If `qt_app` is provided, it's used. `should_run_event_loop_here` is `False`.
    *   If `qt_app` is `None`, it tries `QApplication.instance()`. If found, `should_run_event_loop_here` is `False`.
    *   If no instance found, creates `QApplication([])`. `should_run_event_loop_here` is `True`.
*   **Window Creation**: Instantiates `MainWindow(initial_data=initial_data_param, config_dict_param=config_param_dict, app_instance=app_instance_to_use)` and calls `main_window.show()`.
*   **Return Logic**:
    *   If `should_run_event_loop_here` is `True`:
        *   Calls `app_instance_to_use.exec_()` (blocking).
        *   Returns `main_window.backend.logic.get_final_data()` (the final data dict).
    *   If `should_run_event_loop_here` is `False`:
        *   Returns `main_window` (the `QMainWindow` instance). The caller is responsible for the event loop.

## `src/themule_atomic_hitl/hitl_node.py`

Provides a high-level library interface to the HITL tool.

### Function: `hitl_node_run(content_to_review: Union[str, Dict[str, Any]], custom_config_path: Optional[str] = None, existing_qt_app: Optional[QApplication] = None) -> Optional[Dict[str, Any]]`

*   **Purpose**: Simplifies launching the HITL tool, especially for library consumers.
*   **Parameters**:
    *   `content_to_review`: Either a string (becomes the main text) or a dictionary.
    *   `custom_config_path`: Optional path to a custom JSON config file.
    *   `existing_qt_app`: Optional existing `QApplication` instance.
*   **Logic**:
    1.  Initializes `config_manager = Config(custom_config_path=custom_config_path)`.
    2.  Prepares `initial_data: Dict[str, Any]`:
        *   If `content_to_review` is a string, it's used for both `config_manager.main_editor_modified_field` and `config_manager.main_editor_original_field`.
        *   If `content_to_review` is a dict, it's copied. Ensures required editor fields are present, defaulting to empty or copying from modified field if original is missing.
    3.  Calls `returned_value_from_runner = run_application(initial_data_param=initial_data, config_param_dict=config_manager.get_config(), qt_app=existing_qt_app)`.
    4.  **Return Value Handling**:
        *   If `existing_qt_app` was provided to `run_application`:
            *   `run_application` returns the `QMainWindow` instance.
            *   `hitl_node_run` then needs to manage or wait for this window's session to end. It does this by creating a local `QEventLoop`, connecting the window's `backend.sessionTerminatedSignal` to `local_event_loop.quit`, showing the window if not visible, and then `local_event_loop.exec_()`.
            *   After the local loop quits, it retrieves `final_data` from `main_window_instance.backend.logic.get_final_data()`.
        *   If `existing_qt_app` was NOT provided (so `run_application` manages its own loop):
            *   `run_application` returns the `final_data` dictionary directly.
        *   Returns `final_data` or `None` on error/unexpected return.
*   **Error Handling**: Includes a `try-except` block to catch general errors during execution and print tracebacks.

## Frontend (`src/themule_atomic_hitl/frontend/`)

### `index.html` & `frontend.js`

*   **`index.html`**: Standard HTML file. Sets up the basic layout, includes placeholders for dynamic content (like diff editor, fields, actions), and loads `frontend.js`.
*   **`frontend.js`**:
    *   **`QWebChannel` Initialization**:
        ```javascript
        new QWebChannel(qt.webChannelTransport, function (channel) {
            window.backend = channel.objects.backend;
            // ... connect signals, call getInitialPayload ...
        });
        ```
    *   **Initial Load**: Calls `window.backend.getInitialPayload()` to get config and data. Parses the JSON response.
    *   **Dynamic UI Rendering**: Based on the `config` from payload, dynamically creates HTML elements for fields (labels, text inputs, textareas, diff editor container) and action buttons. Assigns IDs for later manipulation.
    *   **Signal Connections**: Connects JS handler functions to signals from `window.backend`:
        *   `window.backend.updateView.connect(function(data, config, queueInfo) { ... });`
        *   `window.backend.showDiffPreview.connect(function(orig, edit, ctxBefore, ctxAfter) { ... });`
        *   And similarly for `requestClarification`, `showError`, `promptUserToConfirmLocation`.
    *   **Event Listeners (User Actions to Python Slots)**:
        *   Attaches click listeners to action buttons.
        *   These listeners collect necessary data from input fields (e.g., hint, instruction, manually edited snippet) and call the corresponding methods on `window.backend` (e.g., `window.backend.submitEditRequest(hint, instruction);`, `window.backend.performAction(actionName, dataPayload);`).
    *   **DOM Manipulation**: Handler functions for signals update the content of HTML elements (e.g., setting text of labels, values of inputs, content of status messages).
    *   **Diff Editor**: If a diff editor is configured (e.g., Monaco), this JS would be responsible for initializing it, setting its original/modified content, and retrieving content from it. The current Python code provides fields for "originalDataField" and "modifiedDataField" in the config, which JS would use to populate the diff editor from the `data` object.
    *   **State Management (Minimal)**: Primarily reflects state from Python backend. May hold temporary UI state (e.g., which task is being confirmed).

This technical documentation provides a deeper dive into the implementation details of the TheMule Atomic HITL tool.

## `src/themule_atomic_hitl/terminal_main.py`

### Function: `main()`
*   **Purpose**: The main entry point for the application.
*   **Logic**:
    1.  Sets up logging by calling `setup_logging()` from `logging_config.py`.
    2.  Parses command-line arguments: `--no-frontend`, `--config`, `--data`.
    3.  Initializes the `Config` object, loading a custom config if provided.
    4.  Loads initial data from a file (JSON or text) or uses a default if no file is provided.
    5.  If `--no-frontend` is specified, it logs that the terminal interface is not yet implemented.
    6.  If in GUI mode, it calls `hitl_node.hitl_node_run` to start the application, passing the loaded data and config path.
    7.  Logs the final data returned by the application upon session completion.

## `src/themule_atomic_hitl/terminal_interface.py`

### Class: `TerminalInterface`
*   **Purpose**: To provide a terminal-based interface for the Surgical Editor. (Note: Implementation is currently incomplete).
*   **Initialization (`__init__(self, initial_data: Dict[str, Any], config: Config)`)**:
    *   Initializes the `SurgicalEditorLogic` with terminal-specific callbacks.
*   **Key Methods**:
    *   `run(self) -> Dict[str, Any]`: Starts the main loop for the terminal interface.
    *   `on_update_view(...)`, `on_show_diff_preview(...)`, etc.: A suite of callback methods to handle updates from the `SurgicalEditorLogic` and display them in the terminal.

### Function: `run_terminal_interface(initial_data: Dict[str, Any], config: Config) -> Dict[str, Any]`
*   **Purpose**: Sets up and runs the terminal-based interface.

## `src/themule_atomic_hitl/logging_config.py`

### Function: `setup_logging()`
*   **Purpose**: Configures the root logger for the application.
*   **Logic**:
    1.  Gets the root logger and sets its level to `DEBUG`.
    2.  Removes any pre-existing handlers to ensure a clean setup.
    3.  Creates a `FileHandler` to write `DEBUG` level logs and higher to `app.log`. The log format is detailed, including timestamp, level, filename, and line number.
    4.  Creates a `StreamHandler` to write `INFO` level logs and higher to `sys.stdout`. The log format is simple, showing only the message.
    5.  Adds both handlers to the root logger.

## `src/themule_atomic_hitl/prompts/`
This directory contains the text files used as system prompts for the LLM. Externalizing prompts allows for easier modification without changing the Python code.
*   **`editor.txt`**: The system prompt for the "editor" task. It instructs the LLM to act as an editor, applying a directive as surgically as possible to a given text snippet.
*   **`locator.txt`**: The system prompt for the "locator" task. It instructs the LLM to act as a locator, finding specific sentences or paragraphs in a larger text based on a hint and returning them in a structured JSON format.
```

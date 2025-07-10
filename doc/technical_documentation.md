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
    *   `get_llm_config() -> Dict[str, Any]`: Returns the `llm_config` section of the configuration, falling back to the `llm_config` from `DEFAULT_CONFIG` if not present.
    *   `get_system_prompt(task_name: str) -> Optional[str]`: Retrieves a specific system prompt from `llm_config.system_prompts`.
*   **Key Properties**:
    *   `main_editor_original_field -> str`: Name of the data field for the original text in the main diff editor (from `fields` config). Defaults to `'originalText'`.
    *   `main_editor_modified_field -> str`: Name of the data field for the modified text in the main diff editor. Defaults to `'editedText'`.
    *   `window_title -> str`: The default window title from `settings.defaultWindowTitle`. Defaults to `"HITL Review Tool"`.

## `src/themule_atomic_hitl/core.py`

Contains the core business logic for the HITL editing process.

### Class: `SurgicalEditorLogic`

*   **Purpose**: Manages the state and lifecycle of edit requests, orchestrating LLM interactions and UI updates via callbacks.
*   **Initialization (`__init__(self, initial_data: Dict[str, Any], config: Config, callbacks: Dict[str, Callable])`)**:
    *   `initial_data`: The starting data for the editing session. A deep copy is stored in `_initial_data_snapshot` for revert functionality.
    *   `config`: An instance of `themule_atomic_hitl.config.Config`.
    *   `callbacks`: A dictionary of functions provided by the `Backend` (in `runner.py`) to communicate with the UI. Expected keys: `'update_view'`, `'show_error'`, `'confirm_location_details'`, `'show_diff_preview'`, `'request_clarification'`.
    *   Initializes `edit_request_queue` (a `collections.deque`) and `active_edit_task` (Optional[Dict]).
    *   Initializes `llm_service` (an instance of `LLMService`) using `config.get_llm_config()`. Handles potential errors during LLM service initialization.
    *   Ensures `initial_data` contains fields specified by `config.main_editor_original_field` and `config.main_editor_modified_field`.
*   **State Attributes**:
    *   `data: Dict[str, Any]`: The current, live data being edited.
    *   `_initial_data_snapshot: Dict[str, Any]`: A deep copy of the data passed during initialization, used for reverting changes.
    *   `edit_results: list`: A log of completed edit tasks and their outcomes.
    *   `edit_request_queue: deque[Tuple[str, str, str]]`: Stores pending edit requests as tuples of `(user_hint, user_instruction, content_snapshot_at_request_time)`.
    *   `active_edit_task: Optional[Dict[str, Any]]`: Holds details of the task currently being processed. Structure includes:
        *   `user_hint`, `user_instruction`, `original_content_snapshot`
        *   `status`: e.g., "locating_snippet", "awaiting_location_confirmation", "awaiting_diff_approval", "location_failed", "awaiting_clarification".
        *   `location_info`: Dict with `{'snippet', 'start_idx', 'end_idx'}` from locator.
        *   `llm_generated_snippet_details`: Dict with `{'start', 'end', 'original_snippet', 'edited_snippet'}`.
*   **Key Methods for Edit Lifecycle**:
    *   `start_session()`: Initializes the session, ensures original text fields are correctly set up for diffing, notifies the view, and attempts to process the first edit request.
    *   `add_edit_request(hint: str, instruction: str)`:
        *   Takes a snapshot of `self.current_main_content`.
        *   Appends `(hint, instruction, snapshot)` to `edit_request_queue`.
        *   Calls `_notify_view_update()` and `_process_next_edit_request()` if no task is active.
    *   `_process_next_edit_request()`:
        *   If no active task and queue is not empty, pops the next request.
        *   Sets up `self.active_edit_task` with status "locating_snippet".
        *   Calls `_notify_view_update()` and then `_execute_llm_attempt()`.
    *   `_execute_llm_attempt()`: (Gatekeeper Loop - Part 1)
        *   Uses `self._llm_locator()` with the task's `user_hint` and `original_content_snapshot`.
        *   If location successful:
            *   Updates `active_edit_task['location_info']` and status to "awaiting_location_confirmation".
            *   Calls `callbacks['confirm_location_details']` with location info, hint, and instruction.
        *   If location fails: Updates status to "location_failed".
    *   `proceed_with_edit_after_location_confirmation(confirmed_hint_or_location_details: Dict, original_instruction: str)`: (Worker Loop - Part 1)
        *   Called by UI after user confirms/corrects location.
        *   Validates `confirmed_hint_or_location_details`.
        *   Updates `active_edit_task['location_info']`.
        *   Calls `self._llm_editor()` with the confirmed snippet and `original_instruction`.
        *   Stores result in `active_edit_task['llm_generated_snippet_details']` and sets status to "awaiting_diff_approval".
        *   Calls `callbacks['show_diff_preview']` with original, edited snippets, and context.
    *   `process_llm_task_decision(decision: str, manually_edited_snippet: Optional[str] = None)`: (Worker Loop - Part 2)
        *   Handles user's decision ('approve', 'reject', 'cancel') on the LLM's suggestion.
        *   If 'approve':
            *   Uses `manually_edited_snippet` if provided, else `llm_generated_snippet_details['edited_snippet']`.
            *   Constructs the new content based on `active_edit_task['original_content_snapshot']` and the chosen snippet.
            *   **Critically, updates `self.current_main_content` with this new content.** This assumes a sequential processing model where the indices from the snapshot are applied to the snapshot's content, and this result becomes the new live content.
            *   Logs result, clears `active_edit_task`, calls `_notify_view_update()`, and `_process_next_edit_request()`.
        *   If 'reject': Sets status to "awaiting_clarification", calls `callbacks['request_clarification']`.
        *   If 'cancel': Logs result, clears `active_edit_task`, calls `_notify_view_update()`, and `_process_next_edit_request()`.
    *   `update_active_task_and_retry(new_hint: str, new_instruction: str)`:
        *   Called by UI after user provides clarification for a rejected task.
        *   Updates `active_edit_task`'s hint/instruction, resets status to "locating_snippet".
        *   Calls `_execute_llm_attempt()` to retry.
*   **LLM Interaction Methods**:
    *   `_llm_locator(text_to_search: str, hint: str) -> Optional[Dict[str, Any]]`:
        *   Uses `self.llm_service.invoke_llm()` with task "locator".
        *   User prompt combines `text_to_search` and `hint`, asking LLM to return the exact snippet.
        *   If successful, finds the returned snippet in `text_to_search` to get `start_idx`, `end_idx`. Includes a lenient regex fallback if exact match fails.
        *   Returns `{'start_idx', 'end_idx', 'snippet'}` or `None`.
    *   `_llm_editor(snippet_to_edit: str, instruction: str) -> str`:
        *   Uses `self.llm_service.invoke_llm()` with task "editor".
        *   User prompt combines `snippet_to_edit` and `instruction`, asking LLM to return only the modified snippet.
        *   Returns the edited snippet (stripped) or the original snippet on error/empty response.
*   **Generic Action Handling**:
    *   `perform_action(action_name: str, payload: Optional[Dict[str, Any]] = None)`:
        *   Dynamically calls handler methods like `handle_approve_main_content(payload)`.
        *   `handle_approve_main_content(payload)`: Updates `self.current_main_content` and other fields in `self.data` from the payload.
        *   `handle_revert_changes(payload)`: Resets `self.data` to `_initial_data_snapshot`, cancels active task, and clears `edit_request_queue`.
*   **UI Notification**:
    *   `_notify_view_update()`: Calls `callbacks['update_view']` with current `self.data`, `self.config_manager.get_config()`, and queue status information.
*   **Data Access**:
    *   `current_main_content` (property): Getter/setter for `self.data[self.main_text_field]`.
    *   `get_final_data() -> Dict[str, Any]`: Returns `self.data`.

## `src/themule_atomic_hitl/llm_service.py`

Handles all communication with Large Language Models.

### Class: `LLMService`

*   **Purpose**: To abstract LLM interactions, manage different providers, and handle API calls.
*   **Initialization (`__init__(self, llm_config: dict)`)**:
    *   `llm_config`: A dictionary (usually from `Config.get_llm_config()`) containing:
        *   `providers`: Configuration for each LLM provider (e.g., "google", "local") including model names, API key environment variable names, base URLs (for local), and temperature.
        *   `task_llms`: Mapping of task names (e.g., "locator", "editor") to provider names. Includes a "default" provider.
        *   `system_prompts`: Mapping of task names to default system prompt strings.
    *   Calls `_initialize_llms()`.
*   **Private Method (`_initialize_llms()`)**:
    *   Iterates through providers in `self.config['providers']`.
    *   **Google**: If "google" provider configured:
        *   Retrieves API key from environment variable specified in `api_key_env`.
        *   Initializes `self.google_llm = ChatGoogleGenerativeAI(...)` from `langchain_google_genai`.
    *   **Local (OpenAI-compatible)**: If "local" provider configured:
        *   Retrieves base URL from environment variable specified in `base_url_env`.
        *   Initializes `self.local_llm = ChatOpenAI(...)` from `langchain_openai`, setting `openai_api_base` and `openai_api_key` (can be dummy for some local LLMs).
    *   Handles and prints errors if initialization fails for any provider.
*   **Key Public Methods**:
    *   `get_llm_for_task(task_name: str)`:
        *   Determines which LLM client (`self.google_llm` or `self.local_llm`) to use based on `task_name` and the `task_llms` mapping in `self.config`.
        *   Falls back to the "default" provider if task-specific one is not available or configured.
        *   Ultimate fallback to any initialized LLM if the preferred default also fails.
        *   Raises `RuntimeError` if no LLM can be selected/initialized.
    *   `invoke_llm(task_name: str, user_prompt: str, system_prompt_override: Optional[str] = None) -> str`:
        *   Selects LLM using `get_llm_for_task(task_name)`.
        *   Determines system prompt: uses `system_prompt_override` if provided; otherwise, fetches from `self.config['system_prompts'][task_name]`; falls back to a generic "You are a helpful AI assistant." if none found.
        *   Constructs a list of messages: `[SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]` (from `langchain_core.messages`).
        *   Invokes the selected LLM with these messages (`llm.invoke(messages)`).
        *   Returns `response.content` (the string output from LLM).
        *   Raises exceptions on LLM API errors.

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
```

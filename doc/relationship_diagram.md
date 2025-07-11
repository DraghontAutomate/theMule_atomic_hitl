```markdown
# Repository File Relationship Diagram

This document outlines the relationships and dependencies between the Python files in the `themule_atomic_hitl` repository.

## Module Dependencies

Here's a breakdown of how the modules interact, primarily based on import statements:

**1. `src/themule_atomic_hitl/` (Core Package)**

*   **`__init__.py`** (Package Initializer)
    *   Acts as the public interface for the package.
    *   Imports:
        *   `run_application` from `.runner`
        *   `hitl_node_run` from `.hitl_node`
    *   Purpose: Makes key functionalities directly importable from `themule_atomic_hitl`.

*   **`config.py`** (Configuration Management)
    *   Imports:
        *   `json` (std)
        *   `os` (std)
        *   `typing` (std)
    *   Purpose: Manages default and custom configurations for the tool, including UI elements, LLM settings, and file paths.
    *   Used by: `core.py`, `hitl_node.py`, `runner.py`, `examples/run_tool.py`.

*   **`core.py`** (Core Logic Engine - `SurgicalEditorLogic`)
    *   Imports:
        *   `re`, `uuid`, `json`, `typing`, `collections.deque` (std)
        *   `.config.Config`
        *   `.llm_service.LLMService`
    *   Purpose: Contains the main business logic for the HITL tool, managing state, edit queues, and interactions with the LLM service. It's designed to be UI-agnostic.
    *   Used by: `runner.py` (instantiated by `Backend`).

*   **`hitl_node.py`** (Library Entry Point - `hitl_node_run`)
    *   Imports:
        *   `sys`, `typing` (std)
        *   `PyQt5.QtWidgets.QApplication` (external)
        *   `.config.Config`
        *   `.runner.run_application`
    *   Purpose: Provides a simplified function (`hitl_node_run`) to launch the HITL tool, making it easy to integrate as a library. It handles configuration loading and data preparation before calling `run_application`.
    *   Used by: `examples/run_tool.py`, and potentially external applications using this package.

*   **`llm_service.py`** (LLM Interaction)
    *   Imports:
        *   `os` (std)
        *   `dotenv.load_dotenv` (external)
        *   `langchain_google_genai.ChatGoogleGenerativeAI` (external)
        *   `langchain_openai.ChatOpenAI` (external)
        *   `langchain_core.messages.SystemMessage, HumanMessage` (external)
        *   `yaml` (external, but not actively used in current code)
    *   Purpose: Abstracts communication with Large Language Models (Google, local OpenAI-compatible). Handles API key management, model selection, and prompt formatting.
    *   Used by: `core.py`.

*   **`runner.py`** (Application Runner & PyQt Backend)
    *   Imports:
        *   `logging`, `sys`, `os`, `json`, `typing` (std)
        *   `PyQt5.QtCore`, `PyQt5.QtWidgets`, `PyQt5.QtWebEngineWidgets`, `PyQt5.QtWebChannel` (external)
        *   `.core.SurgicalEditorLogic`
        *   `.config.Config`
    *   Purpose: Sets up the PyQt5 application, main window, and the `QWebChannel` bridge (`Backend` class) between Python logic (`SurgicalEditorLogic`) and the JavaScript frontend (`frontend/index.html`, `frontend/frontend.js`). The `run_application` function is the main entry point here.
    *   Used by: `hitl_node.py`, `__init__.py`.

**2. `src/themule_atomic_hitl/frontend/` (User Interface)**

*   **`index.html`**: The main HTML structure for the web-based UI.
    *   Loads `frontend.js`.
    *   Interacts with the Python backend via the `QWebChannel` exposed by `runner.py`.
*   **`frontend.js`**: Contains the JavaScript logic for the UI.
    *   Handles user interactions, dynamic content updates, and communication with the Python `Backend` through the `qt.webChannelTransport`.

**3. `examples/` (Usage Examples)**

*   **`run_tool.py`** (Example Script)
    *   Imports:
        *   `faulthandler`, `sys`, `logging`, `os`, `json` (std)
        *   `src.themule_atomic_hitl.hitl_node_run` (project)
        *   `src.themule_atomic_hitl.runner._load_json_file` (project)
        *   `src.themule_atomic_hitl.config.Config` (project)
    *   Purpose: Demonstrates how to use `hitl_node_run` with various configurations (string input, dictionary input, custom config file).
    *   Relies on: `hitl_node.py` and indirectly all other core modules.

*   **`config.json`** (Example Custom Configuration)
    *   A JSON file providing a sample custom configuration for the HITL tool.
    *   Used by: `examples/run_tool.py` (as an argument to `hitl_node_run`).

*   **`sample_data.json`** (Example Data)
    *   A JSON file providing sample input data for the HITL tool.
    *   Used by: `examples/run_tool.py` (as an argument to `hitl_node_run`).

## High-Level Flow

1.  An external script (like `examples/run_tool.py`) or application calls `hitl_node_run` from `hitl_node.py`.
2.  `hitl_node.py` initializes `Config` (from `config.py`) and prepares data.
3.  `hitl_node.py` calls `run_application` from `runner.py`.
4.  `runner.py`:
    *   Sets up the `QApplication`.
    *   Creates `MainWindow` which hosts `QWebEngineView`.
    *   Instantiates `Backend`. The `Backend` initializes `SurgicalEditorLogic` (from `core.py`).
    *   `SurgicalEditorLogic` initializes `LLMService` (from `llm_service.py`) if LLM features are configured.
    *   `Backend` sets up the `QWebChannel` to communicate with `frontend.js`.
    *   Loads `frontend/index.html` into the `QWebEngineView`.
5.  `frontend/index.html` and `frontend/frontend.js` render the UI and communicate with `Backend` for actions and data updates.
6.  `Backend` delegates calls to `SurgicalEditorLogic`, which performs operations (potentially using `LLMService`) and uses callbacks to update `Backend`.
7.  `Backend` emits signals that `frontend.js` listens to, updating the UI.

## Visual Representation (Textual Hierarchy)

```
(Entry Point, e.g., examples/run_tool.py)
  └── calls src.themule_atomic_hitl.hitl_node_run
      └── src.themule_atomic_hitl.hitl_node.py (hitl_node_run)
          ├── Uses src.themule_atomic_hitl.config.Config
          └── Calls src.themule_atomic_hitl.runner.run_application
              └── src.themule_atomic_hitl.runner.py (run_application, Backend, MainWindow)
                  ├── Uses src.themule_atomic_hitl.config.Config
                  ├── Instantiates Backend
                  │   └── Instantiates src.themule_atomic_hitl.core.SurgicalEditorLogic
                  │       ├── Uses src.themule_atomic_hitl.config.Config
                  │       └── Instantiates src.themule_atomic_hitl.llm_service.LLMService
                  │           └── (Interacts with LLM APIs: Google, OpenAI-compatible)
                  ├── Loads src.themule_atomic_hitl.frontend/index.html
                  │   └── Loads src.themule_atomic_hitl.frontend/frontend.js
                  └── (PyQt5 components for UI and WebChannel)

src.themule_atomic_hitl.__init__.py
  ├── Imports from .runner
  └── Imports from .hitl_node
```

This textual representation should give a good overview of the module relationships and data flow within the repository.
```

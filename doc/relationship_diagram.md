```markdown
# Repository File Relationship Diagram

This document outlines the relationships and dependencies between the Python files in the `themule_atomic_hitl` repository.

## Module Dependencies

Here's a breakdown of how the modules interact, primarily based on import statements:

**1. `src/themule_atomic_hitl/` (Core Package)**

*   **`__init__.py`** (Package Initializer)
    *   Acts as the public interface for the package.
    *   Imports:
        *   `hitl_node_run` from `.hitl_node`
    *   Purpose: Makes key functionalities directly importable from `themule_atomic_hitl`.

*   **`config.py`** (Configuration Management)
    *   Imports: `json`, `os`, `typing` (std)
    *   Purpose: Manages default and custom configurations for the tool, including UI elements, LLM settings (providers, prompts, schemas), and file paths.
    *   Used by: `core.py`, `hitl_node.py`, `runner.py`, `terminal_main.py`.

*   **`core.py`** (Core Logic Engine - `SurgicalEditorLogic`)
    *   Imports: `re`, `uuid`, `json`, `typing`, `collections.deque` (std), `.config.Config`, `.llm_service.LLMService`
    *   Purpose: Contains the main business logic for the HITL tool, managing state, edit queues (for hint-based and selection-specific requests), and interactions with the LLM service. It's designed to be UI-agnostic.
    *   Used by: `runner.py` (instantiated by `Backend`), `terminal_interface.py`.

*   **`hitl_node.py`** (Library Entry Point - `hitl_node_run`)
    *   Imports: `sys`, `typing` (std), `PyQt5.QtWidgets` (external), `.config.Config`, `.runner.run_application`
    *   Purpose: Provides a simplified function (`hitl_node_run`) to launch the HITL tool, making it easy to integrate as a library. It handles configuration loading and data preparation.
    *   Used by: `terminal_main.py`, `examples/run_tool.py`.

*   **`llm_service.py`** (LLM Interaction)
    *   Imports: `os`, `typing` (std), `dotenv` (external), `langchain` libraries (external), `jsonschema_pydantic` (external).
    *   Purpose: Abstracts communication with Large Language Models (Google, local OpenAI-compatible). Handles API key management, model selection, structured output generation, and prompt formatting.
    *   Used by: `core.py`.

*   **`logging_config.py`** (Logging Setup)
    *   Imports: `logging`, `sys` (std).
    *   Purpose: Provides a `setup_logging` function to configure file and stream handlers for the application.
    *   Used by: `terminal_main.py`.

*   **`runner.py`** (Application Runner & PyQt Backend)
    *   Imports: `logging`, `sys`, `os`, `json`, `typing` (std), `PyQt5` libraries (external), `.core.SurgicalEditorLogic`, `.config.Config`.
    *   Purpose: Sets up the PyQt5 application, main window, and the `QWebChannel` bridge (`Backend` class) between Python logic (`SurgicalEditorLogic`) and the JavaScript frontend.
    *   Used by: `hitl_node.py`.

*   **`terminal_interface.py`** (Terminal UI)
    *   Imports: `typing` (std), `.core.SurgicalEditorLogic`, `.config.Config`.
    *   Purpose: Provides a (currently incomplete) terminal-based user interface for the tool.
    *   Used by: Potentially `terminal_main.py` in the future.

*   **`terminal_main.py`** (Main Entry Point)
    *   Imports: `argparse`, `logging`, `os`, `sys`, `json` (std), `.config.Config`, `.hitl_node.hitl_node_run`, `.logging_config`.
    *   Purpose: The primary executable for the application. Parses command-line arguments to launch the GUI or terminal mode.
    *   Used by: Users running the application from the command line.

**2. `src/themule_atomic_hitl/prompts/` (LLM System Prompts)**

*   Contains `.txt` files that serve as the system prompts for different LLM tasks (e.g., `editor.txt`, `locator.txt`).
*   Read by: `config.py` when `get_system_prompt()` is called.

**3. `src/themule_atomic_hitl/frontend/` (User Interface)**

*   **`index.html`**: The main HTML structure for the web-based UI.
    *   Loads `frontend.js`.
    *   Interacts with the Python backend via the `QWebChannel` exposed by `runner.py`.
*   **`frontend.js`**: Contains the JavaScript logic for the UI.
    *   Handles user interactions, dynamic content updates, and communication with the Python `Backend` through the `qt.webChannelTransport`.

**3. `examples/` (Usage Examples)**

*   **`run_tool.py`** (Example Script)
    *   Imports: `sys`, `os`, `json` (std), `src.themule_atomic_hitl.hitl_node_run` (project).
    *   Purpose: Demonstrates how to use `hitl_node_run` with various configurations (string input, dictionary input, custom config file).
    *   Relies on: `hitl_node.py` and indirectly all other core modules.

*   **`config.json`** (Example Custom Configuration)
    *   A JSON file providing a sample custom configuration for the HITL tool.
    *   Used by: `examples/run_tool.py` (as an argument to `hitl_node_run`).

*   **`sample_data.json`** (Example Data)
    *   A JSON file providing sample input data for the HITL tool.
    *   Used by: `examples/run_tool.py` (as an argument to `hitl_node_run`).

## High-Level Flow

1.  A user runs `terminal_main.py`.
2.  `terminal_main.py` parses arguments, sets up logging (`logging_config.py`), and loads data. It then calls `hitl_node.hitl_node_run`.
3.  `hitl_node.py` initializes `Config` (from `config.py`) and prepares data.
4.  `hitl_node.py` calls `run_application` from `runner.py`.
5.  `runner.py`:
    *   Sets up the `QApplication`.
    *   Creates `MainWindow` which hosts `QWebEngineView`.
    *   Instantiates `Backend`. The `Backend` initializes `SurgicalEditorLogic` (from `core.py`).
    *   `SurgicalEditorLogic` initializes `LLMService` (from `llm_service.py`). `LLMService` uses `config.py` to get provider details and prompt paths.
    *   `Backend` sets up the `QWebChannel` to communicate with `frontend.js`.
    *   Loads `frontend/index.html` into the `QWebEngineView`.
6.  `frontend.js` communicates with `Backend` for actions and data updates.
7.  `Backend` delegates calls to `SurgicalEditorLogic`, which performs operations (using `LLMService`) and uses callbacks to update `Backend`.
8.  `Backend` emits signals that `frontend.js` listens to, updating the UI.

## Visual Representation (Textual Hierarchy)

```
(Entry Point: src/themule_atomic_hitl/terminal_main.py)
  ├── Uses src.themule_atomic_hitl.logging_config.py (to setup logging)
  └── Calls src.themule_atomic_hitl.hitl_node.hitl_node_run
      └── src.themule_atomic_hitl.hitl_node.py (hitl_node_run)
          ├── Uses src.themule_atomic_hitl.config.Config
          └── Calls src.themule_atomic_hitl.runner.run_application
              └── src.themule_atomic_hitl.runner.py (run_application, Backend, MainWindow)
                  ├── Uses src.themule_atomic_hitl.config.Config
                  ├── Instantiates Backend
                  │   └── Instantiates src.themule_atomic_hitl.core.SurgicalEditorLogic
                  │       ├── Uses src.themule_atomic_hitl.config.Config
                  │       └── Instantiates src.themule_atomic_hitl.llm_service.LLMService
                  │           ├── Uses src.themule_atomic_hitl.config.Config (to get prompt paths)
                  │           │   └── Reads files from src/themule_atomic_hitl/prompts/
                  │           └── (Interacts with LLM APIs: Google, OpenAI-compatible)
                  ├── Loads src.themule_atomic_hitl.frontend/index.html
                  │   └── Loads src.themule_atomic_hitl.frontend/frontend.js
                  └── (PyQt5 components for UI and WebChannel)

src.themule_atomic_hitl.__init__.py
  └── Imports from .hitl_node

(Separate Utility: src/llm_prompt_tool/)
```

This textual representation should give a good overview of the module relationships and data flow within the repository.

**4. `examples/` (Usage Examples)**

*   **`run_tool.py`**: Example script demonstrating library usage of `hitl_node_run`.

**5. `src/llm_prompt_tool/` (LLM Prompt Refinement Tool)**

*   **`main_loop.py`** (Main Orchestrator): Runs the main prompt refinement loop.
*   **`llm_tester.py`** (LLM Interface): Provides a mock or real interface to an LLM.
*   **`evaluator.py`** (Response Evaluator): Evaluates LLM responses based on defined criteria.
```

.
├── .env.example
├── .gitignore
├── LICENSE
├── MANIFEST.in
├── README.md
├── doc
│   ├── functional_documentation.md
│   ├── llm_prompt_tool_description.md
│   ├── relationship_diagram.md
│   └── technical_documentation.md
├── examples
│   ├── __init__.py
│   ├── config.json
│   ├── run_tool.py
│   └── sample_data.json
├── missing_test_enhancements.txt
├── pre-push-hook.sh
├── requirements.txt
├── run_tests.py
├── setup.py
├── src
│   ├── llm_prompt_tool
│   │   ├── README.md
│   │   ├── evaluator.py
│   │   ├── llm_tester.py
│   │   └── main_loop.py
│   └── themule_atomic_hitl
│       ├── __init__.py
│       ├── config.py
│       ├── core.py
│       ├── frontend
│       │   ├── css
│       │   │   └── reset.css
│       │   ├── frontend.js
│       │   └── index.html
│       ├── hitl_node.py
│       ├── llm_service.py
│       ├── main.py
│       └── runner.py
│       └── terminal_interface.py
└── tests
    ├── asimov_mule_analysis.txt
    ├── bruce_lee_zend_martial_arts.txt
    ├── run_test_return_report.py
    ├── test_config.py
    ├── test_core_logic.py
    ├── test_hitl_node.py
    └── test_llm_prompt_tool.py

# File Descriptions

*   **.env.example**: Example environment file for setting API keys and other secrets.
*   **.gitignore**: A list of files and directories for Git to ignore.
*   **LICENSE**: The license for the project.
*   **MANIFEST.in**: A file that specifies which files to include in a source distribution.
*   **README.md**: The main README file for the project.
*   **doc/**: A directory containing the project's documentation.
    *   `functional_documentation.md`: Provides a high-level functional overview of all the modules in the repository.
    *   `llm_prompt_tool_description.md`: Provides a detailed description of the `llm_prompt_tool`.
    *   `relationship_diagram.md`: Outlines the relationships and dependencies between all the Python files in the repository.
    *   `technical_documentation.md`: Provides a detailed technical breakdown of all the modules, classes, and functions in the repository.
*   **examples/**: A directory containing examples of how to use the tool.
    *   `__init__.py`: Makes the `examples` directory a Python package.
    *   `config.json`: An example configuration file for the `themule_atomic_hitl` tool.
    *   `run_tool.py`: An example script for running the `themule_atomic_hitl` tool.
    *   `sample_data.json`: Example data for the `themule_atomic_hitl` tool.
*   **missing_test_enhancements.txt**: A file that lists missing test enhancements.
*   **pre-push-hook.sh**: A pre-push hook script to run tests before pushing to the repository.
*   **requirements.txt**: A list of the Python packages required to run the project.
*   **run_tests.py**: A script for running the project's tests.
*   **setup.py**: A script for packaging and distributing the project.
*   **src/**: A directory containing the project's source code.
    *   `llm_prompt_tool/`: A directory containing the `llm_prompt_tool`.
        *   `README.md`: The README file for the `llm_prompt_tool`.
        *   `evaluator.py`: A module for evaluating LLM responses.
        *   `llm_tester.py`: A module for interacting with an LLM.
        *   `main_loop.py`: The main script for the `llm_prompt_tool`.
    *   `themule_atomic_hitl/`: A directory containing the `themule_atomic_hitl` tool.
        *   `__init__.py`: Makes the `themule_atomic_hitl` directory a Python package.
        *   `config.py`: A module for managing the tool's configuration.
        *   `core.py`: The core logic of the tool.
        *   `frontend/`: A directory containing the tool's frontend code.
            *   `css/`: A directory containing the tool's CSS files.
                *   `reset.css`: The main CSS file for the tool.
            *   `frontend.js`: The main JavaScript file for the tool.
            *   `index.html`: The main HTML file for the tool.
        *   `hitl_node.py`: A module for running the tool as a library.
        *   `llm_service.py`: A module for interacting with an LLM.
        *   `main.py`: The main entry point for the application.
        *   `runner.py`: A module for running the tool's GUI.
        *   `terminal_interface.py`: A module for running the tool's terminal interface.
*   **tests/**: A directory containing the project's tests.
    *   `asimov_mule_analysis.txt`: A text file for testing.
    *   `bruce_lee_zend_martial_arts.txt`: A text file for testing.
    *   `run_test_return_report.py`: A script for running the tests and returning a report.
    *   `test_config.py`: Tests for the `config.py` module.
    *   `test_core_logic.py`: Tests for the `core.py` module.
    *   `test_hitl_node.py`: Tests for the `hitl_node.py` module.
    *   `test_llm_prompt_tool.py`: Tests for the `llm_prompt_tool`.

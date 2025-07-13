# Makefile for TheMule Atomic HITL Surgical Editor

# Default python interpreter
PYTHON = python3

# Path to the main application script
MAIN_SCRIPT = src/themule_atomic_hitl/main.py

# Default paths for data and config files (using examples)
DEFAULT_DATA = examples/sample_data.json
DEFAULT_CONFIG = examples/config.json

# --- Primary Targets ---

.PHONY: help run-gui run-terminal install test

help:
	@echo "Makefile for TheMule Atomic HITL Surgical Editor"
	@echo ""
	@echo "Usage:"
	@echo "  make install         - Install required Python packages from requirements.txt"
	@echo "  make run-gui         - Run the application with the GUI frontend"
	@echo "  make run-terminal    - Run the application with the terminal interface"
	@echo "  make test            - Run the test suite"
	@echo ""
	@echo "You can also customize the run commands with DATA and CONFIG variables:"
	@echo "  make run-gui DATA=path/to/data.json CONFIG=path/to/config.json"
	@echo ""

# Target to run the application with the GUI
run-gui:
	@echo "Starting application in GUI mode..."
	$(PYTHON) $(MAIN_SCRIPT) --data $(or $(DATA),$(DEFAULT_DATA)) --config $(or $(CONFIG),$(DEFAULT_CONFIG))

# Target to run the application in terminal-only mode
run-terminal:
	@echo "Starting application in Terminal mode..."
	$(PYTHON) $(MAIN_SCRIPT) --no-frontend --data $(or $(DATA),$(DEFAULT_DATA)) --config $(or $(CONFIG),$(DEFAULT_CONFIG))

# Target to install dependencies
install:
	@echo "Installing dependencies from requirements.txt..."
	pip install -r requirements.txt

# Target to run tests (assuming a script or command to run tests)
test:
	@echo "Running tests..."
	$(PYTHON) -m pytest

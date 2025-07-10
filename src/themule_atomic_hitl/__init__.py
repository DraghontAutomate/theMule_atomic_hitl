# src/themule_atomic_hitl/__init__.py

"""
This file serves as the entry point for the themule_atomic_hitl package.

It makes the main application runner function and the HITL node function
available for import when the package is imported, and also defines the package version.
"""

# Import key functions to make them accessible at the package level.
from .runner import run_application
from .hitl_node import hitl_node_run

# Optional: define __version__
# Specifies the version of the package. This is useful for package management and distribution.
__version__ = "0.1.0"

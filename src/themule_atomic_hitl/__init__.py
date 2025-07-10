# src/themule_atomic_hitl/__init__.py

"""
This file serves as the entry point for the themule_atomic_hitl package.

It makes the main application runner function available for import when the package is imported,
and also defines the package version.
"""

# Import the main application runner function to make it accessible at the package level.
# This allows users to run the application using `from themule_atomic_hitl import run_application`.
from .runner import run_application

# Optional: define __version__
# Specifies the version of the package. This is useful for package management and distribution.
__version__ = "0.1.0"

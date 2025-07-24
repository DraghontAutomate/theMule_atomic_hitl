"""
Public package interface for themule_atomic_hitl.

This module exposes the main entry points without importing heavy Qt
modules at import time. Functions are imported lazily when accessed so
that environments without Qt can still import the package for testing.
"""

__all__ = ["run_application", "hitl_node_run", "__version__"]

__version__ = "0.1.0"


def __getattr__(name):
    import importlib, sys

    if name == "run_application":
        from .runner import run_application
        return run_application
    if name == "hitl_node_run":
        from .hitl_node import hitl_node_run
        return hitl_node_run
    if name in {"runner", "hitl_node"}:
        if f"{__name__}.{name}" in sys.modules:
            return sys.modules[f"{__name__}.{name}"]
        import types
        stub = types.ModuleType(f"{__name__}.{name}")
        # Provide placeholders so unit tests can patch attributes on this stub
        stub.QApplication = None
        stub.QMainWindow = None
        stub.QEventLoop = None
        stub.run_application = None
        setattr(sys.modules[__name__], name, stub)
        sys.modules[f"{__name__}.{name}"] = stub
        return stub
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

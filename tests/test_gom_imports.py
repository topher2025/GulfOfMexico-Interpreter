"""Import tests for the gom package modules.

All modules under gom/ are currently stubs (empty files).  These tests verify
that every module can be imported without raising an exception, and that the
package itself is importable.  They serve as a baseline so any future
implementation additions are automatically included in coverage runs.
"""

import importlib
import sys
import os

# Ensure the repo root is on the path so ``gom`` is importable as a package.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


GOM_MODULES = [
    "gom.lexer",
    "gom.parser",
    "gom.nodes",
    "gom.executor",
    "gom.environment",
    "gom.io",
    "gom.ai",
]


def test_gom_package_importable():
    """The top-level ``gom`` package is importable."""
    import gom  # noqa: F401


class TestGomModuleImports:
    """Each module inside gom/ can be imported without errors."""

    def test_lexer_importable(self):
        importlib.import_module("gom.lexer")

    def test_parser_importable(self):
        importlib.import_module("gom.parser")

    def test_nodes_importable(self):
        importlib.import_module("gom.nodes")

    def test_executor_importable(self):
        importlib.import_module("gom.executor")

    def test_environment_importable(self):
        importlib.import_module("gom.environment")

    def test_io_importable(self):
        importlib.import_module("gom.io")

    def test_ai_importable(self):
        importlib.import_module("gom.ai")

    def test_all_modules_importable(self):
        """Parametric-style check: every declared module imports cleanly."""
        for module_name in GOM_MODULES:
            mod = importlib.import_module(module_name)
            assert mod is not None, f"Module {module_name!r} imported as None"

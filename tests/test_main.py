"""Tests for main.py arg_parser()."""

import os
import sys
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from main import arg_parser


def _parse(argv, capsys):
    """Helper: set sys.argv, call arg_parser(), return args and stdout."""
    sys.argv = ["gom"] + argv
    args = arg_parser()
    captured = capsys.readouterr()
    return args, captured.out


# ---------------------------------------------------------------------------
# run subcommand
# ---------------------------------------------------------------------------

class TestRunSubcommand:
    def test_run_basic(self, capsys):
        args, _ = _parse(["run", "hello.gom"], capsys)
        assert args.command == "run"
        assert args.file == "hello.gom"

    def test_run_dump_env(self, capsys):
        args, _ = _parse(["run", "hello.gom", "--dump-env"], capsys)
        assert args.dump_env is True

    def test_run_dump_env_defaults_false(self, capsys):
        args, _ = _parse(["run", "hello.gom"], capsys)
        assert args.dump_env is False

    def test_run_verbose_short(self, capsys):
        args, _ = _parse(["run", "-v", "hello.gom"], capsys)
        assert args.verbose == 1

    def test_run_verbose_long(self, capsys):
        args, _ = _parse(["run", "--verbose", "hello.gom"], capsys)
        assert args.verbose == 1

    def test_run_verbose_stacked(self, capsys):
        args, _ = _parse(["run", "-v", "-v", "-v", "hello.gom"], capsys)
        assert args.verbose == 3

    def test_run_verbose_default_zero(self, capsys):
        args, _ = _parse(["run", "hello.gom"], capsys)
        assert args.verbose == 0

    def test_run_debug(self, capsys):
        args, _ = _parse(["run", "--debug", "hello.gom"], capsys)
        assert args.debug is True

    def test_run_debug_default_false(self, capsys):
        args, _ = _parse(["run", "hello.gom"], capsys)
        assert args.debug is False

    def test_run_trace(self, capsys):
        args, _ = _parse(["run", "--trace", "hello.gom"], capsys)
        assert args.trace is True

    def test_run_trace_default_false(self, capsys):
        args, _ = _parse(["run", "hello.gom"], capsys)
        assert args.trace is False

    def test_run_all_flags(self, capsys):
        args, _ = _parse(["run", "-v", "--debug", "--trace", "--dump-env", "prog.gom"], capsys)
        assert args.command == "run"
        assert args.file == "prog.gom"
        assert args.verbose == 1
        assert args.debug is True
        assert args.trace is True
        assert args.dump_env is True

    def test_run_prints_args(self, capsys):
        _, out = _parse(["run", "hello.gom"], capsys)
        # arg_parser() prints the Namespace; verify output is non-empty and
        # contains the file argument.
        assert "hello.gom" in out

    def test_run_returns_namespace(self, capsys):
        import argparse
        args, _ = _parse(["run", "hello.gom"], capsys)
        assert isinstance(args, argparse.Namespace)


# ---------------------------------------------------------------------------
# compile subcommand
# ---------------------------------------------------------------------------

class TestCompileSubcommand:
    def test_compile_basic(self, capsys):
        args, _ = _parse(["compile", "prog.gom"], capsys)
        assert args.command == "compile"
        assert args.file == "prog.gom"

    def test_compile_output_short(self, capsys):
        args, _ = _parse(["compile", "prog.gom", "-o", "out.cdb"], capsys)
        assert args.output == "out.cdb"

    def test_compile_output_long(self, capsys):
        args, _ = _parse(["compile", "prog.gom", "--output", "result.cdb"], capsys)
        assert args.output == "result.cdb"

    def test_compile_output_default_none(self, capsys):
        args, _ = _parse(["compile", "prog.gom"], capsys)
        assert args.output is None

    def test_compile_verbose(self, capsys):
        args, _ = _parse(["compile", "-v", "prog.gom"], capsys)
        assert args.verbose == 1

    def test_compile_debug(self, capsys):
        args, _ = _parse(["compile", "--debug", "prog.gom"], capsys)
        assert args.debug is True

    def test_compile_trace(self, capsys):
        args, _ = _parse(["compile", "--trace", "prog.gom"], capsys)
        assert args.trace is True

    def test_compile_all_flags(self, capsys):
        args, _ = _parse(
            ["compile", "-v", "--debug", "--trace", "-o", "out.cdb", "prog.gom"], capsys
        )
        assert args.command == "compile"
        assert args.file == "prog.gom"
        assert args.output == "out.cdb"
        assert args.verbose == 1
        assert args.debug is True
        assert args.trace is True


# ---------------------------------------------------------------------------
# cdb-check subcommand
# ---------------------------------------------------------------------------

class TestCdbCheckSubcommand:
    def test_cdb_check_basic(self, capsys):
        args, _ = _parse(["cdb-check", "archive.cdb"], capsys)
        assert args.command == "cdb-check"
        assert args.file == "archive.cdb"

    def test_cdb_check_verbose(self, capsys):
        args, _ = _parse(["cdb-check", "-v", "archive.cdb"], capsys)
        assert args.verbose == 1

    def test_cdb_check_debug(self, capsys):
        args, _ = _parse(["cdb-check", "--debug", "archive.cdb"], capsys)
        assert args.debug is True

    def test_cdb_check_trace(self, capsys):
        args, _ = _parse(["cdb-check", "--trace", "archive.cdb"], capsys)
        assert args.trace is True

    def test_cdb_check_all_flags(self, capsys):
        args, _ = _parse(["cdb-check", "-v", "--debug", "--trace", "archive.cdb"], capsys)
        assert args.command == "cdb-check"
        assert args.file == "archive.cdb"
        assert args.verbose == 1
        assert args.debug is True
        assert args.trace is True


# ---------------------------------------------------------------------------
# No subcommand / top-level
# ---------------------------------------------------------------------------

class TestNoSubcommand:
    def test_no_args_returns_none_command(self, capsys):
        args, _ = _parse([], capsys)
        assert args.command is None

    def test_version_exits(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            sys.argv = ["gom", "--version"]
            arg_parser()
        assert exc_info.value.code == 0

    def test_unknown_subcommand_exits(self, capsys):
        with pytest.raises(SystemExit):
            sys.argv = ["gom", "notacommand"]
            arg_parser()

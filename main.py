#!/usr/bin/env python3

import argparse
from pathlib import Path


def arg_parser():
    import argparse

    # ------------------------------
    # Parent parser: global arguments
    # ------------------------------
    global_parser = argparse.ArgumentParser(add_help=False)
    global_parser.add_argument(
        "-v", "--verbose", action="count", default=0, help="Increase verbosity"
    )
    global_parser.add_argument(
        "--debug", action="store_true", help="Enable debug mode"
    )
    global_parser.add_argument(
        "--trace", action="store_true", help="Show step-by-step execution"
    )

    # ------------------------------
    # Main parser
    # ------------------------------
    parser = argparse.ArgumentParser(
        prog="gom",
        description="Gulf of Mexico Interpreter",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0",
        help="Show program version"
    )

    subparsers = parser.add_subparsers(dest="command")  # not required for global flags

    # ------------------------------
    # Subcommand: run
    # ------------------------------
    run_parser = subparsers.add_parser(
        "run",
        parents=[global_parser],
        help="Run a .gom file"
    )
    run_parser.add_argument("file", help="The .gom file to run")
    run_parser.add_argument(
        "--dump-env",
        action="store_true",
        help="Show all variables at the end of execution"
    )

    # ------------------------------
    # Subcommand: compile
    # ------------------------------
    compile_parser = subparsers.add_parser(
        "compile",
        parents=[global_parser],
        help="Compile to .cdb (legacy Dream Bird format)"
    )
    compile_parser.add_argument("file", help="The .gom file to compile")
    compile_parser.add_argument(
        "-o", "--output", default=None, help="Output file (.cdb)"
    )

    # ------------------------------
    # Subcommand: cdb-check
    # ------------------------------
    cdb_check_parser = subparsers.add_parser(
        "cdb-check",
        parents=[global_parser],
        help="Inspect legacy .cdb files"
    )
    cdb_check_parser.add_argument("file", help=".cdb file to inspect")


    # ------------------------------
    # Parse arguments
    # ------------------------------
    args = parser.parse_args()
    print(args)
    return args



if __name__ == '__main__':
    args = arg_parser()
    print(args)



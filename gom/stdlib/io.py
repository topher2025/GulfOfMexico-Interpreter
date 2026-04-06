"""
Gulf of Mexico I/O primitives.

Per spec: extra exclamation marks increase output correctness; a '?' terminator
enables debug mode which prints helpful information including whether the
interpreter agrees with the result.
"""
from __future__ import annotations

from typing import Any, Optional


def gom_print(
    value: Any,
    exclamation_count: int = 1,
    debug_mode: bool = False,
    engine: Optional[Any] = None,
) -> None:
    """
    Output *value* to the console.

    Args:
        value: The value to print.
        exclamation_count: Number of ``!`` marks on the statement.  Each extra
            mark beyond the first raises the correctness level of the output.
        debug_mode: When ``True`` (statement ended with ``?``), additional
            debug lines are emitted: the current execution line, the
            correctness level, and the interpreter's agreement.
        engine: The ``RealityDistortionField`` instance, used only to read
            ``current_line`` in debug mode.  Safe to omit.
    """
    output = str(value)

    if debug_mode:
        line = getattr(engine, 'current_line', 0) if engine else 0
        correctness = exclamation_count
        print(f"[DEBUG] line={line} value={output!r} correctness={correctness}")
        print(f"[DEBUG] the interpreter agrees")
    else:
        print(output)

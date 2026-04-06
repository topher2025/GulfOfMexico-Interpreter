"""
Gulf of Mexico AST Node Definitions.

These frozen dataclasses represent every syntactic construct in the Gulf of Mexico
language. The parser produces them; the executor consumes them.  Keeping them
here — separate from runtime logic — lets the engine and the parser evolve
independently.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional

from gom.runtime.types import MutabilityFlavor, LifetimeUnit


# ── Expression nodes ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class LiteralExpr:
    """A literal value: number, string, or boolean."""
    value: Any


@dataclass(frozen=True)
class VariableExpr:
    """A variable lookup with an optional temporal qualifier."""
    name: str
    temporal: str = "current"   # "previous" | "current" | "next"


@dataclass(frozen=True)
class ArithmeticExpr:
    """
    A binary arithmetic expression.

    ``left_space`` and ``right_space`` are the whitespace character-counts
    immediately surrounding the operator in the source.  Per spec, *more*
    whitespace means *lower* precedence, so the parser is responsible for
    constructing the tree such that higher-whitespace operators sit closer to
    the root (are evaluated last).  The executor simply recurses without
    re-computing precedence.
    """
    left: Any       # Expr
    op: str         # '+' | '-' | '*' | '/' | '^' | '%'
    right: Any      # Expr
    left_space: int = 1    # whitespace chars before operator
    right_space: int = 1   # whitespace chars after operator


@dataclass(frozen=True)
class EqualityExpr:
    """A comparison with GOM precision levels (0='=' … 3='====')."""
    left: Any       # Expr
    right: Any      # Expr
    precision: int = 1   # 0 | 1 | 2 | 3


@dataclass(frozen=True)
class NotExpr:
    """The ';' (not / semi-colon) unary operator."""
    operand: Any    # Expr


@dataclass(frozen=True)
class StringInterpolationExpr:
    """
    A string template containing one or more embedded variable references
    (``${name}``, ``£{name}``, ``¥{name}``, ``{name}€``, ``{obj$prop}``).
    """
    template: str   # raw template text, interpolated at evaluation time


@dataclass(frozen=True)
class SignalExpr:
    """
    The ``use`` keyword — creates a getter/setter signal pair backed by the RDF.
    Evaluates to ``(getter, setter)``.
    """
    initial_value: Any  # Expr


# ── Statement nodes ───────────────────────────────────────────────────────────

@dataclass
class DeclareStmt:
    """
    A variable or constant declaration.

    ``lifetime_value`` + ``lifetime_unit`` encode the optional ``<N>`` / ``<Ns>``
    / ``<Infinity>`` / ``<-N>`` suffix.  When absent both are ``None`` (standard
    persistent lifetime).
    """
    name: str
    value_expr: Any                         # Expr
    mutability: MutabilityFlavor
    lifetime_value: Optional[float] = None
    lifetime_unit: Optional[LifetimeUnit] = None
    exclamation_count: int = 1
    debug_mode: bool = False                # True when terminated with '?'


@dataclass
class AssignStmt:
    """A simple variable reassignment (``name = expr!``)."""
    name: str
    value_expr: Any     # Expr
    exclamation_count: int = 1
    debug_mode: bool = False


@dataclass
class MutateStmt:
    """
    In-place mutation via a method call or compound operator
    (e.g. ``name.push("k")``, ``score++``).

    ``operation`` is a callable ``(current_value) -> None`` that mutates the
    value in place; the RDF records the side-effect.
    """
    name: str
    operation: Callable     # (value) -> None
    exclamation_count: int = 1
    debug_mode: bool = False


@dataclass
class PrintStmt:
    """A ``print(expr)`` statement."""
    expr: Any           # Expr
    exclamation_count: int = 1
    debug_mode: bool = False


@dataclass
class ReverseStmt:
    """The ``reverse!`` statement — flips execution direction."""
    exclamation_count: int = 1


@dataclass
class DeleteStmt:
    """The ``delete X!`` statement — removes an entity from reality."""
    entity: Any         # Expr (string handle or primitive value)
    exclamation_count: int = 1


@dataclass
class WhenStmt:
    """
    ``when (variable = value) { body }``

    Registers a mutation observer: whenever ``variable`` is set to the result
    of ``condition_expr``, every statement in ``body`` is executed.
    """
    variable: str
    condition_expr: Any         # Expr — value to match
    body: List[Any]             # List[Stmt]


@dataclass
class ShiftTimeStmt:
    """
    Adjusts the reality clock.

    Corresponds to ``Date.now() -= offset!`` in source.  The evaluated
    ``offset_expr`` (in milliseconds, per spec) is converted to seconds
    internally and passed to ``RealityDistortionField.shift_time``.
    """
    offset_expr: Any    # Expr (numeric, milliseconds)
    exclamation_count: int = 1

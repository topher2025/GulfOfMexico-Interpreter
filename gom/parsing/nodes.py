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


# ── Additional expression nodes ───────────────────────────────────────────────

@dataclass(frozen=True)
class NegationExpr:
    """Unary negation: ``-x``."""
    operand: Any    # Expr


@dataclass(frozen=True)
class CallExpr:
    """
    A function call expression: ``add(3, 2)``.

    Per spec, parentheses are optional and are replaced by whitespace.
    The parser resolves this; the executor looks up the name in the RDF
    function registry.
    """
    name: str
    args: List[Any]     # List[Expr]


@dataclass(frozen=True)
class ArrayLiteralExpr:
    """An array literal: ``[3, 2, 5]``."""
    elements: List[Any]     # List[Expr]


@dataclass(frozen=True)
class IndexExpr:
    """Array/object index access: ``scores[-1]``."""
    target: Any     # Expr — evaluates to a GOMArray or GOMObject
    index: Any      # Expr


@dataclass(frozen=True)
class AttributeExpr:
    """Object property access: ``player.name``."""
    target: Any     # Expr — evaluates to a GOMObject or similar
    attribute: str


@dataclass(frozen=True)
class NewInstanceExpr:
    """
    Class instantiation: ``new Player()``.

    Per spec only one instance per class is allowed; the RDF enforces this.
    """
    class_name: str
    args: List[Any] = field(default_factory=list)  # List[Expr]


# ── Additional statement nodes ────────────────────────────────────────────────

@dataclass
class IfStmt:
    """
    ``if (condition) { then_body } else { else_body }``

    ``else_body`` may be an empty list when there is no else branch.
    """
    condition: Any          # Expr
    then_body: List[Any]    # List[Stmt]
    else_body: List[Any]    # List[Stmt] — empty list when absent
    exclamation_count: int = 1


@dataclass
class FunctionDeclStmt:
    """
    A function declaration using any permitted keyword variant:
    ``function``, ``func``, ``fun``, ``fn``, ``functi``, ``f``.

    Arrow-expression bodies are stored as a single ``ReturnStmt`` wrapping
    the expression (the parser normalises both forms).
    """
    name: str
    params: List[str]       # positional parameter names
    body: List[Any]         # List[Stmt]
    is_async: bool = False
    exclamation_count: int = 1


@dataclass
class ReturnStmt:
    """``return expr!`` — exits the current function with a value."""
    value_expr: Any         # Expr; may be LiteralExpr(None) for bare return
    exclamation_count: int = 1


@dataclass
class CallStmt:
    """
    A function call used as a statement (for side effects).

    Wraps a ``CallExpr``; the return value is discarded.
    """
    call_expr: Any          # CallExpr
    exclamation_count: int = 1
    debug_mode: bool = False


@dataclass
class IncrementStmt:
    """
    ``score++!`` — increments a numeric variable by one.

    Equivalent to ``score = score + 1`` but expresses intentional counting.
    """
    name: str
    exclamation_count: int = 1


@dataclass
class DecrementStmt:
    """
    ``score--!`` — decrements a numeric variable by one.

    Equivalent to ``score = score - 1``.
    """
    name: str
    exclamation_count: int = 1


@dataclass
class NoopStmt:
    """
    ``noop!`` — intentional no-operation.

    In async contexts this causes the coroutine to yield its turn so the
    other coroutine can advance two lines.
    """
    exclamation_count: int = 1


@dataclass
class ArrayDestructureStmt:
    """
    ``const var [getter, setter] = use(0)!``

    Binds each name in ``names`` to the corresponding element from the
    iterable produced by ``value_expr``.
    """
    names: List[str]
    value_expr: Any         # Expr — must evaluate to an iterable
    mutability: MutabilityFlavor
    exclamation_count: int = 1
    debug_mode: bool = False


@dataclass
class FileSeparatorStmt:
    """
    ``=====`` or ``======= name.gom =======``

    Marks the boundary between logical files inside a single ``.gom`` source.
    When executed, clears all non-global local timelines (resetting scope to
    only const-const-const globals).
    """
    filename: Optional[str] = None  # None when no name is given
    exclamation_count: int = 0      # separators have no terminator


@dataclass
class ClassDeclStmt:
    """
    ``class Player { body }`` or ``className Player { body }``

    Per spec, only one instance of each class may exist in the reality.
    """
    name: str
    body: List[Any]         # List[DeclareStmt | FunctionDeclStmt]
    exclamation_count: int = 1


@dataclass
class ExportStmt:
    """
    ``export name to "file.gom"!``

    Makes ``name`` available for import in the target file.
    """
    name: str
    target_file: str
    exclamation_count: int = 1


@dataclass
class ImportStmt:
    """
    ``import name!``

    Imports ``name`` from whichever file exported it.

    **Per spec:** Imported code runs 25 % slower and, at random, 25 % of
    imported lines are silently discarded (tariff simulation).
    """
    name: str
    exclamation_count: int = 1

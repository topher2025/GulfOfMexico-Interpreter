"""
Gulf of Mexico Executor.

Walks a list of AST statement nodes and executes them against a
RealityDistortionField.  This module is the bridge between the parsed program
representation and the runtime engine; it has no dependency on the lexer or
parser so it can be driven programmatically (e.g. from tests or a REPL).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from gom.runtime.engine import RealityDistortionField
from gom.runtime.types import MutabilityFlavor, LifetimeUnit
from gom.parsing.nodes import (
    # expressions
    LiteralExpr, VariableExpr, ArithmeticExpr, EqualityExpr,
    NotExpr, StringInterpolationExpr, SignalExpr,
    # statements
    DeclareStmt, AssignStmt, MutateStmt, PrintStmt,
    ReverseStmt, DeleteStmt, WhenStmt, ShiftTimeStmt,
)
from gom.stdlib.io import gom_print


class GOMExecutor:
    """
    Execute a Gulf of Mexico program against a RealityDistortionField.

    Usage::

        rdf = RealityDistortionField()
        executor = GOMExecutor(rdf)
        executor.execute_program([
            DeclareStmt("name", LiteralExpr("Luke"), MutabilityFlavor.CONST_CONST),
            PrintStmt(VariableExpr("name")),
        ])
    """

    def __init__(self, rdf: RealityDistortionField):
        self.rdf = rdf

    # ── Public API ────────────────────────────────────────────────────────────

    def execute_program(self, statements: List[Any]) -> None:
        """
        Execute a complete program.

        **Phase 1 — Pre-scan:** All declarations with negative lifetimes are
        registered before any statement runs, enabling variable hoisting (the
        ``<-N>`` lifetime syntax).

        **Phase 2 — Execute:** Statements are stepped through in order,
        honouring the current ``execution_direction`` on the RDF (which may be
        flipped by a ``reverse!`` statement mid-program).
        """
        self._prescan(statements)
        self._execute_statements(statements)

    # ── Phases ────────────────────────────────────────────────────────────────

    def _prescan(self, statements: List[Any]) -> None:
        """
        Register every negative-lifetime declaration before execution begins.

        The RDF cursor is briefly moved to the declaration's source line so the
        ``TemporalAnchor`` records the correct position, then restored.
        """
        saved_line = self.rdf.current_line
        for i, stmt in enumerate(statements):
            if (
                isinstance(stmt, DeclareStmt)
                and stmt.lifetime_unit == LifetimeUnit.NEGATIVE_LINES
                and stmt.lifetime_value is not None
                and stmt.lifetime_value < 0
            ):
                self.rdf.current_line = i
                value = self._eval(stmt.value_expr)
                self.rdf.declare_variable(
                    stmt.name,
                    value,
                    stmt.mutability,
                    stmt.lifetime_value,
                    stmt.lifetime_unit,
                    stmt.exclamation_count,
                )
        self.rdf.current_line = saved_line

    def _execute_statements(self, statements: List[Any]) -> None:
        """
        Step through statements, respecting ``execution_direction``.

        Forward execution: index increments by +1 each step.
        Reverse execution: index decrements by -1 (set by ``reverse!``).
        """
        i = 0
        while 0 <= i < len(statements):
            self.rdf.current_line = i
            self._execute_stmt(statements[i])
            self.rdf.advance_time()
            i += self.rdf.execution_direction

    # ── Statement dispatch ────────────────────────────────────────────────────

    def _execute_stmt(self, stmt: Any) -> None:
        if isinstance(stmt, DeclareStmt):
            self._exec_declare(stmt)
        elif isinstance(stmt, AssignStmt):
            self._exec_assign(stmt)
        elif isinstance(stmt, MutateStmt):
            self.rdf.mutate_variable(stmt.name, stmt.operation)
        elif isinstance(stmt, PrintStmt):
            value = self._eval(stmt.expr)
            gom_print(value, stmt.exclamation_count, stmt.debug_mode, engine=self.rdf)
        elif isinstance(stmt, ReverseStmt):
            self.rdf.reverse_execution()
        elif isinstance(stmt, DeleteStmt):
            self.rdf.delete_entity(self._eval(stmt.entity))
        elif isinstance(stmt, WhenStmt):
            self._exec_when(stmt)
        elif isinstance(stmt, ShiftTimeStmt):
            # Spec stores offsets in milliseconds; engine uses seconds
            offset_ms = float(self._eval(stmt.offset_expr))
            self.rdf.shift_time(offset_ms / 1000.0)
        # Unknown statement types are silently accepted — per spec, everything
        # is correct and intended.

    def _exec_declare(self, stmt: DeclareStmt) -> None:
        # Hoisted (negative-lifetime) declarations were already registered in
        # the pre-scan; skip them during normal forward execution.
        if (
            stmt.lifetime_unit == LifetimeUnit.NEGATIVE_LINES
            and stmt.lifetime_value is not None
            and stmt.lifetime_value < 0
        ):
            return
        value = self._eval(stmt.value_expr)
        self.rdf.declare_variable(
            stmt.name,
            value,
            stmt.mutability,
            stmt.lifetime_value,
            stmt.lifetime_unit,
            stmt.exclamation_count,
        )
        if stmt.debug_mode:
            gom_print(value, stmt.exclamation_count, debug_mode=True, engine=self.rdf)

    def _exec_assign(self, stmt: AssignStmt) -> None:
        value = self._eval(stmt.value_expr)
        self.rdf.set_variable(stmt.name, value)
        if stmt.debug_mode:
            gom_print(value, stmt.exclamation_count, debug_mode=True, engine=self.rdf)

    def _exec_when(self, stmt: WhenStmt) -> None:
        condition_value = self._eval(stmt.condition_expr)
        body = stmt.body

        def observer_callback():
            for s in body:
                self._execute_stmt(s)

        self.rdf.register_observer(stmt.variable, condition_value, observer_callback)

    # ── Expression evaluation ─────────────────────────────────────────────────

    def _eval(self, expr: Any) -> Any:
        """Recursively evaluate an expression node and return its value."""
        if isinstance(expr, LiteralExpr):
            return expr.value

        if isinstance(expr, VariableExpr):
            return self.rdf.get_variable(expr.name, expr.temporal)

        if isinstance(expr, ArithmeticExpr):
            return self._eval_arithmetic(expr)

        if isinstance(expr, EqualityExpr):
            left = self._eval(expr.left)
            right = self._eval(expr.right)
            return self.rdf.evaluate_equality(left, right, expr.precision)

        if isinstance(expr, NotExpr):
            val = self._eval(expr.operand)
            if val == "maybe":
                return "maybe"      # ;maybe is still maybe
            if isinstance(val, bool):
                return not val
            return not val

        if isinstance(expr, StringInterpolationExpr):
            context = self._build_interpolation_context()
            return self.rdf.interpolate_string(expr.template, context)

        if isinstance(expr, SignalExpr):
            initial = self._eval(expr.initial_value)
            return self.rdf.use_signal(initial)

        # Raw Python values (e.g. literals passed directly in tests) pass through.
        return expr

    def _eval_arithmetic(self, expr: ArithmeticExpr) -> Any:
        """
        Evaluate a binary arithmetic expression.

        Operator precedence is already encoded in the tree structure (the parser
        places higher-whitespace operators closer to the root so they are
        evaluated last).  The executor simply recurses left-to-right.
        """
        left = self._eval(expr.left)
        right = self._eval(expr.right)
        op = expr.op
        try:
            if op == '+':
                return left + right
            if op == '-':
                return left - right
            if op == '*':
                return left * right
            if op == '/':
                return self.rdf.UNDEFINED if right == 0 else left / right
            if op == '^':
                return left ** right
            if op == '%':
                return left % right
        except (TypeError, ZeroDivisionError):
            return self.rdf.UNDEFINED
        return self.rdf.UNDEFINED

    def _build_interpolation_context(self) -> Dict[str, Any]:
        """Snapshot of all currently-alive variable values for string interpolation."""
        context: Dict[str, Any] = {}
        for name, timeline in self.rdf.timelines.items():
            point = timeline.get_at_time(self.rdf.current_line, self.rdf.current_timestamp)
            if point is not None:
                context[name] = point.value
        return context

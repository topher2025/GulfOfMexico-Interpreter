"""
Gulf of Mexico Executor.

Walks a list of AST statement nodes and executes them against a
RealityDistortionField.  This module is the bridge between the parsed program
representation and the runtime engine; it has no dependency on the lexer or
parser so it can be driven programmatically (e.g. from tests or a REPL).
"""
from __future__ import annotations

import random
import time
from typing import Any, Dict, List, Optional

from gom.runtime.engine import RealityDistortionField
from gom.runtime.types import MutabilityFlavor, LifetimeUnit
from gom.parsing.nodes import (
    # expressions
    LiteralExpr, VariableExpr, ArithmeticExpr, EqualityExpr,
    NotExpr, NegationExpr, StringInterpolationExpr, SignalExpr,
    CallExpr, ArrayLiteralExpr, IndexExpr, AttributeExpr, NewInstanceExpr,
    # statements
    DeclareStmt, AssignStmt, MutateStmt, PrintStmt,
    ReverseStmt, DeleteStmt, WhenStmt, ShiftTimeStmt,
    IfStmt, FunctionDeclStmt, ReturnStmt, CallStmt,
    IncrementStmt, DecrementStmt, NoopStmt,
    ArrayDestructureStmt, FileSeparatorStmt,
    ClassDeclStmt, ExportStmt, ImportStmt,
)
from gom.stdlib.io import gom_print


class _ReturnSignal(Exception):
    """
    Internal control-flow exception used to unwind the call stack when a
    ``return`` statement is executed inside a function body.
    """
    def __init__(self, value: Any) -> None:
        self.value = value


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
        elif isinstance(stmt, IfStmt):
            self._exec_if(stmt)
        elif isinstance(stmt, FunctionDeclStmt):
            self.rdf.declare_function(stmt.name, stmt.params, stmt.body, stmt.is_async)
        elif isinstance(stmt, ReturnStmt):
            value = self._eval(stmt.value_expr) if stmt.value_expr is not None else self.rdf.UNDEFINED
            raise _ReturnSignal(value)
        elif isinstance(stmt, CallStmt):
            result = self._eval(stmt.call_expr)
            if stmt.debug_mode:
                gom_print(result, stmt.exclamation_count, debug_mode=True, engine=self.rdf)
        elif isinstance(stmt, IncrementStmt):
            self._exec_increment(stmt)
        elif isinstance(stmt, DecrementStmt):
            self._exec_decrement(stmt)
        elif isinstance(stmt, NoopStmt):
            pass    # intentional no-op; advances the line counter only
        elif isinstance(stmt, ArrayDestructureStmt):
            self._exec_array_destructure(stmt)
        elif isinstance(stmt, FileSeparatorStmt):
            self._exec_file_separator(stmt)
        elif isinstance(stmt, ClassDeclStmt):
            self.rdf.declare_class(stmt.name, stmt.body)
        elif isinstance(stmt, ExportStmt):
            pass    # file-level concern; no runtime effect in the engine
        elif isinstance(stmt, ImportStmt):
            self._exec_import(stmt)
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

    def _exec_if(self, stmt: IfStmt) -> None:
        condition = self._eval(stmt.condition)
        # GOM treats "maybe" as a valid boolean — execution still continues;
        # "maybe" is truthy enough to run the then-branch (as in life itself).
        branch = stmt.then_body if condition else stmt.else_body
        for s in branch:
            self._execute_stmt(s)

    def _exec_increment(self, stmt: IncrementStmt) -> None:
        current = self.rdf.get_variable(stmt.name)
        try:
            self.rdf.set_variable(stmt.name, current + 1)
        except TypeError:
            # Non-numeric — per spec everything is valid and correct, skip
            pass

    def _exec_decrement(self, stmt: DecrementStmt) -> None:
        current = self.rdf.get_variable(stmt.name)
        try:
            self.rdf.set_variable(stmt.name, current - 1)
        except TypeError:
            pass

    def _exec_array_destructure(self, stmt: ArrayDestructureStmt) -> None:
        """
        Bind each name in ``stmt.names`` to the corresponding element from
        the evaluated iterable.  Extra names receive ``"undefined"``; extra
        elements are silently discarded.
        """
        iterable = self._eval(stmt.value_expr)
        try:
            values = list(iterable)
        except TypeError:
            values = [iterable]
        for name, value in zip(stmt.names, values):
            self.rdf.declare_variable(name, value, stmt.mutability, exclamation_marks=stmt.exclamation_count)
        # Names without a corresponding value receive "undefined"
        for name in stmt.names[len(values):]:
            self.rdf.declare_variable(name, self.rdf.UNDEFINED, stmt.mutability, exclamation_marks=stmt.exclamation_count)

    def _exec_file_separator(self, stmt: FileSeparatorStmt) -> None:
        """
        Reset the non-global scope when a file separator is encountered.

        All timelines except const-const-const globals are cleared, effectively
        starting a new file while retaining eternal constants.
        """
        # Clear local scope if inside a function
        if self.rdf._local_scopes:
            self.rdf._local_scopes[-1].clear()
        else:
            # At top level: clear all user-defined (non-global-immutable) timelines
            names_to_clear = [
                name for name in list(self.rdf.timelines.keys())
                if name not in self.rdf.GLOBAL_IMMUTABLES
            ]
            for name in names_to_clear:
                del self.rdf.timelines[name]
        self.rdf.temporal_anomalies.clear()
        self.rdf.mutation_observers.clear()

    def _exec_import(self, stmt: ImportStmt) -> None:
        """
        ``import name!``

        Per spec, imported code runs 25 % slower (``time.sleep``) and
        25 % of imports are silently discarded (tariff simulation).
        """
        # 25 % tariff: randomly discard the import entirely
        if random.random() < 0.25:
            if self.rdf.debug:
                print(f"[TARIFF] Import of '{stmt.name}' was lost (25 % tariff)")
            return
        # 25 % slower: brief sleep to simulate import overhead
        time.sleep(0.001 * 0.25)

    # ── Expression evaluation ─────────────────────────────────────────────────

    def _eval(self, expr: Any) -> Any:
        """Recursively evaluate an expression node and return its value."""
        result = self._eval_inner(expr)
        # Per spec: ``delete 3!`` removes '3' from reality; any subsequent
        # expression that *produces* the value 3 (e.g. ``2 + 1``) must raise.
        self._check_not_deleted(result)
        return result

    def _check_not_deleted(self, value: Any) -> None:
        """Raise if *value* has been deleted from reality."""
        try:
            if value in self.rdf.deleted_entities:
                raise RuntimeError(f"Error: {value!r} has been deleted from reality")
        except TypeError:
            pass  # unhashable values (lists, dicts) cannot be individually deleted

    def _eval_inner(self, expr: Any) -> Any:
        """Core expression evaluation without the deleted-entity post-check."""
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

        if isinstance(expr, NegationExpr):
            val = self._eval(expr.operand)
            try:
                return -val
            except TypeError:
                return self.rdf.UNDEFINED

        if isinstance(expr, StringInterpolationExpr):
            context = self._build_interpolation_context()
            return self.rdf.interpolate_string(expr.template, context)

        if isinstance(expr, SignalExpr):
            initial = self._eval(expr.initial_value)
            return self.rdf.use_signal(initial)

        if isinstance(expr, CallExpr):
            return self._eval_call(expr)

        if isinstance(expr, ArrayLiteralExpr):
            from gom.stdlib.collections import GOMArray
            return GOMArray([self._eval(e) for e in expr.elements])

        if isinstance(expr, IndexExpr):
            target = self._eval(expr.target)
            index = self._eval(expr.index)
            try:
                return target[index]
            except (IndexError, KeyError, TypeError):
                return self.rdf.UNDEFINED

        if isinstance(expr, AttributeExpr):
            target = self._eval(expr.target)
            try:
                return target[expr.attribute]
            except (KeyError, TypeError):
                try:
                    return getattr(target, expr.attribute)
                except AttributeError:
                    return self.rdf.UNDEFINED

        if isinstance(expr, NewInstanceExpr):
            return self.rdf.instantiate_class(expr.class_name)

        # Raw Python values (e.g. literals passed directly in tests) pass through.
        return expr

    def _eval_call(self, expr: CallExpr) -> Any:
        """Look up and invoke a user-declared GOM function."""
        try:
            params, body, is_async = self.rdf.get_function_def(expr.name)
        except NameError:
            # Unknown function — per spec it's always correct; return undefined
            return self.rdf.UNDEFINED

        args = [self._eval(a) for a in expr.args]
        self.rdf.push_scope()
        try:
            for param, arg_value in zip(params, args):
                self.rdf.declare_variable(param, arg_value, MutabilityFlavor.VAR_VAR)
            # Remaining params with no matching arg receive "undefined"
            for param in params[len(args):]:
                self.rdf.declare_variable(param, self.rdf.UNDEFINED, MutabilityFlavor.VAR_VAR)
            return_value = self.rdf.UNDEFINED
            try:
                for stmt in body:
                    self._execute_stmt(stmt)
            except _ReturnSignal as sig:
                return_value = sig.value
            return return_value
        finally:
            self.rdf.pop_scope()

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
        # Collect from all scope frames (innermost last so they take precedence)
        for timeline_map in [self.rdf.timelines] + list(self.rdf._local_scopes):
            for name, timeline in timeline_map.items():
                point = timeline.get_at_time(self.rdf.current_line, self.rdf.current_timestamp)
                if point is not None:
                    context[name] = point.value
        return context

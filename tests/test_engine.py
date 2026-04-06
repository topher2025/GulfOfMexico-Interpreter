"""
Tests for the Gulf of Mexico temporal engine.

Covers: types, temporal data structures, RealityDistortionField, number-word
resolution, GOMArray, equality logic, string interpolation, I/O, AI correction
passes, and end-to-end executor round-trips.
"""
import pytest

from gom.runtime.engine import RealityDistortionField
from gom.runtime.executor import GOMExecutor
from gom.runtime.logic import evaluate_equality, resolve_number_word
from gom.runtime.strings import interpolate_string
from gom.runtime.temporal import TemporalAnchor, TimelinePoint, VariableTimeline
from gom.runtime.types import MutabilityFlavor, LifetimeUnit
from gom.stdlib.ai import aemi, abi, aqmi, ai, apply_all
from gom.stdlib.collections import GOMArray
from gom.stdlib.io import gom_print
from gom.parsing.nodes import (
    ArithmeticExpr, AssignStmt, DeclareStmt, DeleteStmt, EqualityExpr,
    LiteralExpr, NotExpr, PrintStmt, ReverseStmt, StringInterpolationExpr,
    VariableExpr, WhenStmt, SignalExpr,
    NegationExpr, CallExpr, ArrayLiteralExpr, IndexExpr, AttributeExpr,
    NewInstanceExpr, IfStmt, FunctionDeclStmt, ReturnStmt, CallStmt,
    IncrementStmt, DecrementStmt, NoopStmt, ArrayDestructureStmt,
    FileSeparatorStmt, ClassDeclStmt, ExportStmt, ImportStmt,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clear_globals():
    """Prevent const-const-const pollution between tests."""
    RealityDistortionField.clear_globals()
    yield
    RealityDistortionField.clear_globals()


def fresh() -> RealityDistortionField:
    return RealityDistortionField()


# ── MutabilityFlavor ──────────────────────────────────────────────────────────

class TestMutabilityFlavor:
    def test_all_five_flavors_exist(self):
        for flavor in (
            MutabilityFlavor.CONST_CONST,
            MutabilityFlavor.CONST_CONST_CONST,
            MutabilityFlavor.CONST_VAR,
            MutabilityFlavor.VAR_CONST,
            MutabilityFlavor.VAR_VAR,
        ):
            assert flavor

    def test_const_const_value_string(self):
        assert MutabilityFlavor.CONST_CONST.value == "const const"

    def test_var_var_value_string(self):
        assert MutabilityFlavor.VAR_VAR.value == "var var"


# ── LifetimeUnit ──────────────────────────────────────────────────────────────

class TestLifetimeUnit:
    def test_all_units_exist(self):
        for unit in (
            LifetimeUnit.LINES,
            LifetimeUnit.SECONDS,
            LifetimeUnit.INFINITY,
            LifetimeUnit.NEGATIVE_LINES,
        ):
            assert unit


# ── TemporalAnchor ────────────────────────────────────────────────────────────

class TestTemporalAnchor:
    def test_repr_contains_line(self):
        anchor = TemporalAnchor(line_number=3, timestamp=1.5, real_time=0.0)
        assert "line=3" in repr(anchor)

    def test_repr_contains_timestamp(self):
        anchor = TemporalAnchor(line_number=0, timestamp=2.75, real_time=0.0)
        assert "2.75s" in repr(anchor)


# ── TimelinePoint.is_alive ────────────────────────────────────────────────────

class TestTimelinePointIsAlive:
    def _point(self, lifetime_value=None, lifetime_unit=None, line=0, ts=0.0):
        anchor = TemporalAnchor(line_number=line, timestamp=ts, real_time=ts)
        return TimelinePoint(
            value="x",
            anchor=anchor,
            mutability=MutabilityFlavor.CONST_CONST,
            lifetime_value=lifetime_value,
            lifetime_unit=lifetime_unit,
        )

    def test_standard_alive_from_anchor_line(self):
        p = self._point(line=2)
        assert p.is_alive(2, 0.0)
        assert p.is_alive(100, 0.0)

    def test_standard_not_alive_before_anchor(self):
        p = self._point(line=2)
        assert not p.is_alive(1, 0.0)

    def test_infinity_always_alive(self):
        p = self._point(lifetime_unit=LifetimeUnit.INFINITY)
        assert p.is_alive(0, 0.0)
        assert p.is_alive(1_000_000, 0.0)

    def test_lines_alive_within_range(self):
        p = self._point(lifetime_value=2, lifetime_unit=LifetimeUnit.LINES, line=5)
        assert p.is_alive(5, 0.0)
        assert p.is_alive(7, 0.0)

    def test_lines_expired_after_range(self):
        p = self._point(lifetime_value=2, lifetime_unit=LifetimeUnit.LINES, line=5)
        assert not p.is_alive(8, 0.0)

    def test_negative_lines_hoisting_one(self):
        # declared at line 5, <-1> → alive only at line 4
        p = self._point(lifetime_value=-1, lifetime_unit=LifetimeUnit.NEGATIVE_LINES, line=5)
        assert p.is_alive(4, 0.0)
        assert not p.is_alive(3, 0.0)
        assert not p.is_alive(5, 0.0)

    def test_negative_lines_hoisting_three(self):
        # declared at line 10, <-3> → alive at lines 7, 8, 9
        p = self._point(lifetime_value=-3, lifetime_unit=LifetimeUnit.NEGATIVE_LINES, line=10)
        for ln in (7, 8, 9):
            assert p.is_alive(ln, 0.0)
        assert not p.is_alive(6, 0.0)
        assert not p.is_alive(10, 0.0)

    def test_seconds_alive_within_duration(self):
        p = self._point(lifetime_value=1.0, lifetime_unit=LifetimeUnit.SECONDS, ts=0.0)
        assert p.is_alive(0, 0.5)
        assert p.is_alive(0, 1.0)

    def test_seconds_expired(self):
        p = self._point(lifetime_value=1.0, lifetime_unit=LifetimeUnit.SECONDS, ts=0.0)
        assert not p.is_alive(0, 1.001)


# ── VariableTimeline ──────────────────────────────────────────────────────────

class TestVariableTimeline:
    def _make_point(self, value, line, priority=1):
        anchor = TemporalAnchor(line_number=line, timestamp=0.0, real_time=0.0)
        return TimelinePoint(
            value=value,
            anchor=anchor,
            mutability=MutabilityFlavor.VAR_VAR,
            exclamation_priority=priority,
        )

    def test_highest_priority_wins(self):
        tl = VariableTimeline("score")
        tl.add_point(self._make_point("low", line=0, priority=1))
        tl.add_point(self._make_point("high", line=0, priority=2))
        assert tl.get_at_time(0, 0.0).value == "high"

    def test_get_previous_returns_second_active(self):
        tl = VariableTimeline("score")
        tl.add_point(self._make_point(5, line=0))
        tl.add_point(self._make_point(6, line=1))
        prev = tl.get_previous(2, 0.0)
        assert prev.value == 5

    def test_get_all_history_returns_all_alive(self):
        tl = VariableTimeline("x")
        tl.add_point(self._make_point("a", line=0))
        tl.add_point(self._make_point("b", line=1))
        assert len(tl.get_all_history(5, 0.0)) == 2

    def test_no_points_returns_none(self):
        tl = VariableTimeline("empty")
        assert tl.get_at_time(0, 0.0) is None


# ── RDF built-in constants ────────────────────────────────────────────────────

class TestRDFBuiltinConstants:
    def test_true_is_python_true(self):
        assert fresh().get_variable("true") is True

    def test_false_is_python_false(self):
        assert fresh().get_variable("false") is False

    def test_maybe_is_string(self):
        assert fresh().get_variable("maybe") == "maybe"

    def test_undefined_is_string(self):
        assert fresh().get_variable("undefined") == "undefined"

    def test_date_now_is_float(self):
        assert isinstance(fresh().get_variable("Date.now"), float)


# ── Number-word resolution ────────────────────────────────────────────────────

class TestResolveNumberWord:
    @pytest.mark.parametrize("name,expected", [
        ("zero", 0),
        ("one", 1),
        ("two", 2),
        ("nine", 9),
        ("ten", 10),
        ("eleven", 11),
        ("nineteen", 19),
        ("twenty", 20),
        ("twenty-one", 21),
        ("thirty-seven", 37),
        ("ninety-nine", 99),
        ("one hundred", 100),
        ("two hundred", 200),
        ("two hundred thirty-four", 234),
        ("one thousand", 1_000),
        ("one thousand two hundred thirty-four", 1_234),
        ("one million", 1_000_000),
        ("one billion", 1_000_000_000),
        ("one trillion", 1_000_000_000_000),
        ("one million two hundred thirty-four thousand five hundred sixty-seven", 1_234_567),
    ])
    def test_known_number_word(self, name, expected):
        assert resolve_number_word(name) == expected

    @pytest.mark.parametrize("name", ["hello", "not a number", "", "score", "x"])
    def test_non_number_returns_none(self, name):
        assert resolve_number_word(name) is None

    def test_rdf_resolves_via_get_variable(self):
        rdf = fresh()
        assert rdf.get_variable("one") == 1
        assert rdf.get_variable("two") == 2
        assert rdf.get_variable("forty-two") == 42
        assert rdf.get_variable("one hundred") == 100

    def test_spec_example_one_plus_two(self):
        rdf = fresh()
        assert rdf.get_variable("one") + rdf.get_variable("two") == 3

    def test_user_can_override_number_word(self):
        rdf = fresh()
        rdf.declare_variable("one", 99, MutabilityFlavor.VAR_VAR)
        assert rdf.get_variable("one") == 99


# ── RDF declare ───────────────────────────────────────────────────────────────

class TestRDFDeclare:
    def test_stores_and_retrieves_value(self):
        rdf = fresh()
        rdf.declare_variable("name", "Luke", MutabilityFlavor.CONST_CONST)
        assert rdf.get_variable("name") == "Luke"

    def test_const_const_const_is_global(self):
        rdf1 = fresh()
        rdf1.declare_variable("pi", 3.14, MutabilityFlavor.CONST_CONST_CONST)
        rdf2 = fresh()
        assert rdf2.get_variable("pi") == 3.14

    def test_cannot_redeclare_eternal(self):
        rdf = fresh()
        rdf.declare_variable("e", 2.71, MutabilityFlavor.CONST_CONST_CONST)
        with pytest.raises(RuntimeError, match="eternal"):
            rdf.declare_variable("e", 9.99, MutabilityFlavor.CONST_CONST)

    def test_overloading_higher_exclamation_wins(self):
        rdf = fresh()
        rdf.declare_variable("name", "Lu", MutabilityFlavor.CONST_CONST, exclamation_marks=2)
        rdf.declare_variable("name", "Luke", MutabilityFlavor.CONST_CONST, exclamation_marks=1)
        assert rdf.get_variable("name") == "Lu"

    def test_overloading_inverted_exclamation_loses(self):
        rdf = fresh()
        rdf.declare_variable("name", "Lu", MutabilityFlavor.CONST_CONST, exclamation_marks=1)
        rdf.declare_variable("name", "Luke", MutabilityFlavor.CONST_CONST, exclamation_marks=-1)
        assert rdf.get_variable("name") == "Lu"

    def test_deleted_value_cannot_be_declared(self):
        rdf = fresh()
        rdf.delete_entity(3)
        with pytest.raises(RuntimeError):
            rdf.declare_variable("x", 3, MutabilityFlavor.CONST_CONST)

    def test_unknown_name_raises_name_error(self):
        with pytest.raises(NameError):
            fresh().get_variable("nonexistent_var_xyz")


# ── RDF set_variable ──────────────────────────────────────────────────────────

class TestRDFSet:
    def test_var_var_can_be_reassigned(self):
        rdf = fresh()
        rdf.declare_variable("score", 5, MutabilityFlavor.VAR_VAR)
        rdf.set_variable("score", 6)
        assert rdf.get_variable("score") == 6

    def test_const_const_cannot_be_reassigned(self):
        rdf = fresh()
        rdf.declare_variable("name", "Luke", MutabilityFlavor.CONST_CONST)
        with pytest.raises(RuntimeError):
            rdf.set_variable("name", "Lu")

    def test_const_var_cannot_be_reassigned(self):
        rdf = fresh()
        rdf.declare_variable("name", "Luke", MutabilityFlavor.CONST_VAR)
        with pytest.raises(RuntimeError):
            rdf.set_variable("name", "Lu")

    def test_set_date_now_shifts_clock(self):
        rdf = fresh()
        rdf.set_variable("Date.now", 0.0)
        assert abs(rdf.current_timestamp) < 5.0


# ── RDF temporal lookups ──────────────────────────────────────────────────────

class TestRDFTemporalLookup:
    def test_current_returns_latest_value(self):
        rdf = fresh()
        rdf.declare_variable("score", 5, MutabilityFlavor.VAR_VAR)
        rdf.advance_time()
        rdf.set_variable("score", 6)
        assert rdf.get_variable("score", "current") == 6

    def test_previous_returns_prior_value(self):
        rdf = fresh()
        rdf.declare_variable("score", 5, MutabilityFlavor.VAR_VAR)
        rdf.advance_time()
        rdf.set_variable("score", 6)
        assert rdf.get_variable("score", "previous") == 5

    def test_next_returns_future_timeline_value(self):
        rdf = fresh()
        rdf.declare_variable("score", 5, MutabilityFlavor.VAR_VAR)
        # Pre-load a future value by moving the cursor forward
        rdf.current_line = 10
        rdf.set_variable("score", 99)
        rdf.current_line = 0
        assert rdf.get_variable("score", "next") == 99

    def test_negative_lifetime_hoisting_at_boundary(self):
        rdf = fresh()
        rdf.current_line = 1
        rdf.declare_variable("name", "Luke", MutabilityFlavor.CONST_CONST, -1, LifetimeUnit.NEGATIVE_LINES)
        rdf.current_line = 0
        assert rdf.get_variable("name") == "Luke"

    def test_negative_lifetime_not_visible_outside_range(self):
        rdf = fresh()
        rdf.current_line = 5
        rdf.declare_variable("name", "Luke", MutabilityFlavor.CONST_CONST, -1, LifetimeUnit.NEGATIVE_LINES)
        rdf.current_line = 3   # too far before creation
        with pytest.raises((NameError, RuntimeError)):
            rdf.get_variable("name")

    def test_lifetime_in_lines_expires(self):
        rdf = fresh()
        rdf.declare_variable("temp", "here", MutabilityFlavor.CONST_CONST, 2, LifetimeUnit.LINES)
        assert rdf.get_variable("temp") == "here"
        rdf.current_line = 3
        with pytest.raises(RuntimeError):
            rdf.get_variable("temp")


# ── RDF execution direction ───────────────────────────────────────────────────

class TestRDFExecution:
    def test_starts_forward(self):
        assert fresh().execution_direction == 1

    def test_reverse_flips_direction(self):
        rdf = fresh()
        rdf.reverse_execution()
        assert rdf.execution_direction == -1

    def test_double_reverse_restores_forward(self):
        rdf = fresh()
        rdf.reverse_execution()
        rdf.reverse_execution()
        assert rdf.execution_direction == 1

    def test_advance_respects_direction(self):
        rdf = fresh()
        rdf.reverse_execution()
        rdf.advance_time()
        assert rdf.current_line == -1


# ── RDF delete ────────────────────────────────────────────────────────────────

class TestRDFDelete:
    def test_delete_primitive(self):
        rdf = fresh()
        rdf.delete_entity(3)
        assert rdf.is_deleted(3)

    def test_delete_variable_removes_from_timelines(self):
        rdf = fresh()
        rdf.declare_variable("x", 1, MutabilityFlavor.VAR_VAR)
        rdf.delete_entity("x")
        with pytest.raises(NameError):
            rdf.get_variable("x")

    def test_delete_delete_disables_delete(self):
        rdf = fresh()
        rdf.delete_entity("delete")
        with pytest.raises(RuntimeError, match="deleted"):
            rdf.delete_entity("something")


# ── RDF when observer ─────────────────────────────────────────────────────────

class TestRDFWhenObserver:
    def test_observer_fires_on_match(self):
        rdf = fresh()
        results = []
        rdf.declare_variable("health", 10, MutabilityFlavor.VAR_VAR)
        rdf.register_observer("health", 0, lambda: results.append("dead"))
        rdf.set_variable("health", 5)
        assert results == []
        rdf.set_variable("health", 0)
        assert results == ["dead"]

    def test_observer_does_not_fire_on_mismatch(self):
        rdf = fresh()
        results = []
        rdf.declare_variable("x", 1, MutabilityFlavor.VAR_VAR)
        rdf.register_observer("x", 99, lambda: results.append("hit"))
        rdf.set_variable("x", 50)
        assert results == []


# ── RDF signal ────────────────────────────────────────────────────────────────

class TestRDFSignal:
    def test_initial_value(self):
        getter, _ = fresh().use_signal(42)
        assert getter() == 42

    def test_setter_updates_getter(self):
        getter, setter = fresh().use_signal(0)
        setter(99)
        assert getter() == 99

    def test_getter_and_setter_share_state(self):
        g, s = fresh().use_signal("hello")
        s("world")
        assert g() == "world"


# ── RDF time ──────────────────────────────────────────────────────────────────

class TestRDFTime:
    def test_shift_time_increases_timestamp(self):
        rdf = fresh()
        before = rdf.current_timestamp
        rdf.shift_time(1000.0)
        assert rdf.current_timestamp - before >= 999.9

    def test_shift_time_negative(self):
        rdf = fresh()
        rdf.shift_time(100.0)
        before = rdf.current_timestamp
        rdf.shift_time(-50.0)
        assert rdf.current_timestamp < before


# ── RDF equality delegation ───────────────────────────────────────────────────

class TestRDFEquality:
    def test_loose_int_float(self):
        assert fresh().evaluate_equality(3, 3.14, 0) is True

    def test_double_equal_cross_type(self):
        assert fresh().evaluate_equality(3.14, "3.14", 1) is True

    def test_triple_equal_different_types(self):
        assert fresh().evaluate_equality(3.14, "3.14", 2) is False

    def test_quad_equal_same_object(self):
        s = "hello"
        assert fresh().evaluate_equality(s, s, 3) is True

    def test_quad_equal_different_objects(self):
        # Use float() constructor to guarantee two distinct objects at runtime
        a = float("3.14")
        b = float("3.14")
        assert a is not b
        assert fresh().evaluate_equality(a, b, 3) is False


# ── RDF string interpolation delegation ──────────────────────────────────────

class TestRDFStringInterpolation:
    def test_dollar_interpolation(self):
        result = fresh().interpolate_string("Hello ${name}!", {"name": "world"})
        assert result == "Hello world!"

    def test_pound_interpolation(self):
        result = fresh().interpolate_string("Hello £{name}!", {"name": "GB"})
        assert result == "Hello GB!"

    def test_euro_suffix_consumed(self):
        result = fresh().interpolate_string("Hello {name}€ there", {"name": "EU"})
        assert result == "Hello EU there"

    def test_yen_interpolation(self):
        result = fresh().interpolate_string("Hello ¥{name}!", {"name": "JP"})
        assert result == "Hello JP!"


# ── evaluate_equality (standalone) ───────────────────────────────────────────

class TestEvaluateEquality:
    def test_precision_0_loose(self):
        assert evaluate_equality(3, 3.14, 0) is True

    def test_precision_1_cross_type(self):
        assert evaluate_equality(3.14, "3.14", 1) is True

    def test_precision_2_string_vs_string(self):
        assert evaluate_equality("abc", "abc", 2) is True

    def test_precision_3_same_identity(self):
        obj = object()
        assert evaluate_equality(obj, obj, 3) is True

    def test_precision_3_different_float_literals(self):
        # Two float objects with the same value but different identities
        a = float("3.14")
        b = float("3.14")
        assert a is not b
        assert evaluate_equality(a, b, 3) is False


# ── interpolate_string (standalone) ──────────────────────────────────────────

class TestInterpolateString:
    def test_escudo_nested_property(self):
        player = {"name": "Lu"}
        result = interpolate_string("Hello {player$name}!", {"player": player})
        assert result == "Hello Lu!"

    def test_missing_key_returns_undefined(self):
        result = interpolate_string("${missing}", {}, "undefined")
        assert result == "undefined"


# ── GOMArray ──────────────────────────────────────────────────────────────────

class TestGOMArray:
    def test_index_minus_one_is_first(self):
        assert GOMArray([3, 2, 5])[-1] == 3

    def test_index_zero_is_second(self):
        assert GOMArray([3, 2, 5])[0] == 2

    def test_index_one_is_third(self):
        assert GOMArray([3, 2, 5])[1] == 5

    def test_float_insert(self):
        arr = GOMArray([3, 2, 5])
        arr[0.5] = 4
        assert list(arr) == [3, 2, 4, 5]

    def test_repr_contains_class_name(self):
        assert "GOMArray" in repr(GOMArray([1, 2]))

    def test_out_of_bounds_raises(self):
        with pytest.raises(IndexError):
            _ = GOMArray([1, 2])[99]

    def test_set_by_integer_index(self):
        arr = GOMArray([10, 20, 30])
        arr[0] = 99
        assert arr[0] == 99


# ── gom_print ─────────────────────────────────────────────────────────────────

class TestGOMPrint:
    def test_basic_print(self, capsys):
        gom_print("Hello Gulf")
        assert "Hello Gulf" in capsys.readouterr().out

    def test_debug_mode_shows_metadata(self, capsys):
        gom_print("test", exclamation_count=3, debug_mode=True)
        out = capsys.readouterr().out
        assert "[DEBUG]" in out
        assert "correctness=3" in out
        assert "the interpreter agrees" in out

    def test_debug_mode_uses_engine_line(self, capsys):
        rdf = fresh()
        rdf.current_line = 7
        gom_print("x", exclamation_count=1, debug_mode=True, engine=rdf)
        out = capsys.readouterr().out
        assert "line=7" in out

    def test_non_string_value_coerced(self, capsys):
        gom_print(42)
        assert "42" in capsys.readouterr().out


# ── AI correction passes ──────────────────────────────────────────────────────

class TestAEMI:
    def test_adds_exclamation_to_unterminated_statement(self):
        assert aemi('print("hello")').strip().endswith('!')

    def test_leaves_exclamation_terminated_alone(self):
        assert aemi('print("hello")!').strip() == 'print("hello")!'

    def test_leaves_question_mark_terminated_alone(self):
        assert aemi('print("hello")?').strip() == 'print("hello")?'

    def test_ignores_comment_lines(self):
        result = aemi('// just a comment')
        assert '!' not in result

    def test_ignores_blank_lines(self):
        assert aemi('').strip() == ''


class TestABI:
    def test_adds_brackets_to_bare_print(self):
        assert 'print(' in abi('print "hello"')

    def test_leaves_existing_brackets_alone(self):
        assert abi('print("hello")').strip() == 'print("hello")'

    def test_handles_var_declaration(self):
        src = 'const const x = 1!'
        assert abi(src).strip() == src.strip()


class TestAQMI:
    def test_quotes_lowercase_bare_word(self):
        assert '"hello"' in aqmi('print(hello)')

    def test_leaves_quoted_string_alone(self):
        assert aqmi('print("world")').strip() == 'print("world")'

    def test_leaves_boolean_keyword_alone(self):
        assert 'print(true)' in aqmi('print(true)')

    def test_leaves_maybe_alone(self):
        assert 'print(maybe)' in aqmi('print(maybe)')


class TestAI:
    def test_replaces_unrecognised_line(self):
        result = ai('completely invalid garbage here')
        assert 'print("")' in result

    def test_leaves_valid_terminated_statement_alone(self):
        assert ai('print("hello")!').strip() == 'print("hello")!'

    def test_leaves_file_separator_alone(self):
        sep = '===================='
        assert ai(sep).strip() == sep


class TestApplyAll:
    def test_full_pipeline_on_bare_print(self):
        result = apply_all('print "hello"')
        assert 'print(' in result
        assert result.strip().endswith('!')


# ── GOMExecutor end-to-end ────────────────────────────────────────────────────

class TestExecutor:
    def _run(self, stmts):
        rdf = fresh()
        GOMExecutor(rdf).execute_program(stmts)
        return rdf

    def test_declare_and_lookup(self):
        rdf = self._run([DeclareStmt("x", LiteralExpr(42), MutabilityFlavor.CONST_CONST)])
        assert rdf.get_variable("x") == 42

    def test_assign_updates_value(self):
        rdf = self._run([
            DeclareStmt("x", LiteralExpr(1), MutabilityFlavor.VAR_VAR),
            AssignStmt("x", LiteralExpr(99)),
        ])
        assert rdf.get_variable("x") == 99

    def test_print_statement(self, capsys):
        self._run([PrintStmt(LiteralExpr("Hello Gulf"), exclamation_count=1)])
        assert "Hello Gulf" in capsys.readouterr().out

    def test_reverse_flips_engine_direction(self):
        rdf = self._run([ReverseStmt()])
        assert rdf.execution_direction == -1

    def test_arithmetic_add(self):
        rdf = self._run([
            DeclareStmt("r", ArithmeticExpr(LiteralExpr(3), '+', LiteralExpr(4)),
                        MutabilityFlavor.CONST_CONST),
        ])
        assert rdf.get_variable("r") == 7

    def test_arithmetic_divide_by_zero_returns_undefined(self):
        rdf = self._run([
            DeclareStmt("r", ArithmeticExpr(LiteralExpr(3), '/', LiteralExpr(0)),
                        MutabilityFlavor.CONST_CONST),
        ])
        assert rdf.get_variable("r") == "undefined"

    def test_arithmetic_whitespace_precedence_encoded_in_tree(self):
        # 1 + 2*3 (lower space around * = higher precedence) = 7
        inner = ArithmeticExpr(LiteralExpr(2), '*', LiteralExpr(3),
                               left_space=0, right_space=0)
        outer = ArithmeticExpr(LiteralExpr(1), '+', inner,
                               left_space=1, right_space=1)
        rdf = self._run([DeclareStmt("r", outer, MutabilityFlavor.CONST_CONST)])
        assert rdf.get_variable("r") == 7

    def test_equality_expr(self):
        rdf = self._run([
            DeclareStmt("eq",
                        EqualityExpr(LiteralExpr(3.14), LiteralExpr("3.14"), 1),
                        MutabilityFlavor.CONST_CONST),
        ])
        assert rdf.get_variable("eq") is True

    def test_not_expr_true(self):
        rdf = self._run([
            DeclareStmt("r", NotExpr(LiteralExpr(True)), MutabilityFlavor.CONST_CONST),
        ])
        assert rdf.get_variable("r") is False

    def test_not_maybe_stays_maybe(self):
        rdf = self._run([
            DeclareStmt("r", NotExpr(LiteralExpr("maybe")), MutabilityFlavor.CONST_CONST),
        ])
        assert rdf.get_variable("r") == "maybe"

    def test_delete_stmt(self):
        rdf = self._run([
            DeclareStmt("x", LiteralExpr(1), MutabilityFlavor.VAR_VAR),
            DeleteStmt(LiteralExpr("x")),
        ])
        with pytest.raises(NameError):
            rdf.get_variable("x")

    def test_when_stmt_fires_body(self, capsys):
        self._run([
            DeclareStmt("health", LiteralExpr(10), MutabilityFlavor.VAR_VAR),
            WhenStmt("health", LiteralExpr(0),
                     [PrintStmt(LiteralExpr("you lose"))]),
            AssignStmt("health", LiteralExpr(0)),
        ])
        assert "you lose" in capsys.readouterr().out

    def test_string_interpolation_in_print(self, capsys):
        self._run([
            DeclareStmt("name", LiteralExpr("world"), MutabilityFlavor.CONST_CONST),
            PrintStmt(StringInterpolationExpr("Hello ${name}!")),
        ])
        assert "Hello world!" in capsys.readouterr().out

    def test_negative_lifetime_hoisting(self, capsys):
        # print(name)! at line 0, const const name<-1> = "Luke"! at line 1
        # Pre-scan should make name visible at line 0.
        rdf = fresh()
        executor = GOMExecutor(rdf)
        executor.execute_program([
            PrintStmt(VariableExpr("name")),           # line 0
            DeclareStmt("name", LiteralExpr("Luke"),   # line 1 with <-1>
                        MutabilityFlavor.CONST_CONST,
                        lifetime_value=-1,
                        lifetime_unit=LifetimeUnit.NEGATIVE_LINES),
        ])
        assert "Luke" in capsys.readouterr().out

    def test_temporal_previous_via_executor(self):
        rdf = self._run([
            DeclareStmt("score", LiteralExpr(5), MutabilityFlavor.VAR_VAR),
            AssignStmt("score", LiteralExpr(6)),
        ])
        assert rdf.get_variable("score", "current") == 6
        assert rdf.get_variable("score", "previous") == 5

    def test_number_word_in_arithmetic(self):
        rdf = self._run([
            DeclareStmt("r",
                        ArithmeticExpr(VariableExpr("one"), '+', VariableExpr("two")),
                        MutabilityFlavor.CONST_CONST),
        ])
        assert rdf.get_variable("r") == 3

    def test_number_word_large(self):
        rdf = self._run([
            DeclareStmt("big",
                        VariableExpr("one million"),
                        MutabilityFlavor.CONST_CONST),
        ])
        assert rdf.get_variable("big") == 1_000_000


# ── New engine features ───────────────────────────────────────────────────────

class TestSignalSentinel:
    """use_signal should accept None/0/False as valid new values (not treat as 'no arg')."""

    def test_signal_set_to_none(self):
        getter, setter = fresh().use_signal("initial")
        setter(None)
        assert getter() is None

    def test_signal_set_to_zero(self):
        getter, setter = fresh().use_signal(99)
        setter(0)
        assert getter() == 0

    def test_signal_set_to_false(self):
        getter, setter = fresh().use_signal(True)
        setter(False)
        assert getter() is False

    def test_getter_returns_current_without_arg(self):
        getter, setter = fresh().use_signal(42)
        assert getter() == 42

    def test_getter_equals_setter(self):
        getter, setter = fresh().use_signal(0)
        assert getter is setter


class TestWhenLooseEquality:
    """when (health = 0) uses GOM loose '=' (precision 0), not Python ==."""

    def test_when_fires_on_float_int_loose_match(self, capsys):
        rdf = fresh()
        rdf.declare_variable("hp", 10, MutabilityFlavor.VAR_VAR)
        rdf.register_observer("hp", 0, lambda: print("dead"))
        rdf.set_variable("hp", 0)
        assert "dead" in capsys.readouterr().out

    def test_when_fires_loose_int_vs_float(self, capsys):
        """3 = 3.14 is True at precision 0 (int(float) comparison)."""
        rdf = fresh()
        rdf.declare_variable("x", 10, MutabilityFlavor.VAR_VAR)
        rdf.register_observer("x", 3, lambda: print("match"))
        rdf.set_variable("x", 3)
        assert "match" in capsys.readouterr().out


class TestScopeManagement:
    def test_push_pop_scope(self):
        rdf = fresh()
        rdf.push_scope()
        assert len(rdf._local_scopes) == 1
        rdf.pop_scope()
        assert len(rdf._local_scopes) == 0

    def test_local_variable_hidden_from_outer_scope(self):
        rdf = fresh()
        rdf.push_scope()
        rdf.declare_variable("local_x", 42, MutabilityFlavor.VAR_VAR)
        rdf.pop_scope()
        with pytest.raises(NameError):
            rdf.get_variable("local_x")

    def test_local_shadows_global(self):
        rdf = fresh()
        rdf.declare_variable("score", 10, MutabilityFlavor.VAR_VAR)
        rdf.push_scope()
        rdf.declare_variable("score", 99, MutabilityFlavor.VAR_VAR)
        assert rdf.get_variable("score") == 99
        rdf.pop_scope()
        assert rdf.get_variable("score") == 10


class TestFunctionRegistry:
    def test_declare_and_lookup_function(self):
        rdf = fresh()
        rdf.declare_function("add", ["a", "b"], [ReturnStmt(ArithmeticExpr(VariableExpr("a"), '+', VariableExpr("b")))])
        params, body, is_async = rdf.get_function_def("add")
        assert params == ["a", "b"]
        assert is_async is False

    def test_unknown_function_raises(self):
        with pytest.raises(NameError):
            fresh().get_function_def("nonexistent")


class TestClassRegistry:
    def test_declare_class(self):
        rdf = fresh()
        rdf.declare_class("Player", [])
        instance = rdf.instantiate_class("Player")
        assert instance["__class__"] == "Player"

    def test_single_instance_enforcement(self):
        rdf = fresh()
        rdf.declare_class("Player", [])
        rdf.instantiate_class("Player")
        with pytest.raises(RuntimeError, match="one 'Player' instance"):
            rdf.instantiate_class("Player")

    def test_instantiate_unknown_class_raises(self):
        with pytest.raises(NameError):
            fresh().instantiate_class("Unknown")


class TestGOMObject:
    def test_dict_access(self):
        from gom.stdlib.collections import GOMObject
        obj = GOMObject({"name": "Luke"})
        assert obj["name"] == "Luke"

    def test_attribute_access(self):
        from gom.stdlib.collections import GOMObject
        obj = GOMObject({"name": "Luke"})
        assert obj.name == "Luke"

    def test_attribute_set(self):
        from gom.stdlib.collections import GOMObject
        obj = GOMObject()
        obj.name = "Lu"
        assert obj["name"] == "Lu"

    def test_missing_attribute_raises(self):
        from gom.stdlib.collections import GOMObject
        obj = GOMObject()
        with pytest.raises(AttributeError):
            _ = obj.nonexistent

    def test_repr(self):
        from gom.stdlib.collections import GOMObject
        obj = GOMObject({"a": 1})
        assert "'a'" in repr(obj)


class TestNewNodes:
    """Verify all new AST nodes can be instantiated correctly."""

    def test_negation_expr(self):
        from gom.parsing.nodes import NegationExpr
        e = NegationExpr(LiteralExpr(5))
        assert e.operand.value == 5

    def test_call_expr(self):
        from gom.parsing.nodes import CallExpr
        e = CallExpr("add", [LiteralExpr(1), LiteralExpr(2)])
        assert e.name == "add"
        assert len(e.args) == 2

    def test_array_literal_expr(self):
        from gom.parsing.nodes import ArrayLiteralExpr
        e = ArrayLiteralExpr([LiteralExpr(1), LiteralExpr(2)])
        assert len(e.elements) == 2

    def test_index_expr(self):
        from gom.parsing.nodes import IndexExpr
        e = IndexExpr(VariableExpr("arr"), LiteralExpr(-1))
        assert e.target == VariableExpr("arr")
        assert e.index == LiteralExpr(-1)

    def test_attribute_expr(self):
        from gom.parsing.nodes import AttributeExpr
        e = AttributeExpr(VariableExpr("player"), "name")
        assert e.attribute == "name"

    def test_if_stmt(self):
        from gom.parsing.nodes import IfStmt
        s = IfStmt(LiteralExpr(True), [PrintStmt(LiteralExpr("yes"))], [])
        assert s.else_body == []

    def test_function_decl_stmt(self):
        from gom.parsing.nodes import FunctionDeclStmt
        s = FunctionDeclStmt("add", ["a", "b"], [])
        assert s.is_async is False

    def test_return_stmt(self):
        from gom.parsing.nodes import ReturnStmt
        s = ReturnStmt(LiteralExpr(42))
        assert s.value_expr.value == 42

    def test_increment_stmt(self):
        from gom.parsing.nodes import IncrementStmt
        s = IncrementStmt("score")
        assert s.name == "score"

    def test_decrement_stmt(self):
        from gom.parsing.nodes import DecrementStmt
        s = DecrementStmt("health")
        assert s.name == "health"

    def test_class_decl_stmt(self):
        from gom.parsing.nodes import ClassDeclStmt
        s = ClassDeclStmt("Player", [])
        assert s.name == "Player"

    def test_file_separator_stmt(self):
        from gom.parsing.nodes import FileSeparatorStmt
        s = FileSeparatorStmt("add.gom")
        assert s.filename == "add.gom"

    def test_export_stmt(self):
        from gom.parsing.nodes import ExportStmt
        s = ExportStmt("add", "main.gom")
        assert s.target_file == "main.gom"

    def test_import_stmt(self):
        from gom.parsing.nodes import ImportStmt
        s = ImportStmt("add")
        assert s.name == "add"


class TestExecutorNewFeatures:
    def _run(self, stmts):
        rdf = fresh()
        GOMExecutor(rdf).execute_program(stmts)
        return rdf

    # ── NegationExpr ─────────────────────────────────────────────────────────

    def test_negation_positive_number(self):
        from gom.parsing.nodes import NegationExpr
        rdf = self._run([DeclareStmt("r", NegationExpr(LiteralExpr(5)), MutabilityFlavor.CONST_CONST)])
        assert rdf.get_variable("r") == -5

    def test_negation_negative_number(self):
        from gom.parsing.nodes import NegationExpr
        rdf = self._run([DeclareStmt("r", NegationExpr(LiteralExpr(-3)), MutabilityFlavor.CONST_CONST)])
        assert rdf.get_variable("r") == 3

    # ── ArrayLiteralExpr / IndexExpr / AttributeExpr ──────────────────────────

    def test_array_literal(self):
        from gom.parsing.nodes import ArrayLiteralExpr
        rdf = self._run([
            DeclareStmt("scores", ArrayLiteralExpr([LiteralExpr(3), LiteralExpr(2), LiteralExpr(5)]),
                        MutabilityFlavor.CONST_CONST),
        ])
        arr = rdf.get_variable("scores")
        assert arr[-1] == 3   # GOM index -1 = first element
        assert arr[0] == 2
        assert arr[1] == 5

    def test_index_expr(self):
        from gom.parsing.nodes import ArrayLiteralExpr, IndexExpr
        rdf = self._run([
            DeclareStmt("scores", ArrayLiteralExpr([LiteralExpr(3), LiteralExpr(2), LiteralExpr(5)]),
                        MutabilityFlavor.CONST_CONST),
            DeclareStmt("first", IndexExpr(VariableExpr("scores"), LiteralExpr(-1)),
                        MutabilityFlavor.CONST_CONST),
        ])
        assert rdf.get_variable("first") == 3

    def test_attribute_expr_on_object(self):
        from gom.parsing.nodes import AttributeExpr
        from gom.stdlib.collections import GOMObject
        obj = GOMObject({"health": 10})
        rdf = self._run([
            DeclareStmt("player", LiteralExpr(obj), MutabilityFlavor.CONST_CONST),
            DeclareStmt("hp", AttributeExpr(VariableExpr("player"), "health"),
                        MutabilityFlavor.CONST_CONST),
        ])
        assert rdf.get_variable("hp") == 10

    # ── CallExpr / FunctionDeclStmt / ReturnStmt ──────────────────────────────

    def test_function_call_returns_value(self):
        from gom.parsing.nodes import FunctionDeclStmt, ReturnStmt, CallExpr
        rdf = self._run([
            FunctionDeclStmt("double", ["x"], [
                ReturnStmt(ArithmeticExpr(VariableExpr("x"), '*', LiteralExpr(2)))
            ]),
            DeclareStmt("r", CallExpr("double", [LiteralExpr(5)]), MutabilityFlavor.CONST_CONST),
        ])
        assert rdf.get_variable("r") == 10

    def test_function_add(self):
        from gom.parsing.nodes import FunctionDeclStmt, ReturnStmt, CallExpr
        rdf = self._run([
            FunctionDeclStmt("add", ["a", "b"], [
                ReturnStmt(ArithmeticExpr(VariableExpr("a"), '+', VariableExpr("b")))
            ]),
            DeclareStmt("r", CallExpr("add", [LiteralExpr(3), LiteralExpr(4)]),
                        MutabilityFlavor.CONST_CONST),
        ])
        assert rdf.get_variable("r") == 7

    def test_function_scope_isolation(self):
        from gom.parsing.nodes import FunctionDeclStmt, ReturnStmt, CallExpr
        """Local params must not pollute the global scope after the call."""
        rdf = self._run([
            FunctionDeclStmt("f", ["local_param"], [
                ReturnStmt(LiteralExpr(99))
            ]),
            DeclareStmt("r", CallExpr("f", [LiteralExpr(1)]), MutabilityFlavor.CONST_CONST),
        ])
        with pytest.raises(NameError):
            rdf.get_variable("local_param")

    def test_unknown_function_returns_undefined(self):
        from gom.parsing.nodes import CallExpr
        rdf = self._run([
            DeclareStmt("r", CallExpr("ghost", []), MutabilityFlavor.CONST_CONST),
        ])
        assert rdf.get_variable("r") == "undefined"

    def test_call_stmt(self, capsys):
        from gom.parsing.nodes import FunctionDeclStmt, CallStmt, CallExpr
        self._run([
            FunctionDeclStmt("greet", [], [PrintStmt(LiteralExpr("hello"))]),
            CallStmt(CallExpr("greet", [])),
        ])
        assert "hello" in capsys.readouterr().out

    # ── IfStmt ────────────────────────────────────────────────────────────────

    def test_if_true_branch(self, capsys):
        from gom.parsing.nodes import IfStmt
        self._run([IfStmt(LiteralExpr(True), [PrintStmt(LiteralExpr("yes"))], [])])
        assert "yes" in capsys.readouterr().out

    def test_if_false_branch(self, capsys):
        from gom.parsing.nodes import IfStmt
        self._run([IfStmt(LiteralExpr(False),
                          [PrintStmt(LiteralExpr("yes"))],
                          [PrintStmt(LiteralExpr("no"))])])
        assert "no" in capsys.readouterr().out

    def test_if_maybe_truthy(self, capsys):
        from gom.parsing.nodes import IfStmt
        self._run([IfStmt(LiteralExpr("maybe"), [PrintStmt(LiteralExpr("ran"))], [])])
        assert "ran" in capsys.readouterr().out

    # ── IncrementStmt / DecrementStmt ─────────────────────────────────────────

    def test_increment(self):
        from gom.parsing.nodes import IncrementStmt
        rdf = self._run([
            DeclareStmt("score", LiteralExpr(5), MutabilityFlavor.VAR_VAR),
            IncrementStmt("score"),
        ])
        assert rdf.get_variable("score") == 6

    def test_decrement(self):
        from gom.parsing.nodes import DecrementStmt
        rdf = self._run([
            DeclareStmt("hp", LiteralExpr(10), MutabilityFlavor.VAR_VAR),
            DecrementStmt("hp"),
        ])
        assert rdf.get_variable("hp") == 9

    # ── NoopStmt ──────────────────────────────────────────────────────────────

    def test_noop_does_nothing(self, capsys):
        from gom.parsing.nodes import NoopStmt
        self._run([NoopStmt()])
        assert capsys.readouterr().out == ""

    # ── ArrayDestructureStmt ──────────────────────────────────────────────────

    def test_signal_destructure(self):
        from gom.parsing.nodes import ArrayDestructureStmt
        rdf = self._run([
            ArrayDestructureStmt(
                ["getter", "setter"],
                SignalExpr(LiteralExpr(0)),
                MutabilityFlavor.VAR_VAR,
            ),
        ])
        getter = rdf.get_variable("getter")
        setter = rdf.get_variable("setter")
        # Both should be callable and point to the same handler
        assert callable(getter)
        assert callable(setter)
        setter(42)
        assert getter() == 42

    def test_destructure_extra_names_get_undefined(self):
        from gom.parsing.nodes import ArrayDestructureStmt, ArrayLiteralExpr
        rdf = self._run([
            ArrayDestructureStmt(
                ["a", "b", "c"],
                LiteralExpr([10, 20]),   # only 2 elements
                MutabilityFlavor.CONST_CONST,
            ),
        ])
        assert rdf.get_variable("c") == "undefined"

    # ── FileSeparatorStmt ─────────────────────────────────────────────────────

    def test_file_separator_clears_local_timelines(self):
        from gom.parsing.nodes import FileSeparatorStmt
        rdf = self._run([
            DeclareStmt("x", LiteralExpr(1), MutabilityFlavor.VAR_VAR),
            FileSeparatorStmt(),
        ])
        with pytest.raises(NameError):
            rdf.get_variable("x")

    def test_file_separator_keeps_globals(self):
        from gom.parsing.nodes import FileSeparatorStmt
        rdf = fresh()
        rdf.declare_variable("eternal", 42, MutabilityFlavor.CONST_CONST_CONST)
        GOMExecutor(rdf).execute_program([FileSeparatorStmt()])
        assert rdf.get_variable("eternal") == 42

    # ── ClassDeclStmt / NewInstanceExpr ──────────────────────────────────────

    def test_class_decl_and_instantiate(self):
        from gom.parsing.nodes import ClassDeclStmt, NewInstanceExpr
        rdf = self._run([
            ClassDeclStmt("Player", []),
            DeclareStmt("p", NewInstanceExpr("Player"), MutabilityFlavor.CONST_CONST),
        ])
        player = rdf.get_variable("p")
        assert player["__class__"] == "Player"

    def test_second_instance_raises(self):
        from gom.parsing.nodes import ClassDeclStmt, NewInstanceExpr
        with pytest.raises(RuntimeError, match="one 'Player' instance"):
            self._run([
                ClassDeclStmt("Player", []),
                DeclareStmt("p1", NewInstanceExpr("Player"), MutabilityFlavor.CONST_CONST),
                DeclareStmt("p2", NewInstanceExpr("Player"), MutabilityFlavor.CONST_CONST),
            ])

    # ── Spec example: numeric variable names ──────────────────────────────────

    def test_numeric_variable_name_overrides_literal(self):
        """const const 5 = 4!  →  print(2 + 2 === 5)!  // true"""
        rdf = self._run([
            DeclareStmt("5", LiteralExpr(4), MutabilityFlavor.CONST_CONST),
            DeclareStmt("r",
                        EqualityExpr(
                            ArithmeticExpr(LiteralExpr(2), '+', LiteralExpr(2)),
                            VariableExpr("5"),
                            2,    # ===
                        ),
                        MutabilityFlavor.CONST_CONST),
        ])
        assert rdf.get_variable("r") is True


# ── Framework-completion fixes ────────────────────────────────────────────────

class TestDeleteLawOnExpressions:
    """
    Per spec: ``delete 3!`` → ``print(2 + 1)! // Error: 3 has been deleted``

    Any expression that *produces* a deleted value must raise, not just variable
    lookups at declaration time.
    """

    def _run(self, stmts):
        rdf = fresh()
        GOMExecutor(rdf).execute_program(stmts)
        return rdf

    def test_deleted_literal_in_arithmetic_raises(self):
        with pytest.raises(RuntimeError, match="3.*deleted"):
            self._run([
                DeleteStmt(LiteralExpr(3)),
                DeclareStmt("r", ArithmeticExpr(LiteralExpr(2), '+', LiteralExpr(1)),
                            MutabilityFlavor.CONST_CONST),
            ])

    def test_deleted_string_value_raises(self):
        with pytest.raises(RuntimeError, match="'hello'.*deleted"):
            self._run([
                DeleteStmt(LiteralExpr("hello")),
                PrintStmt(LiteralExpr("hello")),
            ])

    def test_non_deleted_value_is_fine(self):
        rdf = self._run([
            DeleteStmt(LiteralExpr(3)),
            DeclareStmt("r", LiteralExpr(4), MutabilityFlavor.CONST_CONST),
        ])
        assert rdf.get_variable("r") == 4

    def test_deleted_boolean_raises(self):
        with pytest.raises(RuntimeError, match="True.*deleted"):
            self._run([
                DeleteStmt(LiteralExpr(True)),
                PrintStmt(LiteralExpr(True)),
            ])

    def test_unhashable_value_not_crashed(self):
        """Deleting a list value (unhashable) should not crash the engine."""
        rdf = self._run([
            DeclareStmt("x", LiteralExpr(5), MutabilityFlavor.VAR_VAR),
        ])
        # unhashable entity — delete_entity silently skips it
        rdf.delete_entity([1, 2, 3])
        assert rdf.get_variable("x") == 5


class TestNextKeywordLocalScope:
    """_get_next_from_timeline must find future values in local scope frames."""

    def test_next_finds_local_future_value(self):
        """Inside a function scope, ``next x`` should see the future local assignment."""
        from gom.parsing.nodes import FunctionDeclStmt, ReturnStmt
        rdf = fresh()
        # Manually push a scope and pre-populate a future timeline point
        rdf.push_scope()
        rdf.declare_variable("x", 5, MutabilityFlavor.VAR_VAR)
        # Simulate a future assignment by advancing the line counter
        saved_line = rdf.current_line
        rdf.current_line = 99
        rdf.set_variable("x", 99)
        rdf.current_line = saved_line
        # next x from line 0 should see the point at line 99
        future_val = rdf._get_next_from_timeline("x")
        assert future_val == 99
        rdf.pop_scope()

    def test_next_returns_none_when_no_future_exists(self):
        rdf = fresh()
        rdf.push_scope()
        rdf.declare_variable("y", 7, MutabilityFlavor.VAR_VAR)
        # No future point — should return None
        assert rdf._get_next_from_timeline("y") is None
        rdf.pop_scope()


class TestEnvironmentFacade:
    """environment.py must export all public framework components."""

    def test_gomobject_exported(self):
        from gom.environment import GOMObject
        obj = GOMObject({"a": 1})
        assert obj.a == 1

    def test_all_exports_present(self):
        import gom.environment as env
        for name in [
            "MutabilityFlavor", "LifetimeUnit",
            "TemporalAnchor", "TimelinePoint", "VariableTimeline",
            "GOMArray", "GOMObject",
            "RealityDistortionField", "GOMExecutor",
        ]:
            assert hasattr(env, name), f"environment.py is missing export: {name}"


class TestDebugReality:
    """debug_reality must display local scope variables without crashing."""

    def test_debug_reality_runs_without_error(self, capsys):
        rdf = fresh()
        rdf.declare_variable("x", 42, MutabilityFlavor.VAR_VAR)
        rdf.debug_reality()
        out = capsys.readouterr().out
        assert "REALITY DEBUG DUMP" in out
        assert "x" in out

    def test_debug_reality_shows_local_scopes(self, capsys):
        rdf = fresh()
        rdf.push_scope()
        rdf.declare_variable("local_val", 99, MutabilityFlavor.VAR_VAR)
        rdf.debug_reality()
        out = capsys.readouterr().out
        assert "local_val" in out
        assert "Local Scope" in out
        rdf.pop_scope()

    def test_debug_reality_no_local_scopes_no_frame_section(self, capsys):
        rdf = fresh()
        rdf.debug_reality()
        out = capsys.readouterr().out
        assert "Local Scope" not in out


class TestDeadCodeRemoved:
    """_assign_timeline must no longer exist (it was dead code)."""

    def test_assign_timeline_removed(self):
        rdf = fresh()
        assert not hasattr(rdf, "_assign_timeline"), (
            "_assign_timeline is dead code and should have been removed"
        )

    def test_declare_variable_scope_aware_replaces_assign_timeline(self):
        """
        Verify that ``declare_variable`` correctly stores declarations in the
        innermost local scope when inside a function — which is the
        functionality that ``_assign_timeline`` was intended to provide.
        """
        rdf = fresh()
        # Global declaration
        rdf.declare_variable("x", 1, MutabilityFlavor.VAR_VAR)

        # Push a scope and declare a shadowing 'x' locally
        rdf.push_scope()
        rdf.declare_variable("x", 99, MutabilityFlavor.VAR_VAR)

        # Inside the scope 'x' resolves to the local shadow
        assert rdf.get_variable("x") == 99

        # After popping, the global 'x' is visible again
        rdf.pop_scope()
        assert rdf.get_variable("x") == 1

        # The inner declaration must NOT have written to the global timeline
        assert rdf.timelines["x"].get_at_time(rdf.current_line, rdf.current_timestamp).value == 1

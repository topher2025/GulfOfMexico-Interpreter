import time
from typing import Any, Dict, List, Optional, Tuple, Callable
from collections import defaultdict
from gom.runtime.types import MutabilityFlavor, LifetimeUnit
from gom.runtime.temporal import TemporalAnchor, TimelinePoint, VariableTimeline
from gom.runtime.logic import evaluate_equality, resolve_number_word
from gom.runtime.strings import interpolate_string

# Sentinel used by use_signal() to distinguish "no argument passed" from
# a valid falsy value (None, 0, False, …).  Defined at module level so the
# same object identity is preserved for the lifetime of the interpreter.
_SIGNAL_UNSET = object()

class RealityDistortionField:
    """
    The main temporal reality engine of the Gulf of Mexico.
    
    This engine manages all variables (manifestations) across all timelines
    in all realities. It handles temporal traversal, mutability constraints,
    and reality-wide state modifications.
    """
    
    # Process-level storage for global/eternal manifestations
    GLOBAL_IMMUTABLES: Dict[str, Any] = {}

    # Standard constant for undefined manifestations
    UNDEFINED = "undefined"

    def __init__(self, debug: bool = False):
        """
        Initialize a new Reality Distortion Field (RDF).
        
        Args:
            debug: If enabled, detailed reality state shifts will be logged.
        """
        self.debug = debug
        # Map variable names to their timelines
        self.timelines: Dict[str, VariableTimeline] = {}
        
        # Track current position in time-space
        self.current_line = 0
        self.time_offset = 0.0 # Support for Date.now() shifts
        self.program_start_time = time.time()
        
        # For reverse execution
        self.execution_direction = 1  # 1 = forward, -1 = backward
        
        # Queue of variables with negative lifetimes (future declarations)
        self.temporal_anomalies: List[Tuple[str, TimelinePoint]] = []
        
        # Observers for the 'when' keyword (mutation watching)
        self.mutation_observers: Dict[str, List[Tuple[Any, Callable]]] = defaultdict(list)
        
        # For 'next' keyword - awaiting future values
        self.future_watchers: Dict[str, List[Callable]] = defaultdict(list)
        
        # Track deleted primitives and keywords
        self.deleted_entities = set()

        # ── Scope stack ─────────────────────────────────────────────────────
        # Each frame is a dict[name → VariableTimeline] representing local
        # variables for a function invocation.  The innermost frame is checked
        # first; global timelines (self.timelines) are the outermost scope.
        self._local_scopes: List[Dict[str, "VariableTimeline"]] = []

        # ── Function registry ────────────────────────────────────────────────
        # Maps function name → (params, body_stmts, is_async)
        self._functions: Dict[str, Any] = {}

        # ── Class registry ───────────────────────────────────────────────────
        # Maps class name → (body_stmts,)
        self._classes: Dict[str, Any] = {}
        # Tracks which classes have already been instantiated (single-instance rule)
        self._class_instances: Dict[str, Any] = {}
        
        # Manifest standard constants into the RDF
        self._manifest_constants()

    # ── Scope helpers ─────────────────────────────────────────────────────────

    def push_scope(self) -> None:
        """Open a new local variable scope (called at the start of a function body)."""
        self._local_scopes.append({})

    def pop_scope(self) -> None:
        """Close the innermost local scope (called when a function returns)."""
        if self._local_scopes:
            self._local_scopes.pop()

    def _resolve_timeline(self, name: str) -> Optional["VariableTimeline"]:
        """Search for a timeline by name from innermost scope to global."""
        for frame in reversed(self._local_scopes):
            if name in frame:
                return frame[name]
        return self.timelines.get(name)

    # ── Function registry ──────────────────────────────────────────────────────

    def declare_function(
        self,
        name: str,
        params: List[str],
        body: Any,           # List[Stmt] or a single expression-stmt
        is_async: bool = False,
    ) -> None:
        """
        Register a function definition in the reality engine.

        The body is an opaque list of AST statement nodes; the executor is
        responsible for evaluating it when the function is called.
        """
        self._functions[name] = (params, body, is_async)
        if self.debug:
            print(f"📐 Function '{name}' manifested with params {params}")

    def get_function_def(self, name: str) -> Any:
        """
        Retrieve a registered function definition.

        Returns a ``(params, body, is_async)`` tuple, or raises ``NameError``
        if the function has not been declared.
        """
        if name not in self._functions:
            raise NameError(f"Function '{name}' has not been manifested in this reality")
        return self._functions[name]

    # ── Class registry ─────────────────────────────────────────────────────────

    def declare_class(self, name: str, body: Any) -> None:
        """
        Register a class definition.

        Per spec, each class can only ever have one instance.  The body is an
        opaque list of AST nodes; the executor processes it when instantiating.
        """
        self._classes[name] = body
        if self.debug:
            print(f"🏛  Class '{name}' registered in the cosmic registry")

    def instantiate_class(self, class_name: str) -> Any:
        """
        Create an instance of a class — enforcing the single-instance rule.

        Raises ``RuntimeError`` if a second instance would be created.
        Returns the existing instance object (a ``GOMObject``).
        """
        if class_name not in self._classes:
            raise NameError(f"Class '{class_name}' has not been defined")
        if class_name in self._class_instances:
            raise RuntimeError(
                f"Error: Can't have more than one '{class_name}' instance!"
            )
        # Import here to avoid circular import at module level
        from gom.stdlib.collections import GOMObject
        instance = GOMObject()
        instance["__class__"] = class_name
        self._class_instances[class_name] = instance
        if self.debug:
            print(f"🏛  '{class_name}' instantiated (only instance in this reality)")
        return instance

    def _manifest_constants(self):
        """Initialize the sacred constants required for any stable reality."""
        self.declare_variable("true", True, MutabilityFlavor.CONST_CONST)
        self.declare_variable("false", False, MutabilityFlavor.CONST_CONST)
        # Maybe: stored as 1.5 bits, but manifested as a string for human comfort
        self.declare_variable("maybe", "maybe", MutabilityFlavor.CONST_CONST)
        # Undefined: returned by things like division by zero
        self.declare_variable("undefined", self.UNDEFINED, MutabilityFlavor.CONST_CONST)
        
        # Date.now() support: initialized as a special manifestation
        self.declare_variable("Date.now", self.current_timestamp, MutabilityFlavor.VAR_VAR)
        # Note: English number words (one, two, three, …, one million, …) are
        # resolved dynamically by resolve_number_word() in get_variable(), so
        # they do not need to be pre-declared here.  This means every number
        # word works out of the box and users can still override them with an
        # explicit declaration (per the spec's variable-overloading rules).
    
    @classmethod
    def clear_globals(cls):
        """
        Remove all eternal manifestations from the global registry.

        Intended for use in tests only — in production, eternal constants should
        never be cleared (that is the whole point of ``const const const``).
        """
        cls.GLOBAL_IMMUTABLES.clear()

    def __enter__(self):
        """RDF activation within a reality scope."""
        if self.debug:
            print("🌌 Reality initialized...")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """RDF teardown and reality collapsing."""
        if self.debug:
            print("🌌 Reality collapsing...")
        return False
    
    def advance_time(self, lines: int = 1):
        """
        Move the execution cursor across the line-space and update real-time coordinates.
        """
        self.current_line += lines * self.execution_direction
    
    @property
    def current_timestamp(self) -> float:
        """The relative program-time (in seconds) shifted by time offsets."""
        return (time.time() - self.program_start_time) + self.time_offset

    def shift_time(self, offset_seconds: float):
        """
        Adjust the clocks within this RDF reality.
        
        Args:
            offset_seconds: numeric value to shift time (negative or positive).
        """
        self.time_offset += offset_seconds
        if self.debug:
            print(f"⏰ Clocks shifted by {offset_seconds}s. New relative time: {self.current_timestamp:.2f}s")
    
    def reverse_execution(self):
        """Reverse the flow of time within this RDF."""
        self.execution_direction *= -1
        if self.debug:
            direction = "FORWARD" if self.execution_direction > 0 else "BACKWARD"
            print(f"⏪ Execution reversed! Now going {direction}")
    
    def declare_variable(
        self,
        name: str,
        value: Any,
        mutability: MutabilityFlavor,
        lifetime_value: Optional[float] = None,
        lifetime_unit: Optional[LifetimeUnit] = None,
        exclamation_marks: int = 1
    ):
        """
        Anchor a new variable manifestation to reality at current coordinates.
        
        Args:
            name: The unicode handle for the variable.
            value: The data to manifestation.
            mutability: Sacred rules for this manifestation.
            lifetime_value: Numeric duration.
            lifetime_unit: Unit for measuring duration.
            exclamation_marks: Priority of this reality manifestation.
        """
        # Global Eternal check
        if name in self.GLOBAL_IMMUTABLES:
            raise RuntimeError(f"Cannot redeclare eternal manifestation '{name}'")

        if mutability == MutabilityFlavor.CONST_CONST_CONST:
            self.GLOBAL_IMMUTABLES[name] = value
            if self.debug:
                print(f"🌍 {name} has become an eternal constant.")

        # Existence validation
        try:
            if value in self.deleted_entities:
                raise RuntimeError(f"Error: {value!r} has been deleted from reality")
        except TypeError:
            pass # Unhashable types cannot be deleted individually (use their name)
        
        anchor = TemporalAnchor(
            line_number=self.current_line,
            timestamp=self.current_timestamp,
            real_time=time.time()
        )
        
        point = TimelinePoint(
            value=value,
            anchor=anchor,
            mutability=mutability,
            lifetime_value=lifetime_value,
            lifetime_unit=lifetime_unit,
            exclamation_priority=exclamation_marks
        )
        
        if lifetime_unit == LifetimeUnit.NEGATIVE_LINES:
            self.temporal_anomalies.append((name, point))
        
        # Store in the innermost local scope if inside a function, else global.
        # We always *declare* into the current scope (creating a shadow if a
        # global with the same name exists) so that local variables are properly
        # isolated from the outer reality.
        if self._local_scopes:
            frame = self._local_scopes[-1]
            if name not in frame:
                frame[name] = VariableTimeline(name)
            tl = frame[name]
        else:
            if name not in self.timelines:
                self.timelines[name] = VariableTimeline(name)
            tl = self.timelines[name]
        
        tl.add_point(point)
        
        # Check mutation observers for 'when' keyword
        self._check_mutation_observers(name, value)
        
        # Future watcher notification
        if name in self.future_watchers:
            for callback in self.future_watchers[name]:
                callback(value)
            self.future_watchers[name].clear()
    
    def get_variable(self, name: str, temporal_mode: str = "current") -> Any:
        """
        Retrieve a variable value from the time-space continuum.
        
        Args:
            name: The unicode handle of the variable to retrieve.
            temporal_mode: The temporal perspective to use ("current", "previous", "next").
            
        Returns:
            The manifestation of the variable value.
        """
        # Special handling for Date.now() and 'current' keyword
        if name == "Date.now":
            return self.current_timestamp

        if temporal_mode == "next":
            # First try a pre-scheduled future value already in the timeline.
            next_val = self._get_next_from_timeline(name)
            if next_val is not None:
                return next_val
            return self._await_next_manifestation(name)

        # Check temporal anomalies first
        for anomaly_name, point in self._get_active_anomalies(name):
            if temporal_mode == "current":
                return point.value
        
        tl = self._resolve_timeline(name)
        if tl is None:
            # Check global manifestations
            if name in self.GLOBAL_IMMUTABLES:
                return self.GLOBAL_IMMUTABLES[name]
            # Resolve English number words (one, two, twenty-three, one million…)
            number_value = resolve_number_word(name)
            if number_value is not None:
                return number_value
            raise NameError(f"Manifestation '{name}' does not exist in this reality frame")
        
        timeline = tl
        
        if temporal_mode == "current":
            point = timeline.get_at_time(self.current_line, self.current_timestamp)
            if point is None:
                raise RuntimeError(f"Manifestation '{name}' has evaporated from reality")
            return point.value
        
        elif temporal_mode == "previous":
            point = timeline.get_previous(self.current_line, self.current_timestamp)
            if point is None:
                raise RuntimeError(f"No previous manifestation exists for '{name}'")
            return point.value

    def _get_active_anomalies(self, name: str):
        """Generator for active temporal anomalies matching the name."""
        for anomaly_name, point in self.temporal_anomalies:
            if anomaly_name == name and point.is_alive(self.current_line, self.current_timestamp):
                yield anomaly_name, point

    def _get_next_from_timeline(self, name: str) -> Optional[Any]:
        """
        Look ahead in the timeline for the nearest future manifestation of *name*.

        Searches local scope frames (innermost first) then global timelines.
        Returns the value of the earliest point with an anchor line number greater
        than the current line, or None if none exists.
        """
        tl = self._resolve_timeline(name)
        if tl is None:
            return None
        future_points = [
            p for p in tl.timeline_points
            if p.anchor.line_number > self.current_line
        ]
        if future_points:
            future_points.sort(key=lambda p: p.anchor.line_number)
            return future_points[0].value
        return None

    def _await_next_manifestation(self, name: str) -> Any:
        """Logic for the 'next' keyword: blocks until the next manifestation occurs."""
        import threading
        event = threading.Event()
        result = [None]
        
        def callback(val):
            result[0] = val
            event.set()
        
        self.future_watchers[name].append(callback)
        
        # In this interpreter context, we assume single-threaded execution for now.
        # If we block here, we might deadlock if the setter is on the same thread.
        # So for 'rough draft', we'll print a warning or raise if it would deadlock.
        if self.debug:
            print(f"⌛ Reality is waiting for the next manifestation of '{name}'...")
        
        # For simulation purposes in tests, we'll allow a short timeout
        # In production, this would be a proper async wait.
        signaled = event.wait(timeout=0.001) 
        if not signaled:
             # If it didn't happen instantly (which it wouldn't), we return a marker 
             # that the executor would handle.
             return f"<Future manifestation of {name}>"
        return result[0]
    
    def set_variable(self, name: str, value: Any):
        """
        Mutate a variable's binding in the current timeline.
        
        Args:
            name: The handle to reassign.
            value: The new manifestation.
        """
        # Special handling for Date.now()
        if name == "Date.now":
            # Setting Date.now shifts the reality's time offset
            new_offset = value - (time.time() - self.program_start_time)
            self.time_offset = new_offset
            return

        if name in self.GLOBAL_IMMUTABLES:
            raise RuntimeError(f"Cannot reassign eternal manifestation '{name}'")

        timeline = self._resolve_timeline(name)
        if timeline is None:
            raise NameError(f"Cannot reassign undefined handle '{name}'")
        current_point = timeline.get_at_time(self.current_line, self.current_timestamp)
        
        if current_point is None:
            raise RuntimeError(f"Manifestation '{name}' has evaporated")
        
        mutability = current_point.mutability
        
        if mutability in (MutabilityFlavor.CONST_CONST, MutabilityFlavor.CONST_CONST_CONST):
            raise RuntimeError(f"Cannot reassign {mutability.value} manifestation '{name}'")
        
        if mutability == MutabilityFlavor.CONST_VAR:
            raise RuntimeError(f"Cannot reassign const var handle '{name}' (but you can mutate its value)")
        
        new_anchor = TemporalAnchor(
            line_number=self.current_line,
            timestamp=self.current_timestamp
        )
        
        new_point = TimelinePoint(
            value=value,
            anchor=new_anchor,
            mutability=mutability,
            lifetime_value=current_point.lifetime_value,
            lifetime_unit=current_point.lifetime_unit,
            exclamation_priority=current_point.exclamation_priority
        )
        
        timeline.add_point(new_point)
        
        # Trigger observers
        self._check_mutation_observers(name, value)
    
    def _check_mutation_observers(self, name: str, value: Any):
        """Verify if any 'when' observers are triggered by this manifestation shift.
        
        Per spec, ``when (health = 0)`` uses the single-equals loose equality
        operator (GOM precision 0), not Python identity or strict equality.
        """
        if name in self.mutation_observers:
            for target_val, callback in self.mutation_observers[name]:
                if evaluate_equality(value, target_val, 0):
                    callback()

    def register_observer(self, name: str, target_value: Any, callback: Callable):
        """
        Register a 'when' keyword observer for a specific variable handle.
        """
        self.mutation_observers[name].append((target_value, callback))
        if self.debug:
            print(f"👀 Observer registered for '{name}' manifesting as {target_value!r}")
    
    def use_signal(self, initial_value: Any) -> Tuple[Callable, Callable]:
        """
        The 'use' keyword - creates a signal getter/setter pair.

        Per spec, getter and setter are the *same* function:
        - Called with no arguments → returns current value
        - Called with any single argument → sets and returns the new value

        Both elements of the returned tuple point to the same handler, so::

            const var [getScore, setScore] = use(0)!
            getScore(9)!   // also sets
            setScore()?    // also gets
        """
        _UNSET = _SIGNAL_UNSET   # module-level sentinel — consistent identity across calls
        state = [initial_value]

        def signal_handler(new_value=_UNSET):
            if new_value is not _UNSET:
                state[0] = new_value
                if self.debug:
                    print(f"📡 Signal mutated: {new_value!r}")
                return new_value
            return state[0]

        # Both getter and setter point to the same handler (per spec)
        return signal_handler, signal_handler
    
    def mutate_variable(self, name: str, operation: Callable):
        """
        Perform an in-place mutation of a value in the current timeline.
        
        Args:
            name: The handle whose value is being mutated.
            operation: A callable that accepts the value for in-place modification.
        """
        if name in self.GLOBAL_IMMUTABLES:
            raise RuntimeError(f"Cannot mutate eternal manifestation '{name}'")

        timeline = self._resolve_timeline(name)
        if timeline is None:
            raise NameError(f"Cannot mutate undefined manifestation '{name}'")
        current_point = timeline.get_at_time(self.current_line, self.current_timestamp)
        
        if current_point is None:
            raise RuntimeError(f"Manifestation '{name}' has evaporated")
        
        mutability = current_point.mutability
        
        if mutability in (MutabilityFlavor.CONST_CONST, MutabilityFlavor.VAR_CONST, MutabilityFlavor.CONST_CONST_CONST):
            raise RuntimeError(f"Cannot mutate {mutability.value} manifestation '{name}'")
        
        # Perform in-place mutation
        operation(current_point.value)

        # Trigger observers after mutation
        self._check_mutation_observers(name, current_point.value)
    
    def delete_entity(self, entity: Any):
        """
        Yeet an entity from existence across all of reality.
        
        Args:
            entity: The primitive, keyword, or object to delete.
        """
        # Support for 'delete delete!'
        if entity == "delete":
            # Invalidate this method
            def deleted_delete(*args, **kwargs):
                raise RuntimeError("Error: 'delete' has been deleted from reality.")
            self.delete_entity = deleted_delete
            self.deleted_entities.add("delete")
            if self.debug:
                print("💀 The concept of 'delete' has been deleted from reality.")
            return

        # Deleting a handle (e.g. 'class', 'print', or a variable name)
        if isinstance(entity, str):
            # Search scope frames as well as global timelines
            deleted_from_scope = False
            for frame in reversed(self._local_scopes):
                if entity in frame:
                    del frame[entity]
                    deleted_from_scope = True
                    break
            if not deleted_from_scope:
                if entity in self.timelines:
                    del self.timelines[entity]
            if entity in self.GLOBAL_IMMUTABLES:
                del self.GLOBAL_IMMUTABLES[entity]
        
        try:
            self.deleted_entities.add(entity)
        except TypeError:
            # Unhashable types (like lists/dicts) - we usually delete them by handle
            # but if the user wants to delete the actual value across all of reality,
            # we'd need to track them. For now, we skip if unhashable.
            pass

        if self.debug:
            print(f"💀 {entity!r} has been deleted from reality.")
    
    def is_deleted(self, entity: Any) -> bool:
        """Check if an entity has been permanently removed from existence."""
        return entity in self.deleted_entities

    def evaluate_equality(self, left: Any, right: Any, precision: int = 1) -> bool:
        """
        GOM-specific equality logic based on precision level.
        Delegate to specialized logic module.
        """
        return evaluate_equality(left, right, precision)

    def interpolate_string(self, template: str, context: Dict[str, Any]) -> str:
        """
        Interpolate string with regional currency and typographical norms.
        Delegate to specialized string module.
        """
        return interpolate_string(template, context, self.UNDEFINED)

    def debug_reality(self):
        """Print the current state of all reality"""
        print("\n" + "="*70)
        print("🌌 REALITY DEBUG DUMP 🌌")
        print("="*70)
        print(f"Current Line: {self.current_line}")
        print(f"Current Timestamp: {self.current_timestamp:.2f}s")
        print(f"Execution Direction: {'→' if self.execution_direction > 0 else '←'}")
        print(f"Temporal Anomalies: {len(self.temporal_anomalies)}")
        print(f"Deleted Entities: {self.deleted_entities}")
        print(f"Global Immutables: {list(self.GLOBAL_IMMUTABLES.keys())}")
        print(f"\nActive Timelines: {len(self.timelines)}")

        for name, timeline in self.timelines.items():
            current = timeline.get_at_time(self.current_line, self.current_timestamp)
            if current:
                print(f"  • {name} = {current.value!r} ({current.mutability.value})")
            else:
                print(f"  • {name} = [EXPIRED] 💀")

        if self._local_scopes:
            print(f"\nLocal Scope Frames: {len(self._local_scopes)}")
            for depth, frame in enumerate(self._local_scopes):
                print(f"  Frame {depth} (innermost = {depth == len(self._local_scopes) - 1}):")
                for name, timeline in frame.items():
                    current = timeline.get_at_time(self.current_line, self.current_timestamp)
                    if current:
                        print(f"    • {name} = {current.value!r} ({current.mutability.value})")
                    else:
                        print(f"    • {name} = [EXPIRED] 💀")

        print("="*70 + "\n")

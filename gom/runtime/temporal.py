import time
from typing import Any, List, Optional
from dataclasses import dataclass, field
from gom.runtime.types import MutabilityFlavor, LifetimeUnit

@dataclass(frozen=True)
class TemporalAnchor:
    """
    A specific coordinate in the time-space continuum where a variable was anchored.
    
    Attributes:
        line_number: The execution line number where the variable was anchored.
        timestamp: The relative program-time (in seconds) since reality initialized.
        real_time: The system wall-clock time (seconds) of anchoring.
    """
    line_number: int
    timestamp: float
    real_time: float = field(default_factory=time.time)
    
    def __repr__(self):
        return f"TemporalAnchor(line={self.line_number}, relative={self.timestamp:.2f}s, wall={self.real_time:.2f})"


@dataclass(frozen=True)
class TimelinePoint:
    """
    A specific point on a variable's timeline - represents a single value manifestation.
    
    Attributes:
        value: The actual data being stored.
        anchor: The temporal coordinate of this point's manifestation.
        mutability: The sacred mutability rules governing this point.
        lifetime_value: The numeric duration of existence.
        lifetime_unit: The unit used for measuring the lifetime.
        exclamation_priority: The priority derived from exclamation marks (higher = more real).
    """
    value: Any
    anchor: TemporalAnchor
    mutability: MutabilityFlavor
    lifetime_value: Optional[float] = None
    lifetime_unit: Optional[LifetimeUnit] = None
    exclamation_priority: int = 1
    
    def is_alive(self, current_line: int, current_time: float) -> bool:
        """
        Determine if this timeline point currently exists in the manifestation of reality.
        
        Args:
            current_line: The current line number of the execution engine.
            current_time: The current relative time since program start (shifted).
            
        Returns:
            True if the point exists in the current reality frame.
        """
        if self.lifetime_unit == LifetimeUnit.INFINITY:
            return True
        
        if self.lifetime_unit == LifetimeUnit.NEGATIVE_LINES:
            # Variable hoisting: exists for |lifetime_value| lines before creation.
            # e.g. anchor=5, lifetime=-1 → alive at line 4 only
            # e.g. anchor=5, lifetime=-3 → alive at lines 2, 3, 4
            start = self.anchor.line_number + int(self.lifetime_value or -1)
            return start <= current_line < self.anchor.line_number
        
        if self.lifetime_unit == LifetimeUnit.LINES:
            # Exists for a fixed number of execution steps
            return self.anchor.line_number <= current_line <= (self.anchor.line_number + (self.lifetime_value or 0))
        
        if self.lifetime_unit == LifetimeUnit.SECONDS:
            # Duration based on relative program time (which can be shifted)
            elapsed = current_time - self.anchor.timestamp
            return elapsed <= (self.lifetime_value or 0)
        
        # Standard: persistent until manual deletion or program end
        return current_line >= self.anchor.line_number
    
    def __repr__(self):
        status = "PERSISTENT" if not self.lifetime_unit else f"{self.lifetime_value} {self.lifetime_unit.value}"
        return f"TimelinePoint(value={self.value!r}, priority={self.exclamation_priority}, life={status})"


@dataclass
class VariableTimeline:
    """
    A holistic record of all values manifestations assigned to a specific variable name.
    
    Timelines are multi-dimensional, holding multiple points that may be active 
    simultaneously. Selection is performed based on exclamation priority.
    """
    name: str
    timeline_points: List[TimelinePoint] = field(default_factory=list)
    
    def add_point(self, point: TimelinePoint):
        """
        Incorporate a new temporal manifestation into the timeline.
        Timelines are automatically optimized by priority sorting.
        """
        self.timeline_points.append(point)
        # Higher exclamation count = higher reality priority.
        # Inverted exclamation mark (¡) can be used for negative priority.
        # Secondary sort by line number (descending) to ensure most recent is prioritized.
        # Tertiary sort by real_time so that multiple assignments on the same line
        # resolve to the most recently created point (avoids stable-sort ambiguity).
        # Stability is preserved for points with identical priority, line, and time.
        self.timeline_points.sort(
            key=lambda p: (p.exclamation_priority, p.anchor.line_number, p.anchor.real_time),
            reverse=True,
        )
    
    def get_at_time(self, line: int, timestamp: float) -> Optional[TimelinePoint]:
        """
        Extract the most dominant reality manifestation for the given time-space coordinates.
        
        Args:
            line: current execution line.
            timestamp: relative program runtime.
        """
        for point in self.timeline_points:
            if point.is_alive(line, timestamp):
                return point
        return None
    
    def get_previous(self, line: int, timestamp: float) -> Optional[TimelinePoint]:
        """
        Temporal archaeology: retrieve the second-most dominant active manifestation.
        """
        found_first = False
        for point in self.timeline_points:
            if point.is_alive(line, timestamp):
                if not found_first:
                    found_first = True
                    continue
                return point
        return None
    
    def get_all_history(self, line: int, timestamp: float) -> List[TimelinePoint]:
        """
        Exhaustive audit of all manifestations currently active in this reality frame.
        """
        return [p for p in self.timeline_points if p.is_alive(line, timestamp)]

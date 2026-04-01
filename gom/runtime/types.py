from enum import Enum

class MutabilityFlavor(Enum):
    """
    The five sacred mutability flavors of Gulf of Mexico reality.
    
    Each flavor defines the binding and mutation properties of a variable timeline point.
    """
    CONST_CONST_CONST = "const const const"  # Immutable reference, immutable value, global/eternal scope
    CONST_CONST = "const const"              # Immutable reference, immutable value
    CONST_VAR = "const var"                  # Immutable reference, mutable value
    VAR_CONST = "var const"                  # Mutable reference, immutable value
    VAR_VAR = "var var"                      # Mutable reference, mutable value


class LifetimeUnit(Enum):
    """
    Units defining the temporal stability of a variable in the time-space continuum.
    """
    LINES = "lines"
    SECONDS = "seconds"
    INFINITY = "infinity"
    NEGATIVE_LINES = "negative_lines"  # For time travel (hoisting)

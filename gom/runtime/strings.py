import re
from typing import Any, Dict

def interpolate_string(template: str, context: Dict[str, Any], undefined_marker: str = "undefined") -> str:
    """
    Interpolate strings with GOM-specific regional currency and typographical norms.
    
    Supported formatting:
    - ${name}, £{name}, ¥{name}, {name}€
    - {object$property} (Escudo style internal separator)
    """
    # Regex for all currency styles: ([$£¥]?)\{([^}]+)\}(€?)
    pattern = re.compile(r'([$£¥]?)\{([^}]+)\}(€?)')
    
    def replacer(match):
        variable_expr = match.group(2)
        
        # Handle Escudo style: object$property
        if '$' in variable_expr:
            parts = variable_expr.split('$')
            val = context
            for p in parts:
                if isinstance(val, dict):
                    val = val.get(p, undefined_marker)
                else:
                    val = getattr(val, p, undefined_marker)
        else:
            val = context.get(variable_expr, undefined_marker)
        
        return str(val)
        
    return pattern.sub(replacer, template)

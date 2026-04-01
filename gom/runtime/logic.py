from typing import Any, List, Union

def normalize_gom_type(val: Any) -> Any:
    """
    Normalize GOM values into comparable forms based on type alias laws.
    
    Examples:
        String -> List[Char]
        Int -> List[Digit]
    """
    if isinstance(val, str):
        return list(val)
    if isinstance(val, int):
        return [int(d) for d in str(val)]
    return val

def normalize_gom_name(name: str) -> str:
    """
    Normalize type names based on GOM type alias laws.
    """
    if name in ["String", "Char[]"]:
        return "String"
    if name in ["Int", "Digit[]", "Int9", "Int99"]:
        return "Int"
    return name

def evaluate_equality(left: Any, right: Any, precision: int = 1) -> bool:
    """
    GOM-specific equality logic based on precision level.
    
    Precision:
    0: '='   - Loose/Estimated (3 = 3.14)
    1: '=='  - Loose (3.14 == "3.14")
    2: '===' - Precise (3.14 === "3.14" -> False, but String === Char[])
    3: '===='- Extreme Precise (Identity/Value check)
    """
    if precision == 0:  # '='
        # Very loose: cast to float/int if possible and compare rounded/base
        try:
            return int(float(left)) == int(float(right))
        except (ValueError, TypeError):
            return str(left) == str(right)

    if precision == 1:  # '=='
        # Loose equality also allows cross-type comparison of normalized forms
        try:
            # Try numeric comparison first if it looks like numbers
            return float(left) == float(right)
        except (ValueError, TypeError):
            pass
            
        n_left = normalize_gom_type(left)
        n_right = normalize_gom_type(right)
        if isinstance(n_left, list) and isinstance(n_right, list):
            return n_left == n_right
        return str(left) == str(right)
        
    if precision == 2:  # '==='
        # Precision 2 allows String == Char[] and Int == Digit[] 
        # as they are considered the SAME type effectively.
        
        # If we are comparing type names (strings)
        if isinstance(left, str) and isinstance(right, str):
            if normalize_gom_name(left) == normalize_gom_name(right):
                return True

        n_left = normalize_gom_type(left)
        n_right = normalize_gom_type(right)
        return n_left == n_right
        
    if precision >= 3:  # '===='
        # Extreme precision: must be same type, same value, AND same identity
        return type(left) is type(right) and left == right and left is right
        
    return left == right

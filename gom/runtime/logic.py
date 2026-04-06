import re
from typing import Any, List, Optional, Union


# ── Number-word resolution ────────────────────────────────────────────────────

_ONES: dict = {
    'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4,
    'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9,
    'ten': 10, 'eleven': 11, 'twelve': 12, 'thirteen': 13,
    'fourteen': 14, 'fifteen': 15, 'sixteen': 16, 'seventeen': 17,
    'eighteen': 18, 'nineteen': 19,
}

_TENS: dict = {
    'twenty': 20, 'thirty': 30, 'forty': 40, 'fifty': 50,
    'sixty': 60, 'seventy': 70, 'eighty': 80, 'ninety': 90,
}

_MAGNITUDES: dict = {
    'hundred': 100,
    'thousand': 1_000,
    'million': 1_000_000,
    'billion': 1_000_000_000,
    'trillion': 1_000_000_000_000,
}


def resolve_number_word(name: str) -> Optional[int]:
    """
    Convert an English number-word name to its integer value.

    Returns ``None`` if ``name`` is not a recognisable number word so that the
    caller can try other lookup strategies.

    Supports:
    - Basic words: zero … nineteen
    - Decade words: twenty … ninety
    - Compound tens: twenty-one, thirty-seven (hyphenated or space-separated)
    - Hundreds: two hundred, one hundred forty-two
    - Larger magnitudes: thousand, million, billion, trillion, and combinations
      thereof (e.g. "one million two hundred thirty-four thousand five hundred
      sixty-seven").

    Examples::

        resolve_number_word("one")                  # 1
        resolve_number_word("twenty-three")         # 23
        resolve_number_word("one hundred")          # 100
        resolve_number_word("two thousand")         # 2000
        resolve_number_word("one million")          # 1_000_000
        resolve_number_word("forty-two")            # 42
    """
    tokens = re.split(r'[\s\-]+', name.strip().lower())
    if not tokens or tokens == ['']:
        return None

    current = 0   # accumulator for the current magnitude group
    total = 0     # running sum of completed magnitude groups

    for token in tokens:
        if not token:
            continue
        if token in _ONES:
            current += _ONES[token]
        elif token in _TENS:
            current += _TENS[token]
        elif token == 'hundred':
            # "two hundred" → current(2) * 100 = 200
            current = (current if current != 0 else 1) * 100
        elif token in _MAGNITUDES:
            mag = _MAGNITUDES[token]
            current = (current if current != 0 else 1) * mag
            total += current
            current = 0
        else:
            # Unrecognised token — not a number word
            return None

    return total + current


# ── Number-to-word conversion ─────────────────────────────────────────────────

_ONES_WORDS: List[str] = [
    '', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine',
    'ten', 'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen',
    'seventeen', 'eighteen', 'nineteen',
]

_TENS_WORDS: List[str] = [
    '', '', 'twenty', 'thirty', 'forty', 'fifty',
    'sixty', 'seventy', 'eighty', 'ninety',
]


def int_to_number_word(n: int) -> str:
    """
    Convert an integer to its English number-word representation.

    This is the exact inverse of ``resolve_number_word`` and supports the
    same range: zero through trillions (including negatives).

    Used by the engine to name a deleted integer value so that expressions
    which produce it keep running instead of crashing — ``delete 3!`` means
    ``2 + 1`` returns ``"three"`` rather than raising.

    Examples::

        int_to_number_word(0)          # "zero"
        int_to_number_word(3)          # "three"
        int_to_number_word(42)         # "forty-two"
        int_to_number_word(100)        # "one hundred"
        int_to_number_word(1_000)      # "one thousand"
        int_to_number_word(-5)         # "negative five"
    """
    if n < 0:
        return "negative " + int_to_number_word(-n)
    if n == 0:
        return "zero"

    def _below_thousand(num: int) -> str:
        if num == 0:
            return ""
        if num < 20:
            return _ONES_WORDS[num]
        if num < 100:
            tens_part = _TENS_WORDS[num // 10]
            ones_part = _ONES_WORDS[num % 10]
            return tens_part + ("-" + ones_part if ones_part else "")
        hundreds_part = _ONES_WORDS[num // 100] + " hundred"
        remainder = _below_thousand(num % 100)
        return (hundreds_part + " " + remainder).strip() if remainder else hundreds_part

    parts: List[str] = []
    for magnitude, label in [
        (1_000_000_000_000, "trillion"),
        (1_000_000_000,     "billion"),
        (1_000_000,         "million"),
        (1_000,             "thousand"),
    ]:
        if n >= magnitude:
            parts.append(_below_thousand(n // magnitude) + " " + label)
            n %= magnitude
    if n > 0:
        parts.append(_below_thousand(n))
    return " ".join(parts)


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

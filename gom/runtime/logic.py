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

# ── Conway-Wechsler illion system ─────────────────────────────────────────────
# Generates magnitude names (million, billion, … decillion, centillion, …)
# programmatically for any group index, without storing a fixed table.
#
# Mapping: _illion_name(n) is the English word for 10^(3*(n+1)):
#   n=1 → million  (10^6)
#   n=2 → billion  (10^9)
#   n=3 → trillion (10^12)
#   n=10 → decillion (10^33)
#   n=100 → centillion (10^303)
#   n=999 → (CW-generated name) (10^2999)

# n=1..9: traditional names that predate the systematic Latin scheme
_SMALL_ILLIONS: List[str] = [
    '',             # 0 — placeholder
    'million',      # 10^6
    'billion',      # 10^9
    'trillion',     # 10^12
    'quadrillion',  # 10^15
    'quintillion',  # 10^18
    'sextillion',   # 10^21
    'septillion',   # 10^24
    'octillion',    # 10^27
    'nonillion',    # 10^30
]

# Conway-Wechsler Latin prefix components (used for n >= 10)
_CW_ONES: List[str] = [
    '', 'un', 'duo', 'tre', 'quattuor', 'quin', 'sex', 'septen', 'octo', 'novem',
]
_CW_TENS: List[str] = [
    '', 'dec', 'vigint', 'trigint', 'quadragint', 'quinquagint',
    'sexagint', 'septuagint', 'octogint', 'nonagint',
]
_CW_HUNDREDS: List[str] = [
    '', 'cent', 'ducent', 'trecent', 'quadringent', 'quingent',
    'sescent', 'septingent', 'octingent', 'nongent',
]


def _illion_name(n: int) -> str:
    """
    Return the English magnitude word for the n-th illion (10^(3*(n+1))).

    n=1 → 'million', n=2 → 'billion', n=3 → 'trillion',
    n=10 → 'decillion', n=100 → 'centillion'.
    Supports n from 1 to 999 (covering values up to 10^2999).

    Applies the Latin boundary adjustment "tre → tres" when ones=3 and a
    hundreds component is present, to avoid the collision with the hundreds
    prefix "trecent" (n=300).  e.g. n=103 → 'trescentillion' (not 'trecentillion').
    """
    if n < 1:
        raise ValueError(f"_illion_name: n must be >= 1, got {n!r}")
    if n < len(_SMALL_ILLIONS):
        return _SMALL_ILLIONS[n]
    hundreds = n // 100
    tens = (n // 10) % 10
    ones = n % 10
    if hundreds > 9:
        raise ValueError(f"_illion_name: n={n!r} is out of range (max 999)")
    # "tre" (ones=3) becomes "tres" before a hundreds component to avoid the
    # "trecent" (hundreds=3) collision.
    ones_str = _CW_ONES[ones]
    if ones == 3 and hundreds > 0:
        ones_str = 'tres'
    return ones_str + _CW_TENS[tens] + _CW_HUNDREDS[hundreds] + 'illion'


def _decode_cw_prefix(prefix: str) -> Optional[int]:
    """
    Decode a Conway-Wechsler prefix (the part before 'illion') back to n.

    Returns n (>= 10) on success, or None if *prefix* is not a valid CW prefix.
    Values 1-9 are handled by ``_SMALL_ILLIONS`` lookups, not here.
    """
    remaining = prefix
    # Match hundreds suffix first (iterate high→low so longer tokens win)
    hundreds = 0
    for i in range(len(_CW_HUNDREDS) - 1, 0, -1):
        if remaining.endswith(_CW_HUNDREDS[i]):
            hundreds = i
            remaining = remaining[:-len(_CW_HUNDREDS[i])]
            break
    # Then tens
    tens = 0
    for i in range(len(_CW_TENS) - 1, 0, -1):
        if remaining.endswith(_CW_TENS[i]):
            tens = i
            remaining = remaining[:-len(_CW_TENS[i])]
            break
    # Finally ones — what's left must be an exact ones entry (or "tres") or empty
    ones = 0
    if remaining:
        # "tres" is the hundreds-boundary form of ones=3 (see _illion_name)
        if remaining == 'tres' and hundreds > 0:
            ones = 3
        else:
            for i in range(len(_CW_ONES) - 1, 0, -1):
                if remaining == _CW_ONES[i]:
                    ones = i
                    remaining = ''
                    break
            else:
                return None  # leftover text — not a valid CW prefix
    n = ones + tens * 10 + hundreds * 100
    return n if n >= 10 else None  # n < 10 are small illions, not CW-generated


def _parse_illion(token: str) -> Optional[int]:
    """
    Recognise any illion word and return its numeric value.

    Returns the integer the word represents (e.g. 'quadrillion' → 10^15),
    or None if *token* is not a recognised illion word.
    """
    # Try well-known small illions first (n=1..9)
    for n, name in enumerate(_SMALL_ILLIONS):
        if name and token == name:
            return 1000 ** (n + 1)
    # Accept any word ending in 'illion' and attempt CW prefix decoding
    if not token.endswith('illion'):
        return None
    cw_prefix = token[:-len('illion')]
    if not cw_prefix:
        return None  # bare 'illion' is not valid
    n = _decode_cw_prefix(cw_prefix)
    if n is None:
        return None
    return 1000 ** (n + 1)


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
    - Larger magnitudes: thousand, and any illion — million, billion, trillion,
      quadrillion … nonillion (n=1–9) plus programmatically generated names via
      the Conway-Wechsler system for n=10–999 (decillion … up to 10^2999), and
      combinations thereof.

    Examples::

        resolve_number_word("one")                  # 1
        resolve_number_word("twenty-three")         # 23
        resolve_number_word("one hundred")          # 100
        resolve_number_word("two thousand")         # 2000
        resolve_number_word("one million")          # 1_000_000
        resolve_number_word("one quadrillion")      # 10^15
        resolve_number_word("one decillion")        # 10^33
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
            # Try any illion word (quadrillion, decillion, centillion, …)
            mag = _parse_illion(token)
            if mag is not None:
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

    Supports any arbitrarily large integer.  Magnitude names are generated
    programmatically via the Conway-Wechsler system so there is no hardcoded
    upper bound — every group of three digits receives its correct label
    (million, billion, …, decillion, centillion, …) up to 10^2999 (n=999),
    after which a ``ValueError`` is raised.

    The two functions are inverses: ``resolve_number_word(int_to_number_word(n)) == n``
    for all supported n.  ``int_to_number_word`` always emits the canonical
    hyphenated form (``"twenty-one"``), while ``resolve_number_word`` also
    accepts space-separated forms.

    Used by the engine so that expressions which produce a deleted integer keep
    running: ``delete 3!`` means ``2 + 1`` returns ``"three"`` rather than
    crashing.

    Examples::

        int_to_number_word(0)                    # "zero"
        int_to_number_word(3)                    # "three"
        int_to_number_word(42)                   # "forty-two"
        int_to_number_word(1_000)                # "one thousand"
        int_to_number_word(10 ** 15)             # "one quadrillion"
        int_to_number_word(10 ** 33)             # "one decillion"
        int_to_number_word(-5)                   # "negative five"
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

    # Split n into groups of 3 digits.
    # groups[0] = ones group (< 1000), groups[1] = thousands, groups[2] = millions, …
    groups: List[int] = []
    temp = n
    while temp > 0:
        groups.append(temp % 1000)
        temp //= 1000

    parts: List[str] = []
    for k in range(len(groups) - 1, -1, -1):
        g = groups[k]
        if g == 0:
            continue
        group_word = _below_thousand(g)
        if k == 0:
            parts.append(group_word)
        elif k == 1:
            parts.append(group_word + " thousand")
        else:
            # k=2 → million (n=1), k=3 → billion (n=2), …
            parts.append(group_word + " " + _illion_name(k - 1))
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

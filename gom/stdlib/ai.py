"""
Gulf of Mexico AI correction passes.

Per spec: "If your code is incomplete, the interpreter will complete it
correctly."  Four passes are applied in order before lexing:

1. **AEMI** — Automatic Exclamation Mark Insertion
2. **ABI**  — Automatic Bracket Insertion
3. **AQMI** — Automatic Quotation Mark Insertion
4. **AI**   — Automatic Interpretation (final fallback completion)
"""
from __future__ import annotations

import re
from typing import List


# ── Compiled patterns ─────────────────────────────────────────────────────────

# A line that already has a valid statement terminator
_TERMINATOR_RE = re.compile(r'[!?¡]\s*$')

# Line openers that identify a statement worth terminating
_STMT_STARTER_RE = re.compile(
    r'^\s*(print|const|var|fun\b|func\b|fn\b|f\b|function|functi|'
    r'delete|reverse|when|return)\b',
    re.IGNORECASE,
)

# print call that is missing its surrounding parentheses
# e.g.  print "hello"  →  print("hello")
_PRINT_NO_PARENS_RE = re.compile(r'^(\s*print)\s+(?!\()(.+)$')

# Bare word (no quotes, no digit start) inside a print(…) call
_BARE_WORD_IN_PRINT_RE = re.compile(r'\bprint\(([^"\')\d\s][^)]*)\)')

# Known keywords / boolean literals that must not be auto-quoted
_KNOWN_KEYWORDS = frozenset({
    'true', 'false', 'maybe', 'undefined',
    'previous', 'current', 'next',
})


# ── Individual passes ─────────────────────────────────────────────────────────

def aemi(source: str) -> str:
    """
    **Automatic Exclamation Mark Insertion.**

    Appends ``!`` to any source line that looks like a statement but is not
    already terminated with ``!``, ``?``, or ``¡``.
    """
    result: List[str] = []
    for line in source.splitlines(keepends=True):
        stripped = line.rstrip('\n').rstrip('\r')
        bare = stripped.strip()
        if bare and not bare.startswith('//'):
            if _STMT_STARTER_RE.match(stripped) and not _TERMINATOR_RE.search(stripped):
                stripped += '!'
        result.append(stripped + ('\n' if line.endswith('\n') else ''))
    return ''.join(result)


def abi(source: str) -> str:
    """
    **Automatic Bracket Insertion.**

    Rewrites ``print <expr>`` → ``print(<expr>)`` where parentheses are absent.
    A trailing terminator (``!``, ``?``, ``¡``) added by a prior pass is stripped
    from the argument and re-appended outside the new parentheses.
    """
    result: List[str] = []
    for line in source.splitlines(keepends=True):
        stripped = line.rstrip('\n').rstrip('\r')
        m = _PRINT_NO_PARENS_RE.match(stripped)
        if m:
            arg = m.group(2).rstrip()
            # Preserve any trailing terminator that was already added (e.g. by AEMI)
            terminator = ''
            while arg and arg[-1] in '!?¡':
                terminator = arg[-1] + terminator
                arg = arg[:-1].rstrip()
            stripped = f"{m.group(1)}({arg}){terminator}"
        result.append(stripped + ('\n' if line.endswith('\n') else ''))
    return ''.join(result)


def aqmi(source: str) -> str:
    """
    **Automatic Quotation Mark Insertion.**

    Wraps bare-word arguments inside ``print(…)`` calls with double quotes,
    but only when the argument contains only lowercase letters and is not a
    known keyword or boolean literal.

    Examples::

        print(hello)   →  print("hello")
        print(score)   →  unchanged  (mixed/underscore → looks like a variable)
        print(true)    →  unchanged  (known keyword)
    """
    def _maybe_quote(m: re.Match) -> str:
        arg = m.group(1).strip()
        # Only quote pure lowercase ASCII words that aren't known keywords
        if re.fullmatch(r'[a-z]+', arg) and arg not in _KNOWN_KEYWORDS:
            return f'print("{arg}")'
        return m.group(0)

    return _BARE_WORD_IN_PRINT_RE.sub(_maybe_quote, source)


def ai(source: str) -> str:
    """
    **Automatic Interpretation.**

    Any line that is non-blank, non-comment, and still unrecognised after the
    previous passes is replaced with ``print("")!`` so execution can always
    continue correctly.
    """
    result: List[str] = []
    for line in source.splitlines(keepends=True):
        stripped = line.rstrip('\n').rstrip('\r')
        bare = stripped.strip()
        if bare and not bare.startswith('//'):
            if (
                not _TERMINATOR_RE.search(stripped)
                and not _STMT_STARTER_RE.match(stripped)
                and not bare.startswith('=')   # file-separator lines (=====)
            ):
                stripped = 'print("")!'
        result.append(stripped + ('\n' if line.endswith('\n') else ''))
    return ''.join(result)


# ── Combined pipeline ─────────────────────────────────────────────────────────

def apply_all(source: str) -> str:
    """Apply all four AI correction passes in order: AEMI → ABI → AQMI → AI."""
    source = aemi(source)
    source = abi(source)
    source = aqmi(source)
    source = ai(source)
    return source

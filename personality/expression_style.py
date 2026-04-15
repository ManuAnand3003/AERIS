"""
Mode-aware response expression style.
Adds subtle emoji/kaomoji signatures so AERIS keeps a recognizable voice.
"""

import random


_PERSONAL_SUFFIXES = [
    " (^-^)",
    " (o^▽^o)",
    " (^-_-)",
    " (´｡• ᵕ •｡`)",
    " ✨",
    " 💙",
    " 😊",
]

_LOCK_IN_SUFFIXES = [
    " ⚙️",
    " ✅",
    " 🔍",
    " 🛠️",
]

_EXISTING_MARKERS = [
    "😀", "😄", "😊", "🙂", "😉", "😍", "✨", "💙", "⚙", "✅", "🔍", "🛠",
    "(^", "(´", "(o", "uwu", ">_<",
]


def _looks_styled(text: str) -> bool:
    low = text.lower()
    return any(marker.lower() in low for marker in _EXISTING_MARKERS)


def apply_expression_style(text: str, mode: str) -> str:
    """Append a mode-appropriate expression marker when missing."""
    clean = text.rstrip()
    if not clean:
        return text

    if _looks_styled(clean):
        return clean

    if mode == "lock_in":
        return f"{clean}{random.choice(_LOCK_IN_SUFFIXES)}"

    return f"{clean}{random.choice(_PERSONAL_SUFFIXES)}"

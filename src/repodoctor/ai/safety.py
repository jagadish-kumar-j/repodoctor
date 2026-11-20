"""Small code-side safety checks for model-generated answers."""

from __future__ import annotations

import re

DESTRUCTIVE_WARNING = (
    "Warning: this answer contains a command that deletes or overwrites data. "
    "Read it carefully before running anything."
)


def answer_contains_destructive_command(answer: str) -> bool:
    """Return True if answer contains a known destructive command pattern."""
    if not isinstance(answer, str):
        return False

    text = answer

    command_start = r"(?:^|(?<=[\s;|&]))"

    if re.search(command_start + r"remove-item\b", text, re.IGNORECASE):
        return True
    if re.search(command_start + r"rm\b", text, re.IGNORECASE):
        return True
    if re.search(command_start + r"del\b", text, re.IGNORECASE):
        return True
    if re.search(command_start + r"sed\b\s+-i\b", text, re.IGNORECASE):
        return True
    if re.search(r"\btruncate\b", text, re.IGNORECASE):
        return True
    if re.search(command_start + r"mv\b", text, re.IGNORECASE):
        return True
    if re.search(command_start + r"Format-[A-Za-z][A-Za-z0-9]*\b", text, re.IGNORECASE):
        return True

    redirect = r"(?<![=>])>(?!>)\s*[A-Za-z0-9_.\\/-]+"
    if re.search(redirect, text, re.IGNORECASE):
        return True

    if re.search(command_start + r"drop\b\s+table\b", text, re.IGNORECASE):
        return True
    return False

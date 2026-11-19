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

    text = answer.lower()

    if "=>" in text:
        text = text.replace("=>", " ")

    command_start = r"(?<!\w)(?:^|[\s;|&])"

    if re.search(command_start + r"remove-item\b", text):
        return True
    if re.search(command_start + r"rm\b", text):
        return True
    if re.search(command_start + r"del\b", text):
        return True
    if re.search(command_start + r"sed\b\s+-i\b", text):
        return True
    if re.search(r"\btruncate\b", text):
        return True
    if re.search(command_start + r"mv\b", text):
        return True
    if re.search(command_start + r"format-[a-z][a-z0-9]*\b", text):
        return True
    if re.search(r"(?:^|[;|&]|\n)\s*(?:echo\b|printf\b|write-output\b|set-content\b|add-content\b|out-file\b)[^<>\n]*(?<!>)>(?![=>])\s*[^\s|;&]+", text):
        return True
    if re.search(command_start + r"drop\s+table\b", text):
        return True
    return False

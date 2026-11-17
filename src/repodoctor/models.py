from dataclasses import dataclass
from typing import Optional


@dataclass
class Requirement:
    """Represents a single tool requirement discovered in a project file.

    Attributes:
        tool: The name of the tool or package.
        version_spec: The version specifier (e.g. ">=3.10"), or None if unspecified.
        source: The file path where the requirement was found.
    """
    tool: str
    version_spec: Optional[str] = None
    source: str = ""

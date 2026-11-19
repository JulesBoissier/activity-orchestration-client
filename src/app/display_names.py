"""Readable names for process executables shown on the dashboard."""

import json
from pathlib import Path
from typing import Dict, Optional

DEFAULT_PATH = Path(__file__).parent / "metadata" / "exe_display_names.json"


def load_display_names(path: Path = DEFAULT_PATH) -> Dict[str, str]:
    """Load the exe → display name map with lowercase keys; an unreadable file gives ``{}``.

    Keys are lowercased here because Windows file names are case-insensitive and the
    watchdog reports them as the process was launched (``Code.exe``, ``code.exe``).
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError):
        return {}
    return {str(k).lower(): v for k, v in raw.items()}


def display_name(process_name: Optional[str], names: Dict[str, str]) -> Optional[str]:
    """The readable name for a process, or the process name itself when there's none."""
    if not process_name:
        return process_name
    return names.get(process_name.lower(), process_name)

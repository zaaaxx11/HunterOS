"""Accessible, stream-local terminal decoration and visible-width helpers."""
from __future__ import annotations

import os
import re
import shutil
import sys


_ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_GREEN = "\x1b[92m"
_BOLD = "\x1b[1m"
_RESET = "\x1b[0m"


def enable_windows_vt(stream) -> bool:
    """Best-effort enable ANSI processing for one Windows console stream."""
    if os.name != "nt":
        return True
    try:
        import ctypes
        import msvcrt

        handle = msvcrt.get_osfhandle(stream.fileno())
        kernel32 = ctypes.windll.kernel32
        mode = ctypes.c_uint()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        return bool(kernel32.SetConsoleMode(handle, mode.value | 0x0004))
    except (AttributeError, OSError, ValueError):
        return False


def supports_color(stream, env=None) -> bool:
    """True only for a capable TTY that has not opted out of color."""
    environment = os.environ if env is None else env
    if "NO_COLOR" in environment or environment.get("TERM", "").lower() == "dumb":
        return False
    try:
        if not stream.isatty():
            return False
    except (AttributeError, OSError):
        return False
    return enable_windows_vt(stream)


def style(text: str, *, green: bool = False, bold: bool = False, color: bool = True) -> str:
    """Decorate text and always close enabled decoration with a reset."""
    if not color or not (green or bold):
        return text
    prefix = ("" if not green else _GREEN) + ("" if not bold else _BOLD)
    return f"{prefix}{text}{_RESET}"


def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def visible_width(text: str) -> int:
    """Return terminal column width for printable Unicode text."""
    import unicodedata

    width = 0
    for char in strip_ansi(text):
        if unicodedata.combining(char) or unicodedata.category(char) in {"Cc", "Cf"}:
            continue
        width += 2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1
    return width


def truncate_visible(text: str, width: int, marker: str = "...") -> str:
    """Truncate without cutting ANSI escapes or combining characters."""
    if width <= 0:
        return ""
    if visible_width(text) <= width:
        return text
    marker_width = visible_width(marker)
    if marker_width >= width:
        return marker[:width]
    target = width - marker_width
    out: list[str] = []
    current = 0
    index = 0
    while index < len(text):
        match = _ANSI_RE.match(text, index)
        if match:
            out.append(match.group(0))
            index = match.end()
            continue
        char = text[index]
        char_width = visible_width(char)
        if current + char_width > target:
            break
        out.append(char)
        current += char_width
        index += 1
    result = "".join(out)
    if _ANSI_RE.search(result) and not result.endswith(_RESET):
        result += _RESET
    return result + marker


def pad_visible(text: str, width: int, align: str = "left") -> str:
    """Pad text to width; overlong text is visibly truncated first."""
    value = truncate_visible(text, width)
    padding = max(0, width - visible_width(value))
    if align == "right":
        return " " * padding + value
    if align == "center":
        left = padding // 2
        return " " * left + value + " " * (padding - left)
    if align != "left":
        raise ValueError("align must be left, right, or center")
    return value + " " * padding


def terminal_width(stream=None, default: int = 80) -> int:
    """Read terminal columns without mutating stream or process state."""
    stream = sys.stdout if stream is None else stream
    try:
        fd = stream.fileno()
    except (AttributeError, OSError, ValueError):
        fd = None
    try:
        return shutil.get_terminal_size(fallback=(default, 24) if fd is None else (default, 24)).columns
    except OSError:
        return default

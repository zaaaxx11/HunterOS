"""Accessible, stream-local terminal decoration and visible-width helpers."""
from __future__ import annotations

import os
import re
import shutil
import sys
from dataclasses import dataclass


_ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_BOLD = "\x1b[1m"
_RESET = "\x1b[0m"


@dataclass(frozen=True)
class Palette:
    """Named terminal tones used by human-facing renderers."""

    primary: str
    success: str
    info: str
    warning: str
    error: str
    muted: str
    reset: str = _RESET


TEAL = Palette(
    primary="\x1b[96m",
    success="\x1b[92m",
    info="\x1b[36m",
    warning="\x1b[93m",
    error="\x1b[91m",
    muted="\x1b[90m",
)
PLAIN = Palette("", "", "", "", "", "", reset="")
PALETTES = {"teal": TEAL, "turquoise": TEAL, "plain": PLAIN, "none": PLAIN, "off": PLAIN}


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


def resolve_palette(stream, *, env=None, requested=None, color=None) -> Palette:
    """Resolve a palette without emitting warnings or contaminating output."""
    environment = os.environ if env is None else env
    if color is False or not supports_color(stream, environment):
        return PLAIN
    name = str(requested or environment.get("HUNT_THEME", "teal")).lower()
    return PALETTES.get(name, PLAIN)


def decorate(text: str, *, tone: str = "primary", palette: Palette | None = None,
             color: bool = True, bold: bool = False) -> str:
    """Apply a semantic tone while preserving visible text and reset safety."""
    if not color or palette is None or not palette.reset:
        return text
    if not hasattr(palette, tone):
        raise ValueError(f"unknown terminal tone: {tone}")
    prefix = getattr(palette, tone)
    if not prefix and not bold:
        return text
    return f"{prefix}{_BOLD if bold else ''}{text}{palette.reset}"


def style(text: str, *, green: bool = False, bold: bool = False, color: bool = True) -> str:
    """Backward-compatible wrapper for the legacy green/bold API."""
    if not green and bold:
        return f"{_BOLD}{text}{_RESET}" if color else text
    palette = TEAL if color else PLAIN
    return decorate(text, tone="primary", palette=palette, color=color, bold=bold)


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

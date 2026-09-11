import io

from huntos.cli.terminal import (
    PLAIN,
    TEAL,
    decorate,
    resolve_palette,
    style,
    strip_ansi,
)


class TTY(io.StringIO):
    def isatty(self):
        return True


def test_teal_palette_has_semantic_tones():
    for tone in ("primary", "success", "info", "warning", "error", "muted"):
        rendered = decorate("status", tone=tone, palette=TEAL)
        assert "\x1b[" in rendered
        assert rendered.endswith(TEAL.reset)
        assert strip_ansi(rendered) == "status"


def test_plain_palette_is_byte_clean():
    for tone in ("primary", "success", "info", "warning", "error", "muted"):
        assert decorate("status", tone=tone, palette=PLAIN) == "status"


def test_palette_respects_tty_and_environment(monkeypatch):
    stream = TTY()
    monkeypatch.setattr("huntos.cli.terminal.enable_windows_vt", lambda _: True)
    assert resolve_palette(stream, env={}, requested="teal") is TEAL
    assert resolve_palette(stream, env={}, requested="TEAL") is TEAL
    assert resolve_palette(stream, env={"NO_COLOR": ""}, requested="teal") is PLAIN
    assert resolve_palette(stream, env={"TERM": "dumb"}, requested="teal") is PLAIN
    assert resolve_palette(stream, env={}, requested="plain") is PLAIN
    assert resolve_palette(stream, env={}, requested="unknown") is PLAIN
    assert resolve_palette(io.StringIO(), env={}, requested="teal") is PLAIN


def test_legacy_style_api_remains_compatible():
    assert style("x", green=False, bold=False, color=False) == "x"
    assert strip_ansi(style("x", green=True, color=True)) == "x"
    assert strip_ansi(style("x", bold=True, color=True)) == "x"
    assert "\x1b[96m" in style("x", green=True, color=True)


def test_panel_uses_teal_theme_on_tty(monkeypatch):
    from huntos.cli.render import panel

    monkeypatch.setattr("huntos.cli.terminal.enable_windows_vt", lambda _: True)
    output = panel("HUNT-OS", ["ready"], width=60, stream=TTY())
    assert "\x1b[96m" in output
    assert strip_ansi(output).count("+") >= 4
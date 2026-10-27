import json
import re


from conftest import posix_only
from ulb.theme import (
    PALETTES,
    resolve_mode,
    stylesheet,
    system_mode
)


def test_palettes_have_the_same_tokens_and_valid_colours():
    assert PALETTES["dark"].keys() == PALETTES["light"].keys()

    for palette in PALETTES.values():
        for token, value in palette.items():
            assert re.fullmatch(r"#[0-9A-Fa-f]{6}", value), token


def test_stylesheets_differ_and_have_no_unreplaced_token():
    dark, light = stylesheet("dark"), stylesheet("light")

    assert dark != light
    assert PALETTES["dark"]["bg"] in dark
    assert PALETTES["light"]["bg"] in light
    assert "$" not in dark and "$" not in light


def test_light_text_is_readable_on_light_background():
    def luminance(colour):
        r, g, b = (int(colour[i:i + 2], 16) / 255 for i in (1, 3, 5))
        lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
               for c in (r, g, b)]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]

    def contrast(a, b):
        la, lb = sorted((luminance(a), luminance(b)), reverse=True)
        return (la + 0.05) / (lb + 0.05)

    for mode, palette in PALETTES.items():
        for text, background in (
            ("text", "bg"), ("input_text", "panel"), ("button_text", "button"),
            ("note", "bg"), ("muted", "bg"), ("ok", "bg"), ("bad", "bg"),
            ("warn", "bg"), ("card_text", "card_bg"), ("banner", "context_bg"),
            ("tab_selected_text", "tab_selected_bg"),
            ("header_text", "header_bg")
        ):
            assert contrast(palette[text], palette[background]) >= 3.0, (
                mode, text, background
            )


def test_resolve_mode():
    assert resolve_mode("light", "ColorScheme.Dark") == "light"
    assert resolve_mode("dark", "ColorScheme.Light") == "dark"
    assert resolve_mode("system", "ColorScheme.Light") == "light"
    assert resolve_mode("system", "ColorScheme.Dark") == "dark"
    assert system_mode("ColorScheme.Unknown", 230) == "light"
    assert system_mode(None, 20) == "dark"
    assert system_mode() == "dark"


@posix_only
def test_theme_switching_in_the_window(fake_wsl, monkeypatch):
    from ulb.constants import settings_file
    from ulb.logos import logo
    from test_ui import make_window

    app, window = make_window(fake_wsl, monkeypatch)
    window.detect_scheme = lambda: ("ColorScheme.Light", 240)

    window.theme_choice.setCurrentText("Sombre")
    assert window.theme_mode == "dark"
    assert PALETTES["dark"]["bg"] in window.styleSheet()
    assert json.loads(settings_file().read_text())["theme"] == "dark"

    window.theme_choice.setCurrentText("Clair")
    assert window.theme_mode == "light"
    assert PALETTES["light"]["bg"] in window.styleSheet()

    window.theme_choice.setCurrentText("Système")
    assert window.theme_mode == "light"   # le système est clair
    window.detect_scheme = lambda: ("ColorScheme.Dark", 20)
    window.system_scheme_changed()
    assert window.theme_mode == "dark"    # il suit le système à chaud

    # une fois forcé, le système ne change plus rien
    window.theme_choice.setCurrentText("Clair")
    window.system_scheme_changed()
    assert window.theme_mode == "light"

    # la carte de famille sélectionnée et les couleurs d'état suivent
    selected = [b for b in window.cards.values() if b.property("selected")]
    assert len(selected) == 1
    assert window.theme_colors()["ok"] == PALETTES["light"]["ok"]
    assert not logo("Slackware", 24).isNull()
    window.close()


@posix_only
def test_theme_choice_is_restored_at_startup(fake_wsl, monkeypatch):
    from test_ui import make_window

    app, window = make_window(fake_wsl, monkeypatch)
    window.theme_choice.setCurrentText("Clair")
    window.close()

    app, window = make_window(fake_wsl, monkeypatch)
    assert window.theme_setting == "light"
    assert window.theme_choice.currentText() == "Clair"
    assert window.theme_mode == "light"
    window.close()

"""Thèmes de l'application : système, clair, sombre.

Toutes les couleurs viennent de PALETTES ; la feuille de style est
générée à partir du modèle ci-dessous. Les widgets qui avaient des
couleurs en dur utilisent une propriété « role » (ou « state »), ce qui
permet de changer de thème à chaud."""

from string import Template

THEMES = ["Système", "Clair", "Sombre"]
SETTING_VALUES = {"Système": "system", "Clair": "light", "Sombre": "dark"}
SETTING_LABELS = {value: label for label, value in SETTING_VALUES.items()}

PALETTES = {
    "dark": {
        "bg": "#10151D", "panel": "#171F2B", "text": "#DCE4EF",
        "text_strong": "#F0F5FC", "input_text": "#E5ECF5",
        "border": "#2C394B", "selection": "#28558A",
        "selection_text": "#FFFFFF",
        "button": "#253448", "button_text": "#E5EDF7",
        "button_border": "#354A62", "button_hover": "#304761",
        "button_hover_border": "#52789E",
        "disabled_text": "#66778A", "disabled_bg": "#1A2330",
        "pane": "#263447", "tab_bg": "#151D29", "tab_text": "#AAB8CB",
        "tab_selected_bg": "#1D2A3B", "tab_selected_text": "#FFFFFF",
        "accent": "#5B9DE3", "alt_row": "#1D2939",
        "header_bg": "#24344A", "header_text": "#DCE5F1",
        "header_border": "#34455B",
        "group_border": "#2B3A4D", "group_title": "#9EB8D6",
        "scroll_bg": "#141D29", "scroll_handle": "#3B4E66",
        "subtitle": "#8FA9C8", "muted": "#7892AF", "note": "#8FA4BF",
        "banner": "#C9D8EA",
        "context_bg": "#162233",
        "card_bg": "#192431", "card_border": "#2C3A4D",
        "card_text": "#B8C8DB", "card_hover": "#24364B",
        "card_sel_bg": "#20354C", "card_sel_border": "#5796D5",
        "card_sel_text": "#FFFFFF",
        "ok": "#7FCE9D", "bad": "#E8776F", "warn": "#E6AD5D",
        "neutral": "#95A4B6", "default": "#DCE4EF",
        "slackware": "#D0D7E2"
    },
    "light": {
        "bg": "#F3F5F9", "panel": "#FFFFFF", "text": "#1B2430",
        "text_strong": "#0F1722", "input_text": "#1B2430",
        "border": "#C3CDDB", "selection": "#A9CBF2",
        "selection_text": "#0F1722",
        "button": "#E4E9F1", "button_text": "#1B2430",
        "button_border": "#B7C3D4", "button_hover": "#D6DEEA",
        "button_hover_border": "#7FA1CB",
        "disabled_text": "#8795A8", "disabled_bg": "#EDF0F5",
        "pane": "#C9D2DF", "tab_bg": "#E6EBF2", "tab_text": "#4A5A70",
        "tab_selected_bg": "#FFFFFF", "tab_selected_text": "#0F1722",
        "accent": "#2F6FBF", "alt_row": "#F0F3F8",
        "header_bg": "#DCE4EF", "header_text": "#1F2D40",
        "header_border": "#C3CDDB",
        "group_border": "#C3CDDB", "group_title": "#35557D",
        "scroll_bg": "#E9EDF3", "scroll_handle": "#AEBBCC",
        "subtitle": "#52647C", "muted": "#66778D", "note": "#52647C",
        "banner": "#243247",
        "context_bg": "#E9EFF8",
        "card_bg": "#EAEFF6", "card_border": "#C3CDDB",
        "card_text": "#2F3F55", "card_hover": "#DCE5F1",
        "card_sel_bg": "#D5E5F8", "card_sel_border": "#2F6FBF",
        "card_sel_text": "#0F1722",
        "ok": "#1E7B45", "bad": "#C0392B", "warn": "#9C5F00",
        "neutral": "#6B7A8D", "default": "#1B2430",
        "slackware": "#2B3445"
    }
}

TEMPLATE = Template("""
QWidget {
    background: $bg;
    color: $text;
    font-family: "Segoe UI";
    font-size: 12px;
}

QMainWindow { background: $bg; }

QLabel { background: transparent; }

QLineEdit, QComboBox, QTextEdit, QTableWidget {
    background: $panel;
    color: $input_text;
    border: 1px solid $border;
    border-radius: 5px;
    padding: 5px;
    selection-background-color: $selection;
    selection-color: $selection_text;
}

QComboBox QAbstractItemView {
    background: $panel;
    color: $input_text;
    selection-background-color: $selection;
    selection-color: $selection_text;
}

QPushButton {
    background: $button;
    color: $button_text;
    border: 1px solid $button_border;
    border-radius: 5px;
    padding: 7px 12px;
    min-height: 22px;
}

QPushButton:hover {
    background: $button_hover;
    border-color: $button_hover_border;
}

QPushButton:disabled {
    color: $disabled_text;
    background: $disabled_bg;
}

QCheckBox { background: transparent; }

QTabWidget::pane {
    border: 1px solid $pane;
    border-top: none;
}

QTabBar::tab {
    background: $tab_bg;
    color: $tab_text;
    padding: 10px 17px;
    border-right: 1px solid $pane;
}

QTabBar::tab:selected {
    background: $tab_selected_bg;
    color: $tab_selected_text;
    border-bottom: 2px solid $accent;
}

QTableWidget {
    alternate-background-color: $alt_row;
    gridline-color: transparent;
}

QHeaderView::section {
    background: $header_bg;
    color: $header_text;
    border: none;
    border-right: 1px solid $header_border;
    padding: 7px;
}

QGroupBox {
    border: 1px solid $group_border;
    border-radius: 6px;
    margin-top: 13px;
    padding-top: 12px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 5px;
    color: $group_title;
}

QScrollBar:vertical { background: $scroll_bg; width: 11px; }
QScrollBar::handle:vertical { background: $scroll_handle; border-radius: 5px; }
QScrollBar:horizontal { background: $scroll_bg; height: 11px; }
QScrollBar::handle:horizontal { background: $scroll_handle; border-radius: 5px; }

QProgressBar {
    background: $panel;
    color: $input_text;
    border: 1px solid $border;
    border-radius: 5px;
    text-align: center;
}

QProgressBar::chunk { background: $accent; border-radius: 4px; }

QToolTip { background: $panel; color: $input_text; border: 1px solid $border; }

QTabWidget#sections::pane { border: 1px solid $pane; border-top: none; }
QTabWidget#sections QTabBar::tab { padding: 8px 14px; }

QLabel[role="title"] { font-size: 20px; font-weight: 600; color: $text_strong; }
QLabel[role="heading"] { font-size: 16px; font-weight: 600; }
QLabel[role="subtitle"] { color: $subtitle; font-size: 12px; }
QLabel[role="muted"] { color: $muted; }
QLabel[role="note"] { color: $note; }
QLabel[role="banner"] { font-size: 13px; font-weight: 600; color: $banner; }
QLabel[role="context"] {
    color: $banner; background: $context_bg;
    border: 1px solid $border; border-radius: 6px; padding: 6px 10px;
}
QLabel[role="preview"] { border: 1px solid $border; color: $muted; }
QLabel[state="ok"] { color: $ok; }
QLabel[state="warn"] { color: $warn; }
QLabel[state="off"] { color: $neutral; }

QPushButton[role="card"] {
    background: $card_bg; border: 1px solid $card_border;
    border-radius: 7px; padding: 8px; color: $card_text;
}
QPushButton[role="card"]:hover { background: $card_hover; }
QPushButton[role="card"][selected="true"] {
    background: $card_sel_bg; border: 1px solid $card_sel_border;
    font-weight: 600; color: $card_sel_text;
}
""")


def palette(mode):
    return PALETTES["light" if mode == "light" else "dark"]


def stylesheet(mode):
    return TEMPLATE.substitute(palette(mode))


# Compatibilité : ancien nom de la feuille sombre.
DARK = stylesheet("dark")


def system_mode(scheme=None, window_lightness=None):
    """« light » ou « dark » d'après le système.

    scheme : valeur de QStyleHints.colorScheme() (Qt 6.5+) sous forme de
    texte « Dark », « Light » ou « Unknown » ; window_lightness : luminosité
    (0-255) de la couleur de fenêtre, utilisée si le système ne répond pas."""

    name = str(scheme or "").split(".")[-1].lower()

    if name == "dark":
        return "dark"

    if name == "light":
        return "light"

    if window_lightness is not None:
        return "light" if window_lightness >= 128 else "dark"

    return "dark"


def resolve_mode(setting, scheme=None, window_lightness=None):
    if setting in ("light", "dark"):
        return setting

    return system_mode(scheme, window_lightness)

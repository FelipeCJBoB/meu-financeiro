from __future__ import annotations

from nicegui import ui

# Type scale. The previous UI sat at 11-13px, below the readable-font-size
# guideline; this follows the 12/14/16/18/24/32 progression instead.
FONT = {
    "meta": "13px",
    "small": "14px",
    "body": "15px",
    "label": "16px",
    "title": "18px",
    "kpi": "30px",
    "chart": 13,
    "chart_legend": 13,
}

THEMES: dict[str, dict[str, str]] = {
    "linen": {
        "bg": "#DDD5C5",
        "s1": "#EDE7DB",
        "s2": "#F6F2E9",
        "overlay": "#FBF8F1",
        "border": "#C7BCA4",
        "text": "#241F17",
        "text2": "#4C452F",
        "textm": "#736A56",
        "accent": "#A8643E",
        "accent2": "#4C6B41",
        # On a light surface a neon tone washes out and fails contrast, so the
        # light theme uses deep saturated versions of the same hues instead.
        "pos": "#0B6B3A",
        "neg": "#B3202F",
        "green": "#0B6B3A",
        "amber": "#8A5A06",
        "red": "#B3202F",
        "glow_pos": "none",
        "glow_neg": "none",
        "icon": "dark_mode",
    },
    "dusk": {
        "bg": "#242B36",
        "s1": "#2F3846",
        "s2": "#394454",
        "overlay": "#394453",
        "border": "#4B5768",
        "text": "#F2F6FB",
        "text2": "#B8C4D4",
        "textm": "#8797AB",
        "accent": "#7EB3E8",
        "accent2": "#5FE3C9",
        # Dark surfaces are where neon actually reads: high luminance on a low
        # luminance background gives strong contrast and pre-attentive pop.
        "pos": "#2BFF9E",
        "neg": "#FF4D6D",
        "green": "#2BFF9E",
        "amber": "#FFC53D",
        "red": "#FF4D6D",
        "glow_pos": "0 0 12px rgba(43,255,158,0.35)",
        "glow_neg": "0 0 12px rgba(255,77,109,0.30)",
        "icon": "light_mode",
    },
}

_state = {"name": None}


def _ensure_loaded() -> None:
    if _state["name"] is None:
        try:
            from app.db import get_session
            from app.services import settings as settings_service

            with get_session() as session:
                name = settings_service.get_settings(session).theme_name
            _state["name"] = name if name in THEMES else "linen"
        except Exception:
            _state["name"] = "linen"


def current() -> dict[str, str]:
    _ensure_loaded()
    return THEMES[_state["name"]]


def current_name() -> str:
    _ensure_loaded()
    return _state["name"]


def is_dark() -> bool:
    _ensure_loaded()
    return _state["name"] == "dusk"


def var(key: str) -> str:
    return f"var(--app-{key})"


def font(key: str) -> str:
    return FONT[key]


def rgba(hex_color: str, alpha: float) -> str:
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def _vars_css(name: str) -> str:
    theme = THEMES[name]
    return ";".join(f"--app-{k}:{v}" for k, v in theme.items() if k != "icon")


def inject_head() -> None:
    _ensure_loaded()
    ui.add_head_html(f"""
    <style>
      :root {{ {_vars_css(_state["name"])} }}
      body, .nicegui-content, .q-page {{
        background: var(--app-bg) !important;
        color: var(--app-text);
        font-size: {FONT["body"]};
      }}
      /* Quasar renders menus, dropdowns and dialogs at body level, where they
         picked up the light body text colour over their own light background
         and became unreadable in the dark theme. Pin them to theme surfaces. */
      .q-menu, .q-dialog__inner > div, .q-select__dialog, .q-popup-edit {{
        background: var(--app-overlay) !important;
        color: var(--app-text) !important;
      }}
      .q-item, .q-item__label, .q-virtual-scroll__content .q-item {{
        color: var(--app-text) !important;
        font-size: {FONT["body"]};
      }}
      .q-item__label--caption {{ color: var(--app-textm) !important; }}
      .q-item.q-manual-focusable--focused,
      .q-item--active,
      .q-item:hover {{
        background: var(--app-s1) !important;
        color: var(--app-text) !important;
      }}
      .q-field__native, .q-field__input, .q-field__prefix, .q-field__suffix {{
        color: var(--app-text) !important;
        font-size: {FONT["body"]};
      }}
      .q-field__label, .q-field__marginal {{ color: var(--app-textm) !important; }}
      .q-field--outlined .q-field__control:before {{
        border-color: var(--app-border) !important;
      }}
      .q-checkbox__label, .q-radio__label, .q-toggle__label {{
        color: var(--app-text) !important;
        font-size: {FONT["small"]};
      }}
      .q-tooltip {{
        background: var(--app-overlay) !important;
        color: var(--app-text) !important;
        font-size: {FONT["small"]} !important;
        border: 1px solid var(--app-border);
        max-width: 340px;
      }}
      .q-notification {{ font-size: {FONT["small"]}; }}
      /* Money figures line up column to column instead of jittering. */
      .money {{ font-variant-numeric: tabular-nums; font-feature-settings: "tnum"; }}
      ::-webkit-scrollbar {{ width: 10px; height: 10px; }}
      ::-webkit-scrollbar-thumb {{ background: var(--app-border); border-radius: 6px; }}
      ::-webkit-scrollbar-track {{ background: transparent; }}
    </style>
    """)


def toggle(icon_element: ui.icon | None = None) -> None:
    _ensure_loaded()
    _state["name"] = "dusk" if _state["name"] == "linen" else "linen"
    try:
        from app.db import get_session
        from app.services import settings as settings_service

        with get_session() as session:
            settings_service.set_theme_name(session, _state["name"])
    except Exception:
        pass  # a failed preference write must not block switching themes
    ui.navigate.reload()

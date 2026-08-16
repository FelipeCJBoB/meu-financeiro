from __future__ import annotations

from nicegui import ui

from app import design

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
    # Surfaces were pulled off the beige: the old #DDD5C5 / #EDE7DB pair left the
    # category colours between 2.09:1 and 2.81:1 against the card, below the 3:1
    # floor, so every chart read washed out. These keep the warm identity but sit
    # neutral enough for the validated ramp to hold its contrast.
    "linen": {
        "bg": "#E7E3DA",
        "s1": "#F4F1EA",
        "s2": "#FAF8F3",
        "overlay": "#FDFCF8",
        "border": "#D3CDC0",
        "text": "#1F1D19",
        "text2": "#55514A",
        "textm": "#8A857C",
        "accent": "#9C5230",
        "accent2": "#46704E",
        # On a light surface a neon tone washes out and fails contrast, so the
        # light theme uses deep saturated versions of the same hues instead.
        "pos": "#1B6B3A",
        "neg": "#A5192B",
        "green": "#1B6B3A",
        "amber": "#8A5A06",
        "red": "#A5192B",
        "glow_pos": "none",
        "glow_neg": "none",
        "icon": "dark_mode",
    },
    # Deepened for the same reason, in the other direction: a darker card gives
    # the dark ramp the contrast headroom the old #2F3846 did not have.
    "dusk": {
        "bg": "#1B1F26",
        "s1": "#232830",
        "s2": "#2C323C",
        "overlay": "#2C323C",
        "border": "#3A424F",
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


def categorical() -> list[str]:
    """The eight series colours of the active theme, in fixed order."""
    _ensure_loaded()
    return design.CATEGORICAL[_state["name"]]


def categorical_color(slot: int) -> str:
    """Slot -> colour. Wraps past eight so a caller can never index out of range,
    but wrapping means two categories share a colour: keep charts at six series
    or fewer and fold the rest into an "Outros" bucket."""
    palette = categorical()
    return palette[slot % len(palette)]


def category_color(category) -> str:
    """A category painted from its slot, so it changes with the theme instead of
    carrying one hex that only works in linen. A category the user recoloured by
    hand has no slot and keeps its own colour."""
    slot = getattr(category, "color_slot", None)
    if slot is not None:
        return categorical_color(slot)
    return category.color


def rgba(hex_color: str, alpha: float) -> str:
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def _vars_css(name: str) -> str:
    theme = THEMES[name]
    parts = [f"--app-{k}:{v}" for k, v in theme.items() if k != "icon"]
    parts += [f"--sp-{step}:{value}" for step, value in design.SPACE.items()]
    parts += [f"--r-{key}:{value}" for key, value in design.RADIUS.items()]
    parts += [f"--cat-{i}:{color}" for i, color in enumerate(design.CATEGORICAL[name])]
    parts += [f"--motion-{key}:{value}" for key, value in design.MOTION.items()]
    return ";".join(parts)


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
      /* Plotly injects its own toolbar markup even with displayModeBar off in
         some code paths; belt and braces, since a floating edit toolbar is the
         single element that most reads "ferramenta de BI" instead of "produto". */
      .js-plotly-plot .modebar {{ display: none !important; }}
      @media (prefers-reduced-motion: reduce) {{
        *, *::before, *::after {{
          animation-duration: 0.01ms !important;
          transition-duration: 0.01ms !important;
        }}
      }}
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

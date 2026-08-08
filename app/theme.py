from __future__ import annotations

from nicegui import ui

THEMES: dict[str, dict[str, str]] = {
    "linen": {
        "bg": "#DDD5C5",
        "s1": "#EDE7DB",
        "s2": "#F6F2E9",
        "border": "#C7BCA4",
        "text": "#2E2A22",
        "text2": "#5C543F",
        "textm": "#867C68",
        "accent": "#A8643E",
        "accent2": "#5F7A54",
        "green": "#5F8A4F",
        "amber": "#A87A2E",
        "red": "#A0503F",
        "icon": "dark_mode",
    },
    "dusk": {
        "bg": "#2C3440",
        "s1": "#38414F",
        "s2": "#414B5B",
        "border": "#4B5566",
        "text": "#E8EDF3",
        "text2": "#A2AFC1",
        "textm": "#727F93",
        "accent": "#7EB3E8",
        "accent2": "#7ED6D0",
        "green": "#8ACB9B",
        "amber": "#E0BE79",
        "red": "#DF8D89",
        "icon": "light_mode",
    },
}

_state = {"name": "linen"}


def current() -> dict[str, str]:
    return THEMES[_state["name"]]


def current_name() -> str:
    return _state["name"]


def var(key: str) -> str:
    return f"var(--app-{key})"


def rgba(hex_color: str, alpha: float) -> str:
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def _vars_css(name: str) -> str:
    theme = THEMES[name]
    return ";".join(f"--app-{k}:{v}" for k, v in theme.items() if k != "icon")


def inject_head() -> None:
    ui.add_head_html(f"""
    <style>
      :root {{ {_vars_css(_state["name"])} }}
      body, .nicegui-content, .q-page {{
        background: var(--app-bg) !important;
        color: var(--app-text);
      }}
      ::-webkit-scrollbar {{ width: 10px; height: 10px; }}
      ::-webkit-scrollbar-thumb {{ background: var(--app-border); border-radius: 6px; }}
    </style>
    """)


def toggle(icon_element: ui.icon | None = None) -> None:
    _state["name"] = "dusk" if _state["name"] == "linen" else "linen"
    theme = THEMES[_state["name"]]
    calls = ";".join(
        f"document.documentElement.style.setProperty('--app-{k}','{v}')"
        for k, v in theme.items()
        if k != "icon"
    )
    ui.run_javascript(calls)
    if icon_element is not None:
        icon_element.set_name(theme["icon"])

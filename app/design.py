"""Design tokens: the single place a size, a spacing, a radius or a series colour
is allowed to be decided.

Before this file the UI carried 87 literal `font-size` declarations across 10
different values, 5 radii and 9 gap sizes - the tokens existed informally in
`theme.FONT` and were routinely bypassed. Everything visual that is not a
surface colour lives here now; `theme.py` keeps the per-theme palettes.

The categorical ramp is NOT hand picked. Both variants were generated in OKLCH
and run through the palette validator until every check passed on their own
surface: lightness band, chroma floor, adjacent separation under deuteranopia
and protanopia, normal-vision separation and contrast. The lightness varies
slot to slot on purpose - two colours at the same lightness collapse into each
other under colour blindness no matter how far apart their hues are, which is
exactly how the previous palette failed.
"""

from __future__ import annotations

# 4pt scale. Anything vertical uses these; nothing invents its own number.
SPACE = {0: "0", 1: "4px", 2: "8px", 3: "12px", 4: "16px", 5: "24px", 6: "32px", 7: "48px"}

RADIUS = {"sm": "8px", "md": "12px", "lg": "16px", "pill": "999px"}

# Typography by role, not by size: a caller asks for "the hero number", not for
# "44px". Weights stop at 500 - 600+ reads heavy at these sizes on Windows.
TYPE: dict[str, tuple[str, str, str]] = {
    "hero": ("44px", "500", "1.05"),
    "kpi": ("28px", "500", "1.15"),
    "stat": ("18px", "500", "1.2"),
    "title": ("18px", "500", "1.3"),
    "body": ("15px", "400", "1.55"),
    "label": ("14px", "400", "1.4"),
    "meta": ("13px", "400", "1.4"),
}

# Entering is slower than exiting: an element that arrives wants to be noticed,
# one that leaves should get out of the way.
MOTION = {
    "in": "150ms cubic-bezier(0.2,0,0,1)",
    "out": "100ms cubic-bezier(0.4,0,1,1)",
}

ELEVATION = {
    "flat": "none",
    "raised": "0 1px 2px rgba(0,0,0,0.06)",
    "overlay": "0 8px 24px rgba(0,0,0,0.18)",
}

# Eight fixed slots, assigned in order and never cycled or reshuffled: a colour
# identifies a category, so it must not change when a filter drops a series.
CATEGORICAL: dict[str, list[str]] = {
    "linen": [
        "#3F93F7",  # 0 azul
        "#A02300",  # 1 laranja queimado
        "#229633",  # 2 verde
        "#9D6FE3",  # 3 roxo
        "#009093",  # 4 teal
        "#A51C30",  # 5 vermelho
        "#9F8600",  # 6 oliva
        "#9F3E99",  # 7 magenta
    ],
    "dusk": [
        "#3C8AE7",
        "#A73400",
        "#2D9539",
        "#9369D4",
        "#008F91",
        "#AC2F3B",
        "#947D00",
        "#9C4297",
    ],
}


def space(step: int) -> str:
    return SPACE[step]


def radius(name: str = "md") -> str:
    return RADIUS[name]


def type_css(role: str, *, color: str | None = None) -> str:
    """The CSS fragment for a type role, ready to concatenate into a style string."""
    size, weight, line_height = TYPE[role]
    css = f"font-size:{size};font-weight:{weight};line-height:{line_height}"
    if color:
        css += f";color:{color}"
    return css


def font_size(role: str) -> str:
    return TYPE[role][0]

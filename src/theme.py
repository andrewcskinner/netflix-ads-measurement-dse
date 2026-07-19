"""Plotly theme + palette.

Series colors are the dark-mode categorical palette validated for CVD-safe
adjacent contrast on the #1a1a19 surface (assigned in fixed order, never
cycled). Netflix-style red (#E50914) is reserved for UI chrome only — it never
encodes data. Status colors are reserved for state and always ship with a
text label, never color alone.
"""

import plotly.graph_objects as go
import plotly.io as pio

SURFACE = "#1a1a19"
PAGE = "#0d0d0d"
INK = "#ffffff"
INK_2 = "#c3c2b7"
MUTED = "#898781"
GRID = "#2c2c2a"
BASELINE = "#383835"
ACCENT = "#E50914"  # chrome only, never a data series

# fixed-order categorical slots (dark mode)
CAT = ["#3987e5", "#008300", "#d55181", "#c98500", "#199e70", "#d95926", "#9085e9", "#e66767"]
SEQ = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7",
       "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b"]
DIVERGING = [[0.0, "#104281"], [0.5, "#383835"], [1.0, "#e66767"]]

STATUS = {"good": "#0ca30c", "warning": "#fab219", "serious": "#ec835a", "critical": "#d03b3b"}

FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'


def register():
    tpl = go.layout.Template()
    tpl.layout = go.Layout(
        paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
        font=dict(family=FONT, color=INK_2, size=13),
        title_font=dict(color=INK, size=15),
        colorway=CAT,
        margin=dict(l=10, r=10, t=48, b=10),
        xaxis=dict(gridcolor=GRID, zerolinecolor=BASELINE, linecolor=BASELINE,
                   tickfont=dict(color=MUTED), title_font=dict(color=INK_2)),
        yaxis=dict(gridcolor=GRID, zerolinecolor=BASELINE, linecolor=BASELINE,
                   tickfont=dict(color=MUTED), title_font=dict(color=INK_2)),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=INK_2)),
        hoverlabel=dict(bgcolor="#252523", font=dict(family=FONT, color=INK)),
    )
    pio.templates["ads_dark"] = tpl
    pio.templates.default = "ads_dark"


def status_for_fill(fill: float) -> tuple[str, str, str]:
    """(label, color, icon) for a fill rate — icon+label so color never stands alone."""
    if fill >= 0.90:
        return "Hot", STATUS["good"], "▲"
    if fill >= 0.75:
        return "Healthy", STATUS["good"], "●"
    if fill >= 0.60:
        return "Soft", STATUS["warning"], "◆"
    return "Cold", STATUS["serious"], "▼"

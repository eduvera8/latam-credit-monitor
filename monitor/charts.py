#!/usr/bin/env python3
"""Inline-SVG line charts for the monitor.

Hand-rolled rather than matplotlib so the published page carries no runtime
dependency and no raster images: the chart is text, it scales, and it inherits
the page's light/dark tokens instead of baking a background colour.

Conventions follow the house data-viz rules: one y-axis per chart, solid hairline
grid, 2px lines, categorical hues assigned by fixed slot (never by rank), the
endpoint of each series directly labelled, and a crosshair tooltip layer driven
by the JSON the chart carries in `data-series`.
"""

import json
import math

# Categorical slots 1-3. Light and dark steps are the same three hues restepped
# for the dark surface; both runs pass the all-pairs CVD and normal-vision gates.
SLOT_VAR = {1: "--series-1", 2: "--series-2", 3: "--series-3"}


def num(value, decimals):
    """pt-BR number: thin-space thousands, comma decimal."""
    return f"{value:,.{decimals}f}".replace(",", "\u2009").replace(".", ",")

W, H = 760, 300
# PAD_R has to hold the longest endpoint label ('Pessoa jurídica' plus its
# value) inside the viewBox; measured, it needs ~118 units.
PAD_L, PAD_R, PAD_T, PAD_B = 44, 118, 10, 26
PLOT_W = W - PAD_L - PAD_R
PLOT_H = H - PAD_T - PAD_B


def nice_bounds(lo, hi, ticks=5):
    """Round a data range out to readable tick values.

    Picks the smallest 1/2/2.5/5-style step whose tick count still fits, so an
    axis over 0-25 lands on steps of 5 rather than jumping to 10.
    """
    if hi == lo:
        hi, lo = hi + 1, lo - 1
    exp = math.floor(math.log10(hi - lo)) - 1
    lo_t = hi_t = step = None
    for e in range(exp, exp + 5):
        for mult in (1, 2, 2.5, 5):
            step = mult * 10 ** e
            lo_t = step * math.floor(lo / step)
            hi_t = step * math.ceil(hi / step)
            if round((hi_t - lo_t) / step) <= ticks + 1:
                break
        else:
            continue
        break
    values, v = [], lo_t
    while v <= hi_t + step * 1e-9:
        values.append(round(v, 10))
        v += step
    return lo_t, hi_t, values


def _declutter(points, min_gap=13.0, top=PAD_T, bottom=PAD_T + PLOT_H):
    """Nudge endpoint labels apart vertically so they never overlap."""
    ordered = sorted(points, key=lambda p: p["y"])
    for i in range(1, len(ordered)):
        gap = ordered[i]["ly"] - ordered[i - 1]["ly"]
        if gap < min_gap:
            ordered[i]["ly"] = ordered[i - 1]["ly"] + min_gap
    overshoot = ordered[-1]["ly"] - bottom
    if overshoot > 0:
        for p in ordered:
            p["ly"] -= overshoot
    if ordered[0]["ly"] < top:
        shift = top - ordered[0]["ly"]
        for p in ordered:
            p["ly"] += shift
    return points


def line_chart(chart_id, series, dates, unit="", decimals=2):
    """Render one chart. `series` is a list of dicts: label, slot, values.

    `values` is aligned to `dates` and may hold None for gaps. Returns SVG as a
    string, with the series data attached for the tooltip layer.
    """
    live = [v for s in series for v in s["values"] if v is not None]
    if not live:
        return '<p class="chart-empty">Sem dados.</p>'

    lo, hi, ticks = nice_bounds(min(live), max(live))
    # Whole-number ticks drop the decimal entirely: a 1-7 axis reads better
    # as 1 2 3 than as 1,0 2,0 3,0.
    tick_dec = 0 if all(abs(t - round(t)) < 1e-9 for t in ticks) else 1
    n = len(dates)

    def sx(i):
        return PAD_L + (PLOT_W * i / (n - 1) if n > 1 else PLOT_W / 2)

    def sy(v):
        return PAD_T + PLOT_H - PLOT_H * (v - lo) / (hi - lo)

    out = [
        f'<svg class="chart" id="{chart_id}" viewBox="0 0 {W} {H}" '
        f'role="img" preserveAspectRatio="xMidYMid meet" '
        f'data-series=\'{json.dumps([{"label": s["label"], "slot": s["slot"], "values": s["values"]} for s in series])}\' '
        f'data-dates=\'{json.dumps(dates)}\' data-unit="{unit}" data-decimals="{decimals}" '
        f'data-ylo="{lo}" data-yhi="{hi}">'
    ]

    # Horizontal grid and y labels.
    for t in ticks:
        y = sy(t)
        out.append(f'<line class="grid" x1="{PAD_L}" y1="{y:.1f}" x2="{PAD_L + PLOT_W}" y2="{y:.1f}"/>')
        out.append(f'<text class="tick" x="{PAD_L - 8}" y="{y + 3:.1f}" text-anchor="end">'
                   f'{num(t, tick_dec)}</text>')

    # Year ticks on the x-axis, thinned so labels never collide.
    years = {}
    for i, d in enumerate(dates):
        years.setdefault(d[:4], i)
    keys = sorted(years)
    stride = max(1, round(len(keys) / 8))
    for k in keys[::stride]:
        out.append(f'<text class="tick" x="{sx(years[k]):.1f}" y="{PAD_T + PLOT_H + 17}" '
                   f'text-anchor="middle">{k}</text>')

    # Series paths.
    endpoints = []
    for s in series:
        var = SLOT_VAR[s["slot"]]
        runs, run = [], []
        for i, v in enumerate(s["values"]):
            if v is None:
                if len(run) > 1:
                    runs.append(run)
                run = []
            else:
                run.append((sx(i), sy(v)))
        if len(run) > 1:
            runs.append(run)
        for r in runs:
            pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in r)
            out.append(f'<polyline class="series" style="stroke:var({var})" points="{pts}"/>')
        last = next((i for i in range(len(s["values"]) - 1, -1, -1) if s["values"][i] is not None), None)
        if last is not None:
            endpoints.append({"x": sx(last), "y": sy(s["values"][last]), "ly": sy(s["values"][last]),
                              "var": var, "label": s["label"], "value": s["values"][last]})

    # Endpoint markers plus direct labels. Direct labels are the required relief
    # for the slots that sit under 3:1 contrast on the light surface, so they are
    # not optional decoration.
    for p in _declutter(endpoints):
        out.append(f'<circle class="dot-ring" cx="{p["x"]:.1f}" cy="{p["y"]:.1f}" r="4"/>')
        out.append(f'<circle class="dot" cx="{p["x"]:.1f}" cy="{p["y"]:.1f}" r="4" '
                   f'style="fill:var({p["var"]})"/>')
        if abs(p["ly"] - p["y"]) > 1.5:
            out.append(f'<line class="leader" x1="{p["x"] + 6:.1f}" y1="{p["y"]:.1f}" '
                       f'x2="{p["x"] + 11:.1f}" y2="{p["ly"]:.1f}"/>')
        out.append(f'<text class="endlabel" x="{p["x"] + 13:.1f}" y="{p["ly"] + 3:.1f}">'
                   f'{p["label"]} <tspan class="endvalue">{num(p["value"], decimals)}</tspan></text>')

    # Crosshair layer, populated by the tooltip script.
    out.append(f'<line class="crosshair" x1="0" y1="{PAD_T}" x2="0" y2="{PAD_T + PLOT_H}" hidden/>')
    out.append(f'<g class="hoverdots"></g>')
    out.append(f'<rect class="hitbox" x="{PAD_L}" y="{PAD_T}" width="{PLOT_W}" height="{PLOT_H}"/>')
    out.append("</svg>")
    return "\n".join(out)


def legend(series):
    # One series needs no legend: the chart's own title names it.
    if len(series) < 2:
        return ""
    items = "".join(
        f'<li><span class="swatch" style="background:var({SLOT_VAR[s["slot"]]})"></span>{s["label"]}</li>'
        for s in series)
    return f'<ul class="legend">{items}</ul>'


BAR_W = 760
BAR_PAD_L, BAR_PAD_R, BAR_PAD_T, BAR_PAD_B = 104, 54, 8, 26
BAR_ROW, BAR_GAP = 15, 3   # 3px of surface between adjacent bars


def _bar_path(x0, x1, y, h, r=4):
    """A bar with its growing end rounded and its baseline end square."""
    r = min(r, abs(x1 - x0), h / 2)
    if r <= 0:
        return f"M{x0:.1f},{y:.1f} L{x1:.1f},{y:.1f} L{x1:.1f},{y + h:.1f} L{x0:.1f},{y + h:.1f} Z"
    s = 1 if x1 >= x0 else -1
    return (f"M{x0:.1f},{y:.1f} L{x1 - s * r:.1f},{y:.1f} Q{x1:.1f},{y:.1f} {x1:.1f},{y + r:.1f} "
            f"L{x1:.1f},{y + h - r:.1f} Q{x1:.1f},{y + h:.1f} {x1 - s * r:.1f},{y + h:.1f} "
            f"L{x0:.1f},{y + h:.1f} Z")


def ranked_bar(chart_id, items, unit="", decimals=1, extremes=3):
    """A ranked horizontal bar chart for nominal categories.

    One series, so one colour for every bar - shading by value would burn the
    only free channel on information the bar length already carries. Values are
    direct-labelled only at the extremes; the gridlines, the hover tooltip and
    the table below carry the rest.
    """
    if not items:
        return '<p class="chart-empty">Sem dados.</p>'

    values = [v for _, v in items]
    lo, hi, ticks = nice_bounds(min(min(values), 0), max(max(values), 0))
    tick_dec = 0 if all(abs(t - round(t)) < 1e-9 for t in ticks) else 1

    plot_w = BAR_W - BAR_PAD_L - BAR_PAD_R
    height = BAR_PAD_T + len(items) * BAR_ROW + BAR_PAD_B

    def sx(v):
        return BAR_PAD_L + plot_w * (v - lo) / (hi - lo)

    zero = sx(0)
    out = [f'<svg class="chart chart-bars" id="{chart_id}" viewBox="0 0 {BAR_W} {height}" '
           f'role="img" preserveAspectRatio="xMidYMid meet" data-unit="{unit}" '
           f'data-decimals="{decimals}">']

    for t in ticks:
        x = sx(t)
        out.append(f'<line class="grid" x1="{x:.1f}" y1="{BAR_PAD_T}" x2="{x:.1f}" '
                   f'y2="{BAR_PAD_T + len(items) * BAR_ROW:.1f}"/>')
        out.append(f'<text class="tick" x="{x:.1f}" y="{height - 8}" text-anchor="middle">'
                   f'{num(t, tick_dec)}</text>')

    ranked = sorted(range(len(items)), key=lambda i: items[i][1], reverse=True)
    flagged = set(ranked[:extremes]) | set(ranked[-extremes:])

    for row, (label, value) in enumerate(items):
        y = BAR_PAD_T + row * BAR_ROW + BAR_GAP / 2
        h = BAR_ROW - BAR_GAP
        out.append(f'<text class="cat" x="{BAR_PAD_L - 8}" y="{y + h / 2 + 3.2:.1f}" '
                   f'text-anchor="end">{label}</text>')
        out.append(f'<path class="bar" d="{_bar_path(zero, sx(value), y, h)}" '
                   f'data-label="{label}" data-value="{value:.6f}"/>')
        if row in flagged:
            end = sx(value)
            anchor = "start" if value >= 0 else "end"
            dx = 6 if value >= 0 else -6
            out.append(f'<text class="barval" x="{end + dx:.1f}" y="{y + h / 2 + 3.2:.1f}" '
                       f'text-anchor="{anchor}">{num(value, decimals)}</text>')

    out.append(f'<line class="axis-zero" x1="{zero:.1f}" y1="{BAR_PAD_T}" x2="{zero:.1f}" '
               f'y2="{BAR_PAD_T + len(items) * BAR_ROW:.1f}"/>')
    out.append("</svg>")
    return "\n".join(out)

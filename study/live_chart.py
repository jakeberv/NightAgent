"""Local, event-driven search progress: observations, not training-loss estimates."""
import math

from rich.text import Text


AXES = ("time", "cost", "tokens")
AXIS_LABELS = {"time": "Elapsed time", "cost": "Cumulative API cost", "tokens": "Cumulative API tokens"}


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def plot_data(state, axis):
    """Preserve true completion coordinates; unknown accounting has no coordinate."""
    if axis not in AXES:
        raise ValueError(f"Unknown chart axis: {axis}")
    key = {"time": "elapsed", "cost": "cost", "tokens": "tokens"}[axis]
    points, omitted = [], 0
    for observation in state.history:
        x = observation.get(key)
        if not finite(x) or x < 0:
            omitted += 1
            continue
        points.append({**observation, "x": x})
    values = [p[k] for p in state.history for k in ("score", "best") if finite(p.get(k))]
    targets = [t["value"] for t in state.targets if finite(t.get("value"))]
    values.extend(targets)
    low, high = min(values, default=0), max(values, default=1)
    # Pad and quantize using the entire run; bounds expand but never contract.
    spread = high - low if high > low else max(abs(high) * .001, .001)
    step = 10 ** math.floor(math.log10(spread))
    low = math.floor((low - spread * .1) / step) * step
    high = math.ceil((high + spread * .1) / step) * step
    previous = getattr(state, "chart_bounds", None)
    if previous:
        low, high = min(low, previous[0]), max(high, previous[1])
    if values:
        state.chart_bounds = (low, high)
    limit = {"time": state.allowance, "cost": state.config.get("dollar_cap", 0), "tokens": 0}[axis]
    maximum = max([p["x"] for p in points] + [limit, 1])
    if axis == "tokens":
        # Stable buckets rather than moving every dot after each API response.
        maximum = 1000 * 2 ** max(0, math.ceil(math.log2(maximum / 1000)))
    return dict(points=points, omitted=omitted, targets=targets, low=low, high=high, x_max=maximum)


def raster(points, targets, *, width, height, x_max, low, high, ascii_only=False):
    """Draw targets, then steps, then observations. Best markers win cell collisions."""
    grid = [[" " for _ in range(width)] for _ in range(height)]
    def column(x):
        return min(width - 1, max(0, round(x / x_max * (width - 1))))
    def row(y):
        return min(height - 1, max(0, round((high - y) / (high - low) * (height - 1))))
    horizontal, vertical = ("-", "|") if ascii_only else ("─", "│")
    for target in targets:
        for x in range(0, width, 2):
            grid[row(target)][x] = ":" if ascii_only else "┄"
    last = None
    for p in points:
        if not finite(p.get("best")):
            continue
        x, y = column(p["x"]), row(p["best"])
        if last:
            old_x, old_y = last
            for col in range(old_x, x + 1):
                grid[old_y][col] = horizontal
            for line in range(min(y, old_y), max(y, old_y) + 1):
                grid[line][x] = vertical
        last = x, y
    markers = []
    previous = None
    for p in points:
        best = p.get("best")
        improved = finite(best) and p["score"] == best and (previous is None or best != previous)
        markers.append((column(p["x"]), row(p["score"]), improved))
        if finite(best):
            previous = best
    # Always retain a record-setting point if multiple results occupy one cell.
    for improved in (False, True):
        for x, y, record in markers:
            if record == improved:
                grid[y][x] = ("*" if record else "o") if ascii_only else ("●" if record else "·")
    return ["".join(line) for line in grid]


def progress_sentence(state):
    last_improvement = None
    previous = None
    selected = 0
    for p in state.history:
        best = p.get("best")
        if not finite(best):
            continue
        selected += 1
        if previous is None or best != previous:
            last_improvement = selected
        previous = best
    if not selected:
        return "Waiting for a selected validation result."
    unchanged = selected - last_improvement
    if unchanged:
        return f"The best score has not improved in the last {unchanged} {'trial' if unchanged == 1 else 'trials'}."
    return "The latest experiment established the best score so far."


def chart(state, *, width, height=10, axis="time", ascii_only=False):
    """Fixed-size, cached Text; idle spinner refreshes never rebuild this plot."""
    from .terminal import duration, text
    key = (state.chart_revision, width, height, axis, ascii_only)
    if key in state.chart_cache:
        return state.chart_cache[key]
    data = plot_data(state, axis)
    direction = "lower" if state.objective["direction"] == "minimize" else "higher"
    lines = [f"Validation {state.objective['metric']} ({direction} is better)"]
    # Reserve one column for the y axis, with labels sized for the actual range.
    rows = max(2, height - 5)
    accuracy = state.objective["metric"] == "accuracy"
    def y_label(value):
        return f"{value * 100:.1f}%" if accuracy else f"{value:.5f}"
    labels = [y_label(data['high'] - i * (data['high'] - data['low']) / (rows - 1)) for i in range(rows)]
    margin = max(map(len, labels)) + 1
    plot_width = max(2, width - margin - 1)
    if data['points']:
        grid = raster(data['points'], data['targets'], width=plot_width, height=rows,
                      x_max=data['x_max'], low=data['low'], high=data['high'], ascii_only=ascii_only)
        for label, row in zip(labels, grid):
            lines.append(label.rjust(margin) + ("|" if ascii_only else "│") + row)
    else:
        message = "Waiting for completed experiments." if not state.history else "No experiments have complete accounting on this axis."
        lines.extend([message] + [""] * (rows - 1))
    lines.append(" " * margin + ("+" + "-" * plot_width if ascii_only else "└" + "─" * plot_width))
    end = duration(data['x_max']) if axis == 'time' else f"${data['x_max']:g}" if axis == 'cost' else f"{data['x_max']:g}"
    axis_label = f"0  {AXIS_LABELS[axis]}"
    lines.append(" " * margin + axis_label + " " * max(1, plot_width + 1 - len(axis_label) - len(end)) + end)
    legend = "o Trial  * New best  - Best  : Target" if ascii_only else "· Trial  ● New best  ─ Best  ┄ Target"
    lines.append(legend)
    if data['omitted']:
        lines.append(f"{data['omitted']} omitted: incomplete {axis} accounting")
    result = Text()
    for index, line in enumerate(lines[:height]):
        if index:
            result.append("\n")
        safe = text(line, "bold cyan" if index == 0 else "dim")
        safe.truncate(width, overflow="crop")
        if 1 <= index <= rows and data['points']:
            for position, character in enumerate(safe.plain):
                if position <= margin:
                    continue
                style = ("not dim bold bright_green" if character in "*●" else
                         "not dim bright_cyan" if character in "o·" else
                         "not dim yellow" if character in ":┄" else "not dim green")
                safe.stylize(style, position, position + 1)
        result.append_text(safe)
    # Bound cache across terminal resizes/axis changes; history itself stays intact.
    if len(state.chart_cache) >= 12:
        state.chart_cache.clear()
    state.chart_cache[key] = result
    return result

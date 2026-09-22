from __future__ import annotations

import html
import json
import math
import re
from pathlib import Path
from typing import Any, Dict


def _safe(value: Any) -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip()).strip("._")
    return text or "item"


def _cell(value: Any) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:.6g}"
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return str(value).replace("|", "\\|").replace("\n", " ")


def _metrics(snapshot: Dict[str, Any]) -> Dict[str, float]:
    raw = ((snapshot or {}).get("result_evidence") or {}).get("metrics") or {}
    out: Dict[str, float] = {}
    if isinstance(raw, dict):
        for key, value in raw.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            out[str(key).upper()] = float(value)
    return out


def _render_settings(settings: Any) -> str:
    if not isinstance(settings, dict) or not settings:
        return "_Settings unavailable._\n"
    out = "| Setting | Value |\n|---|---|\n"
    for key in sorted(settings, key=lambda x: str(x).lower()):
        out += f"| {_cell(key)} | {_cell(settings[key])} |\n"
    return out


def _render_metrics(root: Dict[str, Any], current: Dict[str, Any]) -> str:
    rm, cm = _metrics(root), _metrics(current)
    names = sorted(set(rm) | set(cm))
    if not names:
        return "_No result metrics available._\n"
    compare = str(root.get("alpha_id")) != str(current.get("alpha_id")) or rm != cm
    if compare:
        out = "| Metric | Root | Current Incumbent | Delta |\n|---|---:|---:|---:|\n"
        for name in names:
            rv, cv = rm.get(name), cm.get(name)
            delta = cv - rv if rv is not None and cv is not None else None
            out += f"| {_cell(name)} | {_cell(rv)} | {_cell(cv)} | {_cell(delta)} |\n"
        return out
    out = "| Metric | Value |\n|---|---:|\n"
    for name in names:
        out += f"| {_cell(name)} | {_cell(cm.get(name))} |\n"
    return out


def _render_checks(snapshot: Dict[str, Any]) -> str:
    checks = ((snapshot or {}).get("result_evidence") or {}).get("checks") or []
    if not isinstance(checks, list) or not checks:
        return "_No complete check snapshot available._\n"
    out = "| Check | Status | Value | Limit |\n|---|---:|---:|---:|\n"
    for row in checks:
        if not isinstance(row, dict):
            continue
        out += (
            f"| {_cell(row.get('name'))} | {_cell(row.get('status'))} | "
            f"{_cell(row.get('value'))} | {_cell(row.get('limit'))} |\n"
        )
    return out


def _render_fields(context: Dict[str, Any], fallback: list[str]) -> str:
    raw = context.get("fields") if isinstance(context, dict) else []
    rows = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, str) and item.strip():
                rows.append({"name": item.strip()})
            elif isinstance(item, dict) and item.get("name"):
                rows.append(item)
    known = {str(x.get("name")) for x in rows}
    for name in fallback:
        if str(name) not in known:
            rows.append({"name": name})
    if not rows:
        return "_Field information unavailable._\n"
    out = "| Field | Type | Dataset | Coverage | Date coverage | Description |\n|---|---|---|---:|---:|---|\n"
    for row in rows:
        out += (
            f"| {_cell(row.get('name'))} | {_cell(row.get('type'))} | {_cell(row.get('dataset'))} | "
            f"{_cell(row.get('coverage'))} | {_cell(row.get('dateCoverage', row.get('date_coverage')))} | "
            f"{_cell(row.get('description'))} |\n"
        )
    return out


def _render_progression(state: Dict[str, Any]) -> str:
    rows = []
    for hid, hyp in (state.get("hypotheses") or {}).items():
        result = ((hyp or {}).get("result") or {}).get("evidence") or {}
        if not result:
            continue
        evaluation = ((hyp or {}).get("result") or {}).get("evaluation") or {}
        rows.append((hid, hyp, result, evaluation))
    if not rows:
        return "_No optimization candidate has produced a result yet._\n"
    out = (
        "| Hypothesis | Alpha | Mechanism | Status | Sharpe | Fitness | Returns | Margin | Turnover | New blockers |\n"
        "|---|---|---|---|---:|---:|---:|---:|---:|---|\n"
    )
    for hid, hyp, result, evaluation in rows:
        m = {}
        for key, value in (result.get("metrics") or {}).items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                m[str(key).upper()] = float(value)
        blockers = ", ".join(evaluation.get("new_blockers") or [])
        out += (
            f"| {_cell(hid)} | {_cell(result.get('alpha_id'))} | "
            f"{_cell(((hyp.get('contract') or {}).get('mechanism')))} | {_cell(hyp.get('status'))} | "
            f"{_cell(m.get('SHARPE'))} | {_cell(m.get('FITNESS'))} | {_cell(m.get('RETURNS'))} | "
            f"{_cell(m.get('MARGIN'))} | {_cell(m.get('TURNOVER'))} | {_cell(blockers)} |\n"
        )
    return out


def _normalize_chart(raw: Any) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("chart must be an object")
    kind = str(raw.get("type") or "").lower()
    if kind not in {"line", "bar"}:
        raise ValueError("chart.type must be line or bar")
    labels = raw.get("labels")
    if not isinstance(labels, list) or not labels:
        raise ValueError("chart.labels must be a non-empty list")
    labels = [str(x) for x in labels]
    raw_series = raw.get("series")
    if not isinstance(raw_series, list) or not raw_series:
        values = raw.get("values")
        if not isinstance(values, list):
            raise ValueError("chart requires series or values")
        raw_series = [{"name": raw.get("value_label") or "Value", "values": values}]
    series = []
    for index, row in enumerate(raw_series):
        if not isinstance(row, dict) or not isinstance(row.get("values"), list):
            raise ValueError("each chart series requires values")
        if len(row["values"]) != len(labels):
            raise ValueError("chart values length must match labels")
        values = []
        for value in row["values"]:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError("chart values must be numeric")
            number = float(value)
            if not math.isfinite(number):
                raise ValueError("chart values must be finite")
            values.append(number)
        series.append({"name": str(row.get("name") or f"Series {index + 1}"), "values": values})
    return {
        "id": _safe(raw.get("id") or raw.get("title") or "chart"),
        "title": str(raw.get("title") or raw.get("id") or "Visualization"),
        "type": kind,
        "labels": labels,
        "series": series,
    }


def _svg_text(value: Any) -> str:
    return html.escape(str(value), quote=True)


def write_chart_svg(state: Dict[str, Any], raw: Any) -> Dict[str, Any]:
    chart = _normalize_chart(raw)
    run = state.get("run") or {}
    log_path = Path(str(run.get("log_path") or "")).expanduser().resolve()
    if not run.get("log_path"):
        raise ValueError("run log is required before chart rendering")
    assets = log_path.parent / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    filename = f"{_safe(run.get('run_id') or state.get('root_alpha_id'))}_{chart['id']}.svg"
    target = assets / filename

    width, height = 900, 360
    left, right, top, bottom = 72, 24, 48, 62
    plot_w, plot_h = width - left - right, height - top - bottom
    all_values = [v for series in chart["series"] for v in series["values"]]
    ymin, ymax = min(all_values), max(all_values)
    if ymin == ymax:
        pad = abs(ymin) * 0.05 or 1.0
    else:
        pad = (ymax - ymin) * 0.08
    ymin, ymax = ymin - pad, ymax + pad

    def x_at(i: int) -> float:
        n = len(chart["labels"])
        if chart["type"] == "bar":
            return left + (i + 0.5) * plot_w / max(n, 1)
        return left + i * plot_w / max(n - 1, 1)

    def y_at(value: float) -> float:
        return top + (ymax - value) * plot_h / (ymax - ymin)

    palette = ["#2f80ed", "#27ae60", "#f2994a", "#9b51e0"]
    pieces = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{left}" y="28" font-family="Arial,sans-serif" font-size="18" font-weight="600" fill="#222">{_svg_text(chart["title"])}</text>',
    ]
    for tick in range(5):
        value = ymin + (ymax - ymin) * tick / 4
        y = y_at(value)
        pieces.append(f'<line x1="{left}" y1="{y:.2f}" x2="{width-right}" y2="{y:.2f}" stroke="#e6e6e6" stroke-width="1"/>')
        pieces.append(f'<text x="{left-8}" y="{y+4:.2f}" text-anchor="end" font-family="Arial,sans-serif" font-size="11" fill="#666">{value:.3g}</text>')

    labels = chart["labels"]
    label_step = max(1, len(labels) // 8)
    for i, label in enumerate(labels):
        if i % label_step != 0 and i != len(labels) - 1:
            continue
        x = x_at(i)
        pieces.append(
            f'<text x="{x:.2f}" y="{height-27}" text-anchor="middle" '
            f'font-family="Arial,sans-serif" font-size="10" fill="#666">{_svg_text(label[:18])}</text>'
        )

    if chart["type"] == "line":
        for si, series in enumerate(chart["series"]):
            color = palette[si % len(palette)]
            points = " ".join(f"{x_at(i):.2f},{y_at(v):.2f}" for i, v in enumerate(series["values"]))
            pieces.append(f'<polyline fill="none" stroke="{color}" stroke-width="2" points="{points}"/>')
    else:
        n = len(labels)
        group_w = plot_w / max(n, 1)
        gap = group_w * 0.14
        bar_w = max(2.0, (group_w - 2 * gap) / max(len(chart["series"]), 1))
        zero_y = y_at(0.0) if ymin <= 0 <= ymax else y_at(ymin)
        for si, series in enumerate(chart["series"]):
            color = palette[si % len(palette)]
            for i, value in enumerate(series["values"]):
                x = left + i * group_w + gap + si * bar_w
                y = y_at(value)
                rect_y = min(y, zero_y)
                rect_h = max(1.0, abs(zero_y - y))
                pieces.append(
                    f'<rect x="{x:.2f}" y="{rect_y:.2f}" width="{bar_w*0.86:.2f}" '
                    f'height="{rect_h:.2f}" fill="{color}" opacity="0.88"/>'
                )

    if len(chart["series"]) > 1:
        legend_x = left
        for si, series in enumerate(chart["series"]):
            color = palette[si % len(palette)]
            pieces.append(f'<rect x="{legend_x}" y="{height-14}" width="10" height="10" fill="{color}"/>')
            pieces.append(
                f'<text x="{legend_x+14}" y="{height-5}" font-family="Arial,sans-serif" '
                f'font-size="10" fill="#555">{_svg_text(series["name"])}</text>'
            )
            legend_x += 150

    pieces.append("</svg>")
    target.write_text("".join(pieces), encoding="utf-8")
    chart["asset"] = f"assets/{filename}"
    return chart


def enrich_context_with_charts(state: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("dashboard payload must be an object")
    current = state.get("dashboard_context") or {"fields": [], "visualization": {}}
    context = json.loads(json.dumps(current))

    if "fields" in payload:
        fields = payload.get("fields")
        if not isinstance(fields, list):
            raise ValueError("fields must be a list")
        normalized = []
        for row in fields:
            if isinstance(row, str) and row.strip():
                normalized.append({"name": row.strip()})
            elif isinstance(row, dict) and isinstance(row.get("name"), str) and row["name"].strip():
                normalized.append(json.loads(json.dumps(row)))
            else:
                raise ValueError("invalid field row")
        context["fields"] = normalized

    if "visualization" in payload:
        vis = payload.get("visualization")
        if vis is None:
            context["visualization"] = {}
        elif not isinstance(vis, dict):
            raise ValueError("visualization must be an object")
        else:
            vis = json.loads(json.dumps(vis))
            charts = vis.get("charts", [])
            if charts is not None and not isinstance(charts, list):
                raise ValueError("visualization.charts must be a list")
            if charts is not None:
                vis["charts"] = [write_chart_svg(state, chart) for chart in charts]
            context["visualization"] = vis
    return context


def _render_visualization(context: Dict[str, Any]) -> str:
    vis = context.get("visualization") if isinstance(context, dict) else None
    if not isinstance(vis, dict) or not vis:
        return "_No visualization diagnostic recorded yet._\n"
    out = ""
    if vis.get("alpha_id"):
        out += f"- Diagnostic Alpha: {_cell(vis.get('alpha_id'))}\n"
    if vis.get("control"):
        out += f"- Control: {_cell(vis.get('control'))}\n"
    recordsets = vis.get("recordsets")
    if isinstance(recordsets, list) and recordsets:
        out += f"- Recordsets: {_cell(', '.join(str(x) for x in recordsets))}\n"
    summary = vis.get("summary")
    if isinstance(summary, list):
        for item in summary:
            out += f"- {_cell(item)}\n"
    elif summary:
        out += f"- {_cell(summary)}\n"
    for chart in vis.get("charts") or []:
        if not isinstance(chart, dict) or not chart.get("asset"):
            continue
        title = chart.get("title") or chart.get("id") or "Visualization"
        out += f"\n**{_cell(title)}**\n\n![{_cell(title)}]({_cell(chart['asset'])})\n"
    return out or "_Visualization metadata is present but no renderable content was supplied._\n"


def render_dashboard(state: Dict[str, Any]) -> str:
    root = state.get("root_baseline") or {}
    current = state.get("incumbent") or root
    context = state.get("dashboard_context") or {}

    out = "## Alpha Snapshot / Dashboard\n\n"
    out += f"- **Root:** {_cell(root.get('alpha_id', state.get('root_alpha_id')))}\n"
    out += f"- **Current Incumbent:** {_cell(current.get('alpha_id'))}\n"
    out += f"- **Run status:** {_cell((state.get('run') or {}).get('status', 'RUNNING'))}\n\n"

    out += "### 1. Expression + Settings\n\n"
    expression = str(current.get("expression") or "unknown").replace("\n", " ")
    out += f"    {expression}\n\n"
    out += _render_settings(current.get("settings"))

    out += "\n### 2. Result\n\n"
    out += _render_metrics(root, current)
    out += "\n#### Current checks\n\n"
    out += _render_checks(current)

    out += "\n### 3. Field Information\n\n"
    out += _render_fields(context, list(current.get("fields") or []))

    out += "\n### 4. Visualization / Diagnostics\n\n"
    out += _render_visualization(context)

    out += "\n### Optimization Progression\n\n"
    out += _render_progression(state)

    out += "\n---\n\n## Audit Trail\n"
    return out

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
    registry: Dict[str, Dict[str, Any]] = {}
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, str) and item.strip():
                registry[item.strip()] = {"name": item.strip()}
            elif isinstance(item, dict) and item.get("name"):
                registry[str(item["name"])] = item

    # Dashboard Field Information describes the fields actually used by the
    # current Incumbent. The context is a metadata registry and may contain
    # pre-authorized fields that are not yet in the expression.
    rows = []
    for name in fallback:
        rows.append(registry.get(str(name), {"name": str(name)}))
    if not rows and registry:
        rows = list(registry.values())
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


def _compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _metric_map(snapshot: Dict[str, Any]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for key, value in (snapshot.get("metrics") or {}).items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            out[str(key).upper()] = float(value)
    return out


def _render_machine_decision_trail(state: Dict[str, Any]) -> str:
    hypotheses = state.get("hypotheses") or {}
    if not hypotheses:
        return "_No hypothesis has been opened in this run._\n"

    out = ""
    candidates = state.get("candidates") or {}
    evidence_registry = state.get("evidence") or {}

    for hid, hyp in hypotheses.items():
        hyp = hyp or {}
        contract = hyp.get("contract") or {}
        fingerprint = hyp.get("candidate_fingerprint")
        candidate = candidates.get(fingerprint, {}) if fingerprint else {}
        spec = candidate.get("spec") if isinstance(candidate.get("spec"), dict) else {}
        preflight = candidate.get("preflight") if isinstance(candidate.get("preflight"), dict) else {}
        result = hyp.get("result") if isinstance(hyp.get("result"), dict) else {}
        result_snapshot = result.get("evidence") if isinstance(result.get("evidence"), dict) else {}
        evaluation = result.get("evaluation") if isinstance(result.get("evaluation"), dict) else {}
        result_ref = result.get("evidence_ref") or candidate.get("result_evidence_ref")
        learned = evidence_registry.get(result_ref, {}) if result_ref else {}

        mechanism = contract.get("mechanism") or "unbound"
        out += f"### {_cell(hid)} — {_cell(mechanism)}\n\n"
        out += f"- **Machine status:** {_cell(hyp.get('status'))}\n"
        out += f"- **Parent Incumbent:** {_cell(spec.get('parent_id'))}\n"
        out += f"- **Route:** {_cell(hyp.get('route_id'))}; target={_cell(contract.get('target'))}\n"
        out += f"- **Frozen hypothesis:** {_cell(contract.get('principal_hypothesis'))}\n"
        out += f"- **Mutation:** `{_cell(_compact_json(contract.get('mutation') or {}))}`\n"
        out += f"- **Success criteria:** `{_cell(_compact_json(contract.get('success_criteria') or []))}`\n"
        out += f"- **Protected metrics:** `{_cell(_compact_json(contract.get('protected_metrics') or []))}`\n"
        out += f"- **Failure meaning:** {_cell(contract.get('failure_meaning'))}\n"
        refs = contract.get("evidence_refs") or []
        if refs:
            out += f"- **Evidence refs:** {_cell(', '.join(str(ref) for ref in refs))}\n"

        if fingerprint:
            out += f"- **Candidate fingerprint:** `{_cell(fingerprint)}`\n"
        if spec:
            out += f"- **Candidate fields:** {_cell(', '.join(str(x) for x in (spec.get('fields') or [])))}\n"
            expression = str(spec.get("expression") or "").strip()
            if expression:
                out += "\n**Candidate expression**\n\n"
                out += f"    {expression.replace(chr(10), ' ')}\n\n"
        if preflight:
            out += (
                f"- **Preflight drift:** complexity_vs_root={_cell(preflight.get('complexity_delta_vs_root'))}; "
                f"settings={_cell(', '.join(preflight.get('setting_diff_keys') or []))}; "
                f"fields={_cell(_compact_json(preflight.get('field_diff') or {}))}\n"
            )

        if result_snapshot:
            out += (
                f"- **Result Alpha:** {_cell(result_snapshot.get('alpha_id'))}; "
                f"source={_cell(result_snapshot.get('source'))}; "
                f"observed_at={_cell(result_snapshot.get('observed_at'))}\n"
            )
            metrics = _metric_map(result_snapshot)
            if metrics:
                preferred = ["SHARPE", "FITNESS", "RETURNS", "MARGIN", "TURNOVER", "DRAWDOWN", "PNL"]
                ordered = [name for name in preferred if name in metrics]
                ordered += [name for name in metrics if name not in ordered]
                out += "- **Result metrics:** " + "; ".join(
                    f"{name}={_cell(metrics[name])}" for name in ordered
                ) + "\n"

        if evaluation:
            failed_success = [
                str((row.get("criterion") or {}).get("name") or "")
                for row in evaluation.get("criterion_results", [])
                if isinstance(row, dict) and not row.get("passed")
            ]
            failed_protection = [
                str((row.get("policy") or {}).get("name") or "")
                for row in evaluation.get("protected_results", [])
                if isinstance(row, dict) and not row.get("passed")
            ]
            failed_root_protection = [
                str((row.get("policy") or {}).get("name") or "")
                for row in evaluation.get("root_protected_results", [])
                if isinstance(row, dict) and not row.get("passed")
            ]
            out += (
                f"- **Evaluation:** status={_cell(evaluation.get('status'))}; "
                f"failed_success={_cell(', '.join(failed_success))}; "
                f"failed_protection={_cell(', '.join(failed_protection))}; "
                f"failed_root_protection={_cell(', '.join(failed_root_protection))}; "
                f"new_blockers={_cell(', '.join(evaluation.get('new_blockers') or []))}; "
                f"new_unresolved={_cell(', '.join(evaluation.get('new_unresolved_checks') or []))}\n"
            )

        decision = candidate.get("status") or result.get("disposition") or hyp.get("status")
        out += f"- **Decision:** {_cell(decision)}\n"
        if candidate.get("disposition_reason"):
            out += f"- **Disposition reason:** {_cell(candidate.get('disposition_reason'))}\n"
        if learned.get("claim"):
            out += f"- **Learned evidence:** {_cell(learned.get('claim'))}\n"
        out += "\n"

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


def prepare_chart_snapshot(raw: Any, *, max_points: int = 32) -> Dict[str, Any]:
    """Keep a compact chart projection in embedded machine state, not as the user-facing chart."""
    chart = _normalize_chart(raw)
    total = len(chart["labels"])
    if total <= max_points:
        indices = list(range(total))
    else:
        indices = sorted({
            round(i * (total - 1) / (max_points - 1))
            for i in range(max_points)
        })
    return {
        "id": chart["id"],
        "title": chart["title"],
        "type": chart["type"],
        "labels": [chart["labels"][i] for i in indices],
        "series": [
            {
                "name": row["name"],
                "values": [row["values"][i] for i in indices],
            }
            for row in chart["series"]
        ],
        "sampled": total > len(indices),
        "original_point_count": total,
    }


def _svg_text(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _chart_svg_group(
    chart: Dict[str, Any],
    *,
    y_offset: int,
    width: int,
    panel_height: int,
) -> list[str]:
    left, right, top, bottom = 82, 28, 54, 58
    plot_w = width - left - right
    plot_h = panel_height - top - bottom
    all_values = [value for row in chart["series"] for value in row["values"]]
    ymin, ymax = min(all_values), max(all_values)
    if chart["type"] == "bar":
        ymin = min(ymin, 0.0)
        ymax = max(ymax, 0.0)
    if ymin == ymax:
        pad = abs(ymin) * 0.05 or 1.0
    else:
        pad = (ymax - ymin) * 0.08
    ymin, ymax = ymin - pad, ymax + pad

    def x_at(index: int) -> float:
        count = len(chart["labels"])
        if chart["type"] == "bar":
            return left + (index + 0.5) * plot_w / max(count, 1)
        return left + index * plot_w / max(count - 1, 1)

    def y_at(value: float) -> float:
        return top + (ymax - value) * plot_h / (ymax - ymin)

    palette = ["#2f80ed", "#27ae60", "#f2994a", "#9b51e0", "#eb5757", "#56ccf2"]
    pieces = [
        f'<g transform="translate(0,{y_offset})">',
        f'<rect x="0" y="0" width="{width}" height="{panel_height}" fill="white"/>',
        f'<text x="{left}" y="30" font-family="Arial,sans-serif" font-size="18" '
        f'font-weight="600" fill="#222">{_svg_text(chart["title"])}</text>',
    ]

    for tick in range(5):
        value = ymin + (ymax - ymin) * tick / 4
        y = y_at(value)
        pieces.append(
            f'<line x1="{left}" y1="{y:.2f}" x2="{width-right}" y2="{y:.2f}" '
            'stroke="#e6e6e6" stroke-width="1"/>'
        )
        pieces.append(
            f'<text x="{left-10}" y="{y+4:.2f}" text-anchor="end" '
            f'font-family="Arial,sans-serif" font-size="11" fill="#666">{value:.4g}</text>'
        )

    labels = chart["labels"]
    label_step = max(1, math.ceil(len(labels) / 8))
    shown = set(range(0, len(labels), label_step))
    shown.add(len(labels) - 1)
    for index in sorted(shown):
        x = x_at(index)
        pieces.append(
            f'<text x="{x:.2f}" y="{panel_height-28}" text-anchor="middle" '
            f'font-family="Arial,sans-serif" font-size="10" fill="#666">'
            f'{_svg_text(labels[index][:18])}</text>'
        )

    if chart["type"] == "line":
        for series_index, series in enumerate(chart["series"]):
            color = palette[series_index % len(palette)]
            points = " ".join(
                f"{x_at(index):.2f},{y_at(value):.2f}"
                for index, value in enumerate(series["values"])
            )
            pieces.append(
                f'<polyline fill="none" stroke="{color}" stroke-width="1.8" '
                f'stroke-linejoin="round" stroke-linecap="round" points="{points}"/>'
            )
    else:
        count = len(labels)
        group_w = plot_w / max(count, 1)
        gap = min(group_w * 0.14, 10.0)
        bar_w = max(1.0, (group_w - 2 * gap) / max(len(chart["series"]), 1))
        zero_y = y_at(0.0) if ymin <= 0 <= ymax else y_at(ymin)
        for series_index, series in enumerate(chart["series"]):
            color = palette[series_index % len(palette)]
            for index, value in enumerate(series["values"]):
                x = left + index * group_w + gap + series_index * bar_w
                y = y_at(value)
                rect_y = min(y, zero_y)
                rect_h = max(1.0, abs(zero_y - y))
                pieces.append(
                    f'<rect x="{x:.2f}" y="{rect_y:.2f}" width="{bar_w*0.88:.2f}" '
                    f'height="{rect_h:.2f}" fill="{color}" opacity="0.88"/>'
                )

    if len(chart["series"]) > 1:
        legend_x = left
        legend_y = panel_height - 8
        for series_index, series in enumerate(chart["series"]):
            color = palette[series_index % len(palette)]
            pieces.append(
                f'<rect x="{legend_x}" y="{legend_y-10}" width="10" height="10" fill="{color}"/>'
            )
            pieces.append(
                f'<text x="{legend_x+14}" y="{legend_y}" font-family="Arial,sans-serif" '
                f'font-size="10" fill="#555">{_svg_text(series["name"][:24])}</text>'
            )
            legend_x += 175

    pieces.append(
        f'<line x1="24" y1="{panel_height-1}" x2="{width-24}" y2="{panel_height-1}" '
        'stroke="#d9d9d9" stroke-width="1"/>'
    )
    pieces.append("</g>")
    return pieces


def write_dashboard_svg(state: Dict[str, Any], raw_charts: list[Any]) -> str | None:
    charts = [_normalize_chart(chart) for chart in raw_charts]
    if not charts:
        return None

    run = state.get("run") or {}
    raw_log_path = run.get("log_path")
    if not raw_log_path:
        raise ValueError("run log is required before SVG dashboard rendering")
    log_path = Path(str(raw_log_path)).expanduser().resolve()
    filename = f"{log_path.stem}_dashboard.svg"
    target = log_path.with_name(filename)

    width = 1100
    panel_height = 330
    header_height = 46
    total_height = header_height + panel_height * len(charts)
    pieces = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{total_height}" '
        f'viewBox="0 0 {width} {total_height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="24" y="30" font-family="Arial,sans-serif" font-size="20" '
        f'font-weight="700" fill="#111">Alpha Visualization Dashboard</text>',
    ]
    for index, chart in enumerate(charts):
        pieces.extend(
            _chart_svg_group(
                chart,
                y_offset=header_height + index * panel_height,
                width=width,
                panel_height=panel_height,
            )
        )
    pieces.append("</svg>")
    target.write_text("\n".join(pieces) + "\n", encoding="utf-8")
    return filename


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
        existing = {
            str(row.get("name")): row
            for row in (context.get("fields") or [])
            if isinstance(row, dict) and row.get("name")
        }
        for row in normalized:
            name = str(row["name"])
            merged = dict(existing.get(name, {}))
            merged.update(row)
            existing[name] = merged
        context["fields"] = list(existing.values())

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
                asset = write_dashboard_svg(state, charts)
                vis["charts"] = [prepare_chart_snapshot(chart) for chart in charts]
                if asset:
                    vis["asset"] = asset
                else:
                    vis.pop("asset", None)
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
    unavailable = vis.get("unavailable_recordsets")
    if isinstance(unavailable, list) and unavailable:
        out += f"- Unavailable after bounded fetch: {_cell(', '.join(str(x) for x in unavailable))}\n"
    unrendered = vis.get("unrendered_recordsets")
    if isinstance(unrendered, list) and unrendered:
        out += f"- Raw/table-only recordsets: {_cell(', '.join(str(x) for x in unrendered))}\n"

    chart_rows = [row for row in (vis.get("charts") or []) if isinstance(row, dict)]
    if chart_rows:
        out += "- Charts: " + _cell(
            "; ".join(str(row.get("title") or row.get("id") or "Visualization") for row in chart_rows)
        ) + "\n"

    asset = vis.get("asset")
    if asset:
        chart_count = len(chart_rows)
        out += (
            f"\n**Visualization Dashboard ({chart_count} chart"
            f"{'s' if chart_count != 1 else ''})**\n\n"
            f"![Visualization Dashboard]({_cell(asset)})\n"
        )
    elif vis.get("charts"):
        out += (
            "\n_Chart metadata is present, but this legacy run has no SVG dashboard asset. "
            "Refresh the dashboard to render the SVG._\n"
        )
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

    out += "\n---\n\n## Audit Trail\n\n"
    out += "### Machine Decision Trail\n\n"
    out += _render_machine_decision_trail(state)
    out += "\n### Append-only Notes\n"
    return out

from __future__ import annotations

from typing import Any


RECORDSET_ORDER = [
    "pnl",
    "daily-pnl",
    "sharpe",
    "turnover",
    "coverage",
    "yearly-stats",
    "coverage-by-cap",
    "coverage-by-capitalization",
    "coverage-by-sector",
    "coverage-by-industry",
    "average-size-by-cap",
    "average-size-by-capitalization",
    "average-size-by-sector",
    "average-size-by-industry",
    "average-value-by-sector",
    "average-value-by-industry",
    "pnl-by-cap",
    "pnl-by-capitalization",
    "pnl-by-sector",
    "pnl-by-industry",
    "sharpe-by-cap",
    "sharpe-by-capitalization",
    "sharpe-by-sector",
    "sharpe-by-industry",
]


def _properties(recordset: dict) -> list[dict]:
    schema = recordset.get("schema") if isinstance(recordset, dict) else None
    props = schema.get("properties") if isinstance(schema, dict) else None
    return props if isinstance(props, list) else []


def _records(recordset: dict) -> list[list[Any]]:
    rows = recordset.get("records") if isinstance(recordset, dict) else None
    return rows if isinstance(rows, list) else []


def _column_names(recordset: dict) -> list[str]:
    return [str(row.get("name")) for row in _properties(recordset) if isinstance(row, dict) and row.get("name")]


def _column_types(recordset: dict) -> list[str]:
    return [str(row.get("type") or "").lower() for row in _properties(recordset) if isinstance(row, dict)]


def _is_numeric_type(value: str) -> bool:
    return value in {"number", "integer", "float", "amount", "percent", "ratio", "currency"}


def _title(recordset_name: str, recordset: dict) -> str:
    schema = recordset.get("schema") if isinstance(recordset, dict) else None
    if isinstance(schema, dict) and schema.get("title"):
        return str(schema["title"])
    return recordset_name.replace("-", " ").title()


def _line_chart(recordset_name: str, recordset: dict) -> dict | None:
    names = _column_names(recordset)
    types = _column_types(recordset)
    rows = _records(recordset)
    if not names or not rows:
        return None

    x_index = None
    for index, (name, kind) in enumerate(zip(names, types)):
        if kind == "date" or name.lower() in {"date", "day", "year"}:
            x_index = index
            break
    if x_index is None:
        return None

    numeric_indices = [
        i for i, kind in enumerate(types)
        if i != x_index and _is_numeric_type(kind)
    ]
    if not numeric_indices:
        return None

    labels = []
    series_values = [[] for _ in numeric_indices]
    for row in rows:
        if not isinstance(row, list) or len(row) < len(names):
            continue
        labels.append(str(row[x_index]))
        for target, column_index in zip(series_values, numeric_indices):
            value = row[column_index]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                target.append(None)
            else:
                target.append(float(value))

    if not labels:
        return None

    # Current SVG renderer requires finite numeric values. Keep only complete rows;
    # do not interpolate or fabricate missing values.
    keep = [
        i for i in range(len(labels))
        if all(values[i] is not None for values in series_values)
    ]
    labels = [labels[i] for i in keep]
    if not labels:
        return None

    series = []
    for column_index, values in zip(numeric_indices, series_values):
        series.append({
            "name": names[column_index],
            "values": [values[i] for i in keep],
        })

    return {
        "id": recordset_name,
        "title": _title(recordset_name, recordset),
        "type": "line",
        "labels": labels,
        "series": series,
    }


def _bar_chart(recordset_name: str, recordset: dict) -> dict | None:
    if "-by-" not in recordset_name:
        return None
    names = _column_names(recordset)
    types = _column_types(recordset)
    rows = _records(recordset)
    if len(names) < 2 or not rows:
        return None

    label_index = 0
    numeric_indices = [
        i for i, kind in enumerate(types)
        if i != label_index and _is_numeric_type(kind)
    ]
    if not numeric_indices:
        return None

    labels = []
    values_by_column = [[] for _ in numeric_indices]
    for row in rows:
        if not isinstance(row, list) or len(row) < len(names):
            continue
        numeric_values = []
        valid = True
        for column_index in numeric_indices:
            value = row[column_index]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                valid = False
                break
            numeric_values.append(float(value))
        if not valid:
            continue
        labels.append(str(row[label_index]))
        for target, value in zip(values_by_column, numeric_values):
            target.append(value)

    if not labels:
        return None

    return {
        "id": recordset_name,
        "title": _title(recordset_name, recordset),
        "type": "bar",
        "labels": labels,
        "series": [
            {"name": names[column_index], "values": values}
            for column_index, values in zip(numeric_indices, values_by_column)
        ],
    }


def chart_from_recordset(recordset_name: str, recordset: dict) -> dict | None:
    # yearly-stats often mixes incomparable metrics; keep it as raw/table evidence
    # rather than forcing a misleading shared-axis chart.
    if recordset_name == "yearly-stats":
        return None
    if "-by-" in recordset_name:
        return _bar_chart(recordset_name, recordset)
    return _line_chart(recordset_name, recordset)


def charts_from_recordsets(recordsets: dict[str, dict]) -> list[dict]:
    if not isinstance(recordsets, dict):
        return []

    known_order = {name: i for i, name in enumerate(RECORDSET_ORDER)}
    names = sorted(recordsets, key=lambda name: (known_order.get(name, 10_000), name))
    charts = []
    for name in names:
        recordset = recordsets.get(name)
        if not isinstance(recordset, dict):
            continue
        chart = chart_from_recordset(name, recordset)
        if chart:
            charts.append(chart)
    return charts


def dashboard_visualization_from_recordsets(
    alpha_id: str,
    control: str,
    listing: dict,
    recordsets: dict[str, dict],
) -> dict:
    listed = listing.get("results") if isinstance(listing, dict) else None
    names = [
        str(row.get("name"))
        for row in (listed if isinstance(listed, list) else [])
        if isinstance(row, dict) and row.get("name")
    ]
    charts = charts_from_recordsets(recordsets)
    return {
        "alpha_id": alpha_id,
        "control": control,
        "recordsets": names,
        "summary": [
            f"{len(names)} recordsets discovered.",
            f"{len(charts)} recordsets have deterministic chart renderers; remaining recordsets stay as raw evidence.",
        ],
        "charts": charts,
    }

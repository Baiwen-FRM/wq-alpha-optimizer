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


def _temporal_index(names: list[str], types: list[str]) -> int | None:
    temporal_names = {"date", "day", "year", "time", "timestamp"}
    for index, (name, kind) in enumerate(zip(names, types)):
        if kind in {"date", "datetime", "timestamp"} or name.lower() in temporal_names:
            return index
    return None


def _category_index(names: list[str], types: list[str]) -> int | None:
    preferred = {
        "bucket", "capitalization", "cap", "sector", "industry", "subindustry",
        "country", "region", "group", "label", "name",
    }
    for index, (name, kind) in enumerate(zip(names, types)):
        if name.lower() in preferred and not _is_numeric_type(kind):
            return index
    for index, kind in enumerate(types):
        if not _is_numeric_type(kind) and kind not in {"date", "datetime", "timestamp"}:
            return index
    return None


def _boundary_indices(names: list[str], types: list[str]) -> tuple[int, int] | None:
    lower_tokens = ("min", "lower", "from", "start", "left")
    upper_tokens = ("max", "upper", "to", "end", "right")

    def find(tokens: tuple[str, ...]) -> int | None:
        for index, (name, kind) in enumerate(zip(names, types)):
            normalized = name.lower().replace("_", "").replace("-", "")
            if _is_numeric_type(kind) and any(token in normalized for token in tokens):
                return index
        return None

    lower = find(lower_tokens)
    upper = find(upper_tokens)
    if lower is None or upper is None or lower == upper:
        return None
    return lower, upper


def _format_bucket_value(value: Any) -> str:
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float)):
        numeric = float(value)
        return f"{numeric:g}"
    return str(value)


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

    x_index = _temporal_index(names, types)
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

    category_index = _category_index(names, types)
    boundaries = _boundary_indices(names, types) if category_index is None else None

    excluded: set[int] = set()
    if category_index is not None:
        excluded.add(category_index)
    elif boundaries is not None:
        excluded.update(boundaries)
    else:
        # Preserve the legacy deterministic fallback for simple two-column
        # bucket recordsets whose first bucket column is numeric.
        category_index = 0
        excluded.add(0)

    numeric_indices = [
        i for i, kind in enumerate(types)
        if i not in excluded and _is_numeric_type(kind)
    ]
    if not numeric_indices:
        return None

    labels: list[str] = []
    values_by_column = [[] for _ in numeric_indices]
    for row in rows:
        if not isinstance(row, list) or len(row) < len(names):
            continue

        if boundaries is not None:
            lower, upper = boundaries
            label = f"{_format_bucket_value(row[lower])}–{_format_bucket_value(row[upper])}"
        elif category_index is not None:
            label = str(row[category_index])
        else:
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
        labels.append(label)
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

    names = _column_names(recordset)
    types = _column_types(recordset)

    # Schema semantics outrank recordset naming. "-by-" recordsets can still be
    # time series (for example PnL by capitalization/industry across dates).
    # Those must be multi-line charts, not thousands of thin bars.
    if _temporal_index(names, types) is not None:
        return _line_chart(recordset_name, recordset)
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
    rendered = {str(chart.get("id")) for chart in charts if isinstance(chart, dict) and chart.get("id")}
    fetched = set(recordsets)
    unavailable = [name for name in names if name not in fetched]
    unrendered = [name for name in names if name in fetched and name not in rendered]
    return {
        "alpha_id": alpha_id,
        "control": control,
        "recordsets": names,
        "unavailable_recordsets": unavailable,
        "unrendered_recordsets": unrendered,
        "summary": [
            f"{len(names)} recordsets discovered.",
            f"{len(charts)} recordsets have deterministic chart renderers.",
            f"{len(unavailable)} listed recordsets were unavailable after bounded fetch.",
            f"{len(unrendered)} fetched recordsets remain raw/table evidence.",
        ],
        "charts": charts,
    }

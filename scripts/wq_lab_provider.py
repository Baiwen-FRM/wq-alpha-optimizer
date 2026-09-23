from __future__ import annotations

import argparse
import contextlib
import copy
import importlib
import io
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from optimizer_guard import inspect_expression
from recordset_dashboard import dashboard_visualization_from_recordsets


BASE_RECORDSETS = {"pnl", "sharpe", "turnover", "daily-pnl", "yearly-stats"}


def _load_wq_lib(*, require_submission_start: bool = False):
    try:
        module = importlib.import_module("wq_lib")
    except ImportError as exc:
        raise RuntimeError(
            "wq_lib is not importable in this Python environment. "
            "Install/use the local WQ Lab environment before running the optimizer."
        ) from exc
    required = [
        "login", "get_result", "get_submission_check", "get_datafield",
        "get_alpha_recordsets", "get_alpha_recordset", "get_prod_corr",
        "get_self_corr", "get_operators", "simulate_single",
    ]
    if require_submission_start:
        required.append("_start_simulation")
    missing = [name for name in required if not callable(getattr(module, name, None))]
    if missing:
        raise RuntimeError(
            "local wq_lib is missing required additive primitives: " + ", ".join(missing)
        )
    return module


def _code(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("code") or "")
    return "" if value is None else str(value)


def _expression_codes(details: dict) -> list[str]:
    alpha_type = str(details.get("type") or "REGULAR").upper()
    if alpha_type == "SUPER":
        return [code for code in (_code(details.get("selection")), _code(details.get("combo"))) if code]
    code = _code(details.get("regular"))
    return [code] if code else []


def _used_fields(details: dict) -> list[str]:
    fields: set[str] = set()
    for expression in _expression_codes(details):
        inspected = inspect_expression(expression)
        if inspected.get("parse_ok") and isinstance(inspected.get("identifiers"), list):
            fields.update(str(x) for x in inspected["identifiers"])
    return sorted(fields)


def _scope_match(row: dict, settings: dict) -> bool:
    return (
        str(row.get("region")) == str(settings.get("region"))
        and str(row.get("delay")) == str(settings.get("delay"))
        and str(row.get("universe")) == str(settings.get("universe"))
    )


def _field_dashboard_row(field: dict, settings: dict) -> dict:
    data_rows = field.get("data") if isinstance(field.get("data"), list) else []
    selected = next((row for row in data_rows if isinstance(row, dict) and _scope_match(row, settings)), {})
    dataset = field.get("dataset") if isinstance(field.get("dataset"), dict) else {}
    return {
        "name": field.get("id"),
        "type": field.get("type"),
        "dataset": dataset.get("id") or dataset.get("name"),
        "coverage": selected.get("coverage"),
        "dateCoverage": selected.get("dateCoverage"),
        "description": field.get("description"),
        "visualizable": field.get("visualizable"),
    }


def _metrics(details: dict) -> dict:
    values = details.get("is") if isinstance(details.get("is"), dict) else {}
    keys = (
        "sharpe", "fitness", "returns", "margin", "turnover", "drawdown", "pnl",
        "longCount", "shortCount", "bookSize",
    )
    return {key: values.get(key) for key in keys if key in values}


def _detail_checks(details: dict) -> list[dict]:
    values = details.get("is") if isinstance(details.get("is"), dict) else {}
    checks = values.get("checks")
    return checks if isinstance(checks, list) else []


def _dedicated_check_snapshot_present(payload: dict) -> bool:
    values = payload.get("is") if isinstance(payload, dict) and isinstance(payload.get("is"), dict) else payload
    return isinstance(values, dict) and isinstance(values.get("checks"), list)


def _guard_checks(payload: dict) -> list[dict]:
    values = payload.get("is") if isinstance(payload, dict) and isinstance(payload.get("is"), dict) else payload
    checks = values.get("checks") if isinstance(values, dict) else None
    rows = []
    for item in (checks if isinstance(checks, list) else []):
        if not isinstance(item, dict) or not item.get("name"):
            continue
        status = item.get("status") or item.get("result")
        if not status:
            continue
        row = dict(item)
        row["name"] = str(item["name"])
        row["status"] = str(status).upper()
        row.pop("result", None)
        rows.append(row)
    return rows


def result_evidence_snapshot(session, wq, alpha_id: str, simulation_id: str) -> dict:
    details = wq.get_result(session, alpha_id)
    if not isinstance(details, dict) or not details:
        return {
            "alpha_id": alpha_id,
            "simulation_id": simulation_id,
            "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "source": "BRAIN:wq_lib.get_result+get_submission_check",
            "response_complete": False,
            "authenticated": True,
            "metrics": {},
            "checks": [],
        }

    dedicated_payload = wq.get_submission_check(session, alpha_id)
    dedicated_checks = _guard_checks(dedicated_payload if isinstance(dedicated_payload, dict) else {})
    raw_metrics = _metrics(details)
    metrics = {
        key: value
        for key, value in raw_metrics.items()
        if not isinstance(value, bool) and isinstance(value, (int, float))
    }
    # response_complete means the current Result + dedicated check snapshot
    # is structurally present. A PENDING/UNKNOWN check is still a real current
    # observation; readiness policy is handled by Guard rather than hidden in
    # the provider.
    checks_present = _dedicated_check_snapshot_present(
        dedicated_payload if isinstance(dedicated_payload, dict) else {}
    )
    return {
        "alpha_id": alpha_id,
        "simulation_id": simulation_id,
        "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": "BRAIN:wq_lib.get_result+get_submission_check",
        "response_complete": checks_present,
        "authenticated": True,
        "metrics": metrics,
        "checks": dedicated_checks,
    }


def _baseline_from_root(root: dict) -> dict:
    details = root.get("details_raw") if isinstance(root.get("details_raw"), dict) else {}
    expressions = root.get("expressions") if isinstance(root.get("expressions"), list) else []
    if str(root.get("type") or "REGULAR").upper() != "REGULAR" or len(expressions) != 1:
        raise RuntimeError("optimizer_guard FE baseline currently requires one REGULAR FASTEXPR expression")
    settings = copy.deepcopy(root.get("settings") if isinstance(root.get("settings"), dict) else {})
    for key in list(settings):
        if str(key).lower() == "testperiod":
            settings.pop(key)
    dedicated_check_payload = root.get("submission_check_raw") if isinstance(root.get("submission_check_raw"), dict) else {}
    dedicated_checks = _guard_checks(dedicated_check_payload)
    fallback_checks = _guard_checks(details)
    dedicated_complete = _dedicated_check_snapshot_present(dedicated_check_payload)
    checks = dedicated_checks if dedicated_complete else fallback_checks
    source = (
        "BRAIN:wq_lib.get_result+get_submission_check"
        if dedicated_complete
        else "BRAIN:wq_lib.get_result(checks_fallback)"
    )
    return {
        "alpha_id": root["alpha_id"],
        "expression": expressions[0],
        "fields": [row["field_id"] for row in root.get("fields", []) if isinstance(row, dict) and row.get("field_id")],
        "settings": settings,
        "language": str(settings.get("language") or "FASTEXPR"),
        "result_evidence": {
            "metrics": root.get("metrics") or {},
            "checks": checks,
            "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "source": source,
            "response_complete": dedicated_complete,
            "authenticated": True,
        },
    }


def _dashboard_from_intake(root: dict, visualization: dict) -> dict:
    fields = [
        row["dashboard"]
        for row in root.get("fields", [])
        if isinstance(row, dict) and isinstance(row.get("dashboard"), dict)
    ]
    vis = visualization.get("dashboard_visualization") if isinstance(visualization, dict) else {}
    return {"fields": fields, "visualization": vis if isinstance(vis, dict) else {}}


def root_snapshot(session, wq, alpha_id: str) -> dict:
    details = wq.get_result(session, alpha_id)
    if not isinstance(details, dict) or not details:
        raise RuntimeError(f"Unable to read Alpha details for {alpha_id}")

    settings = details.get("settings") if isinstance(details.get("settings"), dict) else {}
    fields = []
    for field_id in _used_fields(details):
        field = wq.get_datafield(session, field_id)
        fields.append(
            {
                "field_id": field_id,
                "raw": field if isinstance(field, dict) else {},
                "dashboard": _field_dashboard_row(field, settings) if isinstance(field, dict) else {"name": field_id},
            }
        )

    submission_check = wq.get_submission_check(session, alpha_id)
    return {
        "alpha_id": alpha_id,
        "type": details.get("type"),
        "expressions": _expression_codes(details),
        "settings": settings,
        "metrics": _metrics(details),
        "detail_checks": _detail_checks(details),
        "submission_check_raw": submission_check if isinstance(submission_check, dict) else {},
        "fields": fields,
        "details_raw": details,
    }


def _visualization_payload(details: dict) -> dict:
    payload = {
        "type": str(details.get("type") or "REGULAR").upper(),
        "settings": copy.deepcopy(details.get("settings") if isinstance(details.get("settings"), dict) else {}),
    }
    payload["settings"]["visualization"] = True
    if payload["type"] == "SUPER":
        payload["selection"] = _code(details.get("selection"))
        payload["combo"] = _code(details.get("combo"))
    else:
        payload["regular"] = _code(details.get("regular"))
    return payload


def _recordset_names(listing: dict) -> list[str]:
    rows = listing.get("results") if isinstance(listing, dict) else None
    if not isinstance(rows, list):
        return []
    names = [str(row.get("name")) for row in rows if isinstance(row, dict) and row.get("name")]
    return names


def _discover_recordsets(session, wq, alpha_id: str, attempts: int, sleep_seconds: float) -> tuple[dict, list[str]]:
    best_listing: dict = {}
    best_names: list[str] = []
    previous_rich_names: list[str] | None = None
    rich_stable_reads = 0

    for attempt in range(max(1, attempts)):
        listing = wq.get_alpha_recordsets(session, alpha_id)
        names = _recordset_names(listing)
        if len(names) > len(best_names):
            best_listing, best_names = listing, names

        # Do not stop at the first rich recordset. Visualization recordsets can
        # appear incrementally after the simulation resolves. Once a rich
        # listing is observed twice unchanged, treat the currently available
        # set as stable. If it never stabilizes within the bounded budget,
        # return the largest listing observed rather than dropping late entries.
        if set(names) - BASE_RECORDSETS:
            if names == previous_rich_names:
                rich_stable_reads += 1
            else:
                rich_stable_reads = 1
                previous_rich_names = list(names)
            if rich_stable_reads >= 2:
                return listing, names
        else:
            previous_rich_names = None
            rich_stable_reads = 0

        if attempt + 1 < max(1, attempts) and sleep_seconds > 0:
            time.sleep(sleep_seconds)

    return best_listing, best_names


def visualization_snapshot(
    session,
    wq,
    alpha_id: str,
    *,
    details: dict | None = None,
    discovery_attempts: int = 4,
    discovery_sleep_seconds: float = 2.0,
) -> dict:
    details = details if isinstance(details, dict) and details else wq.get_result(session, alpha_id)
    if not isinstance(details, dict) or not details:
        raise RuntimeError(f"Unable to read Alpha details for {alpha_id}")

    root_visualization_enabled = bool(
        isinstance(details.get("settings"), dict) and details["settings"].get("visualization")
    )
    root_attempts = max(1, discovery_attempts) if root_visualization_enabled else 1
    root_listing, root_names = _discover_recordsets(
        session, wq, alpha_id, root_attempts, discovery_sleep_seconds
    )
    diagnostic_alpha_id = alpha_id
    control = "existing Alpha recordsets"
    simulation = None

    if not (set(root_names) - BASE_RECORDSETS):
        payload = _visualization_payload(details)
        simulation = wq.simulate_single(session, payload)
        if not isinstance(simulation, dict) or simulation.get("status") != "done" or not simulation.get("alpha_id"):
            return {
                "ok": False,
                "alpha_id": alpha_id,
                "diagnostic_alpha_id": None,
                "control": "same expression/settings; visualization=true",
                "simulation": simulation,
                "recordset_listing": root_listing,
                "recordsets": {},
                "dashboard_visualization": {
                    "alpha_id": None,
                    "control": "same expression/settings; visualization=true",
                    "recordsets": root_names,
                    "summary": ["Visualization control did not produce a resolved diagnostic Alpha."],
                    "charts": [],
                },
            }
        diagnostic_alpha_id = str(simulation["alpha_id"])
        control = "same expression/settings; visualization=true"
        listing, names = _discover_recordsets(
            session, wq, diagnostic_alpha_id, max(1, discovery_attempts), discovery_sleep_seconds
        )
    else:
        listing, names = root_listing, root_names

    recordsets: dict[str, dict] = {}
    for name in names:
        data = wq.get_alpha_recordset(session, diagnostic_alpha_id, name)
        if isinstance(data, dict) and data:
            recordsets[name] = data

    dashboard_visualization = dashboard_visualization_from_recordsets(
        diagnostic_alpha_id, control, listing, recordsets
    )
    return {
        "ok": True,
        "alpha_id": alpha_id,
        "diagnostic_alpha_id": diagnostic_alpha_id,
        "control": control,
        "simulation": simulation,
        "recordset_listing": listing,
        "recordsets": recordsets,
        "dashboard_visualization": dashboard_visualization,
    }


def intake_snapshot(
    alpha_id: str,
    *,
    discovery_attempts: int = 4,
    discovery_sleep_seconds: float = 2.0,
) -> dict:
    wq = _load_wq_lib()
    session = wq.login()
    root = root_snapshot(session, wq, alpha_id)
    visualization = visualization_snapshot(
        session,
        wq,
        alpha_id,
        details=root["details_raw"],
        discovery_attempts=discovery_attempts,
        discovery_sleep_seconds=discovery_sleep_seconds,
    )
    return {
        "root": root,
        "visualization": visualization,
        "baseline": _baseline_from_root(root),
        "dashboard": _dashboard_from_intake(root, visualization),
    }


def _json_default(value: Any):
    if hasattr(value, "to_dict"):
        try:
            return value.to_dict(orient="records")
        except TypeError:
            return value.to_dict()
    return str(value)


def _emit(data: Any, output: str | None = None) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=2, default=_json_default)
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
        print(json.dumps({"ok": True, "output": str(path)}, ensure_ascii=False))
        return
    print(text)


def _load_json_file(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Thin deterministic bridge from wq-alpha-optimizer to local WQ Lab/wq_lib.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("intake")
    p.add_argument("--alpha-id", required=True)
    p.add_argument("--output")
    p.add_argument("--baseline-output")
    p.add_argument("--dashboard-output")
    p.add_argument("--discovery-attempts", type=int, default=4)
    p.add_argument("--discovery-sleep-seconds", type=float, default=2.0)

    p = sub.add_parser("root-snapshot")
    p.add_argument("--alpha-id", required=True)
    p.add_argument("--output")

    p = sub.add_parser("result-evidence")
    p.add_argument("--alpha-id", required=True)
    p.add_argument("--simulation-id", required=True)
    p.add_argument("--output")

    p = sub.add_parser("visualization-snapshot")
    p.add_argument("--alpha-id", required=True)
    p.add_argument("--output")
    p.add_argument("--discovery-attempts", type=int, default=4)
    p.add_argument("--discovery-sleep-seconds", type=float, default=2.0)

    p = sub.add_parser("simulate")
    p.add_argument("--payload", required=True)
    p.add_argument("--location")
    p.add_argument("--output")

    p = sub.add_parser("operators")
    p.add_argument("--output")

    p = sub.add_parser("correlation")
    p.add_argument("--alpha-id", required=True)
    p.add_argument("--type", choices=["prod", "self"], required=True)
    p.add_argument("--output")

    args = parser.parse_args()
    wq = _load_wq_lib()
    with contextlib.redirect_stdout(io.StringIO()):
        session = wq.login()

    if args.cmd == "intake":
        root = root_snapshot(session, wq, args.alpha_id)
        vis = visualization_snapshot(
            session,
            wq,
            args.alpha_id,
            details=root["details_raw"],
            discovery_attempts=args.discovery_attempts,
            discovery_sleep_seconds=args.discovery_sleep_seconds,
        )
        data = {
            "root": root,
            "visualization": vis,
            "baseline": _baseline_from_root(root),
            "dashboard": _dashboard_from_intake(root, vis),
        }
        if args.baseline_output:
            Path(args.baseline_output).parent.mkdir(parents=True, exist_ok=True)
            Path(args.baseline_output).write_text(
                json.dumps(data["baseline"], ensure_ascii=False, indent=2, default=_json_default) + "\n",
                encoding="utf-8",
            )
        if args.dashboard_output:
            Path(args.dashboard_output).parent.mkdir(parents=True, exist_ok=True)
            Path(args.dashboard_output).write_text(
                json.dumps(data["dashboard"], ensure_ascii=False, indent=2, default=_json_default) + "\n",
                encoding="utf-8",
            )
        _emit(data, args.output)
    elif args.cmd == "root-snapshot":
        _emit(root_snapshot(session, wq, args.alpha_id), args.output)
    elif args.cmd == "result-evidence":
        _emit(result_evidence_snapshot(session, wq, args.alpha_id, args.simulation_id), args.output)
    elif args.cmd == "visualization-snapshot":
        _emit(
            visualization_snapshot(
                session,
                wq,
                args.alpha_id,
                discovery_attempts=args.discovery_attempts,
                discovery_sleep_seconds=args.discovery_sleep_seconds,
            ),
            args.output,
        )
    elif args.cmd == "simulate":
        payload = _load_json_file(args.payload)
        _emit(wq.simulate_single(session, payload, location=args.location), args.output)
    elif args.cmd == "operators":
        _emit(wq.get_operators(session), args.output)
    elif args.cmd == "correlation":
        fn = wq.get_prod_corr if args.type == "prod" else wq.get_self_corr
        _emit(fn(session, args.alpha_id), args.output)


if __name__ == "__main__":
    main()

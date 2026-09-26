from __future__ import annotations

import argparse
import contextlib
import io
import json
from pathlib import Path
from typing import Any

import optimizer_guard as guard
import wq_lab_provider as provider


def _append_bootstrap_note(store: guard.StateStore, *, status: str, detail: str) -> None:
    store.append_log(
        "BOOTSTRAP",
        f"- Status: `{status}`\n- Detail: {detail}",
    )


def bootstrap_run(
    alpha_id: str,
    *,
    discovery_attempts: int = 4,
    discovery_sleep_seconds: float = 2.0,
) -> dict[str, Any]:
    # Local compatibility check is allowed before the run starts because it
    # performs no BRAIN I/O and should not create a failed run artifact.
    try:
        provider._load_wq_lib()
    except Exception as exc:
        return {
            "ok": False,
            "stage": "LOCAL_PROVIDER_PREFLIGHT",
            "root_alpha_id": alpha_id,
            "error": str(exc),
        }

    started = guard.start_or_resume(alpha_id)
    if not started.get("ok"):
        return {"ok": False, "stage": "START_OR_RESUME", "detail": started}

    state_path = Path(str(started["state_path"]))
    log_path = Path(str(started["log_path"]))
    run_id = str(started["run_id"])
    store = guard.StateStore(state_path, alpha_id)

    try:
        with contextlib.redirect_stdout(io.StringIO()):
            intake = provider.intake_snapshot(
                alpha_id,
                discovery_attempts=discovery_attempts,
                discovery_sleep_seconds=discovery_sleep_seconds,
            )
    except Exception as exc:
        detail = f"WQ Lab intake failed: {exc}"
        store.set_run_phase_status("RECOVERY_REQUIRED", detail)
        _append_bootstrap_note(store, status="RECOVERY_REQUIRED", detail=detail)
        return {
            "ok": False,
            "stage": "WQ_LAB_INTAKE",
            "run_id": run_id,
            "state_path": str(state_path),
            "log_path": str(log_path),
            "resumed": bool(started.get("resumed")),
            "error": str(exc),
        }

    initialized = store.initialize(intake["baseline"])
    if not initialized.get("initialized"):
        detail = f"Guard init failed: {initialized}"
        store.set_run_phase_status("RECOVERY_REQUIRED", detail)
        _append_bootstrap_note(store, status="RECOVERY_REQUIRED", detail=detail)
        return {
            "ok": False,
            "stage": "GUARD_INIT",
            "run_id": run_id,
            "state_path": str(state_path),
            "log_path": str(log_path),
            "resumed": bool(started.get("resumed")),
            "detail": initialized,
        }

    dashboard = store.update_dashboard(intake["dashboard"])
    if not dashboard.get("ok"):
        detail = f"Dashboard update failed: {dashboard}"
        store.set_run_phase_status("RECOVERY_REQUIRED", detail)
        _append_bootstrap_note(store, status="RECOVERY_REQUIRED", detail=detail)
        return {
            "ok": False,
            "stage": "DASHBOARD_UPDATE",
            "run_id": run_id,
            "state_path": str(state_path),
            "log_path": str(log_path),
            "resumed": bool(started.get("resumed")),
            "detail": dashboard,
        }

    visualization = intake.get("visualization") if isinstance(intake.get("visualization"), dict) else {}
    listing = visualization.get("recordset_listing") if isinstance(visualization.get("recordset_listing"), dict) else {}
    recordsets = listing.get("results") if isinstance(listing.get("results"), list) else []

    _append_bootstrap_note(
        store,
        status="READY",
        detail=(
            "Deterministic Root intake completed via local WQ Lab in memory; "
            f"recordsets discovered: {len(recordsets)}. "
            "No raw/derived intake snapshots were persisted."
        ),
    )

    return {
        "ok": True,
        "stage": "READY_FOR_DIAGNOSIS",
        "root_alpha_id": alpha_id,
        "run_id": run_id,
        "state_path": str(state_path),
        "log_path": str(log_path),
        "diagnostic_alpha_id": visualization.get("diagnostic_alpha_id"),
        "recordset_count": len(recordsets),
        "initialized": initialized,
        "dashboard_updated": True,
        "resumed": bool(started.get("resumed")),
    }

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Deterministic run bootstrap: WQ Lab intake -> Guard init -> Dashboard update."
    )
    parser.add_argument("--alpha-id", required=True)
    parser.add_argument("--discovery-attempts", type=int, default=4)
    parser.add_argument("--discovery-sleep-seconds", type=float, default=2.0)
    args = parser.parse_args()

    result = bootstrap_run(
        args.alpha_id,
        discovery_attempts=args.discovery_attempts,
        discovery_sleep_seconds=args.discovery_sleep_seconds,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())

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


def bootstrap_run(alpha_id: str) -> dict[str, Any]:
    # Capability preflight is local-only and must not create a run on setup errors.
    try:
        provider._load_wq_lib()
    except Exception as exc:
        return {
            "ok": False,
            "stage": "LOCAL_PROVIDER_PREFLIGHT",
            "root_alpha_id": alpha_id,
            "error": str(exc),
        }

    started = guard.start_run(alpha_id)
    if not started.get("ok"):
        return {"ok": False, "stage": "START_RUN", "detail": started}

    state_path = Path(str(started["state_path"]))
    log_path = Path(str(started["log_path"]))
    run_id = str(started["run_id"])
    store = guard.StateStore(state_path, alpha_id)

    try:
        # Root bootstrap is intentionally lean: current Alpha facts, checks and
        # exact metadata for fields actually used by the expression. No
        # visualization POST, recordset sweep, correlation call or candidate
        # simulation belongs here.
        with contextlib.redirect_stdout(io.StringIO()):
            intake = provider.root_intake_snapshot(alpha_id)
    except Exception as exc:
        _append_bootstrap_note(store, status="FAILED", detail=f"WQ Lab Root intake failed: {exc}")
        return {
            "ok": False,
            "stage": "WQ_LAB_ROOT_INTAKE",
            "run_id": run_id,
            "state_path": str(state_path),
            "log_path": str(log_path),
            "error": str(exc),
        }

    initialized = store.initialize(intake["baseline"])
    if not initialized.get("initialized"):
        _append_bootstrap_note(store, status="FAILED", detail=f"Guard init failed: {initialized}")
        return {
            "ok": False,
            "stage": "GUARD_INIT",
            "run_id": run_id,
            "state_path": str(state_path),
            "log_path": str(log_path),
            "detail": initialized,
        }

    dashboard = store.update_dashboard(intake["dashboard"])
    if not dashboard.get("ok"):
        _append_bootstrap_note(store, status="FAILED", detail=f"Dashboard update failed: {dashboard}")
        return {
            "ok": False,
            "stage": "DASHBOARD_UPDATE",
            "run_id": run_id,
            "state_path": str(state_path),
            "log_path": str(log_path),
            "detail": dashboard,
        }

    _append_bootstrap_note(
        store,
        status="READY",
        detail="Lean Root intake completed via local WQ Lab; continue directly into optimization.",
    )

    return {
        "ok": True,
        "stage": "READY_FOR_OPTIMIZATION",
        "root_alpha_id": alpha_id,
        "run_id": run_id,
        "state_path": str(state_path),
        "log_path": str(log_path),
        "initialized": initialized,
        "dashboard_updated": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Lean deterministic Root bootstrap: WQ Lab facts -> Guard init -> Dashboard."
    )
    parser.add_argument("--alpha-id", required=True)
    args = parser.parse_args()

    result = bootstrap_run(args.alpha_id)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())

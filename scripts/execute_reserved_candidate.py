#!/usr/bin/env python3
"""Crash-safe executor for one Guard-reserved Alpha candidate.

The executor owns orchestration only. BRAIN I/O remains inside local wq_lib.
It persists POST intent before submission, records Location immediately after a
confirmed 201, resumes polling by Location without reposting, builds current
Result/check evidence, evaluates the frozen hypothesis, and promotes only a
machine-SUPPORTED candidate.
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import io
import json
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import optimizer_guard as guard
import wq_lab_provider as provider


RESUMABLE_TRANSPORT = {"RESERVED", "HTTP_429", "POSTED"}
RECOVERY_TRANSPORT = {"SUBMITTING", "AMBIGUOUS_POST"}
MAX_INTERNAL_CONTINUATIONS = 8
CONTINUATION_SLEEP_SECONDS = 2.0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _candidate_payload(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "REGULAR",
        "regular": str(candidate["expression"]),
        "settings": copy.deepcopy(candidate["settings"]),
    }


def _active_fingerprints(state: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for fp, candidate in (state.get("candidates") or {}).items():
        if not isinstance(candidate, dict):
            continue
        if candidate.get("result_evaluation") is not None or candidate.get("status") == "PROMOTED":
            continue
        spec = candidate.get("spec") if isinstance(candidate.get("spec"), dict) else {}
        hypothesis_id = str(spec.get("hypothesis_id") or "")
        hypothesis = (state.get("hypotheses") or {}).get(hypothesis_id)
        if not isinstance(hypothesis, dict) or hypothesis.get("status") != "OPEN":
            continue
        simulation = (state.get("simulations") or {}).get(fp)
        if not isinstance(simulation, dict):
            continue
        if simulation.get("status") in RESUMABLE_TRANSPORT | RECOVERY_TRANSPORT:
            out.append(str(fp))
    return sorted(out)


def _select_fingerprint(state: dict[str, Any], requested: str | None) -> str:
    if requested:
        if requested not in (state.get("candidates") or {}):
            raise ValueError(f"unknown candidate fingerprint: {requested}")
        return requested
    candidates = _active_fingerprints(state)
    if len(candidates) != 1:
        raise ValueError(
            "executor requires exactly one active candidate when --fingerprint is omitted; "
            f"found {len(candidates)}"
        )
    return candidates[0]


def _data_dir(state: dict[str, Any], fingerprint: str) -> Path | None:
    run = state.get("run") if isinstance(state.get("run"), dict) else {}
    run_id = str(run.get("run_id") or "").strip()
    if not run_id:
        return None
    return guard.LOGS_DIR / ".data" / run_id / "candidates" / fingerprint


def _write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, default=str)
        handle.write("\n")
        temp = Path(handle.name)
    temp.replace(path)


def _persist(store: guard.StateStore, fingerprint: str, name: str, value: Any) -> None:
    directory = _data_dir(store.read(), fingerprint)
    if directory is not None:
        _write_json_atomic(directory / name, value)


def _response_summary(response: Any) -> dict[str, Any]:
    status = getattr(response, "status_code", None)
    headers = getattr(response, "headers", {}) or {}
    location = ""
    try:
        location = str(headers.get("Location") or "")
    except Exception:
        location = ""
    body = ""
    try:
        body = str(getattr(response, "text", "") or "")[:1000]
    except Exception:
        body = ""
    return {"http_status": status, "location": location, "body": body}


def _failure_evidence(
    store: guard.StateStore,
    fingerprint: str,
    hypothesis_id: str,
    *,
    kind: str,
    source: str,
    claim: str,
) -> str:
    prefixes = {
        "SIMULATION_FAILURE": "E_SIM_FAIL",
        "TRANSPORT_FAILURE": "E_TRANSPORT_FAIL",
        "RESULT_CONTRACT_FAILURE": "E_RESULT_CONTRACT_FAIL",
    }
    prefix = prefixes.get(kind, "E_FAILURE")
    evidence_id = f"{prefix}_{fingerprint[:16]}"
    record = {
        "id": evidence_id,
        "kind": kind,
        "subject": hypothesis_id,
        "source": source,
        "observed_at": _now_iso(),
        "claim": claim,
    }
    registered = store.register_evidence(record)
    if not registered.get("ok"):
        # A prior identical failure may already exist under this deterministic id.
        state = store.read()
        existing = (state.get("evidence") or {}).get(evidence_id)
        if not isinstance(existing, dict):
            raise RuntimeError(f"unable to register failure evidence: {registered}")
        if (
            existing.get("kind") != kind
            or existing.get("subject") != hypothesis_id
            or existing.get("source") != source
            or existing.get("claim") != claim
        ):
            raise RuntimeError(f"failure evidence id collision: {registered}")
    return evidence_id


def _existing_result_or_promotion(
    store: guard.StateStore,
    fingerprint: str,
    candidate: dict[str, Any],
) -> dict[str, Any] | None:
    state = store.read()
    row = (state.get("candidates") or {}).get(fingerprint) or {}
    if row.get("status") == "PROMOTED":
        return {
            "ok": True,
            "stage": "PROMOTED",
            "fingerprint": fingerprint,
            "incumbent_alpha_id": (state.get("incumbent") or {}).get("alpha_id"),
            "idempotent": True,
        }
    evaluation = row.get("result_evaluation")
    if not isinstance(evaluation, dict):
        return None
    status = str(evaluation.get("status") or "")
    if status == "SUPPORTED":
        promoted = store.promote(candidate)
        return {
            "ok": bool(promoted.get("promoted")),
            "stage": "PROMOTED" if promoted.get("promoted") else "PROMOTION_FAILED",
            "fingerprint": fingerprint,
            "evaluation": evaluation,
            "promotion": promoted,
            "idempotent": True,
        }
    return {
        "ok": True,
        "stage": "RESULT_ALREADY_EVALUATED",
        "fingerprint": fingerprint,
        "evaluation": evaluation,
        "idempotent": True,
    }


def _evaluate_done_alpha(
    store: guard.StateStore,
    wq: Any,
    session: Any,
    fingerprint: str,
    candidate: dict[str, Any],
    alpha_id: str,
    simulation_id: str,
) -> dict[str, Any]:
    try:
        evidence = provider.result_evidence_snapshot(session, wq, alpha_id, simulation_id)
    except Exception as exc:
        return {
            "ok": False,
            "stage": "RESULT_FETCH_EXCEPTION",
            "fingerprint": fingerprint,
            "alpha_id": alpha_id,
            "simulation_id": simulation_id,
            "error": str(exc),
            "resumable": True,
        }
    _persist(store, fingerprint, "result_evidence.json", evidence)

    state = store.read()
    hypothesis_id = str(candidate.get("hypothesis_id") or "")
    hypothesis = (state.get("hypotheses") or {}).get(hypothesis_id) or {}
    contract = hypothesis.get("contract") if isinstance(hypothesis.get("contract"), dict) else {}
    baseline_schema_missing = guard.hypothesis_observation_schema_missing(
        contract,
        (state.get("incumbent") or {}).get("result_evidence", {}),
    )
    if baseline_schema_missing:
        check_facts = [
            {
                key: row.get(key)
                for key in ("name", "status", "value", "limit")
                if row.get(key) is not None
            }
            for row in (evidence.get("checks") or [])
            if isinstance(row, dict)
        ]
        fact_summary = {
            "alpha_id": alpha_id,
            "metrics": evidence.get("metrics") or {},
            "checks": check_facts,
        }
        reason = (
            "Frozen hypothesis references observations that are not present in the "
            f"Incumbent snapshot schema: {', '.join(baseline_schema_missing)}. "
            "The posted hypothesis cannot be rewritten after seeing Result. "
            f"Observed candidate snapshot={json.dumps(fact_summary, ensure_ascii=False, sort_keys=True)}"
        )
        evidence_ref = _failure_evidence(
            store,
            fingerprint,
            hypothesis_id,
            kind="RESULT_CONTRACT_FAILURE",
            source="optimizer_guard:hypothesis_observation_schema_missing",
            claim=reason,
        )
        closed = store.close_posted_hypothesis(hypothesis_id, evidence_ref, reason)
        return {
            "ok": bool(closed.get("ok")),
            "stage": "POSTED_RESULT_CONTRACT_INCONCLUSIVE",
            "fingerprint": fingerprint,
            "alpha_id": alpha_id,
            "simulation_id": simulation_id,
            "missing_baseline_observations": baseline_schema_missing,
            "result_evidence": evidence,
            "closure": closed,
        }

    missing_contract_observations = guard.candidate_result_pending_observations(
        contract,
        (state.get("incumbent") or {}).get("result_evidence", {}),
        evidence,
    )
    if not evidence.get("response_complete") or missing_contract_observations:
        return {
            "ok": False,
            "stage": "RESULT_EVIDENCE_PENDING",
            "fingerprint": fingerprint,
            "alpha_id": alpha_id,
            "simulation_id": simulation_id,
            "missing_contract_observations": missing_contract_observations,
            "result_evidence": evidence,
            "resumable": True,
        }

    evaluated = store.evaluate_result(candidate, evidence)
    if not evaluated.get("ok"):
        return {
            "ok": False,
            "stage": "EVALUATE_FAILED",
            "fingerprint": fingerprint,
            "evaluation": evaluated,
            "resumable": False,
        }

    if evaluated.get("status") == "SUPPORTED":
        promoted = store.promote(candidate)
        return {
            "ok": bool(promoted.get("promoted")),
            "stage": "PROMOTED" if promoted.get("promoted") else "PROMOTION_FAILED",
            "fingerprint": fingerprint,
            "alpha_id": alpha_id,
            "simulation_id": simulation_id,
            "evaluation": evaluated,
            "promotion": promoted,
        }

    return {
        "ok": True,
        "stage": "RESULT_EVALUATED",
        "fingerprint": fingerprint,
        "alpha_id": alpha_id,
        "simulation_id": simulation_id,
        "evaluation": evaluated,
    }


def _poll_posted(
    store: guard.StateStore,
    wq: Any,
    session: Any,
    fingerprint: str,
    candidate: dict[str, Any],
) -> dict[str, Any]:
    state = store.read()
    transport = (state.get("simulations") or {}).get(fingerprint) or {}
    location = str(transport.get("simulation_id") or "")
    if transport.get("status") != "POSTED" or not location:
        return {
            "ok": False,
            "stage": "POSTED_LOCATION_REQUIRED",
            "fingerprint": fingerprint,
            "transport": transport,
        }

    payload = _candidate_payload(candidate)
    try:
        outcome = wq.simulate_single(session, payload, location=location)
    except Exception as exc:
        return {
            "ok": False,
            "stage": "POLL_EXCEPTION",
            "fingerprint": fingerprint,
            "simulation_id": location,
            "error": str(exc),
            "resumable": True,
        }

    if not isinstance(outcome, dict):
        outcome = {"status": "unknown", "error": "wq_lib.simulate_single returned non-object"}
    _persist(store, fingerprint, "simulation_outcome.json", outcome)

    status = str(outcome.get("status") or "").lower()
    alpha_id = str(outcome.get("alpha_id") or "")
    if status == "done" and alpha_id:
        return _evaluate_done_alpha(
            store, wq, session, fingerprint, candidate, alpha_id, location
        )

    if status in {"running", "poll_timeout", "complete_unresolved"}:
        return {
            "ok": False,
            "stage": "SIMULATION_PENDING",
            "fingerprint": fingerprint,
            "simulation_id": location,
            "simulation_status": status,
            "error": outcome.get("error"),
            "resumable": True,
        }

    if status in {"error", "cancelled"}:
        hypothesis_id = str(candidate.get("hypothesis_id") or "")
        claim = (
            f"POSTED simulation terminated without usable Alpha result: status={status}; "
            f"error={str(outcome.get('error') or '')[:500]}"
        )
        evidence_ref = _failure_evidence(
            store,
            fingerprint,
            hypothesis_id,
            kind="SIMULATION_FAILURE",
            source="BRAIN:wq_lib.simulate_single",
            claim=claim,
        )
        failed = store.close_posted_hypothesis(hypothesis_id, evidence_ref, claim)
        return {
            "ok": bool(failed.get("ok")),
            "stage": "POSTED_SIMULATION_INCONCLUSIVE",
            "fingerprint": fingerprint,
            "simulation_id": location,
            "simulation_status": status,
            "failure": failed,
        }

    return {
        "ok": False,
        "stage": "SIMULATION_STATUS_UNRESOLVED",
        "fingerprint": fingerprint,
        "simulation_id": location,
        "simulation_status": status,
        "error": outcome.get("error"),
        "resumable": True,
    }


def _submit_reserved(
    store: guard.StateStore,
    wq: Any,
    session: Any,
    fingerprint: str,
    candidate: dict[str, Any],
) -> dict[str, Any]:
    begun = store.begin_submission(fingerprint)
    if not begun.get("ok"):
        return {
            "ok": False,
            "stage": "SUBMISSION_BEGIN_REJECTED",
            "fingerprint": fingerprint,
            "guard": begun,
        }

    payload = _candidate_payload(candidate)
    _persist(store, fingerprint, "candidate_payload.json", payload)
    try:
        response = wq._start_simulation(session, payload)
    except Exception as exc:
        recorded = store.record_transport(fingerprint, "AMBIGUOUS_POST")
        return {
            "ok": False,
            "stage": "AMBIGUOUS_POST",
            "fingerprint": fingerprint,
            "error": str(exc),
            "guard": recorded,
            "recovery_required": True,
        }

    summary = _response_summary(response)
    http_status = summary["http_status"]
    location = str(summary["location"] or "")

    if http_status == 201 and location:
        try:
            posted = store.record_transport(fingerprint, "POSTED", location)
        except Exception as exc:
            _persist(store, fingerprint, "submission_response.json", summary)
            return {
                "ok": False,
                "stage": "POST_RECORD_EXCEPTION",
                "fingerprint": fingerprint,
                "submission": summary,
                "error": str(exc),
                "recovery_required": True,
                "recover_location": location,
            }
        _persist(store, fingerprint, "submission_response.json", summary)
        if not posted.get("ok"):
            return {
                "ok": False,
                "stage": "POST_RECORD_FAILED",
                "fingerprint": fingerprint,
                "submission": summary,
                "guard": posted,
                "recovery_required": True,
                "recover_location": location,
            }
        return _poll_posted(store, wq, session, fingerprint, candidate)

    if http_status == 429:
        limited = store.record_transport(fingerprint, "HTTP_429")
        _persist(store, fingerprint, "submission_response.json", summary)
        return {
            "ok": False,
            "stage": "HTTP_429",
            "fingerprint": fingerprint,
            "guard": limited,
            "retry_count": limited.get("retry_count"),
            "resumable": True,
        }

    if http_status == 201 or (isinstance(http_status, int) and http_status >= 500):
        ambiguous = store.record_transport(fingerprint, "AMBIGUOUS_POST")
        _persist(store, fingerprint, "submission_response.json", summary)
        return {
            "ok": False,
            "stage": "AMBIGUOUS_POST",
            "fingerprint": fingerprint,
            "submission": summary,
            "guard": ambiguous,
            "recovery_required": True,
        }

    reason = (
        f"BRAIN submission was explicitly rejected before a confirmed POST: "
        f"HTTP {http_status}; body={summary['body'][:500]}"
    )
    released = store.release_reservation(fingerprint, reason)
    _persist(store, fingerprint, "submission_response.json", summary)
    hypothesis_id = str(candidate.get("hypothesis_id") or "")
    evidence_ref = _failure_evidence(
        store,
        fingerprint,
        hypothesis_id,
        kind="TRANSPORT_FAILURE",
        source="BRAIN:wq_lib._start_simulation",
        claim=reason,
    )
    abandoned = store.abandon_hypothesis(hypothesis_id, evidence_ref, reason)
    return {
        "ok": bool(released.get("ok") and abandoned.get("ok")),
        "stage": "NO_POST_INCONCLUSIVE",
        "fingerprint": fingerprint,
        "submission": summary,
        "release": released,
        "abandon": abandoned,
    }


def execute_reserved_candidate(
    store: guard.StateStore,
    wq: Any,
    session: Any,
    *,
    fingerprint: str | None = None,
    recover_location: str | None = None,
) -> dict[str, Any]:
    state = store.read()
    fingerprint = _select_fingerprint(state, fingerprint)
    candidate_row = (state.get("candidates") or {}).get(fingerprint)
    if not isinstance(candidate_row, dict) or not isinstance(candidate_row.get("spec"), dict):
        return {"ok": False, "stage": "CANDIDATE_SPEC_REQUIRED", "fingerprint": fingerprint}
    candidate = candidate_row["spec"]

    existing = _existing_result_or_promotion(store, fingerprint, candidate)
    if existing is not None:
        return existing

    state = store.read()
    hypothesis = (state.get("hypotheses") or {}).get(str(candidate.get("hypothesis_id") or "")) or {}
    if hypothesis.get("status") in {"INCONCLUSIVE", "WITHDRAWN", "REFUTED"}:
        return {
            "ok": True,
            "stage": "HYPOTHESIS_ALREADY_TERMINAL",
            "fingerprint": fingerprint,
            "hypothesis_status": hypothesis.get("status"),
            "idempotent": True,
        }
    transport = (state.get("simulations") or {}).get(fingerprint)
    if not isinstance(transport, dict):
        return {"ok": False, "stage": "SIMULATION_STATE_REQUIRED", "fingerprint": fingerprint}
    status = str(transport.get("status") or "")

    if status in RECOVERY_TRANSPORT:
        if not recover_location:
            return {
                "ok": False,
                "stage": "POST_RECONCILIATION_REQUIRED",
                "fingerprint": fingerprint,
                "transport_status": status,
                "recovery_required": True,
                "note": "No automatic repost is allowed from SUBMITTING/AMBIGUOUS_POST.",
            }
        recovered = store.record_transport(fingerprint, "POSTED", recover_location)
        if not recovered.get("ok"):
            return {
                "ok": False,
                "stage": "POST_RECONCILIATION_FAILED",
                "fingerprint": fingerprint,
                "guard": recovered,
            }
        return _poll_posted(store, wq, session, fingerprint, candidate)

    if status == "POSTED":
        return _poll_posted(store, wq, session, fingerprint, candidate)

    if status == "HTTP_429":
        reserved = store.reserve_simulation(candidate)
        if not reserved.get("allowed"):
            return {
                "ok": False,
                "stage": "HTTP_429_RETRY_REJECTED",
                "fingerprint": fingerprint,
                "guard": reserved,
            }
        status = "RESERVED"

    if status == "RESERVED":
        return _submit_reserved(store, wq, session, fingerprint, candidate)

    return {
        "ok": False,
        "stage": "TRANSPORT_STATE_NOT_EXECUTABLE",
        "fingerprint": fingerprint,
        "transport_status": status,
    }


def execute_until_boundary(
    store: guard.StateStore,
    wq: Any,
    session: Any,
    *,
    fingerprint: str | None = None,
    recover_location: str | None = None,
    max_continuations: int = MAX_INTERNAL_CONTINUATIONS,
    sleep_seconds: float = CONTINUATION_SLEEP_SECONDS,
) -> dict[str, Any]:
    """Own all safe continuation for one candidate until a real decision boundary."""
    result = execute_reserved_candidate(
        store,
        wq,
        session,
        fingerprint=fingerprint,
        recover_location=recover_location,
    )
    continuations = 0
    while result.get("resumable"):
        if continuations >= max_continuations:
            return {
                "ok": False,
                "stage": "CONTINUATION_RECONCILIATION_REQUIRED",
                "fingerprint": result.get("fingerprint") or fingerprint,
                "last_stage": result.get("stage"),
                "last_result": result,
                "continuations": continuations,
                "recovery_required": True,
            }
        continuations += 1
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)
        result = execute_reserved_candidate(
            store,
            wq,
            session,
            fingerprint=str(result.get("fingerprint") or fingerprint or ""),
        )
    if isinstance(result, dict):
        result = dict(result)
        result["continuations"] = continuations
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Execute one Guard-reserved candidate through WQ Lab without duplicate POST."
    )
    parser.add_argument("--state", required=True)
    parser.add_argument("--root-alpha-id", required=True)
    parser.add_argument("--fingerprint")
    parser.add_argument(
        "--recover-location",
        help="Attach an externally reconciled simulation Location to SUBMITTING/AMBIGUOUS_POST; never causes a repost.",
    )
    args = parser.parse_args()

    store = guard.StateStore(Path(args.state), args.root_alpha_id)
    wq = provider._load_wq_lib(require_submission_start=True)
    with contextlib.redirect_stdout(io.StringIO()):
        session = wq.login()

    result = execute_until_boundary(
        store,
        wq,
        session,
        fingerprint=args.fingerprint,
        recover_location=args.recover_location,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())

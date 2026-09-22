#!/usr/bin/env python3
"""Deterministic local guard/state helper for WQ Alpha Optimizer FE candidates.

v3.4.0 principles:
- Root is immutable; candidates must descend from the current Incumbent.
- A focus (DEFECT or ENHANCEMENT) is explicit and can be evidence-exhausted.
- A hypothesis freezes its whole falsifiable contract before simulation.
- One hypothesis ID is permanently bound to one payload fingerprint.
- Transport transitions are explicit; POSTED cannot be reopened.
- Result classification/promotion use structured post-simulation evidence rather
  than caller-supplied readiness booleans; research support does not require final
  submission-threshold passage.
- Canonical run logs render a live dashboard before the append-only audit trail.
- Fast Expression inspection uses a lightweight FE tokenizer instead of Python AST.

The guard still cannot verify economic truth or live BRAIN semantics. It binds and
checks facts supplied from the platform/controller so that state transitions are
machine-auditable and internally consistent.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable

from run_dashboard import enrich_context_with_charts, render_dashboard

SCHEMA_VERSION = 4
MAX_EXPLICIT_429_RETRIES = 3
LOCKED_SCOPE_KEYS = {"region", "delay", "universe", "instrumenttype"}

SKILL_ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = SKILL_ROOT / "logs"
STATE_DIR = LOGS_DIR / ".state"


def _safe_component(value: Any) -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value).strip())
    text = text.strip("._")
    return text or "alpha"


def _run_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def _canonical_run_paths(root_alpha_id: str, stamp: str | None = None) -> tuple[Path, Path, str]:
    stamp = stamp or _run_stamp()
    run_id = f"{_safe_component(root_alpha_id)}_{stamp}"
    return LOGS_DIR / f"{run_id}.md", STATE_DIR / f"{run_id}.json", run_id


def _initial_log_text(root_alpha_id: str, run_id: str, started_at: str, status: str = "RUNNING") -> str:
    return (
        "# WQ Alpha Optimization Run\n\n"
        f"- Run ID: `{run_id}`\n"
        f"- Root Alpha: `{root_alpha_id}`\n"
        f"- Started at: `{started_at}`\n"
        f"- Status: `{status}`\n\n"
        "> This file is the single canonical human-readable log for this optimizer run. "
        "The dashboard below is regenerated from machine state; the audit trail remains append-only.\n\n"
    )

def _render_run_log(state: Dict[str, Any]) -> str:
    run = state.get("run") or {}
    text = _initial_log_text(
        str(state.get("root_alpha_id", "")),
        str(run.get("run_id", "")),
        str(run.get("started_at", "")),
        str(run.get("status") or "RUNNING"),
    )
    text += render_dashboard(state)
    for entry in state.get("log_entries", []):
        section = str(entry.get("section", "RUN")).strip() or "RUN"
        body = str(entry.get("text", "")).rstrip()
        at = str(entry.get("at", ""))
        text += f"\n## {section}\n\n"
        if at:
            text += f"_Recorded at: {at}_\n\n"
        text += body + "\n"
    return text

HYPOTHESIS_FINAL = {"SUPPORTED", "REFUTED", "INCONCLUSIVE"}
FOCUS_TYPES = {"DEFECT", "ENHANCEMENT"}
TRANSPORT_TRANSITIONS = {
    "RESERVED": {"POSTED", "HTTP_429", "AMBIGUOUS_POST"},
    "AMBIGUOUS_POST": {"POSTED"},  # recovery discovers the original simulation; never repost
}
PLAN_ROUTE_STATUSES = {"PENDING", "ACTIVE", "EXHAUSTED", "DISMISSED", "COMPLETED"}
TERMINAL_ROUTE_STATUSES = {"EXHAUSTED", "DISMISSED", "COMPLETED"}
RUN_TERMINAL_STATUSES = {
    "SUCCESS",
    "SUBMISSION_READY",
    "COMPLETED_WITH_EXHAUSTION",
    "USER_STOP",
    "SCOPE_BOUNDARY",
    "PLATFORM_UNRECOVERABLE",
}
FORCED_TERMINAL_STATUSES = {"USER_STOP", "SCOPE_BOUNDARY", "PLATFORM_UNRECOVERABLE"}

# Lightweight Fast Expression tokenizer. It intentionally validates lexical and
# delimiter structure, not live operator signatures or arity.
_TOKEN_RE = re.compile(
    r"""
    (?P<WS>\s+)
  | (?P<NUMBER>(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)
  | (?P<STRING>'(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*")
  | (?P<IDENT>[A-Za-z_][A-Za-z0-9_.$:]*)
  | (?P<OP>\*\*|&&|\|\||==|!=|<=|>=|[+\-*/%^<>=!?:])
  | (?P<PUNCT>[(),\[\]])
    """,
    re.VERBOSE,
)
_RESERVED = {"true", "false", "nan", "inf", "null", "none"}
_COMPLEXITY_OPS = {"+", "-", "*", "/", "%", "^", "**", "&&", "||", "==", "!=", "<", "<=", ">", ">=", "!", "?"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_iso(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("timestamp required")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return dt.astimezone(timezone.utc)


def _tokenize_fe(expression: str) -> list[tuple[str, str]]:
    if not isinstance(expression, str) or not expression.strip():
        raise SyntaxError("empty expression")
    tokens: list[tuple[str, str]] = []
    pos = 0
    while pos < len(expression):
        m = _TOKEN_RE.match(expression, pos)
        if not m:
            raise SyntaxError(f"unsupported token at offset {pos}: {expression[pos:pos+16]!r}")
        kind = m.lastgroup or ""
        value = m.group(kind)
        pos = m.end()
        if kind != "WS":
            tokens.append((kind, value))
    if not tokens:
        raise SyntaxError("empty expression")

    stack: list[str] = []
    pair = {")": "(", "]": "["}
    for kind, value in tokens:
        if kind == "PUNCT" and value in {"(", "["}:
            stack.append(value)
        elif kind == "PUNCT" and value in {")", "]"}:
            if not stack or stack[-1] != pair[value]:
                raise SyntaxError(f"unbalanced delimiter: {value}")
            stack.pop()
    if stack:
        raise SyntaxError(f"unclosed delimiter: {stack[-1]}")
    return tokens


def _canonical_expression(expression: str) -> str:
    try:
        return "".join(value for _, value in _tokenize_fe(expression))
    except Exception:
        return str(expression).strip()


def _inspect_fe(expression: str) -> Dict[str, Any]:
    try:
        tokens = _tokenize_fe(expression)
    except (SyntaxError, ValueError, TypeError) as exc:
        return {
            "parse_ok": False,
            "operator_count": None,
            "identifiers": None,
            "counting_method": "FE_TOKEN_V1",
            "error": str(exc),
        }

    function_positions: set[int] = set()
    keyword_positions: set[int] = set()
    for i, (kind, value) in enumerate(tokens):
        if kind != "IDENT":
            continue
        if i + 1 < len(tokens) and tokens[i + 1] == ("PUNCT", "("):
            function_positions.add(i)
        if i + 1 < len(tokens) and tokens[i + 1] == ("OP", "="):
            keyword_positions.add(i)

    identifiers = sorted({
        value
        for i, (kind, value) in enumerate(tokens)
        if kind == "IDENT"
        and i not in function_positions
        and i not in keyword_positions
        and value.lower() not in _RESERVED
        and value.lower() not in {"and", "or", "not"}
    })
    call_count = len(function_positions)
    op_count = sum(1 for kind, value in tokens if kind == "OP" and value in _COMPLEXITY_OPS)
    return {
        "parse_ok": True,
        "operator_count": call_count + op_count,
        "function_call_count": call_count,
        "infix_operator_count": op_count,
        "identifiers": identifiers,
        "counting_method": "FE_TOKEN_V1",
        "error": None,
    }


def inspect_expression(expression: str) -> Dict[str, Any]:
    return _inspect_fe(expression)


def inspect_root(expression: str) -> Dict[str, Any]:
    out = inspect_expression(expression)
    out["diagnosable"] = True
    out["absolute_complexity_gate_applied"] = False
    return out


def _nonempty(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict)):
        return bool(value)
    return value is not None


def _normalize_key(key: Any) -> str:
    return "".join(ch for ch in str(key).lower() if ch.isalnum())


def _has_testperiod(value: Any) -> bool:
    if isinstance(value, dict):
        for k, v in value.items():
            if _normalize_key(k) == "testperiod":
                return True
            if _has_testperiod(v):
                return True
    elif isinstance(value, (list, tuple)):
        return any(_has_testperiod(x) for x in value)
    return False


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _copy_json(value: Any) -> Any:
    return json.loads(_canonical_json(value))


def _route_key(route: Dict[str, Any]) -> str:
    return "|".join(
        str(route.get(name, "")).strip()
        for name in ("target", "owner", "mechanism")
    )


def _setting_map(settings: Dict[str, Any]) -> Dict[str, tuple[str, Any]]:
    out: Dict[str, tuple[str, Any]] = {}
    for key, value in settings.items():
        nk = _normalize_key(key)
        if nk in out and out[nk][0] != key:
            raise ValueError(f"ambiguous normalized setting keys: {out[nk][0]!r} and {key!r}")
        out[nk] = (str(key), value)
    return out


def _settings_diff(base: Dict[str, Any], candidate: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    b = _setting_map(base)
    c = _setting_map(candidate)
    diff: Dict[str, Dict[str, Any]] = {}
    for nk in sorted(set(b) | set(c)):
        bv = b.get(nk, (None, None))[1]
        cv = c.get(nk, (None, None))[1]
        if nk not in b or nk not in c or _canonical_json(bv) != _canonical_json(cv):
            diff[nk] = {
                "base_key": b.get(nk, (None, None))[0],
                "candidate_key": c.get(nk, (None, None))[0],
                "base": bv,
                "candidate": cv,
            }
    return diff


def _normalize_checks(checks: Any) -> list[Dict[str, Any]]:
    if checks is None:
        return []
    if not isinstance(checks, list):
        raise ValueError("checks must be a list")
    out = []
    seen_names = set()
    for item in checks:
        if not isinstance(item, dict) or not _nonempty(item.get("name")) or not _nonempty(item.get("status")):
            raise ValueError("each check needs name/status")
        row = dict(item)
        check_name = str(row["name"])
        if check_name in seen_names:
            raise ValueError(f"duplicate check name: {check_name}")
        seen_names.add(check_name)
        row["name"] = check_name
        row["status"] = str(row["status"]).upper()
        # FAIL is always blocking. WARNING needs an explicit project/platform
        # classification before it can support SUBMISSION_READY. A blocking
        # classification is itself explicit; non-blocking WARNING requires
        # policy_classified=true from the controller.
        row["policy_blocking"] = bool(row.get("policy_blocking", False))
        row["policy_classified"] = bool(row.get("policy_classified", False) or row["policy_blocking"] or row["status"] != "WARNING")
        row["blocking"] = row["status"] == "FAIL" or row["policy_blocking"]
        out.append(row)
    return out


def _normalize_metrics(metrics: Any) -> Dict[str, float]:
    if metrics is None:
        return {}
    if not isinstance(metrics, dict):
        raise ValueError("metrics must be an object")
    out: Dict[str, float] = {}
    for key, value in metrics.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"metric {key} must be numeric")
        out[str(key).upper()] = float(value)
    return out


def _fail_blockers(checks: list[Dict[str, Any]]) -> set[str]:
    return {str(c["name"]) for c in checks if bool(c.get("blocking")) or str(c.get("status", "")).upper() == "FAIL"}


def _unresolved_checks(checks: list[Dict[str, Any]]) -> set[str]:
    unresolved = set()
    for row in checks:
        status = str(row.get("status", "")).upper()
        if status == "PASS" or row.get("blocking"):
            continue
        if status == "WARNING" and row.get("policy_classified"):
            continue
        unresolved.add(str(row.get("name")))
    return unresolved


def _snapshot_from_json(baseline: Dict[str, Any], root_alpha_id: str) -> Dict[str, Any]:
    required = ("alpha_id", "expression", "fields", "settings", "language")
    missing = [k for k in required if not _nonempty(baseline.get(k))]
    if missing:
        raise ValueError(f"baseline missing required fields: {', '.join(missing)}")
    if str(baseline["alpha_id"]) != str(root_alpha_id):
        raise ValueError(f"baseline alpha_id mismatch: {baseline['alpha_id']} != {root_alpha_id}")
    language = str(baseline["language"]).upper()
    if language not in {"FASTEXPR", "FE"}:
        raise ValueError("baseline language unsupported by FE guard")
    if not isinstance(baseline["settings"], dict) or not baseline["settings"]:
        raise ValueError("baseline settings must be a non-empty full snapshot")
    if _has_testperiod(baseline["settings"]):
        raise ValueError("baseline settings must not contain testPeriod")
    fields = baseline["fields"]
    if not isinstance(fields, list) or any(not isinstance(x, str) or not x.strip() for x in fields):
        raise ValueError("baseline fields must be a list of non-empty strings")
    inspected = inspect_expression(str(baseline["expression"]))
    if not inspected["parse_ok"]:
        raise ValueError(f"baseline expression parse failed: {inspected['error']}")
    declared = sorted(dict.fromkeys(x.strip() for x in fields))
    if inspected["identifiers"] != declared:
        raise ValueError(f"baseline field declaration mismatch: expression={inspected['identifiers']} declared={declared}")
    _setting_map(baseline["settings"])
    evidence = baseline.get("result_evidence") or {}
    metrics = _normalize_metrics(evidence.get("metrics")) if evidence else {}
    checks = _normalize_checks(evidence.get("checks")) if evidence else []
    observed_at = evidence.get("observed_at") if evidence else None
    if observed_at:
        _parse_iso(observed_at)
    return {
        "alpha_id": str(baseline["alpha_id"]),
        "expression": str(baseline["expression"]),
        "fields": declared,
        "settings": baseline["settings"],
        "language": language,
        "operator_count": inspected["operator_count"],
        "counting_method": inspected["counting_method"],
        "result_evidence": {
            "metrics": metrics,
            "checks": checks,
            "observed_at": observed_at,
            "source": evidence.get("source") if evidence else None,
            "response_complete": bool(evidence.get("response_complete")) if evidence else False,
            "authenticated": bool(evidence.get("authenticated")) if evidence else False,
        },
    }


def _validate_evidence_record(record: Dict[str, Any]) -> Dict[str, Any]:
    required = ("id", "kind", "subject", "source", "observed_at", "claim")
    missing = [k for k in required if not _nonempty(record.get(k))]
    if missing:
        raise ValueError(f"evidence missing: {', '.join(missing)}")
    _parse_iso(record["observed_at"])
    source = str(record["source"])
    claim = str(record["claim"])
    if ":" not in source or len(source.strip()) < 5:
        raise ValueError("evidence source must be an auditable namespace/action, e.g. BRAIN:get_data_fields")
    if len(claim.strip()) < 12:
        raise ValueError("evidence claim is too short to audit")
    return {
        "id": str(record["id"]),
        "kind": str(record["kind"]).upper(),
        "subject": str(record["subject"]),
        "source": source,
        "observed_at": str(record["observed_at"]),
        "claim": claim,
    }


def _evidence_fingerprint(record: Dict[str, Any]) -> str:
    """Fingerprint informational content, excluding audit identity/time fields."""
    content = {
        "kind": str(record.get("kind", "")).strip().upper(),
        "subject": str(record.get("subject", "")).strip(),
        "source": str(record.get("source", "")).strip(),
        "claim": " ".join(str(record.get("claim", "")).split()),
    }
    return hashlib.sha256(_canonical_json(content).encode("utf-8")).hexdigest()


def _result_fact_fingerprint(evidence: Dict[str, Any]) -> str:
    """Fingerprint current Result/check facts while ignoring source timestamp/order."""
    metrics = _normalize_metrics((evidence or {}).get("metrics"))
    checks = _normalize_checks((evidence or {}).get("checks"))
    canonical_checks = sorted((_copy_json(row) for row in checks), key=_canonical_json)
    return hashlib.sha256(
        _canonical_json({"metrics": metrics, "checks": canonical_checks}).encode("utf-8")
    ).hexdigest()


def _terminal_rejection(state: Dict[str, Any]) -> Dict[str, Any] | None:
    status = (state.get("run") or {}).get("status")
    if status in RUN_TERMINAL_STATUSES:
        return {"ok": False, "reason": "RUN_ALREADY_TERMINAL", "status": status}
    return None


def _submission_readiness(state: Dict[str, Any]) -> Dict[str, Any]:
    incumbent = state.get("incumbent") or {}
    if not incumbent:
        return {"ready": False, "reason": "STATE_NOT_INITIALIZED", "blockers": [], "unresolved_checks": []}
    evidence = incumbent.get("result_evidence") or {}
    if not evidence.get("response_complete") or not evidence.get("authenticated"):
        return {"ready": False, "reason": "READINESS_EVIDENCE_INCOMPLETE", "blockers": [], "unresolved_checks": []}
    source = evidence.get("source")
    observed_at = evidence.get("observed_at")
    if not isinstance(source, str) or ":" not in source or not observed_at:
        return {"ready": False, "reason": "READINESS_EVIDENCE_NOT_AUDITABLE", "blockers": [], "unresolved_checks": []}
    try:
        _parse_iso(observed_at)
        checks = _normalize_checks(evidence.get("checks"))
    except ValueError as exc:
        return {"ready": False, "reason": "READINESS_EVIDENCE_CONTRACT", "detail": str(exc), "blockers": [], "unresolved_checks": []}
    if not checks:
        return {"ready": False, "reason": "READINESS_CHECKS_REQUIRED", "blockers": [], "unresolved_checks": []}

    blockers = sorted(_fail_blockers(checks))
    unresolved = sorted(_unresolved_checks(checks))

    if blockers:
        return {"ready": False, "reason": "CURRENT_BLOCKERS_REMAIN", "blockers": blockers, "unresolved_checks": unresolved}
    if unresolved:
        return {"ready": False, "reason": "READINESS_CHECKS_UNRESOLVED", "blockers": [], "unresolved_checks": unresolved}
    return {
        "ready": True,
        "reason": None,
        "blockers": [],
        "unresolved_checks": [],
        "observed_at": observed_at,
        "source": source,
    }


def _active_plan_rejection(state: Dict[str, Any]) -> Dict[str, Any] | None:
    if state.get("planning_contract") != "v1":
        return None
    plan = state.get("optimization_plan")
    if not plan:
        return {"ok": False, "reason": "PLAN_REQUIRED"}
    status = plan.get("status")
    if status != "ACTIVE":
        reason = "PLAN_STALE_REPLAN_REQUIRED" if status == "STALE" else "PLAN_NOT_ACTIVE"
        return {"ok": False, "reason": reason, "plan_status": status}
    return None


def _route_candidate_result_count(state: Dict[str, Any], route_id: str, incumbent_alpha_id: str | None = None) -> int:
    count = 0
    for candidate in state.get("candidates", {}).values():
        if not isinstance(candidate, dict) or candidate.get("route_id") != route_id:
            continue
        spec = candidate.get("spec") if isinstance(candidate.get("spec"), dict) else {}
        if incumbent_alpha_id is not None and str(spec.get("parent_id")) != str(incumbent_alpha_id):
            continue
        if candidate.get("result_evaluation") is not None:
            count += 1
    return count


def _novel_post_activation_evidence(
    state: Dict[str, Any],
    evidence_ref: str | None,
    activated_at_evidence_revision: int,
) -> Dict[str, Any] | None:
    if not evidence_ref:
        return None
    evidence = state.get("evidence", {}).get(evidence_ref)
    if not isinstance(evidence, dict):
        return None
    if int(evidence.get("revision", 0)) <= int(activated_at_evidence_revision):
        return None
    prior_fingerprints = {
        row.get("content_fingerprint") or _evidence_fingerprint(row)
        for row in state.get("evidence", {}).values()
        if isinstance(row, dict) and int(row.get("revision", 0)) <= int(activated_at_evidence_revision)
    }
    fingerprint = evidence.get("content_fingerprint") or _evidence_fingerprint(evidence)
    if fingerprint in prior_fingerprints:
        return None
    return evidence


def _route_closure_rejection(
    state: Dict[str, Any],
    route: Dict[str, Any],
    *,
    evidence_ref: str | None = None,
    plan: Dict[str, Any] | None = None,
) -> Dict[str, Any] | None:
    plan = plan or state.get("optimization_plan") or {}
    incumbent_alpha_id = plan.get("incumbent_alpha_id") or (state.get("incumbent") or {}).get("alpha_id")
    result_count = _route_candidate_result_count(state, str(route.get("id")), incumbent_alpha_id)
    if result_count > 0:
        return None

    activated_revision = int(
        route.get(
            "activated_at_evidence_revision",
            plan.get("based_on_evidence_revision", state.get("evidence_revision", 0)),
        )
    )
    evidence = _novel_post_activation_evidence(state, evidence_ref, activated_revision)
    if evidence is not None:
        return None

    return {
        "ok": False,
        "reason": "ROUTE_REQUIRES_CANDIDATE_RESULT_OR_NEW_EVIDENCE",
        "route_id": route.get("id"),
        "candidate_result_count": result_count,
        "activated_at_evidence_revision": activated_revision,
        "current_evidence_revision": int(state.get("evidence_revision", 0)),
        "required": (
            "At least one evaluated candidate Result bound to this route, or an explicit "
            "evidence_ref for genuinely new post-activation diagnostic evidence."
        ),
    }


def _terminal_route_attempt_violations(state: Dict[str, Any]) -> list[Dict[str, Any]]:
    incumbent_alpha_id = str((state.get("incumbent") or {}).get("alpha_id") or "")
    plans = [
        *[item for item in state.get("optimization_plan_history", []) if isinstance(item, dict)],
        state.get("optimization_plan"),
    ]
    violations: list[Dict[str, Any]] = []
    for plan in plans:
        if not isinstance(plan, dict):
            continue
        if incumbent_alpha_id and str(plan.get("incumbent_alpha_id") or "") != incumbent_alpha_id:
            continue
        for route in plan.get("routes", []):
            if not isinstance(route, dict) or route.get("status") not in TERMINAL_ROUTE_STATUSES:
                continue
            result_count = max(
                int(route.get("candidate_result_count", 0) or 0),
                _route_candidate_result_count(state, str(route.get("id")), incumbent_alpha_id or None),
            )
            if result_count > 0:
                continue
            activated_revision = int(
                route.get(
                    "activated_at_evidence_revision",
                    plan.get("based_on_evidence_revision", 0),
                )
            )
            evidence_ref = route.get("zero_candidate_closure_evidence_ref")
            if _novel_post_activation_evidence(state, evidence_ref, activated_revision) is not None:
                continue
            violations.append(
                {
                    "route_id": route.get("id"),
                    "status": route.get("status"),
                    "candidate_result_count": result_count,
                    "activated_at_evidence_revision": activated_revision,
                    "closed_at_evidence_revision": route.get("closed_at_evidence_revision"),
                    "zero_candidate_closure_evidence_ref": evidence_ref,
                }
            )
    return violations


def _normalize_plan_route(route: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(route, dict):
        raise ValueError("plan route must be an object")
    required = ("id", "target", "owner", "mechanism", "evidence_refs", "rationale")
    missing = [key for key in required if not _nonempty(route.get(key))]
    if missing:
        raise ValueError(f"plan route missing: {', '.join(missing)}")
    refs = route["evidence_refs"]
    if not isinstance(refs, list) or any(not isinstance(ref, str) or not ref.strip() for ref in refs):
        raise ValueError("plan route evidence_refs must be a non-empty string list")
    status = str(route.get("status", "PENDING")).upper()
    if status not in {"PENDING", "ACTIVE"}:
        raise ValueError("new plan routes must start as PENDING or ACTIVE")
    normalized = {
        "id": str(route["id"]).strip(),
        "target": str(route["target"]).strip(),
        "owner": str(route["owner"]).strip(),
        "mechanism": str(route["mechanism"]).strip(),
        "evidence_refs": sorted(dict.fromkeys(ref.strip() for ref in refs)),
        "rationale": str(route["rationale"]).strip(),
        "status": status,
    }
    if _nonempty(route.get("reopen_reason")):
        normalized["reopen_reason"] = str(route["reopen_reason"]).strip()
    if route.get("new_observation_refs") is not None:
        refs = route["new_observation_refs"]
        if not isinstance(refs, list) or any(not isinstance(ref, str) or not ref.strip() for ref in refs):
            raise ValueError("new_observation_refs must be a string list")
        normalized["new_observation_refs"] = sorted(dict.fromkeys(ref.strip() for ref in refs))
    return normalized


def _validate_hypothesis_contract(contract: Dict[str, Any]) -> Dict[str, Any]:
    required = ("target", "principal_hypothesis", "mutation", "success_criteria", "protected_metrics", "failure_meaning", "evidence_refs")
    missing = [k for k in required if not _nonempty(contract.get(k))]
    if missing:
        raise ValueError(f"hypothesis contract missing: {', '.join(missing)}")
    mutation = contract["mutation"]
    if not isinstance(mutation, dict) or mutation.get("type") not in {"expression", "setting"}:
        raise ValueError("hypothesis mutation must be expression or setting")
    if mutation.get("type") == "setting" and not _nonempty(mutation.get("key")):
        raise ValueError("setting hypothesis requires mutation.key")
    criteria = contract["success_criteria"]
    if not isinstance(criteria, list) or not criteria:
        raise ValueError("success_criteria must be a non-empty list")
    normalized_criteria = []
    for c in criteria:
        if not isinstance(c, dict) or c.get("type") not in {"metric", "check"} or not _nonempty(c.get("name")):
            raise ValueError("invalid success criterion")
        row = dict(c)
        row["type"] = str(row["type"]).lower()
        row["name"] = str(row["name"]).upper() if row["type"] == "metric" else str(row["name"])
        if row["type"] == "metric":
            if row.get("direction") not in {"higher", "lower"}:
                raise ValueError("metric criterion direction must be higher/lower")
            min_change = row.get("min_change", 0.0)
            if isinstance(min_change, bool) or not isinstance(min_change, (int, float)) or float(min_change) < 0:
                raise ValueError("metric criterion min_change must be non-negative")
            row["min_change"] = float(min_change)
            row.pop("tolerance", None)
        else:
            if not _nonempty(row.get("required_status")):
                raise ValueError("check criterion requires required_status")
            row["required_status"] = str(row["required_status"]).upper()
            if row["required_status"] != "PASS":
                raise ValueError("check success criterion must require PASS")
        normalized_criteria.append(row)

    protected = contract["protected_metrics"]
    if not isinstance(protected, list):
        raise ValueError("protected_metrics must be a list")
    normalized_protected = []
    for p in protected:
        if not isinstance(p, dict) or not _nonempty(p.get("name")) or p.get("rule") not in {"not_lower", "not_higher"}:
            raise ValueError("protected metric needs name and rule=not_lower/not_higher")
        tol = p.get("tolerance", 0.0)
        if isinstance(tol, bool) or not isinstance(tol, (int, float)) or float(tol) < 0:
            raise ValueError("protected tolerance must be non-negative")
        normalized_protected.append({"name": str(p["name"]).upper(), "rule": p["rule"], "tolerance": float(tol)})

    refs = contract["evidence_refs"]
    if not isinstance(refs, list) or any(not isinstance(x, str) or not x.strip() for x in refs):
        raise ValueError("evidence_refs must be a non-empty string list")

    out = {
        "target": str(contract["target"]).strip(),
        "principal_hypothesis": str(contract["principal_hypothesis"]).strip(),
        "mutation": mutation,
        "success_criteria": normalized_criteria,
        "protected_metrics": normalized_protected,
        "failure_meaning": str(contract["failure_meaning"]).strip(),
        "evidence_refs": sorted(dict.fromkeys(refs)),
    }
    if _nonempty(contract.get("mechanism")):
        out["mechanism"] = str(contract["mechanism"]).strip()
    if _nonempty(contract.get("complexity_reason")):
        out["complexity_reason"] = str(contract["complexity_reason"]).strip()
    if _nonempty(contract.get("field_change_reason")):
        out["field_change_reason"] = str(contract["field_change_reason"]).strip()
    return out


def payload_fingerprint(candidate: Dict[str, Any]) -> str:
    payload = {
        "language": str(candidate.get("language", "FASTEXPR")).upper(),
        "expression": _canonical_expression(str(candidate.get("expression", ""))),
        "settings": candidate.get("settings") or {},
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def preflight_candidate(candidate: Dict[str, Any], state: Dict[str, Any] | None = None, *, require_open_hypothesis: bool = False) -> Dict[str, Any]:
    required = ("parent_id", "hypothesis_id", "expression", "fields", "settings", "language")
    missing = [k for k in required if not _nonempty(candidate.get(k))]
    if missing:
        return {"valid": False, "reject_code": "CANDIDATE_CONTRACT", "missing": missing}

    language = str(candidate.get("language", "")).upper()
    if language not in {"FASTEXPR", "FE"}:
        return {"valid": False, "reject_code": "LANGUAGE_UNSUPPORTED_BY_FE_GUARD"}
    fields = candidate.get("fields")
    if not isinstance(fields, list) or any(not isinstance(x, str) or not x.strip() for x in fields):
        return {"valid": False, "reject_code": "FIELD_DECLARATION_UNKNOWN"}
    declared_fields = sorted(dict.fromkeys(x.strip() for x in fields))
    settings = candidate.get("settings")
    if not isinstance(settings, dict) or not settings:
        return {"valid": False, "reject_code": "FULL_SETTINGS_REQUIRED"}
    if _has_testperiod(settings):
        return {"valid": False, "reject_code": "TEST_PERIOD_GAMING"}
    try:
        _setting_map(settings)
    except ValueError as exc:
        return {"valid": False, "reject_code": "SETTINGS_KEY_AMBIGUITY", "detail": str(exc)}

    inspected = inspect_expression(str(candidate["expression"]))
    if not inspected["parse_ok"]:
        return {"valid": False, "reject_code": "FE_PARSE_UNKNOWN", "parse_error": inspected["error"]}
    if inspected["identifiers"] != declared_fields:
        return {
            "valid": False,
            "reject_code": "FIELD_DECLARATION_MISMATCH",
            "expression_fields": inspected["identifiers"],
            "declared_fields": declared_fields,
            "operator_count": inspected["operator_count"],
        }

    out: Dict[str, Any] = {
        "valid": True,
        "reject_code": None,
        "operator_count": inspected["operator_count"],
        "field_count": len(declared_fields),
        "counting_method": inspected["counting_method"],
        "scope_verified": False,
    }
    if state is None:
        out["note"] = "Structural preflight only. Supply initialized state to verify parent/scope/hypothesis."
        return out

    root = state.get("root_baseline")
    incumbent = state.get("incumbent")
    if not root or not incumbent:
        return {"valid": False, "reject_code": "STATE_NOT_INITIALIZED"}
    planning_rejection = _active_plan_rejection(state)
    if planning_rejection:
        return {"valid": False, "reject_code": planning_rejection["reason"]}
    focus = state.get("focus")
    if not focus or focus.get("status") != "OPEN":
        return {"valid": False, "reject_code": "NO_OPEN_FOCUS", "focus": focus}
    if str(candidate["parent_id"]) != str(incumbent.get("alpha_id")):
        return {"valid": False, "reject_code": "PARENT_NOT_CURRENT_INCUMBENT", "expected_parent_id": incumbent.get("alpha_id"), "candidate_parent_id": candidate.get("parent_id")}
    if language != str(incumbent.get("language", "")).upper():
        return {"valid": False, "reject_code": "LANGUAGE_DRIFT"}

    hypothesis_id = str(candidate["hypothesis_id"])
    hyp = state.get("hypotheses", {}).get(hypothesis_id)
    if not hyp:
        return {"valid": False, "reject_code": "UNKNOWN_HYPOTHESIS", "hypothesis_id": hypothesis_id}
    if require_open_hypothesis and hyp.get("status") != "OPEN":
        return {"valid": False, "reject_code": "HYPOTHESIS_NOT_OPEN", "hypothesis_id": hypothesis_id, "status": hyp.get("status")}
    if hyp.get("focus_revision") != focus.get("revision"):
        return {"valid": False, "reject_code": "HYPOTHESIS_FOCUS_MISMATCH"}
    contract = hyp.get("contract") or {}

    allowed_fields = set(state.get("allowed_fields", []))
    unknown_fields = sorted(set(declared_fields) - allowed_fields)
    if unknown_fields:
        return {"valid": False, "reject_code": "FIELD_OUTSIDE_ALLOWLIST", "unknown_fields": unknown_fields, "allowed_fields": sorted(allowed_fields)}

    incumbent_fields = sorted(incumbent.get("fields") or [])
    field_changed = declared_fields != incumbent_fields
    if field_changed and not _nonempty(contract.get("field_change_reason")):
        return {"valid": False, "reject_code": "FIELD_CHANGE_NOT_PREDECLARED", "incumbent_fields": incumbent_fields, "candidate_fields": declared_fields}

    incumbent_expr = str(incumbent.get("expression", ""))
    expr_changed = _canonical_expression(str(candidate["expression"])) != _canonical_expression(incumbent_expr)
    try:
        setting_diff = _settings_diff(incumbent.get("settings") or {}, settings)
    except ValueError as exc:
        return {"valid": False, "reject_code": "SETTINGS_KEY_AMBIGUITY", "detail": str(exc)}

    inc_keys = set(_setting_map(incumbent.get("settings") or {}))
    cand_keys = set(_setting_map(settings))
    if inc_keys != cand_keys:
        return {"valid": False, "reject_code": "FULL_SETTINGS_REQUIRED", "missing_keys": sorted(inc_keys - cand_keys), "extra_keys": sorted(cand_keys - inc_keys)}
    scope_drift = sorted(set(setting_diff) & LOCKED_SCOPE_KEYS)
    if scope_drift:
        return {"valid": False, "reject_code": "LOCKED_SCOPE_DRIFT", "setting_keys": scope_drift}

    mutation = contract.get("mutation") or {}
    if mutation.get("type") == "expression":
        if not expr_changed:
            return {"valid": False, "reject_code": "NO_EXPRESSION_CHANGE"}
        if setting_diff:
            return {"valid": False, "reject_code": "MULTI_AXIS_MUTATION", "setting_diff_keys": sorted(setting_diff)}
    elif mutation.get("type") == "setting":
        if expr_changed:
            return {"valid": False, "reject_code": "MULTI_AXIS_MUTATION"}
        if len(setting_diff) != 1:
            return {"valid": False, "reject_code": "SETTING_MUTATION_COUNT", "setting_diff_keys": sorted(setting_diff)}
        declared_key = _normalize_key(mutation.get("key"))
        actual_key = next(iter(setting_diff))
        if declared_key != actual_key:
            return {"valid": False, "reject_code": "SETTING_MUTATION_KEY_MISMATCH", "declared_key": declared_key, "actual_key": actual_key}
    else:
        return {"valid": False, "reject_code": "HYPOTHESIS_MUTATION_CONTRACT"}

    incumbent_count = incumbent.get("operator_count")
    if incumbent_count is None:
        incumbent_count = inspect_expression(incumbent_expr).get("operator_count")
    complexity_delta = inspected["operator_count"] - int(incumbent_count)
    if complexity_delta > 0 and not _nonempty(contract.get("complexity_reason")):
        return {"valid": False, "reject_code": "COMPLEXITY_GROWTH_NOT_PREDECLARED", "complexity_delta": complexity_delta}

    root_count = root.get("operator_count")
    out.update({
        "scope_verified": True,
        "incumbent_operator_count": incumbent_count,
        "complexity_delta_vs_incumbent": complexity_delta,
        "root_operator_count": root_count,
        "complexity_delta_vs_root": inspected["operator_count"] - int(root_count),
        "setting_diff_keys": sorted(setting_diff),
        "field_diff": {
            "added_vs_incumbent": sorted(set(declared_fields) - set(incumbent_fields)),
            "removed_vs_incumbent": sorted(set(incumbent_fields) - set(declared_fields)),
        },
        "note": "Local scope/diff checks passed; live platform/operator/economic validation is still required.",
    })
    return out


def _check_status_map(checks: list[Dict[str, Any]]) -> Dict[str, str]:
    return {str(c["name"]): str(c["status"]).upper() for c in checks}


def _evaluate_contract(contract: Dict[str, Any], before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
    before_metrics = _normalize_metrics((before or {}).get("metrics"))
    after_metrics = _normalize_metrics((after or {}).get("metrics"))
    before_checks = _normalize_checks((before or {}).get("checks"))
    after_checks = _normalize_checks((after or {}).get("checks"))
    after_check_map = _check_status_map(after_checks)

    criterion_results = []
    missing = []
    for c in contract.get("success_criteria", []):
        if c["type"] == "metric":
            name = c["name"]
            if name not in before_metrics or name not in after_metrics:
                missing.append(f"metric:{name}")
                continue
            b, a, min_change = before_metrics[name], after_metrics[name], float(c.get("min_change", 0.0))
            delta = a - b
            if c["direction"] == "higher":
                passed = delta > 0 if min_change == 0 else delta >= min_change
            else:
                passed = delta < 0 if min_change == 0 else -delta >= min_change
            criterion_results.append({"criterion": c, "before": b, "after": a, "delta": delta, "passed": passed})
        else:
            name = c["name"]
            if name not in after_check_map:
                missing.append(f"check:{name}")
                continue
            passed = after_check_map[name] == c["required_status"]
            criterion_results.append({"criterion": c, "after": after_check_map[name], "passed": passed})

    protected_results = []
    for p in contract.get("protected_metrics", []):
        name = p["name"]
        if name not in before_metrics or name not in after_metrics:
            missing.append(f"protected_metric:{name}")
            continue
        b, a, tol = before_metrics[name], after_metrics[name], float(p.get("tolerance", 0.0))
        passed = a >= b - tol if p["rule"] == "not_lower" else a <= b + tol
        protected_results.append({"policy": p, "before": b, "after": a, "passed": passed})

    before_check_names = {str(row["name"]) for row in before_checks}
    after_check_names = {str(row["name"]) for row in after_checks}
    missing_prior_checks = before_check_names - after_check_names
    missing.extend(f"check:{name}" for name in sorted(missing_prior_checks))

    old_blockers = _fail_blockers(before_checks)
    new_blockers = _fail_blockers(after_checks) - old_blockers
    old_unresolved = _unresolved_checks(before_checks)
    candidate_unresolved = _unresolved_checks(after_checks)
    new_unresolved = candidate_unresolved - old_unresolved
    if missing or new_unresolved:
        status = "INCONCLUSIVE"
    elif criterion_results and all(x["passed"] for x in criterion_results) and all(x["passed"] for x in protected_results) and not new_blockers:
        status = "SUPPORTED"
    else:
        status = "REFUTED"
    return {
        "status": status,
        "criterion_results": criterion_results,
        "protected_results": protected_results,
        "missing": sorted(set(missing)),
        "old_blockers": sorted(old_blockers),
        "candidate_blockers": sorted(_fail_blockers(after_checks)),
        "new_blockers": sorted(new_blockers),
        "old_unresolved_checks": sorted(old_unresolved),
        "candidate_unresolved_checks": sorted(candidate_unresolved),
        "new_unresolved_checks": sorted(new_unresolved),
        "missing_prior_checks": sorted(missing_prior_checks),
    }


class StateStore:
    def __init__(self, path: Path | str, root_alpha_id: str):
        self.path = Path(path)
        self.root_alpha_id = str(root_alpha_id)
        if not self.path.exists():
            self._write(self._initial_state())
        else:
            state = self.read()
            existing = state.get("root_alpha_id")
            if existing and str(existing) != self.root_alpha_id:
                raise ValueError(f"state root mismatch: {existing} != {self.root_alpha_id}")
            version = int(state.get("schema_version", 0))
            if version != SCHEMA_VERSION:
                raise ValueError(f"state schema {version} is not supported; re-initialize with schema {SCHEMA_VERSION}")

    def _initial_state(self) -> Dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "_state_revision": 0,
            "root_alpha_id": self.root_alpha_id,
            "planning_contract": "v1",
            "root_baseline": None,
            "incumbent": None,
            "evidence_revision": 0,
            "evidence": {},
            "optimization_plan": None,
            "optimization_plan_history": [],
            "focus": None,
            "allowed_fields": [],
            "allowed_field_evidence": {},
            "hypotheses": {},
            "candidates": {},
            "simulations": {},
            "run": None,
            "dashboard_context": {"fields": [], "visualization": {}},
            "log_entries": [],
        }

    def read(self) -> Dict[str, Any]:
        if not self.path.exists():
            return self._initial_state()
        state = json.loads(self.path.read_text(encoding="utf-8"))
        state.setdefault("_state_revision", 0)
        if "planning_contract" not in state:
            state["planning_contract"] = "legacy" if state.get("root_baseline") else "v1"
        state.setdefault("optimization_plan", None)
        state.setdefault("optimization_plan_history", [])
        state.setdefault("dashboard_context", {"fields": [], "visualization": {}})

        # Read-time compatibility enrichment for pre-v3.3 state snapshots.
        # These values are mechanically derivable and do not rewrite economic
        # or platform facts.
        for snapshot_key in ("root_baseline", "incumbent"):
            snapshot = state.get(snapshot_key)
            if not isinstance(snapshot, dict):
                continue
            evidence = snapshot.get("result_evidence")
            if not isinstance(evidence, dict):
                continue
            checks = evidence.get("checks")
            if not isinstance(checks, list):
                continue
            for row in checks:
                if not isinstance(row, dict) or not row.get("status"):
                    continue
                status = str(row.get("status")).upper()
                row.setdefault("policy_blocking", False)
                row.setdefault("policy_classified", bool(row.get("policy_blocking")) or status != "WARNING")
                row.setdefault("blocking", status == "FAIL" or bool(row.get("policy_blocking")))

        # v1 planning compatibility: priority and focus mechanism are derivable
        # from existing route order/binding.
        plan = state.get("optimization_plan")
        if state.get("planning_contract") == "v1" and isinstance(plan, dict):
            routes = plan.get("routes", [])
            for priority, route in enumerate(routes, start=1):
                route.setdefault("priority", priority)
            focus = state.get("focus")
            if isinstance(focus, dict) and not focus.get("mechanism"):
                route = None
                if focus.get("route_id"):
                    route = next((item for item in routes if item.get("id") == focus.get("route_id")), None)
                if route is None:
                    matching = [
                        item for item in routes
                        if item.get("status") == "ACTIVE"
                        and item.get("owner") == focus.get("owner")
                        and item.get("target") == focus.get("target")
                    ]
                    if len(matching) == 1:
                        route = matching[0]
                if route and route.get("mechanism"):
                    focus["mechanism"] = route.get("mechanism")
                    state["focus"] = focus
        return state

    def _ensure_run_log(self, state: Dict[str, Any]) -> tuple[Dict[str, Any], bool]:
        """Ensure this run has exactly one canonical MD under <skill>/logs/."""
        run = state.get("run")
        created = False
        if not isinstance(run, dict) or not run.get("log_path") or not run.get("run_id"):
            log_path, _canonical_state_path, run_id = _canonical_run_paths(self.root_alpha_id)
            run = {
                "run_id": run_id,
                "started_at": _now_iso(),
                "status": "RUNNING",
                "log_path": str(log_path.resolve()),
            }
            state["run"] = run
            created = True
        else:
            log_path = Path(str(run["log_path"])).expanduser().resolve()
            logs_root = LOGS_DIR.resolve()
            try:
                log_path.relative_to(logs_root)
            except ValueError as exc:
                raise ValueError(f"run log must live under {logs_root}: {log_path}") from exc
            if log_path.suffix.lower() != ".md":
                raise ValueError("run log must be a .md file")

        log_path = Path(str(state["run"]["log_path"])).expanduser().resolve()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        if not log_path.exists():
            log_path.write_text(_render_run_log(state), encoding="utf-8")
            created = True
        return state, created

    def append_log(self, section: str, text: str) -> Dict[str, Any]:
        if not section.strip() or not text.strip():
            return {"ok": False, "reason": "LOG_SECTION_AND_TEXT_REQUIRED"}
        state = self.read()
        state, created = self._ensure_run_log(state)
        entry = {"section": section.strip(), "text": text.rstrip(), "at": _now_iso()}
        state.setdefault("log_entries", []).append(entry)
        self._write(state)
        log_path = Path(state["run"]["log_path"])
        log_path.write_text(_render_run_log(state), encoding="utf-8")
        return {"ok": True, "log_path": str(log_path), "log_created_or_recreated": created, "entry_count": len(state["log_entries"])}

    def update_dashboard(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        state = self.read()
        state, created = self._ensure_run_log(state)
        try:
            state["dashboard_context"] = enrich_context_with_charts(state, payload)
        except ValueError as exc:
            return {"ok": False, "reason": "DASHBOARD_CONTRACT", "detail": str(exc)}
        self._write(state)
        log_path = Path(state["run"]["log_path"])
        log_path.write_text(_render_run_log(state), encoding="utf-8")
        return {
            "ok": True,
            "log_path": str(log_path),
            "log_created_or_recreated": created,
            "dashboard_context": state["dashboard_context"],
        }

    def _write(self, state: Dict[str, Any]) -> None:
        """Atomic compare-and-swap write.

        The optimizer may be invoked by multiple controller/tool calls in one
        run. A plain atomic replace prevents torn JSON but does not prevent a
        stale reader from silently overwriting a newer decision. Serialize the
        replace with a file lock and reject stale snapshots instead.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.path.with_name(self.path.name + ".lock")
        lock_path.touch(exist_ok=True)
        expected_revision = int(state.get("_state_revision", 0))

        with lock_path.open("r+") as lock_fh:
            fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX)
            try:
                current_revision = 0
                if self.path.exists():
                    current = json.loads(self.path.read_text(encoding="utf-8"))
                    current_revision = int(current.get("_state_revision", 0))
                if current_revision != expected_revision:
                    raise ValueError(
                        "STATE_WRITE_CONFLICT: state changed after read; "
                        f"expected revision {expected_revision}, found {current_revision}. "
                        "Re-read state and retry the intended transition serially."
                    )

                next_state = _copy_json(state)
                next_state["_state_revision"] = expected_revision + 1
                fd, tmp = tempfile.mkstemp(
                    prefix=self.path.name + ".",
                    suffix=".tmp",
                    dir=str(self.path.parent),
                )
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as fh:
                        json.dump(next_state, fh, ensure_ascii=False, sort_keys=True, indent=2)
                        fh.flush()
                        os.fsync(fh.fileno())
                    os.replace(tmp, self.path)
                    state["_state_revision"] = expected_revision + 1
                    run = state.get("run") or {}
                    if run.get("log_path"):
                        Path(str(run["log_path"])).write_text(_render_run_log(state), encoding="utf-8")
                finally:
                    if os.path.exists(tmp):
                        os.unlink(tmp)
            finally:
                fcntl.flock(lock_fh.fileno(), fcntl.LOCK_UN)

    def initialize(self, baseline: Dict[str, Any]) -> Dict[str, Any]:
        snapshot = _snapshot_from_json(baseline, self.root_alpha_id)
        state = self.read()
        state, log_created = self._ensure_run_log(state)
        if state.get("root_baseline"):
            self._write(state)
            if _canonical_json(state["root_baseline"]) == _canonical_json(snapshot):
                return {"initialized": True, "already_initialized": True, "root_alpha_id": self.root_alpha_id, "log_path": state["run"]["log_path"], "log_created_or_recreated": log_created}
            return {"initialized": False, "reason": "ROOT_BASELINE_IMMUTABLE", "log_path": state["run"]["log_path"]}
        state["root_baseline"] = snapshot
        state["incumbent"] = dict(snapshot)
        state["planning_contract"] = "v1"
        state["optimization_plan"] = None
        state["optimization_plan_history"] = []
        state["allowed_fields"] = list(snapshot["fields"])
        state["allowed_field_evidence"] = {f: "ROOT" for f in snapshot["fields"]}
        state["dashboard_context"] = {
            "fields": [{"name": field} for field in snapshot["fields"]],
            "visualization": {},
        }
        self._write(state)
        Path(state["run"]["log_path"]).write_text(_render_run_log(state), encoding="utf-8")
        return {"initialized": True, "already_initialized": False, "root_alpha_id": self.root_alpha_id, "incumbent_alpha_id": snapshot["alpha_id"], "allowed_fields": snapshot["fields"], "log_path": state["run"]["log_path"], "log_created_or_recreated": log_created}

    def refresh_incumbent_result(self, result_evidence: Dict[str, Any]) -> Dict[str, Any]:
        state = self.read()
        terminal = _terminal_rejection(state)
        if terminal:
            return terminal
        incumbent = state.get("incumbent")
        if not incumbent:
            return {"ok": False, "reason": "STATE_NOT_INITIALIZED"}
        if (state.get("focus") or {}).get("status") == "OPEN":
            return {"ok": False, "reason": "REFRESH_REQUIRES_CLOSED_FOCUS"}
        open_hypotheses = [key for key, item in state.get("hypotheses", {}).items() if item.get("status") == "OPEN"]
        if open_hypotheses:
            return {"ok": False, "reason": "REFRESH_REQUIRES_NO_OPEN_HYPOTHESIS", "hypotheses": open_hypotheses}

        required = ("alpha_id", "observed_at", "source", "response_complete", "authenticated", "metrics", "checks")
        missing = [key for key in required if key not in result_evidence]
        if missing:
            return {"ok": False, "reason": "RESULT_REFRESH_CONTRACT", "missing": missing}
        if str(result_evidence.get("alpha_id")) != str(incumbent.get("alpha_id")):
            return {
                "ok": False,
                "reason": "RESULT_REFRESH_ALPHA_MISMATCH",
                "expected_alpha_id": incumbent.get("alpha_id"),
                "alpha_id": result_evidence.get("alpha_id"),
            }
        try:
            observed = _parse_iso(result_evidence.get("observed_at"))
            metrics = _normalize_metrics(result_evidence.get("metrics"))
            checks = _normalize_checks(result_evidence.get("checks"))
        except ValueError as exc:
            return {"ok": False, "reason": "RESULT_REFRESH_CONTRACT", "detail": str(exc)}
        if not result_evidence.get("response_complete") or not result_evidence.get("authenticated"):
            return {"ok": False, "reason": "INCOMPLETE_OR_UNAUTHENTICATED_EVIDENCE"}
        source = result_evidence.get("source")
        if not isinstance(source, str) or ":" not in source:
            return {"ok": False, "reason": "RESULT_SOURCE_NOT_AUDITABLE"}

        previous = incumbent.get("result_evidence") or {}
        previous_observed = previous.get("observed_at")
        if previous_observed:
            try:
                previous_dt = _parse_iso(previous_observed)
            except ValueError:
                previous_dt = None
            if previous_dt and observed < previous_dt:
                return {
                    "ok": False,
                    "reason": "STALE_RESULT_REFRESH",
                    "observed_at": result_evidence.get("observed_at"),
                    "current_observed_at": previous_observed,
                }

        previous_checks = _normalize_checks(previous.get("checks")) if previous else []
        previous_check_names = {str(row["name"]) for row in previous_checks}
        current_check_names = {str(row["name"]) for row in checks}
        missing_prior_checks = sorted(previous_check_names - current_check_names)
        if missing_prior_checks:
            return {
                "ok": False,
                "reason": "RESULT_REFRESH_CHECK_SET_INCOMPLETE",
                "missing_checks": missing_prior_checks,
            }

        snapshot = {
            "metrics": metrics,
            "checks": checks,
            "observed_at": str(result_evidence["observed_at"]),
            "source": str(source),
            "response_complete": True,
            "authenticated": True,
        }
        if previous_observed and observed == _parse_iso(previous_observed):
            if _result_fact_fingerprint(previous) == _result_fact_fingerprint(snapshot):
                incumbent["result_evidence"] = snapshot
                state["incumbent"] = incumbent
                self._write(state)
                return {
                    "ok": True,
                    "already_current": True,
                    "facts_changed": False,
                    "incumbent_alpha_id": incumbent.get("alpha_id"),
                    "readiness": _submission_readiness(state),
                    "plan_status": (state.get("optimization_plan") or {}).get("status"),
                }
            return {"ok": False, "reason": "RESULT_REFRESH_TIMESTAMP_CONFLICT"}

        facts_changed = _result_fact_fingerprint(previous) != _result_fact_fingerprint(snapshot)
        incumbent["result_evidence"] = snapshot
        state["incumbent"] = incumbent
        plan = state.get("optimization_plan")
        if facts_changed and plan and plan.get("status") in {"ACTIVE", "EXHAUSTED"}:
            plan["status"] = "STALE"
            plan["stale_reason"] = "INCUMBENT_RESULT_REFRESHED"
            plan["stale_at_evidence_revision"] = state.get("evidence_revision", 0)
            state["optimization_plan"] = plan
        self._write(state)
        return {
            "ok": True,
            "already_current": False,
            "facts_changed": facts_changed,
            "incumbent_alpha_id": incumbent.get("alpha_id"),
            "readiness": _submission_readiness(state),
            "plan_status": (state.get("optimization_plan") or {}).get("status"),
        }

    def register_evidence(self, record: Dict[str, Any]) -> Dict[str, Any]:
        try:
            normalized = _validate_evidence_record(record)
        except ValueError as exc:
            return {"ok": False, "reason": "EVIDENCE_CONTRACT", "detail": str(exc)}
        state = self.read()
        terminal = _terminal_rejection(state)
        if terminal:
            return terminal
        eid = normalized["id"]
        normalized["content_fingerprint"] = _evidence_fingerprint(normalized)
        old = state["evidence"].get(eid)
        if old:
            content_keys = ("kind", "subject", "source", "observed_at", "claim")
            if _canonical_json({key: old.get(key) for key in content_keys}) == _canonical_json({key: normalized.get(key) for key in content_keys}):
                return {"ok": True, "already_registered": True, "id": eid, "revision": state["evidence_revision"]}
            return {"ok": False, "reason": "EVIDENCE_ID_ALREADY_USED"}
        state["evidence_revision"] = int(state.get("evidence_revision", 0)) + 1
        normalized["revision"] = state["evidence_revision"]
        state["evidence"][eid] = normalized
        self._write(state)
        return {"ok": True, "already_registered": False, "id": eid, "revision": state["evidence_revision"]}

    def set_plan(self, plan: Dict[str, Any], *, final_replan: bool = False) -> Dict[str, Any]:
        if not isinstance(plan, dict):
            return {"ok": False, "reason": "PLAN_CONTRACT"}
        state = self.read()
        terminal = _terminal_rejection(state)
        if terminal:
            return terminal
        if not state.get("root_baseline") or not state.get("incumbent"):
            return {"ok": False, "reason": "STATE_NOT_INITIALIZED"}
        current = state.get("optimization_plan")
        if (state.get("focus") or {}).get("status") == "OPEN":
            return {"ok": False, "reason": "PLAN_REQUIRES_CLOSED_FOCUS"}
        if any(item.get("status") == "OPEN" for item in state.get("hypotheses", {}).values()):
            return {"ok": False, "reason": "PLAN_REQUIRES_NO_OPEN_HYPOTHESIS"}

        if final_replan:
            if not current or current.get("final_replan_used"):
                return {"ok": False, "reason": "FINAL_REPLAN_ALREADY_USED"}
            if any(route.get("status") not in TERMINAL_ROUTE_STATUSES for route in current.get("routes", [])):
                return {"ok": False, "reason": "PLAN_NOT_EXHAUSTED"}
        elif current:
            if current.get("status") == "STALE":
                pass
            elif current.get("status") == "EXHAUSTED" and not current.get("final_replan_used"):
                return {"ok": False, "reason": "FINAL_REPLAN_REQUIRED"}
            else:
                return {"ok": False, "reason": "PLAN_ALREADY_ACTIVE"}

        current_incumbent_id = (current or {}).get("incumbent_alpha_id")
        incumbent_id = (state.get("incumbent") or {}).get("alpha_id")
        new_incumbent_cycle = bool(
            current
            and current.get("status") == "STALE"
            and current_incumbent_id
            and incumbent_id
            and str(current_incumbent_id) != str(incumbent_id)
        )

        raw_routes = plan.get("routes", [])
        if not isinstance(raw_routes, list):
            return {"ok": False, "reason": "PLAN_ROUTES_REQUIRED"}
        # The initial Root profile or any legitimate STALE re-profile may
        # find no justified normal route. Install an empty EXHAUSTED plan rather
        # than fabricating a route. A new Incumbent resets final-replan usage;
        # a same-Incumbent refresh preserves that cycle's existing allowance.
        allow_empty_fresh_profile = current is None or (current or {}).get("status") == "STALE"
        if not raw_routes and not final_replan and not allow_empty_fresh_profile:
            return {"ok": False, "reason": "PLAN_ROUTES_REQUIRED"}
        try:
            based_on_evidence_revision = int(plan.get("based_on_evidence_revision", state.get("evidence_revision", 0)))
        except (TypeError, ValueError):
            return {"ok": False, "reason": "PLAN_EVIDENCE_REVISION_INVALID"}
        if based_on_evidence_revision < 0 or based_on_evidence_revision > int(state.get("evidence_revision", 0)):
            return {"ok": False, "reason": "PLAN_EVIDENCE_REVISION_UNKNOWN"}

        routes = []
        ids = set()
        keys = set()
        for raw_route in raw_routes:
            try:
                route = _normalize_plan_route(raw_route)
            except ValueError as exc:
                return {"ok": False, "reason": "PLAN_ROUTE_CONTRACT", "detail": str(exc)}
            if route["id"] in ids:
                return {"ok": False, "reason": "DUPLICATE_ROUTE_ID", "route_id": route["id"]}
            route_key = _route_key(route)
            if route_key in keys:
                return {"ok": False, "reason": "DUPLICATE_PLAN_ROUTE", "route_key": route_key}
            ids.add(route["id"])
            keys.add(route_key)
            missing = [ref for ref in route["evidence_refs"] if ref not in state.get("evidence", {})]
            if missing:
                return {"ok": False, "reason": "UNKNOWN_EVIDENCE_REF", "missing": missing, "route_id": route["id"]}
            observation_refs = route.get("new_observation_refs", [])
            missing_observations = [ref for ref in observation_refs if ref not in state.get("evidence", {})]
            if missing_observations:
                return {"ok": False, "reason": "UNKNOWN_NEW_OBSERVATION_REF", "missing": missing_observations, "route_id": route["id"]}
            for ref in [*route["evidence_refs"], *observation_refs]:
                if int(state["evidence"][ref].get("revision", 0)) > based_on_evidence_revision:
                    return {"ok": False, "reason": "PLAN_EVIDENCE_REVISION_MISMATCH", "route_id": route["id"], "evidence_ref": ref}
            routes.append(route)

        active = [route for route in routes if route["status"] == "ACTIVE"]
        if len(active) > 1:
            return {"ok": False, "reason": "MULTIPLE_ACTIVE_ROUTES"}
        if routes and not active:
            routes[0]["status"] = "ACTIVE"
        for priority, route in enumerate(routes, start=1):
            route["priority"] = priority
            if route.get("status") == "ACTIVE":
                route.setdefault("activated_at_evidence_revision", int(state.get("evidence_revision", 0)))
            route.setdefault("candidate_result_count", 0)

        # Exhaustion/reopen history is scoped to the current Incumbent cycle.
        # A promoted Incumbent is a materially new parent and may legitimately
        # revisit a mechanism that was terminal for its predecessor.
        historical_routes = []
        if current and str(current.get("incumbent_alpha_id")) == str(incumbent_id):
            historical_routes.extend(current.get("routes", []))
        for old_plan in state.get("optimization_plan_history", []):
            if str(old_plan.get("incumbent_alpha_id")) == str(incumbent_id):
                historical_routes.extend(old_plan.get("routes", []))
        for route in routes:
            previous = [old for old in historical_routes if _route_key(old) == _route_key(route) and old.get("status") in TERMINAL_ROUTE_STATUSES]
            if not previous:
                continue
            if not route.get("reopen_reason"):
                return {"ok": False, "reason": "ROUTE_REOPEN_REASON_REQUIRED", "route_id": route["id"]}
            observation_refs = route.get("new_observation_refs", [])
            if not observation_refs:
                return {"ok": False, "reason": "ROUTE_NEW_OBSERVATION_REQUIRED", "route_id": route["id"]}
            closed_revision = max(int(old.get("closed_at_evidence_revision", 0)) for old in previous)
            available_fingerprints = {
                evidence.get("content_fingerprint") or _evidence_fingerprint(evidence)
                for evidence in state.get("evidence", {}).values()
                if int(evidence.get("revision", 0)) <= closed_revision
            }
            if not any(
                int(state["evidence"][ref].get("revision", 0)) > closed_revision
                and (state["evidence"][ref].get("content_fingerprint") or _evidence_fingerprint(state["evidence"][ref])) not in available_fingerprints
                for ref in observation_refs
            ):
                return {"ok": False, "reason": "ROUTE_NEW_OBSERVATION_NOT_NOVEL", "route_id": route["id"]}

        if current:
            state.setdefault("optimization_plan_history", []).append(_copy_json(current))
        revision = int((current or {}).get("revision", 0)) + 1
        normalized = {
            "revision": revision,
            "based_on_evidence_revision": based_on_evidence_revision,
            "final_replan_used": bool(final_replan or ((current or {}).get("final_replan_used", False) and not new_incumbent_cycle)),
            "status": "ACTIVE" if routes else "EXHAUSTED",
            "routes": routes,
            "incumbent_alpha_id": incumbent_id,
        }
        state["planning_contract"] = "v1"
        state["optimization_plan"] = normalized
        self._write(state)
        if routes:
            active_route = next((route for route in routes if route.get("status") == "ACTIVE"), None)
            return {
                "ok": True,
                "plan": normalized,
                "must_continue": True,
                "next_required_action": "SET_FOCUS",
                "active_route_id": (active_route or {}).get("id"),
            }
        return {
            "ok": True,
            "plan": normalized,
            "must_continue": False,
            "next_required_action": "FINAL_REPLAN_OR_TERMINAL",
        }

    def activate_route(self, route_id: str) -> Dict[str, Any]:
        if not route_id.strip():
            return {"ok": False, "reason": "ROUTE_ID_REQUIRED"}
        state = self.read()
        terminal = _terminal_rejection(state)
        if terminal:
            return terminal
        planning_rejection = _active_plan_rejection(state)
        if planning_rejection:
            return planning_rejection
        plan = state.get("optimization_plan")
        if not plan:
            return {"ok": False, "reason": "PLAN_REQUIRED"}
        if (state.get("focus") or {}).get("status") == "OPEN":
            return {"ok": False, "reason": "ACTIVE_FOCUS_EXISTS"}
        if any(item.get("status") == "OPEN" for item in state.get("hypotheses", {}).values()):
            return {"ok": False, "reason": "OPEN_HYPOTHESIS_EXISTS"}
        routes = plan.get("routes", [])
        target = next((route for route in routes if route.get("id") == route_id), None)
        if not target:
            return {"ok": False, "reason": "UNKNOWN_ROUTE", "route_id": route_id}
        if target.get("status") != "PENDING":
            return {"ok": False, "reason": "ROUTE_NOT_PENDING", "status": target.get("status")}
        active = [route for route in routes if route.get("status") == "ACTIVE"]
        if active:
            return {"ok": False, "reason": "ACTIVE_ROUTE_EXISTS", "route_id": active[0].get("id")}
        target["status"] = "ACTIVE"
        target["activated_at_evidence_revision"] = int(state.get("evidence_revision", 0))
        target.setdefault("candidate_result_count", 0)
        plan["status"] = "ACTIVE"
        self._write(state)
        return {"ok": True, "route": target, "plan": plan}

    def close_route(self, route_id: str, status: str, reason: str, evidence_ref: str | None = None) -> Dict[str, Any]:
        status = status.upper()
        if status not in {"DISMISSED", "COMPLETED"} or not route_id.strip() or not reason.strip():
            return {"ok": False, "reason": "ROUTE_CLOSE_CONTRACT"}
        state = self.read()
        terminal = _terminal_rejection(state)
        if terminal:
            return terminal
        planning_rejection = _active_plan_rejection(state)
        if planning_rejection:
            return planning_rejection
        plan = state.get("optimization_plan")
        if not plan:
            return {"ok": False, "reason": "PLAN_REQUIRED"}
        if (state.get("focus") or {}).get("status") == "OPEN":
            return {"ok": False, "reason": "ACTIVE_FOCUS_EXISTS"}
        if any(item.get("status") == "OPEN" for item in state.get("hypotheses", {}).values()):
            return {"ok": False, "reason": "OPEN_HYPOTHESIS_EXISTS"}
        route = next((item for item in plan.get("routes", []) if item.get("id") == route_id), None)
        if not route:
            return {"ok": False, "reason": "UNKNOWN_ROUTE", "route_id": route_id}
        if route.get("status") not in {"ACTIVE", "PENDING"}:
            return {"ok": False, "reason": "ROUTE_NOT_OPEN", "status": route.get("status")}
        closure_rejection = _route_closure_rejection(
            state, route, evidence_ref=evidence_ref, plan=plan
        )
        if closure_rejection:
            return closure_rejection
        was_active = route.get("status") == "ACTIVE"
        route["status"] = status
        route["close_reason"] = reason.strip()
        route["closed_at_evidence_revision"] = state.get("evidence_revision", 0)
        route["candidate_result_count"] = _route_candidate_result_count(
            state, str(route.get("id")), plan.get("incumbent_alpha_id")
        )
        if evidence_ref:
            route["zero_candidate_closure_evidence_ref"] = evidence_ref
        if was_active:
            for pending in plan.get("routes", []):
                if pending.get("status") == "PENDING":
                    pending["status"] = "ACTIVE"
                    pending["activated_at_evidence_revision"] = int(state.get("evidence_revision", 0))
                    pending.setdefault("candidate_result_count", 0)
                    break
        plan["status"] = "ACTIVE" if any(item.get("status") in {"PENDING", "ACTIVE"} for item in plan.get("routes", [])) else "EXHAUSTED"
        self._write(state)
        return {"ok": True, "route": route, "plan": plan}

    def set_focus(self, focus_type: str, owner: str, target: str, evidence_refs: list[str], blocker: str | None = None, route_id: str | None = None) -> Dict[str, Any]:
        focus_type = focus_type.upper()
        if focus_type not in FOCUS_TYPES or not owner.strip() or not target.strip() or not evidence_refs:
            return {"ok": False, "reason": "FOCUS_CONTRACT"}
        state = self.read()
        terminal = _terminal_rejection(state)
        if terminal:
            return terminal
        missing = [x for x in evidence_refs if x not in state.get("evidence", {})]
        if missing:
            return {"ok": False, "reason": "UNKNOWN_EVIDENCE_REF", "missing": missing}
        plan = state.get("optimization_plan")
        if state.get("planning_contract") == "legacy":
            return {"ok": False, "reason": "LEGACY_PLAN_REQUIRED"}
        focus_mechanism = None
        if state.get("planning_contract") == "v1":
            planning_rejection = _active_plan_rejection(state)
            if planning_rejection:
                return planning_rejection
            if not plan:
                return {"ok": False, "reason": "PLAN_REQUIRED"}
            active_routes = [route for route in plan.get("routes", []) if route.get("status") == "ACTIVE"]
            if len(active_routes) != 1:
                return {"ok": False, "reason": "ACTIVE_ROUTE_REQUIRED"}
            route = active_routes[0]
            if route_id and route_id != route.get("id"):
                return {"ok": False, "reason": "ROUTE_NOT_ACTIVE", "route_id": route_id}
            if route.get("owner") != owner or route.get("target") != target:
                return {"ok": False, "reason": "ROUTE_FOCUS_MISMATCH", "route_id": route.get("id")}
            if not set(evidence_refs) & set(route.get("evidence_refs", [])):
                return {"ok": False, "reason": "ROUTE_EVIDENCE_MISMATCH", "route_id": route.get("id")}
            if route.get("new_observation_refs") and not (set(evidence_refs) & set(route.get("new_observation_refs", []))):
                return {"ok": False, "reason": "ROUTE_REOPEN_OBSERVATION_MISMATCH", "route_id": route.get("id")}
            route_id = route.get("id")
            focus_mechanism = route.get("mechanism")
        inc_checks = (state.get("incumbent") or {}).get("result_evidence", {}).get("checks", [])
        blockers = _fail_blockers(_normalize_checks(inc_checks))
        if focus_type == "ENHANCEMENT":
            if blockers:
                return {"ok": False, "reason": "ENHANCEMENT_REQUIRES_NO_FAIL_BLOCKERS", "blockers": sorted(blockers)}
            readiness = _submission_readiness(state)
            if not readiness.get("ready"):
                return {
                    "ok": False,
                    "reason": "ENHANCEMENT_REQUIRES_RESOLVED_CHECKS",
                    "readiness": readiness,
                }
            if blocker:
                return {"ok": False, "reason": "ENHANCEMENT_MUST_NOT_DECLARE_BLOCKER"}
        else:
            if not blockers:
                return {"ok": False, "reason": "DEFECT_REQUIRES_FAIL_BLOCKER"}
            if not blocker or blocker not in blockers:
                return {"ok": False, "reason": "FOCUS_BLOCKER_NOT_CURRENT_FAIL", "blocker": blocker, "blockers": sorted(blockers)}
        current = state.get("focus")
        if current and current.get("status") == "OPEN":
            same = (
                current.get("type") == focus_type
                and current.get("owner") == owner
                and current.get("target") == target
                and current.get("mechanism") == focus_mechanism
                and current.get("blocker") == (blocker if focus_type == "DEFECT" else None)
                and set(current.get("evidence_refs", [])) == set(evidence_refs)
            )
            if same:
                return {"ok": True, "already_open": True, "focus": current}
            return {"ok": False, "reason": "FOCUS_ALREADY_OPEN", "focus": current}
        if current and current.get("status") == "EVIDENCE_EXHAUSTED":
            same_exhausted_family = (
                current.get("type") == focus_type
                and current.get("owner") == owner
                and current.get("target") == target
                and current.get("mechanism") == focus_mechanism
            )
            if same_exhausted_family:
                newest_ref_revision = max(int(state["evidence"][x].get("revision", 0)) for x in evidence_refs)
                if newest_ref_revision <= int(current.get("closed_at_evidence_revision", -1)):
                    return {"ok": False, "reason": "NEW_EVIDENCE_REQUIRED_AFTER_EXHAUSTION"}
        revision = int((current or {}).get("revision", 0)) + 1
        state["focus"] = {
            "type": focus_type,
            "owner": owner,
            "target": target,
            "mechanism": focus_mechanism,
            "blocker": blocker if focus_type == "DEFECT" else None,
            "status": "OPEN",
            "evidence_refs": sorted(dict.fromkeys(evidence_refs)),
            "opened_at_evidence_revision": state.get("evidence_revision", 0),
            "revision": revision,
        }
        if route_id:
            state["focus"]["route_id"] = route_id
        self._write(state)
        return {"ok": True, "already_open": False, "focus": state["focus"]}

    def exhaust_focus(self, reason: str, evidence_ref: str | None = None) -> Dict[str, Any]:
        if not reason.strip():
            return {"ok": False, "reason": "EXHAUST_REASON_REQUIRED"}
        state = self.read()
        terminal = _terminal_rejection(state)
        if terminal:
            return terminal
        planning_rejection = _active_plan_rejection(state)
        if planning_rejection:
            return planning_rejection
        focus = state.get("focus")
        if not focus or focus.get("status") != "OPEN":
            return {"ok": False, "reason": "NO_OPEN_FOCUS"}
        open_h = [k for k, v in state.get("hypotheses", {}).items() if v.get("status") == "OPEN" and v.get("focus_revision") == focus.get("revision")]
        if open_h:
            return {"ok": False, "reason": "OPEN_HYPOTHESIS_EXISTS", "hypotheses": open_h}
        plan = state.get("optimization_plan")
        route_id = focus.get("route_id")
        if isinstance(plan, dict) and route_id:
            route = next((item for item in plan.get("routes", []) if item.get("id") == route_id), None)
            if route and route.get("status") == "ACTIVE":
                closure_rejection = _route_closure_rejection(
                    state, route, evidence_ref=evidence_ref, plan=plan
                )
                if closure_rejection:
                    return closure_rejection
        focus["status"] = "EVIDENCE_EXHAUSTED"
        focus["exhaust_reason"] = reason
        focus["closed_at_evidence_revision"] = state.get("evidence_revision", 0)
        state["focus"] = focus
        next_route = None
        final_replan_required = False
        if plan and route_id:
            route = next((item for item in plan.get("routes", []) if item.get("id") == route_id), None)
            if route and route.get("status") == "ACTIVE":
                route["status"] = "EXHAUSTED"
                route["close_reason"] = reason.strip()
                route["closed_at_evidence_revision"] = state.get("evidence_revision", 0)
                route["candidate_result_count"] = _route_candidate_result_count(
                    state, str(route.get("id")), plan.get("incumbent_alpha_id")
                )
                if evidence_ref:
                    route["zero_candidate_closure_evidence_ref"] = evidence_ref
            next_route = next((item for item in plan.get("routes", []) if item.get("status") == "PENDING"), None)
            if next_route:
                next_route["status"] = "ACTIVE"
                next_route["activated_at_evidence_revision"] = int(state.get("evidence_revision", 0))
                next_route.setdefault("candidate_result_count", 0)
                plan["status"] = "ACTIVE"
            else:
                plan["status"] = "EXHAUSTED"
                final_replan_required = not bool(plan.get("final_replan_used"))
            state["optimization_plan"] = plan
        self._write(state)
        return {
            "ok": True,
            "status": "EVIDENCE_EXHAUSTED",
            "focus": focus,
            "next_route": next_route,
            "final_replan_required": final_replan_required,
        }

    def open_hypothesis(self, hypothesis_id: str, contract: Dict[str, Any]) -> Dict[str, Any]:
        if not hypothesis_id.strip():
            return {"ok": False, "reason": "HYPOTHESIS_ID_REQUIRED"}
        try:
            normalized = _validate_hypothesis_contract(contract)
        except ValueError as exc:
            return {"ok": False, "reason": "HYPOTHESIS_CONTRACT", "detail": str(exc)}
        state = self.read()
        terminal = _terminal_rejection(state)
        if terminal:
            return terminal
        if state.get("planning_contract") == "legacy":
            return {"ok": False, "reason": "LEGACY_PLAN_REQUIRED"}
        planning_rejection = _active_plan_rejection(state)
        if planning_rejection:
            return planning_rejection
        focus = state.get("focus")
        if not focus or focus.get("status") != "OPEN":
            return {"ok": False, "reason": "NO_OPEN_FOCUS"}
        missing_refs = [x for x in normalized["evidence_refs"] if x not in state.get("evidence", {})]
        if missing_refs:
            return {"ok": False, "reason": "UNKNOWN_EVIDENCE_REF", "missing": missing_refs}
        if not (set(normalized["evidence_refs"]) & set(focus.get("evidence_refs", []))):
            return {"ok": False, "reason": "HYPOTHESIS_NOT_GROUNDED_IN_FOCUS_EVIDENCE"}
        if state.get("planning_contract") == "v1" and normalized["target"] != focus.get("target"):
            return {"ok": False, "reason": "HYPOTHESIS_TARGET_MISMATCH", "focus_target": focus.get("target"), "hypothesis_target": normalized["target"]}
        if state.get("planning_contract") == "v1":
            if not _nonempty(normalized.get("mechanism")):
                return {"ok": False, "reason": "HYPOTHESIS_MECHANISM_REQUIRED"}
            if normalized.get("mechanism") != focus.get("mechanism"):
                return {
                    "ok": False,
                    "reason": "HYPOTHESIS_MECHANISM_MISMATCH",
                    "focus_mechanism": focus.get("mechanism"),
                    "hypothesis_mechanism": normalized.get("mechanism"),
                }
        old = state["hypotheses"].get(hypothesis_id)
        if old:
            if old.get("status") == "OPEN" and _canonical_json(old.get("contract")) == _canonical_json(normalized):
                return {"ok": True, "already_open": True, "hypothesis_id": hypothesis_id}
            return {"ok": False, "reason": "HYPOTHESIS_ID_ALREADY_USED", "status": old.get("status")}
        other_open = [
            hid for hid, item in state.get("hypotheses", {}).items()
            if item.get("status") == "OPEN" and item.get("focus_revision") == focus.get("revision")
        ]
        if other_open:
            return {"ok": False, "reason": "OPEN_HYPOTHESIS_EXISTS", "hypotheses": sorted(other_open)}
        state["hypotheses"][hypothesis_id] = {
            "contract": normalized,
            "status": "OPEN",
            "focus_revision": focus.get("revision"),
            "route_id": focus.get("route_id"),
            "opened_at_evidence_revision": state.get("evidence_revision", 0),
            "candidate_fingerprint": None,
            "result": None,
        }
        self._write(state)
        return {"ok": True, "already_open": False, "hypothesis_id": hypothesis_id}

    def allow_field(self, field: str, evidence_ref: str) -> Dict[str, Any]:
        field = field.strip()
        state = self.read()
        terminal = _terminal_rejection(state)
        if terminal:
            return terminal
        ev = state.get("evidence", {}).get(evidence_ref)
        if not field or not ev:
            return {"ok": False, "reason": "ALLOW_FIELD_EVIDENCE_REQUIRED"}
        if ev.get("kind") != "FIELD_SCOPE" or ev.get("subject") != field:
            return {"ok": False, "reason": "FIELD_SCOPE_EVIDENCE_MISMATCH", "evidence": ev}
        if field not in state["allowed_fields"]:
            state["allowed_fields"].append(field); state["allowed_fields"].sort()
        state["allowed_field_evidence"][field] = evidence_ref
        self._write(state)
        return {"ok": True, "field": field, "evidence_ref": evidence_ref, "allowed_fields": state["allowed_fields"]}

    def reserve_simulation(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        state = self.read()
        terminal = _terminal_rejection(state)
        if terminal:
            return {"allowed": False, "reason": terminal["reason"], "status": terminal["status"]}
        pre = preflight_candidate(candidate, state, require_open_hypothesis=True)
        if not pre["valid"]:
            return {"allowed": False, "reason": pre["reject_code"], "preflight": pre}
        fp = payload_fingerprint(candidate)
        hid = str(candidate["hypothesis_id"])
        hyp = state["hypotheses"][hid]
        bound = hyp.get("candidate_fingerprint")
        if bound and bound != fp:
            return {"allowed": False, "reason": "HYPOTHESIS_PAYLOAD_IMMUTABLE", "hypothesis_id": hid, "existing_fingerprint": bound, "candidate_fingerprint": fp}
        if not bound:
            hyp["candidate_fingerprint"] = fp
            state["hypotheses"][hid] = hyp

        rec = state["simulations"].get(fp)
        if rec:
            status = rec.get("status")
            if status == "HTTP_429":
                if int(rec.get("retry_count", 0)) >= MAX_EXPLICIT_429_RETRIES:
                    return {"allowed": False, "reason": "HTTP_429_RETRY_EXHAUSTED", "fingerprint": fp}
            elif status == "RELEASED":
                pass
            elif status == "RESERVED":
                return {"allowed": False, "reason": "RESERVED_RECOVERY_REQUIRED", "fingerprint": fp}
            elif status == "AMBIGUOUS_POST":
                return {"allowed": False, "reason": "AMBIGUOUS_POST_BLOCK", "fingerprint": fp}
            else:
                return {"allowed": False, "reason": "DUPLICATE_PAYLOAD", "fingerprint": fp, "status": status}
        else:
            rec = {"status": "NEW", "retry_count": 0, "simulation_id": None, "release_history": [], "history": []}
        rec["status"] = "RESERVED"
        rec["candidate_parent_id"] = candidate.get("parent_id")
        rec["hypothesis_id"] = hid
        rec.setdefault("history", []).append({"status": "RESERVED", "at": _now_iso()})
        state["simulations"][fp] = rec
        state["candidates"][fp] = {
            "spec": candidate,
            "preflight": pre,
            "status": "RESERVED",
            "route_id": hyp.get("route_id"),
        }
        self._write(state)
        return {"allowed": True, "reason": None, "fingerprint": fp, "preflight": pre}

    def record_transport(self, fingerprint: str, status: str, simulation_id: str | None = None) -> Dict[str, Any]:
        state = self.read()
        terminal = _terminal_rejection(state)
        if terminal:
            return terminal
        rec = state["simulations"].get(fingerprint)
        if not rec:
            return {"ok": False, "reason": "UNKNOWN_FINGERPRINT"}
        current = str(rec.get("status"))
        status = status.upper()
        allowed = TRANSPORT_TRANSITIONS.get(current, set())
        if status not in allowed:
            return {"ok": False, "reason": "INVALID_TRANSPORT_TRANSITION", "current": current, "requested": status, "allowed": sorted(allowed)}
        if status == "POSTED" and not simulation_id:
            return {"ok": False, "reason": "SIMULATION_ID_REQUIRED"}
        if current == "AMBIGUOUS_POST" and status == "POSTED" and not simulation_id:
            return {"ok": False, "reason": "RECOVERY_SIMULATION_ID_REQUIRED"}
        if status == "HTTP_429":
            rec["retry_count"] = int(rec.get("retry_count", 0)) + 1
        rec["status"] = status
        if simulation_id is not None:
            rec["simulation_id"] = simulation_id
        event = {"status": status, "at": _now_iso()}
        if simulation_id is not None: event["simulation_id"] = simulation_id
        rec.setdefault("history", []).append(event)
        if status == "POSTED":
            rec["posted_at"] = event["at"]
        state["simulations"][fingerprint] = rec
        if fingerprint in state["candidates"]:
            state["candidates"][fingerprint]["status"] = status
        self._write(state)
        return {"ok": True, "fingerprint": fingerprint, "from": current, "status": status, "retry_count": rec.get("retry_count", 0)}

    def release_reservation(self, fingerprint: str, reason: str) -> Dict[str, Any]:
        if not reason.strip():
            return {"ok": False, "reason": "RELEASE_REASON_REQUIRED"}
        state = self.read()
        terminal = _terminal_rejection(state)
        if terminal:
            return terminal
        rec = state["simulations"].get(fingerprint)
        if not rec:
            return {"ok": False, "reason": "UNKNOWN_FINGERPRINT"}
        if rec.get("status") != "RESERVED" or rec.get("simulation_id"):
            return {"ok": False, "reason": "RELEASE_NOT_ALLOWED", "status": rec.get("status")}
        rec["status"] = "RELEASED"
        rec.setdefault("release_history", []).append({"reason": reason, "at": _now_iso()})
        rec.setdefault("history", []).append({"status": "RELEASED", "at": _now_iso()})
        state["simulations"][fingerprint] = rec
        if fingerprint in state["candidates"]:
            state["candidates"][fingerprint]["status"] = "RELEASED"
        self._write(state)
        return {"ok": True, "fingerprint": fingerprint, "status": "RELEASED"}

    def abandon_hypothesis(self, hypothesis_id: str, evidence_ref: str, reason: str) -> Dict[str, Any]:
        """Close a pre-POST transport failure without treating it as a result."""
        if not hypothesis_id.strip() or not evidence_ref.strip() or not reason.strip():
            return {"ok": False, "reason": "ABANDON_CONTRACT_REQUIRED"}
        state = self.read()
        terminal = _terminal_rejection(state)
        if terminal:
            return terminal
        focus = state.get("focus")
        if not focus or focus.get("status") != "OPEN":
            return {"ok": False, "reason": "NO_OPEN_FOCUS"}
        hypothesis = state.get("hypotheses", {}).get(hypothesis_id)
        if not hypothesis:
            return {"ok": False, "reason": "UNKNOWN_HYPOTHESIS"}
        if hypothesis.get("status") != "OPEN":
            return {"ok": False, "reason": "HYPOTHESIS_NOT_OPEN", "status": hypothesis.get("status")}
        if hypothesis.get("focus_revision") != focus.get("revision"):
            return {"ok": False, "reason": "HYPOTHESIS_NOT_IN_CURRENT_FOCUS"}

        evidence = state.get("evidence", {}).get(evidence_ref)
        if not evidence:
            return {"ok": False, "reason": "UNKNOWN_EVIDENCE_REF"}
        if evidence.get("kind") != "TRANSPORT_FAILURE" or evidence.get("subject") != hypothesis_id:
            return {"ok": False, "reason": "TRANSPORT_FAILURE_EVIDENCE_MISMATCH"}

        fingerprint = hypothesis.get("candidate_fingerprint")
        if not fingerprint:
            return {"ok": False, "reason": "CANDIDATE_FINGERPRINT_REQUIRED"}
        simulation = state.get("simulations", {}).get(fingerprint)
        if not simulation:
            return {"ok": False, "reason": "UNKNOWN_FINGERPRINT"}
        if simulation.get("status") != "RELEASED" or simulation.get("simulation_id"):
            return {
                "ok": False,
                "reason": "ABANDON_ONLY_RELEASED_WITHOUT_SIMULATION",
                "status": simulation.get("status"),
                "simulation_id": simulation.get("simulation_id"),
            }

        hypothesis["status"] = "INCONCLUSIVE"
        hypothesis["result"] = {
            "disposition": "ABANDONED_BEFORE_POST",
            "reason": reason.strip(),
            "evidence_ref": evidence_ref,
            "transport_status": simulation.get("status"),
            "simulation_id": None,
        }
        state["hypotheses"][hypothesis_id] = hypothesis
        if fingerprint in state.get("candidates", {}):
            state["candidates"][fingerprint]["disposition"] = "INCONCLUSIVE"
            state["candidates"][fingerprint]["disposition_reason"] = reason.strip()
        self._write(state)
        return {
            "ok": True,
            "hypothesis_id": hypothesis_id,
            "status": "INCONCLUSIVE",
            "evidence_ref": evidence_ref,
            "fingerprint": fingerprint,
        }

    def evaluate_result(self, candidate: Dict[str, Any], result_evidence: Dict[str, Any]) -> Dict[str, Any]:
        state = self.read()
        terminal = _terminal_rejection(state)
        if terminal:
            return terminal
        pre = preflight_candidate(candidate, state, require_open_hypothesis=True)
        if not pre["valid"]:
            return {"ok": False, "reason": pre["reject_code"], "preflight": pre}
        fp = payload_fingerprint(candidate)
        transport = state.get("simulations", {}).get(fp)
        if not transport or transport.get("status") != "POSTED" or not transport.get("simulation_id"):
            return {"ok": False, "reason": "POSTED_SIMULATION_REQUIRED"}
        required = ("alpha_id", "simulation_id", "observed_at", "source", "response_complete", "authenticated", "metrics", "checks")
        missing = [k for k in required if k not in result_evidence]
        if missing:
            return {"ok": False, "reason": "RESULT_EVIDENCE_CONTRACT", "missing": missing}
        if str(result_evidence["simulation_id"]) != str(transport["simulation_id"]):
            return {"ok": False, "reason": "SIMULATION_ID_MISMATCH"}
        try:
            observed = _parse_iso(result_evidence["observed_at"])
            posted = _parse_iso(transport["posted_at"])
            metrics = _normalize_metrics(result_evidence["metrics"])
            checks = _normalize_checks(result_evidence["checks"])
        except ValueError as exc:
            return {"ok": False, "reason": "RESULT_EVIDENCE_CONTRACT", "detail": str(exc)}
        if observed < posted:
            return {"ok": False, "reason": "STALE_RESULT_EVIDENCE", "observed_at": result_evidence["observed_at"], "posted_at": transport["posted_at"]}
        if not result_evidence.get("response_complete") or not result_evidence.get("authenticated"):
            return {"ok": False, "reason": "INCOMPLETE_OR_UNAUTHENTICATED_EVIDENCE"}
        if not isinstance(result_evidence.get("source"), str) or ":" not in result_evidence["source"]:
            return {"ok": False, "reason": "RESULT_SOURCE_NOT_AUDITABLE"}

        hid = str(candidate["hypothesis_id"])
        hyp = state["hypotheses"].get(hid)
        if not hyp or hyp.get("status") != "OPEN":
            return {"ok": False, "reason": "HYPOTHESIS_NOT_OPEN", "status": None if not hyp else hyp.get("status")}
        result_snapshot = {
            "alpha_id": str(result_evidence["alpha_id"]),
            "simulation_id": str(result_evidence["simulation_id"]),
            "observed_at": str(result_evidence["observed_at"]),
            "source": str(result_evidence["source"]),
            "response_complete": True,
            "authenticated": True,
            "metrics": metrics,
            "checks": checks,
        }
        evaluation = _evaluate_contract(hyp["contract"], state["incumbent"].get("result_evidence", {}), result_snapshot)
        hyp["status"] = evaluation["status"]
        hyp["result"] = {"evidence": result_snapshot, "evaluation": evaluation}
        state["hypotheses"][hid] = hyp
        state["candidates"][fp]["result_evaluation"] = evaluation
        state["candidates"][fp]["result_alpha_id"] = str(result_evidence["alpha_id"])
        route_id = state["candidates"][fp].get("route_id") or hyp.get("route_id")
        plan = state.get("optimization_plan")
        if route_id and isinstance(plan, dict):
            route = next((item for item in plan.get("routes", []) if item.get("id") == route_id), None)
            if route is not None:
                route["candidate_result_count"] = _route_candidate_result_count(
                    state, str(route_id), plan.get("incumbent_alpha_id")
                )
        self._write(state)
        return {"ok": True, "hypothesis_id": hid, "status": evaluation["status"], "evaluation": evaluation}

    def promote(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        state = self.read()
        terminal = _terminal_rejection(state)
        if terminal:
            return {"promoted": False, "reason": terminal["reason"], "status": terminal["status"]}
        pre = preflight_candidate(candidate, state, require_open_hypothesis=False)
        if not pre["valid"]:
            return {"promoted": False, "reason": pre["reject_code"], "preflight": pre}
        hid = str(candidate["hypothesis_id"])
        hyp = state["hypotheses"].get(hid)
        if not hyp or hyp.get("status") != "SUPPORTED" or not hyp.get("result"):
            return {"promoted": False, "reason": "MACHINE_SUPPORTED_RESULT_REQUIRED", "status": None if not hyp else hyp.get("status")}
        fp = payload_fingerprint(candidate)
        transport = state.get("simulations", {}).get(fp)
        if not transport or transport.get("status") != "POSTED" or not transport.get("simulation_id"):
            return {"promoted": False, "reason": "POSTED_SIMULATION_REQUIRED"}
        result = hyp["result"]["evidence"]
        if str(result.get("simulation_id")) != str(transport.get("simulation_id")):
            return {"promoted": False, "reason": "RESULT_TRANSPORT_MISMATCH"}
        snapshot = {
            "alpha_id": str(result["alpha_id"]),
            "expression": str(candidate["expression"]),
            "fields": sorted(dict.fromkeys(x.strip() for x in candidate["fields"])),
            "settings": candidate["settings"],
            "language": str(candidate["language"]).upper(),
            "operator_count": pre["operator_count"],
            "counting_method": pre["counting_method"],
            "result_evidence": {
                "metrics": result["metrics"], "checks": result["checks"], "observed_at": result["observed_at"],
                "source": result["source"], "response_complete": True, "authenticated": True,
            },
        }
        previous = state["incumbent"]["alpha_id"]
        state["incumbent"] = snapshot
        state["candidates"][fp].update({"status": "PROMOTED", "alpha_id": snapshot["alpha_id"]})
        focus = state.get("focus")
        if focus and focus.get("status") == "OPEN":
            focus["status"] = "CLOSED"
            focus["closed_reason"] = "PROMOTED_SUPPORTED_CANDIDATE"
            focus["closed_at_evidence_revision"] = state.get("evidence_revision", 0)
            state["focus"] = focus
        plan = state.get("optimization_plan")
        if plan:
            plan["status"] = "STALE"
            plan["stale_reason"] = "INCUMBENT_CHANGED"
            plan["stale_at_evidence_revision"] = state.get("evidence_revision", 0)
            plan["stale_incumbent_alpha_id"] = snapshot["alpha_id"]
            state["optimization_plan"] = plan
        self._write(state)
        return {"promoted": True, "previous_incumbent": previous, "incumbent_alpha_id": snapshot["alpha_id"], "complexity_delta_vs_root": pre.get("complexity_delta_vs_root")}

    def finish_run(self, status: str, reason: str) -> Dict[str, Any]:
        status = status.upper()
        if status not in RUN_TERMINAL_STATUSES or not reason.strip():
            return {"ok": False, "reason": "RUN_FINISH_CONTRACT"}
        state = self.read()
        terminal = _terminal_rejection(state)
        if terminal:
            return terminal
        state, _ = self._ensure_run_log(state)
        run = state["run"]
        plan = state.get("optimization_plan")
        focus = state.get("focus") or {}
        open_hypotheses = [key for key, item in state.get("hypotheses", {}).items() if item.get("status") == "OPEN"]

        # Explicit abort/boundary terminals freeze the state exactly as observed.
        # They are valid even if research objects remain open, because requiring
        # artificial cleanup can destroy the evidence of why the run stopped.
        if status not in FORCED_TERMINAL_STATUSES:
            if not state.get("root_baseline") or not state.get("incumbent"):
                return {"ok": False, "reason": "STATE_NOT_INITIALIZED"}
            if open_hypotheses:
                return {"ok": False, "reason": "OPEN_HYPOTHESIS_EXISTS", "hypotheses": open_hypotheses}
            if focus.get("status") == "OPEN":
                return {"ok": False, "reason": "OPEN_FOCUS_EXISTS"}

            if status == "COMPLETED_WITH_EXHAUSTION":
                if not plan or not plan.get("final_replan_used"):
                    return {"ok": False, "reason": "FINAL_REPLAN_REQUIRED"}
                if plan.get("status") != "EXHAUSTED" or any(route.get("status") not in TERMINAL_ROUTE_STATUSES for route in plan.get("routes", [])):
                    return {"ok": False, "reason": "PLAN_NOT_EXHAUSTED"}
                route_violations = _terminal_route_attempt_violations(state)
                if route_violations:
                    return {
                        "ok": False,
                        "reason": "ZERO_CANDIDATE_ROUTE_NOT_AUDITABLY_EXHAUSTED",
                        "routes": route_violations,
                    }
            elif status == "SUBMISSION_READY":
                readiness = _submission_readiness(state)
                if not readiness.get("ready"):
                    return {"ok": False, "reason": readiness.get("reason"), "readiness": readiness}
            elif plan and plan.get("status") == "ACTIVE" and any(route.get("status") == "ACTIVE" for route in plan.get("routes", [])):
                return {"ok": False, "reason": "ACTIVE_ROUTE_EXISTS"}
        run["status"] = status
        run["finished_at"] = _now_iso()
        run["end_reason"] = reason.strip()
        state["run"] = run
        self._write(state)
        Path(run["log_path"]).write_text(_render_run_log(state), encoding="utf-8")
        return {"ok": True, "status": status, "run": run}

    def summary(self) -> Dict[str, Any]:
        state = self.read()
        state, log_created = self._ensure_run_log(state)
        self._write(state)
        return {
            "schema_version": state.get("schema_version"),
            "planning_contract": state.get("planning_contract"),
            "root_alpha_id": state.get("root_alpha_id"),
            "initialized": bool(state.get("root_baseline")),
            "run_id": (state.get("run") or {}).get("run_id"),
            "log_path": (state.get("run") or {}).get("log_path"),
            "log_exists": bool((state.get("run") or {}).get("log_path") and Path(state["run"]["log_path"]).exists()),
            "log_created_or_recreated": log_created,
            "incumbent_alpha_id": (state.get("incumbent") or {}).get("alpha_id"),
            "evidence_revision": state.get("evidence_revision"),
            "run_status": (state.get("run") or {}).get("status", "RUNNING"),
            "optimization_plan": state.get("optimization_plan"),
            "focus": state.get("focus"),
            "allowed_fields": state.get("allowed_fields", []),
            "hypotheses": {k: v.get("status") for k, v in state.get("hypotheses", {}).items()},
            "simulation_states": {k: v.get("status") for k, v in state.get("simulations", {}).items()},
            "submission_readiness": _submission_readiness(state),
            "dashboard_context": state.get("dashboard_context", {}),
        }


def start_run(root_alpha_id: str) -> Dict[str, Any]:
    log_path, state_path, run_id = _canonical_run_paths(root_alpha_id)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    store = StateStore(state_path, root_alpha_id)
    state = store.read()
    state["run"] = {"run_id": run_id, "started_at": _now_iso(), "status": "RUNNING", "log_path": str(log_path.resolve())}
    state, _ = store._ensure_run_log(state)
    store._write(state)
    return {
        "ok": True,
        "root_alpha_id": str(root_alpha_id),
        "run_id": run_id,
        "state_path": str(state_path.resolve()),
        "log_path": str(log_path.resolve()),
        "log_exists": log_path.exists(),
    }


def _load_text_arg(path: str | None) -> str:
    if path:
        return Path(path).read_text(encoding="utf-8")
    return os.sys.stdin.read()


def _load_json_arg(path: str | None) -> Dict[str, Any]:
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return json.load(os.sys.stdin)


def _main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="WQ Alpha Optimizer deterministic FE guard/state helper")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("inspect-root"); p.add_argument("expression")
    p = sub.add_parser("start-run"); p.add_argument("--root-alpha-id", required=True)
    p = sub.add_parser("init"); p.add_argument("--baseline", required=True); p.add_argument("--state", required=True); p.add_argument("--root-alpha-id", required=True)
    p = sub.add_parser("append-log"); p.add_argument("--state", required=True); p.add_argument("--root-alpha-id", required=True); p.add_argument("--section", required=True); p.add_argument("--text-file")
    p = sub.add_parser("update-dashboard"); p.add_argument("--dashboard", required=True); p.add_argument("--state", required=True); p.add_argument("--root-alpha-id", required=True)
    p = sub.add_parser("status"); p.add_argument("--state", required=True); p.add_argument("--root-alpha-id", required=True)
    p = sub.add_parser("register-evidence"); p.add_argument("--evidence", required=True); p.add_argument("--state", required=True); p.add_argument("--root-alpha-id", required=True)
    p = sub.add_parser("refresh-incumbent"); p.add_argument("--result", required=True); p.add_argument("--state", required=True); p.add_argument("--root-alpha-id", required=True)
    p = sub.add_parser("set-plan"); p.add_argument("--plan", required=True); p.add_argument("--state", required=True); p.add_argument("--root-alpha-id", required=True); p.add_argument("--final-replan", action="store_true")
    p = sub.add_parser("activate-route"); p.add_argument("--route-id", required=True); p.add_argument("--state", required=True); p.add_argument("--root-alpha-id", required=True)
    p = sub.add_parser("close-route"); p.add_argument("--route-id", required=True); p.add_argument("--status", required=True, choices=["DISMISSED", "COMPLETED"]); p.add_argument("--reason", required=True); p.add_argument("--evidence-ref"); p.add_argument("--state", required=True); p.add_argument("--root-alpha-id", required=True)
    p = sub.add_parser("set-focus"); p.add_argument("--state", required=True); p.add_argument("--root-alpha-id", required=True); p.add_argument("--type", required=True); p.add_argument("--owner", required=True); p.add_argument("--target", required=True); p.add_argument("--blocker"); p.add_argument("--route-id"); p.add_argument("--evidence-ref", action="append", required=True)
    p = sub.add_parser("exhaust-focus"); p.add_argument("--state", required=True); p.add_argument("--root-alpha-id", required=True); p.add_argument("--reason", required=True); p.add_argument("--evidence-ref")
    p = sub.add_parser("finish-run"); p.add_argument("--status", required=True, choices=sorted(RUN_TERMINAL_STATUSES)); p.add_argument("--reason", required=True); p.add_argument("--state", required=True); p.add_argument("--root-alpha-id", required=True)
    p = sub.add_parser("open-hypothesis"); p.add_argument("--state", required=True); p.add_argument("--root-alpha-id", required=True); p.add_argument("--id", required=True); p.add_argument("--contract", required=True)
    p = sub.add_parser("abandon-hypothesis"); p.add_argument("--state", required=True); p.add_argument("--root-alpha-id", required=True); p.add_argument("--hypothesis-id", required=True); p.add_argument("--evidence-ref", required=True); p.add_argument("--reason", required=True)
    p = sub.add_parser("allow-field"); p.add_argument("--state", required=True); p.add_argument("--root-alpha-id", required=True); p.add_argument("--field", required=True); p.add_argument("--evidence-ref", required=True)
    p = sub.add_parser("preflight"); p.add_argument("--candidate"); p.add_argument("--state"); p.add_argument("--root-alpha-id")
    p = sub.add_parser("reserve"); p.add_argument("--candidate"); p.add_argument("--state", required=True); p.add_argument("--root-alpha-id", required=True)
    p = sub.add_parser("record"); p.add_argument("--state", required=True); p.add_argument("--root-alpha-id", required=True); p.add_argument("--fingerprint", required=True); p.add_argument("--status", required=True); p.add_argument("--simulation-id")
    p = sub.add_parser("release"); p.add_argument("--state", required=True); p.add_argument("--root-alpha-id", required=True); p.add_argument("--fingerprint", required=True); p.add_argument("--reason", required=True)
    p = sub.add_parser("evaluate"); p.add_argument("--candidate", required=True); p.add_argument("--result", required=True); p.add_argument("--state", required=True); p.add_argument("--root-alpha-id", required=True)
    p = sub.add_parser("promote"); p.add_argument("--candidate", required=True); p.add_argument("--state", required=True); p.add_argument("--root-alpha-id", required=True)

    args = parser.parse_args(argv)
    try:
        if args.cmd == "inspect-root": out = inspect_root(args.expression)
        elif args.cmd == "start-run": out = start_run(args.root_alpha_id)
        elif args.cmd == "init": out = StateStore(args.state, args.root_alpha_id).initialize(_load_json_arg(args.baseline))
        elif args.cmd == "append-log": out = StateStore(args.state, args.root_alpha_id).append_log(args.section, _load_text_arg(args.text_file))
        elif args.cmd == "update-dashboard": out = StateStore(args.state, args.root_alpha_id).update_dashboard(_load_json_arg(args.dashboard))
        elif args.cmd == "status": out = StateStore(args.state, args.root_alpha_id).summary()
        elif args.cmd == "register-evidence": out = StateStore(args.state, args.root_alpha_id).register_evidence(_load_json_arg(args.evidence))
        elif args.cmd == "refresh-incumbent": out = StateStore(args.state, args.root_alpha_id).refresh_incumbent_result(_load_json_arg(args.result))
        elif args.cmd == "set-plan": out = StateStore(args.state, args.root_alpha_id).set_plan(_load_json_arg(args.plan), final_replan=args.final_replan)
        elif args.cmd == "activate-route": out = StateStore(args.state, args.root_alpha_id).activate_route(args.route_id)
        elif args.cmd == "close-route": out = StateStore(args.state, args.root_alpha_id).close_route(args.route_id, args.status, args.reason, args.evidence_ref)
        elif args.cmd == "set-focus": out = StateStore(args.state, args.root_alpha_id).set_focus(args.type, args.owner, args.target, args.evidence_ref, args.blocker, args.route_id)
        elif args.cmd == "exhaust-focus": out = StateStore(args.state, args.root_alpha_id).exhaust_focus(args.reason, args.evidence_ref)
        elif args.cmd == "finish-run": out = StateStore(args.state, args.root_alpha_id).finish_run(args.status, args.reason)
        elif args.cmd == "open-hypothesis": out = StateStore(args.state, args.root_alpha_id).open_hypothesis(args.id, _load_json_arg(args.contract))
        elif args.cmd == "abandon-hypothesis": out = StateStore(args.state, args.root_alpha_id).abandon_hypothesis(args.hypothesis_id, args.evidence_ref, args.reason)
        elif args.cmd == "allow-field": out = StateStore(args.state, args.root_alpha_id).allow_field(args.field, args.evidence_ref)
        elif args.cmd == "preflight":
            cand = _load_json_arg(args.candidate)
            out = preflight_candidate(cand, StateStore(args.state, args.root_alpha_id).read(), require_open_hypothesis=True) if args.state and args.root_alpha_id else preflight_candidate(cand)
        elif args.cmd == "reserve": out = StateStore(args.state, args.root_alpha_id).reserve_simulation(_load_json_arg(args.candidate))
        elif args.cmd == "record": out = StateStore(args.state, args.root_alpha_id).record_transport(args.fingerprint, args.status, args.simulation_id)
        elif args.cmd == "release": out = StateStore(args.state, args.root_alpha_id).release_reservation(args.fingerprint, args.reason)
        elif args.cmd == "evaluate": out = StateStore(args.state, args.root_alpha_id).evaluate_result(_load_json_arg(args.candidate), _load_json_arg(args.result))
        else: out = StateStore(args.state, args.root_alpha_id).promote(_load_json_arg(args.candidate))
    except (ValueError, KeyError, json.JSONDecodeError) as exc:
        out = {"ok": False, "reason": "GUARD_ERROR", "detail": str(exc)}

    print(json.dumps(out, ensure_ascii=False, sort_keys=True, indent=2))
    success = out.get("valid", out.get("allowed", out.get("promoted", out.get("initialized", out.get("ok", True)))))
    return 0 if success else 2


if __name__ == "__main__":
    raise SystemExit(_main())

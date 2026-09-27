from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import optimizer_guard as guard


def _plans_for_incumbent_cycle(state: dict[str, Any]) -> list[dict[str, Any]]:
    incumbent_id = str((state.get("incumbent") or {}).get("alpha_id") or "")
    plans = [
        *[item for item in state.get("optimization_plan_history", []) if isinstance(item, dict)],
        state.get("optimization_plan"),
    ]
    return [
        plan
        for plan in plans
        if isinstance(plan, dict)
        and (
            not incumbent_id
            or str(plan.get("incumbent_alpha_id") or "") == incumbent_id
        )
    ]


def _route_context_index(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for plan in _plans_for_incumbent_cycle(state):
        synthesis = plan.get("synthesis") if isinstance(plan.get("synthesis"), dict) else {}
        assessment_map = guard._synthesis_assessment_map(synthesis)
        for route in plan.get("routes", []):
            if not isinstance(route, dict) or not route.get("id"):
                continue
            refs = [str(ref) for ref in route.get("assessment_refs", [])]
            assessments = [assessment_map[ref] for ref in refs if ref in assessment_map]
            method_families = sorted(
                {
                    str(row.get("method_family"))
                    for row in assessments
                    if row.get("method_family")
                }
            )
            index[str(route["id"])] = {
                "route_id": str(route["id"]),
                "target": route.get("target"),
                "owner": route.get("owner"),
                "mechanism": route.get("mechanism"),
                "objective_type": route.get("objective_type"),
                "route_status": route.get("status"),
                "method_families": method_families,
            }
    return index


def _candidate_history(state: dict[str, Any]) -> list[dict[str, Any]]:
    incumbent = state.get("incumbent") if isinstance(state.get("incumbent"), dict) else {}
    incumbent_id = str(incumbent.get("alpha_id") or "")
    before_metrics = {
        str(key).upper(): float(value)
        for key, value in ((incumbent.get("result_evidence") or {}).get("metrics") or {}).items()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    }
    route_index = _route_context_index(state)
    rows: list[dict[str, Any]] = []

    for hypothesis_id, hypothesis in sorted((state.get("hypotheses") or {}).items()):
        if not isinstance(hypothesis, dict):
            continue
        result = hypothesis.get("result")
        if not isinstance(result, dict):
            continue
        evidence = result.get("evidence") if isinstance(result.get("evidence"), dict) else {}
        evaluation = result.get("evaluation") if isinstance(result.get("evaluation"), dict) else {}
        fingerprint = str(hypothesis.get("candidate_fingerprint") or "")
        candidate = (state.get("candidates") or {}).get(fingerprint)
        if not isinstance(candidate, dict):
            continue
        spec = candidate.get("spec") if isinstance(candidate.get("spec"), dict) else {}
        if incumbent_id and str(spec.get("parent_id") or "") != incumbent_id:
            continue

        after_metrics = {
            str(key).upper(): float(value)
            for key, value in (evidence.get("metrics") or {}).items()
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        }
        deltas = {
            name: after_metrics[name] - before_metrics[name]
            for name in sorted(set(before_metrics) & set(after_metrics))
        }
        failed_success = [
            str((item.get("criterion") or {}).get("name") or "")
            for item in evaluation.get("criterion_results", [])
            if isinstance(item, dict) and not item.get("passed")
        ]
        failed_protection = [
            str((item.get("policy") or {}).get("name") or "")
            for item in evaluation.get("protected_results", [])
            if isinstance(item, dict) and not item.get("passed")
        ]
        route_id = str(candidate.get("route_id") or hypothesis.get("route_id") or "")
        route_context = route_index.get(route_id, {})
        settings_diff = guard._settings_diff(
            incumbent.get("settings") if isinstance(incumbent.get("settings"), dict) else {},
            spec.get("settings") if isinstance(spec.get("settings"), dict) else {},
        )
        rows.append(
            {
                "hypothesis_id": str(hypothesis_id),
                "route_id": route_id,
                "target": route_context.get("target") or (hypothesis.get("contract") or {}).get("target"),
                "owner": route_context.get("owner"),
                "mechanism": route_context.get("mechanism") or (hypothesis.get("contract") or {}).get("mechanism"),
                "method_families": route_context.get("method_families", []),
                "status": evaluation.get("status") or hypothesis.get("status"),
                "candidate_alpha_id": evidence.get("alpha_id"),
                "observed_at": evidence.get("observed_at"),
                "evidence_ref": result.get("evidence_ref") or candidate.get("result_evidence_ref"),
                "metrics_before": before_metrics,
                "metrics_after": after_metrics,
                "metric_deltas": deltas,
                "failed_success": failed_success,
                "failed_protection": failed_protection,
                "new_blockers": evaluation.get("new_blockers", []),
                "new_unresolved_checks": evaluation.get("new_unresolved_checks", []),
                "expression_changed": str(spec.get("expression") or "") != str(incumbent.get("expression") or ""),
                "settings_diff_keys": sorted(settings_diff),
            }
        )

    rows.sort(key=lambda row: (str(row.get("observed_at") or ""), str(row.get("hypothesis_id") or "")))
    return rows


def _enhancement_progress(
    state: dict[str, Any],
    objectives: list[tuple[str, str]],
    candidate_history: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    route_index = _route_context_index(state)
    conclusive_routes = {
        str(row.get("route_id") or "")
        for row in candidate_history
        if str(row.get("status") or "").upper() in {"SUPPORTED", "REFUTED"}
    }
    rows: list[dict[str, Any]] = []
    for target, owner in objectives:
        entry = guard._catalog_entry_for_enhancement(target, owner)
        catalog_families = sorted(
            {
                str(item.get("method_family"))
                for item in entry.get("mechanisms", [])
                if isinstance(item, dict) and item.get("method_family")
            }
        )
        routed_families: set[str] = set()
        conclusive_families: set[str] = set()
        for route_id, context in route_index.items():
            if str(context.get("target") or "") != target or str(context.get("owner") or "") != owner:
                continue
            families = {str(value) for value in context.get("method_families", []) if value}
            routed_families.update(families)
            if route_id in conclusive_routes:
                conclusive_families.update(families)
        rows.append(
            {
                "target": target,
                "owner": owner,
                "catalog_method_families": catalog_families,
                "routed_method_families": sorted(routed_families),
                "conclusive_candidate_method_families": sorted(conclusive_families),
                "unrouted_method_families": sorted(set(catalog_families) - routed_families),
            }
        )
    return rows


def build_synthesis_scaffold(
    state: dict[str, Any],
    enhancements: list[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    blockers = guard._current_blockers(state)
    revision = int(state.get("evidence_revision", 0))
    incumbent = state.get("incumbent") if isinstance(state.get("incumbent"), dict) else {}
    dashboard = state.get("dashboard_context") if isinstance(state.get("dashboard_context"), dict) else {}
    explicit_enhancements = [tuple(item) for item in (enhancements or [])]
    entered_enhancements = [
        (str(item["target"]), str(item["owner"]))
        for item in guard._enhancement_objectives_for_incumbent_cycle(state)
    ]
    enhancement_objectives = sorted(dict.fromkeys([*entered_enhancements, *explicit_enhancements]))
    candidate_history = _candidate_history(state)

    available_evidence = [
        {
            "id": evidence_id,
            "kind": row.get("kind"),
            "subject": row.get("subject"),
            "source": row.get("source"),
            "claim": row.get("claim"),
            "revision": row.get("revision"),
        }
        for evidence_id, row in sorted((state.get("evidence") or {}).items())
        if isinstance(row, dict)
    ]

    rows = []
    for blocker in blockers:
        entry = guard._catalog_entry_for_blocker(blocker)
        rows.append(
            {
                "name": blocker,
                "target": entry.get("target"),
                "owner": entry.get("owner"),
                "observation_refs": [],
                "mechanisms": [
                    {
                        "id": f"{blocker}:{item['id']}",
                        "mechanism": item["id"],
                        "method_family": item["method_family"],
                        "status": "UNASSESSED",
                        "evidence_refs": [],
                        "reasoning": "",
                        "next_question": "",
                    }
                    for item in entry.get("mechanisms", [])
                ],
            }
        )

    enhancement_rows = []
    for target, owner in enhancement_objectives:
        entry = guard._catalog_entry_for_enhancement(target, owner)
        enhancement_rows.append(
            {
                "target": target,
                "owner": owner,
                "observation_refs": [],
                "mechanisms": [
                    {
                        "id": f"ENHANCEMENT:{target}:{item['id']}",
                        "mechanism": item["id"],
                        "method_family": item["method_family"],
                        "status": "UNASSESSED",
                        "evidence_refs": [],
                        "reasoning": "",
                        "next_question": "",
                    }
                    for item in entry.get("mechanisms", [])
                ],
            }
        )

    return {
        "incumbent_alpha_id": str(incumbent.get("alpha_id") or ""),
        "based_on_evidence_revision": revision,
        "context": {
            "expression": incumbent.get("expression"),
            "settings": incumbent.get("settings"),
            "result_evidence": incumbent.get("result_evidence"),
            "fields": dashboard.get("fields", []),
            "visualization": dashboard.get("visualization", {}),
        },
        "blockers": rows,
        "enhancements": enhancement_rows,
        "candidate_history": candidate_history,
        "enhancement_progress": _enhancement_progress(
            state,
            enhancement_objectives,
            candidate_history,
        ),
        "available_evidence": available_evidence,
        "instructions": {
            "statuses": [
                "ACTIONABLE",
                "PLAUSIBLE_PROBE",
                "NEEDS_DIAGNOSTIC",
                "EXCLUDED",
            ],
            "rule": (
                "Combine current evidence with the blocker or enhancement owner's mechanism families. "
                "After any evaluated candidate, reason from candidate_history jointly rather than treating "
                "each Result as an isolated experiment. Use metric_deltas, protection failures, route history "
                "and unrouted method families to formulate the next discriminator. Do not claim the cause is "
                "known unless evidence supports it. When evidence is limited, PLAUSIBLE_PROBE or "
                "NEEDS_DIAGNOSTIC is preferred over pretending a mechanism is proven or declaring exhaustion. "
                "Lack of an immediately obvious payload is not evidence that a method family is exhausted."
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a deterministic evidence+method synthesis scaffold for the current incumbent."
    )
    parser.add_argument("--state", required=True)
    parser.add_argument("--root-alpha-id", required=True)
    parser.add_argument(
        "--enhancement",
        nargs=2,
        action="append",
        metavar=("TARGET", "OWNER"),
        help="Add a blocker-free enhancement objective, e.g. TURNOVER optimization/turnover.md",
    )
    parser.add_argument("--output")
    args = parser.parse_args()

    store = guard.StateStore(Path(args.state), args.root_alpha_id)
    scaffold = build_synthesis_scaffold(
        store.read(),
        enhancements=[tuple(item) for item in (args.enhancement or [])],
    )
    text = json.dumps(scaffold, ensure_ascii=False, indent=2)
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
        print(json.dumps({"ok": True, "output": str(path)}, ensure_ascii=False))
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

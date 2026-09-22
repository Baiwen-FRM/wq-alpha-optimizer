from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import optimizer_guard as guard


def build_synthesis_scaffold(state: dict[str, Any]) -> dict[str, Any]:
    blockers = guard._current_blockers(state)
    revision = int(state.get("evidence_revision", 0))
    incumbent = state.get("incumbent") if isinstance(state.get("incumbent"), dict) else {}
    dashboard = state.get("dashboard_context") if isinstance(state.get("dashboard_context"), dict) else {}
    run = state.get("run") if isinstance(state.get("run"), dict) else {}

    raw_intake_path = None
    if run.get("log_path") and run.get("run_id"):
        log_path = Path(str(run["log_path"]))
        candidate = log_path.parent / ".data" / str(run["run_id"]) / "intake.json"
        if candidate.exists():
            raw_intake_path = str(candidate)

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

    return {
        "incumbent_alpha_id": str(incumbent.get("alpha_id") or ""),
        "based_on_evidence_revision": revision,
        "context": {
            "expression": incumbent.get("expression"),
            "settings": incumbent.get("settings"),
            "result_evidence": incumbent.get("result_evidence"),
            "fields": dashboard.get("fields", []),
            "visualization": dashboard.get("visualization", {}),
            "raw_intake_path": raw_intake_path,
        },
        "blockers": rows,
        "available_evidence": available_evidence,
        "instructions": {
            "statuses": [
                "ACTIONABLE",
                "PLAUSIBLE_PROBE",
                "NEEDS_DIAGNOSTIC",
                "EXCLUDED",
            ],
            "rule": (
                "Combine current evidence with the blocker owner's mechanism families. "
                "Do not claim the cause is known unless evidence supports it. "
                "When evidence is limited, PLAUSIBLE_PROBE is preferred over pretending "
                "a mechanism is proven or declaring exhaustion."
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a deterministic evidence+method synthesis scaffold for the current incumbent."
    )
    parser.add_argument("--state", required=True)
    parser.add_argument("--root-alpha-id", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()

    store = guard.StateStore(Path(args.state), args.root_alpha_id)
    scaffold = build_synthesis_scaffold(store.read())
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

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import optimizer_guard as guard


def build_synthesis_scaffold(state: dict[str, Any]) -> dict[str, Any]:
    blockers = guard._current_blockers(state)
    revision = int(state.get("evidence_revision", 0))
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
        "incumbent_alpha_id": str((state.get("incumbent") or {}).get("alpha_id") or ""),
        "based_on_evidence_revision": revision,
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

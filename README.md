# wq-alpha-optimizer v3.2.2

Constrained optimizer for an **existing WorldQuant BRAIN Alpha**. It is an evidence-driven repair/enhancement pipeline, not a metric-search engine.

This README is an orientation map, not a second rulebook. Normative behavior lives in the files below.

## Single sources of truth

- `SKILL.md` — trigger, global boundaries and stop policy.
- `references/index.md` — current Metric/Check → Primary owner router.
- `references/runtime/alpha-intake.md` — controller order, including canonical run-log creation.
- `references/runtime/candidate-contract.md` — the only machine contract for state/evidence/plan/focus/hypothesis/candidate/result/transport/promotion.
- `references/runtime/thresholds.md` — current platform check/limit/readiness interpretation.
- `references/runtime/operators.md` — FE tokenization/counting semantics and operator-role guidance.
- `references/runtime/anchors.md` — generic numeric anchors.
- `references/runtime/report-templates.md` — human-readable log structure only.
- `references/optimization/` — defect mechanisms and same-thesis repair families.
- `scripts/optimizer_guard.py` — deterministic enforcement of the machine contract, including plan/route/run transitions, where locally verifiable.

Release ZIP excludes runtime log contents/test scratch/`__MACOSX`/`.DS_Store`/pycache/pyc/temp backups. Run `python3 scripts/optimizer_guard.py --help` for the CLI.

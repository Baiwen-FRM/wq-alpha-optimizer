# wq-alpha-optimizer v3.5.2

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
- `scripts/optimizer_guard.py` — deterministic enforcement of the machine contract, including current-result refresh, plan/route/focus/hypothesis/candidate/transport/result/promotion/readiness/terminal transitions, where locally verifiable.

Release ZIP excludes runtime log contents/test scratch/`__MACOSX`/`.DS_Store`/pycache/pyc/temp backups. Run `python3 scripts/optimizer_guard.py --help` for the CLI.


## v3.3 lifecycle

The normal FE path is:

```text
Run start → Root snapshot → Diagnose/Profile → Ordered Plan
→ one Active Route → Focus → Frozen Hypothesis → Candidate/Transport
→ Result → Promotion or route closure
→ fresh Incumbent Result/check refresh when needed
→ re-profile/re-plan
→ SUBMISSION_READY / SUCCESS / one-final-replan exhaustion
   / USER_STOP / SCOPE_BOUNDARY / PLATFORM_UNRECOVERABLE
```

An empty Profile/Plan is a valid result when no justified route exists; the controller must not invent a route merely to keep searching. GitHub CI runs the stdlib test suite and compile checks for every push/PR.


## v3.3.1 real-run hardening

- stale/concurrent Guard state writes are rejected instead of silently overwriting newer evidence;
- planned routes must already be actionable, rather than placeholders for possible future diagnostics;
- zero-hypothesis route exhaustion requires a newly observed reason that removed actionability;
- conflicting PENDING/UNKNOWN submission evidence gets one bounded reconciliation attempt and otherwise remains unresolved.


## v3.3.2 diagnostic-first exhaustion

- a route cannot claim exhaustion while a material in-scope discriminator is still cheaply obtainable;
- Robust/Sub-Universe failures escalate to targeted visualization/recordset diagnostics before structural or decay candidates when those diagnostics can distinguish the root cause;
- prior-run negative evidence may prevent duplicate candidates only when Root identity and current material facts still match;
- final logs must show which diagnostics were completed, reused, unavailable, or still unknown before exhaustion.


## v3.4.0 progressive optimization + run dashboard

- hypothesis support is explicitly separated from final submission-threshold passage: a safely improving candidate can become the new Incumbent even while the original blocker remains FAIL;
- REFUTED applies to the frozen hypothesis/payload, not automatically to the whole mechanism family;
- after promotion the plan becomes stale and the optimizer re-diagnoses from the improved Incumbent, enabling bounded stepwise progress without dense parameter scans;
- every canonical run MD now opens with a live Dashboard: expression/settings, Result/checks, field metadata, visualization/recordsets, optional SVG charts, and candidate progression;
- dashboard charts are generated with the Python standard library only and remain local under ignored run-log assets.


## v3.5 current architecture: local WQ Lab + lean execution

- authenticated BRAIN I/O uses the user's local WQ Lab/`wq_lib`; WQ Lab remains narrowly scoped to BRAIN communication and is not vendored into the Skill;
- normal Root startup is one lean command, `scripts/bootstrap_run.py --alpha-id <ID>`, which obtains only current Alpha facts, submission checks and exact metadata for fields actually used by the expression, then initializes Guard/Dashboard;
- visualization/recordsets are not a fixed startup tax: they are requested only when they can materially distinguish the active mechanism, and any acquired recordsets are rendered by fixed code in `recordset_dashboard.py` / `run_dashboard.py`;
- Profile/Plan are internal control state, not a user-facing stopping point: an actionable active route continues in the same invocation to Focus → Hypothesis → Candidate → Simulation/Result;
- live operator/schema validation happens only after a concrete candidate exists and only when that candidate changes signature-sensitive structure;
- normal runtime artifacts stay under ignored `logs/`; do not create bundles of scratch evidence/projection files in `/private/tmp` or other project-external locations;
- no silent CNHKMCP fallback is used, so transport choice cannot change optimizer behavior or Dashboard layout.


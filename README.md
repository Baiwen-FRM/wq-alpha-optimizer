# wq-alpha-optimizer v3.6.0

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

An empty Profile/Plan is valid only after the evidence+method synthesis gate proves that every current blocker method family is either audibly excluded or has no unresolved discriminator; the controller must not invent a route merely to keep searching, but it also cannot use history summaries to skip unassessed method space. GitHub CI runs the stdlib test suite and compile checks for every push/PR.


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


## v3.5.0 local WQ Lab provider

- authenticated BRAIN I/O now uses the user's local WQ Lab/`wq_lib` as the normal provider instead of agent-selected CNHKMCP calls;
- WQ Lab remains narrowly scoped to BRAIN communication; the optimizer does not vendor or restructure it;
- the optimizer requires only three additive WQ Lab primitives: exact `get_datafield`, generic recordset discovery, and generic recordset retrieval;
- `wq_lab_provider.py intake` fixes Root data acquisition order and emits separate raw-evidence, Guard-baseline, and Dashboard projections;
- visualization control stays in the Skill: same expression/settings with only `visualization=true`, followed by bounded recordset discovery;
- recordset-to-chart behavior is code-defined in `recordset_dashboard.py`; the model no longer chooses chart type or ordering;
- normal execution has no silent CNHKMCP fallback, preventing backend choice from changing run behavior or UI.


## v3.5.1 deterministic bootstrap

- normal Root intake is now one command: `scripts/bootstrap_run.py --alpha-id <ID>`;
- the controller no longer manually chains run creation, WQ Lab intake, Guard initialization and Dashboard update;
- every run persists raw intake, Guard baseline projection and Dashboard projection under `logs/.data/<run_id>/`;
- WQ Lab capability mismatch fails before run creation; BRAIN/auth intake failure after run creation is written to the canonical audit log and stops the bootstrap;
- low-level provider commands remain available only for debugging/recovery, preserving one stable normal execution order.


## v3.5.3 full intake + continuous optimization

- restores the v3.5.1 full deterministic intake as the normal path;
- four information surfaces are mandatory before diagnosis: Expression + Settings, current Result + submission checks, exact used-field/dataset metadata, and Visualization with all currently listed recordsets;
- visualization recordset discovery no longer stops at the first rich recordset; it waits for a stable rich listing within the bounded retry budget and keeps the largest listing observed;
- recordset count is platform-derived rather than hard-coded: if BRAIN lists 19, all 19 are attempted; if it lists a different number, that full current list is attempted;
- Profile/Plan are explicitly nonterminal. An active plan returns `must_continue=true` and `next_required_action=SET_FOCUS`; normal optimize execution must continue to candidate simulation/result instead of replying “next step later”;
- WQ Lab remains BRAIN I/O only; optimization reasoning, state, charts and Markdown remain in the Skill.


## v3.5.4 route-attempt enforcement

- fixes the remaining loophole where a controller could create an actionable ACTIVE route, close it without any Focus/Hypothesis/Candidate Result, run an empty final re-plan, and still reach `COMPLETED_WITH_EXHAUSTION`;
- every route now records its activation evidence revision and candidate Results are bound back to `route_id`;
- ACTIVE route closure requires either at least one evaluated candidate Result, or an explicit genuinely-new post-activation diagnostic `evidence_ref`;
- duplicate/timestamp-only/pre-plan evidence cannot satisfy the zero-candidate closure exception;
- automatic activation of the next pending route stamps a new activation revision, so each route has its own attempt boundary;
- exhaustion terminal performs a second route-history audit and rejects unaudited zero-candidate closures.


## v3.6.0 evidence + method synthesis

- mandatory intake facts and blocker repair references are now joined before planning instead of being treated as separate tracks;
- each current blocker is assessed through its canonical method families using `ACTIONABLE / PLAUSIBLE_PROBE / NEEDS_DIAGNOSTIC / EXCLUDED`;
- limited evidence no longer forces false certainty: a bounded discriminating experiment is legal through `PLAUSIBLE_PROBE`, while conflicting clues can require a targeted diagnostic;
- routes must cite synthesis assessments and carry the evidence that made the mechanism testable; one upstream mechanism may explain multiple blockers only when each blocker has a compatible assessment;
- historical “tried before” summaries cannot certify mechanism exhaustion or `EXCLUDED`;
- normal non-empty plans remain lightweight and do not enumerate every method family;
- an empty plan/final re-plan is deliberately strict: every current blocker method family must be assessed, with no remaining testable or diagnostic question;
- the canonical mechanism catalog is aligned with existing Sharpe/Fitness/Returns/Margin/Turnover/Sub/Robust/Ladder/Correlation/Weight/Data-quality/Investability references and unknown project checks route to definition resolution first.

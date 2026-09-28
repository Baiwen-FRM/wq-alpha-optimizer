# Runtime scripts

`optimizer_guard.py` 是 stdlib-only 的确定性 FE guard/state helper。它只执行本地可验证的机器约束，不判断经济 thesis 是否正确。

工作流和 contract 以 `../references/runtime/` 下的 owner 文件为准；本 README 只说明脚本边界。

CLI：

```text
python3 scripts/optimizer_guard.py --help
```

`update-dashboard` enriches the canonical MD header with field metadata and visualization diagnostics. Expression/settings/results/checks are rendered directly from current guard state. The field metadata context acts as a registry: Root metadata arrives from intake, later `FIELD_SCOPE` evidence adds exact metadata for newly authorized fields, and the rendered table shows only fields used by the current Incumbent. Full incoming chart series are rendered immediately into one sibling `<run>_dashboard.svg`; the embedded Guard state keeps only compact chart projections for resume/audit efficiency. The Markdown references that one SVG. No Unicode sparkline is used as the primary visualization, and no `assets/` or per-chart SVG files are created.

The same Markdown also renders a deterministic `Machine Decision Trail` from Guard state. It exposes each H1–Hn frozen contract, candidate payload identity, Result/evaluation, promotion/disposition and learned evidence claim. This is a readable projection of existing state, not a second hand-maintained log; only the later `Append-only Notes` section is manually appended.

Planning transitions are intentionally small: `set-plan`, `activate-route`,
`close-route`, `exhaust-focus`, `refresh-incumbent`, and `finish-run`.
`set-plan --final-replan` is accepted only after all routes in the current plan
are terminal. A repeated final re-plan for the same Incumbent is allowed only when routing-material evidence has appeared since the previous final re-plan (for example a current candidate Result or mechanism diagnostic); transport-only/history evidence does not reopen the gate. Root or a legitimate STALE re-profile may install an empty EXHAUSTED plan only after the v2 synthesis contract provides a complete auditable no-action proof. `refresh-incumbent` updates the current authenticated Result/check snapshot and stales an existing plan when facts change.

`withdraw-hypothesis` is the narrow pre-reservation correction path: it only works while an OPEN hypothesis has no candidate fingerprint and no candidate/simulation record. Use it when deterministic preflight finds a contract omission before reserve/POST. It records the old hypothesis as WITHDRAWN and requires a new hypothesis ID. It is deliberately blocked after reserve, including after RELEASED.

`finish-run --status COMPLETED_WITH_EXHAUSTION` requires the final re-plan
gate and an EXHAUSTED plan. `SUBMISSION_READY` is machine-gated by the selected Root-protected submission candidate
Incumbent check snapshot. `USER_STOP`, `SCOPE_BOUNDARY`, and
`PLATFORM_UNRECOVERABLE` are explicit terminal freeze states.

Guard 不能独立验证 live BRAIN operator signature、dataset semantics、经济因果或远端 source authenticity；这些必须来自当前认证平台 evidence 与 Primary defect reference。


State mutation is single-writer. Concurrent/stale state snapshots are rejected with `STATE_WRITE_CONFLICT`; re-read the state and retry serially. This prevents evidence loss from overlapping Guard commands.


## Evidence + method synthesis

After mandatory intake evidence is registered, use:

```text
python3 scripts/mechanism_synthesis.py --state <STATE_PATH> --root-alpha-id <ROOT_ALPHA_ID>
```

The script creates a deterministic blocker/enhancement-method-family/evidence scaffold. For blocker-free work, pass `--enhancement <TARGET> <OWNER>` (repeatable); enhancement objectives already entered in the current Incumbent cycle are also recovered automatically. The scaffold includes structured `candidate_history` and `enhancement_progress`, so the next planning pass can reason jointly over all conclusive Results and see which catalog method families have never been routed. It does not choose economic causes or operators. The controller fills mechanism assessments, and `optimizer_guard.py set-plan` enforces the v2 synthesis contract. Normal routes need only the assessments that justify those routes; any same-Incumbent empty plan requires full catalog coverage for entered enhancement objectives, including STALE re-profiles after fresh Result/check refresh.

## Reserved candidate executor

After `optimizer_guard.py reserve` returns `allowed=true`, run:

```text
python3 scripts/execute_reserved_candidate.py --state <STATE_PATH> --root-alpha-id <ROOT_ALPHA_ID>
```

It owns the mechanical path `RESERVED → SUBMITTING → POSTED → current Result/check snapshot → evaluate → promote-if-SUPPORTED`. Before waiting on unrelated pending checks, it previews the frozen mechanism contract: a decisive criterion/protection failure is recorded immediately as `REFUTED`; only a still-supportable candidate waits for unresolved safety/check observations. The POST intent is persisted before WQ Lab submission, and a confirmed Location is persisted before polling. Re-running a POSTED candidate resumes by Location and never sends a second POST.

The executor also closes a legacy already-POSTED hypothesis as `INCONCLUSIVE` when its frozen observation type cannot exist in the Incumbent snapshot schema; it preserves the real Result evidence and never rewrites the frozen contract after seeing outcome data.

## Deterministic bootstrap

Normal Root intake is a single command:

```text
python3 scripts/bootstrap_run.py --alpha-id <ID>
```

It performs local WQ Lab capability preflight, starts or resumes the canonical nonterminal run for the Root, executes WQ Lab intake in memory, initializes the Guard, and updates the live Dashboard. Normal execution persists exactly one Markdown file; the compressed machine state is embedded inside that file for safe resume. Raw/derived intake projections are not archived separately. The controller should not manually reorder these steps.

## WQ Lab provider

`wq_lab_provider.py` is the lower-level Skill-side bridge to the user's local `wq_lib`. It does not contain BRAIN HTTP implementations and does not vendor WQ Lab. Its CLI remains available for debugging/recovery; normal execution goes through `bootstrap_run.py`.

`recordset_dashboard.py` deterministically maps raw BRAIN recordsets to chart specs; `run_dashboard.py` renders those specs. Rendering/MD code remains in this Skill, never in WQ Lab.

The local WQ Lab must expose the three additive generic reads listed in `../references/runtime/wq-lab-provider.md`. No silent CNHKMCP fallback is used.

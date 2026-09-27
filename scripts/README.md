# Runtime scripts

`optimizer_guard.py` 是 stdlib-only 的确定性 FE guard/state helper。它只执行本地可验证的机器约束，不判断经济 thesis 是否正确。

工作流和 contract 以 `../references/runtime/` 下的 owner 文件为准；本 README 只说明脚本边界。

CLI：

```text
python3 scripts/optimizer_guard.py --help
```

`update-dashboard` enriches the canonical MD header with field metadata and visualization diagnostics. Expression/settings/results/checks are rendered directly from current guard state. Chart payloads are reduced to compact deterministic snapshots and rendered inline in the Markdown log; no separate chart assets are written.

Planning transitions are intentionally small: `set-plan`, `activate-route`,
`close-route`, `exhaust-focus`, `refresh-incumbent`, and `finish-run`.
`set-plan --final-replan` is accepted only after all routes in the current plan
are terminal and can be used once per Incumbent cycle. Root or a legitimate STALE re-profile may install an empty EXHAUSTED plan only after the v2 synthesis contract provides a complete auditable no-action proof; a missing or merely historical method review cannot create an empty plan. `refresh-incumbent` updates the current authenticated Result/check snapshot and stales an existing plan when facts change.

`withdraw-hypothesis` is the narrow pre-reservation correction path: it only works while an OPEN hypothesis has no candidate fingerprint and no candidate/simulation record. Use it when deterministic preflight finds a contract omission before reserve/POST. It records the old hypothesis as WITHDRAWN and requires a new hypothesis ID. It is deliberately blocked after reserve, including after RELEASED.

`finish-run --status COMPLETED_WITH_EXHAUSTION` requires the final re-plan
gate and an EXHAUSTED plan. `SUBMISSION_READY` is machine-gated by the current
Incumbent check snapshot. `USER_STOP`, `SCOPE_BOUNDARY`, and
`PLATFORM_UNRECOVERABLE` are explicit terminal freeze states.

Guard 不能独立验证 live BRAIN operator signature、dataset semantics、经济因果或远端 source authenticity；这些必须来自当前认证平台 evidence 与 Primary defect reference。


State mutation is single-writer. Concurrent/stale state snapshots are rejected with `STATE_WRITE_CONFLICT`; re-read the state and retry serially. This prevents evidence loss from overlapping Guard commands.


## Evidence + method synthesis

After mandatory intake evidence is registered, use:

```text
python3 scripts/mechanism_synthesis.py --state <STATE_PATH> --root-alpha-id <ROOT_ALPHA_ID>
```

The script creates a deterministic blocker/enhancement-method-family/evidence scaffold. For blocker-free work, pass `--enhancement <TARGET> <OWNER>` (repeatable). It does not choose economic causes or operators. The controller fills mechanism assessments, and `optimizer_guard.py set-plan` enforces the v2 synthesis contract. Normal routes need only the assessments that justify those routes; full catalog coverage is required when claiming an empty plan/exhaustion, including enhancement targets already entered in the current Incumbent cycle.

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

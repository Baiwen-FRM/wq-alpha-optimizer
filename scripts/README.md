# Runtime scripts

`optimizer_guard.py` 是 stdlib-only 的确定性 FE guard/state helper。它只执行本地可验证的机器约束，不判断经济 thesis 是否正确。

工作流和 contract 以 `../references/runtime/` 下的 owner 文件为准；本 README 只说明脚本边界。

CLI：

```text
python3 scripts/optimizer_guard.py --help
```

`update-dashboard` enriches the canonical MD header with field metadata and visualization diagnostics. Expression/settings/results/checks are rendered directly from current guard state. Optional chart payloads are written as stdlib-only SVG files under `logs/assets/` and referenced relatively from the run MD; no plotting dependency is required.

Planning transitions are intentionally small: `set-plan`, `activate-route`,
`close-route`, `exhaust-focus`, `refresh-incumbent`, and `finish-run`.
`set-plan --final-replan` is accepted only after all routes in the current plan
are terminal and can be used once per Incumbent cycle. Root or a legitimate
STALE re-profile may install an empty EXHAUSTED plan rather than fabricating a
route. `refresh-incumbent` updates the current authenticated Result/check
snapshot and stales an existing plan when facts change.

`finish-run --status COMPLETED_WITH_EXHAUSTION` requires the final re-plan
gate and an EXHAUSTED plan. `SUBMISSION_READY` is machine-gated by the current
Incumbent check snapshot. `USER_STOP`, `SCOPE_BOUNDARY`, and
`PLATFORM_UNRECOVERABLE` are explicit terminal freeze states.

Guard 不能独立验证 live BRAIN operator signature、dataset semantics、经济因果或远端 source authenticity；这些必须来自当前认证平台 evidence 与 Primary defect reference。


State mutation is single-writer. Concurrent/stale state snapshots are rejected with `STATE_WRITE_CONFLICT`; re-read the state and retry serially. This prevents evidence loss from overlapping Guard commands.

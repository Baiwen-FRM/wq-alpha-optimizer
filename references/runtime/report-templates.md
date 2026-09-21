# Optimization Report Template

本文件只定义可读报告结构；run-log 生命周期与 machine state 分别按 `alpha-intake.md` 和 `candidate-contract.md` 执行，本文件不再定义它们。

## ROOT

```text
Root Alpha: {id}
Root Baseline: immutable
Incumbent: {id; initially root}
Status: {status; PENDING is unknown}
Expression/code fingerprint: {...}
Settings fingerprint: {...}
Result/checks: {value / limit / status / source / observed_at}
```

## DIAGNOSE

```text
Idea / expression map: {...}
Fields actually used: {...}
Evidence registered: {E1, E2, ...; source / observed_at / claim}
Deep diagnostics / visualization used: {why / none}
Unknowns: {...}
```

## FOCUS

```text
Type: {DEFECT / ENHANCEMENT}
Current FAIL blockers: {...}
Bound blocker: {one current FAIL / none for ENHANCEMENT}
Primary owner / target: {...}
Why this is upstream or a justified enhancement opportunity: {...}
Evidence refs: {...}
Secondary mechanisms deferred: {...}
```

## PLAN

```text
Profile summary: {facts / unknowns used for planning}
Plan revision: {revision}; Incumbent={id}; based on evidence revision={n}; final re-plan used={true/false}
Routes (ordered): {priority / id / target / mechanism / owner / status / evidence refs / rationale}
Route history: {exhausted / dismissed / reopened with new observation, if any}
```

## HYPOTHESIS / CANDIDATE

```text
Hypothesis ID: {Hn}
Parent Incumbent: {id}
Route mechanism: {must match active route/focus}
Mechanism hypothesis: {one falsifiable question inside that route mechanism}
Mutation: {expression OR one setting key}
Success criteria: {machine-readable criteria}
Protected metrics: {rule / tolerance}
Failure meaning: {...}
Evidence refs: {...}
Payload fingerprint: {...}
vs Root drift note: {...}
```

| Candidate | Diff | Raw post-sim evidence | vs Incumbent | vs Root | Machine status | Decision |
|---|---|---|---|---|---|---|
| {id} | {...} | {source / observed_at / metrics / checks; new blockers / new unresolved checks} | {...} | {...} | SUPPORTED / REFUTED / INCONCLUSIVE | promote / reject / resolve-check / stop |

Iteration conclusion: `{what was learned; what question remains open}`

## Final report

```text
# Optimization Complete
End reason: {SUCCESS / SUBMISSION_READY / COMPLETED_WITH_EXHAUSTION / USER_STOP / SCOPE_BOUNDARY / PLATFORM_UNRECOVERABLE}

Root Alpha: {id}; key metrics={...}
Research Best / Incumbent: {id / root}; improvement={...}
Submission Ready: {YES / NO / unknown}
Remaining blockers: {...}
Remaining unknowns: {...}
Exhausted focus/families: {...}
Current-result refreshes: {source / observed_at / readiness effect}
Plan revisions / final re-plan: {...}
```

没有候选改善 Root 时明确写 `未优化成功`；Evidence Exhausted / No Justified Enhancement 都是合法结束状态。


### Submission Ready reporting

只有 guard 的 `submission_readiness.ready=true` 才写 `Submission Ready: YES`。若仍有 FAIL/policy-blocking check、未分类 WARNING、PENDING/UNKNOWN、缺失/未认证/不可审计 snapshot，则写 `NO` 或 `unknown` 并列出 reason；普通 `SUCCESS` 不自动升级为 Submission Ready。

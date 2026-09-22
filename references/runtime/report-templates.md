# Optimization Report Template

本文件只定义可读报告结构；run-log 生命周期与 machine state 分别按 `alpha-intake.md` 和 `candidate-contract.md` 执行，本文件不再定义它们。

## MD 首页 Dashboard

每个 canonical run MD 的最前面固定渲染一个由当前 machine state + dashboard metadata 生成的首页。Audit Trail 仍保持 append-only；Dashboard 可以随着 Incumbent、Result、field metadata、visualization evidence 更新而重绘。

固定顺序：

1. **Expression + Settings**
   - 当前 Incumbent expression；
   - 完整 settings 表。
2. **Result**
   - Root 与 Current Incumbent 的关键 metrics；若尚未 promotion，则显示单列 current value；
   - 当前完整 checks 表。
3. **Field Information**
   - actual field name / type / dataset / coverage / dateCoverage / exact description。
4. **Visualization / Diagnostics**
   - diagnostic Alpha ID / control 说明；
   - 实际取得的 recordset 名称；
   - 关键摘要；
   - 有可审计数值序列时生成轻量 SVG：ordered time/PnL 用 line，bucket/cap/sector/industry 对比用 bar；不补点、不平滑、不猜缺失值。
5. **Optimization Progression**
   - 已有 result 的 hypothesis / candidate Alpha / mechanism / status / Sharpe/Fitness/Returns/Margin/Turnover / new blockers。

Dashboard 更新使用：

```text
python3 scripts/optimizer_guard.py update-dashboard --dashboard <json> --state <state.json> --root-alpha-id <ID>
```

最小 metadata 示例：

```json
{
  "fields": [
    {
      "name": "mdl242_1mt",
      "type": "MATRIX",
      "dataset": "model242",
      "coverage": 1.0,
      "dateCoverage": 1.0,
      "description": "Overall TM1 tactical composite alpha score for the D1 horizon"
    }
  ],
  "visualization": {
    "alpha_id": "wpZnAnQ5",
    "control": "same expression/settings; visualization=true",
    "recordsets": ["pnl", "sharpe-by-capitalization"],
    "summary": ["Capitalization Sharpe shows a strong gradient."],
    "charts": [
      {
        "id": "cap-sharpe",
        "title": "Sharpe by capitalization bucket",
        "type": "bar",
        "labels": ["0-20", "20-40", "40-60", "60-80", "80-100"],
        "values": [1.28, 1.45, 0.35, 0.78, -0.22]
      }
    ]
  }
}
```

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
Diagnostic escalation considered: {needed / reused historical evidence / attempted and unavailable / not needed}
Historical evidence reused: {run id / Root identity match / candidate families / why still applicable}
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
Why this candidate is preferred over diagnostic escalation or other mechanism families: {...}
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
Diagnostics completed before exhaustion: {...}
Diagnostics still unavailable: {...}
Current-result refreshes: {source / observed_at / readiness effect}
Plan revisions / final re-plan: {...}
```

没有候选改善 Root 时明确写 `未优化成功`；Evidence Exhausted / No Justified Enhancement 都是合法结束状态。


### Submission Ready reporting

只有 guard 的 `submission_readiness.ready=true` 才写 `Submission Ready: YES`。若仍有 FAIL/policy-blocking check、未分类 WARNING、PENDING/UNKNOWN、缺失/未认证/不可审计 snapshot，则写 `NO` 或 `unknown` 并列出 reason；普通 `SUCCESS` 不自动升级为 Submission Ready。

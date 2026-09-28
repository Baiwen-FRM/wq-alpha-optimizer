# Optimization Report Template

本文件只定义可读报告结构；run-log 生命周期与 machine state 分别按 `alpha-intake.md` 和 `candidate-contract.md` 执行，本文件不再定义它们。

## MD 首页 Dashboard

每个 canonical run MD 的最前面固定渲染一个由当前 machine state + dashboard metadata 生成的首页。`Machine Decision Trail` 也由 machine state 确定性重绘；只有 `Append-only Notes` 是人工追加区。Dashboard 可以随着 Incumbent、Result、field metadata、visualization evidence 更新而重绘。

固定顺序：

1. **Expression + Settings**
   - 当前 Incumbent expression；
   - 完整 settings 表。
2. **Result**
   - Root 与 Current Incumbent 的关键 metrics；若尚未 promotion，则显示单列 current value；
   - 当前完整 checks 表。
3. **Field Information**
   - actual field name / type / dataset / coverage / dateCoverage / exact description；registry 可保存 Root 与后续已授权 field 的 metadata，但这里只投影当前 Incumbent 实际使用的 fields。
4. **Visualization / Diagnostics**
   - diagnostic Alpha ID / control 说明；
   - 实际取得的 recordset 名称；
   - 关键摘要；
   - 有可审计数值序列时生成真正的 SVG 图表。chart type 以 schema 为准而不是 recordset 名称：只要存在 date/day/year/time/timestamp 轴，就用 line/multi-line；只有没有时间轴的静态 category/bucket/cap/sector/industry comparison 才用 bar。numeric lower/upper bucket bounds 组合成一个 bucket label，不作为独立 series。不补点、不平滑、不猜缺失值。listing 中已经出现但经过一次额外有界 fetch 仍拿不到的 recordset，必须在 MD 明列 unavailable；已经 fetch 但没有安全 renderer 的明列 raw/table-only。一个 run 的所有可绘制 chart 合并到同一个 `<run>_dashboard.svg` 中，MD 只引用这个 companion SVG；不得用 Unicode sparkline 替代主图，也不得恢复每-chart asset 文件。
5. **Optimization Progression**
   - 已有 result 的 hypothesis / candidate Alpha / mechanism / status / Sharpe/Fitness/Returns/Margin/Turnover / new blockers。
6. **Audit Trail / Machine Decision Trail**
   - 对每个 H1–Hn 自动展开 Parent、route/mechanism、frozen principal hypothesis、mutation、success criteria、protected metrics、candidate fingerprint/expression/fields、preflight drift、真实 Result source+observed_at+metrics、machine evaluation、promotion/disposition 与 learned evidence claim；
   - 不复制 hidden state 全量 JSON，不要求 controller 人工维护同一事实的第二份日志。

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
Selected Submission Candidate: {id / none}; Root-relative comparison={...}
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

只有 Guard 已完成 final candidate selection，且 selected candidate 的 archived readiness=true、Root protection eligible=true 时才写 `Submission Ready: YES`。若存在多个 eligible ready candidates 但尚未 selection、仍有 FAIL/policy-blocking check、未分类 WARNING、PENDING/UNKNOWN、Root protection failure、缺失/未认证/不可审计 snapshot，则写 `NO` 或 `unknown` 并列出 reason；普通 `SUCCESS` 不自动升级为 Submission Ready。

# Candidate / Evidence Contract

本文件是 FE optimizer 的唯一 machine contract。它约束可验证状态与证据绑定；经济机制是否值得提出仍由 controller + Primary reference 决定。

## 1. Root / Incumbent

- `root_baseline` immutable；保存 root expression / fields / full settings / language，并尽量保存当前 Result/check snapshot。
- `incumbent` 是当前正式 promotion 的 parent；candidate 的 `parent_id` 必须等于它。
- locked scope：`region / delay / universe / instrumentType` 不得由普通 candidate 修改。
- Root 已用 fields 自动允许；新 field 只能用已注册的 `FIELD_SCOPE` evidence 单独加入 allowlist。
- legacy schema-4 run 可读取历史状态、完成已有在途 transport/result closure，但**不能开启新的 focus/hypothesis**；首次成功 `set-plan` 后升级为 v1 planning contract，不改写历史事实。

### 1A. Current Incumbent Result/check refresh

Root 初始化和每次 promotion 都保存一个 Incumbent `result_evidence` snapshot。平台后续返回更新的当前 Result/checks 时，使用：

```text
refresh-incumbent --result <json>
```

refresh 必须绑定当前 Incumbent Alpha ID，要求 authenticated + response_complete + auditable source + timezone timestamp，且不能早于当前 snapshot。refresh 只在没有 OPEN focus/hypothesis 时执行；若内容更新，当前 `ACTIVE/EXHAUSTED` plan 标记 `STALE`，随后重新 Profile/Plan。用于新 plan 的诊断事实仍须注册普通 evidence refs；refresh snapshot 本身不是 route rationale 的替代品。

## 2. Evidence registry

先注册可审计 evidence，再用 evidence ref 驱动 focus / hypothesis / field allowlist。

```json
{
  "id": "E1",
  "kind": "DIAGNOSTIC",
  "subject": "HIGH_TURNOVER",
  "source": "BRAIN:get_submission_check",
  "observed_at": "2026-09-20T12:00:00Z",
  "claim": "Turnover fails while Sharpe/Fitness remain otherwise stable."
}
```

`source` 必须是可追溯的 namespace/action；`observed_at` 必须带 timezone。Evidence registry 的作用是留下 provenance，不代表 guard 能独立证明经济解释为真。

Guard 会按 `kind / subject / source / claim` 保存一个 informational content fingerprint，故意排除 evidence ID、revision 和 `observed_at`。换一个 ID 或只换时间戳的 exact informational duplicate 可以保留审计记录，但不能作为 exhausted route 的新 observation。fingerprint 只能拦截 exact normalized content；语义改写、同义 paraphrase 等“实质是否新颖”仍必须由 controller 判断，guard 不宣称能自动识别。

新 field 必须使用：

```json
{
  "id": "E_FIELD_1",
  "kind": "FIELD_SCOPE",
  "subject": "field_b",
  "source": "BRAIN:get_data_fields",
  "observed_at": "...Z",
  "claim": "field_b is verified in the same existing dataset/scope as the incumbent source."
}
```

## 3. Optimization plan

Profile/Plan 位于 DIAGNOSE 与 FOCUS 之间。它只承载 controller 根据已注册 evidence 形成的执行顺序；guard 不判断 route 的经济正确性。

```json
{
  "revision": 1,
  "based_on_evidence_revision": 12,
  "final_replan_used": false,
  "status": "ACTIVE",
  "routes": [
    {
      "id": "R1",
      "target": "LOW_SUB_UNIVERSE_SHARPE",
      "owner": "optimization/subuniverse.md",
      "mechanism": "breadth_robustness",
      "evidence_refs": ["E1"],
      "rationale": "Current blocker and exposure evidence support this mechanism.",
      "status": "ACTIVE"
    }
  ]
}
```

每条 route 必须引用已注册 evidence，并提供 mechanism-level rationale；只因为 operator catalog 存在某个 operator 不能建 route。route 数组顺序是 ordered execution priority，guard 固化为 `priority=1..N`。一次最多一个 `ACTIVE` route，active focus 必须绑定该 route。`PENDING` route 不是 candidate，也不触发其 Primary reference 的加载。

每条 `route.evidence_refs` 与 `route.new_observation_refs` 都必须在 `based_on_evidence_revision` 当时已经存在；否则 plan snapshot 自相矛盾，guard 拒绝。`EXHAUSTED` route 不能因为重复读取同一事实自动复活。若新 plan 要重开同一 Incumbent cycle 内的同一 `target/owner/mechanism`，必须提供 `reopen_reason` 和 exhaustion 之后、且 fingerprint 实质新颖的 `new_observation_refs`；仅换 evidence ID 或 timestamp 不够。Promotion 后的新 Incumbent 不继承前任的 route exhaustion；它可以基于自己的 fresh profile 重新使用同一个 mechanism。

Promotion 或 current-result refresh 会把旧 plan 标记 `STALE`。Root 第一次 Profile、promotion 后的新 Incumbent、以及同一 Incumbent 的合法 STALE re-profile，都允许得到空 fresh plan（状态为 `EXHAUSTED`）；不得为了满足非空 plan 约束而虚构 route。新 Incumbent 会重置 `final_replan_used=false`；同一 Incumbent refresh 不重置该 cycle 已消耗的 final re-plan。

当前 plan 的 routes 全部 terminal 后，controller 只能执行一次 `final-replan`；同一 Incumbent cycle 不得继承已消耗的 final re-plan，新 Incumbent 会开启新的 cycle。没有 OPEN hypothesis、OPEN focus、ACTIVE/PENDING route 且 final re-plan 为空时，guard 才允许 `COMPLETED_WITH_EXHAUSTION`；`SUCCESS/SUBMISSION_READY` 在没有 OPEN hypothesis/focus 时可以结束已因 promotion 变成 `STALE` 的旧 plan。

`run.status` 进入 `SUCCESS`、`SUBMISSION_READY`、`COMPLETED_WITH_EXHAUSTION`、`USER_STOP`、`SCOPE_BOUNDARY` 或 `PLATFORM_UNRECOVERABLE` 后是 terminal boundary；所有 research-state mutation 都拒绝并返回 `RUN_ALREADY_TERMINAL`。`append_log` 只追加最终人工说明，不改变研究状态，因此仍可使用。

其中 `USER_STOP / SCOPE_BOUNDARY / PLATFORM_UNRECOVERABLE` 是显式冻结出口，可以保留当时仍 OPEN 的研究对象作为停止证据；其它正常完成状态要求没有 OPEN focus/hypothesis。`COMPLETED_WITH_EXHAUSTION` 还要求当前 plan 为 `EXHAUSTED` 且该 Incumbent cycle 的 final re-plan 已使用。`SUBMISSION_READY` 额外要求当前 Incumbent snapshot 的 authenticated/complete/auditable checks 无 blocking 或 unresolved 项。

## 4. Focus

一次只允许一个 open focus：

- `DEFECT`：必须绑定一个当前 `FAIL` blocker，再指定其上游 mechanism owner；没有 FAIL blocker 时 guard 不允许伪造 DEFECT；
- `ENHANCEMENT`：仅在当前 Incumbent 没有 FAIL blocker、用户明确要求继续提升、且有 evidence-supported opportunity 时使用。

`Evidence Exhausted` 会关闭当前 focus。重新开启同一 exhausted family 时，新的 focus 必须实际引用一条**在 exhaustion 之后注册**的新 evidence；仅注册无关 evidence 或继续引用旧 evidence 都不够。

在 v1 planning contract 中，hypothesis 的 `target` 和 `mechanism` 都必须与当前 active focus/route 一致；不能绑定到一个 route 后跳去测试另一个 blocker，也不能在同一 target 下偷偷切换到另一个 mechanism family。

## 5. Frozen hypothesis contract

Simulation 前先冻结。同一 focus 同时只允许一个 `OPEN` hypothesis；先得到结果，再开下一个问题，避免并行 candidate wave 变成 winner selection：

```json
{
  "target": "TURNOVER",
  "mechanism": "persistence_mismatch",
  "principal_hypothesis": "Excess turnover is caused by update-frequency/persistence mismatch.",
  "mutation": {"type": "setting", "key": "decay"},
  "success_criteria": [
    {"type": "metric", "name": "TURNOVER", "direction": "lower", "min_change": 0.0}
  ],
  "protected_metrics": [
    {"name": "SHARPE", "rule": "not_lower", "tolerance": 0.0},
    {"name": "FITNESS", "rule": "not_lower", "tolerance": 0.0}
  ],
  "failure_meaning": "If turnover does not fall without protected-metric damage, weaken this persistence mechanism.",
  "evidence_refs": ["E1"]
}
```

Success criterion 允许：

- metric：`higher / lower`；
- check：success criterion 只允许要求 current check 达到 `PASS`；不能把继续 FAIL 预声明成“成功”。

metric success criterion 的 `min_change` 与 protected metric 的 `tolerance` 都必须在 simulation 前声明；不能看完结果后补。需要 field change 或 complexity growth 时，理由也必须在 hypothesis contract 中预声明。

## 6. Candidate JSON

Candidate 只引用 frozen hypothesis，不再重复 hypothesis 文本：

```json
{
  "parent_id": "CURRENT_INCUMBENT_ID",
  "hypothesis_id": "H1",
  "expression": "...",
  "fields": ["field_a"],
  "settings": {"...": "FULL INCUMBENT SETTINGS"},
  "language": "FASTEXPR"
}
```

规则：

- expression hypothesis：settings 与 Incumbent 完全一致；
- setting hypothesis：expression 与 Incumbent 一致，full settings 只能改变声明的一个 key；
- settings 必须完整 snapshot；`testPeriod` 拒绝；
- candidate fields 必须与 expression 实际 identifiers 一致并在 allowlist；
- 一个 hypothesis ID 第一次 reserve 时永久绑定一个 payload fingerprint，`RELEASED` 也不解除绑定。

## 7. Transport

```text
NEW/RELEASED/HTTP_429 --reserve--> RESERVED
RESERVED → POSTED
RESERVED → HTTP_429 --bounded retry--> RESERVED
RESERVED → AMBIGUOUS_POST → POSTED(recovered existing simulation only)
RESERVED --release(no POST confirmed)--> RELEASED --same fingerprint only--> RESERVED
POSTED → terminal
```

非法 state transition 必须拒绝。`POSTED` 不能重新打开；`AMBIGUOUS_POST` 不能转 429 再 reserve。

## 8. Result evidence / promotion

Simulation 后提供 raw evidence；result classification/freshness 由 guard 从 evidence 计算，不接受调用者自报结论：

```json
{
  "alpha_id": "RETURNED_ALPHA_ID",
  "simulation_id": "SIM_ID",
  "observed_at": "...Z",
  "source": "BRAIN:get_submission_check",
  "response_complete": true,
  "authenticated": true,
  "metrics": {"SHARPE": 1.3, "FITNESS": 1.1, "TURNOVER": 0.35},
  "checks": [
    {"name": "LOW_SHARPE", "status": "PASS"},
    {"name": "HIGH_TURNOVER", "status": "PASS"}
  ]
}
```

Guard 必须验证：

- `simulation_id` 与已 POSTED request 一致；
- result evidence 时间不早于 POST；
- response complete + authenticated；
- success criteria 是否成立；
- protected metrics 是否满足预声明 policy；
- candidate 是否引入新的 blocking check。`FAIL` 永远 blocking；若当前项目/平台把某个 WARNING 视为 blocking，可在 raw check row 中显式 `policy_blocking:true`。

`SUBMISSION_READY` 的要求更严格：当前 Incumbent 的 check snapshot 必须非空、authenticated、response_complete、source/timestamp 可审计；`FAIL` 或 `policy_blocking:true` 会阻止 readiness；`PENDING/UNKNOWN` 等非终态也是 unresolved；WARNING 若要作为 non-blocking 接受，必须由 controller 基于当前平台/项目规则显式给出 `policy_classified:true, policy_blocking:false`。普通 `SUCCESS` 只表示 controller 判定用户目标已达到，不自动声称可提交。

只有 guard 计算为 `SUPPORTED` 的 result 才能 promotion。`REFUTED / INCONCLUSIVE` 不能靠调用者改布尔值绕过。

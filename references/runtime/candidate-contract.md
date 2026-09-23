# Candidate / Evidence Contract

本文件是 FE optimizer 的唯一 machine contract。它约束可验证状态与证据绑定；经济机制是否值得提出仍由 controller + Primary reference 决定。

## 1. Root / Incumbent

- `root_baseline` immutable；保存 root expression / fields / full settings / language，并尽量保存当前 Result/check snapshot。
- `incumbent` 是当前正式 promotion 的 parent；candidate 的 `parent_id` 必须等于它。
- locked scope：`region / delay / universe / instrumentType` 不得由普通 candidate 修改。
- Root 已用 fields 自动允许；新 field 只能用已注册的 `FIELD_SCOPE` evidence 单独加入 allowlist。
- legacy schema-4 run 可读取历史状态、完成已有在途 transport/result closure，但**不能开启新的 focus/hypothesis**；首次成功 `set-plan` 后升级为兼容的 v1 route-binding contract，不改写历史事实。新初始化 run 使用 v2 planning contract：在 route 之前增加 evidence+method synthesis gate。

### 1A. Current Incumbent Result/check refresh

Root 初始化和每次 promotion 都保存一个 Incumbent `result_evidence` snapshot。平台后续返回更新的当前 Result/checks 时，使用：

```text
refresh-incumbent --result <json>
```

refresh 必须绑定当前 Incumbent Alpha ID，要求 authenticated + response_complete + auditable source + timezone timestamp，且不能早于当前 snapshot。refresh 只在没有 OPEN focus/hypothesis 时执行。若只是相同 metrics/check facts 的新时间戳/来源，更新 snapshot freshness 但**不**把 plan 标记 STALE；只有 normalized Result/check facts 实质变化时，当前 `ACTIVE/EXHAUSTED` plan 才标记 `STALE` 并重新 Profile/Plan。用于新 plan 的诊断事实仍须注册普通 evidence refs；refresh snapshot 本身不是 route rationale 的替代品。

### 1B. State write concurrency

Guard state is a single-writer research ledger. Every state snapshot carries an internal revision. Concurrent/stale writers are rejected with `STATE_WRITE_CONFLICT`; controller must re-read the latest state and retry the intended transition serially. Atomic file replacement alone is not enough because it can still lose a newer evidence/decision update.

Do not run two mutating Guard commands in parallel against the same `state_path`. Read-only platform queries may still run concurrently if their results are registered serially.

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

## 3. Evidence synthesis + optimization plan

Profile/Plan 位于 DIAGNOSE 与 FOCUS 之间。Guard 不判断经济 thesis 的真伪，但会验证：当前 blocker 是否经过合法 method-family synthesis、route 是否来自一个可测试 assessment、空 plan 是否真的完成了 no-action proof。经济判断仍由 controller + Primary reference 负责。

新 run 的 planning contract 是 v2。Plan 先包含 `synthesis`，再包含执行 routes。最小示意：

```json
{
  "based_on_evidence_revision": 12,
  "synthesis": {
    "blockers": [
      {
        "name": "LOW_SUB_UNIVERSE_SHARPE",
        "target": "LOW_SUB_UNIVERSE_SHARPE",
        "owner": "optimization/subuniverse.md",
        "observation_refs": ["E_SUB", "E_CAP"],
        "mechanisms": [
          {
            "id": "A_SIZE",
            "mechanism": "size_breadth_exposure",
            "method_family": "exposure_control_or_grouping",
            "status": "PLAUSIBLE_PROBE",
            "evidence_refs": ["E_SUB", "E_CAP"],
            "reasoning": "Cap-conditioned Sharpe and the active blocker justify a bounded size/breadth test, but do not prove the exact repair.",
            "next_question": "Does one thesis-preserving exposure intervention improve sub-universe robustness?"
          }
        ]
      }
    ]
  },
  "routes": [
    {
      "id": "R1",
      "target": "LOW_SUB_UNIVERSE_SHARPE",
      "owner": "optimization/subuniverse.md",
      "mechanism": "size_breadth_exposure",
      "evidence_refs": ["E_SUB", "E_CAP"],
      "assessment_refs": ["A_SIZE"],
      "rationale": "Test the mechanism indicated by current cap-conditioned performance."
    }
  ]
}
```

Assessment status 只允许：

- `ACTIONABLE`：当前 evidence 已支持一个明确的机制问题，可直接进入最小实验；
- `PLAUSIBLE_PROBE`：真实原因仍未知，但 evidence + owner method family 足以支持一个有区分力的有限实验；
- `NEEDS_DIAGNOSTIC`：当前事实不能区分机制，且存在具体 in-scope discriminator；
- `EXCLUDED`：有当前、可审计的机制级证据足以排除。历史“以前试过”或 generic blocker fact 不能单独充当 exclusion。

每个 assessment 必须使用该 blocker catalog 中允许的 `method_family`，并引用 plan snapshot 当时已注册的 evidence。描述性 `mechanism` 可以比 catalog id 更具体，但不能脱离 owner 允许的方法族。

正常有 route 的 plan **不要求把整个方法库逐项审批**。只要被选 route 有合法 `ACTIONABLE / PLAUSIBLE_PROBE` assessment 即可继续实验。route 必须：

- 引用至少一个 `assessment_ref`；
- target / owner / mechanism 与 assessment 一致；
- `route.evidence_refs` 不得丢掉 assessment 实际使用的 evidence；
- route 数组顺序就是执行 priority，一次最多一个 `ACTIVE`，其余为 `PENDING`。

一个上游 mechanism 可以通过 `explains_blockers` 同时解释多个 blocker，但 synthesis 中每个被声明 blocker 都必须存在兼容 assessment；不能从“同时 FAIL”直接推断共因。

### Empty-plan / exhaustion gate

`routes=[]` 是强结论，不是普通 planning shortcut。当前仍有 FAIL blocker 时，空 plan 必须满足：

1. synthesis 覆盖每个当前 blocker；
2. 对每个 blocker，catalog 当前列出的全部 method families 都已评估；
3. 不得剩余 `ACTIONABLE / PLAUSIBLE_PROBE`；
4. 不得剩余 `NEEDS_DIAGNOSTIC`；
5. 所有 `EXCLUDED` 都有合法 exclusion basis 与对应 evidence。

否则 Guard 分别拒绝为：

- `EMPTY_PLAN_HAS_TESTABLE_MECHANISM`
- `EMPTY_PLAN_DIAGNOSTIC_REQUIRED`
- `EMPTY_PLAN_METHOD_SPACE_UNASSESSED`
- 或 `SYNTHESIS_CONTRACT`

因此 Root first profile、STALE re-profile、promotion 后 new Incumbent、以及 `final-replan` 都不能再仅凭“历史上试过很多方法”安装空 plan。空 plan 只有通过同一 no-action gate 才能成为 `EXHAUSTED`。

每条 `route.evidence_refs` 与 `route.new_observation_refs` 都必须在 `based_on_evidence_revision` 当时已经存在；否则 snapshot 自相矛盾。若新 plan 要重开同一 Incumbent cycle 内相同 `target/owner/mechanism`，仍必须提供 `reopen_reason` 和 exhaustion 之后 fingerprint 实质新颖的 `new_observation_refs`。Promotion 后的新 Incumbent 不继承前任 route exhaustion。

Promotion 或 material current-result refresh 会使旧 plan `STALE`。新 Incumbent 重置 `final_replan_used=false`；同一 Incumbent refresh 不重置已消耗的 final re-plan。当前 routes 全部 terminal 后只能执行一次 `final-replan`，而 final empty plan 仍必须重新通过上述 synthesis/no-action gate。

### Route closure evidence gate

Route 被计划成 `ACTIVE` 就意味着 controller 当时判断它是 actionable。为了防止“刚建 route 就用同一批旧事实把它判死”，guard 记录 `activated_at_evidence_revision`，并把 hypothesis/candidate 绑定到 `route_id`。

ACTIVE route 的正常 terminal transition 需要满足至少一个条件：

- 该 route 已产生至少一个 **evaluated candidate Result**；或
- 没有 candidate Result，但 controller 提供一个显式 `evidence_ref`，该 evidence 的 revision 必须晚于 route activation，而且 informational fingerprint 在 activation 之前不存在。

第二种是 diagnostic invalidation 例外，不是“跳过 candidate”的常规捷径。它用于 route 激活后出现的新 cap/sector/industry/coverage/schema/平台事实真正让原问题失去 actionability。planning 时已经存在的 blocker、历史实验摘要、旧 recordset、重复 ID、只换 timestamp 的 evidence 都不满足。

`close-route` 与 `exhaust-focus` 都执行这个 gate；`COMPLETED_WITH_EXHAUSTION` 还会重新审计当前 Incumbent cycle 的 terminal route history，防止旧状态或绕路留下零-work route 后直接 final-replan 结束。

`run.status` 进入 `SUCCESS`、`SUBMISSION_READY`、`COMPLETED_WITH_EXHAUSTION`、`USER_STOP`、`SCOPE_BOUNDARY` 或 `PLATFORM_UNRECOVERABLE` 后是 terminal boundary；所有 research-state mutation 都拒绝并返回 `RUN_ALREADY_TERMINAL`。`append_log` 只追加最终人工说明，不改变研究状态，因此仍可使用。

其中 `USER_STOP / SCOPE_BOUNDARY / PLATFORM_UNRECOVERABLE` 是显式冻结出口，可以保留当时仍 OPEN 的研究对象作为停止证据；其它正常完成状态要求没有 OPEN focus/hypothesis。`COMPLETED_WITH_EXHAUSTION` 还要求当前 plan 为 `EXHAUSTED` 且该 Incumbent cycle 的 final re-plan 已使用。`SUBMISSION_READY` 额外要求当前 Incumbent snapshot 的 authenticated/complete/auditable checks 无 blocking 或 unresolved 项。

## 4. Focus

一次只允许一个 open focus：

- `DEFECT`：必须绑定一个当前 `FAIL` blocker，再指定其上游 mechanism owner；没有 FAIL blocker 时 guard 不允许伪造 DEFECT；
- `ENHANCEMENT`：仅在当前 Incumbent 没有 FAIL/policy-blocking/unresolved check、用户明确要求继续提升、且有 evidence-supported opportunity 时使用；未分类 WARNING、PENDING/UNKNOWN 或不完整 readiness evidence 必须先 resolve，不能当作 enhancement 许可。

`Evidence Exhausted` 会关闭当前 focus。exhausted family 由 `type + owner + target + mechanism` 定义；同 target/owner 但不同 mechanism 的 pending route 是不同 family，不应被前一个 focus 的 exhaustion 锁死。真正重开同一 exhausted route 时，新的 focus 必须实际引用该 route 的 `new_observation_refs` 中至少一条；仅注册无关/重复 evidence 或继续只引用旧 evidence 都不够。

在 v1/v2 route-binding contract 中，hypothesis 的 `target` 和 `mechanism` 都必须与当前 active focus/route 一致；不能绑定到一个 route 后跳去测试另一个 blocker，也不能在同一 target 下偷偷切换到另一个 mechanism family。

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

Success criterion 只有三种 observation type：

- `metric`：读取 Result `metrics` 中的数值，声明 `higher / lower + min_change`；
- `check`：读取 submission check 的 `status`，success criterion 只允许要求 `PASS`；
- `check_value`：读取指定 submission check row 的数值 `value`，声明 `higher / lower + min_change`。它用于诸如 sub-universe Sharpe 这类“平台把数值放在 check row，而不是普通 Result metrics”的方向性预测。

Guard 在 hypothesis freeze 时就验证 observation schema：`metric` 名称必须真实存在于当前 Incumbent metrics；`check` 名称必须存在于当前 Incumbent checks；`check_value` 必须存在同名 check 且其 `value` 为 numeric；protected metric 也必须真实存在。类型不匹配直接返回 `HYPOTHESIS_OBSERVATION_SCHEMA_MISMATCH`，不得 reserve/POST。这样不能把 check.value 冒充 metric，也不能等看完 Result 后再改 criterion 类型。

`metric/check_value` 的 `min_change` 与 protected metric 的 `tolerance` 都必须在 simulation 前声明；不能看完结果后补。需要 field change 或 complexity growth 时，理由也必须在 hypothesis contract 中预声明。

### Preflight correction before reservation

冻结 hypothesis 后、第一次 candidate reserve 前，preflight 仍可能发现合同本身不完整，例如 candidate 增加了 expression complexity，但 hypothesis 忘记声明 `complexity_reason`。这种错误不能要求伪造 transport failure，也不能手改 state。

若 hypothesis 仍为 `OPEN`，且：

- `candidate_fingerprint` 仍为 null；
- 没有任何 simulation/candidate record 绑定该 hypothesis；
- 当前 focus 仍 OPEN 且 revision 一致；

可以执行 `withdraw-hypothesis --reason ...`。Guard 将旧 hypothesis 记为 `WITHDRAWN / WITHDRAWN_BEFORE_RESERVATION`，保留审计记录；随后必须使用**新的 hypothesis ID**重新冻结修正后的 contract。

一旦 reserve 已发生，hypothesis 就已经绑定 payload fingerprint，即使 reservation 后来被 `RELEASED`，也不能使用 `withdraw-hypothesis` 修改合同。此时继续遵守 transport recovery / release / abandon 规则，避免 post-reservation contract rewriting。

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

正常路径由 `scripts/execute_reserved_candidate.py` 统一执行：

```text
NEW/RELEASED/HTTP_429 --reserve--> RESERVED
RESERVED --begin-submission--> SUBMITTING
SUBMITTING → POSTED(confirmed 201 + Location)
SUBMITTING → HTTP_429 --later reserve--> RESERVED
SUBMITTING → AMBIGUOUS_POST
SUBMITTING --explicit no-POST response--> RELEASED
AMBIGUOUS_POST → POSTED(reconciled existing Location only)
POSTED --Location resume only--> result / resumable polling
```

`SUBMITTING` 是 crash-safety fence：它必须在调用外部 POST 之前写入 state。若进程在 POST 周围崩溃，下一次 executor 看到 `SUBMITTING` 时不得自动 POST；只有拿到已存在 simulation 的 Location 才能用 `--recover-location` 绑定为 `POSTED`。这宁可产生 reconciliation requirement，也不能冒 duplicate POST 风险。

WQ Lab 已有 `_start_simulation` 只负责一次受控 submission 并立即返回 HTTP response/Location；Skill 不复制 BRAIN HTTP。201+Location 一旦返回，Guard 立即持久化 Location，然后后续全部通过 WQ Lab `simulate_single(..., location=...)` 续跑，因此 poll 异常、result/check 暂时不完整、controller 重启都不会重新提交。

Safe continuation 属于 executor，不属于 controller。一次正常 `execute_reserved_candidate.py` invocation 在内部有界处理 429、poll/result 暂不可得和暂时不完整的 current snapshot；controller 不再接收“`resumable=true` 后请再调用一次”的工作流责任。只有得到 evaluated Result/promotion、明确 posted/pre-post inconclusive，或达到 `recovery_required` reconciliation boundary 时才把控制权交回上层。整个过程中同 fingerprint 不重新 POST。

显式 pre-POST 4xx 且没有 Location 时可以 release，并用 `TRANSPORT_FAILURE` evidence 把 hypothesis 记为 pre-POST `INCONCLUSIVE`。POST 已确认后若 simulation terminal error/cancelled 且没有可用 Alpha result，则用 `SIMULATION_FAILURE` 关闭为 `POSTED_SIMULATION_FAILURE / INCONCLUSIVE`。若一个旧版本已 POST 的 frozen hypothesis 在新 contract 检查下发现 observation type 与 Incumbent snapshot schema 不可能匹配，则保存当前真实 Result snapshot，用 `RESULT_CONTRACT_FAILURE` 关闭为 `POSTED_RESULT_CONTRACT_FAILURE / INCONCLUSIVE`；不得事后改写 hypothesis，也不得把这类确定性 schema mismatch 无限当作 pending。

非法 state transition 必须拒绝。`POSTED` 不能重新打开；`AMBIGUOUS_POST` 不能自动转 429/re-reserve。

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

这里的 `response_complete` 只表示“当前 Result + dedicated submission-check snapshot 已结构化取得”，**不表示所有 check 已 terminal**。`PENDING/UNKNOWN/RUNNING/PROCESSING` 必须作为真实 current check row 保留；不能因为其中一项未终态就把整份 research Result 隐藏在 provider gate 之外。

Guard 必须验证：

- `simulation_id` 与已 POSTED request 一致；
- result evidence 时间不早于 POST，且 snapshot authenticated / source 可审计；
- frozen success/protection contract 所需 typed observations 已存在；
- 为了比较 new blocker/unresolved，当前 snapshot 不得无故丢失 Incumbent 已存在的 check 名称；
- success criteria 与 protected metrics 是否成立；
- candidate 是否引入**新的** blocking check 或新的 unresolved check。`FAIL` 永远 blocking；若当前项目/平台把某个 WARNING 视为 blocking，可在 raw check row 中显式 `policy_blocking:true`。Incumbent 原本已经 PENDING 的 check，在 candidate 仍是同一 PENDING 时不是 new unresolved，不应阻止 mechanism-level evaluation；candidate 新引入的未分类 WARNING、PENDING/UNKNOWN 等 unresolved 才使结果 `INCONCLUSIVE`。

`SUBMISSION_READY` 仍然更严格：当前 Incumbent 的 check snapshot 必须非空、authenticated、response_complete、source/timestamp 可审计；`FAIL` 或 `policy_blocking:true` 会阻止 readiness；任何仍为 `PENDING/UNKNOWN` 等非终态的 check 也是 unresolved；WARNING 若要作为 non-blocking 接受，必须由 controller 基于当前平台/项目规则显式给出 `policy_classified:true, policy_blocking:false`。因此 research evaluation 和 submission readiness 共用一份真实 snapshot，但判定职责不同，不再增加第二套 completeness flag。

只有 guard 计算为 `SUPPORTED` 的 result 才能 promotion。`REFUTED / INCONCLUSIVE` 不能靠调用者改布尔值绕过。

### Research progress is not submission readiness

`success_criteria` 应描述当前 hypothesis 的**机制预测**，不是机械复制最终 submission threshold。对于修复型路线，如果假设预测“Sharpe 应提高且 Fitness 不明显下降”，那么 candidate 在 `LOW_SHARPE` 仍为 FAIL 的情况下也可以得到 `SUPPORTED`，只要预声明 metric criterion / protected metrics 成立且没有新的 blocking/unresolved check。此时 promotion 表示“成为新的研究 parent / Incumbent”，**不表示** blocker 已修复，也不表示 `SUBMISSION_READY`。

只有当 hypothesis 本身有充分理由预测“这一步就应跨过当前 check threshold”时，才把 `check required_status=PASS` 作为 success criterion。若机制预测的是 check 数值的方向性改善而不是一步过线，使用 `check_value`，例如从 `LOW_SUB_UNIVERSE_SHARPE.value=0.88` 提升到 `0.90` 可以满足预声明的 `min_change=0.01`，即使该 check 仍为 FAIL。不要把所有 repair hypothesis 都写成“一步过线”，也不要把 check.value 塞进普通 metrics。

`REFUTED` 只否定当前 frozen hypothesis/payload 所声称的问题。它**不自动证明整个 route mechanism 已耗尽**。Controller 只有在剩余 same-mechanism questions 已有负证据、重复、或没有新的可证伪信息时才能 `exhaust-focus`。反过来，`SUPPORTED` 后 promotion 会产生新的 Incumbent cycle；旧 plan 变 STALE，必须 fresh diagnosis/re-plan，而不是沿参数邻域连续扫点。

# Alpha Intake：Root → Profile/Plan → Focus → Result

目标是取得**足以定位当前 mechanism 的证据**，不是机械跑满所有诊断。用户可读证据只追加到本次 run 的 canonical log；machine state 由 guard 独立维护。

## Stage 0 — RUN START

收到并接受一个现有 Alpha ID 后，**在任何平台读取、诊断或 simulation 之前**运行：

```text
python3 scripts/optimizer_guard.py start-run --root-alpha-id <ID>
```

Guard 必须返回 `log_exists=true`、`log_path` 和 `state_path`。`log_path` 必须位于当前 `wq-alpha-optimizer/logs/` 下。后续所有阶段只使用这一个 MD；需要写可读分析时使用同一 `state_path` 的 `append-log`，不得手工创建第二份 run MD。

如果 canonical MD 无法创建，当前 optimizer run 不继续。

## Stage A — ROOT

读取并记录当前认证平台返回的：

- root Alpha ID、完整 expression/settings、region/delay/universe/instrument type；
- 实际 fields 与 dataset/scope；对**实际用到的 field**，可便宜取得时同时记录 exact description、type、dataset、metadata coverage/dateCoverage；不要扫描无关字段池；
- Sharpe、Fitness、Returns、Margin、Turnover、Weight、coverage 等 Result；
- 每项 submission check 的 `name/value/limit/status/observed_at/source`。

Root Baseline immutable；Incumbent 初始等于 Root。`PENDING` 是未知，不是 PASS。

初始化 guard 时尽量把 Root 的 current Result/check snapshot 一并写入 `result_evidence`，这样后续 protected metric / new blocker 比较可以 machine-check。

## Stage B — DIAGNOSE

从 expression 建立最小必要映射：

```text
expression node → operator/transformation → field → dataset → idea role
```

区分平台事实、结构推断、未证实假设。字段名不能代替字段语义；field description 应参与 expression node → idea role 的解释，但 description 本身不证明 PIT、lag、update cadence、unit 或 missing semantics。

只在能区分机制时增加 deep diagnostics：coverage/concentration、tail/sentinel/ties、stale/churn、gate activation、PnL/exposure/区域贡献等。Visualization 同样按证据触发，不是固定 gate。

所有要驱动 machine decision 的诊断，先作为 evidence record 注册到 guard。

## Stage C — PROFILE / OPTIMIZATION PLAN

第一次正式 candidate 前，基于当前 Root/Incumbent 和本 run 已注册 evidence 建立一个可审计的 Alpha Profile，并生成持久的 mechanism-level plan：

- 聚合 expression/settings、Result/checks、fields/dataset/type/coverage、PnL/时间稳定性、可用 exposure/concentration、expression structure 与历史实验；拿不到的内容写 unknown，不猜；
- 每条 route 必须有 target、Primary owner、mechanism、evidence refs 和 rationale；operator 存在性不是 route evidence；
- route 数组顺序就是执行优先级；guard 会固化为 priority。可以规划多条 route，但同一时刻最多一条 `ACTIVE`，其余为 `PENDING`；planning 不预加载所有 Primary references；
- 通过 `set-plan` 写入 guard 后，只有 active route 才能进入 FOCUS。Root 第一次 Profile 或任何合法 `STALE` re-profile 都可以得到**空 fresh plan**；这表示“没有 justified normal route”，不是 planner 失败，也不得为了满足非空约束虚构 route；
- Incumbent promotion 会使旧 plan `STALE`；`refresh-incumbent` 只有在 normalized metrics/check facts 发生实质变化时才使旧 plan `STALE`，纯 timestamp/source refresh 不重新打开 planning；route exhaustion/reopen 只在同一 Incumbent cycle 内继承；
- 当前 plan 的 route 全部 terminal 后，必须执行该 Incumbent cycle 唯一的一次 `final-replan`。final re-plan 仍为空才可进入 `COMPLETED_WITH_EXHAUSTION`，不得无限重规划。

## Stage D — FOCUS

### C1. DEFECT

有 blocker 时，从 `../index.md` 选择，并把一个当前 `FAIL` blocker 作为 machine focus 的 `blocker` 绑定：

> **Primary defect = 有证据支持、最上游、能够合理解释一个或多个当前 blocker 的 mechanism owner。**

不要机械选择数值最差 metric。只加载 Primary owner；secondary mechanism 只有被新证据明确识别后再加载。

### C2. ENHANCEMENT

如果当前 blocking checks 全部通过，但用户明确要求继续提升 Result：

1. 不得人为制造 blocker，也不得简单挑“最差的一个数字”开始调参；
2. 只有存在当前 evidence 支持的、same-thesis、可证伪 improvement opportunity 时才设置 `FOCUS=ENHANCEMENT`；
3. 仍然只能选一个 target / mechanism，并使用同一 hypothesis/candidate/promotion 纪律；
4. 如果没有这样的 opportunity，把 Profile 写成空 plan，再执行一次 final re-plan；仍为空则以 `COMPLETED_WITH_EXHAUSTION` 结束，并在报告中写 `No justified enhancement hypothesis`。

ENHANCEMENT 不是无限优化许可，也不能用来绕过已有 FAIL blocker。

## Stage E — HYPOTHESIS → CANDIDATE

本阶段只负责顺序：**先冻结 hypothesis，再生成 candidate，再做 live operator/schema 检查，再 preflight/reserve**。所有字段、允许的 mutation、field/complexity 约束、payload binding 与 transport 行为只以 `candidate-contract.md` 为准；本文件不重复定义。

若 candidate 引入或改变 operator family、GROUP/VECTOR 参数角色、named argument 或其它可能受 live signature 影响的结构，在 reserve/POST 前用当前 `get_operators()` 定义核对名称、arity/type/NaN 语义，并把能驱动决定的结论注册为 evidence。轻量 FE tokenizer 只负责 lexical/field/diff guard，不声称替代 live type checking。

Primary reference 负责提出经济机制；guard contract 负责判断该实验在机器层面是否允许执行。

## Stage F — RESULT → CLOSEOUT

Simulation 后先登记 raw Result/check evidence，再由 guard 按 `candidate-contract.md` 计算 hypothesis 状态。需要重新读取当前 Incumbent 的 fresh Result/checks（例如 promotion 后、终检前或平台状态更新后）时，使用 `refresh-incumbent`；任何用于新 plan 的 fresh facts 仍要另外注册 evidence refs。Controller 只根据 machine status 继续：

- `SUPPORTED`：尝试 promotion；成功后回到 fresh diagnosis/routing，处理仍存在的 blocker 或按用户目标结束。
- `REFUTED`：淘汰该 hypothesis；只有仍存在不同、未解决且 evidence-supported 的问题时才开下一 hypothesis。
- `INCONCLUSIVE`：只有缺失信息能够被明确补齐时才 retest；否则停止该问题。
- 当前 focus 已没有新的合理 question：`exhaust-focus`；guard 关闭当前 route，并自动激活下一个 pending route（如有）。
- 没有 pending route 时，controller 先执行一次 final re-plan；只有 final re-plan 仍为空且没有 OPEN hypothesis/focus/ACTIVE route，才能 `finish-run --status COMPLETED_WITH_EXHAUSTION`。
- `SUBMISSION_READY` 只能在当前 Incumbent 的 fresh、完整、authenticated、auditable checks 没有 blocking/unresolved 项时由 guard 接受；普通 `SUCCESS` 不等价于 submission-ready。
- 用户明确停止、下一步必须跨 locked scope、或认证平台在恢复纪律后仍不可继续时，分别使用 `USER_STOP / SCOPE_BOUNDARY / PLATFORM_UNRECOVERABLE`。这些 terminal 会冻结当时 machine state，不要求为了“收尾好看”伪造关闭动作。

Evidence Exhausted 的重新开启条件、result freshness、promotion、transport recovery 全部以 `candidate-contract.md` 为准。

最终报告区分 Root Baseline、Research Best（Incumbent）、Submission Ready、remaining blockers/unknowns，并记录 current-result refresh、plan revision、route history、re-plan 和 terminal reason。网络中断优先恢复已有 simulation，不重复 POST。

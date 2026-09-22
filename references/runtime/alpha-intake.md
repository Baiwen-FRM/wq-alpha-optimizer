# Alpha Intake：Root → Profile/Plan → Focus → Result

目标是取得**足以定位当前 mechanism 的证据**，不是机械跑满所有诊断。用户可读证据只追加到本次 run 的 canonical log；machine state 由 guard 独立维护。

## Stage 0 — RUN START / DETERMINISTIC BOOTSTRAP

收到并接受一个现有 Alpha ID 后，正常路径只运行一个入口：

```text
python3 scripts/bootstrap_run.py --alpha-id <ID>
```

**任何分析/评判开始前，四类信息都必须取得：**

1. **Expression + Settings**：当前 Alpha expression、instrument/region/universe/delay/decay/neutralization/truncation 等 locked settings；
2. **Result + Checks**：current Sharpe/Fitness/Returns/Margin/Turnover 等 Result，以及专用 submission-check endpoint 的 current checks；
3. **Data Field / Dataset**：从 expression 解析实际使用 fields，并对这些 fields 做 exact detail lookup，记录 description/type/dataset/coverage/dateCoverage；
4. **Visualization**：先检查现有 rich recordsets；若不足，创建一个 same-expression / same-settings、仅 `visualization=true` 的 diagnostic simulation。对 diagnostic Alpha 的 recordset listing 做有界稳定性确认，然后读取**平台当前列出的全部 available recordsets**。不要把“19”硬编码成协议；某次平台列出 19 个，就必须尝试读取这 19 个，未来列出 17/21 个也按实际列表全取。

Bootstrap 固定完成 run MD/state 创建、上述四类事实取得、raw intake 持久化、Guard baseline 初始化与 Dashboard 更新。Controller 不得把这些步骤拆开自由重排。

若单个 recordset 在有界 retry 后仍不可读，保留其 listing 与 incomplete/unavailable 状态并继续使用其余事实；不要误判为“没有 visualization”。只有 WQ Lab capability/auth/BRAIN 整体不可继续时 bootstrap 才失败。

**Bootstrap 不是用户请求的完成点。** 返回 `READY_FOR_DIAGNOSIS` 后，必须在同一次 optimize 执行继续 Stage A → B → C；若 plan 有 ACTIVE route，再立即继续 Stage D → E → F。不得以“已完成 intake/Profile/Plan，下一步将继续”为最终答复。

## Stage A — ROOT

读取并记录当前认证平台返回的：

- root Alpha ID、完整 expression/settings、region/delay/universe/instrument type；
- 实际 fields 与 dataset/scope；对**实际用到的 field**，可便宜取得时同时记录 exact description、type、dataset、metadata coverage/dateCoverage；不要扫描无关字段池；
- Sharpe、Fitness、Returns、Margin、Turnover、Weight、coverage 等 Result；
- 每项 submission check 的 `name/value/limit/status/observed_at/source`。

Root Baseline immutable；Incumbent 初始等于 Root。`PENDING` 是未知，不是 PASS。

初始化 guard 时尽量把 Root 的 current Result/check snapshot 一并写入 `result_evidence`，这样后续 protected metric / new blocker 比较可以 machine-check。

四类 Root facts 取得后立即更新 canonical MD 首页 Dashboard。首页不是 audit note，而是当前 state 的固定可读投影：**Expression + Settings / Result + Checks / Field Information / Visualization & Diagnostics**。如果 visualization 或某个 recordset 经有界恢复仍不可得，明确写 incomplete/unavailable，不猜，也不因此跳过后续分析。

## Stage B — DIAGNOSE

从 expression 建立最小必要映射：

```text
expression node → operator/transformation → field → dataset → idea role
```

区分平台事实、结构推断、未证实假设。字段名不能代替字段语义；field description 应参与 expression node → idea role 的解释，但 description 本身不证明 PIT、lag、update cadence、unit 或 missing semantics。

先基于 mandatory intake 的四类信息进行完整判断：expression/settings 给结构与约束，Result/checks 给目标，field metadata 给数据语义，visualization/recordsets 给时间稳定性、coverage、size/sector/industry exposure 等横截面信息。recordsets 是基础信息面；只有其中能实际支持某个机制判断的内容才注册为 routing evidence。若这四类信息之外仍存在一个能实质区分机制的 in-scope diagnostic，再增加 targeted deep diagnostic，而不是重新做一遍普遍 intake。

**Diagnostic escalation before exhaustion.** 如果当前 blocker 的 Primary reference 明确指出某个 in-scope diagnostic 能区分候选机制，而 Root 当前 evidence 缺少这个 diagnostic，则在开 candidate 或声明 exhaustion 前先补这个信息面。典型情况：Sub-Universe / Robust-Universe / exposure 类 blocker 需要 cap/sector/industry/liquidity/coverage bucket 证据，但 Root 只返回基础 PnL/yearly recordsets；此时若同表达式、同 settings、仅 `visualization=true` 的 diagnostic control 能暴露 recordsets，应先运行一次该 control，并对 recordset discovery 做有界重试。这个 control 是诊断，不是 optimization candidate，不进入 promotion 比较。

只有以下任一成立时才可以跳过该 escalation：
- 当前 run 已经取得等价、可审计的 diagnostic；
- 有一个历史 run 的同一 Root identity 已经取得该 diagnostic，且当前 expression/settings/scope 与关键 Result/check facts 没有 material drift；
- 平台经过有界恢复后仍无法提供该 diagnostic，此时记录 unavailable/unknown，而不是猜。

如果日志在 closeout 中写“继续需要某个当前 scope 内可取得的 diagnostic”，但本 run 并未尝试它，则不能把当前 run 归因于 `COMPLETED_WITH_EXHAUSTION`；先完成 diagnostic escalation。

所有要驱动 machine decision 的诊断，先作为 evidence record 注册到 guard。Visualization raw recordsets 由 WQ Lab provider 获取，`recordset_dashboard.py` 按固定规则生成 chart specs，再用 `update-dashboard` 更新同一 MD 首页。模型不得临场选择 chart type、排序、axis 或标题。图形只展示平台返回数据，不补点、不插值、不编造。

## Stage C — PROFILE / OPTIMIZATION PLAN

第一次正式 candidate 前，基于当前 Root/Incumbent 和本 run 已注册 evidence 建立一个可审计的 Alpha Profile，并生成持久的 mechanism-level plan：

- 聚合 expression/settings、Result/checks、fields/dataset/type/coverage、PnL/时间稳定性、可用 exposure/concentration、expression structure 与历史实验；拿不到的内容写 unknown，不猜；
- 历史 run 可以作为 negative/positive mechanism evidence，但必须先验证 **Root identity**：expression、完整 locked scope/settings 和相关 field source 必须一致，且当前关键 Result/check facts 没有 material drift。历史日志还必须能审计到 candidate expression/settings/result/disposition **以及当时 frozen success/protection contract**；只有“以前试过”这种摘要不能自动继承 exhaustion。尤其不能把“candidate 有方向性改善但最终 check 仍 FAIL，所以当时被 REFUTED”的旧记录直接当成 mechanism-negative evidence；需要按当前 progressive contract 重新解释。身份不匹配、事实漂移或旧 contract 无法审计时，历史 run 只作背景，不阻止当前 run 重新诊断；
- 每条 route 必须有 target、Primary owner、mechanism、evidence refs 和 rationale；operator 存在性不是 route evidence。**Route 必须已经 actionable**：当前 evidence 至少足以提出一个明确、可证伪的下一步 mechanism question；如果还只是“可能需要更多诊断”，先留在 DIAGNOSE，不要先建 route 再立刻 evidence-exhaust；
- route 数组顺序就是执行优先级；guard 会固化为 priority。可以规划多条 route，但同一时刻最多一条 `ACTIVE`，其余为 `PENDING`；planning 不预加载所有 Primary references；
- 通过 `set-plan` 写入 guard 后，只有 active route 才能进入 FOCUS。Root 第一次 Profile 或任何合法 `STALE` re-profile 都可以得到**空 fresh plan**；这表示“没有 justified normal route”，不是 planner 失败，也不得为了满足非空约束虚构 route；
- Incumbent promotion 会使旧 plan `STALE`；`refresh-incumbent` 只有在 normalized metrics/check facts 发生实质变化时才使旧 plan `STALE`，纯 timestamp/source refresh 不重新打开 planning；route exhaustion/reopen 只在同一 Incumbent cycle 内继承；
- 当前 plan 的 route 全部 terminal 后，必须执行该 Incumbent cycle 唯一的一次 `final-replan`。final re-plan 仍为空才可进入 `COMPLETED_WITH_EXHAUSTION`，不得无限重规划。
- **Plan 写入后立即执行。** `set-plan` 若返回 `must_continue=true` / `next_required_action=SET_FOCUS`，controller 必须立即进入 Stage D；正常 optimize 请求不得在这里结束或向用户报告“下一步再继续”。

## Stage D — FOCUS

### C1. DEFECT

有 blocker 时，从 `../index.md` 选择，并把一个当前 `FAIL` blocker 作为 machine focus 的 `blocker` 绑定：

> **Primary defect = 有证据支持、最上游、能够合理解释一个或多个当前 blocker 的 mechanism owner。**

不要机械选择数值最差 metric。只加载 Primary owner；secondary mechanism 只有被新证据明确识别后再加载。

### C2. ENHANCEMENT

如果当前 checks 已 fresh resolve、没有 blocking/unresolved 项，且用户明确要求继续提升 Result：

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

- `SUPPORTED`：尝试 promotion。这里的 supported 是**mechanism-level research progress**，不要求最终 blocker 已 PASS；promotion 后把 candidate 作为新的 Incumbent，旧 plan STALE，回到 fresh diagnosis/routing。若 blocker 仍存在，只能基于新 Incumbent 的新事实提出下一步，不得机械扫描相邻参数。
- `REFUTED`：淘汰当前 frozen hypothesis/payload；不要自动把整个 mechanism family 标为 exhausted。只有该 mechanism 下已没有不同、未解决且 evidence-supported 的 falsifiable question 时才关闭 route。
- `INCONCLUSIVE`：只有缺失信息能够被明确补齐时才 retest；否则停止该问题。
- 当前 focus 已没有新的合理 question：`exhaust-focus`；guard 关闭当前 route，并自动激活下一个 pending route（如有）。
- 没有 pending route 时，controller 先执行一次 final re-plan；只有 final re-plan 仍为空且没有 OPEN hypothesis/focus/ACTIVE route，且所有会 materially change routing 的可取得 in-scope diagnostics 已完成或明确 unavailable，才能 `finish-run --status COMPLETED_WITH_EXHAUSTION`。若一个 route 从激活到 exhaustion **没有产生任何 hypothesis/candidate**，日志必须说明是哪个新诊断事实让它失去 actionability，或列出已复用且身份匹配的历史 negative evidence；不能只复述进入 route 前就已知的 blocker。
- 若 submission check 的 `PENDING/UNKNOWN` 与专用 endpoint 的 `passes_check/value/limit` 冲突，做一次有界 fresh reconciliation；仍冲突则保留 unresolved/unknown，不据此 promotion、也不为通过 check 制造 candidate。
- `SUBMISSION_READY` 只能在当前 Incumbent 的 fresh、完整、authenticated、auditable checks 没有 blocking/unresolved 项时由 guard 接受；普通 `SUCCESS` 不等价于 submission-ready。
- 用户明确停止、下一步必须跨 locked scope、或认证平台在恢复纪律后仍不可继续时，分别使用 `USER_STOP / SCOPE_BOUNDARY / PLATFORM_UNRECOVERABLE`。这些 terminal 会冻结当时 machine state，不要求为了“收尾好看”伪造关闭动作。

Evidence Exhausted 的重新开启条件、result freshness、promotion、transport recovery 全部以 `candidate-contract.md` 为准。

最终报告区分 Root Baseline、Research Best（Incumbent）、Submission Ready、remaining blockers/unknowns，并记录 current-result refresh、plan revision、route history、re-plan 和 terminal reason。网络中断优先恢复已有 simulation，不重复 POST。

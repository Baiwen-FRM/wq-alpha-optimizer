---
name: wq-alpha-optimizer
description: Use when the user provides an existing WorldQuant BRAIN Alpha ID and asks to diagnose submission blockers, optimize, improve, fix, enhance, or prepare that Alpha for submission.
metadata:
  version: 3.6.6
---

# WQ Alpha Optimizer

受约束地修复或增强既有 Alpha：先冻结事实，再定位机制，再做最小实验；不把优化变成参数搜索，不通过扩大 scope 来制造“改善”，不自动提交。

## Execution ownership

完整执行顺序只由 `references/runtime/alpha-intake.md` 维护；Root、Incumbent、Focus、Hypothesis、Candidate、transport、result 和 promotion 的机器定义只由 `references/runtime/candidate-contract.md` 维护。

## Global boundaries

这些是 optimizer 的高层边界，不在这里重复 machine-contract 细节：

- **Optimize hypotheses, not numbers.** 没有证据支持的问题，不用 simulation 去“找答案”；禁止 dense grid、magic-number search 和 winner-only 叙事。
- **Same thesis / existing scope.** 普通 candidate 必须留在当前 Alpha 的既有 thesis/scope 内；锁定字段、新字段准入和 scope boundary 由 `references/runtime/candidate-contract.md` 统一定义。用户若要求比较 scope 变量，结束当前 candidate path 并记录 scope boundary。
- **Minimal causal change.** 一次实验只回答一个 principal mechanism；复杂度增加必须由该机制解释。
- **Preflight errors are recoverable before transport.** hypothesis 冻结后若 candidate preflight 在 reserve 之前发现 contract omission（例如漏写 `complexity_reason` / `field_change_reason`），不要伪造 transport failure、不要手改 state，也不要关闭 route。使用 Guard 的 `withdraw-hypothesis` 保留旧 hypothesis 审计记录，再用新 hypothesis ID 冻结修正后的 contract；一旦 reserve 已发生则禁止此路径。
- **Reserved candidates are executed by one deterministic executor.** `reserve` 成功后，正常 controller 只调用一次 `scripts/execute_reserved_candidate.py`，不再手工拼 WQ payload、transport、poll、Result/check evidence 或 promotion。Executor 在真实 POST 前先持久化 `SUBMITTING`，201+Location 后立刻记 `POSTED`，之后只按 Location 续跑，并在内部有界处理 429、poll/result 暂不可得和 incomplete snapshot；正常返回必须已经到 evaluated Result、promotion、posted inconclusive，或明确 `recovery_required` boundary。Controller 不承担中间 retry/poll 循环的正确性责任，也不得重新 intake、重建 hypothesis 或重复 POST。
- **Progress, then re-plan.** Hypothesis support 判断的是预声明的 mechanism prediction，不要求每一步 candidate 直接把最终平台 blocker 从 FAIL 变 PASS。若 directional improvement 满足 success/protection contract 且没有新 blocker，可以 promotion 为新的 Incumbent；随后必须 fresh re-profile/re-plan。Root 始终 immutable，用于控制 drift。每条 `protected_metrics` policy 使用 simulation 前已冻结的同一个 tolerance，必须同时通过 **vs 当前 Parent/Incumbent** 和 **vs immutable Root** 两个 gate；不能用多次小幅 promotion 累积绕过 Root-level protection。
- **Research Incumbent is not automatically the final submission candidate.** 每个 evaluated Alpha 若其真实 Result/check snapshot 本身达到 submission readiness，就进入 `submission_candidate_archive`，即使其 frozen hypothesis 因机制 criterion 被 `REFUTED`。Archive 另外记录 Root-relative metric deltas 与 Root protection eligibility。终局有多个 eligible ready candidates 时，controller 必须基于 archive 的 Root-relative comparison 自主调用 submission-candidate selection；不得默认最后一个 promotion 胜出，也不得把这个选择交给用户。
- **Result facts before conclusions.** 平台结果/check evidence 先于“成功/失败”叙事；指标变好本身不等于机制得到支持。
- **Post-candidate learning is mandatory.** 每个 conclusive `SUPPORTED/REFUTED` candidate 后都必须重新生成 `mechanism_synthesis` scaffold，并把当前 Incumbent cycle 的 `candidate_history`、metric deltas、protection failures、new blockers 与 route/method-family history 联合起来推导下一条问题。不得把多个 Result 当成互不相关的独立实验；若多个实验共同形成新的约束（例如“降 turnover 会破坏 edge，而更快响应又触发 turnover ceiling”），下一条 hypothesis 必须针对这个联合约束，而不是继续沿单一参数轴扫点。
- **In-scope optimization is autonomous.** 对当前 locked scope 内的 enhancement target、route 顺序、diagnostic 选择和 next hypothesis，controller 自己按当前 evidence、区分能力、最小 causal change 与 protected-metric 风险排序并继续执行；**不要使用 AskUserQuestion 让用户在这些正常研究分支之间做选择**。只有需要扩大 scope/引入新字段或数据、用户目标本身冲突，或构造 candidate 所需的官方 operator/platform 语义确实缺失时才请求用户输入。
- **Stop is a valid outcome.** 当前 scope 内没有新的合理可证伪问题时停止，而不是扩大自由度；但如果一个当前 scope 内可取得的 diagnostic 能实质区分机制，必须先完成/复用该诊断，不能把“还没诊断”写成 evidence exhaustion。
- **Plan before focus, then continue.** 在第一次 candidate 前，先用已注册 evidence 形成 ordered mechanism-level optimization plan；多个 route 可以 pending，但一次只执行一个 active route，hypothesis 必须绑定该 route 的 target + mechanism。Plan/Profile 只是内部控制状态，不是正常 optimize 请求的交付物；只要 plan 有 ACTIVE route，必须在同一次执行继续到 Focus → Hypothesis → Candidate → Simulation/Result。
- **Evidence and methods are one diagnosis step.** Mandatory intake facts are not a separate report from repair/enhancement references. After intake, combine current observations with the active blocker **or blocker-free enhancement objective** owner's method families using `references/runtime/evidence-method-synthesis.md`. If the cause is unknown, use a falsifiable `PLAUSIBLE_PROBE` or `NEEDS_DIAGNOSTIC`; do not pretend the cause is known, and do not jump from a metric/check name alone to a generic operator recipe. Historical “tried before” evidence cannot by itself exclude a whole mechanism family.
- **Four mandatory intake surfaces.** 在第一次分析/评判前必须取得：① Expression + Settings；② current Result + submission checks；③ 实际使用 Data Field / Dataset 的 exact metadata；④ Visualization diagnostic 的完整当前可用 recordsets。若 Root 本身没有 rich recordsets，则用同 expression、同 settings、仅 `visualization=true` 做一次 diagnostic simulation，再读取平台列出的全部 available recordsets。平台暂时缺失/单个 recordset 不可读时记录 incomplete/unavailable，但不能把整块 visualization 静默跳过。
- **Fresh facts invalidate stale execution.** Incumbent promotion 或显式 fresh Result/check refresh 后，旧 plan 不得继续机械执行；重新 Profile/Plan。旧 legacy run 只能完成已有在途工作，不能在未安装 v1 plan 时开启新的 focus/hypothesis。
- **Focus exhaustion is not run exhaustion.** 当前 route 耗尽后切换下一个 pending route。空 plan 只有在 synthesis 对当前 blocker，以及本 Incumbent cycle 已进入过的 blocker-free enhancement objective，完成 catalog method-family 的可审计 no-action proof 时才合法；一个 payload 的 REFUTED 只能排除它所绑定的 mechanism，不能用 reason 文本把同 owner 的其它 families 一并宣告 exhausted。这个 no-action gate 对同一 Incumbent 的 **STALE re-profile 也持续有效**：final re-plan 后即使 fresh Result/check refresh 把 plan 标记 STALE，也不能再装一个无 synthesis 的 `routes=[]` 绕过剩余 method families。只有完整 no-action proof 成立时才以 exhaustion 结束 run。
- **No zero-work route closure.** 一条 route 一旦成为 `ACTIVE`，不能只靠 planning 时已经存在的 blocker、历史实验或旧 evidence 立刻关闭。Guard 只允许两种正常关闭依据：①该 route 已产生至少一个绑定的、**conclusive `SUPPORTED/REFUTED`** candidate Result；②route 激活之后出现一个 fingerprint 实质新的、来自 `BRAIN:` 且 subject 明确绑定当前 mechanism 的 `ROUTE_DIAGNOSTIC/DIAGNOSTIC_EXCLUSION` evidence。`INCONCLUSIVE`、transport failure、result-contract/plumbing failure 都不能证明 mechanism exhausted。否则 Guard 拒绝关闭。
- **Terminal means terminal.** `SUBMISSION_READY` 必须由最终 selected submission candidate 的完整、认证、可审计 Result/check snapshot 证明，同时该 candidate 必须通过 Root-relative protection eligibility；不能绕过 ACTIVE/STALE plan 或 mandatory final re-plan。若优化 cycle 已完成但没有任何 eligible evaluated candidate，且 Incumbent 仍等于 Root（没有 promotion），正常结论是 `COMPLETED_WITH_EXHAUSTION`，即“未找到更优 Incumbent”；不能因为 Root 本来可提交就用 `SUBMISSION_READY` 掩盖优化结果。`USER_STOP / SCOPE_BOUNDARY / PLATFORM_UNRECOVERABLE` 是显式冻结出口。

## Routing

正式路由入口是 `references/index.md`：planning 可以识别多个 evidence-supported route/owner，但执行时只加载当前 active route 的一个 Primary owner；不要预加载全部 optimization references。

Expression/settings、Result/checks、used-field metadata 与 visualization/recordsets 四类必需事实都走单入口 deterministic bootstrap；bootstrap 对同一 Root 的非终态任务使用 start-or-resume，controller 不再手工串联 start-run / intake / init / dashboard。每个 run 的机器事实仍只由一个 canonical Markdown 承载，安全续跑所需的 Guard state 压缩嵌入该 Markdown；若存在可绘制 visualization，则只允许额外生成 **一个同名 companion `*_dashboard.svg`** 供人类查看，不得恢复 `.state/.data/assets`、raw/derived snapshots 或每-chart 多文件。Bootstrap 后先做 evidence + method synthesis，再形成 route；不得把 intake、synthesis、Profile/Plan 当成正常终点。

真实 FE 查询、checks、field metadata、recordsets、correlation 和 simulation 使用本地已认证的 WQ Lab/`wq_lib`，接口边界见 `references/runtime/wq-lab-provider.md`。正常路径不再静默切回 CNHKMCP。Python Alpha 的转换、实现和 Python 专属回测由 `wq-python-alpha` 负责。

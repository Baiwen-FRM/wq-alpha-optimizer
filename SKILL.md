---
name: wq-alpha-optimizer
description: Use when the user provides an existing WorldQuant BRAIN Alpha ID and asks to diagnose submission blockers, optimize, improve, fix, enhance, or prepare that Alpha for submission.
metadata:
  version: 3.6.3
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
- **Progress, then re-plan.** Hypothesis support 判断的是预声明的 mechanism prediction，不要求每一步 candidate 直接把最终平台 blocker 从 FAIL 变 PASS。若 directional improvement 满足 success/protection contract 且没有新 blocker，可以 promotion 为新的 Incumbent；随后必须 fresh re-profile/re-plan。Root 始终 immutable，用于控制 drift。
- **Result facts before conclusions.** 平台结果/check evidence 先于“成功/失败”叙事；指标变好本身不等于机制得到支持。
- **Stop is a valid outcome.** 当前 scope 内没有新的合理可证伪问题时停止，而不是扩大自由度；但如果一个当前 scope 内可取得的 diagnostic 能实质区分机制，必须先完成/复用该诊断，不能把“还没诊断”写成 evidence exhaustion。
- **Plan before focus, then continue.** 在第一次 candidate 前，先用已注册 evidence 形成 ordered mechanism-level optimization plan；多个 route 可以 pending，但一次只执行一个 active route，hypothesis 必须绑定该 route 的 target + mechanism。Plan/Profile 只是内部控制状态，不是正常 optimize 请求的交付物；只要 plan 有 ACTIVE route，必须在同一次执行继续到 Focus → Hypothesis → Candidate → Simulation/Result。
- **Evidence and methods are one diagnosis step.** Mandatory intake facts are not a separate report from blocker repair references. After intake, combine current observations with the active blocker owner's method families using `references/runtime/evidence-method-synthesis.md`. If the cause is unknown, use a falsifiable `PLAUSIBLE_PROBE` or `NEEDS_DIAGNOSTIC`; do not pretend the cause is known, and do not jump from blocker name alone to a generic operator recipe. Historical “tried before” evidence cannot by itself exclude a whole mechanism family.
- **Four mandatory intake surfaces.** 在第一次分析/评判前必须取得：① Expression + Settings；② current Result + submission checks；③ 实际使用 Data Field / Dataset 的 exact metadata；④ Visualization diagnostic 的完整当前可用 recordsets。若 Root 本身没有 rich recordsets，则用同 expression、同 settings、仅 `visualization=true` 做一次 diagnostic simulation，再读取平台列出的全部 available recordsets。平台暂时缺失/单个 recordset 不可读时记录 incomplete/unavailable，但不能把整块 visualization 静默跳过。
- **Fresh facts invalidate stale execution.** Incumbent promotion 或显式 fresh Result/check refresh 后，旧 plan 不得继续机械执行；重新 Profile/Plan。旧 legacy run 只能完成已有在途工作，不能在未安装 v1 plan 时开启新的 focus/hypothesis。
- **Focus exhaustion is not run exhaustion.** 当前 route 耗尽后切换下一个 pending route。空 plan 只有在 synthesis 对当前 blocker 的 catalog method families 做了完整、可审计的 no-action proof 时才合法；不能因为历史上“试过很多方法”就把未评估的方法空间当成 exhausted。只有该 Incumbent cycle 的一次 final re-plan 也通过同样的 no-action gate 时，才以 exhaustion 结束 run。
- **No zero-work route closure.** 一条 route 一旦成为 `ACTIVE`，不能只靠 planning 时已经存在的 blocker、历史实验或旧 evidence 立刻关闭。Guard 只允许两种正常关闭依据：①该 route 已产生至少一个绑定的 evaluated candidate Result；②route 激活之后出现了一个 fingerprint 实质新的 diagnostic evidence，并在 `close-route/exhaust-focus --evidence-ref` 中显式引用。否则返回 `ROUTE_REQUIRES_CANDIDATE_RESULT_OR_NEW_EVIDENCE`。这条约束是 machine-enforced，不依赖 controller 自律。
- **Terminal means terminal.** `SUBMISSION_READY` 必须由当前 Incumbent 的完整、认证、可审计 checks 证明；`USER_STOP / SCOPE_BOUNDARY / PLATFORM_UNRECOVERABLE` 是显式冻结出口，结束后不再改变 research state。

## Routing

正式路由入口是 `references/index.md`：planning 可以识别多个 evidence-supported route/owner，但执行时只加载当前 active route 的一个 Primary owner；不要预加载全部 optimization references。

Expression/settings、Result/checks、used-field metadata 与 visualization/recordsets 四类必需事实都走单入口 deterministic bootstrap；controller 不再手工串联 start-run / intake / init / dashboard。Bootstrap 后先做 evidence + method synthesis，再形成 route；不得把 intake、synthesis、Profile/Plan 当成正常终点。

真实 FE 查询、checks、field metadata、recordsets、correlation 和 simulation 使用本地已认证的 WQ Lab/`wq_lib`，接口边界见 `references/runtime/wq-lab-provider.md`。正常路径不再静默切回 CNHKMCP。Python Alpha 的转换、实现和 Python 专属回测由 `wq-python-alpha` 负责。

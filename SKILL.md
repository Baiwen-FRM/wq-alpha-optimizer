---
name: wq-alpha-optimizer
description: Use when the user provides an existing WorldQuant BRAIN Alpha ID and asks to diagnose submission blockers, optimize, improve, fix, enhance, or prepare that Alpha for submission.
metadata:
  version: 3.3.1
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
- **Result facts before conclusions.** 平台结果/check evidence 先于“成功/失败”叙事；指标变好本身不等于机制得到支持。
- **Stop is a valid outcome.** 当前 scope 内没有新的合理可证伪问题时停止，而不是扩大自由度。
- **Plan before focus.** 在第一次 candidate 前，先用已注册 evidence 形成 ordered mechanism-level optimization plan；多个 route 可以 pending，但一次只执行一个 active route，hypothesis 必须绑定该 route 的 target + mechanism。
- **Fresh facts invalidate stale execution.** Incumbent promotion 或显式 fresh Result/check refresh 后，旧 plan 不得继续机械执行；重新 Profile/Plan。旧 legacy run 只能完成已有在途工作，不能在未安装 v1 plan 时开启新的 focus/hypothesis。
- **Focus exhaustion is not run exhaustion.** 当前 route 耗尽后切换下一个 pending route；Root/Incumbent profile 可以合法得到空 plan，不得为了继续而虚构 route。只有该 Incumbent cycle 的一次 final re-plan 也没有新 justified route 时，才以 exhaustion 结束 run。
- **Terminal means terminal.** `SUBMISSION_READY` 必须由当前 Incumbent 的完整、认证、可审计 checks 证明；`USER_STOP / SCOPE_BOUNDARY / PLATFORM_UNRECOVERABLE` 是显式冻结出口，结束后不再改变 research state。

## Routing

正式路由入口是 `references/index.md`：planning 可以识别多个 evidence-supported route/owner，但执行时只加载当前 active route 的一个 Primary owner；不要预加载全部 optimization references。

Visualization 是 conditional diagnostic enrichment，不是固定 gate；其触发和执行位置由 `references/runtime/alpha-intake.md` 决定。

真实 FE 查询、checks 和 simulation 使用已认证的 CNHKMCP。Python Alpha 的转换、实现和 Python 专属回测由 `wq-python-alpha` 负责。

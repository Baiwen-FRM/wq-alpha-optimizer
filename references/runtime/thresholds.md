---
name: submission-thresholds
description: 提交前门槛的解释与读取规则；具体 limit 以当前 Alpha 的平台检查返回值为准。
---

# Submission Thresholds

## Evidence priority

1. 当前认证 Alpha 的 `get_submission_check`：决定本次 `value / limit / status`。
2. 平台当前文档：解释检查含义、region/delay/project 特殊项。
3. 本文件：只解释 evidence/readiness/submission policy；不负责 repair 路由。

不要用历史常数补造未返回的 status/limit。响应缺失或调用失败时标 evidence unknown，并按 controller 重试或阻塞。

## Source conflict

Raw check evidence 保留 `source / observed_at / value / limit / status / response_complete / authenticated`。历史 Alpha details 不能覆盖更新的实时 check。两个当前、认证、完整来源实质冲突时标 `SOURCE_CONFLICT`，重新查询首选入口；持续冲突则 `BLOCK_EVIDENCE`，禁止挑更有利的来源。

## Readiness / WARNING / all_passed

`all_passed=true` 只说明该接口自己的聚合条件为真，不自动等于真实可提交；WARNING 也不能一律当 PASS 或一律当 BLOCK。

- 如果当前 UI、项目规则或用户**在本任务中明确给出的提交约束**会让某 WARNING 阻止提交，则 Submission Ready 仍为 NO/unknown，直到该约束满足或用户明确修改。
- 其它 WARNING 按当前平台语义和本任务明确约束分类；不要引入未定义的额外契约。
- ProdCorr/SelfCorr 的局部 `passes_check=true` 不能覆盖其它 submission-policy 证据。

## Threshold / headroom discipline

所有 threshold 以当前平台返回的 `limit/status` 为准。可记录 headroom 用于稳健性判断，但不固化统一 0.01/0.05 等 magic margin。

`PASS` 只表示当前平台判定通过。余量极薄、合理的小扰动可能轻易跨回 FAIL 时，可标 `FRAGILE_PASS`；它不覆盖平台 PASS，也不自动 BLOCK。只有用户在当前任务明确给出额外 headroom 要求时才按该要求判断。

## Fitness

```text
Fitness = Sharpe * sqrt(abs(Returns) / max(Turnover, 0.125))
```

仅用于解释组成；实际 PASS/FAIL 仍服从平台当前返回值，repair 路由由 `../index.md` 维护。

## Sub/Robust/Investability and time-window checks

Sub-Universe、Robust Universe、Investability、IS Ladder、LOW_2Y、地区特殊 Sharpe 等可能随 user/region/delay/project 改变。只记录平台当前窗口、value、limit、status；不复制静态 cutoff/年份表。

终检至少保留当前关键指标与 blocking checks 的 fresh evidence，并明确：Root、Research Best、Submission Ready、unknowns。Python Alpha 专属限制由 `wq-python-alpha` 维护。

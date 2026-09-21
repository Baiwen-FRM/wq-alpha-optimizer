## IS Ladder Sharpe

IS Ladder 检查不同历史长度的累积 Sharpe。它用于判断收益是否只集中在某个时期；具体年份、窗口和 `limit` 以平台当前返回值为准。

### 诊断顺序

1. 记录每个 Ladder 子项的 `value / limit / status`，不要只看总状态。
2. 对照逐年 Sharpe、Returns、Turnover 和 LOW_2Y，区分近期失效、早期异常收益和换手成本。
3. 如果结构或字段质量有问题，先修复已诊断的结构/数据原因并 fresh re-check；generic decay/窗口/settings 调优只有在当前 Ladder 机制明确支持时才做，不按固定阶段顺序机械展开。
4. 每个 candidate 只检验一个主要机制；孤立的 Ladder 高点标记为 `FRAGILE_PASS`，只有机制解释与有限邻域/结构证据足以支持时才可 promotion。

### 结构候选

`ts_rank`、`ts_mean`、`signed_power` 等只能在经济逻辑成立、算子参数已确认且字段/算子硬约束仍满足时作为候选。它们可能改变时间频率、尾部和覆盖，不能作为通用“包裹层”。

当 Ladder 弱项证据指向“某一阶段少数极端多头/空头主导”且 sign structure 有经济意义时，可按 `two-year-sharpe.md` 中的 `rank_by_side` 条件候选进行同一机制测试；本文件不维护第二套定义或参数规则。

```text
原信号 → 一个有解释的时间/分布变换 → 复查逐年、LOW_2Y、Turnover、Weight、PC/SC
```

### Candidate rejection / family closure

- 某个 candidate 改善 Ladder 却制造 LOW_2Y、Weight、PC/SC 或其它 protected-gate 新失败 → reject 该 candidate；这本身不代表整个 direction exhausted。
- 只有单个窗口/参数点改善 → `FRAGILE_PASS`；需要机制解释与有限邻域/结构证据，不按孤立 winner 自动 promotion，也不因孤立而自动终止研究。
- 只有当当前 Ladder remediation 的适用机制均已测试或被证据排除，并且没有新的具体可证伪问题时，才把该方向记为 Exhausted。

关闭后报告证据，不继续堆叠时间算子。只允许在当前字段/当前 thesis 范围内尝试尚未测试且有机制依据的表示；如果下一步需要新字段族、新数据集或新收益来源，则记录 scope boundary。

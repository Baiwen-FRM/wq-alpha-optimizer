# Data Quality / Field Semantics

本文件在当前证据指向 coverage、missing/outlier/stale、字段类型、cardinality、VECTOR 语义、post-expression validity，或其他 Primary owner 需要数据证据来区分机制时按需加载。目标不是把所有字段变成“满 coverage”，而是判断缺失和极端值的来源，再选择不会改变经济含义的处理。

### Field semantic context

可便宜取得时保留 field ID、exact `description`、type、dataset/scope、metadata coverage / dateCoverage。`description` 是字段语义证据，不单独证明 PIT、实际 lag、update cadence / 更新频率、unit/scale、missing-value semantics 或实际分布。

必须区分 **metadata coverage**、当前样本中的 observed field behavior，以及组合/变换后的 post-expression coverage；headline metadata coverage 高，不代表 NaN intersection、长历史窗口或 gate 后仍有足够有效样本。

### 1. 字段画像

按当前问题选择能改变诊断的维度；相关维度包括：

| 维度 | 问题 |
|---|---|
| coverage / dateCoverage | 有多少股票、多少交易日有值？ |
| non-zero coverage | 非零值是否足够？ |
| 更新频率 | 日频、月频、季频还是事件型？ |
| 缺失结构 | 随机缺失、行业/地区集中、长期缺失，还是缺失本身有含义？ |
| 新鲜度 | 最近有效值距当前多少天？回填后 stale 比例多大？ |
| 横截面分布 | 偏度、尾部比例、极端突变、`inf`/sentinel 是否存在？ |
| 字段类型 | `MATRIX / VECTOR / GROUP`？是否需要语义化聚合后才能进入当前算子链？ |
| 基数 / 编码 | 是否只有少数离散值、整数编码或大量 ties，导致表面高 coverage 但有效截面很窄？ |
| 多字段交集 | 组合后有效样本是否因 NaN 日期/股票不重叠而骤降？ |
| 有效样本 | 每日横截面和每个分组是否有足够有效值？ |

字段画像不足以区分当前候选机制时，先做小样本 probe；不要用一个回测 Sharpe 推断 coverage 已解决，也不要为了“完整”无条件采集所有画像维度。

### 2. 路线选择

| 画像 | 首选候选 | 不应做 |
|---|---|---|
| 高频且覆盖稳定 | raw、必要时 `rank`/稳健截面变换 | 无理由的长窗口回填 |
| 低频但持续更新 | 有限 `ts_backfill`，窗口匹配更新周期 | 把 120 天当所有字段默认值 |
| 同组可比的稀疏 level | `group_backfill`，再验证分组偏差 | 对不可比字段填组均值 |
| 事件型或缺失有含义 | 保留缺失，或用 freshness/missingness 门控 | 常数填充、无条件回填 |
| 结构性低 coverage | 当前 data scope 内同 thesis 的可用表示；若只能换新字段族/数据集则 a scope boundary | 继续扩大回填窗口 |
| 少量重尾极端值 | `winsorize`、稳健 z-score、分位数/排名变换 | 把所有极端值都当错误 |
| VECTOR 字段 | 按字段语义选择 `vec_avg/sum/max/count/range/stddev/IR` 等已验证聚合 | 为了能跑而机械 `vec_avg` |
| 低基数/编码字段 | 先确认编码含义；按 group/categorical 结构重表达或停止该表示 | 靠 winsorize / signed_power 强行制造连续性 |
| 多字段 NaN 交集 | 先测组合后的有效样本；必要时改为 thesis-consistent 的缺失处理/组合逻辑 | 假设两个高 coverage 字段组合后仍高 coverage |

候选只做单机制对照。`raw`、回填窗口、回填方法、异常值处理是候选机制族，不是必须依次遍历的固定顺序；只生成与当前缺失/更新/尾部证据匹配的方案，不要把互不相关的 fill、winsorize、rank 和中性化捆成一个 candidate。

### 3. Fast Expression

候选表达式必须先用 `get_operators()` 验证参数。`ts_backfill`、`group_backfill`、`winsorize`、`rank`、`group_zscore` 的作用范围和 NaN 行为以当前平台定义为准。`winsorize(x, std=4)` 是均值±标准差语义；不要把分位数 `min/max` 写法混入 FE 方案。

证据随 mutation 风险匹配：fill 关注处理前后 coverage / stale，tail 处理关注分布与裁剪影响，多字段组合关注 post-expression coverage；同时复查 active Target 与该 mutation 可能影响的 hard blockers，不机械展开无关指标。


### 3A. VECTOR / categorical semantics

VECTOR → scalar is **feature engineering**, not a mechanical cleaning step. Choose reduction by meaning: `vec_sum` for additive quantity, `vec_avg` for typical level, `vec_max` for extreme observation, `vec_count` for breadth/activity, `vec_range/stddev` for dispersion, `vec_ir` for mean-vs-dispersion style confidence only when its definition matches the field. Verify the current operator list and field definition first.

Structural zero and sentinel values must be separated from genuine economic zero before ranking/backfill. A low-cardinality categorical code should not be treated as a continuous magnitude unless the field definition explicitly supports that interpretation.

For combination expressions, profile **post-combination** coverage; NaN intersections can turn two individually broad fields into a sparse Alpha and then surface as CW/Sub/Robust failures.

### 4. Python boundary

Python Alpha 的 sentinel、NaN、universe mask、store、warm-up、`trade_when`、`winsorize` 和 `group_backfill` 实现规则统一由 `wq-python-alpha` 维护。本文件只规定通用字段诊断、候选决策和验收证据；需要 Python 细节时交给 `wq-python-alpha`，不要在这里复制一份。

### 5. Evidence outcome

Data verification 可以有两种结果：

- **字段画像健康、无需 cleaning remediation**：记录 `route=raw`，确认 coverage/有效样本、新鲜度、缺失结构和尾部没有需要修复的问题；**不要求为了“有改善”而强行清洗。**
- **字段画像存在问题并进入 remediation**：处理必须针对已诊断的问题产生可解释改善，且 stale 比例没有失控。

两种路径都必须满足：

- 没有用常数/错误 sentinel 制造虚假信号；
- Sharpe、Fitness、Turnover、LOW_2Y、LOW_SUB_UNIVERSE 和 Weight 没有新增 blocking FAIL；
- 最终路线的经济含义仍能用一句话解释；
- FE/Python 语义差异已记录，不能把本地 replay 当成平台确认。

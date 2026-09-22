# Overfitting Discipline

Canonical principle: **optimize hypotheses, not numbers**。本文件只负责研究层面的过拟合识别与停止纪律；payload binding、transport、promotion 等机器规则统一由 `../runtime/candidate-contract.md` 维护。

## O1 — Question before simulation

Simulation 应回答一个由当前 evidence 支持、可证伪的问题，而不是探索“还有什么参数能变好”。如果没有新的 evidence 或仍未解决的 concrete question，就不应继续生成实验。

## O2 — Root drift and complexity

持续比较当前 Incumbent 与 immutable Root。连续小改动也可能累积成 thesis drift；相对 Root 的结构、field 和 exposure 漂移必须能被同一经济逻辑解释。

复杂度采用 baseline-relative 判断：更简单通常是正证据；更复杂只有在新增结构直接服务于已声明机制、且 robustness evidence 随之增强时才合理。

## O3 — Natural scales, not numeric mining

Numeric tuning 使用 `../runtime/anchors.md` 的可解释尺度。先做 mechanism discovery，再做有限 confirmation；禁止 dense neighborhood/grid、逐点扫参和只保留 winner 的选择方式。

## O4 — Field/data freedom

新 dataset/new return source 属于 scope boundary。Same-scope alternative field 也不能把整个 dataset 预先变成候选池；是否允许进入实验由 machine contract 的 field-scope evidence 规则决定。

## O5 — Selection-bias warning signs

出现下列现象时优先降自由度、做 targeted robustness 或停止：

- improvement 只存在于一个孤立参数点；
- 连续 candidate 只是小幅改 window/decay/truncation，却没有新的机制信息；
- explanation 在看到结果后发生变化；
- 复杂度持续增加，但 causal evidence 没有增强；
- 为通过一个 check 引入另一个 blocker；
- 当前 Alpha 已 all-pass，却只是因为“还能更高”而继续搜索。

## O6 — Confirmation, progression and stop

机制初步得到支持后，优先 promotion 成新的 Incumbent，再基于新 Incumbent 的 fresh facts 决定是否还有同机制的下一步。允许的 refinement 必须回答**由上一结果产生的新问题**，例如确认改善是否来自 persistence 而非偶然单点；它不能只是“既然 10 更好，再试 11/12/13”。

`SUPPORTED` 不等于最终 check 已 PASS；它允许一步步推进。`REFUTED` 也只否定当前 frozen payload/question，不能凭一次失败自动宣布整个 mechanism family 死亡。

有限 confirmation 不是重新打开参数搜索。当前 focus 已不能提出新的 evidence-supported falsifiable question 时，结束该 focus。

Metric improvement alone 不等于 robustness，也不等于必须继续优化；但一个满足预声明 success/protection contract 的中间改善也不能仅因为最终 threshold 尚未跨过而被当成无效信息。


## O7 — Route mechanism is a research boundary

Active route 的 `target + mechanism` 不是标签，而是当前研究边界。v1 hypothesis 必须显式声明同一个 mechanism；不能在同一 target 下从 tail → neutralization → seasonality → momentum → component subtraction 逐个“试一遍”而仍称为同一路线。

一个 mechanism 内可以有少量、能区分同一 causal question 的 candidate（例如同一 persistence mechanism 的 expression-vs-setting implementation），但每个新 candidate 必须说明它相对于上一结果新增了什么可证伪信息。若只是换 operator、窗口、group、系数或 field 表示继续寻找 winner，而没有新的 observation/question，则应 exhaust 当前 route，而不是扩大自由度。

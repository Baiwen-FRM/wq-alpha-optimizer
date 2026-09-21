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

## O6 — Confirmation and stop

机制初步得到支持后，只允许足以验证稳定性的有限 confirmation；confirmation 不是重新打开参数搜索。当前 focus 已不能提出新的 evidence-supported falsifiable question 时，结束该 focus。

Metric improvement alone 不等于 robustness，也不等于必须继续优化。

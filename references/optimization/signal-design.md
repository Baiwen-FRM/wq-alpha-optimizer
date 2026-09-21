# Same-thesis Structural Enhancement

Use when the current routed defect requires a same-thesis structural repair. The goal is to improve the **existing economic thesis** without opening a new region, dataset family or unrelated return source.

Field cleaning belongs to `data-quality.md`; generic numeric scales belong to `../runtime/anchors.md` when the diagnosed mechanism needs them.

### Structural router

- **Noise / persistence mismatch** → causal temporal aggregation, smoothing, stable-vs-innovation decomposition.
- **Wrong forecast horizon** → align transformation/holding logic with the thesis horizon.
- **Cross-sectional exposure dominates** → justified grouping/neutralization/residualization.
- **Event information is sparse** → event/update gating that preserves the source thesis.
- **Distribution/tail structure is the issue** → justified rank/zscore/winsorization/nonlinearity with a declared role.
- **FE cannot express a justified same-thesis transform** → Python-specific implementation after the Python equivalence/native-baseline gate.

**Transformation placement is part of the mechanism.** For temporal denoising/innovation, operating on the raw/time-series layer **before rank/group_rank or other cross-sectional normalization** is not equivalent to smoothing an already ranked/normalized output **after rank**. Choose the placement that matches the thesis, state it in the hypothesis, and test one placement mechanism at a time.

Do not use this file to invent a new dataset, region or return logic. If the only credible improvement requires one, record a scope boundary and leave that idea to idea development.

### Structural test discipline

结构设计只决定“该机制应该怎样改变表达式”。实验次数、hypothesis lifecycle、payload binding、numeric-mining 限制统一服从 `overfitting.md` 与 `../runtime/candidate-contract.md`，本文件不再另设一套 candidate 规则。

对 temporal denoising、innovation、neutralization placement 等结构问题，一次只测试一个能够区分机制的 placement/representation；不要同时改多个可独立解释的结构轴。

### Python boundary

Python-specific FIR、Kalman、FFT、Haar/DWT、IIR、store、NaN、dtype、warm-up 和因果回放规则统一由 `wq-python-alpha/references/signal-processing.md` 与其 Python contract 维护。本文件只负责决定当前 Alpha 是否需要一个同 thesis 的结构机制；一旦路线进入 Python 实现，就交给 `wq-python-alpha`，不要在 optimizer 内重复实现。


### Algebra / component-removal discipline

不要把 `subtract(composite, component)` 自动解释成“移除了该 component”。只有在当前 expression 的代数分解明确证明 `composite = component + remainder`（含相同缩放、归一化、group/rank placement 与 NaN 语义）时，这种 subtraction 才能代表真正的 component ablation。否则它只是一个新的 nonlinear expression，必须按新的机制解释，不能用“去掉某因子”的叙事包装。

同理，component 权重、0.5/1.5 等系数没有当前 Alpha 的结构/经济证据时不是 canonical anchor；不要通过连续加减组件或权重形成 serial operator search。

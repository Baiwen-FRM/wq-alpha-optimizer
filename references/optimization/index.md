# Optimization References

本目录只放“当前 Alpha 有什么缺陷、应该测试哪些同 thesis 机制”的资料。平台 evidence/readiness 口径与 candidate 约束统一由 `../runtime/thresholds.md`、`../runtime/alpha-intake.md` 和 `../runtime/candidate-contract.md` 维护；这里不重复定义。

- `sharpe.md`、`fitness.md`、`turnover.md`、`margin-weight.md`：核心指标缺陷。
- `correlation.md`、`subuniverse.md`、`robust-universe.md`：相关性、子宇宙和可投资性问题。
- `two-year-sharpe.md`、`is-ladder.md`、`health-check.md`：时间稳定性和健康度。
- `data-quality.md`：字段语义、coverage、missing、stale 和 post-expression 数据诊断。
- `signal-design.md`、`overfitting.md`：同 thesis 结构设计和过拟合边界。
Python Alpha 的实现、等价验证、signal processing 和 Python 专属回测不在本目录维护；入口 skill 已定义交接边界。

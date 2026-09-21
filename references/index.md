# Optimization Metric Router

本文件是当前 Alpha Result / submission checks → 最小 Primary owner 的唯一总路由。平台当前 `value / limit / status` 是权威事实；reference 产生 hypothesis，不拥有 workflow state。

进入路由前先完成 `runtime/alpha-intake.md` 的 ROOT、core DIAGNOSE 与 PROFILE。**多个 blocker 并存时，不按数值最差项机械排序：优先选择有证据支持、最上游、能够解释一个或多个下游失败项的 mechanism owner。** Planner 可以把多个不同 mechanism route 排入 pending plan；执行时只激活一个 Primary owner。修复/排除或 promotion 后重新读取 fresh checks，再次路由。

## Metric / Check Router

| Metric / check signal | Target | Primary owner | Diagnose / test |
|---|---|---|---|
| `SHARPE`, `LOW_SHARPE`, weak risk-adjusted return | SHARPE | `optimization/sharpe.md` | signal quality, scaling, sign, persistence |
| `RETURNS`, `LOW_RETURNS`, weak absolute return | RETURNS | `optimization/fitness.md` | same-thesis structural weakness |
| `FITNESS`, `LOW_FITNESS` | FITNESS | `optimization/fitness.md` | Sharpe/returns/turnover interaction |
| low `MARGIN`, weak PnL per trade | MARGIN | `optimization/margin-weight.md` | persistence, trade selectivity, weight efficiency |
| `TURNOVER`, `HTVR`, `HIGH_TURNOVER`, excessive trading | TURNOVER | `optimization/turnover.md` | update frequency, persistence, churn, activation, settings mechanism |
| `LOW_TURNOVER`, over-smoothed / inactive trading | LOW_TURNOVER | `optimization/turnover.md` | stale holding, over-smoothing, inactive event gate |
| `WEIGHT_CONCENTRATION`, `CONCENTRATED_WEIGHT` | WEIGHT_CONCENTRATION | `optimization/margin-weight.md` | realized-weight concentration; route field/coverage cause to data-quality when evidenced |
| `COVERAGE_DATA_QUALITY`, low/date coverage, missing/outlier/stale, VECTOR/type issue | COVERAGE_DATA_QUALITY | `optimization/data-quality.md` | data validity, field semantics, justified cleaning |
| `PROD_CORRELATION`, high ProdCorr | PROD_CORRELATION | `optimization/correlation.md` | field/signal/exposure/activation similarity |
| `SELF_CORRELATION`, high SelfCorr | SELF_CORRELATION | `optimization/correlation.md` | same-thesis differentiation from own history |
| `LOW_2Y_SHARPE`, recent-window weakness | LOW_2Y_SHARPE | `optimization/two-year-sharpe.md` | recent decay/regime/stability and tail dominance |
| `IS_LADDER_SHARPE`, ladder weakness | IS_LADDER_SHARPE | `optimization/is-ladder.md` | multi-window stability and time dependence |
| `LOW_SUB_UNIVERSE_SHARPE`, sub-universe weakness | LOW_SUB_UNIVERSE_SHARPE | `optimization/subuniverse.md` | breadth, size/liquidity exposure, robustness |
| `LOW_ROBUST_UNIVERSE_SHARPE`, `LOW_ROBUST_UNIVERSE_RETURNS` | ROBUST_UNIVERSE | `optimization/robust-universe.md` | coverage dimension, capitalization/liquidity bucket weakness, persistence, exposure |
| `LOW_AFTER_COST_ILLIQUID_UNIVERSE_SHARPE`, `LOW_INVESTABILITY_CONSTRAINED_SHARPE`, `LIQUIDITY_UNIVERSE`, investability/size exposure | INVESTABILITY | `optimization/robust-universe.md` | liquidity-conditioned behavior, PnL/trading concentration, coverage |
| `LOW_GLB_AMER_SHARPE`, `LOW_GLB_APAC_SHARPE`, `LOW_GLB_EMEA_SHARPE`, `LOW_ASI_JPN_SHARPE`, other region-subset weakness | REGIONAL_SHARPE | `runtime/regional.md` | region-specific data/exposure/horizon diagnosis |
| health deterioration / unstable recent years | HEALTH_TREND | `optimization/health-check.md` | trend diagnosis, then route root cause back through this table |
| expression complexity / structural fragility | COMPLEXITY | `optimization/overfitting.md` | baseline-relative complexity and same-thesis simplification |
| FE parse/count/preflight issue | OPERATOR_PREFLIGHT | `runtime/operators.md` | FE token counting and verified operator roles |
| parameter sensitivity / isolated good point | PARAMETER_STABILITY | `optimization/overfitting.md` | fragility first; use `runtime/anchors.md` only for mechanism-supported scale |
| unfamiliar/project-specific check (`POWER_POOL_*`, `CLUSTER_*`, etc.) | UNKNOWN_PROJECT_CHECK | `runtime/thresholds.md` | fetch current definition first; never infer policy from stale examples |

Planning may identify multiple evidence-supported owners, but execution must **load one active Primary owner first**. Pending routes are not candidates and do not authorize preloading their references. Follow a cross-reference only after current evidence identifies the secondary mechanism. `runtime/thresholds.md` 只解释当前 check/limit/policy，不是每个 metric 的伴随文件。

## No-blocker enhancement entry

当前没有 blocking check 且用户明确要求继续 improve/enhance 时，不从本表伪造 defect；直接转 `runtime/alpha-intake.md` 的 ENHANCEMENT 分支。

## Auxiliary References

| Need | Load |
|---|---|
| Root/core diagnosis/conditional visualization | `runtime/alpha-intake.md` |
| candidate/state/guard contract | `runtime/candidate-contract.md` |
| same-thesis structural redesign | `optimization/signal-design.md` |
| generic numeric anchors | `runtime/anchors.md` |
| overfitting / robustness discipline | `optimization/overfitting.md` |
| region/delay interpretation | `runtime/regional.md` |
| operator syntax / FE token counting | `runtime/operators.md` |
| reporting | `runtime/report-templates.md` |
| Python Alpha | `wq-python-alpha` |

## Labels

- **Canonical rule** constrains execution.
- **Candidate** tests one open hypothesis against the current Incumbent.
- **Case-only evidence** may motivate a mechanism, never a universal threshold/parameter/search order.

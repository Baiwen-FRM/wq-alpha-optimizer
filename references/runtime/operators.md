## Canonical Operator Counting

FE preflight 的 `operator_count` 使用内部 `FE_TOKEN_V1`；平台 details/Judge 若有自己的 `operatorCount`，必须单独记录，不能混写。

`FE_TOKEN_V1` 是轻量 Fast Expression lexer/canonicalizer，不依赖 Python AST：

- 每个 function call occurrence 计 1，包括 `and(...)` / `or(...)`；
- arithmetic/comparison/logical/ternary operator token 计 1；
- field identifier、literal、括号、named argument 标签不计；
- 检查 token 与括号/方括号平衡，但**不**声称验证 live operator signature/arity；
- 无法可靠 tokenize 时 `FE_PARSE_UNKNOWN -> REJECT_PRECHECK`。

**绝对 operator 数是诊断，不是统一 hard cutoff。** Guard 比较 candidate vs current Incumbent；复杂度增加必须已在 frozen hypothesis 中声明机制理由，并持续记录相对 Root drift。

## Operator Role Framework

下表是作用分类，不是平台可用清单。使用前用当前 `get_operators()` 核对名称、参数、语言和 NaN 语义。

| Role | Examples | Purpose |
|---|---|---|
| Foundation | abs, add, multiply, divide, log | build relationships / transform raw signals |
| Cross-Sectional | rank, zscore, scale, normalize | cross-sectional comparison / normalization |
| Time-Series | ts_rank, ts_delta, ts_mean, ts_corr | history, trend, persistence |
| Signal Cleaning | ts_backfill, group_backfill, winsorize, truncate | missing/tail/weight repair only when diagnosed |
| Turnover Control | trade_when, hump, ts_target_tvr_decay | activation/persistence/turnover mechanism |
| Group Intelligence | group_rank, group_neutralize, bucket | group-aware representation / exposure control |
| Vector | vec_avg, vec_count, vec_range | verified vector → scalar semantics |
| Logical | if_else, and, or, is_nan | conditional/event handling |
| Distribution | densify, bucket | distribution/regime structure |
| Advanced candidates | regression_neut, ts_quantile, inst_tvr | only after live definition/signature verification |

不要为了 uniqueness 或 operator rarity 堆叠算子。Operator role 必须服务于当前 open hypothesis。

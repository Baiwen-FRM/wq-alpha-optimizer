## Sub-Universe Sharpe

A Sub-Universe failure usually points to coverage, investability/size exposure, or signal concentration. Diagnose those before adding transformations.

### SU1 — Coverage
- compare full-universe vs failed-subuniverse coverage, stale/non-zero ratios and daily valid-stock count;
- sparse fields route to `data-quality.md`;
- gates/thresholds must report selection rate so the subuniverse does not collapse toward a constant signal.

### SU2 — Size / liquidity exposure
Check whether the failed subset is mainly small-cap, low-liquidity or a narrow industry exposure. Unexplained size multipliers are a candidate root cause, not an automatic repair recipe.

### SU2A — Missing discriminator

如果当前只有 aggregate PnL/Sharpe 和 field metadata，却缺少 cap/liquidity/sector/industry/coverage bucket 诊断，不要直接跳到 neutralization、window、decay 或 gate candidate。先按 runtime intake 的 diagnostic-escalation 规则尝试同表达式 visualization control / authoritative recordsets。只有在诊断完成、已有同 Root 历史证据可复用，或平台明确 unavailable 后，才决定 structural candidate 或 exhaustion。

### SU3 — Structural candidates
After coverage/exposure diagnosis, test one mechanism at a time: temporal aggregation/rank, distribution transform, grouping/neutralization, thesis-preserving exposure control, or a verified change-control operator such as `hump` when daily instability is the diagnosed cause. `signed_power` is a possible distribution-strength candidate only when the current weight/tail geometry supports emphasizing stronger signals; it is not a universal Sub-Universe fix. Numeric scales come from `../runtime/anchors.md`.

A complementary **new return source or new dataset** is outside optimizer scope unless the user explicitly moves to idea development.

### SU4 — Controls and stop
Recheck full-universe Sharpe, LOW_2Y/Ladder, Weight, Margin, Turnover and PC/SC. If the in-scope directions are exhausted and any further repair requires a new source/region/universe thesis, record scope boundary rather than micro-tuning.

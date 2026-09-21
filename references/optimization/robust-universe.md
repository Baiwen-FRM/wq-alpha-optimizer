# Robust Universe / Investability Robustness

Current platform `value / limit / status` is authoritative for `LOW_ROBUST_UNIVERSE_SHARPE`, `LOW_ROBUST_UNIVERSE_RETURNS`, investability-constrained and illiquid-universe checks. Do not use any cutoff/ratio that is not supported by the current platform check. Robust Universe is related to, but not identical with, Sub-Universe.

## Root-cause router

- **Date coverage / intermittent history**: particular dates lose most valid names → route to `data-quality.md`; a thesis-consistent `ts_backfill`/persistence repair may be legitimate.
- **Cross-sectional coverage**: too few stocks have usable observations even when date coverage is stable → group-aware repair may be legitimate only when the group is economically comparable.
- **Capitalization / liquidity bucket weakness**: inspect available Sharpe-by-capitalization / liquidity diagnostics and identify whether weakness is concentrated in a specific investability bucket.
- **Tail / distribution fragility**: robust subset is dominated by a few extremes → test a targeted distribution/tail mechanism.
- **Persistence mismatch**: signal is too pulse-like/noisy or too over-smoothed for the robust subset → test one horizon/change-control mechanism.
- **Exposure / grouping mismatch**: country/industry/size exposure dominates subset performance → test one justified group/neutralization structure.
- **Investability mismatch**: PnL/trading is concentrated where liquidity or scalable execution is poor → use a thesis-consistent liquidity/investability gate only if the needed fields are already in scope.

## Candidate families

### RU1 — Coverage repair
Distinguish **date coverage** from **stock-count coverage** before choosing `ts_backfill` vs `group_backfill`. A group fill is only valid when the field is meaningfully comparable within that group; do not maximize coverage for its own sake. Recheck stale ratio and Weight/CW after fill.

### RU2 — Distribution / tail robustness
Use verified winsorize/rank/quantile/tail/nonlinearity only when observed tails explain the subset failure. Choose any scale from current distribution/economic evidence; more aggressive tail compression is not automatically better.

### RU3 — Temporal persistence
Use thesis-consistent smoothing/decay/rank/change-control only when refresh/horizon evidence supports it. Backfill and temporal windows can be non-monotonic across datasets/regions; do not assume longer is safer and do not sweep dense windows.

### RU4 — Exposure / grouping
Country/industry/size-bucket neutralization or group comparison can be tested when the robust weakness maps to those exposures. Fine group structures must still retain enough names per group.

### RU5 — Targeted investability / liquidity gate
A `trade_when` / `if_else` / multiplier gate on liquidity or capitalization can be tested **only** if bucket diagnostics identify a specific bad subset and the gate preserves the original thesis. Report selection rate/coverage. Arbitrarily deleting a percentile solely to pass Robust is overfit. Changing the simulation universe is outside the ordinary candidate contract; diagnose the weakness within the locked universe or record a scope boundary.

## Scope and rejection rules

- Do not stitch an unrelated high-Robust Alpha into the parent; that creates a new return source/family.
- Do not switch dataset/category merely to pass Robust/CW; record a scope boundary if a new source is required.
- Do not run neutralization × decay × truncation × window cross-product grids. Test one causal mechanism per candidate.
- `maxTrade`, project-specific switches or special pool rules must be verified against the current platform definition before use; unverified semantics are not actionable.

After every candidate recheck main Sharpe/Fitness/Returns/Margin/Turnover, Robust Sharpe/Returns, Sub-Universe, Weight/CW, LOW_2Y/Ladder and PC/SC. A Robust improvement that creates a new hard blocker is rejected.

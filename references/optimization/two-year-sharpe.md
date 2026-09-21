# Two-Year Sharpe Optimization

LOW_2Y is a platform stability check; the current returned window/limit/status is authoritative. It is distinct from IS Ladder.

## Root-cause hypotheses

- recent regime/horizon mismatch;
- source signal decay or weaker recent information content;
- data quality / field-definition change;
- tail/event concentration making recent results unstable;
- excessive smoothing/holding horizon that adapts too slowly;
- a few extreme long/short names dominating recent PnL and making the result regime-sensitive.

## Route

1. Verify field coverage, missingness, stale ratio and any known source change via `data-quality.md` before altering the signal.
2. Compare recent-period behavior with full-period and yearly evidence; large divergence is a diagnosis signal, not proof of a single cause.
3. If tail concentration is plausible, run a **targeted tail robustness control** whose cut/transform follows the observed distribution; do not use a universal fixed percentage.
4. If timing/persistence mismatch is plausible, test one mechanism family such as justified smoothing, horizon alignment or hold/gating; numeric scales come from `../runtime/anchors.md`.
5. If a few extreme names dominate one side while the **sign structure remains economically important**, a verified `rank_by_side` is a distinct candidate: it ranks/compresses the long and short sides separately, preserving sign better than a global rank. Recheck Margin because compressing strong-position amplitude can reduce PnL per trade.
6. If recent weakness follows over-smoothing, test a shorter thesis-consistent horizon or removal of an unnecessary smoothing layer; if it follows short-window noise, test the opposite. Do not assume “shorter” or “longer” is universally better.
7. If the same thesis no longer has credible predictive support and the next step needs a new dataset/return source, use a scope boundary.

Recheck LOW_2Y together with Sharpe, Fitness, Margin, Turnover, Weight/SubUniverse and correlation headroom; do not pass LOW_2Y by sacrificing other protected gates.


## Recent trajectory diagnostic

Use yearly / rolling evidence to answer whether LOW_2Y is a gradual decay, abrupt regime break, or a few-period/tail concentration. A custom “score” may summarize evidence for convenience, but it is **not** a platform threshold and must not replace the raw LOW_2Y check.

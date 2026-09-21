## High Turnover / HTVR

Turnover is a symptom. Optimize useful predictive PnL per trade, not the lowest Turnover number. Platform `value / limit / status` remains authoritative.

### Root-cause router

- **Information-update mismatch**: Alpha trades faster than the field materially refreshes.
- **Persistence mismatch**: position changes faster than the forecast is expected to decay.
- **Small-change churn**: many small signal changes create trading without material information change.
- **Noisy innovation**: short-horizon noise contributes little PnL but dominates position changes.
- **Event logic missing**: the thesis should act only when a verified event/state occurs.
- **Settings-driven turnover**: the mechanism is sound but simulation smoothing/holding behavior is too fast.
- **Over-smoothed / inactive signal (`LOW_TURNOVER`)**: too much decay/holding/gating may have removed useful responsiveness; diagnose separately from high turnover.


### Candidate families

#### T1 — Temporal aggregation / persistence
Use thesis-consistent smoothing/aggregation when the source has a slower information horizon than the current position path. In-expression aggregation operators such as `ts_decay_linear`, `ts_mean`, or `ts_decay_exp_window` (only after the current operator definition confirms semantics) belong here. Numeric windows come only from `../runtime/anchors.md` and must be justified by field refresh/persistence/economic horizon.

#### T2 — Information-update / event gating
When new information arrives discretely, hold the prior position until the verified update/event condition changes. `trade_when`-style logic is a candidate only when the platform operator semantics and event condition are verified.

#### T3 — No-trade / hysteresis-style churn control
If tiny output changes cause most trading, test a hold/hump/gating mechanism that ignores economically immaterial changes. Verified `hump` / `hump_decay`-style behavior belongs here only when its current semantics fit the hypothesis. Any threshold must come from signal noise/distribution or a defined economic scale; no dense threshold scan. Python-specific stateful implementation belongs to `wq-python-alpha`.

#### T4 — Stable vs noisy component
If short-term innovation produces substantial trading but little PnL, shrink/remove that component while retaining the stable predictive component. This is denoising, not blanket smoothing.

#### T5 — Information innovation representation
When the thesis is about **newly arriving information** rather than a persistent level, compare the same-source level representation with a change/`delta`/surprise/revision/acceleration representation. This is a signal-representation mechanism, not generic smoothing. Do not apply it when the economic thesis genuinely depends on the level; any lag/window must follow the information horizon and `../runtime/anchors.md`.

#### T6 — Settings decay
Settings-level decay is a candidate only when the mechanism is genuinely smoothing/partial adjustment. Generic numeric choices come from `../runtime/anchors.md`. Use a setting as a turnover repair only when the current turnover mechanism directly justifies it.

#### T7 — Verified direct target-TVR control
A direct target-TVR operator (for example `ts_target_tvr_decay`, `ts_target_tvr_hump`, or a current-platform equivalent, only after semantics are verified) is a distinct candidate family when direct turnover control fits the thesis better than generic smoothing. The target must come from the current platform constraint/economic trade-off evidence; never sweep copied target-TVR constants or optimize to the lowest reachable Turnover.

#### T8 — Verified position-change / delta limiting
Verified `ts_delta_limit` / `ts_target_tvr_delta_limit`-style mechanisms belong to a **separate** family: cap economically immaterial position changes relative to a justified reference only when the current operator definition confirms the signature and the Alpha thesis justifies that reference. Do not copy unverified reference series or target values, and do not sweep reference series just to find a PASS.

### Low Turnover / over-smoothed signal

If the platform returns `LOW_TURNOVER` or the Alpha is clearly inactive, reverse the diagnosis rather than adding more smoothing: inspect excessive decay/holding, a gate that rarely opens, stale carried positions, or a temporal window longer than the information horizon. Test one mechanism at a time by restoring justified responsiveness; protect Sharpe/Margin and do not increase turnover merely to hit an unsupported static range.

### HTVR context

High turnover can be correct when the thesis itself is short-lived. The question is whether information arrives and decays fast enough to justify frequent position changes. Validate PnL realization horizon against the thesis; do not impose a universal horizon or turnover number without current-Alpha evidence.

### Evidence interpretation

Always compare Turnover with useful PnL evidence (`Returns / Margin / Turnover / Sharpe / Fitness`) and the active blocker. Recheck LOW_2Y / Weight / SubUniverse / ProdCorr / SelfCorr when they are already material or the mutation can materially affect them. A candidate that cuts Turnover while destroying useful PnL is not automatically better.

### Anti-patterns

- no delay/universe change inside an ordinary optimizer candidate; use a scope boundary instead;
- no fixed hump/target-TVR values or copied parameter journeys;
- no neutralization sweep unless exposure evidence makes neutralization the tested mechanism;
- no repeated micro-tuning after an in-scope direction is refuted/exhausted;
- no Fast Expression → Python conversion as a turnover “fix”; conversion alone is not a turnover mechanism. Python implementation details belong to `wq-python-alpha`.

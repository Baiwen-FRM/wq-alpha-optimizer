## Margin / Weight / Concentration

### Low Margin

Margin = profit/loss per unit traded. Brain backtest does not itself deduct real slippage/transaction costs. Use current platform evidence for PASS/FAIL; do not introduce universal Margin/Turnover thresholds.

#### M1 — Margin Root-Cause Router

`LOW_MARGIN` is a symptom. **Optimize predictive PnL per trade, not Turnover alone.** If several causes are evidence-supported, prioritize the most upstream cause and test them sequentially; do not open a parallel candidate wave. Unverified causes remain hypotheses.

- **Excess trading / timing mismatch** → `turnover.md`:
  - persistence mismatch;
  - information-update mismatch;
  - small-change churn / no-trade-hysteresis candidate;
  - noisy short-horizon innovation.
- **Liquidity / investability weakness** → route to `robust-universe.md`; this file only retains the Margin/Weight interaction needed to identify that route.
- **Concentration / output-tail inefficiency** → use the CO/W routes below.
- **Predictive-efficiency weakness** → `signal-design.md`: horizon alignment, stable-vs-noisy decomposition, or same-thesis structural improvement. A new source/dataset is a scope boundary.

Compare `ΔReturns`, `ΔTurnover` and `ΔMargin` together. Region/delay changes diagnostic priority only; they do not create universal thresholds.


---

### Concentration

Concentration is about realized portfolio weights, not merely expression values. Current platform Weight/Concentration `value / limit / status` is authoritative.

#### CO1 — Diagnose the cause
Check **which structural mechanism creates concentration** before applying a wrapper:
- low cross-sectional coverage / too few valid names;
- **temporal sparsity** or long history requirement causing daily coverage cliffs;
- **low-cardinality / encoded fields** whose many equal values collapse the cross-section;
- **multi-field NaN intersection** where individually acceptable fields lose breadth after `add/multiply/ratio`;
- output tails / outliers;
- size/liquidity or group imbalance;
- simulation truncation / normalization behavior.

A `rank` transform does **not** prove final positions are equal-weight or that simulation truncation is irrelevant; verify the actual weight result. Route field-type/coverage issues to `data-quality.md`.

#### CO2 — Expression-level tail / distribution control
`winsorize`, `clip`, rank-like transforms, robust z-score/scale, or another verified tail-compression/distribution transform is a candidate when extreme expression values create disproportionate weights. It changes the expression distribution; it is not the same mechanism as simulation truncation. Special nonlinear mappings are candidates only when current operator semantics and the observed signal distribution justify that geometry.

#### CO3 — Simulation truncation
Truncation caps/controls portfolio weights according to current platform semantics. Numeric candidates come only from `../runtime/anchors.md`. Response can differ by signal distribution; do not assume “higher” or “lower” is always better.

#### CO4 — Scale / normalization
Scale/normalization can change overall portfolio normalization but does not guarantee a Max-Weight fix. Use only when the current weight pipeline shows a normalization problem and validate on actual weights.

#### CO5 — Temporal sparsity / persistence and change control
When concentration is caused by pulse-like/event updates or time-clustered validity, a short thesis-consistent `ts_mean`, `ts_decay_exp_window`, or equivalent persistence transform may be tested **only** if the mechanism is temporal sparsity rather than tail size. `hump` is primarily a change/churn-control mechanism; use it here only when unstable position changes are the diagnosed cause. None of these is a generic concentration clip.

#### CO6 — Structural exposure
Unexplained size/liquidity multipliers or highly imbalanced component weights can concentrate exposure. Remove/restructure them only when this preserves the same thesis.

---

### Data-quality boundary for concentration

Headline field coverage alone does **not** prove concentration safety. If low cardinality, VECTOR semantics, long-history/date clustering, multi-field NaN intersection or other field-validity structure is implicated, route diagnosis and remediation to `data-quality.md`; keep this file responsible for the realized-weight consequence. Do not switch dataset/category solely to pass CW; if a valid repair requires a new source, record a scope boundary.

### Weight distribution

Weight warnings can arise from skew/asymmetry even when the single-stock max is acceptable.

- inspect long/short dispersion, group imbalance and tail contribution;
- use one mechanism at a time: tail control, normalization, exposure restructuring, or simulation truncation;
- do not require every ranked signal to be followed by `scale`; verify the actual platform weight pipeline instead;
- if the response is insensitive to a settings axis, mark that family exhausted rather than micro-tuning it.

### Compare

After every candidate recheck Weight/Concentration plus Sharpe, Fitness, Returns, Margin, Turnover, SubUniverse and PC/SC. Do not trade one hard failure for another.

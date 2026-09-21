## Region / Delay Context

This file supplies **context for the Alpha's current region/delay**, not new Alpha ideas. It never authorizes cross-region expansion, a new dataset, a new universe thesis or a fixed attempt count. Current platform definitions/settings/checks are authoritative.

### R1 — Multi-country regions

For GLB/ASI/EUR-style multi-country universes, country/industry exposure can materially affect cross-sectional signals. If exposure evidence supports it, a combined grouping/neutralization mechanism may be tested. Verify current operator semantics before constructing a composite group; do not sweep many group combinations.
For multi-axis exposure control, do **not** assume sequential `group_neutralize` calls are equivalent to joint neutralization. If the current operator set supports a joint/cartesian grouping (for example `group_cartesian_product`, optionally `densify` when required by current semantics), construct/verify the joint group and neutralize once. Treat the operator names as conditional examples: verify them with the current operator definitions before use.

### R2 — ASI / JPN context

ASI may contain heterogeneous country and liquidity behavior; JPN can be a weak sub-region in some Alphas. Treat this as a **diagnostic priority only**:
- inspect current JPN/sub-region evidence if the platform exposes it;
- inspect liquidity/investability/coverage when Margin or SubUniverse is weak;
- choose grouping based on current exposure evidence, not a copied default.

Do not replace a weak component with a new price/fundamental source inside this optimizer; that crosses the existing data/return scope.

### R3 — IND / sparse-market context

When the current region has sparse fields, route first to `../optimization/data-quality.md`: coverage, missingness, stale ratio and group structure. Backfill/window choices must follow the current field profile and `anchors.md`, not a copied/static sequence.

### R4 — D0 context

D0 is appropriate only when the existing thesis genuinely uses same-day/overnight information. Expect timing and turnover sensitivity to matter more, but do not assume D0 is better or impose a universal Turnover/Margin threshold.

Changing delay is outside the ordinary optimizer candidate contract. Preserve the original delay baseline; if the user explicitly requests a delay comparison, record a scope boundary and handle that comparison outside this candidate path rather than mutating the current run.

### R5 — Fast D1 context

Fast-D1 fields are a distinct data-timing representation. Use them only if the current Alpha already belongs to that data scope and the field semantics are verified. Faster updates may raise turnover; route any resulting timing/churn issue to `../optimization/turnover.md`.

### R6 — PnL realization horizon

Use the observed realization horizon to test whether position adjustment matches the existing thesis:
- short-lived information should realize relatively quickly;
- slower fundamental information may justify longer holding/persistence.

These are directional hypotheses, not fixed day thresholds. If improving the Alpha requires a fundamentally different region/dataset/return source, return a scope boundary.

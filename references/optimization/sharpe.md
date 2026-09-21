## Low Sharpe

Current platform `value / limit / status` is authoritative. Treat low Sharpe as a signal-quality/noise/exposure/timing symptom, not a reason to sweep parameters.

### Root-cause router

- **High-frequency noise / persistence mismatch** → test a justified smoothing or temporal aggregation mechanism; choose numeric scale from `../runtime/anchors.md` based on horizon/field refresh.
- **Unwanted cross-sectional exposure** → test one supported neutralization/grouping change; do not sweep every neutralization setting.
- **Wrong temporal representation** → compare a thesis-preserving `ts_rank / ts_delta / timing` transform when it matches the economic claim.
- **Sign/direction wrong** → a sign-flip control is legitimate when the hypothesis predicts the opposite direction.
- **Source signal genuinely weak** → use `signal-design.md` to strengthen the same thesis; a new dataset or new return source is a scope boundary.

### Anti-patterns

- no fixed window sequence in this file; generic numbers live only in `../runtime/anchors.md`;
- no arbitrary weighted mix coefficients;
- no “more predictive dataset” substitution unless the user explicitly moves into idea-development scope;
- no generic decay tuning; use a setting only when the Sharpe blocker mechanism directly justifies it.

Evaluate Sharpe together with Fitness/Returns/Margin/Turnover and the protected platform checks relevant to the declared mechanism.

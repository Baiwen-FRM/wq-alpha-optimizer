## Low Fitness

Platform `value / limit / status` is authoritative. Fitness is a composite symptom; diagnose which component is weak before generating candidates.

```text
Fitness = Sharpe * sqrt(abs(Returns) / max(Turnover, platform_formula_floor))
```

### Root-cause router

- **Sharpe is the weak component** → load `sharpe.md`.
- **Turnover is high relative to useful PnL** → load `turnover.md`.
- **Returns are weak despite acceptable Sharpe/Turnover** → strengthen the same-thesis signal via `signal-design.md`; do not add a new return source inside this optimizer.
- **A settings mechanism is explicit** → use `../runtime/anchors.md` only through a blocker-specific, single-setting candidate.

Never improve Fitness by changing `testPeriod`, hiding instability, or optimizing only the displayed composite while a component materially worsens. Recheck Sharpe, Returns, Margin, Turnover and the active platform blockers after each evaluated candidate.

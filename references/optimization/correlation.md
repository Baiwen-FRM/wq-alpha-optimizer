## High ProdCorr / SelfCorr

Current submission check `value / limit / status` is authoritative. ProdCorr and SelfCorr are distinct; local correlation tools are optional pre-screening only and never replace the platform check.

### Root-cause router

- **Same-field / same-lineage representation** → change a thesis-preserving field representation or operator family inside the **same existing data scope**.
- **Common exposure dominates** → test a justified grouping/neutralization/residualization mechanism.
- **Sibling Alpha too similar** → avoid window/decay-only micro-variants; change one structural mechanism while preserving the economic thesis.
- **Middle-distribution noise creates similarity** → a distribution/tail gate can be a candidate only when the observed signal distribution supports it.
- **No in-scope structural difference remains** → scope boundary; do not switch to a new dataset just to hack correlation.

### Candidate families

#### C1 — Same-scope field representation
Use alternative fields only when they remain within the current Alpha's existing data scope and preserve the thesis. A new dataset/source is idea-development scope.

#### C2 — Operator / temporal structure
Examples of legitimate mechanism changes:
- cross-sectional rank vs group-relative representation;
- time-series rank/change vs level when the thesis is about relative change;
- event/persistence structure when the source information arrives discretely.

Do not use “rare operators” merely to be different.

#### C3 — Exposure control / orthogonalization
Residualization or vector/group neutralization is a candidate when current evidence indicates common factor/group exposure is causing correlation. Verified `regression_neut`-style residualization belongs here only when its current signature and economic regressor role are justified. Verify the current operator definition before use. Orthogonalization itself does not guarantee lower ProdCorr/SelfCorr or better quality.

#### C4 — Distribution / tail / selection structure
A thesis-preserving distribution reweighting/nonlinearity or a two-tail/gated construction (including a verified `tail`-style operator when appropriate) may reduce shared distribution exposure, but only when the observed signal/weight shape and economic thesis support that mechanism. Thresholds/scales must come from the observed distribution, `../runtime/anchors.md`, or a current-Alpha economic rationale; do not copy constants.

For a verified rank-like output on `[0,1]`, a symmetric two-tail rule must first center around the neutral midpoint before applying absolute-tail logic; otherwise the lower tail is not represented symmetrically. Verify the current operator range/semantics rather than assuming every rank-like transform uses the same interval.

Recheck selection rate, coverage, Sharpe, Fitness, Margin, Turnover and SubUniverse because aggressive reweighting/gating may reduce usable breadth.

#### C5 — Same-lineage SelfCorr risk
If SelfCorr repeatedly blocks siblings that only differ by window/decay/settings, stop generating more micro-variants. Prefer a mechanism-level change in temporal representation, exposure structure, event logic or source transformation **within the same thesis/scope**.

### Evidence interpretation

Repeatedly high correlation among window/decay-only siblings supports a structural-mechanism change rather than more micro-variants. If all in-scope mechanism families are exhausted/excluded and the only next step is a new dataset/region/return source, record a scope boundary rather than correlation hacking.

### Anti-patterns

- no fixed ProdCorr/SelfCorr cutoff outside the current platform check;
- no novelty heuristic (“use uncommon operators”);
- no portfolio/IQC workflow inside this single-Alpha optimizer;
- no broad dataset sweep;
- no generic decay/truncation search unless a current correlation mechanism explicitly justifies it.

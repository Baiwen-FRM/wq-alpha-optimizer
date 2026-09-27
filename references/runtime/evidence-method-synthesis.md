# Evidence + Method Synthesis

This layer bridges mandatory Alpha intake and optimization planning.

It does **not** claim that the current evidence reveals the true cause. Its job is to combine:

- current blockers, or an explicitly selected blocker-free enhancement objective;
- Expression + Settings;
- current Result + checks;
- exact used-field / dataset metadata;
- Visualization / recordsets;
- auditable historical evidence when identity-compatible;
- the blocker/enhancement owner's allowed method families.

The output is a small set of falsifiable mechanism assessments that can drive diagnostics or experiments.

## Ownership

`mechanism-catalog.json` is only the machine-readable mirror of the method families already owned by `references/index.md` and the corresponding Primary optimization references. It may constrain planning/exhaustion bookkeeping, but it must not invent operator semantics, numeric parameters, thresholds or new repair recipes. When catalog wording and an owner reference disagree, fix the catalog to match the owner reference rather than treating the catalog as a second rulebook.

## Scaffold

After mandatory intake evidence has been registered, create the deterministic scaffold:

```text
python3 scripts/mechanism_synthesis.py \
  --state <STATE_PATH> \
  --root-alpha-id <ROOT_ALPHA_ID>
```

The scaffold puts the current intake context and method space in one object: current Incumbent expression/settings/result evidence, fixed Dashboard field/visualization context, current blockers, any explicitly requested **or already-entered** blocker-free enhancement objectives, canonical owners/method families from `mechanism-catalog.json`, the evidence registry, the current Incumbent cycle's conclusive candidate history, and enhancement progress. Raw intake/recordsets are runtime inputs and are not represented as persistent artifact paths. The controller fills the assessments; the script does not guess economics.

`candidate_history` is deliberately factual rather than interpretive. For each evaluated candidate whose parent is the current Incumbent it exposes: hypothesis/route/mechanism, method family, Result status, before/after metrics, metric deltas, failed success/protection clauses, new blockers/unresolved checks, and expression/settings drift. `enhancement_progress` exposes catalog families already routed versus families never routed in the current cycle. These fields are the mandatory input for post-candidate learning; they prevent H1/H2/H3 from being treated as isolated anecdotes.

## Assessment states

Each assessed mechanism uses exactly one status:

- `ACTIONABLE`: current evidence materially supports a specific mechanism question and a minimal candidate can test it.
- `PLAUSIBLE_PROBE`: the cause is not known, but the current evidence plus an allowed method family justify one bounded experiment that can discriminate the mechanism.
- `NEEDS_DIAGNOSTIC`: the available facts cannot distinguish the mechanism yet, and a concrete in-scope diagnostic can.
- `EXCLUDED`: current evidence rules out the mechanism strongly enough that it should not generate a route.

Limited evidence is **not** a reason to invent certainty. When the cause remains unknown, prefer `PLAUSIBLE_PROBE` or `NEEDS_DIAGNOSTIC`.

## Evidence discipline

A mechanism assessment must cite registered evidence. Historical summaries may lower confidence, prevent an exact duplicate payload, or motivate a different question, but they cannot by themselves certify `EXCLUDED`.

`EXCLUDED` requires one of:

- mechanism-specific current BRAIN diagnostic evidence;
- an evaluated current candidate Result;
- an explicit scope-boundary fact.

For a current diagnostic exclusion, the evidence subject must identify the mechanism being excluded. A generic blocker fact such as “LOW_SHARPE fails” cannot be relabeled as proof that smoothing, neutralization, backfill, or any other family is exhausted.

Conflicting observations should normally produce a discriminator. Example: if Sharpe is uneven by capitalization **and** sector, do not immediately assume the cap effect is causal; ask whether the cap gradient survives a sector-conditioned comparison.

## Cross-candidate learning

After every conclusive `SUPPORTED` or `REFUTED` candidate, rebuild the scaffold before choosing the next route. The next assessment must use the **joint constraints** implied by the current cycle's candidate history, not only the most recent Result.

Examples of valid learning behavior:

- one candidate reduces Turnover but destroys Sharpe/Returns, while another increases Sharpe/Returns but breaches a Turnover ceiling → the next question should preserve the fast edge while discriminating low-value position changes, rather than continue a one-dimensional “faster/slower” sweep;
- two different neutralization/grouping interventions fail in the same exposure-sensitive subset → ask whether the underlying field/coverage mechanism is wrong before trying a third cosmetic grouping change.

The scaffold does not invent these economic conclusions. It gives the controller the factual deltas and route history required to reason about them. “I cannot immediately think of a payload” is not evidence. If a catalog family has no valid exclusion basis, classify it as `PLAUSIBLE_PROBE` or `NEEDS_DIAGNOSTIC` when an in-scope discriminator remains possible; do not silently convert it into exhaustion.

## From assessments to routes

A route must reference one or more `assessment_refs` whose status is `ACTIONABLE` or `PLAUSIBLE_PROBE`. The route target/owner/mechanism must match the assessment, and the route must carry the evidence used by that assessment.

One upstream mechanism may explain multiple blockers only when the synthesis contains a compatible assessment for each claimed blocker. This supports causal compression without allowing a route to claim unrelated failures.

The synthesis chooses a **method family / mechanism question**, not an operator. For blocker-free enhancement, call the scaffold with `--enhancement <TARGET> <OWNER>` (for example `--enhancement TURNOVER optimization/turnover.md`) so the same catalog-bound assessment contract applies. Exact expression/settings mutations are selected later by the active Primary reference and frozen hypothesis contract.

## Empty plan / exhaustion

Normal plans are intentionally lightweight: if a justified route exists, the controller does **not** need to enumerate every method family before testing it.

An empty plan is different. To claim “no justified route” for a blocker, the synthesis must cover the entire current method-family catalog for that blocker. For a blocker-free enhancement cycle, **every later empty plan for the same Incumbent** must cover the entire catalog method space of every enhancement target/owner entered during that cycle. This includes the normal final re-plan and any later STALE re-profile caused by a fresh Result/check refresh. Every required family must be assessed and there may be no `ACTIONABLE`, `PLAUSIBLE_PROBE`, or `NEEDS_DIAGNOSTIC` assessment.

Therefore:

- testable mechanism remains → `EMPTY_PLAN_HAS_TESTABLE_MECHANISM`;
- unresolved diagnostic remains → `EMPTY_PLAN_DIAGNOSTIC_REQUIRED`;
- method families were never assessed → `EMPTY_PLAN_METHOD_SPACE_UNASSESSED`;
- only a complete, auditable no-action proof can install an empty exhausted plan;
- one REFUTED payload excludes only its bound mechanism/method-family claim; it cannot be generalized to sibling method families without their own current evidence.

This is the machine gate that prevents “we tried many things historically” from silently becoming evidence that the present Alpha has no experiment left.

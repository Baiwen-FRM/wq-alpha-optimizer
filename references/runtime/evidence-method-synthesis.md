# Evidence + Method Synthesis

This layer bridges mandatory Alpha intake and optimization planning.

It does **not** claim that the current evidence reveals the true cause. Its job is to combine:

- current blockers;
- Expression + Settings;
- current Result + checks;
- exact used-field / dataset metadata;
- Visualization / recordsets;
- auditable historical evidence when identity-compatible;
- the blocker owner's allowed method families.

The output is a small set of falsifiable mechanism assessments that can drive diagnostics or experiments.

## Scaffold

After mandatory intake evidence has been registered, create the deterministic scaffold:

```text
python3 scripts/mechanism_synthesis.py \
  --state <STATE_PATH> \
  --root-alpha-id <ROOT_ALPHA_ID>
```

The scaffold lists the current blockers, their canonical owners/method families from `mechanism-catalog.json`, and the evidence currently available. The controller fills the assessments; the script does not guess economics.

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

## From assessments to routes

A route must reference one or more `assessment_refs` whose status is `ACTIONABLE` or `PLAUSIBLE_PROBE`. The route target/owner/mechanism must match the assessment, and the route must carry the evidence used by that assessment.

One upstream mechanism may explain multiple blockers only when the synthesis contains a compatible assessment for each claimed blocker. This supports causal compression without allowing a route to claim unrelated failures.

The synthesis chooses a **method family / mechanism question**, not an operator. Exact expression/settings mutations are selected later by the active Primary reference and frozen hypothesis contract.

## Empty plan / exhaustion

Normal plans are intentionally lightweight: if a justified route exists, the controller does **not** need to enumerate every method family before testing it.

An empty plan is different. To claim “no justified route” for a blocker, the synthesis must cover the entire current method-family catalog for that blocker. Every family must be assessed and there may be no `ACTIONABLE`, `PLAUSIBLE_PROBE`, or `NEEDS_DIAGNOSTIC` assessment.

Therefore:

- testable mechanism remains → `EMPTY_PLAN_HAS_TESTABLE_MECHANISM`;
- unresolved diagnostic remains → `EMPTY_PLAN_DIAGNOSTIC_REQUIRED`;
- method families were never assessed → `EMPTY_PLAN_METHOD_SPACE_UNASSESSED`;
- only a complete, auditable no-action proof can install an empty exhausted plan.

This is the machine gate that prevents “we tried many things historically” from silently becoming evidence that the present Alpha has no experiment left.

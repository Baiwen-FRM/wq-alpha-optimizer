# Codex Second-Pass Review Brief — wq-alpha-optimizer planning patch

## Scope

Only patch the current `wq-alpha-optimizer` skill. Do not redesign the optimizer and do not modify unrelated WorldQuant agents.

The first planning implementation is directionally correct and its existing 8 tests pass. Keep the new architecture:

```text
Profile/Plan
→ one ACTIVE route
→ one focus
→ one hypothesis
→ result
→ exhaust current route
→ activate next pending route
→ one final re-plan
→ terminal exhaustion
```

This second pass is only to close confirmed state-machine loopholes found by adversarial review.

## 1. Current review result

Existing tests on the uploaded implementation:

```text
Ran 8 tests
OK
```

Static compile also passes for:

- `scripts/optimizer_guard.py`
- `tests/test_optimizer_guard_planning.py`

The basic behavior is implemented correctly:

- multiple plan routes, one ACTIVE;
- exhausting R1 can activate R2;
- exhaustion is blocked before final re-plan;
- final re-plan cannot be called repeatedly in the simple same-incumbent path;
- promotion marks the plan `STALE`;
- unknown evidence is rejected;
- parent drift remains rejected.

However, the following loopholes were reproduced against the actual new guard and must be fixed before treating the planning layer as complete.

## 2. P0 — `STALE` plan can still open a new focus

### Confirmed behavior

After a plan is marked:

```text
status = STALE
```

the route objects inside it still remain `ACTIVE/PENDING`.

`set_focus()` currently only checks that there is exactly one route whose route-level status is `ACTIVE`; it does not reject a plan whose plan-level status is `STALE`.

Therefore this succeeds:

```text
promotion
→ plan.status = STALE
→ old active route still ACTIVE
→ set_focus(old route)
→ accepted
```

This directly violates the intended rule:

> Incumbent promotion invalidates the old plan; the controller must re-profile/re-plan before more focus/candidate work.

### Required fix

In planning-contract runs, `set_focus()` must require:

```text
optimization_plan.status == ACTIVE
```

and reject at least:

```text
STALE
EXHAUSTED
```

with a deterministic reject code such as:

```text
PLAN_NOT_ACTIVE
PLAN_STALE_REPLAN_REQUIRED
```

Do not silently reactivate a stale plan.

Also ensure `open_hypothesis`, `reserve_simulation`, etc. cannot bypass this through an old focus.

### Required test

Add a test:

```text
promote candidate
→ plan becomes STALE
→ calling set_focus against old active route
→ rejected
→ set-plan with a fresh plan
→ focus becomes allowed again
```

## 3. P0 — successful promotion currently blocks `finish-run SUCCESS`

### Confirmed behavior

After a successful promotion:

```text
plan.status = STALE
```

but the active route inside the stale plan still has:

```text
route.status = ACTIVE
```

`finish_run(SUCCESS / SUBMISSION_READY)` currently rejects if any route has route-level `ACTIVE`.

Observed result:

```text
PROMOTE -> success
finish_run("SUCCESS", ...)
→ ACTIVE_ROUTE_EXISTS
```

So the success path can become impossible immediately after the very promotion that achieved the target.

### Required fix

Success termination must not be blocked by stale/pending optimization work that is no longer relevant after the objective has been reached.

Minimal acceptable behavior:

- `COMPLETED_WITH_EXHAUSTION` keeps strict plan exhaustion/final-replan gates.
- `SUCCESS` / `SUBMISSION_READY` may terminate after no OPEN hypothesis/focus remains, even if the old plan is `STALE`.
- If current project semantics require a readiness check, reuse the existing authoritative success/readiness contract; do not invent a new one here.

Do not require the controller to manually mutate stale routes just to finish a successful run.

### Required test

```text
plan active
→ focus/hypothesis/candidate
→ supported result
→ promote
→ plan is STALE
→ finish_run(SUCCESS or SUBMISSION_READY)
→ allowed
```

## 4. P0 — run terminal state is not actually terminal

### Confirmed behavior

Current implementation permits:

```text
finish_run("SUCCESS")
→ finish_run("SUBMISSION_READY")
```

and the second call overwrites the first terminal state.

It also permits further research mutations after finish, e.g.:

```text
register_evidence(...)
set_plan(...)
```

after `run.status` is already terminal.

This means the new terminal state is only a label, not a state-machine boundary.

### Required fix

Add a small centralized terminal guard.

Once:

```text
run.status in RUN_TERMINAL_STATUSES
```

research-state mutations must be rejected with something like:

```text
RUN_ALREADY_TERMINAL
```

At minimum guard:

- `set_plan`
- `activate_route`
- `close_route`
- `set_focus`
- `exhaust_focus`
- `open_hypothesis`
- `abandon_hypothesis`
- `allow_field`
- `reserve_simulation`
- `record_transport`
- `release_reservation`
- `evaluate_result`
- `promote`
- a second `finish_run`

Decide whether `register_evidence` should be frozen too. For reproducibility, freezing it is preferable. `append_log` may remain allowed for final human notes if desired, because it does not change research decisions.

Do not over-engineer this; a single helper is sufficient.

### Required tests

1. Second `finish_run` is rejected.
2. `set_plan` after terminal is rejected.
3. `set_focus` / `open_hypothesis` after terminal is rejected.
4. If `append_log` is intentionally allowed after terminal, test that explicitly.

## 5. P0 — hypothesis can escape the active route target

### Confirmed behavior

The new route binding correctly checks:

```text
route.owner == focus.owner
route.target == focus.target
focus evidence overlaps route evidence
```

But `open_hypothesis()` only checks evidence overlap with the focus.

It does **not** require:

```text
hypothesis.target == focus.target
```

Confirmed example:

```text
active route target = SHARPE
focus target = SHARPE
hypothesis target = TURNOVER
same E1 evidence
→ accepted
```

This defeats the new planning boundary: the model can bind to a SHARPE route, then run a hypothesis for another target.

### Required fix

At minimum require:

```text
normalized_hypothesis.target == focus.target
```

If the existing contract intentionally distinguishes blocker name vs metric target, preserve that convention, but the hypothesis must not be able to jump to an unrelated planning target.

If mechanism identity is stored at hypothesis level in the local design, also bind it appropriately. Do not invent mechanism fields if the current hypothesis contract does not have them.

### Required test

```text
R1 target SHARPE
→ focus target SHARPE
→ open hypothesis target TURNOVER
→ rejected
```

and the matching SHARPE hypothesis must still pass.

## 6. P0/P1 — “new observation” can be the exact same fact under a new evidence ID

### Confirmed behavior

The documentation says:

> merely changing evidence ID or timestamp is not enough to reopen an exhausted route.

But the guard currently enforces only:

```text
new_observation.revision > route.closed_at_evidence_revision
```

Evidence registration has no content fingerprint.

Therefore:

```text
E1 claim = X
route exhausted
E2 claim = exact same X, same source/subject, new ID
→ E2 gets newer revision
→ final-replan with reopen_reason + new_observation_refs=[E2]
→ accepted
```

This recreates the exact loophole that caused the original long run: reread/re-register the same observation and obtain “fresh evidence”.

### Required fix

Keep this simple.

Add a deterministic content fingerprint for evidence, excluding only fields that do not change informational content, e.g. ID/revision and optionally timestamp.

A reasonable minimum fingerprint may be based on normalized:

```text
kind
subject
source
claim
```

Then:

- exact duplicate informational evidence gets the same fingerprint;
- registering a new ID may still be allowed if desired for audit history, but it must not qualify as a `new_observation_ref` for reopening the same exhausted route;
- route reopening must include at least one observation whose content fingerprint was not already available at/before that route's close.

Important limitation:
A machine guard cannot reliably detect semantic paraphrases. Do not claim that it can. The controller/reference contract must still decide whether differently worded evidence is materially novel.

Update the documentation accordingly:

```text
guard blocks exact informational duplicates;
controller must judge semantic novelty beyond exact fingerprint equality.
```

### Required tests

1. Same claim/source/subject under a new evidence ID cannot reopen.
2. A genuinely different observation registered after route close can reopen.
3. New timestamp alone cannot reopen.

## 7. P1 — `final_replan_used` leaks across incumbent changes

### Confirmed behavior

Current `set_plan()` creates a new plan with:

```python
"final_replan_used":
    final_replan or current.final_replan_used
```

So if the old incumbent already consumed final re-plan, then a route from that final re-plan produces a promotion:

```text
old incumbent
→ normal plan exhausted
→ final re-plan used = true
→ final re-plan finds a route
→ route succeeds
→ promote new incumbent
→ old plan becomes STALE
→ create fresh plan for new incumbent
```

the fresh plan still inherits:

```text
final_replan_used = true
```

The README says final re-plan is once per incumbent/plan cycle, but implementation makes it sticky across incumbent cycles.

### Required fix

When a stale plan is replaced because:

```text
incumbent_alpha_id changed
```

start a new planning cycle:

```text
final_replan_used = false
```

Do not reset it when merely revising the same incumbent's exhausted plan.

A simple rule:

```text
if new plan is for a different incumbent than current plan.incumbent_alpha_id:
    new cycle
    final_replan_used = false
else:
    preserve same-cycle semantics
```

Ensure the stored `incumbent_alpha_id` is actually used for this.

### Required test

```text
incumbent A
→ consume final re-plan
→ route from final re-plan promotes incumbent B
→ B gets a fresh plan
→ B's final_replan_used == false
→ B may later use exactly one final re-plan
```

## 8. P1 — legacy state can install a plan but still bypass plan binding

### Confirmed behavior

`read()` labels an old schema-4 state with no planning fields as:

```text
planning_contract = legacy
```

Calling `set_plan()` on that state succeeds, but `set_plan()` does not upgrade:

```text
planning_contract = v1
```

As a result the state now contains an optimization plan, but `set_focus()` still follows the legacy path and does not enforce active-route binding.

Confirmed:

```text
legacy old state
→ set_plan(R1)
→ planning_contract remains legacy
→ set_focus(owner/target/route_id that do not match R1)
→ accepted
```

This is especially relevant because the original real `O0Nq51jR` state was schema 4 and had no planning fields.

### Required fix

Preferred minimal policy:

When a legacy state successfully receives its first `set_plan()`:

```text
planning_contract = v1
```

From that moment onward new route/focus binding is enforced.

Do not rewrite historical hypotheses/candidates or alter old facts.

Alternatively, reject `set_plan()` on legacy states and require a dedicated migration command, but that is more complexity and is not necessary here.

### Required tests

Use either a real-state-derived fixture or a minimal legacy shape:

```text
no planning_contract
no optimization_plan
root baseline exists
→ read() => legacy
→ set_plan()
→ planning_contract becomes v1
→ mismatched route/focus is rejected
```

The current “real run shape” test creates a fresh v1 store via `initialize()`, so it does not actually test this legacy transition.

## 9. P1 — `based_on_evidence_revision` can contradict the route evidence

### Confirmed behavior

The guard only checks:

```text
0 <= based_on_evidence_revision <= current evidence revision
```

It does not ensure that all evidence referenced by the plan existed at that declared revision.

Confirmed:

```text
E1 revision = 1
plan.based_on_evidence_revision = 0
route.evidence_refs = [E1]
→ accepted
```

That makes the audit snapshot internally inconsistent.

### Required fix

For every:

```text
route.evidence_refs
route.new_observation_refs
```

require:

```text
evidence[ref].revision <= based_on_evidence_revision
```

If the planner omits `based_on_evidence_revision`, keeping the default of current revision is fine.

### Required test

```text
E1 revision 1
plan based_on_evidence_revision 0 and cites E1
→ rejected
```

## 10. Keep these first-pass changes

Do **not** undo:

- Profile/Plan stage in workflow docs.
- Multiple routes in a plan with only one ACTIVE.
- Active focus bound to the active route.
- Exhausting current focus closes/exhausts only that route.
- Automatic activation of next pending route.
- Final re-plan gate before `COMPLETED_WITH_EXHAUSTION`.
- Promotion marks old plan stale.
- Existing candidate/transport/field/scope guard behavior.
- No automatic BRAIN submit/network action.
- No rewrite of `references/optimization/*`.

## 11. Add regression tests instead of redesigning

After fixes, keep the original 8 tests and add tests for all confirmed cases above.

Target test suite should include at least:

```text
existing 8
+ stale plan cannot open focus
+ success can finish after promotion/stale plan
+ terminal run cannot be mutated/re-finished
+ hypothesis target cannot escape route/focus
+ exact duplicate evidence cannot reopen route
+ genuinely new evidence can reopen route
+ final-replan resets for new incumbent cycle
+ legacy set-plan upgrades planning contract
+ plan evidence revision consistency
```

No remote BRAIN calls are needed.

Run:

```bash
python3 -m unittest discover -s tests -v
```

and a no-write compile check for the guard/tests.

## 12. Final delivery format

Return:

1. exact files changed;
2. concise explanation for each confirmed bug and fix;
3. exact test output;
4. whether real old `O0Nq51jR` state can now safely enter the v1 planning contract without rewriting its historical facts;
5. any remaining limitation that the guard cannot solve deterministically, especially semantic novelty/paraphrase detection;
6. a reviewable diff.

Do not make unrelated refactors and do not commit/push unless explicitly asked.

## Acceptance criterion

After this patch, the planning layer should have this property:

> A route can continue only while the current plan is active and internally consistent; promotion invalidates the old plan; stale or terminal states cannot keep producing candidates; an exhausted route cannot be reopened merely by re-registering the same observation; legacy runs that opt into planning receive the same route-binding safety as fresh runs.

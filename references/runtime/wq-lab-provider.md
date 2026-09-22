# WQ Lab Provider Contract

This optimizer uses the user's local `wq_lib` package as the primary authenticated BRAIN I/O layer. It does **not** vendor or rewrite WQ Lab.

## Boundary

WQ Lab owns only BRAIN communication primitives:

- authentication/session;
- Alpha details / current Result;
- submission checks;
- exact data-field detail and dataset metadata returned with it;
- operator definitions;
- prod/self correlation;
- single/multi simulation and Location polling;
- Alpha recordset discovery and raw recordset retrieval.

The Skill owns:

- run order and state;
- Root/Incumbent/Hypothesis/Candidate contracts;
- deciding whether a visualization control is needed;
- cloning an Alpha into a same-expression/same-settings `visualization=true` diagnostic control;
- bounded recordset discovery policy;
- raw snapshot persistence;
- recordset → chart normalization;
- SVG/Markdown rendering;
- diagnosis, optimization logic, reports and submission-readiness policy.

Do not move dashboard/rendering/optimization policy into WQ Lab. Do not duplicate BRAIN HTTP calls in the Skill when a required WQ Lab primitive exists.

## Required additive WQ Lab surface

The optimizer expects the local WQ Lab to expose these existing primitives:

`login`, `get_result`, `get_submission_check`, `get_prod_corr`, `get_self_corr`,
`get_operators`, `simulate_single`, `get_datasets`, `get_datafields`.

It additionally requires exactly these generic read primitives:

```python
get_datafield(session, field_id) -> dict
get_alpha_recordsets(session, alpha_id) -> dict
get_alpha_recordset(session, alpha_id, recordset_type) -> dict
```

These three functions must return BRAIN facts without dashboard-specific transformation.

## Deterministic intake

The normal optimizer entrypoint is:

```text
python3 scripts/bootstrap_run.py --alpha-id <ID>
```

`bootstrap_run.py` owns run creation, persistence, Guard initialization and Dashboard update. It calls the lower-level `wq_lab_provider.py` code rather than asking the controller to chain commands manually.

The provider layer uses one authenticated WQ Lab session and always performs the same BRAIN order:

1. Alpha details;
2. submission check;
3. parse actual expression identifiers;
4. exact `get_datafield` for each used field and select the matching region/delay/universe coverage row;
5. inspect existing Alpha recordsets;
6. if no rich visualization recordsets are present, create one same-expression/same-settings diagnostic with only `visualization=true`;
7. discover recordsets with a bounded fixed retry policy;
8. fetch each discovered recordset as raw schema/records;
9. build deterministic dashboard field rows and chart specs.

The bootstrap stores all three under `logs/.data/<run_id>/`: `intake.json` is raw evidence, `baseline.json` is only the Guard initialization projection, and `dashboard.json` is only the deterministic presentation projection. The lower-level provider CLI remains available for debugging/recovery but is not the normal controller path.

## Visualization normalization

`scripts/recordset_dashboard.py` owns recordset → chart-spec mapping.

- date/day series → line chart;
- `*-by-*` bucket/group recordsets → zero-baseline bar chart downstream;
- `yearly-stats` remains raw/table evidence rather than forcing heterogeneous metrics onto one axis;
- missing numeric observations are dropped from that plotted row, never interpolated;
- recordset ordering is fixed by code;
- unknown recordsets remain raw evidence and do not trigger model-invented chart layouts.

The model does not choose chart type, axis layout, title convention or recordset ordering.

## Backend policy

There is no silent CNHKMCP fallback in the normal optimizer path. If local WQ Lab is unavailable or lacks the required additive primitives, stop with an explicit local-provider/setup error rather than switching transport backends mid-run.

A future fallback backend may be added only behind the same provider contract and canonical schemas, so changing transport cannot change the Dashboard or optimizer behavior.

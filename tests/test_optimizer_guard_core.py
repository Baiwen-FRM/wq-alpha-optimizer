import sys
import tempfile
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import optimizer_guard as guard  # noqa: E402


class CoreGuardTests(TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        self.logs = root / "logs"
        self.state_path = root / "state.json"
        self.patches = patch.multiple(guard, LOGS_DIR=self.logs, STATE_DIR=self.logs / ".state")
        self.patches.start()
        self.store = guard.StateStore(self.state_path, "ROOT")
        self._initialize(self.store)
        self._register(
            self.store,
            "E1",
            "DIAGNOSTIC",
            "LOW_SHARPE",
            "BRAIN:test",
            "Current LOW_SHARPE failure supports a signal-quality route.",
        )

    def tearDown(self):
        self.patches.stop()
        self.tempdir.cleanup()

    def _initialize(self, store, *, checks=None, observed_at="2026-09-21T00:00:00Z"):
        result = store.initialize(
            {
                "alpha_id": store.root_alpha_id,
                "expression": "rank(close)",
                "fields": ["close"],
                "settings": {
                    "language": "FASTEXPR",
                    "region": "GBR",
                    "delay": 0,
                    "universe": "TOP700",
                    "instrumentType": "EQUITY",
                    "decay": 5,
                    "truncation": 0.08,
                },
                "language": "FASTEXPR",
                "result_evidence": {
                    "metrics": {"SHARPE": 2.0, "FITNESS": 1.5, "TURNOVER": 0.2},
                    "checks": checks if checks is not None else [{"name": "LOW_SHARPE", "status": "FAIL"}],
                    "observed_at": observed_at,
                    "source": "BRAIN:test",
                    "response_complete": True,
                    "authenticated": True,
                },
            }
        )
        self.assertTrue(result["initialized"], result)

    def _register(self, store, evidence_id, kind, subject, source, claim, observed_at="2026-09-21T00:01:00Z"):
        result = store.register_evidence(
            {
                "id": evidence_id,
                "kind": kind,
                "subject": subject,
                "source": source,
                "observed_at": observed_at,
                "claim": claim,
            }
        )
        self.assertTrue(result["ok"], result)
        return result

    def _set_plan(self, store=None, *, mechanism="signal_quality", target="SHARPE", owner="optimization/sharpe.md", evidence="E1"):
        store = store or self.store
        return store.set_plan(
            {
                "based_on_evidence_revision": store.read()["evidence_revision"],
                "routes": [
                    {
                        "id": "R1",
                        "target": target,
                        "owner": owner,
                        "mechanism": mechanism,
                        "evidence_refs": [evidence],
                        "rationale": "Current evidence supports this mechanism.",
                    }
                ],
            }
        )

    def _open_focus(self, store=None, *, mechanism="signal_quality"):
        store = store or self.store
        result = store.set_focus(
            "DEFECT",
            "optimization/sharpe.md",
            "SHARPE",
            ["E1"],
            blocker="LOW_SHARPE",
            route_id="R1",
        )
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["focus"]["mechanism"], mechanism)
        return result

    def _contract(self, *, mutation=None, protected=None, mechanism="signal_quality", field_change_reason=None):
        contract = {
            "target": "SHARPE",
            "mechanism": mechanism,
            "principal_hypothesis": "The declared mechanism should improve Sharpe without protected-metric damage.",
            "mutation": mutation or {"type": "expression"},
            "success_criteria": [{"type": "metric", "name": "SHARPE", "direction": "higher", "min_change": 0}],
            "protected_metrics": protected if protected is not None else [{"name": "FITNESS", "rule": "not_lower", "tolerance": 0}],
            "failure_meaning": "If Sharpe does not improve safely, weaken this mechanism.",
            "evidence_refs": ["E1"],
            "complexity_reason": "Any added expression structure is the single declared mechanism.",
        }
        if field_change_reason:
            contract["field_change_reason"] = field_change_reason
        return contract

    def _open_hypothesis(self, store=None, *, contract=None, hypothesis_id="H1"):
        store = store or self.store
        result = store.open_hypothesis(hypothesis_id, contract or self._contract())
        self.assertTrue(result["ok"], result)
        return result

    def _candidate(self, *, expression="rank(-close)", fields=None, settings=None, hypothesis_id="H1", parent_id=None):
        state = self.store.read()
        return {
            "parent_id": parent_id or state["incumbent"]["alpha_id"],
            "hypothesis_id": hypothesis_id,
            "expression": expression,
            "fields": fields or ["close"],
            "settings": settings or state["incumbent"]["settings"],
            "language": "FASTEXPR",
        }

    def test_submission_ready_rejects_current_blocker(self):
        result = self.store.finish_run("SUBMISSION_READY", "Attempt readiness.")
        self.assertEqual(result["reason"], "CURRENT_BLOCKERS_REMAIN")
        self.assertIn("LOW_SHARPE", result["readiness"]["blockers"])

    def test_warning_requires_explicit_nonblocking_classification_for_readiness(self):
        unresolved = self.store.refresh_incumbent_result(
            {
                "alpha_id": "ROOT",
                "metrics": {"SHARPE": 2.0, "FITNESS": 1.5},
                "checks": [
                    {"name": "LOW_SHARPE", "status": "PASS"},
                    {"name": "PROJECT_WARNING", "status": "WARNING"},
                ],
                "observed_at": "2026-09-21T00:05:00Z",
                "source": "BRAIN:get_submission_check",
                "response_complete": True,
                "authenticated": True,
            }
        )
        self.assertTrue(unresolved["ok"], unresolved)
        self.assertEqual(unresolved["readiness"]["reason"], "READINESS_CHECKS_UNRESOLVED")

        classified = self.store.refresh_incumbent_result(
            {
                "alpha_id": "ROOT",
                "metrics": {"SHARPE": 2.0, "FITNESS": 1.5},
                "checks": [
                    {"name": "LOW_SHARPE", "status": "PASS"},
                    {
                        "name": "PROJECT_WARNING",
                        "status": "WARNING",
                        "policy_classified": True,
                        "policy_blocking": False,
                    },
                ],
                "observed_at": "2026-09-21T00:06:00Z",
                "source": "BRAIN:get_submission_check",
                "response_complete": True,
                "authenticated": True,
            }
        )
        self.assertTrue(classified["readiness"]["ready"], classified)
        finished = self.store.finish_run("SUBMISSION_READY", "Current checks are explicitly classified and non-blocking.")
        self.assertTrue(finished["ok"], finished)

    def test_refresh_incumbent_result_stales_existing_plan(self):
        planned = self._set_plan()
        self.assertTrue(planned["ok"], planned)
        refreshed = self.store.refresh_incumbent_result(
            {
                "alpha_id": "ROOT",
                "metrics": {"SHARPE": 2.05, "FITNESS": 1.52},
                "checks": [{"name": "LOW_SHARPE", "status": "PASS"}],
                "observed_at": "2026-09-21T00:05:00Z",
                "source": "BRAIN:get_submission_check",
                "response_complete": True,
                "authenticated": True,
            }
        )
        self.assertTrue(refreshed["ok"], refreshed)
        self.assertEqual(refreshed["plan_status"], "STALE")
        self.assertTrue(refreshed["readiness"]["ready"])
        finished = self.store.finish_run("SUBMISSION_READY", "Fresh current checks are ready.")
        self.assertTrue(finished["ok"], finished)

    def test_refresh_rejects_wrong_alpha_and_stale_timestamp(self):
        wrong = self.store.refresh_incumbent_result(
            {
                "alpha_id": "OTHER",
                "metrics": {},
                "checks": [],
                "observed_at": "2026-09-21T00:05:00Z",
                "source": "BRAIN:test",
                "response_complete": True,
                "authenticated": True,
            }
        )
        self.assertEqual(wrong["reason"], "RESULT_REFRESH_ALPHA_MISMATCH")
        stale = self.store.refresh_incumbent_result(
            {
                "alpha_id": "ROOT",
                "metrics": {},
                "checks": [],
                "observed_at": "2026-09-20T23:59:00Z",
                "source": "BRAIN:test",
                "response_complete": True,
                "authenticated": True,
            }
        )
        self.assertEqual(stale["reason"], "STALE_RESULT_REFRESH")

    def test_user_stop_can_freeze_open_research_state(self):
        self.assertTrue(self._set_plan()["ok"])
        self._open_focus()
        self._open_hypothesis()
        stopped = self.store.finish_run("USER_STOP", "User explicitly stopped the run.")
        self.assertTrue(stopped["ok"], stopped)
        self.assertEqual(stopped["status"], "USER_STOP")
        blocked = self.store.register_evidence(
            {
                "id": "E_AFTER",
                "kind": "DIAGNOSTIC",
                "subject": "AFTER",
                "source": "BRAIN:test",
                "observed_at": "2026-09-21T00:07:00Z",
                "claim": "Research mutation after terminal must be blocked.",
            }
        )
        self.assertEqual(blocked["reason"], "RUN_ALREADY_TERMINAL")

    def test_scope_boundary_and_platform_unrecoverable_are_terminal(self):
        scope_store = guard.StateStore(Path(self.tempdir.name) / "scope.json", "SCOPE")
        self._initialize(scope_store)
        scope = scope_store.finish_run("SCOPE_BOUNDARY", "Further work requires a new dataset.")
        self.assertTrue(scope["ok"], scope)

        platform_store = guard.StateStore(Path(self.tempdir.name) / "platform.json", "PLATFORM")
        self._initialize(platform_store)
        platform = platform_store.finish_run("PLATFORM_UNRECOVERABLE", "Authenticated platform recovery was exhausted.")
        self.assertTrue(platform["ok"], platform)

    def test_locked_scope_drift_is_rejected(self):
        self.assertTrue(self._set_plan()["ok"])
        self._open_focus()
        self._open_hypothesis()
        settings = dict(self.store.read()["incumbent"]["settings"])
        settings["region"] = "USA"
        candidate = self._candidate(settings=settings)
        pre = guard.preflight_candidate(candidate, self.store.read(), require_open_hypothesis=True)
        self.assertEqual(pre["reject_code"], "LOCKED_SCOPE_DRIFT")

    def test_setting_hypothesis_changes_exactly_one_declared_key(self):
        self.assertTrue(self._set_plan()["ok"])
        self._open_focus()
        contract = self._contract(mutation={"type": "setting", "key": "decay"})
        self._open_hypothesis(contract=contract)

        settings = dict(self.store.read()["incumbent"]["settings"])
        settings["decay"] = 10
        candidate = self._candidate(expression="rank(close)", settings=settings)
        pre = guard.preflight_candidate(candidate, self.store.read(), require_open_hypothesis=True)
        self.assertTrue(pre["valid"], pre)

        two_keys = dict(settings)
        two_keys["truncation"] = 0.10
        invalid = self._candidate(expression="rank(close)", settings=two_keys)
        pre2 = guard.preflight_candidate(invalid, self.store.read(), require_open_hypothesis=True)
        self.assertEqual(pre2["reject_code"], "SETTING_MUTATION_COUNT")

    def test_field_change_requires_allowlist_and_predeclaration(self):
        self.assertTrue(self._set_plan()["ok"])
        self._open_focus()
        contract = self._contract(field_change_reason="field_b is verified in the same existing scope.")
        self._open_hypothesis(contract=contract)

        candidate = self._candidate(expression="rank(add(close,field_b))", fields=["close", "field_b"])
        before = guard.preflight_candidate(candidate, self.store.read(), require_open_hypothesis=True)
        self.assertEqual(before["reject_code"], "FIELD_OUTSIDE_ALLOWLIST")

        self._register(
            self.store,
            "E_FIELD",
            "FIELD_SCOPE",
            "field_b",
            "BRAIN:get_data_fields",
            "field_b is verified in the same existing dataset and scope as the incumbent source.",
            observed_at="2026-09-21T00:03:00Z",
        )
        allowed = self.store.allow_field("field_b", "E_FIELD")
        self.assertTrue(allowed["ok"], allowed)
        after = guard.preflight_candidate(candidate, self.store.read(), require_open_hypothesis=True)
        self.assertTrue(after["valid"], after)

    def test_http_429_retry_budget_is_bounded(self):
        self.assertTrue(self._set_plan()["ok"])
        self._open_focus()
        self._open_hypothesis()
        candidate = self._candidate()
        first = self.store.reserve_simulation(candidate)
        self.assertTrue(first["allowed"], first)
        fp = first["fingerprint"]
        for retry in range(1, guard.MAX_EXPLICIT_429_RETRIES + 1):
            recorded = self.store.record_transport(fp, "HTTP_429")
            self.assertTrue(recorded["ok"], recorded)
            self.assertEqual(recorded["retry_count"], retry)
            if retry < guard.MAX_EXPLICIT_429_RETRIES:
                again = self.store.reserve_simulation(candidate)
                self.assertTrue(again["allowed"], again)
        exhausted = self.store.reserve_simulation(candidate)
        self.assertFalse(exhausted["allowed"], exhausted)
        self.assertEqual(exhausted["reason"], "HTTP_429_RETRY_EXHAUSTED")

    def test_result_older_than_post_is_rejected(self):
        self.assertTrue(self._set_plan()["ok"])
        self._open_focus()
        self._open_hypothesis()
        candidate = self._candidate()
        reserved = self.store.reserve_simulation(candidate)
        fp = reserved["fingerprint"]
        self.assertTrue(self.store.record_transport(fp, "POSTED", "SIM-STALE")["ok"])
        result = self.store.evaluate_result(
            candidate,
            {
                "alpha_id": "CHILD",
                "simulation_id": "SIM-STALE",
                "observed_at": "2026-09-20T00:00:00Z",
                "source": "BRAIN:test",
                "response_complete": True,
                "authenticated": True,
                "metrics": {"SHARPE": 2.1, "FITNESS": 1.5},
                "checks": [{"name": "LOW_SHARPE", "status": "FAIL"}],
            },
        )
        self.assertEqual(result["reason"], "STALE_RESULT_EVIDENCE")

    def test_missing_protected_metric_makes_result_inconclusive(self):
        self.assertTrue(self._set_plan()["ok"])
        self._open_focus()
        self._open_hypothesis()
        candidate = self._candidate()
        reserved = self.store.reserve_simulation(candidate)
        fp = reserved["fingerprint"]
        self.assertTrue(self.store.record_transport(fp, "POSTED", "SIM-INCONCLUSIVE")["ok"])
        result = self.store.evaluate_result(
            candidate,
            {
                "alpha_id": "CHILD",
                "simulation_id": "SIM-INCONCLUSIVE",
                "observed_at": guard._now_iso(),
                "source": "BRAIN:test",
                "response_complete": True,
                "authenticated": True,
                "metrics": {"SHARPE": 2.1},
                "checks": [{"name": "LOW_SHARPE", "status": "FAIL"}],
            },
        )
        self.assertEqual(result["status"], "INCONCLUSIVE")
        self.assertIn("protected_metric:FITNESS", result["evaluation"]["missing"])

    def test_same_incumbent_stale_empty_reprofile_preserves_final_replan_usage(self):
        empty = self.store.set_plan({"routes": []})
        self.assertTrue(empty["ok"], empty)
        final = self.store.set_plan({"routes": []}, final_replan=True)
        self.assertTrue(final["ok"], final)
        self.assertTrue(final["plan"]["final_replan_used"])

        refreshed = self.store.refresh_incumbent_result(
            {
                "alpha_id": "ROOT",
                "metrics": {"SHARPE": 1.99, "FITNESS": 1.49},
                "checks": [{"name": "LOW_SHARPE", "status": "FAIL"}],
                "observed_at": "2026-09-21T00:05:00Z",
                "source": "BRAIN:get_submission_check",
                "response_complete": True,
                "authenticated": True,
            }
        )
        self.assertEqual(refreshed["plan_status"], "STALE")
        replacement = self.store.set_plan({"routes": []})
        self.assertTrue(replacement["ok"], replacement)
        self.assertTrue(replacement["plan"]["final_replan_used"])
        finished = self.store.finish_run("COMPLETED_WITH_EXHAUSTION", "Fresh re-profile still found no justified route.")
        self.assertTrue(finished["ok"], finished)


    def test_refresh_same_facts_new_timestamp_does_not_stale_plan(self):
        planned = self._set_plan()
        self.assertTrue(planned["ok"], planned)
        refreshed = self.store.refresh_incumbent_result(
            {
                "alpha_id": "ROOT",
                "metrics": {"SHARPE": 2.0, "FITNESS": 1.5, "TURNOVER": 0.2},
                "checks": [{"name": "LOW_SHARPE", "status": "FAIL"}],
                "observed_at": "2026-09-21T00:05:00Z",
                "source": "BRAIN:get_submission_check",
                "response_complete": True,
                "authenticated": True,
            }
        )
        self.assertTrue(refreshed["ok"], refreshed)
        self.assertFalse(refreshed["facts_changed"], refreshed)
        self.assertEqual(refreshed["plan_status"], "ACTIVE")
        self.assertEqual(self.store.read()["optimization_plan"]["status"], "ACTIVE")


    def test_pre_v33_check_rows_keep_initialize_idempotent(self):
        state = self.store.read()
        for snapshot_key in ("root_baseline", "incumbent"):
            for row in state[snapshot_key]["result_evidence"]["checks"]:
                row.pop("policy_classified", None)
        self.store.path.write_text(__import__("json").dumps(state), encoding="utf-8")

        again = self.store.initialize(
            {
                "alpha_id": "ROOT",
                "expression": "rank(close)",
                "fields": ["close"],
                "settings": {
                    "language": "FASTEXPR",
                    "region": "GBR",
                    "delay": 0,
                    "universe": "TOP700",
                    "instrumentType": "EQUITY",
                    "decay": 5,
                    "truncation": 0.08,
                },
                "language": "FASTEXPR",
                "result_evidence": {
                    "metrics": {"SHARPE": 2.0, "FITNESS": 1.5, "TURNOVER": 0.2},
                    "checks": [{"name": "LOW_SHARPE", "status": "FAIL"}],
                    "observed_at": "2026-09-21T00:00:00Z",
                    "source": "BRAIN:test",
                    "response_complete": True,
                    "authenticated": True,
                },
            }
        )
        self.assertTrue(again["initialized"], again)
        self.assertTrue(again["already_initialized"], again)


    def test_enhancement_requires_resolved_current_checks(self):
        unresolved_store = guard.StateStore(Path(self.tempdir.name) / "enh-unresolved.json", "ENH1")
        self._initialize(
            unresolved_store,
            checks=[{"name": "PROJECT_WARNING", "status": "WARNING"}],
        )
        self._register(
            unresolved_store,
            "E1",
            "DIAGNOSTIC",
            "ENHANCEMENT",
            "BRAIN:test",
            "A same-thesis enhancement opportunity is supported by current diagnostics.",
        )
        plan = self._set_plan(unresolved_store)
        self.assertTrue(plan["ok"], plan)
        blocked = unresolved_store.set_focus(
            "ENHANCEMENT",
            "optimization/sharpe.md",
            "SHARPE",
            ["E1"],
            route_id="R1",
        )
        self.assertEqual(blocked["reason"], "ENHANCEMENT_REQUIRES_RESOLVED_CHECKS")

        classified_store = guard.StateStore(Path(self.tempdir.name) / "enh-classified.json", "ENH2")
        self._initialize(
            classified_store,
            checks=[
                {
                    "name": "PROJECT_WARNING",
                    "status": "WARNING",
                    "policy_classified": True,
                    "policy_blocking": False,
                }
            ],
        )
        self._register(
            classified_store,
            "E1",
            "DIAGNOSTIC",
            "ENHANCEMENT",
            "BRAIN:test",
            "A same-thesis enhancement opportunity is supported by current diagnostics.",
        )
        plan2 = self._set_plan(classified_store)
        self.assertTrue(plan2["ok"], plan2)
        opened = classified_store.set_focus(
            "ENHANCEMENT",
            "optimization/sharpe.md",
            "SHARPE",
            ["E1"],
            route_id="R1",
        )
        self.assertTrue(opened["ok"], opened)


    def test_new_unresolved_check_makes_candidate_inconclusive(self):
        self.assertTrue(self._set_plan()["ok"])
        self._open_focus()
        self._open_hypothesis()
        candidate = self._candidate()
        reserved = self.store.reserve_simulation(candidate)
        fp = reserved["fingerprint"]
        self.assertTrue(self.store.record_transport(fp, "POSTED", "SIM-WARNING")["ok"])
        result = self.store.evaluate_result(
            candidate,
            {
                "alpha_id": "CHILD-WARNING",
                "simulation_id": "SIM-WARNING",
                "observed_at": guard._now_iso(),
                "source": "BRAIN:get_submission_check",
                "response_complete": True,
                "authenticated": True,
                "metrics": {"SHARPE": 2.1, "FITNESS": 1.5, "TURNOVER": 0.2},
                "checks": [
                    {"name": "LOW_SHARPE", "status": "FAIL"},
                    {"name": "NEW_PROJECT_WARNING", "status": "WARNING"},
                ],
            },
        )
        self.assertEqual(result["status"], "INCONCLUSIVE", result)
        self.assertIn("NEW_PROJECT_WARNING", result["evaluation"]["new_unresolved_checks"])


    def test_normal_completion_requires_initialized_state_but_forced_stop_does_not(self):
        raw_store = guard.StateStore(Path(self.tempdir.name) / "uninitialized.json", "RAW")
        success = raw_store.finish_run("SUCCESS", "Cannot succeed before Root initialization.")
        self.assertEqual(success["reason"], "STATE_NOT_INITIALIZED")
        forced = raw_store.finish_run("PLATFORM_UNRECOVERABLE", "Platform failed before Root intake completed.")
        self.assertTrue(forced["ok"], forced)


    def test_directional_improvement_can_promote_while_target_check_still_fails(self):
        self.assertTrue(self._set_plan()["ok"])
        self._open_focus()
        self._open_hypothesis()
        candidate = self._candidate()
        reserved = self.store.reserve_simulation(candidate)
        fp = reserved["fingerprint"]
        self.assertTrue(self.store.record_transport(fp, "POSTED", "SIM-PROGRESS")["ok"])
        result = self.store.evaluate_result(
            candidate,
            {
                "alpha_id": "CHILD-PROGRESS",
                "simulation_id": "SIM-PROGRESS",
                "observed_at": guard._now_iso(),
                "source": "BRAIN:test",
                "response_complete": True,
                "authenticated": True,
                "metrics": {"SHARPE": 2.1, "FITNESS": 1.55, "TURNOVER": 0.2},
                "checks": [{"name": "LOW_SHARPE", "status": "FAIL"}],
            },
        )
        self.assertEqual(result["status"], "SUPPORTED", result)
        promoted = self.store.promote(candidate)
        self.assertTrue(promoted["promoted"], promoted)
        state = self.store.read()
        self.assertEqual(state["incumbent"]["alpha_id"], "CHILD-PROGRESS")
        self.assertEqual(state["incumbent"]["result_evidence"]["checks"][0]["status"], "FAIL")
        self.assertEqual(state["optimization_plan"]["status"], "STALE")
        log_text = Path(state["run"]["log_path"]).read_text(encoding="utf-8")
        self.assertIn("**Current Incumbent:** CHILD-PROGRESS", log_text)
        self.assertIn("### Optimization Progression", log_text)

    def test_refuted_payload_does_not_automatically_exhaust_mechanism_route(self):
        self.assertTrue(self._set_plan()["ok"])
        self._open_focus()
        self._open_hypothesis()
        candidate = self._candidate()
        reserved = self.store.reserve_simulation(candidate)
        fp = reserved["fingerprint"]
        self.assertTrue(self.store.record_transport(fp, "POSTED", "SIM-REFUTED")["ok"])
        result = self.store.evaluate_result(
            candidate,
            {
                "alpha_id": "CHILD-REFUTED",
                "simulation_id": "SIM-REFUTED",
                "observed_at": guard._now_iso(),
                "source": "BRAIN:test",
                "response_complete": True,
                "authenticated": True,
                "metrics": {"SHARPE": 1.9, "FITNESS": 1.4, "TURNOVER": 0.2},
                "checks": [{"name": "LOW_SHARPE", "status": "FAIL"}],
            },
        )
        self.assertEqual(result["status"], "REFUTED", result)
        state = self.store.read()
        self.assertEqual(state["focus"]["status"], "OPEN")
        self.assertEqual(state["optimization_plan"]["routes"][0]["status"], "ACTIVE")

    def test_dashboard_is_rendered_at_top_and_writes_svg_visualization(self):
        updated = self.store.update_dashboard(
            {
                "fields": [
                    {
                        "name": "close",
                        "type": "MATRIX",
                        "dataset": "pv1",
                        "coverage": 1.0,
                        "dateCoverage": 1.0,
                        "description": "Closing price",
                    }
                ],
                "visualization": {
                    "alpha_id": "ROOT-VIS",
                    "control": "same expression/settings; visualization=true",
                    "recordsets": ["pnl", "sharpe-by-capitalization"],
                    "summary": ["Capitalization buckets show dispersion."],
                    "charts": [
                        {
                            "id": "cap-sharpe",
                            "title": "Sharpe by capitalization bucket",
                            "type": "bar",
                            "labels": ["0-20", "20-40", "40-60", "60-80", "80-100"],
                            "values": [1.28, 1.45, 0.35, 0.78, -0.22],
                        }
                    ],
                },
            }
        )
        self.assertTrue(updated["ok"], updated)
        log_path = Path(updated["log_path"])
        text = log_path.read_text(encoding="utf-8")
        self.assertIn("## Alpha Snapshot / Dashboard", text)
        self.assertIn("### 1. Expression + Settings", text)
        self.assertIn("### 2. Result", text)
        self.assertIn("### 3. Field Information", text)
        self.assertIn("### 4. Visualization / Diagnostics", text)
        self.assertIn("Closing price", text)
        self.assertIn("![Sharpe by capitalization bucket](assets/", text)
        self.assertLess(text.index("## Alpha Snapshot / Dashboard"), text.index("## Audit Trail"))
        charts = self.store.read()["dashboard_context"]["visualization"]["charts"]
        asset = log_path.parent / charts[0]["asset"]
        self.assertTrue(asset.exists())
        self.assertIn("<svg", asset.read_text(encoding="utf-8"))

    def test_stale_concurrent_state_write_is_rejected_without_data_loss(self):
        first = self.store.read()
        stale = self.store.read()

        first.setdefault("log_entries", []).append(
            {"section": "A", "text": "first writer", "at": guard._now_iso()}
        )
        self.store._write(first)

        stale.setdefault("log_entries", []).append(
            {"section": "B", "text": "stale writer", "at": guard._now_iso()}
        )
        with self.assertRaisesRegex(ValueError, "STATE_WRITE_CONFLICT"):
            self.store._write(stale)

        current = self.store.read()
        texts = [entry.get("text") for entry in current.get("log_entries", [])]
        self.assertIn("first writer", texts)
        self.assertNotIn("stale writer", texts)


if __name__ == "__main__":
    main()

import json
import sys
import tempfile
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import optimizer_guard as guard  # noqa: E402


class PlanningGuardTests(TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        self.logs = root / "logs"
        self.state_path = root / "state.json"
        self.patches = patch.multiple(guard, LOGS_DIR=self.logs, STATE_DIR=self.logs / ".state")
        self.patches.start()
        self.store = guard.StateStore(self.state_path, "ROOT")
        self.store.initialize(
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
                },
                "language": "FASTEXPR",
                "result_evidence": {
                    "metrics": {"SHARPE": 2.0, "FITNESS": 1.5},
                    "checks": [{"name": "LOW_SHARPE", "status": "FAIL"}],
                    "observed_at": "2026-09-21T00:00:00Z",
                    "source": "BRAIN:test",
                    "response_complete": True,
                    "authenticated": True,
                },
            }
        )
        self._evidence("E1", "LOW_SHARPE", "BRAIN:test", "Current LOW_SHARPE failure supports a signal-quality route.")
        self._evidence("E2", "LOW_SUB_UNIVERSE_SHARPE", "BRAIN:test", "Sub-universe evidence supports a breadth route.")

    def tearDown(self):
        self.patches.stop()
        self.tempdir.cleanup()

    def _evidence(self, evidence_id, subject, source, claim):
        result = self.store.register_evidence(
            {
                "id": evidence_id,
                "kind": "DIAGNOSTIC",
                "subject": subject,
                "source": source,
                "observed_at": "2026-09-21T00:01:00Z",
                "claim": claim,
            }
        )
        self.assertTrue(result["ok"], result)

    def _plan(self, *routes):
        return {
            "based_on_evidence_revision": 2,
            "routes": [
                {
                    "id": route_id,
                    "target": target,
                    "owner": owner,
                    "mechanism": mechanism,
                    "evidence_refs": refs,
                    "rationale": rationale,
                }
                for route_id, target, owner, mechanism, refs, rationale in routes
            ],
        }

    def _open_focus(self, route_id="R1", target="SHARPE", owner="optimization/sharpe.md", evidence="E1", blocker="LOW_SHARPE"):
        result = self.store.set_focus(
            "DEFECT",
            owner,
            target,
            [evidence],
            blocker=blocker,
            route_id=route_id,
        )
        self.assertTrue(result["ok"], result)

    def _hypothesis_contract(self, target="SHARPE", evidence_refs=None, mechanism="signal_quality"):
        return {
            "target": target,
            "mechanism": mechanism,
            "principal_hypothesis": "A sign-preserving expression change improves the active target.",
            "mutation": {"type": "expression"},
            "success_criteria": [{"type": "metric", "name": target, "direction": "higher", "min_change": 0}],
            "protected_metrics": [{"name": "SHARPE", "rule": "not_lower", "tolerance": 0}],
            "failure_meaning": "The expression route is not supported if the target does not improve.",
            "evidence_refs": list(evidence_refs or ["E1"]),
            "complexity_reason": "The declared expression mutation is the single tested mechanism.",
        }

    def _promote_current_plan(self, target="SHARPE", evidence="E1", child_id="CHILD", expression="rank(-close)"):
        mechanism = (self.store.read().get("focus") or {}).get("mechanism") or "signal_quality"
        opened = self.store.open_hypothesis("H1", self._hypothesis_contract(target, [evidence], mechanism=mechanism))
        self.assertTrue(opened["ok"], opened)
        candidate = {
            "parent_id": self.store.read()["incumbent"]["alpha_id"],
            "hypothesis_id": "H1",
            "expression": expression,
            "fields": ["close"],
            "settings": self.store.read()["incumbent"]["settings"],
            "language": "FASTEXPR",
        }
        reserved = self.store.reserve_simulation(candidate)
        self.assertTrue(reserved["allowed"], reserved)
        fingerprint = reserved["fingerprint"]
        self.assertTrue(self.store.record_transport(fingerprint, "POSTED", f"SIM-{child_id}")["ok"])
        evaluated = self.store.evaluate_result(
            candidate,
            {
                "alpha_id": child_id,
                "simulation_id": f"SIM-{child_id}",
                "observed_at": guard._now_iso(),
                "source": "BRAIN:test",
                "response_complete": True,
                "authenticated": True,
                "metrics": {"SHARPE": 2.1},
                "checks": [{"name": "LOW_SHARPE", "status": "FAIL"}],
            },
        )
        self.assertEqual(evaluated["status"], "SUPPORTED", evaluated)
        promoted = self.store.promote(candidate)
        self.assertTrue(promoted["promoted"], promoted)
        return candidate

    def test_plan_has_multiple_routes_with_one_active(self):
        result = self.store.set_plan(
            self._plan(
                ("R1", "SHARPE", "optimization/sharpe.md", "signal_quality", ["E1"], "The current blocker points to signal quality."),
                ("R2", "LOW_SUB_UNIVERSE_SHARPE", "optimization/subuniverse.md", "breadth_robustness", ["E2"], "The sub-universe evidence supports a separate breadth route."),
            )
        )
        self.assertTrue(result["ok"], result)
        routes = result["plan"]["routes"]
        self.assertEqual([route["status"] for route in routes], ["ACTIVE", "PENDING"])

    def test_exhausting_focus_activates_pending_route_without_finishing_run(self):
        self.store.set_plan(
            self._plan(
                ("R1", "SHARPE", "optimization/sharpe.md", "signal_quality", ["E1"], "Signal evidence supports the first route."),
                ("R2", "LOW_SUB_UNIVERSE_SHARPE", "optimization/subuniverse.md", "breadth_robustness", ["E2"], "Breadth evidence supports the second route."),
            )
        )
        self._open_focus()
        result = self.store.exhaust_focus("R1 has no remaining falsifiable question.")
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["next_route"]["id"], "R2")
        state = self.store.read()
        self.assertEqual(state["optimization_plan"]["routes"][0]["status"], "EXHAUSTED")
        self.assertEqual(state["optimization_plan"]["routes"][1]["status"], "ACTIVE")
        self.assertEqual(state["run"]["status"], "RUNNING")

    def test_exhaustion_requires_final_replan_before_finish(self):
        self.store.set_plan(
            self._plan(("R1", "SHARPE", "optimization/sharpe.md", "signal_quality", ["E1"], "Signal evidence supports the route."))
        )
        self._open_focus()
        self.store.exhaust_focus("R1 exhausted.")
        blocked = self.store.finish_run("COMPLETED_WITH_EXHAUSTION", "No more routes.")
        self.assertEqual(blocked["reason"], "FINAL_REPLAN_REQUIRED")
        replan = self.store.set_plan({"routes": []}, final_replan=True)
        self.assertTrue(replan["ok"], replan)
        finished = self.store.finish_run("COMPLETED_WITH_EXHAUSTION", "Final re-plan found no justified route.")
        self.assertTrue(finished["ok"], finished)
        self.assertIn("Status: `COMPLETED_WITH_EXHAUSTION`", Path(finished["run"]["log_path"]).read_text())

    def test_final_replan_can_be_used_only_once(self):
        self.store.set_plan(
            self._plan(("R1", "SHARPE", "optimization/sharpe.md", "signal_quality", ["E1"], "Signal evidence supports the route."))
        )
        self._open_focus()
        self.store.exhaust_focus("R1 exhausted.")
        self.assertTrue(self.store.set_plan({"routes": []}, final_replan=True)["ok"])
        result = self.store.set_plan({"routes": []}, final_replan=True)
        self.assertEqual(result["reason"], "FINAL_REPLAN_ALREADY_USED")

    def test_promotion_marks_plan_stale(self):
        self.store.set_plan(
            self._plan(("R1", "SHARPE", "optimization/sharpe.md", "signal_quality", ["E1"], "Signal evidence supports the route."))
        )
        self._open_focus()
        contract = {
            "target": "SHARPE",
            "mechanism": "signal_quality",
            "principal_hypothesis": "A sign-preserving expression change improves signal quality.",
            "mutation": {"type": "expression"},
            "success_criteria": [{"type": "metric", "name": "SHARPE", "direction": "higher", "min_change": 0}],
            "protected_metrics": [{"name": "SHARPE", "rule": "not_lower", "tolerance": 0}],
            "failure_meaning": "The expression route is not supported if Sharpe does not improve.",
            "evidence_refs": ["E1"],
            "complexity_reason": "The unary sign operation is the single declared signal-quality mechanism.",
        }
        opened = self.store.open_hypothesis("H1", contract)
        self.assertTrue(opened["ok"], opened)
        candidate = {
            "parent_id": "ROOT",
            "hypothesis_id": "H1",
            "expression": "rank(-close)",
            "fields": ["close"],
            "settings": self.store.read()["incumbent"]["settings"],
            "language": "FASTEXPR",
        }
        reserved = self.store.reserve_simulation(candidate)
        self.assertTrue(reserved["allowed"], reserved)
        fingerprint = reserved["fingerprint"]
        self.assertTrue(self.store.record_transport(fingerprint, "POSTED", "SIM-1")["ok"])
        evaluated = self.store.evaluate_result(
            candidate,
            {
                "alpha_id": "CHILD",
                "simulation_id": "SIM-1",
                "observed_at": guard._now_iso(),
                "source": "BRAIN:test",
                "response_complete": True,
                "authenticated": True,
                "metrics": {"SHARPE": 2.1},
                "checks": [{"name": "LOW_SHARPE", "status": "FAIL"}],
            },
        )
        self.assertEqual(evaluated["status"], "SUPPORTED", evaluated)
        promoted = self.store.promote(candidate)
        self.assertTrue(promoted["promoted"], promoted)
        self.assertEqual(self.store.read()["optimization_plan"]["status"], "STALE")

    def test_route_requires_registered_evidence(self):
        result = self.store.set_plan(
            {
                "routes": [
                    {
                        "id": "R1",
                        "target": "SHARPE",
                        "owner": "optimization/sharpe.md",
                        "mechanism": "signal_quality",
                        "evidence_refs": ["NOT_REGISTERED"],
                        "rationale": "This route is intentionally invalid.",
                    }
                ]
            }
        )
        self.assertEqual(result["reason"], "UNKNOWN_EVIDENCE_REF")

    def test_legacy_candidate_safety_still_rejects_parent_drift(self):
        self.store.set_plan(
            self._plan(("R1", "SHARPE", "optimization/sharpe.md", "signal_quality", ["E1"], "Signal evidence supports the route."))
        )
        self._open_focus()
        opened = self.store.open_hypothesis(
            "H1",
            {
                "target": "SHARPE",
                "mechanism": "signal_quality",
                "principal_hypothesis": "Test parent binding.",
                "mutation": {"type": "expression"},
                "success_criteria": [{"type": "metric", "name": "SHARPE", "direction": "higher"}],
                "protected_metrics": [{"name": "SHARPE", "rule": "not_lower", "tolerance": 0}],
                "failure_meaning": "Parent drift is rejected.",
                "evidence_refs": ["E1"],
            },
        )
        self.assertTrue(opened["ok"], opened)
        result = guard.preflight_candidate(
            {
                "parent_id": "NOT_ROOT",
                "hypothesis_id": "H1",
                "expression": "rank(close)",
                "fields": ["close"],
                "settings": self.store.read()["incumbent"]["settings"],
                "language": "FASTEXPR",
            },
            self.store.read(),
            require_open_hypothesis=True,
        )
        self.assertEqual(result["reject_code"], "PARENT_NOT_CURRENT_INCUMBENT")

    def test_real_run_shape_continues_after_exhausted_focus(self):
        self.store = guard.StateStore(Path(self.tempdir.name) / "real-state.json", "O0Nq51jR")
        self.store.initialize(
            {
                "alpha_id": "O0Nq51jR",
                "expression": "ts_mean(mdl242_1mt, 10)",
                "fields": ["mdl242_1mt"],
                "settings": {"language": "FASTEXPR", "region": "GBR", "delay": 0, "universe": "TOP700", "instrumentType": "EQUITY"},
                "language": "FASTEXPR",
                "result_evidence": {"metrics": {"SHARPE": 2.06}, "checks": [{"name": "LOW_SUB_UNIVERSE_SHARPE", "status": "FAIL"}], "observed_at": "2026-09-21T00:00:00Z", "source": "BRAIN:get_alpha_details", "response_complete": True, "authenticated": True},
            }
        )
        self.assertTrue(self.store.register_evidence({"id": "E_ROOT", "kind": "DIAGNOSTIC", "subject": "LOW_SUB_UNIVERSE_SHARPE", "source": "BRAIN:get_submission_check", "observed_at": "2026-09-21T00:01:00Z", "claim": "The real O0Nq51jR run has a current sub-universe blocker."})["ok"])
        self.assertTrue(self.store.register_evidence({"id": "E_NEXT", "kind": "DIAGNOSTIC", "subject": "TAIL", "source": "BRAIN:get_record_set_data", "observed_at": "2026-09-21T00:02:00Z", "claim": "The real run later recorded a distinct tail observation."})["ok"])
        self.assertTrue(self.store.set_plan(self._plan(("R1", "LOW_SUB_UNIVERSE_SHARPE", "optimization/subuniverse.md", "breadth_robustness", ["E_ROOT"], "The blocker supports a breadth route."), ("R2", "SHARPE", "optimization/sharpe.md", "tail_robustness", ["E_NEXT"], "The later observation supports a separate tail route.")))["ok"])
        self._open_focus(route_id="R1", target="LOW_SUB_UNIVERSE_SHARPE", owner="optimization/subuniverse.md", evidence="E_ROOT", blocker="LOW_SUB_UNIVERSE_SHARPE")
        result = self.store.exhaust_focus("The first focus is exhausted; the next route remains justified.")
        self.assertEqual(result["next_route"]["id"], "R2")
        self.assertNotEqual(self.store.read().get("run", {}).get("status"), "COMPLETED_WITH_EXHAUSTION")

    def test_stale_plan_rejects_old_focus_until_fresh_plan(self):
        self.store.set_plan(self._plan(("R1", "SHARPE", "optimization/sharpe.md", "signal_quality", ["E1"], "Signal evidence supports the route.")))
        self._open_focus()
        self._promote_current_plan()

        rejected = self.store.set_focus("DEFECT", "optimization/sharpe.md", "SHARPE", ["E1"], blocker="LOW_SHARPE", route_id="R1")
        self.assertEqual(rejected["reason"], "PLAN_STALE_REPLAN_REQUIRED")
        bypass_hypothesis = self.store.open_hypothesis("H_STALE", self._hypothesis_contract())
        self.assertEqual(bypass_hypothesis["reason"], "PLAN_STALE_REPLAN_REQUIRED")
        bypass_candidate = {
            "parent_id": self.store.read()["incumbent"]["alpha_id"],
            "hypothesis_id": "H1",
            "expression": "rank(close)",
            "fields": ["close"],
            "settings": self.store.read()["incumbent"]["settings"],
            "language": "FASTEXPR",
        }
        bypass_simulation = self.store.reserve_simulation(bypass_candidate)
        self.assertEqual(bypass_simulation["reason"], "PLAN_STALE_REPLAN_REQUIRED")

        fresh = self.store.set_plan(self._plan(("R2", "SHARPE", "optimization/sharpe.md", "signal_quality_next", ["E1"], "The new incumbent needs a fresh route.")))
        self.assertTrue(fresh["ok"], fresh)
        reopened = self.store.set_focus("DEFECT", "optimization/sharpe.md", "SHARPE", ["E1"], blocker="LOW_SHARPE", route_id="R2")
        self.assertTrue(reopened["ok"], reopened)

    def test_success_can_finish_after_promotion_stales_plan(self):
        self.store.set_plan(self._plan(("R1", "SHARPE", "optimization/sharpe.md", "signal_quality", ["E1"], "Signal evidence supports the route.")))
        self._open_focus()
        self._promote_current_plan()
        finished = self.store.finish_run("SUCCESS", "Promotion reached the requested objective.")
        self.assertTrue(finished["ok"], finished)
        self.assertEqual(finished["status"], "SUCCESS")

    def test_terminal_run_blocks_research_mutations_but_allows_append_log(self):
        first = self.store.finish_run("SUCCESS", "The run is complete.")
        self.assertTrue(first["ok"], first)

        terminal_calls = [
            self.store.finish_run("SUBMISSION_READY", "A second terminal status is not allowed."),
            self.store.set_plan(self._plan(("R1", "SHARPE", "optimization/sharpe.md", "signal_quality", ["E1"], "Not allowed after finish."))),
            self.store.activate_route("R1"),
            self.store.close_route("R1", "COMPLETED", "Not allowed after finish."),
            self.store.set_focus("DEFECT", "optimization/sharpe.md", "SHARPE", ["E1"], blocker="LOW_SHARPE", route_id="R1"),
            self.store.exhaust_focus("Not allowed after finish."),
            self.store.open_hypothesis("H1", self._hypothesis_contract()),
            self.store.abandon_hypothesis("H1", "E1", "Not allowed after finish."),
            self.store.allow_field("close", "E1"),
            self.store.reserve_simulation({}),
            self.store.record_transport("unknown", "POSTED", "SIM-1"),
            self.store.release_reservation("unknown", "Not allowed after finish."),
            self.store.register_evidence({
                "id": "E3", "kind": "DIAGNOSTIC", "subject": "TERMINAL", "source": "BRAIN:test",
                "observed_at": "2026-09-21T00:03:00Z", "claim": "This evidence must not be registered after termination.",
            }),
            self.store.evaluate_result({}, {}),
            self.store.promote({}),
        ]
        for result in terminal_calls:
            self.assertEqual(result["reason"], "RUN_ALREADY_TERMINAL", result)

        note = self.store.append_log("FINAL", "A final human note remains append-only.")
        self.assertTrue(note["ok"], note)
        self.assertEqual(self.store.read()["run"]["status"], "SUCCESS")

    def test_hypothesis_target_must_match_active_route_target(self):
        self.store.set_plan(self._plan(("R1", "SHARPE", "optimization/sharpe.md", "signal_quality", ["E1"], "Signal evidence supports the route.")))
        self._open_focus()
        rejected = self.store.open_hypothesis("H_BAD", self._hypothesis_contract("TURNOVER"))
        self.assertEqual(rejected["reason"], "HYPOTHESIS_TARGET_MISMATCH")
        accepted = self.store.open_hypothesis("H_GOOD", self._hypothesis_contract("SHARPE"))
        self.assertTrue(accepted["ok"], accepted)

    def test_exact_duplicate_evidence_id_cannot_reopen_exhausted_route(self):
        self.store.set_plan(self._plan(("R1", "SHARPE", "optimization/sharpe.md", "signal_quality", ["E1"], "Signal evidence supports the route.")))
        self._open_focus()
        self.store.exhaust_focus("The route has no remaining falsifiable question.")
        self.assertTrue(self.store.register_evidence({
            "id": "E_DUP_ID", "kind": "DIAGNOSTIC", "subject": "LOW_SHARPE", "source": "BRAIN:test",
            "observed_at": "2026-09-21T00:01:00Z", "claim": "Current LOW_SHARPE failure supports a signal-quality route.",
        })["ok"])
        plan = self._plan(("R1_REOPEN", "SHARPE", "optimization/sharpe.md", "signal_quality", ["E1"], "The same fact was re-registered."))
        plan["routes"][0]["reopen_reason"] = "A new evidence ID was observed."
        plan["routes"][0]["new_observation_refs"] = ["E_DUP_ID"]
        plan["based_on_evidence_revision"] = 3
        rejected = self.store.set_plan(plan, final_replan=True)
        self.assertEqual(rejected["reason"], "ROUTE_NEW_OBSERVATION_NOT_NOVEL")

    def test_timestamp_only_duplicate_evidence_cannot_reopen_exhausted_route(self):
        self.store.set_plan(self._plan(("R1", "SHARPE", "optimization/sharpe.md", "signal_quality", ["E1"], "Signal evidence supports the route.")))
        self._open_focus()
        self.store.exhaust_focus("The route has no remaining falsifiable question.")
        self.assertTrue(self.store.register_evidence({
            "id": "E_DUP_TIME", "kind": "DIAGNOSTIC", "subject": "LOW_SHARPE", "source": "BRAIN:test",
            "observed_at": "2026-09-21T00:02:00Z", "claim": "Current LOW_SHARPE failure supports a signal-quality route.",
        })["ok"])
        plan = self._plan(("R1_REOPEN", "SHARPE", "optimization/sharpe.md", "signal_quality", ["E1"], "Only the timestamp changed."))
        plan["routes"][0]["reopen_reason"] = "The same observation was timestamped again."
        plan["routes"][0]["new_observation_refs"] = ["E_DUP_TIME"]
        plan["based_on_evidence_revision"] = 3
        rejected = self.store.set_plan(plan, final_replan=True)
        self.assertEqual(rejected["reason"], "ROUTE_NEW_OBSERVATION_NOT_NOVEL")

    def test_genuinely_new_evidence_can_reopen_exhausted_route(self):
        self.store.set_plan(self._plan(("R1", "SHARPE", "optimization/sharpe.md", "signal_quality", ["E1"], "Signal evidence supports the route.")))
        self._open_focus()
        self.store.exhaust_focus("The route has no remaining falsifiable question.")
        self.assertTrue(self.store.register_evidence({
            "id": "E_NEW", "kind": "DIAGNOSTIC", "subject": "TAIL", "source": "BRAIN:get_record_set_data",
            "observed_at": "2026-09-21T00:02:00Z", "claim": "A distinct tail observation supports a new route question.",
        })["ok"])
        plan = self._plan(("R1_REOPEN", "SHARPE", "optimization/sharpe.md", "signal_quality", ["E1"], "The new tail evidence changes the falsifiable question."))
        plan["routes"][0]["reopen_reason"] = "A distinct tail observation was registered after exhaustion."
        plan["routes"][0]["new_observation_refs"] = ["E_NEW"]
        plan["based_on_evidence_revision"] = 3
        reopened = self.store.set_plan(plan, final_replan=True)
        self.assertTrue(reopened["ok"], reopened)

    def test_final_replan_resets_for_new_incumbent_cycle(self):
        self.store.set_plan(self._plan(("R1", "SHARPE", "optimization/sharpe.md", "signal_quality", ["E1"], "Signal evidence supports the route.")))
        self._open_focus()
        self.store.exhaust_focus("The first route is exhausted.")
        self.assertTrue(self.store.register_evidence({
            "id": "E_CYCLE", "kind": "DIAGNOSTIC", "subject": "TAIL", "source": "BRAIN:get_record_set_data",
            "observed_at": "2026-09-21T00:02:00Z", "claim": "A distinct tail observation supports the final re-plan route.",
        })["ok"])
        cycle_plan = self._plan(("R2", "SHARPE", "optimization/sharpe.md", "signal_quality_confirmation", ["E_CYCLE"], "The final re-plan has one justified route."))
        cycle_plan["based_on_evidence_revision"] = 3
        self.assertTrue(self.store.set_plan(cycle_plan, final_replan=True)["ok"])
        self._open_focus(route_id="R2", evidence="E_CYCLE")
        self._promote_current_plan(evidence="E_CYCLE", child_id="CHILD_B")

        fresh = self.store.set_plan(self._plan(("R3", "SHARPE", "optimization/sharpe.md", "new_incumbent_cycle", ["E1"], "The new incumbent starts a fresh planning cycle.")))
        self.assertTrue(fresh["ok"], fresh)
        self.assertFalse(fresh["plan"]["final_replan_used"])
        self._open_focus(route_id="R3")
        self.store.exhaust_focus("The new incumbent route is exhausted.")
        one_more = self.store.set_plan({"routes": []}, final_replan=True)
        self.assertTrue(one_more["ok"], one_more)

    def test_legacy_set_plan_upgrades_to_v1_binding(self):
        legacy = self.store.read()
        legacy.pop("planning_contract", None)
        legacy.pop("optimization_plan", None)
        legacy.pop("optimization_plan_history", None)
        self.store.path.write_text(json.dumps(legacy), encoding="utf-8")
        self.assertEqual(self.store.read()["planning_contract"], "legacy")

        installed = self.store.set_plan(self._plan(("R1", "SHARPE", "optimization/sharpe.md", "signal_quality", ["E1"], "Signal evidence supports the route.")))
        self.assertTrue(installed["ok"], installed)
        self.assertEqual(self.store.read()["planning_contract"], "v1")
        rejected = self.store.set_focus("DEFECT", "optimization/turnover.md", "TURNOVER", ["E1"], blocker="LOW_SHARPE", route_id="R1")
        self.assertEqual(rejected["reason"], "ROUTE_FOCUS_MISMATCH")

    def test_plan_rejects_evidence_newer_than_declared_revision(self):
        plan = self._plan(("R1", "SHARPE", "optimization/sharpe.md", "signal_quality", ["E1"], "The plan cites evidence registered at revision one."))
        plan["based_on_evidence_revision"] = 0
        rejected = self.store.set_plan(plan)
        self.assertEqual(rejected["reason"], "PLAN_EVIDENCE_REVISION_MISMATCH")


    def test_new_incumbent_can_install_empty_plan_then_final_replan(self):
        self.store.set_plan(
            self._plan(
                ("R1", "SHARPE", "optimization/sharpe.md", "signal_quality", ["E1"], "Signal evidence supports the route.")
            )
        )
        self._open_focus()
        self._promote_current_plan(child_id="CHILD_EMPTY_PLAN")

        fresh = self.store.set_plan({"routes": []})
        self.assertTrue(fresh["ok"], fresh)
        self.assertEqual(fresh["plan"]["status"], "EXHAUSTED")
        self.assertEqual(fresh["plan"]["incumbent_alpha_id"], "CHILD_EMPTY_PLAN")
        self.assertFalse(fresh["plan"]["final_replan_used"])
        self.assertEqual(fresh["plan"]["routes"], [])

        blocked = self.store.finish_run(
            "COMPLETED_WITH_EXHAUSTION",
            "The fresh incumbent has no justified normal route.",
        )
        self.assertEqual(blocked["reason"], "FINAL_REPLAN_REQUIRED")

        final_replan = self.store.set_plan({"routes": []}, final_replan=True)
        self.assertTrue(final_replan["ok"], final_replan)
        self.assertTrue(final_replan["plan"]["final_replan_used"])

        finished = self.store.finish_run(
            "COMPLETED_WITH_EXHAUSTION",
            "The mandatory final re-plan also found no justified route.",
        )
        self.assertTrue(finished["ok"], finished)



    def test_initial_empty_plan_can_reach_exhaustion_without_fabricated_route(self):
        empty = self.store.set_plan({"routes": []})
        self.assertTrue(empty["ok"], empty)
        self.assertEqual(empty["plan"]["status"], "EXHAUSTED")
        self.assertEqual(empty["plan"]["routes"], [])
        blocked = self.store.finish_run("COMPLETED_WITH_EXHAUSTION", "No justified normal route exists.")
        self.assertEqual(blocked["reason"], "FINAL_REPLAN_REQUIRED")
        final_replan = self.store.set_plan({"routes": []}, final_replan=True)
        self.assertTrue(final_replan["ok"], final_replan)
        finished = self.store.finish_run("COMPLETED_WITH_EXHAUSTION", "Final re-plan found no justified route.")
        self.assertTrue(finished["ok"], finished)

    def test_hypothesis_mechanism_must_match_active_route(self):
        self.store.set_plan(
            self._plan(
                ("R1", "SHARPE", "optimization/sharpe.md", "signal_quality", ["E1"], "Signal evidence supports the route.")
            )
        )
        self._open_focus()
        rejected = self.store.open_hypothesis(
            "H_BAD_MECH",
            self._hypothesis_contract("SHARPE", ["E1"], mechanism="tail_robustness"),
        )
        self.assertEqual(rejected["reason"], "HYPOTHESIS_MECHANISM_MISMATCH")
        accepted = self.store.open_hypothesis(
            "H_GOOD_MECH",
            self._hypothesis_contract("SHARPE", ["E1"], mechanism="signal_quality"),
        )
        self.assertTrue(accepted["ok"], accepted)

    def test_route_reopen_history_is_scoped_to_incumbent_cycle(self):
        self.store.set_plan(
            self._plan(
                ("R1", "SHARPE", "optimization/sharpe.md", "signal_quality", ["E1"], "First route."),
                ("R2", "SHARPE", "optimization/sharpe.md", "signal_quality_confirmation", ["E1"], "Second route."),
            )
        )
        closed = self.store.close_route("R1", "COMPLETED", "R1 completed for the old incumbent.")
        self.assertTrue(closed["ok"], closed)
        self._open_focus(route_id="R2")
        self._promote_current_plan(child_id="CHILD_HISTORY")

        fresh = self.store.set_plan(
            self._plan(
                ("R3", "SHARPE", "optimization/sharpe.md", "signal_quality", ["E1"], "The new incumbent may revisit this mechanism.")
            )
        )
        self.assertTrue(fresh["ok"], fresh)
        self.assertEqual(fresh["plan"]["incumbent_alpha_id"], "CHILD_HISTORY")

    def test_legacy_state_requires_plan_before_new_focus_or_hypothesis(self):
        legacy = self.store.read()
        legacy.pop("planning_contract", None)
        legacy.pop("optimization_plan", None)
        legacy.pop("optimization_plan_history", None)
        self.store.path.write_text(json.dumps(legacy), encoding="utf-8")
        self.assertEqual(self.store.read()["planning_contract"], "legacy")

        focus = self.store.set_focus(
            "DEFECT",
            "optimization/sharpe.md",
            "SHARPE",
            ["E1"],
            blocker="LOW_SHARPE",
            route_id="R1",
        )
        self.assertEqual(focus["reason"], "LEGACY_PLAN_REQUIRED")

        # A legacy state with an already-open historical focus may still close it,
        # but it cannot open a new hypothesis until it installs a v1 plan.
        legacy = self.store.read()
        legacy["focus"] = {
            "type": "DEFECT",
            "owner": "optimization/sharpe.md",
            "target": "SHARPE",
            "blocker": "LOW_SHARPE",
            "status": "OPEN",
            "evidence_refs": ["E1"],
            "revision": 1,
        }
        self.store.path.write_text(json.dumps(legacy), encoding="utf-8")
        hyp = self.store.open_hypothesis("H_LEGACY", self._hypothesis_contract())
        self.assertEqual(hyp["reason"], "LEGACY_PLAN_REQUIRED")
        exhausted = self.store.exhaust_focus("Close the historical focus before migration.")
        self.assertTrue(exhausted["ok"], exhausted)


    def test_next_route_same_target_owner_but_different_mechanism_can_open_with_preexisting_evidence(self):
        self.store.set_plan(
            self._plan(
                ("R1", "SHARPE", "optimization/sharpe.md", "signal_quality", ["E1"], "First mechanism."),
                ("R2", "SHARPE", "optimization/sharpe.md", "exposure_control", ["E2"], "Second mechanism."),
            )
        )
        self._open_focus(route_id="R1", target="SHARPE", owner="optimization/sharpe.md", evidence="E1", blocker="LOW_SHARPE")
        exhausted = self.store.exhaust_focus("The signal-quality mechanism is exhausted.")
        self.assertEqual(exhausted["next_route"]["id"], "R2")

        opened = self.store.set_focus(
            "DEFECT",
            "optimization/sharpe.md",
            "SHARPE",
            ["E2"],
            blocker="LOW_SHARPE",
            route_id="R2",
        )
        self.assertTrue(opened["ok"], opened)
        self.assertEqual(opened["focus"]["mechanism"], "exposure_control")

    def test_reopened_route_focus_must_use_reopen_observation(self):
        self.store.set_plan(
            self._plan(
                ("R1", "SHARPE", "optimization/sharpe.md", "signal_quality", ["E1"], "Initial route.")
            )
        )
        self._open_focus()
        self.store.exhaust_focus("Initial route exhausted.")
        self.assertTrue(
            self.store.register_evidence(
                {
                    "id": "E_NOVEL_FOCUS",
                    "kind": "DIAGNOSTIC",
                    "subject": "TAIL",
                    "source": "BRAIN:get_record_set_data",
                    "observed_at": "2026-09-21T00:03:00Z",
                    "claim": "A genuinely new tail observation changes the signal-quality question.",
                }
            )["ok"]
        )
        plan = self._plan(
            ("R1B", "SHARPE", "optimization/sharpe.md", "signal_quality", ["E1", "E_NOVEL_FOCUS"], "Novel evidence justifies reopening.")
        )
        plan["routes"][0]["reopen_reason"] = "A new tail observation appeared after exhaustion."
        plan["routes"][0]["new_observation_refs"] = ["E_NOVEL_FOCUS"]
        plan["based_on_evidence_revision"] = self.store.read()["evidence_revision"]
        reopened = self.store.set_plan(plan, final_replan=True)
        self.assertTrue(reopened["ok"], reopened)

        old_only = self.store.set_focus(
            "DEFECT",
            "optimization/sharpe.md",
            "SHARPE",
            ["E1"],
            blocker="LOW_SHARPE",
            route_id="R1B",
        )
        self.assertEqual(old_only["reason"], "ROUTE_REOPEN_OBSERVATION_MISMATCH")

        grounded = self.store.set_focus(
            "DEFECT",
            "optimization/sharpe.md",
            "SHARPE",
            ["E1", "E_NOVEL_FOCUS"],
            blocker="LOW_SHARPE",
            route_id="R1B",
        )
        self.assertTrue(grounded["ok"], grounded)


if __name__ == "__main__":
    main()

import sys
import tempfile
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import execute_reserved_candidate as executor  # noqa: E402
import optimizer_guard as guard  # noqa: E402


class FakeResponse:
    def __init__(self, status_code, *, location="", text=""):
        self.status_code = status_code
        self.headers = {"Location": location} if location else {}
        self.text = text


class SequenceWQ:
    def __init__(self, submissions, polls, *, checks_complete=True):
        self.submissions = list(submissions)
        self.polls = list(polls)
        self.start_calls = 0
        self.poll_calls = 0
        self.checks_complete = checks_complete

    def _start_simulation(self, session, payload):
        self.start_calls += 1
        item = self.submissions.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def simulate_single(self, session, payload, *, location=None):
        self.poll_calls += 1
        if not location:
            raise AssertionError("executor must never use simulate_single to submit")
        item = self.polls.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def get_result(self, session, alpha_id):
        return {
            "id": alpha_id,
            "type": "REGULAR",
            "regular": {"code": "rank(-close)"},
            "settings": {
                "language": "FASTEXPR",
                "region": "GBR",
                "delay": 0,
                "universe": "TOP700",
                "instrumentType": "EQUITY",
                "decay": 5,
                "truncation": 0.08,
            },
            "is": {
                "sharpe": 2.2,
                "fitness": 1.5,
                "turnover": 0.2,
            },
        }

    def get_submission_check(self, session, alpha_id):
        if not self.checks_complete:
            return {}
        return {
            "is": {
                "checks": [
                    {"name": "LOW_SHARPE", "result": "FAIL", "value": 2.2, "limit": 2.69}
                ]
            }
        }


class ReservedCandidateExecutorTests(TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        self.logs = root / "logs"
        self.state_path = root / "state.json"
        self.patches = patch.multiple(guard, LOGS_DIR=self.logs, STATE_DIR=self.logs / ".state")
        self.patches.start()
        self.store = guard.StateStore(self.state_path, "ROOT")
        initialized = self.store.initialize(
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
                    "observed_at": "2026-09-23T00:00:00Z",
                    "source": "BRAIN:test",
                    "response_complete": True,
                    "authenticated": True,
                },
            }
        )
        self.assertTrue(initialized["initialized"], initialized)
        evidence = self.store.register_evidence(
            {
                "id": "E1",
                "kind": "DIAGNOSTIC",
                "subject": "LOW_SHARPE",
                "source": "BRAIN:test",
                "observed_at": "2026-09-23T00:01:00Z",
                "claim": "Current LOW_SHARPE failure supports one bounded signal-quality probe.",
            }
        )
        self.assertTrue(evidence["ok"], evidence)

        plan = {
            "based_on_evidence_revision": self.store.read()["evidence_revision"],
            "synthesis": {
                "blockers": [
                    {
                        "name": "LOW_SHARPE",
                        "target": "SHARPE",
                        "owner": "optimization/sharpe.md",
                        "observation_refs": ["E1"],
                        "mechanisms": [
                            {
                                "id": "A1",
                                "mechanism": "signal_quality",
                                "method_family": "temporal_aggregation_or_smoothing",
                                "status": "PLAUSIBLE_PROBE",
                                "evidence_refs": ["E1"],
                                "reasoning": "One bounded mechanism probe is justified.",
                                "next_question": "Does the probe improve Sharpe safely?",
                            }
                        ],
                    }
                ]
            },
            "routes": [
                {
                    "id": "R1",
                    "target": "SHARPE",
                    "owner": "optimization/sharpe.md",
                    "mechanism": "signal_quality",
                    "evidence_refs": ["E1"],
                    "assessment_refs": ["A1"],
                    "rationale": "Test one mechanism.",
                }
            ],
        }
        planned = self.store.set_plan(plan)
        self.assertTrue(planned["ok"], planned)
        focus = self.store.set_focus(
            "DEFECT",
            "optimization/sharpe.md",
            "SHARPE",
            ["E1"],
            blocker="LOW_SHARPE",
            route_id="R1",
        )
        self.assertTrue(focus["ok"], focus)
        opened = self.store.open_hypothesis(
            "H1",
            {
                "target": "SHARPE",
                "mechanism": "signal_quality",
                "principal_hypothesis": "The candidate should improve Sharpe without reducing Fitness.",
                "mutation": {"type": "expression"},
                "success_criteria": [
                    {"type": "metric", "name": "SHARPE", "direction": "higher", "min_change": 0.01}
                ],
                "protected_metrics": [
                    {"name": "FITNESS", "rule": "not_lower", "tolerance": 0.0}
                ],
                "failure_meaning": "If Sharpe does not improve safely, this payload does not support the mechanism.",
                "evidence_refs": ["E1"],
                "complexity_reason": "Adds one unary expression operation for the single declared probe.",
            },
        )
        self.assertTrue(opened["ok"], opened)
        self.candidate = {
            "parent_id": "ROOT",
            "hypothesis_id": "H1",
            "expression": "rank(-close)",
            "fields": ["close"],
            "settings": self.store.read()["incumbent"]["settings"],
            "language": "FASTEXPR",
        }
        reserved = self.store.reserve_simulation(self.candidate)
        self.assertTrue(reserved["allowed"], reserved)
        self.fingerprint = reserved["fingerprint"]

    def tearDown(self):
        self.patches.stop()
        self.tempdir.cleanup()

    def test_confirmed_post_polls_evaluates_and_promotes(self):
        wq = SequenceWQ(
            [FakeResponse(201, location="/simulations/S1")],
            [{"status": "done", "alpha_id": "CHILD"}],
        )
        result = executor.execute_reserved_candidate(self.store, wq, object())
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["stage"], "PROMOTED")
        self.assertEqual(wq.start_calls, 1)
        self.assertEqual(wq.poll_calls, 1)

        state = self.store.read()
        self.assertEqual(state["simulations"][self.fingerprint]["status"], "POSTED")
        self.assertEqual(state["simulations"][self.fingerprint]["simulation_id"], "/simulations/S1")
        self.assertEqual(state["candidates"][self.fingerprint]["status"], "PROMOTED")
        self.assertEqual(state["incumbent"]["alpha_id"], "CHILD")

        again = executor.execute_reserved_candidate(self.store, wq, object(), fingerprint=self.fingerprint)
        self.assertTrue(again["ok"], again)
        self.assertEqual(again["stage"], "PROMOTED")
        self.assertTrue(again["idempotent"])
        self.assertEqual(wq.start_calls, 1)
        self.assertEqual(wq.poll_calls, 1)

    def test_submitting_state_never_reposts_without_reconciled_location(self):
        begun = self.store.begin_submission(self.fingerprint)
        self.assertTrue(begun["ok"], begun)
        wq = SequenceWQ([], [])
        result = executor.execute_reserved_candidate(self.store, wq, object())
        self.assertFalse(result["ok"])
        self.assertEqual(result["stage"], "POST_RECONCILIATION_REQUIRED")
        self.assertTrue(result["recovery_required"])
        self.assertEqual(wq.start_calls, 0)
        self.assertEqual(wq.poll_calls, 0)
        self.assertEqual(self.store.read()["simulations"][self.fingerprint]["status"], "SUBMITTING")

    def test_submitting_state_can_attach_reconciled_location_without_repost(self):
        begun = self.store.begin_submission(self.fingerprint)
        self.assertTrue(begun["ok"], begun)
        wq = SequenceWQ([], [{"status": "done", "alpha_id": "CHILD"}])
        result = executor.execute_reserved_candidate(
            self.store,
            wq,
            object(),
            recover_location="/simulations/RECOVERED",
        )
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["stage"], "PROMOTED")
        self.assertEqual(wq.start_calls, 0)
        self.assertEqual(wq.poll_calls, 1)
        self.assertEqual(
            self.store.read()["simulations"][self.fingerprint]["simulation_id"],
            "/simulations/RECOVERED",
        )

    def test_ambiguous_submit_is_recorded_and_second_run_never_reposts(self):
        wq = SequenceWQ([RuntimeError("submission status unknown")], [])
        first = executor.execute_reserved_candidate(self.store, wq, object())
        self.assertFalse(first["ok"])
        self.assertEqual(first["stage"], "AMBIGUOUS_POST")
        self.assertEqual(self.store.read()["simulations"][self.fingerprint]["status"], "AMBIGUOUS_POST")
        self.assertEqual(wq.start_calls, 1)

        second = executor.execute_reserved_candidate(self.store, wq, object())
        self.assertFalse(second["ok"])
        self.assertEqual(second["stage"], "POST_RECONCILIATION_REQUIRED")
        self.assertEqual(wq.start_calls, 1)

    def test_explicit_429_is_resumable_and_next_invocation_can_submit(self):
        wq = SequenceWQ(
            [
                FakeResponse(429, text="rate limited"),
                FakeResponse(201, location="/simulations/S2"),
            ],
            [{"status": "done", "alpha_id": "CHILD"}],
        )
        first = executor.execute_reserved_candidate(self.store, wq, object())
        self.assertFalse(first["ok"])
        self.assertEqual(first["stage"], "HTTP_429")
        self.assertEqual(self.store.read()["simulations"][self.fingerprint]["status"], "HTTP_429")
        self.assertEqual(self.store.read()["simulations"][self.fingerprint]["retry_count"], 1)

        second = executor.execute_reserved_candidate(self.store, wq, object())
        self.assertTrue(second["ok"], second)
        self.assertEqual(second["stage"], "PROMOTED")
        self.assertEqual(wq.start_calls, 2)

    def test_explicit_prepost_rejection_releases_and_abandons_without_fake_result(self):
        wq = SequenceWQ([FakeResponse(400, text="invalid simulation payload")], [])
        result = executor.execute_reserved_candidate(self.store, wq, object())
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["stage"], "NO_POST_INCONCLUSIVE")

        state = self.store.read()
        self.assertEqual(state["simulations"][self.fingerprint]["status"], "RELEASED")
        self.assertEqual(state["hypotheses"]["H1"]["status"], "INCONCLUSIVE")
        self.assertNotIn("result_evaluation", state["candidates"][self.fingerprint])
        self.assertEqual(wq.poll_calls, 0)

    def test_posted_terminal_simulation_error_closes_hypothesis_inconclusive(self):
        wq = SequenceWQ(
            [FakeResponse(201, location="/simulations/S3")],
            [{"status": "error", "error": "platform simulation failed"}],
        )
        result = executor.execute_reserved_candidate(self.store, wq, object())
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["stage"], "POSTED_SIMULATION_INCONCLUSIVE")

        state = self.store.read()
        self.assertEqual(state["simulations"][self.fingerprint]["status"], "POSTED")
        self.assertEqual(state["hypotheses"]["H1"]["status"], "INCONCLUSIVE")
        self.assertEqual(
            state["hypotheses"]["H1"]["result"]["disposition"],
            "POSTED_SIMULATION_FAILURE",
        )
        self.assertNotIn("result_evaluation", state["candidates"][self.fingerprint])

    def test_incomplete_result_checks_leave_posted_candidate_resumable_without_repost(self):
        wq = SequenceWQ(
            [FakeResponse(201, location="/simulations/S4")],
            [
                {"status": "done", "alpha_id": "CHILD"},
                {"status": "done", "alpha_id": "CHILD"},
            ],
            checks_complete=False,
        )
        first = executor.execute_reserved_candidate(self.store, wq, object())
        self.assertFalse(first["ok"])
        self.assertEqual(first["stage"], "RESULT_EVIDENCE_PENDING")
        self.assertEqual(self.store.read()["simulations"][self.fingerprint]["status"], "POSTED")
        self.assertEqual(self.store.read()["hypotheses"]["H1"]["status"], "OPEN")
        self.assertEqual(wq.start_calls, 1)

        wq.checks_complete = True
        second = executor.execute_reserved_candidate(self.store, wq, object())
        self.assertTrue(second["ok"], second)
        self.assertEqual(second["stage"], "PROMOTED")
        self.assertEqual(wq.start_calls, 1)
        self.assertEqual(wq.poll_calls, 2)

    def test_poll_exception_keeps_posted_location_for_safe_resume(self):
        wq = SequenceWQ(
            [FakeResponse(201, location="/simulations/S5")],
            [RuntimeError("temporary polling failure")],
        )
        result = executor.execute_reserved_candidate(self.store, wq, object())
        self.assertFalse(result["ok"])
        self.assertEqual(result["stage"], "POLL_EXCEPTION")
        self.assertTrue(result["resumable"])
        state = self.store.read()
        self.assertEqual(state["simulations"][self.fingerprint]["status"], "POSTED")
        self.assertEqual(state["simulations"][self.fingerprint]["simulation_id"], "/simulations/S5")


    def test_201_without_location_is_ambiguous_and_never_reposted(self):
        wq = SequenceWQ([FakeResponse(201, text="created without Location")], [])
        first = executor.execute_reserved_candidate(self.store, wq, object())
        self.assertFalse(first["ok"])
        self.assertEqual(first["stage"], "AMBIGUOUS_POST")
        self.assertEqual(self.store.read()["simulations"][self.fingerprint]["status"], "AMBIGUOUS_POST")
        self.assertEqual(wq.start_calls, 1)

        second = executor.execute_reserved_candidate(self.store, wq, object())
        self.assertFalse(second["ok"])
        self.assertEqual(second["stage"], "POST_RECONCILIATION_REQUIRED")
        self.assertEqual(wq.start_calls, 1)

    def test_server_5xx_is_ambiguous_not_release_and_retry(self):
        wq = SequenceWQ([FakeResponse(503, text="service unavailable")], [])
        result = executor.execute_reserved_candidate(self.store, wq, object())
        self.assertFalse(result["ok"])
        self.assertEqual(result["stage"], "AMBIGUOUS_POST")
        self.assertTrue(result["recovery_required"])
        self.assertEqual(self.store.read()["simulations"][self.fingerprint]["status"], "AMBIGUOUS_POST")
        self.assertNotEqual(self.store.read()["simulations"][self.fingerprint]["status"], "RELEASED")

    def test_http_429_retry_budget_is_machine_bounded(self):
        wq = SequenceWQ(
            [
                FakeResponse(429, text="rate limited 1"),
                FakeResponse(429, text="rate limited 2"),
                FakeResponse(429, text="rate limited 3"),
            ],
            [],
        )
        for expected_retry in (1, 2, 3):
            result = executor.execute_reserved_candidate(self.store, wq, object())
            self.assertFalse(result["ok"])
            self.assertEqual(result["stage"], "HTTP_429")
            self.assertEqual(
                self.store.read()["simulations"][self.fingerprint]["retry_count"],
                expected_retry,
            )

        exhausted = executor.execute_reserved_candidate(self.store, wq, object())
        self.assertFalse(exhausted["ok"])
        self.assertEqual(exhausted["stage"], "HTTP_429_RETRY_REJECTED")
        self.assertEqual(exhausted["guard"]["reason"], "HTTP_429_RETRY_EXHAUSTED")
        self.assertEqual(wq.start_calls, 3)

    def test_missing_required_metric_keeps_result_pending_instead_of_false_inconclusive(self):
        class MissingFitnessWQ(SequenceWQ):
            def get_result(self, session, alpha_id):
                return {
                    "id": alpha_id,
                    "type": "REGULAR",
                    "regular": {"code": "rank(-close)"},
                    "settings": {
                        "language": "FASTEXPR",
                        "region": "GBR",
                        "delay": 0,
                        "universe": "TOP700",
                        "instrumentType": "EQUITY",
                        "decay": 5,
                        "truncation": 0.08,
                    },
                    "is": {
                        "sharpe": 2.2,
                        "turnover": 0.2,
                    },
                }

        wq = MissingFitnessWQ(
            [FakeResponse(201, location="/simulations/S6")],
            [{"status": "done", "alpha_id": "CHILD"}],
        )
        result = executor.execute_reserved_candidate(self.store, wq, object())
        self.assertFalse(result["ok"])
        self.assertEqual(result["stage"], "RESULT_EVIDENCE_PENDING")
        self.assertIn("protected_metric:FITNESS", result["missing_contract_observations"])
        self.assertEqual(self.store.read()["hypotheses"]["H1"]["status"], "OPEN")
        self.assertNotIn("result_evaluation", self.store.read()["candidates"][self.fingerprint])

    def test_terminal_transport_failure_is_idempotent_when_fingerprint_is_explicit(self):
        wq = SequenceWQ([FakeResponse(400, text="invalid simulation payload")], [])
        first = executor.execute_reserved_candidate(self.store, wq, object())
        self.assertTrue(first["ok"], first)
        self.assertEqual(first["stage"], "NO_POST_INCONCLUSIVE")

        second = executor.execute_reserved_candidate(
            self.store,
            wq,
            object(),
            fingerprint=self.fingerprint,
        )
        self.assertTrue(second["ok"], second)
        self.assertEqual(second["stage"], "HYPOTHESIS_ALREADY_TERMINAL")
        self.assertTrue(second["idempotent"])
        self.assertEqual(wq.start_calls, 1)


    def test_deterministic_guard_evaluate_failure_is_not_marked_resumable(self):
        wq = SequenceWQ(
            [FakeResponse(201, location="/simulations/S7")],
            [{"status": "done", "alpha_id": "CHILD"}],
        )
        with patch.object(
            self.store,
            "evaluate_result",
            return_value={"ok": False, "reason": "SIMULATION_ID_MISMATCH"},
        ):
            result = executor.execute_reserved_candidate(self.store, wq, object())
        self.assertFalse(result["ok"])
        self.assertEqual(result["stage"], "EVALUATE_FAILED")
        self.assertFalse(result["resumable"])
        self.assertEqual(result["evaluation"]["reason"], "SIMULATION_ID_MISMATCH")
        self.assertEqual(wq.start_calls, 1)



if __name__ == "__main__":
    main()

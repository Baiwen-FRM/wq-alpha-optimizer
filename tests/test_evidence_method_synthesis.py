import sys
import tempfile
from pathlib import Path
from unittest import TestCase


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import mechanism_synthesis  # noqa: E402
import optimizer_guard as guard  # noqa: E402


class EvidenceMethodSynthesisAdversarialTests(TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.state_path = Path(self.tempdir.name) / "state.json"

    def tearDown(self):
        self.tempdir.cleanup()

    def _store(self, checks):
        store = guard.StateStore(self.state_path, "ROOT")
        initialized = store.initialize(
            {
                "alpha_id": "ROOT",
                "expression": "ts_mean(close, 10)",
                "fields": ["close"],
                "settings": {
                    "language": "FASTEXPR",
                    "instrumentType": "EQUITY",
                    "region": "GBR",
                    "universe": "TOP700",
                    "delay": 0,
                    "decay": 10,
                    "neutralization": "SLOW",
                    "truncation": 0.08,
                },
                "language": "FASTEXPR",
                "result_evidence": {
                    "metrics": {
                        "SHARPE": 2.06,
                        "FITNESS": 1.57,
                        "TURNOVER": 0.1054,
                    },
                    "checks": checks,
                    "observed_at": "2026-09-22T00:00:00Z",
                    "source": "BRAIN:test",
                    "response_complete": True,
                    "authenticated": True,
                },
            }
        )
        self.assertTrue(initialized["initialized"], initialized)
        return store

    def _evidence(self, store, evidence_id, kind, subject, claim, source="BRAIN:get_record_set_data"):
        result = store.register_evidence(
            {
                "id": evidence_id,
                "kind": kind,
                "subject": subject,
                "source": source,
                "observed_at": guard._now_iso(),
                "claim": claim,
            }
        )
        self.assertTrue(result["ok"], result)
        return evidence_id

    def _assessment(
        self,
        assessment_id,
        mechanism,
        method_family,
        status,
        refs,
        *,
        reasoning="Evidence and the blocker method family make this mechanism testable.",
        next_question="Would a minimal intervention change the target as predicted?",
        exclusion_basis=None,
    ):
        row = {
            "id": assessment_id,
            "mechanism": mechanism,
            "method_family": method_family,
            "status": status,
            "evidence_refs": list(refs),
            "reasoning": reasoning,
            "next_question": next_question,
        }
        if exclusion_basis:
            row["exclusion_basis"] = exclusion_basis
        return row

    def _blocker_row(self, name, mechanisms, observations):
        entry = guard._catalog_entry_for_blocker(name)
        return {
            "name": name,
            "target": entry["target"],
            "owner": entry["owner"],
            "observation_refs": list(observations),
            "mechanisms": mechanisms,
        }

    def _plan(self, store, blocker_rows, routes):
        return {
            "based_on_evidence_revision": store.read()["evidence_revision"],
            "synthesis": {"blockers": blocker_rows},
            "routes": routes,
        }

    def test_scaffold_combines_current_blocker_with_method_catalog(self):
        store = self._store([{"name": "LOW_SHARPE", "status": "FAIL"}])
        self._evidence(store, "E_SHARPE", "DIAGNOSTIC", "LOW_SHARPE", "Sharpe is below the current limit.")
        scaffold = mechanism_synthesis.build_synthesis_scaffold(store.read())
        self.assertEqual([row["name"] for row in scaffold["blockers"]], ["LOW_SHARPE"])
        methods = {row["method_family"] for row in scaffold["blockers"][0]["mechanisms"]}
        self.assertIn("temporal_aggregation_or_smoothing", methods)
        self.assertIn("grouping_or_neutralization", methods)
        self.assertIn("ts_rank_delta_or_timing", methods)
        self.assertTrue(all(row["status"] == "UNASSESSED" for row in scaffold["blockers"][0]["mechanisms"]))

    def test_limited_low_sharpe_evidence_must_become_probe_not_empty_plan(self):
        store = self._store([{"name": "LOW_SHARPE", "status": "FAIL"}])
        ref = self._evidence(
            store, "E_LOW_SHARPE", "DIAGNOSTIC", "LOW_SHARPE",
            "Low Sharpe is observed, but current diagnostics do not identify a unique cause."
        )
        row = self._blocker_row(
            "LOW_SHARPE",
            [
                self._assessment(
                    "A_NOISE",
                    "noise_persistence_question",
                    "temporal_aggregation_or_smoothing",
                    "PLAUSIBLE_PROBE",
                    [ref],
                )
            ],
            [ref],
        )
        rejected = store.set_plan(self._plan(store, [row], []))
        self.assertFalse(rejected["ok"])
        self.assertEqual(rejected["reason"], "EMPTY_PLAN_HAS_TESTABLE_MECHANISM")

    def test_unresolved_discriminator_requires_diagnostic_instead_of_exhaustion(self):
        store = self._store([{"name": "LOW_SHARPE", "status": "FAIL"}])
        ref = self._evidence(
            store, "E_SHARPE_DIST", "DIAGNOSTIC", "SHARPE_DISTRIBUTION",
            "Available Sharpe evidence is insufficient to distinguish exposure from persistence."
        )
        row = self._blocker_row(
            "LOW_SHARPE",
            [
                self._assessment(
                    "A_EXPOSURE",
                    "cross_sectional_exposure_question",
                    "grouping_or_neutralization",
                    "NEEDS_DIAGNOSTIC",
                    [ref],
                    next_question="Does cap/sector/industry-conditioned Sharpe identify a systematic exposure?",
                )
            ],
            [ref],
        )
        rejected = store.set_plan(self._plan(store, [row], []))
        self.assertFalse(rejected["ok"])
        self.assertEqual(rejected["reason"], "EMPTY_PLAN_DIAGNOSTIC_REQUIRED")

    def test_historical_summary_cannot_certify_mechanism_exclusion(self):
        store = self._store([{"name": "LOW_SHARPE", "status": "FAIL"}])
        hist = self._evidence(
            store,
            "E_HISTORY",
            "HISTORICAL_SUMMARY",
            "LOW_SHARPE",
            "Old runs tried smoothing, grouping and winsorization.",
            source="HISTORY:old_run",
        )
        row = self._blocker_row(
            "LOW_SHARPE",
            [
                self._assessment(
                    "A_OLD",
                    "historically_tried_mechanism",
                    "temporal_aggregation_or_smoothing",
                    "EXCLUDED",
                    [hist],
                    exclusion_basis="CURRENT_DIAGNOSTIC",
                )
            ],
            [hist],
        )
        rejected = store.set_plan(self._plan(store, [row], []))
        self.assertFalse(rejected["ok"])
        self.assertEqual(rejected["reason"], "SYNTHESIS_CONTRACT")
        self.assertIn("diagnostic-exclusion", rejected["detail"].lower())

    def test_plain_blocker_fact_cannot_be_relabelled_as_exclusion(self):
        store = self._store([{"name": "LOW_SHARPE", "status": "FAIL"}])
        ref = self._evidence(
            store,
            "E_BLOCKER",
            "DIAGNOSTIC",
            "LOW_SHARPE",
            "LOW_SHARPE is currently failing.",
        )
        row = self._blocker_row(
            "LOW_SHARPE",
            [
                self._assessment(
                    "A_BAD_EXCLUSION",
                    "noise_persistence_question",
                    "temporal_aggregation_or_smoothing",
                    "EXCLUDED",
                    [ref],
                    exclusion_basis="CURRENT_DIAGNOSTIC",
                )
            ],
            [ref],
        )
        rejected = store.set_plan(self._plan(store, [row], []))
        self.assertFalse(rejected["ok"])
        self.assertEqual(rejected["reason"], "SYNTHESIS_CONTRACT")

    def test_current_diagnostic_can_support_true_no_action_certificate(self):
        store = self._store([{"name": "LOW_SHARPE", "status": "FAIL"}])
        entry = guard._catalog_entry_for_blocker("LOW_SHARPE")
        mechanisms = []
        refs = []
        for index, item in enumerate(entry["mechanisms"], start=1):
            ref = self._evidence(
                store,
                f"E_EXCLUDE_{index}",
                "DIAGNOSTIC_EXCLUSION",
                item["id"],
                f"Current targeted diagnostic falsifies mechanism {item['id']}.",
            )
            refs.append(ref)
            mechanisms.append(
                self._assessment(
                    f"A_EX_{index}",
                    item["id"],
                    item["method_family"],
                    "EXCLUDED",
                    [ref],
                    exclusion_basis="CURRENT_DIAGNOSTIC",
                )
            )
        accepted = store.set_plan(
            self._plan(store, [self._blocker_row("LOW_SHARPE", mechanisms, refs)], [])
        )
        self.assertTrue(accepted["ok"], accepted)
        self.assertEqual(accepted["plan"]["status"], "EXHAUSTED")

    def test_empty_plan_must_assess_entire_method_space(self):
        store = self._store([{"name": "LOW_SHARPE", "status": "FAIL"}])
        ref = self._evidence(
            store,
            "E_ONE_EXCLUSION",
            "DIAGNOSTIC_EXCLUSION",
            "noise_persistence_mismatch",
            "Current targeted diagnostic excludes only the persistence mechanism.",
        )
        row = self._blocker_row(
            "LOW_SHARPE",
            [
                self._assessment(
                    "A_ONLY_ONE",
                    "noise_persistence_mismatch",
                    "temporal_aggregation_or_smoothing",
                    "EXCLUDED",
                    [ref],
                    exclusion_basis="CURRENT_DIAGNOSTIC",
                )
            ],
            [ref],
        )
        rejected = store.set_plan(self._plan(store, [row], []))
        self.assertFalse(rejected["ok"])
        self.assertEqual(rejected["reason"], "EMPTY_PLAN_METHOD_SPACE_UNASSESSED")
        missing = rejected["blockers"][0]["missing_method_families"]
        self.assertIn("grouping_or_neutralization", missing)
        self.assertIn("ts_rank_delta_or_timing", missing)

    def test_cap_sharpe_dispersion_and_subuniverse_blocker_form_targeted_route(self):
        store = self._store([{"name": "LOW_SUB_UNIVERSE_SHARPE", "status": "FAIL"}])
        blocker = self._evidence(
            store, "E_SUB", "DIAGNOSTIC", "LOW_SUB_UNIVERSE_SHARPE",
            "Sub-universe Sharpe is below the current requirement."
        )
        cap = self._evidence(
            store, "E_CAP", "DIAGNOSTIC", "SHARPE_BY_CAP",
            "Capitalization Sharpe buckets are strongly uneven: 1.28/1.45/0.35/0.78/-0.22."
        )
        assessment = self._assessment(
            "A_SIZE",
            "size_breadth_exposure",
            "exposure_control_or_grouping",
            "ACTIONABLE",
            [blocker, cap],
            reasoning=(
                "The blocker and cap-conditioned Sharpe jointly support a size/breadth exposure "
                "mechanism; they do not prove the exact repair."
            ),
            next_question="Does one thesis-preserving size exposure control improve sub-universe robustness?",
        )
        row = self._blocker_row("LOW_SUB_UNIVERSE_SHARPE", [assessment], [blocker, cap])
        route = {
            "id": "R_SIZE",
            "target": "LOW_SUB_UNIVERSE_SHARPE",
            "owner": "optimization/subuniverse.md",
            "mechanism": "size_breadth_exposure",
            "evidence_refs": [blocker, cap],
            "assessment_refs": ["A_SIZE"],
            "rationale": "Test the size/breadth mechanism indicated by the observed cap distribution.",
        }
        accepted = store.set_plan(self._plan(store, [row], [route]))
        self.assertTrue(accepted["ok"], accepted)
        self.assertTrue(accepted["must_continue"])
        self.assertEqual(accepted["active_route_id"], "R_SIZE")

    def test_uniform_metadata_coverage_does_not_prove_backfill_is_needed(self):
        store = self._store([{"name": "LOW_SUB_UNIVERSE_SHARPE", "status": "FAIL"}])
        blocker = self._evidence(
            store, "E_SUB", "DIAGNOSTIC", "LOW_SUB_UNIVERSE_SHARPE",
            "Sub-universe Sharpe fails."
        )
        coverage = self._evidence(
            store, "E_COV", "DIAGNOSTIC", "FIELD_METADATA",
            "Headline metadata coverage and dateCoverage are both 1."
        )
        row = self._blocker_row(
            "LOW_SUB_UNIVERSE_SHARPE",
            [
                self._assessment(
                    "A_COVERAGE",
                    "coverage_sparsity",
                    "data_quality_or_coverage_repair",
                    "NEEDS_DIAGNOSTIC",
                    [blocker, coverage],
                    reasoning=(
                        "Headline metadata coverage does not establish post-expression or bucket-level "
                        "missingness, so backfill is not yet justified."
                    ),
                    next_question="Does observed coverage/staleness actually deteriorate in the weak subset?",
                )
            ],
            [blocker, coverage],
        )
        rejected = store.set_plan(self._plan(store, [row], []))
        self.assertEqual(rejected["reason"], "EMPTY_PLAN_DIAGNOSTIC_REQUIRED")

    def test_two_blockers_can_share_one_upstream_mechanism(self):
        store = self._store(
            [
                {"name": "LOW_SHARPE", "status": "FAIL"},
                {"name": "LOW_SUB_UNIVERSE_SHARPE", "status": "FAIL"},
            ]
        )
        low_sharpe = self._evidence(store, "E_SH", "DIAGNOSTIC", "LOW_SHARPE", "Sharpe is low.")
        sub = self._evidence(store, "E_SUB", "DIAGNOSTIC", "LOW_SUB_UNIVERSE_SHARPE", "Sub-universe Sharpe is low.")
        cap = self._evidence(
            store, "E_CAP", "DIAGNOSTIC", "SHARPE_BY_CAP",
            "Sharpe varies sharply by capitalization bucket."
        )

        sharpe_row = self._blocker_row(
            "LOW_SHARPE",
            [
                self._assessment(
                    "A_SH_SIZE",
                    "size_breadth_exposure",
                    "grouping_or_neutralization",
                    "PLAUSIBLE_PROBE",
                    [low_sharpe, cap],
                )
            ],
            [low_sharpe, cap],
        )
        sub_row = self._blocker_row(
            "LOW_SUB_UNIVERSE_SHARPE",
            [
                self._assessment(
                    "A_SUB_SIZE",
                    "size_breadth_exposure",
                    "exposure_control_or_grouping",
                    "ACTIONABLE",
                    [sub, cap],
                )
            ],
            [sub, cap],
        )
        route = {
            "id": "R_UPSTREAM_SIZE",
            "target": "LOW_SUB_UNIVERSE_SHARPE",
            "owner": "optimization/subuniverse.md",
            "mechanism": "size_breadth_exposure",
            "evidence_refs": [sub, cap],
            "assessment_refs": ["A_SUB_SIZE"],
            "explains_blockers": ["LOW_SHARPE", "LOW_SUB_UNIVERSE_SHARPE"],
            "rationale": "One upstream size/breadth mechanism may explain both current failures.",
        }
        accepted = store.set_plan(self._plan(store, [sharpe_row, sub_row], [route]))
        self.assertTrue(accepted["ok"], accepted)
        self.assertEqual(
            accepted["plan"]["routes"][0]["explains_blockers"],
            ["LOW_SHARPE", "LOW_SUB_UNIVERSE_SHARPE"],
        )

    def test_route_cannot_claim_cross_blocker_explanation_without_matching_assessment(self):
        store = self._store(
            [
                {"name": "LOW_SHARPE", "status": "FAIL"},
                {"name": "LOW_SUB_UNIVERSE_SHARPE", "status": "FAIL"},
            ]
        )
        sh = self._evidence(store, "E_SH", "DIAGNOSTIC", "LOW_SHARPE", "Sharpe is low.")
        sub = self._evidence(store, "E_SUB", "DIAGNOSTIC", "LOW_SUB_UNIVERSE_SHARPE", "Sub Sharpe is low.")
        sharpe_row = self._blocker_row(
            "LOW_SHARPE",
            [
                self._assessment(
                    "A_SH_NOISE", "noise_question", "temporal_aggregation_or_smoothing",
                    "PLAUSIBLE_PROBE", [sh]
                )
            ],
            [sh],
        )
        sub_row = self._blocker_row(
            "LOW_SUB_UNIVERSE_SHARPE",
            [
                self._assessment(
                    "A_SUB_SIZE", "size_breadth_exposure", "exposure_control_or_grouping",
                    "ACTIONABLE", [sub]
                )
            ],
            [sub],
        )
        route = {
            "id": "R_SIZE",
            "target": "LOW_SUB_UNIVERSE_SHARPE",
            "owner": "optimization/subuniverse.md",
            "mechanism": "size_breadth_exposure",
            "evidence_refs": [sub],
            "assessment_refs": ["A_SUB_SIZE"],
            "explains_blockers": ["LOW_SHARPE", "LOW_SUB_UNIVERSE_SHARPE"],
            "rationale": "Invalidly claims the size mechanism explains both blockers.",
        }
        rejected = store.set_plan(self._plan(store, [sharpe_row, sub_row], [route]))
        self.assertFalse(rejected["ok"])
        self.assertEqual(rejected["reason"], "ROUTE_CROSS_BLOCKER_MECHANISM_UNSUPPORTED")

    def test_wrong_method_family_is_rejected_even_when_mechanism_story_sounds_plausible(self):
        store = self._store([{"name": "LOW_SHARPE", "status": "FAIL"}])
        ref = self._evidence(store, "E_SH", "DIAGNOSTIC", "LOW_SHARPE", "Sharpe is low.")
        row = self._blocker_row(
            "LOW_SHARPE",
            [
                self._assessment(
                    "A_FAKE",
                    "size_story",
                    "data_quality_or_ts_backfill",
                    "PLAUSIBLE_PROBE",
                    [ref],
                )
            ],
            [ref],
        )
        rejected = store.set_plan(self._plan(store, [row], []))
        self.assertFalse(rejected["ok"])
        self.assertEqual(rejected["reason"], "SYNTHESIS_CONTRACT")
        self.assertIn("method_family", rejected["detail"])

    def test_route_must_carry_the_evidence_used_by_its_assessment(self):
        store = self._store([{"name": "LOW_SHARPE", "status": "FAIL"}])
        blocker = self._evidence(store, "E_SH", "DIAGNOSTIC", "LOW_SHARPE", "Sharpe is low.")
        dist = self._evidence(store, "E_DIST", "DIAGNOSTIC", "SHARPE_DISTRIBUTION", "Sharpe is uneven across groups.")
        row = self._blocker_row(
            "LOW_SHARPE",
            [
                self._assessment(
                    "A_EXP",
                    "cross_sectional_exposure",
                    "grouping_or_neutralization",
                    "ACTIONABLE",
                    [blocker, dist],
                )
            ],
            [blocker, dist],
        )
        route = {
            "id": "R_EXP",
            "target": "SHARPE",
            "owner": "optimization/sharpe.md",
            "mechanism": "cross_sectional_exposure",
            "evidence_refs": [blocker],
            "assessment_refs": ["A_EXP"],
            "rationale": "Drops the distribution evidence and therefore must be rejected.",
        }
        rejected = store.set_plan(self._plan(store, [row], [route]))
        self.assertFalse(rejected["ok"])
        self.assertEqual(rejected["reason"], "ROUTE_DROPS_ASSESSMENT_EVIDENCE")

    def test_o0_shape_historical_methods_tried_still_cannot_end_with_empty_plan(self):
        store = self._store(
            [
                {"name": "LOW_SHARPE", "status": "FAIL"},
                {"name": "LOW_SUB_UNIVERSE_SHARPE", "status": "FAIL"},
            ]
        )
        sh = self._evidence(store, "E_SH", "DIAGNOSTIC", "LOW_SHARPE", "Sharpe 2.06 is below 2.69.")
        sub = self._evidence(store, "E_SUB", "DIAGNOSTIC", "LOW_SUB_UNIVERSE_SHARPE", "Sub Sharpe 0.88 is below 0.98.")
        cap = self._evidence(
            store, "E_CAP", "DIAGNOSTIC", "SHARPE_BY_CAP",
            "Cap Sharpe is 1.28/1.45/0.35/0.78/-0.22."
        )
        history = self._evidence(
            store, "E_HISTORY", "HISTORICAL_SUMMARY", "OLD_EXPERIMENTS",
            "Historical runs tried cap, sector, industry, smoothing and winsorization.",
            source="HISTORY:O0",
        )

        sh_row = self._blocker_row(
            "LOW_SHARPE",
            [
                self._assessment(
                    "A_SH_EXP",
                    "size_breadth_exposure",
                    "grouping_or_neutralization",
                    "PLAUSIBLE_PROBE",
                    [sh, cap, history],
                    reasoning=(
                        "History lowers confidence in repeated payloads but does not prove the current "
                        "mechanism family exhausted; the cap distribution still creates a falsifiable question."
                    ),
                )
            ],
            [sh, cap, history],
        )
        sub_row = self._blocker_row(
            "LOW_SUB_UNIVERSE_SHARPE",
            [
                self._assessment(
                    "A_SUB_EXP",
                    "size_breadth_exposure",
                    "exposure_control_or_grouping",
                    "ACTIONABLE",
                    [sub, cap, history],
                )
            ],
            [sub, cap, history],
        )
        rejected = store.set_plan(self._plan(store, [sh_row, sub_row], []))
        self.assertFalse(rejected["ok"])
        self.assertEqual(rejected["reason"], "EMPTY_PLAN_HAS_TESTABLE_MECHANISM")


if __name__ == "__main__":
    import unittest

    unittest.main()

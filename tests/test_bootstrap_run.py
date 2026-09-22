import sys
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import bootstrap_run as bootstrap  # noqa: E402
import optimizer_guard as guard  # noqa: E402


class BootstrapRunTests(TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        self.logs = root / "logs"
        self.patches = patch.multiple(guard, LOGS_DIR=self.logs, STATE_DIR=self.logs / ".state")
        self.patches.start()

    def tearDown(self):
        self.patches.stop()
        self.tempdir.cleanup()

    def _intake(self):
        return {
            "root": {"alpha_id": "ROOT"},
            "baseline": {
                "alpha_id": "ROOT",
                "expression": "rank(close)",
                "fields": ["close"],
                "settings": {
                    "instrumentType": "EQUITY",
                    "region": "GBR",
                    "universe": "TOP700",
                    "delay": 0,
                    "decay": 0,
                    "neutralization": "NONE",
                    "truncation": 0.08,
                    "language": "FASTEXPR",
                },
                "language": "FASTEXPR",
                "result_evidence": {
                    "metrics": {"SHARPE": 2.0, "FITNESS": 1.5, "TURNOVER": 0.2},
                    "checks": [{"name": "LOW_SHARPE", "status": "FAIL"}],
                    "observed_at": "2026-09-22T00:00:00Z",
                    "source": "BRAIN:wq_lib.get_result+get_submission_check",
                    "response_complete": True,
                    "authenticated": True,
                },
            },
            "dashboard": {
                "fields": [
                    {
                        "name": "close",
                        "type": "MATRIX",
                        "dataset": "pv1",
                        "coverage": 1.0,
                        "dateCoverage": 0.99,
                        "description": "Closing price",
                    }
                ],
                "visualization": {},
            },
        }

    def test_bootstrap_runs_lean_root_pipeline_without_runtime_projection_files(self):
        with patch.object(bootstrap.provider, "_load_wq_lib", return_value=object()), patch.object(
            bootstrap.provider, "root_intake_snapshot", return_value=self._intake()
        ) as intake:
            result = bootstrap.bootstrap_run("ROOT")

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["stage"], "READY_FOR_OPTIMIZATION")
        intake.assert_called_once_with("ROOT")

        store = guard.StateStore(Path(result["state_path"]), "ROOT")
        state = store.read()
        self.assertEqual(state["root_baseline"]["alpha_id"], "ROOT")
        self.assertEqual(state["dashboard_context"]["fields"][0]["description"], "Closing price")
        self.assertEqual(state["dashboard_context"]["visualization"], {"charts": []})

        self.assertFalse((self.logs / ".data").exists())

        text = Path(result["log_path"]).read_text(encoding="utf-8")
        self.assertIn("## Alpha Snapshot / Dashboard", text)
        self.assertIn("Closing price", text)
        self.assertIn("## BOOTSTRAP", text)
        self.assertIn("Status: `READY`", text)
        self.assertIn("continue directly into optimization", text)
        self.assertLess(text.index("## Alpha Snapshot / Dashboard"), text.index("## Audit Trail"))

    def test_provider_preflight_failure_does_not_create_run(self):
        with patch.object(
            bootstrap.provider, "_load_wq_lib", side_effect=RuntimeError("missing primitives")
        ):
            result = bootstrap.bootstrap_run("ROOT")

        self.assertFalse(result["ok"])
        self.assertEqual(result["stage"], "LOCAL_PROVIDER_PREFLIGHT")
        self.assertFalse(self.logs.exists())

    def test_root_intake_failure_keeps_uninitialized_run_and_records_failure(self):
        with patch.object(bootstrap.provider, "_load_wq_lib", return_value=object()), patch.object(
            bootstrap.provider, "root_intake_snapshot", side_effect=RuntimeError("BRAIN unavailable")
        ):
            result = bootstrap.bootstrap_run("ROOT")

        self.assertFalse(result["ok"])
        self.assertEqual(result["stage"], "WQ_LAB_ROOT_INTAKE")
        state = guard.StateStore(Path(result["state_path"]), "ROOT").read()
        self.assertIsNone(state["root_baseline"])
        text = Path(result["log_path"]).read_text(encoding="utf-8")
        self.assertIn("## BOOTSTRAP", text)
        self.assertIn("WQ Lab Root intake failed", text)


if __name__ == "__main__":
    import unittest
    unittest.main()

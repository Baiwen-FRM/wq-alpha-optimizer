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
            "visualization": {
                "diagnostic_alpha_id": "VIS1",
                "recordset_listing": {
                    "count": 2,
                    "results": [
                        {"name": "pnl", "title": "PnL"},
                        {"name": "sharpe-by-cap", "title": "Sharpe by Cap"},
                    ],
                },
            },
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
                    "source": "BRAIN:wq_lib.get_result",
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
                "visualization": {
                    "alpha_id": "VIS1",
                    "control": "same expression/settings; visualization=true",
                    "recordsets": ["pnl", "sharpe-by-cap"],
                    "summary": ["2 recordsets discovered."],
                    "charts": [],
                },
            },
        }

    def test_bootstrap_runs_fixed_pipeline_without_persisting_projections(self):
        with patch.object(bootstrap.provider, "_load_wq_lib", return_value=object()), patch.object(
            bootstrap.provider, "intake_snapshot", return_value=self._intake()
        ) as intake:
            result = bootstrap.bootstrap_run("ROOT", discovery_attempts=3, discovery_sleep_seconds=0)

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["stage"], "READY_FOR_DIAGNOSIS")
        self.assertEqual(result["diagnostic_alpha_id"], "VIS1")
        self.assertEqual(result["recordset_count"], 2)
        intake.assert_called_once_with(
            "ROOT", discovery_attempts=3, discovery_sleep_seconds=0
        )

        self.assertFalse((self.logs / ".data").exists())
        self.assertFalse((self.logs / ".state").exists())
        self.assertFalse(result["resumed"])
        self.assertEqual(result["state_path"], result["log_path"])

        store = guard.StateStore(Path(result["state_path"]), "ROOT")
        state = store.read()
        self.assertEqual(state["root_baseline"]["alpha_id"], "ROOT")
        self.assertEqual(state["dashboard_context"]["fields"][0]["description"], "Closing price")

        text = Path(result["log_path"]).read_text(encoding="utf-8")
        self.assertIn("## Alpha Snapshot / Dashboard", text)
        self.assertIn("Closing price", text)
        self.assertIn("## BOOTSTRAP", text)
        self.assertIn("Status: `READY`", text)
        self.assertLess(text.index("## Alpha Snapshot / Dashboard"), text.index("## Audit Trail"))

    def test_bootstrap_renders_one_real_svg_dashboard_without_asset_sprawl(self):
        intake = self._intake()
        intake["dashboard"]["visualization"]["charts"] = [
            {
                "id": "pnl",
                "title": "PnL",
                "type": "line",
                "labels": [f"2026-01-{day:02d}" for day in range(1, 41)],
                "series": [
                    {
                        "name": "PnL",
                        "values": [float(day * day) for day in range(1, 41)],
                    }
                ],
            },
            {
                "id": "sharpe-by-cap",
                "title": "Sharpe by capitalization",
                "type": "bar",
                "labels": ["0-20", "20-40", "40-60", "60-80", "80-100"],
                "series": [
                    {
                        "name": "Sharpe",
                        "values": [1.43, 0.40, 0.90, 1.33, 1.65],
                    }
                ],
            },
        ]

        with patch.object(bootstrap.provider, "_load_wq_lib", return_value=object()), patch.object(
            bootstrap.provider, "intake_snapshot", return_value=intake
        ):
            result = bootstrap.bootstrap_run("ROOT", discovery_attempts=1, discovery_sleep_seconds=0)

        self.assertTrue(result["ok"], result)
        log_path = Path(result["log_path"])
        svg_path = log_path.with_name(f"{log_path.stem}_dashboard.svg")
        self.assertTrue(svg_path.exists(), svg_path)
        self.assertFalse((self.logs / "assets").exists())

        markdown = log_path.read_text(encoding="utf-8")
        self.assertIn(f"]({svg_path.name})", markdown)
        self.assertNotRegex(markdown, r"[▁▂▃▄▅▆▇█]")

        svg = svg_path.read_text(encoding="utf-8")
        self.assertIn("<svg", svg)
        self.assertIn("<polyline", svg)
        self.assertIn("Sharpe by capitalization", svg)
        self.assertIn('opacity="0.88"', svg)

        persistent_files = sorted(path.name for path in self.logs.iterdir() if path.is_file())
        self.assertEqual(persistent_files, [log_path.name, svg_path.name])

    def test_provider_preflight_failure_does_not_create_run(self):
        with patch.object(
            bootstrap.provider, "_load_wq_lib", side_effect=RuntimeError("missing primitives")
        ):
            result = bootstrap.bootstrap_run("ROOT")

        self.assertFalse(result["ok"])
        self.assertEqual(result["stage"], "LOCAL_PROVIDER_PREFLIGHT")
        self.assertFalse(self.logs.exists())

    def test_intake_failure_keeps_uninitialized_run_and_records_failure(self):
        with patch.object(bootstrap.provider, "_load_wq_lib", return_value=object()), patch.object(
            bootstrap.provider, "intake_snapshot", side_effect=RuntimeError("BRAIN unavailable")
        ):
            result = bootstrap.bootstrap_run("ROOT")

        self.assertFalse(result["ok"])
        self.assertEqual(result["stage"], "WQ_LAB_INTAKE")
        state = guard.StateStore(Path(result["state_path"]), "ROOT").read()
        self.assertIsNone(state["root_baseline"])
        self.assertEqual(state["run"]["status"], "RECOVERY_REQUIRED")
        text = Path(result["log_path"]).read_text(encoding="utf-8")
        self.assertIn("## BOOTSTRAP", text)
        self.assertIn("WQ Lab intake failed", text)

    def test_retry_resumes_same_run_after_intake_failure(self):
        snapshots = [RuntimeError("temporary BRAIN failure"), self._intake()]
        with patch.object(bootstrap.provider, "_load_wq_lib", return_value=object()), patch.object(
            bootstrap.provider, "intake_snapshot", side_effect=snapshots
        ):
            first = bootstrap.bootstrap_run("ROOT")
            second = bootstrap.bootstrap_run("ROOT")

        self.assertFalse(first["ok"])
        self.assertTrue(second["ok"], second)
        self.assertEqual(first["run_id"], second["run_id"])
        self.assertEqual(first["state_path"], second["state_path"])
        self.assertEqual(first["log_path"], second["log_path"])
        self.assertTrue(second["resumed"])
        self.assertEqual(second["state_path"], second["log_path"])
        self.assertEqual(len(list(self.logs.glob("ROOT_*.md"))), 1)
        self.assertFalse((self.logs / ".data").exists())
        self.assertFalse((self.logs / ".state").exists())


if __name__ == "__main__":
    import unittest
    unittest.main()

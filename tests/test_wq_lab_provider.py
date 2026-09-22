import sys
from pathlib import Path
from unittest import TestCase, main


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import recordset_dashboard as rd  # noqa: E402
import wq_lab_provider as provider  # noqa: E402


class WQLabProviderTests(TestCase):
    def test_visualization_payload_preserves_settings_and_only_enables_visualization(self):
        details = {
            "type": "REGULAR",
            "regular": {"code": "ts_mean(close, 10)"},
            "settings": {
                "instrumentType": "EQUITY",
                "region": "GBR",
                "universe": "TOP700",
                "delay": 0,
                "decay": 10,
                "neutralization": "SLOW",
                "truncation": 0.08,
                "visualization": False,
            },
        }
        payload = provider._visualization_payload(details)
        self.assertEqual(payload["regular"], "ts_mean(close, 10)")
        self.assertTrue(payload["settings"]["visualization"])
        for key, value in details["settings"].items():
            if key != "visualization":
                self.assertEqual(payload["settings"][key], value)
        self.assertFalse(details["settings"]["visualization"])

    def test_root_snapshot_uses_exact_field_detail_and_scope_row(self):
        class FakeWQ:
            @staticmethod
            def get_result(session, alpha_id):
                return {
                    "id": alpha_id,
                    "type": "REGULAR",
                    "regular": {"code": "rank(close)"},
                    "settings": {"region": "GBR", "delay": 0, "universe": "TOP700"},
                    "is": {"sharpe": 2.0, "fitness": 1.5, "checks": [{"name": "LOW_SHARPE", "result": "FAIL"}]},
                }

            @staticmethod
            def get_datafield(session, field_id):
                return {
                    "id": field_id,
                    "dataset": {"id": "pv1", "name": "Price Volume"},
                    "type": "MATRIX",
                    "description": "Closing price",
                    "visualizable": True,
                    "data": [
                        {"region": "USA", "delay": 1, "universe": "TOP3000", "coverage": 0.9, "dateCoverage": 0.8},
                        {"region": "GBR", "delay": 0, "universe": "TOP700", "coverage": 1.0, "dateCoverage": 0.99},
                    ],
                }

            @staticmethod
            def get_submission_check(session, alpha_id):
                return {"checks": [{"name": "LOW_SHARPE", "result": "FAIL"}]}

        snapshot = provider.root_snapshot(object(), FakeWQ, "A1")
        self.assertEqual(snapshot["fields"][0]["field_id"], "close")
        row = snapshot["fields"][0]["dashboard"]
        self.assertEqual(row["dataset"], "pv1")
        self.assertEqual(row["coverage"], 1.0)
        self.assertEqual(row["dateCoverage"], 0.99)

        baseline = provider._baseline_from_root(snapshot)
        self.assertEqual(baseline["alpha_id"], "A1")
        self.assertEqual(baseline["expression"], "rank(close)")
        self.assertEqual(baseline["fields"], ["close"])
        self.assertEqual(baseline["result_evidence"]["checks"][0]["status"], "FAIL")

    def test_recordset_adapters_are_deterministic(self):
        recordsets = {
            "sharpe-by-cap": {
                "schema": {
                    "name": "sharpe-by-cap",
                    "title": "Sharpe by Cap",
                    "properties": [
                        {"name": "bucket", "title": "Bucket", "type": "string"},
                        {"name": "sharpe", "title": "Sharpe", "type": "number"},
                    ],
                },
                "records": [["0-20", 1.28], ["20-40", 1.45]],
            },
            "pnl": {
                "schema": {
                    "name": "pnl",
                    "title": "PnL",
                    "properties": [
                        {"name": "date", "title": "Date", "type": "date"},
                        {"name": "pnl", "title": "PnL", "type": "amount"},
                        {"name": "equal-weight-pnl", "title": "Equal Weight PnL", "type": "amount"},
                    ],
                },
                "records": [["2026-01-01", 100.0, 90.0], ["2026-01-02", 110.0, 95.0]],
            },
            "yearly-stats": {
                "schema": {
                    "name": "yearly-stats",
                    "title": "Yearly Statistics",
                    "properties": [
                        {"name": "year", "title": "Year", "type": "integer"},
                        {"name": "sharpe", "title": "Sharpe", "type": "number"},
                        {"name": "turnover", "title": "Turnover", "type": "number"},
                    ],
                },
                "records": [[2025, 2.0, 0.1]],
            },
        }
        charts = rd.charts_from_recordsets(recordsets)
        self.assertEqual([chart["id"] for chart in charts], ["pnl", "sharpe-by-cap"])
        self.assertEqual(charts[0]["type"], "line")
        self.assertEqual(charts[1]["type"], "bar")
        self.assertEqual(charts[1]["labels"], ["0-20", "20-40"])
        self.assertEqual(charts[1]["series"][0]["values"], [1.28, 1.45])

    def test_missing_line_values_are_dropped_not_imputed(self):
        recordset = {
            "schema": {
                "name": "pnl",
                "title": "PnL",
                "properties": [
                    {"name": "date", "title": "Date", "type": "date"},
                    {"name": "pnl", "title": "PnL", "type": "amount"},
                ],
            },
            "records": [["2026-01-01", 100.0], ["2026-01-02", None], ["2026-01-03", 120.0]],
        }
        chart = rd.chart_from_recordset("pnl", recordset)
        self.assertEqual(chart["labels"], ["2026-01-01", "2026-01-03"])
        self.assertEqual(chart["series"][0]["values"], [100.0, 120.0])


if __name__ == "__main__":
    main()

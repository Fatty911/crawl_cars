import json
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main
from unittest.mock import patch

import requests

from scripts import aws_crawl_pipeline as pipeline
from scripts import refresh_aws_autohome_ranks as ranks


def html(kind, period="2026-10"):
    sales = kind == "sales"
    payload = {"props": {"pageProps": {
        "initialValues": {"typeid": "1" if sales else "2", "subranktypeid": "1" if sales else "2001",
                          "levelid": "0", "price": "0-9000", "date": period},
        "listRes": {"scenetitle": "全车型销量总榜" if sales else "全车型关注总榜",
                    "pageindex": 1, "list": [{"seriesid": 5769, "salecount": 100}]} }}}
    return b'<script id="__NEXT_DATA__" type="application/json">' + json.dumps(payload).encode() + b'</script>'


class RankingRefreshTests(TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name)
        self.path = self.directory / "rankings.json"
        self.observed = date(2026, 11, 12)
        self.urls = ranks.page_urls(self.observed)

    def test_updates_sales_without_losing_previous_heat_when_request_times_out(self):
        old_heat = {"observed_on": "2026-11-06", "ranks": {"7806": 1}}
        pipeline.atomic_json(self.path, {"heat": old_heat})

        def fetch(url):
            if url == self.urls["heat"]:
                raise requests.Timeout()
            return html("sales")

        receipt = ranks.refresh_rankings(self.path, self.observed, fetch)
        self.assertEqual(receipt["updated"], ["sales"])
        self.assertEqual(receipt["preserved"], ["heat"])
        live = pipeline.private_json(self.path)
        self.assertEqual(live["heat"], old_heat)
        self.assertEqual(live["sales"]["period"], "2026-10")
        self.assertEqual(live["sales"]["ranks"], {"5769": 1})

    def test_invalid_boards_leave_previous_bytes_untouched(self):
        pipeline.atomic_json(self.path, {"sales": {"observed_on": "2026-11-11", "period": "2026-10", "ranks": {"1": 1}}})
        before = self.path.read_bytes()
        receipt = ranks.refresh_rankings(self.path, self.observed, lambda url: b"<html>wrong board</html>")
        self.assertEqual(receipt["updated"], [])
        self.assertEqual(self.path.read_bytes(), before)

    def test_downgrade_in_sales_period_is_rejected_and_valid_heat_is_saved(self):
        previous = {"observed_on": "2026-11-11", "period": "2026-10", "ranks": {"1": 1}}
        pipeline.atomic_json(self.path, {"sales": previous})
        receipt = ranks.refresh_rankings(self.path, self.observed,
            lambda url: html("sales", "2026-09") if url == self.urls["sales"] else html("heat"))
        self.assertEqual(receipt["updated"], ["heat"])
        self.assertEqual(pipeline.private_json(self.path)["sales"], previous)

    def test_daily_refresh_attempt_is_durable_before_starting_worker(self):
        plan = {"targets": {"autohome": {"priority": {"refresh": True, "rankings_path": str(self.path)}}},
                "network": {"probe_ip": "192.0.2.1"}}
        receipt = self.directory / "autohome-ranking-attempt.json"

        def run(*args, **kwargs):
            self.assertEqual(pipeline.private_json(receipt), {"period": "20261112", "status": "started"})
            raise OSError("fixture failed before worker")

        with patch.object(pipeline.subprocess, "run", side_effect=run) as subprocess_run:
            pipeline.refresh_priority_rankings(plan, self.directory, "20261112", self.directory)
            pipeline.refresh_priority_rankings(plan, self.directory, "20261112", self.directory)
        self.assertEqual(subprocess_run.call_count, 1)
        self.assertEqual(pipeline.private_json(receipt)["status"], "failed")

    def test_missing_first_snapshot_can_use_pinned_catalog(self):
        catalog = self.directory / "catalog.json"
        pipeline.atomic_json(catalog, {"source": "autohome", "targets": [{
            "target": {"car_id": "5769", "series": "Model Y", "brand": "Tesla"}, "trim_cost": 1
        }]})
        plan = {"targets": {"autohome": {"row_limit": 2, "priority": {
            "catalog_path": str(catalog), "catalog_sha256": pipeline.digest(catalog),
            "rankings_path": str(self.path), "refresh": True
        }}}}
        selection = pipeline.plan_run_targets(plan, "20261112", {})
        self.assertEqual(json.loads(selection["autohome"]["payload"])[0]["car_id"], "5769")
        self.assertEqual(selection["autohome"]["rankings_used"], [])


if __name__ == "__main__":
    main()

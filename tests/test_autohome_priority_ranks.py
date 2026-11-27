from datetime import date
import json

import pytest

from scripts.normalize_autohome_priority_ranks import autohome_rank_snapshot
from scripts.plan_aws_crawl_priority import plan

TODAY = date(2026, 11, 6)


def test_autohome_saved_page_uses_native_series_ids_and_checks_scope(tmp_path):
    data = {"props": {"pageProps": {
        "initialValues": {"typeid": "1", "subranktypeid": 1, "levelid": "0", "price": "0-9000", "date": "2026-09"},
        "listRes": {"pageindex": 1, "scenetitle": "全车型销量总榜",
                    "list": [{"seriesid": "81", "salecount": 20}, {"seriesid": "82", "salecount": 10}]},
    }}}
    path = tmp_path / "rank.html"
    path.write_text('<script id="__NEXT_DATA__" type="application/json">' + json.dumps(data) + "</script>")
    actual = autohome_rank_snapshot(path, "sales", TODAY)
    assert actual["metric"] == "autohome_monthly_sales"
    assert actual["ranks"] == {"81": 1, "82": 2}
    _, receipt = plan({"source": "autohome", "targets": [{"target": {"car_id": "81", "series": "样本", "brand": "样本"}, "trim_cost": 1}], "rankings": {"sales": actual}}, TODAY, 2)
    assert receipt["selected"][0]["lane"] == "hot"
    with pytest.raises(ValueError, match="unexpected"):
        autohome_rank_snapshot(path, "heat", TODAY)

from datetime import date
from scripts.plan_aws_crawl_priority import plan


TODAY = date(2026, 11, 6)


def target(key, *, cost=1, last=None, first=None, missing=False):
    return {
        "target": {"car_id": str(key), "series": "车系" + str(key), "brand": "品牌"},
        "trim_cost": cost, "last_success": last, "first_seen": first, "missing_source": missing,
    }


def rankings(sales=None, heat=None):
    return {
        "sales": {"observed_on": "2026-11-06", "metric": "monthly_retail", "period": "2026-09",
                  "ranks": sales or {}},
        "heat": {"observed_on": "2026-11-06", "ranks": heat or {}},
    }


def test_hot_oldest_and_gap_are_interleaved_without_repeating_targets():
    rows = [target(1, cost=2), target(2, cost=3), target(3, cost=3),
            target(4, cost=2, missing=True), target(5, last="2026-11-05")]
    targets, result = plan({
        "source": "autohome", "targets": rows, "rankings": rankings({"1": 1, "5": 2}, {"2": 4, "1": 3}),
    }, TODAY, 10)
    assert [item["car_id"] for item in targets] == ["1", "3", "4", "2"]
    assert result["selected_estimated_trims"] == {"hot": 5, "oldest": 3, "new_gap": 2}
    assert result["estimated_trims_unused"] == 0


def test_stale_heat_and_non_retail_sales_fall_back_to_oldest():
    signals = rankings({"9": 1}, {"8": 1})
    signals["sales"]["metric"] = "wholesale"
    signals["heat"]["observed_on"] = "2026-10-20"
    _, result = plan({
        "source": "autohome", "targets": [target(9, last="2026-11-02"), target(8)], "rankings": signals,
    }, TODAY, 2)
    assert result["rankings_used"] == []
    assert [(row["id"], row["lane"]) for row in result["selected"]] == [("8", "oldest"), ("9", "oldest")]


def test_old_month_is_ignored_even_if_downloaded_today():
    signals = rankings({"1": 1})
    signals["sales"]["period"] = "2026-06"
    _, result = plan({"source": "autohome", "targets": [target(1)], "rankings": signals}, TODAY, 2)
    assert "sales" not in result["rankings_used"]


def test_yiche_manifest_preserves_source_url_and_refuses_oversized_target():
    targets, report = plan({
        "source": "yiche",
        "targets": [
            {"target": {"serial_id": "81", "brand": "品牌", "series": "车系",
                        "url": "https://car.yiche.com/series-a/peizhi/"}, "trim_cost": 2},
            {"target": {"serial_id": "82", "brand": "品牌", "series": "车系B",
                        "url": "https://car.yiche.com/series-b/peizhi/"}, "trim_cost": 11},
        ],
    }, TODAY, 10)
    assert list(targets) == ["https://car.yiche.com/series-a/peizhi/"]
    assert targets[next(iter(targets))]["serial_id"] == "81"
    assert report["estimated_trims_unused"] == 8

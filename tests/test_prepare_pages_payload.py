import importlib.util
import json
import sys
from pathlib import Path


def listed(row):
    row = dict(row)
    row.setdefault("官方指导价", "12.98万")
    row.setdefault("上市时间", "2026-01-01")
    return row


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SCRIPT = ROOT / "scripts" / "prepare_pages_payload.py"
SPEC = importlib.util.spec_from_file_location("prepare_pages_payload", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_prepare_rows_keeps_recent_sparse_rows_and_meaningful_zeroes():
    rows = [
        listed({"品牌": "甲", "车型名称": "旧车 2021款", "年款": "2021", "远程启动": "标配"}),
        listed({"品牌": "甲", "车型名称": "新车 2024款", "年款": "", "远程启动": "-", "气囊数": 0}),
        listed({"品牌": "甲", "车型名称": "无年款", "年款": "-", "数据来源": "仅懂车帝"}),
        {"品牌": "乙", "车系": "乙车系", "车型名称": "易车无年款", "年款": "-", "数据来源": "仅易车", "配置A": "-"},
        listed({"品牌": "乙", "车系": "乙车系", "车型名称": "易车旧款", "年款": "2021", "数据来源": "仅易车", "易车上市状态": "approved", "车款ID": "1001"}),
        listed({"品牌": "乙", "车系": "乙车系", "车型名称": "易车新款 2026款", "年款": "2026", "数据来源": "仅易车", "易车上市状态": "approved", "车款ID": "1001", "配置A": "有"}),
    ]

    assert MODULE.prepare_rows(rows, 2022) == [
        listed({"品牌": "甲", "车型名称": "新车 2024款", "气囊数": 0}),
        listed({"品牌": "乙", "车系": "乙车系", "车型名称": "易车新款 2026款", "年款": "2026", "数据来源": "仅易车", "易车上市状态": "approved", "车款ID": "1001", "配置A": "有"}),
    ]


def test_main_supports_atomic_in_place_compaction(tmp_path, monkeypatch):
    payload = tmp_path / "latest.json"
    payload.write_text(
        json.dumps(
            [
                listed({"品牌": "甲", "车型名称": "甲 2022款", "年款": "2022", "配置A": "-", "配置B": "有"}),
                listed({"品牌": "乙", "车型名称": "乙 2021款", "年款": "2021", "配置B": "有"}),
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    before = payload.stat().st_size
    monkeypatch.setattr(
        "sys.argv",
        [str(SCRIPT), "--input", str(payload), "--output", str(payload), "--min-year", "2022"],
    )

    assert MODULE.main() == 0
    assert json.loads(payload.read_text(encoding="utf-8")) == [
        listed({"品牌": "甲", "车型名称": "甲 2022款", "年款": "2022", "配置B": "有"})
    ]
    assert payload.stat().st_size < before


def test_prepare_rows_rejects_blank_brand_and_model():
    rows = [
        listed({"品牌": " ", "车型名称": "A 2026款", "年款": "2026"}),
        listed({"品牌": "甲", "车型名称": "-", "年款": "2026"}),
        listed({"品牌": "甲", "车型名称": "A 2026款", "年款": "2026"}),
    ]
    assert MODULE.prepare_rows(rows, 2022) == [rows[2]]


def test_prepare_rows_rejects_dirty_yiche_identity_and_status():
    rows = [
        {"品牌": "特斯拉", "车系": "modely-6224", "车型名称": "Model Y 2026款", "年款": "2026", "数据来源": "仅易车", "易车上市状态": "approved", "车款ID": "1001"},
        {"品牌": "特斯拉", "车系": "特斯拉Model Y", "车型名称": "Model Y 2026款", "年款": "", "数据来源": "仅易车", "易车上市状态": "approved", "车款ID": "1001"},
        {"品牌": "特斯拉", "车系": "特斯拉Model Y", "车型名称": "Model Y 2026款", "年款": "2026", "数据来源": "仅易车", "易车上市状态": "unapproved"},
        listed({"品牌": "特斯拉", "车系": "特斯拉Model Y", "车型名称": "Model Y 2026款", "年款": "2026", "数据来源": "仅易车", "易车上市状态": "approved", "车款ID": "1001"}),
    ]
    assert MODULE.prepare_rows(rows, 2022) == [rows[-1]]


def test_prepare_rows_rejects_dirty_yiche_rows():
    rows = [
        {"品牌": "凯迪拉克", "车系": "vistiq-11581", "车型名称": "2026款 豪华版", "年款": "2026", "数据来源": "仅易车", "易车上市状态": "approved", "车款ID": "1001"},
        {"品牌": "凯迪拉克", "车系": "凯威德", "车型名称": "2026款 基本型", "年款": "2026", "数据来源": "仅易车", "易车上市状态": "unapproved"},
        listed({"品牌": "凯迪拉克", "车系": "凯威德", "车型名称": "2026款 豪华版", "年款": "2026", "数据来源": "仅易车", "易车上市状态": "approved", "车款ID": "1001"}),
    ]
    assert MODULE.prepare_rows(rows, 2022) == [rows[2]]


def test_prepare_rows_requires_autohome_numeric_car_id():
    valid = listed({
        "数据来源": "仅汽车之家",
        "品牌": "甲",
        "车系": "甲车系",
        "车系ID": "100",
        "车型名称": "甲 2026款 Pro",
        "年款": "2026",
        "车款ID": "54529",
    })
    missing_id = dict(valid)
    missing_id.pop("车款ID")
    dirty_id = dict(valid, 车款ID="abc")
    assert MODULE.prepare_rows([missing_id, dirty_id, valid], 2022) == [valid]


def test_prepare_rows_rejects_autohome_slug_series():
    rows = [
        listed({
            "数据来源": "仅汽车之家",
            "品牌": "甲",
            "车系": "modely-6224",
            "车型名称": "甲 2026款 Pro",
            "年款": "2026",
            "车款ID": "54529",
        })
    ]
    assert MODULE.prepare_rows(rows, 2022) == []


def test_prepare_rows_keeps_autohome_latin_commercial_series():
    model3 = listed({
        "数据来源": "仅汽车之家",
        "品牌": "特斯拉",
        "车系": "Model 3",
        "车系ID": "5346",
        "车型名称": "2022款 后轮驱动版",
        "年款": "2022",
        "车款ID": "54529",
    })
    ds9 = listed({
        "数据来源": "仅汽车之家",
        "品牌": "雪铁龙",
        "车系": "DS 9",
        "车系ID": "5001",
        "车型名称": "2024款 歌剧院版",
        "年款": "2024",
        "车款ID": "60001",
    })
    mini = listed({
        "数据来源": "仅汽车之家",
        "品牌": "宝马",
        "车系": "MINI",
        "车系ID": "5002",
        "车型名称": "2024款 Cooper",
        "年款": "2024",
        "车款ID": "60002",
    })
    invalid = [
        dict(model3, 车系="modely-6224", 车款ID="60003"),
        dict(model3, 车系="", 车款ID="60004"),
        dict(model3, 年款="", 车款ID="60005"),
        dict(model3, 车款ID=""),
        dict(model3, 车款ID="abc"),
    ]

    assert MODULE.prepare_rows(invalid + [model3, ds9, mini], 2022) == [model3, ds9, mini]


def test_prepare_rows_normalizes_official_price_by_source_priority():
    autohome = listed({"数据来源": "仅汽车之家", "品牌": "特斯拉", "车系": "Model 3", "车型名称": "2022款 后轮驱动版", "年款": "2022", "车款ID": "54529", "官方指导价": "", "厂商指导价_元_": "265900"})
    yiche = listed({"数据来源": "仅易车", "品牌": "特斯拉", "车系": "特斯拉Model Y", "车型名称": "2026款 后轮驱动版", "年款": "2026", "车款ID": "1901", "易车上市状态": "approved", "官方指导价": "-", "价格": "26.35万", "城市参考价": "25.00万"})
    dcd = listed({"数据来源": "仅懂车帝", "品牌": "甲", "车系": "甲车系", "车型名称": "甲 2026款", "年款": "2026", "官方指导价": "18.88万"})
    prepared = MODULE.prepare_rows([autohome, yiche, dcd], 2022)
    assert [row["官方指导价"] for row in prepared] == ["265900", "26.35万", "18.88万"]


def test_prepare_rows_rejects_missing_or_placeholder_price_without_dealer_fallback():
    base = listed({"数据来源": "仅易车", "品牌": "特斯拉", "车系": "特斯拉Model Y", "车型名称": "2026款 后轮驱动版", "年款": "2026", "车款ID": "1901", "易车上市状态": "approved", "官方指导价": "", "价格": "暂无报价", "城市参考价": "25.00万"})
    assert MODULE.prepare_rows([base, dict(base, 价格=""), dict(base, 价格="--")], 2022) == []


def test_prepare_rows_rejects_blank_listing_time_accepts_combined_past_and_rejects_future():
    base = {"数据来源": "仅懂车帝", "品牌": "甲", "车系": "甲车系", "车型名称": "甲 2026款", "年款": "2026", "官方指导价": "18.88万"}
    blank = dict(base, 上市时间="")
    combined = dict(base, 上市时间="汽车之家:2026-04-16|懂车帝:2026.04")
    future = dict(base, 上市时间="2099-01-01")
    assert MODULE.prepare_rows([blank, combined, future], 2022) == [combined]


def test_prepare_rows_normalizes_audited_headers_without_losing_conflicts_or_acceleration_scope():
    row = listed({
        "数据来源": "仅懂车帝",
        "品牌": "甲",
        "车系": "甲车系",
        "车型名称": "甲 2026款",
        "年款": "2026",
        " 能源类型 ": "纯电动",
        "燃料形式": "增程式",
        "轴距[mm]": "2800",
        "轴距_mm_": "2810",
        "电能当量燃料消耗量[L/100km]": "1.20",
        "电能当量燃料消耗量_L_100km_": "1.25",
        "官方0-100km/h加速[s]": "7.0",
        "官方0-50km_h加速_s_": "3.5",
        "官方0—50Km/h加速时间(s)": "3.6",
    })

    prepared = MODULE.prepare_rows([row], 2022)

    assert len(prepared) == 1
    normalized = prepared[0]
    assert normalized["能源类型"] == "纯电动|增程式"
    assert normalized["轴距(mm)"] == "2800|2810"
    assert normalized["电能当量燃料消耗量(L/100km)"] == "1.20|1.25"
    assert normalized["百公里加速(s)"] == "7.0"
    assert normalized["官方0-50km/h加速(s)"] == "3.5|3.6"
    assert not any(key != key.strip() for key in normalized)
    assert "官方0-50km/h加速(s)" != "百公里加速(s)"


def test_prepare_rows_reports_price_and_listing_drop_stats():
    base = {"数据来源": "仅懂车帝", "品牌": "甲", "车系": "甲车系", "车型名称": "甲 2026款", "年款": "2026"}
    rows = [
        dict(base, 官方指导价="暂无报价", 上市时间="2026-01-01"),
        dict(base, 官方指导价="12.98万", 上市时间=""),
        dict(base, 官方指导价="12.98万", 上市时间="2099-01-01"),
        dict(base, 官方指导价="12.98万", 上市时间="汽车之家:2026-04-16|懂车帝:2026.04"),
    ]
    prepared, stats = MODULE.prepare_rows_with_stats(rows, 2022)
    assert prepared == [rows[-1]]
    assert stats == {
        "droppedMissingOfficialPrice": 1,
        "droppedMissingListingTime": 1,
        "droppedFutureListingTime": 1,
    }


def component_row(source, name, *, model_id="", **fields):
    row = listed({
        "数据来源": source,
        "品牌": "本田",
        "车系": "皓影",
        "车型名称": name,
        "年款": "2026",
        "能源类型": "油电混合",
        "级别": "紧凑型SUV",
        "座位数(个)": "5",
        "驱动形式": "前置四驱",
        **fields,
    })
    if "汽车之家" in source:
        row.update({"车系ID": "5393", "车款ID": model_id or "77904"})
    elif "易车" in source:
        row.update({"车款ID": model_id or "189503", "易车上市状态": "approved"})
    else:
        row.update({"车系ID": "4079"})
    return row


def test_safe_three_source_chain_gets_one_auditable_visible_component_id():
    dongchedi = component_row("仅懂车帝", "锐·混动 2.0L 四驱尊耀版")
    yiche = component_row("仅易车", "26款 e:HEV 2.0L 四驱锐·尊耀版")
    autohome = component_row("仅汽车之家", "皓影 2026款 e:HEV 四驱尊耀版")

    prepared, stats = MODULE.prepare_rows_with_stats([dongchedi, yiche, autohome], 2022)

    component_ids = {row["跨源归并ID"] for row in prepared}
    assert len(component_ids) == 1
    evidence = json.loads(prepared[0]["跨源归并证据"])
    assert evidence["sources"] == ["汽车之家", "懂车帝", "易车"]
    assert sorted(edge["score"] for edge in evidence["edges"]) == [0.62, 0.6575]
    assert [row["车型名称"] for row in prepared] == [
        dongchedi["车型名称"],
        yiche["车型名称"],
        autohome["车型名称"],
    ]
    assert [row.get("车款ID") for row in prepared] == [None, "189503", "77904"]
    assert stats["visibleFResolvedComponents"] == 1
    assert stats["visibleFResolvedRows"] == 3
    assert stats["visibleFThreeSourceComponents"] == 1


def test_safe_two_source_component_is_annotated_without_deleting_payload_rows():
    autohome = component_row("仅汽车之家", "皓影 2026款 e:HEV 四驱尊耀版")
    yiche = component_row("仅易车", "26款 e:HEV 2.0L 四驱锐·尊耀版")

    prepared, stats = MODULE.prepare_rows_with_stats([autohome, yiche], 2022)

    assert len(prepared) == 2
    assert prepared[0]["跨源归并ID"] == prepared[1]["跨源归并ID"]
    assert stats["visibleFTwoSourceComponents"] == 1


def test_visible_component_conflicts_and_true_many_to_many_stay_fail_closed():
    base_left = component_row("仅汽车之家", "皓影 2026款 Pro 四驱版")
    conflict_cases = [
        (dict(base_left, 年款="2025", 车型名称="皓影 2025款 Pro 四驱版"), component_row("仅懂车帝", "Pro 四驱版")),
        (dict(base_left, 车型名称="皓影 2026款 Ultra 四驱版"), component_row("仅懂车帝", "基本型 四驱版")),
        (dict(base_left, 车型名称="皓影 2026款 Pro 四驱版"), component_row("仅懂车帝", "Max 四驱版")),
        (dict(base_left, 车型名称="皓影 2026款 Pro 四驱版"), component_row("仅懂车帝", "Plus 四驱版")),
        (dict(base_left, 车型名称="皓影 2026款 Pro 四驱版 5座", **{"座位数(个)": "5"}), component_row("仅懂车帝", "Pro 四驱版 6座", **{"座位数(个)": "6"})),
        (dict(base_left, 车型名称="皓影 2026款 Pro 四驱版 5座", **{"座位数(个)": "5"}), component_row("仅懂车帝", "Pro 四驱版 7座", **{"座位数(个)": "7"})),
        (dict(base_left, 驱动形式="前置四驱"), component_row("仅懂车帝", "Pro 两驱版", 驱动形式="两驱")),
        (dict(base_left, 激光雷达="支持"), component_row("仅懂车帝", "Pro 四驱版", 激光雷达="-")),
        (dict(base_left, 能源类型="纯电动"), component_row("仅懂车帝", "Pro 四驱版", 能源类型="汽油")),
        (dict(base_left, 级别="紧凑型SUV"), component_row("仅懂车帝", "Pro 四驱版", 级别="中型轿车")),
        (dict(base_left, 车体结构="承载式"), component_row("仅懂车帝", "Pro 四驱版", 车体结构="非承载式")),
        (dict(base_left, 车型名称="皓影 2026款 Pro 四驱版 73kWh"), component_row("仅懂车帝", "Pro 四驱版 66kWh")),
        (dict(base_left, 车型名称="皓影 2026款 Pro 四驱版 700km"), component_row("仅懂车帝", "Pro 四驱版 600km")),
    ]
    for left, right in conflict_cases:
        with_id = MODULE.prepare_rows([left, right], 2022)
        assert all("跨源归并ID" not in row for row in with_id)

    right_a = component_row("仅懂车帝", "Pro 四驱版 智享")
    right_b = component_row("仅懂车帝", "Pro 四驱版 智领")
    ambiguous = MODULE.prepare_rows([base_left, right_a, right_b], 2022)
    assert all("跨源归并ID" not in row for row in ambiguous)


def test_same_source_frontend_fold_and_existing_multi_id_competitor_are_not_stolen():
    autohome = component_row("仅汽车之家", "皓影 2026款 Pro 四驱版", model_id="77904")
    duplicate_autohome = dict(autohome, 官方指导价="13.98万")
    dongchedi = component_row("仅懂车帝", "Pro 四驱版")
    folded = MODULE.prepare_rows([autohome, duplicate_autohome, dongchedi], 2022)
    assert all("跨源归并ID" not in row for row in folded)

    existing_multi = component_row(
        "汽车之家+懂车帝",
        "皓影 2026款 已核验版",
        model_id="77904",
    )
    competed = MODULE.prepare_rows([autohome, dongchedi, existing_multi], 2022)
    assert all("跨源归并ID" not in row for row in competed)


def test_visible_card_formula_counts_annotated_components_without_payload_loss():
    autohome = component_row("仅汽车之家", "皓影 2026款 e:HEV 四驱尊耀版")
    yiche = component_row("仅易车", "26款 e:HEV 2.0L 四驱锐·尊耀版")
    untouched = listed({
        "数据来源": "仅懂车帝",
        "品牌": "甲",
        "车系": "甲车系",
        "车型名称": "甲 2026款 独立版",
        "年款": "2026",
        "官方指导价": "18.88万",
    })
    prepared = MODULE.prepare_rows([autohome, yiche, untouched], 2022)

    stats = MODULE.visible_card_stats(prepared)

    assert stats == {
        "payload_rows": 3,
        "visible_rows": 2,
        "visible_single": 1,
        "visible_multi": 1,
        "visible_rate": 50.0,
    }

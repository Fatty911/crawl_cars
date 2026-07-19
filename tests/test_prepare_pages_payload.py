import importlib.util
import json
from pathlib import Path


def listed(row):
    row = dict(row)
    row.setdefault("官方指导价", "12.98万")
    row.setdefault("上市时间", "2026-01-01")
    return row


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "prepare_pages_payload.py"
SPEC = importlib.util.spec_from_file_location("prepare_pages_payload", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_prepare_rows_keeps_recent_sparse_rows_and_meaningful_zeroes():
    rows = [
        {"品牌": "甲", "车型名称": "旧车 2021款", "年款": "2021", "远程启动": "标配"},
        {"品牌": "甲", "车型名称": "新车 2024款", "年款": "", "远程启动": "-", "气囊数": 0},
        {"品牌": "甲", "车型名称": "无年款", "年款": "-", "数据来源": "仅懂车帝"},
        {"品牌": "乙", "车系": "乙车系", "车型名称": "易车无年款", "年款": "-", "数据来源": "仅易车", "配置A": "-"},
        listed({"品牌": "乙", "车系": "乙车系", "车型名称": "易车旧款", "年款": "2021", "数据来源": "仅易车", "易车上市状态": "approved", "车款ID": "1001"}),
        listed({"品牌": "乙", "车系": "乙车系", "车型名称": "易车新款 2026款", "年款": "2026", "数据来源": "仅易车", "易车上市状态": "approved", "车款ID": "1001", "配置A": "有"}),
    ]

    assert MODULE.prepare_rows(rows, 2022) == [
        {"品牌": "甲", "车型名称": "新车 2024款", "气囊数": 0},
        listed({"品牌": "乙", "车系": "乙车系", "车型名称": "易车新款 2026款", "年款": "2026", "数据来源": "仅易车", "易车上市状态": "approved", "车款ID": "1001", "配置A": "有"}),
    ]


def test_main_supports_atomic_in_place_compaction(tmp_path, monkeypatch):
    payload = tmp_path / "latest.json"
    payload.write_text(
        json.dumps(
            [
                {"品牌": "甲", "车型名称": "甲 2022款", "年款": "2022", "配置A": "-", "配置B": "有"},
                {"品牌": "乙", "车型名称": "乙 2021款", "年款": "2021", "配置B": "有"},
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
        {"品牌": "甲", "车型名称": "甲 2022款", "年款": "2022", "配置B": "有"}
    ]
    assert payload.stat().st_size < before


def test_prepare_rows_rejects_blank_brand_and_model():
    rows = [
        {"品牌": " ", "车型名称": "A 2026款", "年款": "2026"},
        {"品牌": "甲", "车型名称": "-", "年款": "2026"},
        {"品牌": "甲", "车型名称": "A 2026款", "年款": "2026"},
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

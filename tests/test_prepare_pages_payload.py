import importlib.util
import json
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "prepare_pages_payload.py"
SPEC = importlib.util.spec_from_file_location("prepare_pages_payload", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_prepare_rows_keeps_recent_sparse_rows_and_meaningful_zeroes():
    rows = [
        {"车型名称": "旧车 2021款", "年款": "2021", "远程启动": "标配"},
        {"车型名称": "新车 2024款", "年款": "", "远程启动": "-", "气囊数": 0},
        {"车型名称": "无年款", "年款": "-", "数据来源": "仅懂车帝"},
        {"车型名称": "易车无年款", "年款": "-", "数据来源": "仅易车", "配置A": "-"},
        {"车型名称": "易车旧款", "年款": "2021", "数据来源": "仅易车"},
    ]

    assert MODULE.prepare_rows(rows, 2022) == [
        {"车型名称": "新车 2024款", "气囊数": 0},
        {"车型名称": "易车无年款", "数据来源": "仅易车"},
    ]


def test_main_supports_atomic_in_place_compaction(tmp_path, monkeypatch):
    payload = tmp_path / "latest.json"
    payload.write_text(
        json.dumps(
            [
                {"车型名称": "甲 2022款", "年款": "2022", "配置A": "-", "配置B": "有"},
                {"车型名称": "乙 2021款", "年款": "2021", "配置B": "有"},
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
        {"车型名称": "甲 2022款", "年款": "2022", "配置B": "有"}
    ]
    assert payload.stat().st_size < before

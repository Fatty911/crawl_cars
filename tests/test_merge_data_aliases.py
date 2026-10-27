from __future__ import annotations

from unittest import mock

from scripts.merge_data import (
    _load_header_aliases,
    header_alias_lookup,
    normalize_audited_publish_header,
)


def test_alias_lookup_returns_none_when_config_is_empty() -> None:
    # The committed config ships an empty aliases list.
    aliases = _load_header_aliases()
    assert isinstance(aliases, dict)
    assert header_alias_lookup("NOMI Mate 3.0") is None


def test_alias_lookup_degrades_on_corrupt_config() -> None:
    with mock.patch("scripts.merge_data.open", mock.mock_open(read_data="{not json")):
        with mock.patch("scripts.merge_data._HEADER_ALIASES", None):
            assert _load_header_aliases() == {}


def test_normalize_returns_stripped_original_without_alias_or_v4_suffix() -> None:
    # 未配置别名且无 v4 后缀、不在 HEADER_MAP 的列名原样返回（去掉首尾空白）
    assert normalize_audited_publish_header(" 未知属性X ") == "未知属性X"


def test_normalize_applies_configured_alias_canonical() -> None:
    with mock.patch(
        "scripts.merge_data.header_alias_lookup",
        return_value={"canonical": "车载智能系统", "value": "NOMI Mate 3.0"},
    ):
        assert normalize_audited_publish_header("NOMI Mate 3.0") == "车载智能系统"


def test_normalize_folds_v4_value_suffix_back_to_canonical_attribute() -> None:
    assert (
        normalize_audited_publish_header("driving_assist_chip_v4_NVIDIA DRIVE Orin X")
        == "辅助驾驶芯片"
    )


import json
import os
import subprocess
import sys
from pathlib import Path

from scripts.merge_data import _merge_existing_with_source
from scripts.prepare_pages_payload import normalize_publish_row_headers

REPO_ROOT = Path(__file__).resolve().parent.parent

# 子进程内固定调用链：真实 _merge_existing_with_source + normalize_publish_row_headers。
_SUBPROCESS_PROBE = """
import json, sys
sys.path.insert(0, sys.argv[1])
from scripts.merge_data import _merge_existing_with_source
from scripts.prepare_pages_payload import normalize_publish_row_headers

current = json.loads(sys.argv[2])
incoming = json.loads(sys.argv[3])
merged = _merge_existing_with_source(current, "懂车帝", "易车", incoming)
normalized = normalize_publish_row_headers(merged)
print(json.dumps({
    "merged_keys": list(merged),
    "merged_screen": {k: v for k, v in merged.items() if "屏" in k},
    "merged_types": {k: type(v).__name__ for k, v in merged.items()},
    "normalized_screen": {k: v for k, v in normalized.items() if "屏" in k},
}, ensure_ascii=False))
"""

_SCREEN_CURRENT = {
    "品牌": "奔驰",
    "车系": "奔驰C级",
    "车型名称": "26款 C 260 L 运动轿车",
    "车款ID": "181360",
    "年款": "2026",
    "价格": "35.28",
    "数据来源": "懂车帝",
}
_SCREEN_INCOMING = {
    "数据来源": "易车",
    "中控屏幕尺寸": "●",
    "中控屏幕尺寸(英寸)": "11.9",
}


def _run_probe(seed: str, current: dict, incoming: dict) -> dict:
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = seed
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            _SUBPROCESS_PROBE,
            str(REPO_ROOT),
            json.dumps(current, ensure_ascii=False),
            json.dumps(incoming, ensure_ascii=False),
        ],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def _seed_results(seeds, current=_SCREEN_CURRENT, incoming=_SCREEN_INCOMING):
    return {seed: _run_probe(seed, current, incoming) for seed in seeds}


def test_merge_plus_normalize_screen_value_is_identical_across_hash_seeds() -> None:
    # 真实子进程：同输入不同 PYTHONHASHSEED 必须给出同一字面值。
    results = _seed_results(("1", "2", "3", "5", "7", "11", "19", "31"))
    rendered = {seed: r["normalized_screen"]["中控屏幕尺寸"] for seed, r in results.items()}
    assert len(set(rendered.values())) == 1, rendered
    value = rendered["1"]
    assert "11.9" in value and "●" in value, value


def test_merge_key_order_is_identical_across_hash_seeds() -> None:
    results = _seed_results(("1", "5", "31"))
    orders = {seed: tuple(r["merged_keys"]) for seed, r in results.items()}
    assert len(set(orders.values())) == 1, orders
    # 既有字段前缀仍按 current 原次序在前。
    order = list(orders["1"])
    assert order[: len(_SCREEN_CURRENT)] == list(_SCREEN_CURRENT), order


def test_screen_atoms_kept_textual_and_never_coerced_to_measurement() -> None:
    results = _seed_results(("1", "5", "31"))
    for seed, r in results.items():
        # 原始 incoming 单元格保持原字面值：● 不变成数值，11.9 不被吞。
        assert r["merged_screen"]["中控屏幕尺寸"] == "●", seed
        assert r["merged_screen"]["中控屏幕尺寸(英寸)"] == "11.9", seed
        assert r["merged_types"]["中控屏幕尺寸"] == "str", seed
        segments = r["normalized_screen"]["中控屏幕尺寸"].split("|")
        assert sorted(segments) == ["11.9", "●"], (seed, segments)


def test_merge_is_insensitive_to_incoming_key_insertion_order() -> None:
    ordered = {"数据来源": "易车", "中控屏幕尺寸": "●", "中控屏幕尺寸(英寸)": "11.9"}
    reversed_order = {"中控屏幕尺寸(英寸)": "11.9", "数据来源": "易车", "中控屏幕尺寸": "●"}
    first = _run_probe("1", _SCREEN_CURRENT, ordered)
    second = _run_probe("1", _SCREEN_CURRENT, reversed_order)
    assert first["merged_keys"] == second["merged_keys"]
    assert first["merged_screen"] == second["merged_screen"]
    assert first["normalized_screen"] == second["normalized_screen"]


def test_merge_keeps_current_prefix_values_types_and_leaves_inputs_untouched() -> None:
    current = dict(_SCREEN_CURRENT)
    incoming = dict(_SCREEN_INCOMING)
    current_snapshot = dict(current)
    incoming_snapshot = dict(incoming)
    merged = _merge_existing_with_source(current, "懂车帝", "易车", incoming)
    assert current == current_snapshot
    assert incoming == incoming_snapshot
    assert list(merged)[: len(current_snapshot)] == list(current_snapshot)
    for key, value in current_snapshot.items():
        assert merged[key] == value
        assert type(merged[key]) is type(value)
    # 新增字段追加在既有前缀之后，原样保留 incoming 文本。
    assert merged["中控屏幕尺寸"] == "●"
    assert merged["中控屏幕尺寸(英寸)"] == "11.9"


def test_merge_keeps_source_priority_segmentation_negation_and_zero() -> None:
    segmented = _merge_existing_with_source(
        {"品牌": "奔驰", "数据来源": "懂车帝", "中控屏幕尺寸": "懂车帝:11.9"},
        "懂车帝",
        "易车",
        {"数据来源": "易车", "中控屏幕尺寸": "●"},
    )
    assert segmented["中控屏幕尺寸"] == "懂车帝:11.9|易车:●"

    zero = _merge_existing_with_source(
        {"纯电续航(km)": "605", "数据来源": "懂车帝"},
        "懂车帝",
        "易车",
        {"纯电续航(km)": "0", "数据来源": "易车"},
    )
    assert zero["纯电续航(km)"] == "懂车帝:605|易车:0"

    kept_when_incoming_blank = _merge_existing_with_source(
        {"中控屏幕尺寸": "11.9", "数据来源": "懂车帝"},
        "懂车帝",
        "易车",
        {"中控屏幕尺寸": "-", "数据来源": "易车"},
    )
    assert kept_when_incoming_blank["中控屏幕尺寸"] == "11.9"

    filled_when_current_blank = _merge_existing_with_source(
        {"中控屏幕尺寸": "-", "数据来源": "懂车帝"},
        "懂车帝",
        "易车",
        {"中控屏幕尺寸": "11.9", "数据来源": "易车"},
    )
    assert filled_when_current_blank["中控屏幕尺寸"] == "11.9"


def test_single_screen_field_without_collision_stays_verbatim() -> None:
    # 单字段无别名碰撞时不得改写或拼接任何字面值。
    for column, value in (("中控屏幕尺寸", "●"), ("中控屏幕尺寸(英寸)", "11.9")):
        current = {"品牌": "奔驰", "数据来源": "懂车帝"}
        incoming = {"数据来源": "易车", column: value}
        merged = _merge_existing_with_source(current, "懂车帝", "易车", incoming)
        assert merged[column] == value
        assert merged["品牌"] == "奔驰"
        normalized = normalize_publish_row_headers({column: value})
        assert normalized == {normalize_audited_publish_header(column): value}


import copy

from scripts.merge_data import _collapse, dedupe_merged_rows

FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "merge_alias_real_peer_cluster_20261015.json"

# 子进程内固定调用链：真实 18 行 fixture → 生产 dedupe_merged_rows → normalize_publish_row_headers。
_FULLPATH_PROBE = """
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from scripts.merge_data import dedupe_merged_rows
from scripts.prepare_pages_payload import normalize_publish_row_headers

rows = json.loads(Path(sys.argv[2]).read_bytes())
merged = dedupe_merged_rows(rows)
normalized = [normalize_publish_row_headers(r) if isinstance(r, dict) else r for r in merged]
# 键序另列一份：sort_keys=True 只整理对象键，值里的 "●|11.9" 原子串一字不动。
print(json.dumps({"n_input": len(rows), "n_merged": len(merged), "rows": normalized,
                  "key_orders": [list(r) for r in normalized]},
                 ensure_ascii=False, sort_keys=True))
"""


def _fullpath_probe(seed: str) -> dict:
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = seed
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [sys.executable, "-B", "-c", _FULLPATH_PROBE, str(REPO_ROOT), str(FIXTURE_PATH)],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_real_peer_cluster_full_path_signature_is_identical_across_hash_seeds() -> None:
    # 真实 18 peer 输入：dedupe_merged_rows 全路径 + 发布列归一，跨哈希种子必须逐行逐值一致。
    signatures = {seed: _fullpath_probe(seed) for seed in ("1", "3")}
    # 12 行逐行逐值 + 逐行键序都要一致（键序漂移同样算不确定输出）。
    rendered = {seed: json.dumps([p["rows"], p["key_orders"]], ensure_ascii=False, sort_keys=True)
                for seed, p in signatures.items()}
    assert len(set(rendered.values())) == 1, rendered
    signature = signatures["1"]
    assert signature["n_input"] == 18, signature["n_input"]
    assert signature["n_merged"] == 12, signature["n_merged"]
    ids = {str(r.get("车款ID") or "").strip() for r in signature["rows"]} - {"", "-"}
    assert len(ids) == 12, sorted(ids)

_COLLAPSE_SEED_PROBE = """
import json, sys
sys.path.insert(0, sys.argv[1])
from scripts.merge_data import _collapse
rows = json.loads(sys.argv[2])
out = _collapse(rows, lambda r: ("unit",))
print(json.dumps({"keys": list(out[0]), "screen": out[0].get("中控屏幕尺寸"),
                  "row": out[0]}, ensure_ascii=False, sort_keys=True))
"""

_REAL_TARGET_IDS = ("181357", "181359", "181360", "185491", "189115")


def _fixture_rows() -> list:
    return json.loads(FIXTURE_PATH.read_bytes())


def test_real_peer_fixture_input_untouched_and_identity_columns_kept() -> None:
    raw = _fixture_rows()
    snapshot = copy.deepcopy(raw)
    assert len(raw) == 18
    merged = dedupe_merged_rows(raw)
    # 输入行按原字节内容不变（折叠返回新列表，不得就地改写）。
    assert raw == snapshot
    expected = {str(r.get("车款ID")).strip(): (r.get("年款"), r.get("官方指导价"))
                for r in snapshot if str(r.get("车款ID") or "").strip() not in ("", "-")}
    assert len(expected) == 12
    got = {str(r.get("车款ID")).strip(): (r.get("年款"), r.get("官方指导价"))
           for r in merged if str(r.get("车款ID") or "").strip() not in ("", "-")}
    # 12 个非空 SKU ID 一个不少，且 ID 自己的年款/价格身份没被邻居改写。
    assert got == expected
    assert len(merged) == 12


def test_real_peer_screen_cells_are_text_with_both_atoms_kept() -> None:
    merged = dedupe_merged_rows(_fixture_rows())
    by_id = {str(r.get("车款ID")).strip(): r for r in merged}
    for sku_id in _REAL_TARGET_IDS:
        row = by_id[sku_id]
        raw_cell = row["中控屏幕尺寸"]
        assert type(raw_cell) is str, (sku_id, type(raw_cell))
        assert raw_cell == "●", (sku_id, raw_cell)
        normalized = normalize_publish_row_headers(row)["中控屏幕尺寸"]
        assert type(normalized) is str, (sku_id, type(normalized))
        assert sorted(normalized.split("|")) == ["11.9", "●"], (sku_id, normalized)
        # 支持符号不得被当成测量值：整格无法按数值解析。
        try:
            float(normalized)
        except ValueError:
            pass
        else:  # pragma: no cover - 只有回归才走这里
            raise AssertionError(f"{sku_id} 把 ● 合成了数值: {normalized!r}")


def test_real_peer_row_without_inch_source_does_not_invent_measurement() -> None:
    merged = dedupe_merged_rows(_fixture_rows())
    by_id = {str(r.get("车款ID")).strip(): r for r in merged}
    # 185560 的源侧只有支持符号；不得凭空出现别行的英寸数值。
    normalized = normalize_publish_row_headers(by_id["185560"])["中控屏幕尺寸"]
    assert normalized == "●", normalized
    assert "11.9" not in normalized


def test_collapse_keeps_keeper_prefix_types_zero_and_stable_new_key_order() -> None:
    keeper = {
        "品牌": "测试品牌",
        "车系": "测试车系",
        "年款": "2026",
        "官方指导价": "10.00万",
        "数据来源": "汽车之家+懂车帝",
        "中控屏幕尺寸": "●",
        "纯电续航(km)": "0",
    }
    tail_a = {"数据来源": "懂车帝", "中控屏幕尺寸(英寸)": "11.9", "远程启动": "●", "HUD抬头显示": "○"}
    tail_b = {"HUD抬头显示": "○", "远程启动": "●", "中控屏幕尺寸(英寸)": "11.9", "数据来源": "懂车帝"}
    first = _collapse([dict(keeper), dict(tail_a)], lambda r: ("unit",))
    second = _collapse([dict(keeper), dict(tail_b)], lambda r: ("unit",))
    assert len(first) == 1 and len(second) == 1
    prefix = list(keeper)
    # 既有前缀（含空的/零值/类型）原样在前，逐值逐类型保留。
    for out in (first[0], second[0]):
        assert list(out)[: len(prefix)] == prefix, list(out)[: len(prefix)]
    assert first[0]["中控屏幕尺寸"] == "●"
    assert first[0]["纯电续航(km)"] == "0"
    assert type(first[0]["纯电续航(km)"]) is str
    assert first[0]["中控屏幕尺寸(英寸)"] == "11.9"
    # 只改另一行键插入顺序 ⇒ 出口键序、值完全一致。
    assert list(first[0]) == list(second[0])
    assert first[0] == second[0]


def test_collapse_backfills_single_real_candidate_only() -> None:
    # keeper 这一格空着（不是显式否定 `-`，`-` 本身算一个候选），簇内恰好一个真实候选 ⇒ 回填。
    keeper = {"车系": "测试车系", "数据来源": "汽车之家+懂车帝", "远程启动": ""}
    single = _collapse(
        [dict(keeper), {"数据来源": "懂车帝", "远程启动": "●"}], lambda r: ("unit",))
    assert single[0]["远程启动"] == "●"
    two = _collapse(
        [dict(keeper), {"数据来源": "懂车帝", "远程启动": "●"},
         {"数据来源": "汽车之家", "远程启动": "○"}],
        lambda r: ("unit",))
    # 两个互异候选 ⇒ 留空，不挑一个写成事实。
    assert str(two[0].get("远程启动") or "").strip() == "", two[0].get("远程启动")
    # keeper 自己写着显式否定时，另一行的 `●` 与之互异 ⇒ 仍是两个候选，不许改写成标配。
    neg_keeper = _collapse(
        [{"车系": "测试车系", "数据来源": "汽车之家+懂车帝", "远程启动": "-"},
         {"数据来源": "懂车帝", "远程启动": "●"}], lambda r: ("unit",))
    assert neg_keeper[0]["远程启动"] == "-"


def test_collapse_merges_three_rows_deterministically_across_seeds() -> None:
    rows = [
        {"车系": "测试车系", "数据来源": "汽车之家+懂车帝", "中控屏幕尺寸": "●",
         "中控屏幕尺寸(英寸)": "11.9", "远程启动": ""},
        {"车系": "测试车系", "数据来源": "懂车帝", "中控屏幕尺寸": "11.9", "远程启动": "●"},
        {"车系": "测试车系", "数据来源": "汽车之家", "HUD抬头显示": "○", "远程启动": "●"},
    ]
    signatures = set()
    for seed in ("1", "3"):
        env = dict(os.environ)
        env["PYTHONHASHSEED"] = seed
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        proc = subprocess.run(
            [sys.executable, "-B", "-c", _COLLAPSE_SEED_PROBE, str(REPO_ROOT),
             json.dumps(rows, ensure_ascii=False)],
            cwd=str(REPO_ROOT), env=env, capture_output=True, text=True,
            encoding="utf-8", timeout=120,
        )
        assert proc.returncode == 0, proc.stderr
        signatures.add(proc.stdout)
    # 跨种子同一输入 ⇒ 同一键序、同一行内容（值里的原子串原样保留）。
    assert len(signatures) == 1, signatures
    rendered = json.loads(signatures.pop())
    # keeper 这格本来就写着 `●` ⇒ 不被别行的 `11.9` 顶掉，也不被改写成数值。
    assert rendered["row"]["中控屏幕尺寸"] == "●", rendered["row"]["中控屏幕尺寸"]
    assert rendered["row"]["中控屏幕尺寸(英寸)"] == "11.9"
    # keeper 既有键（含已存在的 `远程启动`）保持原序在前；唯一新增的键按排序追加在后。
    assert rendered["keys"] == [
        "车系", "数据来源", "中控屏幕尺寸", "中控屏幕尺寸(英寸)", "远程启动", "HUD抬头显示",
    ], rendered["keys"]
    assert rendered["row"]["远程启动"] == "●"
    assert rendered["row"]["HUD抬头显示"] == "○"

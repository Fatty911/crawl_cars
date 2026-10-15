"""remerge_published_data.py 的判据：用修好的归并逻辑重跑已发布数据。

背景：CNB 核时限额用完，发布面数据要靠别的平台重新生成。本脚本吃的输入是
**上一轮真实爬取的合并产物**（`merged_<date>.json`，即发布面 latest），
只补跑修好的归并段，**不重新爬取**。

为什么可以直接吃这份输入（脚本里也写了）：归并键含年款 ⇒ 跨年款永不合并，
因此在已过年款过滤的数据上补跑 dedupe，与在流水线里跑结果一致。
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "remerge_published_data.py"

_spec = importlib.util.spec_from_file_location("remerge_published_data", SCRIPT)
RM = importlib.util.module_from_spec(_spec)
try:
    _spec.loader.exec_module(RM)
except SystemExit:
    pass

_OPTS = ["-c", "import sys; sys.path.insert(0, 'scripts')", ]


def _row(sku, name, series, year, price, source, series_id):
    return {
        "品牌": "测试品牌", "车系": series, "车系ID": series_id,
        "车型名称": name, "年款": year, "车款ID": sku,
        "官方指导价": price, "数据来源": source,
    }


def _run_cli(tmp_path, rows, date="20261015", extra=()):
    merged = tmp_path / f"merged_{date}.json"
    merged.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--merged", str(merged), "--date", date,
         "--outdir", str(tmp_path)] + list(extra),
        capture_output=True, text=True, cwd=str(ROOT),
    )
    return proc


def _pad(rows, target=1200):
    """把样本垫到超过 MIN_ROWS，避免触发"行数太少"闸门而测不到目标行为。"""
    out = list(rows)
    for i in range(target - len(rows)):
        out.append(_row(f"F{i}", f"填充车型{i}", "甲车系", "2026", "10.00万", "仅汽车之家", "100"))
    return out


def test_remerge_collapses_duplicate_sku_ids() -> None:
    """同车款ID + 同年款 + 异名/异车系ID 必须归并（乐道L90 76215 与领克900 72145 实测形状）。"""
    rows = [
        _row("76215", "六座版Pro", "乐道L90", "2026", "26.58万", "懂车帝+汽车之家", "25234"),
        _row("76215", "乐道L90 2026款 Pro 六座版", "乐道L90", "2026", "26.58万",
             "汽车之家+懂车帝(车系级)", "25234"),
        _row("76215", "乐道L90 2026款 Pro 六座版", "乐道L90", "2026", "26.58万", "仅汽车之家", "8045"),
        _row("72145", "1.5T Halo 六座", "领克900", "2025", "30.99万", "懂车帝+汽车之家", "25161"),
        _row("72145", "领克900 2025款 1.5T Halo 6座", "领克900", "2025", "30.99万",
             "汽车之家+懂车帝", "8002"),
    ]
    merged = RM.remerge(_pad(rows))
    kept = {str(r.get("车款ID")) for r in merged if str(r.get("车款ID")) in ("76215", "72145")}
    assert kept == {"76215", "72145"}, "重复车款ID 没被归并（或把不同 ID 也并了）：%s" % kept
    before_groups, before_rows = RM.dup_id_groups(rows)
    after_groups, after_rows = RM.dup_id_groups(merged)
    assert after_groups < before_groups, "重复车款ID 组数没减少"


def test_remerge_keeps_different_years_apart() -> None:
    """年款不同 = 不同 SKU（用户裁定），一行都不许少。"""
    rows = [
        _row("74526", "凯翼昆仑L8 2025款 通畅版", "凯翼昆仑L8", "2025", "19.68万", "仅汽车之家", "5001"),
        _row("74526", "凯翼昆仑L8 2026款 通畅版", "凯翼昆仑L8", "2026", "19.68万", "仅汽车之家", "5001"),
    ]
    merged = RM.remerge(_pad(rows))
    kept = [r for r in merged if str(r.get("车款ID")) == "74526"]
    assert len(kept) == 2, "同车款ID 不同年款被归并了（%d 行）" % len(kept)
    assert {str(r.get("年款")) for r in kept} == {"2025", "2026"}


def test_remerge_is_idempotent() -> None:
    """归并本身必须稳定：审计/校验脚本会对已发布数据再跑一次。"""
    rows = _pad([
        _row("76215", "六座版Pro", "乐道L90", "2026", "26.58万", "懂车帝+汽车之家", "25234"),
        _row("76215", "乐道L90 2026款 Pro 六座版", "乐道L90", "2026", "26.58万",
             "汽车之家+懂车帝(车系级)", "8045"),
    ])
    once = RM.remerge(rows)
    twice = RM.remerge(once)
    assert len(once) == len(twice), "重合并不幂等：%d vs %d" % (len(once), len(twice))


def test_remerge_fails_closed_on_shrink_beyond_threshold() -> None:
    """掉行超过阈值必须 fail closed，不许悄悄把数据并没。"""
    # 造一个会被大幅归并的输入：大量同 ID 同配置的重复行。
    # 2400 -> 1200（掉 50%），仍高于 MIN_ROWS=1000 ⇒ 才能撞到"掉行超阈值"而不是"行数太少"。
    rows = []
    for i in range(1200):
        rows.append(_row(f"D{i}", "同一配置", "甲车系", "2026", "10.00万", "仅汽车之家", "100"))
        rows.append(_row(f"D{i}", "同一配置", "甲车系", "2026", "10.00万", "仅懂车帝", "100"))
    # 直接调函数：减少 50% >> 8% 阈值
    try:
        RM.remerge(rows, max_drop_pct=8.0)
    except SystemExit as exc:
        assert "减少" in str(exc), "报错信息看不出是掉行超限：%s" % exc
    else:
        raise AssertionError("掉行 50% 竟然没有 fail closed")


def test_remerge_fails_closed_on_tiny_input() -> None:
    rows = [_row("1", "只有一行", "甲车系", "2026", "10.00万", "仅汽车之家", "100")]
    try:
        RM.remerge(rows)
    except SystemExit as exc:
        assert "行" in str(exc)
    else:
        raise AssertionError("输入少于 %d 行竟然没拦" % RM.MIN_ROWS)


def test_cli_with_filtered_only_removes_duplicates(tmp_path) -> None:
    """给 --filtered 时：发布行集（按 车款ID+年款）一个都不许丢，只许折叠重复。"""
    rows = _pad([
        _row("76215", "六座版Pro", "乐道L90", "2026", "26.58万", "懂车帝+汽车之家", "25234"),
        _row("76215", "乐道L90 2026款 Pro 六座版", "乐道L90", "2026", "26.58万",
             "汽车之家+懂车帝(车系级)", "8045"),
    ])
    merged = tmp_path / "merged_20261015.json"
    merged.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    # 现网 filtered 是收窄列（34 列）的形态，这里只保留归并需要的字段即可
    keep = ("品牌", "车系", "车系ID", "车型名称", "年款", "车款ID", "官方指导价", "数据来源")
    filt_rows = [{k: r[k] for k in keep if k in r} for r in rows]
    filt = tmp_path / "filtered_cars_20261015.json"
    filt.write_text(json.dumps(filt_rows, ensure_ascii=False), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--merged", str(merged), "--filtered", str(filt),
         "--date", "20261015", "--outdir", str(tmp_path)],
        capture_output=True, text=True, cwd=str(ROOT))
    assert proc.returncode == 0, proc.stderr[-800:]
    stats = json.loads(proc.stdout.strip())
    assert stats["filtered_dup_sku_groups_after"] < stats["filtered_dup_sku_groups_before"], \
        "filtered 的重复车款ID 组没减少：%s" % stats
    after = json.loads((tmp_path / "filtered_cars_20261015.json").read_text(encoding="utf-8"))
    assert len(after) < len(filt_rows), "filtered 行数没减少（重复没折叠）"
    # 行集守恒：按 (车款ID, 年款) 一个都不许丢
    before_keys = {(str(r.get("车款ID", "")).strip(), str(r.get("年款", "")))
                   for r in filt_rows if str(r.get("车款ID", "")).strip()}
    after_keys = {(str(r.get("车款ID", "")).strip(), str(r.get("年款", "")))
                  for r in after if str(r.get("车款ID", "")).strip()}
    assert before_keys == after_keys, "去重把 SKU 丢掉了：少了 %s" % sorted(before_keys - after_keys)[:5]


def test_cli_writes_all_four_outputs(tmp_path) -> None:
    rows = _pad([
        _row("76215", "六座版Pro", "乐道L90", "2026", "26.58万", "懂车帝+汽车之家", "25234"),
        _row("76215", "乐道L90 2026款 Pro 六座版", "乐道L90", "2026", "26.58万",
             "汽车之家+懂车帝(车系级)", "8045"),
    ])
    proc = _run_cli(tmp_path, rows)
    assert proc.returncode == 0, proc.stderr[-800:]
    for name in ("merged_20261015.json", "merged_20261015.csv",
                 "filtered_cars_20261015.json", "filtered_cars_20261015.csv"):
        assert (tmp_path / name).exists(), "缺少产出 %s" % name
    stats = json.loads(proc.stdout.strip())
    assert stats["removed_by_sku_dedupe"] > 0, "没消掉任何重复行：%s" % stats
    assert stats["dup_sku_groups_after"] < stats["dup_sku_groups_before"]
    after = json.loads((tmp_path / "merged_20261015.json").read_text(encoding="utf-8"))
    assert len(after) == stats["merged_rows_after"], "落盘行数与打印读数不一致"

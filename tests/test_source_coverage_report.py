"""覆盖率报告必须在发布前暴露「某源输入很多但几乎不入选」的形态背离。"""

from __future__ import annotations

import importlib.util
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _merge_data():
    spec = importlib.util.spec_from_file_location("merge_data", ROOT / "scripts" / "merge_data.py")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except SystemExit:  # pragma: no cover - module-level CLI guard
        pass
    return module


MD = _merge_data()


def _row(source, **extra):
    row = {"数据来源": source, "品牌": "测试品牌", "车系": "测试车系", "车型名称": "2026款 测试", "年款": "2026"}
    row.update(extra)
    return row


def test_report_splits_counts_by_source_membership() -> None:
    rows = [
        _row("仅易车"),
        _row("懂车帝+易车"),
        _row("仅懂车帝"),
    ]
    kept = [_row("懂车帝+易车")]
    report = MD.build_source_coverage_report(rows, kept)
    assert report["易车"]["rows"] == 2
    assert report["懂车帝"]["rows"] == 2
    assert report["汽车之家"]["rows"] == 0
    assert report["易车"]["kept"] == 1


def test_report_records_the_first_blocking_condition() -> None:
    rows = [_row("仅易车")]
    report = MD.build_source_coverage_report(rows, [])
    blockers = report["易车"]["first_blocked_by_condition"]
    assert blockers
    assert sum(blockers.values()) == len(rows)
    assert "PASS" not in blockers


def test_report_shares_are_fractions_of_their_own_population() -> None:
    rows = [_row("仅易车"), _row("仅懂车帝")]
    kept = [_row("仅懂车帝")]
    report = MD.build_source_coverage_report(rows, kept)
    assert report["易车"]["share_before"] == 0.5
    assert report["易车"]["share_after"] == 0.0
    assert report["懂车帝"]["share_before"] == 0.5
    assert report["懂车帝"]["share_after"] == 1.0


def test_writing_the_report_emits_a_collapse_warning(capsys, tmp_path) -> None:
    """易车那种「输入 35% / 入选 9%」的腰斩必须打出告警，而不是静默发布。"""
    rows = [_row("仅易车") for _ in range(3)] + [_row("仅懂车帝", **{
        c["field"]: "1" for c in MD.FILTER_CONDITIONS if c.get("type") == "range"
    })]
    kept = [row for row in rows if MD.filter_car(row)]
    report = MD.report_source_coverage(str(tmp_path), "20260101", rows, kept)
    out = capsys.readouterr().out
    assert (tmp_path / "source_coverage_20260101.json").is_file()
    assert report["易车"]["share_after"] < report["易车"]["share_before"] * 0.5
    assert "腰斩" in out


def test_empty_filtered_set_does_not_raise() -> None:
    report = MD.build_source_coverage_report([_row("仅易车")], [])
    assert report["易车"]["share_after"] == 0.0

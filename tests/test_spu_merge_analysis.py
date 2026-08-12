"""spu_merge_analysis.py SPU 归并分析测试。"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "spu_merge_analysis.py"


def _run(data_path: Path, output_path: Path) -> dict:
    proc = subprocess.run(
        ["python3", str(SCRIPT), "--data", str(data_path), "--output", str(output_path)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(output_path.read_text(encoding="utf-8"))


def _rows(tmp_path: Path) -> Path:
    rows = [
        # 车系 A：多源车系——2 行多源 + 1 行单源（同款命名差异 → 归并候选）
        {"品牌": "甲", "车系": "系A", "车型名称": "2023款 GT-Line", "年款": "2023", "数据来源": "汽车之家+懂车帝"},
        {"品牌": "甲", "车系": "系A", "车型名称": "2023款 GT-Line", "年款": "2023", "数据来源": "懂车帝+汽车之家"},
        {"品牌": "甲", "车系": "系A", "车型名称": "23款 671km 后驱GT-Line", "年款": "2023", "数据来源": "仅易车"},
        # 车系 B：纯单源车系（整系无多源 → 不算 SPU 内归并）
        {"品牌": "乙", "车系": "系B", "车型名称": "2024款 标准版", "年款": "2024", "数据来源": "仅易车"},
        # 车系 C：多源车系但单源行年款不同（不得配对）
        {"品牌": "丙", "车系": "系C", "车型名称": "2025款 Pro", "年款": "2025", "数据来源": "汽车之家+懂车帝"},
        {"品牌": "丙", "车系": "系C", "车型名称": "2024款 Pro", "年款": "2024", "数据来源": "仅汽车之家"},
    ]
    p = tmp_path / "rows.json"
    p.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return p


def test_single_source_classification(tmp_path: Path) -> None:
    data = _rows(tmp_path)
    out = tmp_path / "report.json"
    r = _run(data, out)
    # 单源 3 行（系A 1 + 系B 1 + 系C 1）；车系级单源 1（系B）；SPU 内单源 2（系A、系C）
    assert r["total_single"] == 3
    assert r["series_only_single"] == 1
    assert r["spu_inner_single"] == 2
    assert r["multi_series_count"] == 2  # 系A、系C


def test_merge_candidate_same_year(tmp_path: Path) -> None:
    data = _rows(tmp_path)
    out = tmp_path / "report.json"
    r = _run(data, out)
    # 系A 的 23款 vs 2023款 是归并候选（同年款、核心 token 重叠）
    cand = [c for c in r["merge_candidates_sample"] if c["series"] == "系A"]
    assert len(cand) == 1
    assert cand[0]["single_row"] == "23款 671km 后驱GT-Line"
    assert cand[0]["multi_row"] == "2023款 GT-Line"
    assert cand[0]["single_year"] == cand[0]["multi_year"] == "2023"


def test_merge_candidate_different_year_excluded(tmp_path: Path) -> None:
    data = _rows(tmp_path)
    out = tmp_path / "report.json"
    r = _run(data, out)
    # 系C 单源 2024 vs 多源 2025：年款不同 → 不配对
    cand = [c for c in r["merge_candidates_sample"] if c["series"] == "系C"]
    assert len(cand) == 0

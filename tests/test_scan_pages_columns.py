"""scan_pages_columns.js 列名扫描与归并测试。

覆盖：
1. 首次扫描建立全量基线（所有列名计入历史）
2. 二次扫描 0 新增（持续归并）
3. 新列名（含首行新增常规列）被识别为新增待归并
4. 别名列归并到 canonical（含 Unicode 兼容字符变体）
5. 无浏览器时 --no-browser 数据文件模式可用（workflow fallback）
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCAN_SCRIPT = REPO_ROOT / "scripts" / "scan_pages_columns.js"

ALIASES_JSON = {
    "version": 1,
    "aliases": [
        {"column": "百公里加速时间", "canonical": "百公里加速(s)", "confidence": 1.0},
        {"column": "超清电⼦外后视镜", "canonical": "超清电子外后视镜", "confidence": 1.0},
    ],
}

FILTER_JSON = {
    "version": 1,
    "columnAliases": {
        "纯电续航(km)": ["CLTC纯电续航里程(km)", "纯电续航"],
    },
}


def _run_scan(data_path: Path, history_path: Path, repo_root: Path, out_path: Path) -> dict:
    proc = subprocess.run(
        [
            "node",
            str(SCAN_SCRIPT),
            "--no-browser",
            "--data",
            str(data_path),
            "--history",
            str(history_path),
            "--out",
            str(out_path),
            "--repo-root",
            str(repo_root),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, f"scan 退出码 {proc.returncode}: {proc.stderr}"
    return json.loads(proc.stdout)


@pytest.fixture()
def scan_env(tmp_path: Path):
    """独立知识库 + 小型数据文件环境。"""
    repo = tmp_path / "repo"
    (repo / "config").mkdir(parents=True)
    (repo / "docs").mkdir(parents=True)
    (repo / "config" / "column_header_aliases.json").write_text(
        json.dumps(ALIASES_JSON, ensure_ascii=False), encoding="utf-8"
    )
    (repo / "docs" / "filter_conditions.json").write_text(
        json.dumps(FILTER_JSON, ensure_ascii=False), encoding="utf-8"
    )
    data = [
        {
            "品牌": "测试",
            "车型名称": "T1",
            "年款": 2025,
            "能源类型": "纯电",
            "百公里加速(s)": 5.0,
            "纯电续航(km)": 500,
        },
        {
            "品牌": "测试",
            "车型名称": "T1",
            "年款": 2025,
            "能源类型": "纯电",
            "百公里加速(s)": 5.0,
            "纯电续航(km)": 500,
            "16扬Flyme音响(限时赠送)_1": "有",  # 稀疏变体列
        },
    ]
    data_path = tmp_path / "latest.json"
    data_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return {"repo": repo, "data": data_path}


def test_first_scan_establishes_full_baseline(scan_env, tmp_path: Path) -> None:
    hist = tmp_path / "hist.json"
    out = tmp_path / "r1.json"
    r = _run_scan(scan_env["data"], hist, scan_env["repo"], out)
    # 首次扫描：知识库外的列名全部算新增待归并（基线建立）
    # 数据 7 列 - 知识库 canonical 2 列（百公里加速(s)、纯电续航(km)）= 5 个待归并
    assert r["newColumnsTotal"] == 5
    # 知识库 canonical 命中
    assert r["mappedCount"] == 2
    # 稀疏变体列在待归并清单中
    assert "16扬Flyme音响(限时赠送)_1" in r["newColumns"]
    # 历史已写入
    assert hist.exists()
    hist_data = json.loads(hist.read_text(encoding="utf-8"))
    assert "16扬Flyme音响(限时赠送)_1" in hist_data["seenColumns"]


def test_second_scan_reports_zero_new(scan_env, tmp_path: Path) -> None:
    hist = tmp_path / "hist.json"
    out1 = tmp_path / "r1.json"
    _run_scan(scan_env["data"], hist, scan_env["repo"], out1)
    out2 = tmp_path / "r2.json"
    r2 = _run_scan(scan_env["data"], hist, scan_env["repo"], out2)
    assert r2["newColumnsTotal"] == 0


def test_new_column_in_first_row_is_detected(scan_env, tmp_path: Path) -> None:
    """新增列加在首行（成为常规列）也必须被识别为新增。"""
    hist = tmp_path / "hist.json"
    out1 = tmp_path / "r1.json"
    _run_scan(scan_env["data"], hist, scan_env["repo"], out1)

    data = json.loads(scan_env["data"].read_text(encoding="utf-8"))
    data[0]["全新属性X"] = "v"
    new_data = tmp_path / "latest2.json"
    new_data.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    out2 = tmp_path / "r2.json"
    r2 = _run_scan(new_data, hist, scan_env["repo"], out2)
    assert r2["newColumnsTotal"] == 1
    assert "全新属性X" in r2["newColumns"]


def test_alias_unicode_variant_mapped(scan_env, tmp_path: Path) -> None:
    """Unicode 兼容字符变体（⼦ vs 子）通过别名库归并。"""
    data = json.loads(scan_env["data"].read_text(encoding="utf-8"))
    data[0]["超清电⼦外后视镜"] = "有"
    data[0].pop("百公里加速(s)", None)  # 不干扰
    data[0].pop("纯电续航(km)", None)
    new_data = tmp_path / "latest3.json"
    new_data.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    hist = tmp_path / "hist.json"
    out = tmp_path / "r3.json"
    r = _run_scan(new_data, hist, scan_env["repo"], out)
    assert any(
        hit["column"] == "超清电⼦外后视镜" and hit["canonical"] == "超清电子外后视镜"
        for hit in r["aliasHits"]
    )


def test_no_browser_mode_falls_back_to_data_only(scan_env, tmp_path: Path) -> None:
    """--no-browser 时 headerCount=0 且数据列正常扫描（workflow fallback 路径）。"""
    hist = tmp_path / "hist.json"
    out = tmp_path / "r1.json"
    r = _run_scan(scan_env["data"], hist, scan_env["repo"], out)
    assert r["browserUsed"] is None
    assert r["headerCount"] == 0
    assert r["dataColumnCount"] >= 7

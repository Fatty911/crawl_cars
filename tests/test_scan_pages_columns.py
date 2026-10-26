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
import os
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
            "--require-data",
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
        encoding="utf-8",
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
    assert r2["unmappedCount"] == 5
    assert r2["mappedCount"] == 2
    assert "16扬Flyme音响(限时赠送)_1" in r2["unmapped"]
    assert len(json.loads(hist.read_text(encoding="utf-8"))["unmappedColumns"]) == 5


def test_only_explicit_mapping_resolves_a_seen_unknown(scan_env, tmp_path: Path) -> None:
    hist = tmp_path / "hist.json"
    _run_scan(scan_env["data"], hist, scan_env["repo"], tmp_path / "before.json")
    alias = scan_env["repo"] / "config/column_header_aliases.json"
    knowledge = json.loads(alias.read_text(encoding="utf-8"))
    knowledge["aliases"].append({"column": "16扬Flyme音响(限时赠送)_1", "canonical": "音响配置"})
    alias.write_text(json.dumps(knowledge, ensure_ascii=False), encoding="utf-8")
    report = _run_scan(scan_env["data"], hist, scan_env["repo"], tmp_path / "after.json")
    assert report["newColumnsTotal"] == 0
    assert report["unmappedCount"] == 4
    assert any(item["canonical"] == "音响配置" for item in report["aliasHits"])
    assert "16扬Flyme音响(限时赠送)_1" not in json.loads(hist.read_text(encoding="utf-8"))["unmappedColumns"]


@pytest.mark.parametrize("content", [None, "[]", "{broken", '[{"品牌":"测试"},null]', '[{"品牌":"测试"},[]]'])
def test_strict_local_scan_fails_for_missing_empty_or_broken_data(tmp_path, content):
    data = tmp_path / "input.json"
    if content is not None:
        data.write_text(content, encoding="utf-8")
    result = subprocess.run(
        ["node", str(SCAN_SCRIPT), "--no-browser", "--require-data", "--data", str(data)],
        capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    assert result.returncode == 1
    assert "--require-data" in result.stderr


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


def test_strict_local_mode_does_not_resolve_remote_pages(scan_env, tmp_path):
    marker = tmp_path / "network-attempt.txt"
    hook = tmp_path / "network-trap.js"
    hook.write_text(
        'require("node:child_process").execFileSync = function () {'
        'require("node:fs").writeFileSync(process.env.SCAN_NETWORK_MARKER, "attempted");'
        'throw new Error("unexpected external command");};', encoding="utf-8",
    )
    env = dict(os.environ, GITHUB_REPOSITORY="test/forbidden-network",
               NODE_OPTIONS='--require "' + hook.as_posix() + '"', SCAN_NETWORK_MARKER=str(marker))
    result = subprocess.run(
        ["node", str(SCAN_SCRIPT), "--no-browser", "--require-data", "--data", str(scan_env["data"]),
         "--repo-root", str(scan_env["repo"]), "--history", str(tmp_path / "history.json")],
        env=env, capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["url"] == ""
    assert not marker.exists()


@pytest.mark.parametrize("fault", ["invalid_json", "directory", "blocked_parent"])
def test_strict_history_failure_cannot_report_success(scan_env, tmp_path, fault):
    history = tmp_path / "history.json"
    if fault == "invalid_json":
        history.write_text("{broken", encoding="utf-8")
    elif fault == "directory":
        history.mkdir()
    else:
        parent = tmp_path / "parent-file"
        parent.write_text("keep this existing file", encoding="utf-8")
        history = parent / "history.json"
    result = subprocess.run(
        ["node", str(SCAN_SCRIPT), "--no-browser", "--require-data", "--data", str(scan_env["data"]),
         "--repo-root", str(scan_env["repo"]), "--history", str(history)],
        capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    assert result.returncode == 1, result.stderr
    assert "--require-data" in result.stderr
    if fault == "invalid_json":
        assert history.read_text(encoding="utf-8") == "{broken"
    if fault == "blocked_parent":
        assert parent.read_text(encoding="utf-8") == "keep this existing file"


# ---------------------------------------------------------------------------
# 小目标 A/B/C 回归：知识来源精确化、完整 pending 队列、输入/知识哈希绑定
# ---------------------------------------------------------------------------
DECLARED_FILTER_JSON = {
    "version": 1,
    "defaultVisibleColumns": ["品牌", "车型名称", "年款"],
    "conditions": [
        {"id": "zero_to_hundred", "label": "加速标签", "field": "百公里加速(s)"},
        {"id": "noa", "label": "领航标签", "fields": ["NOA城市领航", "城市领航辅助"]},
    ],
    "filterTaxonomy": [
        {
            "id": "basic",
            "label": "基本信息",
            "sections": [
                {"id": "identity", "label": "车型身份", "columns": ["车款ID"]},
                {"id": "budget", "label": "价格", "columnPatterns": ["指导价|售价"]},
            ],
        },
    ],
    "columnAliases": {"纯电续航(km)": ["CLTC纯电续航里程(km)"]},
    "hiddenByDefault": ["隐藏列甲"],
    "dropIfUniformPositive": ["丢弃列乙"],
}

DECLARED_ALIASES_JSON = {
    "version": 1,
    "aliases": [{"column": "百公里加速时间", "canonical": "百公里加速(s)"}],
}

# 数据里确实出现、且被 docs/filter_conditions.json 明确声明为列名的那些列
DECLARED_IN_DATA = ["品牌", "车型名称", "年款", "百公里加速(s)", "NOA城市领航", "车款ID", "纯电续航(km)"]
# 只出现在 label / id / 正则 / 首行键 / hiddenByDefault / dropIfUniformPositive 里的名字，不得被批准
NON_APPROVAL_COLUMNS = [
    "车型身份", "identity", "加速标签", "zero_to_hundred",
    "指导价|售价", "隐藏列甲", "丢弃列乙", "首行键丙",
]


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _run_raw(args, env=None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["node", str(SCAN_SCRIPT), *args],
        capture_output=True, text=True, encoding="utf-8", timeout=120, env=env,
    )


@pytest.fixture()
def kb_env(tmp_path: Path):
    """声明式知识库（defaultVisibleColumns / conditions / filterTaxonomy）。"""
    repo = tmp_path / "repo"
    _write_json(repo / "config" / "column_header_aliases.json", DECLARED_ALIASES_JSON)
    _write_json(repo / "docs" / "filter_conditions.json", DECLARED_FILTER_JSON)
    rows = [
        {
            "品牌": "合成品牌", "车型名称": "合成型", "年款": 2025, "百公里加速(s)": 5.0,
            "NOA城市领航": "支持", "车款ID": "C1", "纯电续航(km)": 500,
            "车型身份": "甲", "identity": "甲", "加速标签": "甲", "zero_to_hundred": "甲",
            "指导价|售价": "甲", "隐藏列甲": "有", "丢弃列乙": "有",
        },
        {"品牌": "合成品牌", "车型名称": "合成型二", "年款": 2026, "首行键丙": "乙"},
    ]
    data = tmp_path / "declared.json"
    _write_json(data, rows)
    return {"repo": repo, "data": data}


def test_declared_knowledge_sources_are_known(kb_env, tmp_path: Path) -> None:
    """defaultVisibleColumns / conditions[].field|fields / taxonomy columns 都算已知列。"""
    report = _run_scan(kb_env["data"], tmp_path / "h.json", kb_env["repo"], tmp_path / "r.json")
    pending = [item["column"] for item in report["pendingColumns"]]
    assert set(pending).isdisjoint(DECLARED_IN_DATA), pending
    assert report["mappedCount"] == len(DECLARED_IN_DATA)
    assert report["unmappedCount"] == len(NON_APPROVAL_COLUMNS)
    assert set(pending) == set(NON_APPROVAL_COLUMNS)


@pytest.mark.parametrize("column", NON_APPROVAL_COLUMNS)
def test_labels_ids_patterns_firstrow_and_defaults_do_not_approve(kb_env, tmp_path, column) -> None:
    """label/id/columnPatterns/首行键/hiddenByDefault/dropIfUniformPositive 不是批准来源。"""
    report = _run_scan(kb_env["data"], tmp_path / "h.json", kb_env["repo"], tmp_path / "r.json")
    pending = {item["column"]: item for item in report["pendingColumns"]}
    assert column in pending, f"{column} 被非列名来源误批准"
    assert pending[column]["status"] == "pending_review"


def test_history_never_approves_unknown_columns(scan_env, tmp_path: Path) -> None:
    """历史只抑制重复通知，第二次扫描 new=0 但 pending 仍完整保留。"""
    hist = tmp_path / "h.json"
    first = _run_scan(scan_env["data"], hist, scan_env["repo"], tmp_path / "r1.json")
    second = _run_scan(scan_env["data"], hist, scan_env["repo"], tmp_path / "r2.json")
    assert second["newColumnsTotal"] == 0
    assert second["pendingCount"] == first["pendingCount"] == second["unmappedCount"]
    assert [i["id"] for i in second["pendingColumns"]] == [i["id"] for i in first["pendingColumns"]]
    assert [i["samples"] for i in second["pendingColumns"]] == [i["samples"] for i in first["pendingColumns"]]
    assert "16扬Flyme音响(限时赠送)_1" in {i["column"] for i in second["pendingColumns"]}


def test_pending_queue_is_complete_beyond_legacy_200_cap(scan_env, tmp_path: Path) -> None:
    """>200 未知列：原 unmapped 仍截断前 200，pendingColumns 必须全量且按列名排序。"""
    row = {"品牌": "合成品牌"}
    for i in range(260):
        row[f"未知列{i:03d}"] = f"值{i}"
    data = tmp_path / "wide.json"
    _write_json(data, [row])
    report = _run_scan(data, tmp_path / "h.json", scan_env["repo"], tmp_path / "r.json")
    assert report["pendingCount"] == 261
    assert len(report["pendingColumns"]) == 261
    names = [i["column"] for i in report["pendingColumns"]]
    assert names == sorted(names)
    assert len(set(names)) == 261
    assert len(report["unmapped"]) == 200 and report["unmappedCount"] == 261
    assert len(report["newColumns"]) == 200 and report["newColumnsTotal"] == 261
    for item in report["pendingColumns"]:
        assert len(item["id"]) == 64 and int(item["id"], 16) >= 0
        assert item["occurrences"] == 1 and item["nonEmptyCount"] == 1


def test_pending_id_is_schema_plus_column_only(kb_env, tmp_path: Path) -> None:
    """稳定 id 只绑定 schema 版本 + 精确列名，可跨轮去重。"""
    import hashlib

    report = _run_scan(kb_env["data"], tmp_path / "h.json", kb_env["repo"], tmp_path / "r.json")
    for item in report["pendingColumns"]:
        expected = hashlib.sha256(("pages-column-scan/pending/v1\n" + item["column"]).encode("utf-8")).hexdigest()
        assert item["id"] == expected


def test_input_value_change_changes_hash_but_not_column_ids(scan_env, tmp_path: Path) -> None:
    """输入改值：inputSha256 变，列名 id/证据结构不变。"""
    import hashlib

    hist = tmp_path / "h.json"
    first = _run_scan(scan_env["data"], hist, scan_env["repo"], tmp_path / "r1.json")
    rows = json.loads(scan_env["data"].read_text(encoding="utf-8"))
    rows[0]["能源类型"] = "插混"
    changed = tmp_path / "latest_changed.json"
    _write_json(changed, rows)
    second = _run_scan(changed, hist, scan_env["repo"], tmp_path / "r2.json")
    assert first["inputSha256"] == hashlib.sha256(scan_env["data"].read_bytes()).hexdigest()
    assert second["inputSha256"] == hashlib.sha256(changed.read_bytes()).hexdigest()
    assert second["inputSha256"] != first["inputSha256"]
    assert [i["id"] for i in second["pendingColumns"]] == [i["id"] for i in first["pendingColumns"]]


def test_report_binds_knowledge_source_bytes(scan_env, tmp_path: Path) -> None:
    """knowledgeSources 记录实际读取的两个配置原字节 hash，缺失文件明确标出。"""
    import hashlib

    repo = scan_env["repo"]
    report = _run_scan(scan_env["data"], tmp_path / "h.json", repo, tmp_path / "r.json")
    sources = report["knowledgeSources"]
    alias_sha = hashlib.sha256((repo / "config/column_header_aliases.json").read_bytes()).hexdigest()
    filter_sha = hashlib.sha256((repo / "docs/filter_conditions.json").read_bytes()).hexdigest()
    assert sources["config/column_header_aliases.json"]["sha256"] == alias_sha
    assert sources["docs/filter_conditions.json"]["sha256"] == filter_sha
    assert report["complete"] is True and report["knowledgeErrors"] == []

    (repo / "docs/filter_conditions.json").unlink()
    missing = _run_scan(scan_env["data"], tmp_path / "h2.json", repo, tmp_path / "r2.json")
    assert missing["knowledgeSources"]["docs/filter_conditions.json"]["status"] == "missing"
    assert missing["knowledgeSources"]["docs/filter_conditions.json"]["sha256"] is None


def test_only_explicit_mapping_clears_matching_pending(scan_env, tmp_path: Path) -> None:
    """只有显式 alias 变更才清掉对应 pending，其余 pending 原样保留。"""
    hist = tmp_path / "h.json"
    before = _run_scan(scan_env["data"], hist, scan_env["repo"], tmp_path / "r1.json")
    alias_path = scan_env["repo"] / "config/column_header_aliases.json"
    knowledge = json.loads(alias_path.read_text(encoding="utf-8"))
    knowledge["aliases"].append({"column": "品牌", "canonical": "品牌规范列"})
    _write_json(alias_path, knowledge)
    after = _run_scan(scan_env["data"], hist, scan_env["repo"], tmp_path / "r2.json")
    before_cols = {i["column"]: i["id"] for i in before["pendingColumns"]}
    after_cols = {i["column"]: i["id"] for i in after["pendingColumns"]}
    assert "品牌" not in after_cols
    assert after["pendingCount"] == before["pendingCount"] - 1
    for column, pid in after_cols.items():
        assert before_cols[column] == pid


def test_pending_samples_are_real_values_with_explicit_truncation(scan_env, tmp_path: Path) -> None:
    """样本取自当前输入对应列的真实值，只做明确标注的截断并附原值 SHA。"""
    import hashlib

    long_value = "长" * 300
    rows = [
        {"品牌": "合成品牌", "多值列": "前/后", "否定列": "不支持"},
        {"品牌": "合成品牌", "多值列": "前/后", "否定列": "支持"},
        {"品牌": "合成品牌", "多值列": long_value, "否定列": ""},
        {"品牌": "合成品牌", "多值列": "   "},
    ]
    data = tmp_path / "samples.json"
    _write_json(data, rows)
    report = _run_scan(data, tmp_path / "h.json", scan_env["repo"], tmp_path / "r.json")
    items = {i["column"]: i for i in report["pendingColumns"]}

    multi = items["多值列"]
    assert multi["occurrences"] == 4 and multi["nonEmptyCount"] == 3
    assert [s["value"] for s in multi["samples"]] == ["前/后", "长" * 120]
    assert [s["rowIndex"] for s in multi["samples"]] == [0, 2]
    assert multi["samples"][0]["truncated"] is False
    assert multi["samples"][0]["originalLength"] == 3
    assert multi["samples"][0]["valueSha256"] == hashlib.sha256("前/后".encode("utf-8")).hexdigest()
    assert multi["samples"][1]["truncated"] is True
    assert multi["samples"][1]["originalLength"] == 300
    assert multi["samples"][1]["valueSha256"] == hashlib.sha256(long_value.encode("utf-8")).hexdigest()

    negated = items["否定列"]
    assert [s["value"] for s in negated["samples"]] == ["不支持", "支持"]
    assert negated["nonEmptyCount"] == 2
    for item in report["pendingColumns"]:
        assert item["samples"] == item["samples"][:3]
        for sample in item["samples"]:
            assert set(sample) >= {"rowIndex", "value", "truncated", "originalLength", "valueSha256", "identity"}
            assert sample["identity"].get("车型名称") in ("", "合成型") or isinstance(sample["identity"], dict)
        assert "approval" not in item and "hidden" not in item and "mapping" not in item


@pytest.mark.parametrize(
    "fault",
    ["filter_broken_json", "filter_bad_shape", "alias_broken_json", "alias_bad_shape", "alias_missing_key"],
)
def test_strict_broken_knowledge_fails_and_preserves_history_and_out(scan_env, tmp_path, fault) -> None:
    """严格模式下坏知识库必须 exit1，且不覆盖既有 history / out 原字节。"""
    repo = scan_env["repo"]
    filter_path = repo / "docs" / "filter_conditions.json"
    alias_path = repo / "config" / "column_header_aliases.json"
    if fault == "filter_broken_json":
        filter_path.write_text("{broken", encoding="utf-8")
    elif fault == "filter_bad_shape":
        _write_json(filter_path, {"defaultVisibleColumns": "品牌", "conditions": [{"field": 7}]})
    elif fault == "alias_broken_json":
        alias_path.write_text("[1,2,3", encoding="utf-8")
    elif fault == "alias_bad_shape":
        _write_json(alias_path, {"aliases": [{"column": "", "canonical": 5}]})
    else:
        _write_json(alias_path, {"version": 1})

    hist = tmp_path / "h.json"
    out = tmp_path / "r.json"
    hist.write_text('{"seenColumns":["旧列"],"keep":true}', encoding="utf-8")
    out.write_text('{"keep":"sentinel"}', encoding="utf-8")
    hist_bytes, out_bytes = hist.read_bytes(), out.read_bytes()

    proc = _run_raw([
        "--no-browser", "--require-data", "--data", str(scan_env["data"]),
        "--repo-root", str(repo), "--history", str(hist), "--out", str(out),
    ])
    assert proc.returncode == 1, proc.stdout
    assert "--require-data" in proc.stderr
    assert hist.read_bytes() == hist_bytes
    assert out.read_bytes() == out_bytes


def test_lenient_broken_knowledge_warns_without_claiming_pass(scan_env, tmp_path: Path) -> None:
    """宽松模式可只告警，但报告不得自称完整/通过。"""
    (scan_env["repo"] / "docs/filter_conditions.json").write_text("{broken", encoding="utf-8")
    marker = tmp_path / "unexpected-network.txt"
    hook = tmp_path / "offline.js"
    hook.write_text('require("node:child_process").execFileSync = function () {'
                    'require("node:fs").writeFileSync(process.env.SCAN_NETWORK_MARKER,"attempted");'
                    'throw new Error("unexpected external command");};', encoding="utf-8")
    env = dict(os.environ, NODE_OPTIONS='--require "' + hook.as_posix() + '"',
               SCAN_NETWORK_MARKER=str(marker))
    for key in ("GITHUB_REPOSITORY", "GITHUB_TOKEN", "PAGES_URL", "GITHUB_PAGES_URL"):
        env.pop(key, None)
    proc = _run_raw([
        "--no-browser", "--data", str(scan_env["data"]),
        "--repo-root", str(scan_env["repo"]), "--history", str(tmp_path / "h.json"),
        "--out", str(tmp_path / "r.json"),
    ], env=env)
    assert proc.returncode == 0, proc.stderr
    report = json.loads(proc.stdout)
    assert report["complete"] is False
    assert report["knowledgeErrors"] and report["knowledgeErrors"][0]["path"].endswith("filter_conditions.json")
    assert report["knowledgeSources"]["docs/filter_conditions.json"]["status"] == "invalid"
    assert not marker.exists(), "合成宽松模式测试不能继承 CI 环境后访问网络"


def test_strict_mode_stays_offline_without_no_browser_flag(scan_env, tmp_path):
    """--require-data 下即使不给 --no-browser，也不解析 Pages URL、不调用外部命令。"""
    marker = tmp_path / "network-attempt.txt"
    hook = tmp_path / "network-trap.js"
    hook.write_text(
        'require("node:child_process").execFileSync = function () {'
        'require("node:fs").writeFileSync(process.env.SCAN_NETWORK_MARKER, "attempted");'
        'throw new Error("unexpected external command");};', encoding="utf-8",
    )
    env = dict(os.environ, GITHUB_REPOSITORY="test/forbidden-network", PAGES_URL="https://example.invalid/",
               NODE_OPTIONS='--require "' + hook.as_posix() + '"', SCAN_NETWORK_MARKER=str(marker))
    result = _run_raw(
        ["--require-data", "--data", str(scan_env["data"]), "--repo-root", str(scan_env["repo"]),
         "--history", str(tmp_path / "h.json")],
        env=env,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["url"] == "" and report["browserUsed"] is None
    assert not marker.exists()


@pytest.mark.parametrize("target,payload", [
    ("alias", None),
    ("filter", None),
    ("filter", {"defaultVisibleColumns": None}),
    ("filter", {"conditions": [{"fields": None}]}),
    ("filter", {"filterTaxonomy": [{"sections": [{"columns": None}]}]}),
    ("filter", {"columnAliases": {"规范列": None}}),
])
def test_null_knowledge_is_not_a_missing_optional_declaration(scan_env, tmp_path, target, payload):
    """JSON null 与文件/字段缺失不同；损坏配置不得擦掉既有证据后报成功。"""
    relative = "config/column_header_aliases.json" if target == "alias" else "docs/filter_conditions.json"
    _write_json(scan_env["repo"] / relative, payload)
    history, out = tmp_path / "history.json", tmp_path / "report.json"
    history.write_bytes(b'{"keep":"old history"}')
    out.write_bytes(b'{"keep":"old report"}')
    proc = _run_raw(["--no-browser", "--require-data", "--data", str(scan_env["data"]),
                     "--repo-root", str(scan_env["repo"]), "--history", str(history), "--out", str(out)])
    assert proc.returncode == 1
    assert history.read_bytes() == b'{"keep":"old history"}'
    assert out.read_bytes() == b'{"keep":"old report"}'


def test_pending_samples_preserve_each_rows_actual_provider(scan_env, tmp_path):
    rows = [{"数据来源": "源甲", "车型名称": "合成甲", "待审列": "支持"},
            {"数据来源": "源乙", "车型名称": "合成乙", "待审列": "不支持"}]
    data = tmp_path / "provider-evidence.json"
    _write_json(data, rows)
    report = _run_scan(data, tmp_path / "history.json", scan_env["repo"], tmp_path / "report.json")
    item = next(x for x in report["pendingColumns"] if x["column"] == "待审列")
    assert [(s["rowIndex"], s["dataSource"], s["value"]) for s in item["samples"]] == [
        (0, "源甲", "支持"), (1, "源乙", "不支持")]


def test_pending_nested_and_typed_values_have_lossless_json_commitments(scan_env, tmp_path):
    import hashlib
    rows = [{"未知嵌套": {"事实": "甲"}, "未知混合": 1},
            {"未知嵌套": {"事实": "乙"}, "未知混合": "1"}]
    data = tmp_path / "typed-evidence.json"
    _write_json(data, rows)
    report = _run_scan(data, tmp_path / "history.json", scan_env["repo"], tmp_path / "report.json")
    for column in ("未知嵌套", "未知混合"):
        item = next(x for x in report["pendingColumns"] if x["column"] == column)
        assert len(item["samples"]) == 2, "不同对象或数字/字符串不得碰撞成一条证据"
        for sample in item["samples"]:
            original = rows[sample["rowIndex"]][column]
            encoded = json.dumps(original, ensure_ascii=False, separators=(",", ":"))
            assert sample["jsonValueSha256"] == hashlib.sha256(encoded.encode()).hexdigest()
            assert sample["valueType"] == ("object" if isinstance(original, dict) else "number" if type(original) is int else "string")
            assert "[object Object]" not in sample["value"]


@pytest.mark.parametrize("credential", ["synthetic\nBAD", "synthetic\rBAD"])
def test_control_character_credentials_never_reach_curl(scan_env, tmp_path, credential):
    marker = tmp_path / "called.json"
    hook = tmp_path / "intercept.js"
    hook.write_text('require("node:child_process").execFileSync = function () {'
                    'require("node:fs").writeFileSync(process.env.SCAN_NETWORK_MARKER,"called");'
                    'return JSON.stringify({html_url:"https://example.invalid/synthetic/"});};', encoding="utf-8")
    env = dict(os.environ, GITHUB_REPOSITORY="synthetic-owner/synthetic-repo", GITHUB_TOKEN=credential,
               NODE_OPTIONS='--require "' + hook.as_posix() + '"', SCAN_NETWORK_MARKER=str(marker))
    for key in ("PAGES_URL", "GITHUB_PAGES_URL"):
        env.pop(key, None)
    proc = _run_raw(["--no-browser", "--data", str(scan_env["data"]), "--repo-root", str(scan_env["repo"]),
                     "--history", str(tmp_path / "history.json")], env=env)
    assert proc.returncode == 0
    assert not marker.exists(), "控制字符不得进入 curl 配置或 Header"


def test_legacy_github_api_resolver_passes_credential_via_stdin_only(scan_env, tmp_path):
    # 所有外部执行均被离线拦截，只使用合成哨兵，绝不读取/使用实际凭据。
    sentinel = "SYNTHETIC_UNIT_TEST_NOT_A_REAL_CREDENTIAL"
    marker = tmp_path / "intercepted.json"
    hook = tmp_path / "intercept.js"
    hook.write_text('require("node:child_process").execFileSync = function (cmd,args,options) {'
                    'require("node:fs").writeFileSync(process.env.SCAN_NETWORK_MARKER,'
                    'JSON.stringify({cmd,args,input:options.input}));'
                    'return JSON.stringify({html_url:"https://example.invalid/synthetic/"});};', encoding="utf-8")
    env = dict(os.environ, GITHUB_REPOSITORY="synthetic-owner/synthetic-repo", GITHUB_TOKEN=sentinel,
               NODE_OPTIONS='--require "' + hook.as_posix() + '"', SCAN_NETWORK_MARKER=str(marker))
    for key in ("PAGES_URL", "GITHUB_PAGES_URL"):
        env.pop(key, None)
    proc = _run_raw(["--no-browser", "--data", str(scan_env["data"]), "--repo-root", str(scan_env["repo"]),
                     "--history", str(tmp_path / "history.json")], env=env)
    assert proc.returncode == 0
    observed = json.loads(marker.read_text(encoding="utf-8"))
    assert all(sentinel not in arg for arg in observed["args"])
    assert observed["args"][:3] == ["--disable", "--config", "-"]
    assert observed["input"] == 'header = ' + json.dumps("Authorization: Bearer " + sentinel) + '\n'

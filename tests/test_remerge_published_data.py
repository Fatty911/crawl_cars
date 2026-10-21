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


def test_raised_threshold_allowed_when_identity_conserved() -> None:
    """负责人口径（10-15）：默认档位是给半月自动链兜底的，调试轮可以抬高，
    但抬高的凭据是**身份不变式**：折叠消掉的是同车款ID 的重复行 ⇒ ID 集合前后相等 ⇒ 放行。"""
    rows = _pad([
        _row("76215", "乐道L90 2026款 Pro 六座版", "乐道L90", "2026", "26.58万", "仅懂车帝", "25234"),
        _row("76215", "26款 Pro 六座版", "乐道L90", "2026", "26.58万", "仅易车", "8045"),
    ], target=1200)
    out = RM.remerge(rows, max_drop_pct=90.0)
    assert len(out) < len(rows), "重复行没被折叠，本例没测到目标行为"
    assert RM.sku_ids(out) == RM.sku_ids(rows), "车款ID 集合发生变化 ⇒ 不该放行"


def test_raised_threshold_refuses_when_identity_set_shrinks(monkeypatch) -> None:
    """红样（语义变异，不是语法破坏）：模拟归并键退化到把不同车款的整行吃掉，
    即使档位被抬到 90%，也必须拒绝发布 —— 否则"抬高"就退化成裸跳闸门。"""
    rows = _pad([
        _row("K1", "车型甲", "丙车系", "2026", "10.00万", "仅懂车帝", "300"),
        _row("K2", "车型乙", "丙车系", "2026", "10.00万", "仅易车", "300"),
    ], target=1200)

    def lossy_merge(inp):
        return [dict(r) for r in inp if str(r.get("车款ID")) != "K2"]

    # 评审 B2 之后身份不变式是**无条件**的：默认档位与抬高档位都必须拦住，
    # 且拒绝理由要点名"是哪个车款ID 丢了"（不许只报一个掉行百分比）。
    for drop_cap in (RM.MAX_DROP_PCT, 90.0):
        monkeypatch.setattr(RM.MD, "dedupe_merged_rows", lossy_merge)
        try:
            RM.remerge(rows, max_drop_pct=drop_cap)
        except SystemExit as exc:
            text = str(exc)
            assert "车款ID 身份集合" in text and "丢失=1" in text and "K2" in text, (
                "档位=%s 时拒绝理由没点名身份损失：%s" % (drop_cap, text))
        else:
            raise AssertionError("档位=%s 下车款ID 集合缩小却被放行 ⇒ 身份不变式没无条件生效" % (drop_cap,))


def test_k1_rebuild_restores_a_source_the_publish_gate_deleted(tmp_path) -> None:
    """K1 重建必须把"被发布门禁整源删掉"的那一源找回来。

    实测形状（监工 2026-10-16）：`易车上市状态` 不在 `PAGES_IDENTITY_COLUMNS` 里
    ⇒ `narrow_pages_rows` 先裁列、`yiche_publish_identity_valid` 后判 ⇒
    `approve` 过的易车行在 filtered 面上**一条都不剩**（现网 latest 有 5069 行含易车标签，
    filtered 有 0 行）。旧行为"只对 inherited 去重"永远救不回被删的行。
    """
    rows = _pad([
        dict(_row("90001", "易车款 A", "甲车系", "2026", "12.00万", "懂车帝+易车", "100"),
             易车上市状态="approved"),
        _row("90002", "汽车之家款 B", "乙车系", "2026", "15.00万", "仅汽车之家", "101"),
    ])
    merged = tmp_path / "merged_20261016.json"
    merged.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    keep = ("品牌", "车系", "车系ID", "车型名称", "年款", "车款ID", "官方指导价", "数据来源")
    # 模拟现网：inherited filtered 里易车那源整个不见了
    filt_rows = [{k: r[k] for k in keep if k in r} for r in rows if "易车" not in str(r.get("数据来源"))]
    filt = tmp_path / "filtered_cars_20261016.json"
    filt.write_text(json.dumps(filt_rows, ensure_ascii=False), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--merged", str(merged), "--filtered", str(filt),
         "--date", "20261016", "--outdir", str(tmp_path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(ROOT))
    assert proc.returncode == 0, proc.stderr[-800:]
    after = json.loads((tmp_path / "filtered_cars_20261016.json").read_text(encoding="utf-8"))
    ids = {str(r.get("车款ID") or "").strip() for r in after}
    assert "90001" in ids, "重建没有把被门禁误删的易车行找回来：%s" % sorted(ids)[:8]
    assert "90002" in ids, "已发布的汽车之家身份被重建弄丢了"


def test_k2_rebuild_never_loses_a_published_identity(tmp_path) -> None:
    """K2 反向：只用重算会丢"已发布但今日门禁会拒"的身份 ⇒ 必须并集保住（发布防缩小）。

    实测：现网 filtered 有 3 个身份（70672/70687/72803）在"按今日门禁重算"里会被
    `autohome_publish_identity_valid` 拒掉——它们是在那道闸之前发布的。
    这里用一个 latest 里没有、只在 inherited 里的身份复现同一形状。
    """
    rows = _pad([_row("91001", "在管款", "甲车系", "2026", "12.00万", "仅懂车帝", "100")])
    merged = tmp_path / "merged_20261016.json"
    merged.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    orphan = _row("91999", "孤legacy款", "丙车系", "2026", "18.00万", "仅汽车之家", "102")
    filt = tmp_path / "filtered_cars_20261016.json"
    filt.write_text(json.dumps(_pad([orphan]), ensure_ascii=False), encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--merged", str(merged), "--filtered", str(filt),
         "--date", "20261016", "--outdir", str(tmp_path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(ROOT))
    assert proc.returncode == 0, proc.stderr[-800:]
    after = json.loads((tmp_path / "filtered_cars_20261016.json").read_text(encoding="utf-8"))
    ids = {str(r.get("车款ID") or "").strip() for r in after}
    assert "91999" in ids, "重建把已发布身份悄悄缩小了（发布防缩小被违反）：%s" % sorted(ids)[:8]


def test_k3_identity_key_carries_year_and_price() -> None:
    """K3（评审 E③）：并集去重的**身份键必须带年款与归一价**，只按车款ID 判"同一身份"会漏保已发布行。

    折叠第一遍的键就是 `("sku", 车款ID, 年款, 价格)`；若并集只比 ID，
    已发布的 2025 行会因为在重算面里"有同一个 ID 的 2026 行"而被当作已经存在 ⇒ 不再补回
    ⇒ 发布面少一行（用户看到的就是一台车少一个年款）。
    """
    rebuilt = [_row("93001", "2026款 在管甲", "甲车系", "2026", "12.00万", "仅懂车帝", "100")]
    inherited_old_year = _row("93001", "2025款 老甲", "甲车系", "2025", "11.00万",
                              "仅懂车帝", "100")
    out = RM.union_filtered([inherited_old_year], rebuilt)
    years = sorted({str(r.get("年款")) for r in out if str(r.get("车款ID")) == "93001"})
    assert years == ["2025", "2026"], "同 ID 不同年款的已发布行被当作重复丢掉了：%s" % years

    # 反向：同 ID 同年款同价、只差名称写法 ⇒ 不许再补回来（评审 B4 的那 96 行假补回）
    same_identity = _row("93001", "在管甲 26款", "甲车系", "2026", "12.00万", "仅懂车帝", "100")
    out2 = RM.union_filtered([same_identity], rebuilt)
    assert len(out2) == 1, "同一身份只换了名称写法就被再补一行：%r" % [
        r.get("车型名称") for r in out2]

    # 评审 G⑩：**只改价格**也必须保住——文本键早先不带价格，
    # 同 (车系,年款,名称) 而价不同的已发布行会被文本键判成"已经有了"而漏保。
    price_only = _row("", "在管乙", "乙车系", "2026", "13.00万", "仅懂车帝", "200")
    rebuilt_b = [_row("", "在管乙", "乙车系", "2026", "12.00万", "仅懂车帝", "200")]
    out3 = RM.union_filtered([price_only], rebuilt_b)
    prices = sorted({str(r.get("官方指导价")) for r in out3 if str(r.get("车系")) == "乙车系"})
    assert prices == ["12.00万", "13.00万"], (
        "同名称不同价的已发布行被文本键吞掉了：%s" % prices)


WORKFLOW = ROOT / ".github" / "workflows" / "remerge-and-publish.yml"


def test_w1_workflow_can_raise_threshold_but_defaults_unchanged() -> None:
    """W1：GitHub 那条"重合并并发布"链必须能传阈值，**但默认行为一字不动**。

    实测动因：本地演练同一轮真数据，脚本默认 8.0% 当场拒发（本轮折叠掉 10.80%，
    而身份守恒不变式是无条件通过的）⇒ 不传阈值的链跑不出东西来。
    负责人 10-15 口径：8% 不是他定的，"调试过程在证据充足时应该能跳过此限制"。
    所以只加一个**留空即默认**的入参；默认值必须仍是空串（不许把 8.0 改成别的数）。"""
    import yaml
    raw = WORKFLOW.read_text(encoding="utf-8")
    doc = yaml.safe_load(raw)
    # PyYAML 1.1 把 `on:` 解析成布尔键 True ⇒ 两种写法都要认，否则这条判据自己会假红
    top = doc.get("on") or doc.get(True) or {}
    inputs = top.get("workflow_dispatch", {}).get("inputs", {})
    assert "max_drop_pct" in inputs, "工作流没有 max_drop_pct 入参 ⇒ 本轮这类数据会被默认档拒发"
    assert str(inputs["max_drop_pct"].get("default", "")) == "", (
        "默认值被改成了 %r：留空才等于沿用脚本默认 8.0%%" % inputs["max_drop_pct"].get("default"))
    # shell 那两条要看**原文**：走 `json.dumps` 的话双引号会被转义成 \" ⇒ 判据永远找不到（我自己踩过）
    assert "--max-drop-pct" in raw, "入参没被转发给 remerge_published_data"
    assert 'if [ -n "$DROP" ]' in raw, (
        "转发不是条件式的：空串也会传成 `--max-drop-pct ''` ⇒ 参数解析当场报错")

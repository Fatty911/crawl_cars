"""易车续跑断点必须小到能被回推体积闸放行，并且瘦身后仍能跨轮续跑。

实测取证（2026-10-12，构建 cnb-kjq-1k4mdjfui，阶段「回推增量状态」原文）：

    ❌ 以下文件超过 5MB，撤出本次回推（防仓库膨胀）：
    crawl_state/yiche_frontier.json
    [main 00065fb] chore: 半月增量爬取+发布 [skip ci]

同一轮「爬取-易车」阶段的原文：

    易车续跑：基于上一轮断点 crawl_state/yiche_frontier.json (brands_remaining=83)
    易车检查点: status=partial stage=finished attempted=298 brands_scanned=6 rows=413

而 00065fb 里提交的 crawl_state/yiche_frontier.json 与上一轮 11c10bb 的**同一个 blob**
（sha 相同、updated_at 仍是 2026-10-11T20:43:05、brands_scanned 仍是 1）。
⇒ 断点内嵌逐行明细（scripts/crawl_yiche.py 的 snapshot() 把全部 rows 写进断点），
品牌数一涨就撞 .cnb.yml 的 5MB 体积闸，被 `git reset -q HEAD --` 静默撤出；
main 上因此永远留着旧的小断点，下一轮再拿它当续跑输入。
**进度被自己的文件尺寸吃掉**：这不是预算不够，也不是 crawler_sha256 漂移。

判据口径（四条互不掩盖）：
1. 断点体积不变式：夹具 20 品牌 × 每品牌 100 行 × 220 列（都先过真行闸门），
   序列化后必须 ≤ 512KB；
2. 解析端必须接受瘦身后的断点：同一份断点要能 load 回来并给出可用续跑状态；
3. 身份闸门不许顺手放宽（外来 producer 的断点仍必须被拒）；
4. 体积闸撤出 `crawl_state/` 下的续跑状态时必须让阶段变红（静默撤出=静默倒退），
   且不得删掉续跑接线与既有测试依赖的字面。
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SIZE_GATE_BYTES = 5 * 1024 * 1024  # .cnb.yml 里的 5242880
CHECKPOINT_BUDGET = 512 * 1024


def _crawler():
    spec = importlib.util.spec_from_file_location("crawl_yiche", ROOT / "scripts" / "crawl_yiche.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fixture_rows(brands=20, per_brand=100, columns=220):
    """自造夹具，但必须先过爬虫自己的真行闸门——否则「合法修好」也会因夹具被拒而变红。"""
    crawler = _crawler()
    rows = []
    for b in range(brands):
        for i in range(per_brand):
            row = {
                "品牌": "夹具品牌%d" % b,
                "车系": "夹具车系%d-%d" % (b, i),
                "车型名称": "夹具车型%d" % i,
                "年款": "2026",
                "易车上市状态": "approved",
            }
            row.update({"夹具属性%d" % c: "值%d-%d" % (i, c) for c in range(columns)})
            rows.append(row)
    kept = crawler.validate_real_rows(rows)
    assert len(kept) == len(rows), (
        "夹具行没过 is_real_config_row（%d/%d）：判据自身的夹具坏了，"
        "这种红不具备验收效力，必须先把夹具修到能过真行闸门" % (len(kept), len(rows)))
    return rows


def _resume_state(crawler):
    """一份能通过 load_resume_checkpoint 全部不变式的续跑状态（不含逐行明细）。"""
    urls = []
    for i in range(5):
        candidate = f"https://car.yiche.com/series-{i}/peizhi/"
        urls.append(crawler.normalize_series_url(candidate))
    known = {url: {"brand": f"夹具品牌{i}", "series": f"夹具车系{i}", "serial_id": str(900 + i)}
             for i, url in enumerate(urls)}
    frontier = {
        "brand_queue": [[str(1000 + i), f"夹具品牌{i}"] for i in range(6)],
        "retry_queue": [],
        "brand_attempts": {},
        "brands_total": 736,
        "brands_scanned": 6,
        "pages_scanned": 6,
        "seen_serial_ids": [str(900 + i) for i in range(5)],
        "duplicate_serial_ids": 0,
        "brand_discovery_retries": 0,
        "brand_discovery_failures": 0,
        "last_failed_master_id": "",
        "initialized": True,
    }
    return {
        "known_targets": known,
        "pending": urls[:3],
        "completed": urls[3:],
        "attempts": {urls[0]: 1},
        "stats": {"attempted": 298, "success": 95, "403": 6, "429": 0, "failed": 6},
        "frontier": frontier,
        "legacy_frontier": {},
    }


def _write_slim_checkpoint(tmp_path, crawler, rows):
    path = tmp_path / "yiche_frontier.json"
    observer = crawler.CrawlObserver(str(path), heartbeat_interval=0)
    observer.start()
    observer.checkpoint(
        progress=True,
        force=True,
        status="partial",
        stage="finished",
        brands_scanned=6,
        remaining_brands=83,
        targets_discovered=132,
        queue_depth=53,
        current_url="",
        last_completed_url="",
        stop_reason="safety_buffer_reached",
        stats={"attempted": 298, "success": 95, "403": 6, "429": 0, "failed": 6},
        resume_state=_resume_state(crawler),
        rows=rows,
    )
    observer.close("partial", rows=rows, stage="finished")
    return path


def test_frontier_checkpoint_stays_under_size_gate(tmp_path) -> None:
    """断点里不许装逐行明细：宽表夹具下必须远小于回推体积闸。"""
    crawler = _crawler()
    path = _write_slim_checkpoint(tmp_path, crawler, _fixture_rows())
    blob = path.read_bytes()
    payload = json.loads(blob.decode("utf-8"))
    assert len(blob) <= CHECKPOINT_BUDGET, (
        "续跑断点 %.1fKB，超过预算 %dKB（回推体积闸 %dKB）："
        "断点里装着 %d 行逐行明细，品牌一涨就被 .cnb.yml 静默撤出，"
        "main 上的断点永远冻结在旧的一轮 -> %s"
        % (len(blob) / 1024.0, CHECKPOINT_BUDGET // 1024, SIZE_GATE_BYTES // 1024,
           len(payload.get("rows") or []), path)
    )


def test_slim_frontier_still_resumes(tmp_path, monkeypatch) -> None:
    """瘦身必须两端一起改：解析端不能因为断点里没有 rows 就判「没有续跑状态」。"""
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    crawler = _crawler()
    path = _write_slim_checkpoint(tmp_path, crawler, _fixture_rows())
    payload = json.loads(path.read_bytes().decode("utf-8"))
    producer = payload.get("producer") or {}
    try:
        result = crawler.load_resume_checkpoint(
            str(path),
            source_run_id=producer.get("run_id", ""),
            source_artifact_id=producer.get("artifact_id", ""),
            source_artifact_sha256="0" * 64,
            source_checkpoint_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            source_head_sha=producer.get("head_sha", ""),
            source_crawler_sha256=crawler.file_sha256(str(ROOT / "scripts" / "crawl_yiche.py")),
        )
    except ValueError as exc:
        raise AssertionError(
            "瘦身后的断点被解析端拒绝，续跑会退回首轮重爬并 rm -f 删断点：%s" % exc
        )
    assert isinstance(result, dict) and result.get("frontier"), (
        "load_resume_checkpoint 必须返回带 frontier 的可用续跑状态，实得 keys=%s"
        % sorted(result if isinstance(result, dict) else {})
    )
    assert isinstance(result.get("pending"), list) and result["pending"], (
        "续跑队列必须非空，否则本轮之后没有任何待爬车系")


def test_identity_gate_still_rejects_foreign_producer(tmp_path, monkeypatch) -> None:
    """不许用「放宽身份闸门」来给瘦身让路：外来仓库的断点仍必须被拒。"""
    import pytest

    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    crawler = _crawler()
    path = _write_slim_checkpoint(tmp_path, crawler, _fixture_rows())
    payload = json.loads(path.read_bytes().decode("utf-8"))
    payload["producer"] = dict(payload.get("producer") or {})
    payload["producer"]["repository"] = "someone-else/other-repo"
    blob = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    path.write_bytes(blob)
    with pytest.raises(ValueError, match="producer identity mismatch"):
        crawler.load_resume_checkpoint(
            str(path),
            source_run_id="",
            source_artifact_id="",
            source_artifact_sha256="0" * 64,
            source_checkpoint_sha256=hashlib.sha256(blob).hexdigest(),
            source_head_sha="",
            source_crawler_sha256=crawler.file_sha256(str(ROOT / "scripts" / "crawl_yiche.py")),
        )


def _stage_dicts(node):
    """结构遍历收所有 stages 阶段对象：.cnb.yml 的层级是 main.<事件>[0].stages，
    按单层 dict 去摸会一条都摸不到（我第一版就这么漏空了，必须递归）。"""
    out = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "stages" and isinstance(value, list):
                out.extend([s for s in value if isinstance(s, dict)])
            else:
                out.extend(_stage_dicts(value))
    elif isinstance(node, list):
        for item in node:
            out.extend(_stage_dicts(item))
    return out


def _stage_script(stage):
    """CNB 的 stage.script 是 {run: 多行脚本}，不是 list——按 list 迭代只会拿到键名，
    于是「读了个空」被当成「没找到闸」（红着的绿灯）。"""
    script = stage.get("script")
    if isinstance(script, dict):
        script = script.get("run") or ""
    elif isinstance(script, list):
        script = "\n".join(str(item) for item in script)
    return str(script or "")


def test_pushback_size_gate_fails_the_stage_when_resume_state_is_dropped() -> None:
    """撤出续跑状态必须变红：静默撤出等于静默把每轮进度归零。"""
    import yaml

    cfg = yaml.safe_load((ROOT / ".cnb.yml").read_text(encoding="utf-8"))
    offenders = []
    gated = []
    for stage in _stage_dicts(cfg):
        script = _stage_script(stage)
        if "5242880" not in script:
            continue
        name = str(stage.get("name"))
        gated.append(name)
        # 只认会被 shell 真正执行的行：注释里的字符串不算机制（防文本摆放糊弄）
        live = "\n".join(l for l in script.splitlines() if not l.strip().startswith("#"))
        if "RESUME_STATE_DROPPED" not in live:
            offenders.append("%s：体积闸撤出文件却没有任何点名" % name)
            continue
        if "exit 1" not in live:
            offenders.append("%s：点名了撤出但没有非零出口（阶段仍会报绿）" % name)
            continue
        if "git commit" in live and live.index("git commit") > live.index("exit 1"):
            offenders.append("%s：exit 1 早于 git commit，会把正常增量一起挡掉" % name)
    assert gated, (
        "读数没在任何阶段里看到 5MB 体积闸——解析器或阶段结构坏了，"
        "这条判据此刻是红着的绿灯，不许当验收用")
    assert not offenders, (
        "体积闸共 %d 处（%s），以下各处静默吞掉续跑状态：%s"
        % (len(gated), "、".join(gated), "；".join(offenders)))


def test_cnb_yml_keeps_literals_required_by_existing_tests() -> None:
    """本单不许为了让断点瘦身而打死既有断言：tests/test_yiche_crawler.py:823-834 读的是
    .github/workflows/crawl-yiche.yml（不是 .cnb.yml），两处接线都得保住。"""
    gh = (ROOT / ".github" / "workflows" / "crawl-yiche.yml").read_text(encoding="utf-8")
    for literal in ("yiche-checkpoint-", "yiche_checkpoint.json", "--resume-source-crawler-sha256"):
        assert literal in gh, (
            ".github/workflows/crawl-yiche.yml 里 %r 被删掉了，"
            "tests/test_yiche_crawler.py:823-834 会因此变红；瘦身断点不得以牺牲既有测试为代价"
            % literal)
    cnb = (ROOT / ".cnb.yml").read_text(encoding="utf-8")
    for literal in ("--resume-checkpoint", "crawl_state/yiche_frontier.json"):
        assert literal in cnb, (
            ".cnb.yml 里 %r 被删掉了：续跑接线本身被拆，断点会更彻底地丢（这不是修法）"
            % literal)

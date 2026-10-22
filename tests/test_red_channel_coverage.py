from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
MONITOR = ROOT / ".github/workflows/AI_Auto_Fix_Monitor.yml"
# 服务端 state=active 的**旁路（不爬取）链**快照。出处：`GET /repos/Fatty911/crawl_cars/actions/workflows`
# 于 2026-10-22T14:21+08:00 的逐条读数——5 条 active 的正是 `部署车型配置网页/懂车帝爬虫/CI` 等
# disabled_manually 之外的那 5 条；其余 9 条 state=disabled_manually（爬虫类与 PR 自动合并）不参与"全部成功"。
# 为什么这里是快照而不是现调 API：本套测试不许依赖网络与凭据（夹具里的本机事实会让判据在别的 OS 上假红）。
# 这条快照**会漂**：10-22 的教训是监视名单补到 5 条而这里还停在 3 条 ⇒
# `test_real_monitor_matches_current_active_chains` 当场判红并点名两条链——那是**这条不变式在正常工作**，
# 补名单必须同批改这里，判据不许反过来迁就名单。
# 服务端 workflow **整表**读数（14 条：active 5 + disabled_manually 9）。
# 出处：`GET /repos/Fatty911/crawl_cars/actions/workflows?per_page=50`，2026-10-22T14:21+08:00。
# 为什么是常量而不是现调 API：本套测试不许依赖网络与凭据（宿主事实会让判据在别的 OS 上假红）。
# 为什么不再单独维护一份"active 名单"：10-22 的实测事故就是名单补到 5 条、测试里的快照还停在 3 条
# ——两边各抄一份，必然有一边先漂。这里是**整表**（含 disabled 的 9 条），所以"漏列一条真 active 的链"
# 与"混进一条停用链"两向都能判。刷新方式（机械动作，别手改 state）：
#   gh api "repos/Fatty911/crawl_cars/actions/workflows?per_page=50" #     --jq '.workflows[]|{name,state}' | python -c "import json,sys;print({json.loads(l)[\"name\"]:json.loads(l)[\"state\"] for l in sys.stdin if l.strip()})"
# 把输出贴进下面的 dict（并更新 read_at/source），再跑本文件。
PLATFORM_READING = {
    "read_at": "2026-10-22T14:21:00+08:00",
    "source": "GET https://api.github.com/repos/Fatty911/crawl_cars/actions/workflows?per_page=50",
    "states": {
        "重合并并发布（不爬取）": "active",
        "Deploy verified CNB Pages": "active",
        "部署前端展示": "active",
        "Markdown privacy (candidate)": "active",
        "Runtime proxy cache guard": "active",
        "AI Auto Fix Monitor": "disabled_manually",
        "CI": "disabled_manually",
        "PR 自动合并": "disabled_manually",
        "懂车帝爬虫": "disabled_manually",
        "易车爬虫": "disabled_manually",
        "汽车之家爬虫": "disabled_manually",
        "爬虫外部触发器": "disabled_manually",
        "经销商报价增量爬虫": "disabled_manually",
        "部署车型配置网页": "disabled_manually",
    },
}
ACTIVE = [name for name, state in PLATFORM_READING["states"].items() if state == "active"]


def _load():
    spec = importlib.util.spec_from_file_location(
        "red_channel_coverage", ROOT / "scripts" / "check_red_channel_coverage.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _states(names=None, extra=None):
    out = [{"name": n, "state": "active"} for n in (names or ACTIVE)]
    out += [{"name": n, "state": "disabled_manually"} for n in (extra or ["汽车之家爬虫", "CI"])]
    out.append({"name": "AI Auto Fix Monitor", "state": "active"})
    return out


def _monitor(tmp_path, workflows=None, if_expr="github.event.workflow_run.conclusion == 'failure'",
             body="gh issue create --title x --body y\n"):
    wf = workflows if workflows is not None else ACTIVE
    lines = [
        "name: AI Auto Fix Monitor",
        "on:",
        "  workflow_run:",
        "    workflows: [%s]" % ", ".join('"%s"' % w for w in wf),
        "    types: [completed]",
        "jobs:",
        "  archive:",
        "    if: ${{ %s }}" % if_expr,
        "    steps:",
        "      - run: |",
        "          " + body.replace("\n", "\n          "),
    ]
    p = tmp_path / "monitor.yml"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def test_green_when_monitor_covers_every_active_chain(tmp_path):
    mod = _load()
    errs, active, monitored = mod.check(_monitor(tmp_path), _states())
    assert errs == []
    assert active == set(ACTIVE)
    assert monitored == set(ACTIVE)


def test_missing_active_chain_is_red_and_named(tmp_path):
    mod = _load()
    errs, _, _ = mod.check(_monitor(tmp_path, workflows=ACTIVE[:2]), _states())
    assert any("部署前端展示" in e for e in errs), errs


def test_ghost_or_disabled_name_is_red(tmp_path):
    mod = _load()
    errs, _, _ = mod.check(_monitor(tmp_path, workflows=ACTIVE + ["汽车之家爬虫"]), _states())
    assert any("汽车之家爬虫" in e for e in errs), errs


def test_success_trigger_is_red(tmp_path):
    mod = _load()
    errs, _, _ = mod.check(
        _monitor(tmp_path, if_expr="github.event.workflow_run.conclusion == 'failure' || "
                                   "github.event.workflow_run.conclusion == 'success'"),
        _states())
    assert any("success" in e for e in errs), errs


def test_paid_model_fix_leg_is_red(tmp_path):
    mod = _load()
    errs, _, _ = mod.check(
        _monitor(tmp_path, body="uses: openai/codex-action@v1\ngh issue create --title x --body y\n"),
        _states())
    assert any("付费模型" in e for e in errs), errs


def test_real_monitor_matches_current_active_chains(tmp_path):
    mod = _load()
    errs, _, _ = mod.check(MONITOR, _states())
    assert errs == [], errs


def test_too_few_active_is_third_state(tmp_path):
    mod = _load()
    with pytest.raises(mod.UnreadableState):
        mod.check(_monitor(tmp_path, workflows=ACTIVE[:2]), _states(names=ACTIVE[:2]))


def test_too_few_active_main_returns_2(monkeypatch, capsys, tmp_path):
    mod = _load()
    states = tmp_path / "states.json"
    states.write_text(json.dumps({"workflows": _states(names=ACTIVE[:2])}), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["x", "--states-json", str(states),
                                      "--monitor", str(_monitor(tmp_path, workflows=ACTIVE[:2]))])
    rc = mod.main()
    out = capsys.readouterr().out
    assert rc == 2, out
    assert "COVERAGE_UNREADABLE" in out


def test_disabled_chain_with_stale_monitor_is_red(monkeypatch, capsys, tmp_path):
    # active 只剩两条、名单仍列三条（停用链未同步）⇒ 覆盖红(1)，不是第三态(2)。
    mod = _load()
    states = tmp_path / "states.json"
    states.write_text(json.dumps({"workflows": _states(names=ACTIVE[:2])}), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["x", "--states-json", str(states),
                                      "--monitor", str(_monitor(tmp_path))])
    rc = mod.main()
    out = capsys.readouterr().out
    assert rc == 1, out
    assert "COVERAGE_FAIL" in out
    assert "部署前端展示" in out


def test_unreadable_states_exits_third_state(monkeypatch, capsys):
    mod = _load()
    monkeypatch.setattr(sys, "argv", ["x", "--states-json", str(ROOT / "no-such-states.json")])
    rc = mod.main()
    out = capsys.readouterr().out
    assert rc == 2, out
    assert "COVERAGE_UNREADABLE" in out


def test_states_fixture_roundtrip(tmp_path):
    p = tmp_path / "states.json"
    p.write_text(json.dumps({"workflows": _states()}), encoding="utf-8")
    # 原来这里手抄的是 6。名单从 3 条补到 5 条时它必然跟着红——而红的不是判据，是**抄来的常数**。
    # 换成由夹具自己推：写进去几条，读出来就该是几条（这才是 roundtrip 要钉的东西）。
    assert len(_load().load_states(str(p), "x/y")) == len(_states())


def test_unreadable_survives_gbk_stdio(tmp_path):
    # 第三态文案里有 `⇒`；Windows cp936 控制台不重配 stdout 会在打印时崩成 rc=1。
    monitor = _monitor(tmp_path, workflows=ACTIVE[:2])
    states = tmp_path / "states.json"
    states.write_text(json.dumps({"workflows": _states(names=ACTIVE[:2])}), encoding="utf-8")
    env = dict(os.environ, PYTHONIOENCODING="gbk")
    p = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_red_channel_coverage.py"),
         "--states-json", str(states), "--monitor", str(monitor)],
        capture_output=True, env=env, timeout=60)
    blob = p.stdout + p.stderr
    assert p.returncode == 2, blob[-2000:]
    assert b"COVERAGE_UNREADABLE" in blob


def test_snapshot_names_exist_as_declared_workflows() -> None:
    """ACTIVE 快照里每个名字都必须真能在 `.github/workflows/*.yml` 的顶层 `name:` 找到。

    这条钉的是"快照↔仓内声明"这一层：服务端状态读不到（不许联网），但**名字消失/被改名**
    是纯仓内事实，能判红。上一轮的实际事故是名单与快照不同批改 ⇒ 另一条不变式已经红过；
    这一条补的是另一半：快照里写了个仓里已经不存在的链名（那叫凑数覆盖）。
    """
    declared = set()
    for yml in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        for line in yml.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("name:"):          # 只认顶层 name（job 级的有缩进）
                declared.add(line.split(":", 1)[1].strip().strip('"').strip("'"))
                break
    missing = [n for n in ACTIVE + ["AI Auto Fix Monitor"] if n not in declared]
    assert missing == [], "快照点名了仓内并不存在的工作流名（凑数覆盖）：%s ｜ 仓内顶层 name=%s" % (
        missing, sorted(declared))


def test_platform_reading_covers_every_declared_workflow() -> None:
    """平台读数必须覆盖仓内**每一条**工作流（含 disabled 的）：少了谁，谁就能从判据的参考集合里消失。

    这是"单向抓不到"那一格的补法：此前的 active 集合是从监视名单自己推出来的
    （名单漏一条 active 链 ⇒ 判据两边一起漏 ⇒ 照样绿）。现在参考集合是**整表读数**，
    与名单不是同一个来源；仓里新增/改名一条工作流而没人刷新读数 ⇒ 本条红。
    """
    declared = set()
    for yml in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        for line in yml.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("name:"):
                declared.add(line.split(":", 1)[1].strip().strip('"').strip("'"))
                break
    missing = sorted(declared - set(PLATFORM_READING["states"]))
    assert missing == [], (
        "平台读数里缺了仓内声明的工作流（按文件顶部注释刷新 PLATFORM_READING）：%s" % missing)


def test_full_platform_reading_is_checked_two_ways_against_the_monitor() -> None:
    """拿**整表读数**（不只 active）过一遍判据：两条方向都必须成立。

    第一向：读数里 state=active 的链，一条都不许缺席监视名单（旧缺口就在这一向）。
    第二向：名单里不许出现读数说非 active 的名字（凑数覆盖）。
    与 `test_real_monitor_matches_current_active_chains` 的差别：那条只喂 2 条 disabled 名字，
    这条喂**全表**（9 条 disabled 全在），所以"名单里混进任何一条停用链"都会被抓到。
    """
    mod = _load()
    states = [{"name": n, "state": s} for n, s in PLATFORM_READING["states"].items()]
    errs, active, monitored = mod.check(MONITOR, states)
    assert errs == [], errs
    assert set(ACTIVE) <= monitored, "读数说 active 但名单里没有：%s" % sorted(set(ACTIVE) - monitored)


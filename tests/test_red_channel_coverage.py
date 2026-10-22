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
ACTIVE = ["重合并并发布（不爬取）", "Deploy verified CNB Pages", "部署前端展示",
          "Markdown privacy (candidate)", "Runtime proxy cache guard"]


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

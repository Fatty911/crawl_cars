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
ACTIVE = ["重合并并发布（不爬取）", "Deploy verified CNB Pages", "部署前端展示"]


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
    assert len(_load().load_states(str(p), "x/y")) == 6


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

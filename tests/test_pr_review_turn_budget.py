"""PR 审查链必须有够用的轮次预算 —— `maxTurns: 20` 连续把 #16 的 PR 卡成红。

取证（2026-10-12 06:38，两条 pull_request 运行的阶段日志尾部原文）：

    cnb-gnk-1k4n2omir  install-deps success 1.2s  →  NPC-PR审查 error 3.0m
        Master[agent][20] aborted by maxTurns: 20
        Master[agent][21] done. 21 turns, 62 messages
        stop with error: Agent aborted: reached maxTurns limit (20)
    cnb-nnc-1k4n28lbo  install-deps（无）          →  NPC-PR审查 error 2.9m
        同上：reached maxTurns limit (20)

⇒ Issue #16 的修复在平台侧**确实生效**（PR 链第一次出现 `install-deps` 且 success），
  但审查阶段只剩 20 轮 ⇒ 一读 diff 就触顶 ⇒ PR 永远红 ⇒ 无法合并。
⇒ 这是本仓"同一形状三处重复"里的最后一处：issue 链 50→150、自修复 120、**PR 审查仍 20**。

判据口径：
1. `pull_request` 链里 `type: npc:go` 的阶段必须有 `options.maxTurns`，且 **≥ 100**
   （20 连读一份 diff 都不够；issue 链已是 150，取同族下界 100 作硬线）；
2. 该阶段必须存在真跑 pytest 的兄弟阶段（`install-deps` + `pytest`），
   否则审查只能读文本，不算验证（Issue #16 已补，这里钉住不许回退）；
3. 不许用"删掉审查阶段"或把它改成非 agent 阶段来过关（判据按 `type: npc:go` 结构识别）。
"""

from __future__ import annotations

import pathlib

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
CFG = yaml.safe_load((ROOT / ".cnb.yml").read_text(encoding="utf-8"))
MIN_TURNS = 100


def _job(chain_key: str):
    node = (CFG.get("main") or {}).get(chain_key)
    if node is None:
        return None
    jobs = node if isinstance(node, list) else [node]
    return jobs[0] if jobs else None


def _stages(job):
    v = (job or {}).get("stages")
    return [s for s in (v or []) if isinstance(s, dict)]


def _agent_stages(job):
    return [s for s in _stages(job) if str(s.get("type") or "").strip().lower() == "npc:go"]


def _script(stage) -> str:
    b = stage.get("script")
    if isinstance(b, dict):
        b = b.get("run") or ""
    elif isinstance(b, list):
        b = "\n".join(str(x) for x in b)
    return str(b or "")


def test_pr_chain_has_agent_review_stage() -> None:
    job = _job("pull_request")
    assert job is not None, ".cnb.yml 里读不到 main.pull_request 链"
    agents = _agent_stages(job)
    assert agents, (
        "pull_request 链里没有 `type: npc:go` 的审查阶段——"
        "用删掉/降级审查阶段来过关不是修法（PR 就没人多模型交叉审）")


def test_pr_agent_stage_declares_sufficient_max_turns() -> None:
    agents = _agent_stages(_job("pull_request"))
    bad = []
    for s in agents:
        opts = s.get("options") if isinstance(s.get("options"), dict) else {}
        mt = opts.get("maxTurns")
        if not isinstance(mt, int):
            bad.append("%s：maxTurns 缺失或非整数（%r）" % (s.get("name"), mt))
        elif mt < MIN_TURNS:
            bad.append("%s：maxTurns=%d < %d（实测 20 轮就 aborted by maxTurns，连读 diff 都不够）"
                       % (s.get("name"), mt, MIN_TURNS))
    assert not bad, "PR 审查轮次预算不足：\n  " + "\n  ".join(bad)


def test_pr_chain_can_actually_run_pytest() -> None:
    """审查要能真验证：链里必须有装依赖的阶段，且不许用 || true 把失败吃掉。"""
    stages = _stages(_job("pull_request"))
    install = [s for s in stages
               if "pip install" in _script(s) and "requirements.txt" in _script(s)]
    assert install, (
        "pull_request 链没有真跑 `pip install -r requirements.txt` 的阶段："
        "审查阶段没有 pytest 可跑，等于只读文本（Issue #16 已补上，不许回退）")
    silenced = [str(s.get("name")) for s in install
                if "|| true" in _script(s) or "|| exit 0" in _script(s)]
    assert not silenced, "装依赖阶段把失败吃成成功（|| true / || exit 0）：%s" % silenced

"""issue 派发链与 PR 审查链必须真的能跑 Python —— 这是 14 次运行零交付的环境级根因。

取证（2026-10-12，构建 `cnb-k59-1k4mtsnm6` = Issue #14，阶段「AI-Issue驱动修复」日志原文）：

    sh: line 1: cnb: command not found
    sh: line 1: node: command not found
    sh: line 1: python: command not found
    sh: line 1: python3: command not found

同仓 `.cnb.yml` 结构比对（`yaml.safe_load`，不是肉眼）：

    main.push         docker.image = python:3.11   + 阶段 install-deps / pytest
    main.api_trigger  docker.image = python:3.12   + 阶段 install-deps
    main.$['issue.open']   无 docker 声明（落到 cnbcool/default-build-env，里面没有 python）
    main.pull_request      无 docker 声明

⇒ 监工下发的每一份判据都写着"随后运行 `python -m pytest …`"，而 **agent 的容器里根本没有 python**；
本仓 AGENTS.md 又硬要求"推送代码前必须确保所有单元测试通过"。
一个守规矩的 agent 唯一的正确选择就是**不推**——于是跑了 14 次 issue 运行，
`已交付=0 假交付=5 零交付=7`（`delivery_audit.py` 实测）。
这不是提示词能修的，也不是判据写得够不够细的问题：**是环境缺位**。

判据口径：
1. `issue.open` 链必须声明带 python 的镜像，且链里存在一个**非 agent** 阶段真的装依赖
   （`pip install` + `requirements.txt`），排在 agent 阶段之前；
2. `pull_request` 链同样必须有 python 镜像（它要跑 pytest 才能验证 NPC 交付）；
3. 不许把 agent 阶段拆掉来"修环境"，也不许用 `|| true` / `|| exit 0` 把装依赖失败吃成成功；
4. 交付报告必须贴该容器内 `python -V` 与 `python -m pytest --version` 的**真实输出**（监工复核）。
"""

from __future__ import annotations

import pathlib
import re

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
CFG = yaml.safe_load((ROOT / ".cnb.yml").read_text(encoding="utf-8"))


def _job(chain_key: str):
    """非 ref 事件在**文档顶层** `$:`（origin/main 顶层键是 `['$', 'main']`），
    不是 `main.$` —— 取错地方会把"链不存在"错报成"链被拆了"，是判据自己的缺陷。"""
    node = CFG.get("$") or {}
    if chain_key == "issue.open":
        node = node.get("issue.open") or ((CFG.get("main") or {}).get("$") or {}).get("issue.open")
    else:
        node = (CFG.get("main") or {}).get(chain_key)
    if node is None:
        return None
    jobs = node if isinstance(node, list) else [node]
    return jobs[0] if jobs else None


def _stage_list(job) -> list:
    out = []
    for key in ("stages",):
        v = (job or {}).get(key)
        if isinstance(v, list):
            out.extend([s for s in v if isinstance(s, dict)])
    return out


def _script(stage) -> str:
    script = stage.get("script")
    if isinstance(script, dict):
        script = script.get("run") or ""
    elif isinstance(script, list):
        script = "\n".join(str(x) for x in script)
    return str(script or "")


def _is_agent_stage(stage) -> bool:
    if str(stage.get("type") or "").strip().lower() in ("npc:go", "npcgo", "npc"):
        return True
    return bool(re.search(r"npc:go|npcGo", str(stage)))


def _image_of(job) -> str:
    docker = (job or {}).get("docker")
    if isinstance(docker, dict):
        return str(docker.get("image") or "")
    return str((job or {}).get("image") or "")


def test_issue_chain_declares_python_image() -> None:
    job = _job("issue.open")
    assert job is not None, ".cnb.yml 里读不到 $: issue.open 链——判据无法工作，先报结构"
    image = _image_of(job)
    assert re.search(r"python:3\.\d+", image), (
        "issue.open 链没有声明带 python 的镜像（实得 docker=%r）。"
        "默认构建镜像里没有 python/node，agent 跑不了任何判据里要求的 pytest，"
        "结果就是守规矩地不推 -> 零交付" % image)


def test_pull_request_chain_declares_python_image() -> None:
    job = _job("pull_request")
    assert job is not None, ".cnb.yml 里读不到 main.pull_request 链"
    image = _image_of(job)
    assert re.search(r"python:3\.\d+", image), (
        "pull_request 链没有 python 镜像（实得 docker=%r）："
        "PR 审查阶段无法真跑 pytest ⇒ NPC 交付没有平台质检站，审查只能读文本" % image)


def test_issue_chain_installs_dependencies_before_agent_stage() -> None:
    job = _job("issue.open")
    stages = _stage_list(job)
    agent_idx = [i for i, s in enumerate(stages) if _is_agent_stage(s)]
    assert agent_idx, "issue 链里找不到 agent 阶段（npc:go）：链被拆了不是修法"
    first_agent = agent_idx[0]
    installers = [i for i, s in enumerate(stages)
                  if (not _is_agent_stage(s)) and "pip install" in _script(s)
                  and "requirements.txt" in _script(s)]
    assert installers, (
        "issue 链在 agent 阶段之前没有任何真跑 pip install -r requirements.txt 的阶段："
        "光有 python 解释器也跑不了判据（PyYAML/pytest 都不在默认镜像里）")
    assert min(installers) < first_agent, (
        "装依赖阶段排在 agent 之后（%s < %s 不成立）：agent 仍然什么都跑不了"
        % (min(installers), first_agent))


def test_dependency_install_is_not_silenced() -> None:
    """装依赖失败必须让链变红：`|| true` 会把环境缺位重新吃成静默。"""
    job = _job("issue.open")
    bad = []
    for s in _stage_list(job):
        if _is_agent_stage(s):
            continue
        body = _script(s)
        if "pip install" not in body:
            continue
        live = "\n".join(l for l in body.splitlines() if not l.strip().startswith("#"))
        if re.search(r"pip install[^\n]*\|\|\s*(true|exit 0)", live):
            bad.append(str(s.get("name")))
    assert not bad, "这些阶段把 pip 失败吃成成功（|| true / || exit 0）：%s" % bad


def test_agent_stage_is_not_removed_as_a_workaround() -> None:
    """不许为了'修环境'把 npc:go 阶段删掉——那是把派发通道本身拆了。"""
    job = _job("issue.open")
    stages = _stage_list(job)
    agents = [s for s in stages if _is_agent_stage(s)]
    assert len(agents) == 1, "issue 链的 agent 阶段数量应恰为 1，实得 %d" % len(agents)
    body = _script(agents[0]) + yaml.safe_dump(agents[0], allow_unicode=True)
    assert re.search(r"maxTurns", str(body)), "agent 阶段的 maxTurns 声明被删：派发会退回无上限烧轮次"

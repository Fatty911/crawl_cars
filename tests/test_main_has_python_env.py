"""合并后的**落地校验**：#16 的通道修复必须真的进到 `origin/main`，不是停在 PR 分支上。

为什么单独要这一条（监工口径）：PR #17 现在是 `mergeable_state=mergeable`、`blocked_on=unblocked`、
`review_count=0`，只差 `NPC-PR审查` 不再因 `reached maxTurns limit (20)` 触顶；
但"分支上判据全绿"**不等于**"线上已经修好"——本仓已经吃过太多次假绿，
所以这条判据**只读 `origin/main` 的内容**（不读工作树、不读 PR 分支）。

判据口径（结构与 #16 一致，但断言对象换成 main）：
1. `main.pull_request` 与顶层 `$: issue.open` 两条 job 都声明 `docker.image` 含 `python:3.x`；
2. `issue.open` 链在 agent 阶段之前有真跑 `pip install -r requirements.txt` 的非 agent 阶段；
3. 该装依赖阶段不许用 `|| true` / `|| exit 0` 把失败吃成成功。
"""

from __future__ import annotations

import os
import re
import subprocess

import yaml


def _discover_repo() -> str:
    """CI 里 cwd 就是仓库根；监工侧要能指向本地 cnb 克隆。
    用 env `GATE_REPO` 显式覆盖，否则从 . / .. / ../cnb-dispatch 里挑第一个真能读到文件的。"""
    cands = [os.environ.get("GATE_REPO"), ".", "..", "../cnb-dispatch"]
    for c in cands:
        if not c:
            continue
        r = subprocess.run(["git", "-C", c, "rev-parse", "--git-dir"], capture_output=True)
        if r.returncode == 0:
            s = subprocess.run(["git", "-C", c, "rev-parse", "--verify", "origin/main"], capture_output=True)
            if s.returncode == 0:
                return c
    raise AssertionError(
        "找不到带 origin/main 的 git 仓库（试过 . / .. / ../cnb-dispatch）；"
        "本判据必须读 origin/main 的内容，禁止退回工作树或凭记忆判定")


PATH_IN_REPO = ".cnb.yml"


def _main_text() -> str:
    """按**内容**取 origin/main 的流水线定义：工作树可能落后（本会话已两次因此读错）。"""
    out = subprocess.run(["git", "-C", _discover_repo(), "show", "origin/main:" + PATH_IN_REPO],
                         capture_output=True)
    assert out.returncode == 0, (
        "读不到 origin/main:%s —— 判据必须停在『崩』，不许拿工作树内容冒充线上" % PATH_IN_REPO)
    return out.stdout.decode("utf-8", "replace")


def _cfg():
    return yaml.safe_load(_main_text())


def _job(cfg: dict, chain_key: str):
    if chain_key == "issue.open":
        node = (cfg.get("$") or {}).get("issue.open") or ((cfg.get("main") or {}).get("$") or {}).get("issue.open")
    else:
        node = (cfg.get("main") or {}).get(chain_key)
    if node is None:
        return None
    jobs = node if isinstance(node, list) else [node]
    return jobs[0] if jobs else None


def _stages(job):
    return [s for s in ((job or {}).get("stages") or []) if isinstance(s, dict)]


def _script(stage) -> str:
    b = stage.get("script")
    if isinstance(b, dict):
        b = b.get("run") or ""
    elif isinstance(b, list):
        b = "\n".join(str(x) for x in b)
    return str(b or "")


def _image(job) -> str:
    dk = (job or {}).get("docker")
    return str(dk.get("image")) if isinstance(dk, dict) else str((job or {}).get("image") or "")


def _is_agent(stage) -> bool:
    return str(stage.get("type") or "").strip().lower() == "npc:go"


def test_main_pr_chain_has_python_image() -> None:
    cfg = _cfg()
    image = _image(_job(cfg, "pull_request"))
    assert re.search(r"python:3\.\d+", image), (
        "origin/main 上 pull_request 链仍没有 python 镜像（实得 %r）："
        "PR 审查跑不了 pytest，合并门禁形同虚设" % image)


def test_main_issue_chain_has_python_image() -> None:
    cfg = _cfg()
    image = _image(_job(cfg, "issue.open"))
    assert re.search(r"python:3\.\d+", image), (
        "origin/main 上 $: issue.open 链仍没有 python 镜像（实得 %r）："
        "这就是 14 次运行零交付的环境级根因，未进 main 就不算修好" % image)


def test_main_issue_chain_installs_deps_before_agent() -> None:
    cfg = _cfg()
    stages = _stages(_job(cfg, "issue.open"))
    agent_idx = [i for i, s in enumerate(stages) if _is_agent(s)]
    assert agent_idx, "origin/main 的 issue 链里找不到 npc:go 阶段"
    installers = [i for i, s in enumerate(stages)
                  if (not _is_agent(s)) and "pip install" in _script(s) and "requirements.txt" in _script(s)]
    assert installers, "origin/main 的 issue 链在 agent 之前没有装依赖的阶段"
    assert min(installers) < agent_idx[0], "装依赖阶段排在 agent 之后，agent 仍跑不了判据"


def test_main_install_stage_is_not_silenced() -> None:
    cfg = _cfg()
    bad = []
    for key in ("issue.open", "pull_request"):
        for s in _stages(_job(cfg, key)):
            body = _script(s)
            if "pip install" not in body:
                continue
            live = "\n".join(l for l in body.splitlines() if not l.strip().startswith("#"))
            if re.search(r"pip install[^\n]*\|\|\s*(true|exit 0)", live):
                bad.append("%s/%s" % (key, s.get("name")))
    assert not bad, "origin/main 上这些装依赖阶段把失败吃成成功：%s" % bad

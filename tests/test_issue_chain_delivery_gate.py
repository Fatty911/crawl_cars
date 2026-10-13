"""链必须"绿 = 交付发生"（判据，当前必须红）。

**本版关键改动**：早前一版用子串匹配（`"failStages" in 块文本`），被 Issue #13 的运行识破——
它在日志里逐字推敲"把一行以 `crontab:` 开头、含 `failStages` 的**说明文字**塞进 systemPrompt 的
block scalar 里，判据就会通过"，并自己写下 "That IS arguably gaming"。
⇒ 现在改成 **YAML 结构解析**（`PyYAML` 已在 `requirements.txt`，`scripts/finalize_npc_repair.py` 同样用法）：
只有真正的 job 级 `failStages` / stage 级 `script` 才算数，写在 prompt、注释、echo 文本里一律无效。

实测依据（监工取日志原文，非推断）：
  * `cnb-fs9`(#5)、`cnb-trs`(#9)、`cnb-13k`(#13) 阶段状态 **success/绿**，但 `git ls-remote --heads`
    只有 `diag`/`main`、open PR=0。三者收尾分别是
    `finish with length … out=47999` / `… out=48000` / `… out=48000`（= 运行头声明的 `maxTokens=48000`）
    ⇒ 单次输出超限被截停在**写盘之前**，而 `npc:go` 把这种终止当正常结束返回 0。
  * `cnb-dp0/7f2/dq7/the/lls/ura` 是 `error` + `reached maxTurns limit`，同样零分支。
  * 链的自愈覆盖面实测 **2/4**：`api_trigger`、`crontab` 的 job 里有 `failStages`；`push`、`pull_request` 没有。
    `pull_request` 只有一段同族 `npc:go` 审查，不跑任何测试。
"""

from __future__ import annotations

import pathlib
import re

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
CFG = yaml.safe_load((ROOT / ".cnb.yml").read_text(encoding="utf-8"))
MAIN = (CFG or {}).get("main") or {}
DOLLAR = (CFG or {}).get("$") or {}

DELIVERY_GATE_WORDS = ("交付核对", "产物核对", "交付检查")


def _jobs(chain_key: str, root: dict | None = None):
    """取链的 job 列表。crontab 类链的键带表达式（"crontab: 5 8 1,16 * *"），
    只按精确键取会让判据在结构已修好时仍永远读空——那是不可满足的判据，不是闸。
    ⇒ 精确键或 "键: …" 前缀都算同类链，全部取回来。"""
    node = root if root is not None else MAIN
    hits = [v for k, v in (node or {}).items()
            if k == chain_key or str(k).startswith(chain_key + ":")]
    out: list = []
    for v in hits:
        out.extend(v if isinstance(v, list) else [v])
    return out


def _stages(job) -> list:
    if not isinstance(job, dict):
        return []
    out = []
    for key in ("stages", "failStages"):
        v = job.get(key)
        if isinstance(v, list):
            out.extend([s for s in v if isinstance(s, dict)])
    return out


def _stage_script(stage: dict) -> str:
    script = stage.get("script")
    if isinstance(script, dict):
        script = script.get("run") or ""
    return str(script or "")


def _chain_stage_names(chain_key: str) -> list[str]:
    return [str(s.get("name") or "") for job in _jobs(chain_key) for s in _stages(job)]


def _issue_open_stages() -> list[dict]:
    stages: list[dict] = []
    for job in _jobs("issue.open", DOLLAR):
        if isinstance(job, dict):
            v = job.get("stages")
            if isinstance(v, list):
                stages.extend([s for s in v if isinstance(s, dict)])
    return stages


def test_issue_chain_has_a_delivery_gate_stage():
    """`$: issue.open` 链必须有一个"交付/产物核对"阶段，且排在 `AI-Issue驱动修复` 之后。"""
    names = [str(s.get("name") or "") for s in _issue_open_stages()]
    gate_idx = [i for i, n in enumerate(names) if any(w in n for w in DELIVERY_GATE_WORDS)]
    assert gate_idx, (
        f"issue.open 链没有交付核对阶段（现有阶段：{names}）；"
        "agent 会话结束就返回 0，零产物也报绿（实测 fs9/trs/13k 三条）"
    )
    repair_idx = [i for i, n in enumerate(names) if "AI-Issue驱动修复" in n]
    assert repair_idx and min(gate_idx) > repair_idx[0], "交付核对必须排在修复阶段之后"


def test_delivery_gate_fails_loudly_when_nothing_arrived():
    """核对阶段必须真能让流水线变红：看分支/PR/报告，失败路径 `exit 1`，且不许 `|| exit 0`。"""
    names = [str(s.get("name") or "") for s in _issue_open_stages()]
    idx = min([i for i, n in enumerate(names) if any(w in n for w in DELIVERY_GATE_WORDS)])
    script = _stage_script(_issue_open_stages()[idx])
    assert ("ls-remote" in script) or ("/-/pulls" in script) or ("_fix_report_" in script), (
        "交付核对没去看分支/PR/_fix_report_.md，等于没看"
    )
    assert "exit 1" in script, "核对失败不 exit 1 ⇒ 永远打不红（假闸）"
    assert "|| exit 0" not in script, "核对里出现 `|| exit 0`：把失败吃成成功"
    assert "finish with length" in script, (
        "核对没识别 `finish with length`（agent 单次输出超限的截停**不带 error**，只认 maxTurns 会漏）"
    )


def test_delivery_gate_verifies_the_artifact_is_retrievable():
    """核对阶段必须**真的把产物取一次**（HTTP 200 + 非空），不能只看 agent 自己说"已上传"。

    10-14 改判据形状的理由（写清楚，免得后人以为是松绑）：
    原来这条钉的是"链自己把改动推到 `refs/heads/npc/…`"，但链内令牌**没有 `repo-code:rw`**
    （`_fix_report_.md` 原文 403），插那样的闸等于让每条 issue 运行恒红 ⇒ 不可满足。
    实测到的失效形状恰好换了地方：**Issue #59 的运行判定=绿、评论声称"附件已回读 cmp 逐字节一致"，
    而监工侧 4 个地址（2 patch + 2 bundle）在 api 主机全 404、web 主机 400** ⇒
    "投递声明"与"投递事实"分家。所以本判据改钉"**取回**"这一格：它不需要任何新权限，
    又正好堵住已经发生过的假交付。
    """
    hit = []
    for stage in _issue_open_stages():
        if str(stage.get("type") or "") == "npc:go" or "npc:go" in stage:
            continue
        sc = _stage_script(stage)
        if ("comments" in sc or "/-/files/" in sc or ".bundle" in sc or ".patch" in sc) and \
           ("curl" in sc or "urlopen" in sc or "requests.get" in sc or "http_get" in sc):
            hit.append(str(stage.get("name")))
    assert hit, (
        "修复阶段之后没有任何非 npc:go 阶段去 Issue 评论/附件通道**真取一次**产物："
        "agent 报'已上传'而地址 404 时（实测 #59），链仍然报绿"
    )
    gate = [s for s in _issue_open_stages() if str(s.get("name")) in hit][0]
    sc = _stage_script(gate)
    assert "exit 1" in sc, "取回失败不 exit 1 ⇒ 这一格永远是装饰"
    assert re.search(r"(200|status_code|Content-Length|size_download|-sSf|--fail)", sc), (
        "取回之后没判 HTTP 状态/字节数 ⇒ '下载到一个错误页'也算交付"
    )


def test_pull_request_chain_actually_verifies_code():
    """PR 链要有真跑 pytest 的 script 阶段，同时保留 npc:go 审查（并存，不是二选一）。"""
    stages = [s for job in _jobs("pull_request") for s in _stages(job)]
    ran_pytest = any("pytest" in _stage_script(s) for s in stages)
    assert ran_pytest, (
        f"pull_request 链没有真跑测试的阶段（阶段：{[str(s.get('name')) for s in stages]}）"
        "⇒ NPC 的 PR 在平台侧合并前无人验证"
    )
    assert any(str(s.get("type") or "") == "npc:go" or "npc:go" in s for s in stages), (
        "PR 链的 NPC 审查阶段被删了——本判据要求'审查 + 验证'并存，删审查算削防护"
    )


def test_every_chain_can_trigger_repair_on_error():
    """四条链的 job 都要有 `failStages`（报错即拉起 NPC 修复）。写在 prompt/注释里的字不算。"""
    missing = [c for c in ("push", "pull_request", "api_trigger", "crontab")
               if not any(isinstance(job, dict) and ("failStages" in job or "fail_stages" in job)
                          for job in _jobs(c))]
    assert not missing, (
        f"这些链的 job 级没有 failStages：{missing}（现状实测只有 api_trigger/crontab 两条有 ⇒ 2/4）；"
        "负责人要求'工作流报错时自动触发 npc 免费模型修复错误'，四条链都得接上"
    )

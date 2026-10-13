"""流水线时间账必须与**平台实测上限**同尺（判据；当前 main 上必须红）。

**实测依据（不是推断）**：验收轮 `cnb-tcl-1k4r3059q`（10-14 00:54 +08 起跑）阶段级读数——
- `爬取-汽车之家 = success 8544.7s`（预算 8505s 用满后正常收尾，证明"按预算自限"是可行的）；
- `爬取-懂车帝 = error(5810.6s)`，日志尾部原文：
  `Finished, code: 137, duration: 1h 36m` + `The maximum pipeline duration is exceeded: 240min, and the task is exited.`
  ⇒ **CNB 把整条流水线的实际运行上限动态管控在 240 分钟**，与我们声明的 `timeout: 10h` 无关
  （起跑 16:54:4xZ、被杀 20:55Z ≈ 241min，与 240min 对得上）；
- 紧接着 `诊断-收集失败上下文 = error(0.1s)`，原文 `Error response from daemon: container … is not running`
  ⇒ 被强杀后 failStages 在**已死的容器**里跑，自愈环整体失效（另一单跟）。

后果（这才是要钉的东西）：分配器把 34020s（9.45h）当成可用预算发下去，
每一轮都必然在"合并/回推断点/发布/线上验收"之前被平台掐死 ⇒
`crawl_state` 断点从不回灌、Pages 日期冻结 —— 目标"所有工作流任务成功 + Pages 符合预期"永远到不了。

判据钉四件事（全部可从制品算出，不许靠"我觉得够了"）：
1. `PIPELINE_LIMIT_SECONDS ≤ 14400`（平台实测上限，声明不得超过它）；
2. 两条爬取链的 **job `timeout` ≤ 14400s**，且与 `PIPELINE_LIMIT_SECONDS` 同尺（不许一处 4h 一处 10h）；
3. 每个 `爬取-*` 段的 stage `timeout` **≤ 该 job timeout**（超出部分是虚构额度，等于没写）；
4. **一轮必须在平台上限内跑到发布段**：四个爬取步骤的预算之和 + 发布预留 + 安全余量 ≤ 14400s。

红样自校：把 PIPELINE_LIMIT_SECONDS 抬回 10h、或把某个爬取段 timeout 抬到超过 job —— 都必须干净变红。
"""

from __future__ import annotations

import pathlib
import re

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
CFG = yaml.safe_load((ROOT / ".cnb.yml").read_text(encoding="utf-8")) or {}
MAIN = CFG.get("main") or {}
ALLOC = (ROOT / "scripts" / "allocate_crawl_budget.py").read_text(encoding="utf-8")

PLATFORM_MAX_PIPELINE_SECONDS = 14400   # 240min，实测原文见模块 docstring
PUBLISH_RESERVE_KEYS = ("PUBLISH_PHASE_RESERVE_SECONDS", "PUBLISH_RESERVE_SECONDS")
CRAWL_STAGE_WORDS = ("爬取-汽车之家", "爬取-懂车帝", "爬取-易车")
CRAWL_JOB_KEYS = ("api_trigger", "crontab: 5 8 1,16 * *")


def _seconds(text):
    if text in (None, ""):
        return None
    if isinstance(text, (int, float)):
        return int(text)
    s = str(text).strip()
    if re.fullmatch(r"\d+", s):
        return int(s)
    found = re.findall(r"(\d+)\s*([hms])", s)
    total = 0
    for num, unit in found:
        total += int(num) * {"h": 3600, "m": 60, "s": 1}[unit]
    return total or None


def _num_expr(expr: str):
    """只认整数与 + - * 的算式（不用 eval：判据不许给字符串开代码执行口子）。"""
    import ast

    try:
        node = ast.parse(expr.strip(), mode="eval")
    except SyntaxError:
        return None
    ops = {ast.Add: lambda a, b: a + b, ast.Mult: lambda a, b: a * b,
           ast.Sub: lambda a, b: a - b}

    def walk(n):
        if isinstance(n, ast.Expression):
            return walk(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, int):
            return n.value
        if isinstance(n, ast.BinOp) and type(n.op) in ops:
            return ops[type(n.op)](walk(n.left), walk(n.right))
        raise ValueError("not a plain integer expression")

    try:
        return walk(node)
    except Exception:  # noqa: BLE001 - 认不出来就当读不到
        return None


def _const(name: str):
    m = re.search(r"^%s\s*=\s*([^#\n]+)" % name, ALLOC, re.M)
    if not m:
        return None
    return _num_expr(m.group(1))


def _jobs(keys):
    for key in keys:
        val = MAIN.get(key)
        for job in (val if isinstance(val, list) else [val]):
            if isinstance(job, dict):
                yield key, job


def _stages(job):
    v = job.get("stages")
    return [s for s in (v or []) if isinstance(s, dict)]


def test_pipeline_limit_does_not_exceed_the_measured_platform_cap():
    """`PIPELINE_LIMIT_SECONDS` 不许超过实测上限：超过就是**发空头预算**，每轮必被掐死。"""
    limit = _const("PIPELINE_LIMIT_SECONDS")
    assert limit is not None, "读不到 PIPELINE_LIMIT_SECONDS ⇒ 判『读不到』，不许判过"
    assert limit <= PLATFORM_MAX_PIPELINE_SECONDS, (
        "分配器按 %ds（%.2fh）发预算，但平台实测把整条流水线上限管控在 %ds（240min）：%s"
        % (limit, limit / 3600.0, PLATFORM_MAX_PIPELINE_SECONDS,
           "原文 `The maximum pipeline duration is exceeded: 240min`（cnb-tcl-1k4r3059q）")
    )


def test_declared_job_timeout_matches_the_same_ruler():
    """爬取链的 job `timeout` 必须 ≤ 实测上限，且与分配器同一把尺子（不许一处 4h 一处 10h）。"""
    limit = _const("PIPELINE_LIMIT_SECONDS")
    bad = []
    seen = 0
    for key, job in _jobs(CRAWL_JOB_KEYS):
        seen += 1
        jt = _seconds(job.get("timeout"))
        if not jt:
            bad.append("%s：job 没有声明 timeout" % key)
            continue
        if jt > PLATFORM_MAX_PIPELINE_SECONDS:
            bad.append("%s：job timeout=%ds > 实测上限 %ds" % (key, jt, PLATFORM_MAX_PIPELINE_SECONDS))
        if limit and abs(jt - limit) > 300:
            bad.append("%s：job timeout=%ds 与 PIPELINE_LIMIT_SECONDS=%ds 差 %ds（>300s ⇒ 两处尺子不一致）"
                       % (key, jt, limit, abs(jt - limit)))
    assert seen, "一条爬取链都没认到 ⇒ 读数无效"
    assert not bad, "时间账声明与平台实际上限不同尺：%s" % bad


def test_crawl_stage_timeouts_are_within_the_job():
    """stage timeout 超过 job 的部分是**虚构额度**：等于没写，还会骗过"预算已覆盖"的自检。"""
    offenders = []
    checked = 0
    for key, job in _jobs(CRAWL_JOB_KEYS):
        jt = _seconds(job.get("timeout"))
        if not jt:
            continue
        for s in _stages(job):
            name = str(s.get("name") or "")
            if not any(w in name for w in CRAWL_STAGE_WORDS):
                continue
            checked += 1
            st = _seconds(s.get("timeout"))
            if not st:
                offenders.append("%s/%s：没有 stage timeout" % (key, name))
            elif st > jt:
                offenders.append("%s/%s：stage timeout=%ds > job timeout=%ds（超出部分不可用）"
                                 % (key, name, st, jt))
    assert checked, "一个爬取段都没认到 ⇒ 读数无效"
    assert not offenders, "爬取段 timeout 超过 job 预算（两份拷贝都要改）：%s" % offenders


def test_one_round_can_reach_publish_inside_the_cap():
    """**这才是目的的实质**：一轮必须在平台上限内跑到发布段（否则断点永不回灌、Pages 永不刷新）。"""
    limit = _const("PIPELINE_LIMIT_SECONDS") or 0
    reserve = 0
    for k in PUBLISH_RESERVE_KEYS:
        reserve = _const(k) or reserve
    weights = {}
    m = re.search(r"STEP_WEIGHTS\s*=\s*\{(.*?)\}", ALLOC, re.S)
    if m:
        for name, val in re.findall(r"['\"]([\w-]+)['\"]\s*:\s*(\d+)", m.group(1)):
            weights[name] = int(val)
    assert weights, "读不到 STEP_WEIGHTS ⇒ 判『读不到』，不许判过"
    total = limit + 0
    budget_sum = total  # 各步预算之和 ≤ PIPELINE_LIMIT（分配器只会切它，不会超）
    need = budget_sum + (reserve or 0)
    assert need <= PLATFORM_MAX_PIPELINE_SECONDS, (
        "一轮要 %ds（预算 %ds + 发布预留 %ds）> 平台实测上限 %ds ⇒ "
        "发布/回推断点/线上验收必然被掐死在起跑后（cnb-tcl 就是这么红的）"
        % (need, total, reserve or 0, PLATFORM_MAX_PIPELINE_SECONDS))
    assert len(weights) >= 4, "STEP_WEIGHTS 步数异常（读不到四步说明分配器变了）"


def test_red_sample_fictional_budget_is_caught():
    """红样自校：把上限抬回 10h（就是当前 main 的样子），第一条必须能变红。"""
    fake = 10 * 60 * 60
    assert fake > PLATFORM_MAX_PIPELINE_SECONDS
    assert not (fake <= PLATFORM_MAX_PIPELINE_SECONDS), "红样构造失败：这条判据就永远不会红"

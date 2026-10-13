"""爬取阶段的 `timeout` 必须盖得住分配器真的发给它的秒数（判据，当前 main 上必须红）。

**为什么是比值不变式而不是写死 3h/5h**：写死数字会在下一次改权重/改 job timeout 时又脱节。
本仓已经为脱节付过两次学费：
  * #34 把 `allocate_crawl_budget.py` 的 `PIPELINE_LIMIT_SECONDS` 从 2h 折算对齐到 job 声明的 10h；
  * 但**阶段级** `timeout` 还停在旧尺度上 ⇒ 预算给到 8505s，阶段 3600s 就被硬杀。

**实测（监工 10-13 22:24 +08:00，两条证据互相咬合）**：
- `origin/main` 上 `爬取-汽车之家 timeout: 1h`、`爬取-懂车帝 timeout: 2h`、`爬取-易车 timeout: 6h`
  （`api_trigger` 与半月 `crontab: 5 8 1,16 * *` **两份拷贝都是这个值**）；
- `scripts/allocate_crawl_budget.py`：`PIPELINE_LIMIT_SECONDS=10h`、发布预留 1800s、安全余量 180s，
  `STEP_WEIGHTS` 四步各 250‰ ⇒ 每步 8505s ⇒ 汽车之家要 8505s、懂车帝要 17010s；
- 手动轮 `cnb-k02-1k4oc66pl`（10-12 15:37Z）阶段级读数：
  **`爬取-汽车之家=error(3600.1s)`** —— 正好死在 1h 上，其后 17 个阶段全部 skipped
  ⇒ 这一轮既没发布、也没回推断点，现网 Pages 的 `manifest.updatedAt` 至今还停在 10-12T09:37:58Z。

**两条红线（本判据都钉住）**：
1. 阶段 timeout ≥ 该阶段被发的预算（不够就是"注定被硬杀"）；
2. **不许靠削预算来过关**：各步预算之和仍要 ≥ job timeout 的一个下限比例，
   否则"把 PIPELINE_LIMIT_SECONDS 改回 2h"这种假修会让不变式当场变绿而覆盖率倒退（#34 的成果被吃掉）。
"""

from __future__ import annotations

import importlib.util
import pathlib
import re

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
CFG = yaml.safe_load((ROOT / ".cnb.yml").read_text(encoding="utf-8")) or {}
MAIN = CFG.get("main") or {}

STAGE_FOR_STEP = {
    "爬取-汽车之家": ("autohome_step1",),
    "爬取-懂车帝": ("dongchedi_step1", "dongchedi_step2"),
    "爬取-易车": ("yiche",),
}
BUDGET_FLOOR_RATIO = 0.60  # 削预算假修的探测器：见文档字符串第 2 条红线


def _spec():
    path = ROOT / "scripts" / "allocate_crawl_budget.py"
    return importlib.util.spec_from_file_location("allocate_crawl_budget", path)


def _allocator():
    mod = importlib.util.module_from_spec(_spec())
    _spec().loader.exec_module(mod)
    return mod


def _seconds(text) -> int:
    """`1h` / `30m` / `1h30m` / 裸秒数都能读；读不出来就报错，不许当 0。"""
    if isinstance(text, (int, float)):
        return int(text)
    s = str(text or "").strip()
    if not s:
        raise ValueError("空的 timeout 声明")
    if re.fullmatch(r"\d+", s):
        return int(s)
    found = re.findall(r"(\d+)\s*([hm])", s)
    if not found:
        raise ValueError("认不出的 timeout 写法：%r" % s)
    total = 0
    for num, unit in found:
        total += int(num) * (3600 if unit == "h" else 60)
    return total


def _crawl_chains():
    """按**内容**认链：含任一爬取阶段的 job。crontab 的键带表达式，所以不写死键名。"""
    out = []
    for key, val in MAIN.items():
        for job in (val if isinstance(val, list) else [val]):
            if not isinstance(job, dict):
                continue
            stages = [s for s in (job.get("stages") or []) if isinstance(s, dict)]
            names = {str(s.get("name") or "") for s in stages}
            hit = [n for n in STAGE_FOR_STEP if any(n in x for x in names)]
            if hit:
                out.append((str(key), job, stages, hit))
    return out


def test_chains_discovered_and_budget_nonzero():
    chains = _crawl_chains()
    assert chains, "一条含爬取阶段的链都没认出来：解析退化 ≠ 没跑，宁可判崩"
    copies = {c[0] for c in chains}
    assert len(copies) >= 2, (
        "只认出 %d 份爬虫链（%s）：本仓的爬虫链至少有 api_trigger 与半月 crontab 两份拷贝，"
        "只改一份是半修" % (len(copies), sorted(copies)))
    mod = _allocator()
    budgets = mod.allocate(None, 0, debug=False)
    assert sum(budgets.values()) > 0, (
        "分配器在正常调用下给出 0 预算 ⇒ 读数无效（不许据此判绿）；实际=%s" % budgets)


def test_stage_timeout_covers_allocated_budget():
    mod = _allocator()
    budgets = mod.allocate(None, 0, debug=False)
    offenders = []
    for key, job, stages, _hit in _crawl_chains():
        for stage in stages:
            name = str(stage.get("name") or "")
            steps = next((v for k, v in STAGE_FOR_STEP.items() if k in name), None)
            if not steps:
                continue
            need = sum(int(budgets.get(s, 0)) for s in steps)
            if need <= 0:
                continue  # 预算被窗口/余量吃光时该阶段自己会跳过，不是本不变式管的
            declared = _seconds(stage.get("timeout")) if stage.get("timeout") else 0
            if declared < need:
                offenders.append("%s / %s：阶段 timeout=%ds 盖不住分配器发的 %ds（差 %ds）"
                                 % (key, name, declared, need, need - declared))
    assert not offenders, (
        "预算给到了，阶段却会在中途被硬杀 ⇒ 整轮判红、发布与断点回推全被连带跳过"
        "（实测同形失败：`cnb-k02` 的 爬取-汽车之家=error(3600.1s)）。缺口：%s" % offenders)


def test_budget_not_gutted_to_pass_the_invariant():
    """防假修：不许把 PIPELINE_LIMIT_SECONDS / 权重调小来让第二条变绿。"""
    mod = _allocator()
    job_seconds = max(
        _seconds(j.get("timeout")) or 0
        for _k, v in MAIN.items() for j in (v if isinstance(v, list) else [v])
        if isinstance(j, dict) and any(
            any(n in str(s.get("name") or "") for s in (j.get("stages") or []) if isinstance(s, dict))
            for n in STAGE_FOR_STEP))
    assert job_seconds > 0, "认不到任何爬虫 job 的 timeout ⇒ 读数无效"
    budgets = mod.allocate(None, 0, debug=False)
    total = sum(budgets.values())
    ratio = total / float(job_seconds)
    assert ratio >= BUDGET_FLOOR_RATIO, (
        "各步预算之和只占 job 声明 timeout 的 %.0f%%（%ds/%ds）：这是靠削预算让"
        "『timeout 盖得住预算』假绿，覆盖率会倒退。#34 的对齐成果不许被吃掉。" % (
            ratio * 100, total, job_seconds))
    assert mod.PIPELINE_LIMIT_SECONDS == job_seconds, (
        "分配器承认的总上限 %ds 与爬虫 job 声明的 timeout %ds 又脱节了"
        % (mod.PIPELINE_LIMIT_SECONDS, job_seconds))

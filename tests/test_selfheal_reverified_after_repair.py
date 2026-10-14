"""自愈段跑完之后必须**再过一次交付核对**，且核对逻辑只能有一份物理实现（判据，main 上必须红）。

**实测依据（10-14 逐条取数，不是推断）**：
- `$: issue.open` 的链形状（main `6999c96` 上 YAML 解析结果，原样）：
  `stages = ['检查fix标签','install-deps','AI-Issue驱动修复','交付核对-产物必须真取回']`
  `failStages = ['诊断-收集失败上下文','AI-修复-第1轮']`
  ⇒ `交付核对` 只在**修复之前**跑一次；修完之后**没有任何一段再核对**。
- 现网正好演完了这一幕：`cnb-8d5-1k4socvu6`（Issue #82）
  `AI-Issue驱动修复 success 2863s` → `交付核对 error(1s)`（`DELIVERY-FAIL reason=no-comments`）
  → `诊断 success` → `AI-修复-第1轮 start` ——
  如果这轮修复真的产出了产物，**没人再取一次、再判一次**；如果它什么都没产出，
  整条构建仍可能以 success 收场 ⇒ "链的绿 = 交付发生"在自愈路径上是空的。
- 同一族的历史读数：`goal_audit` 三档里 **"修复段自身跑绿" b=0、"红段+修复绿+门禁绿" 完整案例 c=0**
  —— 在现在这个形状下，c **结构上不可观测**，不是"还没碰上"。

⇒ 判据钉三件事（都可结构判定、算术可比）：
1. **每条含 `failStages` 的链**，其自愈链里 `npc:go` 修复段**之后**必须存在**再验证段**
   （名字含「交付核对」或「验证」），不能只靠主链里修复**之前**那次；
2. **核对逻辑只许一份物理实现**：再验证段与主链的核对段都必须**调用同一个脚本文件**
   （`scripts/<name>.py` 真存在于仓库里），
   内联字面块出现两份 = 半修（改一处漏一处，本店踩过：同一文件里的重复字面块只改一份会留下第二份被执行）；
3. 再验证段**不许恒真**：不许 `|| true`、不许 `exit 0` 无条件、不许把结果只 `echo` 出来就过。

红样自校（`--selftest`）：把再验证段删掉 / 把它挪到修复段之前 / 两处各自内联一份字面块 /
把再验证段改成 `|| true` —— 四种变异都必须干净变红；合规样张必须绿。
"""

from __future__ import annotations

import argparse
import copy
import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
CFG = ROOT / ".cnb.yml"
RECHECK_MARK = ("交付核对", "验证")
SCRIPT_RE = re.compile(r"scripts/[0-9A-Za-z_./-]+\.py")
BAD_ALWAYS_TRUE = ("|| true", "||exit 0", "|| exit 0")


def load(path=CFG):
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def jobs_of(cfg):
    out = []
    for section, prefix in (("main", ""), ("$", "$: ")):
        node = cfg.get(section) or {}
        if not isinstance(node, dict):
            continue
        for event, jobs in node.items():
            for job in (jobs if isinstance(jobs, list) else [jobs]):
                if isinstance(job, dict):
                    out.append(("%s%s" % (prefix, event), job))
    return out


def stage_list(job, bucket):
    return [s for s in (job.get(bucket) or []) if isinstance(s, dict)]


def text_of(stage):
    return "%s\n%s" % (str(stage.get("script") or ""), str(stage.get("steps") or ""))


def find_recheck(stages):
    for i, s in enumerate(stages):
        name = str(s.get("name") or "")
        if any(mark in name for mark in RECHECK_MARK):
            return i, s
    return None, None


def check(cfg, require_files=True) -> list[str]:
    bad: list[str] = []
    jobs = jobs_of(cfg)
    if not jobs:
        return ["读不到任何链（解析退化 ⇒ 判崩不判过）"]
    for event, job in jobs:
        heal = stage_list(job, "failStages")
        if not heal:
            continue
        repair_idx = None
        for i, s in enumerate(heal):
            if str(s.get("type") or "") == "npc:go" or "修复" in str(s.get("name") or ""):
                repair_idx = i
                break
        if repair_idx is None:
            bad.append("%s：自愈链里没有修复段" % event)
            continue
        recheck_idx, recheck = find_recheck(heal)
        if recheck is None:
            bad.append("%s：自愈链在修复段之后**没有再验证段**"
                       "（主链那次核对跑在修复之前，修完没人再取产物再判一次）" % event)
            continue
        if recheck_idx <= repair_idx:
            bad.append("%s：再验证段(%d)排在修复段(%d)之前或同一位置 ⇒ 修完仍未被复核"
                       % (event, recheck_idx, repair_idx))
            continue
        body = text_of(recheck)
        if any(w in body for w in BAD_ALWAYS_TRUE) or re.search(r"\|\|\s*exit\s+0", body):
            bad.append("%s：再验证段恒真（出现 `|| true` / `|| exit 0` 一类）" % event)
        scripts = SCRIPT_RE.findall(body)
        gate_like = "交付核对" in str(recheck.get("name") or "")
        runs_pytest = bool(re.search(r"pytest", body))
        if not scripts and not (runs_pytest and not gate_like):
            bad.append("%s：再验证段既没调用 `scripts/*.py`，也不是真跑 pytest ⇒ 拿不到可复核的结论"
                       "（『验证-实际pytest』这种内联跑法是可接受的，只有交付核对类必须共用一份脚本实现）"
                       % event)

        main_idx, main_recheck = find_recheck(stage_list(job, "stages"))
        if main_recheck is not None and scripts:
            main_scripts = SCRIPT_RE.findall(text_of(main_recheck))
            if not gate_like:
                pass   # 再验证是"真跑 pytest"类：不要求与主链共用脚本
            elif not main_scripts:
                bad.append("%s：主链核对段没调用脚本（与再验证段不可能同一把尺子）" % event)
            elif set(main_scripts) & set(scripts):
                pass   # 共用同一份实现：这才是要求的形状
            else:
                bad.append("%s：主链核对用 %s、自愈再验证用 %s ⇒ 两份字面块，改一处漏一处"
                           % (event, main_scripts[:2], scripts[:2]))
        for path in scripts:
            if require_files and not (ROOT / path).exists():
                bad.append("%s：再验证段调用的 %s 在仓库里不存在" % (event, path))
    return bad


def sample() -> dict:
    gate_script = "python scripts/check_delivery_artifacts.py --issue \"$CNB_EVENT_ISSUE_NUMBER\""
    heal = [
        {"name": "诊断-收集失败上下文", "timeout": "5m", "script": "tail -50 /tmp/x.log"},
        {"name": "AI-修复-第1轮", "type": "npc:go", "timeout": "60m",
         "options": {"maxTurns": 120}},
        {"name": "交付核对-修复后必须真取回", "timeout": "10m", "script": gate_script},
    ]
    return {"main": {"api_trigger": [{
        "name": "爬虫轮次", "timeout": "3h",
        "stages": [{"name": "交付核对-产物必须真取回", "timeout": "10m", "script": gate_script}],
        "failStages": heal}]}}


def selftest() -> int:
    cases = []
    bad = check(sample(), require_files=False)
    cases.append(("合规样张判绿", not bad, bad[:2]))

    m = copy.deepcopy(sample())
    m["main"]["api_trigger"][0]["failStages"].pop()
    cases.append(("删掉再验证段判红", bool(check(m, require_files=False)), []))

    m = copy.deepcopy(sample())
    fs = m["main"]["api_trigger"][0]["failStages"]
    fs.append(fs.pop(2))
    fs.insert(0, fs.pop())
    cases.append(("再验证排在修复之前判红", bool(check(m, require_files=False)), []))

    m = copy.deepcopy(sample())
    m["main"]["api_trigger"][0]["failStages"][2]["script"] = \
        "python scripts/check_repair_artifacts.py || true"
    cases.append(("恒真再验证判红", bool(check(m, require_files=False)), []))

    m = copy.deepcopy(sample())
    m["main"]["api_trigger"][0]["failStages"][2]["script"] = "echo 看一眼就行"
    cases.append(("没有脚本调用的再验证判红", bool(check(m, require_files=False)), []))

    fails = 0
    for name, want, extra in cases:
        fails += 0 if want else 1
        print("  自校 %-26s ⇒ %s%s" % (name, "OK" if want else "错",
                                       (" " + str(extra)) if extra and not want else ""))
    print("SELFTEST %s" % ("通过（双向都能判对）" if not fails else "失败 %d 例" % fails))
    return 1 if fails else 0


# ---------------- pytest 口（判据必须被 `python -m pytest` 收起来，否则 CI 里等于没装闸） ----------------
# 反面教材（10-14 复盘，同一类四份一起中招）：只写 CLI 就发单，正文又要求 `pytest … rc=0`
# ⇒ 实际收 0 例退 5；要么 NPC 死于不可满足的验收，要么闸交付回来仍是惰性的。

def test_parser_recognizes_chains():
    """反空转：一条链都没认到 ⇒ 判定退化，必须当场变红，不许"空集合通过"。"""
    assert jobs_of(load()), "解析不到任何链（`.cnb.yml` 形状变了或读法退化）⇒ 读数无效"


def test_selftest_bidirectional():
    """变异回放：删再验证段 / 排在修复之前 / 恒真 / 不调用脚本 都要干净变红，合规样张必须绿。"""
    assert selftest() == 0


def test_repo_chains_have_post_repair_recheck():
    """现网每条带自愈链的链都必须有"修复之后"的再核对段（本单落地前必须红）。"""
    problems = check(load())
    assert not problems, "\n".join(problems)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    bad = check(load())
    if bad:
        print("自愈之后没有再验证（或有两份字面块）：%d 处" % len(bad))
        for b in bad:
            print("  ✗ " + b)
        return 1
    print("每条自愈链都在修复段之后再核对一次，且核对逻辑只有一份物理实现")
    return 0


if __name__ == "__main__":
    sys.exit(main())

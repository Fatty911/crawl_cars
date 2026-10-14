"""回推段必须按**工作树状态**判成活，不许按 `rebase` 的返回码判（判据，main 上必须红）。

**这不是假想坑，是 10-14 21:18 用真实 git 冲突仿真测出来的**（一次性 scratch 仓库，跑完即删）：

```
$ git fetch -q origin main && git rebase -q --autostash FETCH_HEAD
Created autostash: 9362faf
Your local changes are stashed, however applying them resulted in conflicts.
STEP1 autostash rc=0                 ← **返回 0**
$ git rev-list --count FETCH_HEAD..HEAD  → 1     （本地提交已重放成功）
$ git status --porcelain             → UU p.json （工作树留着 `<<<<<<<`，.git/AUTO_MERGE 在场）
STEP2 再跑一次 rc=128                ← 下一轮进循环就是 fatal: Cannot autostash
```

⇒ 两条独立的失效通道，都得钉：
① **`--autostash` 的 rc=0 假成活**：`until` 循环第一次就"成功"，不重试、不点名 `PUSHBACK-FAIL`，
   随后 `git push` 是 fast-forward ⇒ 回推段**判绿**，而同一条流水线后面的
   `组装发布站点` / `发布到 Cloudflare Pages` / `线上验收` 读的是**同一片带冲突标记的工作树**；
② **三次用尽后 `break` 仍走到 `git push`**（现网 `.cnb.yml:473` 只有 `break`，`:478` 无条件 push）。
   HEAD 与远端相同时 push 回 `Everything up-to-date` rc=0 ⇒ **又是绿**。

**判据钉四件事**（都按解析出来的数据判定，链名/键名不写死；三处回推段各查一遍，只改一处 = 半修）：
1. **E1 用尽即失败**：`PUSHBACK-FAIL reason=` 那条点名分支必须在同一个复合语句里 `exit 1`
   （或紧跟 `exit` 非零），**不许只 `break`** —— `break` 只是跳出循环，后面那行 push 照样执行；
2. **E2 push 前必须证明工作树没有未合并项**：循环 `done` 之后、`git push` 之前，必须存在一次
   unmerged 检查（`git ls-files -u` / `git diff --check` / `git status --porcelain` 配 `UU|AA|DD|U ` 形状），
   并且不干净时 `exit 1`。**只看 rebase 的返回码不算**（上面实测它冲突时返回 0）；
3. **E3 不许把 #87 改掉**：`--autostash`（或 `stash push -u` + `stash pop` 的等价形状）必须仍在，
   `fetch` + rebase 到 `FETCH_HEAD`/`origin/main` 的语义必须仍在，`git push` 仍不许 `--force`；
4. **E4 覆盖面与反退化**：认到的回推段每一段都要过 1+2+3；一段都没认到 ⇒ 判"读数无效"，不许判过。

红样自校（`--selftest`）：只 `break` 不 `exit 1` / 缺 unmerged 检查 / unmerged 检查放在 push 之后 /
三处只补两处（半修）/ 摘掉 `--autostash` / 改用 `push --force` —— 六种变异都必须**干净变红**；
合规样张必须绿。
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
CFG = ROOT / ".cnb.yml"

REASON_RE = re.compile(r"PUSHBACK-FAIL\s+reason=")
EXIT_RE = re.compile(r"\bexit\s+[1-9]")
UNMERGED_RE = re.compile(r"git\s+ls-files\s+-u|--unmerged|git\s+diff\s+--check|"
                         r"git\s+status\s+--porcelain[^\n]*(?:\|\s*grep[^\n]*(?:UU|AA|DD|U\s|\^))")
PUSH_RE = re.compile(r"git\s+push\b")
AUTOSTASH_RE = re.compile(r"git\s+(?:-[^\s]+\s+)*rebase\b[^\n|;&]*--autostash|"
                          r"git\s+(?:-[^\s]+\s+)*pull\s+--rebase[^\n|;&]*--autostash")
STASH_PUSH_RE = re.compile(r"git\s+stash\s+push\b[^\n]*(?:-u|--include-untracked)")
STASH_POP_RE = re.compile(r"git\s+stash\s+pop\b")
FETCH_RE = re.compile(r"git\s+fetch\b")
REBASE_RE = re.compile(r"git\s+(?:-[^\s]+\s+)*rebase\b")
FORCE_PUSH_RE = re.compile(r"git\s+push\b[^\n]*(?:--force(?!-with-lease)|-f\b)")
LOOP_END_RE = re.compile(r"^\s*done\b", re.M)


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


def pushback_stages(job):
    found = []
    for bucket in ("stages", "failStages"):
        for s in job.get(bucket) or []:
            if isinstance(s, dict) and "回推" in str(s.get("name") or ""):
                found.append(s)
    return found


def body_of(stage):
    return str(stage.get("script") or "") + "\n" + str(stage.get("steps") or "")


def _clean(line):
    """去掉行尾续行符，让"复合语句里有没有 exit 1"这类判断只看同一逻辑行。"""
    return line.rstrip("\\").rstrip()


def check_stage(body):
    problems = []

    # --- E1：点名失败的分支必须非零退出，不能只是 break ---
    reason_lines = [ln for ln in body.splitlines() if REASON_RE.search(ln)]
    if not reason_lines:
        problems.append("失败没有 PUSHBACK-FAIL reason= 点名（不许用静默跳过凑绿）")
    else:
        # **每一处**点名都必须自带非零 exit（同一行或紧随两行内）。
        # 用 any() 会被别处（比如 E2 的守卫块）的 exit 掩盖 —— 10-14 自校就是这么暴露的：
        # "只 break" 的变异被守卫块里的 `exit 1` 顶了一下，读成绿。
        lines = body.splitlines()
        idxs = [i for i, ln in enumerate(lines) if REASON_RE.search(ln)]
        silent = [i + 1 for i in idxs
                  if not any(EXIT_RE.search(_clean(j)) for j in lines[i:i + 3])]
        if silent:
            problems.append("E1：第 %s 行的 PUSHBACK-FAIL 点名后面没有非零 exit ⇒ "
                            "用尽后只 break，后面的 git push 仍会执行（假绿通道②）"
                            % "、".join(str(n) for n in silent))

    # --- E2：push 之前必须查未合并项并不干净就退出 ---
    push_at = [i for i, ln in enumerate(body.splitlines()) if PUSH_RE.search(ln)
               and not re.search(r"#.*git push", ln)]
    if not push_at:
        problems.append("没找到 git push ⇒ 本段形状变了，读数无效")
    else:
        first_push = min(push_at)
        lines = body.splitlines()
        # 守卫必须落在"**重试循环结束之后、push 之前**"这一段里。
        # 只看"文里某处有 unmerged 检查"是宽松的：写在循环之前（那时还没 rebase）拦不住任何东西。
        rebase_idxs = [i for i, ln in enumerate(lines) if REBASE_RE.search(ln) and i < first_push]
        window_start = (max(rebase_idxs) + 1) if rebase_idxs else max(0, first_push - 8)
        guard_at = [i for i, ln in enumerate(lines)
                    if UNMERGED_RE.search(ln) and window_start <= i < first_push]
        if not rebase_idxs:
            problems.append("E2：push 之前没有 rebase ⇒ 定位不了『rebase 之后、push 之前』这段")
        elif not guard_at:
            problems.append("E2：rebase 之后、push 之前没有未合并项检查（实测 rebase --autostash "
                            "冲突时 rc=0，只看返回码会把带 <<<<<<< 的工作树当成活推上去）")
        else:
            near = lines[min(guard_at):min(guard_at) + 6]
            if not any(EXIT_RE.search(_clean(ln)) for ln in near):
                problems.append("E2：查了未合并项但不 exit 非零 ⇒ 只报数不拦停")

    # --- E3：不许为了凑绿把 #87 的形状改掉 ---
    if REBASE_RE.search(body) and not (AUTOSTASH_RE.search(body)
                                       or (STASH_PUSH_RE.search(body) and STASH_POP_RE.search(body))):
        problems.append("E3：rebase 不再是脏树可成活形状（#87 那格被改回去了）")
    if not FETCH_RE.search(body):
        problems.append("E3：fetch 语义丢失（必须回到远端 main 再推）")
    if FORCE_PUSH_RE.search(body):
        problems.append("E3：用 push --force 掩盖 non-fast-forward（越权：会抹掉别人的提交）")
    return problems


def check(cfg):
    bad = []
    total = 0
    good = 0
    for event, job in jobs_of(cfg):
        for stage in pushback_stages(job):
            total += 1
            problems = check_stage(body_of(stage))
            if problems:
                bad.append("%s/%s：%s" % (event, stage.get("name"), "；".join(problems)))
            else:
                good += 1
    if not total:
        return ["一条回推段都没认到 ⇒ 读数无效，不许判过（反退化：至少应认出 3 处）"]
    if good < total:
        bad.append("半修风险：回推段共 %d 处，全合规只有 %d 处" % (total, good))
    if total < 3:
        bad.append("只认出 %d 处回推段（现网应有 3 处）⇒ 覆盖面可疑，判读数无效" % total)
    return bad


# ---------------- 样张与红样自校 ----------------

def _block(reason="exit", guard="before", autostash=True, force=False):
    """合规形状的一段回推脚本。reason=break ⇒ 模拟现网"只跳出循环"；
    guard=after ⇒ 未合并检查排在 push 之后；guard=none ⇒ 根本没有检查。"""
    lines = ["set -e",
             'PB_REMOTE=https://cnb.example/repo.git',
             "n=0",
             "git add -f crawl_state || true"]
    rebase = "git rebase -q%s FETCH_HEAD" % (" --autostash" if autostash else "")
    tail = ("{ echo \"PUSHBACK-FAIL reason=rebase-exhausted attempts=$n\"; exit 1; }"
            if reason == "exit" else
            "{ echo \"PUSHBACK-FAIL reason=rebase-exhausted attempts=$n\"; break; }")
    lines += ["until git fetch -q \"$PB_REMOTE\" main && %s; do" % rebase,
              "  n=$((n+1))",
              "  if [ \"$n\" -ge 3 ]; then %s; fi" % tail,
              "  echo \"[pushback] rebase 第 $n 次没成，10s 后重试\"",
              "  sleep 1",
              "done"]
    guard_txt = ('if [ -n "$(git ls-files -u)" ]; then\n'
                 '  echo "PUSHBACK-FAIL reason=unmerged-after-autostash"\n'
                 '  exit 1\n'
                 'fi')
    push = 'git push%s "$PB_REMOTE" HEAD:main' % (" --force" if force else "")
    if guard == "before_loop":
        lines = [guard_txt] + lines + [push]
    elif guard == "before":
        lines += [guard_txt, push]
    elif guard == "after":
        lines += [push, guard_txt]
    else:
        lines += [push]
    return "\n".join(lines) + "\n"


def sample(breaks=(), half=False, guard="before", autostash=True, force=False):
    """三处回推段（api_trigger / 半月 crontab / 周报价链）。
    half=True ⇒ 只有前两处合规（模拟半修）；breaks 里列的下标改成只 break。"""
    def one(i):
        bad_break = (i in breaks) or (half and i == 2)
        bad_guard = "none" if (half and i == 2) else guard
        return _block(reason="break" if bad_break else "exit",
                      guard=bad_guard, autostash=autostash, force=force)
    cfg = {"$": {
        "api_trigger": [{"stages": [{"name": "回推增量状态", "script": one(0)}]}],
        "crontab: 5 8 1,16 * *": [{"stages": [{"name": "回推增量状态", "script": one(1)}]}],
        "crontab: 37 8 * * 0": [{"stages": [{"name": "回推报价数据", "script": one(2)}]}],
    }}
    return cfg


MUTATIONS = [
    ("现网形状：用尽后只 break", dict(breaks=(0, 1, 2)), True),
    ("push 前不查未合并项", dict(guard="none"), True),
    ("未合并检查排在 push 之后", dict(guard="after"), True),
    ("未合并检查排在循环之前（还没 rebase 就查）", dict(guard="before_loop"), True),
    ("三处只补两处（半修）", dict(half=True), True),
    ("摘掉 --autostash（回退 #87）", dict(autostash=False), True),
    ("改用 push --force", dict(force=True), True),
    ("合规样张（三处全对）", dict(), False),
]


BOUND_RE = re.compile(r"^\s*(?:fi|done|\}|\belse\b|\belif\b)\b")


def _branch_has_exit(lines, i, span=14):
    """从点名那行往后扫到**本分支的边界**（fi/done/}/else），要求边界之前出现非零 exit。
    定死"三行内"是过严：合理实现会在 exit 前多打几行诊断（10-14 仿真里我自己就被这条绊了一下）。"""
    for j in range(i, min(i + span, len(lines))):
        if j > i and BOUND_RE.match(lines[j]):
            return False
        if EXIT_RE.search(_clean(lines[j])):
            return True
    return False


def selftest():
    bad = 0
    for name, kw, expect_red in MUTATIONS:
        problems = check(sample(**kw))
        red = bool(problems)
        ok = red == expect_red
        print("%-34s 期望=%-6s 实得=%-6s %s  %s"
              % (name, "红" if expect_red else "绿", "红" if red else "绿",
                 "OK" if ok else "FAIL", (problems or [""])[0][:78]))
        bad += 0 if ok else 1
    print("\n%d/%d 例通过" % (len(MUTATIONS) - bad, len(MUTATIONS)))
    return 1 if bad else 0


# ---------------- pytest 口（判据要能被 `python -m pytest` 收起来才算真上线） ----------------
# 反面教材：上一单的判据只有 CLI、没有 test_* 函数 ⇒ `pytest <该文件> -q` 退 5（no tests ran），
# 而我写进派发单里的验收命令要求 rc=0 —— 那是**监工自造的不可满足**。本单从第一版就带 test_*。

def test_sample_parser_sees_three_sites():
    """先证解析器看得见样张：认不到 3 处 ⇒ 自校与判定都会退化成"空对空"，必须当场变红。"""
    recognized = sum(len(pushback_stages(job)) for _e, job in jobs_of(sample()))
    assert recognized == 3, "样张只认出 %d 处回推段 ⇒ 样张形状与解析器不符" % recognized


def test_mutations_all_flip():
    """六种变异必须红、合规样张必须绿（单向测过的门禁等于没测）。"""
    wrong = []
    for name, kw, expect_red in MUTATIONS:
        red = bool(check(sample(**kw)))
        if red != expect_red:
            wrong.append("%s 期望%s 实得%s" % (name, "红" if expect_red else "绿",
                                              "红" if red else "绿"))
    assert not wrong, "变异回放不合格：%s" % "; ".join(wrong)


def test_repo_pushback_sites_gate_on_worktree():
    """现网 `.cnb.yml`：三处回推段都要"用尽即 exit 1 + push 前按工作树判成活"（#87 落地前必须红）。"""
    problems = check(load())
    assert not problems, "\n".join(problems)


def test_dirty_tree_guard_is_pytest_collectible():
    """上一单（#87）那份判据**只有 CLI、没有 `def test_`** ⇒ `pytest` 收到 0 例（rc=5），
    CI 里等于**闸没装**（监工自造缺陷，10-14 落地时实测 rc=5 才发现）。
    本单顺手补入口：往那份文件**追加** 3 个 `test_*` 函数，**断言逻辑一个字节都不许改**
    （落地时监工按 `git diff` 逐行核，只许文件末尾追加）。
    """
    sib = ROOT / "tests" / "test_pushback_rebase_survives_dirty_tree.py"
    assert sib.exists(), "找不到 #87 那份判据文件（被删了？那 #87 的修复也一起没了）"
    txt = sib.read_text(encoding="utf-8")
    assert re.search(r"^def test_", txt, re.M), (
        "#87 的判据没有 pytest 入口 ⇒ 全量套件永远不执行它；"
        "请只追加 test_* 函数（调用既有 check()/selftest()），不要动既有函数")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--file", default=str(CFG))
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    problems = check(load(pathlib.Path(a.file)))
    if problems:
        for p in problems:
            print("FAIL %s" % p)
        return 1
    print("PASS 三处回推段都按工作树状态判成活（用尽即 exit 1，push 前查未合并项，#87 形状仍在）")
    return 0


if __name__ == "__main__":
    sys.exit(main())

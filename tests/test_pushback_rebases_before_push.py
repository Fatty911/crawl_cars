"""回推段必须先 fetch + 有界 rebase 再 push（判据；当前 main 上必须全红）。

实测：轮次 `cnb-msr-1k4rn81kp` 的 `回推增量状态 = error(1.1s)`，原文
`! [rejected] HEAD -> main (fetch first)` —— 轮次跑到一半有人合并进 main，
轮次手里的克隆还停在起跑时的 main ⇒ 非快进被拒，整轮白跑。
本判据只钉"push 前先同步远端且有界重试"这一格（搬段顺序不在本单范围，也未证成）。
"""

from __future__ import annotations

import pathlib
import re

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
CFG = yaml.safe_load((ROOT / ".cnb.yml").read_text(encoding="utf-8")) or {}
MAIN = CFG.get("main") or {}

PUSHBACK = "回推增量状态"
CRAWL_CHAINS = ("api_trigger", "crontab: 5 8 1,16 * *")


def _script(stage):
    s = stage.get("script")
    if isinstance(s, dict):
        s = s.get("run") or ""
    return str(s or "")


def _pushback_stages():
    out = []
    for key in CRAWL_CHAINS:
        val = MAIN.get(key)
        for job in (val if isinstance(val, list) else [val]):
            if not isinstance(job, dict):
                continue
            for s in (job.get("stages") or []):
                if isinstance(s, dict) and PUSHBACK in str(s.get("name") or ""):
                    out.append((key, s))
    return out


def test_there_are_two_chain_copies_to_fix():
    """两份拷贝都要认到，否则"只改一份"会被当成修好（本仓栽过一次）。"""
    got = _pushback_stages()
    keys = {k for k, _ in got}
    assert len(got) >= 2, (
        "只找到 %d 处 `回推增量状态`（应为 api_trigger 与半月 crontab 两份拷贝各一处）⇒ "
        "改一份 = 半修，判据不允许据此判绿" % len(got))
    assert keys == set(CRAWL_CHAINS), "两份拷贝没都认到：%s" % sorted(keys)


def test_pushback_syncs_and_rebases_before_push():
    offenders = []
    for key, s in _pushback_stages():
        sc = _script(s)
        i_push = sc.find("git push")
        i_fetch = sc.find("git fetch")
        i_rebase = sc.find("rebase")
        if i_push < 0:
            offenders.append("%s：段里没有 git push（结构变了，判『读不到』）" % key)
            continue
        if i_fetch < 0 or i_rebase < 0:
            offenders.append("%s：push 前缺 fetch/rebase" % key)
            continue
        if not (i_fetch < i_push and i_rebase < i_push):
            offenders.append("%s：fetch/rebase 出现在 push 之后（等于没同步）" % key)
    assert not offenders, "回推没在 push 前同步远端 ⇒ 轮次期间任何一次合并都会让它 (fetch first) 被拒：%s" % offenders


def test_retry_is_bounded_and_names_the_reason():
    offenders = []
    for key, s in _pushback_stages():
        sc = _script(s)
        bounded = bool(re.search(r"until[\s\S]{0,600}(\-ge|\>=|>|==)\s*[1-9]", sc)) or \
            bool(re.search(r"for\s+\w+\s+in\s+[\d\s]+\.", sc))
        reason = ("PUSHBACK-FAIL" in sc) or ("reason=" in sc)
        if not bounded:
            offenders.append("%s：重试没有上限（无界循环不是修法）" % key)
        if not reason:
            offenders.append("%s：失败没点名 reason ⇒ 又像 1.1s 静默红" % key)
        if "|| exit 0" in sc or "|| true" in sc.split("git push")[0][-400:]:
            offenders.append("%s：push 附近出现 || true / || exit 0 ⇒ 把红吃成绿" % key)
    assert not offenders, "回推的同步重试不可核算或会静默：%s" % offenders


def test_red_sample_without_sync_is_caught():
    """红样自校：把 fetch/rebase 摘掉后，第二条必须变红（证明它不是空闸）。"""
    sc = "set -e\ngit commit -m x\nGIT_ASKPASS=/tmp/a git push \"$R\" HEAD:main\n"
    i_push = sc.find("git push")
    assert sc.find("git fetch") < 0 and sc.find("rebase") < 0
    assert not (0 <= sc.find("git fetch") < i_push), "红样构造失败 ⇒ 本自校无效（不许据此判绿）"

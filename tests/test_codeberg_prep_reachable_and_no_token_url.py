"""Codeberg 发布段的"重试"必须真的可达；全仓任何 push 都不许把令牌拼进 URL（判据，当前必须红）。

**为什么单独钉这两条（Issue #52 的 bundle 已把推送/预检改成 3 次循环，但整段还没闭环）**：
监工 10-13 22:35 +08:00 在 bundle 分支（`0dfb093`，基于 `ea2a67c`）里逐行读出 Codeberg 段的形状：

     1| set -e
    19| python scripts/setup_proxy_runtime.py --github-env /tmp/codeberg-proxy.env --test-url https://codeberg.org
    26| CB_ATTEMPT=1
    28| while [ "$CB_ATTEMPT" -le "$CB_MAX_ATTEMPTS" ]; do   ← 第一个重试循环从这里才开始

⇒ 代理准备（第 19 行）本身就是那条会因 TLS/代理抖动失败的网络命令，它在 `set -e` 下**裸跑**，
一抖就整段退出，后面的 curl 预检循环与 push 循环**一次都轮不到**。
"重试已实现"与"重试可达"是两件事——本判据钉后者。

**第二条**：`#40/#52` 只改了三处回推的凭据形状，第四处仍在把令牌拼进 URL：
NPC 自修复链的 `git push "https://${CNB_TOKEN_USER_NAME:-cnb}:${CNB_TOKEN}@cnb.cool/…/crawl_cars.git" HEAD:refs/heads/diag`。
本仓规则是"凭据只走 GIT_ASKPASS/临时配置，不入 URL/进程表/被跟踪文件"，且本仓已经发生过一次
公开构建日志凭据外泄 ⇒ 这一处必须一起收口（判据按**全文所有链所有段**扫，不留"这处不属本单"的死角）。

两条都配反空壳守卫：不许用"删掉诊断回推段"或"删掉代理准备段"来让扫描变绿。
"""

from __future__ import annotations

import pathlib
import re

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
CFG = yaml.safe_load((ROOT / ".cnb.yml").read_text(encoding="utf-8")) or {}
MAIN = CFG.get("main") or {}
DOLLAR = CFG.get("$") or {}

CODEBERG_WORDS = ("Codeberg",)
TOKEN_URL = re.compile(r"[/@][^\s\"']*\$\{?[A-Z0-9_]*TOKEN[^\s\"']*\}@|:\$\{?[A-Z0-9_]*TOKEN\}?\@")
RETRY_HEAD = re.compile(r"\b(while|for)\b")
PREP_CMD = "setup_proxy_runtime.py"


def _script(stage):
    b = stage.get("script")
    if isinstance(b, dict):
        b = b.get("run") or ""
    elif isinstance(b, list):
        b = "\n".join(str(x) for x in b)
    return str(b or "")


def _live(script):
    return [l for l in script.splitlines() if not l.strip().startswith("#")]


def _all_stages():
    out = []
    for root in (MAIN, DOLLAR):
        for key, val in root.items():
            for job in (val if isinstance(val, list) else [val]):
                if not isinstance(job, dict):
                    continue
                for bucket in ("stages", "failStages"):
                    for s in (job.get(bucket) or []):
                        if isinstance(s, dict):
                            out.append((str(key), s))
    return out


def _codeberg_stages():
    return [(k, s) for k, s in _all_stages()
            if any(w in str(s.get("name") or "") for w in CODEBERG_WORDS)]


def test_codeberg_stages_exist_in_both_copies():
    """反空壳：不许靠删掉 Codeberg 发布段来过。"""
    got = _codeberg_stages()
    assert got, "整份 .cnb.yml 里找不到 Codeberg 发布段：要么链被拆了，要么在读不到 ⇒ 不许判绿"
    chains = {k for k, _ in got}
    assert len(chains) >= 2, (
        "只有 %s 有 Codeberg 段：本仓爬虫链至少两份拷贝，只改一份是半修" % sorted(chains))


def test_fallible_prep_is_reachable_from_a_retry_loop():
    """代理准备（会因 TLS/代理抖动失败）必须落在重试循环体内，或带显式 `if !` 处理；
    `set -e` + 裸命令 = 一抖就退出，后面的循环永远轮不到。"""
    offenders = []
    for key, stage in _codeberg_stages():
        lines = _live(_script(stage))
        text = "\n".join(lines)
        idx = next((i for i, l in enumerate(lines) if PREP_CMD in l), None)
        if idx is None:
            offenders.append("%s：%s 段里没有 %s，代理准备这一环不见了（不许删环节过关）"
                             % (key, stage.get("name"), PREP_CMD))
            continue
        guarded = bool(re.search(r"if\s+!\s*.*%s" % re.escape(PREP_CMD), text))
        in_loop = False
        depth = 0
        for i, l in enumerate(lines):
            if RETRY_HEAD.search(l):
                depth += 1
            if depth > 0 and i == idx:
                in_loop = True
            if re.match(r"^\s*done\b", l) and depth > 0:
                depth -= 1
        if not (in_loop or guarded):
            offenders.append(
                "%s：第 %d 行的代理准备在 `set -e` 下裸跑（重试循环从第 %s 行才开始）⇒ 抖动直接退出，循环不可达"
                % (key, idx + 1,
                   next((str(i + 1) for i, l in enumerate(lines) if RETRY_HEAD.search(l)), "无")))
    assert not offenders, "Codeberg 段的重试结构形同虚设：%s" % offenders


def test_no_token_in_any_push_url():
    """全文扫：任何链、任何段（含 failStages 与 diag 回推）都不许把 *TOKEN* 拼进 push/clone URL。"""
    offenders = []
    for key, stage in _all_stages():
        for l in _live(_script(stage)):
            if ("git push" in l or "git clone" in l or "git -c" in l or "remote add" in l) and TOKEN_URL.search(l):
                offenders.append("%s / %s：%s" % (key, stage.get("name"), l.strip()[:110]))
    assert not offenders, (
        "凭据面违规（令牌进 URL ⇒ 进进程表与公开构建日志）：%s" % offenders)


def test_diag_pushback_still_exists_and_uses_askpass():
    """反空壳：第四处收口不能靠删掉诊断回推段。"""
    hits = []
    for key, stage in _all_stages():
        lines = _live(_script(stage))
        text = "\n".join(lines)
        if "refs/heads/diag" in text and "git push" in text:
            hits.append((key, stage, text, lines))
    assert hits, (
        "全仓找不到了 `HEAD:refs/heads/diag` 的诊断回推：不许用删段让上一条判据变绿（失败诊断归档还要能回推证据）")
    bad = []
    for key, stage, text, lines in hits:
        if "GIT_ASKPASS" not in text and "askpass" not in text:
            bad.append("%s / %s：diag 回推没走 GIT_ASKPASS" % (key, stage.get("name")))
    assert not bad, "诊断回推凭据形状不合规：%s" % bad
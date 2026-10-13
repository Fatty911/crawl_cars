"""断点回推不许把 `__pycache__/*.pyc` 带进提交（判据，当前 main 上必须红）。

**实测链条（监工 10-13 22:56 +08:00 从 `cnb-k02-1k4oc66pl` 的阶段日志原文定位）**：
那一轮的 `AI-修复-第1轮` **跑成功了的**（`success(72.7m)`），但紧接着
`验证-实际pytest及Node和语法 = error(7.2s)`，原文最后一行：

    repair blocked: PROTECTED_OR_UNAPPROVED_CHANGE: crawl_state/__pycache__/__init__.cpython-312.pyc,
    crawl_state/__pycache__/registry.cpython-312.pyc, …
    Finished, code: 1, duration: 7.1s

⇒ 后续 `NPC审核前免费额度复查` / `审查-GLM只读交叉评审` / `最终门禁` **三段全部 skipped**：
一次修复成功被两个字节级垃圾文件废掉，而且是**每轮都会重演**的形状。

**成因是两行配置的合谋，不是 NPC 乱提交**：
1. `.cnb.yml:589`（两条链各一份）：`[ -d crawl_state ] && git add -f crawl_state || true`
   —— `__pycache__/` 虽然在 `.gitignore:5` 里，但 **`-f` 会无视 .gitignore**；
2. `origin/main` 上现在确实跟踪着 `crawl_state/__pycache__/__init__.cpython-312.pyc` 与
   `crawl_state/__pycache__/registry.cpython-312.pyc`（`11c10bb` 那次一起进的仓）。

**两条红线（本判据都钉）**：
- 加了排除**不算修好**，如果排除把断点本身也排掉了 ⇒ `回推增量状态` 必须仍然 `git add -f crawl_state`；
- 只改一份链拷贝不算修好 ⇒ 判据按内容认链、逐条点名。
"""

from __future__ import annotations

import pathlib
import re

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
CFG = yaml.safe_load((ROOT / ".cnb.yml").read_text(encoding="utf-8")) or {}
MAIN = CFG.get("main") or {}

PUSHBACK = "回推增量状态"
PYC_PATTERNS = ("__pycache__", "*.pyc", ".pyc")


def _pushback_stages():
    out = []
    for key, val in MAIN.items():
        for job in (val if isinstance(val, list) else [val]):
            if not isinstance(job, dict):
                continue
            for bucket in ("stages", "failStages"):
                for s in (job.get(bucket) or []):
                    if isinstance(s, dict) and PUSHBACK in str(s.get("name") or ""):
                        out.append((str(key), s))
    return out


def _live(stage) -> list:
    b = stage.get("script")
    if isinstance(b, dict):
        b = b.get("run") or ""
    elif isinstance(b, list):
        b = "\n".join(str(x) for x in b)
    return [l for l in str(b or "").splitlines() if not l.strip().startswith("#")]


def test_pushback_stages_are_discovered_in_both_copies():
    got = _pushback_stages()
    assert got, "一条含 %r 的阶段都没认出来：解析退化 ≠ 没跑，禁止据此判绿" % PUSHBACK
    chains = {k for k, _ in got}
    assert len(chains) >= 2, (
        "只认出 %d 份回推阶段（%s）：本仓爬虫链至少两份拷贝，只改一份是半修" % (len(chains), sorted(chains)))


def test_pushback_excludes_pycache_from_the_commit():
    """排除必须真的写在**有效行**里（注释里提一句不算），且不能把断点本身排除掉。"""
    offenders = []
    for key, stage in _pushback_stages():
        lines = _live(stage)
        text = "\n".join(lines)
        if "git add -f crawl_state" not in text:
            offenders.append("%s：回推段不再 `git add -f crawl_state` ⇒ 断点永不回灌（这是拆功能不是修排除）" % key)
            continue
        hit = [l for l in lines if any(p in l for p in PYC_PATTERNS)]
        if not hit:
            offenders.append("%s：`git add -f crawl_state` 会无视 .gitignore 把 __pycache__/*.pyc 一并提交，"
                             "但段内没有任何排除 pyc 的有效行" % key)
            continue
        bad = [l.strip()[:70] for l in hit
               if re.search(r"git\s+(add|reset|rm)[^\n]*crawl_state(?:\s|$)[^\n]*\b(--all|-A)\b", l)]
        if bad:
            offenders.append("%s：排除写法把整个 crawl_state 一起排掉了：%s" % (key, bad))
    assert not offenders, "回推阶段的 pyc 排除不合规：%s" % offenders


def test_repo_does_not_track_pyc_files():
    """效果级断言：签出树里不该有被跟踪的 `crawl_state/**/*.pyc`（CI 克隆 = 已跟踪文件才会出现）。"""
    cs = ROOT / "crawl_state"
    if not cs.exists():
        assert False, "crawl_state 目录不见了：断点面读不到，不许当通过"
        return
    pycs = sorted(str(p.relative_to(ROOT)) for p in cs.rglob("*.pyc"))
    assert not pycs, (
        "仓库里仍跟踪着 pyc：%s ⇒ 修复链每次都会被 finalize 门禁判 PROTECTED_OR_UNAPPROVED_CHANGE，"
        "连带跳过额度复查/GLM 评审/最终门禁（实测 cnb-k02：修复 success(72.7m) 仍被这两个文件废掉）" % pycs[:4])


def test_guard_message_would_still_be_reachable_if_pyc_returns():
    """自校：如果 pyc 又出现，第三条必须能抓到（不是永远绿的空判据）。"""
    probe = ROOT / "crawl_state" / "__pycache__" / "_oracle_probe_dummy.pyc"
    probe.parent.mkdir(parents=True, exist_ok=True)
    created = not probe.exists()
    try:
        probe.write_bytes(b"\x00probe")
        found = sorted(str(p) for p in (ROOT / "crawl_state").rglob("*.pyc"))
        assert found, "写入探针后 rglob 仍读不到 ⇒ 本判据的探测面坏了（宁可判崩）"
    finally:
        if created:
            probe.unlink()
            if not any(probe.parent.iterdir()):
                probe.parent.rmdir()

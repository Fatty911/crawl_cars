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
import subprocess
import re

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
CFG = yaml.safe_load((ROOT / ".cnb.yml").read_text(encoding="utf-8")) or {}
MAIN = CFG.get("main") or {}

PUSHBACK = "回推增量状态"
PYC_PATTERNS = ("__pycache__", "*.pyc", ".pyc")




def _tracked_pyc():
    """git 索引里 crawl_state 下的 .pyc（测量面=跟踪状态，不是磁盘存在性）。"""
    return _tracked_under("crawl_state/", "*.pyc")


def _tracked_under(prefix, pattern=""):
    cmd = ["git", "-C", str(ROOT), "ls-files", "-z"]
    if pattern:
        cmd.append("%s/%s" % (prefix.rstrip("/"), pattern))
    else:
        cmd.append(prefix)
    try:
        out = subprocess.run(cmd, capture_output=True, timeout=60)
    except Exception:  # noqa: BLE001 - 读不到就判『读不到』
        return None
    if out.returncode != 0:
        return None
    raw = out.stdout.decode("utf-8", "replace")
    return [x for x in raw.split("\0") if x.strip()]

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
    """效果级断言：**git 索引里**不该有 `crawl_state/**/*.pyc`。

    测量面必须选对（10-14 的教训）：早先这一条用 `Path.rglob("*.pyc")` 查**工作区**，
    而工作区里 pyc 本来就会重生（`tests/test_dcd_provider_identity.py` 等会 import
    `crawl_state.registry`），于是"磁盘上有 pyc"与"仓库跟踪着 pyc"被混成一件事 ⇒
    这条判据在全量 pytest 里**必红**（实测 #64 工作树：`11 failed` vs main `10 failed`，
    新增的那一条就是它），合进去只会把 push CI 弄红，不是修好。
    ⇒ 正确测量面是 git 索引：`git ls-files`（CI 克隆里出现的正是被跟踪的文件）。
    """
    tracked = _tracked_pyc()
    assert tracked is not None, "读不到 git 索引 ⇒ 判『读不到』，不许当通过"
    assert not tracked, (
        "仓库仍跟踪着 pyc：%s ⇒ 修复链每次都会被 finalize 门禁判 PROTECTED_OR_UNAPPROVED_CHANGE，"
        "连带跳过额度复查/GLM 评审/最终门禁（实测 cnb-k02：修复 success(72.7m) 仍被这两个文件废掉）"
        % tracked[:4])


def test_the_sieve_can_actually_see_tracked_files():
    """自校两条，防"空集是因为筛子坏了"和"测量面又滑回工作区"：

    1. 同一个 `git ls-files` 查询必须能筛到 `crawl_state/` 下的**其他**被跟踪文件
       （读不到任何跟踪文件 ⇒ 索引查询本身失效，判红而不是判绿）；
    2. 在 `crawl_state/__pycache__/` 里造一个 dummy `.pyc` 后，
       **索引**读数必须不变（证明我们量的是跟踪状态，不是磁盘存在性）。
    """
    others = _tracked_under("crawl_state/")
    assert others is not None and len(others) > 0, (
        "`git ls-files crawl_state/` 一个文件都没返回 ⇒ 索引查询坏了，"
        "此时第一条的『空集』不代表没有 pyc 被跟踪（存在性≠状态，筛子坏了也算读不到）")
    before = _tracked_pyc()
    probe = ROOT / "crawl_state" / "__pycache__" / "_oracle_probe_dummy.pyc"
    probe.parent.mkdir(parents=True, exist_ok=True)
    existed = probe.exists()
    try:
        probe.write_bytes(b"\x00dummy")
        after = _tracked_pyc()
        assert after == before, (
            "写入磁盘上的 dummy pyc 后索引读数从 %s 变成 %s ⇒ 测量面又滑回工作区了" % (before, after))
        assert any("crawl_state" in o for o in others), "跟踪文件读数与 crawl_state 无关 ⇒ 筛子选错了面"
    finally:
        if not existed:
            try:
                probe.unlink()
            except OSError:
                pass

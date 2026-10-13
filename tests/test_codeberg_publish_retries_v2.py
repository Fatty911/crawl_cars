"""Codeberg 发布：**每一条会抖动的网络命令**都要在重试结构里（v2，逐循环体校验）。

为什么有 v2（PR #51 的 GLM 只读交叉评审实测抓出来的，不是推断）：
  证据链里的失败原文是
      curl: (35) TLS connect error: error:0A000126:SSL routines::unexpected eof while reading
      Finished, code: 35, duration: 15.6s
  即**抖动命中的是 `curl --fail ... --connect-timeout 20` 那条连通性预检**，它在 `git push` 之前、
  且 stage 顶上有 `set -e`（非零直接终止整个阶段）。v1 判据只要求"stage 文本里存在循环 + sleep"，
  NPC 于是只把 `git push` 包进重试 —— **判据全绿，但复现路径原封不动**。
  v1 还被实测出弱断言：把重试块里的 `exit 1` 删掉后判据仍绿（检测不到「响亮失败」被拿掉）。

v2 的口径（按循环体逐个查，不是全文搜关键字）：
  A. `curl --fail`（连通性预检）必须落在某个循环体内，且该循环体内有退避（sleep）与耗尽后的 exit 1；
  B. `git push`（发布动作）同样必须落在某个循环体内，且该循环体内有退避与 exit 1；
  C. 任何一处都不许用 `|| true` / `|| exit 0` 把失败吃成成功。
"""

from __future__ import annotations

import pathlib
import re

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
CFG = yaml.safe_load((ROOT / ".cnb.yml").read_text(encoding="utf-8"))
STAGE_WORDS = ("发布到Codeberg", "Codeberg")
MIN_LOOPS = 2  # 预检一条 + 发布一条，各一个循环；少于它就是"只改了一份"


def _jobs():
    for key, val in ((CFG.get("main") or {}).items()):
        for j in (val if isinstance(val, list) else [val]):
            if isinstance(j, dict):
                yield key, j


def _stage_text(job) -> str:
    out = []
    for section in ("stages", "failStages"):
        for s in (job.get(section) or []):
            if not isinstance(s, dict) or not any(w in str(s.get("name") or "") for w in STAGE_WORDS):
                continue
            b = s.get("script")
            if isinstance(b, dict):
                b = b.get("run") or ""
            elif isinstance(b, list):
                b = "\n".join(str(x) for x in b)
            out.append(str(b or ""))
    return "\n".join(out)


def _loop_bodies(lines: list) -> list:
    """返回每个 while/for 循环体的行区间 [(start, end)]（end 为 done 所在行）。"""
    ranges, stack = [], []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if re.match(r"(while|for)\b", stripped) and stripped.endswith("do"):
            stack.append(i)
        elif stripped == "done" and stack:
            ranges.append((stack.pop(), i))
    return ranges


def _body(lines: list, start: int, end: int) -> str:
    return "\n".join(lines[start + 1:end])


def test_codeberg_stage_exists_and_is_readable() -> None:
    found = [(k, _stage_text(j)) for k, j in _jobs() if _stage_text(j)]
    assert found, "在 .cnb.yml 里认不到任何含 %r 的阶段脚本（结构解析退化？）" % STAGE_WORDS[0]
    for key, text in found:
        assert len(text) > 80, "链 %r 的 Codeberg 阶段脚本只读到 %d 字 ⇒ 判『读不到』" % (key, len(text))


def test_every_flaky_network_command_is_inside_a_retry_loop() -> None:
    """A+B：curl 预检与 git push 必须各自在某个循环体内，且体内有 sleep 与 exit 1。"""
    offenders = []
    for key, job in _jobs():
        text = _stage_text(job)
        if not text:
            continue
        lines = text.splitlines()
        loops = _loop_bodies(lines)
        if len(loops) < MIN_LOOPS:
            offenders.append("%s：循环体只有 %d 个（<%d）⇒ 预检/发布里至少有一条没进重试"
                             % (key, len(loops), MIN_LOOPS))
        for token, label in ((r"curl[^\n]*--fail", "连通性预检 curl --fail"),
                             (r"git push", "发布 git push")):
            inside = [rg for rg in loops if re.search(token, _body(lines, *rg))]
            if not inside:
                offenders.append("%s：%s 不在任何循环体内（抖动命中它就直接终止阶段）" % (key, label))
                continue
            for start, end in inside:
                body = _body(lines, start, end)
                if not re.search(r"sleep\s+[\"']?[\d$(]", body):
                    offenders.append("%s：%s 所在的循环体内没有退避 sleep" % (key, label))
                if not re.search(r"exit\s+1", body):
                    offenders.append("%s：%s 所在的循环体内没有耗尽后的 exit 1（静默吞失败的同款形状）" % (key, label))
    assert not offenders, (
        "Codeberg 经代理时 TLS 握手会偶发被打断（实测 code 35），每条会抖动的网络命令都要各自进重试"
        "（退避 + 耗尽仍 exit 1）；只在 git push 上加重试、把 curl 预检留在循环外 = 半修。%s" % offenders)


def test_retry_exhaustion_still_fails_loudly() -> None:
    """C：不许把失败吃成成功（v1 的这条被实测可绕过，v2 由上面的逐循环检查覆盖，这里再兜底全文）。"""
    bad = []
    for key, job in _jobs():
        text = _stage_text(job)
        if not text:
            continue
        live = "\n".join(l for l in text.splitlines() if not l.strip().startswith("#"))
        if re.search(r"(curl|git push)[^\n]*\|\|\s*(true|exit 0)", live):
            bad.append("%s：失败被 || true/|| exit 0 吃掉" % key)
    assert not bad, "重试不许拿掉原有防护（放宽保护前必须证明兜底还在）：%s" % bad

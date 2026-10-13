"""断点回推不许被上游发布失败连带跳过（Issue #4 那类缺陷的验收判据，自包含、可证伪）。

现网事实（监工在 origin/main=65b80f8 上数出来的，不是推断）：
  api_trigger 与半月 crontab 两条爬虫链的阶段顺序里，
  `回推增量状态` 排在**最后一格（index 20）**，而它前面有 12 个会失败的阶段
  （`发布到Cloudflare Pages`、`发布到Codeberg Pages`、`线上验收` 等）。
  CNB 的语义是"某阶段 error ⇒ 后续阶段不再执行"，所以只要发布或验收红一次，
  这一轮的 `crawl_state/` 断点就**从不回灌 main** —— 这正是易车覆盖倒退三条独立成因里的第一条，
  而且它会自我锁死：断点不回灌 ⇒ 下一轮又从头爬 ⇒ 又撞发布失败。

判据断言的是**结构可达性**，不是发布成功率：
  `回推增量状态` 要么排在任何"发布会变红的阶段"**之前**，
  要么被写进该 job 的 `failStages`（失败也要执行）。两种形状都算修好。

现网必须红；上面两种形状任一实现后必须绿。
"""

from __future__ import annotations

import pathlib
import re

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
CFG = yaml.safe_load((ROOT / ".cnb.yml").read_text(encoding="utf-8"))

PUSHBACK = "回推增量状态"
# 这些阶段都会因外部依赖（CF/Codeberg/GitHub/线上站点）而变红
FALLIBLE_PUBLISH_WORDS = ("发布到", "线上验收", "推送数据到")
MIN_STAGES = 18  # 反退化：解析不出这么多阶段就是"读不到"，不许当通过


def _crawler_jobs() -> list[tuple[str, dict]]:
    """从被解析的数据里认链，别写死键名（crontab 的键带表达式）。"""
    out = []
    for key, val in ((CFG.get("main") or {}).items()):
        jobs = val if isinstance(val, list) else [val]
        for j in jobs:
            if not isinstance(j, dict):
                continue
            stages = [s for s in (j.get("stages") or []) if isinstance(s, dict)]
            if any(PUSHBACK in str(s.get("name") or "") for s in stages):
                out.append((str(key), j))
    return out


def _script(stage: dict) -> str:
    b = stage.get("script")
    if isinstance(b, dict):
        b = b.get("run") or ""
    elif isinstance(b, list):
        b = "\n".join(str(x) for x in b)
    return str(b or "")


def test_crawler_chains_are_discovered_not_assumed() -> None:
    jobs = _crawler_jobs()
    assert jobs, (
        "一条含 %r 的爬虫链都没认出来：解析退化或链被拆，这种读数不许当通过（宁可判崩）；"
        "实际认到的 main 键：%s" % (PUSHBACK, list((CFG.get("main") or {}).keys()))
    )
    for key, job in jobs:
        stages = [s for s in (job.get("stages") or []) if isinstance(s, dict)]
        assert len(stages) >= MIN_STAGES, (
            "链 %r 只认出 %d 个阶段（<%d）：阶段集为空/读不到 ≠ 没跑，禁止据此判绿" % (key, len(stages), MIN_STAGES)
        )


def test_pushback_is_reachable_when_publish_fails() -> None:
    offenders = []
    for key, job in _crawler_jobs():
        names = [str(s.get("name") or "") for s in (job.get("stages") or []) if isinstance(s, dict)]
        pb = [i for i, n in enumerate(names) if PUSHBACK in n]
        assert pb, "链 %r 认到了 %r 却没有可索引的阶段（不可能，属读数故障）" % (key, PUSHBACK)
        first_bad = [i for i, n in enumerate(names) if any(w in n for w in FALLIBLE_PUBLISH_WORDS)]
        fail_names = [str(s.get("name") or "") for s in (job.get("failStages") or []) if isinstance(s, dict)]
        in_fail = any(PUSHBACK in n for n in fail_names)
        if first_bad and min(pb) > min(first_bad) and not in_fail:
            offenders.append(
                "%s：回推排在 index %d，晚于会变红的 %r（index %d），且不在 failStages（%s）"
                % (key, min(pb), names[min(first_bad)], min(first_bad), fail_names[:3]))
    assert not offenders, (
        "上游任一发布/验收阶段变红就会连带跳过断点回推 ⇒ crawl_state 断点从不回灌（自我锁死）。"
        "两种合规形状任选：把 %r 移到发布会变红的阶段之前，或把它写进该 job 的 failStages。新增红：%s"
        % (PUSHBACK, offenders))


def test_pushback_actually_pushes_checkpoint_files() -> None:
    """防空壳：把回推"提前"不能靠搬一个不做实事的阶段，脚本必须真的推 crawl_state。"""
    bad = []
    for key, job in _crawler_jobs():
        for s in (job.get("stages") or []):
            if not isinstance(s, dict) or PUSHBACK not in str(s.get("name") or ""):
                continue
            live = "\n".join(l for l in _script(s).splitlines() if not l.strip().startswith("#"))
            if "git push" not in live or "crawl_state" not in live:
                bad.append("%s：%s 的脚本没有同时出现 git push 与 crawl_state" % (key, s.get("name")))
            if re.search(r"git\s+push[^\n]*\|\|\s*(true|exit 0)", live):
                bad.append("%s：回推被 `|| true`/`|| exit 0` 吃成成功（静默失败）" % key)
    assert not bad, "回推阶段不做实事或静默失败，等于没回灌：%s" % bad


def test_pushback_does_not_put_token_in_the_url() -> None:
    """回推不许把令牌拼进 URL（本仓安全规则：凭据只走 GIT_ASKPASS/临时配置，不入 URL/进程表）。

    现网实测：`回推增量状态` 的脚本里写着
    `git push "https://${CNB_TOKEN_USER_NAME:-cnb}:${CNB_TOKEN}@cnb.cool/…"`
    ⇒ 令牌进 URL ⇒ 进进程表、进公开构建日志（本仓已发生过一次凭据外泄）。
    合规形状同链已有先例：`推送代码到GitLab` 就是 `GIT_ASKPASS` + `git push gitlab …`。
    """
    offenders = []
    for key, job in _crawler_jobs():
        for s in (job.get("stages") or []):
            if not isinstance(s, dict) or PUSHBACK not in str(s.get("name") or ""):
                continue
            live = "\n".join(l for l in _script(s).splitlines() if not l.strip().startswith("#"))
            if ":${CNB_TOKEN}@" in live or "CNB_TOKEN}@" in live:
                offenders.append("%s：%s 把令牌拼进了 push URL" % (key, s.get("name")))
            elif "GIT_ASKPASS" not in live and "askpass" not in live:
                offenders.append("%s：%s 没有走 GIT_ASKPASS（改 URL 不算修好）" % (key, s.get("name")))
    assert not offenders, "凭据面违规：%s" % offenders

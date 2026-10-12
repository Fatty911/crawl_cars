"""流水线自己写的提交不许绕过 push CI（判据，当前必须红）。

现网事实（10-12 在 origin/main 上实测，四类提交点全中）：

    .cnb.yml:579    git commit -m "chore: 半月增量爬取+发布 [skip ci]"      # api_trigger 链的回推
    .cnb.yml:1181   git commit -m "chore: 半月增量爬取+发布 [skip ci]"      # crontab 链的同一段拷贝
    .cnb.yml:1346   git commit -m "chore: 报价链失败诊断 [skip ci]"          # 报价独立链
    scripts/finalize_npc_repair.py:207  "-m", "fix: reviewed CNB NPC repair [skip ci]"

后果有读数：`11c10bb`（411 个文件、把 `crawl_state/yiche_frontier.json`、400+ HTML 快照与
`__pycache__/*.pyc` 一起提交进仓库）触发的 `cnb-qen-1k4mbirjn` 判**假绿**——
`install-deps / 推送代码到GitLab / pytest / 语法校验 / 治理校验` 五个实质阶段**一个都没执行**。
`4fba1ac` 那条 NPC 自修复提交同形。⇒ 只要提交信息里带 `[skip ci]`，
本仓所有质量闸（真跑 pytest、语法校验、治理校验）对流水线自己写的东西全部失效。

口径：断的是"类别"（四个点都要覆盖）与"闸不会被消息内容关掉"，不是某一行文案。
"""

from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
CNB_YML = (ROOT / ".cnb.yml").read_text(encoding="utf-8").replace("\r", "")
COMMIT_SITES = [
    (ROOT / "scripts" / "finalize_npc_repair.py"),
    (ROOT / "scripts" / "prepare_cnb_pages.py"),
    (ROOT / "scripts" / "publish_github_release.py"),
    (ROOT / "scripts" / "preserve_publish_baseline.py"),
]

# `git commit` 的命令行/参数里把 [skip ci] 塞进 -m 的写法
SKIP_IN_COMMIT = re.compile(r"git\s+commit[^\n]*\[skip ci\]|\"[^\"]*\[skip ci\][^\"]*\"|'-[^']*\[skip ci\][^']*'")


def test_cnb_yml_never_writes_skip_ci_into_its_own_commits():
    hits = [ln for ln in CNB_YML.splitlines() if "git commit" in ln and "[skip ci]" in ln]
    assert not hits, (
        ".cnb.yml 里 %d 处回推/诊断提交自带 [skip ci]，使 push CI 的 pytest/语法/治理校验对流水线自己写的"
        "提交永不执行（实测 cnb-qen 判假绿）：%s" % (len(hits), [h.strip()[:80] for h in hits][:4])
    )


def test_pipeline_scripts_never_write_skip_ci():
    bad = []
    for path in COMMIT_SITES:
        if not path.exists():
            continue
        for i, ln in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "[skip ci]" in ln and ("commit" in ln or "-m" in ln):
                bad.append("%s:%d %s" % (path.name, i, ln.strip()[:90]))
    assert not bad, "脚本把 [skip ci] 写进提交信息，等于自断门禁：%s" % bad[:4]


def test_all_duplicate_commit_sites_are_fixed_together():
    """`.cnb.yml` 的回推段有两份拷贝：只改一份就是半修（第二份在 crontab 链上照样带 [skip ci]）。"""
    occurrences = len(re.findall(r"\[skip ci\]", CNB_YML))
    assert occurrences == 0, (
        "`.cnb.yml` 里仍有 %d 处 [skip ci]（api_trigger 与 crontab 两段拷贝要一起改，"
        "只改一份的话半月链照样绕过 CI）" % occurrences
    )


def test_push_ci_stages_are_unconditional():
    """实质阶段不许被 `if:` 关掉——否则去掉 [skip ci] 也只是换了一种假绿。"""
    for stage in ("pytest", "语法校验", "治理校验"):
        idx = CNB_YML.find("name: " + stage)
        assert idx >= 0, "push 链缺少实质阶段 %s" % stage
        block = CNB_YML[idx:idx + 400]
        head = block.split("script:")[0]
        assert "if:" not in head, "阶段 %s 被 if: 条件守卫，可能整轮不执行（假绿）" % stage

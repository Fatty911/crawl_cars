"""回推「体积闸 + 白名单」的回归测试。

为什么需要这道闸（实测 2026-10-09）：
`data/` 里已跟踪了 8.4MB 的 dongchedi_20260302.json、8.1MB 的 merged_20260622.json
等历史产物。`.gitignore` 里虽然写了 `data/merged_*.json`，但
**对已跟踪文件无效**（Git 基本行为），于是每轮 `git add data` 都会把它们重新提交，
仓库体积不可逆地膨胀。

测试守三件事：
1. 回推 stage 用**显式白名单**而不是 `git add data`；
2. 白名单里不包含任何已知的 MB 级历史产物；
3. 体积闸真的能撤出大文件（用临时 git 仓库做真实 git 行为验证）。
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
Cnb = ROOT / ".cnb.yml"

SIZE_LIMIT = 5 * 1024 * 1024  # 与 .cnb.yml 里的 5242880 保持一致


def pushback_scripts() -> list[tuple[str, str]]:
    """取出所有「回推增量状态」stage 的 script（api_trigger 与半月 crontab 各一份）。"""
    main = (yaml.safe_load(Cnb.read_text(encoding="utf-8")) or {})["main"]
    out = []
    for key, job in main.items():
        if not isinstance(job, list) or not job or not isinstance(job[0], dict):
            continue
        for stage in job[0].get("stages") or []:
            if stage.get("name") == "回推增量状态":
                out.append((str(key), stage.get("script") or ""))
    return out


class PushbackWhitelistTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scripts = pushback_scripts()
        if not self.scripts:
            self.skipTest("未找到回推增量状态 stage")

    def test_pushback_stage_exists(self) -> None:
        self.assertGreaterEqual(len(self.scripts), 2, "回推 stage 应在两个 job 里各有一份")

    def test_uses_whitelist_not_whole_data_dir(self) -> None:
        for key, script in self.scripts:
            with self.subTest(job=key):
                self.assertNotIn(
                    'git add "$d"',
                    script,
                    "回推不得整目录 git add data（已跟踪的 MB 级历史产物会被反复提交）",
                )
                self.assertNotIn(
                    'for d in crawl_state docs/analysis data',
                    script,
                    "回推不得用整目录循环 add data",
                )

    def test_whitelist_only_contains_small_artifacts(self) -> None:
        # 白名单允许出现的具体文件（报价 / 断点 / 报告）
        allowed = {
            "data/dealer_prices.json",
            "data/progress.json",
            "data/dongchedi_series_list.json",
            "data/proxies.json",
            "crawl_state",
            "docs/analysis",
            "pages-audit-report.json",
        }
        for key, script in self.scripts:
            with self.subTest(job=key):
                # 提取所有 git add -f <path> 的参数
                import re
                added = set(re.findall(r"git add -f (\S+)", script))
                self.assertTrue(added, "白名单为空，回推会退化成整目录 add")
                unexpected = {
                    p for p in added
                    if p not in allowed and p.rstrip("/") not in allowed
                }
                self.assertEqual(
                    unexpected, set(),
                    f"白名单出现未授权条目：{unexpected}",
                )

    def test_size_gate_present(self) -> None:
        for key, script in self.scripts:
            with self.subTest(job=key):
                self.assertIn("5242880", script, "缺少 5MB 体积闸阈值")
                self.assertIn("git reset", script, "体积闸必须能把大文件撤出暂存区")


class SizeGateBehaviourTests(unittest.TestCase):
    """用真实 git 仓库验证体积闸的行为，不只检查脚本里有没有那句话。"""

    def setUp(self) -> None:
        if not shutil.which("git"):
            self.skipTest("无 git")
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args], cwd=self.tmp, capture_output=True,
            text=True, encoding="utf-8", errors="replace",
        )

    def test_gate_withdraws_large_file_keeps_small_one(self) -> None:
        self._run("init", "-q")
        self._run("config", "user.email", "t@t")
        self._run("config", "user.name", "t")

        data = self.tmp / "data"
        data.mkdir()
        small = data / "dealer_prices.json"
        small.write_text(json.dumps({"series": {}}, ensure_ascii=False), encoding="utf-8")
        big = data / "big.json"
        big.write_text("x" * (SIZE_LIMIT + 1024), encoding="utf-8")

        self._run("add", "-f", "data/dealer_prices.json", "data/big.json")

        # 与 .cnb.yml 里体积闸等价的逻辑
        import re

        listed = self._run("diff", "--cached", "--name-only").stdout.split()
        big_files = []
        for rel in listed:
            p = self.tmp / rel
            if p.is_file() and p.stat().st_size > SIZE_LIMIT:
                big_files.append(rel)
        for rel in big_files:
            self._run("reset", "-q", "HEAD", "--", rel)

        remaining = set(self._run("diff", "--cached", "--name-only").stdout.split())
        self.assertIn("data/dealer_prices.json", remaining)
        self.assertNotIn("data/big.json", remaining)

    def test_gitignore_does_not_untrack_already_tracked_files(self) -> None:
        # 记录一个反直觉但关键的 Git 行为：.gitignore 对已跟踪文件无效。
        # 这正是原回推 stage 会反复提交 MB 级文件的原因。
        self._run("init", "-q")
        self._run("config", "user.email", "t@t")
        self._run("config", "user.name", "t")
        f = self.tmp / "big.json"
        f.write_text("{}", encoding="utf-8")
        self._run("add", "-f", "big.json")
        self._run("commit", "-q", "-m", "init")

        (self.tmp / ".gitignore").write_text("big.json\n", encoding="utf-8")
        f.write_text('{"changed": true}', encoding="utf-8")
        self._run("add", "-A")

        staged = self._run("diff", "--cached", "--name-only").stdout.split()
        self.assertIn(
            "big.json", staged,
            "已跟踪文件不受 .gitignore 约束 —— 这就是必须用白名单+体积闸的原因",
        )


if __name__ == "__main__":
    unittest.main()
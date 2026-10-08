"""cars 爬取预算分配器的回归测试。

背景：CNB 流水线有 120min硬上限，超时整条构建被杀，Pages 停在上一轮日期。
GitHub Actions 时代各源 `--time-limit` 各自独立，相加远超 CNB 上限，
于是「每源留足预算」等于「每源都被腰斩」。`allocate_crawl_budget.py` 的职责
就是把这个总额切开，并保证切出来的和恒≤ 可用预算。

这里守住的护栏有三条，都不是「测试实现细节」而是发布语义：
1. 各步预算之和不得超过可用预算（否则重演120min 被杀）。
2. 已耗时必须从预算里扣掉（分母不能是常量 120min）。
3. 发布阶段的固定开销必须先扣（否则爬取把合并阶段的时间吃光，
   数据抓到了却发不出去，Pages 照样不更新）。

外加两条 debug 语义：
4. DEBUG_MODE 下走独立固定小预算，且真的限量（时间 + 车系数/步数），
   否则 debug 又变成「名义上的debug、实际上的全量」。
5. 限量必须是确定性前缀而非随机采样，否则跨轮数据无法对齐。
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
ALLOCATOR = SCRIPTS / "allocate_crawl_budget.py"
DEALER = SCRIPTS / "crawl_dealer_prices.py"
CRAWL_WORKFLOW = ROOT / ".cnb.yml"


def load_allocator():
    spec = importlib.util.spec_from_file_location("allocate_crawl_budget", ALLOCATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {ALLOCATOR}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AllocatorGuardTests(unittest.TestCase):
    """护栏：预算分配本身不能把构建送进 120min 死线。"""

    def setUp(self) -> None:
        self.mod = load_allocator()

    def test_weights_sum_matches_declared_total(self) -> None:
        # 权重漂移会让预算口径与文档不符，必须在import 期就炸（脚本内有断言），
        # 这里再从外部确认一次「守卫真的在」，而不是恰好通过。
        self.assertEqual(sum(self.mod.STEP_WEIGHTS.values()), self.mod.WEIGHT_TOTAL)

    def test_allocation_never_exceeds_available_budget(self) -> None:
        # 核心护栏：切出来的和必须 ≤ 可用预算。
        for elapsed in (0, 600, 1800, 3000, 5000):
            available = self.mod._resolve_total_seconds(None, elapsed)
            budgets = self.mod.allocate(None, elapsed, debug=False)
            self.assertLessEqual(
                sum(budgets.values()),
                available,
                f"elapsed={elapsed} 各步之和 {sum(budgets.values())} 超出可用预算 {available}",
            )

    def test_available_budget_shrinks_with_elapsed_time(self) -> None:
        # 已耗时必须真扣：晚启动的轮次拿到的总预算必须更少，
        # 否则「按 120min 固定分预算」会在后半程把合并阶段挤爆。
        base = self.mod._resolve_total_seconds(None, 0)
        later = self.mod._resolve_total_seconds(None, 1800)
        self.assertEqual(base - later, 1800)

    def test_publish_phase_reserve_is_deducted_first(self) -> None:
        # 总额里必须预留合并/发布/回推的时间。
        self.assertEqual(
            self.mod._resolve_total_seconds(self.mod.PIPELINE_LIMIT_SECONDS, 0),
            self.mod.PIPELINE_LIMIT_SECONDS - self.mod.PUBLISH_PHASE_RESERVE_SECONDS,
        )

    def test_every_crawl_source_gets_a_budget_slot(self) -> None:
        # 基础属性的四个吃预算的步都必须有槽位；漏一个就意味着那个源退回无界
        # （= 超时元凶）。经销商报价不在此列：它已拆成独立链路，自带 time-limit。
        for step in ("autohome_step1", "dongchedi_step1", "dongchedi_step2", "yiche"):
            self.assertIn(step, self.mod.STEP_WEIGHTS, f"{step} 没有预算槽位")
            budgets = self.mod.allocate(None, 0, debug=False)
            self.assertGreater(budgets[step], 0, f"{step} 预算为 0")

    def test_malformed_weights_do_not_inflate_budget(self) -> None:
        # 权重被改成总和 1500 时，除数必须是实际权重和而不是声明的 1000，
        # 否则每一步都会被放大 1.5 倍——恰好制造它本该防的超预算。
        original = self.mod.STEP_WEIGHTS
        self.mod.STEP_WEIGHTS = {name: 300 for name in original}
        try:
            available = self.mod._resolve_total_seconds(None, 0)
            budgets = self.mod.allocate(None, 0, debug=False)
            self.assertLessEqual(sum(budgets.values()), available)
        finally:
            self.mod.STEP_WEIGHTS = original

    def test_budget_never_drops_to_zero(self) -> None:
        # 已经超时耗尽预算时，各步仍保底：给 0 会让爬虫「秒退」并零产出，
        # 合并阶段直接失败；保底 120s 至少留一个车系的机会。
        budgets = self.mod.allocate(None, 99999, debug=False)
        for step, seconds in budgets.items():
            self.assertGreaterEqual(seconds, self.mod.MIN_STEP_SECONDS, f"{step} 跌破下限")


class DebugModeTests(unittest.TestCase):
    """DEBUG_MODE 必须真的 debug，否则又是一次名义小批量、实际全量。"""

    def setUp(self) -> None:
        self.mod = load_allocator()

    def test_debug_uses_fixed_small_budget(self) -> None:
        budgets = self.mod.allocate(None, 0, debug=True)
        for step, seconds in budgets.items():
            self.assertEqual(seconds, self.mod.DEBUG_STEP_SECONDS, f"{step} 未走 debug 固定预算")
        self.assertLess(
            sum(budgets.values()),
            sum(self.mod.allocate(None, 0, debug=False).values()),
            "debug 预算不应高于生产预算",
        )

    def test_debug_flag_reads_environment_when_not_explicit(self) -> None:
        # 不传 --debug-mode 时必须读环境变量，否则 API 触发的 DEBUG_MODE=true 到不了分配器。
        import os

        previous = os.environ.get("DEBUG_MODE")
        os.environ["DEBUG_MODE"] = "true"
        try:
            self.assertTrue(self.mod._is_debug(None))
        finally:
            if previous is None:
                os.environ.pop("DEBUG_MODE", None)
            else:
                os.environ["DEBUG_MODE"] = previous

    def test_explicit_debug_flag_overrides_environment(self) -> None:
        import os

        os.environ["DEBUG_MODE"] = "false"
        try:
            self.assertTrue(self.mod._is_debug("true"))
            self.assertFalse(self.mod._is_debug("false"))
        finally:
            os.environ.pop("DEBUG_MODE", None)


class EmittedEnvTests(unittest.TestCase):
    """env 文件是 stage 之间唯一的传参通道，格式必须 shell 可 source。"""

    def setUp(self) -> None:
        self.mod = load_allocator()

    def test_emitted_env_is_shell_sourceable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "budget.env"
            budgets = self.mod.allocate(None, 0, debug=False)
            self.mod.emit_env(str(out), budgets, debug=False, available=5820)

            # 真用 sh 去 source，验证语法（而不是自己 split() 假装能读）。
            # 必须转成 POSIX 路径：Windows 的反斜杠会被 sh 当转义符吃掉。
            posix = out.as_posix()
            result = subprocess.run(
                ["sh", "-c",
                 f". {posix} && echo $AUTOHOME_STEP1_TIME_LIMIT $DONGCHEDI_STEP2_TIME_LIMIT"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                result.stdout.strip(),
                f"{budgets['autohome_step1']} {budgets['dongchedi_step2']}",
            )

    def test_emitted_env_contains_debug_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "budget.env"
            budgets = self.mod.allocate(None, 0, debug=True)
            self.mod.emit_env(str(out), budgets, debug=True, available=0)
            text = out.read_text(encoding="utf-8")
            self.assertIn("CRAWL_BUDGET_DEBUG=true", text)
            self.assertIn("YICHE_TIME_LIMIT", text)


class CliTests(unittest.TestCase):
    def test_cli_runs_and_writes_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "b.env"
            result = subprocess.run(
                [sys.executable, str(ALLOCATOR), "--output", str(out), "--print"],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(out.exists())
            self.assertIn("AUTOHOME_STEP1_TIME_LIMIT", out.read_text(encoding="utf-8"))


class DealerBudgetTests(unittest.TestCase):
    """经销商报价原是四源里唯一完全无界的，必须有上限且限量要确定性。"""

    def test_dealer_script_exposes_budget_flags(self) -> None:
        text = DEALER.read_text(encoding="utf-8")
        self.assertIn("--time-limit", text)
        self.assertIn("--max-series", text)

    def test_dealer_limits_by_deterministic_prefix(self) -> None:
        # 随机采样会让同一车系在两轮之间忽隐忽现，污染增量合并；
        # 必须是 slice 前缀。
        text = DEALER.read_text(encoding="utf-8")
        self.assertIn("series_ids = series_ids[: args.max_series]", text)
        self.assertNotIn("random", text.lower().split("def main")[1][:2000])

    def test_dealer_time_limit_keeps_partial_result(self) -> None:
        # 到点收尾必须是设计内行为：已抓到的部分照常落盘并过闸，
        # 不能因为「没跑完」就把整轮判失败。
        text = DEALER.read_text(encoding="utf-8")
        self.assertIn("timed_out", text)
        self.assertIn("keeping partial result", text)

    def test_dealer_cli_accepts_new_flags(self) -> None:
        result = subprocess.run(
            [sys.executable, str(DEALER), "--help"],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--time-limit", result.stdout)
        self.assertIn("--max-series", result.stdout)


class WorkflowWiringTests(unittest.TestCase):
    """`.cnb.yml` 必须真的接上分配器，而不是只在仓库里躺着一个脚本。"""

    def setUp(self) -> None:
        self.text = CRAWL_WORKFLOW.read_text(encoding="utf-8")

    def test_no_hardcoded_time_limit_remains(self) -> None:
        # 三源硬编码 2700 已被--time-limit 2700 取代；
        # 任何残留都会让「预算分配」变成只对部分源生效。
        self.assertNotIn("--time-limit 2700", self.text)

    def test_budget_allocator_stage_present(self) -> None:
        self.assertIn("分配爬取时间预算", self.text)
        self.assertIn("scripts/allocate_crawl_budget.py", self.text)

    def test_every_crawl_stage_sources_budget_env(self) -> None:
        # 基础属性链的三个爬取 stage（汽车之家/懂车帝/易车）
        # 在 api_trigger 与半月 crontab 两个 job 里各出现一次 → 2× 3 = 6 次 source。
        # 经销商报价已拆成独立链路（失败域隔离），它有自己的 --time-limit 1500，
        # 不再从分配器取预算，所以不计入这里。
        self.assertEqual(
            self.text.count(". /tmp/cnb-crawl-budget.env"),
            6,
            "基础属性链的三源各自在 api_trigger 与半月 crontab 里 source 一次",
        )

    def test_every_env_var_read_by_crawlers_is_produced_somewhere(self) -> None:
        # 反向守卫：分配器 env 里的每个键都必须在 .cnb.yml 里被真正消费，
        # 防止「分配器发了预算但stage 没读」这种静默失效。
        for key in (
            "AUTOHOME_STEP1_TIME_LIMIT",
            "DONGCHEDI_STEP1_TIME_LIMIT",
            "DONGCHEDI_STEP2_TIME_LIMIT",
            "YICHE_TIME_LIMIT",
        ):
            self.assertIn(key, self.text, f"{key} 在 .cnb.yml 里没有任何消费方")

    def test_dealer_budget_not_in_shared_allocator(self) -> None:
        # 报价已拆成独立链路（用户裁定：报价失败不许拖住基础属性），
        # 它不再与三源共享 120min 总预算，自带 --time-limit 1500。
        # 因此主链里不该再出现 DEALER_TIME_LIMIT——出现即说明有人把报价并回了主链。
        dealer_job_marker = '"crontab: 37 8,16 * * *"'
        self.assertIn(dealer_job_marker, self.text, "报价独立链路 job 不见了")
        main_chain_text = self.text.split(dealer_job_marker, 1)[0]
        self.assertNotIn(
            "DEALER_TIME_LIMIT",
            main_chain_text,
            "DEALER_TIME_LIMIT 出现在报价独立链路之外 —— 报价可能被并回主链了",
        )

    def test_dead_debug_variables_are_gone(self) -> None:
        # MR/BN_MR/MO_MR/TE_MR/UN_MR/UN_SL/TB_B/TB_Z 全仓无人 os.getenv 读取，
        # 留着只会让人误以为 debug 生效。
        # 只看真实赋值行：注释里可以提到这些名字（说明它们被删了）。
        import re

        assignments = re.findall(r"^\s*(?!#)\s*([A-Z_][A-Z_0-9]*)\s*=", self.text, re.MULTILINE)
        assigned = set(assignments)
        for dead in ("MR", "BN_MR", "MO_MR", "TE_MR", "UN_MR", "UN_SL", "TB", "TB_B", "TB_Z"):
            self.assertNotIn(dead, assigned, f"死变量 {dead} 仍在 .cnb.yml 里被赋值")

    def test_debug_mode_passes_real_limit_flags(self) -> None:
        # 真正生效的 debug 开关是 --debug-limit / --max-cars / --max-series。
        self.assertIn("--debug-limit 20", self.text)
        self.assertIn("AH_MAX_CARS=20", self.text)
        self.assertIn("--max-series 20", self.text)

    def test_failstages_retry_also_uses_budget(self) -> None:
        # 重跑体此前连 debug 分支都没有，必然再超时一次。
        self.assertGreaterEqual(self.text.count("DCD_DEBUG_ARGS"), 4)


if __name__ == "__main__":
    unittest.main()
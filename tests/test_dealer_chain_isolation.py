"""报价链与基础属性链的**失败域隔离**回归测试。

用户裁定（2026-10-09）：经销商报价可能无值、会随时间变化，
它必须与基础属性**异步解耦**——报价失败不许拖住基础属性更新。

移植到 CNB 时报价被塞进同一条半月流水线，后果实测过：
报价占主链时间预算、共用 120min 硬上限，一个月只刷 2 次，
Pages 因此停更到 2026-08-12。

这里把「隔离」钉死成可测的结构约束，防止以后有人顺手把报价并回主链：
1. 报价爬取 stage **不得**出现在基础属性链（api_trigger / 半月 crontab）里；
2. 报价必须是独立 job，且有独立 timeout；
3. 独立链路的输入必须是**线上** latest.json（覆盖用户当前看到的发布集），
   而不是仓库里过期的 docs/data；
4. 报价未达 min-rows 时必须放弃本轮、保留旧文件——绝不用残缺数据覆盖；
5. 发布前必须开 --refresh-dealer-prices，否则陈旧报价不会被更新；
6. 独立链路里不该出现基础属性爬取（否则又耦合回去了）。
"""

from __future__ import annotations

import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
Cnb = ROOT / ".cnb.yml"

CRAWL_SOURCES = ("爬取-汽车之家", "爬取-懂车帝", "爬取-易车")
# 基础属性链里原来的 stage 名（现在必须已被摘除）
DEALER_STAGE = "爬取-经销商报价"
# 独立链路里的 stage 名
DEALER_STAGE_IN_CHAIN = "增量爬取经销商报价"


def load_main() -> dict:
    return (yaml.safe_load(Cnb.read_text(encoding="utf-8")) or {}).get("main") or {}


def stage_names(job: dict) -> list[str]:
    runner = job[0]
    return [s.get("name") for s in runner.get("stages") or []]


def stage_script(job: dict, name: str) -> str:
    runner = job[0]
    for s in runner.get("stages") or []:
        if s.get("name") == name:
            return s.get("script") or ""
    raise AssertionError(f"stage {name!r} not found")


def find_dealer_job(main: dict):
    """找报价独立 job。

    注意：判断依据是**独立链路里的 stage 名**（`增量爬取经销商报价`），
    不是基础属性链里那个被摘除的旧名（`爬取-经销商报价`）——
    用旧名去找，隔离生效后反而找不到，因为旧名已经被删干净了。
    """
    for key, job in main.items():
        if not isinstance(job, list) or not job or not isinstance(job[0], dict):
            continue
        if "stages" not in job[0]:
            continue
        if DEALER_STAGE_IN_CHAIN in stage_names(job):
            return key, job
    return None, None


def base_attribute_jobs(main: dict) -> list[tuple[str, dict]]:
    """含基础属性爬取的两个 job：api_trigger（手动/API 触发）与半月 crontab。"""
    out = []
    for key, job in main.items():
        if not isinstance(job, list) or not job or not isinstance(job[0], dict):
            continue
        if "stages" not in job[0]:
            continue
        names = stage_names(job)
        if any(src in names for src in CRAWL_SOURCES):
            out.append((key, job))
    return out


class DealerIsolationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.main = load_main()

    def test_base_attribute_jobs_exist(self) -> None:
        # 先确认我们找对了 job，否则下面的隔离断言会假绿
        jobs = base_attribute_jobs(self.main)
        self.assertGreaterEqual(
            len(jobs), 2, f"含基础属性爬取的 job 少于 2 个：{[k for k, _ in jobs]}"
        )

    def test_dealer_not_in_base_attribute_chain(self) -> None:
        # 核心隔离断言：报价不许出现在基础属性链里
        for key, job in base_attribute_jobs(self.main):
            with self.subTest(job=key):
                self.assertNotIn(
                    DEALER_STAGE,
                    stage_names(job),
                    f"{key} 里仍有报价 stage —— 报价失败会拖住基础属性，隔离失效",
                )

    def test_dealer_runs_in_its_own_job(self) -> None:
        key, job = find_dealer_job(self.main)
        self.assertIsNotNone(job, "找不到独立的报价 job")
        names = stage_names(job)
        for src in CRAWL_SOURCES:
            self.assertNotIn(
                src, names, f"报价链路里混进了 {src} —— 两个链路又耦合了"
            )

    def test_dealer_job_has_independent_timeout(self) -> None:
        # 独立预算：报价有自己的 timeout，不与基础属性共用 120min 上限
        _, job = find_dealer_job(self.main)
        timeout = job[0].get("timeout")
        self.assertIsNotNone(timeout, "报价 job 没有独立 timeout")
        self.assertIn(str(timeout), ("30m", "45m", "1h", "1h30m", "2h"))

    def test_dealer_reads_live_baseline_not_repo_docs(self) -> None:
        # 输入必须是最新完整已验证的 immutable Release：旧 Pages 缓存或
        # 仓库 docs/data 都可能遗漏新车系。
        _, job = find_dealer_job(self.main)
        script = "\n".join(
            stage_script(job, n) for n in stage_names(job)
        )
        self.assertIn("download_verified_release.py --repo Fatty911/crawl_cars --no-legacy", script)
        self.assertIn("python scripts/prepare_cnb_pages.py", script)
        self.assertIn('if len(rows) < 10000:', script)
        self.assertIn('--series-input /tmp/dealer-baseline/latest.json', script)
        self.assertNotIn("docs/data/latest.json", script)

    def test_dealer_aborts_when_min_rows_not_met(self) -> None:
        # 未达 min-rows 必须放弃本轮并保留旧文件，绝不用残缺数据覆盖
        _, job = find_dealer_job(self.main)
        script = "\n".join(stage_script(job, n) for n in stage_names(job))
        self.assertIn("--min-rows 300", script)
        self.assertIn("保留现有 data/dealer_prices.json", script)

    def test_dealer_never_auto_retries(self) -> None:
        # 报价是锦上添花，反复重跑只占带宽并可能与基础属性链抢带宽。
        # 失败后只归档诊断，不自动重跑。
        _, job = find_dealer_job(self.main)
        names = stage_names(job)
        retry_words = ("重触发", "自动重跑", "retry-pipeline", "重试-自动")
        for n in names:
            for w in retry_words:
                self.assertNotIn(w, n, f"报价链路不该有自动重跑stage：{n}")

    def test_publish_enables_dealer_refresh(self) -> None:
        # 发布前必须开 --refresh-dealer-prices：
        # 否则报价链刷新了报价，发布时overlay 仍只填空值，陈旧报价不会被更新。
        found = 0
        for key, job in base_attribute_jobs(self.main):
            script = "\n".join(stage_script(job, n) for n in stage_names(job))
            with self.subTest(job=key):
                self.assertIn(
                    "--refresh-dealer-prices",
                    script,
                    f"{key} 的发布未开 --refresh-dealer-prices，陈旧报价不会更新",
                )
                found += 1
        self.assertGreater(found, 0)


class DealerScriptCapabilityTests(unittest.TestCase):
    """报价脚本自身必须真的支持限量与到点收尾，否则独立链路的边界是假的。"""

    def test_script_flags_exist(self) -> None:
        text = (ROOT / "scripts" / "crawl_dealer_prices.py").read_text(encoding="utf-8")
        self.assertIn("--time-limit", text)
        self.assertIn("--max-series", text)

    def test_timeout_keeps_partial_result(self) -> None:
        text = (ROOT / "scripts" / "crawl_dealer_prices.py").read_text(encoding="utf-8")
        self.assertIn("keeping partial result", text)


class CnbStrictYamlTests(unittest.TestCase):
    """CNB 的 YAML 解析比 PyYAML 严格，本地能过的配置在 CNB 会被拒。

    实测踩过的坑：插入报价 job 时重复写入了同名 job 键，
    PyYAML `safe_load` 静默接受（后者覆盖前者），而 CNB 直接返回
    `422 [CONFIG_ERROR] ... duplicated mapping key`，整个仓库无法触发构建。
    这类问题必须在本地拦住，否则只能靠线上报错发现。
    """

    def _load_strict(self, text: str):
        class StrictLoader(yaml.SafeLoader):
            pass

        duplicates: list[str] = []

        def _mapping(loader, node, deep=False):
            loader.flatten_mapping(node)
            seen: dict = {}
            for key_node, _value_node in node.value:
                key = loader.construct_object(key_node, deep=deep)
                if key in seen:
                    duplicates.append(f"{key!r} @ line {key_node.start_mark.line + 1}")
                seen[key] = True
            return yaml.SafeLoader.construct_mapping(loader, node, deep)

        StrictLoader.construct_mapping = _mapping
        try:
            yaml.load(text, Loader=StrictLoader)
        finally:
            pass
        return duplicates

    def test_no_duplicate_keys(self) -> None:
        text = Cnb.read_text(encoding="utf-8")
        duplicates = self._load_strict(text)
        self.assertEqual(duplicates, [], f".cnb.yml 存在重复 key（CNB 会拒）: {duplicates}")

    def test_dealer_job_appears_exactly_once(self) -> None:
        text = Cnb.read_text(encoding="utf-8")
        count = sum(
            1 for line in text.splitlines()
            if line.strip() == '"crontab: 37 8 * * 0":'
        )
        self.assertEqual(count, 1, f"报价 job 键出现了 {count} 次")

    def test_dealer_job_indentation_is_valid(self) -> None:
        # job 键是 2 空格缩进，其列表项 `- runner:` 必须是 4 空格。
        # 后续层级不用硬编码偏移（太脆，行一多就错位），交给 YAML 解析验证——
        # 缩进错位的典型表现正是「能解析出结构，但结构是错的块序列」。
        text = Cnb.read_text(encoding="utf-8")
        lines = text.splitlines()
        start = next(
            i for i, l in enumerate(lines)
            if l.strip() == '"crontab: 37 8 * * 0":'
        )
        self.assertEqual(
            len(lines[start]) - len(lines[start].lstrip()), 2,
            "报价 job 键缩进应为 2（与 main 下其他 job 同级）",
        )
        runner = lines[start + 1]
        self.assertEqual(
            len(runner) - len(runner.lstrip()), 4,
            f"报价 job 的首行列表项缩进应为 4：{runner!r}",
        )
        # 完整结构由 YAML 解析背书：9 个 stage、1h timeout、正确的时间字段类型。
        main = yaml.safe_load(text)["main"]
        dealer = next(v for k, v in main.items() if "37 8 * * 0" in str(k))
        self.assertIsInstance(dealer, list)
        self.assertEqual(dealer[0]["timeout"], "1h")
        self.assertEqual(len(dealer[0]["stages"]), 9)
        for stage in dealer[0]["stages"]:
            self.assertIn("name", stage)
            self.assertIn("script", stage)


if __name__ == "__main__":
    unittest.main()

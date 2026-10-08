"""经销商报价 overlay 的回归测试。

背景：报价**会随时间变化**（dealers 调价、车型停产/改名）。
原实现只填「空/无价」的行，于是 `data/dealer_prices.json` 刷新了，
Pages 上已有的旧报价永远不会被更新。

这里守住的语义：
1. **补空**是默认且始终生效的（原语义不能丢）；
2. **刷新**必须显式开启——`merge_data` 的输入里已有各源当场抓的现价，
   比 8 小时前的 dealer 索引更新，无条件覆盖是用旧打新；
3. **区间/多值形态**（`46.76万|29.90万起`）信息量高于单值，任何模式下都不被覆盖；
4. 同值不写入，不制造无意义 diff；
5. 索引缺文件/坏JSON 时必须静默返回空（不能因报价文件坏了就发不出 Pages）。
"""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
OVERLAY = SCRIPTS / "dealer_price_overlay.py"


def load_overlay_module():
    spec = importlib.util.spec_from_file_location("dealer_price_overlay_t", OVERLAY)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {OVERLAY}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _TempOverlayModule:
    """在临时目录里造一棵 scripts/ + data/ 树，加载真实模块指向它。

    这样测的是真实实现（含 Path 解析），而不是把 load_dealer_index 换掉的假货。
    """

    def __init__(self, series: dict | None, *, raw_text: str | None = None) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / "scripts").mkdir()
        (root / "data").mkdir()
        if raw_text is not None:
            (root / "data" / "dealer_prices.json").write_text(raw_text, encoding="utf-8")
        elif series is not None:
            (root / "data" / "dealer_prices.json").write_text(
                json.dumps({"updated_at": "2026-10-09T00:00:00+08:00", "series": series},
                           ensure_ascii=False),
                encoding="utf-8",
            )
        target = root / "scripts" / "dealer_price_overlay.py"
        target.write_text(OVERLAY.read_text(encoding="utf-8"), encoding="utf-8")
        spec = importlib.util.spec_from_file_location(
            f"dealer_price_overlay_temp_{id(self)}", target
        )
        assert spec is not None and spec.loader is not None
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def close(self) -> None:
        self.tmp.cleanup()


class OverlaySemanticTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mod = load_overlay_module()
        # 用假索引隔离真实 data/dealer_prices.json（语义测试不关心文件 IO）。
        # 键必须是 _norm_year / _norm_name 之后的形态：
        #   年款 "2025款" → "2025"；车型名去掉内部空格。
        self.name_with_space = "2.0T 汽油自动两驱标准版 5座"
        self.name_norm = self.mod._norm_name(self.name_with_space)
        self.index = {
            ("1296", "2025", self.name_norm): "17.88万",
            ("20136", "2026", self.mod._norm_name("540km 精英版")): "17.19万",
            ("777", "2024", self.mod._norm_name("全系")): "9.99万",
        }
        self.mod.load_dealer_index = lambda: dict(self.index)

    def _row(self, sid: str, year: str, name: str, price: str) -> dict:
        return {
            "车系ID": sid,
            "年款": year,
            "车型名称": name,
            "经销商参考价": price,
        }

    def _hit_row(self, price: str) -> dict:
        """构造一个必定命中索引 1296/2025 的行。"""
        return self._row("1296", "2025", self.name_with_space, price)

    def test_empty_price_is_filled(self) -> None:
        for empty in ("", "-", "暂无报价", "None"):
            with self.subTest(value=empty):
                rows = [self._hit_row(empty)]
                self.mod.overlay_dealer_prices(rows)
                self.assertEqual(rows[0]["经销商参考价"], "17.88万")

    def test_missing_price_key_is_filled(self) -> None:
        # 行里根本没有「经销商参考价」这个键，也应被补上
        rows = [{"车系ID": "1296", "年款": "2025", "车型名称": self.name_with_space}]
        self.mod.overlay_dealer_prices(rows)
        self.assertEqual(rows[0]["经销商参考价"], "17.88万")

    def test_existing_price_not_refreshed_by_default(self) -> None:
        # 默认不刷新：merge_data 输入里的现价比索引新，不能被旧值覆盖
        rows = [self._hit_row("18.50万")]
        self.mod.overlay_dealer_prices(rows)
        self.assertEqual(rows[0]["经销商参考价"], "18.50万")

    def test_existing_price_refreshed_when_enabled(self) -> None:
        # 显式开启刷新：报价源本轮更新过时，陈旧单值必须跟上
        rows = [self._hit_row("18.50万")]
        self.mod.overlay_dealer_prices(rows, refresh_existing=True)
        self.assertEqual(rows[0]["经销商参考价"], "17.88万")

    def test_multi_value_price_never_overwritten(self) -> None:
        # 区间值信息量更高，单值覆盖是信息降级——两种模式都不许覆盖
        for multi in ("46.76万|29.90万起", "12.00万、13.00万", "10万/12万"):
            with self.subTest(value=multi):
                rows = [self._hit_row(multi)]
                self.mod.overlay_dealer_prices(rows, refresh_existing=True)
                self.assertEqual(rows[0]["经销商参考价"], multi)

    def test_same_value_not_rewritten(self) -> None:
        # 同值不该写入，否则每次发布都产生无意义 diff
        rows = [self._hit_row("17.88万")]
        before = json.dumps(rows, ensure_ascii=False, sort_keys=True)
        self.mod.overlay_dealer_prices(rows, refresh_existing=True)
        self.assertEqual(json.dumps(rows, ensure_ascii=False, sort_keys=True), before)

    def test_unmatched_row_untouched(self) -> None:
        rows = [self._row("999", "2020", "不存在", "5.00万")]
        self.mod.overlay_dealer_prices(rows, refresh_existing=True)
        self.assertEqual(rows[0]["经销商参考价"], "5.00万")

    def test_key_normalization(self) -> None:
        # 归一化：年款「2025款」→2025，车型名去前置「2025款 」、去内部空格
        self.index[("888", "2025", self.mod._norm_name("旗舰版"))] = "30.00万"
        rows = [self._row("888", "2025款", "2025款 旗舰版", "")]
        self.mod.overlay_dealer_prices(rows)
        self.assertEqual(rows[0]["经销商参考价"], "30.00万")


class OverlayResilienceTests(unittest.TestCase):
    """索引侧的真实 IO 行为：文件缺失/损坏/为空都不能拖垮发布。"""

    def test_missing_index_file_returns_empty(self) -> None:
        # 不造data/dealer_prices.json → load_dealer_index 必须返回空
        holder = _TempOverlayModule(series=None)
        try:
            self.assertEqual(holder.module.load_dealer_index(), {})
            rows = [{"车系ID": "1", "经销商参考价": "10万"}]
            self.assertIs(holder.module.overlay_dealer_prices(rows), rows)
        finally:
            holder.close()

    def test_malformed_index_file_is_tolerated(self) -> None:
        # 坏 JSON：必须静默当空处理，绝不能让 Pages 发布因报价文件坏了而崩
        holder = _TempOverlayModule(None, raw_text="{not json at all")
        try:
            self.assertEqual(holder.module.load_dealer_index(), {})
            rows = [{"车系ID": "1", "经销商参考价": "10万"}]
            self.assertIs(holder.module.overlay_dealer_prices(rows), rows)
        finally:
            holder.close()

    def test_real_file_overlay_end_to_end(self) -> None:
        # 端到端：真实文件 → 真实索引 → 真正改写行
        holder = _TempOverlayModule(
            series={"1296": [{"year": "2025", "name": "2.0T 汽油自动两驱标准版 5座",
                              "dealer_price": "17.88万"}]}
        )
        try:
            rows = [{"车系ID": "1296", "年款": "2025",
                     "车型名称": "2.0T 汽油自动两驱标准版 5座", "经销商参考价": "暂无报价"}]
            holder.module.overlay_dealer_prices(rows)
            self.assertEqual(rows[0]["经销商参考价"], "17.88万")
        finally:
            holder.close()

    def test_empty_series_key_is_noop(self) -> None:
        holder = _TempOverlayModule(series={})
        try:
            self.assertEqual(holder.module.load_dealer_index(), {})
            rows = [{"车系ID": "1", "经销商参考价": ""}]
            holder.module.overlay_dealer_prices(rows)
            self.assertEqual(rows[0]["经销商参考价"], "")
        finally:
            holder.close()


class PreparePagesPayloadRefreshTests(unittest.TestCase):
    """prepare_pages_payload 是发布前最后一道闸，必须能开启刷新。"""

    def setUp(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "prepare_pages_payload_t", SCRIPTS / "prepare_pages_payload.py"
        )
        self.assertIsNotNone(spec)
        assert spec is not None and spec.loader is not None
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)

    def _row(self, sid: str, year: str, name: str, price: str, official: str) -> dict:
        return {
            "车系ID": sid,
            "年款": year,
            "车型名称": name,
            "经销商参考价": price,
            "官方指导价": official,
            "上市时间": "2025.06",
        }

    def test_signature_accepts_refresh_flag(self) -> None:
        import inspect

        params = inspect.signature(self.mod.prepare_rows_with_stats).parameters
        self.assertIn("refresh_dealer_prices", params)
        self.assertIs(params["refresh_dealer_prices"].default, False)

    def test_refresh_flag_propagates_to_overlay(self) -> None:
        calls = []

        def fake(rows, *, refresh_existing=False):
            calls.append(refresh_existing)
            return rows

        self.mod.overlay_dealer_prices = fake
        row = self._row("1296", "2025", "2.0T 汽油自动两驱标准版 5座", "18.50万", "17.88万")
        self.mod.prepare_rows_with_stats([row], 2022, refresh_dealer_prices=True)
        self.assertEqual(calls, [True])

    def test_default_does_not_refresh(self) -> None:
        calls = []

        def fake(rows, *, refresh_existing=False):
            calls.append(refresh_existing)
            return rows

        self.mod.overlay_dealer_prices = fake
        row = self._row("1296", "2025", "2.0T 汽油自动两驱标准版 5座", "18.50万", "17.88万")
        self.mod.prepare_rows_with_stats([row], 2022)
        self.assertEqual(calls, [False])

    def test_cli_exposes_refresh_flag(self) -> None:
        import subprocess
        import sys

        out = subprocess.run(
            [sys.executable, str(SCRIPTS / "prepare_pages_payload.py"), "--help"],
            capture_output=True, text=True, encoding="utf-8",
        )
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("--refresh-dealer-prices", out.stdout)


if __name__ == "__main__":
    unittest.main()
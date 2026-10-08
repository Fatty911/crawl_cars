#!/usr/bin/env python3
"""Shared incremental dealer-price overlay (懂车帝 garage data).

设计要点（2026-10-09 修订）
---------------------------
原实现只填「空/无价」的行（`if cur and cur not in ("", "-", "暂无报价"): continue`），
这在「报价是静态字段」的假设下成立，但报价**会随时间变化**：
 dealers 调价、车型停产/改名都会让旧值失效。原实现下，
 `data/dealer_prices.json` 刷新了，已有的旧报价**永远不会被更新**，
 于是 Pages 上的经销商参考价会无限期停留在首次抓取的值。

修订后有两条覆盖路径：
1. **补空**（原语义保留）：原值是空 / `-` / `暂无报价` / `None` → 填入报价。
2. **刷新**（新增）：原值非空但来源与「本次报价索引」不一致时，
   只有当调用方显式开启 `refresh_existing=True` 才覆盖。

为什么刷新要显式开启、而不是无条件覆盖：
 `merge_data.py` 的输入包含各源自己的报价字段（懂车帝/易车当场抓的现价），
 那些值比 8 小时前的 dealer 索引**更新**。无条件覆盖会用旧数据打新数据。
 因此默认仍以「补空」为主，只有确认要走「报价索引为准」的路径（如
 `prepare_pages_payload.py` 的发布前刷新）才打开 refresh。

识别「陈旧值」用值的形态而不是时间戳：dealer 索引里的值都是 `17.88万` 这种
单值形态；各源自报的报价常是区间/多值形态（`46.76万|29.90万起`）。
区间值信息量更大，不该被单值覆盖。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


# 原值判定为「无价」的形态
EMPTY_PRICE_VALUES = {"", "-", "暂无报价", "None", "null", "暂无", "无"}
# 区间/多值形态：信息量高于单值，不接受被 dealer 单值覆盖
MULTI_VALUE_SEPARATORS = "|、,，;；/和"


def load_dealer_index() -> dict[tuple[str, str, str], str]:
    """Load data/dealer_prices.json into {(车系ID, 年款, 归一名称): dealer_price}.

    Returns an empty dict when the file is missing or malformed.
    """
    dp_path = Path(__file__).resolve().parents[1] / "data" / "dealer_prices.json"
    if not dp_path.exists():
        return {}
    try:
        data = json.loads(dp_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    by_series = data.get("series") or {}
    index: dict[tuple[str, str, str], str] = {}
    for sid, cars in by_series.items():
        for car in cars:
            if not car.get("dealer_price"):
                continue
            key = (str(sid), _norm_year(str(car.get("year", ""))),
                   _norm_name(str(car.get("name", ""))))
            # 用 setdefault：同一(车系,年款,车型)出现多次时取第一次，
            # 避免遍历顺序影响结果（dict 保序，但仍取决于源数据顺序）。
            index.setdefault(key, str(car["dealer_price"]))
    return index


def _norm_year(year: str) -> str:
    m = re.search(r"20\d{2}|\d{4}", year)
    return m.group(0) if m else year.strip()


def _norm_name(name: str) -> str:
    name = re.sub(r"^\d{2,4}款\s*", "", name.strip())
    return re.sub(r"\s+", "", name)


def _is_empty_price(value: Any) -> bool:
    return str(value or "").strip() in EMPTY_PRICE_VALUES


def _is_multi_value(value: str) -> bool:
    """区间/多值形态（如 `46.76万|29.90万起`）信息量更高，不被单值覆盖。"""
    return any(sep in value for sep in MULTI_VALUE_SEPARATORS)


def overlay_dealer_prices(
    rows: list[dict[str, Any]],
    *,
    refresh_existing: bool = False,
) -> list[dict[str, Any]]:
    """Overlay dealer prices onto rows.

    Args:
        rows: 待增强的行（原地修改）。
        refresh_existing:
            False（默认）= 只补空。原语义，适合 merge_data 阶段
            （输入里已有各源当场抓的现价，比索引新）。
            True = 补空 + 刷新单值形态的陈旧报价，适合发布前刷新
            （以 dealer 索引为准，让 Pages 上的报价跟上最新变化）。
            区间/多值形态在任何模式下都不被覆盖。
    """
    index = load_dealer_index()
    if not index:
        return rows
    filled = 0
    refreshed = 0
    for row in rows:
        sid = str(row.get("车系ID") or "").strip()
        year = _norm_year(str(row.get("年款") or "").strip())
        name = _norm_name(str(row.get("车型名称") or ""))
        cur = str(row.get("经销商参考价") or "").strip()
        price = index.get((sid, year, name))
        if not price:
            continue
        if _is_empty_price(cur):
            row["经销商参考价"] = price
            filled += 1
            continue
        if not refresh_existing:
            continue
        # 同值无需写入，避免无意义的 diff 噪音
        if price == cur:
            continue
        # 区间值信息量更高，用单值覆盖是信息降级
        if _is_multi_value(cur):
            continue
        row["经销商参考价"] = price
        refreshed += 1
    if filled or refreshed:
        print(f"[dealer overlay] 补空 {filled} 行, 刷新 {refreshed} 行")
    return rows
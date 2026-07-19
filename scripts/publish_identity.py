#!/usr/bin/env python3
"""Shared publish identity rules for release and Pages safety checks."""

from __future__ import annotations

import re
from datetime import date
from typing import Any


YEAR_RE = re.compile(r"(?:19|20)\d{2}")
CAR_ID_FIELDS = ("车款ID", "易车车型ID", "车型ID", "spec_id", "specId")
INVALID_PRICE_VALUES = {"", "-", "--", "None", "null", "暂无", "暂无报价"}


def value(row: dict[str, Any], field: str) -> str:
    text = str(row.get(field, "") or "").strip()
    return "" if text in {"", "-", "None", "null"} else text


def valid_official_price(value_text: Any) -> str:
    text = str(value_text or "").strip()
    if text in INVALID_PRICE_VALUES:
        return ""
    if "暂无" in text or "报价" in text and not re.search(r"\d", text):
        return ""
    return text if re.search(r"\d", text) else ""


def normalize_official_price(row: dict[str, Any]) -> str:
    current = valid_official_price(row.get("官方指导价"))
    if current:
        return current
    if is_autohome_row(row):
        return valid_official_price(row.get("厂商指导价_元_"))
    if is_yiche_row(row):
        return valid_official_price(row.get("价格"))
    return ""


def normalize_publish_official_price(row: dict[str, Any]) -> bool:
    price = normalize_official_price(row)
    if not price:
        return False
    row["官方指导价"] = price
    return True


def has_valid_listing_time(row: dict[str, Any], today: date | None = None) -> bool:
    text = value(row, "上市时间")
    if not text:
        return False
    current = today or date.today()
    for year, month, day in re.findall(r"((?:19|20)\d{2})[年./-]([01]?\d)(?:[月./-]([0-3]?\d))?", text):
        y = int(year)
        m = int(month)
        d = int(day) if day else 1
        if not 1 <= m <= 12 or not 1 <= d <= 31:
            continue
        if date(y, m, min(d, 28)) <= current:
            return True
    return False


def has_chinese(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text))


def is_slug_series(text: str) -> bool:
    return bool(re.fullmatch(r"[a-z][a-z0-9-]*-\d+", text))


def autohome_series_valid(series: str) -> bool:
    return bool(series and series != "-" and not is_slug_series(series))


def is_autohome_row(row: dict[str, Any]) -> bool:
    return "汽车之家" in str(row.get("数据来源", "") or "")


def is_yiche_row(row: dict[str, Any]) -> bool:
    return "易车" in str(row.get("数据来源", "") or "")


def row_car_id(row: dict[str, Any]) -> str:
    for field in CAR_ID_FIELDS:
        text = value(row, field)
        if text:
            return text
    return ""


def publish_year(row: dict[str, Any]) -> str:
    year = value(row, "年款")
    if YEAR_RE.fullmatch(year):
        return year
    match = YEAR_RE.search(value(row, "车型名称"))
    return match.group(0) if match else ""


def autohome_publish_identity_valid(row: dict[str, Any]) -> bool:
    if not is_autohome_row(row):
        return True
    brand = value(row, "品牌")
    series = value(row, "车系")
    model = value(row, "车型名称")
    year = value(row, "年款")
    car_id = row_car_id(row)
    return (
        bool(brand and model and YEAR_RE.fullmatch(year))
        and has_chinese(brand)
        and autohome_series_valid(series)
        and car_id.isdigit()
    )


def yiche_publish_identity_valid(row: dict[str, Any]) -> bool:
    if not is_yiche_row(row):
        return True
    brand = value(row, "品牌")
    series = value(row, "车系")
    model = value(row, "车型名称")
    year = value(row, "年款")
    status = value(row, "易车上市状态")
    car_id = row_car_id(row)
    return (
        bool(brand and series and model and YEAR_RE.fullmatch(year))
        and has_chinese(brand)
        and not is_slug_series(series)
        and car_id.isdigit()
        and status == "approved"
    )


def publish_boundary_valid(row: dict[str, Any]) -> bool:
    if not isinstance(row, dict):
        return False
    if value(row, "数据来源") and (not normalize_publish_official_price(row) or not has_valid_listing_time(row)):
        return False
    if is_yiche_row(row):
        return yiche_publish_identity_valid(row)
    if is_autohome_row(row):
        return autohome_publish_identity_valid(row)
    brand = value(row, "品牌")
    series = value(row, "车系")
    model = value(row, "车型名称")
    year = publish_year(row)
    if not value(row, "数据来源"):
        return bool(brand and model and year)
    return bool(brand and series and model and year and not is_slug_series(series))


def identity_key(row: dict[str, Any]) -> tuple[str, ...]:
    if not isinstance(row, dict):
        raise ValueError("each row must be a JSON object")
    if is_yiche_row(row) and not yiche_publish_identity_valid(row):
        raise ValueError("Yiche identity requires approved status and Chinese brand/series")
    if is_autohome_row(row) and not autohome_publish_identity_valid(row):
        raise ValueError("Autohome identity requires brand, series, model and year")

    model = value(row, "车型名称")
    year = publish_year(row)
    if not model or not year:
        raise ValueError("identity requires 车型名称 and 年款")

    series_id = value(row, "车系ID")
    if series_id:
        return ("series_id", series_id, model, year)

    brand = value(row, "品牌")
    series = value(row, "车系")
    if not brand or not series:
        raise ValueError("identity without 车系ID requires 品牌 and 车系")
    if is_slug_series(series):
        raise ValueError("identity requires non-slug 车系")
    return ("fallback", brand, series, model, year)

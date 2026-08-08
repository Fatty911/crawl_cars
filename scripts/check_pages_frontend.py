#!/usr/bin/env python3
"""Check the live Pages frontend WITHOUT vision: console logs, JS
exceptions and DOM rendering state (cards / table rows / stats loaded).
Outputs a JSON report; exits 0 always (the caller decides)."""
import json
import os
import sys
import re

from playwright.sync_api import sync_playwright

URL = "https://cars.jiucai.eu.org/"


def main() -> int:
    console_errors: list[dict] = []
    page_errors: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        def on_console(msg):
            if msg.type in ("error", "warning"):
                text = msg.text[:300]
                if "favicon" in text.lower() or "net::" in text and "ERR_ABORTED" in text:
                    return
                console_errors.append({"type": msg.type, "text": text})

        def on_pageerror(err):
            page_errors.append(str(err)[:300])

        page.on("console", on_console)
        page.on("pageerror", on_pageerror)
        page.goto(URL, wait_until="domcontentloaded", timeout=180000)

        # 等待数据加载：统计区域出现且当前结果非 0（latest.json 144MB，可能较慢）
        loaded = False
        stats_text = ""
        for _ in range(60):
            page.wait_for_timeout(3000)
            body = page.locator("body").inner_text()
            m = re.search(r"当前结果\s*\n?\s*(\d+)", body)
            if m and int(m.group(1)) > 0:
                loaded = True
                stats_text = body[:600]
                break
        cards = page.locator(".series-card").count()
        table_rows = page.locator("table tbody tr").count()
        match_m = re.search(r"匹配车系\s*\n?\s*(\d+)", page.locator("body").inner_text())
        match_count = int(match_m.group(1)) if match_m else None
        browser.close()

    result = {
        "url": URL,
        "data_loaded": loaded,
        "match_series": match_count,
        "cards_rendered": cards,
        "table_rows": table_rows,
        "console_errors": console_errors[:20],
        "page_errors": page_errors[:10],
        "healthy": bool(loaded and not page_errors and cards > 0),
    }
    print(json.dumps(result, ensure_ascii=False))
    out = os.environ.get("GITHUB_OUTPUT", "")
    if out:
        def emit(k, v):
            with open(out, "a", encoding="utf-8") as f:
                f.write(f"{k}={v}\n")
        emit("pages_health", "ok" if result["healthy"] else "degraded")
        if page_errors:
            emit("pages_page_errors", " | ".join(page_errors[:3]))
        if cards == 0 and loaded:
            emit("pages_cards_empty", "1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

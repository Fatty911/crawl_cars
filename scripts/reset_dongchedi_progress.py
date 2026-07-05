#!/usr/bin/env python3
"""Reset Dongchedi crawl progress while preserving the series-list cache."""

from __future__ import annotations

import json
import os
from pathlib import Path


PROGRESS_PATH = Path("dongchedi/progress.json")
KEEP_KEYS = ("series_list", "excluded_series")


def main() -> int:
    keep: dict[str, object] = {}

    if PROGRESS_PATH.exists():
        try:
            with PROGRESS_PATH.open("r", encoding="utf-8") as f:
                data = json.load(f)
            for key in KEEP_KEYS:
                if data.get(key):
                    keep[key] = data[key]
        except Exception as exc:
            print(f"读取旧懂车帝进度失败，将清空进度: {exc}")

    if keep:
        PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with PROGRESS_PATH.open("w", encoding="utf-8") as f:
            json.dump(keep, f, ensure_ascii=False)
        print(f"保留懂车帝车系列表缓存 {len(keep.get('series_list', []))} 条")
    else:
        try:
            os.remove(PROGRESS_PATH)
        except FileNotFoundError:
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

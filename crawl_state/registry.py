"""
统一型号注册表模块

所有爬虫共用，持久化已爬取型号 UID 到 JSON 文件（提交到 git），
支持增量比对——即使 GitHub Actions 换 Runner 也能快速判断增量。

典型用法:
    from crawl_state.registry import ModelRegistry

    registry = ModelRegistry("autohome")
    new_ids = registry.get_new_uids(current_uid_list)
    registry.register_uids(new_ids, meta={"source": "autohome"})
"""

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


REGISTRY_DIR = Path(__file__).parent
REGISTRY_DIR.mkdir(exist_ok=True)


class ModelRegistry:
    """型号注册表：持久化存储已爬取型号 UID，支持增量比对"""

    def __init__(self, source_name: str):
        self.source_name = source_name
        self.path = REGISTRY_DIR / f"model_registry_{source_name}.json"
        self._data = self._load()

    def _load(self) -> Dict:
        if self.path.exists():
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                print(f"注册表 {self.path} 读取失败，将重建: {e}")
        return {"last_updated": None, "models": {}}

    def _save(self):
        self._data["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
        tmp = self.path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    def get_existing_uids(self) -> Set[str]:
        return set(self._data.get("models", {}).keys())

    def get_new_uids(self, current_uids: List[str]) -> List[str]:
        """返回本次新增的 UID 列表（不在注册表中的）"""
        existing = self.get_existing_uids()
        return [uid for uid in current_uids if uid not in existing]

    def register_uids(self, uids: List[str], meta: Optional[Dict[str, Any]] = None):
        """登记已爬取型号 UID 及其元数据"""
        for uid in uids:
            self._data.setdefault("models", {})[uid] = meta or {}
        self._save()

    def unregister_uids(self, uids: List[str]):
        """移除指定型号（用于重新爬取或清理）"""
        models = self._data.get("models", {})
        for uid in uids:
            models.pop(uid, None)
        self._save()

    def is_registered(self, uid: str) -> bool:
        return uid in self._data.get("models", {})

    def is_first_run(self) -> bool:
        """无注册表或注册表为空 = 首次运行"""
        return not self.path.exists() or not self._data.get("models")

    def count(self) -> int:
        return len(self._data.get("models", {}))

    def reset(self):
        """清空注册表"""
        self._data = {"last_updated": None, "models": {}}
        self._save()

    def prune_missing_files(self, directory: str, suffix: str = "") -> int:
        """清理注册表中对应文件已不存在的条目，返回清理数量"""
        if not os.path.isdir(directory):
            return 0
        existing_files = set(os.listdir(directory))
        models = self._data.get("models", {})
        to_remove = []
        for uid in list(models.keys()):
            filename = uid + suffix
            if filename not in existing_files:
                to_remove.append(uid)
        if to_remove:
            self.unregister_uids(to_remove)
        return len(to_remove)

"""Field-specific checks for carried publish data; never infer missing facts."""
from __future__ import annotations

import re

_SOURCE = re.compile(r"(?:^|\|)(汽车之家|懂车帝|易车):")
_FOREIGN_LEVEL = re.compile(r"^(?:L[0-5]级|暂无(?:价格|报价)|[●○◯〇◉](?:\s*暂无(?:价格|报价))?)$")


def clean_vehicle_level(value: object) -> tuple[str, list[str]]:
    text = str(value or "")
    matches = list(_SOURCE.finditer(text))
    segments = []
    if not matches:
        segments.append(("", text))
    else:
        if matches[0].start():
            segments.append(("", text[:matches[0].start()].rstrip("|")))
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            segments.append((match.group(1), text[match.end():end].rstrip("|")))
    kept = []
    removed = []
    for source, content in segments:
        values = []
        for part in content.split("|"):
            if _FOREIGN_LEVEL.fullmatch(part.strip()):
                removed.append(part)
            else:
                values.append(part)
        if values:
            kept.append((source + ":" if source else "") + "|".join(values))
    return ("|".join(kept), removed) if removed else (text, [])


def vehicle_level_residual(rows: list[dict]) -> list[int]:
    return [index for index, row in enumerate(rows) if clean_vehicle_level(row.get("级别"))[1]]


def model_year_conflicts(rows: list[dict]) -> list[int]:
    """Detect explicit disagreement without choosing a source or changing facts."""
    conflicts = []
    for index, row in enumerate(rows):
        named = set(re.findall(r"(?<![0-9])(20[0-9]{2})\s*款", str(row.get("车型名称") or "")))
        declared = set(re.findall(r"(?<![0-9])(20[0-9]{2})(?![0-9])", str(row.get("年款") or "")))
        if len(named) > 1 or len(declared) > 1 or (named and declared and named != declared):
            conflicts.append(index)
    return conflicts

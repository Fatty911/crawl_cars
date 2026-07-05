"""抓取汽车零整比公开发布数据，生成可供 merge_data.py 合并的 JSON。"""
import csv
import io
import json
import os
import re
from datetime import date
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import requests

DIR = Path(__file__).resolve().parents[1]

DEFAULT_SOURCES = [
    {
        "source": "中国保险行业协会/中国汽车维修行业协会",
        "published_at": "2019-04",
        "url": "https://www.iachina.cn/module/download/downfile.jsp?classid=0&filename=ad76b64b664640838086078928c0b080.pdf",
    },
    {
        "source": "中国保险行业协会/中国汽车维修行业协会",
        "published_at": "2016-03",
        "url": "https://www.iachina.cn/module/download/downfile.jsp?classid=0&filename=f4d619c2d4d743349f01063242f268f5.pdf",
    },
]

USER_AGENT = "Mozilla/5.0 (compatible; crawl-cars-zero-to-whole/1.0)"
RATIO_RE = re.compile(r"^\d+(?:\.\d+)?%$")
BODY_MARKERS = [
    "三厢",
    "两厢",
    "SUV",
    "MPV",
    "旅行版",
    "敞篷",
    "硬顶",
    "皮卡",
    "手动",
    "自动",
    "手自一体",
    "双离合",
    "CVT",
    "AMT",
    "DCT",
    "EV",
    "PHEV",
]


def clean_text(value) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def parse_ratio(value) -> Optional[float]:
    text = clean_text(value)
    match = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    if not match:
        return None
    return round(float(match.group(1)), 2)


def infer_series_from_model(brand: str, model_name: str) -> str:
    text = clean_text(model_name)
    text = re.sub(r"^(19|20)\d{2}\s*", "", text)
    if brand:
        text = re.sub(rf"^{re.escape(brand)}\s*", "", text)
    marker_positions = [text.find(marker) for marker in BODY_MARKERS if text.find(marker) > 0]
    if marker_positions:
        text = text[: min(marker_positions)]
    text = re.sub(r"\b\d+(?:\.\d+)?[TL]\b.*$", "", text, flags=re.IGNORECASE)
    return clean_text(text) or brand


def split_source_urls(raw: str) -> List[str]:
    if not raw:
        return []
    raw = raw.strip()
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, list):
        return [str(item).strip() for item in parsed if str(item).strip()]
    if isinstance(parsed, dict):
        items = parsed.get("urls") or parsed.get("sources") or parsed.get("subscriptions") or []
        return [str(item).strip() for item in items if str(item).strip()]
    return [item.strip() for item in re.split(r"[\r\n;|]+", raw) if item.strip()]


def load_sources() -> List[Dict[str, str]]:
    sources = list(DEFAULT_SOURCES)
    config_path = DIR / "zero_to_whole_sources.json"
    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as f:
            configured = json.load(f)
        if isinstance(configured, list):
            sources.extend(configured)
        elif isinstance(configured, dict):
            sources.extend(configured.get("sources", []))

    for url in split_source_urls(os.environ.get("ZERO_TO_WHOLE_RATIO_URLS", "")):
        sources.append({"source": "环境变量零整比来源", "published_at": "", "url": url})

    deduped = []
    seen = set()
    for source in sources:
        url = clean_text(source.get("url"))
        if not url or url in seen:
            continue
        seen.add(url)
        deduped.append(
            {
                "source": clean_text(source.get("source")) or "零整比公开来源",
                "published_at": clean_text(source.get("published_at")),
                "url": url,
            }
        )
    return deduped


def download(url: str) -> bytes:
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=45)
    response.raise_for_status()
    return response.content


def compact_table_row(row: Iterable[object]) -> List[str]:
    return [clean_text(cell) for cell in row if clean_text(cell)]


def looks_like_data_row(cells: List[str]) -> bool:
    return any(RATIO_RE.match(cell) for cell in cells) and any(re.fullmatch(r"\d{5,7}", cell) for cell in cells)


def append_continuation(target: Dict[str, str], cells: List[str]) -> None:
    text = clean_text(" ".join(cells))
    if not text:
        return
    if re.search(r"\d{5,7}|\d+(?:\.\d+)?%", text):
        return
    target["车型名称"] = clean_text(f"{target.get('车型名称', '')} {text}")


def row_from_cells(cells: List[str], source: Dict[str, str]) -> Optional[Dict[str, object]]:
    ratio_index = next((idx for idx, cell in enumerate(cells) if RATIO_RE.match(cell)), -1)
    if ratio_index <= 0:
        return None
    price_index = next(
        (idx for idx in range(ratio_index - 1, -1, -1) if re.fullmatch(r"\d{5,7}", cells[idx])),
        -1,
    )
    if price_index < 0:
        if len(cells) < 4 or not cells[0].isdigit():
            return None
        brand = cells[1]
        model_name = cells[2]
        series = infer_series_from_model(brand, model_name)
        return {
            "数据来源": source["source"],
            "来源URL": source["url"],
            "发布日期": source.get("published_at", ""),
            "品牌": brand,
            "车系": series,
            "车型名称": model_name,
            "年款": re.search(r"\b(19\d{2}|20\d{2})\b", model_name).group(1)
            if re.search(r"\b(19\d{2}|20\d{2})\b", model_name)
            else "",
            "零整比": parse_ratio(cells[ratio_index]),
            "零整比原始值": f"{parse_ratio(cells[ratio_index]):.2f}%",
        }

    ratio = parse_ratio(cells[ratio_index])
    if ratio is None:
        return None

    prefix = cells[:price_index]
    if len(prefix) < 3:
        return None

    brand = prefix[0]
    series = prefix[1]
    model_name = prefix[-1]
    year_match = re.search(r"\b(19\d{2}|20\d{2})\b", model_name)

    return {
        "数据来源": source["source"],
        "来源URL": source["url"],
        "发布日期": source.get("published_at", ""),
        "品牌": brand,
        "车系": series,
        "车型名称": model_name,
        "年款": year_match.group(1) if year_match else "",
        "零整比": ratio,
        "零整比原始值": f"{ratio:.2f}%",
    }


def extract_pdf_rows_with_pdfplumber(content: bytes, source: Dict[str, str]) -> List[Dict[str, object]]:
    try:
        import pdfplumber
    except ImportError:
        return []

    rows: List[Dict[str, object]] = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables() or []:
                last_row = None
                for raw_row in table:
                    cells = compact_table_row(raw_row)
                    if not cells:
                        continue
                    parsed = row_from_cells(cells, source)
                    if parsed:
                        rows.append(parsed)
                        last_row = parsed
                    elif last_row and not looks_like_data_row(cells):
                        append_continuation(last_row, cells)
    return rows


def extract_pdf_rows_with_text(content: bytes, source: Dict[str, str]) -> List[Dict[str, object]]:
    try:
        from pypdf import PdfReader
    except ImportError:
        return []

    reader = PdfReader(io.BytesIO(content))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    chunks = re.split(r"(?=\n[\u4e00-\u9fffA-Za-z]{1,12}\s+[\u4e00-\u9fffA-Za-z0-9 -]{1,30}\s+)", text)
    rows = []
    for chunk in chunks:
        flat = clean_text(chunk)
        match = re.search(r"(\d{5,7})\s+(\d+(?:\.\d+)?)%", flat)
        if not match:
            continue
        before = flat[: match.start()].split()
        if len(before) < 3:
            continue
        ratio = round(float(match.group(2)), 2)
        model_match = re.search(r"\b(19\d{2}|20\d{2})\b\s+(.+)$", flat[: match.start()])
        model_name = model_match.group(0) if model_match else " ".join(before[2:])
        rows.append(
            {
                "数据来源": source["source"],
                "来源URL": source["url"],
                "发布日期": source.get("published_at", ""),
                "品牌": before[0],
                "车系": before[1],
                "车型名称": clean_text(model_name),
                "年款": model_match.group(1) if model_match else "",
                "零整比": ratio,
                "零整比原始值": f"{ratio:.2f}%",
            }
        )
    return rows


def extract_html_rows(content: bytes, source: Dict[str, str]) -> List[Dict[str, object]]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(content, "lxml")
    rows = []
    for tr in soup.find_all("tr"):
        cells = [clean_text(cell.get_text(" ")) for cell in tr.find_all(["td", "th"])]
        parsed = row_from_cells([cell for cell in cells if cell], source)
        if parsed:
            rows.append(parsed)
    return rows


def extract_rows(content: bytes, source: Dict[str, str]) -> List[Dict[str, object]]:
    head = content[:512].lower()
    if b"%pdf" in head:
        rows = extract_pdf_rows_with_pdfplumber(content, source)
        if rows:
            return rows
        return extract_pdf_rows_with_text(content, source)
    return extract_html_rows(content, source)


def load_local_rows() -> List[Dict[str, object]]:
    rows = []
    for path in sorted(DIR.glob("zero_to_whole_manual.*")):
        if path.suffix.lower() == ".json":
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            rows.extend(data if isinstance(data, list) else data.get("rows", []))
        elif path.suffix.lower() == ".csv":
            with path.open("r", encoding="utf-8-sig", newline="") as f:
                rows.extend(csv.DictReader(f))
    out = []
    for row in rows:
        ratio = parse_ratio(row.get("零整比") or row.get("ratio") or row.get("ratio_percent"))
        if ratio is None:
            continue
        out.append(
            {
                "数据来源": clean_text(row.get("数据来源") or row.get("source") or "本地零整比数据"),
                "来源URL": clean_text(row.get("来源URL") or row.get("url")),
                "发布日期": clean_text(row.get("发布日期") or row.get("published_at")),
                "品牌": clean_text(row.get("品牌") or row.get("brand")),
                "车系": clean_text(row.get("车系") or row.get("series")),
                "车型名称": clean_text(row.get("车型名称") or row.get("model_name")),
                "年款": clean_text(row.get("年款") or row.get("year")),
                "零整比": ratio,
                "零整比原始值": f"{ratio:.2f}%",
            }
        )
    return out


def dedupe_rows(rows: Iterable[Dict[str, object]]) -> List[Dict[str, object]]:
    deduped = []
    seen = set()
    for row in rows:
        key = (
            row.get("数据来源"),
            row.get("来源URL"),
            row.get("品牌"),
            row.get("车系"),
            row.get("车型名称"),
            row.get("零整比"),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def main() -> None:
    rows = load_local_rows()
    for source in load_sources():
        try:
            content = download(source["url"])
            extracted = extract_rows(content, source)
            print(f"{source['source']} {source['published_at']} 提取 {len(extracted)} 条: {source['url']}")
            rows.extend(extracted)
        except Exception as exc:
            print(f"零整比来源跳过: {source['url']} ({exc})")

    rows = dedupe_rows(rows)
    today = date.today().strftime("%Y%m%d")
    dated_path = DIR / f"zero_to_whole_ratios_{today}.json"
    latest_path = DIR / "zero_to_whole_ratios.json"
    for path in (dated_path, latest_path):
        with path.open("w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
    print(f"零整比数据完成: {len(rows)} 条")
    print(f"  {dated_path}")
    print(f"  {latest_path}")


if __name__ == "__main__":
    main()

"""易车爬虫 - 从易车车型参数配置页提取车型配置数据。"""

import argparse
import json
import os
import re
import time
from datetime import date
from html import unescape
from urllib.parse import urljoin

import bs4
import requests


DEFAULT_DISCOVERY_URLS = ["https://car.yiche.com/"]
DEFAULT_SERIES_URLS = [
    "https://car.yiche.com/hanl/peizhi/",
    "https://car.yiche.com/modely-6224/peizhi/",
    "https://car.yiche.com/guanzhigq3/peizhi/",
    "https://car.yiche.com/hafub26/peizhi/",
    "https://car.yiche.com/idera5s/peizhi/",
    "https://car.yiche.com/teslamodelx/peizhi/",
]


HEADER_MAP = {
    "厂商指导价": "价格",
    "排量": "发动机排量",
    "最大扭矩": "扭矩",
    "最大功率": "功率",
    "变速箱": "变速器",
    "长*宽*高": "长x宽x高",
    "轴距": "轴距(mm)",
    "整备质量": "整备质量(kg)",
    "燃料形式": "燃油类型",
    "WLTC综合油耗": "油耗(L/100km)",
    "CLTC纯电续航里程": "纯电续航(km)",
    "NEDC纯电续航里程": "纯电续航(km)",
    "快充时间": "快充(小时)",
    "慢充时间": "慢充(小时)",
    "驱动方式": "驱动形式",
    "前悬架类型": "前悬挂",
    "后悬架类型": "后悬挂",
    "电动机总功率": "电机功率(kW)",
    "电动机总扭矩": "电机扭矩(N·m)",
    "电池能量密度": "电池能量密度(Wh/kg)",
    "官方0-100km/h加速": "0-100km/h加速(s)",
    "最高车速": "最高车速(km/h)",
    "前轮胎规格": "前轮胎",
    "后轮胎规格": "后轮胎",
}


def clean_text(value):
    return re.sub(r"\s+", " ", unescape(str(value or ""))).strip()


def normalize_key(key):
    key = clean_text(key).strip("：:")
    return HEADER_MAP.get(key, key)


def split_urls(raw):
    return [item.strip() for item in re.split(r"[,\n]", raw or "") if item.strip()]


def load_urls(args):
    urls = []
    if args.url:
        urls.extend(args.url)
    urls.extend(split_urls(os.getenv("YICHE_SERIES_URLS", "")))
    if args.url_file and os.path.exists(args.url_file):
        with open(args.url_file, "r", encoding="utf-8") as f:
            urls.extend(line.strip() for line in f if line.strip() and not line.startswith("#"))
    return list(dict.fromkeys(urls))


def normalize_series_url(url):
    page_url = url if url.endswith("/") else url + "/"
    if not page_url.endswith("peizhi/"):
        page_url = urljoin(page_url, "peizhi/")
    return page_url


def extract_candidate_urls(base_url, html):
    pattern = re.compile(r'https?://car\.yiche\.com/[a-z0-9][a-z0-9-]*/(?:peizhi/)?|/[a-z0-9][a-z0-9-]*/(?:peizhi/)?', re.I)
    excluded = {
        "brand",
        "newcar",
        "xuanchegongju",
        "suv",
        "jiaoche",
        "mpv",
        "paoche",
        "pika",
    }
    urls = []
    for match in pattern.findall(html):
        absolute = urljoin(base_url, match)
        slug = absolute.rstrip("/").split("/")[-1]
        if slug == "peizhi":
            slug = absolute.rstrip("/").split("/")[-2]
        if slug in excluded or len(slug) <= 1:
            continue
        urls.append(absolute)
    return list(dict.fromkeys(urls))


def discover_series_urls(session, discovery_urls, max_pages=30):
    discovered = []
    candidate_pages = []
    for discovery_url in discovery_urls:
        try:
            print(f"发现易车车系 URL: {discovery_url}")
            html = fetch(session, discovery_url)
        except requests.RequestException as exc:
            print(f"  易车发现页抓取失败，跳过: {exc}")
            continue
        for candidate in extract_candidate_urls(discovery_url, html):
            if candidate.endswith("/peizhi/"):
                discovered.append(candidate)
            else:
                candidate_pages.append(candidate)

    for candidate in list(dict.fromkeys(candidate_pages))[:max_pages]:
        try:
            html = fetch(session, candidate)
        except requests.RequestException as exc:
            print(f"  易车候选页抓取失败，跳过: {candidate} {exc}")
            continue
        for nested in extract_candidate_urls(candidate, html):
            discovered.append(normalize_series_url(nested))

    deduped = list(dict.fromkeys(discovered))
    print(f"自动发现易车车系 URL {len(deduped)} 个")
    return deduped


def fetch(session, url):
    response = session.get(url, timeout=30)
    response.raise_for_status()
    return response.text


def parse_next_data(html):
    soup = bs4.BeautifulSoup(html, "html.parser")
    script = soup.find("script", id="__NEXT_DATA__")
    if not script or not script.string:
        return None
    try:
        return json.loads(script.string)
    except json.JSONDecodeError:
        return None


def walk(obj):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from walk(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from walk(value)


def extract_from_next_data(data):
    rows = {}
    for obj in walk(data):
        model_id = obj.get("carId") or obj.get("carid") or obj.get("id")
        model_name = obj.get("carName") or obj.get("carname") or obj.get("name")
        if not model_id or not model_name:
            continue
        row = rows.setdefault(str(model_id), {"车型名称": clean_text(model_name)})
        for src, dst in (("brandName", "品牌"), ("brandname", "品牌"), ("serialName", "车系"), ("serialname", "车系"), ("year", "年款")):
            if obj.get(src) and not row.get(dst):
                row[dst] = clean_text(obj[src])
        key = obj.get("name") or obj.get("itemName") or obj.get("paramName") or obj.get("configName")
        value = obj.get("value") or obj.get("val") or obj.get("paramValue") or obj.get("configValue")
        if key and value and clean_text(key) != clean_text(model_name):
            row[normalize_key(key)] = clean_text(value)
    return [row for row in rows.values() if row.get("车型名称")]


def extract_identity_from_meta(html):
    soup = bs4.BeautifulSoup(html, "html.parser")
    title = clean_text(soup.title.get_text(" ") if soup.title else "")
    description_tag = soup.find("meta", attrs={"name": "description"})
    description = clean_text(description_tag.get("content") if description_tag else "")
    if "参数配置暂未公布" in title or "参数配置暂未公布" in description:
        return []
    text = title or description
    if not text:
        return []
    brand = ""
    series = ""
    match = re.search(r"(?:【[^】]*配置】)?([^_【】]+)_([^_【】]+?)(?:详细参数|综合配置|参数配置|频道|$)", text)
    if match:
        brand = clean_text(match.group(1))
        series = clean_text(match.group(2))
    else:
        match = re.search(r"【?([^【】_]+?)(?:配置|参数配置|详细参数)", text)
        if match:
            series = clean_text(match.group(1))
    if not series:
        return []
    row = {"车系": series, "车型名称": series}
    if brand and brand != series:
        row["品牌"] = brand
    return [row]


def extract_from_tables(html):
    soup = bs4.BeautifulSoup(html, "html.parser")
    rows = []
    headers = [clean_text(th.get_text(" ")) for th in soup.select("table tr th")]
    model_names = [h for h in headers if h and h not in {"参数", "配置", "车型"}]
    for name in model_names:
        rows.append({"车型名称": name})
    if not rows:
        return []
    for tr in soup.select("table tr"):
        cells = [clean_text(cell.get_text(" ")) for cell in tr.find_all(["th", "td"])]
        if len(cells) < 2:
            continue
        key = normalize_key(cells[0])
        for idx, value in enumerate(cells[1:len(rows) + 1]):
            if value:
                rows[idx][key] = value
    return rows


def series_slug_from_url(url):
    return url.rstrip("/").split("/")[-2] if url.rstrip("/").endswith("peizhi") else url.rstrip("/").split("/")[-1]


def extract_identity_from_url(url, html):
    if "参数配置暂未公布" in html:
        return []
    series_slug = series_slug_from_url(url)
    if not series_slug:
        return []
    return [{"车系": series_slug, "车型名称": series_slug}]


def enrich_identity(rows, url):
    series_slug = series_slug_from_url(url)
    for row in rows:
        row.setdefault("车系", series_slug)
        row.setdefault("数据来源", "易车")
    return rows


def crawl(urls, delay, time_limit=0):
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    all_rows = []
    start = time.monotonic()
    for url in urls:
        if time_limit and time.monotonic() - start >= time_limit:
            print("易车爬取时间预算已用完，停止继续抓取")
            break
        page_url = normalize_series_url(url)
        print(f"抓取易车: {page_url}")
        try:
            html = fetch(session, page_url)
            data = parse_next_data(html)
            rows = extract_from_next_data(data) if data else []
            if not rows:
                rows = extract_from_tables(html)
            if not rows:
                rows = extract_identity_from_meta(html)
            if not rows:
                rows = extract_identity_from_url(page_url, html)
            rows = enrich_identity(rows, page_url)
            print(f"  提取 {len(rows)} 条")
            all_rows.extend(rows)
        except requests.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else None
            if status_code in {403, 429}:
                rows = enrich_identity(extract_identity_from_url(page_url, ""), page_url)
                print(f"  易车页面被限制访问({status_code})，使用 URL 兜底提取 {len(rows)} 条")
                all_rows.extend(rows)
            else:
                print(f"  易车页面抓取失败，跳过: {exc}")
        except requests.RequestException as exc:
            print(f"  易车页面抓取失败，跳过: {exc}")
        if delay:
            time.sleep(delay)
    return all_rows


def main():
    parser = argparse.ArgumentParser(description="易车爬虫")
    parser.add_argument("--url", action="append", help="易车车系页 URL，可重复传入")
    parser.add_argument("--url-file", default="config/yiche_series_urls.txt", help="易车车系 URL 列表")
    parser.add_argument("--discover-url", action="append", help="未配置车系 URL 时用于自动发现的易车入口页，可重复传入")
    parser.add_argument("--output", default="", help="输出 JSON 路径")
    parser.add_argument("--delay", type=float, default=float(os.getenv("CRAWL_MIN_DELAY_SECONDS", "8")))
    parser.add_argument("--time-limit", type=int, default=0, help="最大运行时间(秒)，0表示不限制")
    parser.add_argument("--max-series", type=int, default=0, help="最多爬取车系 URL 数，0表示不限制")
    parser.add_argument("--max-discovery-pages", type=int, default=30, help="自动发现时最多跟进的候选页数量")
    args = parser.parse_args()

    urls = load_urls(args)
    if not urls:
        discovery_urls = args.discover_url or split_urls(os.getenv("YICHE_DISCOVERY_URLS", "")) or DEFAULT_DISCOVERY_URLS
        session = requests.Session()
        session.headers.update({"User-Agent": "Mozilla/5.0"})
        urls = DEFAULT_SERIES_URLS + discover_series_urls(session, discovery_urls, args.max_discovery_pages)
    urls = list(dict.fromkeys(normalize_series_url(url) for url in urls))
    if args.max_series > 0:
        urls = urls[:args.max_series]
    if not urls:
        print("未配置且未发现易车车系 URL，生成空数据文件。可通过 --url、--url-file、YICHE_SERIES_URLS 或 YICHE_DISCOVERY_URLS 配置。")
    rows = crawl(urls, args.delay, args.time_limit) if urls else []
    output = args.output or f"yiche_{date.today().strftime('%Y%m%d')}.json"
    with open(output, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    print(f"易车数据已写入 {output}，共 {len(rows)} 条")


if __name__ == "__main__":
    main()

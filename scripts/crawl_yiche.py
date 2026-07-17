"""易车爬虫 - 从易车车型参数配置页提取车型配置数据。"""

import argparse
import hashlib
import json
import os
import re
import time
from datetime import date
from html import unescape
from urllib.parse import urljoin, urlparse

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

YICHE_CONFIG_API = "https://mapi.yiche.com/web_api/car_model_api/api/v1/car/config_new_param"
YICHE_BRAND_API = "https://mapi.yiche.com/web_api/car_model_api/api/v1/brand/get_brand_list"
YICHE_API_CID = "508"
YICHE_API_SECRET = "19DDD1FBDFF065D3A4DA777D2D7A81EC"
IDENTITY_FIELDS = {"车系", "车型名称", "品牌", "年款", "数据来源"}
NON_SERIES_SLUGS = {
    "api", "article", "assets", "authenservice", "citybase", "current",
    "issue", "message", "videos",
}


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


def serial_id_from_url(url):
    slug = series_slug_from_url(normalize_series_url(url))
    match = re.search(r"-(\d+)$", slug)
    return match.group(1) if match else ""


def is_series_path(url):
    parsed = urlparse(url)
    if parsed.netloc and parsed.netloc != "car.yiche.com":
        return False
    parts = [part for part in parsed.path.split("/") if part]
    if parts and parts[-1] == "peizhi":
        parts.pop()
    if len(parts) != 1:
        return False
    slug = parts[0].lower()
    return slug not in NON_SERIES_SLUGS and bool(re.fullmatch(r"[a-z][a-z0-9-]+", slug))


def extract_candidate_urls(base_url, html):
    soup = bs4.BeautifulSoup(html, "html.parser")
    urls = []
    for link in soup.find_all("a", href=True):
        absolute = urljoin(base_url, link["href"])
        if not is_series_path(absolute):
            continue
        serial_id = serial_id_from_url(absolute)
        explicit_config_link = urlparse(absolute).path.rstrip("/").endswith("/peizhi")
        if serial_id or explicit_config_link:
            urls.append(absolute)
    return list(dict.fromkeys(urls))


def extract_series_targets(base_url, html):
    """Return configuration page URLs paired with page-provided serial IDs."""
    soup = bs4.BeautifulSoup(html, "html.parser")
    targets = {}
    for link in soup.find_all("a", href=True):
        raw_url = urljoin(base_url, link["href"])
        if not is_series_path(raw_url):
            continue
        absolute = normalize_series_url(raw_url)
        serial_id = ""
        node = link
        for _ in range(4):
            if node is None:
                break
            for key in ("data-serial-id", "data-serialid"):
                value = node.attrs.get(key)
                if value and str(value).isdigit():
                    serial_id = str(value)
                    break
            if serial_id:
                break
            node = node.parent
        if serial_id:
            targets[absolute] = serial_id

    for script in soup.find_all("script"):
        text = script.string or script.get_text()
        for match in re.finditer(
            r'(?s)(?:"(?:url|href|path)"\s*:\s*"(?P<url>/[^"?#]+)").{0,600}?'
            r'"(?:serialId|serialid)"\s*:\s*"?(?P<id>\d+)"?'
            r'|"(?:serialId|serialid)"\s*:\s*"?(?P<id_first>\d+)"?.{0,600}?'
            r'"(?:url|href|path)"\s*:\s*"(?P<url_last>/[^"?#]+)"',
            text,
        ):
            candidate = match.group("url") or match.group("url_last")
            serial_id = match.group("id") or match.group("id_first")
            raw_url = urljoin(base_url, candidate)
            absolute = normalize_series_url(raw_url)
            if is_series_path(raw_url):
                targets.setdefault(absolute, serial_id)
    return targets


def extract_serial_id(html):
    patterns = (
        r'"(?:serialId|serialid)"\s*:\s*"?(\d+)"?',
        r'(?:data-serial-id|data-serialid)=["\'](\d+)["\']',
    )
    for pattern in patterns:
        match = re.search(pattern, html)
        if match:
            return match.group(1)
    return ""


def discover_series_urls(session, discovery_urls, max_pages=30):
    discovered = {}
    candidate_pages = []
    for discovery_url in discovery_urls:
        try:
            print(f"发现易车车系 URL: {discovery_url}")
            html = fetch(session, discovery_url)
        except requests.RequestException as exc:
            print(f"  易车发现页抓取失败，跳过: {exc}")
            continue
        discovered.update(extract_series_targets(discovery_url, html))
        for candidate in extract_candidate_urls(discovery_url, html):
            normalized = normalize_series_url(candidate)
            serial_id = serial_id_from_url(normalized)
            if serial_id:
                discovered.setdefault(normalized, serial_id)
            elif candidate.endswith("/peizhi/"):
                candidate_pages.append(candidate)

    for candidate in list(dict.fromkeys(candidate_pages))[:max_pages]:
        try:
            html = fetch(session, candidate)
        except requests.RequestException as exc:
            print(f"  易车候选页抓取失败，跳过: {candidate} {exc}")
            continue
        discovered.update(extract_series_targets(candidate, html))

    trusted = {url: serial_id for url, serial_id in discovered.items() if serial_id}
    print(
        f"自动发现易车车系 URL {len(trusted)} 个，均含 serialId; "
        f"拒绝无 serialId 自动候选 {len(discovered) - len(trusted)} 个"
    )
    return trusted


def fetch(session, url):
    response = session.get(url, timeout=30)
    response.raise_for_status()
    return response.text


def fetch_yiche_api(session, endpoint, parameters):
    param = json.dumps(parameters, separators=(",", ":"))
    timestamp = str(int(time.time() * 1000))
    signature = hashlib.md5(
        f"cid={YICHE_API_CID}&param={param}{YICHE_API_SECRET}{timestamp}".encode()
    ).hexdigest()
    response = session.get(
        endpoint,
        params={"cid": YICHE_API_CID, "param": param},
        headers={
            "Referer": "https://car.yiche.com/",
            "content-type": "application/json;charset=UTF-8",
            "x-city-id": "2401",
            "x-platform": "pc",
            "x-sign": signature,
            "x-timestamp": timestamp,
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def fetch_config_api(session, serial_id):
    payload = fetch_yiche_api(session, YICHE_CONFIG_API, {"cityId": "2401", "serialId": str(serial_id)})
    data = payload.get("data") if isinstance(payload, dict) else None
    first_items = data[0].get("items") if isinstance(data, list) and data and isinstance(data[0], dict) else None
    first_item = first_items[0] if isinstance(first_items, list) and first_items and isinstance(first_items[0], dict) else {}
    print(
        f"  易车配置 API: serialId={serial_id} status={payload.get('status') if isinstance(payload, dict) else None} "
        f"message={payload.get('message') if isinstance(payload, dict) else None!r} data_type={type(data).__name__} "
        f"groups={len(data) if isinstance(data, list) else 0} "
        f"group_keys={sorted(data[0]) if isinstance(data, list) and data and isinstance(data[0], dict) else []} "
        f"item_keys={sorted(first_item)}"
    )
    return payload


def extract_master_brands(html):
    brands = []
    seen = set()
    soup = bs4.BeautifulSoup(html, "html.parser")
    for node in soup.select(".brand-list .item-brand, .brand-list-content .item-brand"):
        master_id = clean_text(node.get("data-id"))
        name = clean_text(node.get("data-name") or node.get_text())
        if master_id.isdigit() and name and master_id not in seen:
            seen.add(master_id)
            brands.append((master_id, name))
    return brands


def extract_brand_series(payload):
    series = []
    for maker in payload.get("data") or []:
        if not isinstance(maker, dict):
            continue
        maker_name = clean_text(maker.get("name"))
        for item in maker.get("serialList") or []:
            if not isinstance(item, dict):
                continue
            serial_id = clean_text(item.get("id"))
            name = clean_text(item.get("name"))
            brand = clean_text(item.get("brandName") or item.get("masterName") or maker_name)
            slug = clean_text(item.get("allSpell"))
            if serial_id.isdigit() and name and brand:
                url = f"https://car.yiche.com/{slug}/peizhi/" if re.fullmatch(r"[a-z][a-z0-9-]+", slug) else f"https://car.yiche.com/serial-{serial_id}/peizhi/"
                series.append((url, serial_id))
    return series


class YicheDiscoveryFrontier:
    def __init__(self, session):
        self.session = session
        self.brand_queue = []
        self.brands_total = 0
        self.brands_scanned = 0
        self.pages_scanned = 0
        self.seen_serial_ids = set()
        self.duplicate_serial_ids = 0
        self.initialized = False

    @property
    def exhausted(self):
        return self.initialized and not self.brand_queue

    def discover(self):
        if not self.initialized:
            html = fetch(self.session, DEFAULT_DISCOVERY_URLS[0])
            self.brand_queue = extract_master_brands(html)
            self.brands_total = len(self.brand_queue)
            self.initialized = True
            print(f"易车可信发现初始化: brands_total={self.brands_total} source={DEFAULT_DISCOVERY_URLS[0]}")
            if not self.brand_queue:
                raise RuntimeError("易车首页未解析到结构化品牌节点，拒绝把推荐车系耗尽当作全量发现完成")
        if not self.brand_queue:
            return {}
        master_id, brand_name = self.brand_queue.pop(0)
        payload = fetch_yiche_api(self.session, YICHE_BRAND_API, {"masterId": master_id})
        self.brands_scanned += 1
        self.pages_scanned += 1
        targets = {}
        for url, serial_id in extract_brand_series(payload):
            if serial_id in self.seen_serial_ids:
                self.duplicate_serial_ids += 1
                continue
            self.seen_serial_ids.add(serial_id)
            targets[url] = serial_id
        print(
            f"易车可信发现: brand={brand_name!r} master_id={master_id} brands_scanned={self.brands_scanned} "
            f"brands_total={self.brands_total} pages_scanned={self.pages_scanned} new_serial_ids={len(targets)} "
            f"unique_serial_ids={len(self.seen_serial_ids)} remaining_brands={len(self.brand_queue)}"
        )
        return targets


def extract_from_config_api(payload):
    rows = []
    for group_index, group in enumerate(payload.get("data") or []):
        if not isinstance(group, dict):
            continue
        for item_index, item in enumerate(group.get("items") or []):
            key = normalize_key(item.get("name"))
            if not key:
                continue
            for index, raw_value in enumerate(item.get("paramValues") or []):
                while len(rows) <= index:
                    rows.append({})
                value = clean_text(raw_value.get("value"))
                if (not value or value == "-") and raw_value.get("subList"):
                    value = clean_text(raw_value["subList"][0].get("value"))
                model_name = clean_text(
                    raw_value.get("carName") or raw_value.get("carname") or raw_value.get("name")
                )
                brand_name = clean_text(raw_value.get("brandName") or raw_value.get("brandname"))
                if model_name:
                    rows[index]["车型名称"] = model_name
                if brand_name:
                    rows[index]["品牌"] = brand_name
                if value and value != "-":
                    if key in {"车型", "车型名称", "车款"} or (group_index == 0 and item_index == 0):
                        rows[index]["车型名称"] = value
                    else:
                        rows[index][key] = value
    for row in rows:
        brand = clean_text(row.get("品牌") or row.get("厂商"))
        if brand and brand != "-":
            row["品牌"] = brand
    return rows


def is_real_config_row(row):
    brand = clean_text(row.get("品牌"))
    model = clean_text(row.get("车型名称"))
    return brand not in {"", "-"} and model not in {"", "-"} and any(
        clean_text(value) for key, value in row.items() if key not in IDENTITY_FIELDS
    )


def validate_real_rows(rows):
    return [row for row in rows if isinstance(row, dict) and is_real_config_row(row)]


def identity_quality_counts(rows):
    return {
        "invalid_brand": sum(clean_text(row.get("品牌")) in {"", "-"} for row in rows if isinstance(row, dict)),
        "invalid_model_name": sum(clean_text(row.get("车型名称")) in {"", "-"} for row in rows if isinstance(row, dict)),
    }


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
        if key in {"车型", "车型名称", "车款"}:
            continue
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


def crawl(
    targets,
    delay,
    time_limit=0,
    *,
    discovery_callback=None,
    max_attempts=1,
    finish_buffer=60,
    start_time=None,
):
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    all_rows = []
    stats = {"attempted": 0, "success": 0, "403": 0, "429": 0, "failed": 0, "degraded_identity": 0}
    start = start_time if start_time is not None else time.monotonic()
    deadline = start + time_limit if time_limit else 0
    known_targets = dict(targets) if isinstance(targets, dict) else {url: "" for url in targets}
    pending = list(known_targets)
    known_serial_ids = {serial_id for serial_id in known_targets.values() if serial_id}
    attempts = {}
    completed = set()
    idle_discovery_rounds = 0
    stop_reason = "target_exhausted"
    stats.update({"discovery_rounds": 0, "retry_attempted": 0, "invalid_brand": 0, "invalid_model_name": 0})
    print(
        f"易车预算: budget_seconds={time_limit} finish_buffer_seconds={finish_buffer} "
        f"deadline_monotonic={deadline:.3f} targets_initial={len(known_targets)} max_attempts={max_attempts}"
    )
    while pending or (
        discovery_callback
        and (
            (hasattr(discovery_callback, "discover") and not discovery_callback.exhausted)
            or (not hasattr(discovery_callback, "discover") and idle_discovery_rounds < 2)
        )
    ):
        if deadline and time.monotonic() >= deadline - finish_buffer:
            stop_reason = "safety_buffer_reached"
            break
        if not pending and hasattr(discovery_callback, "discover"):
            stats["discovery_rounds"] += 1
            discovered = discovery_callback.discover()
            added = 0
            for discovered_url, discovered_id in discovered.items():
                if discovered_id in known_serial_ids:
                    continue
                normalized = normalize_series_url(discovered_url)
                known_targets[normalized] = discovered_id
                known_serial_ids.add(discovered_id)
                pending.append(normalized)
                added += 1
            print(
                f"易车发现队列: round={stats['discovery_rounds']} new_serial_ids={added} "
                f"queue_depth={len(pending)} unique_serial_ids={len(known_serial_ids)}"
            )
            if not pending:
                continue
        elif not pending and discovery_callback:
            stats["discovery_rounds"] += 1
            discovered = discovery_callback()
            added = 0
            for discovered_url, discovered_id in discovered.items():
                normalized = normalize_series_url(discovered_url)
                if normalized not in known_targets:
                    known_targets[normalized] = discovered_id
                    pending.append(normalized)
                    added += 1
            idle_discovery_rounds = 0 if added else idle_discovery_rounds + 1
            print(f"易车增量发现: round={stats['discovery_rounds']} discovered={len(discovered)} added_or_enriched={added}")
        if not pending:
            continue
        url = pending.pop(0)
        if url in completed:
            continue
        serial_id = known_targets.get(url, "")
        attempts[url] = attempts.get(url, 0) + 1
        if attempts[url] > 1:
            stats["retry_attempted"] += 1
        target_succeeded = False
        page_url = normalize_series_url(url)
        stats["attempted"] += 1
        print(f"抓取易车: {page_url}")
        try:
            html = fetch(session, page_url)
            serial_id = serial_id or extract_serial_id(html)
            data = parse_next_data(html)
            rows = extract_from_next_data(data) if data else []
            if not rows:
                rows = extract_from_tables(html)
            if not rows:
                rows = extract_identity_from_meta(html)
            rows = enrich_identity(rows, page_url)
            quality = identity_quality_counts(rows)
            stats["invalid_brand"] += quality["invalid_brand"]
            stats["invalid_model_name"] += quality["invalid_model_name"]
            real_rows = validate_real_rows(rows)
            if not real_rows and serial_id:
                api_rows = enrich_identity(extract_from_config_api(fetch_config_api(session, serial_id)), page_url)
                quality = identity_quality_counts(api_rows)
                stats["invalid_brand"] += quality["invalid_brand"]
                stats["invalid_model_name"] += quality["invalid_model_name"]
                real_rows = validate_real_rows(api_rows)
            if real_rows:
                target_succeeded = True
                stats["success"] += 1
                print(f"  提取真实配置 {len(real_rows)} 条")
                print(f"  真实配置样例: 车型名称={real_rows[0]['车型名称']!r} 配置字段={list(key for key in real_rows[0] if key not in IDENTITY_FIELDS)[:5]}")
                all_rows.extend(real_rows)
            else:
                stats["degraded_identity"] += len(rows) or 1
                page_title = clean_text(bs4.BeautifulSoup(html, "html.parser").title)
                print(f"  仅获得降级身份，未计入真实配置 (html_bytes={len(html.encode())} title={page_title!r})")
        except requests.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else None
            if status_code in {403, 429}:
                stats[str(status_code)] += 1
            try:
                api_rows = enrich_identity(extract_from_config_api(fetch_config_api(session, serial_id)), page_url) if serial_id else []
                quality = identity_quality_counts(api_rows)
                stats["invalid_brand"] += quality["invalid_brand"]
                stats["invalid_model_name"] += quality["invalid_model_name"]
                real_rows = validate_real_rows(api_rows)
            except requests.RequestException as api_exc:
                real_rows = []
                print(f"  易车配置 API 抓取失败: {api_exc}")
            if real_rows:
                target_succeeded = True
                stats["success"] += 1
                print(f"  页面受限({status_code})，API 提取真实配置 {len(real_rows)} 条")
                print(f"  真实配置样例: 车型名称={real_rows[0]['车型名称']!r} 配置字段={list(key for key in real_rows[0] if key not in IDENTITY_FIELDS)[:5]}")
                all_rows.extend(real_rows)
            else:
                stats["failed"] += 1
                print(f"  易车页面受限({status_code})且无可用真实配置，跳过")
        except requests.RequestException as exc:
            stats["failed"] += 1
            print(f"  易车页面抓取失败，跳过: {exc}")
        if delay:
            time.sleep(delay)
        if target_succeeded:
            completed.add(url)
        elif attempts[url] < max_attempts and serial_id:
            pending.append(url)
        if not pending and discovery_callback and not hasattr(discovery_callback, "discover") and idle_discovery_rounds < 2:
            stats["discovery_rounds"] += 1
            discovered = discovery_callback()
            added = 0
            for discovered_url, discovered_id in discovered.items():
                normalized = normalize_series_url(discovered_url)
                previous_id = known_targets.get(normalized, "")
                if normalized not in known_targets:
                    known_targets[normalized] = discovered_id
                    pending.append(normalized)
                    added += 1
                elif discovered_id and not previous_id:
                    known_targets[normalized] = discovered_id
                    if normalized not in completed and attempts.get(normalized, 0) < max_attempts:
                        pending.append(normalized)
                        added += 1
            idle_discovery_rounds = 0 if added else idle_discovery_rounds + 1
            print(f"易车增量发现: round={stats['discovery_rounds']} discovered={len(discovered)} added_or_enriched={added}")
    deduped_rows = []
    if discovery_callback and hasattr(discovery_callback, "discover") and discovery_callback.exhausted and not pending:
        stop_reason = "trusted_discovery_exhausted"
    seen_rows = set()
    for row in all_rows:
        key = tuple(clean_text(row.get(field)) for field in ("品牌", "车系", "车型名称", "年款"))
        if key not in seen_rows:
            seen_rows.add(key)
            deduped_rows.append(row)
    print(
        "易车抓取统计: "
        + " ".join(f"{key}={value}" for key, value in stats.items())
        + f" targets_discovered={len(known_targets)} unique_serial_ids_attempted={len({known_targets[url] for url in attempts if known_targets.get(url)})} "
        + f"brands_total={getattr(discovery_callback, 'brands_total', 0)} brands_scanned={getattr(discovery_callback, 'brands_scanned', 0)} "
        + f"pages_scanned={getattr(discovery_callback, 'pages_scanned', 0)} queue_depth={len(pending)} real_rows={len(deduped_rows)} "
        + f"elapsed_seconds={time.monotonic() - start:.1f} remaining_seconds={max(0, deadline - time.monotonic()):.1f} "
        + f"stop_reason={stop_reason}"
    )
    return deduped_rows


def main():
    started_at = time.monotonic()
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
    targets = {normalize_series_url(url): serial_id_from_url(url) for url in urls}
    if not targets:
        discovery_urls = args.discover_url or split_urls(os.getenv("YICHE_DISCOVERY_URLS", "")) or DEFAULT_DISCOVERY_URLS
        session = requests.Session()
        session.headers.update({"User-Agent": "Mozilla/5.0"})
        targets = {normalize_series_url(url): serial_id_from_url(url) for url in DEFAULT_SERIES_URLS}
        targets.update(discover_series_urls(session, discovery_urls, args.max_discovery_pages))
    if args.max_series > 0:
        targets = dict(list(targets.items())[:args.max_series])
    if not targets:
        print("未配置且未发现易车车系 URL，生成空数据文件。可通过 --url、--url-file、YICHE_SERIES_URLS 或 YICHE_DISCOVERY_URLS 配置。")
    discovery_callback = None
    if not urls:
        discovery_callback = YicheDiscoveryFrontier(session)
    rows = crawl(
        targets,
        args.delay,
        args.time_limit,
        discovery_callback=discovery_callback,
        max_attempts=2 if args.max_series == 0 else 1,
        start_time=started_at,
    ) if targets else []
    output = args.output or f"yiche_{date.today().strftime('%Y%m%d')}.json"
    if not rows:
        if os.path.exists(output):
            os.remove(output)
        raise SystemExit("未抓到任何具有真实车型身份和配置字段的易车数据，拒绝生成输出")
    with open(output, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    print(f"易车数据已写入 {output}，共 {len(rows)} 条")


if __name__ == "__main__":
    main()

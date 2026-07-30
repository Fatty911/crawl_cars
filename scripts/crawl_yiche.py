"""易车爬虫 - 从易车车型参数配置页提取车型配置数据。"""

import argparse
import hashlib
import json
import os
import re
import signal
import threading
import time
from datetime import date, datetime, timezone
from html import unescape
from contextlib import contextmanager
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
YICHE_MASTER_BRAND_API = "https://mapi.yiche.com/web_api/car_model_api/api/v1/brand/get_master_brand_list"
YICHE_API_CID = "508"
YICHE_API_SECRET = "19DDD1FBDFF065D3A4DA777D2D7A81EC"
YICHE_CONNECT_TIMEOUT = float(os.getenv("YICHE_CONNECT_TIMEOUT_SECONDS", "8"))
YICHE_READ_TIMEOUT = float(os.getenv("YICHE_READ_TIMEOUT_SECONDS", "20"))
YICHE_WALL_TIMEOUT = int(os.getenv("YICHE_WALL_TIMEOUT_SECONDS", "35"))
YICHE_ITEM_TIMEOUT = float(os.getenv("YICHE_ITEM_TIMEOUT_SECONDS", "120"))
YICHE_HEARTBEAT_INTERVAL = float(os.getenv("YICHE_HEARTBEAT_INTERVAL_SECONDS", "60"))
YICHE_CHECKPOINT_SCHEMA_VERSION = 2
YICHE_CHECKPOINT_STATE_COMPAT_VERSION = 1
IDENTITY_FIELDS = {"车系", "车型名称", "品牌", "年款", "数据来源", "易车车型ID", "易车上市状态", "车款ID"}
NON_SERIES_SLUGS = {
    "api", "article", "assets", "authenservice", "citybase", "current",
    "issue", "message", "videos",
}
YICHE_APPROVED_STATUS_TEXT = ("在售", "已上市")
YICHE_UNAPPROVED_STATUS_TEXT = ("未上市", "即将上市", "即将", "预售", "预测", "概念", "未定名")
LEGACY_INCIDENT = {
    "run_id": "30538098345",
    "artifact_id": "8761651220",
    "artifact_sha256": "e0c4585eab10ff8f04c17a91c5e0ef9aa64ca2a990e12f854f2ccc68a886f177",
    "checkpoint_sha256": "0eec901d948068cfdfdda9b3ea9bbb3732dd3988edb7cc55d53d8cf764879e9c",
    "logs_sha256": "6bff3254de0e70f7b87163c4d822034a5de78dc61d75cf80c7dbeec5b9b4fc90",
    "head_sha": "60e340af63f316785123ca38c958d7edfc570a4f",
    "seen_serial_ids_count": 1420,
    "seen_serial_ids_sha256": "b14570b0c720baed068e23b554ba678822062ffe54d27253cdf25ec5ac04d37f",
    "scanned_master_ids": [
        "9", "295", "619", "629", "819", "97", "92", "881", "555", "861", "848", "458",
        "423", "313", "268", "536", "634", "528", "654", "318", "719", "712", "496", "753",
        "766", "326", "393", "493", "473", "360", "319", "422", "474", "491", "499", "532",
        "650", "653", "656", "679", "693", "715", "720", "755", "786", "844", "15", "2",
        "3", "26", "127", "82", "163", "59", "5", "157", "85", "14", "195", "172", "135",
        "744", "683", "427", "456", "129", "236", "211", "216", "806", "411", "168", "746",
        "417", "352", "263", "671", "607", "286", "320", "282", "641", "548", "377",
    ],
    "pending_targets": [
        ("https://car.yiche.com/puravision/peizhi/", {"serial_id": "6394", "brand": "进口宾尼法利纳·新能源", "series": "Pura Vision"}),
        ("https://car.yiche.com/teorema/peizhi/", {"serial_id": "7598", "brand": "进口宾尼法利纳·新能源", "series": "Teorema"}),
        ("https://car.yiche.com/enigmagt/peizhi/", {"serial_id": "10765", "brand": "进口宾尼法利纳·新能源", "series": "Enigma GT"}),
        ("https://car.yiche.com/battista/peizhi/", {"serial_id": "6290", "brand": "进口宾尼法利纳·新能源", "series": "Battista"}),
        ("https://car.yiche.com/pininfarinab95/peizhi/", {"serial_id": "10434", "brand": "进口宾尼法利纳·新能源", "series": "Pininfarina B95"}),
        ("https://car.yiche.com/h2speed/peizhi/", {"serial_id": "6291", "brand": "进口宾尼法利纳·新能源", "series": "H2 Speed"}),
        ("https://car.yiche.com/viritechapricaleconcept/peizhi/", {"serial_id": "9635", "brand": "进口宾尼法利纳·新能源", "series": "Viritech Apricale Concept"}),
    ],
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


def contains_chinese(value):
    return bool(re.search(r"[\u4e00-\u9fff]", clean_text(value)))


def normalize_model_year(value, *, trusted_bare_year=False):
    text = clean_text(value)
    match = re.search(r"((?:19|20)\d{2})\s*款", text)
    if match:
        return match.group(1)
    if trusted_bare_year:
        match = re.fullmatch(r"(?:19|20)\d{2}", text) or re.search(r"((?:19|20)\d{2})", text)
        if match:
            return match.group(0) if match.lastindex is None else match.group(1)
    match = re.search(r"(?<!\d)(\d{2})\s*款", text)
    if match:
        short_year = int(match.group(1))
        return str(1900 + short_year if short_year >= 80 else 2000 + short_year)
    return ""


def is_positive_yiche_sale_status(value):
    text = clean_text(value)
    if not text or text == "-":
        return False
    if any(token in text for token in YICHE_UNAPPROVED_STATUS_TEXT):
        return False
    if any(token in text for token in YICHE_APPROVED_STATUS_TEXT):
        return True
    return text.lower() in {"1", "2", "3", "sale", "onsale", "on_sale", "sell", "selling", "listed"}


def parse_yiche_base_info(raw_value):
    if not isinstance(raw_value, dict):
        return {}
    base_info = raw_value.get("baseInfo") or raw_value.get("baseinfo")
    if isinstance(base_info, dict):
        return base_info
    if isinstance(base_info, str):
        try:
            parsed = json.loads(base_info)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def yiche_sale_status(raw_value):
    values = []
    if isinstance(raw_value, dict):
        base_info = parse_yiche_base_info(raw_value)
        for key in ("saleStatus", "saleStatusName", "marketStatus", "marketStatusName", "status", "statusName"):
            if key in base_info:
                values.append(clean_text(base_info.get(key)))
        for key in ("saleStatus", "saleStatusName", "marketStatus", "marketStatusName", "status", "statusName", "sale_state", "saleState", "sale_state_name"):
            if key in raw_value:
                values.append(clean_text(raw_value.get(key)))
    text = " ".join(value for value in values if value)
    if any(token in text for token in YICHE_UNAPPROVED_STATUS_TEXT):
        return "unapproved"
    if any(token in text for token in YICHE_APPROVED_STATUS_TEXT):
        return "approved"
    lowered = {value.lower() for value in values if value}
    if lowered & {"1", "2", "3", "sale", "onsale", "on_sale", "sell", "selling", "listed"}:
        return "approved"
    if lowered & {"0", "-1", "8", "presale", "pre_sale", "coming"}:
        return "unapproved"
    return "unknown"


def target_serial_id(target):
    if isinstance(target, dict):
        return clean_text(target.get("serial_id") or target.get("serialId"))
    return clean_text(target)


def target_brand(target):
    return clean_text(target.get("brand") if isinstance(target, dict) else "")


def target_series(target):
    return clean_text(target.get("series") if isinstance(target, dict) else "")


def make_target(serial_id, brand="", series=""):
    return {"serial_id": clean_text(serial_id), "brand": clean_text(brand), "series": clean_text(series)}


def normalize_key(key):
    key = clean_text(key).strip("：:")
    return HEADER_MAP.get(key, key)


class ItemStageTimeout(TimeoutError):
    pass


class CrawlInterrupted(Exception):
    def __init__(self, signum):
        self.signum = signum
        super().__init__(f"crawler interrupted by signal {signum}")


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@contextmanager
def wall_timeout(seconds, timeout_factory):
    if (
        seconds <= 0
        or not hasattr(signal, "SIGALRM")
        or threading.current_thread() is not threading.main_thread()
    ):
        yield
        return

    def timeout_handler(signum, frame):
        raise timeout_factory()

    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.getitimer(signal.ITIMER_REAL)
    started = time.monotonic()
    if previous_timer[0] and previous_timer[0] <= seconds:
        effective_seconds = previous_timer[0]
    else:
        effective_seconds = seconds
        signal.signal(signal.SIGALRM, timeout_handler)
    signal.setitimer(signal.ITIMER_REAL, effective_seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer[0]:
            elapsed = time.monotonic() - started
            remaining = previous_timer[0] - elapsed
            if remaining > 0:
                signal.setitimer(signal.ITIMER_REAL, remaining, previous_timer[1])


@contextmanager
def request_wall_timeout(seconds):
    with wall_timeout(seconds, lambda: requests.Timeout(f"request exceeded wall timeout {seconds}s")):
        yield


@contextmanager
def item_wall_timeout(seconds, stage):
    with wall_timeout(seconds, lambda: ItemStageTimeout(f"{stage} exceeded wall timeout {seconds}s")):
        yield


class CrawlObserver:
    def __init__(self, checkpoint_path="", heartbeat_interval=YICHE_HEARTBEAT_INTERVAL):
        self.checkpoint_path = checkpoint_path
        self.heartbeat_interval = heartbeat_interval
        self.started_at = time.monotonic()
        self.last_progress_at = self.started_at
        self.last_checkpoint_at = 0.0
        self.checkpoint_interval = heartbeat_interval if heartbeat_interval > 0 else 60
        self.state = {
            "format": "yiche-raw-progress",
            "schema_version": YICHE_CHECKPOINT_SCHEMA_VERSION,
            "state_compat_version": YICHE_CHECKPOINT_STATE_COMPAT_VERSION,
            "producer": {
                "repository": os.getenv("GITHUB_REPOSITORY", ""),
                "workflow": ".github/workflows/crawl-yiche.yml",
                "run_id": os.getenv("GITHUB_RUN_ID", ""),
                "run_attempt": os.getenv("GITHUB_RUN_ATTEMPT", ""),
                "head_sha": os.getenv("GITHUB_SHA", ""),
                "crawler_sha256": file_sha256(__file__),
            },
            "status": "starting",
            "stage": "initializing",
            "stats": {},
        }
        self.rows = []
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.thread = None

    def start(self):
        self.checkpoint(progress=True, force=True, status="running", stage="initializing")
        if self.heartbeat_interval > 0 and self.thread is None:
            self.thread = threading.Thread(target=self._heartbeat_loop, name="yiche-heartbeat", daemon=True)
            self.thread.start()

    def update(self, *, progress=False, rows=None, **state):
        with self.lock:
            self.state.update(state)
            if rows is not None:
                self.rows = [dict(row) for row in rows]
            if progress:
                self.last_progress_at = time.monotonic()

    def snapshot(self):
        with self.lock:
            payload = dict(self.state)
            payload["stats"] = dict(self.state.get("stats") or {})
            payload["rows"] = [dict(row) for row in self.rows]
            payload["updated_at"] = datetime.now(timezone.utc).isoformat()
            payload["elapsed_seconds"] = round(time.monotonic() - self.started_at, 3)
            payload["last_progress_age_seconds"] = round(time.monotonic() - self.last_progress_at, 3)
        return payload

    def persist(self):
        if not self.checkpoint_path:
            return
        payload = self.snapshot()
        temp_path = f"{self.checkpoint_path}.tmp"
        with open(temp_path, "w", encoding="utf-8") as checkpoint_file:
            json.dump(payload, checkpoint_file, ensure_ascii=False, indent=2)
            checkpoint_file.flush()
            os.fsync(checkpoint_file.fileno())
        os.replace(temp_path, self.checkpoint_path)

    def checkpoint(self, *, progress=False, rows=None, force=False, **state):
        self.update(progress=progress, rows=rows, **state)
        if not self.checkpoint_path:
            return
        now = time.monotonic()
        if not force and now - self.last_checkpoint_at < self.checkpoint_interval:
            return
        self.persist()
        self.last_checkpoint_at = now
        payload = self.snapshot()
        stats = payload.get("stats") or {}
        print(
            f"易车检查点: status={payload.get('status')} stage={payload.get('stage')} "
            f"attempted={stats.get('attempted', 0)} brands_scanned={payload.get('brands_scanned', 0)} "
            f"rows={len(payload.get('rows') or [])}",
            flush=True,
        )

    def emit_heartbeat(self):
        payload = self.snapshot()
        stats = payload.get("stats") or {}
        print(
            f"易车心跳: status={payload.get('status')} stage={payload.get('stage')} "
            f"attempted={stats.get('attempted', 0)} brands_scanned={payload.get('brands_scanned', 0)} "
            f"rows={len(payload.get('rows') or [])} elapsed_seconds={payload.get('elapsed_seconds')} "
            f"last_progress_age_seconds={payload.get('last_progress_age_seconds')}",
            flush=True,
        )

    def _heartbeat_loop(self):
        while not self.stop_event.wait(self.heartbeat_interval):
            self.emit_heartbeat()

    def close(self, status, *, rows=None, **state):
        self.stop_event.set()
        if self.thread is not None and self.thread is not threading.current_thread():
            self.thread.join(timeout=1)
        self.checkpoint(progress=True, rows=rows, force=True, status=status, **state)


def session_get(session, url, **kwargs):
    kwargs.setdefault("timeout", (YICHE_CONNECT_TIMEOUT, YICHE_READ_TIMEOUT))
    with request_wall_timeout(YICHE_WALL_TIMEOUT):
        return session.get(url, **kwargs)


def target_meta(value):
    if isinstance(value, dict):
        meta = {}
        for key, val in value.items():
            if isinstance(val, (set, list, tuple)):
                meta[key] = ",".join(clean_text(item) for item in val if clean_text(item))
            else:
                meta[key] = clean_text(val)
        return meta
    return {"serial_id": clean_text(value)}


def is_chinese_text(value):
    return contains_chinese(value)


def is_slug_series(value):
    text = clean_text(value)
    return bool(text and re.fullmatch(r"[a-z][a-z0-9-]*-?\d*", text) and not is_chinese_text(text))


def extract_sale_model_ids(html):
    soup = bs4.BeautifulSoup(html or "", "html.parser")
    sale_ids = set()
    for link in soup.find_all("a", href=True):
        text = clean_text(link.get_text(" "))
        href = link["href"]
        if "即将上市" in text or any(token in text for token in YICHE_UNAPPROVED_STATUS_TEXT):
            continue
        if not normalize_model_year(text):
            continue
        around = clean_text(str(link.parent))
        if any(token in around for token in YICHE_UNAPPROVED_STATUS_TEXT):
            continue
        for pattern in (r"/m(\d+)/", r"[?&](?:carId|carid|modelId|id)=(\d+)", r"-(\d+)\.html"):
            match = re.search(pattern, href)
            if match:
                sale_ids.add(match.group(1))
    for obj in walk(extract_json_objects(html)):
        if not isinstance(obj, dict):
            continue
        model_id = clean_text(obj.get("carId") or obj.get("carid") or obj.get("modelId") or obj.get("id"))
        model_name = clean_text(obj.get("carName") or obj.get("carname") or obj.get("name"))
        status = yiche_sale_status(obj)
        if model_id.isdigit() and normalize_model_year(model_name) and status == "approved":
            sale_ids.add(model_id)
    return sale_ids


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
    global LAST_DISCOVERED_MASTER_BRANDS
    discovered = {}
    discovered_brands = []
    candidate_pages = []
    for discovery_url in discovery_urls:
        try:
            print(f"发现易车车系 URL: {discovery_url}")
            html = fetch(session, discovery_url)
        except requests.RequestException as exc:
            print(f"  易车发现页抓取失败，跳过: {exc}")
            continue
        discovered.update(extract_series_targets(discovery_url, html))
        discovered_brands.extend(extract_master_brands(html))
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

    LAST_DISCOVERED_MASTER_BRANDS = list(dict.fromkeys(discovered_brands))
    trusted = {url: serial_id for url, serial_id in discovered.items() if serial_id}
    print(
        f"自动发现易车车系 URL {len(trusted)} 个，均含 serialId; "
        f"拒绝无 serialId 自动候选 {len(discovered) - len(trusted)} 个"
    )
    return trusted


def fetch(session, url):
    response = session_get(session, url)
    response.raise_for_status()
    return response.text


def fetch_yiche_api(session, endpoint, parameters):
    param = json.dumps(parameters, separators=(",", ":"))
    timestamp = str(int(time.time() * 1000))
    signature = hashlib.md5(
        f"cid={YICHE_API_CID}&param={param}{YICHE_API_SECRET}{timestamp}".encode()
    ).hexdigest()
    response = session_get(
        session,
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


def extract_json_objects(html):
    objects = []
    for match in re.finditer(r"<script[^>]*>(.*?)</script>", html or "", re.S | re.I):
        text = match.group(1).strip()
        if not text or "{" not in text:
            continue
        if text.startswith("{") or text.startswith("["):
            try:
                objects.append(json.loads(text))
            except json.JSONDecodeError:
                pass
    next_data = parse_next_data(html)
    if next_data is not None:
        objects.append(next_data)
    return objects


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
    for link in soup.find_all("a", href=True):
        match = re.search(r"[?&]mid=(\d+)", link["href"])
        name = clean_text(link.get_text(" "))
        if match and name and is_chinese_text(name) and match.group(1) not in seen:
            seen.add(match.group(1))
            brands.append((match.group(1), name))
    for link in soup.find_all("a", href=True):
        match = re.search(r"[?&]mid=(\d+)", link["href"])
        name = clean_text(link.get_text(" "))
        if match and name and is_chinese_text(name) and match.group(1) not in seen:
            seen.add(match.group(1))
            brands.append((match.group(1), name))
    for obj in walk(extract_json_objects(html)):
        master_id = clean_text(obj.get("masterId") or obj.get("masterid") or obj.get("id"))
        name = clean_text(obj.get("masterName") or obj.get("mastername") or obj.get("name"))
        if master_id.isdigit() and name and is_chinese_text(name) and master_id not in seen:
            seen.add(master_id)
            brands.append((master_id, name))
    return brands


def extract_master_brands_from_payload(payload):
    brands = []
    seen = set()
    for obj in walk(payload):
        master_id = clean_text(obj.get("masterId") or obj.get("masterid") or obj.get("id"))
        name = clean_text(obj.get("masterName") or obj.get("mastername") or obj.get("name"))
        if master_id.isdigit() and name and is_chinese_text(name) and master_id not in seen:
            seen.add(master_id)
            brands.append((master_id, name))
    return brands


def extract_approved_model_ids_from_obj(obj):
    ids = set()
    for child in walk(obj):
        if not isinstance(child, dict):
            continue
        model_id = clean_text(child.get("carId") or child.get("carid") or child.get("modelId") or child.get("id"))
        model_name = clean_text(child.get("carName") or child.get("carname") or child.get("name"))
        if model_id.isdigit() and normalize_model_year(model_name) and yiche_sale_status(child) == "approved":
            ids.add(model_id)
    return ids


def target_sale_model_ids(target):
    meta = target_meta(target)
    return {item for item in re.split(r"[,;，；\s]+", meta.get("sale_model_ids", "")) if item}


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
                target = {"serial_id": serial_id, "brand": brand, "series": name}
                sale_model_ids = extract_approved_model_ids_from_obj(item)
                if sale_model_ids:
                    target["sale_model_ids"] = sale_model_ids
                series.append((url, target))
    return series


class YicheDiscoveryFrontier:
    def __init__(
        self,
        session,
        max_brand_attempts=3,
        retry_backoff=1,
        max_init_attempts=3,
        initial_brands=None,
        legacy_scanned_master_ids=None,
        legacy_brands_total=0,
        legacy_seen_serial_ids_count=0,
        legacy_seen_serial_ids_sha256="",
    ):
        self.session = session
        self.brand_queue = list(initial_brands or [])
        self.retry_queue = []
        self.brand_attempts = {}
        self.max_brand_attempts = max_brand_attempts
        self.retry_backoff = retry_backoff
        self.max_init_attempts = max_init_attempts
        self.init_attempts = 0
        self.brands_total = 0
        self.brands_scanned = 0
        self.pages_scanned = 0
        self.seen_serial_ids = set()
        self.duplicate_serial_ids = 0
        self.brand_discovery_retries = 0
        self.brand_discovery_failures = 0
        self.last_failed_master_id = ""
        self.initialized = False
        self.legacy_scanned_master_ids = list(legacy_scanned_master_ids or [])
        self.legacy_seen_serial_ids_count = int(legacy_seen_serial_ids_count)
        self.legacy_seen_serial_ids_sha256 = legacy_seen_serial_ids_sha256
        if self.legacy_scanned_master_ids:
            self.brands_scanned = len(self.legacy_scanned_master_ids)
            self.pages_scanned = len(self.legacy_scanned_master_ids)
            self.brands_total = int(legacy_brands_total)

    def export_state(self):
        return {
            "brand_queue": [list(item) for item in self.brand_queue],
            "retry_queue": [[master_id, brand_name] for _, master_id, brand_name in self.retry_queue],
            "brand_attempts": dict(self.brand_attempts),
            "brands_total": self.brands_total,
            "brands_scanned": self.brands_scanned,
            "pages_scanned": self.pages_scanned,
            "seen_serial_ids": sorted(self.seen_serial_ids),
            "duplicate_serial_ids": self.duplicate_serial_ids,
            "brand_discovery_retries": self.brand_discovery_retries,
            "brand_discovery_failures": self.brand_discovery_failures,
            "last_failed_master_id": self.last_failed_master_id,
            "initialized": self.initialized,
        }

    def restore_state(self, state):
        self.brand_queue = [tuple(item) for item in state.get("brand_queue") or []]
        self.retry_queue = [(time.monotonic(), *item) for item in state.get("retry_queue") or []]
        self.brand_attempts = dict(state.get("brand_attempts") or {})
        self.brands_total = int(state.get("brands_total", 0))
        self.brands_scanned = int(state.get("brands_scanned", 0))
        self.pages_scanned = int(state.get("pages_scanned", 0))
        self.seen_serial_ids = set(state.get("seen_serial_ids") or [])
        self.duplicate_serial_ids = int(state.get("duplicate_serial_ids", 0))
        self.brand_discovery_retries = int(state.get("brand_discovery_retries", 0))
        self.brand_discovery_failures = int(state.get("brand_discovery_failures", 0))
        self.last_failed_master_id = clean_text(state.get("last_failed_master_id"))
        self.initialized = bool(state.get("initialized"))

    @property
    def exhausted(self):
        return self.initialized and not self.brand_queue and not self.retry_queue

    @property
    def remaining_brands(self):
        if self.legacy_scanned_master_ids and not self.initialized:
            return max(0, self.brands_total - self.brands_scanned)
        return len(self.brand_queue) + len(self.retry_queue)

    def _next_brand(self):
        now = time.monotonic()
        for index, (ready_at, master_id, brand_name) in enumerate(self.retry_queue):
            if ready_at <= now:
                self.retry_queue.pop(index)
                return master_id, brand_name
        if self.brand_queue:
            return self.brand_queue.pop(0)
        ready_at, master_id, brand_name = min(self.retry_queue)
        time.sleep(max(0, ready_at - now))
        self.retry_queue.remove((ready_at, master_id, brand_name))
        return master_id, brand_name

    def discover(self):
        if not self.initialized:
            errors = []
            if self.brand_queue:
                self.init_attempts = 0
            for attempt in range(1, self.max_init_attempts + 1):
                if self.brand_queue:
                    break
                self.init_attempts = attempt
                try:
                    self.init_attempts = attempt
                    html = fetch(self.session, DEFAULT_DISCOVERY_URLS[0])
                    self.brand_queue = extract_master_brands(html)
                    if not self.brand_queue:
                        payload = fetch_yiche_api(self.session, YICHE_MASTER_BRAND_API, {})
                        self.brand_queue = extract_master_brands_from_payload(payload)
                    if self.brand_queue:
                        break
                    errors.append("empty_brand_tree")
                except requests.RequestException as exc:
                    errors.append(f"{type(exc).__name__}:{exc}")
                if attempt < self.max_init_attempts:
                    self.brand_discovery_retries += 1
                    time.sleep(self.retry_backoff * (2 ** (attempt - 1)))
            self.brands_total = len(self.brand_queue)
            if self.legacy_scanned_master_ids:
                prefix = [master_id for master_id, _ in self.brand_queue[:len(self.legacy_scanned_master_ids)]]
                if prefix != self.legacy_scanned_master_ids:
                    raise RuntimeError("易车 legacy checkpoint 品牌前缀已变化，拒绝不确定恢复")
                seen_serial_ids = set()
                for master_id, _ in self.brand_queue[:len(self.legacy_scanned_master_ids)]:
                    payload = fetch_yiche_api(self.session, YICHE_BRAND_API, {"masterId": master_id})
                    seen_serial_ids.update(target_serial_id(target) for _, target in extract_brand_series(payload))
                seen_digest = hashlib.sha256(
                    ("\n".join(sorted(seen_serial_ids)) + "\n").encode()
                ).hexdigest()
                if (
                    len(seen_serial_ids) != self.legacy_seen_serial_ids_count
                    or seen_digest != self.legacy_seen_serial_ids_sha256
                ):
                    raise RuntimeError("易车 legacy checkpoint 历史 serialId 集合已变化，拒绝不确定恢复")
                self.seen_serial_ids = seen_serial_ids
                self.brand_queue = self.brand_queue[len(self.legacy_scanned_master_ids):]
                self.brands_scanned = len(self.legacy_scanned_master_ids)
                self.pages_scanned = len(self.legacy_scanned_master_ids)
            self.initialized = True
            print(
                f"易车可信发现初始化: brands_total={self.brands_total} source={DEFAULT_DISCOVERY_URLS[0]} "
                f"init_attempts={self.init_attempts} errors={errors[-3:]}"
            )
            if not self.brand_queue:
                raise RuntimeError("易车结构化品牌发现反复不可用，拒绝上传小样本 artifact")
        if self.exhausted:
            return {}
        master_id, brand_name = self._next_brand()
        attempt = self.brand_attempts.get(master_id, 0) + 1
        self.brand_attempts[master_id] = attempt
        try:
            payload = fetch_yiche_api(self.session, YICHE_BRAND_API, {"masterId": master_id})
        except requests.RequestException as exc:
            self.last_failed_master_id = master_id
            if attempt < self.max_brand_attempts:
                delay = self.retry_backoff * (2 ** (attempt - 1))
                self.retry_queue.append((time.monotonic() + delay, master_id, brand_name))
                self.brand_discovery_retries += 1
                outcome = f"retry_in={delay}s"
            else:
                self.brands_scanned += 1
                self.brand_discovery_failures += 1
                outcome = "retry_exhausted"
            print(
                f"易车品牌发现请求失败: master_id={master_id} attempt={attempt}/{self.max_brand_attempts} "
                f"exception={type(exc).__name__} outcome={outcome} remaining_brands={self.remaining_brands}"
            )
            return {}
        self.brands_scanned += 1
        self.pages_scanned += 1
        targets = {}
        for url, target in extract_brand_series(payload):
            serial_id = target_serial_id(target)
            if serial_id in self.seen_serial_ids:
                self.duplicate_serial_ids += 1
                continue
            self.seen_serial_ids.add(serial_id)
            targets[url] = target
        print(
            f"易车可信发现: brand={brand_name!r} master_id={master_id} brands_scanned={self.brands_scanned} "
            f"brands_total={self.brands_total} pages_scanned={self.pages_scanned} new_serial_ids={len(targets)} "
            f"unique_serial_ids={len(self.seen_serial_ids)} remaining_brands={self.remaining_brands}"
        )
        return targets


def extract_from_config_api(payload, target=None):
    rows = []
    target_brand_name = target_brand(target)
    target_series_name = target_series(target)
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
                base_info = parse_yiche_base_info(raw_value)
                value = clean_text(raw_value.get("value"))
                if (not value or value == "-") and raw_value.get("subList"):
                    value = clean_text(raw_value["subList"][0].get("value"))
                model_name = clean_text(
                    base_info.get("carName") or base_info.get("carname") or base_info.get("name")
                    or raw_value.get("carName") or raw_value.get("carname") or raw_value.get("name")
                )
                brand_name = clean_text(
                    base_info.get("brandName") or base_info.get("brandname") or base_info.get("masterName")
                    or base_info.get("mastername") or raw_value.get("brandName") or raw_value.get("brandname")
                    or rows[index].get("品牌") or target_brand_name
                )
                series_name = clean_text(
                    base_info.get("serialName") or base_info.get("serialname")
                    or raw_value.get("serialName") or raw_value.get("serialname") or rows[index].get("车系") or target_series_name
                )
                model_id = clean_text(
                    base_info.get("carId") or base_info.get("carid") or base_info.get("modelId")
                    or raw_value.get("carId") or raw_value.get("carid") or raw_value.get("modelId") or raw_value.get("id")
                )
                model_year = clean_text(base_info.get("year") or base_info.get("yearName") or base_info.get("modelYear"))
                sale_status = yiche_sale_status(raw_value)
                if model_name:
                    rows[index]["车型名称"] = model_name
                    rows[index].setdefault("年款", normalize_model_year(model_year, trusted_bare_year=True) or normalize_model_year(model_name))
                if brand_name:
                    rows[index]["品牌"] = brand_name
                if series_name:
                    rows[index]["车系"] = series_name
                if model_id:
                    rows[index]["车款ID"] = model_id
                previous_status = rows[index].get("易车上市状态")
                if sale_status in {"approved", "unapproved"} or not previous_status:
                    rows[index]["易车上市状态"] = sale_status
                if value and value != "-":
                    if key in {"车型", "车型名称", "车款"} or (group_index == 0 and item_index == 0):
                        rows[index]["车型名称"] = model_name or value
                    else:
                        rows[index][key] = value
    for row in rows:
        brand = clean_text(row.get("品牌") or row.get("厂商") or target_brand_name)
        series = clean_text(row.get("车系") or target_series_name)
        year = clean_text(row.get("年款")) or normalize_model_year(row.get("车型名称"))
        if brand and brand != "-":
            row["品牌"] = brand
        if series and series != "-":
            row["车系"] = series
        if year:
            row["年款"] = year
    return rows


def is_real_config_row(row):
    brand = clean_text(row.get("品牌"))
    series = clean_text(row.get("车系"))
    model = clean_text(row.get("车型名称"))
    year = clean_text(row.get("年款"))
    status = clean_text(row.get("易车上市状态"))
    return (
        brand not in {"", "-"}
        and series not in {"", "-"}
        and model not in {"", "-"}
        and bool(re.fullmatch(r"(?:19|20)\d{2}", year))
        and contains_chinese(brand)
        and contains_chinese(series)
        and status == "approved"
        and any(clean_text(value) for key, value in row.items() if key not in IDENTITY_FIELDS)
    )


def validate_real_rows(rows):
    return [row for row in rows if isinstance(row, dict) and is_real_config_row(row)]


def is_nonnegative_int(value):
    return type(value) is int and value >= 0


def validate_frontier_resume_state(frontier):
    required = {
        "brand_queue", "retry_queue", "brand_attempts", "brands_total", "brands_scanned",
        "pages_scanned", "seen_serial_ids", "duplicate_serial_ids", "brand_discovery_retries",
        "brand_discovery_failures", "last_failed_master_id", "initialized",
    }
    if not isinstance(frontier, dict) or set(frontier) != required:
        return False
    brand_queue = frontier["brand_queue"]
    retry_queue = frontier["retry_queue"]
    brand_attempts = frontier["brand_attempts"]
    seen_serial_ids = frontier["seen_serial_ids"]
    if (
        not isinstance(brand_queue, list)
        or not isinstance(retry_queue, list)
        or not isinstance(brand_attempts, dict)
        or not isinstance(seen_serial_ids, list)
    ):
        return False
    queue_ids = [item[0] for item in brand_queue if isinstance(item, list) and len(item) == 2]
    retry_ids = [item[0] for item in retry_queue if isinstance(item, list) and len(item) == 2]
    if (
        len(queue_ids) != len(brand_queue)
        or len(retry_ids) != len(retry_queue)
        or any(not clean_text(item[0]).isdigit() or not clean_text(item[1]) for item in brand_queue + retry_queue)
        or len(queue_ids) != len(set(queue_ids))
        or len(retry_ids) != len(set(retry_ids))
        or set(queue_ids) & set(retry_ids)
        or any(not clean_text(key).isdigit() or not is_nonnegative_int(value) for key, value in brand_attempts.items())
        or len(seen_serial_ids) != len(set(seen_serial_ids))
        or any(not clean_text(value).isdigit() for value in seen_serial_ids)
        or type(frontier["initialized"]) is not bool
        or not all(is_nonnegative_int(frontier[key]) for key in (
            "brands_total", "brands_scanned", "pages_scanned", "duplicate_serial_ids",
            "brand_discovery_retries", "brand_discovery_failures",
        ))
        or frontier["brands_scanned"] > frontier["brands_total"]
        or frontier["pages_scanned"] + frontier["brand_discovery_failures"] != frontier["brands_scanned"]
        or not isinstance(frontier["last_failed_master_id"], str)
        or (frontier["last_failed_master_id"] and not frontier["last_failed_master_id"].isdigit())
    ):
        return False
    return True


def load_resume_checkpoint(
    path,
    *,
    source_run_id,
    source_artifact_id,
    source_artifact_sha256,
    source_checkpoint_sha256,
    source_head_sha,
    source_crawler_sha256,
):
    with open(path, "rb") as checkpoint_file:
        checkpoint_bytes = checkpoint_file.read()
    actual_checkpoint_sha256 = hashlib.sha256(checkpoint_bytes).hexdigest()
    if actual_checkpoint_sha256 != source_checkpoint_sha256:
        raise ValueError("checkpoint SHA256 mismatch")
    try:
        payload = json.loads(checkpoint_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"checkpoint JSON invalid: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("checkpoint root must be an object")

    if "schema_version" not in payload:
        expected_identity = (
            LEGACY_INCIDENT["run_id"],
            LEGACY_INCIDENT["artifact_id"],
            LEGACY_INCIDENT["artifact_sha256"],
            LEGACY_INCIDENT["checkpoint_sha256"],
            LEGACY_INCIDENT["head_sha"],
        )
        actual_identity = (
            str(source_run_id),
            str(source_artifact_id),
            source_artifact_sha256.lower(),
            source_checkpoint_sha256.lower(),
            source_head_sha.lower(),
        )
        if actual_identity != expected_identity:
            raise ValueError("legacy checkpoint source identity is not allowlisted")
        required = {
            "status", "stage", "stats", "targets_discovered", "current_url", "brands_scanned",
            "remaining_brands", "queue_depth", "last_completed_url", "stop_reason", "rows",
            "updated_at", "elapsed_seconds", "last_progress_age_seconds",
        }
        if set(payload) != required:
            raise ValueError("legacy checkpoint schema mismatch")
        rows = payload.get("rows")
        if not isinstance(rows, list) or not rows or len(validate_real_rows(rows)) != len(rows):
            raise ValueError("legacy checkpoint rows failed the original quality gate")
        if (
            payload.get("stop_reason") != "safety_buffer_reached"
            or payload.get("brands_scanned") != 84
            or payload.get("remaining_brands") != 651
            or payload.get("queue_depth") != 7
            or payload.get("last_completed_url") != LEGACY_INCIDENT["pending_targets"][0][0]
        ):
            raise ValueError("legacy checkpoint progress identity mismatch")
        historical_stats = dict(payload.get("stats") or {})
        stats = dict(historical_stats)
        for key in ("attempted", "403", "failed"):
            if not isinstance(stats.get(key), int) or stats[key] <= 0:
                raise ValueError(f"legacy checkpoint invalid stats.{key}")
            stats[key] -= 1
        known_targets = {url: dict(target) for url, target in LEGACY_INCIDENT["pending_targets"]}
        return {
            "rows": [dict(row) for row in rows],
            "stats": stats,
            "historical_stats": historical_stats,
            "known_targets": known_targets,
            "pending": list(known_targets),
            "attempts": {},
            "completed": [],
            "targets_discovered": int(payload["targets_discovered"]),
            "legacy_frontier": {
                "scanned_master_ids": list(LEGACY_INCIDENT["scanned_master_ids"]),
                "brands_total": int(payload["brands_scanned"]) + int(payload["remaining_brands"]),
                "seen_serial_ids_count": LEGACY_INCIDENT["seen_serial_ids_count"],
                "seen_serial_ids_sha256": LEGACY_INCIDENT["seen_serial_ids_sha256"],
                "logs_sha256": LEGACY_INCIDENT["logs_sha256"],
            },
            "source": {
                "run_id": str(source_run_id),
                "artifact_id": str(source_artifact_id),
                "artifact_sha256": source_artifact_sha256.lower(),
                "checkpoint_sha256": source_checkpoint_sha256.lower(),
                "head_sha": source_head_sha.lower(),
                "migration": "legacy-30538098345-safe-boundary-v1",
            },
        }

    if (
        payload.get("format") != "yiche-raw-progress"
        or payload.get("schema_version") != YICHE_CHECKPOINT_SCHEMA_VERSION
        or payload.get("state_compat_version") != YICHE_CHECKPOINT_STATE_COMPAT_VERSION
    ):
        raise ValueError("checkpoint schema/state compatibility mismatch")
    producer = payload.get("producer") or {}
    if (
        producer.get("repository") != os.getenv("GITHUB_REPOSITORY", "Fatty911/crawl_cars")
        or str(producer.get("run_id")) != str(source_run_id)
        or producer.get("head_sha") != source_head_sha
        or producer.get("workflow") != ".github/workflows/crawl-yiche.yml"
        or producer.get("crawler_sha256") != source_crawler_sha256
    ):
        raise ValueError("checkpoint producer identity mismatch")
    resume = payload.get("resume_state")
    rows = payload.get("rows")
    if not isinstance(resume, dict) or not isinstance(rows, list) or not rows:
        raise ValueError("checkpoint resume state missing")
    if len(validate_real_rows(rows)) != len(rows):
        raise ValueError("checkpoint rows failed the original quality gate")
    known_targets = resume.get("known_targets")
    pending = resume.get("pending")
    completed = resume.get("completed")
    attempts = resume.get("attempts")
    stats = resume.get("stats")
    frontier = resume.get("frontier")
    legacy_frontier = resume.get("legacy_frontier")
    if (
        not isinstance(known_targets, dict)
        or any(
            not isinstance(url, str)
            or normalize_series_url(url) != url
            or not isinstance(target, dict)
            for url, target in known_targets.items()
        )
        or not isinstance(pending, list)
        or any(not isinstance(url, str) for url in pending)
        or not isinstance(completed, list)
        or any(not isinstance(url, str) for url in completed)
        or not isinstance(attempts, dict)
        or not isinstance(stats, dict)
        or any(not is_nonnegative_int(value) for value in stats.values())
        or not is_nonnegative_int(stats.get("attempted"))
        or stats["attempted"] <= 0
        or len(pending) != len(set(pending))
        or len(completed) != len(set(completed))
        or not set(pending).issubset(known_targets)
        or not set(completed).issubset(known_targets)
        or set(pending) & set(completed)
        or not set(attempts).issubset(known_targets)
        or any(not is_nonnegative_int(value) or value <= 0 for value in attempts.values())
        or not validate_frontier_resume_state(frontier)
        or not isinstance(legacy_frontier, dict)
    ):
        raise ValueError("checkpoint resume state invariants failed")
    if legacy_frontier and legacy_frontier != {
        "scanned_master_ids": LEGACY_INCIDENT["scanned_master_ids"],
        "brands_total": 735,
        "seen_serial_ids_count": LEGACY_INCIDENT["seen_serial_ids_count"],
        "seen_serial_ids_sha256": LEGACY_INCIDENT["seen_serial_ids_sha256"],
        "logs_sha256": LEGACY_INCIDENT["logs_sha256"],
    }:
        raise ValueError("checkpoint legacy frontier identity mismatch")
    result = dict(resume)
    result["rows"] = [dict(row) for row in rows]
    result["source"] = {
        "run_id": str(source_run_id),
        "artifact_id": str(source_artifact_id),
        "artifact_sha256": source_artifact_sha256.lower(),
        "checkpoint_sha256": source_checkpoint_sha256.lower(),
        "head_sha": source_head_sha.lower(),
    }
    return result


def identity_quality_counts(rows):
    dict_rows = [row for row in rows if isinstance(row, dict)]
    return {
        "invalid_brand": sum(clean_text(row.get("品牌")) in {"", "-"} or not contains_chinese(row.get("品牌")) for row in dict_rows),
        "invalid_model_name": sum(clean_text(row.get("车型名称")) in {"", "-"} for row in dict_rows),
        "invalid_series": sum(clean_text(row.get("车系")) in {"", "-"} or not contains_chinese(row.get("车系")) for row in dict_rows),
        "invalid_year": sum(not re.fullmatch(r"(?:19|20)\d{2}", clean_text(row.get("年款"))) for row in dict_rows),
        "unapproved_status": sum(clean_text(row.get("易车上市状态")) != "approved" for row in dict_rows),
    }


def add_quality_counts(stats, rows):
    quality = identity_quality_counts(rows)
    for key, value in quality.items():
        stats[key] = stats.get(key, 0) + value


def series_home_url(page_url):
    parsed = urlparse(normalize_series_url(page_url).replace("/peizhi/", "/"))
    return f"{parsed.scheme or 'https'}://{parsed.netloc or 'car.yiche.com'}{parsed.path}"


def mobile_series_home_url(page_url):
    parsed = urlparse(series_home_url(page_url))
    return f"https://car.m.yiche.com{parsed.path}"


def extract_sale_model_refs(html):
    sale_ids = extract_sale_model_ids(html)
    sale_names = set()
    soup = bs4.BeautifulSoup(html or "", "html.parser")
    text = clean_text(soup.get_text(" "))
    for marker in ("即将上市", "停售车款", "停售"):
        if marker in text:
            text = text.split(marker, 1)[0]
    for match in re.finditer(r"((?:19|20)?\d{2}款[^|<>\n]{1,60}?)(?:图片|参数|指导价|\d+\.\d+万)", text):
        name = clean_text(match.group(1))
        if name and not any(token in name for token in YICHE_UNAPPROVED_STATUS_TEXT):
            sale_names.add(name)
    for obj in walk(extract_json_objects(html)):
        if not isinstance(obj, dict):
            continue
        if yiche_sale_status(obj) == "approved":
            name = clean_text(obj.get("carName") or obj.get("carname") or obj.get("name"))
            if name:
                sale_names.add(name)
    return sale_ids, sale_names


def approve_rows_from_sale_page(session, page_url, rows, target=None):
    sale_ids = target_sale_model_ids(target)
    sale_names = set()
    errors = []
    status_values = {clean_text(row.get("易车上市状态")) for row in rows}
    needs_sale_page = "unknown" in status_values or "" in status_values
    if not sale_ids and needs_sale_page:
        for candidate_url in (series_home_url(page_url), mobile_series_home_url(page_url)):
            try:
                ids, names = extract_sale_model_refs(fetch(session, candidate_url))
            except requests.RequestException as exc:
                errors.append(f"{candidate_url} {type(exc).__name__}: {exc}")
                continue
            sale_ids.update(ids)
            sale_names.update(names)
            if sale_ids or sale_names:
                break
    if errors and not (sale_ids or sale_names):
        print(f"  易车在售车款页抓取失败，使用 API 状态字段判定: {'; '.join(errors[-2:])}")
    approved = []
    rejected = 0
    for row in rows:
        model_id = clean_text(row.get("车款ID"))
        model_name = clean_text(row.get("车型名称"))
        if sale_ids or sale_names:
            row["易车上市状态"] = "approved" if (model_id and model_id in sale_ids) or model_name in sale_names else "unapproved"
        if is_real_config_row(row):
            approved.append(row)
        else:
            rejected += 1
    print(
        f"  易车上市过滤: sale_model_ids={len(sale_ids)} sale_model_names={len(sale_names)} approved_rows={len(approved)} "
        f"rejected_rows={rejected}"
    )
    return approved

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


def enrich_identity(rows, url, target=None):
    series_name = target_series(target)
    brand_name = target_brand(target)
    for row in rows:
        if brand_name:
            row.setdefault("品牌", brand_name)
        if series_name:
            row.setdefault("车系", series_name)
        row.setdefault("年款", normalize_model_year(row.get("车型名称")))
        status_value = row.get("易车上市状态") or row.get("上市状态") or row.get("状态")
        if status_value:
            status = yiche_sale_status({"saleStatusName": status_value})
            if status in {"approved", "unapproved"}:
                row.setdefault("易车上市状态", status)
        row.setdefault("数据来源", "易车")
    return rows


def crawl(
    targets,
    delay,
    time_limit=0,
    *,
    discovery_callback=None,
    max_attempts=1,
    max_targets=0,
    finish_buffer=60,
    start_time=None,
    item_timeout=YICHE_ITEM_TIMEOUT,
    heartbeat_interval=YICHE_HEARTBEAT_INTERVAL,
    checkpoint_path="",
    observer=None,
    resume_state=None,
    resume_smoke_targets=0,
):
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    resume_state = dict(resume_state or {})
    all_rows = [dict(row) for row in resume_state.get("rows") or []]
    stats = dict(resume_state.get("stats") or {
        "attempted": 0, "success": 0, "403": 0, "429": 0, "failed": 0, "degraded_identity": 0,
    })
    start = start_time if start_time is not None else time.monotonic()
    deadline = start + time_limit if time_limit else 0
    known_targets = {
        url: target_meta(value) for url, value in (resume_state.get("known_targets") or {}).items()
    }
    incoming_targets = dict(targets) if isinstance(targets, dict) else {url: {"serial_id": ""} for url in targets}
    for url, value in incoming_targets.items():
        known_targets.setdefault(url, target_meta(value))
    if max_targets > 0:
        known_targets = dict(list(known_targets.items())[:max_targets])
    pending = list(resume_state["pending"]) if "pending" in resume_state else list(known_targets)
    known_serial_ids = {target_serial_id(value) for value in known_targets.values() if target_serial_id(value)}
    attempts = {url: int(value) for url, value in (resume_state.get("attempts") or {}).items()}
    completed = set(resume_state.get("completed") or [])
    idle_discovery_rounds = 0
    stop_reason = "target_exhausted"
    for key in (
        "attempted", "success", "403", "429", "failed", "degraded_identity",
        "discovery_rounds", "discovery_network_errors", "retry_attempted", "item_timeouts",
        "invalid_brand", "invalid_model_name", "invalid_series", "invalid_year", "unapproved_status",
    ):
        stats.setdefault(key, 0)
    targets_discovered_count = int(resume_state.get("targets_discovered", len(known_targets)))
    baseline_attempted = int(stats.get("attempted", 0))

    def checkpoint_resume_state():
        frontier_state = discovery_callback.export_state() if hasattr(discovery_callback, "export_state") else {}
        legacy_frontier = resume_state.get("legacy_frontier") or {}
        return {
            "stats": dict(stats),
            "known_targets": {url: target_meta(value) for url, value in known_targets.items()},
            "pending": list(pending),
            "attempts": dict(attempts),
            "completed": sorted(completed),
            "targets_discovered": targets_discovered_count,
            "frontier": frontier_state,
            "legacy_frontier": legacy_frontier if not frontier_state.get("initialized") else {},
            "historical_stats": dict(resume_state.get("historical_stats") or {}),
        }

    owns_observer = observer is None
    observer = observer or CrawlObserver(checkpoint_path, heartbeat_interval)
    observer.update(
        rows=all_rows,
        stats=stats,
        targets_discovered=targets_discovered_count,
        resume_source=resume_state.get("source") or {},
        resume_state=checkpoint_resume_state(),
        brands_scanned=getattr(discovery_callback, "brands_scanned", 0),
        remaining_brands=getattr(discovery_callback, "remaining_brands", 0),
    )
    observer.start()
    if resume_state:
        print(
            f"易车恢复: attempted={baseline_attempted} rows={len(all_rows)} "
            f"pending={len(pending)} targets_discovered={targets_discovered_count} "
            f"source_run={resume_state.get('source', {}).get('run_id', '-')}",
            flush=True,
        )

    print(
        f"易车预算: budget_seconds={time_limit} finish_buffer_seconds={finish_buffer} item_timeout_seconds={item_timeout} "
        f"deadline_monotonic={deadline:.3f} targets_initial={len(known_targets)} max_attempts={max_attempts}"
    )
    while pending or (
        discovery_callback
        and (
            (hasattr(discovery_callback, "discover") and not discovery_callback.exhausted)
            or (not hasattr(discovery_callback, "discover") and idle_discovery_rounds < 2)
        )
    ):
        if resume_smoke_targets > 0 and stats["attempted"] - baseline_attempted >= resume_smoke_targets:
            stop_reason = "resume_smoke_limit_reached"
            break
        if deadline and time.monotonic() >= deadline - finish_buffer:
            stop_reason = "safety_buffer_reached"
            break
        if not pending and max_targets > 0 and len(known_targets) >= max_targets:
            stop_reason = "max_targets_reached"
            break
        if not pending and hasattr(discovery_callback, "discover"):
            stats["discovery_rounds"] += 1
            observer.update(
                stage="discovery",
                stats=stats,
                brands_scanned=getattr(discovery_callback, "brands_scanned", 0),
                remaining_brands=getattr(discovery_callback, "remaining_brands", 0),
            )
            try:
                discovered = discovery_callback.discover()
            except requests.RequestException as exc:
                stats["discovery_network_errors"] += 1
                print(f"易车发现回调网络异常，保留已有数据并继续: {type(exc).__name__}: {exc}")
                if delay:
                    time.sleep(min(delay, 1))
                continue
            except RuntimeError as exc:
                stop_reason = "discovery_unavailable_fail_closed" if max_targets == 0 else "discovery_unavailable_after_seed_rows"
                print(f"易车结构化发现不可用: stop_reason={stop_reason} seed_rows={len(all_rows)} error={exc}")
                if resume_state:
                    observer.checkpoint(
                        force=True,
                        rows=all_rows,
                        status="partial",
                        stage="discovery",
                        stop_reason="resume_discovery_identity_mismatch",
                        stats=stats,
                        queue_depth=len(pending),
                        targets_discovered=targets_discovered_count,
                        resume_state=checkpoint_resume_state(),
                    )
                    raise
                if max_targets == 0:
                    all_rows = []
                break
            added = 0
            for discovered_url, discovered_value in discovered.items():
                if max_targets > 0 and len(known_targets) >= max_targets:
                    break
                discovered_id = target_serial_id(discovered_value)
                if discovered_id in known_serial_ids:
                    continue
                normalized = normalize_series_url(discovered_url)
                known_targets[normalized] = target_meta(discovered_value)
                known_serial_ids.add(discovered_id)
                pending.append(normalized)
                added += 1
            targets_discovered_count += added
            print(
                f"易车发现队列: round={stats['discovery_rounds']} new_serial_ids={added} "
                f"queue_depth={len(pending)} unique_serial_ids={len(known_serial_ids)}"
            )
            observer.checkpoint(
                progress=True,
                rows=all_rows,
                status="running",
                stage="discovery_complete",
                stats=stats,
                brands_scanned=getattr(discovery_callback, "brands_scanned", 0),
                remaining_brands=getattr(discovery_callback, "remaining_brands", 0),
                queue_depth=len(pending),
                targets_discovered=targets_discovered_count,
                resume_state=checkpoint_resume_state(),
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
                    if max_targets > 0 and len(known_targets) >= max_targets:
                        break
                    known_targets[normalized] = discovered_id if isinstance(discovered_id, dict) else make_target(discovered_id)
                    pending.append(normalized)
                    added += 1
            idle_discovery_rounds = 0 if added else idle_discovery_rounds + 1
            print(f"易车增量发现: round={stats['discovery_rounds']} discovered={len(discovered)} added_or_enriched={added}")
        if not pending:
            continue
        url = pending.pop(0)
        if url in completed:
            continue
        meta = target_meta(known_targets.get(url, {}))
        serial_id = meta.get("serial_id", "")
        attempts[url] = attempts.get(url, 0) + 1
        if attempts[url] > 1:
            stats["retry_attempted"] += 1
        target_succeeded = False
        target_timed_out = False
        page_url = normalize_series_url(url)
        stats["attempted"] += 1
        observer.update(
            stage="item",
            current_url=page_url,
            stats=stats,
            brands_scanned=getattr(discovery_callback, "brands_scanned", 0),
            remaining_brands=getattr(discovery_callback, "remaining_brands", 0),
            queue_depth=len(pending),
        )
        print(f"抓取易车: {page_url}")
        item_timeout_context = item_wall_timeout(item_timeout, f"item {page_url}")
        item_timeout_context.__enter__()
        try:
            html = ""
            rows = []
            if serial_id:
                try:
                    api_rows = enrich_identity(extract_from_config_api(fetch_config_api(session, serial_id), meta), page_url, meta)
                    real_rows = approve_rows_from_sale_page(session, page_url, api_rows, meta)
                    add_quality_counts(stats, api_rows)
                    rows = api_rows
                except requests.RequestException as api_exc:
                    print(f"  易车配置 API 抓取失败，改用页面限时兜底: {api_exc}")
                    real_rows = []
            if not serial_id or not real_rows:
                html = fetch(session, page_url)
                serial_id = serial_id or extract_serial_id(html)
                data = parse_next_data(html)
                rows = extract_from_next_data(data) if data else []
                if not rows:
                    rows = extract_from_tables(html)
                if not rows:
                    rows = extract_identity_from_meta(html)
                rows = enrich_identity(rows, page_url, meta)
                add_quality_counts(stats, rows)
                real_rows = validate_real_rows(rows)
                if not real_rows and serial_id:
                    api_rows = enrich_identity(extract_from_config_api(fetch_config_api(session, serial_id), meta), page_url, meta)
                    real_rows = approve_rows_from_sale_page(session, page_url, api_rows, meta)
                    add_quality_counts(stats, api_rows)
            if real_rows:
                target_succeeded = True
                stats["success"] += 1
                print(f"  提取真实配置 {len(real_rows)} 条")
                print(f"  真实配置样例: 车型名称={real_rows[0]['车型名称']!r} 配置字段={list(key for key in real_rows[0] if key not in IDENTITY_FIELDS)[:5]}")
                all_rows.extend(real_rows)
            else:
                stats["degraded_identity"] += len(rows) or 1
                page_title = clean_text(bs4.BeautifulSoup(html, "html.parser").title) if not serial_id else ""
                print(f"  仅获得降级身份，未计入真实配置 (html_bytes={len(html.encode())} title={page_title!r})")
        except ItemStageTimeout as exc:
            target_timed_out = True
            stats["item_timeouts"] += 1
            stats["failed"] += 1
            print(f"  易车阶段超时: url={page_url} timeout_seconds={item_timeout} error={exc}")
        except requests.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else None
            if status_code in {403, 429}:
                stats[str(status_code)] += 1
            try:
                api_rows = enrich_identity(extract_from_config_api(fetch_config_api(session, serial_id), meta), page_url, meta) if serial_id else []
                real_rows = approve_rows_from_sale_page(session, page_url, api_rows, meta)
                add_quality_counts(stats, api_rows)
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
        finally:
            item_timeout_context.__exit__(None, None, None)
        if delay:
            time.sleep(delay)
        if target_succeeded:
            completed.add(url)
        elif not target_timed_out and attempts[url] < max_attempts and serial_id:
            pending.append(url)
        observer.checkpoint(
            progress=True,
            rows=all_rows,
            status="running",
            stage="item_complete",
            current_url="",
            last_completed_url=page_url,
            stats=stats,
            brands_scanned=getattr(discovery_callback, "brands_scanned", 0),
            remaining_brands=getattr(discovery_callback, "remaining_brands", 0),
            queue_depth=len(pending),
            targets_discovered=targets_discovered_count,
            resume_state=checkpoint_resume_state(),
        )
        if not pending and discovery_callback and not hasattr(discovery_callback, "discover") and idle_discovery_rounds < 2:
            stats["discovery_rounds"] += 1
            discovered = discovery_callback()
            added = 0
            for discovered_url, discovered_id in discovered.items():
                normalized = normalize_series_url(discovered_url)
                previous_id = known_targets.get(normalized, "")
                if normalized not in known_targets:
                    if max_targets > 0 and len(known_targets) >= max_targets:
                        break
                    known_targets[normalized] = discovered_id if isinstance(discovered_id, dict) else make_target(discovered_id)
                    pending.append(normalized)
                    added += 1
                elif discovered_id and not previous_id:
                    known_targets[normalized] = discovered_id if isinstance(discovered_id, dict) else make_target(discovered_id)
                    if normalized not in completed and attempts.get(normalized, 0) < max_attempts:
                        pending.append(normalized)
                        added += 1
            idle_discovery_rounds = 0 if added else idle_discovery_rounds + 1
            print(f"易车增量发现: round={stats['discovery_rounds']} discovered={len(discovered)} added_or_enriched={added}")
    deduped_rows = []
    if (
        stop_reason == "target_exhausted"
        and discovery_callback
        and hasattr(discovery_callback, "discover")
        and discovery_callback.exhausted
        and not pending
    ):
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
        + f" targets_discovered={targets_discovered_count} unique_serial_ids_attempted={len({target_serial_id(known_targets[url]) for url in attempts if target_serial_id(known_targets.get(url, {}))})} "
        + f"brands_total={getattr(discovery_callback, 'brands_total', 0)} brands_scanned={getattr(discovery_callback, 'brands_scanned', 0)} "
        + f"remaining_brands={getattr(discovery_callback, 'remaining_brands', 0)} pages_scanned={getattr(discovery_callback, 'pages_scanned', 0)} "
        + f"brand_discovery_retries={getattr(discovery_callback, 'brand_discovery_retries', 0)} "
        + f"brand_discovery_failures={getattr(discovery_callback, 'brand_discovery_failures', 0)} "
        + f"last_failed_master_id={getattr(discovery_callback, 'last_failed_master_id', '') or '-'} queue_depth={len(pending)} real_rows={len(deduped_rows)} "
        + f"elapsed_seconds={time.monotonic() - start:.1f} remaining_seconds={max(0, deadline - time.monotonic()):.1f} "
        + f"stop_reason={stop_reason}"
    )
    final_status = "partial" if stop_reason in {"safety_buffer_reached", "resume_smoke_limit_reached"} else "completed"
    if owns_observer:
        observer.close(
            final_status,
            rows=deduped_rows,
            stage="finished",
            stop_reason=stop_reason,
            stats=stats,
            brands_scanned=getattr(discovery_callback, "brands_scanned", 0),
            remaining_brands=getattr(discovery_callback, "remaining_brands", 0),
            queue_depth=len(pending),
            targets_discovered=targets_discovered_count,
            resume_state=checkpoint_resume_state(),
        )
    else:
        observer.update(
            progress=True,
            rows=deduped_rows,
            stage="finished",
            stop_reason=stop_reason,
            stats=stats,
            brands_scanned=getattr(discovery_callback, "brands_scanned", 0),
            remaining_brands=getattr(discovery_callback, "remaining_brands", 0),
            queue_depth=len(pending),
            targets_discovered=targets_discovered_count,
            resume_state=checkpoint_resume_state(),
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
    parser.add_argument("--item-timeout", type=float, default=YICHE_ITEM_TIMEOUT, help="单车系阶段墙钟上限(秒)")
    parser.add_argument("--heartbeat-interval", type=float, default=YICHE_HEARTBEAT_INTERVAL, help="心跳间隔(秒)")
    parser.add_argument("--checkpoint", default=os.getenv("YICHE_CHECKPOINT_PATH", "yiche_checkpoint.json"), help="运行检查点路径")
    parser.add_argument("--resume-checkpoint", default="", help="已验证的恢复检查点路径")
    parser.add_argument("--resume-source-run-id", default="")
    parser.add_argument("--resume-source-artifact-id", default="")
    parser.add_argument("--resume-source-artifact-sha256", default="")
    parser.add_argument("--resume-source-checkpoint-sha256", default="")
    parser.add_argument("--resume-source-head-sha", default="")
    parser.add_argument("--resume-source-crawler-sha256", default="")
    parser.add_argument("--resume-smoke-targets", type=int, default=0)
    args = parser.parse_args()

    resume_state = None
    if args.resume_checkpoint:
        resume_state = load_resume_checkpoint(
            args.resume_checkpoint,
            source_run_id=args.resume_source_run_id,
            source_artifact_id=args.resume_source_artifact_id,
            source_artifact_sha256=args.resume_source_artifact_sha256,
            source_checkpoint_sha256=args.resume_source_checkpoint_sha256,
            source_head_sha=args.resume_source_head_sha,
            source_crawler_sha256=args.resume_source_crawler_sha256,
        )
        if args.max_series != 0:
            raise SystemExit("恢复模式不接受 --max-series；短烟测请使用 --resume-smoke-targets")
    urls = [] if resume_state else load_urls(args)
    targets = {} if resume_state else {normalize_series_url(url): serial_id_from_url(url) for url in urls}
    if not targets and not resume_state:
        discovery_urls = args.discover_url or split_urls(os.getenv("YICHE_DISCOVERY_URLS", "")) or DEFAULT_DISCOVERY_URLS
        session = requests.Session()
        session.headers.update({"User-Agent": "Mozilla/5.0"})
        targets = {normalize_series_url(url): make_target(serial_id_from_url(url)) for url in DEFAULT_SERIES_URLS}
        targets.update(discover_series_urls(session, discovery_urls, args.max_discovery_pages))
    if args.max_series > 0:
        targets = dict(list(targets.items())[:args.max_series])
    if not targets and not resume_state:
        print("未配置且未发现易车车系 URL，生成空数据文件。可通过 --url、--url-file、YICHE_SERIES_URLS 或 YICHE_DISCOVERY_URLS 配置。")
    discovery_callback = None
    if resume_state:
        session = requests.Session()
        session.headers.update({"User-Agent": "Mozilla/5.0"})
        legacy_frontier = resume_state.get("legacy_frontier") or {}
        discovery_callback = YicheDiscoveryFrontier(
            session,
            legacy_scanned_master_ids=legacy_frontier.get("scanned_master_ids"),
            legacy_brands_total=legacy_frontier.get("brands_total", 0),
            legacy_seen_serial_ids_count=legacy_frontier.get("seen_serial_ids_count", 0),
            legacy_seen_serial_ids_sha256=legacy_frontier.get("seen_serial_ids_sha256", ""),
        )
        if resume_state.get("frontier"):
            discovery_callback.restore_state(resume_state["frontier"])
    elif not urls:
        discovery_callback = YicheDiscoveryFrontier(session, initial_brands=LAST_DISCOVERED_MASTER_BRANDS)
    observer = CrawlObserver(args.checkpoint, args.heartbeat_interval)
    previous_handlers = {}

    def interrupt_handler(signum, frame):
        raise CrawlInterrupted(signum)

    for signal_name in ("SIGINT", "SIGTERM"):
        if hasattr(signal, signal_name):
            signum = getattr(signal, signal_name)
            previous_handlers[signum] = signal.signal(signum, interrupt_handler)
    try:
        rows = crawl(
            targets,
            args.delay,
            args.time_limit,
            discovery_callback=discovery_callback,
            max_attempts=2 if args.max_series == 0 else 1,
            max_targets=args.max_series,
            start_time=started_at,
            item_timeout=args.item_timeout,
            observer=observer,
            resume_state=resume_state,
            resume_smoke_targets=args.resume_smoke_targets,
        ) if targets or resume_state else []
    except CrawlInterrupted as exc:
        observer.close("cancelled", stage="interrupted", signal=exc.signum)
        print(f"易车爬虫收到取消信号 {exc.signum}，已刷新检查点", flush=True)
        return 128 + exc.signum
    except BaseException:
        observer.close("failed", stage="failed")
        raise
    else:
        stop_reason = observer.state.get("stop_reason")
        final_status = "partial" if stop_reason in {"safety_buffer_reached", "resume_smoke_limit_reached"} else "completed"
        observer.close(final_status, rows=rows, stage="finished")
    finally:
        for signum, previous_handler in previous_handlers.items():
            signal.signal(signum, previous_handler)
    output = args.output or f"yiche_{date.today().strftime('%Y%m%d')}.json"
    if not rows:
        observer.close("failed", rows=rows, stage="quality_gate_failed", stop_reason="no_real_rows")
        if os.path.exists(output):
            os.remove(output)
        raise SystemExit("未抓到任何具有真实车型身份和配置字段的易车数据，拒绝生成输出")
    with open(output, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    print(f"易车数据已写入 {output}，共 {len(rows)} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

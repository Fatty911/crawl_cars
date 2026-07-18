import os
import sys
import shutil
import csv
import bs4
import requests
import time
import random
import json
import re
import argparse
from datetime import date, datetime
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
from selenium import webdriver
from selenium.webdriver.chrome.service import Service

parser = argparse.ArgumentParser(description="汽车之家爬虫")
parser.add_argument("--step", type=int, choices=[1, 2, 3, 4, 5, 6], help="运行指定步骤")
parser.add_argument(
    "--time-limit", type=int, default=0, help="每步最大运行时间(秒)，0表示不限制"
)
parser.add_argument(
    "--max-cars", type=int, default=0, help="第一步最多爬取车型数，0表示不限制"
)
parser.add_argument(
    "--auto", action="store_true", help="全自动模式：跑完自动进入下一步"
)
parser.add_argument(
    "--incremental", action="store_true", help="增量模式：只爬取新增车型，跳过已存在的"
)
args = parser.parse_args()

MAX_TIME_PER_STEP = args.time_limit
MAX_CARS_PER_RUN = args.max_cars
AUTO_MODE = args.auto
INCREMENTAL_MODE = args.incremental
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"
DEBUG_OUTPUT_MAX_ROWS = int(os.getenv("DEBUG_OUTPUT_MAX_ROWS", "30"))
CRAWL_MIN_DELAY_SECONDS = float(os.getenv("CRAWL_MIN_DELAY_SECONDS", "8"))
CRAWL_MAX_DELAY_SECONDS = float(os.getenv("CRAWL_MAX_DELAY_SECONDS", "20"))
if CRAWL_MAX_DELAY_SECONDS < CRAWL_MIN_DELAY_SECONDS:
    CRAWL_MAX_DELAY_SECONDS = CRAWL_MIN_DELAY_SECONDS


# 设置代码目录与隔离的运行状态目录
working_dir = os.path.dirname(os.path.abspath(__file__))
repo_dir = os.path.dirname(working_dir)
state_dir = os.path.join(repo_dir, "crawl_state", "autohome")

# 创建目录
html_dir = os.path.join(state_dir, "html")
newhtml_dir = os.path.join(state_dir, "newhtml")
json_dir = os.path.join(state_dir, "json")
content_dir = os.path.join(state_dir, "content")
newjson_dir = os.path.join(state_dir, "newjson")
exception_dir = os.path.join(state_dir, "exception")
series_queue_file = os.path.join(working_dir, "data", "autohome_series_queue.json")
target_manifest_file = os.path.join(state_dir, "target_manifest.json")

for dir_path in [
    html_dir,
    newhtml_dir,
    json_dir,
    content_dir,
    newjson_dir,
    exception_dir,
]:
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

CURRENT_YEAR = 2026
MIN_YEAR = 0


def find_chrome_binary():
    for c in [
        shutil.which("chromium-browser"),
        shutil.which("chromium"),
        shutil.which("google-chrome"),
        shutil.which("google-chrome-stable"),
        r"C:\Program Files\Google\Chrome Beta\Application\chrome.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    ]:
        if c and os.path.exists(c):
            return c
    return None


def find_chromedriver():
    for c in [shutil.which("chromedriver"), r"D:\Scripts\chromedriver.exe"]:
        if c and os.path.exists(c):
            return c
    return None


# 纯电续航相关字段关键词
EV_RANGE_KEYWORDS = ["纯电续航", "CLTC纯电续航", "NEDC纯电续航"]
# 空调热泵相关字段关键词
HEAT_PUMP_KEYWORDS = ["热泵"]
# 燃油类型字段关键词（用于判断是否纯油车）
FUEL_TYPE_KEYWORDS = ["燃油类型", "燃料类型", "燃料形式", "能源类型"]
LEVEL_FIELD_KEYWORDS = ["级别", "车身结构", "车型级别", "车辆类型"]
ALLOWED_VEHICLE_LEVEL_KEYWORDS = [
    "轿车",
    "微型车",
    "小型车",
    "紧凑型车",
    "中型车",
    "中大型车",
    "大型车",
    "跑车",
    "SUV",
]
EXCLUDED_VEHICLE_LEVEL_KEYWORDS = [
    "MPV",
    "房车",
    "货车",
    "卡车",
    "皮卡",
    "微卡",
    "轻卡",
    "轻客",
    "微面",
    "客车",
    "面包车",
    "厢式",
    "载货",
    "牵引",
    "自卸",
]


def is_pure_gas_car(row, all_headers):
    """判断是否为纯油车（非插混、非纯电、非增程）"""
    for h in all_headers:
        if any(kw in h for kw in FUEL_TYPE_KEYWORDS):
            val = row.get(h, "-")
            if val and val != "-":
                # 含有"电"或"插"或"增程"的不是纯油车
                if any(k in val for k in ["电", "插", "增程"]):
                    return False
                # 含有"汽油"或"柴油"的是纯油车
                if any(k in val for k in ["汽油", "柴油"]):
                    return True
    return False


def fill_pure_gas_defaults(row, all_headers):
    """纯油车：纯电续航赋值999，空调热泵赋值'是'"""
    if not is_pure_gas_car(row, all_headers):
        return
    for h in all_headers:
        if any(kw in h for kw in EV_RANGE_KEYWORDS):
            row[h] = "999"
        if any(kw in h for kw in HEAT_PUMP_KEYWORDS):
            row[h] = "是"


def get_vehicle_level(row, all_headers):
    for h in all_headers:
        if any(kw in h for kw in LEVEL_FIELD_KEYWORDS):
            val = row.get(h, "")
            if val and val != "-":
                return str(val)
    return ""


def is_supported_vehicle_level(level):
    if not level:
        return True
    normalized = re.sub(r"\s+", "", str(level).upper())
    if any(kw.upper() in normalized for kw in EXCLUDED_VEHICLE_LEVEL_KEYWORDS):
        return False
    return any(kw.upper() in normalized for kw in ALLOWED_VEHICLE_LEVEL_KEYWORDS)


def is_supported_vehicle_row(row, all_headers):
    return is_supported_vehicle_level(get_vehicle_level(row, all_headers))


# 设置重试策略
retry_strategy = Retry(
    total=3, status_forcelist=[429, 500, 503, 504], backoff_factor=0.5
)

# 创建会话并挂载重试适配器
session = requests.Session()
session.mount("https://", HTTPAdapter(max_retries=retry_strategy))

# 添加请求头
session.headers.update(
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
    }
)

# 检查是否存在进度文件
progress_file = os.path.join(state_dir, "progress.json")
if os.path.exists(progress_file):
    with open(progress_file, "r") as f:
        progress = json.load(f)
    if "--restart" in sys.argv:
        progress = {}
        print("已重置进度")
    else:
        print("从上次进度继续（使用 --restart 可重新开始）")
else:
    progress = {}


def check_time_limit(start_time):
    if MAX_TIME_PER_STEP > 0:
        elapsed = time.time() - start_time
        if elapsed >= MAX_TIME_PER_STEP:
            print(f"已达到时间限制 {MAX_TIME_PER_STEP}秒，保存进度并退出")
            with open(progress_file, "w") as f:
                json.dump(progress, f)
            return True
    return False


def check_car_limit(cars_downloaded):
    if MAX_CARS_PER_RUN > 0 and cars_downloaded >= MAX_CARS_PER_RUN:
        print(f"已达到车型数量限制 {MAX_CARS_PER_RUN}，保存进度并退出")
        with open(progress_file, "w") as f:
            json.dump(progress, f)
        return True
    return False


def human_delay(label):
    delay = random.uniform(CRAWL_MIN_DELAY_SECONDS, CRAWL_MAX_DELAY_SECONDS)
    print(f"{label}后等待 {delay:.1f} 秒，模拟人工浏览节奏")
    time.sleep(delay)


def stop_incomplete_step1(message):
    print(message)
    if AUTO_MODE:
        raise SystemExit(10)
    raise RuntimeError(message)


def normalize_series_name(value):
    text = str(value or "").lower()
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[·・\-_()（）\[\]【】/\\.,，。:：;；]", "", text)
    text = re.sub(r"^(19|20)\d{2}款?", "", text)
    return text


def _series_name_from_record(value):
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("series", "车系", "车系名称", "name"):
            name = value.get(key)
            if name:
                return name
    return ""




def extract_model_year(spec):
    specname = str(spec.get("specname", "") or "")
    match = re.search(r"((?:19|20)\d{2})\s*款", specname)
    if match:
        return match.group(1)
    for condition in spec.get("condition") or []:
        text = str(condition or "")
        if re.fullmatch(r"(?:19|20)\d{2}", text):
            return text
    year = spec.get("year")
    if isinstance(year, int) and 1900 <= year <= 2100:
        return str(year)
    return ""


def flatten_param_value(item):
    value = item.get("itemname") or ""
    sublist = item.get("sublist") or []
    if sublist:
        sub_values = [str(sub.get("subitemname") or sub.get("name") or "") for sub in sublist]
        sub_values = [sub for sub in sub_values if sub]
        if sub_values:
            value = " / ".join(sub_values)
    return value or "-"


def build_value_items(api_rows, title_index, fallback_name=None):
    values = []
    for spec in api_rows:
        value = "-"
        if fallback_name == "年款":
            value = extract_model_year(spec) or "-"
        else:
            paramconf = spec.get("paramconflist") or []
            if isinstance(title_index, int) and title_index < len(paramconf):
                value = flatten_param_value(paramconf[title_index])
        values.append({"value": value})
    return values


def build_autohome_api_html(car_id, api_payload):
    result = api_payload.get("result") or {}
    title_list = result.get("titlelist") or []
    data_list = result.get("datalist") or []
    bread = result.get("bread") or {}
    if not title_list or not data_list:
        return None

    paramtypeitems = []
    configtypeitems = []
    has_model_year = False
    title_index = 0
    for group in title_list:
        group_name = group.get("groupname") or group.get("itemtype") or "参数信息"
        paramitems = []
        configitems = []
        for title in group.get("items") or []:
            name = title.get("itemname") or ""
            if not name:
                title_index += 1
                continue
            valueitems = build_value_items(data_list, title_index, name)
            title_index += 1
            target = {"name": name, "valueitems": valueitems}
            if group_name == "参数信息":
                paramitems.append(target)
            else:
                configitems.append(target)
            if name == "年款":
                has_model_year = True
        if paramitems:
            paramtypeitems.append({"name": group_name, "paramitems": paramitems})
        if configitems:
            configtypeitems.append({"name": group_name, "configitems": configitems})

    if not has_model_year:
        paramtypeitems.insert(0, {"name": "基本参数", "paramitems": [{"name": "年款", "valueitems": build_value_items(data_list, None, "年款")} ]})
    if not any(
        item.get("name") == "车型名称" and any(v.get("value") != "-" for v in item.get("valueitems", []))
        for group in paramtypeitems
        for item in group.get("paramitems", [])
    ):
        return None

    config = {"returncode": 0, "message": "success", "result": {"paramtypeitems": paramtypeitems}}
    option = {"returncode": 0, "message": "success", "result": {"configtypeitems": configtypeitems}}
    series_name = bread.get("seriesname") or str(car_id)
    title = f"汽车之家 | {series_name} | 参数配置"
    return (
        "<!DOCTYPE html><html><head>"
        f"<title>{title}</title>"
        "<meta charset=\"utf-8\"></head><body>"
        f"<script>var config = {json.dumps(config, ensure_ascii=False)};"
        f"var option = {json.dumps(option, ensure_ascii=False)};"
        "var bag = {};"
        "</script></body></html>"
    )


def fetch_autohome_api_html(car_id):
    api_url = f"https://car-web-api.autohome.com.cn/car/param/getParamConf?mode=1&site=1&seriesid={car_id}"
    resp = session.get(api_url, timeout=15, headers={"Referer": "https://car.autohome.com.cn/"})
    content_type = resp.headers.get("content-type", "")
    if resp.status_code != 200 or "application/json" not in content_type.lower():
        print(f"车型{car_id} API不可用: status={resp.status_code}, content-type={content_type}")
        return None, False
    try:
        payload = resp.json()
    except ValueError:
        print(f"车型{car_id} API返回非JSON")
        return None, False
    if payload.get("returncode") != 0:
        print(f"车型{car_id} API返回失败: returncode={payload.get('returncode')}, message={payload.get('message')}")
        return None, False
    result = payload.get("result") or {}
    if not (result.get("titlelist") or []) and not (result.get("datalist") or []):
        print(f"车型{car_id} API确认无当前在售配置数据")
        return None, True
    html = build_autohome_api_html(car_id, payload)
    if not html:
        print(f"车型{car_id} API缺少有效titlelist/datalist，回退HTML")
        return None, False
    print(f"车型{car_id} API优先成功: {api_url}, datalist={len((payload.get('result') or {}).get('datalist') or [])}")
    return html, False


def load_target_manifest():
    try:
        with open(target_manifest_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_target_manifest(manifest):
    with open(target_manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2, sort_keys=True)


def original_series_id_from_cache_key(cache_key):
    return str(cache_key).split("_spec_", 1)[0]


def invalidate_autohome_target_cache(cache_key, progress_obj=None):
    for path in [
        os.path.join(html_dir, cache_key),
        os.path.join(newhtml_dir, f"{cache_key}.html"),
        os.path.join(json_dir, cache_key),
        os.path.join(content_dir, f"{cache_key}.html"),
        os.path.join(newjson_dir, cache_key),
    ]:
        if os.path.exists(path):
            os.remove(path)
    if progress_obj is not None:
        for key, value in list(progress_obj.items()):
            if key in ("parse_js_to_html", "parse_json_data", "crack_html_files", "generate_data_files") and isinstance(value, list):
                progress_obj[key] = [
                    item for item in value
                    if item not in (cache_key, f"{cache_key}.html")
                ]


def mark_target_fetch_pending(cache_key, manifest):
    meta = manifest.get(cache_key)
    if not isinstance(meta, dict):
        return
    meta["fetch_pending"] = True
    meta["fetch_retry_count"] = int(meta.get("fetch_retry_count", 0) or 0) + 1


def extract_var_json(content, var_name):
    match = re.search(rf"var\s+{re.escape(var_name)}\s*=\s*(.*?);\s*var", content, re.S)
    if not match:
        match = re.search(rf"var\s+{re.escape(var_name)}\s*=\s*(.*?);", content, re.S)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def cached_html_has_valid_autohome_data(cache_key):
    html_path = os.path.join(html_dir, cache_key)
    if not os.path.exists(html_path):
        return False
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return False
    config = extract_var_json(content, "config")
    option = extract_var_json(content, "option")
    if not config or not option:
        return False
    target_meta = load_target_manifest().get(cache_key) or {}
    series_name = target_meta.get("series") or extract_series_from_html(cache_key)
    brand = target_meta.get("brand") or derive_brand_from_series(series_name)
    names, years = [], []
    for pt in ((config.get("result") or {}).get("paramtypeitems") or []):
        for it in pt.get("paramitems", []):
            vals = [clean_value(str(v.get("value", "") or "")) for v in it.get("valueitems", [])]
            if it.get("name") == "车型名称":
                names = vals
            elif it.get("name") == "年款":
                years = vals
    if not brand or not series_name or not names:
        return False
    for idx, name in enumerate(names):
        year = years[idx] if idx < len(years) else ""
        if name and re.search(r"(?:19|20)\d{2}", year):
            return True
    return False


def cache_key_for_history_target(series_id, year, spec_id):
    return f"{series_id}_spec_{year}_{spec_id}"


def sale_page_has_verifiable_structure(sale_html):
    if re.search(r"验证码|安全验证|访问验证|人机验证|请稍后重试", sale_html):
        return False
    return bool(re.search(r"(?:https?:)?//www\.autohome\.com\.cn/spec/\d+/?|/spec/\d+(?:/|\.html)", sale_html))


def parse_sale_history_targets(series_id, brand, series_name, sale_html):
    targets_by_year = {}
    pattern = r"(?:https?:)?//www\.autohome\.com\.cn/spec/(\d+)/?[^>]*>([^<]+)</a>|/spec/(\d+)(?:/|\.html)[^>]*>([^<]+)</a>"
    for match in re.findall(pattern, sale_html):
        spec_id = match[0] or match[2]
        title = match[1] or match[3]
        title_text = re.sub(r"\s+", " ", title).strip()
        year_match = re.search(r"((?:20)\d{2})\s*款", title_text)
        if not year_match:
            continue
        year = int(year_match.group(1))
        if year < 2022 or year > CURRENT_YEAR:
            continue
        if re.search(r"预售|未上市|即将上市|概念", title_text):
            continue
        targets_by_year.setdefault(str(year), {
            "cache_key": cache_key_for_history_target(series_id, year, spec_id),
            "car_id": str(series_id),
            "spec_id": str(spec_id),
            "year": str(year),
            "brand": brand,
            "series": series_name,
            "url": f"https://car.autohome.com.cn/config/spec/{spec_id}.html",
            "target_type": "history",
        })
    return [targets_by_year[year] for year in sorted(targets_by_year)]


def discover_history_targets(series_id, brand, series_name, manifest):
    sale_url = f"https://www.autohome.com.cn/{series_id}/sale.html"
    try:
        resp = session.get(sale_url, timeout=15)
        if resp.status_code != 200:
            return [], False
        resp.encoding = resp.apparent_encoding
    except requests.exceptions.RequestException:
        return [], False
    targets = parse_sale_history_targets(series_id, brand, series_name, resp.text)
    if not targets and sale_page_has_verifiable_structure(resp.text):
        manifest[f"{series_id}_history_no_data"] = {
            "car_id": str(series_id),
            "brand": brand,
            "series": series_name,
            "target_type": "history_terminal_no_data",
            "terminal": True,
            "url": sale_url,
        }
        return targets, True
    return targets, bool(targets)


def has_history_discovery_state(series_id, manifest):
    if manifest.get(f"{series_id}_history_no_data"):
        return True
    return any(
        isinstance(value, dict)
        and value.get("target_type") == "history"
        and str(value.get("car_id")) == str(series_id)
        for value in manifest.values()
    )


def mark_history_discovery_pending(series_id, brand, series_name, manifest):
    key = f"{series_id}_history_pending"
    pending = manifest.get(key) if isinstance(manifest.get(key), dict) else {}
    pending.update({
        "car_id": str(series_id),
        "brand": brand,
        "series": series_name,
        "target_type": "history_pending",
        "terminal": False,
        "retry_count": int(pending.get("retry_count", 0) or 0) + 1,
        "url": f"https://www.autohome.com.cn/{series_id}/sale.html",
    })
    manifest[key] = pending


def pending_history_indices(series_queue, manifest):
    pending_ids = {
        str(value.get("car_id"))
        for value in manifest.values()
        if isinstance(value, dict) and value.get("target_type") == "history_pending"
    }
    return [
        idx for idx, item in enumerate(series_queue)
        if str(item.get("car_id", "")) in pending_ids and not has_history_discovery_state(str(item.get("car_id", "")), manifest)
    ]


def discover_history_targets_until_deadline(series_queue, manifest, start_time):
    cursor = int(progress.get("history_discovery_idx", 0) or 0)
    batch_limit = int(os.getenv("AUTOHOME_HISTORY_DISCOVERY_BATCH", "0"))
    processed = 0
    while cursor < len(series_queue):
        if check_time_limit(start_time) or (batch_limit > 0 and processed >= batch_limit):
            progress["history_discovery_idx"] = cursor
            save_target_manifest(manifest)
            with open(progress_file, "w") as f:
                json.dump(progress, f)
            stop_incomplete_step1(f"汽车之家历史目标发现未完成：{cursor}/{len(series_queue)}")
        item = series_queue[cursor]
        series_id = str(item.get("car_id", ""))
        if not series_id or has_history_discovery_state(series_id, manifest):
            cursor += 1
            progress["history_discovery_idx"] = cursor
            continue
        targets, completed = discover_history_targets(series_id, item.get("brand", ""), item.get("series", ""), manifest)
        for target in targets:
            manifest[target["cache_key"]] = target
        if not completed:
            mark_history_discovery_pending(series_id, item.get("brand", ""), item.get("series", ""), manifest)
        cursor += 1
        processed += 1
        progress["history_discovery_idx"] = cursor
        save_target_manifest(manifest)
        with open(progress_file, "w") as f:
            json.dump(progress, f)
    pending = pending_history_indices(series_queue, manifest)
    if pending:
        progress["history_discovery_idx"] = pending[0]
        save_target_manifest(manifest)
        with open(progress_file, "w") as f:
            json.dump(progress, f)
        stop_incomplete_step1(f"汽车之家历史目标发现存在待重试目标：{len(pending)}")
    return True


def build_autohome_targets(series_queue, manifest):
    targets = []
    for item in series_queue:
        series_id = str(item.get("car_id", ""))
        if not series_id:
            continue
        current = manifest.get(series_id) if isinstance(manifest.get(series_id), dict) else None
        if not current or current.get("target_type") != "current_terminal_no_data":
            current = {
                "cache_key": series_id,
                "car_id": series_id,
                "brand": item.get("brand", ""),
                "series": item.get("series", ""),
                "heat": item.get("heat", 999),
                "url": f"https://car.autohome.com.cn/config/series/{series_id}.html",
                "target_type": "current",
            }
        manifest[series_id] = current
        targets.append(current)
        known_history = [
            value for value in manifest.values()
            if isinstance(value, dict)
            and value.get("target_type") == "history"
            and str(value.get("car_id")) == series_id
        ]
        for target in known_history:
            manifest[target["cache_key"]] = target
            targets.append(target)
    return targets


def prepare_autohome_targets(series_queue, manifest, start_time):
    if DEBUG_MODE and MAX_CARS_PER_RUN > 0:
        sampled_queue = list(series_queue[:MAX_CARS_PER_RUN])
        print(
            f"Debug模式：目标预扫描限制为前 {len(sampled_queue)} 个车系，"
            "跳过全量历史目标发现"
        )
        return build_autohome_targets(sampled_queue, manifest)

    discover_history_targets_until_deadline(series_queue, manifest, start_time)
    return build_autohome_targets(series_queue, manifest)


def load_autohome_priority_series_names():
    data_root = os.path.join(repo_dir, "data")
    dongchedi_path = os.path.join(data_root, "dongchedi_series_list.json")
    try:
        with open(dongchedi_path, "r", encoding="utf-8") as f:
            dongchedi_rows = json.load(f)
        if not isinstance(dongchedi_rows, list):
            return set()

        merged_names = [
            name
            for name in os.listdir(data_root)
            if re.fullmatch(r"merged_\d{8}\.json", name)
        ]
        if not merged_names:
            return set()
        with open(
            os.path.join(data_root, max(merged_names)), "r", encoding="utf-8"
        ) as f:
            merged_rows = json.load(f)
        if not isinstance(merged_rows, list):
            return set()
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return set()

    dongchedi_names = {
        normalize_series_name(_series_name_from_record(row))
        for row in dongchedi_rows
    }
    gap_names = set()
    for row in merged_rows:
        if not isinstance(row, dict):
            continue
        source = str(row.get("数据来源", "") or "")
        if "懂车帝" in source and "汽车之家" not in source:
            gap_names.add(normalize_series_name(_series_name_from_record(row)))

    dongchedi_names.discard("")
    gap_names.discard("")
    return dongchedi_names & gap_names


def prioritize_series_queue(series_queue, queue_idx):
    priority_names = load_autohome_priority_series_names()
    if not priority_names:
        return list(series_queue)

    start = max(0, min(int(queue_idx or 0), len(series_queue)))
    prefix = list(series_queue[:start])
    tail = list(series_queue[start:])

    def priority_key(item):
        series_name = normalize_series_name(item.get("series", ""))
        return (
            0 if series_name in priority_names else 1,
            -(item.get("salecount", 0) or 0),
            item.get("heat", 999),
            series_name,
        )

    return prefix + sorted(tail, key=priority_key)


# 第一步,下载出所有车型的网页
def download_car_pages():
    print("第一步,下载出所有车型的网页")
    letters = progress.get("download_car_pages", [])

    # 校验：Runner重启后缓存目录可能为空，需重置所有依赖缓存的进度。
    if letters:
        existing_html = os.listdir(html_dir) if os.path.isdir(html_dir) else []
        if not existing_html:
            print("html目录无车型缓存，Runner已重建，重置step1及后续进度")
            letters = []
            progress["download_car_pages"] = letters
            progress["target_idx"] = 0
            progress["history_discovery_idx"] = 0
            progress.pop("queue_idx", None)
            progress.pop("legacy_series_queue_idx", None)
            progress.pop("cars_downloaded", None)
            for key in ("parse_js_to_html", "parse_json_data",
                        "crack_html_files", "generate_data_files"):
                progress.pop(key, None)

    start_time = time.time()
    cars_downloaded = progress.get("cars_downloaded", 0)
    initial_cars_downloaded = cars_downloaded
    skipped_count = 0  # 增量模式下跳过的已存在车型数

    # === Phase 0: 快速扫描所有字母页，收集品牌+车系ID列表 ===
    # 品牌热度排行榜和排序配置通过环境变量自定义，无需改代码
    # 环境变量：
    #   BRAND_HEAT_ORDER    — 逗号分隔的品牌名列表，按热度从高到低
    #   BRAND_NAME_MAP     — 逗号分隔的 映射对，如 "长安:长安汽车,小鹏:小鹏汽车"
    #   SORT_CONFIG         — 逗号分隔的排序字段，格式 "字段:asc|desc"，如 "heat:asc,salecount:desc,series:asc"
    #   SALES_RANK_DATE     — 销量榜日期，格式 "YYYY-MM"，默认自动获取最新
    #   SALES_RANK_SUBRANKS — 逗号分隔的子榜ID，默认 "1,2,3,4,5,6,7,8"

    # 默认品牌热度排行榜（环境变量未设置时使用）
    DEFAULT_BRAND_HEAT_ORDER = [
        "比亚迪", "吉利汽车", "长安汽车", "奇瑞", "上汽大众", "一汽大众",
        "广汽丰田", "一汽丰田", "本田", "东风日产", "五菱汽车", "别克",
        "宝马", "奔驰", "奥迪", "特斯拉", "理想汽车", "蔚来",
        "零跑汽车", "极氪", "小鹏", "小鹏汽车", "领克",
        "哈弗", "宝骏", "红旗", "广汽传祺", "东风本田", "北京现代",
        "长安欧尚", "长安马自达", "广汽本田", "沃尔沃", "凯迪拉克",
        "路虎", "保时捷", "雷克萨斯",
        "长城炮", "坦克", "捷途", "星途", "传祺", "捷达", "smart", "MINI",
        "埃安", "深蓝汽车", "启辰", "阿维塔", "岚图", "岚图汽车", "智己",
        "智己汽车", "极狐", "ARCFOX极狐", "腾势", "方程豹", "仰望",
        "哪吒汽车", "小米汽车", "乐道",
        "极越", "魏牌", "长安启源",
        "北京越野", "北京汽车", "北汽新能源", "东风风行", "江淮",
        "东风风神", "上汽大通", "荣威", "名爵", "东风",
        "标致", "雪铁龙", "雪佛兰", "福特", "起亚", "马自达",
        "斯柯达", "三菱", "斯巴鲁", "铃木", "众泰", "海马",
    ]

    DEFAULT_BRAND_NAME_MAP = {
        "长安": "长安汽车",
        "小鹏": "小鹏汽车",
        "AITO 问界": "问界",
        "岚图汽车": "岚图",
        "智己汽车": "智己",
        "ARCFOX极狐": "极狐",
        "大众": "上汽大众",
        "丰田": "广汽丰田",
        "日产": "东风日产",
    }

    # 从环境变量加载品牌热度排行榜
    env_heat_order = os.environ.get("BRAND_HEAT_ORDER", "")
    if env_heat_order:
        AUTOHOME_BRAND_HEAT_ORDER = [b.strip() for b in env_heat_order.split(",") if b.strip()]
        print(f"从环境变量加载品牌热度排行榜: {len(AUTOHOME_BRAND_HEAT_ORDER)} 个品牌")
    else:
        AUTOHOME_BRAND_HEAT_ORDER = DEFAULT_BRAND_HEAT_ORDER

    # 从环境变量加载品牌名映射
    env_name_map = os.environ.get("BRAND_NAME_MAP", "")
    if env_name_map:
        BRAND_NAME_MAP = {}
        for pair in env_name_map.split(","):
            if ":" in pair:
                k, v = pair.split(":", 1)
                BRAND_NAME_MAP[k.strip()] = v.strip()
    else:
        BRAND_NAME_MAP = DEFAULT_BRAND_NAME_MAP

    # 构建热度查找表：品牌名 → 排名(越小越热)
    heat_map = {}
    for idx, brand in enumerate(AUTOHOME_BRAND_HEAT_ORDER):
        normalized = brand.strip().lower().replace(" ", "")
        heat_map[normalized] = idx

    def get_brand_heat(brand_name):
        """获取品牌热度排名，越小越热门。未列入的返回999。"""
        normalized = brand_name.strip().lower().replace(" ", "")
        # 先直接查
        if normalized in heat_map:
            return heat_map[normalized]
        # 再查映射后的
        mapped = BRAND_NAME_MAP.get(brand_name.strip())
        if mapped:
            mapped_norm = mapped.strip().lower().replace(" ", "")
            if mapped_norm in heat_map:
                return heat_map[mapped_norm]
        return 999

    if os.path.exists(series_queue_file):
        with open(series_queue_file, "r", encoding="utf-8") as f:
            series_queue = json.load(f)
        print(f"加载已有车系队列: {len(series_queue)} 个车系")
    else:
        print("=== Phase 0: 扫描所有字母页，收集品牌+车系ID列表 ===")
        all_letters = [chr(i) for i in range(ord("A"), ord("Z") + 1)]
        series_queue = []
        brand_id_map = {}  # brandid → brandname（用于销量榜反查）

        for letter in all_letters:
            first_url = f"https://www.autohome.com.cn/grade/carhtml/{letter}.html"
            print(f"扫描字母 {letter} ...")

            resp = None
            max_retries = 5
            for attempt in range(max_retries):
                try:
                    resp = session.get(first_url, timeout=20)
                    break
                except (requests.exceptions.SSLError, requests.exceptions.ConnectionError) as e:
                    if attempt < max_retries - 1:
                        wait_time = min(2 ** (attempt + 2), 20)
                        print(f"连接错误，{wait_time}秒后重试 ({attempt+1}/{max_retries}): {e}")
                        time.sleep(wait_time)
                    else:
                        print(f"字母{letter}扫描失败，跳过: {e}")
                        break

            if resp is None or resp.status_code != 200:
                print(f"字母{letter}获取失败，跳过")
                continue

            resp.encoding = resp.apparent_encoding
            soup = bs4.BeautifulSoup(resp.text, "html.parser")

            for dl in soup.find_all("dl"):
                dt = dl.find("dt")
                brand_name = ""
                brand_id = dl.get("id", "")  # dl id 就是 brandid
                if dt:
                    for div in dt.find_all("div"):
                        txt = div.get_text(strip=True)
                        if txt:
                            brand_name = txt
                            break
                    if not brand_name:
                        a = dt.find("a")
                        if a:
                            brand_name = a.get_text(strip=True)

                # 记录 brandid → brandname 映射（用于销量榜反查品牌名）
                if brand_id and brand_name:
                    brand_id_map[brand_id] = brand_name

                # 车系在 dd > ul > li > h4 > a 里
                dd = dl.find("dd")
                if dd:
                    for li in dd.find_all("li"):
                        h4 = li.find("h4")
                        if h4 and h4.a:
                            href = h4.a.get("href")
                            series_name = h4.a.text.strip()
                            if href and isinstance(href, str) and ".cn" in href:
                                car_id = href.split("#")[0][href.index(".cn") + 3:].replace("/", "")
                                if car_id:
                                    heat = get_brand_heat(brand_name)
                                    series_queue.append({
                                        "heat": heat,
                                        "car_id": car_id,
                                        "brand": brand_name,
                                        "brand_id": brand_id,
                                        "series": series_name,
                                    })

            time.sleep(0.5)

        # === 获取车系月销量数据 ===
        print("=== 获取汽车之家销量榜数据 ===")
        sales_map = {}  # seriesid -> salecount
        sales_rank_raw_data = []  # 保存所有子榜的原始 list，用于按 brandid 汇总品牌销量
        # 销量榜日期：环境变量 SALES_RANK_DATE (格式 YYYY-MM)，默认自动获取最新月份
        sales_rank_date = os.environ.get("SALES_RANK_DATE", "")
        if not sales_rank_date:
            from datetime import datetime as _dt
            now = _dt.now()
            # 汽车之家销量榜通常滞后1个月（每月10号更新上月数据）
            if now.day < 10:
                # 月初用上上月
                month = now.month - 2
                year = now.year
                if month <= 0:
                    month += 12
                    year -= 1
            else:
                month = now.month - 1
                year = now.year
                if month <= 0:
                    month += 12
                    year -= 1
            sales_rank_date = f"{year}-{month:02d}"
        print(f"销量榜日期: {sales_rank_date}")

        # 子榜ID：环境变量 SALES_RANK_SUBRANKS，默认 1-8
        env_subranks = os.environ.get("SALES_RANK_SUBRANKS", "")
        if env_subranks:
            RANK_SUBRANKS = [int(x.strip()) for x in env_subranks.split(",") if x.strip()]
        else:
            RANK_SUBRANKS = list(range(1, 9))

        for subrank in RANK_SUBRANKS:
            try:
                url = f"https://www.autohome.com.cn/rank/1-{subrank}-0-0_9000-x-x-x/{sales_rank_date}.html"
                r = session.get(url, timeout=10)
                idx = r.text.find('"listRes"')
                if idx == -1:
                    continue
                obj_start = r.text.index('{', idx)
                brace_count = 0
                for i, c in enumerate(r.text[obj_start:], obj_start):
                    if c == '{': brace_count += 1
                    elif c == '}': brace_count -= 1
                    if brace_count == 0:
                        obj_end = i + 1
                        break
                list_res = json.loads(r.text[obj_start:obj_end])
                rank_list = list_res.get("list", [])
                if rank_list:
                    sales_rank_raw_data.append(rank_list)
                for item in rank_list:
                    sid = str(item.get("seriesid", ""))
                    sc = int(item.get("salecount", 0))
                    if sid and sc > 0 and (sid not in sales_map or sc > sales_map[sid]):
                        sales_map[sid] = sc
                time.sleep(0.3)
            except Exception:
                pass
        print(f"获取到 {len(sales_map)} 个车系的月销量数据")

        # === 动态品牌热度：按品牌汇总月销量作为热度 ===
        # 销量榜数据中有 brandid，用 brand_id_map 反查品牌名
        # 品牌总销量越高 → 热度排名越靠前（heat 值越小）
        brand_sales = {}  # brandname -> total_salecount

        # 从销量榜原始数据中按 brandid 汇总
        brand_sales_raw = {}  # brandid -> total_salecount
        for subrank_url_data in sales_rank_raw_data:
            for rank_item in subrank_url_data:
                bid = str(rank_item.get("brandid", ""))
                sc = int(rank_item.get("salecount", 0))
                if bid and sc > 0:
                    brand_sales_raw[bid] = brand_sales_raw.get(bid, 0) + sc

        # brandid → brandname → 总销量
        for bid, total_sc in brand_sales_raw.items():
            bname = brand_id_map.get(bid, "")
            if bname:
                # 取映射后的标准名
                mapped = BRAND_NAME_MAP.get(bname, bname)
                brand_sales[mapped] = brand_sales.get(mapped, 0) + total_sc

        if brand_sales:
            # 按总销量降序排品牌，生成动态热度排行榜
            dynamic_heat_order = sorted(brand_sales.keys(), key=lambda b: brand_sales[b], reverse=True)
            print(f"动态品牌热度排行榜（按月销量）: 前10 = {[(b, brand_sales[b]) for b in dynamic_heat_order[:10]]}")

            # 更新 heat_map：动态排名覆盖静态
            for idx, brand in enumerate(dynamic_heat_order):
                normalized = brand.strip().lower().replace(" ", "")
                heat_map[normalized] = idx
            # 未在销量榜中的品牌保持 999
            print(f"已更新 {len(dynamic_heat_order)} 个品牌的动态热度")

            # 重新计算 series_queue 中每个车系的 heat
            for item in series_queue:
                item["heat"] = get_brand_heat(item["brand"])
        else:
            print("未获取到销量榜品牌数据，保持静态热度排行榜")

        # === 多关键字排序（类似 Excel 自定义排序）===
        # 排序配置：环境变量 SORT_CONFIG，格式 "字段:asc|desc,字段:asc|desc,..."
        # 默认: 品牌热度升序 → 月销量降序 → 车系名升序
        env_sort_config = os.environ.get("SORT_CONFIG", "")
        if env_sort_config:
            SORT_CONFIG = []
            for part in env_sort_config.split(","):
                part = part.strip()
                if ":" in part:
                    field, direction = part.split(":", 1)
                    SORT_CONFIG.append((field.strip(), direction.strip().lower().startswith("asc")))
                else:
                    SORT_CONFIG.append((part, True))
            print(f"从环境变量加载排序配置: {SORT_CONFIG}")
        else:
            SORT_CONFIG = [
                ("heat", True),       # 第一关键字：品牌热度 升序（热门品牌在前）
                ("salecount", False), # 第二关键字：月销量 降序（销量高在前）
                ("series", True),     # 第三关键字：车系名 升序（字母序）
            ]

        # 补充销量数据到队列
        for item in series_queue:
            item["salecount"] = sales_map.get(item["car_id"], 0)

        # 多字段排序
        def sort_key(item):
            keys = []
            for field, ascending in SORT_CONFIG:
                val = item.get(field, 0)
                if field == "series":
                    val = val.lower()  # 不区分大小写
                if not ascending:
                    val = -val if isinstance(val, (int, float)) else val
                keys.append(val)
            return tuple(keys)

        series_queue.sort(key=sort_key)

        os.makedirs(os.path.dirname(series_queue_file), exist_ok=True)
        with open(series_queue_file, "w", encoding="utf-8") as f:
            json.dump(series_queue, f, ensure_ascii=False, indent=2)

        # 打印统计
        brands_seen = {}
        sales_count = 0
        for s in series_queue:
            brands_seen[s["brand"]] = brands_seen.get(s["brand"], 0) + 1
            if s.get("salecount", 0) > 0:
                sales_count += 1
        print(f"扫描完成: 共 {len(series_queue)} 个车系, {len(brands_seen)} 个品牌, {sales_count} 个有销量数据")
        # 打印热度前20品牌
        top_brands = []
        seen = set()
        for s in series_queue:
            if s["brand"] not in seen:
                top_brands.append((s["brand"], s["heat"], s.get("salecount", 0)))
                seen.add(s["brand"])
        print(f"前20品牌: {top_brands[:20]}")
        # 打印队列前10
        print("队列前10:")
        for i, s in enumerate(series_queue[:10]):
            sc = s.get("salecount", 0)
            print(f"  {i+1}. heat={s['heat']} sales={sc} {s['brand']}/{s['series']}")

    if not series_queue:
        stop_incomplete_step1("汽车之家车系列表为空，拒绝判定step1完成")

    if "target_idx" not in progress and "queue_idx" in progress:
        progress["legacy_series_queue_idx"] = progress.get("queue_idx", 0)
        progress["target_idx"] = 0
        progress.pop("queue_idx", None)
        with open(progress_file, "w") as f:
            json.dump(progress, f)

    # 从队列中恢复进度
    queue_idx = progress.get("legacy_series_queue_idx", 0)

    prioritized_queue = prioritize_series_queue(series_queue, queue_idx)
    if prioritized_queue != series_queue:
        series_queue = prioritized_queue
        with open(series_queue_file, "w", encoding="utf-8") as f:
            json.dump(series_queue, f, ensure_ascii=False, indent=2)
        print(f"已按汽车之家缺口优先级重排未处理队列: queue_idx={queue_idx}")

    manifest = load_target_manifest()
    targets = prepare_autohome_targets(series_queue, manifest, start_time)
    save_target_manifest(manifest)
    if not targets:
        stop_incomplete_step1("汽车之家真实目标队列为空，拒绝判定step1完成")

    target_idx = int(progress.get("target_idx", 0) or 0)
    for idx in range(target_idx, len(targets)):
        item = targets[idx]
        cache_key = item["cache_key"]
        car_id = item["car_id"]
        heat = item.get("heat", 999)
        brand = item["brand"]
        series = item["series"]

        # 检查时间限制和数量限制
        if check_time_limit(start_time) or check_car_limit(cars_downloaded - initial_cars_downloaded):
            progress["cars_downloaded"] = cars_downloaded
            progress["target_idx"] = idx
            progress["download_car_pages"] = letters
            with open(progress_file, "w") as f:
                json.dump(progress, f)
            if AUTO_MODE:
                print(f"未完成，目标第{idx}/{len(targets)}个（{brand}/{series}, cache_key={cache_key}, heat={heat}），等待下次继续")
                sys.exit(10)
            return

        car_file = os.path.join(html_dir, cache_key)
        if os.path.exists(car_file):
            if cached_html_has_valid_autohome_data(cache_key):
                if INCREMENTAL_MODE:
                    skipped_count += 1
                continue
            if item.get("terminal"):
                skipped_count += 1
                continue
            print(f"目标{cache_key}已有缓存不可解析或缺少有效车型，删除并重抓")
            invalidate_autohome_target_cache(cache_key, progress)
            with open(progress_file, "w") as f:
                json.dump(progress, f)

        car_url = item.get("url") or f"https://car.autohome.com.cn/config/series/{car_id}.html"
        print(f"[{idx+1}/{len(targets)}] 正在获取 {brand}/{series} (cache_key={cache_key}, car_id={car_id}, heat={heat})")

        content = None
        current_terminal = False
        if item.get("target_type") == "current":
            try:
                content, current_terminal = fetch_autohome_api_html(car_id)
            except requests.exceptions.RequestException as e:
                print(f"车型{car_id} API请求异常，回退HTML: {e}")
        if current_terminal:
            manifest[cache_key]["target_type"] = "current_terminal_no_data"
            manifest[cache_key]["terminal"] = True
            save_target_manifest(manifest)
            progress["target_idx"] = idx + 1
            with open(progress_file, "w") as f:
                json.dump(progress, f)
            skipped_count += 1
            continue
        if content is None:
            for i in range(5):
                try:
                    resp = session.get(car_url, timeout=15)
                    print(f"目标{cache_key}响应码: {resp.status_code}")
                    break
                except requests.exceptions.RequestException:
                    print(f"请求异常, 重试次数:{i + 1}")
                    human_delay(f"目标{cache_key}请求异常")
            else:
                print(f"获取{cache_key}目标失败，记录pending并继续后续目标")
                mark_target_fetch_pending(cache_key, manifest)
                save_target_manifest(manifest)
                progress["target_idx"] = idx + 1
                with open(progress_file, "w") as f:
                    json.dump(progress, f)
                continue
            resp.encoding = resp.apparent_encoding
            content = resp.text

        with open(car_file, "w", encoding="utf-8") as f:
            f.write(content)
        if not cached_html_has_valid_autohome_data(cache_key):
            print(f"目标{cache_key}缓存未解析出非空config/option/有效车型，删除缓存并等待后续run重试")
            invalidate_autohome_target_cache(cache_key, progress)
            progress["cars_downloaded"] = cars_downloaded
            progress["target_idx"] = idx + 1
            progress["download_car_pages"] = letters
            mark_target_fetch_pending(cache_key, manifest)
            save_target_manifest(manifest)
            with open(progress_file, "w") as f:
                json.dump(progress, f)
            continue
        if manifest[cache_key].get("fetch_pending"):
            manifest[cache_key].pop("fetch_pending", None)
            save_target_manifest(manifest)
        human_delay(f"获取{car_id}车型配置")
        print(f"车型{car_id}内容长度: {len(content)}")
        cars_downloaded += 1

    cached_ids = set(os.listdir(html_dir)) if os.path.isdir(html_dir) else set()
    missing_indices = [
        idx for idx, item in enumerate(targets)
        if not item.get("terminal")
        and (
            str(item.get("cache_key", "")) not in cached_ids
            or not cached_html_has_valid_autohome_data(str(item.get("cache_key", "")))
        )
    ]
    if missing_indices:
        retry_index = missing_indices[0]
        progress["target_idx"] = retry_index
        progress["cars_downloaded"] = cars_downloaded
        progress["download_car_pages"] = letters
        with open(progress_file, "w") as f:
            json.dump(progress, f)
        message = f"step1真实目标缓存不完整：缺少或无效 {len(missing_indices)}/{len(targets)} 个目标，从队列 {retry_index} 重试"
        stop_incomplete_step1(message)

    # 全部队列完成
    progress["target_idx"] = len(targets)
    progress["cars_downloaded"] = cars_downloaded
    progress["download_car_pages"] = [chr(i) for i in range(ord("A"), ord("Z") + 1)]
    with open(progress_file, "w") as f:
        json.dump(progress, f)

    new_downloaded = cars_downloaded - initial_cars_downloaded
    if INCREMENTAL_MODE:
        print(f"增量模式完成：新增 {new_downloaded} 个车型，跳过 {skipped_count} 个已存在车型")
    else:
        print(f"第一步完成：新增 {new_downloaded} 个车型")


# 第二步,解析出每个车型的关键js拼装成一个html
def parse_js_to_html():
    print("第二步,解析出每个车型的关键js拼装成一个html")
    if "parse_js_to_html" in progress:
        print(f"从上次进度继续:{progress['parse_js_to_html']}")
        parsed_files = progress["parse_js_to_html"]
    else:
        parsed_files = []

    start_time = time.time()
    for file in os.listdir(html_dir):
        if file not in parsed_files:
            if check_time_limit(start_time):
                return
            print(f"正在解析文件:{file}")
            content = ""
            with open(os.path.join(html_dir, file), "r", encoding="utf-8") as f:
                content = "".join(f.readlines())

            js_code = (
                "var rules = '2';"
                "var document = {};"
                "function getRules(){return rules}"
                "document.createElement = function() {"
                "      return {"
                "              sheet: {"
                "                      insertRule: function(rule, i) {"
                "                              if (rules.length == 0) {"
                "                                      rules = rule;"
                "                              } else {"
                "                                      rules = rules + '#' + rule;"
                "                              }"
                "                      }"
                "              }"
                "      }"
                "};"
                "document.querySelectorAll = function() {"
                "      return {};"
                "};"
                "document.head = {};"
                "document.head.appendChild = function() {};"
                "var window = {};"
                "window.decodeURIComponent = decodeURIComponent;"
            )

            try:
                js = re.findall(
                    r"\(function\([a-zA-Z]{2}.*?_\).*?\(document\);", content
                )
                print(f"车型{file}提取js函数个数: {len(js)}")
                for item in js:
                    print(f"提取的js函数: {item[:100]}...")
                    js_code += item
            except Exception:
                print("解析js函数异常")

            new_html = "<html><meta http-equiv='Content-Type' content='text/html; charset=utf-8' /><head></head><body>    <script type='text/javascript'>"
            js_code = (
                new_html + js_code + " document.write(rules)</script></body></html>"
            )

            with open(
                os.path.join(newhtml_dir, f"{file}.html"), "w", encoding="utf-8"
            ) as f:
                f.write(js_code)

            parsed_files.append(file)
            progress["parse_js_to_html"] = parsed_files
            with open(progress_file, "w") as f:
                json.dump(progress, f)

    print("第二步完成")


# 第三步,解析出每个车型的数据json,保存到本地
def parse_json_data():
    print("第三步,解析出每个车型的数据json,保存到本地")
    if "parse_json_data" in progress:
        print(f"从上次进度继续:{progress['parse_json_data']}")
        parsed_files = progress["parse_json_data"]
    else:
        parsed_files = []

    start_time = time.time()
    for file in os.listdir(html_dir):
        if file not in parsed_files:
            if check_time_limit(start_time):
                return
            print(f"正在解析文件:{file}")
            content = ""
            with open(os.path.join(html_dir, file), "r", encoding="utf-8") as f:
                content = "".join(f.readlines())

            json_data = ""
            config = re.search(r"var config = (.*?){1,};", content)
            if config:
                json_data += config.group(0)

            option = re.search(r"var option = (.*?)};", content)
            if option:
                json_data += option.group(0)

            bag = re.search(r"var bag = (.*?);", content)
            if bag:
                json_data += bag.group(0)

            with open(os.path.join(json_dir, file), "w", encoding="utf-8") as f:
                f.write(json_data)

            parsed_files.append(file)
            progress["parse_json_data"] = parsed_files
            with open(progress_file, "w") as f:
                json.dump(progress, f)

    print("第三步完成")


# 第四步,浏览器执行第二步生成的html文件,抓取执行结果,保存到本地


class Crack:
    def __init__(self):
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--user-data-dir=/tmp/chrome-user-data-" + str(os.getpid()))
        if os.getenv("PROXY_ENABLED") == "true":
            chrome_proxy = os.getenv("CHROME_PROXY_SERVER", "http://127.0.0.1:7890")
            chrome_options.add_argument(f"--proxy-server={chrome_proxy}")
        cb = find_chrome_binary()
        if cb:
            chrome_options.binary_location = cb
        cd = find_chromedriver()
        if cd:
            self.browser = webdriver.Chrome(service=Service(cd), options=chrome_options)
        else:
            self.browser = webdriver.Chrome(options=chrome_options)

    def crack(self, html_file):
        self.browser.get(f"file:///{os.path.join(newhtml_dir, html_file)}")
        body = self.browser.find_element("tag name", "body")
        text = body.text
        with open(os.path.join(content_dir, html_file), "w", encoding="utf-8") as f:
            f.write(text)

    def __del__(self):
        self.browser.quit()


def crack_html_files():
    print("第四步,浏览器执行第二步生成的html文件,抓取执行结果,保存到本地")
    if "crack_html_files" in progress:
        print(f"从上次进度继续:{progress['crack_html_files']}")
        cracked_files = progress["crack_html_files"]
    else:
        cracked_files = []

    start_time = time.time()
    crack = Crack()
    for file in os.listdir(newhtml_dir):
        if file not in cracked_files:
            if check_time_limit(start_time):
                return
            print(f"正在执行文件:{file}")
            crack.crack(file)
            cracked_files.append(file)
            progress["crack_html_files"] = cracked_files
            with open(progress_file, "w") as f:
                json.dump(progress, f)

    print("第四步完成")


# 第五步,匹配样式文件与json数据文件,生成正常的数据文件
def generate_data_files():
    print("第五步,匹配样式文件与json数据文件,生成正常的数据文件")
    if "generate_data_files" in progress:
        print(f"从上次进度继续:{progress['generate_data_files']}")
        processed_files = progress["generate_data_files"]
    else:
        processed_files = []

    start_time = time.time()
    for json_file in os.listdir(json_dir):
        if json_file not in processed_files:
            if check_time_limit(start_time):
                return
            print(f"正在处理文件:{json_file}")
            json_content = ""
            with open(os.path.join(json_dir, json_file), "r", encoding="utf-8") as f:
                json_content = "".join(f.readlines())

            style_content = ""
            with open(
                os.path.join(content_dir, f"{json_file}.html"), "r", encoding="utf-8"
            ) as f:
                style_content = "".join(f.readlines())

            spans = re.findall(r"<span(.*?)></span>", json_content)
            for span in spans:
                class_match = re.search(r"'(.*?)'", span)
                if not class_match:
                    continue
                class_name = class_match.group(1)
                style_regex = rf"{class_name}::before \{{ content:(.*?)\}}"
                style_value = re.search(style_regex, style_content)
                if style_value:
                    value_match = re.search(r'"(.*?)"', style_value.group(1))
                    if value_match:
                        value = value_match.group(1)
                        json_content = json_content.replace(
                            f"<span class='{class_name}'></span>", value
                        )

            with open(os.path.join(newjson_dir, json_file), "w", encoding="utf-8") as f:
                f.write(json_content)

            processed_files.append(json_file)
            progress["generate_data_files"] = processed_files
            with open(progress_file, "w") as f:
                json.dump(progress, f)

    print("第五步完成")


# 品牌前缀列表（长度降序，长前缀优先匹配）
BRAND_PREFIXES = [
    '吉利银河', '凯迪拉克', '雷克萨斯', '英菲尼迪', '雪铁龙', '比亚迪',
    '保时捷', '沃尔沃', '特斯拉', '阿维塔', '斯柯达', '雪佛兰', '马自达',
    '宝马', '奔驰', '奥迪', '大众', '丰田', '本田', '日产',
    '别克', '福特', '现代', '起亚', '吉利', '长城', '红旗', '领克',
    '极氪', '小鹏', '理想', '蔚来', '零跑', '问界', '埃安', '极狐',
    '岚图', '智己', '路虎', '捷豹', '林肯', '捷达', '五菱', '宝骏',
    'WEY', '坦克', '欧拉', '哈弗', '魏牌', '标致', '奇瑞', '传祺',
    '荣威', '名爵', '长安', '深蓝', '启源', '哪吒', '腾势', '方程豹',
    '仰望', '星途', '捷途', '猛士', '蓝电', '北汽', '江淮', '东风',
    '大通', '依维柯', '金杯', '福田', '庆铃', '江铃', '凯马',
    '长安欧尚', '广汽', '北京', '东南', '海马', '中华', '力帆',
    '众泰', '陆风', '猎豹', '野马', '黄海', '中兴', '福迪',
    '法拉利', '兰博基尼', '玛莎拉蒂', '劳斯莱斯', '宾利', '阿斯顿马丁',
    '迈凯伦', '布加迪', '帕加尼', '科尼赛克', '阿尔法罗密欧',
    '迈巴赫', 'MINI', 'Smart', 'DS', 'Jeep', 'Ram', '道奇',
    '克莱斯勒', 'GMC', '标致', '雷诺', '菲亚特',
    '斯巴鲁', '三菱', '铃木', '五十铃', '双龙', '讴歌',
]

# 车系名→品牌映射: 当车系名不以品牌前缀开头时的兜底
SERIES_TO_BRAND = {
    "皓影": "本田", "皓影新能源": "本田", "冠道": "本田", "缤智": "本田",
    "雅阁": "本田", "凌派": "本田", "ZR-V 致在": "本田",
    "昂科威S": "别克", "昂科威Plus": "别克", "昂科拉PLUS": "别克",
    "君越": "别克", "微蓝6": "别克", "昂扬": "别克",
    "Macan新能源": "保时捷", "Taycan": "保时捷", "Cayenne": "保时捷",
    "Macan": "保时捷",
    "添越": "宾利", "添越插电混动": "宾利", "飞驰插电混动": "宾利",
    "博速 G级": "博速",
    "奔腾T77": "奔腾", "奔腾T99": "奔腾", "奔腾T90": "奔腾",
    "奔腾T90 PHEV": "奔腾", "奔腾E01": "奔腾", "奔腾B70": "奔腾",
    "奔腾B70S": "奔腾",
    "悦意03": "奔腾", "悦意07": "奔腾", "悦意08": "奔腾",
    "魔方": "北京汽车",
    "勇士": "北京汽车制造厂",
    "昌河北斗星": "昌河",
    "212经典": "北京汽车制造厂",
    "巴菲特600": "巴菲特",
}


def derive_brand_from_series(series_name):
    """从车系名称推导品牌"""
    if not series_name:
        return ''
    for bp in BRAND_PREFIXES:
        if series_name.startswith(bp):
            return bp
    # 兜底: 从 SERIES_TO_BRAND 查找
    return SERIES_TO_BRAND.get(series_name, '')


# 第六步,读取数据文件,生成excel
def clean_header(header):
    return re.sub(r"[/()]", "_", header).strip()


def clean_value(value):
    return re.sub(r"<.*?>", "", value)


def extract_series_from_html(file_id):
    """从原始 HTML 文件中提取车系名称"""
    html_path = os.path.join(html_dir, file_id)
    if not os.path.exists(html_path):
        return ''
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()
        m = re.search(r'<title>\s*汽车之家\s*\|\s*([^|]+?)\s*\|', html, re.IGNORECASE)
        if m:
            series = m.group(1).strip()
            series = series.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"').replace('&#39;', "'")
            return series
    except Exception as e:
        print(f"提取车系名称失败 {file_id}: {e}")
    return ''


def target_meta_for_cache_key(file_id):
    manifest = load_target_manifest()
    meta = manifest.get(file_id)
    return meta if isinstance(meta, dict) else {}


def generate_csv():
    print("第六步,生成CSV")
    today = date.today().strftime("%Y%m%d")

    fixed = ["数据来源", "品牌", "车系", "车系ID", "车型名称", "年款"]
    all_h, rows = [], []

    for file in os.listdir(newjson_dir):
        with open(os.path.join(newjson_dir, file), "r", encoding="utf-8") as f:
            content = "".join(f.readlines())

        config = re.search(r"var config = (.*?);", content)
        option = re.search(r"var option = (.*?);var", content)

        if not config or not option:
            print(f"跳过 {file}: 无法解析config或option")
            continue

        try:
            cd = json.loads(config.group(1))
            od = json.loads(option.group(1))
            names, years, data = [], [], {}
            print(f"Processing: {file}")

            # 从原始 HTML 提取车系名称和品牌
            target_meta = target_meta_for_cache_key(file)
            series_name = target_meta.get("series") or extract_series_from_html(file)
            brand = target_meta.get("brand") or derive_brand_from_series(series_name)
            series_id = target_meta.get("car_id") or original_series_id_from_cache_key(file)

            if "result" in cd and "paramtypeitems" in cd["result"]:
                for pt in cd["result"]["paramtypeitems"]:
                    for it in pt.get("paramitems", []):
                        h = clean_header(it["name"])
                        vals = [clean_value(v["value"]) for v in it["valueitems"]]
                        if it["name"] == "车型名称":
                            names = vals
                        if it["name"] == "年款":
                            years = vals
                        data[h] = vals
                        if h not in all_h and h not in fixed:
                            all_h.append(h)

            if "result" in od and "configtypeitems" in od["result"]:
                for ct in od["result"]["configtypeitems"]:
                    for it in ct.get("configitems", []):
                        h = clean_header(it["name"])
                        vals = [clean_value(v["value"]) for v in it["valueitems"]]
                        data[h] = vals
                        if h not in all_h and h not in fixed:
                            all_h.append(h)

            n = max((len(v) for v in data.values()), default=0)
            for i in range(n):
                ys = years[i] if i < len(years) else ""
                ym = re.search(r"(\d{4})", ys)
                if ym and int(ym.group(1)) < MIN_YEAR:
                    continue
                row = {
                    "数据来源": "汽车之家",
                    "品牌": brand,
                    "车系": series_name,
                    "车系ID": series_id,
                    "车型名称": names[i] if i < len(names) else "",
                    "年款": ys,
                }
                if not row["品牌"] or not row["车系"] or not row["车型名称"] or not re.search(r"(?:19|20)\d{2}", row["年款"]):
                    continue
                for h in all_h:
                    v = data.get(h, [])
                    row[h] = v[i] if i < len(v) else "-"
                if not is_supported_vehicle_row(row, all_h):
                    continue
                fill_pure_gas_defaults(row, all_h)
                rows.append(row)

        except Exception as e:
            print(f"解析{file}异常: {e}")
            with open(
                os.path.join(exception_dir, "exception.txt"), "a", encoding="utf-8"
            ) as f:
                f.write(f"{file}: {e}\n")

    fieldnames = fixed + all_h
    if DEBUG_MODE and DEBUG_OUTPUT_MAX_ROWS > 0 and len(rows) > DEBUG_OUTPUT_MAX_ROWS:
        print(f"Debug模式：输出从 {len(rows)} 条截断为 {DEBUG_OUTPUT_MAX_ROWS} 条，避免缩小稳定全量 Pages")
        rows = rows[:DEBUG_OUTPUT_MAX_ROWS]

    csv_path = os.path.join(working_dir, f"autoHome_{today}.csv")
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for rd in rows:
            w.writerow({h: rd.get(h, "-") for h in fieldnames})

    json_path = os.path.join(working_dir, f"autoHome_{today}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    print(f"第六步完成，共{len(rows)}条")
    print(f"  CSV: {csv_path}")
    print(f"  JSON: {json_path}")


def is_step1_completed():
    letters = progress.get("download_car_pages", [])
    if len(letters) < 26 or not os.path.exists(series_queue_file):
        return False
    try:
        with open(series_queue_file, "r", encoding="utf-8") as f:
            queue = json.load(f)
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(queue, list) or not queue:
        return False
    manifest = load_target_manifest()
    targets = []
    for item in queue:
        series_id = str(item.get("car_id", ""))
        if not series_id:
            return False
        current = manifest.get(series_id)
        targets.append(current if isinstance(current, dict) else {"cache_key": series_id, "terminal": False})
        history_targets = [
            value for value in manifest.values()
            if isinstance(value, dict)
            and value.get("target_type") == "history"
            and str(value.get("car_id")) == series_id
        ]
        terminal = manifest.get(f"{series_id}_history_no_data")
        if not history_targets and not terminal:
            return False
        targets.extend(history_targets)
    cached_ids = set(os.listdir(html_dir)) if os.path.isdir(html_dir) else set()
    expected_ids = {
        str(item.get("cache_key", ""))
        for item in targets
        if item.get("cache_key") and not item.get("terminal")
    }
    return (
        expected_ids
        and expected_ids.issubset(cached_ids)
        and all(cached_html_has_valid_autohome_data(cache_key) for cache_key in expected_ids)
        and int(progress.get("target_idx", 0)) >= len(targets)
    )


def check_and_continue():
    if not AUTO_MODE:
        return False
    if not is_step1_completed():
        print("第一步未完成，下次继续")
        return True
    return False


def main():
    step_funcs = {
        1: download_car_pages,
        2: parse_js_to_html,
        3: parse_json_data,
        4: crack_html_files,
        5: generate_data_files,
        6: generate_csv,
    }

    if args.step:
        print(f"运行第 {args.step} 步")
        print(f"时间限制: {MAX_TIME_PER_STEP}秒 (0=不限制)")
        print(f"自动模式: {AUTO_MODE}")
        if args.step == 1:
            print(f"车型数量限制: {MAX_CARS_PER_RUN} (0=不限制)")

        if args.step == 1:
            step_funcs[1]()
            if check_and_continue():
                sys.exit(10)
            if AUTO_MODE and is_step1_completed():
                print("第一步完成，继续执行后续步骤")
        else:
            step_funcs[args.step]()
    else:
        download_car_pages()
        if check_and_continue():
            sys.exit(10)
        parse_js_to_html()
        parse_json_data()
        crack_html_files()
        generate_data_files()
        generate_csv()


if __name__ == "__main__":
    main()

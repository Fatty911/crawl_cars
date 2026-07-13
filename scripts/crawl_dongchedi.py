"""
懂车帝爬虫 - 爬取3年内上市车型的全部配置信息
使用 Selenium 绕过反爬
"""

import os
import sys
import shutil
import json
import time
import random
import re
import csv
import argparse
from datetime import date

from crawl_state.registry import ModelRegistry

# 字段名标准化映射表（网站原始字段名 -> 标准字段名）
HEADER_MAP = {
    '厂商指导价': '价格',
    '发动机': '发动机型号',
    '排量': '发动机排量',
    '最大扭矩': '扭矩',
    '最大功率': '功率',
    '变速箱': '变速器',
    '车身尺寸': '长x宽x高',
    '轴距': '轴距(mm)',
    '整备质量': '整备质量(kg)',
    '燃油标号': '燃油类型',
    'WLTC综合油耗': '油耗(L/100km)',
    'CLTC纯电续航': '纯电续航(km)',
    'NEDC纯电续航': '纯电续航(km)',
    '快充时间': '快充(小时)',
    '慢充时间': '慢充(小时)',
    '驱动方式': '驱动形式',
    '前悬架': '前悬挂',
    '后悬架': '后悬挂',
    '电动机总功率': '电机功率(kW)',
    '电动机总扭矩': '电机扭矩(N·m)',
    '电池能量密度': '电池能量密度(Wh/kg)',
    '百公里加速': '0-100km/h加速(s)',
    '最高车速': '最高车速(km/h)',
    '前轮胎规格': '前轮胎',
    '后轮胎规格': '后轮胎',
}

def normalize_car_fields(car):
    """标准化车型字段名，将网站原始字段名映射为标准字段名"""
    normalized = {}
    for key, value in car.items():
        new_key = HEADER_MAP.get(key, key)
        # 如果标准字段已有值且新值更详细，则更新
        if new_key in normalized and not normalized[new_key] and value:
            normalized[new_key] = value
        elif new_key not in normalized:
            normalized[new_key] = value
        elif value and normalized[new_key]:
            if len(str(value)) > len(str(normalized[new_key])):
                normalized[new_key] = value
    return normalized


parser = argparse.ArgumentParser(description="懂车帝爬虫")
parser.add_argument("--step", type=int, choices=[1, 2, 3, 4], help="运行指定步骤")
parser.add_argument(
    "--time-limit", type=int, default=0, help="每步最大运行时间(秒)，0表示不限制"
)
parser.add_argument(
    "--max-series", type=int, default=0, help="第二步最多爬取车系数，0表示不限制"
)
parser.add_argument(
    "--auto", action="store_true", help="全自动模式：未完成则exit code 10"
)
parser.add_argument(
    "--incremental", action="store_true", help="增量模式：只爬取新增车系，跳过已存在的"
)
parser.add_argument(
    "--debug-limit", type=int, default=0, help="调试模式限制爬取数量（配合 --incremental 使用）"
)
args = parser.parse_args()

MAX_TIME_PER_STEP = args.time_limit
MAX_SERIES_PER_RUN = args.max_series
AUTO_MODE = args.auto
INCREMENTAL_MODE = args.incremental
DEBUG_MODE = args.debug_limit > 0
WORKFLOW_DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"
DEBUG_OUTPUT_MAX_ROWS = int(os.getenv("DEBUG_OUTPUT_MAX_ROWS", "30"))

# 调试模式：强制开启增量扫描模式，并限制爬取数量
if DEBUG_MODE:
    INCREMENTAL_MODE = True
    MAX_SERIES_PER_RUN = args.debug_limit
    print(f"调试模式：限制爬取 {args.debug_limit} 个车系，启用增量扫描模式")

CRAWL_MIN_DELAY_SECONDS = float(os.getenv("CRAWL_MIN_DELAY_SECONDS", "8"))
CRAWL_MAX_DELAY_SECONDS = float(os.getenv("CRAWL_MAX_DELAY_SECONDS", "20"))
DCD_PAGE_LOAD_TIMEOUT = int(os.getenv("DCD_PAGE_LOAD_TIMEOUT", "60"))
DCD_RENDERER_TIMEOUT_RESTART_THRESHOLD = int(
    os.getenv("DCD_RENDERER_TIMEOUT_RESTART_THRESHOLD", "3")
)
DCD_NETWORK_ERROR_RESTART_THRESHOLD = int(
    os.getenv("DCD_NETWORK_ERROR_RESTART_THRESHOLD", "5")
)
DCD_ENTITY_BATCH_SIZE = int(os.getenv("DCD_ENTITY_BATCH_SIZE", "20"))
DCD_HEARTBEAT_INTERVAL = int(os.getenv("DCD_HEARTBEAT_INTERVAL", "30"))  # browser 心跳检测间隔
DCD_SCROLL_STEPS = int(os.getenv("DCD_SCROLL_STEPS", "10"))  # 分段滚动步数
DCD_SCROLL_PAUSE_MIN = float(os.getenv("DCD_SCROLL_PAUSE_MIN", "0.5"))
DCD_SCROLL_PAUSE_MAX = float(os.getenv("DCD_SCROLL_PAUSE_MAX", "1.5"))
if CRAWL_MAX_DELAY_SECONDS < CRAWL_MIN_DELAY_SECONDS:
    CRAWL_MAX_DELAY_SECONDS = CRAWL_MIN_DELAY_SECONDS

# 工作目录
working_dir = os.path.dirname(os.path.abspath(__file__))
dcd_dir = os.path.join(working_dir, "dongchedi")
dcd_json_dir = os.path.join(dcd_dir, "json")
dcd_exception_dir = os.path.join(dcd_dir, "exception")

for d in [dcd_dir, dcd_json_dir, dcd_exception_dir]:
    if not os.path.exists(d):
        os.makedirs(d)

# 进度文件
progress_file = os.path.join(dcd_dir, "progress.json")
if os.path.exists(progress_file):
    with open(progress_file, "r", encoding="utf-8") as f:
        progress = json.load(f)
    if "--restart" in sys.argv:
        progress = {}
        print("已重置进度")
    else:
        print("从上次进度继续（使用 --restart 可重新开始）")
else:
    progress = {}

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
DCD_CATEGORY_KEYS = [
    "level_name",
    "series_level_name",
    "car_level_name",
    "type_name",
    "sub_type_name",
    "category_name",
    "rank_name",
]

CURRENT_YEAR = 2026
MIN_YEAR = 0  # 爬取所有车型


def is_pure_gas_car(row, all_headers):
    """判断是否为纯油车（非插混、非纯电、非增程）"""
    for h in all_headers:
        if any(kw in h for kw in FUEL_TYPE_KEYWORDS):
            val = row.get(h, "-")
            if val and val != "-":
                if any(k in val for k in ["电", "插", "增程"]):
                    return False
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


def is_excluded_vehicle_level(level):
    if not level:
        return False
    normalized = re.sub(r"\s+", "", str(level).upper())
    return any(kw.upper() in normalized for kw in EXCLUDED_VEHICLE_LEVEL_KEYWORDS)


def is_supported_vehicle_row(row, all_headers):
    return is_supported_vehicle_level(get_vehicle_level(row, all_headers))


def get_dcd_series_category(series):
    for key in DCD_CATEGORY_KEYS:
        val = series.get(key)
        if val:
            return str(val)
    for key, val in series.items():
        if any(token in key.lower() for token in ["level", "type", "category", "rank"]):
            if isinstance(val, str) and val:
                return val
    return ""


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


def create_browser(max_attempts=3):
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service

    last_error = None
    for attempt in range(1, max_attempts + 1):
        browser = None
        try:
            chrome_options = webdriver.ChromeOptions()
            chrome_options.add_argument("--headless=new")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_argument("--remote-debugging-port=0")
            chrome_options.add_argument("--window-size=1365,900")
            if os.getenv("PROXY_ENABLED") == "true":
                chrome_proxy = os.getenv("CHROME_PROXY_SERVER", "http://127.0.0.1:7890")
                chrome_options.add_argument(f"--proxy-server={chrome_proxy}")
            chrome_options.add_argument(
                "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            cb = find_chrome_binary()
            if cb:
                chrome_options.binary_location = cb
            cd = find_chromedriver()
            if cd:
                browser = webdriver.Chrome(service=Service(cd), options=chrome_options)
            else:
                browser = webdriver.Chrome(options=chrome_options)
            browser.set_page_load_timeout(DCD_PAGE_LOAD_TIMEOUT)
            browser.set_script_timeout(30)
            browser.execute_cdp_cmd(
                "Page.addScriptToEvaluateOnNewDocument",
                {
                    "source": 'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
                },
            )
            return browser
        except Exception as exc:
            last_error = exc
            print(f"浏览器初始化失败，第 {attempt}/{max_attempts} 次: {exc}")
            if browser is not None:
                try:
                    browser.quit()
                except Exception:
                    pass
            if attempt < max_attempts:
                time.sleep(10 * attempt)

    raise RuntimeError(f"浏览器初始化连续失败 {max_attempts} 次") from last_error


def save_progress():
    with open(progress_file, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False)


def check_time_limit(start_time):
    if MAX_TIME_PER_STEP > 0:
        elapsed = time.time() - start_time
        if elapsed >= MAX_TIME_PER_STEP:
            print(f"已达到时间限制 {MAX_TIME_PER_STEP}秒，保存进度并退出")
            save_progress()
            if AUTO_MODE:
                print("未完成，等待下次继续")
                sys.exit(10)
            return True
    return False


def check_series_limit(crawled_count):
    if MAX_SERIES_PER_RUN > 0 and crawled_count >= MAX_SERIES_PER_RUN:
        print(f"已达到车系数量限制 {MAX_SERIES_PER_RUN}，保存进度并退出")
        save_progress()
        if AUTO_MODE:
            if DEBUG_MODE:
                print("调试模式已达到车系数量限制，准备进入后续解析")
                return True
            print("未完成，等待下次继续")
            sys.exit(10)
        return True
    return False


def human_delay(label):
    delay = random.uniform(CRAWL_MIN_DELAY_SECONDS, CRAWL_MAX_DELAY_SECONDS)
    print(f"{label}后等待 {delay:.1f} 秒，模拟人工浏览节奏")
    time.sleep(delay)


def is_renderer_timeout(exc):
    text = str(exc)
    return "Timed out receiving message from renderer" in text or "timeout: Timed out" in text


def is_network_navigation_error(exc):
    text = str(exc)
    markers = [
        "net::ERR_CONNECTION_CLOSED",
        "net::ERR_CONNECTION_RESET",
        "net::ERR_TUNNEL_CONNECTION_FAILED",
        "net::ERR_PROXY_CONNECTION_FAILED",
        "net::ERR_SOCKS_CONNECTION_FAILED",
        "net::ERR_TIMED_OUT",
    ]
    return any(marker in text for marker in markers)


def check_browser_heartbeat(browser, last_heartbeat, reason="心跳检测"):
    """检测浏览器是否仍然响应，卡死则重启"""
    import time
    if time.time() - last_heartbeat >= DCD_HEARTBEAT_INTERVAL:
        try:
            # 尝试执行简单 JS，验证浏览器存活
            browser.execute_script("return 1")
            return browser, time.time()
        except Exception as e:
            print(f"  ⚠ {reason}: 浏览器无响应 ({e})，强制重启...")
            browser = restart_browser(browser, reason)
            return browser, time.time()
    return browser, last_heartbeat


def restart_browser(browser, reason):
    print(f"  {reason}，重启 Chrome 后继续")
    try:
        browser.quit()
    except Exception as quit_exc:
        print(f"  关闭旧浏览器失败，继续重启: {quit_exc}")
    return create_browser()


def get_existing_payload_ids():
    """返回当前工作区真实存在的车系配置缓存 ID。"""
    if not os.path.isdir(dcd_json_dir):
        return set()
    return {
        os.path.splitext(name)[0]
        for name in os.listdir(dcd_json_dir)
        if (name.endswith(".json") or name.endswith(".html"))
        and os.path.getsize(os.path.join(dcd_json_dir, name)) > 0
    }


def get_existing_html_ids():
    """兼容旧调用：返回当前工作区真实存在的车系配置缓存 ID。"""
    return get_existing_payload_ids()


def reconcile_step2_progress(series_list=None):
    """确保 step2 进度只包含当前工作区有 HTML 文件的车系。"""
    crawled = [str(sid) for sid in progress.get("crawled_series", [])]
    if not crawled:
        return crawled

    payload_ids = get_existing_payload_ids()
    valid_series_ids = None
    if series_list:
        valid_series_ids = {str(series["id"]) for series in series_list}

    valid_crawled = []
    for sid in crawled:
        if sid not in payload_ids:
            continue
        if valid_series_ids is not None and sid not in valid_series_ids:
            continue
        valid_crawled.append(sid)

    if len(valid_crawled) != len(crawled):
        missing = len(crawled) - len(valid_crawled)
        print(f"发现 {missing} 条 step2 进度缺少对应配置缓存，已重置为未爬取")
        progress["crawled_series"] = valid_crawled
        progress.pop("parsed_data", None)
        save_progress()

    return valid_crawled


def is_step2_completed():
    if "series_list" not in progress:
        return False
    series_list = progress.get("series_list", [])
    if not series_list:
        return False
    crawled = set(reconcile_step2_progress(series_list))
    if not crawled:
        return False
    series_ids = {str(series["id"]) for series in series_list}
    return series_ids.issubset(crawled)


def is_debug_step2_completed():
    if not DEBUG_MODE or MAX_SERIES_PER_RUN <= 0:
        return False
    series_list = progress.get("series_list", [])
    if not series_list:
        return False
    required = min(MAX_SERIES_PER_RUN, len(series_list))
    if required <= 0:
        return False
    series_ids = {str(series["id"]) for series in series_list}
    payload_ids = get_existing_payload_ids()
    return len(series_ids & payload_ids) >= required


def require_non_empty_rows(all_rows, stage):
    if not all_rows:
        raise SystemExit(f"{stage} 未解析到任何车型数据，拒绝生成空结果")


dongchedi_registry = ModelRegistry("dongchedi")


def _get_existing_series_ids():
    """获取本地已存车系的series_id集合（优先从注册表读取，fallback 到 HTML 文件扫描）"""
    if not dongchedi_registry.is_first_run():
        ids = dongchedi_registry.get_existing_uids()
        if ids:
            return ids
    existing = set()
    if not os.path.exists(dcd_json_dir):
        return existing
    for filename in os.listdir(dcd_json_dir):
        if filename.endswith('.html'):
            series_id = filename.replace('.html', '')
            if os.path.getsize(os.path.join(dcd_json_dir, filename)) > 0:
                existing.add(series_id)
    return existing


# 品牌销量热度排序：按中国汽车市场销量排行，热门品牌优先
# 来源：2025-2026年乘联会批发销量排行（综合乘用车+新能源）
BRAND_HEAT_ORDER = [
    "比亚迪", "吉利汽车", "长安汽车", "奇瑞", "上汽大众", "一汽大众",
    "广汽丰田", "一汽丰田", "本田", "东风日产", "五菱汽车", "别克",
    "宝马", "奔驰", "奥迪", "特斯拉", "理想汽车", "蔚来", "问界",
    "零跑汽车", "极氪", "小鹏汽车", "领克", "哈弗", "宝骏",
    "红旗", "广汽传祺", "东风本田", "北京现代", "长安欧尚", "长安马自达",
    "广汽本田", "沃尔沃", "凯迪拉克", "路虎", "保时捷", "雷克萨斯",
    "长城炮", "坦克", "捷途", "星途", "传祺", "捷达", " smart", "MINI",
    "埃安", "深蓝汽车", "启辰", "阿维塔", "岚图", "智己", "极狐",
    "腾势", "方程豹", "仰望", "哪吒汽车", "北京越野", "北京汽车",
    "北汽新能源", "东风风行", "江淮", "东风风神", "上汽大通",
    "标致", "雪铁龙", "雪佛兰", "福特", "起亚", "马自达",
    "斯柯达", "三菱", "斯巴鲁", "铃木", "众泰", "海马",
]


def sort_series_by_brand_heat(series_list):
    """按品牌销量热度分组轮询排列，热门品牌优先出场但不同品牌交替出现。

    目的：有限时间内爬到的车系覆盖多个热门品牌，而非单品牌垄断，
    最大化和 autohome 的多品牌双源重叠率。
    """
    if not series_list:
        return series_list

    # 构建品牌→排名映射
    heat_map = {}
    for idx, brand in enumerate(BRAND_HEAT_ORDER):
        normalized = brand.strip().lower().replace(" ", "")
        heat_map[normalized] = idx

    # 按品牌分组，组内保持原始顺序
    groups = {}
    for s in series_list:
        brand = s.get("brand", "").strip().lower().replace(" ", "")
        groups.setdefault(brand, []).append(s)

    # 按品牌热度排序各组
    sorted_brands = sorted(groups.keys(), key=lambda b: heat_map.get(b, 999))

    # 轮询交错排列：每个品牌依次取一个车系
    result = []
    idx_map = {b: 0 for b in sorted_brands}
    while True:
        added = False
        for brand in sorted_brands:
            if idx_map[brand] < len(groups[brand]):
                result.append(groups[brand][idx_map[brand]])
                idx_map[brand] += 1
                added = True
        if not added:
            break

    top_brands = []
    seen = set()
    for s in result[:20]:
        b = s.get("brand", "")
        if b not in seen:
            top_brands.append(b)
            seen.add(b)
    print(f"车系按品牌热度轮询重排完成，前10品牌: {top_brands[:10]}")
    return result


def _scan_all_series():
    """全量扫描所有车系列表（仅收集基础信息，不爬详情）"""
    print("=" * 70)
    print("增量扫描模式：全量扫描所有车系...")
    print("=" * 70)

    import requests

    api = "https://www.dongchedi.com/motor/pc/car/brand/select_series_v2"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.0",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Origin": "https://www.dongchedi.com",
        "Referer": "https://www.dongchedi.com/auto/library/x-x-x-x-x-x-x-x-x-x-x",
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Requested-With": "XMLHttpRequest",
    }
    session = requests.Session()

    all_series = []
    seen_ids = set()
    page = 1

    while True:
        try:
            body = {"limit": 30, "page": page, "city_name": ""}
            r = session.post(api, headers=headers, data=body, timeout=20)
            try:
                d = r.json()
            except ValueError:
                page += 1
                continue

            if d.get("status") != 0:
                break

            data = d.get("data", {})
            series_data = data.get("series") or []
            if not series_data:
                break

            for s in series_data:
                sid = str(s.get("id") or s.get("concern_id") or "")
                sname = s.get("outter_name", "")
                sbrand = s.get("brand_name", "")
                category = get_dcd_series_category(s)
                if category and is_excluded_vehicle_level(category):
                    continue
                if sid and sname and sid not in seen_ids:
                    seen_ids.add(sid)
                    item = {"id": sid, "name": sname, "brand": sbrand}
                    if category:
                        item["category"] = category
                    all_series.append(item)

            page += 1

            # 调试/限制模式下：可以提前终止扫描
            if MAX_SERIES_PER_RUN > 0 and len(all_series) >= MAX_SERIES_PER_RUN * 3:
                print(f"接近数量限制，提前终止车系扫描（已扫描 {len(all_series)} 个车系）")
                break

            if page > 100:
                print("警告：分页超过100页，强制结束以防止无限循环")
                break

        except Exception as e:
            print(f"获取车系列表时发生异常: {e}")
            break

    print(f"全量扫描完成：共 {len(all_series)} 个唯一车系")
    return all_series


# 第一步：获取所有车系ID
def get_series_list(browser=None):
    """通过懂车帝分页API获取全部车系（无需浏览器），增量模式下只返回新增车系"""
    print("第一步：获取所有车系列表")

    # 增量模式：先全量扫描所有车系，与本地已有HTML对比，仅返回新增车系
    if INCREMENTAL_MODE:
        print("=" * 70)
        print("增量模式：先全量扫描所有车系列表，然后仅爬取新增车系...")
        print("=" * 70)

        all_series = _scan_all_series()
        existing_ids = _get_existing_series_ids()
        new_series = [s for s in all_series if str(s.get("id")) not in existing_ids]

        print(f"全量扫描完成：共 {len(all_series)} 个车系，新增 {len(new_series)} 个，已有 {len(all_series) - len(new_series)} 个")

        if not new_series:
            print("增量模式：未发现新增车系，本次可跳过详细抓取")
            progress["series_list"] = []
            save_progress()
            return []

        progress["series_list"] = new_series
        save_progress()
        print(f"增量模式：将爬取 {len(new_series)} 个新增车系")
        return new_series

    # 非增量模式：原有逻辑

    cached_series_list = progress.get("series_list", [])
    if cached_series_list:
        print(
            f"已有缓存车系列表 {len(cached_series_list)} 个，本次会优先刷新；刷新失败则回退使用缓存"
        )

    series_list = []
    seen_ids = set()
    import requests

    api = "https://www.dongchedi.com/motor/pc/car/brand/select_series_v2"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Origin": "https://www.dongchedi.com",
        "Referer": "https://www.dongchedi.com/auto/library/x-x-x-x-x-x-x-x-x-x-x",
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Requested-With": "XMLHttpRequest",
    }
    session = requests.Session()

    print("通过分页API获取全部车系...")
    page = 1
    total_count = None
    consecutive_empty = 0
    excluded_series = []

    while True:
        try:
            body = {"limit": 30, "page": page, "city_name": ""}
            r = session.post(api, headers=headers, data=body, timeout=20)
            try:
                d = r.json()
            except ValueError as exc:
                snippet = r.text[:200].replace("\n", " ")
                raise ValueError(
                    f"非JSON响应 status={r.status_code}, "
                    f"content-type={r.headers.get('content-type')}, body={snippet!r}"
                ) from exc

            if d.get("status") != 0:
                print(f"page {page}: API异常: {d.get('message')}")
                break

            data = d.get("data", {})
            series = data.get("series") or []
            if total_count is None:
                total_count = data.get("series_count", 0)
                print(
                    f"服务端共 {total_count} 个车系，每页30条，共需约 {(total_count + 29) // 30} 页"
                )

            if not series:
                consecutive_empty += 1
                if consecutive_empty >= 3:
                    print(f"连续{consecutive_empty}页为空，停止")
                    break
                human_delay(f"page {page} 空结果")
                page += 1
                continue

            consecutive_empty = 0
            new_count = 0
            for s in series:
                sid = str(s.get("id") or s.get("concern_id") or "")
                sname = s.get("outter_name", "")
                sbrand = s.get("brand_name", "")
                category = get_dcd_series_category(s)
                if category and is_excluded_vehicle_level(category):
                    excluded_series.append(
                        {
                            "id": sid,
                            "name": sname,
                            "brand": sbrand,
                            "category": category,
                        }
                    )
                    continue
                if sid and sname and sid not in seen_ids:
                    seen_ids.add(sid)
                    item = {"id": sid, "name": sname, "brand": sbrand}
                    if category:
                        item["category"] = category
                    series_list.append(item)
                    new_count += 1

            print(
                f"page {page}: +{new_count} 新增，累计 {len(series_list)}/{total_count}"
            )

            if total_count and len(series_list) >= total_count:
                print("已获取全部车系")
                break

            page += 1
            human_delay(f"page {page - 1} API访问")

        except Exception as e:
            print(f"page {page} 异常: {e}，重试...")
            human_delay(f"page {page} API异常")
            consecutive_empty += 1
            if consecutive_empty >= 5:
                break
            continue

    print(f"\n共获取 {len(series_list)} 个目标车系")
    if excluded_series:
        print(f"已按明确级别跳过 {len(excluded_series)} 个非目标车系")

    if series_list:
        progress["series_list"] = series_list
        if excluded_series:
            progress["excluded_series"] = excluded_series
        save_progress()
        return series_list

    if cached_series_list:
        print(f"本次未获取到新车系列表，回退使用缓存 {len(cached_series_list)} 个车系")
        return cached_series_list

    return series_list


def _extract_car_ids(value):
    car_ids = []

    def walk(node):
        if isinstance(node, dict):
            for key, item in node.items():
                if key in {"car_id", "carId", "id"} and isinstance(item, (int, str)):
                    text = str(item)
                    if text.isdigit():
                        car_ids.append(text)
                walk(item)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(value)
    seen = set()
    result = []
    for car_id in car_ids:
        if car_id not in seen:
            seen.add(car_id)
            result.append(car_id)
    return result


def _request_dongchedi_json(url, params=None):
    import requests

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.dongchedi.com/",
    }
    for attempt in range(1, 4):
        try:
            response = requests.get(url, params=params, headers=headers, timeout=30)
            break
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
            if attempt == 3:
                raise
            delay = 2 ** (attempt - 1)
            print(f"  API请求瞬时失败，第 {attempt}/3 次: {exc}，{delay} 秒后重试")
            time.sleep(delay)
    response.raise_for_status()
    return response.json()


def fetch_series_entity_payload(series):
    series_id = str(series["id"])
    garage_url = f"https://www.dongchedi.com/motor/garage/get_cars_by_series_id/{series_id}/"
    garage_payload = _request_dongchedi_json(garage_url, {"no_sales": 1})
    if garage_payload.get("status") not in (0, "0"):
        raise RuntimeError(f"garage API status={garage_payload.get('status')} message={garage_payload.get('message')}")

    car_ids = _extract_car_ids(garage_payload.get("data", garage_payload))
    if not car_ids:
        raise RuntimeError("garage API 未返回 car_id")

    car_info = []
    properties = []
    property_keys = set()
    entity_url = "https://www.dongchedi.com/motor/car_page/v4/get_entity_json/"
    for start in range(0, len(car_ids), max(1, DCD_ENTITY_BATCH_SIZE)):
        batch = car_ids[start:start + max(1, DCD_ENTITY_BATCH_SIZE)]
        entity_payload = _request_dongchedi_json(entity_url, {"car_id_list": ",".join(batch)})
        if entity_payload.get("status") != "success":
            raise RuntimeError(
                f"entity API status={entity_payload.get('status')} message={entity_payload.get('message')}"
            )
        data = entity_payload.get("data", {})
        batch_car_info = data.get("car_info")
        batch_properties = data.get("properties")
        if not isinstance(batch_car_info, list) or not batch_car_info:
            raise RuntimeError("entity API car_info 为空")
        if not isinstance(batch_properties, list) or not batch_properties:
            raise RuntimeError("entity API properties 为空")
        car_info.extend(batch_car_info)
        for prop in batch_properties:
            key = prop.get("key")
            if key and key in property_keys:
                continue
            if key:
                property_keys.add(key)
            properties.append(prop)

    return {
        "source": "dongchedi_entity_api",
        "series_info": series,
        "car_ids": car_ids,
        "data": {"car_info": car_info, "properties": properties},
    }


def is_login_required_next_data(next_data):
    page = next_data.get("page")
    page_props = next_data.get("props", {}).get("pageProps", {})
    redirect = page_props.get("redirect", "")
    return page == "/login-required" or "/login-required" in str(redirect)


# 第二步：爬取每个车系的配置页面
def crawl_series_config(browser, series_list):
    """通过懂车帝公开 JSON API 获取每个车系的配置参数。"""
    print("第二步：通过懂车帝 API 获取车系配置")

    # 按品牌销量热度重排：热门品牌优先爬取，提高有限时间内与 autohome 的双源匹配率
    series_list = sort_series_by_brand_heat(series_list)

    crawled = reconcile_step2_progress(series_list)
    initial_crawled_count = len(crawled)
    start_time = time.time()
    skipped_count = 0
    need_crawl = len(series_list) - initial_crawled_count
    attempted_count = 0  # 调试模式：统计尝试过的车系数（含超时/失败）

    print(f"车系总数: {len(series_list)}，已有配置缓存: {initial_crawled_count}，需爬取: {need_crawl}")

    for idx, series in enumerate(series_list):
        series_id = series["id"]
        series_name = series["name"]

        if series_id in crawled:
            skipped_count += 1
            continue

        # 增量模式和全量模式都检查时间限制和数量限制
        # 调试模式用 attempted_count 确保即使全部超时也能在限制数量后停止
        if DEBUG_MODE:
            attempted_count += 1
            if check_time_limit(start_time) or attempted_count > MAX_SERIES_PER_RUN:
                print(f"调试模式：已尝试 {attempted_count - 1} 个车系，达到限制 {MAX_SERIES_PER_RUN}，停止爬取")
                break
        else:
            if check_time_limit(start_time) or check_series_limit(len(crawled) - initial_crawled_count):
                return browser

        print(
            f"[{idx + 1}/{len(series_list)}] 正在爬取: {series_name} (ID: {series_id})"
        )

        saved_payload = False

        try:
            json_file = os.path.join(dcd_json_dir, f"{series_id}.json")
            if os.path.exists(json_file):
                print(f"  车系{series_id} API缓存已存在，跳过")
                saved_payload = True
            else:
                payload = fetch_series_entity_payload(series)
                with open(json_file, "w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False)
                saved_payload = True
                print(f"  API缓存完成：{len(payload.get('car_ids', []))} 个 car_id，{len(payload.get('data', {}).get('car_info', []))} 个车型")
        except Exception as e:
            print(f"  爬取异常: {e}")
            with open(
                os.path.join(dcd_exception_dir, "exception.txt"), "a", encoding="utf-8"
            ) as f:
                f.write(f"{series_id} {series_name}: {e}\n")

        if saved_payload and series_id not in crawled:
            crawled.append(series_id)
        progress["crawled_series"] = crawled
        save_progress()
        human_delay(f"保存{series_name}配置")

    new_crawled = len(crawled) - initial_crawled_count
    newly_registered = [sid for sid in crawled[initial_crawled_count:] if not dongchedi_registry.is_registered(sid)]
    if newly_registered:
        dongchedi_registry.register_uids(newly_registered)
        print(f"已注册 {len(newly_registered)} 个新车系到注册表（共 {dongchedi_registry.count()} 个）")
    if INCREMENTAL_MODE:
        print(f"增量模式完成：新增 {new_crawled} 个车系，跳过 {skipped_count} 个已存在车系")
    else:
        print(f"第二步完成：新增 {new_crawled} 个车系")
    return browser


# 第三步：解析配置页面，提取数据
def parse_config_pages(series_list):
    """解析保存的配置页面HTML，提取配置数据"""
    print("第三步：解析配置页面")

    try:
        from bs4 import BeautifulSoup
    except ModuleNotFoundError:
        BeautifulSoup = None

    all_rows = []
    all_headers = []

    series_map = {s["id"]: s for s in series_list}

    for html_file in os.listdir(dcd_json_dir):
        if not (html_file.endswith(".html") or html_file.endswith(".json")):
            continue

        series_id = os.path.splitext(html_file)[0]
        series_info = series_map.get(series_id, {})
        series_name = series_info.get("name", "")
        brand_name = series_info.get("brand", "")

        print(f"正在解析: {brand_name} {series_name} (ID: {series_id})")

        with open(os.path.join(dcd_json_dir, html_file), "r", encoding="utf-8") as f:
            file_content = f.read()

        html_content = file_content if html_file.endswith(".html") else ""
        soup = BeautifulSoup(html_content, "html.parser") if BeautifulSoup and html_content else None

        # 优先尝试从__NEXT_DATA__提取数据
        car_names = []
        car_data = {}
        raw_data = {}
        if html_file.endswith(".json"):
            try:
                import json as json_mod

                payload = json_mod.loads(file_content)
                if payload.get("source") == "dongchedi_entity_api":
                    raw_data = payload.get("data", {})
                    payload_series_info = payload.get("series_info", {})
                    if payload_series_info:
                        series_info = {**payload_series_info, **series_info}
                        series_name = series_info.get("name", series_name)
                        brand_name = series_info.get("brand", brand_name)
                    print("  找到懂车帝 entity API 缓存，尝试解析配置数据...")
            except Exception as e:
                print(f"  解析 entity API 缓存异常: {e}")
        next_data_match = re.search(
            r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html_content, re.DOTALL
        )
        if next_data_match and not raw_data:
            try:
                import json as json_mod

                next_data = json_mod.loads(next_data_match.group(1))
                if is_login_required_next_data(next_data):
                    print("  拒绝 login-required __NEXT_DATA__ 登录壳")
                else:
                    print(f"  找到__NEXT_DATA__，尝试解析配置数据...")

                    # 尝试从props.pageProps.rawData提取数据
                    props = next_data.get("props", {})
                    page_props = props.get("pageProps", {})
                    raw_data = page_props.get("rawData", {})
            except Exception as e:
                print(f"  解析__NEXT_DATA__异常: {e}")

        if raw_data:
            try:
                    # 提取车型信息
                    car_info = raw_data.get("car_info", [])
                    if car_info:
                        # 车型名称列表
                        car_names = [info.get("car_name", "") for info in car_info]

                        # 提取配置属性映射 (key -> text)
                        properties = raw_data.get("properties", [])
                        prop_mapping = {}  # key -> text
                        prop_type_mapping = {}  # key -> type

                        for prop in properties:
                            prop_key = prop.get("key")
                            prop_text = prop.get("text")
                            prop_type = prop.get("type")

                            if prop_key and prop_text:
                                prop_mapping[prop_key] = prop_text
                                prop_type_mapping[prop_key] = prop_type

                            # 处理有sub_list的属性（type=3）
                            if prop_type == 3:
                                sub_list = prop.get("sub_list")
                                if sub_list:
                                    for sub in sub_list:
                                        sub_key = sub.get("key")
                                        sub_text = sub.get("text")
                                        if sub_key and sub_text:
                                            # 使用父级text作为前缀
                                            full_text = f"{prop_text} - {sub_text}"
                                            prop_mapping[sub_key] = full_text
                                            prop_type_mapping[sub_key] = prop_type

                        # 为每个车型提取配置值
                        num_cars = len(car_info)

                        # 首先添加基本信息
                        car_data["车型名称"] = car_names

                        # 年款信息
                        year_values = [info.get("car_year", "") for info in car_info]
                        if any(year_values):
                            car_data["年款"] = year_values

                        # 官方指导价
                        price_values = [
                            info.get("official_price", "") for info in car_info
                        ]
                        if any(price_values):
                            car_data["官方指导价"] = price_values

                        # 厂商/品牌
                        brand_values = [info.get("brand_name", "") for info in car_info]
                        if any(brand_values):
                            car_data["厂商"] = brand_values
                        # 从series_info取品牌级的品牌名写入系列品牌
                        series_brand = series_info.get("brand", "") if series_info else ""
                        if series_brand:
                            car_data["系列品牌"] = [series_brand] * num_cars

                        # 收集所有车型中出现的所有配置项key
                        all_config_keys = set()
                        for car in car_info:
                            info = car.get("info", {})
                            all_config_keys.update(info.keys())

                        # 为每个配置项提取所有车型的值
                        for config_key in all_config_keys:
                            if config_key in prop_mapping:
                                prop_text = prop_mapping[config_key]
                            else:
                                # 如果映射中没有，使用key本身
                                prop_text = config_key

                            values = []
                            for car in car_info:
                                info = car.get("info", {})
                                config_value = info.get(config_key, {})
                                if isinstance(config_value, dict):
                                    # 提取value字段
                                    value = config_value.get("value", "")
                                else:
                                    value = str(config_value) if config_value else ""
                                values.append(value)

                            if any(values):  # 只有有值的配置项才添加
                                car_data[prop_text] = values
                                if prop_text not in all_headers:
                                    all_headers.append(prop_text)

                        print(
                            f"  从配置 payload 解析到 {len(car_info)} 个车型, {len(car_data)} 个配置属性"
                        )
            except Exception as e:
                print(f"  解析配置 payload 异常: {e}")

        # 如果__NEXT_DATA__解析失败，则尝试原有解析方式
        if not car_data:
            # 懂车帝配置页面通常用表格或div列表展示
            # 尝试多种选择器

            # 方式1: 查找表格
            tables = soup.find_all("table") if soup else []
            if tables:
                for table in tables:
                    rows = table.find_all("tr")
                    for row in rows:
                        cells = row.find_all(["th", "td"])
                        if len(cells) >= 2:
                            header = cells[0].get_text(strip=True)
                            values = [c.get_text(strip=True) for c in cells[1:]]

                            if header == "车型名称" or header == "官方指导价":
                                if header == "车型名称":
                                    car_names = values
                            if header and header not in car_data:
                                car_data[header] = values
                                if header not in all_headers:
                                    all_headers.append(header)

            # 方式2: 查找div结构的配置列表（适配懂车帝新页面结构）
            if not car_data:
                # 新的选择器匹配懂车帝2026年页面结构
                param_rows = soup.select(
                    '[class*="table_row"], [class*="row_"], [class*="cell_row"], [class*="param-row"], [class*="config-row"]'
                ) if soup else []
                for row in param_rows:
                    # 尝试多种选择器获取标签和值
                    label_elem = row.select_one(
                        '[class*="label"], [class*="cell_label"], .table_is-label__1wIhd label'
                    )
                    if not label_elem:
                        # 如果没有明确标签，尝试第一列
                        first_col = row.select_one(
                            '.table_col__3Pc3_:first-child, [class*="col"]:first-child'
                        )
                        if first_col:
                            label_elem = first_col.select_one(
                                '[class*="label"], [class*="cell_label"], label'
                            )

                    # 获取值列
                    value_cols = row.select(
                        '.table_col__3Pc3_:not(:first-child), [class*="col"]:not(:first-child), [class*="cell_normal"]'
                    )
                    if not value_cols:
                        value_cols = row.select('[class*="cell"], [class*="item"]')

                    if label_elem and value_cols:
                        header = label_elem.get_text(strip=True)
                        values = [col.get_text(strip=True) for col in value_cols]
                        if header and header not in car_data:
                            car_data[header] = values
                            if header not in all_headers:
                                all_headers.append(header)

        if not car_data:
            print("  未能解析到配置数据，跳过")
            continue

        # 获取年款信息用于过滤
        year_values = car_data.get("年款", [])
        if not car_names:
            car_names = car_data.get("车型名称", [])

        num_cars = max((len(v) for v in car_data.values()), default=0)

        for i in range(num_cars):
            # 年款过滤
            year_str = year_values[i] if i < len(year_values) else ""
            year_match = re.search(r"(\d{4})", year_str)
            if year_match:
                year = int(year_match.group(1))
                if year < MIN_YEAR:
                    continue
            # 品牌：优先 series_info，再 __NEXT_DATA__ 系列品牌，再厂商，再车系名推导
            final_brand = brand_name
            if not final_brand:
                series_brand_list = car_data.get("系列品牌", [])
                final_brand = series_brand_list[i] if i < len(series_brand_list) else ""
            if not final_brand:
                mfr_values = car_data.get("厂商", [])
                mfr = mfr_values[i] if i < len(mfr_values) else ""
                if mfr:
                    final_brand = mfr
            if not final_brand and series_name:
                # 按长度降序排列，长前缀优先匹配，避免"吉利"在"吉利银河"前误匹配
                brand_prefixes = ['吉利银河', '凯迪拉克', '雷克萨斯', '英菲尼迪', '雪铁龙', '比亚迪', '保时捷', '沃尔沃', '特斯拉', '阿维塔', '斯柯达', '雪佛兰', '马自达', '宝马', '奔驰', '奥迪', '大众', '丰田', '本田', '日产', '别克', '福特', '现代', '起亚', '吉利', '长城', '红旗', '领克', '极氪', '小鹏', '理想', '蔚来', '零跑', '问界', '埃安', '极狐', '岚图', '智己', '路虎', '捷豹', '林肯', '捷达', '五菱', '宝骏', 'WEY', '坦克', '欧拉', '哈弗', '魏牌', '标致']
                for bp in brand_prefixes:
                    if series_name.startswith(bp):
                        final_brand = bp
                        break
            row = {
                "品牌": final_brand,
                "车系": series_name,
                "车系ID": series_id,
                "车型名称": car_names[i] if i < len(car_names) else "",
                "年款": year_str,
            }
            for header in all_headers:
                vals = car_data.get(header, [])
                row[header] = vals[i] if i < len(vals) else "-"
            if not is_supported_vehicle_row(row, all_headers):
                continue
            fill_pure_gas_defaults(row, all_headers)
            all_rows.append(row)

    print(f"共解析 {len(all_rows)} 条车型数据")
    return all_rows, all_headers


# 第四步：生成CSV
def generate_output(all_rows, all_headers):
    """生成CSV输出文件（全部属性）"""
    print("第四步：生成输出文件")
    today = date.today().strftime("%Y%m%d")

    if WORKFLOW_DEBUG_MODE and DEBUG_OUTPUT_MAX_ROWS > 0 and len(all_rows) > DEBUG_OUTPUT_MAX_ROWS:
        print(f"Debug模式：输出从 {len(all_rows)} 条截断为 {DEBUG_OUTPUT_MAX_ROWS} 条，避免缩小稳定全量 Pages")
        all_rows = all_rows[:DEBUG_OUTPUT_MAX_ROWS]

    fixed_headers = ["品牌", "车系", "车系ID", "车型名称", "年款"]
    fieldnames = fixed_headers + [h for h in all_headers if h not in fixed_headers]

    csv_path = os.path.join(working_dir, f"dongchedi_{today}.csv")
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in all_rows:
            writer.writerow({h: row.get(h, "-") for h in fieldnames})

    json_path = os.path.join(working_dir, f"dongchedi_{today}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        # 标准化字段名
        normalized_rows = [normalize_car_fields(row) for row in all_rows]
        json.dump(normalized_rows, f, ensure_ascii=False, indent=2)

    print("第四步完成")
    print(f"  CSV:  {csv_path}")
    print(f"  JSON: {json_path}")
    print(f"  共{len(all_rows)} 条车型数据")


def main():
    step_funcs = {
        1: get_series_list,
        2: crawl_series_config,
        3: parse_config_pages,
        4: generate_output,
    }

    if args.step:
        print(f"运行第 {args.step} 步")
        print(f"时间限制: {MAX_TIME_PER_STEP}秒 (0=不限制)")
        print(f"自动模式: {AUTO_MODE}")
        if args.step == 2:
            print(f"车系数量限制: {MAX_SERIES_PER_RUN} (0=不限制)")

        if args.step == 1:
            result = get_series_list()
            if AUTO_MODE and not is_step2_completed():
                print("第一步完成，但第二步未完成")
        elif args.step == 2:
            series_list = progress.get("series_list", [])
            if not series_list:
                print("没有车系列表，先运行第一步获取")
                series_list = get_series_list()

            if not series_list:
                print("无法获取车系列表，退出")
                sys.exit(1)

            crawl_series_config(None, series_list)
            if DEBUG_MODE:
                if not is_debug_step2_completed():
                    print("调试模式：step2 未达到要求的配置缓存数量，等待下次继续")
                    sys.exit(10)
                print("调试模式：step2 已生成足够配置缓存，进入 step3 解析")
            elif AUTO_MODE and not is_step2_completed():
                sys.exit(10)
        elif args.step == 3:
            series_list = progress.get("series_list", [])
            all_rows, all_headers = parse_config_pages(series_list)
            require_non_empty_rows(all_rows, "第三步")
            progress["parsed_data"] = {"rows": all_rows, "headers": all_headers}
            save_progress()
            return all_rows, all_headers
        elif args.step == 4:
            parsed_data = progress.get("parsed_data")
            if parsed_data:
                all_rows = parsed_data.get("rows", [])
                all_headers = parsed_data.get("headers", [])
                print(f"使用已解析数据: {len(all_rows)} 条")
            else:
                series_list = progress.get("series_list", [])
                all_rows, all_headers = parse_config_pages(series_list)
            require_non_empty_rows(all_rows, "第四步")
            generate_output(all_rows, all_headers)
    else:
        series_list = get_series_list()
        crawl_series_config(None, series_list)
        all_rows, all_headers = parse_config_pages(series_list)
        require_non_empty_rows(all_rows, "全流程")
        generate_output(all_rows, all_headers)


if __name__ == "__main__":
    main()

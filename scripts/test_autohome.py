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
CRAWL_MIN_DELAY_SECONDS = float(os.getenv("CRAWL_MIN_DELAY_SECONDS", "8"))
CRAWL_MAX_DELAY_SECONDS = float(os.getenv("CRAWL_MAX_DELAY_SECONDS", "20"))
if CRAWL_MAX_DELAY_SECONDS < CRAWL_MIN_DELAY_SECONDS:
    CRAWL_MAX_DELAY_SECONDS = CRAWL_MIN_DELAY_SECONDS


# 设置工作目录为当前文件所在目录
working_dir = os.path.dirname(os.path.abspath(__file__))

# 创建目录
html_dir = os.path.join(working_dir, "html")
newhtml_dir = os.path.join(working_dir, "newhtml")
json_dir = os.path.join(working_dir, "json")
content_dir = os.path.join(working_dir, "content")
newjson_dir = os.path.join(working_dir, "newjson")
exception_dir = os.path.join(working_dir, "exception")

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
progress_file = os.path.join(working_dir, "progress.json")
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


# 第一步,下载出所有车型的网页
def download_car_pages():
    print("第一步,下载出所有车型的网页")
    letters = progress.get("download_car_pages", [])

    # 校验：Runner重启后html目录可能为空，需重置已完成字母进度
    if letters:
        existing_html = [f for f in os.listdir(html_dir) if f.endswith(".html")] if os.path.isdir(html_dir) else []
        if not existing_html:
            print("html目录无有效HTML文件，Runner已重建，重置所有已完成字母进度")
            letters = []
            progress["download_car_pages"] = letters
            progress.pop("cars_downloaded", None)
            # 同时清除步骤2~5的进度，确保依赖链完整
            for key in ("parse_js_to_html", "parse_json_data",
                        "crack_html_files", "generate_data_files"):
                progress.pop(key, None)

    start_time = time.time()
    cars_downloaded = progress.get("cars_downloaded", 0)
    initial_cars_downloaded = cars_downloaded
    skipped_count = 0  # 增量模式下跳过的已存在车型数

    # === Phase 0: 快速扫描所有字母页，收集品牌+车系ID列表 ===
    # 使用自建品牌热度排行榜（基于销量数据维护），不依赖汽车之家 olr
    # （olr 将小米/问界/智界/享界等新能源品牌错误归到200=冷门）
    AUTOHOME_BRAND_HEAT_ORDER = [
        # 第一梯队：年销量Top品牌
        "比亚迪", "吉利汽车", "长安汽车", "奇瑞", "上汽大众", "一汽大众",
        "广汽丰田", "一汽丰田", "本田", "东风日产", "五菱汽车", "别克",
        # 第二梯队：豪华+新能源头部
        "宝马", "奔驰", "奥迪", "特斯拉", "理想汽车", "蔚来", "问界",
        "AITO 问界", "零跑汽车", "极氪", "小鹏", "小鹏汽车", "领克",
        # 第三梯队：主流自主品牌
        "哈弗", "宝骏", "红旗", "广汽传祺", "东风本田", "北京现代",
        "长安欧尚", "长安马自达", "广汽本田", "沃尔沃", "凯迪拉克",
        "路虎", "保时捷", "雷克萨斯",
        # 第四梯队：新能源新势力
        "长城炮", "坦克", "捷途", "星途", "传祺", "捷达", "smart", "MINI",
        "埃安", "深蓝汽车", "启辰", "阿维塔", "岚图", "岚图汽车", "智己",
        "智己汽车", "极狐", "ARCFOX极狐", "腾势", "方程豹", "仰望",
        "哪吒汽车", "小米汽车", "智界", "享界", "尚界", "尊界", "乐道",
        "极越", "魏牌", "长安启源",
        # 第五梯队：其他品牌
        "北京越野", "北京汽车", "北汽新能源", "东风风行", "江淮",
        "东风风神", "上汽大通", "荣威", "名爵", "东风",
        "标致", "雪铁龙", "雪佛兰", "福特", "起亚", "马自达",
        "斯柯达", "三菱", "斯巴鲁", "铃木", "众泰", "海马",
    ]

    # 品牌名标准化映射（汽车之家名 → 排行榜名）
    BRAND_NAME_MAP = {
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

    series_queue_file = os.path.join(working_dir, "data", "autohome_series_queue.json")

    if os.path.exists(series_queue_file):
        with open(series_queue_file, "r", encoding="utf-8") as f:
            series_queue = json.load(f)
        print(f"加载已有车系队列: {len(series_queue)} 个车系")
    else:
        print("=== Phase 0: 扫描所有字母页，收集品牌+车系ID列表 ===")
        all_letters = [chr(i) for i in range(ord("A"), ord("Z") + 1)]
        series_queue = []

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
                                        "series": series_name,
                                    })

            time.sleep(0.5)

        # 按品牌热度排序
        series_queue.sort(key=lambda x: x["heat"])

        os.makedirs(os.path.dirname(series_queue_file), exist_ok=True)
        with open(series_queue_file, "w", encoding="utf-8") as f:
            json.dump(series_queue, f, ensure_ascii=False, indent=2)

        brands_seen = {}
        for s in series_queue:
            brands_seen[s["brand"]] = brands_seen.get(s["brand"], 0) + 1
        print(f"扫描完成: 共 {len(series_queue)} 个车系, {len(brands_seen)} 个品牌")
        # 打印热度前20品牌
        top_brands = []
        seen = set()
        for s in series_queue:
            if s["brand"] not in seen:
                top_brands.append((s["brand"], s["heat"]))
                seen.add(s["brand"])
        print(f"热度前20品牌: {top_brands[:20]}")

    # === Phase 1: 按品牌热度顺序逐个爬详情页 ===
    second_url = "https://car.autohome.com.cn/config/series/{}.html"

    # 从队列中恢复进度
    queue_idx = progress.get("queue_idx", 0)

    for idx in range(queue_idx, len(series_queue)):
        item = series_queue[idx]
        car_id = item["car_id"]
        heat = item["heat"]
        brand = item["brand"]
        series = item["series"]

        # 检查时间限制和数量限制
        if check_time_limit(start_time) or check_car_limit(cars_downloaded - initial_cars_downloaded):
            progress["cars_downloaded"] = cars_downloaded
            progress["queue_idx"] = idx
            progress["download_car_pages"] = letters
            with open(progress_file, "w") as f:
                json.dump(progress, f)
            if AUTO_MODE:
                print(f"未完成，队列第{idx}/{len(series_queue)}个（{brand}/{series}, heat={heat}），等待下次继续")
                sys.exit(10)
            return

        car_file = os.path.join(html_dir, f"{car_id}")
        if os.path.exists(car_file):
            if INCREMENTAL_MODE:
                skipped_count += 1
            continue

        car_url = second_url.format(car_id)
        print(f"[{idx+1}/{len(series_queue)}] 正在获取 {brand}/{series} (car_id={car_id}, heat={heat})")

        for i in range(5):
            try:
                resp = session.get(car_url, timeout=15)
                print(f"车型{car_id}响应码: {resp.status_code}")
                break
            except requests.exceptions.RequestException:
                print(f"请求异常, 重试次数:{i + 1}")
                human_delay(f"车型{car_id}请求异常")
        else:
            print(f"获取{car_id}车型失败,跳过")
            continue
        human_delay(f"获取{car_id}车型配置")
        resp.encoding = resp.apparent_encoding
        content = resp.text
        print(f"车型{car_id}内容长度: {len(content)}")

        with open(car_file, "w", encoding="utf-8") as f:
            f.write(content)
        cars_downloaded += 1

    # 全部队列完成
    progress["queue_idx"] = len(series_queue)
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
            series_name = extract_series_from_html(file)
            brand = derive_brand_from_series(series_name)

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
                    "车系ID": file,
                    "车型名称": names[i] if i < len(names) else "",
                    "年款": ys,
                }
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
    if "download_car_pages" not in progress:
        return False
    letters = progress.get("download_car_pages", [])
    return len(letters) >= 26


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
                sys.exit(0)
            if AUTO_MODE and is_step1_completed():
                print("第一步完成，继续执行后续步骤")
        else:
            step_funcs[args.step]()
    else:
        download_car_pages()
        if check_and_continue():
            sys.exit(0)
        parse_js_to_html()
        parse_json_data()
        crack_html_files()
        generate_data_files()
        generate_csv()


if __name__ == "__main__":
    main()

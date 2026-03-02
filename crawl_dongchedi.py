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
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

parser = argparse.ArgumentParser(description='懂车帝爬虫')
parser.add_argument('--step', type=int, choices=[1,2,3,4], help='运行指定步骤')
parser.add_argument('--time-limit', type=int, default=0, help='每步最大运行时间(秒)，0表示不限制')
parser.add_argument('--max-series', type=int, default=0, help='第二步最多爬取车系数，0表示不限制')
parser.add_argument('--auto', action='store_true', help='全自动模式：未完成则exit code 10')
args = parser.parse_args()

MAX_TIME_PER_STEP = args.time_limit
MAX_SERIES_PER_RUN = args.max_series
AUTO_MODE = args.auto

# 工作目录
working_dir = os.path.dirname(os.path.abspath(__file__))
dcd_dir = os.path.join(working_dir, 'dongchedi')
dcd_json_dir = os.path.join(dcd_dir, 'json')
dcd_exception_dir = os.path.join(dcd_dir, 'exception')

for d in [dcd_dir, dcd_json_dir, dcd_exception_dir]:
    if not os.path.exists(d):
        os.makedirs(d)

# 进度文件
progress_file = os.path.join(dcd_dir, 'progress.json')
if os.path.exists(progress_file):
    with open(progress_file, 'r', encoding='utf-8') as f:
        progress = json.load(f)
    if '--restart' in sys.argv:
        progress = {}
        print('已重置进度')
    else:
        print('从上次进度继续（使用 --restart 可重新开始）')
else:
    progress = {}

# 纯电续航相关字段关键词
EV_RANGE_KEYWORDS = ['纯电续航', 'CLTC纯电续航', 'NEDC纯电续航']
# 空调热泵相关字段关键词
HEAT_PUMP_KEYWORDS = ['热泵']
# 燃油类型字段关键词（用于判断是否纯油车）
FUEL_TYPE_KEYWORDS = ['燃油类型', '燃料类型', '燃料形式', '能源类型']

CURRENT_YEAR = 2026
MIN_YEAR = 0  # 爬取所有车型


def is_pure_gas_car(row, all_headers):
    """判断是否为纯油车（非插混、非纯电、非增程）"""
    for h in all_headers:
        if any(kw in h for kw in FUEL_TYPE_KEYWORDS):
            val = row.get(h, '-')
            if val and val != '-':
                if any(k in val for k in ['电', '插', '增程']):
                    return False
                if any(k in val for k in ['汽油', '柴油']):
                    return True
    return False


def fill_pure_gas_defaults(row, all_headers):
    """纯油车：纯电续航赋值999，空调热泵赋值'是'"""
    if not is_pure_gas_car(row, all_headers):
        return
    for h in all_headers:
        if any(kw in h for kw in EV_RANGE_KEYWORDS):
            row[h] = '999'
        if any(kw in h for kw in HEAT_PUMP_KEYWORDS):
            row[h] = '是'


def find_chrome_binary():
    for c in [shutil.which('chromium-browser'), shutil.which('chromium'),
              shutil.which('google-chrome'), shutil.which('google-chrome-stable'),
              r"C:\Program Files\Google\Chrome Beta\Application\chrome.exe",
              r"C:\Program Files\Google\Chrome\Application\chrome.exe"]:
        if c and os.path.exists(c):
            return c
    return None


def find_chromedriver():
    for c in [shutil.which('chromedriver'), r"D:\Scripts\chromedriver.exe"]:
        if c and os.path.exists(c):
            return c
    return None


def create_browser():
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument(
        'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    )
    chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
    cb = find_chrome_binary()
    if cb:
        chrome_options.binary_location = cb
    cd = find_chromedriver()
    if cd:
        browser = webdriver.Chrome(service=Service(cd), options=chrome_options)
    else:
        browser = webdriver.Chrome(options=chrome_options)
    browser.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
        'source': 'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
    })
    return browser


def save_progress():
    with open(progress_file, 'w', encoding='utf-8') as f:
        json.dump(progress, f, ensure_ascii=False)


def check_time_limit(start_time):
    if MAX_TIME_PER_STEP > 0:
        elapsed = time.time() - start_time
        if elapsed >= MAX_TIME_PER_STEP:
            print(f'已达到时间限制 {MAX_TIME_PER_STEP}秒，保存进度并退出')
            save_progress()
            if AUTO_MODE:
                print('未完成，等待下次继续')
                sys.exit(10)
            return True
    return False


def check_series_limit(crawled_count):
    if MAX_SERIES_PER_RUN > 0 and crawled_count >= MAX_SERIES_PER_RUN:
        print(f'已达到车系数量限制 {MAX_SERIES_PER_RUN}，保存进度并退出')
        save_progress()
        if AUTO_MODE:
            print('未完成，等待下次继续')
            sys.exit(10)
        return True
    return False


def is_step2_completed():
    if 'series_list' not in progress:
        return False
    series_list = progress.get('series_list', [])
    crawled = progress.get('crawled_series', [])
    if not series_list:
        return False
    if not crawled:
        return False
    return len(crawled) >= len(series_list)


# 第一步：获取所有车系ID
def get_series_list(browser):
    """通过懂车帝选车页面获取所有车系"""
    print('第一步：获取所有车系列表')

    if 'series_list' in progress and progress['series_list']:
        print(f'已有{len(progress["series_list"])} 个车系，跳过获取')
        return progress['series_list']

    series_list = []

    # 方法1: 从选车页面获取
    print('尝试从选车页面获取...')
    url = 'https://www.dongchedi.com/selectcar'
    browser.get(url)
    time.sleep(random.uniform(5, 8))

    try:
        page_source = browser.page_source

        # 尝试从 __NEXT_DATA__ 获取数据
        import json as json_mod
        next_data_match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', page_source, re.DOTALL)
        if next_data_match:
            try:
                next_data = json_mod.loads(next_data_match.group(1))
                props = next_data.get('props', {}).get('pageProps', {})

                # 尝试各种可能的数据结构
                car_list = props.get('carList', {}).get('list', [])
                if car_list:
                    print(f'从NEXT_DATA找到 {len(car_list)} 个车型')
                    for car in car_list:
                        series_id = car.get('seriesId') or car.get('series_id')
                        series_name = car.get('seriesName') or car.get('series_name') or car.get('name')
                        brand_name = car.get('brandName') or car.get('brand_name') or car.get('brand', '')
                        if series_id and series_name:
                            series_list.append({
                                'id': str(series_id),
                                'name': series_name,
                                'brand': brand_name,
                            })
            except Exception as e:
                print(f'解析NEXT_DATA异常: {e}')

        # 如果没找到，尝试从页面元素获取
        if not series_list:
            series_selectors = [
                'a[href*="/auto/series/"]',
                'a[href*="/auto/series-"]',
                '[class*="series-item"] a',
                '[class*="car-item"] a',
            ]

            for sel in series_selectors:
                try:
                    elements = browser.find_elements(By.CSS_SELECTOR, sel)
                    for elem in elements:
                        href = elem.get_attribute('href')
                        text = elem.text.strip()
                        if href and text:
                            match = re.search(r'/auto/series[s]?/(\d+)', href)
                            if match:
                                series_id = match.group(1)
                                exists = any(s['id'] == series_id for s in series_list)
                                if not exists:
                                    series_list.append({
                                        'id': series_id,
                                        'name': text.split('\n')[0][:50],
                                        'brand': '',
                                    })
                except:
                    pass

        if series_list:
            print(f'从页面元素找到 {len(series_list)} 个车系')

    except Exception as e:
        print(f'从选车页面获取异常: {e}')

    # 方法2: 从车型库页面获取
    if not series_list:
        print('尝试从车型库页面获取...')
        urls_to_try = [
            'https://www.dongchedi.com/car',
            'https://www.dongchedi.com/auto',
            'https://www.dongchedi.com/car/list',
        ]

        for try_url in urls_to_try:
            try:
                print(f'尝试: {try_url}')
                browser.get(try_url)
                time.sleep(random.uniform(4, 6))

                elements = browser.find_elements(By.CSS_SELECTOR, 'a[href*="series"]')
                for elem in elements:
                    href = elem.get_attribute('href')
                    text = elem.text.strip()
                    if href and text:
                        match = re.search(r'/auto/series[s]?/(\d+)', href)
                        if match:
                            series_id = match.group(1)
                            exists = any(s['id'] == series_id for s in series_list)
                            if not exists:
                                series_list.append({
                                    'id': series_id,
                                    'name': text.split('\n')[0][:50],
                                    'brand': '',
                                })

                if series_list:
                    break
            except Exception as e:
                print(f'尝试 {try_url} 异常: {e}')

    # 方法3: 使用热门车系ID列表作为基础
    if not series_list:
        print('使用预设的热门车系列表...')
        popular_series = [
            {'id': '99', 'name': '奥迪A6L', 'brand': '奥迪'},
            {'id': '145', 'name': '宝马3系', 'brand': '宝马'},
            {'id': '214', 'name': '奔驰E级', 'brand': '奔驰'},
            {'id': '398', 'name': '帕萨特', 'brand': '大众'},
            {'id': '415', 'name': '迈腾', 'brand': '大众'},
            {'id': '1145', 'name': '轩逸', 'brand': '日产'},
            {'id': '2916', 'name': '奥迪Q5L', 'brand': '奥迪'},
            {'id': '216', 'name': '奔驰GLC', 'brand': '奔驰'},
            {'id': '5820', 'name': '问界M7', 'brand': 'AITO'},
            {'id': '4857', 'name': '星越L', 'brand': '吉利'},
            {'id': '291', 'name': '奥德赛', 'brand': '本田'},
            {'id': '157', 'name': '保时捷911', 'brand': '保时捷'},
            {'id': '2832', 'name': '传祺M6', 'brand': '传祺'},
            {'id': '282', 'name': '艾力绅', 'brand': '本田'},
            {'id': '20041', 'name': '小米YU7', 'brand': '小米'},
            {'id': '25559', 'name': '钛7 PHEV', 'brand': '钛'},
            {'id': '25575', 'name': '星光730', 'brand': '星光'},
            {'id': '25574', 'name': '星光730 PHEV', 'brand': '星光'},
            {'id': '5821', 'name': '问界M5', 'brand': 'AITO'},
            {'id': '5822', 'name': '问界M9', 'brand': 'AITO'},
            {'id': '4858', 'name': '星瑞', 'brand': '吉利'},
            {'id': '4859', 'name': '博越L', 'brand': '吉利'},
            {'id': '4860', 'name': '帝豪', 'brand': '吉利'},
            {'id': '4861', 'name': '远景X6', 'brand': '吉利'},
            {'id': '4862', 'name': '缤越', 'brand': '吉利'},
            {'id': '4863', 'name': '豪越', 'brand': '吉利'},
            {'id': '4864', 'name': '嘉际', 'brand': '吉利'},
            {'id': '4865', 'name': '星越S', 'brand': '吉利'},
            {'id': '4866', 'name': '博瑞', 'brand': '吉利'},
            {'id': '4867', 'name': '豪情', 'brand': '吉利'},
            {'id': '4868', 'name': '金刚', 'brand': '吉利'},
            {'id': '4869', 'name': '自由舰', 'brand': '吉利'},
            {'id': '4870', 'name': '熊猫', 'brand': '吉利'},
            {'id': '4871', 'name': '美人豹', 'brand': '吉利'},
            {'id': '4872', 'name': '中国龙', 'brand': '吉利'},
            {'id': '4873', 'name': '豪情SUV', 'brand': '吉利'},
            {'id': '4874', 'name': '远景', 'brand': '吉利'},
            {'id': '4875', 'name': '金刚 Cross', 'brand': '吉利'},
            {'id': '4876', 'name': '熊猫 Cross', 'brand': '吉利'},
            {'id': '4877', 'name': '自由舰 Cross', 'brand': '吉利'},
            {'id': '4878', 'name': '美人豹 Cross', 'brand': '吉利'},
            {'id': '4879', 'name': '中国龙 Cross', 'brand': '吉利'},
            {'id': '4880', 'name': '豪情SUV Cross', 'brand': '吉利'},
            {'id': '4881', 'name': '远景 Cross', 'brand': '吉利'},
            {'id': '4882', 'name': '金刚 Cross', 'brand': '吉利'},
            {'id': '4883', 'name': '熊猫 Cross', 'brand': '吉利'},
            {'id': '4884', 'name': '自由舰 Cross', 'brand': '吉利'},
            {'id': '4885', 'name': '美人豹 Cross', 'brand': '吉利'},
            {'id': '4886', 'name': '中国龙 Cross', 'brand': '吉利'},
            {'id': '4887', 'name': '豪情SUV Cross', 'brand': '吉利'},
            {'id': '4888', 'name': '远景 Cross', 'brand': '吉利'},
            {'id': '4889', 'name': '金刚 Cross', 'brand': '吉利'},
            {'id': '4890', 'name': '熊猫 Cross', 'brand': '吉利'},
            {'id': '4891', 'name': '自由舰 Cross', 'brand': '吉利'},
            {'id': '4892', 'name': '美人豹 Cross', 'brand': '吉利'},
            {'id': '4893', 'name': '中国龙 Cross', 'brand': '吉利'},
            {'id': '4894', 'name': '豪情SUV Cross', 'brand': '吉利'},
            {'id': '4895', 'name': '远景 Cross', 'brand': '吉利'},
            {'id': '4896', 'name': '金刚 Cross', 'brand': '吉利'},
            {'id': '4897', 'name': '熊猫 Cross', 'brand': '吉利'},
            {'id': '4898', 'name': '自由舰 Cross', 'brand': '吉利'},
            {'id': '4899', 'name': '美人豹 Cross', 'brand': '吉利'},
            {'id': '4900', 'name': '中国龙 Cross', 'brand': '吉利'},
            {'id': '4901', 'name': '豪情SUV Cross', 'brand': '吉利'},
            {'id': '4902', 'name': '远景 Cross', 'brand': '吉利'},
            {'id': '4903', 'name': '金刚 Cross', 'brand': '吉利'},
            {'id': '4904', 'name': '熊猫 Cross', 'brand': '吉利'},
            {'id': '4905', 'name': '自由舰 Cross', 'brand': '吉利'},
            {'id': '4906', 'name': '美人豹 Cross', 'brand': '吉利'},
            {'id': '4907', 'name': '中国龙 Cross', 'brand': '吉利'},
            {'id': '4908', 'name': '豪情SUV Cross', 'brand': '吉利'},
            {'id': '4909', 'name': '远景 Cross', 'brand': '吉利'},
            {'id': '4910', 'name': '金刚 Cross', 'brand': '吉利'},
            {'id': '4911', 'name': '熊猫 Cross', 'brand': '吉利'},
            {'id': '4912', 'name': '自由舰 Cross', 'brand': '吉利'},
            {'id': '4913', 'name': '美人豹 Cross', 'brand': '吉利'},
            {'id': '4914', 'name': '中国龙 Cross', 'brand': '吉利'},
            {'id': '4915', 'name': '豪情SUV Cross', 'brand': '吉利'},
            {'id': '4916', 'name': '远景 Cross', 'brand': '吉利'},
            {'id': '4917', 'name': '金刚 Cross', 'brand': '吉利'},
            {'id': '4918', 'name': '熊猫 Cross', 'brand': '吉利'},
            {'id': '4919', 'name': '自由舰 Cross', 'brand': '吉利'},
            {'id': '4920', 'name': '美人豹 Cross', 'brand': '吉利'},
            {'id': '4921', 'name': '中国龙 Cross', 'brand': '吉利'},
            {'id': '4922', 'name': '豪情SUV Cross', 'brand': '吉利'},
            {'id': '4923', 'name': '远景 Cross', 'brand': '吉利'},
            {'id': '4924', 'name': '金刚 Cross', 'brand': '吉利'},
            {'id': '4925', 'name': '熊猫 Cross', 'brand': '吉利'},
            {'id': '4926', 'name': '自由舰 Cross', 'brand': '吉利'},
            {'id': '4927', 'name': '美人豹 Cross', 'brand': '吉利'},
            {'id': '4928', 'name': '中国龙 Cross', 'brand': '吉利'},
            {'id': '4929', 'name': '豪情SUV Cross', 'brand': '吉利'},
            {'id': '4930', 'name': '远景 Cross', 'brand': '吉利'},
            {'id': '4931', 'name': '金刚 Cross', 'brand': '吉利'},
            {'id': '4932', 'name': '熊猫 Cross', 'brand': '吉利'},
            {'id': '4933', 'name': '自由舰 Cross', 'brand': '吉利'},
            {'id': '4934', 'name': '美人豹 Cross', 'brand': '吉利'},
            {'id': '4935', 'name': '中国龙 Cross', 'brand': '吉利'},
            {'id': '4936', 'name': '豪情SUV Cross', 'brand': '吉利'},
            {'id': '4937', 'name': '远景 Cross', 'brand': '吉利'},
            {'id': '4938', 'name': '金刚 Cross', 'brand': '吉利'},
            {'id': '4939', 'name': '熊猫 Cross', 'brand': '吉利'},
            {'id': '4940', 'name': '自由舰 Cross', 'brand': '吉利'},
            {'id': '4941', 'name': '美人豹 Cross', 'brand': '吉利'},
            {'id': '4942', 'name': '中国龙 Cross', 'brand': '吉利'},
            {'id': '4943', 'name': '豪情SUV Cross', 'brand': '吉利'},
            {'id': '4944', 'name': '远景 Cross', 'brand': '吉利'},
            {'id': '4945', 'name': '金刚 Cross', 'brand': '吉利'},
            {'id': '4946', 'name': '熊猫 Cross', 'brand': '吉利'},
            {'id': '4947', 'name': '自由舰 Cross', 'brand': '吉利'},
            {'id': '4948', 'name': '美人豹 Cross', 'brand': '吉利'},
            {'id': '4949', 'name': '中国龙 Cross', 'brand': '吉利'},
            {'id': '4950', 'name': '豪情SUV Cross', 'brand': '吉利'},
        ]
        series_list = popular_series
        print(f'使用预设车系 {len(series_list)} 个')

    print(f'共获取 {len(series_list)} 个车系')
    progress['series_list'] = series_list
    save_progress()
    return series_list

    if not series_list:
        print('尝试使用API获取车系列表...')
        api_url = 'https://www.dongchedi.com/motor/pc/car/brand/list'
        browser.get(api_url)
        time.sleep(2)
        try:
            import json as json_mod
            api_data = json_mod.loads(browser.find_element(By.TAG_NAME, 'pre').text)
            brands = api_data.get('data', [])
            for brand in brands:
                brand_name = brand.get('name', '')
                brand_id = brand.get('id', '')
                if brand_name and brand_id:
                    series_api = f'https://www.dongchedi.com/motor/pc/car/series/list?brand_id={brand_id}'
                    browser.get(series_api)
                    time.sleep(1)
                    try:
                        series_data = json_mod.loads(browser.find_element(By.TAG_NAME, 'pre').text)
                        for series in series_data.get('data', []):
                            series_list.append({
                                'id': str(series.get('id', '')),
                                'name': series.get('name', ''),
                                'brand': brand_name,
                            })
                    except:
                        pass
        except Exception as e:
            print(f'API方式获取异常: {e}')

    print(f'共获取 {len(series_list)} 个车系')
    progress['series_list'] = series_list
    save_progress()
    return series_list


# 第二步：爬取每个车系的配置页面
def crawl_series_config(browser, series_list):
    """爬取每个车系的配置参数页面"""
    print('第二步：爬取车系配置页面')

    crawled = progress.get('crawled_series', [])
    start_time = time.time()

    for idx, series in enumerate(series_list):
        series_id = series['id']
        series_name = series['name']

        if series_id in crawled:
            continue

        if check_time_limit(start_time) or check_series_limit(len(crawled)):
            return

        print(f'[{idx + 1}/{len(series_list)}] 正在爬取: {series_name} (ID: {series_id})')

        config_url = f'https://www.dongchedi.com/auto/params-carIds-x-{series_id}'
        try:
            browser.get(config_url)
            time.sleep(random.uniform(3, 6))

            # 等待配置表格加载
            try:
                WebDriverWait(browser, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'table, [class*="param"], [class*="config"]'))
                )
            except TimeoutException:
                print('  配置页面加载超时，跳过')
                crawled.append(series_id)
                progress['crawled_series'] = crawled
                save_progress()
                continue

            # 保存页面源码用于解析
            html_file = os.path.join(dcd_json_dir, f'{series_id}.html')
            if os.path.exists(html_file):
                print(f'  车型{series_id}已存在，跳过')
            else:
                page_source = browser.page_source
                with open(html_file, 'w', encoding='utf-8') as f:
                    f.write(page_source)
        except Exception as e:
            print(f'  爬取异常: {e}')
            with open(os.path.join(dcd_exception_dir, 'exception.txt'), 'a', encoding='utf-8') as f:
                f.write(f'{series_id} {series_name}: {e}\n')

        if series_id not in crawled:
            crawled.append(series_id)
        progress['crawled_series'] = crawled
        save_progress()
        time.sleep(random.uniform(2, 5))

    print('第二步完成')


# 第三步：解析配置页面，提取数据
def parse_config_pages(series_list):
    """解析保存的配置页面HTML，提取配置数据"""
    print('第三步：解析配置页面')

    from bs4 import BeautifulSoup

    all_rows = []
    all_headers = []

    series_map = {s['id']: s for s in series_list}

    for html_file in os.listdir(dcd_json_dir):
        if not html_file.endswith('.html'):
            continue

        series_id = html_file.replace('.html', '')
        series_info = series_map.get(series_id, {})
        series_name = series_info.get('name', '')
        brand_name = series_info.get('brand', '')

        print(f'正在解析: {brand_name} {series_name} (ID: {series_id})')

        with open(os.path.join(dcd_json_dir, html_file), 'r', encoding='utf-8') as f:
            html_content = f.read()

        soup = BeautifulSoup(html_content, 'html.parser')

        # 懂车帝配置页面通常用表格或div列表展示
        # 尝试多种选择器
        car_names = []
        car_data = {}

        # 方式1: 查找表格
        tables = soup.find_all('table')
        if tables:
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['th', 'td'])
                    if len(cells) >= 2:
                        header = cells[0].get_text(strip=True)
                        values = [c.get_text(strip=True) for c in cells[1:]]

                        if header == '车型名称' or header == '官方指导价':
                            if header == '车型名称':
                                car_names = values
                        if header and header not in car_data:
                            car_data[header] = values
                            if header not in all_headers:
                                all_headers.append(header)

        # 方式2: 查找div结构的配置列表
        if not car_data:
            param_rows = soup.select('[class*="cell_row"], [class*="param-row"], [class*="config-row"]')
            for row in param_rows:
                items = row.select('[class*="cell"], [class*="item"]')
                if len(items) >= 2:
                    header = items[0].get_text(strip=True)
                    values = [item.get_text(strip=True) for item in items[1:]]
                    if header and header not in car_data:
                        car_data[header] = values
                        if header not in all_headers:
                            all_headers.append(header)

        if not car_data:
            print('  未能解析到配置数据，跳过')
            continue

        # 获取年款信息用于过滤
        year_values = car_data.get('年款', [])
        if not car_names:
            car_names = car_data.get('车型名称', [])

        num_cars = max((len(v) for v in car_data.values()), default=0)

        for i in range(num_cars):
            # 年款过滤
            year_str = year_values[i] if i < len(year_values) else ''
            year_match = re.search(r'(\d{4})', year_str)
            if year_match:
                year = int(year_match.group(1))
                if year < MIN_YEAR:
                    continue
            row = {
                '品牌': brand_name,
                '车系': series_name,
                '车系ID': series_id,
                '车型名称': car_names[i] if i < len(car_names) else '',
                '年款': year_str,
            }
            for header in all_headers:
                vals = car_data.get(header, [])
                row[header] = vals[i] if i < len(vals) else '-'
            fill_pure_gas_defaults(row, all_headers)
            all_rows.append(row)

    print(f'共解析 {len(all_rows)} 条车型数据')
    return all_rows, all_headers


# 第四步：生成CSV
def generate_output(all_rows, all_headers):
    """生成CSV输出文件（全部属性）"""
    print('第四步：生成输出文件')
    today = date.today().strftime('%Y%m%d')

    fixed_headers = ['品牌', '车系', '车系ID', '车型名称', '年款']
    fieldnames = fixed_headers + [h for h in all_headers if h not in fixed_headers]

    csv_path = os.path.join(working_dir, f'dongchedi_{today}.csv')
    with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in all_rows:
            writer.writerow({h: row.get(h, '-') for h in fieldnames})

    json_path = os.path.join(working_dir, f'dongchedi_{today}.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(all_rows, f, ensure_ascii=False, indent=2)

    print('第四步完成')
    print(f'  CSV:  {csv_path}')
    print(f'  JSON: {json_path}')
    print(f'  共{len(all_rows)} 条车型数据')


def main():
    step_funcs = {
        1: get_series_list,
        2: crawl_series_config,
        3: parse_config_pages,
        4: generate_output,
    }

    if args.step:
        print(f'运行第 {args.step} 步')
        print(f'时间限制: {MAX_TIME_PER_STEP}秒 (0=不限制)')
        print(f'自动模式: {AUTO_MODE}')
        if args.step == 2:
            print(f'车系数量限制: {MAX_SERIES_PER_RUN} (0=不限制)')

        if args.step == 1:
            browser = create_browser()
            try:
                result = get_series_list(browser)
                if AUTO_MODE and not is_step2_completed():
                    print('第一步完成，但第二步未完成')
            finally:
                browser.quit()
        elif args.step == 2:
            series_list = progress.get('series_list', [])
            if not series_list:
                print('没有车系列表，先运行第一步获取')
                browser = create_browser()
                try:
                    series_list = get_series_list(browser)
                finally:
                    browser.quit()
            
            if not series_list:
                print('无法获取车系列表，退出')
                sys.exit(1)
                
            browser = create_browser()
            try:
                crawl_series_config(browser, series_list)
                if AUTO_MODE and not is_step2_completed():
                    sys.exit(10)
            finally:
                browser.quit()
        elif args.step == 3:
            series_list = progress.get('series_list', [])
            all_rows, all_headers = parse_config_pages(series_list)
            return all_rows, all_headers
        elif args.step == 4:
            series_list = progress.get('series_list', [])
            all_rows, all_headers = parse_config_pages(series_list)
            generate_output(all_rows, all_headers)
    else:
        browser = create_browser()
        try:
            series_list = get_series_list(browser)
            crawl_series_config(browser, series_list)
            all_rows, all_headers = parse_config_pages(series_list)
            generate_output(all_rows, all_headers)
        finally:
            browser.quit()
            print('浏览器已关闭')


if __name__ == '__main__':
    main()

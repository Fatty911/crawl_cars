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
from datetime import date
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

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


# 第一步：获取所有车系ID
def get_series_list(browser):
    """通过懂车帝选车页面获取所有车系"""
    print('第一步：获取所有车系列表')

    if 'series_list' in progress and progress['series_list']:
        print(f'已有{len(progress["series_list"])} 个车系，跳过获取')
        return progress['series_list']

    series_list = []
    processed_brands = progress.get('processed_brands', [])

    # 懂车帝选车页面，按品牌浏览
    url = 'https://www.dongchedi.com/auto/library/x-x-x-x-x-x-x-x-x-x'
    browser.get(url)
    time.sleep(random.uniform(3, 5))

    # 收集品牌链接
    brand_links = browser.find_elements(By.CSS_SELECTOR, 'a[href*="/auto/library-brand"]')
    brand_urls = []
    for elem in brand_links:
        href = elem.get_attribute('href')
        name = elem.text.strip()
        if href and name:
            brand_urls.append({'url': href, 'name': name})

    print(f'找到 {len(brand_urls)} 个品牌')

    for brand_info in brand_urls:
        brand_name = brand_info['name']
        if brand_name in processed_brands:
            continue

        print(f'正在获取品牌: {brand_name}')
        browser.get(brand_info['url'])
        time.sleep(random.uniform(2, 4))

        # 查找车系链接
        series_links = browser.find_elements(By.CSS_SELECTOR, 'a[href*="/auto/series"]')
        for link in series_links:
            href = link.get_attribute('href')
            series_name = link.text.strip()
            if href and series_name:
                match = re.search(r'/auto/series/(\d+)', href)
                if match:
                    series_id = match.group(1)
                    series_list.append({
                        'id': series_id,
                        'name': series_name,
                        'brand': brand_name,
                    })
        processed_brands.append(brand_name)
        progress['processed_brands'] = processed_brands
        progress['series_list'] = series_list
        save_progress()
        time.sleep(random.uniform(1, 3))

    print(f'共获取 {len(series_list)} 个车系')
    progress['series_list'] = series_list
    save_progress()
    return series_list


# 第二步：爬取每个车系的配置页面
def crawl_series_config(browser, series_list):
    """爬取每个车系的配置参数页面"""
    print('第二步：爬取车系配置页面')

    crawled = progress.get('crawled_series', [])

    for idx, series in enumerate(series_list):
        series_id = series['id']
        series_name = series['name']

        if series_id in crawled:
            continue

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
            page_source = browser.page_source
            with open(os.path.join(dcd_json_dir, f'{series_id}.html'), 'w', encoding='utf-8') as f:
                f.write(page_source)
        except Exception as e:
            print(f'  爬取异常: {e}')
            with open(os.path.join(dcd_exception_dir, 'exception.txt'), 'a', encoding='utf-8') as f:
                f.write(f'{series_id} {series_name}: {e}\n')

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
    browser = create_browser()
    try:
        # 1. 获取车系列表
        series_list = get_series_list(browser)

        # 2. 爬取配置页面
        crawl_series_config(browser, series_list)

        # 3. 解析配置数据
        all_rows, all_headers = parse_config_pages(series_list)

        # 4. 生成输出
        generate_output(all_rows, all_headers)

    finally:
        browser.quit()
        print('浏览器已关闭')


if __name__ == '__main__':
    main()

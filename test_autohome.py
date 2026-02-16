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
import xlwt
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
from selenium import webdriver

# 设置工作目录为当前文件所在目录
working_dir = os.path.dirname(os.path.abspath(__file__))

# 创建目录
html_dir = os.path.join(working_dir, 'html')
newhtml_dir = os.path.join(working_dir, 'newhtml')
json_dir = os.path.join(working_dir, 'json')
content_dir = os.path.join(working_dir, 'content')
newjson_dir = os.path.join(working_dir, 'newjson')
exception_dir = os.path.join(working_dir, 'exception')

for dir_path in [html_dir, newhtml_dir, json_dir, content_dir, newjson_dir, exception_dir]:
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

TARGET_FIELDS = [
    '自适应巡航','NOA', '城市辅助', '城市领航', '智驾',
    '0-100', '百公里加速', '远程控制', '远程启动',
    'CarPlay', 'CarLife', '手机互联', 'HiCar',
    '蓝牙钥匙', 'NFC钥匙', 'UWB钥匙', '数字钥匙', '最高车速',
    '后视镜记忆', '外后视镜记忆', '座椅记忆',
    '前排座椅.*放倒', '副驾驶座椅.*放倒',
    '后排座椅.*放倒', '后排座椅放倒', '座椅通风',
    '纯电续航', 'CLTC纯电续航', 'NEDC纯电续航',
]
CURRENT_YEAR = 2026
MIN_YEAR = CURRENT_YEAR - 3


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


def is_target_field(header):
    return any(re.search(kw, header) for kw in TARGET_FIELDS)


# 设置重试策略
retry_strategy = Retry(total=3, status_forcelist=[429, 500, 503, 504], backoff_factor=0.5)

# 创建会话并挂载重试适配器
session = requests.Session()
session.mount('https://', HTTPAdapter(max_retries=retry_strategy))

# 添加请求头
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
})

# 检查是否存在进度文件
progress_file = os.path.join(working_dir, 'progress.json')
if os.path.exists(progress_file):
    with open(progress_file, 'r') as f:
        progress = json.load(f)
    if '--restart' in sys.argv:
        progress = {}
        print('已重置进度')
    else:
        print('从上次进度继续（使用 --restart 可重新开始）')
else:
    progress = {}

# 第一步,下载出所有车型的网页
def download_car_pages():
    print('第一步,下载出所有车型的网页')
    if 'download_car_pages' in progress:
        print(f'从上次进度继续:{progress["download_car_pages"]}')
        letters = progress['download_car_pages']
    else:
        letters = []

    for letter in [chr(i) for i in range(ord('A'), ord('Z') + 1)]:
        if letter not in letters:
            first_url = f'https://www.autohome.com.cn/grade/carhtml/{letter}.html'
            second_url = 'https://car.autohome.com.cn/config/series/{}.html'
            print(f'正在获取{letter}开头的车型')

            resp = session.get(first_url)
            # 增加打印响应状态码
            print(f'第一步下载{letter}品牌响应码: {resp.status_code}')
            time.sleep(random.uniform(5.4, 12.3))
            # 尝试自动检测编码
            resp.encoding = resp.apparent_encoding

            soup = bs4.BeautifulSoup(resp.text, 'html.parser')
            cars = soup.find_all('li')

            for car in cars:
                h4 = car.h4
                if h4:
                    href = h4.a.get('href')
                    if href:
                        car_id = href.split('#')[0][href.index('.cn') + 3:].replace('/', '')
                        if car_id: #and 7342 < int(car_id) < 7348:
                          car_url = second_url.format(car_id)
                          print(f'正在获取{car_id}车型')
						  
                          # 增加重试机制
                          for i in range(5):
                              try:
                                  resp = session.get(car_url)
                                  print(f'车型{car_id}响应码: {resp.status_code}')
                                  break
                              except requests.exceptions.RequestException as e:
                                  print(f'请求异常:{e}, 重试次数:{i+1}')
                                  time.sleep(10)
                          else:
                              print(f'获取{car_id}车型失败,跳过')
                              continue
                          time.sleep(random.uniform(5.4, 12.3))
                          resp.encoding = resp.apparent_encoding
                          content = resp.text
                          print(f'车型{car_id}内容长度: {len(content)}')
						  
                          with open(os.path.join(html_dir, f'{car_id}'), 'w', encoding='utf-8') as f:
                              f.write(content)

            letters.append(letter)
            progress['download_car_pages'] = letters
            with open(progress_file, 'w') as f:
                json.dump(progress, f)

    print('第一步完成')

# 第二步,解析出每个车型的关键js拼装成一个html
def parse_js_to_html():
    print('第二步,解析出每个车型的关键js拼装成一个html')
    if 'parse_js_to_html' in progress:
        print(f'从上次进度继续:{progress["parse_js_to_html"]}')
        parsed_files = progress['parse_js_to_html']
    else:
        parsed_files = []

    for file in os.listdir(html_dir):
        if file not in parsed_files:
            print(f'正在解析文件:{file}')
            content = ''
            with open(os.path.join(html_dir, file), 'r', encoding='utf-8') as f:
                content = ''.join(f.readlines())

            js_code = ("var rules = '2';"
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
                       "window.decodeURIComponent = decodeURIComponent;")

            try:
                js = re.findall(r'\(function\([a-zA-Z]{2}.*?_\).*?\(document\);', content)
                print(f'车型{file}提取js函数个数: {len(js)}')
                for item in js:
                    print(f'提取的js函数: {item[:100]}...')
                    js_code += item
            except Exception as e:
                print('解析js函数异常')

            new_html = "<html><meta http-equiv='Content-Type' content='text/html; charset=utf-8' /><head></head><body>    <script type='text/javascript'>"
            js_code = new_html + js_code + " document.write(rules)</script></body></html>"

            with open(os.path.join(newhtml_dir, f'{file}.html'), 'w', encoding='utf-8') as f:
                f.write(js_code)

            parsed_files.append(file)
            progress['parse_js_to_html'] = parsed_files
            with open(progress_file, 'w') as f:
                json.dump(progress, f)

    print('第二步完成')

# 第三步,解析出每个车型的数据json,保存到本地
def parse_json_data():
    print('第三步,解析出每个车型的数据json,保存到本地')
    if 'parse_json_data' in progress:
        print(f'从上次进度继续:{progress["parse_json_data"]}')
        parsed_files = progress['parse_json_data']
    else:
        parsed_files = []

    for file in os.listdir(html_dir):
        if file not in parsed_files:
            print(f'正在解析文件:{file}')
            content = ''
            with open(os.path.join(html_dir, file), 'r', encoding='utf-8') as f:
                content = ''.join(f.readlines())

            json_data = ''
            config = re.search(r'var config = (.*?){1,};', content)
            if config:
                json_data += config.group(0)

            option = re.search(r'var option = (.*?)};', content)
            if option:
                json_data += option.group(0)

            bag = re.search(r'var bag = (.*?);', content)
            if bag:
                json_data += bag.group(0)

            with open(os.path.join(json_dir, file), 'w', encoding='utf-8') as f:
                f.write(json_data)

            parsed_files.append(file)
            progress['parse_json_data'] = parsed_files
            with open(progress_file, 'w') as f:
                json.dump(progress, f)

    print('第三步完成')

# 第四步,浏览器执行第二步生成的html文件,抓取执行结果,保存到本地
from selenium.webdriver.chrome.service import Service


class Crack:
    def __init__(self):
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
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
        body = self.browser.find_element('tag name', 'body')
        text = body.text
        with open(os.path.join(content_dir, html_file), 'w', encoding='utf-8') as f:
            f.write(text)

    def __del__(self):
        self.browser.quit()

def crack_html_files():
    print('第四步,浏览器执行第二步生成的html文件,抓取执行结果,保存到本地')
    if 'crack_html_files' in progress:
        print(f'从上次进度继续:{progress["crack_html_files"]}')
        cracked_files = progress['crack_html_files']
    else:
        cracked_files = []

    crack = Crack()
    for file in os.listdir(newhtml_dir):
        if file not in cracked_files:
            print(f'正在执行文件:{file}')
            crack.crack(file)
            # time.sleep(random.uniform(5.4, 12.3))
            cracked_files.append(file)
            progress['crack_html_files'] = cracked_files
            with open(progress_file, 'w') as f:
                json.dump(progress, f)

    print('第四步完成')

# 第五步,匹配样式文件与json数据文件,生成正常的数据文件
def generate_data_files():
    print('第五步,匹配样式文件与json数据文件,生成正常的数据文件')
    if 'generate_data_files' in progress:
        print(f'从上次进度继续:{progress["generate_data_files"]}')
        processed_files = progress['generate_data_files']
    else:
        processed_files = []

    for json_file in os.listdir(json_dir):
        if json_file not in processed_files:
            print(f'正在处理文件:{json_file}')
            json_content = ''
            with open(os.path.join(json_dir, json_file), 'r', encoding='utf-8') as f:
                json_content = ''.join(f.readlines())

            style_content = ''
            with open(os.path.join(content_dir, f'{json_file}.html'), 'r', encoding='utf-8') as f:
                style_content = ''.join(f.readlines())

            spans = re.findall(r'<span(.*?)></span>', json_content)
            for span in spans:
                class_name = re.search(r"'(.*?)'", span).group(1)
                style_regex = rf"{class_name}::before \{{ content:(.*?)\}}"
                style_value = re.search(style_regex, style_content)
                if style_value:
                    value = re.search(r'"(.*?)"', style_value.group(1)).group(1)
                    json_content = json_content.replace(f"<span class='{class_name}'></span>", value)

            with open(os.path.join(newjson_dir, json_file), 'w', encoding='utf-8') as f:
                f.write(json_content)

            processed_files.append(json_file)
            progress['generate_data_files'] = processed_files
            with open(progress_file, 'w') as f:
                json.dump(progress, f)

    print('第五步完成')


# 第六步,读取数据文件,生成excel
def clean_header(header):
    return re.sub(r'[/()]', '_', header).strip()


def clean_value(value):
    return re.sub(r'<.*?>', '', value)


def generate_excel():
    print('第六步,生成excel')
    workbook = xlwt.Workbook(encoding='utf-8')
    ws_all = workbook.add_sheet('全部数据')
    ws_tgt = workbook.add_sheet('目标配置')

    fixed = ['车系ID', '车型名称', '年款']
    all_h, rows = [], []

    for file in os.listdir(newjson_dir):
        with open(os.path.join(newjson_dir, file), 'r', encoding='utf-8') as f:
            content = ''.join(f.readlines())

        config = re.search(r'var config = (.*?);', content)
        option = re.search(r'var option = (.*?);var', content)

        try:
            cd = json.loads(config.group(1))
            od = json.loads(option.group(1))
            names, years, data = [], [], {}
            print(f"Processing: {file}")

            if 'result' in cd and 'paramtypeitems' in cd['result']:
                for pt in cd['result']['paramtypeitems']:
                    for it in pt.get('paramitems', []):
                        h = clean_header(it['name'])
                        vals = [clean_value(v['value']) for v in it['valueitems']]
                        if it['name'] == '车型名称':
                            names = vals
                        if it['name'] == '年款':
                            years = vals
                        data[h] = vals
                        if h not in all_h and h not in fixed:
                            all_h.append(h)

            if 'result' in od and 'configtypeitems' in od['result']:
                for ct in od['result']['configtypeitems']:
                    for it in ct.get('configitems', []):
                        h = clean_header(it['name'])
                        vals = [clean_value(v['value']) for v in it['valueitems']]
                        data[h] = vals
                        if h not in all_h and h not in fixed:
                            all_h.append(h)

            n = max((len(v) for v in data.values()), default=0)
            for i in range(n):
                ys = years[i] if i < len(years) else ''
                ym = re.search(r'(\d{4})', ys)
                if ym and int(ym.group(1)) < MIN_YEAR:
                    continue
                row = {
                    '车系ID': file,
                    '车型名称': names[i] if i < len(names) else '',
                    '年款': ys,
                }
                for h in all_h:
                    v = data.get(h, [])
                    row[h] = v[i] if i < len(v) else '-'
                rows.append(row)

        except Exception as e:
            print(f'解析{file}异常: {e}')
            with open(os.path.join(exception_dir, 'exception.txt'), 'a', encoding='utf-8') as f:
                f.write(f'{file}: {e}\n')

    tgt_h = [h for h in all_h if is_target_field(h)]
    print(f'目标字段: {tgt_h}')

    for col, h in enumerate(fixed + all_h):
        ws_all.write(0, col, h)
    for ri, rd in enumerate(rows):
        for col, h in enumerate(fixed + all_h):
            ws_all.write(ri + 1, col, rd.get(h, '-'))

    for col, h in enumerate(fixed + tgt_h):
        ws_tgt.write(0, col, h)
    for ri, rd in enumerate(rows):
        for col, h in enumerate(fixed + tgt_h):
            ws_tgt.write(ri + 1, col, rd.get(h, '-'))

    workbook.save(os.path.join(working_dir, 'autoHome.xls'))

    with open(os.path.join(working_dir, 'autoHome_target.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fixed + tgt_h)
        w.writeheader()
        for rd in rows:
            w.writerow({h: rd.get(h, '-') for h in fixed + tgt_h})

    with open(os.path.join(working_dir, 'autoHome_all.json'), 'w', encoding='utf-8') as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    print(f'第六步完成，共{len(rows)}条')

def main():
    download_car_pages()
    parse_js_to_html()
    parse_json_data()
    crack_html_files()
    generate_data_files()
    generate_excel()

if __name__ == '__main__':
    main()

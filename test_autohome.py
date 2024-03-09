import os
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
    choice = input('进度文件存在,输入1从上次位置继续,输入2从头开始:')
    if choice == '2':
        progress = {}
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

    for letter in [chr(i) for i in range(ord('E'), ord('E') + 1)]:#品牌首字母
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
        if file not in parsed_files and 7342 < int(file) < 7348:
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

# 指定 chromedriver 路径
chromedriver_path = r"D:\Scripts\chromedriver.exe" 

service = Service(chromedriver_path)

class Crack:
    def __init__(self):
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument('--headless')
        chrome_options.binary_location = r"C:\Program Files\Google\Chrome Beta\Application\chrome.exe"
        self.browser = webdriver.Chrome(service=service, options=chrome_options)

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
# 清理表头列名
def clean_header(header):
    return re.sub(r'[/()]', '_', header).strip()

# 清理属性值
def clean_value(value):
    return re.sub(r'<.*?>', '', value)
# 第六步,读取数据文件,生成excel
# 第六步,读取数据文件,生成excel
def generate_excel():
    workbook = xlwt.Workbook(encoding='utf-8')
    worksheet = workbook.add_sheet('汽车之家')
    start_row = 0

    all_headers = set()

    for file in os.listdir(newjson_dir):
        with open(os.path.join(newjson_dir, file), 'r', encoding='utf-8') as f:
            content = ''.join(f.readlines())

        config = re.search(r'var config = (.*?);', content)
        option = re.search(r'var option = (.*?);var', content)
        bag = re.search(r'var bag = (.*?);', content)

        try:
            config_data = json.loads(config.group(1))
            option_data = json.loads(option.group(1))
            bag_data = json.loads(bag.group(1))

            config_items = config_data['result']['paramtypeitems'][0]['paramitems']
            option_items = option_data['result']['configtypeitems'][0]['configitems']

            car_data = {}
            headers = set()

            print(f"Processing file: {file}")

            # 解析基本参数
            for item in config_items:
                header = clean_header(item['name'])
                values = [clean_value(value['value']) for value in item['valueitems']]
                car_data[header] = values
                headers.add(header)
                all_headers.add(header)

            # 解析配置参数
            for item in option_items:
                header = clean_header(item['name'])
                values = [clean_value(value['value']) for value in item['valueitems']]
                car_data[header] = values
                headers.add(header)
                all_headers.add(header)

            print(f"Headers for {file}: {', '.join(sorted(headers))}")

            if start_row == 0:
                col = 0
                for header in sorted(all_headers):
                    worksheet.write(start_row, col, header)
                    col += 1
                start_row += 1

            print(f"All headers: {', '.join(sorted(all_headers))}")

            # 写入数据
            end_row = start_row + max(len(values) for values in car_data.values())
            for row in range(start_row, end_row):
                col = 0
                for header in sorted(all_headers):
                    values = car_data.get(header, ['-'])
                    if row - start_row < len(values):
                        worksheet.write(row, col, values[row - start_row])
                    col += 1

            start_row = end_row

        except Exception as e:
            with open(os.path.join(exception_dir, 'exception.txt'), 'a', encoding='utf-8') as f:
                f.write(f'{file}\n')

    workbook.save(os.path.join(working_dir, 'autoHome.xls'))
    print('第六步完成')

def main():
    download_car_pages()
    parse_js_to_html()
    parse_json_data()
    crack_html_files()
    generate_data_files()
    generate_excel()

if __name__ == '__main__':
    main()

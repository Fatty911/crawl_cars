"""Run once to fix all syntax/logic issues in the crawler files."""
import re, os, sys, textwrap

DIR = os.path.dirname(os.path.abspath(__file__))

def fix_autohome():
    path = os.path.join(DIR, 'test_autohome.py')
    with open(path, 'r', encoding='utf-8') as f:
        src = f.read()

    # Add missing imports
    src = src.replace(
        'import os\n',
        'import os\nimport sys\nimport shutil\nimport csv\n',
        1
    )

    # Replace input() with --restart
    src = re.sub(
        r"choice = input\('进度文件存在.*?'\)\n\s+if choice == '2':\n\s+progress = \{\}",
        "if '--restart' in sys.argv:\n        progress = {}\n        print('已重置进度')\n    else:\n        print('从上次进度继续')",
        src
    )

    # Expand letter range
    src = re.sub(
        r"range\(ord\('E'\), ord\('E'\) \+ 1\)",
        "range(ord('A'), ord('Z') + 1)",
        src
    )

    # Remove car_id filter
    src = re.sub(
        r"if car_id: #and.*?<.*?:",
        "if car_id:",
        src
    )

    # Fix hardcoded Chrome paths - replace Crack class
    old_crack = '''class Crack:
    def __init__(self):
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument('--headless')
        chrome_options.binary_location = r"C:\\Program Files\\Google\\Chrome Beta\\Application\\chrome.exe"
        self.browser = webdriver.Chrome(service=service, options=chrome_options)'''

    new_crack = '''class Crack:
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
            self.browser = webdriver.Chrome(options=chrome_options)'''
    src = src.replace(old_crack, new_crack)

    # Remove old chromedriver setup
    src = re.sub(r'\n#指定 chromedriver 路径\nchromedriver_path.*?\nservice = Service\(chromedriver_path\)\n', '\n', src)

    # Fix tab/space mixing - normalize all indentation
    lines = src.split('\n')
    fixed_lines = []
    for line in lines:
        # Replace tabs with 4 spaces
        fixed_lines.append(line.expandtabs(4))
    src = '\n'.join(fixed_lines)

    # Add helper functions after makedirs block
    helpers = '''
TARGET_FIELDS = [
    '自适应巡航', 'NOA', '城市辅助', '城市领航', '智驾',
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
              r"C:\\Program Files\\Google\\Chrome Beta\\Application\\chrome.exe",
              r"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"]:
        if c and os.path.exists(c):
            return c
    return None

def find_chromedriver():
    for c in [shutil.which('chromedriver'), r"D:\\Scripts\\chromedriver.exe"]:
        if c and os.path.exists(c):
            return c
    return None

def is_target_field(header):
    return any(re.search(kw, header) for kw in TARGET_FIELDS)
'''
    src = src.replace(
        '# 设置重试策略',
        helpers + '\n# 设置重试策略',
        1
    )

    with open(path, 'w', encoding='utf-8') as f:
        f.write(src)
    print(f'Fixed: {path}')


def fix_dongchedi():
    path = os.path.join(DIR, 'crawl_dongchedi.py')
    with open(path, 'r', encoding='utf-8') as f:
        src = f.read()

    # Add missing imports
    if 'import sys' not in src:
        src = src.replace(
            'import os\n',
            'import os\nimport sys\nimport shutil\n',
            1
        )

    # Replace input() with --restart
    src = re.sub(
        r"choice = input\('懂车帝进度.*?'\)\n\s+if choice == '2':\n\s+progress = \{\}",
        "if '--restart' in sys.argv:\n        progress = {}\n        print('已重置进度')\n    else:\n        print('从上次进度继续')",
        src
    )

    # Remove hardcoded paths, add auto-detect
    src = re.sub(
        r"CHROMEDRIVER_PATH = .*\nCHROME_BINARY = .*\n",
        "",
        src
    )

    # Add auto-detect functions before create_browser
    detect_funcs = '''
def find_chrome_binary():
    for c in [shutil.which('chromium-browser'), shutil.which('chromium'),
              shutil.which('google-chrome'), shutil.which('google-chrome-stable'),
              r"C:\\Program Files\\Google\\Chrome Beta\\Application\\chrome.exe"]:
        if c and os.path.exists(c):
            return c
    return None

def find_chromedriver():
    for c in [shutil.which('chromedriver'), r"D:\\Scripts\\chromedriver.exe"]:
        if c and os.path.exists(c):
            return c
    return None

'''
    if'def find_chrome_binary' not in src:
        src = src.replace('def create_browser():', detect_funcs + 'def create_browser():')

    # Fix create_browser to use auto-detect
    src = src.replace(
        "chrome_options.binary_location = CHROME_BINARY",
        "cb = find_chrome_binary()\nif cb:\n        chrome_options.binary_location = cb"
    )
    src = src.replace(
        "service = Service(CHROMEDRIVER_PATH)\n    browser = webdriver.Chrome(service=service, options=chrome_options)",
        "cd = find_chromedriver()\n    if cd:\n        browser = webdriver.Chrome(service=Service(cd), options=chrome_options)\n    else:\n        browser = webdriver.Chrome(options=chrome_options)"
    )

    # Fix continuerow
    src = src.replace('continuerow = {', '                    continue\n\n            row = {')

    # Fix processed_brands indentation
    src = re.sub(
        r"(\s+)\}\)\n\s+processed_brands\.append\(brand_name\)\n(\s+)progress",
        r"\1})\n        processed_brands.append(brand_name)\n        progress",
        src
    )

    # Normalize tabs
    lines = src.split('\n')
    fixed = [line.expandtabs(4) for line in lines]
    src = '\n'.join(fixed)

    with open(path, 'w', encoding='utf-8') as f:
        f.write(src)
    print(f'Fixed: {path}')


if __name__ == '__main__':
    fix_autohome()
    fix_dongchedi()
    print('Done! Now run: python3 -m py_compile test_autohome.py && python3 -m py_compile crawl_dongchedi.py')

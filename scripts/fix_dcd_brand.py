#!/usr/bin/env python3
"""回填懂车帝数据中的空品牌字段"""
import json
import os
import glob
import sys

dir_path = os.path.dirname(os.path.abspath(__file__))
progress_file = os.path.join(dir_path, 'dongchedi', 'progress.json')

# 按长度降序排列，长前缀优先匹配，避免"吉利"在"吉利银河"前误匹配
BRAND_PREFIXES = [
    '吉利银河', '凯迪拉克', '雷克萨斯', '英菲尼迪', '雪铁龙', '比亚迪',
    '保时捷', '沃尔沃', '特斯拉', '阿维塔', '斯柯达', '雪佛兰', '马自达',
    '宝马', '奔驰', '奥迪', '大众', '丰田', '本田', '日产', '沃尔沃',
    '别克', '福特', '现代', '起亚', '吉利', '长城', '红旗', '领克',
    '极氪', '小鹏', '理想', '蔚来', '零跑', '问界', '埃安', '极狐',
    '岚图', '智己', '路虎', '捷豹', '林肯', '捷达', '五菱', '宝骏',
    'WEY', '坦克', '欧拉', '哈弗', '魏牌', '标致',
]

def load_series_brand_map():
    if not os.path.exists(progress_file):
        return {}
    with open(progress_file, 'r', encoding='utf-8') as f:
        prog = json.load(f)
    series_list = prog.get('series_list', [])
    return {str(s.get('id', '')): s.get('brand', '') for s in series_list if s.get('id') and s.get('brand')}

def derive_brand_from_series_name(series_name):
    if not series_name:
        return ''
    for bp in BRAND_PREFIXES:
        if series_name.startswith(bp):
            return bp
    return ''

def fix_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    series_map = load_series_brand_map()
    fixed = 0
    still_empty = 0
    
    for row in data:
        if row.get('品牌'):
            continue
        sid = str(row.get('车系ID', ''))
        brand = series_map.get(sid, '')
        if brand:
            row['品牌'] = brand
            fixed += 1
            continue
        series_name = row.get('车系', '')
        brand = derive_brand_from_series_name(series_name)
        if brand:
            row['品牌'] = brand
            fixed += 1
        else:
            still_empty += 1
    
    if fixed > 0 or still_empty > 0:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f'{os.path.basename(filepath)}: 回填{fixed}条品牌, 仍空{still_empty}条')
    else:
        print(f'{os.path.basename(filepath)}: 无需修复')

if __name__ == '__main__':
    patterns = ['dongchedi_2*.json', 'merged_*.json']
    for pat in patterns:
        for filepath in sorted(glob.glob(os.path.join(dir_path, pat))):
            fix_file(filepath)

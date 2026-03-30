#!/usr/bin/env python3
import json
import re
import os

def debug_json_structure():
    html_file = '/root/crawl_cars/dongchedi/json/99.html'
    
    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # 提取 __NEXT_DATA__
    next_data_match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html_content, re.DOTALL)
    if not next_data_match:
        print('未找到 __NEXT_DATA__')
        return
    
    try:
        next_data = json.loads(next_data_match.group(1))
        print('成功解析 __NEXT_DATA__')
        
        # 保存JSON到文件以便查看
        with open('/tmp/next_data_debug.json', 'w', encoding='utf-8') as f:
            json.dump(next_data, f, ensure_ascii=False, indent=2)
        print('JSON已保存到 /tmp/next_data_debug.json')
        
        # 深度搜索配置值
        def find_values(obj, path=""):
            results = []
            if isinstance(obj, dict):
                for k, v in obj.items():
                    new_path = f"{path}.{k}" if path else k
                    if k == 'values' and isinstance(v, list) and len(v) > 0:
                        results.append((new_path, v))
                    elif isinstance(v, (dict, list)):
                        results.extend(find_values(v, new_path))
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    new_path = f"{path}[{i}]"
                    if isinstance(item, (dict, list)):
                        results.extend(find_values(item, new_path))
            return results
        
        # 搜索values
        print('\n搜索所有values字段...')
        all_values = find_values(next_data)
        for path, values in all_values[:10]:  # 只显示前10个
            print(f'{path}: {len(values)} 个值, 示例: {values[:3] if len(values) > 3 else values}')
        
        # 检查car_info中的info字段
        props = next_data.get('props', {})
        page_props = props.get('pageProps', {})
        raw_data = page_props.get('rawData', {})
        car_info = raw_data.get('car_info', [])
        
        print(f'\n检查car_info的info字段...')
        for i, car in enumerate(car_info[:2]):
            info = car.get('info', {})
            print(f'car[{i}] info keys: {list(info.keys())}')
            if info:
                # 检查info中的配置数据
                for key, value in list(info.items())[:5]:
                    print(f'  {key}: {value}')
        
        # 检查properties中是否有type=2或其他类型的
        properties = raw_data.get('properties', [])
        print(f'\n检查properties的不同type...')
        type_counts = {}
        for prop in properties:
            prop_type = prop.get('type')
            type_counts[prop_type] = type_counts.get(prop_type, 0) + 1
        print(f'type分布: {type_counts}')
        
        # 查找有sub_list且sub_list不为None的properties
        print(f'\n查找有sub_list的properties...')
        for i, prop in enumerate(properties):
            sub_list = prop.get('sub_list')
            if sub_list is not None:
                print(f'property[{i}]: text={prop.get("text")}, type={prop.get("type")}, sub_list长度={len(sub_list) if sub_list else 0}')
                if sub_list:
                    for j, sub in enumerate(sub_list[:2]):
                        print(f'  sub[{j}]: text={sub.get("text")}, keys={list(sub.keys())}')
                        if 'values' in sub:
                            values = sub.get('values', [])
                            print(f'    values: {len(values)} 个值')
        
        # 检查是否有其他数据结构
        print(f'\n检查rawData中的所有keys...')
        for key, value in raw_data.items():
            if isinstance(value, list):
                print(f'{key}: 列表长度 {len(value)}')
            elif isinstance(value, dict):
                print(f'{key}: 字典 keys {list(value.keys())[:10]}')
            else:
                print(f'{key}: {type(value)}')
                
    except Exception as e:
        print(f'解析异常: {e}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    debug_json_structure()
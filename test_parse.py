#!/usr/bin/env python3
import json
import re
import os

def test_parse_html():
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
        
        # 检查数据结构
        props = next_data.get('props', {})
        print(f'props keys: {list(props.keys())}')
        
        page_props = props.get('pageProps', {})
        print(f'pageProps keys: {list(page_props.keys())}')
        
        raw_data = page_props.get('rawData', {})
        print(f'rawData keys: {list(raw_data.keys())}')
        
        # 检查 car_info
        car_info = raw_data.get('car_info', [])
        print(f'\ncar_info 长度: {len(car_info)}')
        if car_info:
            first_car = car_info[0]
            print(f'第一个车型的 keys: {list(first_car.keys())}')
            print(f'车型名称: {first_car.get("car_name")}')
            print(f'property_values keys: {list(first_car.get("property_values", {}).keys())}')
        
        # 检查 properties
        properties = raw_data.get('properties', [])
        print(f'\nproperties 长度: {len(properties)}')
        if properties:
            # 检查前几个properties的结构
            for i, prop in enumerate(properties[:5]):
                print(f'\nproperty[{i}] keys: {list(prop.keys())}')
                print(f'  text: {prop.get("text")}')
                print(f'  type: {prop.get("type")}')
                print(f'  key: {prop.get("key")}')
                print(f'  context: {prop.get("context")}')
                
                # 检查 sub_list
                sub_list = prop.get('sub_list')
                if sub_list is not None:
                    print(f'  sub_list 长度: {len(sub_list)}')
                    if sub_list and len(sub_list) > 0:
                        for j, sub in enumerate(sub_list[:2]):
                            print(f'    sub[{j}] keys: {list(sub.keys())}')
                            print(f'      text: {sub.get("text")}')
                            print(f'      key: {sub.get("key")}')
                            # 检查是否有 values
                            if 'values' in sub:
                                print(f'      values: {sub.get("values")}')
                else:
                    print(f'  sub_list: None')
        
        # 检查 properties 中是否有包含车型值的结构
        print(f'\n检查 properties 中是否包含车型值...')
        for prop in properties[:10]:
            sub_list = prop.get('sub_list')
            if sub_list:
                for sub in sub_list:
                    if 'values' in sub:
                        values = sub.get('values', [])
                        if values and isinstance(values, list) and len(values) > 0:
                            print(f'找到 values 在 property: {prop.get("text")}, sub: {sub.get("text")}')
                            print(f'  values 长度: {len(values)}')
                            print(f'  第一个值: {values[0]}')
                            break
        
        # 查看第一个车型的完整property_values结构
        if car_info:
            car = car_info[0]
            prop_values = car.get('property_values', {})
            if prop_values:
                print(f'\nproperty_values 示例 (前3个):')
                for i, (key, value) in enumerate(list(prop_values.items())[:3]):
                    print(f'  {key}: {value}')
        
    except Exception as e:
        print(f'解析异常: {e}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_parse_html()
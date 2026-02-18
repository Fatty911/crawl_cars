"""合并汽车之家和懂车帝数据，统一表头，对比差异"""
import os
import json
import csv
import glob
from datetime import date

DIR = os.path.dirname(os.path.abspath(__file__))

HEADER_MAP = {
    '全速自适应巡航控制_ACC_': '全速自适应巡航',
    '自适应巡航控制_ACC_': '全速自适应巡航',
    '自适应巡航': '全速自适应巡航',
    'NOA城市路段': 'NOA城市领航',
    '城市辅助驾驶': 'NOA城市领航',
    '城市领航辅助': 'NOA城市领航',
    '城市智驾': 'NOA城市领航',
    '官方0-100km_h加速_s_': '百公里加速(s)',
    '0-100km_h加速时间_s_': '百公里加速(s)',
    '百公里加速时间': '百公里加速(s)',
    '远程启动功能': '远程启动',
    '远程操控': '远程控制',
    'Apple CarPlay': 'CarPlay',
    '手机互联_映射': '手机互联',
    '手机映射': '手机互联',
    '蓝牙钥匙': '蓝牙/数字钥匙',
    'NFC钥匙': '蓝牙/数字钥匙',
    'UWB钥匙': '蓝牙/数字钥匙',
    '数字钥匙': '蓝牙/数字钥匙',
    '手机钥匙': '蓝牙/数字钥匙',
    '最高车速_km_h_': '最高车速(km/h)',
    '后视镜记忆': '外后视镜记忆',
    '主驾驶座椅记忆': '座椅记忆',
    '副驾驶座椅放倒': '前排座椅放倒',
    '后排座椅放倒形式': '后排座椅放倒',
    'CLTC纯电续航里程_km_': '纯电续航(km)',
    'NEDC纯电续航里程_km_': '纯电续航(km)',
    'CLTC纯电续航': '纯电续航(km)',
    '纯电续航': '纯电续航(km)',
}

FIXED = ['数据来源', '品牌', '车系', '车系ID', '车型名称', '年款']


def norm(header):
    if header in HEADER_MAP:
        return HEADER_MAP[header]
    for k, v in HEADER_MAP.items():
        if k in header or header in k:
            return v
    return header


def find_latest(pattern):
    """找到匹配 pattern 的最新文件"""
    files = glob.glob(os.path.join(DIR, pattern))
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def load(path):
    if not path or not os.path.exists(path):
        return []
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def norm_rows(rows, source):
    out = []
    for row in rows:
        nr = {'数据来源': source}
        for k in ['品牌', '车系', '车系ID', '车型名称', '年款']:
            if k in row:
                nr[k] = row[k]
        for k, v in row.items():
            if k in FIXED:
                continue
            u = norm(k)
            if u in nr and nr[u] not in ('', '-'):
                if v not in ('', '-') and v != nr[u]:
                    nr[u] = f'{nr[u]}|{v}'
            else:
                nr[u] = v
        out.append(nr)
    return out


def diff(ah, dcd, all_fields):
    idx = {r.get('车型名称', '').replace(' ', ''): r for r in dcd if r.get('车型名称')}
    out = []
    for r in ah:
        n = r.get('车型名称', '')
        if not n:
            continue
        d = idx.get(n.replace(' ', ''))
        if not d:
            continue
        for f in all_fields:
            a, b = r.get(f, '-'), d.get(f, '-')
            if a != b and a != '-' and b != '-':
                out.append({'车型': n, '配置项': f, '汽车之家': a, '懂车帝': b})
    return out


def main():
    today = date.today().strftime('%Y%m%d')

    ah_file = find_latest('autoHome_*.json')
    dcd_file = find_latest('dongchedi_*.json')
    print(f'汽车之家数据: {ah_file}')
    print(f'懂车帝数据: {dcd_file}')

    ah = norm_rows(load(ah_file), '汽车之家')
    dcd = norm_rows(load(dcd_file), '懂车帝')
    all_rows = ah + dcd
    print(f'汽车之家:{len(ah)} 懂车帝:{len(dcd)} 合计:{len(all_rows)}')

    # 收集所有字段
    all_fields = []
    for r in all_rows:
        for k in r:
            if k not in FIXED and k not in all_fields:
                all_fields.append(k)

    h = FIXED + all_fields
    csv_path = os.path.join(DIR, f'merged_{today}.csv')
    with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=h)
        w.writeheader()
        for r in all_rows:
            w.writerow({k: r.get(k, '-') for k in h})

    diffs = diff(ah, dcd, all_fields)
    diff_path = os.path.join(DIR, f'diff_{today}.csv')
    if diffs:
        with open(diff_path, 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=['车型', '配置项', '汽车之家', '懂车帝'])
            w.writeheader()
            w.writerows(diffs)
        print(f'差异: {len(diffs)} 处')
    else:
        print('无差异')

    json_path = os.path.join(DIR, f'merged_{today}.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(all_rows, f, ensure_ascii=False, indent=2)

    print(f'完成: {csv_path}')


if __name__ == '__main__':
    main()

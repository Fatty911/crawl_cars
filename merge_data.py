"""合并汽车之家和懂车帝数据，统一表头，对比差异，并过滤符合条件的车型。"""
import csv
import glob
import json
import os
import re
from datetime import date

DIR = os.path.dirname(os.path.abspath(__file__))

FILTER_CONDITIONS = {
    "zero_to_hundred": ("百公里加速(s)", 7.0),
    "ev_range": ("纯电续航(km)", 150),
    "city_navigation": [
        "NOA城市领航",
        "城市领航辅助",
        "城市NOA",
        "城市智驾",
        "城市辅助驾驶",
        "NOP城市",
        "城市NOP",
        "城市导航辅助驾驶",
        "城市自动驾驶",
    ],
    "remote_start": ["远程启动", "远程启动功能", "发动机远程启动"],
    "remote_control": ["远程控制", "远程操控", "远程车门", "远程空调", "远程鸣笛闪灯"],
    "bluetooth_key": ["蓝牙/数字钥匙", "蓝牙钥匙", "数字钥匙", "手机钥匙", "UWB钥匙"],
    "seat_memory": ["座椅记忆", "主驾驶座椅记忆", "副驾驶座椅记忆"],
    "mirror_memory": ["后视镜记忆", "外后视镜记忆"],
}

HEADER_MAP = {
    "全速自适应巡航控制_ACC_": "全速自适应巡航",
    "全速自适应巡航": "全速自适应巡航",
    "自适应巡航控制_ACC_": "自适应巡航(ACC)",
    "自适应巡航": "自适应巡航(ACC)",
    "定速巡航": "定速巡航",
    "NOA城市路段": "NOA城市领航",
    "城市辅助驾驶": "NOA城市领航",
    "城市领航辅助": "NOA城市领航",
    "城市智驾": "NOA城市领航",
    "官方0-100km_h加速_s_": "百公里加速(s)",
    "0-100km_h加速时间_s_": "百公里加速(s)",
    "百公里加速时间": "百公里加速(s)",
    "远程启动功能": "远程启动",
    "发动机远程启动": "远程启动",
    "远程操控": "远程控制",
    "手机APP远程功能": "远程控制",
    "Apple CarPlay": "CarPlay",
    "手机互联_映射": "手机互联",
    "手机映射": "手机互联",
    "蓝牙钥匙": "蓝牙/数字钥匙",
    "NFC钥匙": "蓝牙/数字钥匙",
    "UWB钥匙": "蓝牙/数字钥匙",
    "数字钥匙": "蓝牙/数字钥匙",
    "手机钥匙": "蓝牙/数字钥匙",
    "钥匙类型": "蓝牙/数字钥匙",
    "最高车速_km_h_": "最高车速(km/h)",
    "后视镜记忆": "外后视镜记忆",
    "外后视镜功能": "外后视镜记忆",
    "主驾驶座椅记忆": "座椅记忆",
    "电动座椅记忆功能": "座椅记忆",
    "副驾驶座椅放倒": "前排座椅放倒",
    "后排座椅放倒形式": "后排座椅放倒",
    "CLTC纯电续航里程_km_": "纯电续航(km)",
    "NEDC纯电续航里程_km_": "纯电续航(km)",
    "CLTC纯电续航": "纯电续航(km)",
    "纯电续航": "纯电续航(km)",
}

FIXED = ["数据来源", "品牌", "车系", "车系ID", "车型名称", "年款"]


def parse_numbers(value):
    if not value or value == "-":
        return []
    return [float(n) for n in re.findall(r"\d+(?:\.\d+)?", str(value))]


def check_numeric_condition(row, field_name, threshold, op):
    numbers = parse_numbers(row.get(field_name, "-"))
    if not numbers:
        return False
    if op == "<=":
        return any(val <= threshold for val in numbers)
    if op == ">=":
        return any(val >= threshold for val in numbers)
    raise ValueError(f"不支持的比较操作: {op}")


def has_positive_value(value):
    if value is None:
        return False
    text = str(value).strip()
    if not text or text == "-":
        return False
    negative_values = {"无", "不支持", "否", "没有", "未配备", "不提供", "0", "0.0"}
    return text not in negative_values


def check_feature(row, field_names, value_keywords=None, require_keyword=False):
    value_keywords = value_keywords or []

    for field_name in field_names:
        val = row.get(field_name, "-")
        if has_positive_value(val):
            if not require_keyword or any(keyword in str(val) for keyword in value_keywords):
                return True

    for key, val in row.items():
        if not has_positive_value(val):
            continue

        key_text = str(key)
        val_text = str(val)
        key_matches = any(field in key_text or key_text in field for field in field_names)
        value_matches = any(keyword in val_text for keyword in value_keywords)

        if key_matches and not require_keyword:
            return True
        if value_matches:
            return True

    return False


def filter_car(row):
    try:
        if not check_numeric_condition(
            row,
            FILTER_CONDITIONS["zero_to_hundred"][0],
            FILTER_CONDITIONS["zero_to_hundred"][1],
            "<=",
        ):
            return False

        if not check_numeric_condition(
            row,
            FILTER_CONDITIONS["ev_range"][0],
            FILTER_CONDITIONS["ev_range"][1],
            ">=",
        ):
            return False

        if not check_feature(
            row,
            FILTER_CONDITIONS["city_navigation"],
            ["NOA", "NOP", "城市", "领航", "导航辅助"],
        ):
            return False

        if not check_feature(
            row,
            FILTER_CONDITIONS["remote_start"],
            ["远程启动", "车辆启动", "发动机启动", "启动"],
        ):
            return False

        if not check_feature(
            row,
            FILTER_CONDITIONS["remote_control"],
            ["远程控制", "手机APP", "车门控制", "空调控制", "车辆启动"],
        ):
            return False

        if not check_feature(
            row,
            FILTER_CONDITIONS["bluetooth_key"],
            ["蓝牙钥匙", "数字钥匙", "手机钥匙", "UWB钥匙", "NFC钥匙"],
            require_keyword=True,
        ):
            return False

        if not check_feature(
            row,
            FILTER_CONDITIONS["seat_memory"],
            ["座椅记忆", "电动座椅记忆", "主驾驶位", "驾驶位"],
        ):
            return False

        if not check_feature(
            row,
            FILTER_CONDITIONS["mirror_memory"],
            ["后视镜记忆", "外后视镜记忆", "记忆"],
        ):
            return False

        return True
    except Exception as exc:
        print(f"过滤检查异常: {exc}, row: {row.get('车型名称', 'unknown')}")
        return False


def norm(header):
    if header in HEADER_MAP:
        return HEADER_MAP[header]
    for key, value in HEADER_MAP.items():
        if key in header or header in key:
            return value
    return header


def find_latest(pattern):
    """找到匹配 pattern 的最新文件。"""
    files = glob.glob(os.path.join(DIR, pattern))
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def load(path):
    if not path or not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def norm_rows(rows, source):
    out = []
    for row in rows:
        normalized = {"数据来源": source}
        for key in ["品牌", "车系", "车系ID", "车型名称", "年款"]:
            if key in row:
                normalized[key] = row[key]

        for key, val in row.items():
            if key in FIXED:
                continue
            unified = norm(key)
            if unified in normalized and normalized[unified] not in ("", "-"):
                if val not in ("", "-") and val != normalized[unified]:
                    normalized[unified] = f"{normalized[unified]}|{val}"
            else:
                normalized[unified] = val

        out.append(normalized)
    return out


def diff(autohome_rows, dongchedi_rows, all_fields):
    index = {
        row.get("车型名称", "").replace(" ", ""): row
        for row in dongchedi_rows
        if row.get("车型名称")
    }
    out = []
    for row in autohome_rows:
        name = row.get("车型名称", "")
        if not name:
            continue
        dcd_row = index.get(name.replace(" ", ""))
        if not dcd_row:
            continue
        for field in all_fields:
            autohome_val = row.get(field, "-")
            dongchedi_val = dcd_row.get(field, "-")
            if autohome_val != dongchedi_val and autohome_val != "-" and dongchedi_val != "-":
                out.append(
                    {
                        "车型": name,
                        "配置项": field,
                        "汽车之家": autohome_val,
                        "懂车帝": dongchedi_val,
                    }
                )
    return out


def collect_fields(rows):
    fields = []
    for row in rows:
        for key in row:
            if key not in FIXED and key not in fields:
                fields.append(key)
    return FIXED + fields


def write_csv(path, rows, fieldnames):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "-") for key in fieldnames})


def write_json(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)


def main():
    today = date.today().strftime("%Y%m%d")

    autohome_file = find_latest("autoHome_*.json")
    dongchedi_file = find_latest("dongchedi_*.json")
    print(f"汽车之家数据: {autohome_file}")
    print(f"懂车帝数据: {dongchedi_file}")

    autohome_rows = norm_rows(load(autohome_file), "汽车之家")
    dongchedi_rows = norm_rows(load(dongchedi_file), "懂车帝")

    if not autohome_rows and not dongchedi_rows:
        print("错误: 没有找到任何数据文件")
        return

    all_rows = autohome_rows + dongchedi_rows
    print(f"汽车之家:{len(autohome_rows)} 懂车帝:{len(dongchedi_rows)} 合计:{len(all_rows)}")

    filtered_rows = [row for row in all_rows if filter_car(row)]
    print(f"过滤后符合条件的车型: {len(filtered_rows)} 辆")
    if not filtered_rows:
        print("警告: 没有符合条件的车型")

    header = collect_fields(all_rows)

    merged_csv_path = os.path.join(DIR, f"merged_{today}.csv")
    merged_json_path = os.path.join(DIR, f"merged_{today}.json")
    write_csv(merged_csv_path, all_rows, header)
    write_json(merged_json_path, all_rows)

    diffs = []
    if autohome_rows and dongchedi_rows:
        diffs = diff(autohome_rows, dongchedi_rows, header)
        if diffs:
            diff_path = os.path.join(DIR, f"diff_{today}.csv")
            with open(diff_path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["车型", "配置项", "汽车之家", "懂车帝"])
                writer.writeheader()
                writer.writerows(diffs)
            print(f"差异: {len(diffs)} 处")
        else:
            print("无差异")
    else:
        print("跳过差异比较: 只有一个数据源")

    filtered_csv_path = os.path.join(DIR, f"filtered_cars_{today}.csv")
    filtered_json_path = os.path.join(DIR, f"filtered_cars_{today}.json")
    write_csv(filtered_csv_path, filtered_rows, header)
    write_json(filtered_json_path, filtered_rows)

    print("完成")
    print(f"  全部合并: {merged_csv_path}")
    print(f"  全部合并: {merged_json_path}")
    print(f"  符合条件车型: {filtered_csv_path}")
    print(f"  符合条件车型: {filtered_json_path}")


if __name__ == "__main__":
    main()

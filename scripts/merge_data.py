"""合并汽车之家、懂车帝和零整比数据，统一表头，对比差异，并过滤符合条件的车型。"""
import csv
import glob
import json
import os
import re
from datetime import date

DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FILTER_CONFIG_PATH = os.path.join(DIR, "config", "filter_conditions.json")

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
ZERO_RATIO_FIELDS = ["零整比", "零整比来源明细", "零整比匹配方式"]
IDENTITY_FIELDS = {"品牌", "车系", "车型名称", "年款", "车系ID"}

VALUE_SYNONYMS = {
    "标配": "支持",
    "有": "支持",
    "●": "支持",
    "是": "支持",
    "选配": "选装",
    "无": "-",
    "不支持": "-",
    "—": "-",
    "--": "-",
}

MERGE_ANALYSIS_STATS = {}


def canonical_value(value):
    text = str(value or "").strip()
    if not text:
        return "-"
    compact = re.sub(r"\s+", "", text)
    return VALUE_SYNONYMS.get(compact, text)


def tokenize_model(row):
    tokens = set()
    for field in ("车系", "车型名称", "能源类型", "发动机", "变速箱"):
        text = str(row.get(field, "") or "").lower()
        tokens.update(re.findall(r"[a-z]+|\d+(?:\.\d+)?|[\u4e00-\u9fff]+", text))
    stop = {"款", "版", "型", "汽车", "自动", "手动"}
    return {t for t in tokens if t and t not in stop}


def model_sort_key(row):
    year = row_year(row) or 0
    return (
        normalize_match_text(row.get("品牌", "")),
        normalize_match_text(row.get("车系", "")),
        year,
        normalize_match_text(row.get("车型名称", "")),
        normalize_match_text(row.get("能源类型", "")),
        normalize_match_text(row.get("级别", "")),
    )


def identity_match_key(row, name):
    return (
        normalize_match_text(row.get("品牌", "")),
        normalize_match_text(row.get("车系", "")),
        row_year(row) or 0,
        name,
    )


def match_score(ah_row, dcd_row, require_year):
    ah_year = row_year(ah_row)
    dcd_year = row_year(dcd_row)
    if ah_year and dcd_year and ah_year != dcd_year:
        return 0.0, ["year_mismatch"]
    ah_tokens = tokenize_model(ah_row)
    dcd_tokens = tokenize_model(dcd_row)
    union = ah_tokens | dcd_tokens
    inter = ah_tokens & dcd_tokens
    token_score = (len(inter) / len(union)) if union else 0.0
    score = token_score * 0.70
    reasons = ["token_jaccard=%.2f" % token_score]
    if token_score < 0.35:
        return score, reasons
    if ah_year and dcd_year and ah_year == dcd_year:
        score += 0.15
        reasons.append("same_year")
    for field, weight in (("能源类型", 0.08), ("级别", 0.07)):
        av = normalize_match_text(ah_row.get(field, ""))
        dv = normalize_match_text(dcd_row.get(field, ""))
        if av and dv and av == dv:
            score += weight
            reasons.append("same_" + field)
    return score, reasons


def pair_rows_by_features(ah_rows, dcd_rows, stats, level, threshold=0.58):
    ah_unused = sorted(ah_rows, key=model_sort_key)
    dcd_unused = sorted(dcd_rows, key=model_sort_key)
    pairs = []
    candidates = []
    require_year = level == "车系"
    for ai, ah_row in enumerate(ah_unused):
        for di, dcd_row in enumerate(dcd_unused):
            score, reasons = match_score(ah_row, dcd_row, require_year)
            if score >= threshold:
                candidates.append((score, ai, di, reasons))
    candidates.sort(key=lambda item: (-item[0], model_sort_key(ah_unused[item[1]]), model_sort_key(dcd_unused[item[2]])))

    top_by_a = {}
    top_by_d = {}
    for score, ai, di, _ in candidates:
        top_by_a[ai] = max(score, top_by_a.get(ai, score))
        top_by_d[di] = max(score, top_by_d.get(di, score))
    ambiguous_a = {
        ai for ai, top in top_by_a.items()
        if sum(1 for score, candidate_ai, _, _ in candidates if candidate_ai == ai and score == top) > 1
    }
    ambiguous_d = {
        di for di, top in top_by_d.items()
        if sum(1 for score, _, candidate_di, _ in candidates if candidate_di == di and score == top) > 1
    }
    blocked_a = set(ambiguous_a)
    blocked_d = set(ambiguous_d)
    for _, ai, di, _ in candidates:
        if ai in ambiguous_a or di in ambiguous_d:
            blocked_a.add(ai)
            blocked_d.add(di)
    stats.setdefault("_ambiguous_a", set()).update(id(ah_unused[i]) for i in blocked_a)
    stats.setdefault("_ambiguous_d", set()).update(id(dcd_unused[i]) for i in blocked_d)

    used_a = set()
    used_d = set()
    for score, ai, di, reasons in candidates:
        if ai in used_a or di in used_d or ai in blocked_a or di in blocked_d:
            continue
        if score != top_by_a.get(ai) or score != top_by_d.get(di):
            continue
        pairs.append((ah_unused[ai], dcd_unused[di], score, reasons))
        used_a.add(ai)
        used_d.add(di)
    return pairs


def _split_attr_key(key):
    """If key is '属性 - 值', return (属性, 值). Otherwise None."""
    if " - " not in key:
        return None
    parts = key.split(" - ", 1)
    if len(parts) != 2:
        return None
    prefix, suffix = parts
    if not prefix or not suffix:
        return None
    return prefix, suffix


def normalize_attribute_keys(rows):
    """将 one-hot 编码的属性键（如 '辅助驾驶操作系统 - Toyota Pilot'）
    归一化为统一的属性列名，并用后缀作为该行的值。"""
    if not rows:
        return rows

    from collections import defaultdict

    # 收集所有带 " - " 的键
    attrs = defaultdict(list)  # prefix -> [(suffix, full_key)]
    for row in rows:
        for key in list(row.keys()):
            split = _split_attr_key(key)
            if split and (split[1], key) not in attrs[split[0]]:
                attrs[split[0]].append((split[1], key))

    # 只处理有多种后缀的组（真正的 one-hot 编码）
    for prefix, entries in attrs.items():
        if len(entries) <= 1:
            continue
        for row in rows:
            value = None
            for suffix, key in entries:
                val = str(row.get(key, "-") or "-")
                if val and val != "-":
                    if value is None:
                        value = suffix
                    else:
                        value = f"{value}|{suffix}"
                    row.pop(key, None)
                else:
                    row.pop(key, None)
            if value is not None:
                row[prefix] = value

    return rows


def load_filter_config():
    with open(FILTER_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


FILTER_CONFIG = load_filter_config()
FILTER_CONDITIONS = FILTER_CONFIG.get("conditions", [])


def parse_numbers(value):
    if not value or value == "-":
        return []
    return [float(n) for n in re.findall(r"\d+(?:\.\d+)?", str(value))]


def row_year(row):
    for field in ("年款", "车型名称"):
        match = re.search(r"(?:19|20)\d{2}", str(row.get(field, "") or ""))
        if match:
            return int(match.group(0))
    return None


def backfill_year_from_model_name(row):
    if str(row.get("年款", "") or "").strip() not in ("", "-"):
        return
    match = re.search(r"(?:19|20)\d{2}", str(row.get("车型名称", "") or ""))
    if match:
        row["年款"] = match.group(0)


def keep_pages_year(row):
    year = row_year(row)
    return year is not None and year >= 2022


# 品牌名归一化: 汽车之家 vs 懂车帝使用不同品牌名
BRAND_NORMALIZE = {
    "北京": "北京越野",
    "广汽": "广汽传祺",
    "北汽": "北京汽车",
    "aito": "问界",
    "问界": "问界",
    "奥迪audi": "奥迪",
    "埃尚": "埃安",
}

def normalize_match_text(value):
    text = str(value or "").lower()
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[·・\-_()（）\[\]【】/\\.,，。:：;；]", "", text)
    text = re.sub(r"^(19|20)\d{2}款?", "", text)
    return text


def normalize_for_match(text):
    """更激进的文本规范化用于匹配"""
    text = str(text or '')
    text = re.sub(r'\s+', '', text)
    text = text.lower()
    text = re.sub(r'^(19|20)\d{2}款', '', text)
    for word in ['运动版', '运动系列', '豪华版', '精英版', '舒适版', '领先版', '旗舰版', '智享版', '尊享版', '进取版', '时尚版', '经典版', '豪华型', '舒适型', '时尚型', '领先型', '精英型', '旗舰型', '进取型', '尊贵型', '智享型']:
        text = text.replace(word, '')
    text = re.sub(r'[·・\-_/()（）【】\[\]\\\s]', '', text)
    return text


def series_year_key(row):
    """生成车系+年款匹配键"""
    brand = normalize_match_text(row.get('品牌', ''))
    brand = BRAND_NORMALIZE.get(brand, brand)
    series = normalize_match_text(row.get('车系', ''))
    # 品牌为空时从车系名推导
    if not brand and series:
        derived = derive_brand(row.get('车系', ''))
        if derived:
            brand = normalize_match_text(derived)
            brand = BRAND_NORMALIZE.get(brand, brand)
    year = ''
    year_str = str(row.get('年款', ''))
    year_match = re.search(r'(\d{4})', year_str)
    if year_match:
        year = year_match.group(1)
    else:
        # 兜底：从车型名称中提取年款（如"问界M7 2026款 ..."）
        model_name = str(row.get('车型名称', ''))
        year_match2 = re.search(r'(20\d{2})款', model_name)
        if year_match2:
            year = year_match2.group(1)
    return f"{brand}|{series}|{year}" if brand and series else ''


def series_key(row):
    """生成车系匹配键（不含年款，更宽松）"""
    brand = normalize_match_text(row.get('品牌', ''))
    brand = BRAND_NORMALIZE.get(brand, brand)
    series = normalize_match_text(row.get('车系', ''))
    # 品牌为空时从车系名推导
    if not brand and series:
        derived = derive_brand(row.get('车系', ''))
        if derived:
            brand = normalize_match_text(derived)
            brand = BRAND_NORMALIZE.get(brand, brand)
    return f"{brand}|{series}" if brand and series else ''


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
        for condition in FILTER_CONDITIONS:
            condition_type = condition.get("type")
            if condition_type == "range":
                field_name = condition.get("field")
                min_value = condition.get("min")
                max_value = condition.get("max")
                if min_value is not None and not check_numeric_condition(row, field_name, float(min_value), ">="):
                    return False
                if max_value is not None and not check_numeric_condition(row, field_name, float(max_value), "<="):
                    return False
            elif condition_type == "feature":
                if not check_feature(
                    row,
                    condition.get("fields", []),
                    condition.get("keywords", []),
                    condition.get("requireKeyword", False),
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


def load_zero_ratio_rows():
    latest = find_latest("zero_to_whole_ratios_*.json") or os.path.join(DIR, "zero_to_whole_ratios.json")
    rows = load(latest)
    if rows:
        print(f"零整比数据: {latest} ({len(rows)} 条)")
    else:
        print("零整比数据: 未找到，跳过该属性")
    return rows


def parse_ratio_value(value):
    numbers = parse_numbers(value)
    if not numbers:
        return None
    return round(numbers[0], 2)


def zero_ratio_candidates(row, zero_ratio_rows):
    brand = normalize_match_text(row.get("品牌"))
    series = normalize_match_text(row.get("车系"))
    model = normalize_match_text(row.get("车型名称"))
    matches = []

    for item in zero_ratio_rows:
        ratio = parse_ratio_value(item.get("零整比") or item.get("零整比原始值"))
        if ratio is None:
            continue

        src_brand = normalize_match_text(item.get("品牌"))
        src_series = normalize_match_text(item.get("车系"))
        src_model = normalize_match_text(item.get("车型名称"))
        if brand and src_brand and brand not in src_brand and src_brand not in brand and not (
            brand in src_model or src_brand in model
        ):
            continue

        match_type = ""
        if model and src_model and (model == src_model or model in src_model or src_model in model):
            match_type = "车型名称"
        elif series and src_series and (series == src_series or series in src_series or src_series in series):
            match_type = "车系"
        elif series and src_model and series in src_model:
            match_type = "来源车型包含车系"
        elif model and src_series and src_series in model:
            match_type = "车型名称包含来源车系"

        if match_type:
            matches.append((match_type, item, ratio))

    priority = {"车型名称": 0, "车系": 1, "来源车型包含车系": 2, "车型名称包含来源车系": 3}
    if not matches:
        return []
    best = min(priority.get(match_type, 9) for match_type, _, _ in matches)
    return [match for match in matches if priority.get(match[0], 9) == best]


def enrich_zero_ratio(rows, zero_ratio_rows):
    if not zero_ratio_rows:
        return rows

    enriched = 0
    for row in rows:
        candidates = zero_ratio_candidates(row, zero_ratio_rows)
        if not candidates:
            continue

        details = []
        ratios = []
        seen = set()
        match_types = []
        for match_type, item, ratio in candidates:
            detail_key = (
                item.get("数据来源"),
                item.get("发布日期"),
                item.get("车型名称"),
                ratio,
            )
            if detail_key in seen:
                continue
            seen.add(detail_key)
            ratios.append(ratio)
            match_types.append(match_type)
            source = item.get("数据来源", "零整比来源")
            published_at = item.get("发布日期")
            source_label = f"{source}({published_at})" if published_at else source
            model_label = item.get("车型名称") or item.get("车系") or "未命名车型"
            details.append(f"{source_label} {model_label}: {ratio:.2f}%")

        if not ratios:
            continue
        row["零整比"] = f"{sum(ratios) / len(ratios):.2f}%"
        row["零整比来源明细"] = "；".join(details)
        row["零整比匹配方式"] = "|".join(sorted(set(match_types)))
        enriched += 1

    print(f"零整比匹配车型: {enriched} 行")
    return rows


# 品牌前缀列表（从 test_autohome.py 同步，长度降序优先匹配）
BRAND_PREFIXES = [
    '吉利银河', '凯迪拉克', '雷克萨斯', '英菲尼迪', '雪铁龙', '比亚迪',
    '保时捷', '沃尔沃', '特斯拉', '阿维塔', '斯柯达', '雪佛兰', '马自达',
    '宝马', '奔驰', '奥迪', '大众', '丰田', '本田', '日产',
    '别克', '福特', '现代', '起亚', '吉利', '长城', '红旗', '领克',
    '极氪', '小鹏', '理想', '蔚来', '零跑', '问界', '埃安', '极狐',
    '岚图', '智己', '路虎', '捷豹', '林肯', '捷达', '五菱', '宝骏',
    'WEY', '坦克', '欧拉', '哈弗', '魏牌', '标致', '奇瑞', '传祺',
    '荣威', '名爵', '长安', '深蓝', '启源', '哪吒', '腾势', '方程豹',
    '仰望', '星途', '捷途', '猛士', '蓝电', '北汽', '江淮', '东风',
    '大通', '依维柯', '金杯', '福田', '庆铃', '江铃', '凯马',
    '长安欧尚', '广汽', '北京', '东南', '海马', '中华', '力帆',
    '众泰', '陆风', '猎豹', '野马', '黄海', '中兴', '福迪',
    '法拉利', '兰博基尼', '玛莎拉蒂', '劳斯莱斯', '宾利', '阿斯顿马丁',
    '迈凯伦', '布加迪', '帕加尼', '科尼赛克', '阿尔法罗密欧',
    '迈巴赫', 'MINI', 'Smart', 'DS', 'Jeep', 'Ram', '道奇',
    '克莱斯勒', 'GMC', '标致', '雷诺', '菲亚特',
    '斯巴鲁', '三菱', '铃木', '五十铃', '双龙', '讴歌',
]



# 车系名→品牌映射: 当车系名不以品牌前缀开头时的兜底（与 test_autohome.py 同步）
SERIES_TO_BRAND = {
    "皓影": "本田", "皓影新能源": "本田", "冠道": "本田", "缤智": "本田",
    "雅阁": "本田", "凌派": "本田", "ZR-V 致在": "本田",
    "昂科威S": "别克", "昂科威Plus": "别克", "昂科拉PLUS": "别克",
    "君越": "别克", "微蓝6": "别克", "昂扬": "别克",
    "Macan新能源": "保时捷", "Taycan": "保时捷", "Cayenne": "保时捷",
    "Macan": "保时捷",
    "添越": "宾利", "添越插电混动": "宾利", "飞驰插电混动": "宾利",
    "博速 G级": "博速",
    "奔腾T77": "奔腾", "奔腾T99": "奔腾", "奔腾T90": "奔腾",
    "奔腾T90 PHEV": "奔腾", "奔腾E01": "奔腾", "奔腾B70": "奔腾",
    "奔腾B70S": "奔腾",
    "悦意03": "奔腾", "悦意07": "奔腾", "悦意08": "奔腾",
    "魔方": "北京汽车",
    "勇士": "北京汽车制造厂",
    "昌河北斗星": "昌河",
    "212经典": "北京汽车制造厂",
    "巴菲特600": "巴菲特",
    # 比亚迪系列（汽车之家品牌字段为空，需从车系名推导）
    "汉": "比亚迪", "汉L": "比亚迪", "大汉": "比亚迪",
    "秦PLUS": "比亚迪", "秦L": "比亚迪", "秦新能源": "比亚迪",
    "宋Pro新能源": "比亚迪", "宋PLUS新能源": "比亚迪", "宋L EV": "比亚迪",
    "宋L DM-i": "比亚迪", "宋Ultra": "比亚迪", "宋PLUS EV": "比亚迪",
    "宋PLUS DM-i": "比亚迪", "宋Pro DM-i": "比亚迪", "宋DM-i": "比亚迪",
    "元PLUS": "比亚迪", "元UP": "比亚迪", "元Pro": "比亚迪",
    "海豹": "比亚迪", "海豹06": "比亚迪", "海豹06GT": "比亚迪",
    "海豹05 DM-i": "比亚迪", "海豹06 DM-i旅行版": "比亚迪",
    "海豹07 DM-i": "比亚迪", "海豹08": "比亚迪",
    "海狮06": "比亚迪", "海狮05 DM-i": "比亚迪", "海狮05 EV": "比亚迪",
    "海狮07 EV": "比亚迪", "海狮07 DM-i": "比亚迪",
    "海豚": "比亚迪", "海鸥": "比亚迪",
    "驱逐舰05": "比亚迪", "护卫舰07": "比亚迪",
    "唐新能源": "比亚迪", "唐L": "比亚迪", "大唐": "比亚迪",
    "腾势N7": "腾势", "腾势D9": "腾势", "腾势Z9 GT": "腾势",
    "腾势Z9": "腾势", "腾势N8": "腾势", "腾势N9": "腾势",
    # 广汽埃安系列
    "AION V": "埃安", "AION Y": "埃安", "AION LX": "埃安",
    "AION S": "埃安", "AION S MAX": "埃安", "AION S Plus": "埃安",
    "AION RT": "埃安", "AION UT": "埃安", "AION UT super": "埃安",
    "AION N60": "埃安", "AION i60": "埃安",
    # 阿斯顿·马丁
    "阿斯顿·马丁DB12": "阿斯顿·马丁", "阿斯顿·马丁DBX": "阿斯顿·马丁",
    "阿斯顿·马丁DBS": "阿斯顿·马丁", "阿斯顿·马丁DB11": "阿斯顿·马丁",
    "Vanquish": "阿斯顿·马丁", "Valhalla": "阿斯顿·马丁",
    "Valiant": "阿斯顿·马丁", "V8 Vantage": "阿斯顿·马丁",
    # 阿尔法·罗密欧
    "Giulia朱丽叶": "阿尔法·罗密欧", "Tonale托纳利": "阿尔法·罗密欧",
    "Stelvio斯坦维": "阿尔法·罗密欧",
}


def derive_brand(series_name):
    """从车系名称推导品牌，在 merge 阶段作为 brand 回填"""
    if not series_name:
        return ''
    for bp in sorted(BRAND_PREFIXES, key=len, reverse=True):
        if series_name.startswith(bp) or bp in series_name:
            return bp
    # 兜底: 从 SERIES_TO_BRAND 查找
    return SERIES_TO_BRAND.get(series_name, '')


def norm_rows(rows, source):
    out = []
    for row in rows:
        normalized = {"数据来源": source}
        for key in ["品牌", "车系", "车系ID", "车型名称", "年款"]:
            if key in row:
                normalized[key] = row[key]
        backfill_year_from_model_name(normalized)

        # 品牌回填：汽车之家爬虫可能漏品牌，从车系名推导
        if (not normalized.get("品牌") or normalized.get("品牌") == "-") and source == "汽车之家":
            series = normalized.get("车系", "")
            derived = derive_brand(series)
            if derived:
                normalized["品牌"] = derived

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


def merge_single_row(ah_row, dcd_row):
    """合并单个车型的两个数据源，标识字段优先取非空，配置字段冲突用|分隔"""
    merged = {}
    all_keys = set(ah_row.keys()) | set(dcd_row.keys())

    for key in all_keys:
        ah_val = str(ah_row.get(key, "") or "")
        dcd_val = str(dcd_row.get(key, "") or "")
        if key == "年款":
            ah_candidate = dict(ah_row)
            dcd_candidate = dict(dcd_row)
            backfill_year_from_model_name(ah_candidate)
            backfill_year_from_model_name(dcd_candidate)
            ah_val = str(ah_candidate.get(key, "") or "")
            dcd_val = str(dcd_candidate.get(key, "") or "")

        if key in IDENTITY_FIELDS:
            # 标识字段：不拼接，优先取非空且更完整的值
            if ah_val and ah_val != "-":
                if dcd_val and dcd_val != "-" and dcd_val != ah_val:
                    # 两个值都非空且不同，取较长值（通常更完整）
                    merged[key] = ah_val if len(ah_val) >= len(dcd_val) else dcd_val
                else:
                    merged[key] = ah_val
            elif dcd_val and dcd_val != "-":
                merged[key] = dcd_val
            else:
                merged[key] = "-"
        else:
            ah_norm = canonical_value(ah_val)
            dcd_norm = canonical_value(dcd_val)
            if ah_norm != "-" and dcd_norm != "-":
                if ah_norm == dcd_norm:
                    merged[key] = ah_norm
                else:
                    merged[key] = f"汽车之家:{ah_val}|懂车帝:{dcd_val}"
            elif ah_norm != "-":
                merged[key] = ah_norm
            elif dcd_norm != "-":
                merged[key] = dcd_norm
            else:
                merged[key] = "-"

    return merged


def merge_rows(autohome_rows, dongchedi_rows):
    """按车型名称合并两个数据源，支持多级匹配"""
    # 第一级: 精确匹配
    autohome_index = {}
    for row in autohome_rows:
        name = row.get("车型名称", "").replace(" ", "")
        if name:
            autohome_index.setdefault(identity_match_key(row, name), []).append(row)
    dongchedi_index = {}
    for row in dongchedi_rows:
        name = row.get("车型名称", "").replace(" ", "")
        if name:
            dongchedi_index.setdefault(identity_match_key(row, name), []).append(row)

    # 第二级: 规范化匹配
    autohome_norm = {}
    for row in autohome_rows:
        name = row.get("车型名称", "")
        norm_name = normalize_for_match(name)
        if norm_name:
            autohome_norm.setdefault(identity_match_key(row, norm_name), []).append(row)
    dongchedi_norm = {}
    for row in dongchedi_rows:
        name = row.get("车型名称", "")
        norm_name = normalize_for_match(name)
        if norm_name:
            dongchedi_norm.setdefault(identity_match_key(row, norm_name), []).append(row)

    # 第三级: 车系级匹配
    autohome_by_series = {}
    for row in autohome_rows:
        key = series_year_key(row)
        if key:
            autohome_by_series.setdefault(key, []).append(row)
    dongchedi_by_series = {}
    for row in dongchedi_rows:
        key = series_year_key(row)
        if key:
            dongchedi_by_series.setdefault(key, []).append(row)

    merged = []
    used_autohome = set()
    used_dongchedi = set()
    stats = {'精确': 0, '规范': 0, '车系': 0, '仅汽车之家': 0, '仅懂车帝': 0, '低置信拒绝': 0, '歧义拒绝': 0}

    # 第一级: 精确匹配
    for match_key, ah_rows in sorted(autohome_index.items()):
        dcd_rows = dongchedi_index.get(match_key, [])
        for ah_row, dcd_row in zip(sorted(ah_rows, key=model_sort_key), sorted(dcd_rows, key=model_sort_key)):
            merged_row = merge_single_row(ah_row, dcd_row)
            merged_row["数据来源"] = "汽车之家+懂车帝"
            merged.append(merged_row)
            used_autohome.add(id(ah_row))
            used_dongchedi.add(id(dcd_row))
            stats['精确'] += 1

    # 第二级: 规范化匹配
    for match_key, ah_rows in sorted(autohome_norm.items()):
        dcd_rows = dongchedi_norm.get(match_key, [])
        if not dcd_rows:
            continue
        ah_available = sorted((row for row in ah_rows if id(row) not in used_autohome), key=model_sort_key)
        dcd_available = sorted((row for row in dcd_rows if id(row) not in used_dongchedi), key=model_sort_key)
        for ah_row, dcd_row in zip(ah_available, dcd_available):
            merged_row = merge_single_row(ah_row, dcd_row)
            merged_row["数据来源"] = "汽车之家+懂车帝"
            merged.append(merged_row)
            used_autohome.add(id(ah_row))
            used_dongchedi.add(id(dcd_row))
            stats['规范'] += 1

    # 第三级: 车系级匹配（先尝试带年款，再尝试不带年款）
    merged_by_series = {'车系': 0, '车系(无年款)': 0}
    for skey, ah_rows in autohome_by_series.items():
        if skey in dongchedi_by_series:
            dcd_rows_list = dongchedi_by_series[skey]
            ah_unused = [r for r in ah_rows if id(r) not in used_autohome]
            dcd_unused = [r for r in dcd_rows_list if id(r) not in used_dongchedi]
            for ah_match, dcd_match, score, reasons in pair_rows_by_features(ah_unused, dcd_unused, stats, "车系"):
                merged_row = merge_single_row(ah_match, dcd_match)
                merged_row["数据来源"] = "汽车之家+懂车帝(车系级)"
                merged_row["合并匹配置信度"] = f"{score:.2f};" + ",".join(reasons)
                merged.append(merged_row)
                used_autohome.add(id(ah_match))
                used_dongchedi.add(id(dcd_match))
                merged_by_series['车系'] += 1

    # 第四级: 车系匹配（不含年款，更宽松）
    autohome_by_series_noyear = {}
    for row in autohome_rows:
        key = series_key(row)
        if key:
            autohome_by_series_noyear.setdefault(key, []).append(row)
    dongchedi_by_series_noyear = {}
    for row in dongchedi_rows:
        key = series_key(row)
        if key:
            dongchedi_by_series_noyear.setdefault(key, []).append(row)

    for skey, ah_rows in autohome_by_series_noyear.items():
        dcd_rows_list = dongchedi_by_series_noyear.get(skey, [])
        if not dcd_rows_list:
            continue
        ambiguous_a = stats.get("_ambiguous_a", set())
        ambiguous_d = stats.get("_ambiguous_d", set())
        ah_unused = [r for r in ah_rows if id(r) not in used_autohome and id(r) not in ambiguous_a]
        dcd_unused = [r for r in dcd_rows_list if id(r) not in used_dongchedi and id(r) not in ambiguous_d]
        for ah_match, dcd_match, score, reasons in pair_rows_by_features(ah_unused, dcd_unused, stats, "车系(无年款)", threshold=0.72):
            merged_row = merge_single_row(ah_match, dcd_match)
            merged_row["数据来源"] = "汽车之家+懂车帝(车系级)"
            merged_row["合并匹配置信度"] = f"{score:.2f};" + ",".join(reasons)
            merged.append(merged_row)
            used_autohome.add(id(ah_match))
            used_dongchedi.add(id(dcd_match))
            merged_by_series['车系(无年款)'] += 1

    # 未匹配的车型
    for row in autohome_rows:
        if id(row) not in used_autohome:
            merged_row = dict(row)
            merged_row["数据来源"] = "仅汽车之家"
            merged.append(merged_row)
            stats['仅汽车之家'] += 1
    for row in dongchedi_rows:
        if id(row) not in used_dongchedi:
            merged_row = dict(row)
            merged_row["数据来源"] = "仅懂车帝"
            merged.append(merged_row)
            stats['仅懂车帝'] += 1

    ambiguous_a = stats.pop("_ambiguous_a", set())
    ambiguous_d = stats.pop("_ambiguous_d", set())
    stats["歧义拒绝"] = max(len(ambiguous_a), len(ambiguous_d))
    stats["低置信拒绝"] = max(0, min(stats['仅汽车之家'], stats['仅懂车帝']) - stats["歧义拒绝"])
    stats.update(merged_by_series)
    stats["合计"] = len(merged)
    global MERGE_ANALYSIS_STATS
    MERGE_ANALYSIS_STATS = dict(stats)
    print(f"合并统计: 精确{stats['精确']} 规范{stats['规范']} 车系{merged_by_series['车系']} 车系(无年款){merged_by_series['车系(无年款)']} 低置信拒绝{stats['低置信拒绝']} 歧义拒绝{stats['歧义拒绝']} 仅汽车之家{stats['仅汽车之家']} 仅懂车帝{stats['仅懂车帝']} 合计{len(merged)}")
    return merged


def collect_fields(rows):
    fields = []
    for field in ZERO_RATIO_FIELDS:
        if any(row.get(field) for row in rows) and field not in fields:
            fields.append(field)
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
    today = os.environ.get("MERGE_DATE") or date.today().strftime("%Y%m%d")

    autohome_file = find_latest("autoHome_*.json")
    dongchedi_file = find_latest("dongchedi_*.json")
    print(f"汽车之家数据: {autohome_file}")
    print(f"懂车帝数据: {dongchedi_file}")

    autohome_rows = norm_rows(load(autohome_file), "汽车之家")
    dongchedi_rows = norm_rows(load(dongchedi_file), "懂车帝")

    # 归一化 one-hot 属性键（如 "辅助驾驶操作系统 - Toyota Pilot" → "辅助驾驶操作系统": "Toyota Pilot"）
    autohome_rows = normalize_attribute_keys(autohome_rows)
    dongchedi_rows = normalize_attribute_keys(dongchedi_rows)

    if not autohome_rows and not dongchedi_rows:
        print("错误: 没有找到任何数据文件")
        return

    print(f"汽车之家:{len(autohome_rows)} 懂车帝:{len(dongchedi_rows)}")

    # 先diff（需要原始两源数据）
    diffs = []
    if autohome_rows and dongchedi_rows:
        header_for_diff = collect_fields(autohome_rows + dongchedi_rows)
        diffs = diff(autohome_rows, dongchedi_rows, header_for_diff)
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

    # 再合并（按车型去重）
    all_rows = merge_rows(autohome_rows, dongchedi_rows)
    all_rows = enrich_zero_ratio(all_rows, load_zero_ratio_rows())
    before_year_filter = len(all_rows)
    all_rows = [row for row in all_rows if keep_pages_year(row)]
    print(f"2022年及以后车型: {len(all_rows)}/{before_year_filter}")

    filtered_rows = [row for row in all_rows if filter_car(row)]
    print(f"过滤后符合条件的车型: {len(filtered_rows)} 辆")
    analysis_dir = os.path.join(DIR, "docs", "analysis")
    os.makedirs(analysis_dir, exist_ok=True)
    write_json(os.path.join(analysis_dir, f"merge_stats_{today}.json"), {"date": today, "stats": MERGE_ANALYSIS_STATS})
    if not filtered_rows:
        print("警告: 没有符合条件的车型")

    header = collect_fields(all_rows)

    merged_csv_path = os.path.join(DIR, f"merged_{today}.csv")
    merged_json_path = os.path.join(DIR, f"merged_{today}.json")
    write_csv(merged_csv_path, all_rows, header)
    write_json(merged_json_path, all_rows)

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

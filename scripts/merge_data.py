"""合并汽车之家、懂车帝、易车和零整比数据，统一表头，对比差异，并过滤符合条件的车型。"""
from typing import Any
import csv
import glob
import json
import os
import re
import functools
from datetime import date

try:
    from publish_identity import (
        autohome_publish_identity_valid,
        identity_key,
        is_autohome_row,
        is_yiche_row,
        publish_boundary_valid,
        row_car_id,
        valid_official_price,
        yiche_publish_identity_valid,
    )
except ModuleNotFoundError:
    from scripts.publish_identity import (
        autohome_publish_identity_valid,
        identity_key,
        is_autohome_row,
        is_yiche_row,
        publish_boundary_valid,
        row_car_id,
        valid_official_price,
        yiche_publish_identity_valid,
    )

DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FILTER_CONFIG_PATH = os.path.join(DIR, "config", "filter_conditions.json")

YICHE_COMMERCIAL_LEVEL_KEYWORDS = (
    "货车",
    "卡车",
    "皮卡",
    "微货",
    "微卡",
    "轻卡",
    "轻客",
    "微面",
    "客车",
    "面包车",
    "厢式",
    "载货",
    "牵引",
    "自卸",
)

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
    "0-100km/h加速(s)": "百公里加速(s)",
    "0-100km/h加速时间(s)": "百公里加速(s)",
    "官方0-100km/h加速(s)": "百公里加速(s)",
    "官方0-100km_h加速(s)": "百公里加速(s)",
    "官方0-50km_h加速_s_": "官方0-50km/h加速(s)",
    "官方0-50km_h加速(s)": "官方0-50km/h加速(s)",
    "官方0—50Km/h加速时间(s)": "官方0-50km/h加速(s)",
    "官方0-50Km/h加速时间(s)": "官方0-50km/h加速(s)",
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
    "最高车速[km/h]": "最高车速(km/h)",
    "轴距[mm]": "轴距(mm)",
    "轴距_mm_": "轴距(mm)",
    "前轮距[mm]": "前轮距(mm)",
    "前轮距_mm_": "前轮距(mm)",
    "后轮距[mm]": "后轮距(mm)",
    "后轮距_mm_": "后轮距(mm)",
    "整备质量[kg]": "整备质量(kg)",
    "最大功率[kW]": "最大功率(kW)",
    "最大功率_kW_": "最大功率(kW)",
    "最大扭矩[N·m]": "最大扭矩(N·m)",
    "最大扭矩_N·m_": "最大扭矩(N·m)",
    "USB_Type-C接口数量": "USB/Type-C接口数量",
    "蓝牙_车载电话": "蓝牙/车载电话",
    "制动力分配_EBD_CBC等_": "制动力分配(EBD/CBC等)",
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
    "N-Box增强娱乐主机_1": "N-BOX增强娱乐主机_1",
    "N-Box增强娱乐主机_2": "N-BOX增强娱乐主机_2",
    "智能驾驶辅助系统pro": "智能驾驶辅助系统Pro",
    # === 懂车帝 _v4 后缀 → 中文名 ===
    "laser_radar_v4": "激光雷达",
    "driving_assist_chip_computing_v4": "辅助驾驶芯片算力",
    "car_intelligent_system_v4": "车载智能系统",
    "driving_assist_chip_v4": "辅助驾驶芯片",
    "car_intelligent_chip_v4": "车载智能芯片",
    "driving_assist_op_system_v4": "辅助驾驶操作系统",
    "ultrasonic_radar_v4": "超声波雷达",
    "battery_brand_v4": "电池品牌",
    "millimeter_wave_radar_v4": "毫米波雷达",
    "camera_count_v4": "摄像头数量",
    "v2x_communication_v4": "V2X通信",
    "heat_pump_management_system_v4": "热泵管理系统",
    "mobile_remote_control_v4": "手机远程控制",
    "high_precision_map_v4": "高精度地图",
    # === 纯英文字段 → 中文名 ===
    "departure_angle": "离去角(°)",
    "approach_angle": "接近角(°)",
    "engine_max_torque": "最大扭矩(N·m)",
    "electric_max_torque": "电机最大扭矩(N·m)",
    "engine_max_power": "最大功率(kW)",
    "electric_max_power": "电机最大功率(kW)",
    "engine_description": "发动机描述",
    "electric_description": "电机描述",
    "fuel_consumption": "油耗(L/100km)",
    "max_grade": "最大爬坡度(%)",
    "traction_weight": "牵引重量(kg)",
    "ota_version": "OTA版本",
    "total_electric_power": "电机总功率(kW)",
    "total_electric_torque": "电机总扭矩(N·m)",
    "front_electric_max_horsepower": "前电机最大马力(Ps)",
    "ETCS": "ETC装置",
    "ETC": "ETC装置",
    "HomeLink": "HomeLink",
    "HUD": "HUD抬头显示",
    "inductive_back_door": "感应后备厢",
    "electric_back_door": "电动后备厢",
    "electric_door": "电动门",
    "brake_energy_regeneration_v3": "制动能量回收",
    "low_speed_driving_warning_v3": "低速行车警示",
    "battery_type_v3": "电池类型",
    "battery_temperature_management_system_cooling_v3": "电池温控(冷却)",
    "battery_temperature_management_system_heating_v3": "电池温控(加热)",
    "battery_warranty_v3": "电池组质保",
    # === filter_group_ 前缀 → 中文名 ===
    "filter_group_car_year": "年款分组",
    "filter_group_capacity_l": "排量(L)分组",
    "filter_group_driver_form": "驱动形式分组",
    "filter_group_gearbox_type": "变速箱类型分组",
    # === 三源同义词 → 统一列名 ===
    "后悬挂形式": "后悬挂形式",
    "后悬架类型": "后悬挂形式",
    "后悬挂": "后悬挂形式",
    "前悬挂形式": "前悬挂形式",
    "前悬架类型": "前悬挂形式",
    "前悬挂": "前悬挂形式",
    "后悬挂类型": "后悬挂形式",
    "前悬挂类型": "前悬挂形式",
    "长x宽x高(mm)": "长x宽x高(mm)",
    "长*宽*高_mm_": "长x宽x高(mm)",
    "长*宽*高[mm]": "长x宽x高(mm)",
    "长*宽*高(mm)": "长x宽x高(mm)",
    "每缸气门数(个)": "每缸气门数",
    "每缸气门数_个_": "每缸气门数",
    "每缸气门数[个]": "每缸气门数",
    "车门数(个)": "车门数(个)",
    "车门数_个_": "车门数(个)",
    "车门数[个]": "车门数(个)",
    "后备厢容积_L_": "行李舱容积(L)",
    "行李舱容积(L)": "行李舱容积(L)",
    "后座出风口": "后排出风口",
    "后排出风口": "后排出风口",
    "挡位个数": "挡位数",
    "挡位数": "挡位数",
    "低速行车警告": "低速行车警示",
    "低速行车警示音": "低速行车警示",
    "行李厢12V电源接口": "行李舱12V电源接口",
    "行李舱12V电源接口": "行李舱12V电源接口",
    "油箱容积(L)": "油箱容积(L)",
    "油箱容积_L_": "油箱容积(L)",
    "整备质量(kg)": "整备质量(kg)",
    "整备质量_kg_": "整备质量(kg)",
    "满载质量(kg)": "满载质量(kg)",
    "满载质量_kg_": "满载质量(kg)",
    "最小转弯半径_m_": "最小转弯半径(m)",
    "最小转弯半径(m)": "最小转弯半径(m)",
    "风阻系数_Cd_": "风阻系数(Cd)",
    "电动机_Ps_": "电动机马力(Ps)",
    "车机系统内存_GB_": "车机系统内存(GB)",
    "车机系统存储_GB_": "车机系统存储(GB)",
    "电池能量_kWh_": "电池能量(kWh)",
    "多媒体_充电接口": "多媒体充电接口",
    "后轮胎规格尺寸": "后轮胎规格",
    "前轮胎规格尺寸": "前轮胎规格",
    "后轮胎": "后轮胎规格",
    "前轮胎": "前轮胎规格",
    "后轮胎规格": "后轮胎规格",
    "前轮胎规格": "前轮胎规格",
    "备胎放置方式": "备胎放置方式",
    "备胎": "备胎",
    "备胎规格": "备胎",
    "空调控制方式": "空调控制方式",
    "空调温度控制方式": "空调控制方式",
    "座椅材质": "座椅材质",
    "座椅材料": "座椅材质",
    "方向盘材质": "方向盘材质",
    "方向盘材料": "方向盘材质",
    "变速箱类型": "变速箱类型",
    "变速箱描述": "变速箱类型",
    "变速箱": "变速箱类型",
    "变速器": "变速箱类型",
    "驱动形式": "驱动形式",
    "驱动方式": "驱动形式",
    "换挡形式": "换挡形式",
    "换挡方式": "换挡形式",
    "驻车制动类型": "驻车制动类型",
    "驻车制动": "驻车制动类型",
    "前制动器类型": "前制动器类型",
    "前制动器": "前制动器类型",
    "后制动器类型": "后制动器类型",
    "后制动器": "后制动器类型",
    "转向类型": "转向类型",
    "助力类型": "转向类型",
    "驾驶辅助影像": "驾驶辅助影像",
    "倒车影像": "驾驶辅助影像",
    "巡航系统": "巡航系统",
    "定速巡航": "巡航系统",
    "自适应巡航": "巡航系统",
    "道路救援呼叫": "道路救援服务",
    "道路救援服务": "道路救援服务",
    "面部识别": "面部识别",
    "疲劳驾驶提示": "疲劳驾驶提示",
    "驾驶员疲劳提醒": "疲劳驾驶提示",
    "透明底盘_540度影像": "透明底盘/540°影像",
    "哨兵模式_千里眼": "哨兵模式/千里眼",
    "哨兵(千里眼)模式": "哨兵模式/千里眼",
    "哨兵（千里眼）模式": "哨兵模式/千里眼",
    "功放最大输出功率（W）": "功放最大输出功率(W)",
    "超清电⼦外后视镜": "超清电子外后视镜",
    "USB/Type-C接口数量": "USB/Type-C接口数量",
    "USB/Type-C接口": "USB/Type-C接口数量",
    "多媒体接口": "USB/Type-C接口",
    "手机无线充电": "手机无线充电",
    "手机无线充电功能": "手机无线充电",
    "电动后尾门": "电动后备厢",
    "电动后备厢": "电动后备厢",
    "感应后备厢": "感应后备厢",
    "感应后备箱": "感应后备厢",
    "天窗类型": "天窗类型",
    "天窗": "天窗类型",
    "全景天窗": "天窗类型",
    "扬声器数量(个)": "扬声器数量",
    "扬声器数量": "扬声器数量",
    "音响品牌": "扬声器品牌",
    "扬声器品牌": "扬声器品牌",
    "中控屏尺寸(英寸)": "中控屏尺寸",
    "中控屏幕尺寸": "中控屏尺寸",
    "液晶仪表尺寸(英寸)": "液晶仪表尺寸",
    "液晶仪表尺寸": "液晶仪表尺寸",
    "液晶仪表样式": "液晶仪表样式",
    "液晶仪表": "液晶仪表样式",
    "Wi-Fi热点": "WiFi热点",
    "WiFi热点": "WiFi热点",
    "蓝牙/车载电话": "蓝牙/车载电话",
    "蓝牙车载电话": "蓝牙/车载电话",
    "远程启动": "远程启动",
    "远程启动功能": "远程启动",
    "无钥匙进入": "无钥匙进入",
    "无钥匙启动": "无钥匙启动",
    "无钥匙启动系统": "无钥匙启动",
    "无钥匙进入系统": "无钥匙进入",
    "车内氛围灯": "车内氛围灯",
    "氛围灯": "车内氛围灯",
    "大灯延时关闭": "大灯延时关闭",
    "大灯延时": "大灯延时关闭",
    "自适应远近光": "自适应远近光",
    "自适应远近光灯": "自适应远近光",
    "日间行车灯": "日间行车灯",
    "LED日间行车灯": "日间行车灯",
    "近光灯光源": "近光灯",
    "近光灯": "近光灯",
    "远光灯光源": "远光灯",
    "远光灯": "远光灯",

    "内后视镜功能": "内后视镜功能",
    "内后视镜": "内后视镜功能",
    "车窗防夹手功能": "车窗防夹手功能",
    "车窗防夹手": "车窗防夹手功能",
    "后雨刷": "后雨刷",
    "后窗雨刷": "后雨刷",
    "前雾灯": "前雾灯",
    "LED前雾灯": "前雾灯",
    "轮圈材质": "轮圈材质",
    "轮毂材质": "轮圈材质",
    "铝合金轮毂": "铝合金轮毂",
    "铝合金轮圈": "铝合金轮毂",
    "车顶行李架": "车顶行李架",
    "车顶行李架": "车顶行李架",
    "行李架": "车顶行李架",
    "隐藏电动门把手": "隐藏式门把手",
    "隐藏式门把手": "隐藏式门把手",
    "无框设计车门": "无框车门",
    "无框车门": "无框车门",
    "后排隐私玻璃": "后排隐私玻璃",
    "后排侧隐私玻璃": "后排隐私玻璃",
    "主动降噪": "主动降噪",
    "ANC主动降噪": "主动降噪",
    "车载冰箱": "车载冰箱",
    "车载冰箱": "车载冰箱",
    "车载KTV": "车载KTV",
    "K歌功能": "车载KTV",
    "多指飞屏操控": "多指飞屏操控",
    "多指飞屏": "多指飞屏操控",
    "应用商店": "应用商店",
    "应用商城": "应用商店",
    "可见即可说": "可见即可说",
    "语音可见即可说": "可见即可说",
    "能量回收系统": "能量回收系统",
    "制动能量回收": "能量回收系统",
    "防侧翻系统": "防侧翻系统",
    "防翻滚": "防侧翻系统",
    "循迹倒车": "循迹倒车",
    "循迹倒车功能": "循迹倒车",
    "对外放电": "对外放电(V2L)",
    "V2L对外放电": "对外放电(V2L)",
    "外观颜色": "外观颜色",
    "车身颜色": "外观颜色",
    "整车质保": "整车质保",
    "整车保修期限": "整车质保",
    "电池组质保": "电池组质保",
    "三电质保": "电池组质保",
    "燃油标号": "燃油标号",
    "燃油类型": "燃油标号",
    "供油方式": "供油方式",
    "燃油供给方式": "供油方式",
    "缸盖材料": "缸盖材料",
    "缸体材料": "缸体材料",
    "气缸排列形式": "气缸排列形式",
    "气缸排列": "气缸排列形式",
    "气缸数(个)": "气缸数",
    "气缸数": "气缸数",
    "气缸数_个_": "气缸数",
    "压缩比": "压缩比",
    "压缩比_": "压缩比",
    "环保标准": "环保标准",
    "排放标准": "环保标准",
    "发动机型号": "发动机型号",
    "发动机启停技术": "发动机启停技术",
    "发动机自动启停": "发动机启停技术",
    "发动机电子防盗": "发动机电子防盗",
    "发动机防盗锁止": "发动机电子防盗",
    "进气形式": "进气形式",
    "进气方式": "进气形式",
    "配气机构": "配气机构",
    "最大功率转速(rpm)": "最大功率转速(rpm)",
    "最大功率转速": "最大功率转速(rpm)",
    "最大扭矩转速(rpm)": "最大扭矩转速(rpm)",
    "最大扭矩转速": "最大扭矩转速(rpm)",
    "最大马力(Ps)": "最大马力(Ps)",
    "最大马力": "最大马力(Ps)",
    "最大净功率(kW)": "最大净功率(kW)",
    "最大净功率": "最大净功率(kW)",
    "排量(mL)": "排量(mL)",
    "排量(L)": "排量(L)",
    "排量": "排量(L)",
    "燃料形式": "能源类型",
    "能源类型": "能源类型",
    "热泵空调": "热泵空调",
    "热泵管理系统": "热泵空调",
    "CO2热泵空调包": "热泵空调",
    "CO2热泵空调系统": "热泵空调",
    "CO2热泵空调系统_1": "热泵空调",
    "CO2热泵空调系统_2": "热泵空调",
    "CO2热泵空调包_1": "热泵空调",
    "CO2热泵空调包_2": "热泵空调",
    "快充接口": "快充接口",
    "quick_charge_interface_v3": "快充接口",
    "快充接口位置": "快充接口位置",
    "慢充接口位置": "慢充接口位置",
    "快充时间": "快充时间",
    "慢充时间": "慢充时间",
    "电芯品牌": "电芯品牌",
    "电池类型": "电池类型",
    "电池品牌": "电池品牌",
    "四驱形式": "四驱形式",
    "四驱类型": "四驱形式",
    "中央差速器结构": "中央差速器结构",
    "中央差速器": "中央差速器结构",
    "前电动机型号": "前电机型号",
    "后电动机型号": "后电机型号",
    "车体结构": "车体结构",
    "车身结构": "车体结构",
    "车门开启方式": "车门开启方式",
    "车门数": "车门数(个)",
    "座位数(个)": "座位数(个)",
    "座位数_个_": "座位数(个)",
    "座位数[个]": "座位数(个)",
    "座位数": "座位数(个)",
    "上市时间": "上市时间",
    "官方指导价": "官方指导价",
    "经销商报价": "经销商参考价",
    "城市参考价": "经销商参考价",
    "价格": "经销商参考价",
    "级别": "级别",
    "厂商": "厂商",
    "品牌": "品牌",
    "车系": "车系",
    "车型名称": "车型名称",
    "年款": "年款",
    "车系ID": "车系ID",
    "车款ID": "车款ID",
    "系列品牌": "品牌",
    "易车上市状态": "易车上市状态",
    # === 选装包/套装 归一化（去掉 _数字 后缀） ===
    # 这些通常在懂车帝爬虫层已处理，merge 层做兜底
    "选装包列表": "选装包列表",
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
MERGE_DISPOSITION_LEDGER = []


def _safe_identity_key(row):
    """Return a stable identity string for ledger records."""
    try:
        return str(identity_key(row))
    except (ValueError, KeyError, TypeError):
        brand = str(row.get("品牌", "") or "")
        series = str(row.get("车系", "") or "")
        name = str(row.get("车型名称", "") or "")
        return f"{brand}|{series}|{name}"


def _ledger_record(row, decision, reason_code, level="-"):
    """Append a disposition entry to the module-level ledger."""
    MERGE_DISPOSITION_LEDGER.append({
        "identity_key": _safe_identity_key(row),
        "source": str(row.get("数据来源", "") or ""),
        "model_name": str(row.get("车型名称", "") or ""),
        "decision": decision,
        "reason_code": reason_code,
        "level": level,
    })


def canonical_value(value):
    text = str(value or "").strip()
    if not text:
        return "-"
    compact = re.sub(r"\s+", "", text)
    return VALUE_SYNONYMS.get(compact, text)
_VALUE_UNIT_SUFFIX = re.compile(r"(英寸|吋|喇叭|个|秒|s|km|公里|kg|毫米|mm|kW|马力|万元|元|%|L|m|W|度|°|门|座|速)$")
_SHIFT_SUFFIX = ('换挡|变速箱|变速|挡|档'.split("|"))
_DATE_FAMILY = re.compile(r"^(\d{4})[-.](\d{1,2})(?:[-.](\d{1,2}))?$")
_DATE_FIELDS = ('上市时间|上市日期|上市年份|上市月份'.split("|"))
_SHIFT_FIELDS = ('换挡形式|变速箱类型'.split("|"))


def _date_family(compact: str):
    """(year, month, day_or_None) for date-like values."""
    match = _DATE_FAMILY.match(compact)
    if not match:
        return None
    return (match.group(1), int(match.group(2)), match.group(3))

@functools.lru_cache(maxsize=1000000)
def canonical_compare(value: Any, field: str | None = None) -> str:
    """Normalized comparison key that folds format/unit/separator/suffix
    differences without changing the stored value."""
    text = str(value or "").strip()
    if not text:
        return ""
    compact = re.sub(r"\s+", "", text)
    field = str(field or "")
    if field not in _DATE_FIELDS and field not in _SHIFT_FIELDS:
        if not re.search(r"[\d.*×xX]", compact):
            return canonical_value(text)
    if field in _DATE_FIELDS:
        family = _date_family(compact)
        if family:
            if family[2]:
                return "date:%s-%02d-%02d" % (family[0], family[1], int(family[2]))
            return "date:%s-%02d" % (family[0], family[1])
    if field in _SHIFT_FIELDS:
        stripped = compact
        for suffix in _SHIFT_SUFFIX:
            if stripped.endswith(suffix):
                stripped = stripped[: -len(suffix)]
        if stripped:
            return "shift:%s" % stripped
    no_unit = _VALUE_UNIT_SUFFIX.sub("", compact)
    if re.fullmatch(r"\d+(?:\.\d+)?", no_unit):
        return "num:%s" % no_unit
    if re.search(r"[*×xX]", compact):
        dims = [d for d in re.split(r"[*×xX]", compact) if d]
        if dims and all(re.fullmatch(r"\d+(?:\.\d+)?", d) for d in dims):
            return "dims:%s" % "x".join(dims)
    return canonical_value(text)

@functools.lru_cache(maxsize=1000000)
def _date_conflict_foldable(left: str, right: str) -> bool:
    """True when both sides share year+month and at least one side lacks
    the day (precision gap), so folding cannot hide a day-level diff."""
    lf = _date_family(re.sub(r"\s+", "", str(left or "")))
    rf = _date_family(re.sub(r"\s+", "", str(right or "")))
    if not lf or not rf:
        return False
    if lf[0] != rf[0] or lf[1] != rf[1]:
        return False
    return lf[2] is None or rf[2] is None



_CHINESE_SEAT_DIGITS = {"二": "2", "三": "3", "四": "4", "五": "5", "六": "6", "七": "7", "八": "8", "九": "9"}
_TIER_PATTERN = re.compile(r"(?<![a-z0-9])(ultra\+|pro\+|max\+|ultra|elite|pro|max|gt)(?![a-z])", re.I)
_CHINESE_GRADE_PATTERN = re.compile(r"(?<![\u4e00-\u9fff])(闪充\s*)?(尊荣|尊越|旗舰|基本)\s*(?=[型版])")
_BATTERY_NAME_PATTERN = re.compile(r"(?<!\d)(\d{2,3}(?:\.\d+)?)\s*kwh", re.I)
_RANGE_NAME_PATTERN = re.compile(r"(?<!\d)(\d{3,4}(?:\.\d+)?)\s*(?:km|公里)", re.I)
_SERIES_ALIASES = {"腾势n9dm": "腾势n9"}
_EXTERNAL_SERIES_ALIASES: dict[str, str] = {}
_SERIES_ALIASES_LOADED = False
_EXTERNAL_BRAND_ALIASES: dict[str, str] = {}
_BRAND_ALIASES_LOADED = False

def _load_brand_aliases() -> dict[str, str]:
    """Load the AI-maintainable brand alias map once (config/brand_aliases.json).
    Missing config is cached as an empty map; corrupt or unreadable config
    returns an empty map without caching so the next call retries.
    """
    global _EXTERNAL_BRAND_ALIASES, _BRAND_ALIASES_LOADED
    if _BRAND_ALIASES_LOADED:
        return _EXTERNAL_BRAND_ALIASES
    aliases: dict[str, Any] = {"series_brand_aliases": []}
    try:
        path = os.path.join(DIR, "config", "brand_aliases.json")
        with open(path, encoding="utf-8") as handle:
            value = json.load(handle)
        for item in value.get("series_brand_aliases", []) if isinstance(value, dict) else []:
            if not isinstance(item, dict):
                continue
            brand = str(item.get("brand") or "").strip()
            series = str(item.get("series") or "").strip()
            target = str(item.get("target_brand") or "").strip()
            if brand and series and target and target != brand:
                aliases["series_brand_aliases"].append({"brand": brand, "series": series, "target_brand": target})
    except FileNotFoundError:
        pass  # missing config is the normal empty state; cache it
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {}  # corrupt/unreadable: do not cache, retry next call
    _BRAND_ALIASES_LOADED = True
    _EXTERNAL_BRAND_ALIASES = aliases
    return aliases
_PIPE_SUFFIX_PATTERN = re.compile(r"\|[^|]+$")

def normalize_brand_text(value: str) -> str:
    """Normalize a brand name for matching: lowercase, strip whitespace
    and punctuation, drop pipe source-marker suffixes ("奇瑞风云|高德" -> "奇瑞风云"), apply the built-in brand map and the external alias map."
    """
    text = normalize_match_text(value)
    text = _PIPE_SUFFIX_PATTERN.sub("", text)
    return BRAND_NORMALIZE.get(text, text)


def _load_series_aliases() -> dict[str, str]:
    """Load the AI-maintainable series alias map once (config/series_aliases.json).
    Missing config is cached as an empty map; corrupt or unreadable config
    returns an empty map without caching so the next call retries.
    """
    global _EXTERNAL_SERIES_ALIASES, _SERIES_ALIASES_LOADED
    if _SERIES_ALIASES_LOADED:
        return _EXTERNAL_SERIES_ALIASES
    aliases: dict[str, str] = {}
    try:
        path = os.path.join(DIR, "config", "series_aliases.json")
        with open(path, encoding="utf-8") as handle:
            value = json.load(handle)
        for item in value.get("aliases", []) if isinstance(value, dict) else []:
            source = str(item.get("source") or "").strip()
            target = str(item.get("target") or "").strip()
            if source and target and source != target:
                aliases[source] = target
    except FileNotFoundError:
        pass  # missing config is the normal empty state; cache it
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {}  # corrupt/unreadable: do not cache, retry next call
    _SERIES_ALIASES_LOADED = True
    _EXTERNAL_SERIES_ALIASES = aliases
    return aliases

_SEAT_FIELDS = ("座位数(个)", "座位数", "座位数_个_")
_DRIVE_FIELDS = ("驱动形式", "驱动方式", "驱动形式分组", "电机布局", "四驱形式", "四驱类型")
_BATTERY_FIELDS = ("电池能量(kWh)", "电池能量_kWh_", "电池容量(kWh)", "电池容量_kWh_", "电池能量", "电池容量", "动力电池容量")
_RANGE_FIELDS = (
    "纯电续航(km)",
    "纯电续航_km_",
    "纯电续航里程(km)",
    "纯电续航里程_km_",
    "CLTC纯电续航(km)",
    "CLTC纯电续航_km_",
    "CLTC纯电续航里程(km)",
    "CLTC纯电续航里程_km_",
    "工信部纯电续航里程(km)",
    "工信部纯电续航里程_km_",
)


def normalize_series_match_text(value):
    text = normalize_match_text(value)
    external = _load_series_aliases() if not _SERIES_ALIASES_LOADED else _EXTERNAL_SERIES_ALIASES
    return external.get(text, _SERIES_ALIASES.get(text, text))


def _measure_values(values):
    measured = set()
    for value in values:
        for number in re.findall(r"\d+(?:\.\d+)?", str(value or "")):
            measured.add(f"{float(number):g}")
    return measured


def model_positive_evidence(row):
    name = str(row.get("车型名称", "") or "").lower()
    battery = _measure_values(_BATTERY_NAME_PATTERN.findall(name))
    battery.update(_measure_values(row.get(field) for field in _BATTERY_FIELDS))
    driving_range = _measure_values(_RANGE_NAME_PATTERN.findall(name))
    driving_range.update(_measure_values(row.get(field) for field in _RANGE_FIELDS))
    range_class = set()
    if "超长续航" in name:
        range_class.add("extra_long_range")
    elif "长续航" in name:
        range_class.add("long_range")
    if "标准续航" in name or "标准版" in name:
        range_class.add("standard_range")
    return {"battery": battery, "range": driving_range, "range_class": range_class}


def has_explicit_battery_field_inconsistency(row):
    """Detect a published row whose named battery conflicts with one capacity field.

    This is a merged-row integrity check, not a matching hard conflict: battery
    values remain positive-only evidence in ``match_score``.
    """
    name = str(row.get("车型名称", "") or "").lower()
    named_values = _measure_values(_BATTERY_NAME_PATTERN.findall(name))
    if not named_values:
        return False
    for field in _BATTERY_FIELDS:
        field_values = _measure_values([row.get(field)])
        if field_values and named_values.isdisjoint(field_values):
            return True
    return False


def model_variant_signature(row, include_fields=True):
    text = str(row.get("车型名称", "") or "").lower().replace("＋", "+")
    for chinese, digit in _CHINESE_SEAT_DIGITS.items():
        text = re.sub(rf"{chinese}\s*座", f"{digit}座", text)
    tiers = {match.lower() for match in _TIER_PATTERN.findall(text)}
    for match in _CHINESE_GRADE_PATTERN.finditer(text):
        prefix = "flash_" if match.group(1) else ""
        tiers.add(prefix + {"尊荣": "honor", "尊越": "premier", "旗舰": "flagship", "基本": "basic"}[match.group(2)])
    seats = set(re.findall(r"([2-9])\s*座", text))
    if include_fields:
        seats.update(
            match.group(1)
            for field in _SEAT_FIELDS
            if (match := re.fullmatch(r"\s*([2-9])\s*(?:座)?\s*", str(row.get(field, "") or "")))
        )
    lidar = set(re.findall(r"(\d{2,4})\s*线\s*激光雷达", text))
    if include_fields:
        lidar.update(
            match.group(1)
            for key, value in row.items()
            if "激光雷达" in str(key)
            if (match := re.search(r"(\d{2,4})\s*线", str(value or "")))
        )
    drives = set()
    drive_text = text
    if include_fields:
        drive_text = " ".join([drive_text, *(str(row.get(field, "") or "") for field in _DRIVE_FIELDS)])
    if re.search(r"四驱|4wd|awd", drive_text, re.I): drives.add("awd")
    if re.search(r"后驱|rwd", drive_text, re.I): drives.add("rwd")
    if re.search(r"前驱|fwd", drive_text, re.I): drives.add("fwd")
    return {"tier": tiers, "seat": seats, "lidar": lidar, "drive": drives}


def tokenize_model(row):
    tokens = set()
    signature = model_variant_signature(row, include_fields=False)
    for kind, values in signature.items(): tokens.update(f"{kind}:{value}" for value in values)
    for field in ("车系", "车型名称", "能源类型"):
        value = normalize_series_match_text(row.get(field, "")) if field == "车系" else row.get(field, "")
        text = str(value or "").lower().replace("＋", "+")
        for chinese, digit in _CHINESE_SEAT_DIGITS.items(): text = re.sub(rf"{chinese}\s*座", f"{digit}座", text)
        text = re.sub(r"(?:19|20)\d{2}款?", " ", text)
        text = _TIER_PATTERN.sub(" ", text)
        text = _CHINESE_GRADE_PATTERN.sub(" ", text)
        text = re.sub(r"[2-9]\s*座", " ", text)
        text = re.sub(r"\d{2,4}\s*线\s*激光雷达", " ", text)
        text = re.sub(r"四驱|后驱|前驱|4wd|awd|rwd|fwd", " ", text, flags=re.I)
        text = _BATTERY_NAME_PATTERN.sub(" ", text)
        text = _RANGE_NAME_PATTERN.sub(" ", text)
        text = re.sub(r"超长续航|长续航|标准续航|标准版", " ", text)
        tokens.update(re.findall(r"[a-z]+|\d+(?:\.\d+)?|[\u4e00-\u9fff]+", text))
    stop = {"款", "版", "型", "汽车", "自动", "手动", "座"}
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


def _variant_conflict_from_signatures(left_signature, right_signature):
    for field in ("tier", "seat", "lidar", "drive"):
        left_values = left_signature[field]
        right_values = right_signature[field]
        if left_values and right_values and left_values.isdisjoint(right_values):
            return field + "_mismatch"
    return ""

def model_variant_conflict_reason(left_row, right_row):
    left_signature = model_variant_signature(left_row)
    right_signature = model_variant_signature(right_row)
    return _variant_conflict_from_signatures(left_signature, right_signature)


def match_score(ah_row, dcd_row, require_year, _cache=None):
    ah_year = row_year(ah_row)
    dcd_year = row_year(dcd_row)
    if ah_year and dcd_year and ah_year != dcd_year:
        return 0.0, ["year_mismatch"]
    if _cache is not None:
        ah_signature = _cache["left"]["signature"]
        dcd_signature = _cache["right"]["signature"]
        conflict_reason = _variant_conflict_from_signatures(ah_signature, dcd_signature)
    else:
        conflict_reason = model_variant_conflict_reason(ah_row, dcd_row)
    if conflict_reason:
        return 0.0, [conflict_reason]
    if _cache is not None:
        ah_tokens = _cache["left"]["tokens"]
        dcd_tokens = _cache["right"]["tokens"]
    else:
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
    if _cache is not None:
        ah_evidence = _cache["left"]["evidence"]
        dcd_evidence = _cache["right"]["evidence"]
    else:
        ah_evidence = model_positive_evidence(ah_row)
        dcd_evidence = model_positive_evidence(dcd_row)
    for field, weight in (("battery", 0.04), ("range", 0.04), ("range_class", 0.04)):
        if ah_evidence[field] and dcd_evidence[field] and not ah_evidence[field].isdisjoint(dcd_evidence[field]):
            score += weight
            reasons.append("same_" + field)
    return score, reasons


def pair_rows_by_features(ah_rows, dcd_rows, stats, level, threshold=0.58, max_candidates=20000, score_func=None, require_degree_one=False):
    score_func = score_func or match_score
    ah_unused = sorted(ah_rows, key=model_sort_key)
    dcd_unused = sorted(dcd_rows, key=model_sort_key)
    pairs = []
    candidates = []
    require_year = level == "车系"
    candidate_count = len(ah_unused) * len(dcd_unused)
    if candidate_count > max_candidates:
        stats.setdefault("_ambiguous_a", set()).update(id(row) for row in ah_unused)
        stats.setdefault("_ambiguous_d", set()).update(id(row) for row in dcd_unused)
        stats["大桶跳过"] = stats.get("大桶跳过", 0) + 1
        stats["大桶候选"] = stats.get("大桶候选", 0) + candidate_count
        print(
            f"跳过过大车系模糊匹配桶: level={level} "
            f"autohome={len(ah_unused)} dongchedi={len(dcd_unused)} candidates={candidate_count}"
        )
        return pairs
    score_name = getattr(score_func, "__name__", "")
    use_cache = score_name in ("match_score", "yiche_match_score")
    if use_cache:
        if score_name == "match_score":
            ah_cache = [
                {"tokens": tokenize_model(r), "signature": model_variant_signature(r), "evidence": model_positive_evidence(r)}
                for r in ah_unused
            ]
            dcd_cache = [
                {"tokens": tokenize_model(r), "signature": model_variant_signature(r), "evidence": model_positive_evidence(r)}
                for r in dcd_unused
            ]
        else:
            ah_cache = [
                {"tokens": tokenize_yiche_model(r)}
                for r in ah_unused
            ]
            dcd_cache = [
                {"tokens": tokenize_yiche_model(r)}
                for r in dcd_unused
            ]
    else:
        ah_cache = dcd_cache = None

    for ai, ah_row in enumerate(ah_unused):
        for di, dcd_row in enumerate(dcd_unused):
            if use_cache:
                score, reasons = score_func(
                    ah_row, dcd_row, require_year,
                    _cache={"left": ah_cache[ai], "right": dcd_cache[di]},
                )
            else:
                score, reasons = score_func(ah_row, dcd_row, require_year)
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
    if require_degree_one:
        degree_a = {ai: sum(1 for _, candidate_ai, _, _ in candidates if candidate_ai == ai) for ai in top_by_a}
        degree_d = {di: sum(1 for _, _, candidate_di, _ in candidates if candidate_di == di) for di in top_by_d}
        degree_ambiguous_a = {ai for ai, degree in degree_a.items() if degree != 1}
        degree_ambiguous_d = {di for di, degree in degree_d.items() if degree != 1}
        for _, ai, di, _ in candidates:
            if ai in degree_ambiguous_a or di in degree_ambiguous_d:
                blocked_a.add(ai)
                blocked_d.add(di)
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


def _merge_distinct_values(existing, incoming):
    if not has_positive_value(existing):
        return incoming
    if not has_positive_value(incoming):
        return existing
    parts = [part.strip() for part in str(existing).split("|")]
    incoming_text = str(incoming).strip()
    return existing if incoming_text in parts else f"{existing}|{incoming_text}"


def normalize_attribute_keys(rows):
    """Collapse each selected ``attribute - value`` key without losing conflicts."""
    for row in rows:
        for key in list(row.keys()):
            split = _split_attr_key(key)
            if not split:
                continue
            prefix, suffix = split
            raw_value = row.pop(key, None)
            if has_positive_value(raw_value):
                row[prefix] = _merge_distinct_values(row.get(prefix), suffix)
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
    if is_yiche_row(row) and not yiche_publish_identity_valid(row):
        return False
    year = row_year(row)
    if year is None:
        return False
    return year >= 2022


# 品牌名归一化: 汽车之家 vs 懂车帝使用不同品牌名
BRAND_NORMALIZE = {
    "北京": "北京越野",
    "广汽": "广汽传祺",
    "北汽": "北京汽车",
    "aito": "问界",
    "问界": "问界",
    "奥迪audi": "奥迪",
    "埃尚": "埃安",
    '小鹏汽车': '小鹏', '小鹏': '小鹏',
    '腾势汽车': '腾势', '腾势': '腾势',
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


def _apply_series_brand_alias(brand: str, series: str) -> str:
    """Series-scoped brand correction from config/brand_aliases.json.
    Global brand aliases are unsafe (e.g. 荣威R7 exists as its own model,
    so 荣威->飞凡 must never be global); the correction unit is
    (brand, series) -> target brand.  Empty config => zero change.
    """
    if not brand or not series:
        return brand
    external = _load_brand_aliases() if not _BRAND_ALIASES_LOADED else _EXTERNAL_BRAND_ALIASES
    for item in external.get("series_brand_aliases", []):
        if item.get("brand") == brand and item.get("series") == series:
            return item.get("target_brand") or brand
    return brand

def series_year_key(row):
    """生成车系+年款匹配键"""
    brand = normalize_brand_text(row.get('品牌', ''))
    series = normalize_series_match_text(row.get('车系', ''))
    brand = _apply_series_brand_alias(brand, series)
    # 品牌为空时从车系名推导
    if not brand and series:
        derived = derive_brand(row.get('车系', ''))
        if derived:
            brand = normalize_brand_text(derived)
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
    brand = normalize_brand_text(row.get('品牌', ''))
    series = normalize_series_match_text(row.get('车系', ''))
    brand = _apply_series_brand_alias(brand, series)
    # 品牌为空时从车系名推导
    if not brand and series:
        derived = derive_brand(row.get('车系', ''))
        if derived:
            brand = normalize_brand_text(derived)
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


SCHEMA_UNIT_TOKENS = (
    "L/100km", "kWh/100km", "Wh/kg", "万/秒", "km/h", "N·m",
    "英寸", "rpm", "kWh", "mL", "km", "mm", "kg", "kW", "GB",
    "Ps", "Cd", "个", "座", "门", "秒", "°", "%", "L", "m", "W", "s",
)
SCHEMA_UNDERSCORE_UNITS = {
    "L_100km": "L/100km",
    "kWh_100km": "kWh/100km",
    "Wh_kg": "Wh/kg",
    "万_秒": "万/秒",
    "km_h": "km/h",
    **{unit: unit for unit in SCHEMA_UNIT_TOKENS if "/" not in unit},
}


def normalize_schema_unit_header(header):
    """Normalize punctuation-only unit spellings without changing the measured metric."""
    normalized = str(header).strip().translate(str.maketrans({"（": "(", "）": ")", "—": "-", "–": "-"}))
    unit_pattern = "|".join(re.escape(unit) for unit in sorted(SCHEMA_UNIT_TOKENS, key=len, reverse=True))
    normalized = re.sub(rf"\[({unit_pattern})\]$", r"(\1)", normalized)
    for encoded, display in sorted(SCHEMA_UNDERSCORE_UNITS.items(), key=lambda item: len(item[0]), reverse=True):
        suffix = f"_{encoded}_"
        if normalized.endswith(suffix):
            normalized = f"{normalized[:-len(suffix)]}({display})"
            break
    return normalized


def norm(header):
    header = str(header).strip()
    header = HEADER_MAP.get(header, header)
    header = normalize_schema_unit_header(header)
    header = HEADER_MAP.get(header, header)
    # Only the documented v4 schema may use a structured suffix mapping.
    m_v4 = re.match(r'^(.+)_v4_(.+)$', header)
    if m_v4:
        base_v4_key = m_v4.group(1) + "_v4"
        if base_v4_key in HEADER_MAP:
            return HEADER_MAP[base_v4_key]
    return header


AUDITED_PUBLISH_EXACT_HEADERS = {
    "燃料形式",
    "官方0-100km/h加速[s]",
    "官方0-100km_h加速_s_",
    "官方0-50km_h加速_s_",
    "官方0—50Km/h加速时间(s)",
    "官方0-50Km/h加速时间(s)",
    "N-Box增强娱乐主机_1",
    "N-Box增强娱乐主机_2",
    "智能驾驶辅助系统pro",
}


_HEADER_ALIASES: dict[str, dict[str, str]] | None = None


def _load_header_aliases() -> dict[str, dict[str, str]]:
    """Load the AI-maintainable column alias map once (config/column_header_aliases.json).

    A missing or invalid file degrades to an empty map; this module never
    fails because of the alias config.  The map is only consulted by the
    publish-time header normalizer, never by merge matching.
    """
    global _HEADER_ALIASES
    if _HEADER_ALIASES is None:
        aliases: dict[str, dict[str, str]] = {}
        path = os.path.join(DIR, 'config', 'column_header_aliases.json')
        try:
            with open(path, encoding='utf-8') as handle:
                raw = json.load(handle)
            for item in raw.get('aliases', []) if isinstance(raw, dict) else []:
                column = str(item.get('column') or '').strip()
                canonical = str(item.get('canonical') or '').strip()
                if column and canonical and column != canonical:
                    entry: dict[str, str] = {'canonical': canonical}
                    value = str(item.get('value') or '').strip()
                    if value:
                        entry['value'] = value
                    aliases[column] = entry
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            aliases = {}
        _HEADER_ALIASES = aliases
    return _HEADER_ALIASES


def header_alias_lookup(header):
    """Return {'canonical': ..., 'value': ...} for a configured alias or None."""
    return _load_header_aliases().get(str(header).strip())


def normalize_audited_publish_header(header):
    """Apply only the audited punctuation/unit/scope aliases to carried Pages rows."""
    original = str(header)
    stripped = original.strip()
    alias = header_alias_lookup(stripped)
    if alias:
        return alias["canonical"]
    # Mirror the merge-time ``norm`` v4 suffix mapping so one-hot value
    # columns such as ``driving_assist_chip_v4_NVIDIA DRIVE Orin X`` fold
    # back into the canonical attribute at publish time as well.
    m_v4 = re.match(r"^(.+)_v4_(.+)$", stripped)
    if m_v4:
        base_v4_key = m_v4.group(1) + "_v4"
        if base_v4_key in HEADER_MAP:
            return HEADER_MAP[base_v4_key]
    normalized = normalize_schema_unit_header(stripped)
    canonical_unit = any(stripped.endswith(f"({unit})") for unit in SCHEMA_UNIT_TOKENS)
    if original != stripped or normalized != stripped or canonical_unit or stripped in AUDITED_PUBLISH_EXACT_HEADERS:
        return HEADER_MAP.get(normalized, normalized)
    return stripped


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


def normalize_source_row_headers(row):
    """Strip only boundary whitespace from source keys and preserve collisions."""
    normalized = {}
    for key, value in row.items():
        clean_key = str(key).strip()
        if clean_key in normalized:
            normalized[clean_key] = _merge_distinct_values(normalized[clean_key], value)
        else:
            normalized[clean_key] = value
    return normalized


def normalize_option_package_fields(rows):
    """Extract packages only when a row proves the source's description/status pair schema."""
    rows = [normalize_source_row_headers(row) for row in rows]
    package_bases = set()
    for row in rows:
        grouped = {}
        for key, value in row.items():
            match = re.match(r"^(.+)_(\d+)$", key)
            if match:
                grouped.setdefault(match.group(1), {})[match.group(2)] = value
        for base, pair in grouped.items():
            first, second = pair.get("1"), pair.get("2")
            if set(pair) == {"1", "2"} and has_positive_value(first) and has_positive_value(second) and str(first).strip() != str(second).strip():
                package_bases.add(base)

    normalized_rows = []
    for original in rows:
        row = dict(original)
        packages = {}
        raw_packages = row.get("选装包列表")
        if isinstance(raw_packages, dict):
            packages.update(raw_packages)
        elif has_positive_value(raw_packages):
            try:
                parsed = json.loads(raw_packages)
                if isinstance(parsed, dict):
                    packages.update(parsed)
            except (TypeError, ValueError):
                pass
        for base in package_bases:
            description = row.pop(f"{base}_1", "")
            status = row.pop(f"{base}_2", "")
            if has_positive_value(description) or has_positive_value(status):
                packages[base] = {"描述": description, "状态": status}
        if packages:
            row["选装包列表"] = json.dumps(packages, ensure_ascii=False, sort_keys=True)
        normalized_rows.append(row)
    return normalized_rows


def norm_rows(rows, source):
    out = []
    for row in normalize_option_package_fields(rows):
        normalized = {"数据来源": source}
        for key in ["品牌", "车系", "车系ID", "车型名称", "年款"]:
            if key in row:
                normalized[key] = row[key]
        backfill_year_from_model_name(normalized)

        # 易车原始 `价格` 是车型官方指导价；通用表头映射仍将其保留为经销商参考价。
        if source == "易车":
            official_price = valid_official_price(row.get("官方指导价"))
            if not official_price:
                official_price = valid_official_price(row.get("价格"))
            if official_price:
                normalized["官方指导价"] = official_price

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
                if val not in ("", "-"):
                    normalized[unified] = _merge_distinct_values(normalized[unified], val)
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


def merge_source_rows(source_rows):
    """合并同一车型的多个数据源，标识字段优先取非空，配置字段冲突用来源前缀保留。"""
    merged = {}
    all_keys = set()
    for _, row in source_rows:
        all_keys.update(row.keys())

    for key in all_keys:
        values = []
        for source_name, row in source_rows:
            raw_val = str(row.get(key, "") or "")
            if key == "年款":
                candidate = dict(row)
                backfill_year_from_model_name(candidate)
                raw_val = str(candidate.get(key, "") or "")
            norm_val = canonical_value(raw_val)
            if norm_val != "-":
                values.append((source_name, raw_val, norm_val))
        if key in IDENTITY_FIELDS:
            merged[key] = max((raw for _, raw, _ in values), key=len, default="-")
        elif not values:
            merged[key] = "-"
        elif len({norm_val for _, _, norm_val in values}) == 1:
            merged[key] = values[0][2]
        else:
            if key in _DATE_FIELDS:
                date_folded = True
                for _di in range(len(values)):
                    for _dj in range(_di + 1, len(values)):
                        if not _date_conflict_foldable(values[_di][1], values[_dj][1]):
                            date_folded = False
                            break
                    if not date_folded:
                        break
                if date_folded:
                    merged[key] = max((raw for _, raw, _ in values), key=len)
                    continue
            compare_keys = {canonical_compare(raw_val, key) for _, raw_val, _ in values}
            if len(compare_keys) == 1:
                merged[key] = max((raw for _, raw, _ in values), key=len)
            else:
                merged[key] = "|".join(f"{source_name}:{raw_val}" for source_name, raw_val, _ in values)

    return merged


def merge_single_row(ah_row, dcd_row):
    """合并单个车型的两个数据源，标识字段优先取非空，配置字段冲突用|分隔"""
    return merge_source_rows([("汽车之家", ah_row), ("懂车帝", dcd_row)])


def merge_rows(autohome_rows, dongchedi_rows, yiche_rows=None):
    """按车型名称合并汽车之家、懂车帝和可选易车数据源，支持多级匹配"""
    MERGE_DISPOSITION_LEDGER.clear()
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
    stats = {'精确': 0, '规范': 0, '车系': 0, '仅汽车之家': 0, '仅懂车帝': 0, '仅易车': 0, '易车补充': 0, '低置信拒绝': 0, '歧义拒绝': 0, '大桶跳过': 0, '大桶候选': 0}

    # 第一级: 精确匹配
    for match_key, ah_rows in sorted(autohome_index.items()):
        dcd_rows = dongchedi_index.get(match_key, [])
        for ah_row, dcd_row in zip(sorted(ah_rows, key=model_sort_key), sorted(dcd_rows, key=model_sort_key)):
            if model_variant_conflict_reason(ah_row, dcd_row):
                continue
            merged_row = merge_single_row(ah_row, dcd_row)
            merged_row["数据来源"] = "汽车之家+懂车帝"
            merged.append(merged_row)
            used_autohome.add(id(ah_row))
            used_dongchedi.add(id(dcd_row))
            stats['精确'] += 1
            _ledger_record(ah_row, "accepted", "exact_name_match", "精确")
            _ledger_record(dcd_row, "accepted", "exact_name_match", "精确")

    # 第二级: 规范化匹配
    for match_key, ah_rows in sorted(autohome_norm.items()):
        dcd_rows = dongchedi_norm.get(match_key, [])
        if not dcd_rows:
            continue
        ah_available = sorted((row for row in ah_rows if id(row) not in used_autohome), key=model_sort_key)
        dcd_available = sorted((row for row in dcd_rows if id(row) not in used_dongchedi), key=model_sort_key)
        for ah_row, dcd_row in zip(ah_available, dcd_available):
            if model_variant_conflict_reason(ah_row, dcd_row):
                continue
            merged_row = merge_single_row(ah_row, dcd_row)
            merged_row["数据来源"] = "汽车之家+懂车帝"
            merged.append(merged_row)
            used_autohome.add(id(ah_row))
            used_dongchedi.add(id(dcd_row))
            stats['规范'] += 1
            _ledger_record(ah_row, "accepted", "normalized_name_match", "规范")
            _ledger_record(dcd_row, "accepted", "normalized_name_match", "规范")

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
                _ledger_record(ah_match, "accepted", "series_feature_match", "车系")
                _ledger_record(dcd_match, "accepted", "series_feature_match", "车系")

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
            _ledger_record(ah_match, "accepted", "series_noyear_feature_match", "车系(无年款)")
            _ledger_record(dcd_match, "accepted", "series_noyear_feature_match", "车系(无年款)")

    yiche_rows = yiche_rows or []
    used_yiche = set()

    # 未匹配的车型
    ambiguous_a_ids = stats.get("_ambiguous_a", set())
    ambiguous_d_ids = stats.get("_ambiguous_d", set())
    for row in autohome_rows:
        if id(row) not in used_autohome:
            merged_row = dict(row)
            merged_row["数据来源"] = "仅汽车之家"
            merged.append(merged_row)
            stats['仅汽车之家'] += 1
            if id(row) in ambiguous_a_ids:
                _ledger_record(row, "rejected", "ambiguous_match_blocked", "车系")
            else:
                _ledger_record(row, "unmatched", "no_cross_source_candidate", "-")
    for row in dongchedi_rows:
        if id(row) not in used_dongchedi:
            merged_row = dict(row)
            merged_row["数据来源"] = "仅懂车帝"
            merged.append(merged_row)
            stats['仅懂车帝'] += 1
            if id(row) in ambiguous_d_ids:
                _ledger_record(row, "rejected", "ambiguous_match_blocked", "车系")
            else:
                _ledger_record(row, "unmatched", "no_cross_source_candidate", "-")
    merged = merge_yiche_rows(merged, yiche_rows, used_yiche, stats)
    for row in yiche_rows:
        if id(row) not in used_yiche:
            merged_row = dict(row)
            merged_row["数据来源"] = "仅易车"
            merged.append(merged_row)
            stats['仅易车'] += 1
            _ledger_record(row, "unmatched", "no_cross_source_candidate", "-")

    ambiguous_a = stats.pop("_ambiguous_a", set())
    ambiguous_d = stats.pop("_ambiguous_d", set())
    stats["歧义拒绝"] = max(len(ambiguous_a), len(ambiguous_d))
    stats["低置信拒绝"] = max(0, min(stats['仅汽车之家'], stats['仅懂车帝']) - stats["歧义拒绝"])
    stats.update(merged_by_series)
    stats["合计"] = len(merged)
    global MERGE_ANALYSIS_STATS
    MERGE_ANALYSIS_STATS = dict(stats)
    print(f"合并统计: 精确{stats['精确']} 规范{stats['规范']} 车系{merged_by_series['车系']} 车系(无年款){merged_by_series['车系(无年款)']} 易车补充{stats['易车补充']} 低置信拒绝{stats['低置信拒绝']} 歧义拒绝{stats['歧义拒绝']} 大桶跳过{stats['大桶跳过']} 大桶候选{stats['大桶候选']} 仅汽车之家{stats['仅汽车之家']} 仅懂车帝{stats['仅懂车帝']} 仅易车{stats['仅易车']} 合计{len(merged)}")
    return merged


YICHE_MODEL_TERMS = (
    "标准续航", "长续航", "超长续航", "高性能", "皇家剧院", "暗夜骑士",
    "四驱", "后驱", "前驱", "纯电", "增程", "插混", "混动", "改款",
    "旗舰", "尊享", "豪华", "智驾", "运动", "行政", "冠军",
    "ultra", "elite", "premium", "performance", "luxury", "sport",
    "pro+", "max+", "pro", "max", "plus", "air", "gt", "rs",
)

YICHE_MODEL_PATTERN = re.compile(
    "|".join(re.escape(term) for term in sorted(YICHE_MODEL_TERMS, key=len, reverse=True)),
    re.IGNORECASE,
)


def tokenize_yiche_model(row):
    text = str(row.get("车型名称", "") or "").lower()
    series = str(row.get("车系", "") or "").lower()
    for fragment in {series, re.sub(r"\s+", "", series)}:
        if fragment:
            text = text.replace(fragment, " ")
    text = re.sub(r"(?:19|20)?\d{2}\s*款", " ", text)
    text = re.sub(r"\d+(?:\.\d+)?\s*(?:km|公里)", " ", text, flags=re.IGNORECASE)
    token_pattern = r"[a-z]+(?:\+)?|\d+(?:\.\d+)?|[\u4e00-\u9fff]+"
    tokens = []
    cursor = 0
    for match in YICHE_MODEL_PATTERN.finditer(text):
        tokens.extend(re.findall(token_pattern, text[cursor:match.start()]))
        tokens.append(match.group(0).lower())
        cursor = match.end()
    tokens.extend(re.findall(token_pattern, text[cursor:]))
    stop = {"款", "版", "型", "汽车", "自动", "手动", "km", "公里"}
    return {token for token in tokens if token and token not in stop}


def _canonical_yiche_year_values(row):
    raw_year = str(row.get("年款", "") or "")
    model_name = str(row.get("车型名称", "") or "")
    years = {int(value) for value in re.findall(r"(?:19|20)\d{2}", raw_year)}
    years.update(int(value) for value in re.findall(r"((?:19|20)\d{2})\s*款", model_name))
    return years


def _base_yiche_match_score(current_row, yiche_row, require_year, _cache=None):
    current_year = row_year(current_row)
    yiche_year = row_year(yiche_row)
    if require_year and (not current_year or not yiche_year):
        return 0.0, ["year_missing"]
    if current_year and yiche_year and current_year != yiche_year:
        return 0.0, ["year_mismatch"]
    if _cache is not None:
        current_tokens = _cache["left"]["tokens"]
        yiche_tokens = _cache["right"]["tokens"]
    else:
        current_tokens = tokenize_yiche_model(current_row)
        yiche_tokens = tokenize_yiche_model(yiche_row)
    union = current_tokens | yiche_tokens
    intersection = current_tokens & yiche_tokens
    token_score = (len(intersection) / len(union)) if union else 0.0
    score = token_score * 0.70
    reasons = ["yiche_token_jaccard=%.2f" % token_score]
    if token_score < 0.35:
        return score, reasons
    if current_year and yiche_year and current_year == yiche_year:
        score += 0.15
        reasons.append("same_year")
    current_level = normalize_match_text(current_row.get("级别"))
    yiche_level = normalize_match_text(yiche_row.get("级别"))
    if current_level and yiche_level and current_level == yiche_level:
        score += 0.07
        reasons.append("same_级别")
    return score, reasons


def _canonical_yiche_energy_atom(value):
    text = normalize_match_text(value)
    if not text:
        return ""
    if "增程" in text:
        return "增程"
    if "插电" in text or "插混" in text or "phev" in text:
        return "插混"
    if "纯电" in text or text == "ev":
        return "纯电"
    if "油混" in text or "油电" in text or "混动" in text or "混合动力" in text:
        return "油混"
    if "汽油" in text:
        return "汽油"
    if "柴油" in text:
        return "柴油"
    return text


def _explicit_yiche_energy_values(value):
    text = normalize_match_text(value)
    values = set()
    if "增程" in text:
        values.add("增程")
    plug_in_hybrid = "插电" in text or "插混" in text or "phev" in text
    if plug_in_hybrid:
        values.add("插混")
    if "纯电" in text or re.search(r"(?:^|[^a-z])ev(?:$|[^a-z])", str(value or "").lower()):
        values.add("纯电")
    if not plug_in_hybrid and ("油混" in text or "油电" in text or "混动" in text or "混合动力" in text):
        values.add("油混")
    if "汽油" in text:
        values.add("汽油")
    if "柴油" in text:
        values.add("柴油")
    return values


def _canonical_yiche_energy_values(value):
    values = set()
    for part in re.split(r"[|｜]", str(value or "")):
        atomic = re.split(r"[:：]", part, maxsplit=1)[-1]
        explicit = _explicit_yiche_energy_values(atomic)
        if explicit:
            values.update(explicit)
        else:
            normalized = _canonical_yiche_energy_atom(atomic)
            if normalized:
                values.add(normalized)
    return values


def _canonical_yiche_row_energy_values(row):
    values = _canonical_yiche_energy_values(row.get("能源类型"))
    values.update(_explicit_yiche_energy_values(row.get("车型名称")))
    return values


def yiche_match_score(current_row, yiche_row, require_year, _cache=None):
    current_years = _canonical_yiche_year_values(current_row)
    yiche_years = _canonical_yiche_year_values(yiche_row)
    if require_year and (not current_years or not yiche_years):
        return 0.0, ["year_missing"]
    if len(current_years) > 1 or len(yiche_years) > 1:
        return 0.0, ["year_ambiguous"]
    if current_years and yiche_years and current_years != yiche_years:
        return 0.0, ["year_mismatch"]
    current_energies = _canonical_yiche_row_energy_values(current_row)
    yiche_energies = _canonical_yiche_row_energy_values(yiche_row)
    if not current_energies or not yiche_energies:
        return 0.0, ["energy_missing"]
    if len(current_energies) > 1 or len(yiche_energies) > 1:
        return 0.0, ["energy_ambiguous"]
    if current_energies and yiche_energies and current_energies != yiche_energies:
        return 0.0, ["energy_mismatch"]
    current_level = normalize_match_text(current_row.get("级别"))
    yiche_level = normalize_match_text(yiche_row.get("级别"))
    if current_level and yiche_level and current_level != yiche_level:
        return 0.0, ["level_mismatch"]
    return _base_yiche_match_score(current_row, yiche_row, require_year, _cache=_cache)


def _preserved_value_parts(value):
    parts = []
    for raw_part in str(value or "").split("|"):
        raw_part = raw_part.strip()
        match = re.match(r"^(汽车之家|懂车帝|易车|汽车之家\+懂车帝):(.*)$", raw_part)
        parts.append((match.group(1), match.group(2)) if match else ("", raw_part))
    return parts


def _merge_existing_with_source(current, current_source, source_name, incoming):
    result = dict(current)
    for key in set(current) | set(incoming):
        if key == "数据来源":
            continue
        existing = str(current.get(key, "") or "")
        added = str(incoming.get(key, "") or "")
        if key in IDENTITY_FIELDS:
            candidates = [value for value in (existing, added) if canonical_value(value) != "-"]
            result[key] = max(candidates, key=len, default="-")
            continue
        if canonical_value(added) == "-":
            if canonical_value(existing) == "-":
                result[key] = "-"
            continue
        if canonical_value(existing) == "-":
            result[key] = added
            continue
        parts = _preserved_value_parts(existing)
        existing_norms = {canonical_compare(value, key) for _, value in parts}
        if canonical_compare(added, key) in existing_norms:
            continue
        if key in _DATE_FIELDS:
            all_values = [value for _, value in parts] + [added]
            date_folded = True
            for _vi in range(len(all_values)):
                for _vj in range(_vi + 1, len(all_values)):
                    if not _date_conflict_foldable(all_values[_vi], all_values[_vj]):
                        date_folded = False
                        break
                if not date_folded:
                    break
            if date_folded:
                result[key] = max(all_values, key=len)
                continue
        if parts and all(label for label, _ in parts):
            result[key] = f"{existing}|{source_name}:{added}"
        else:
            existing_sources = atomic_source_names(current_source)
            if existing_sources:
                preserved = "|".join(f"{existing_source}:{existing}" for existing_source in existing_sources)
            else:
                preserved = f"{current_source or '已有来源'}:{existing}"
            result[key] = f"{preserved}|{source_name}:{added}"
    return result


def _merge_yiche_into_target(merged, target_idx, yiche_row, used_yiche, stats, match_label):
    current = dict(merged[target_idx])
    current_source = current.pop("数据来源", "")
    merged_row = _merge_existing_with_source(current, current_source, "易车", yiche_row)
    sources = atomic_source_names(current_source)
    if "易车" not in sources:
        sources.append("易车")
    merged_row["数据来源"] = "+".join(sources)
    merged_row["易车匹配方式"] = match_label
    merged[target_idx] = merged_row
    used_yiche.add(id(yiche_row))
    stats['易车补充'] += 1
    _ledger_record(yiche_row, "accepted", "yiche_supplement_match", match_label)


YICHE_HARD_REASONS = {"energy_missing", "energy_mismatch", "energy_ambiguous", "level_mismatch", "year_mismatch", "year_ambiguous", "year_missing"}


def merge_yiche_rows(merged, yiche_rows, used_yiche, stats):
    merged_by_key = {}
    used_targets = set()
    for idx, row in enumerate(merged):
        for name in {row.get("车型名称", ""), normalize_for_match(row.get("车型名称", ""))}:
            key = identity_match_key(row, str(name).replace(" ", ""))
            if key:
                merged_by_key.setdefault(key, []).append(idx)

    exact_candidates = {}
    exact_target_to_yiche = {}
    exact_hard_blocked_yiche = set()
    exact_hard_blocked_targets = set()
    for yiche_row in yiche_rows:
        candidates = set()
        for name in {yiche_row.get("车型名称", ""), normalize_for_match(yiche_row.get("车型名称", ""))}:
            key = identity_match_key(yiche_row, str(name).replace(" ", ""))
            candidates.update(merged_by_key.get(key, []))
        compatible = []
        for target_idx in sorted(candidates):
            _, hard_reasons = yiche_match_score(merged[target_idx], yiche_row, True)
            if YICHE_HARD_REASONS.intersection(hard_reasons):
                exact_hard_blocked_yiche.add(id(yiche_row))
                exact_hard_blocked_targets.add(target_idx)
            else:
                compatible.append(target_idx)
        if compatible:
            exact_candidates[id(yiche_row)] = (yiche_row, compatible)

    filtered_exact_candidates = {}
    exact_target_to_yiche = {}
    for yiche_id, (yiche_row, compatible) in exact_candidates.items():
        if yiche_id in exact_hard_blocked_yiche:
            continue
        compatible = [target_idx for target_idx in compatible if target_idx not in exact_hard_blocked_targets]
        if not compatible:
            continue
        filtered_exact_candidates[yiche_id] = (yiche_row, compatible)
        for target_idx in compatible:
            exact_target_to_yiche.setdefault(target_idx, []).append(yiche_row)
    exact_candidates = filtered_exact_candidates

    exact_ambiguous_yiche = set()
    exact_ambiguous_targets = set()
    for yiche_row, compatible in sorted(exact_candidates.values(), key=lambda item: model_sort_key(item[0])):
        if len(compatible) != 1:
            exact_ambiguous_yiche.add(id(yiche_row))
            exact_ambiguous_targets.update(compatible)
            continue
        target_idx = compatible[0]
        claimants = exact_target_to_yiche.get(target_idx, [])
        if len(claimants) != 1:
            exact_ambiguous_targets.add(target_idx)
            exact_ambiguous_yiche.update(id(row) for row in claimants)
            continue
        _merge_yiche_into_target(merged, target_idx, yiche_row, used_yiche, stats, "精确")
        used_targets.add(target_idx)

    exact_ambiguity_count = max(len(exact_ambiguous_yiche), len(exact_ambiguous_targets))
    merged_by_series_year = {}
    merged_index_by_id = {}
    for idx, row in enumerate(merged):
        if idx in used_targets or idx in exact_ambiguous_targets or idx in exact_hard_blocked_targets:
            continue
        key = series_year_key(row)
        if key and len(_canonical_yiche_year_values(row)) == 1:
            merged_by_series_year.setdefault(key, []).append(row)
            merged_index_by_id[id(row)] = idx
    yiche_by_series_year = {}
    for row in yiche_rows:
        if id(row) in used_yiche or id(row) in exact_ambiguous_yiche or id(row) in exact_hard_blocked_yiche:
            continue
        key = series_year_key(row)
        if key and len(_canonical_yiche_year_values(row)) == 1:
            yiche_by_series_year.setdefault(key, []).append(row)

    yiche_match_stats = {}
    for key, current_rows in merged_by_series_year.items():
        candidate_yiche = yiche_by_series_year.get(key, [])
        if not candidate_yiche:
            continue
        for current, yiche_row, score, reasons in pair_rows_by_features(
            current_rows,
            candidate_yiche,
            yiche_match_stats,
            "车系",
            threshold=0.58,
            score_func=yiche_match_score,
            require_degree_one=True,
        ):
            target_idx = merged_index_by_id[id(current)]
            if target_idx in used_targets or id(yiche_row) in used_yiche:
                continue
            label = f"车系年款:{score:.2f};" + ",".join(reasons)
            _merge_yiche_into_target(merged, target_idx, yiche_row, used_yiche, stats, label)
            used_targets.add(target_idx)
    ambiguous_current = yiche_match_stats.get("_ambiguous_a", set())
    ambiguous_yiche = yiche_match_stats.get("_ambiguous_d", set())
    stats["易车歧义拒绝"] = exact_ambiguity_count + max(len(ambiguous_current), len(ambiguous_yiche))
    stats["易车车系匹配"] = sum(1 for row in merged if str(row.get("易车匹配方式", "")).startswith("车系年款:"))
    return merged


def atomic_source_names(value):
    names = []
    for source_name in ("汽车之家", "懂车帝", "易车"):
        if source_name in str(value or ""):
            names.append(source_name)
    return names


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


def partition_publishable_rows(rows):
    kept = []
    stats = {
        "invalid_brand": 0,
        "invalid_model_name": 0,
        "invalid_publish_boundary": 0,
        "invalid_yiche_identity": 0,
        "excluded_yiche_commercial_level": 0,
    }
    for row in rows:
        if is_yiche_row(row):
            level = str(row.get("级别") or "").strip()
            if any(keyword in level for keyword in YICHE_COMMERCIAL_LEVEL_KEYWORDS):
                stats["excluded_yiche_commercial_level"] += 1
                continue
            if not yiche_publish_identity_valid(row):
                stats["invalid_yiche_identity"] += 1
                continue
        if is_autohome_row(row) and not autohome_publish_identity_valid(row):
            stats.setdefault("invalid_autohome_identity", 0)
            stats["invalid_autohome_identity"] += 1
            continue
        brand = str(row.get("品牌") or "").strip()
        model = str(row.get("车型名称") or "").strip()
        if brand in {"", "-"}:
            stats["invalid_brand"] += 1
            continue
        if model in {"", "-"}:
            stats["invalid_model_name"] += 1
            continue
        normalized = dict(row)
        normalized["品牌"] = brand
        normalized["车型名称"] = model
        if not re.fullmatch(r"(?:19|20)\d{2}", str(normalized.get("年款") or "").strip()):
            stats["invalid_publish_boundary"] += 1
            continue
        if not publish_boundary_valid(normalized):
            stats["invalid_publish_boundary"] += 1
            continue
        kept.append(normalized)
    return kept, stats


def main():
    today = os.environ.get("MERGE_DATE") or date.today().strftime("%Y%m%d")

    autohome_file = find_latest("autoHome_*.json")
    dongchedi_file = find_latest("dongchedi_*.json")
    yiche_file = find_latest("yiche_*.json")
    print(f"汽车之家数据: {autohome_file}")
    print(f"懂车帝数据: {dongchedi_file}")
    print(f"易车数据: {yiche_file}")

    autohome_rows = norm_rows(load(autohome_file), "汽车之家")
    dongchedi_rows = norm_rows(load(dongchedi_file), "懂车帝")
    yiche_rows = norm_rows(load(yiche_file), "易车")

    # 归一化 one-hot 属性键（如 "辅助驾驶操作系统 - Toyota Pilot" → "辅助驾驶操作系统": "Toyota Pilot"）
    autohome_rows = normalize_attribute_keys(autohome_rows)
    dongchedi_rows = normalize_attribute_keys(dongchedi_rows)
    yiche_rows = normalize_attribute_keys(yiche_rows)

    if not autohome_rows and not dongchedi_rows:
        print("错误: 没有找到任何数据文件")
        return

    print(f"汽车之家:{len(autohome_rows)} 懂车帝:{len(dongchedi_rows)} 易车:{len(yiche_rows)}")

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
    all_rows = merge_rows(autohome_rows, dongchedi_rows, yiche_rows)
    all_rows = enrich_zero_ratio(all_rows, load_zero_ratio_rows())
    all_rows, publish_stats = partition_publishable_rows(all_rows)
    print(
        f"发布身份门禁: valid={len(all_rows)} invalid_brand={publish_stats['invalid_brand']} "
        f"invalid_model_name={publish_stats['invalid_model_name']} "
        f"invalid_publish_boundary={publish_stats['invalid_publish_boundary']} "
        f"invalid_autohome_identity={publish_stats.get('invalid_autohome_identity', 0)} "
        f"invalid_yiche_identity={publish_stats['invalid_yiche_identity']} "
        f"excluded_yiche_commercial_level={publish_stats['excluded_yiche_commercial_level']}"
    )
    # 按 identity_key 去重，避免 preserve_publish_baseline.py 报 duplicate identities
    seen_keys = set()
    deduped_rows = []
    dup_count = 0
    for row in all_rows:
        try:
            key = identity_key(row)
        except ValueError:
            deduped_rows.append(row)
            continue
        if key in seen_keys:
            dup_count += 1
            continue
        seen_keys.add(key)
        deduped_rows.append(row)
    if dup_count:
        print(f"identity_key 去重: 移除 {dup_count} 条重复身份行 ({len(all_rows)} -> {len(deduped_rows)})")
    all_rows = deduped_rows
    before_year_filter = len(all_rows)
    all_rows = [row for row in all_rows if keep_pages_year(row)]
    print(f"2022年及以后车型: {len(all_rows)}/{before_year_filter}")

    filtered_rows = [row for row in all_rows if filter_car(row)]
    print(f"过滤后符合条件的车型: {len(filtered_rows)} 辆")
    analysis_dir = os.path.join(DIR, "docs", "analysis")
    os.makedirs(analysis_dir, exist_ok=True)
    write_json(os.path.join(analysis_dir, f"merge_stats_{today}.json"), {"date": today, "stats": MERGE_ANALYSIS_STATS})
    write_json(os.path.join(analysis_dir, f"disposition_ledger_{today}.json"), {"date": today, "ledger": MERGE_DISPOSITION_LEDGER})
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

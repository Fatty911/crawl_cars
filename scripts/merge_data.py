"""合并汽车之家、懂车帝、易车和零整比数据，统一表头，对比差异，并过滤符合条件的车型。"""






from typing import Any






import csv






import glob






import json






import os






import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import re






from pathlib import Path






import functools






from datetime import date













try:






    from publish_identity import (






        autohome_publish_identity_valid,
        publish_year,






        has_valid_listing_time,






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
        publish_year,






        has_valid_listing_time,






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




















# 级别范围判断原先只对易车行生效，这里对全部数据源统一执行。






# MPV 与房车按 config/CRAWL_SCOPE.md 排除（2026-09-28 负责人裁决「不要 MPV」）。






CRAWL_SCOPE_EXCLUDED_LEVEL_KEYWORDS = YICHE_COMMERCIAL_LEVEL_KEYWORDS + ("MPV", "房车")




















def excluded_by_crawl_scope(row):






    """按 config/CRAWL_SCOPE.md 判定该行是否属于不发布的商用车级别。













    对全部数据源生效：该判断原先只作用于易车行。级别缺失时不排除，






    避免把没写级别的行一并删掉。






    """






    level = str(row.get("级别") or "").strip()






    if level in {"", "-"}:






        return False






    upper = level.upper()






    return any(keyword.upper() in upper for keyword in CRAWL_SCOPE_EXCLUDED_LEVEL_KEYWORDS)


































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






    "CLTC纯电续航里程_km_": "纯电续航(CLTC)",






    "NEDC纯电续航里程_km_": "纯电续航(NEDC)",






    "CLTC纯电续航": "纯电续航(CLTC)",






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






    # 易车参配表自身列名 -> 筛选条件使用的规范列名






    "感应雨刷功能": "雨量感应式雨刷",






    "远程控制功能": "远程控制",













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
    # 票面 ①-B（10-18 hy4，非阻断，本轮采纳）：汽车之家的配置表是三态图例
    # `●标配 / ○选配 / -无此配置`，而这四张符号里 `●` 早就映射到 `支持`（上面），
    # `无/不支持/—/--` 也都映射到 `-`（下面），**只有 `○` 漏了**。漏了不是"保守"，
    # 是让同一张图例里三种写法有两种被认、一种不被认 ⇒ `○` 与 `选配` 算两个候选 ⇒ 该补的一格留空。
    # 方向上只会"多认一个既有符号"，不引入任何新写法。
    "○": "选装",






    "无": "-",






    "不支持": "-",






    "—": "-",






    "--": "-",






}













MERGE_ANALYSIS_STATS = {}






MERGE_DISPOSITION_LEDGER = []




















from dealer_price_overlay import overlay_dealer_prices







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






    # A 类归一：只折比较键，不改存储值——悬架/悬挂 同词异写，万元/万 同单位异写
    text = text.replace("悬挂", "悬架")
    text = re.sub(r"万元$", "万", text)
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












    "纯电续航(CLTC)",





    "纯电续航(NEDC)")




















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













    if use_cache:
        dcd_token_index = {}
        for di, entry in enumerate(dcd_cache):
            for tok in entry["tokens"]:
                dcd_token_index.setdefault(tok, set()).add(di)
        for ai, ah_row in enumerate(ah_unused):
            ah_tokens = ah_cache[ai]["tokens"]
            if ah_tokens:
                cand_di = set()
                for tok in ah_tokens:
                    cand_di.update(dcd_token_index.get(tok, ()))
            else:
                cand_di = range(len(dcd_unused))
            for di in cand_di:
                dcd_row = dcd_unused[di]
                score, reasons = score_func(
                    ah_row, dcd_row, require_year,
                    _cache={"left": ah_cache[ai], "right": dcd_cache[di]},
                )
                if score >= threshold:
                    candidates.append((score, ai, di, reasons))
    else:
        for ai, ah_row in enumerate(ah_unused):
            for di, dcd_row in enumerate(dcd_unused):
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






    folded = _folded_source_buckets(existing)

    _merge_source_buckets(folded, _folded_source_buckets(incoming))

    return _render_source_buckets(folded) or existing




















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
    for candidate in field_name.split("|"):
        numbers = parse_numbers(row.get(candidate, "-"))
        if numbers:
            break
    if not numbers and "纯电续航" in field_name:
        for variant in ("纯电续航(CLTC)", "纯电续航(NEDC)", "纯电续航(km)"):
            if variant == field_name:
                continue
            numbers = parse_numbers(row.get(variant, "-"))
            if numbers:
                break
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




















EQUIPMENT_PRESENCE_MARKERS = {"●", "√", "✓", "标配", "支持", "是", "有"}













def check_feature(row, field_names, value_keywords=None, require_keyword=False):






    value_keywords = value_keywords or []













    for field_name in field_names:






        val = row.get(field_name, "-")






        if not has_positive_value(val):






            continue






        if not require_keyword or any(keyword in str(val) for keyword in value_keywords):






            return True






        # 易车参配表用符号标注该项是否配备，语义在列名上而非值上






        if str(val).strip() in EQUIPMENT_PRESENCE_MARKERS and any(






            keyword in str(field_name) for keyword in value_keywords






        ):






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






        if key_matches and require_keyword and val_text.strip() in EQUIPMENT_PRESENCE_MARKERS:






            if any(keyword in key_text for keyword in value_keywords):






                return True













        if value_matches:






            return True













    return False




















def _publish_row_identity_present(row):
    """通用身份校验：车型名称 + 年款（或车系ID）齐全，车系非 URL 片段。

    只做「这条行有没有身份」的判定，不含各数据源特有的 stricter 规则
    （易车 approved / 汽车之家 车款ID 等发布边界由 prepare 层负责）。
    """
    model = str(row.get("车型名称") or "").strip()
    year = str(row.get("年款") or "").strip()
    if not model or model in ("-", "--") or not re.fullmatch(r"(?:19|20)\d{2}", year):
        return False
    series_id = str(row.get("车系ID") or "").strip()
    if series_id:
        return True
    brand = str(row.get("品牌") or "").strip()
    series = str(row.get("车系") or "").strip()
    if not brand or not series:
        return False
    return not re.fullmatch(r"[a-z][a-z0-9-]*-\d+", series)


IDENTITY_ONLY_FIELDS = {
    "数据来源", "品牌", "车系", "车系ID", "车型名称", "年款",
    "车款ID", "易车车型ID", "易车上市状态",
}


def _has_substantive_evidence(row):
    """行内至少有一个非身份字段持有真实值（不是空/占位符）。"""
    for key, value in row.items():
        if key in IDENTITY_ONLY_FIELDS:
            continue
        text = str(value if value is not None else "").strip()
        if text and text not in ("-", "--", "None", "null", "nan"):
            return True
    return False


def filter_car(row):
    """发布行门禁：身份合法 + 至少一项实质证据；不再按前端默认筛选丢行。

    config/filter_conditions.json 的 conditions（zero_to_hundred / ev_range /
    top_speed 及 feature/pagesFeature）是**前端界面的默认勾选值**，不是数据合格判据。
    把它们当硬过滤会在合并阶段删数据源：纯油车的 纯电续航(km) 被 annotate_ev_range
    规范化为 0 后过不了 ev_range ≥150，缺 百公里加速/最高车速 的易车行同理被砍，
    现网后果是 filtered 里燃油车 0 台、易车保留率 1.7%。

    仍然会丢的行：身份不合法（缺车型名称/年款，或车系是 URL 片段），
    以及整行只有身份字段、没有任何实质证据的占位行。
    拦截率诊断继续由 first_blocked_condition 按 FILTER_CONDITIONS 原样统计。
    """
    if not isinstance(row, dict):
        return False
    try:
        if not _publish_row_identity_present(row):
            return False
    except Exception as exc:
        print(f"过滤检查异常: {exc}, row: {row.get('车型名称', 'unknown')}")
        return False
    return _has_substantive_evidence(row)





















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




















_UNIT_HEADER_TRANS = str.maketrans({"（": "(", "）": ")", "—": "-", "–": "-"})
_UNIT_HEADER_PATTERN = re.compile(
    r"\[(" + "|".join(re.escape(unit) for unit in sorted(SCHEMA_UNIT_TOKENS, key=len, reverse=True)) + r")\]$"
)
_UNDERSCORE_UNITS_SORTED = sorted(
    SCHEMA_UNDERSCORE_UNITS.items(), key=lambda item: len(item[0]), reverse=True
)

@functools.lru_cache(maxsize=65536)
def normalize_schema_unit_header(header):
    """Normalize punctuation-only unit spellings without changing the measured metric."""
    normalized = str(header).strip().translate(_UNIT_HEADER_TRANS)
    normalized = _UNIT_HEADER_PATTERN.sub(r"(\1)", normalized)
    for encoded, display in _UNDERSCORE_UNITS_SORTED:
        suffix = f"_{encoded}_"
        if normalized.endswith(suffix):
            normalized = f"{normalized[:-len(suffix)]}({display})"
            break
    return normalized














_V4_HEADER_PATTERN = re.compile(r"^(.+)_v4_(.+)$")

@functools.lru_cache(maxsize=65536)
def norm(header):
    header = str(header).strip()
    header = HEADER_MAP.get(header, header)
    header = normalize_schema_unit_header(header)
    header = HEADER_MAP.get(header, header)
    m_v4 = _V4_HEADER_PATTERN.match(header)
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




















_OPTION_PAIR_PATTERN = re.compile(r"^(.+)_(\d+)$")

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






            match = _OPTION_PAIR_PATTERN.match(key)
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




















def _folded_source_buckets(value, default_sources=()):
    """把值折成 {源: [字面段]}：无前缀尾段归前面最近源，整值无前缀时归 default_sources。"""
    buckets = {}
    previous = ""
    for label, text in _preserved_value_parts(value):
        text = str(text).strip()
        if not text:
            continue
        if label:
            previous = label
            while text.startswith(f"{label}:"):
                text = text[len(label) + 1:].strip()
            if not text:
                continue
            sources = [label]
        elif previous:
            sources = [previous]
        elif default_sources:
            sources = list(default_sources)
        else:
            sources = [""]
        for source in sources:
            tokens = buckets.setdefault(source, [])
            if text not in tokens:
                tokens.append(text)
    return buckets


def _merge_source_buckets(base, extra):
    """同源按字面去重；裸段已被任一源记录时不再重复，不跨源折叠。"""
    known = {token for tokens in base.values() for token in tokens}
    for source, tokens in extra.items():
        target = base.setdefault(source, [])
        for token in tokens:
            if token in target or (not source and token in known):
                continue
            target.append(token)
            known.add(token)
    return base


def _render_source_buckets(buckets):
    """按「源:段|段|源2:段」写回，无源段原样平铺。"""
    parts = []
    for source, tokens in buckets.items():
        tokens = [str(token).strip() for token in tokens if str(token).strip()]
        if not tokens:
            continue
        if source:
            parts.append(f"{source}:{'|'.join(tokens)}")
        else:
            parts.extend(tokens)
    return "|".join(parts)



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






        default_sources = atomic_source_names(current_source) or [current_source or "已有来源"]

        source_buckets = _folded_source_buckets(existing, default_sources)

        _merge_source_buckets(source_buckets, _folded_source_buckets(added, [source_name] if source_name else []))

        result[key] = _render_source_buckets(source_buckets)






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




















SOURCE_COVERAGE_SOURCES = ("懂车帝", "汽车之家", "易车")




















def first_blocked_condition(row):






    """该行在筛选条件里第一个未通过的条件 id；全部通过返回 None。"""






    for condition in FILTER_CONDITIONS:






        if condition.get("type") == "range":






            field_name = condition.get("field")






            min_value = condition.get("min")






            max_value = condition.get("max")






            if min_value is not None and not check_numeric_condition(row, field_name, float(min_value), ">="):






                return condition.get("id")






            if max_value is not None and not check_numeric_condition(row, field_name, float(max_value), "<="):






                return condition.get("id")






        elif condition.get("type") in ("feature", "pagesFeature"):






            if not check_feature(row, condition.get("fields", []), condition.get("keywords", []), condition.get("requireKeyword", False)):






                return condition.get("id")






    return None




















def build_source_coverage_report(rows, filtered_rows):






    """按源统计筛选存活率与首要拦截条件，让单源覆盖倒退在发布前就可见。













    某源输入占比与入选占比明显背离，说明该源的数据形态不再满足条件，






    而不是该源真的没有车——这正是易车覆盖长期偏低却无人发现的原因。






    """






    report = {}






    for source in SOURCE_COVERAGE_SOURCES:






        matched = [row for row in rows if source in str(row.get("数据来源", "") or "")]






        kept = [row for row in filtered_rows if source in str(row.get("数据来源", "") or "")]






        blocked = {}






        for row in matched:






            key = first_blocked_condition(row) or "PASS"






            blocked[key] = blocked.get(key, 0) + 1






        share_before = round(len(matched) / len(rows), 4) if rows else 0.0






        share_after = round(len(kept) / len(filtered_rows), 4) if filtered_rows else 0.0






        report[source] = {






            "rows": len(matched),






            "kept": len(kept),






            "share_before": share_before,






            "share_after": share_after,






            "first_blocked_by_condition": dict(sorted(blocked.items(), key=lambda kv: -kv[1])),






        }






    return report




















def report_source_coverage(analysis_dir, today, rows, filtered_rows):






    report = build_source_coverage_report(rows, filtered_rows)






    write_json(os.path.join(analysis_dir, f"source_coverage_{today}.json"), {"date": today, "sources": report})






    for source, item in report.items():






        print(






            f"覆盖率 {source}: 入选 {item['kept']}/{item['rows']} 行"






            f"｜占榜单 {item['share_after'] * 100:.1f}%（输入占 {item['share_before'] * 100:.1f}%）"






        )






        if item["share_before"] and item["share_after"] < item["share_before"] * 0.5:






            blockers = item["first_blocked_by_condition"]






            lead = next(iter(blockers), "-")






            print(f"⚠️ {source} 入选占比相比输入占比腰斩，首要拦截条件: {lead}={blockers.get(lead, 0)} 行")






    return report




















# 发布面的身份列。**必须与 publish_identity 里各门禁真正读的字段同源**：
# `yiche_publish_identity_valid` 要求 `易车上市状态 == "approved"`，而 `narrow_pages_rows`
# 只保留本列出的列 ⇒ 以前这里少了该列，门禁永远读到空串，
# **每一轮都把整源（实测 5069 行含易车标签）从 filtered 面删掉且没有任何计数**。
PAGES_IDENTITY_COLUMNS = ("品牌", "车系", "车型名称", "年款", "车系ID", "数据来源", "车款ID",
                          "易车上市状态")


def resolve_pages_columns(rows):
    declared = [str(col) for col in (FILTER_CONFIG.get("defaultVisibleColumns") or [])]
    allowed, seen = [], set()
    for col in declared + list(PAGES_IDENTITY_COLUMNS):
        if col and col not in seen:
            seen.add(col)
            allowed.append(col)
    present = set()
    for row in rows or []:
        if isinstance(row, dict):
            present.update(str(key) for key in row.keys())
    return [col for col in allowed if col in present] or allowed[:1]


def narrow_pages_rows(rows):
    keep = set(resolve_pages_columns(rows))
    return [{key: row.get(key) for key in row if key in keep} for row in rows]


def collect_fields(rows):
    fields = []
    seen = set(fields)
    for field in ZERO_RATIO_FIELDS:
        if any(row.get(field) for row in rows) and field not in seen:
            fields.append(field)
            seen.add(field)
    for row in rows:
        for key in row:
            if key not in FIXED and key not in seen:
                fields.append(key)
                seen.add(key)
    return FIXED + fields














def write_csv(path, rows, fieldnames):






    with open(path, "w", encoding="utf-8-sig", newline="") as f:






        writer = csv.DictWriter(f, fieldnames=fieldnames)






        writer.writeheader()






        for row in rows:






            writer.writerow({key: row.get(key, "-") for key in fieldnames})




















def write_json(path, rows):






    # 纯写入器：调用方给什么就写什么。身份级去重是 preserve/merge 的职责






    # （unique_keys / merge_main 的 identity 去重）；在这里再做一遍模糊 SKU 去重






    # 会把「车系ID 不同、其余字段恰好同形」的两条身份静默合并并拼接数据来源，






    # 造成 stats 与落盘行数不一致（tests/test_debug_publish_safety.py 契约组）。






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






        if excluded_by_crawl_scope(row):






            stats["excluded_by_crawl_scope"] = stats.get("excluded_by_crawl_scope", 0) + 1






            if is_yiche_row(row):






                stats["excluded_yiche_commercial_level"] += 1






            continue






        if is_yiche_row(row) and not yiche_publish_identity_valid(row):






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






        # 年款为空时**允许从车型名回退**：各源并不都填年款
        # （懂车帝/易车常留空，年份写在车型名如「A 2026款 Pro」里）。
        # publish_identity.publish_year() 正是为此存在。
        # 原先这里只看 normalized["年款"] 原始值，于是「年款空但车型名含年份」
        # 的正常行被整行判为 invalid_publish_boundary，候选被清空，
        # superset 校验只会报一句误导的「must both be non-empty」。
        #
        # **只在原年款为空时回退**，绝不能覆盖已有值：
        # 上面那个 `noncanonical_year` 用例（年款="2025|25"，车型名含"1966"）
        # 就是反例——无条件回退会从车型名取出 1966，把一条**非法年份**的行
        # 放行，直接削弱发布边界护栏。原值非空就按原值判，非法即拒。
        if not str(normalized.get("年款") or "").strip():
            normalized["年款"] = publish_year(row)

        if not re.fullmatch(r"(?:19|20)\d{2}", str(normalized.get("年款") or "").strip()):






            stats["invalid_publish_boundary"] += 1






            continue






        if not publish_boundary_valid(normalized):






            # 仅豁免「显式暂无报价 + 上市时间有效」：这是在售但尚未挂牌价的真车，






            # 丢弃会让它从发布数据中消失；空价格/空上市时间属于数据质量问题，






            # 照旧丢弃（tests/test_merge_matching.py 的 rejects 契约）。






            # 其余边界违规（车系缺失/slug 等）也仍然致命。






            probe = dict(normalized)






            probe["官方指导价"] = "20.00万"






            probe["上市时间"] = "2026-01"






            price_pending = any(






                str(normalized.get(field) or "").strip() == "暂无报价"






                for field in ("官方指导价", "价格")






            )






            if (






                publish_boundary_valid(probe)






                and price_pending






                and has_valid_listing_time(normalized)






            ):






                stats["incomplete_publish_boundary"] = stats.get("incomplete_publish_boundary", 0) + 1






            else:






                stats["invalid_publish_boundary"] += 1






                continue






        kept.append(normalized)






    return kept, stats






























def _price_token_norm(part):
    """单个价格写法归一：'130.0' / '130.00' / '130' 都收敛到 '130'；非纯数值原样返回。"""
    text = str(part or '').strip()
    if not re.fullmatch(r"\d+(?:\.\d+)?", text):
        return text
    if '.' in text:
        text = text.rstrip('0').rstrip('.')
    return text or '0'


def _price_norm(value):
    """'19.99万' -> '19.99'; '130.0万|130.00万' -> '130'; '' -> ''"""
    text = str(value or '').replace('万', '').strip()
    if not text:
        return ''
    tokens = []
    for part in text.split('|'):
        token = _price_token_norm(part)
        if token and token not in tokens:
            tokens.append(token)
    if not tokens:
        return ''
    if len(tokens) == 1:
        # 同一 SKU 的两源写法（'130.0|130.00'）归一到同一标量，去重键不再分叉；
        # 真正不同的价格（'20|21'）仍保留多值，不折叠真冲突。
        return tokens[0]
    return '|'.join(sorted(tokens))



_SOURCE_LABEL_ORDER = ("汽车之家", "懂车帝", "易车")


def _source_label_atoms(label):
    """'汽车之家+懂车帝(车系级)、懂车帝+汽车之家' -> ['汽车之家', '懂车帝']"""
    atoms = []
    for part in re.split(r"[、+,＋]", str(label or "")):
        part = re.sub(r"[(（][^)）]*[)）]", "", part).strip()
        part = part[1:].strip() if part.startswith("仅") else part
        if not part:
            continue
        for name in _SOURCE_LABEL_ORDER:
            if name in part and name not in atoms:
                atoms.append(name)
                break
    return [name for name in _SOURCE_LABEL_ORDER if name in atoms]


def _dedupe_source_labels(row):
    """同一来源集合只留一个规范标签：原子去重 + 固定顺序；单原子回到 '仅X' 写法。"""
    label = str(row.get("数据来源", "") or "")
    if not label:
        return row
    atoms = _source_label_atoms(label)
    if not atoms:
        row["数据来源"] = label
    elif len(atoms) == 1:
        row["数据来源"] = "仅" + atoms[0]
    else:
        row["数据来源"] = "+".join(atoms)
    return row

_ARABIC_TO_CN = str.maketrans("0123456789", "\u3007\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d")
# 年款标记及其之前的整段前缀（车系名+年款都在里面）一次性丢掉。
# 必须整段丢而不是只丢"年款"两个字：同 SKU 的异名写法差别就在这段前缀上——
#   "乐道L90 2026款 Pro 六座版" vs "六座版Pro"（懂车帝侧根本没有前缀）
#   "腾势N9 2026款 闪充 尊荣型" vs "腾势N9 DM 2026款 闪充 尊荣型"（同 ID 两个车系名）
# 只认四位年份（19xx/20xx）或"两位数字+款"：normalize_match_text 会把小数点当标点删掉，
# "1.5T" 会变成 "15T"，若允许裸两位数字就会把排量当年款吃掉（线上实测踩过）。
_YEAR_PREFIX_RE = re.compile(r"^.*?(?:(?:19|20)\d{2}\u6b3e?|\d{2}\u6b3e)")
# "规格细节"词：驱动方式与电池容量单位。名字里带不带它们不构成 SKU 差异
# （另有 驱动方式 / 电池容量 列承载），但会让同一 SKU 的两种写法 token 对不上。
_SPEC_DETAIL_TOKENS = frozenset({
    "\u540e\u9a71", "\u524d\u9a71", "\u56db\u9a71", "\u4e24\u9a71",      # 后驱/前驱/四驱/两驱
    "\u540e\u7f6e\u540e\u9a71", "\u524d\u7f6e\u56db\u9a71",               # 后置后驱/前置四驱
    "\u53cc\u7535\u673a\u56db\u9a71", "\u53cc\u7535\u673a",                  # 双电机四驱/双电机
    "kwh",
})


def _sku_core_tokens(name, series):
    """SKU 核心 token **集合**：词序不敏感、阿拉伯/中文数字不敏感、前缀不敏感。

    线上实测（2026-10-15 发布面）旧实现是字符串 core，三种脆弱性各自造成同 SKU 多行：
      词序    "六座版Pro" → "六座版pro"  vs  "…Pro 六座版" → "pro六座版"
      数字    "1.5T Halo 六座" → "thalo六座"  vs  "…1.5T Halo 6座" → "thalo 座"（6 被当裸数字剥掉）
      前缀    "腾势N9 2026款…" → "闪充尊荣型"  vs  "腾势N9 DM 2026款…" → "dm闪充尊荣型"
    改为 frozenset + 6→六  transliterate + 年款前缀整段丢之后，三对都落到同一集合。
    genuinely 不同的配置仍然分开（token 集合不同）：
      "…荣耀型 机甲套装" → {荣耀型, 机甲套装}
      "…荣耀型 锦衣套装 逐日版" → {荣耀型, 锦衣套装, 逐日版}
    """
    text = normalize_match_text(name)
    if series:
        s = normalize_match_text(series)
        if s:
            text = text.replace(s, " ")
    m = _YEAR_PREFIX_RE.match(text)
    if m:
        text = text[m.end():]
    # 阿拉伯数字翻成中文再比：6座 == 六座；一.五 != 二.〇（排量差异保留为 token 差异）
    text = text.translate(_ARABIC_TO_CN)
    # 按 CJK / 拉丁边界切词，词序进集合后自然无害：
    #   "六座版Pro" -> {六座版, pro}；"…Pro 六座版" -> {pro, 六座版} ⇒ 同集合
    # CJK 连续段再按"版/型"切成子词并去掉尾缀，段内词序也无关：
    #   "六座版 马到成功版Max" -> {六座, 马到成功, max}
    #   "2026款 Max 马到成功版 六座" -> {max, 马到成功, 六座}   ⇒ 同集合
    tokens = set()
    for piece in re.findall(r"[a-z]+|[\u4e00-\u9fff]+", text, flags=re.I):
        if piece.isascii():
            tokens.add(piece.lower())
            continue
        for sub in re.split(r"(?<=\u7248)|(?<=\u578b)", piece):
            sub = sub.strip("\u7248\u578b")
            if sub:
                tokens.add(sub)
    # 丢掉"规格细节"词：这些属性另有列承载，写在名字里只会让同一 SKU 的两种写法对不上。
    #   驱动方式 后驱/前驱/四驱/两驱 —— 实测阿维塔07：懂车帝写
    #     "Elite 后驱增程版 39.05kWh"、汽车之家写"阿维塔07 2026款 Elite 增程版"，
    #     同车款ID 同价却因这两个词没并上。
    #   电池容量 39.05kWh / 52.01kWh —— 同 SKU 的不同批次命名带/不带容量后缀。
    # 真正的配置差异不靠这些词区分：异车款ID 由键里的 ID 分开，异价由键里的价格分开，
    # 机甲套装 vs 锦衣套装 这类词也不在被丢的集合里。
    tokens = {t for t in tokens if t not in _SPEC_DETAIL_TOKENS}
    return frozenset(tokens)


def _series_norm_key(series: str) -> str:
    """车系名的分组键：只去掉空白差异（"阿维塔 07" 与 "阿维塔07" 同键）。

    实测同一车系在数据里有两种写法，UI 因此把它拆成两组（阿维塔07 一份 11 行、
    阿维塔 07 一份 25 行）。键里用归一化写法，输出时再由 _canonical_series 统一成
    出现次数更多的那种写法。
    """
    return re.sub(r"\s+", "", str(series or "")).strip().lower()


_VERSION_WORDS_RE = re.compile(
    r"大满配|超满配|满配|豪华|尊贵|尊享|智享|行政|精英|舒适|运动|旗舰|标准|尊荣|尊越"
    r"|极夜黑|纪念版|典藏|臻选|致雅|领先|燃擎|致臻|智尊"
)


def _version_words(name):
    """名字里的"版本/外观词"集合：无车款ID 的两行要判成同一款，这些词必须完全一致。
    实测必须留下的反例：沃尔沃XC60 PHEV `T8 四驱长续航智远豪华版` 与
    `T8 四驱长续航智远极夜黑版` 同价 52.39、同续航 90、同加速 5，但版本词不同 ⇒ 两款车。"""
    return frozenset(_VERSION_WORDS_RE.findall(normalize_match_text(name)))


# 停售/停产是**状态**（常写在名字的括号里），以及"人眼会拿来分开两款"的配置 token 集。
# 配置 token 表刻意不含 tier 那类纯写法词（Ultra/Max/Pro/UItra），否则源侧拼写噪声又会拆行。
_STOP_MARK_RE = re.compile(r"停产|停售|已停产|退市")
_EDITION_ROOTS = (r"限量版|限定版|限定|特别版|特别款|纪念款|纪念版|纪念|典藏|臻选|冠军版|高光|联名"
                  r"|纽北|周年|签名版|黑武士|黑标|铂金版|星空版|共创|创始人|首发|暗黑|执迷|弧光|酷不列颠")
# 词根 + **前缀**（专名或编号）才是身份：`青峰` 限定 ≠ `科林斯古铜` 限定；`10周年` ≠ `20周年`。
# 前缀**不交给定长正则**去截：旧写法 `([0-9…一-龥]{0,5}[A-Za-z]{0,4}|[一-龥]{0,6})(词根)`
# 会把 `300万辆纪念版` 的数字丢掉（数词分支吃不下 `辆`，只能回落到中文分支的 `万辆`），
# 于是 `300万辆` 与 `500万辆` 得到同一个身份 ⇒ 两款折一条（评审 GLM 族 F2，生产代码复现）。
# 现在只匹配**词根**，前缀由 `_edition_identities()` 从词根位置往前**整段**取。
_EDITION_ROOT_RE = re.compile("(%s)" % _EDITION_ROOTS)
# 词根的**形态**不该参与比对：`青峰限定` 与 `青峰限定版` 是同一款的两种写法（hy4 票 ②.5，
# 基线出口=1、我上一版=2 ⇒ 是我引入的倒退）。按"去掉尾部的版/款"归一成同一个键。
_EDITION_ROOT_CANON = re.compile(r"(?:版|款)$")


def _edition_root_key(root):
    return _EDITION_ROOT_CANON.sub("", root) or root


# 以 `型` 结尾的版本名是一条**独立冲突轴**（hy4 票 ①P1/P2/P3，三条都是我这包引入的误合）：
# 词表 `_VERSION_WORDS_RE` 只有 21 个词，表外版本名（`时尚型`/`进取型`/`动感型`/`科技型`/`探索型`）
# 落在词表盲区里 ⇒ 同 ID 同价就折成一条。这里不看词表：**两侧都写了《X型》且没有一个相同 ⇒ 两款**。
# 一侧没写不算差异（`45 TFSI quattro 时尚型上市特别版` vs `2024款 …上市特别版` 必须仍折＝现网 63975）。
# 版本名**不再取定长窗口**（第一版取"紧邻 `型` 的两字 + 型"＝末三字窗口，被 hy4 第一票与
# 我自己各自独立指出同一形状：`尊享豪华型` 与 `舒享豪华型` 都归约成 `豪华型` ⇒ 判不出冲突；
# 与 H5"二字窗口把 极光蓝/星光蓝 截成 光蓝"是同一个错误类别）。
# 现在取"整段减去**有主噪声**后的剩余段"：驱动/座位/轴距/代数/能源词各有自己的轴在管，
# 不许混进版本名比对（现网 77498 三行 `能源类型` 都是 `油电混合`，差 `混动` 二字是书写差 ⇒ 必须仍折）。
# `两驱豪华型` 与 `前驱豪华型` 仍给同一个 token（测试 r4），`时尚型` 与 `进取型` 仍不同（票 P1）。
_XING_RUN_RE = re.compile(r"[\u4e00-\u9fff]+型")
_XING_STOP = frozenset({"车型", "原型", "类型", "造型", "箱型", "塔型", "桥型",
                        "血型", "机型", "岩型", "型号", "水型", "风型"})


_XING_OWNED_RE = re.compile(
    r"(?:第[一二三四五六七八九十\d]+代|混动|双擎|插混|插电式混合|插电式|插电|纯电|燃油|轻混|"
    r"增程式|增程|两驱|四驱|全驱|前驱|后驱|电驱|双电机|三电机|单电机|长轴距|长轴|标轴距|标轴|标准|"
    r"[一二三四五六七八九十\d]+座)")
_XING_LEAD_NOISE_RE = re.compile(r"^(?:款|年|型)+")


def _xing_strip_owned(text):
    orig = str(text or "")
    prev = None
    while prev != text:
        prev = text
        text = _XING_OWNED_RE.sub("", text)
    out = _XING_LEAD_NOISE_RE.sub("", text)
    # 剥到空 ⇒ 回退返回原段（票面 ③-1，10-19 在真代码上复现为**误合**）：
    # `标准型` 整段落在"有主噪声"表里（本意是 `标准轴距`），剥完剩 `型`、再被前缀噪声剥成空
    # ⇒ 调用处 `not tok.endswith("型")` 把这一侧整条丢弃 ⇒ 《X型》轴退化成"一侧没写就不判"，
    # 于是 `进取型`/`科技型`/`探索型`/`时尚型` 与 `标准型` 被折成一款（构造面实测出口=1，应为 2）。
    # 不采纳"把 `标准` 从表里摘掉"那种词表修法：那只是把这**一个**词让开，下一个整段撞表的
    # 版本名照样穿；这里按**形态**修：谁把整段剥空了，谁就没资格说这一侧"没写过版本名"。
    if not out and orig.strip():
        return orig.strip()
    return out


def _xing_version_names(name, *junk):
    t = re.sub(r"\s+", "", str(name or ""))
    t = _EDITION_YEAR_TOKEN_RE.sub("", t)
    t = _EDITION_CODE_RE.sub("", t)
    # 车系/品牌要按**中文段**剥：`腾势N9 DM` 这类车系，编码已被上面剥掉 ⇒ 整串在名字里找不到，
    # 只剩 `腾势` 粘在版本名前头（实测把 DENZA 夹具打红）。
    for j in junk:
        j = re.sub(r"\s+", "", str(j or ""))
        for piece in [j] + re.findall(r"[一-龥]{2,}", j):
            if len(piece) >= 2:
                t = t.replace(piece, "")
    out = set()
    for run in _XING_RUN_RE.findall(t):
        tok = _xing_strip_owned(run)
        if tok in _XING_STOP or tok == "型" or not tok.endswith("型"):
            continue
        out.add(tok.lower())
    return frozenset(out)


_BAN_RUN_RE = re.compile(r"[\u4e00-\u9fff]+[版款]")
# 这些"以 版/款 收尾"的串不是版本名：要么是本词，要么是年款/形态描述。
_BAN_STOP = frozenset({"版", "款", "正版", "样版", "样板", "样板款", "同款", "改款",
                       "新款", "老款", "爆款", "特别", "限定", "纪念"})


def _ban_version_names(name, *junk):
    """以 `版`/`款` 收尾的**版本名**整段（hy4 第三票 ①M1 / ⑤S1、S2）。

    为什么单开一根轴而不是往 `_VERSION_WORDS_RE` 那张 21 词表里补词：
    表外版本名（`智领版`/`悦享版`/`智远豪华版`/`智逸豪华版`）既不在词表、也不以 `型` 结尾，
    于是"版本词轴 + 《X型》轴"同时落空 ⇒ 同 ID 同价同年款直接折成一条。
    补词只是把盲区往后挪；这里按**形态**收：整段 `汉字+[版款]`，再套与《X型》轴同一套
    有主噪声剥离（驱动/座位/能源/代数）与后缀关系判等。

    必须排除**限量词根已经认下的段**（`青峰限定版`、`25周年纪念版`、`上市特别版`……）：
    那是限量身份轴在管的事，两根轴各判一次就是抢同一件事，会造出新的假冲突（漏合）。
    """
    t = re.sub(r"\s+", "", str(name or ""))
    t = _EDITION_YEAR_TOKEN_RE.sub("", t)
    t = _EDITION_CODE_RE.sub("", t)
    for j in junk:
        j = re.sub(r"\s+", "", str(j or ""))
        for piece in [j] + re.findall(r"[一-龥]{2,}", j):
            if len(piece) >= 2:
                t = t.replace(piece, "")
    out = set()
    for run in _BAN_RUN_RE.findall(t):
        tok = _xing_strip_owned(run)
        if not tok or tok in _BAN_STOP or not re.search(r"[版款]$", tok):
            continue
        if _EDITION_ROOT_RE.search(tok):
            continue          # 这段归限量身份轴，不在这里再判一遍
        out.add(tok.lower())
    return frozenset(out)


def _xing_same_version(sa, sb):
    """两侧《X型》集合是不是"同一副版本名的两种写法"。

    相等、有交集、或**一侧是另一侧的结尾**（`豪华型` ⊂ `尊享豪华型` ＝少写修饰词）⇒ 同款；
    互非后缀且不相交 ⇒ 两副版本名（`尊享豪华型` vs `舒享豪华型` 必须拦住）。
    """
    if sa & sb:
        return True
    for a in sa:
        for b in sb:
            if a.endswith(b) or b.endswith(a):
                return True
    return False


# 名字里"数字 + 单位"的片段各有自己的轴（座位数/续航/线数/轮胎），不属于限量身份
# （hy4 票 ②.1：`7座 青峰限定版` 与 `青峰限定版` 因残留 `座` 被拆成两行）。
# 中文数词也要一起认（hy4 第二票 ②.3：只认阿拉伯数字时 `六座 青峰限定版` 会残留 `六` ⇒ 漏合）：
# marker 轴早已按"整个中文数词"读座位数（`十一座`＝11），这里必须同口径，两轴才不给同一形状相反答案。
_EDITION_UNIT_TOKEN_RE = re.compile(
    r"(?:\d+(?:\.\d+)?|[一二三四五六七八九十百]{1,3})"
    r"(?:座|kwh|km|公里|线|排|门|个|瓦|kw|寸|英寸)", re.IGNORECASE)
# 量词字符类：只用来区分"辆数里程碑"与"年款"（见下面 `_EDITION_YEAR_TOKEN_RE`）。
# `套` 是 10-17 黑箱票 ②.3 补的：`2000套纪念版` 与 `2001套纪念版` 之前都把 20xx 当年款剥掉
# ⇒ 折成一条（真误合），而 `3000套` 因为不是 20xx 反而不剥 ⇒ 规则自身不一致。
# `批` 是同一形状的第二例（hy4 第二票 ②.2：`2000批` vs `2001批`）。
_EDITION_UNIT_CH = "万亿台辆名位届次套批"
# 名字里"整段就是年款"的片段不属于限量身份：`2026`、`2026款`、`26款`（两源常一个写全一个写简）。
# 但后面紧跟量词的 (`2000 万辆`) 是辆数里程碑，不能当成年款剥掉；
# 两位简写**必须带 `款`**才剥，否则 `35TFSI` 里的 `35` 会被误剥。
# `年款` 这一写法也要认（hy4 第二票 ②.4：`2026年款 青峰限定版` 之前剥不干净 ⇒ 漏合）。
_EDITION_YEAR_TOKEN_RE = re.compile((
    r"(?<!\d)(?:(?:19|20)\d{2}年?款|\d{2}年?款)(?![%s])"
    r"|(?<!\d)(?:19|20)\d{2}(?![\d%s款年])"
    # 裸 `2026年`（不带"款"）也是年款写法——hy4 第三票 ②N1：现网 `2026款`/`26款`/`2026 款`
    # 都认，唯独 `2026年` 不认 ⇒ 一侧写 `2026年青峰限定版`、另一侧写 `青峰限定版` 就多拆。
    # 同一套形态里漏一个分支就是"规则自身不一致"，与先前 `套`/`批` 那两例同族。
    # `年份/年度/年代` 不是年款（那是列名或另一件事），所以这三个后缀不剥。
    r"|(?<!\d)(?:19|20)\d{2}年(?![份度代])") % (_EDITION_UNIT_CH, _EDITION_UNIT_CH))
# 动力/规格编码（数字与字母混写：`2.3T`、`380TSI`、`400THP`、`500h`、`39.05kWh`）不进限量身份：
# 它们是动力轴的量子，留在 affix 里就会因"一侧写排量、另一侧省略"而多拆
# （第八轮 D 回退桶：福特烈马 `2.3T 亚马逊限量版` vs `福特烈马 2026款 2.3T 亚马逊限量版`）。
# 纯数字/中文数词**不在这里剥**（`10周年`、`三百万辆` 是身份本体），纯字母也不剥
# （`PRO`/`MAX`/`Ultra` 是 tier，由版本词/tier 轴管）。
# **字母开头的形要够长才算编码**（hy4 第二票 ②.1）：旧式 `[A-Za-z]+\d+` 会把
# `X1青峰限定版` 与 `X2青峰限定版` 一起吃掉 ⇒ 两款折成一条（真误合）。
# 真编码是 `380TSI`/`400THP`/`Q5L` 这种"字母 + 至少两位数字"，而 `X1`/`Q5`/`iX3` 是车型编号，不许吃。
_EDITION_CODE_RE = re.compile(r"\d+(?:\.\d+)?[A-Za-z]+|[A-Za-z]+\d{2,}[A-Za-z]*")
# 词表按**词根**收而不是收整词：现网实测写法散成 `青峰限定版`、`科林斯古铜特别版`、
# `400万纪念款`、`创始人版`、`黑武士`……只写 `限量版|纪念版` 会漏掉全部变体，
# 每漏一条就是一次**真误合**（同 ID 同价两款并成一行，限量身份从面上消失）。
# `全驱` 就是四轮驱动（不是一根新轴）；不归一就会与 `四驱` 判成两种驱数 ⇒ 凭空造互斥。
_DRIVE_CANON = {"全驱": "四驱", "电动四驱": "四驱", "适时四驱": "四驱", "全时四驱": "四驱"}
_CONFIG_MARKER_KINDS = (
    ("线", re.compile(r"(?<![0-9])(\d{1,4})线")),
    # 座位数必须是**独立**的 1–2 位数字，并允许 `/` 连接的多值（`5/7座` 是"五座或七座"）：
    # ①吃空格后 `EcoBoost 225 6座` 变 `…2256座`，贪婪匹配会把发动机代号吞进座位号
    #   （实测 领裕 61633/62375 因此被误判成"5座 vs 2255座"两款车）；
    # ②中文数词要按**整个数**读：单字匹配会让 `十一座` 读成 `一座`＝1
    #   ⇒ `十一座` 与 `1座` 误合、与 `11座` 假冲突（评审 D2，MPV/轻客真会踩）。
    ("座", re.compile(r"(?<![0-9\d])(\d{1,2}(?:/\d{1,2})*|[一二三四五六七八九十]{1,3})座")),
    ("kwh", re.compile(r"(\d+(?:\.\d+)?)(?:kwh|千瓦时)", re.I)),
    # 驱动分**两轴**（评审 D3）：`驱数`（两驱/四驱）与 `驱位`（前驱/后驱）。
    # 同一辆前置前驱的车，一个源写 `两驱`、另一个写 `前驱`——两轴各说一件事，
    # 塞进同一类就互斥（实测 28 对因此漏合）。`四驱` 同时进两轴：
    # `两驱` vs `四驱` 同轴互斥⇒拦；`前驱` vs `后驱` 同轴互斥⇒拦；`两驱` vs `前驱`⇒不拦。
    ("驱数", re.compile(r"([两四全]驱)")),
    ("驱位", re.compile(r"(前驱|后驱)")),
)
_CONFIG_FLAG_RE = re.compile(r"(改款|长续航|超充|智驾)")
_CN_NUM = {"一": "1", "二": "2", "三": "3", "四": "4", "五": "5", "六": "6",
           "七": "7", "八": "8", "九": "9", "十": "10"}


def _cn_number(text):
    """把座位号的原串读成一个数：`六`→6、`十一`→11、`二十`→20；读不出或超出 1–12 返回 None。
    逐字符替换会把 `十一` 变成 `101`（或从第二个字匹配成 `一`＝1，评审 D2），
    于是 `十一座` 与 `1座` 误合、与 `11座` 假冲突——MPV/轻客真会踩到这个形状。"""
    s = str(text or "").strip()
    if not s:
        return None
    if s.isdigit():
        n = int(s)
    elif "十" in s:
        tens, _, ones = s.partition("十")
        if tens == "":
            t = 1
        elif tens in _CN_NUM:
            t = int(_CN_NUM[tens])
        else:
            return None
        n = t * 10 + (int(_CN_NUM[ones]) if ones in _CN_NUM else 0)
    elif s in _CN_NUM:
        n = int(_CN_NUM[s])
    else:
        return None
    return str(n) if 1 <= n <= 12 else None


def _marker_value(kind, raw):
    """把一处标记的原串摊成规范取值集合（`5/7` → {5,7}，`37.0` → `37`）。

    数值一律 `%g`：`normalize_match_text` 会**吃掉小数点**，实测 `37.0kWh` 归成 `370`
    （与 `37` 判成两种电池 ⇒ 漏合），而 `10.0kWh` 归成 `100`、与 `100kWh` 撞成同一个值
    （真电池差看不见 ⇒ 误合）。所以标记解析不过 normalize，也不留尾部零。
    中文数词只给 `座` 换算（走 `_cn_number`）：对 `四驱` 逐字符替换会把它变成 `4驱`
    （实测凭空造出互斥）。
    `驱数` 先做同义归一：`全驱`＝四轮驱动（hy4 第二票 ⑤：`2.0T 全驱豪华型` 与 `2.0T 前驱豪华型`
    之前两侧都识别不出驱数 ⇒ 不判冲突 ⇒ 折成一条真误合）。"""
    if kind == "驱数":
        raw = _DRIVE_CANON.get(str(raw or "").strip(), raw)
    vals = set()
    for part in str(raw or "").split("/"):
        part = part.strip()
        if not part:
            continue
        if kind == "座":
            num = _cn_number(part)
            if num is None:
                continue
            part = num
        elif kind == "kwh":
            try:
                part = "%g" % float(part)
            except Exception:
                pass
        vals.add(part)
    return frozenset(vals)


def _drive_classes(value):
    """把 `驱动形式`/`驱动方式` 的写法拆成**类**：`驱数`（两驱/四驱）与 `驱位`（前驱/后驱）。

    为什么要拆：跨源对同一个四驱车会写 `双电机四驱` / `三电机四驱` / `前置四驱` / `四驱`，
    整串比就互斥 ⇒ 同 ID 同名同价的行不合（现网出口面 5 组实测）。
    口径与 `_CONFIG_MARKER_KINDS` 里名字侧的两轴一致（评审 D3）：
    多电机 ⇒ 必然是四驱；`前驱`/`后驱` ⇒ 同时算两驱（两轮驱动）；`单电机` **不推断**驱数
    （单电机后驱是真的存在，推成两驱会把 `单电机后驱` 与 `两驱` 的差别吞掉）。
    什么都识别不出来 ⇒ 返回空 ⇒ 这一列不比（缺数据 ≠ 证据）。
    """
    text = re.sub(r"\s+", "", normalize_match_text(value or ""))
    out = {}
    num = set()
    for m in re.findall(r"[两四全]驱", text):
        num.add(_DRIVE_CANON.get(m, m))
    if re.search(r"[二三双]电?机", text):
        num.add("四驱")
    pos = set(re.findall(r"前驱|后驱", text))
    if pos:
        num.add("两驱")
    if num:
        out["驱数"] = num
    if pos:
        out["驱位"] = pos
    return out


def _config_markers(name):
    """名字里的配置标记，**按类别归组**：`{"线": {"192"}, "座": {"5", "7"}, "kwh": {"37"}, "驱": {"四驱"}}`。

    为什么要分类：整集合不相交才判冲突的写法有洞——`增程 Max版 37kWh 6座版 (192线激光雷达）`
    与它的 `896线` 双胞胎共享 `6座`/`kwh`，交集非空 ⇒ 线数差被当成"同款的不同写法"合掉。
    人类分辨这两台车靠的是**同一类配置两侧都声明却给了不同的数**，所以按类比。
    不用 `_sku_core_tokens`：它会剥掉数字，`896线激光雷达` 与 `192线激光雷达` 在它那里长得一样
    （实测 问界M8 6 个簇因此被合）。
    输入只做"去空格 + 小写"，**不过 `normalize_match_text`**（小数点的实测见 `_marker_value`）。
    """
    text = re.sub(r"\s+", "", str(name or "")).lower()
    out = {}
    for kind, rx in _CONFIG_MARKER_KINDS:
        vals = set()
        for m in rx.findall(text):
            vals |= set(_marker_value(kind, m))
        vals.discard("")
        if vals:
            out[kind] = frozenset(vals)
    flags = {re.sub(r"\s", "", str(m)).lower() for m in _CONFIG_FLAG_RE.findall(text)}
    if flags:
        out["flag"] = frozenset(flags)
    # 驱动两轴之间要有**蕴含**关系，否则同轴判据永远比不到（评审 D③）：
    # `前驱`/`后驱` 都是两轮驱动 ⇒ 写了对面就该同时认到 `驱数:两驱`，
    # 于是 懂车帝 `两驱` 与 汽车之家 `前驱` 是"一方说全了"的同一款；
    # 而 `前驱` vs `后驱`（同轴不同值）、`两驱` vs `四驱`（同轴不同值）仍判冲突。
    if out.get("驱位"):
        wd = out.setdefault("驱数", set()) | {"两驱"}
        out["驱数"] = frozenset(wd)
    return out


def _config_marker_conflict(a, b):
    """两行的配置标记是否构成"同一类都声明、值却不相交"。缺类别 = 一侧没写，不算差异。

    旧写法还有一条"整 token 集合互斥 ⇒ 冲突"，实测它把**不同维度**当成互斥
    （评审 E⑤/D③：`Max 四驱版` vs `Max 100kWh版`、`两驱` vs `前驱` 因此漏合），
    而它想拦的"两边各说一件事"已经由 `_sku_spec_conflict` 末尾的
    **身份词互补即不折**那条覆盖（标记集合 ⊆ 身份词集合 ⇒ 集合互斥必然互补）⇒ 删掉。"""
    for kind in set(a) & set(b):
        if a[kind] != b[kind] and not (a[kind] & b[kind]):
            return True
    return False




def _edition_canonical(phrase, root):
    """互补轴上把限量身份缩成"**数字 + 词根**"。

    为什么这里能缩、而 `eds` 轴不许缩：两条轴分工不同。
    `eds` 轴负责**拦误合**（`极光蓝限定版` ≠ `星光蓝限定版`、`110周年` ≠ `210周年`），
    所以它必须整段比；互补轴只是"各说了对方没说的配置"这道额外闸，
    把它也按整段比的话，`途昂青峰限定版` 与 `青峰限定版`（只差车系名写在头）会在这道闸上
    被当成互补 ⇒ 同款拆两行（S1 红过，2026-10-16）。真专名不同在到达互补轴之前就已经被 eds 拦掉了。
    数字必须留：`10周年` 与 `110周年` 是两款，缩成同一个词根会把它们放行。"""
    num = re.search(r"[0-9][0-9.]*|[零〇一二两三四五六七八九十百千万]+", phrase)
    return (num.group(0) if num else "") + root


def _sku_name_identity_tokens(name, series="", brand=""):
    """名字里承载的"身份词"集合：限量身份（已剔掉车系名与比对轴词）+ 配置标记取值 + 版本词。
    选主时用它排序（见 `_merge_cluster`）：`max(len)` 会挑**更长但更空**的名字，
    实测 阿维塔07 74558 两行 `Elite 后驱增程版 39.05kWh`(20 字) 与
    `阿维塔07 2026款 Elite 增程版`(21 字) 折叠后由后者做主 ⇒ `39.05kWh` 与 `后驱`
    从发布面**彻底消失**（该行的 `电池容量(kWh)` 列本来就是空的，名字是唯一载体）。
    `series` 必须一路传到 `_edition_identities`：互补判据（`_sku_spec_conflict` 末尾）
    与限量判据用的是同一批 token，两处口径不一致会一边放行一边拦（评审 G① 的连带面）。"""
    text = str(name or "")
    toks = set("限量:" + _edition_canonical(phrase, root)
               for root, phrases in _edition_identities(text, series, brand).items() for phrase in phrases)
    for kind, vals in _config_markers(text).items():
        for v in vals:
            toks.add("%s:%s" % (kind, v))
    toks |= set(_version_words(text))
    return toks


def _edition_affix(seg, noise):
    """词根**一侧**的这段文字里，属于限量身份的部分。

    三步，每步都有对象，没有一步是"宽启发式"：
    ① 剔噪声词（车系名/品牌/驱动座位电池等标记/版本词）——它们各有自己的比对轴，
       留在身份里就会因"一侧写了、另一侧省略"而多拆（评审 G①/S1）；
    ② 剔四位年款（`2026`、`2026款`）——年款属于年款轴，不是限量身份；
       但 `2000 万辆` 里的 2000 是**辆数**（现网确有 `3000万辆甄选款` 这一族），
       紧跟量词就不许剥，否则 `2000万辆` 与 `2500万辆` 折成一条（qwen 票 A6/A12 同族）；
    ③ 剔 `…型` 结尾的版本名——`飞驰尊享型+豪华臻选包` 里真正区分两款的是版本名（版本词轴已比）
       与包名（这条轴比），不剔就会因"版本名只写在其中一侧"而多拆。现网对象是车款ID 63975
       `45 TFSI quattro 时尚型上市特别版` vs `2024款 45 TFSI quattro 上市特别版`（4 对；
       消融实测 `enumerate_type_rule_effect.py`：去掉这一步，同ID同价同年款空间从 179 → 183 判冲突）。
       我先前把这条的理由挂在 184810 上是**错的**——那是我自己点名打印 `[:40]` 把尾部括注
       `(南方版)` 切掉造成的假形状；184810 现网两行都带括注、两侧都写版本名，与此条无关。
    标点只剥**首尾**：`青峰、限定版` 的顿号是排版，但 `三百·万辆` 中间的 `·` 是身份的一部分
    （deepseek 票 阻断件2 的 D2c 就是想把中间标点也剥掉造成的碰撞）。
    """
    # 顺序很重要：**先整段剥"数字+单位"**，再剔噪声词。反过来会先剥掉 `座` 而把 `7` 留下，
    # 残留的孤立数字仍然把同款拆两行（`7座 青峰限定版` vs `青峰限定版`，hy4 票 ②.1）。
    seg = _EDITION_UNIT_TOKEN_RE.sub("", seg)
    # `第1000台` 与 `1000台` 是同一个里程碑的两种写法（hy4 第三票 ②N3）。
    # 单位整段表里不收 `台`（台/辆只用于区分"辆数里程碑"与"年款"），所以两侧都留着 `1000台`，
    # 真正差的只是那个 `第`：**只吃紧邻数字的 `第`**，`第` 后面没数字的写法不动（不猜语义）。
    seg = re.sub(r"^第(?=\d|[一二三四五六七八九十])", "", seg)
    for j in sorted(noise, key=len, reverse=True):
        seg = seg.replace(j, "")
    seg = _EDITION_YEAR_TOKEN_RE.sub("", seg)
    seg = _EDITION_CODE_RE.sub("", seg)
    seg = re.sub(r"[一-龥]{1,4}型", "", seg)
    # 装饰词（`全新`/`新款`/`新一代`/`NEW`）写在词根**前头**时是营销说法，不是身份：hy4 第二票 ②.6、
    # 第三票 ②N2（只剥 `全新|NEW` 时 `新款青峰限定版` 与 `青峰限定版` 会多拆）。
    # 只剥开头那一处，且不吃 `新年款` 这类含"新"的真实写法（必须是完整词才剥）。
    seg = re.sub(r"^(?:全新|新款|新一代|NEW)", "", seg, flags=re.I)
    # 首尾标点：原来靠一张字符表穷举，永远补不全（`〖青峰〗限定版`、`《青峰》限定版` 都会分开 ⇒ 漏合，
    # hy4 第二票 ②.5）。改成**结构式**规则：首尾连续的非汉字非字母数字全部剥掉——
    # 仍然只动首尾（中间的 `·` 属身份，见上面 docstring 里 deepseek D2c 那条），但不再需要列全表。
    seg = re.sub(r"^[^0-9A-Za-z一-龥]+", "", seg)
    seg = re.sub(r"[^0-9A-Za-z一-龥]+$", "", seg)
    return seg


def _edition_identities(name, series="", brand=""):
    """名字里的限量/纪念身份，**按词根归组并带上词根两侧的专名/编号**：
    `青峰限定版` → `{"限定版": {"青峰限定版"}}`，`10周年纪念版` → `{"周年": {"10周年"}, "纪念版": {"纪念版"}}`。

    只比"有没有命中词根"是评审 E①/D1 点的**真误合**：
    `途昂 青峰限定版` 与 `途昂 科林斯古铜特别版` 两侧 `eds` 都为真 ⇒ 不判冲突 ⇒ 并成一行；
    `10周年纪念版` 与 `20周年纪念版` 词根完全相同 ⇒ 光比词根也挡不住。
    ⇒ 词根只能发现"有限量身份"，身份本身要靠词根**加前缀**比对。

    两侧都必须**剔掉不属于限量身份的东西**（评审 G①，否则修完误合又造出漏合）：
    驱动/座位/电池/线数这些标记各有自己的比对轴，版本词也是，车系名与品牌更不是专名。
    反例（同一款、只是词序不同）：`380TSI 四驱青峰限定版` vs `380TSI 青峰限定版 四驱`
    旧提取得到 `四驱青峰` 与 `青峰` ⇒ 假冲突；`途昂 青峰限定版` vs `青峰限定版` 被车系名污染。"""
    # 空白**一律不算身份边界**：`10 周年`/`10  周年`/`周 年` 都只是排版。
    # 上一版拿空格当分栏符，结果是"空格挪到量词/专名与词根之间就整段丢前缀"
    # （qwen 票 round-8C A6/A8/A12、deepseek 票 阻断件 1/2 全是同一个机制的不同位置）。
    text = re.sub(r"\s+", "", str(name or ""))
    markers = _config_markers(text)
    noise = {v for vals in markers.values() for v in vals if not v.isdigit()}
    # 配置**单位本身**也要剔：`39.05kWh 青峰限定版` 里 noise 只有值 `39.05`，
    # 剥完剩 `kWh` 拼进身份 ⇒ 与省略写法的 `青峰限定版` 不相等 ⇒ 同款被拆两行
    # （hy4 票 ②.1；`7座` 那一支已由 `_EDITION_UNIT_TOKEN_RE` 整段剥掉）。
    noise |= set(markers)
    noise |= set(_version_words(text))
    # 电池化学词也剔出去：它有自己的比对轴（`_CHEM_CANON`）。不剔的话
    # `磷酸铁锂` 与省略写法 `磷酸铁` 会因**名字里的写法差**被限量轴拆成两行
    # （评审 G① 的同一口径：各有自己轴的量不许留在限量身份里）。
    noise |= {c for pat, c in _CHEM_CANON if pat in text for c in (pat, c)}
    for junk in (str(series or ""), str(brand or "")):
        flat = re.sub(r"\s+", "", junk)
        # 品牌/车系要**连段子一起**剔：列写 `AITO 问界`、名字只写 `问界M7` 时，
        # 旧写法只按"整串 + 去空格小写"两种形态匹配 ⇒ 一段都对不上，`问界` 留在限量身份里
        # 把同一款拆成两行（hy4 票 ②.8）。
        for cand in (junk, flat, flat.lower(),
                     *re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z]{2,}", flat)):
            if cand:
                noise.add(cand)
    out = {}
    # 词根在**去空白的整串**上匹配：`10 周 年纪念版`（词根内部夹空格）与 `10周年纪念版`
    # 必须是同一个身份，否则数字整段蒸发 ⇒ 两款折一条（deepseek 票 round-8C 阻断件 1）。
    for m in _EDITION_ROOT_RE.finditer(text):
        # 词根的**形态**（`限定` / `限定版`、`纪念` / `纪念版` / `纪念款`）不算身份差异：
        # 归组与拼身份都用归一后的根，否则同一款因"版/款"写没写被拆成两行（hy4 票 ②.5）。
        root = _edition_root_key(m.group(1))
        # 身份 = 词根**两侧**的整段（各自剔噪后）+ 词根。
        # 为什么两侧都要：`青峰限定版AAA` 与 `青峰限定版BBB` 的区分词在**尾部**，
        # 只比前缀就会把它当空气（两票都点名的残余面）。
        # 为什么不做"取最后一段"：那正是上一轮的洞——空格/标点一挪位置，
        # 前缀就整段丢掉（qwen 票 A6/A8、deepseek 票 阻断件 2 全是同一个机制）。
        head = _edition_affix(text[:m.start()], noise)
        # 尾部（词根之后那段）**不进身份**——这条在第八轮 E 用两边都显式构造的量具定过
        # （`measure_edition_tail_yield.py`：只看前缀判冲突 179 对，收尾部 183 对 ⇒ 代价 +4 对现网同款被拆，
        # 逐对点名（`enumerate_tail_cost_pairs.py`）4 对**全在**车款ID 65447
        # `冠军版 鲲鹏290TGDI DCT豪情版 5座` vs `2024款 冠军版 290TGDI DCT豪情版 5座`，
        # 非显示列只差 `●` vs `支持` 一类同义写法 ⇒ 同一台车），
        # 而那 4 对"收益候选"与代价是**同一批** ⇒ 有效收益 = 0。
        # 两票想要的 `青峰限定版AAA` vs `BBB` 因此仍是**已知未覆盖**：红样里单列打印，不假装已修。
        out.setdefault(root, set()).add(head + root)
    return {k: frozenset(v) for k, v in out.items()}




def _row_seat_values(row):
    """一行的座位取值：先看名字标记（`5/7座` → {5,7}），再看 `model_variant_signature`。
    两处闸必须同一把尺子：签名里的 `([2-9])\\s*座` 只认单值，`5/7座` 被读成 `7`，
    于是与 `5座` 判成两款（评审 E：`/` 多值修复没贯穿到所有护栏）。"""
    vals = set(_config_markers(str(row.get('车型名称') or '')).get('座') or ())
    if vals:
        return vals
    return set(model_variant_signature(row).get('seat') or ())


def _physical_identity(row):
    """第三遍折叠用的"物理身份"：车系 + 年款 + 价格 + 续航 + 加速 + 座位数。
    刻意**不含名字里的 tier / 配置词 / 特征 token**——实测同一款车在两个源里
    名字不同（红旗天工08：懂车帝写 `565 四驱智选版`、汽车之家写 `565 Ultra四驱版`，
    同价 27.98、同续航 565、同加速 3.9），人判"同一款"靠的是这些物理量，
    而名字差异只是各家的叫法。真配置差异仍由 _sku_spec_conflict 逐列拦。"""
    def num(col):
        m = re.search(r"\d+(?:\.\d+)?", str(row.get(col) or ''))
        return m.group(0) if m else ''
    return (
        _series_norm_key(str(row.get('车系', '') or '')),
        str(row.get('年款', '') or '').strip(),
        str(_price_norm(row.get('官方指导价')) or ''),
        num('纯电续航(km)'),
        num('百公里加速(s)'),
        num('座位数'),
    )


def _sku_spec_field(row: dict, fields: tuple) -> str:
    """取规格字段的第一个非空数值/字面（用于"两侧都有值才比较"的冲突判定）。"""
    for field in fields:
        value = str(row.get(field, "") or "").strip()
        if value and value not in ("-", "--", "待查", "暂无", "None", "null"):
            return value
    return ""


def _spec_value_set(value, split_slash=False) -> frozenset:
    """把属性值拆成"规范值集合"：`懂车帝:纯电动|易车:纯电` → {纯电动, 纯电}。
    跨源分段与来源前缀是既定存储形态（不是差异本身），护栏比较前必须先拆开归一。

    `split_slash` 只对**座位数**这一列打开（评审 E/D5）：`座位数(个)` 写 `5 / 4` 是
    "五座、可选四座"，实测 阿维塔11 72863 因此逐列全同的两行留成两行；
    但 `电池容量(kWh)` 的 `75 / 100`、`能源类型` 的 `纯电动/增程式` 是**复合描述**
    （两种配置都在这行里），拆开后与单值行"交集非空"就会把 100kWh 的 SKU 并进 75kWh
    ⇒ 那些列保持整串比对（宁留重复）。
    来源前缀**在原子层面剥到不动为止**（hy4 第三票 ④(c)，10-17 用生产代码复核成立）：
    `纯电续航(km)` 一列里存在两层前缀的写法 `懂车帝:CLTC:600 / WLTC:520`，
    而"各剥一次"是不对称的——`懂车帝:CLTC:600` 只掉外层留 `CLTC:600`，
    另一侧 `CLTC:600` 掉的却是内层留 `600` ⇒ 两个集合空交集 ⇒ **同一台车判成两款**
    （正是下面注释想让"子集照折"的形状，被双层前缀打掉）。
    早先我在 `|` 段层也剥一次，实测 `5 / 易车:4` 的第一次剥离会把 `5 / 易车:` 整段当成前缀删掉
    ⇒ 只剩 `4`，凭空丢掉一个值（评审 G⑤）——那件事的修法是**禁止跨段剥**（前缀字符类里不含 `/`），
    不是限制剥的次数；改成剥到不动之后，`5 / 易车:4` 仍是每段各剥自己那一层，形状不变。"""
    out = set()

    def strip_prefix(atom):
        s = str(atom or "")
        for _ in range(4):        # 防御性上界：现网最深见过两层（来源:工况:数值）
            t = re.sub(r"^\s*[^:：/]{1,8}\s*[:：]\s*", "", s).strip()
            if t == s:
                break
            s = t
        return s

    for seg in str(value or "").split("|"):
        pieces = re.split(r"\s*/\s*|、|,|，", seg) if split_slash else [seg]
        for atom in pieces:
            atom = strip_prefix(atom).strip()
            if not atom or atom in ("-", "--", "待查", "暂无", "None", "null"):
                continue
            out.add(_norm_spec_atom(str(canonical_compare(atom) or "").strip() or atom))
    return frozenset(out)


def _norm_spec_atom(key: str) -> str:
    """纯数值原子里 `110.0` 与 `110`、`52.560` 与 `52.56` 是同一个数，不是差异。
    实测 车款ID 73967（小鹏GX 2026款 纯电 750四驱Ultra旗舰版）两条同价同续航同座位的行，
    因为 电池容量(kWh) 一边写 `110` 一边写 `110.0`，被护栏判成"电池不同"而留在两行——
    那正是用户在筛选中心看到的"重复 SKU"。"""
    m = re.fullmatch(r"(?:num:\s*)?(\d+(?:\.\d+)?)", key)
    if not m:
        return key
    try:
        return "num:%g" % float(m.group(1))
    except Exception:
        return key


def _seat_sets_conflict(sets, anchored):
    """座位取值是否互斥（两族评审在这里给了相反的方向，取保守的一侧并写明理由）。

    · 有锚（组内存在唯一的共同车款ID）⇒ **交集非空即相容**：
      `座位数(个)` 的 `5` 与 `5 / 4`、名字的 `6座` 与 `6座版` 是同一款的不同写法
      （实测 阿维塔11 72863 逐列全同的两行因此留成两行，用户看到的正是重复）。
    · 无锚（组内一行 ID 都没有）⇒ 必须**取值集合完全相同**才敢合：
      评审 H/C 指出 `Max 5/7座` 与 `Max 5座` 相交即折，等于把"可选七座"这一配置粒度抹掉，
      而没有 ID 替我们证明这两行是同一款。负责人口径"宁可留重复也不误合"⇒ 取不折。
    """
    real = [s for s in sets if s]
    if len(real) < 2:
        return False
    if anchored:
        common = set(real[0])
        for s in real[1:]:
            common &= s
        return not common
    return any(s != real[0] for s in real[1:])


def _group_is_anchored(group):
    ids = {str(r.get('车款ID') or '').strip() for r in group} - {'', '-'}
    return len(ids) == 1


# (命中片段, 规范名)：名字里出现左边的任意片段就算那种电池。
# 左边写的是**能覆盖省略写法**的形式（`磷酸铁` 同时命中 `磷酸铁` 与 `磷酸铁锂`），
# 右边是比对用的规范名 ⇒ 一侧写全称、另一侧写省略形不会被当成"一侧没写"。
_CHEM_CANON = (("磷酸铁", "磷酸铁锂"), ("三元锂", "三元锂"),
               ("半固态", "半固态"), ("钠离子", "钠离子"))


_ENERGY_ASSERTS = {
    # 值 → (有燃油机, 有电力驱动, 可外接充电)；None 表示"这一维不作断言"，
    # False 表示"明确否定这一维"。两值相容 = 没有任何一维被一边肯定、另一边否定。
    # 为什么不用"同一类才相容"的粗法：现网 70483（奥迪Q7 55 TFSI）一个源写 `汽油`、
    # 另一个写 `48V轻混系统`——那是同一台车的**详略两种写法**（轻混就是挂在汽油机上的），
    # 按"类别不同即冲突"会把它们判成两款 ⇒ 我这根轴又造一次漏合。
    # 也不用"交集非空即相容"：那样 `油电混合`(HEV) 与 `插电混动`(PHEV) 会因为都含"燃油"而放过，
    # 而它们是实打实的两款 ⇒ 必须靠"否定"这一维分开。
    "汽油": (True, None, None),
    "柴油": (True, None, None),
    "燃油": (True, None, None),
    "48v轻混系统": (True, False, False),
    "汽油+48v轻混系统": (True, False, False),
    "油电混合": (True, False, False),
    "混合动力": (True, False, False),
    "纯电动": (False, True, False),
    "纯电": (False, True, False),
    "ev": (False, True, False),
    "增程式": (True, True, False),
    "增程式纯电动": (True, True, False),
    "插电式混合动力": (True, True, True),
    # `插电混合` 是**易车在现网的实际写法**（10-19 实测 721 行，另有 56 行带源前缀的同款串），
    # 不是猜出来的营销词：这张表按函数自己的说法就是"平台枚举，现网实测覆盖到几乎全部行"，
    # 漏一个真在用的写法 ⇒ 那 721 行对能源"什么都不断言"。
    # 先长后短（上面那处修法）救不了它：`插电混动` 并不是 `插电混合` 的子串，两个都不命中。
    "插电混合": (True, True, True),
    "插电混动": (True, True, True),
    "插电式": (True, True, True),
    "phev": (True, True, True),
    "燃料电池": (None, True, None),
}


def _energy_asserts(value):
    """把能源类型的取值翻成断言三元组；认不出的取值返回 None（= 不作断言，不参与冲突）。

    这里是**平台枚举**（现网实测 14 种取值覆盖到几乎全部行，见 npc-redtests/FINDING §七十二），
    不是无限扩张的营销词表：认不出就当"这一侧没说"，宁可少拦一条误合，也不许拿猜出来的类别
    去造漏合。
    """
    out = []
    for part in re.split(r"[|｜]", str(value or "").strip()):
        atomic = re.split(r"[:：]", part, maxsplit=1)[-1].strip().lower()
        atomic = re.sub(r"\s+", "", atomic)
        if not atomic:
            continue
        hit = _ENERGY_ASSERTS.get(atomic)
        if hit is None:
            # 子串匹配必须**先长后短**（票面 ③-2，10-19 真代码复现为**误合**）：表里的 key 互为子串，
            # 按插入顺序取第一个命中 ⇒ `插电混合动力` 撞上排在前面的 `混合动力`，拿到 (True,False,False)
            # （"能充电"那一维被判成 False）⇒ PHEV 与纯汽油不判冲突 ⇒ 折成一款。
            for k in sorted(_ENERGY_ASSERTS, key=len, reverse=True):
                if k and k in atomic:
                    hit = _ENERGY_ASSERTS[k]
                    break
        if hit is not None:
            out.append(hit)
    if not out:
        return None
    # 多维合并：一侧写了 `汽油+48V轻混系统` 这种复合串，按"任一成分肯定即肯定"处理；
    # 否定只在**整侧都没肯定那一维**时才成立（否则 `增程`(油+电) 会被拆成"不充电⇒否电"）。
    return (True if any(x[0] is True for x in out)
            else (False if all(x[0] is False for x in out) else None),
            True if any(x[1] is True for x in out)
            else (False if all(x[1] is False for x in out) else None),
            True if any(x[2] is True for x in out)
            else (False if all(x[2] is False for x in out) else None))


def _energy_compatible(va, vb):
    """两串的能源描述是否相容：任何一维被一边肯定、被另一边否定 ⇒ 不相容（真两款）。"""
    if va is None or vb is None:
        return True
    return all(not ((a is True and b is False) or (a is False and b is True))
               for a, b in zip(va, vb))


def _canonical_yiche_energy_asserts(value):
    """给轴用的入口：优先复用仓里已有的原子归一，再翻成断言三元组。"""
    asserts = _energy_asserts(value)
    if asserts is not None:
        return asserts
    atoms = _canonical_yiche_energy_values(value)
    for atom in (atoms or []):
        got = _energy_asserts(atom)
        if got is not None:
            return got
    return None


_NAME_CODE_NUM_RE = re.compile(r"(?<![\d.])\d{2,4}(?=\s*[A-Za-z])")


def _name_code_numbers(name):
    r"""名字里"数字紧跟字母词"的编号 token（`350 Max`→{350}、`380TSI`→{380}、`45 TFSI`→{45}）。

    只认**后面必须跟着字母词**这一种形状：`2025款`（年款轴）、`1.5T`（排量，小数点已被
    `(?<![\d.])` 排除）、`EcoBoost 225 6座`（225 后面是数字不是字母词）都不算，
    所以这条轴不会与年款/排量/座位那几根已有轴抢同一件事。
    """
    return {m.group(0) for m in _NAME_CODE_NUM_RE.finditer(re.sub(r"\s+", " ", str(name or "")))}


# 回填登记簿：id(行) -> (行本身, {这一格里被搬进来的列})。
# 连行对象一起存并核 `is`，是为了防 id 复用（旧行被回收后新行拿到同一个 id 就会误清空）。
_BACKFILLED = {}


def _note_backfilled(row, col):
    if not isinstance(row, dict):
        return
    ent = _BACKFILLED.get(id(row))
    if ent is None or ent[0] is not row:
        _BACKFILLED[id(row)] = (row, {str(col)})
    else:
        ent[1].add(str(col))


def _unbackfilled(row):
    """把"搬进来的格"还原成空 ⇒ 后续遍的折/不折判断只看这一行**自己声明过**的值。

    为什么必须还原（10-18 第二族黑箱票的阻断件，我复算逐位对上）：三遍折叠依次作用在上一遍的
    存活行上，就地回填会让下一遍把搬来的值当成"这一侧也写了"，于是原本可并的一对被判互斥——
    `ab_backfill_fold_effect.py` 在现网 33479 行面上量到：短路回填 20288 行、
    就地回填 20402 行（Δ>0 组=86、其中无车款ID=85、Δ<0=0）。
    之前试过"把回填整段挪到折叠之后"，Δ 归零了但**66 个无歧义格补不回来**（风险尺判红、链拒发包），
    所以留在这里：覆盖率不动，搬来的值不参与判断。
    """
    ent = _BACKFILLED.get(id(row))
    if not isinstance(row, dict) or ent is None or ent[0] is not row or not ent[1]:
        return row
    q = dict(row)
    for c in ent[1]:
        q[c] = ''
    return q


def _sku_spec_conflict(group: list) -> bool:
    """组内是否出现"两侧都有值却对不上"的实质属性冲突。缺数据不算冲突。
    车款ID 要求严格相等（源侧主键）；电池/驱动/能源按**规范值集合是否相交**判：
    交集为空 ⇒ 真配置差异（实测昊铂HT 2024 的 80.06 与 83.3 仍拦得住）；
    交集非空 ⇒ 同一属性的两种跨源写法（实测阿维塔07 `懂车帝:纯电动|易车:纯电` vs `纯电`）。"""
    group = [_unbackfilled(r) for r in group]   # 判断只吃"自己声明过"的值，见上面的注释
    ids = {_sku_spec_field(r, ("车款ID",)) for r in group}
    ids.discard("")
    if len(ids) > 1:
        return True
    for field in ("电池容量(kWh)", "电池电量(kWh)", "电池能量(kWh)"):
        # **逐列同口径比**，不许"每行取第一个非空列"再比：同一属性在本仓有多列
        # （电池容量/电池能量…），两个源各填一列时那种取法会拿 79.1 去比 79，
        # 造出跨口径假冲突（实测 小鹏G9 76192 四项全同的两行因此不合）。
        sets = [_spec_value_set(r.get(field)) for r in group]
        sets = [s for s in sets if s]
        if len(sets) < 2:
            continue
        common = set(sets[0])
        for s in sets[1:]:
            common &= s
        if not common:
            return True
    # 能源类型是**闭集枚举**（现网实测取值就那十几种：汽油/纯电动/插电式混合动力/纯电/
    # 48V轻混系统/油电混合/增程式/插电混动/汽油+48V轻混系统/增程式纯电动/柴油…），
    # 同一台车跨源会写成 `纯电动` 与 `纯电`、`增程式` 与 `增程式纯电动`。
    # 8M 现网对象 183689（迈巴赫EQS SUV 礼逸版）：两行同 ID 同价同名，一个源写 `纯电动`、
    # 另一个写 `纯电` ⇒ 拿原始串比会判冲突 ⇒ **本包自己造出一个漏合**（这是我加的轴引入的，
    # main 没有这根轴）。所以这根轴按**类别集合**比：交集非空 ⇒ 同一件事的两种写法；
    # 子集不算差异（`汽油` vs `汽油+48V轻混系统` 与续航那根轴同一口径）。
    # 认不出的取值**原样保留**，不许悄悄归到已知类里（那才会误合）。
    # 归一复用仓里已有的 `_canonical_yiche_energy_values` 作后备（它就在做"按 `|` 拆、
    # 剥 `懂车帝:` 这类源前缀、归成 增程/纯电/插混/油混 原子"）。函数名带 yiche 是历史命名，
    # 实际输入是任意来源的串；要改名请另开一单，别混进本包。
    asserts = [x for x in (_canonical_yiche_energy_asserts(r.get("能源类型")) for r in group) if x]
    for i in range(len(asserts)):
        for j in range(i + 1, len(asserts)):
            if not _energy_compatible(asserts[i], asserts[j]):
                return True
    # 驱动要**按类比**（评审 D3 的同一口径），不能拿整串比：列里同时存在
    # `双电机四驱` / `三电机四驱` / `前置四驱` 三种写法，整串比会互斥 ⇒
    # 同 ID 同名同价同年款的行不合（现网出口面实测 5 组：62872/59421/74782/74511/74580、76219）。
    # 类分完仍要保住真差异：`两驱` vs `四驱`、`前驱` vs `后驱` 各自同类互斥 ⇒ 仍判冲突（test_r4）。
    for field in ("驱动方式", "驱动形式"):
        kinds = [_drive_classes(r.get(field)) for r in group]
        kinds = [k for k in kinds if k]
        if len(kinds) < 2:
            continue
        for kind in ("驱数", "驱位"):
            vals = [k.get(kind) for k in kinds if k.get(kind)]
            if len(vals) >= 2 and not (set.intersection(*[set(v) for v in vals])):
                return True
    # 纯电续航也要比（10-16 安全尺分诊实测：Lorinser 星际战车两行同价，一行 125km、一行 150km
    # 被折成一条；瑞虎9 C-DM 的 `三元锂`/`磷酸铁锂` 两行 82km 与 80km 也进了同一格）。
    # 这一列必须用 `split_slash=True`：`CLTC:600 / WLTC:520` 是**同一 SKU 的两个工况**，
    # 整串比会让它与只写 `CLTC:600` 的另一源判成互斥（假冲突 ⇒ 倒退成漏合）；
    # 剥前缀 + 拆开后 {600,520} ∩ {600} 非空 ⇒ 仍折。子集不算差异（`500|550` vs `550` 照折）。
    for field in ("纯电续航(km)", "CLTC纯电续航里程(km)", "WLTC纯电续航里程(km)",
                  "NEDC纯电续航里程(km)"):
        sets = [_spec_value_set(r.get(field), split_slash=True) for r in group]
        sets = [s for s in sets if s]
        if len(sets) < 2:
            continue
        common = set(sets[0])
        for s in sets[1:]:
            common &= s
        if not common:
            return True
    # 名字里的"数字+字母词"编号是一档车的身份（`350 Max` vs `670 Max`、`330TSI` vs `380TSI`）。
    # 现网对象 74307：两行同 ID、同价、同年款，`纯电续航(km)` 列两边**都是** `CLTC:350 / WLTC:282`
    # （670 那一档的续航列被源侧写成了 350 的值），所以列轴一条都不冲突 ⇒ 我把自己新加的
    # `_id_key`（同 ID 同价同年款就建簇）一路折成一行，`670 Max` 这一档从面上消失——**误合**方向。
    # 我自己那把词表无关的误合尺看不见它（它比的是列），`真误合=0` 那个 0 因此是空读数；
    # 是 `compare_xing_flip_local.py` 报"基线=2 → 新树=1"（新树多折）时我逐列点开才发现的。
    # 口径与版本词/电池同一：两侧都写了且集合不相交 ⇒ 冲突；一侧没写 = 缺数据 ≠ 证据
    # （否则 `670 Max五座激光雷达版` 与 `五座激光雷达版` 会倒退成漏合）。
    name_codes = [_name_code_numbers(str(r.get('车型名称') or '')) for r in group]
    name_codes = [s for s in name_codes if s]
    if len(name_codes) >= 2:
        common = set(name_codes[0])
        for s in name_codes[1:]:
            common &= s
        if not common:
            return True
    # `百公里加速(s)` **不加**进冲突轴（deepseek 票 round-8C 阻断件5 想要，我先加了，再用现网归因撤掉）：
    # `attribute_lost_pair.py` 对车款ID 76544（小米YU7 四驱GT）逐列隔离的结果是——
    # 唯一拦手就是这列（`2.92` vs `2.98`，同一台车的跨源测量差），加它带来 4 对现网真回退；
    # 而另一把量具 `measure_accel_axis_yield.py` 量的"除加速外全同"的形状 = 0 对，
    # 说明票面那个合成反例在现网不对应任何两款真车。GLM 票 round-7 的"跨源加速有噪声"由此被证实。
    # 残余风险如实记：同 ID 同价、仅加速不同时会被折——这是**已知取舍**，不是漏检。
    # 电池种类是**两款车**不是两种写法（负责人 10-15 口径：别的配置都一样也可能只差电池）。
    # 与版本词同一口径：两侧都写了且集合不相交才算冲突，一侧没写 = 缺数据 ≠ 证据。
    # 词表按**省略写法也要命中**的口径写（deepseek 票 round-8C 阻断件4：只认两个精确串时，
    # 一侧写 `磷酸铁` ⇒ 视作没写 ⇒ 缺数据不算冲突 ⇒ 两款折成一条）。
    chems = [{canon for pat, canon in _CHEM_CANON if pat in str(r.get('车型名称') or '')}
             for r in group]
    chems = [c for c in chems if c]
    if len(chems) >= 2:
        common = set(chems[0])
        for c in chems[1:]:
            common &= c
        if not common:
            return True
    # 名字里的版本词也按同一口径比：**两侧都写了**且集合不相交 ⇒ 是两款车。
    # 实测 奇瑞 车款ID 59684 同价 11.39万、同加速 8.28s，但一行写 `DCT尊贵型`、
    # 另一行写 `DCT旗舰型` ⇒ 同 ID 也不能合（源侧 ID 会漂，版本词是人眼的第一判据）。
    # 一侧没写不算差异（缺数据 ≠ 证据）：实测 宝马iX3 66549 一行写 `领先型`、
    # 另一行写 `2024款 领先型`，只差年款前缀写没写 ⇒ 同款（tests 的 H4）。
    # 但**限量/纪念/联名/纽北**这类标记不对称要判冲突（见下面 _EDITION_MARK_RE 那条），
    # 小米SU7 70545 的 `纽北限量版` 与 `Ultra` 就是被评审 B1 从"省后缀"改判成"两款"的。
    words = [(_version_words(str(r.get('车型名称') or '')) - {frozenset()}) for r in group]
    words = [w for w in words if w]
    if len(words) >= 2:
        common = set(words[0])
        for w in words[1:]:
            common &= w
        if not common:
            return True
    # **《X型》版本名是一条不看词表的轴**（hy4 黑箱票 ①P1/P2/P3，三条都是我上一包引入的误合）：
    # `_VERSION_WORDS_RE` 只有 21 个词，`时尚型/进取型/动感型/科技型/探索型` 全在表外 ⇒
    # 同 ID 同价同年款就折成一条，而我原来的分桶尺（D 桶）问"规格是否全同"用的正是同一张表，
    # 对这类形状必然是空读数。口径与版本词轴一致：**两侧都写了、且没有一个相同 ⇒ 两款**；
    # 一侧没写不算差异（现网 63975 `…时尚型上市特别版` vs `2024款 …上市特别版` 必须仍折）。
    xing = [set(_xing_version_names(str(r.get('车型名称') or ''),
                                    str(r.get('车系') or ''), str(r.get('品牌') or ''))) for r in group]
    xing = [x for x in xing if x]
    # 逐对看而不是"整组交集为空"：三行里 `豪华型`/`尊享豪华型`/`舒享豪华型` 这种
    # 只要**任意两行互非后缀**就该分开（整组求交集会把这种"两两都不同"误判成同一条）。
    if len(xing) >= 2:
        for xi in range(len(xing)):
            for xj in range(xi + 1, len(xing)):
                if not _xing_same_version(xing[xi], xing[xj]):
                    return True
    # `版/款` 收尾的版本名同样按"两侧都写了、且互非后缀 ⇒ 两款"判（hy4 第三票 ①M1/S1/S2）。
    # 判等关系直接复用 `_xing_same_version`——它对"两个 token 集合"是形态无关的：
    # 相等/有交集/一侧是另一侧的结尾 ⇒ 同一副版本名的两种写法；互非后缀 ⇒ 两副。
    bans = [set(_ban_version_names(str(r.get('车型名称') or ''),
                                   str(r.get('车系') or ''), str(r.get('品牌') or ''))) for r in group]
    bans = [x for x in bans if x]
    if len(bans) >= 2:
        for bi in range(len(bans)):
            for bj in range(bi + 1, len(bans)):
                if not _xing_same_version(bans[bi], bans[bj]):
                    return True
    # 座位数同样按"两侧都声明了且不相交"判：**不许进同 ID 键**——
    # 实测 22 组同 ID 同价同年款的行被键里的座位签名拆开（瑞虎8 PRO 69951/69952/69953/74589、
    # 瑞虎8 PLUS 77079/77080 等），而两行的 `座位数` 列都是空、名字里也都没写"X座"，
    # 签名却一个是 ('5',) 一个是 () ⇒ 那是一侧从别的列推出来的形状，不是差异证据。
    seats = [_row_seat_values(r) for r in group]
    if _seat_sets_conflict(seats, _group_is_anchored(group)):
        return True
    # 名字推出来的座位签名会被"一侧名字里没写座位"稀释（评审 B1 实测 锐界 78541：
    # `座位数(个)` 列明明是 7 与 5，两行却因签名 {5,7}∩{5} 相交而被合），
    # 所以列值也要单独比：两侧都填了 `座位数(个)` 且数值互斥 ⇒ 是两款车。
    col_seats = [_spec_value_set(r.get('座位数(个)'), split_slash=True) for r in group]
    if _seat_sets_conflict(col_seats, _group_is_anchored(group)):
        return True
    # 停产/停售是**状态**而不是写法：一侧名字里带"(2026.3停产)"、另一侧不带，
    # 折起来就把面上唯一的停售信号抹掉了（实测 探岳 77034/77035）。宁可留重复。
    marks = [bool(_STOP_MARK_RE.search(str(r.get('车型名称') or '') + ' ' + str(r.get('上市时间') or '')))
             for r in group]
    if any(marks) and not all(marks):
        return True
    # 限量/纪念/联名这类是**产品身份**而不是可省的写法。三种形状都要判冲突（评审 E①/D1）：
    # ①一侧写了、另一侧没写（`纽北限量版` vs `Ultra`，实测 小米SU7 70545 两行同价但
    #   520km/1.98s 与 630km/2.1s 是两台车的数）⇒ 不对称即冲突；
    # ②两侧都写了**不同词根**（`青峰限定版` vs `科林斯古铜特别版`）⇒ 旧写法只比 bool 会误合；
    # ③两侧词根相同**但前缀编号/专名不同**（`10周年纪念版` vs `20周年纪念版`）⇒ 只比词根也会误合。
    eds = [_edition_identities(str(r.get('车型名称') or ''), str(r.get('车系') or ''),
                               str(r.get('品牌') or '')) for r in group]
    if any(eds) and not all(eds):
        return True
    eds = [e for e in eds if e]
    for i in range(len(eds)):
        for j in range(i + 1, len(eds)):
            roots_a, roots_b = set(eds[i]), set(eds[j])
            if roots_a != roots_b and not (roots_a & roots_b):
                return True
            for root in roots_a & roots_b:
                # 同一词根下两侧都写了身份，而**没有一个身份完全相等** ⇒ 是两款。
                # 这里刻意不做"后缀豁免/包含豁免"：能承载限量身份的都是专名与编号，
                # 任何放宽规则都被证明会放过真两款（固定窗口撞 `极光蓝`/`星光蓝`、
                # `110`/`210`；后缀豁免撞 `璀璨星空`/`星空`）。书写差在**取前缀时**就用
                # 空格分栏与剔噪解决了，不留到比对方去猜。
                if not (eds[i][root] & eds[j][root]):
                    return True
    # 名字里的**配置 token** 互斥 ⇒ 不是同一款（实测 问界M8：`增程 Max版 53.4kWh`
    # 与 `增程 Max 五座长续航版(896线激光雷达)` 同 车款ID 同价，但一个是 192 线一个是 896 线，
    # 人眼一看就是两款；tier 那种纯写法词（Ultra/UItra）不在此列，不会被误拦）。
    toks = [_config_markers(str(r.get('车型名称') or '')) for r in group]
    toks = [t for t in toks if t]
    for i in range(len(toks)):
        for j in range(i + 1, len(toks)):
            if _config_marker_conflict(toks[i], toks[j]):
                return True
    # 名字的**身份词互补**也不许折（评审 E②）：`Max 四驱 6座 智驾版 192线激光雷达` 与
    # `Max 四驱 6座 100kWh` 同类取值都不矛盾，但各说了对方没说的配置；一折就必然丢掉一边
    # （选主只能留一个名字，而这类行的 `电池容量(kWh)` 列常常是空的，名字是唯一载体）。
    # 一侧名字没写任何标记（H4/P1/Q1 那种）不算互补：那还是"书写省略"。
    # 代价实测很小：filtered 面 1930 次折叠里只多拦 13 行（0.7%）。
    idents = [_sku_name_identity_tokens(str(r.get('车型名称') or ''),
                                        str(r.get('车系') or ''),
                                        str(r.get('品牌') or '')) for r in group]
    idents = [t for t in idents if t]
    for i in range(len(idents)):
        for j in range(i + 1, len(idents)):
            a, b = idents[i], idents[j]
            if a and b and a != b and not (a <= b) and not (b <= a):
                return True
    return False

_MERGE_IDENTITY_COLS = ('品牌', '车系', '车系ID', '年款', '车款ID', '车型名称', '数据来源', '官方指导价')


def _cell_blank(v):
    """与量具 `measure_backfill_risk.py` / `measure_folded_cell_loss.py` 钉成同一口径：
    ""/"-"/"None"/"nan" 算空。两侧口径一旦不一致，"回填了几格"这个数就互相对不上。"""
    return str(v if v is not None else '').strip() in ('', '-', 'None', 'nan')


# 10-18 19:44 hy4 黑箱票的阻断件 ①-A（本轮在真代码上复现，不是推演）：`_cell_blank` 把 `-` 判成
# "没数据"，而**同一个文件**的 `VALUE_SYNONYMS` 把 `无/不支持/—/--` 归一成 `-` —— 于是"某源明确
# 写了无此配置"在这套代码里同时是「一个值」和「空」。后果：keeper 那格 `-`、族内另一行 `●`
# ⇒ 候选集只剩 `●` ⇒ 单候选 ⇒ 搬进 keeper ⇒ 出口对写着"无此配置"的那一家宣称标配。
# 这是"归并后说谎"（§3 第 3 条），不是"少填一格"。
# 只动**回填的候选资格**：`_cell_blank` 一个字不改（它已与 `measure_backfill_risk.py`、
# `measure_folded_cell_loss.py` 钉成同一把尺，改了会让"回填了几格"这个跨轮数失去可比性）。
# 表直接从 `VALUE_SYNONYMS` 反推，不另写一份清单 ⇒ 两处口径将来只会一起变，不会各变各的。
# 票面建议把 `/` 也算显式否定，这里**不采纳**：实测 `canonical_compare('/')` 仍是 `/`，
# 文件里没有任何一处把 `/` 归一到 `-`，收进来就是我替数据源发明同义词。
_EXPLICIT_NEG = frozenset({'-'}) | frozenset(
    k for k, v in VALUE_SYNONYMS.items() if str(v).strip() == '-')


def _backfill_candidate(v):
    """这一格够不够当回填候选：非空，**或**是显式否定写法（后者是"有值"，不是"没数据"）。"""
    s = str(v if v is not None else '').strip()
    return (not _cell_blank(s)) or s in _EXPLICIT_NEG


def dedupe_merged_rows(rows, *, _observe_merge=None):
    if not isinstance(rows, list):
        return rows
    # 登记簿按 id 索引，跨调用会踩到回收后的 id（虽有 `is` 核身，仍会白白涨内存）。
    # 每次入口清空：登记只在**这一次**折叠里有意义。
    _BACKFILLED.clear()
    """Collapse rows that are the same SKU merged at different levels.

    Key: normalized series + year + price + tier/seat signature. Rows sharing
    the key are combined: the row with the richest source label wins, the
    source labels are unioned (deduped), and 数据来源 is set to the merged
    label. Returns a new list (input untouched).
    """
    _TRIM_WORDS = re.compile(
        r"大满配|超满配|满配|豪华|尊贵|尊享|智享|行政|精英|舒适|运动|旗舰|标准|尊荣|尊越"
    )
    def _attr_tail(row):
        """两遍折叠共用的"属性尾巴"：年款/价/级别/座位/配置词/特征 token。"""
        sig = model_variant_signature(row)
        name_text = str(row.get('车型名称', '') or '')
        return (
            str(row.get('年款', '') or ''),          # 年款不同 = 不同 SKU（用户裁定），始终在键里
            _price_norm(row.get('官方指导价')),        # 一个配置只有一个指导价
            tuple(sorted(sig['tier'])),
            tuple(sorted(sig['seat'])),
            tuple(sorted(set(_TRIM_WORDS.findall(name_text)))),
            _sku_core_tokens(name_text, str(row.get('车系', '') or '')),
        )

    # 两种键各建一簇，两遍**依次作用在上一遍的存活行上**。不能各自对原始行建簇：
    # 那样第二遍会按车系把第一遍按车款ID 合好的行重新拆开，并整体丢弃第一遍的结果
    # （实测 腾势N9 / 腾势N9 DM 同车款ID 77164 会退回两行）。
    #   · 车款ID 键 —— 源侧 SKU 主键，跨车系名也认；
    #   · 属性键 —— 车系+年款+价+级别+座位+配置 token，让"一行有 ID、另一行没有"的
    #     同一 SKU 也能合上（实测 6443 行无车款ID，别克至境E7、阿维塔07 都栽在这）。
    # 谁能合并由 _collapse 决定：同簇且无"明确冲突"才并。
    def _id_key(row):
        sku_id = str(row.get('车款ID', '') or '').strip()
        if not sku_id:
            return None
        # 同车款ID = 源侧同一款 ⇒ 这一遍的键里只留"人也会拿来分开两款"的年款与价格。
        # 名字里的形状词（tier、座位签名）都不参与：实测 7 组"同 ID 却两行"栽在 tier 上
        # （汽车之家把 Ultra 写成 UItra、车系全名带 PRO 而短名不带），又有 22 组栽在
        # 座位签名上（两行 `座位数` 列都空、名字都没写"X座"，签名却一个 ('5',) 一个空）。
        # 真差异由 _sku_spec_conflict 逐列拦（电池/驱动/能源/版本词/座位各按
        # "两侧都声明了且不相交"判），而"同 ID 不同价"（奥迪Q5 e-tron 四行两价）由价格分开。
        return ("sku", sku_id,
                str(row.get('年款', '') or ''),
                _price_norm(row.get('官方指导价')))

    def _attr_key(row):
        return (_series_norm_key(str(row.get('车系', '') or '')),) + _attr_tail(row)

    def _phys_key(row):
        k = _physical_identity(row)
        # 车系/年款/价/续航/加速 缺任一项就不参与（缺数据 ≠ 证据）
        if not k[0] or not k[1] or not k[2] or not k[3] or not k[4]:
            return None
        return k

    def _physical_cluster_ok(group):
        # 判"这一簇能不能折"要看在**未回填**输入面上的声明（票面①-c）：前两遍搬进来的座位/续航
        # 若被这一遍当成"两侧都写了"，就会把本可并的一对判成互斥。冲突闸里已这么处理，
        # 这一处原先直接吃原行——覆盖面靠列名巧合成立（`座位数(个)` 恰好不进身份列），换个列名就破。
        group = [_unbackfilled(r) for r in group]
        ids = {str(r.get('车款ID') or '').strip() for r in group} - {'', '-'}
        # 物理身份（车系+年款+价+续航+加速+座位）相同**不等于**同一款：实测 凯迪拉克XT5 2026 的
        # `28T 四驱豪华型/尊贵型/铂金型` 与 `28T 两驱大都会型` 在面上续航/加速/座位都空或同值，
        # 只有名字里的驱动形式能分辨。所以第三遍也必须过逐列+名字的误合闸（旧写法是
        # "簇里只有一个车款ID 就无条件合"，那等于把这遍开成无护栏）。
        if len(ids) >= 2:
            return False                      # 归属有歧义：整簇不折
        if _sku_spec_conflict(group):
            return False
        if len(ids) == 1:
            # 簇里只有一种车款ID（无论是否混着无 ID 行）⇒ 源侧就是同一款，锚成立
            return True
        # 全是无 ID 行（没有锚）⇒ 只有"名字里的版本词 / 座位数 / 改款标记不矛盾"才敢并。
        # 反例（必须留下）：沃尔沃XC60 PHEV `智远豪华版` vs `智远极夜黑版`
        # 同价 52.39、同续航 90、同加速 5，但版本词不同 ⇒ 两款车。
        # 座位这里改成与冲突闸**同一把尺**（评审 G⑦）：旧写法直接调 `model_variant_signature`
        # 的 `([2-9])\s*座`，`Max 5/7座` 被读成 {7}、`Max 5座` 读成 {5} ⇒ 判成不等而拒合；
        # 而 `_row_seat_values` 认 {5,7} 与 {5} 相容。等价性检查本就是多余的
        # （`_collapse` 已先按 `_sku_spec_conflict` 成对分裂过，座位互斥的进不了同一簇）。
        words = {_version_words(str(r.get('车型名称') or '')) for r in group}
        restyle = {('改款' in normalize_match_text(str(r.get('车型名称') or ''))) for r in group}
        if len(words) != 1 or len(restyle) != 1:
            return False
        # 无锚 ⇒ 与冲突闸同一个严格度（取值集合必须相同），只是**取值来源**统一成 `_row_seat_values`
        return not _seat_sets_conflict([_row_seat_values(r) for r in group], anchored=False)

    rows = _collapse(rows, _id_key, _observe_merge=_observe_merge)
    rows = _collapse(rows, _attr_key, _observe_merge=_observe_merge)
    # 第三遍要**跑到不动点**：车系写法归一发生在每一遍的末尾，
    # 所以"物理身份相同、只是车系写法不同"的两行要到归一之后才会落进同一个簇。
    # 实测一轮会留下 12 个这样的簇。
    for _ in range(3):
        before = len(rows)
        rows = _collapse(rows, _phys_key, _physical_cluster_ok, _observe_merge=_observe_merge)
        if len(rows) == before:
            break
    return rows


def _collapse(rows: list, key_fn, accept=None, *, _observe_merge=None) -> list:
    """按 key_fn 对**它收到的这批行**分簇收敛：同簇且无明确冲突才合并成一行。
    行不是 dict 或 key_fn 返回 None ⇒ 原样带走，不参与本遍折叠。
    accept(cluster) 返回假 ⇒ 整簇放弃折叠（用于"归属有歧义就不折"的场合）。"""
    groups = {}
    out = []
    for row in rows:
        if not isinstance(row, dict):
            out.append(row)
            continue
        key = key_fn(_unbackfilled(row))   # 分簇键必须看"这一行自己声明过的值"：回填搬进来的格
                                           # 会改 tier/座位/配置词签名 ⇒ 不改这里就有 72 组假不并
        if key is None:
            out.append(row)
            continue
        groups.setdefault(key, []).append(row)

    def _merge_cluster(group):
        labels = []
        best = group[0]

        def _rank(row):
            # 来源富集度优先；并列时优先"价格干净"（不带 | 合并串）的那一行。
            # 注意这里是**取最大值**做主，所以"干净"必须给高分：旧写法给脏值 1，
            # 结果反而选中合并串价格（评审 D：`40.5万` 输给 `40.5万|40.50万`，
            # 发布面展示字段被合并串污染）。
            label = str(row.get('数据来源', '') or '')
            price = str(row.get('官方指导价', '') or '')
            return (label.count('+'), 1 if '|' not in price else 0)

        for row in group:
            label = str(row.get('数据来源', '') or '')
            if label and label not in labels:
                labels.append(label)
            if _rank(row) > _rank(best):
                best = row
        base = dict(best)
        # 登记簿必须**跟着复制到新行**：三遍折叠每一遍都用 `dict(best)` 造新对象，
        # 上一遍搬进 best 的列如果不继承，下一遍的 `_unbackfilled` 就还原不出来
        # ⇒ 第二/三遍的分簇键与冲突闸仍会看到搬来的值（"搬来的值不参与判断"这条只在最后一遍成立）。
        # 10-18 16:57 复算实测：现网面上残余 390 组、约 7.9 万格是这么漏的（票面②的逐行逐列相等判据据此不成立）。
        _ent = _BACKFILLED.get(id(best))
        if _ent is not None and _ent[0] is best and _ent[1]:
            _BACKFILLED[id(base)] = (base, set(_ent[1]))
        name_candidates = [str(row.get('车型名称', '') or '').strip() for row in group
                           if str(row.get('车型名称', '') or '').strip()]
        # Exclude explicit year contradictions when a compatible observed name
        # exists. Names without a year still carry real trim/battery/drive facts.
        # Only a single explicit field year can contradict an observed name.
        # Missing/ambiguous field years retain the legacy observed-year evidence.
        declared_years = set(re.findall(
            r'(?<![0-9])(20[0-9]{2})(?![0-9])', str(base.get('年款', '') or '')))
        if len(declared_years) == 1:
            compatible_names = [name for name in name_candidates
                                if not (named_years := set(re.findall(
                                    r'(?<![0-9])(20[0-9]{2})\s*款', name)))
                                or named_years == declared_years]
            if compatible_names:
                name_candidates = compatible_names
        if name_candidates:
            # 先比"身份词有多少"、再比长度：光比长度会让**长而空**的名字盖掉短而富的名字，
            # 把电池/驱动这类只写在名字里的信息整块丢掉（实测 阿维塔07 74558 丢 39.05kWh 后驱）。
            base['车型名称'] = max(
                name_candidates,
                key=lambda n: (len(_sku_name_identity_tokens(
                    n, str(best.get('车系') or ''), str(best.get('品牌') or ''))), len(n)))
        for field in ('品牌', '车系', '年款', '车款ID'):
            if not str(base.get(field, '') or '').strip() or base.get(field) == '-':
                for row in group:
                    v = str(row.get(field, '') or '').strip()
                    if v and v != '-':
                        base[field] = row[field]
                        break
        # 品牌特殊处理：发布门禁 `autohome_publish_identity_valid` 要求品牌含中文
        # （`has_chinese(品牌)`，它挡的是 URL 片段式的假品牌）。实测折叠把汽车之家的
        # `道朗格`/`Lorinser罗伦士` 换成懂车帝侧的 `GMC`/`Lorinser`（富标签那行做主），
        # 于是 3 个**已发布身份**（车款ID 70672/70687/72803）在下游被门禁拒掉 ⇒ 发布面被悄悄缩小。
        # 中文写法本来就是该品牌的正式名，优先保留它既不丢信息也不会让任何行变得更不合法。
        if not re.search(r"[\u4e00-\u9fff]", str(base.get('品牌', '') or '')):
            for row in group:
                v = str(row.get('品牌', '') or '').strip()
                if v and v != '-' and re.search(r"[\u4e00-\u9fff]", v):
                    base['品牌'] = row['品牌']
                    break
        if any(not is_yiche_row(r) for r in group):
            yi_approved = next((r.get('易车上市状态') for r in group if is_yiche_row(r) and r.get('易车上市状态') == 'approved'), None)
            if yi_approved:
                if not base.get('易车上市状态'):
                    base['易车上市状态'] = yi_approved
            else:
                labels = [l for l in labels if '易车' not in l]
        # 折叠按"来源富集度"选一行做主 ⇒ 其余行独有的格值整列消失。10-17 在现网 33479 行上量到
        # 默认可见列里有 3323 格属于"做主那行空、族内**恰好一个**非空候选"（`measure_backfill_risk.py`），
        # 这一档回填只是把已经存在的真实值搬到它该在的位置；≥2 个互异候选的 21 格（集中在 `远程启动`）
        # 一律留空：在两个都成立过的值里挑一个写成事实，比留一个空白更难被用户发现。
        # 身份列不参与——它们各有各的保留规则（品牌还要过 `has_chinese` 发布门禁）。
        for col in {k for row in group for k in row}:
            if col in _MERGE_IDENTITY_COLS or not _cell_blank(base.get(col)):
                continue
            # X6（10-18 hy4 黑箱票的阻断件，构造面已复现）：簇里没有 approved 易车行时上面会把
            # `数据来源` 里的"易车"标签剥掉；此时若还把易车行独有的 `易车*` 列搬进 keeper，
            # 出口就成了"带易车身份却没有易车标签"的伪装同源行 ⇒ 一律不搬。
            if str(col).startswith('易车') and not any('易车' in str(l) for l in labels):
                continue
            cands = {str(row.get(col)).strip() for row in group if _backfill_candidate(row.get(col))}
            # 同义写法要先过**文件里已有口径**的归一再数（票面①-b）：`●` 与 `支持` 是同一个意思，
            # 按裸串算成 2 个候选 ⇒ 把"该补的一格"判成"有歧义、留空"（该补的没补）。
            # 归一只用来数集合大小，搬走的仍是原串 ⇒ 展示面不因此换写法。
            if len({canonical_compare(c) for c in cands}) != 1:
                continue
            if len(cands) == 1:
                pick = next(iter(cands))
            else:
                # 同义多写法：取这一簇里来源最富的那行原串（`_rank` 就是选主那把尺），可复现
                pick = next((str(r.get(col) or '').strip() for r in sorted(group, key=_rank, reverse=True)
                             if _backfill_candidate(r.get(col))), '')
            # keeper 这一格本来就已经写着同一个值 ⇒ 不写、也不登记"搬过"。
            # 为什么要单独挡：显式否定现在算候选，`-` vs `-` 会变成"单候选 = `-`"这条通路，
            # 而 `_unbackfilled` 会把登记过的格还原成 `''`（不是还原成 `-`）⇒ 一次"什么都没改"的
            # 回填反而把后续遍看到的 `-` 抹成空，折/不折判断就被我的修法自己动摇了。
            if str(base.get(col) or '').strip() == pick:
                continue
            for row in group:
                if str(row.get(col) or '').strip() == pick:
                    base[col] = row[col]
                    _note_backfilled(base, col)      # 搬来的值不参与后续折/不折判断，见 _sku_spec_conflict
                    break
        # X6（10-18 hy4 黑箱票的阻断件；构造面复现，根因不在回填而在 keeper 选择）：
        # `_rank` 并列时 keeper 可能就是那行**未 approved** 的易车行，上面把标签剥成"仅懂车帝"之后，
        # 出口会带着 `易车上市状态` 却没有易车标签 ⇒ 伪装同源（用户看不出这一行的身份来自谁）。
        # 规则：这一簇的存活标签里没有易车，易车身份列就一并撤掉（显式 approved 富集路径在上面，不受影响）。
        if labels and not any('易车' in str(l) for l in labels):
            for _c in [k for k in base if str(k).startswith('易车')]:
                base.pop(_c, None)
        base['数据来源'] = '、'.join(labels) if labels else base.get('数据来源', '')
        # D2：合并出口做一次规范化，同一来源集合只留一个标签（原子去重 + 固定顺序 +
        # 单原子回到 '仅X'）。否则 '汽车之家+懂车帝(车系级)' 与 '懂车帝+汽车之家'
        # 会按到达顺序并存，覆盖与双源核验计数随写法漂移。
        _dedupe_source_labels(base)
        if _observe_merge is not None:
            _observe_merge(group, base)
        return base

    for group in groups.values():
        if len(group) == 1:
            out.append(group[0])
            continue
        # ---- 护栏：组内**成对**判冲突，有冲突就分裂成子簇，而不是整组否决 ----
        # 1) 车款ID 都非空却不相等 ⇒ 源侧认定是两款车（如揽巡 75386/75387 同价同配置
        #    仍是两个车款）；
        # 2) 电池容量 / 驱动形式 / 能源类型 都非空却不相等 ⇒ 是真配置差异
        #    （实测昊铂HT 2024 有 80.06 与 83.3 两种电池包同价并存）。
        # 某一侧缺数据不算冲突：那是数据不全，不是差异。
        # 为什么不整组否决：实测阿维塔07 有两条 车系/年款/价/车型名称/车款ID 五项全同的行，
        # 只因同簇里混进一条电池容量不同的行就被一起拒绝 ⇒ 真重复留在了发布面上。
        #
        # `accept`（第三遍的物理簇判据）**改成逐子簇复核**（评审 D6）：旧写法在分裂之前
        # 就 `not accept(group) ⇒ 整簇原样带走`，于是"1 个 ID 行 + 2 个无 ID 行"里
        # 只要有一条与 ID 行驱动形式不同，本可以折的那一对也一起被留下 ⇒ 发布面多出真重复。
        cells = []
        for row in group:
            for cell in cells:
                if all(not _sku_spec_conflict([row, other]) for other in cell):
                    cell.append(row)
                    break
            else:
                cells.append([row])
        # 这一句**故意**读原行而不是 `_unbackfilled` 行（10-18 第二张 hy4 黑箱票 B1② 要求统一口径，
        # 监工侧复算后不采纳，理由与数都记在这里，改口径要两族先裁）：
        #   · 锚证据问的是"这一簇里出现过几个源侧主键"。上一遍把某个 ID 搬进 keeper 之后，
        #     那个 ID 就是这一行**代表过的源身份**之一，抹掉它等于让同一行同时并进两个不同车款ID 的簇。
        #   · 构造面可复算（`run_ticket_1802_b1.py`）：X(无ID,富标签)/Y(9001)/Z(9002,Pro)/V(无ID)
        #     现树 ⇒ 出口 3 行；把 identity 搬值登记 + 这一句改取还原行 ⇒ 出口 1 行，
        #     出口行的 `车款ID` 仍是 `9001`，却已经把自报 `9002` 的 Z 并进来了。
        #   · 现网面同批对照（`measure_identity_registration.py`）：短路 20288 ｜ 现树 20288
        #     ｜ 只登记 20284 ｜ 登记+改此句 20264 ⇒ 方向是**多折 24 行**，不是少折。
        #     这 24 行里"跨 ID 搭桥"具体几行，按 group_key 对齐的那把尺量不到
        #     （②恰恰改变了用来对齐的键）⇒ 这条是未量，不是零。
        group_ids = {str(r.get('车款ID') or '').strip() for r in group} - {'', '-'}
        for cluster in cells:
            if len(cluster) == 1:
                out.append(cluster[0])
                continue
            # 但**不许**把"无 ID 行"随意塞进两个以上同形状 ID 中的某一个（F3 原意）：
            # 物理身份完全相同的 66441/66442 两行之间，没有 ID 的那行归谁无从判断，
            # 分裂之后"先落到哪个算哪个"是**虚假归属**，不是折叠。
            if len(group_ids) >= 2 and any(
                    not str(r.get('车款ID') or '').strip() or str(r.get('车款ID') or '').strip() == '-'
                    for r in cluster):
                out.extend(cluster)
                continue
            if accept is not None and not accept(cluster):
                out.extend(cluster)
                continue
            out.append(_merge_cluster(cluster))
    # 车系写法归一：同一车系在数据里有"阿维塔 07"/"阿维塔07"两种写法，UI 会据此拆成
    # 两组。统一成出现次数更多的那种写法（并列时取更短的），让前端只看到一组。
    spellings: dict = {}
    for row in rows:
        key = _series_norm_key(str(row.get('车系', '') or ''))
        if not key:
            continue
        raw = str(row.get('车系', '') or '').strip()
        count, chosen = spellings.get(key, (0, ""))
        if count == 0:
            spellings[key] = (1, raw)
            continue
        spellings[key] = (count + 1, chosen if len(chosen) <= len(raw) else raw)
    for row in out:
        key = _series_norm_key(str(row.get('车系', '') or ''))
        if key and key in spellings:
            row['车系'] = spellings[key][1]
    return out
# 山寨/改装/杂牌品牌黑名单：极冷门非主流车厂，不在 Pages 保留






EXCLUDED_SHANZHAI_BRANDS = frozenset({






    "北汽泰普", "运良汽车", "运良", "车驰汽车", "卡驰汽车", "普曼·巅峰", "克蒂汽车",






    "颢屹汽车", "瑞一汽车", "仁拓博歌", "华夏领舰", "迈越", "星达", "斯达泰克",






    "巴菲特汽车", "国金汽车", "金龙礼宾车", "华东汽车", "龙程汽车", "卡尔森",






    "野马新能源",






})




















def clean_brand_field(row):






    """品牌字段清洗：去掉数据源标识（如 '吉利银河|高德' -> '吉利银河'）。"""






    brand = str(row.get('品牌', '') or '')






    if '|' in brand:






        row['品牌'] = brand.split('|')[0].strip()






    return row




















def is_excluded_brand(row):






    return str(row.get('品牌', '') or '').strip() in EXCLUDED_SHANZHAI_BRANDS













def annotate_ev_range(row):






    """纯电续航(km) 展示值规范化：不能充电的车写 0；多标准（NEDC/CLTC/WLTC/工信部）并存时标注标准。"""






    et = str(row.get('能源类型', '') or '')






    if et and not any(k in et for k in ('插电', '纯电', '增程', '电动')):






        row['纯电续航(km)'] = '0'






        return row






    std_fields = (






        ('CLTC', ('纯电续航(CLTC)', 'CLTC纯电续航(km)', 'CLTC纯电续航_km_', 'CLTC纯电续航里程(km)', 'CLTC纯电续航里程_km_')),






        ('NEDC', ('纯电续航(NEDC)', 'NEDC纯电续航(km)', 'NEDC纯电续航_km_', 'NEDC纯电续航里程(km)', 'NEDC纯电续航里程_km_')),






        ('WLTC', ('WLTC纯电续航里程(km)', 'WLTC纯电续航里程_km_', 'WLTC纯电续航(km)', 'WLTC纯电续航_km_')),






        ('工信部', ('工信部纯电续航里程(km)', '工信部纯电续航里程_km_', '工信部纯电续航(km)', '工信部纯电续航_km_')),






    )






    parts = []






    seen = set()






    for std, fields in std_fields:






        for f in fields:






            v = str(row.get(f, '') or '').strip()






            if v and v not in ('-', '999', '0'):






                m = re.search(r'\d+(?:\.\d+)?', v)






                if m and m.group(0) not in seen:






                    seen.add(m.group(0))






                    parts.append(f'{std}:{m.group(0)}')






                break






    if parts:






        row['纯电续航(km)'] = ' / '.join(parts)






    elif str(row.get('纯电续航(km)', '') or '').strip() == '999':






        row['纯电续航(km)'] = '0'






    return row













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





    all_rows = overlay_dealer_prices(all_rows)






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
    # SKU 级归并：identity_key 只按 (车系ID, 车型名称, 年款) 去重，同一 SKU 跨源/跨车系ID/
    # 异名写法各成一行（线上实测 14097 行里 1095 个车款ID 出现多行，涉 2327 行）。
    # dedupe_merged_rows 以前只在审计/校验脚本里被调用，合并主链路从未调用过——这里补上。
    before_sku = len(all_rows)
    all_rows = dedupe_merged_rows(all_rows)
    print(f"SKU 归并: {before_sku} -> {len(all_rows)} 行（移除 {before_sku - len(all_rows)} 条同 SKU 多行）")






    before_year_filter = len(all_rows)






    all_rows = [row for row in all_rows if keep_pages_year(row)]













    all_rows = [annotate_ev_range(row) for row in all_rows]






    all_rows = [clean_brand_field(row) for row in all_rows]






    all_rows = [row for row in all_rows if not is_excluded_brand(row)]






    all_rows = [row for row in all_rows if not excluded_by_crawl_scope(row)]






    print(f"CRAWL_SCOPE 级别排除(含MPV/房车): 剩余 {len(all_rows)}")






    print(f"2022年及以后车型: {len(all_rows)}/{before_year_filter}")













    filtered_rows = [row for row in all_rows if filter_car(row)]






    print(f"过滤后符合条件的车型: {len(filtered_rows)} 辆")






    analysis_dir = os.path.join(DIR, "docs", "analysis")






    os.makedirs(analysis_dir, exist_ok=True)






    write_json(os.path.join(analysis_dir, f"merge_stats_{today}.json"), {"date": today, "stats": MERGE_ANALYSIS_STATS})






    write_json(os.path.join(analysis_dir, f"disposition_ledger_{today}.json"), {"date": today, "ledger": MERGE_DISPOSITION_LEDGER})






    report_source_coverage(analysis_dir, today, all_rows, filtered_rows)






    if not filtered_rows:






        print("警告: 没有符合条件的车型")













    header = collect_fields(all_rows)













    merged_csv_path = os.path.join(DIR, f"merged_{today}.csv")






    merged_json_path = os.path.join(DIR, f"merged_{today}.json")






    write_csv(merged_csv_path, all_rows, header)






    write_json(merged_json_path, all_rows)













    filtered_csv_path = os.path.join(DIR, f"filtered_cars_{today}.csv")






    filtered_json_path = os.path.join(DIR, f"filtered_cars_{today}.json")






    filtered_rows = narrow_pages_rows(filtered_rows)
    write_csv(filtered_csv_path, filtered_rows, header)






    write_json(filtered_json_path, filtered_rows)













    print("完成")






    print(f"  全部合并: {merged_csv_path}")






    print(f"  全部合并: {merged_json_path}")






    print(f"  符合条件车型: {filtered_csv_path}")






    print(f"  符合条件车型: {filtered_json_path}")




















if __name__ == "__main__":






    main()

"""Pages 筛选默认值不许在工作流里硬丢行（负责人裁定 2026-10-12 复核现网后重申）。

现网读数（2026-10-11T20:45:01Z manifest，浏览器内实测，口径见 npc-redtests/verify-live-pages-defects.js）：
  latest 17752 行 / filtered 1025 行；
  按源保留率 易车 94/5104=1.8%、懂车帝 750/9780=7.7%、汽车之家 708/7907=9.0%；
  filtered 里 **燃油车 0 台**（能源类型含"汽油"且不含插混/增程的行一条都没有）。

机制（已定位到行）：
  `config/filter_conditions.json` 的 conditions 给了区间默认值
  （zero_to_hundred 0–7s、ev_range ≥150km、top_speed ≥180km/h，另有 feature/pagesFeature 条件），
  `scripts/merge_data.py:6935 FILTER_CONDITIONS` 读进来，
  `:8172 filter_car(row)` 逐条判定，`:17278` 用列表推导**直接丢弃**不合格行。
  ⇒ 纯油车的 `纯电续航(km)` 被 `annotate_ev_range` 规范化成 0（见 :16509 那段），
    于是永远过不了 `ev_range ≥150`；百公里加速 >7s 的车同理被 `zero_to_hundred` 砍掉。
  ⇒ 这些本是**前端可调的默认筛选**（同一份 JSON 里就有 defaultVisibleColumns/defaultAllowedLevels
    给前端用），却在工作流里变成了硬过滤，等于替用户做决定并把数据源删掉。

负责人口径（逐条对应下面的断言）：
  1. 「工作流合并数据时把所有油车都丢弃也不对啊」⇒ 油车不得因能源/续航/加速默认区间被丢；
  2. 「筛选应是前端可调默认值而非工作流硬丢弃」⇒ 缺字段不许当成"不合格"；
  3. 「不要 MPV」⇒ 车型范围排除（MPV/房车/货车/皮卡等）**必须继续生效**，不许顺手放宽；
  4. 严格口径「必须有源证明为有」不变——本判据只要求"不因缺证据而丢行"，不要求填占位值。
"""

from __future__ import annotations

import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _md():
    spec = importlib.util.spec_from_file_location("merge_data", ROOT / "scripts" / "merge_data.py")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except SystemExit:  # pragma: no cover - module-level CLI guard
        pass
    return module


MD = _md()


def _row(**kw):
    base = {
        "数据来源": "仅汽车之家",
        "品牌": "测试品牌",
        "车系": "测试车系",
        "车系ID": "1",
        "车型名称": "2026款 测试",
        "年款": "2026",
        "官方指导价": "18.00万",
    }
    base.update(kw)
    return base


# 现网真实形态的样例：长安启源Q05 26款 405km Air（易车、approved、有价、有续航）字段齐全却被丢；
# 这里用最小行复现两类丢弃原因。
FUEL_CAR = _row(**{
    "车型名称": "2026款 2.0T 豪华型",
    "级别": "中型车",
    "能源类型": "汽油",
    "车身结构": "4门5座三厢车",
    "座位数(个)": "5",
    "最高车速(km/h)": "210",
    "百公里加速(s)": "8.5",
    "纯电续航(km)": "0",          # annotate_ev_range 对不能充电的车就是写 0
})

EV_MISSING_OPTIONAL_FIELDS = _row(**{
    "车型名称": "2026款 620km 后驱版",
    "级别": "中大型SUV",
    "能源类型": "纯电动",
    "纯电续航(km)": "620",
    # 故意不给 百公里加速 / 最高车速：易车与部分汽车之家行就是这么残缺
})

FULLY_GOOD_EV = _row(**{
    "车型名称": "2026款 600km 四驱版",
    "级别": "中大型SUV",
    "能源类型": "纯电动",
    "纯电续航(km)": "600",
    "百公里加速(s)": "3.9",
    "最高车速(km/h)": "220",
})

MPV_ROW = _row(**{
    "车型名称": "2026款 7座 旗舰版",
    "级别": "MPV",
    "车身结构": "5门7座MPV",
    "能源类型": "插电混合",
    "座位数(个)": "7",
})


def test_fuel_car_survives_pages_filter():
    """油车不许被能源/续航/加速默认区间判死——负责人明说过"把所有油车都丢弃也不对"。"""
    assert MD.filter_car(dict(FUEL_CAR)) is True, (
        "纯燃油车被工作流硬丢弃：filter_conditions 的 ev_range/zero_to_hundred 默认值被当成了过滤条件"
    )


def test_missing_optional_fields_do_not_drop_a_row():
    """缺证据 ≠ 不合格：没有 百公里加速/最高车速 的行必须留在数据里，前端要筛再筛。"""
    assert MD.filter_car(dict(EV_MISSING_OPTIONAL_FIELDS)) is True, (
        "字段缺失被当成不满足区间条件而丢行（易车行大量因此消失，保留率只剩 1.8%）"
    )


def test_good_ev_still_survives():
    """反向兜底：不许把 filter_car 改成恒真来糊弄前两条。"""
    assert MD.filter_car(dict(FULLY_GOOD_EV)) is True


def test_mpv_still_excluded_by_crawl_scope():
    """车型范围口径不许放宽：MPV/房车/货车/皮卡仍要被排除。

    断的是**处置动作**而不是"filter_car 返回 False"——MPV 在 filter_car 上返回 False 只是因为
    它缺 纯电续航，属于假绿；真正的范围排除口径在 `excluded_by_crawl_scope`（对全部数据源生效）。
    """
    assert MD.excluded_by_crawl_scope(dict(MPV_ROW)) is True, "MPV 排除被削弱了——负责人明确不要 MPV"


def test_per_source_retention_is_not_systematically_skewed():
    """按源保留率不变式：混合 12 条各源行，至少 8 条要留在数据里，且最差源保留率 ≥ 最好源的 60%。

    下限是防"把 filter_car 改成全丢/全留来糊弄比值"：现网是 1.8% vs 9.0%（比值 0.20）所以这条红；
    修好后各源差异只应来自车型范围（MPV 等），不该来自字段残缺。
    """
    fixtures = []
    for src in ("仅懂车帝", "仅汽车之家", "仅易车"):
        for i in range(4):
            fixtures.append(_row(**{
                "数据来源": src,
                "车系": "测试车系%s%d" % (src, i),
                "车型名称": "2026款 %d 型" % i,
                "级别": "中大型SUV",
                "能源类型": "纯电动" if i % 2 else "汽油",
                "纯电续航(km)": "600" if i % 2 else "0",
                "座位数(个)": "5",
                "车身结构": "5门5座SUV",
            }))
    kept = [r for r in fixtures if MD.filter_car(dict(r))]
    assert len(kept) >= 8, (
        "12 条各源正常行只留下 %d 条：工作流在用前端默认筛选硬丢数据（油车/缺字段行被砍光）" % len(kept))

    def rate(src):
        total = [r for r in fixtures if src in str(r["数据来源"])]
        hit = [r for r in kept if src in str(r["数据来源"])]
        return len(hit) / max(1, len(total))

    rates = {s: rate(s) for s in ("仅懂车帝", "仅汽车之家", "仅易车")}
    worst, best = min(rates.values()), max(rates.values())
    assert best == 0 or worst >= 0.6 * best, "各源保留率系统性偏斜 %s（最差/最好=%.2f < 0.6）" % (
        rates, worst / best if best else 0)


def test_user_price_default_is_never_a_saved_data_deletion_rule():
    for price in ("35.8万", "80万", "0", "-"):
        record = dict(FULLY_GOOD_EV, 官方指导价=price)
        assert MD.filter_car(record) is True, "UI price budget cannot remove source records"

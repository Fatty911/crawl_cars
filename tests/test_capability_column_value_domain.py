"""能力列（远程启动 等）的**取值域守卫**判据。

现网实测（filtered 面 manifest 2026-10-14T04:16Z，13388 行 + latest 面前 3 分片 4283 行）：

  `远程启动` 这一列有 **2415 行**装的是发动机规格（`3.0T 354马力 V6` / `1.5T 167马力 L4`），
  另有 **8 行**装 `○ 暂无价格`（价格）、**5 行**装 `纯电动`（能源类型）。
  合法取值域实测为：`标配` 1728 / `●` 1315 / `支持` 52 / `选装` 27。
  latest 面里 47 行的 `远程启动` 与同行 `发动机` **逐字相同** ⇒ 是**重复写入**，不是上游串位；
  而 filtered 面**根本没有发动机类列**（列名里含"发动机/动力"的列 = 0 个），
  于是发动机规格只剩这一处错误出口。

这与负责人点名的口径同源：「无钥匙启动和远程启动是两种不同的功能」——
能力列的**含义**由列名固定，值必须落在该列的取值域内，外域值不许混进来。

这些用例当前为红（main 里没有任何取值域守卫：
`dir(merge_data)` 与 `dir(prepare_pages_payload)` 里搜 `domain|valid_value|value_guard|foreign` 全空）。
"""

from __future__ import annotations

import importlib.util
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except SystemExit:  # pragma: no cover - module-level CLI guard
        pass
    return module


PP = _load("prepare_pages_payload")
MD = _load("merge_data")

ENGINE = "3.0T 354马力 V6"
CAPABILITY_COL = "远程启动"


def _guard():
    """守卫必须是真函数，不能只存在于文档字符串里。"""
    names = [n for n in dir(PP) + dir(MD)
             if re.search(r"(capability_value_guard|value_domain_guard|_guard_capability)", n)]
    return names[0] if names else None


def test_guard_exists_and_is_callable():
    fn = _guard()
    assert fn is not None, (
        "main 里没有能力列取值域守卫（实测 dir() 搜 domain/guard/foreign 全空）："
        "`远程启动` 里 2415 行发动机规格没人拦"
    )
    assert callable(getattr(PP, fn, None) or getattr(MD, fn, None)), "守卫符号存在但不可调用"


def test_invalid_single_source_value_is_cleared_but_row_survives():
    """整列非法（无前缀的发动机规格）⇒ 清掉该列值，**不许丢行**。"""
    fn = _guard()
    guard = getattr(PP, fn, None) or getattr(MD, fn, None)
    row = {"车系": "奥迪SQ5", "年款": "2024", "车型名称": "奥迪SQ5 2024款 3.0 TFSI quattro",
           CAPABILITY_COL: ENGINE, "官方指导价": "59.88万"}
    out, stats = _call(guard, [dict(row)])
    assert out and len(out) == 1, "守卫把行弄丢了（行全是硬口径）"
    assert ENGINE not in str(out[0].get(CAPABILITY_COL, "")), "发动机规格仍在能力列里"
    assert out[0].get("官方指导价") == "59.88万", "守卫动到了别的列（只许处理越界的取值）"
    assert _has_counter(stats, "远程启动") or _has_counter(stats, CAPABILITY_COL), (
        "剔除没有留痕：必须报数（观测进制品，不能只在展示层）"
    )


def test_one_bad_source_does_not_evict_the_good_one():
    """`汽车之家:3.0T 354马力 V6|懂车帝:标配` ⇒ **只剔非法源**，合法源的 `标配` 必须留下。

    这条为什么关键：源前缀在这里反过来是有用的证据——它指出是哪一个源写错了列。
    整列清空会把懂车帝给对的值也丢掉，等于用一种错盖另一种错。
    """
    fn = _guard()
    guard = getattr(PP, fn, None) or getattr(MD, fn, None)
    row = {"车系": "启辰大V DD-i", "年款": "2025", CAPABILITY_COL:
           f"汽车之家:{ENGINE}|懂车帝:标配"}
    out, _stats = _call(guard, [dict(row)])
    text = str(out[0].get(CAPABILITY_COL, ""))
    assert ENGINE not in text, "非法源没被剔掉：%r" % text
    assert "标配" in text, "合法源的值被连带丢了：%r（应为 `懂车帝:标配`）" % text
    assert "懂车帝" in text, "合法源的留痕被抹掉：%r" % text


def test_foreign_domains_are_all_covered():
    """能源类型与**裸**价格文本不许留在能力列里。

    更正（10-14 自查，监工自己写错过的地方）：`○ 暂无价格` **不是**外域值——
    本仓 `prepare_pages_payload.py:200` 写明它是懂车帝状态列的固有写法
    （`○ 暂无价格` = 选装但无报价），并有 `_OPTIONAL_PREFIXES = ("○","◯","〇")` 的判定逻辑。
    判据若要求剔除它，就会把合法的"选装"信号删掉 ⇒ 那是**修坏**，不是修好。
    所以这里只查：没有状态符号前缀的裸 `暂无价格`，以及能源类型/增程器规格。
    """
    fn = _guard()
    guard = getattr(PP, fn, None) or getattr(MD, fn, None)
    for bad in ("暂无价格", "纯电动", "增程器 160马力"):
        out, _s = _call(guard, [{CAPABILITY_COL: bad, "车系": "测试S", "年款": "2026"}])
        assert bad not in str(out[0].get(CAPABILITY_COL, "")), (
            "外域值 %r 仍在能力列里（实测这些形状都出现过）" % bad
        )


def test_source_status_token_is_preserved():
    """红线：`○ 暂无价格` 是源自己的状态写法（选装但无报价），必须**逐字保留**。

    这条是给监工自己上的锁：上一版判据把它当价格串位要求剔除，
    照做会删掉真信息——负责人口径是"必须有源证明"，而"选装"正是源给出的一种证明状态。
    """
    fn = _guard()
    guard = getattr(PP, fn, None) or getattr(MD, fn, None)
    for keep in ("○ 暂无价格", "○", "● 暂无价格"):
        out, _s = _call(guard, [{CAPABILITY_COL: keep, "车系": "测试S", "年款": "2026"}])
        assert str(out[0].get(CAPABILITY_COL, "")) == keep, (
            "源状态写法被误删：%r -> %r（应逐字保留）" % (keep, out[0].get(CAPABILITY_COL)))


def test_legal_values_are_untouched():
    """红线：守卫不许把好值改了。合法取值域实测为 标配/●/支持/选装，多值能力写法原样保留。"""
    fn = _guard()
    guard = getattr(PP, fn, None) or getattr(MD, fn, None)
    for good in ("标配", "●", "支持", "选装", "○", "加热 / 通风",
                 "汽车之家:遥控钥匙 / 蓝牙钥匙|懂车帝:智能遥控钥匙"):
        out, _s = _call(guard, [{CAPABILITY_COL: good, "车系": "测试S", "年款": "2026"}])
        assert str(out[0].get(CAPABILITY_COL, "")) == good, (
            "合法值被改动：%r -> %r（守卫只该管越域值）" % (good, out[0].get(CAPABILITY_COL))
        )


def test_rules_are_config_driven_not_hardcoded():
    """规则必须来自配置或集中的表，**不许**把车系/品牌/车型名硬编码成白名单。

    本仓已被"默认筛选值被当硬丢弃"和"contains_chinese(车系) 误删特斯拉族"咬过两次；
    按车系放行等于把缺陷变成另一批缺陷。
    """
    blob = ""
    for name in ("prepare_pages_payload.py", "merge_data.py"):
        p = ROOT / "scripts" / name
        if p.exists():
            blob += p.read_text(encoding="utf-8")
    assert not re.search(r"(奥迪SQ5|启辰大V|揽胜|阿斯顿).{0,40}(远程启动|capability)", blob), (
        "守卫里出现了按车系/品牌放行的写法（必须是按列的取值域规则）"
    )
    cfg = ROOT / "config"
    hits = []
    if cfg.exists():
        for p in cfg.glob("*.json"):
            if re.search(r"(value_domain|取值域|capability_value)", p.read_text(encoding="utf-8")):
                hits.append(p.name)
    inline = bool(re.search(r"(CAPABILITY_VALUE|VALUE_DOMAIN|_VALUE_DOMAIN)", blob))
    assert hits or inline, (
        "既没有配置文件里的取值域段，也没有集中定义的域表 ⇒ 规则散在分支里无法复核"
    )


def test_guard_is_wired_into_the_publish_path():
    """调用边必须存在：发布面的行级出口要真的经过守卫（"存在函数"不等于"会被执行"）。"""
    src = (ROOT / "scripts" / "prepare_pages_payload.py").read_text(encoding="utf-8")
    fn = _guard()
    assert fn, "没有守卫符号，谈不上接线"
    call_sites = [ln for ln in src.splitlines()
                  if re.search(r"\b%s\s*\(" % re.escape(fn), ln) and "def " not in ln]
    assert call_sites, "守卫在 prepare_pages_payload.py 里从没被调用（只是定义了）"


def _call(guard, rows):
    """兼容两种签名：返回 (rows, stats) 或就地修改后返回 rows。"""
    out = guard(rows)
    if isinstance(out, tuple) and len(out) == 2:
        return list(out[0]), out[1]
    if isinstance(out, list):
        return out, {}
    raise AssertionError("守卫返回形状无法识别：%r（要求 (rows, stats) 或 rows）" % type(out))


def _has_counter(stats, col):
    try:
        blob = str(stats)
    except Exception:
        return False
    return bool(stats) and (col in blob or "能力列" in blob or "capability" in blob.lower())

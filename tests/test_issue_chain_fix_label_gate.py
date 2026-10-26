"""fix 标签闸必须真的是闸（判据，当前在 origin/main 上必须红）。

**缺陷现状（origin/main `.cnb.yml` 1417-1418 实测原文）**：

    - name: 检查fix标签
      script: echo "$CNB_ISSUE_LABELS" | grep -q 'fix' || exit 0

`|| exit 0` 把"没有 fix 标签"这条失败吞成成功 ⇒ 这一段永远不会让链变红，
"Issue 带不带 fix 标签"与"NPC 是否开工"完全脱钩：任何 Issue 都被当成派发单，
而验收面上看起来一切正常。这是用户点名的五个已知缺陷里的第 ④ 个。

**为什么这一版才敢写判据（10-12 11:30 联网查证 + 本仓既有先例）**：
CNB stage 级支持 `if`（Shell 条件）与 `exports`（`##[set-output k=v]` → 环境变量），
本仓 `.cnb.yml` 已经在用这个形状（`NPC免费额度前置门禁` set-output `budget_state=RUN` +
`exports: {budget_state: NPC_BUDGET_STATE}`，下游 `AI-修复-第1轮` 用
`if: '[ "$NPC_BUDGET_STATE" = "RUN" ]'`）。
⇒ 合规修法有现成先例可抄，判据**可满足**：
  1) 闸把结论 set-output 出去（RUN / SKIP），**不许**用 `|| exit 0`/`|| true` 吞失败；
  2) NPC 干活那一段用 `if` 挂在这个变量上 ⇒ 无标签时是 skipped（看得见），而不是"跑了但什么都没干"；
  3) `if` 引用的变量必须由这个闸自己 exports（防止拿别的变量的绿冒充）。

红样/绿样都是**结构变异**（改 YAML 节点，不改注释、不改 prompt 文本），
并显式断言"变异后判据确实变红 / 合规版确实变绿"，见 `_check_*` 三个入口。
本地跑监工自己的副本时可以指别的文件：环境变量 `CNB_YML` 覆盖默认 `<repo>/.cnb.yml`。
"""

from __future__ import annotations

import copy
import os
import pathlib
import re
import shutil
import subprocess

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
PATH = pathlib.Path(os.environ.get("CNB_YML") or (ROOT / ".cnb.yml"))
CFG = yaml.safe_load(PATH.read_text(encoding="utf-8")) or {}

GATE_NAME = "检查fix标签"
AGENT_HINT = "AI-Issue驱动修复"
DEGENERATE = re.compile(r"\|\|\s*(?:exit\s+0|true)\b")


def _issue_jobs(cfg):
    out: list = []
    for key, val in ((cfg.get("$") or {}) or {}).items():
        if str(key).startswith("issue"):
            out.extend(val if isinstance(val, list) else [val])
    return out


def _stages(job):
    if not isinstance(job, dict):
        return []
    out = []
    for k in ("stages", "failStages"):
        v = job.get(k)
        if isinstance(v, list):
            out.extend([s for s in v if isinstance(s, dict)])
    return out


def _all_stages(cfg):
    out = []
    for job in _issue_jobs(cfg):
        out.extend(_stages(job))
    return out


def _script(stage):
    s = stage.get("script")
    if isinstance(s, dict):
        s = s.get("run") or ""
    if isinstance(s, list):
        s = "\n".join(str(x) for x in s)
    return str(s or "")


def _live(script):
    return "\n".join(l for l in script.splitlines() if not l.strip().startswith("#"))


def _find(stages, name):
    for s in stages:
        if name in str(s.get("name") or ""):
            return s
    return None


def _gate_vars(stages):
    gate = _find(stages, GATE_NAME)
    exports = (gate or {}).get("exports")
    if not isinstance(exports, dict):
        return gate, []
    return gate, [str(v) for v in exports.values()]


def check_no_degenerate_gate(cfg):
    """闸在、且不吞失败、且把裁决交出去。"""
    gate, variables = _gate_vars(_all_stages(cfg))
    assert gate is not None, "issue 链里没有名为 %s 的闸" % GATE_NAME
    live = _live(_script(gate))
    assert live.strip(), "%s 的 script 是空的" % GATE_NAME
    assert not DEGENERATE.search(live), (
        "%s 仍是恒通过假闸（`|| exit 0` 把缺标签吞成成功）：%s" % (GATE_NAME, live.strip()[:180]))
    assert ("set-output" in live) or variables, (
        "%s 没把结论交出去（无 ##[set-output …] 且无 exports），下游无法据此条件执行" % GATE_NAME)


def check_gate_exports_variable(cfg):
    gate, variables = _gate_vars(_all_stages(cfg))
    assert gate is not None, "issue 链里没有名为 %s 的闸" % GATE_NAME
    assert variables, "%s 必须 exports 一个环境变量（照抄本仓 budget_state/NPC_BUDGET_STATE 的形状）" % GATE_NAME
    bad = [v for v in variables if not re.match(r"^[A-Z][A-Z0-9_]*$", v)]
    assert not bad, "exports 的目标要写成环境变量名（大写下划线），实际=%s" % bad


def check_agent_guarded_by_gate(cfg):
    stages = _all_stages(cfg)
    _, variables = _gate_vars(stages)
    agent = _find(stages, AGENT_HINT)
    assert agent is not None, "issue 链里没有 %s 段" % AGENT_HINT
    cond = str(agent.get("if") or "").strip()
    assert cond, "%s 没有 if 守卫：无 fix 标签时它照样开工，闸等于装饰" % AGENT_HINT
    assert any(v and v in cond for v in variables), (
        "%s 的 if=%r 没引用 %s 自己导出的变量 %s ⇒ 拿别人的绿冒充" % (AGENT_HINT, cond, GATE_NAME, variables))


def _mutate(cfg, gate_script=None, drop_exports=False, drop_if=False):
    got = copy.deepcopy(cfg)
    for st in _all_stages(got):
        name = str(st.get("name") or "")
        if GATE_NAME in name:
            if gate_script is not None:
                st["script"] = gate_script
            if drop_exports:
                st.pop("exports", None)
        if drop_if and AGENT_HINT in name:
            st.pop("if", None)
    return got


def _compliant_shape():
    """绿样：本仓既有先例的同形写法（不是凭空发明的字段）。"""
    good = copy.deepcopy(CFG)
    for st in _all_stages(good):
        name = str(st.get("name") or "")
        if GATE_NAME in name:
            st["script"] = (
                'if echo "$CNB_ISSUE_LABELS" | grep -q "fix"; then\n'
                '  echo "##[set-output fix_gate=RUN]"\n'
                "else\n"
                '  echo "##[set-output fix_gate=SKIP]"\n'
                "  echo \"无 fix 标签：跳过 NPC 修复段（skipped 可见，不再恒通过）\"\n"
                "fi\n"
            )
            st["exports"] = {"fix_gate": "NPC_FIX_GATE"}
        if AGENT_HINT in name:
            st["if"] = '[ "$NPC_FIX_GATE" = "RUN" ]'
    return good


def test_current_yaml_state_is_reported():
    """把当前 .cnb.yml 的三条判据逐条跑出结果（在 origin/main 上应当是红的）。"""
    fails = []
    for fn in (check_no_degenerate_gate, check_gate_exports_variable, check_agent_guarded_by_gate):
        try:
            fn(CFG)
        except AssertionError as e:
            fails.append("%s: %s" % (fn.__name__, str(e)[:120]))
    assert not fails, "判据在 %s 上未通过（当前形状）：\n  - %s" % (PATH, "\n  - ".join(fails))


def test_green_sample_passes_all_three():
    """可满足性自校：按本仓既有先例改出的绿样必须三条全过（否则判据不可满足，就是废闸）。"""
    good = _compliant_shape()
    for fn in (check_no_degenerate_gate, check_gate_exports_variable, check_agent_guarded_by_gate):
        fn(good)


def test_red_sample_degate_still_turns_red():
    """红样 1：把 `|| exit 0` 塞回去 ⇒ 第一条必须干净地变红（不是崩）。"""
    bad = _mutate(_compliant_shape(), gate_script='echo "$CNB_ISSUE_LABELS" | grep -q "fix" || exit 0',
                  drop_exports=True)
    try:
        check_no_degenerate_gate(bad)
    except AssertionError:
        return
    raise AssertionError("恒通过形状没被判据抓住 ⇒ 判据无效")


def test_red_sample_missing_export_turns_red():
    """红样 2：闸合规但没有 exports ⇒ 第二条必须变红。"""
    bad = _mutate(_compliant_shape(), drop_exports=True)
    try:
        check_gate_exports_variable(bad)
    except AssertionError:
        return
    raise AssertionError("没有 exports 的闸没被抓 ⇒ 判据无效")


def test_red_sample_missing_if_turns_red():
    """红样 3：只改闸、不给 agent 段加 if（半修）⇒ 第三条必须变红。"""
    bad = _mutate(_compliant_shape(), drop_if=True)
    try:
        check_agent_guarded_by_gate(bad)
    except AssertionError:
        return
    raise AssertionError("半修（闸改守卫没改）没被抓 ⇒ 判据无效")


def test_red_sample_foreign_variable_turns_red():
    """红样 4：if 引用别的变量（拿 NPC_BUDGET_STATE 的绿冒充）⇒ 必须变红。"""
    bad = copy.deepcopy(_compliant_shape())
    for st in _all_stages(bad):
        if AGENT_HINT in str(st.get("name") or ""):
            st["if"] = '[ "$NPC_BUDGET_STATE" = "RUN" ]'
    try:
        check_agent_guarded_by_gate(bad)
    except AssertionError:
        return
    raise AssertionError("借别变量的绿没被抓 ⇒ 判据无效")


# ---------------------------------------------------------------------------
# 行为回归：从 CFG 取出**当前**闸脚本，用真实 POSIX shell 跑，按
# CNB_ISSUE_LABELS（官方定义：逗号分隔的名称列表）判定 RUN/SKIP。
# 期望独立写成“按逗号分隔后是否有恰好等于 fix 的名称”，不复用被测脚本的判据。
# ---------------------------------------------------------------------------

def _gate_script():
    gate = _find(_all_stages(CFG), GATE_NAME)
    assert gate is not None, "issue 链里没有名为 %s 的闸" % GATE_NAME
    script = _script(gate)
    assert script.strip(), "%s 的 script 是空的" % GATE_NAME
    return script


def _posix_shell():
    if os.name == "nt":
        candidates = [
            pathlib.Path(r"C:\Program Files\Git\bin\bash.exe"),
            pathlib.Path(r"C:\Program Files\Git\usr\bin\sh.exe"),
            pathlib.Path(r"C:\Program Files (x86)\Git\bin\bash.exe"),
        ]
        found = [str(p) for p in candidates if p.is_file()]
        if not found:
            bash = shutil.which("bash")
            if bash:
                found.append(bash)
    else:
        found = [p for p in (shutil.which("sh"), shutil.which("bash")) if p]
    assert found, (
        "找不到 POSIX shell：Windows 需要已安装的 Git bash，Linux 需要 sh/bash；"
        "本测试不允许 skip，缺少 shell 直接判失败")
    return found[0]


def _run_gate(script, labels, cwd):
    env = dict(os.environ)
    env.pop("CNB_ISSUE_LABELS", None)
    if labels is not None:
        env["CNB_ISSUE_LABELS"] = labels
    proc = subprocess.run(
        [_posix_shell(), "-c", script],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    assert proc.returncode == 0, (
        "闸脚本非零退出：stdout=%r stderr=%r" % (proc.stdout, proc.stderr))
    return proc.stdout


def _decision(stdout):
    got = re.findall(r"##\[set-output\s+fix_gate=(RUN|SKIP)\]", stdout)
    assert len(got) == 1, "期望恰好一条 fix_gate set-output，实际 stdout=%r" % stdout
    return got[0]


def _assert_gate(labels, expected, cwd):
    decision = _decision(_run_gate(_gate_script(), labels, cwd))
    assert decision == expected, (
        "CNB_ISSUE_LABELS=%r 时闸判为 %s，期望 %s（逗号分隔名称中是否有恰好 fix）"
        % (labels, decision, expected))


def test_actual_gate_skips_missing_and_empty_labels(tmp_path):
    """空/missing 都是无标签：missing 不设变量，empty 设为空串，均 SKIP。"""
    _assert_gate(None, "SKIP", tmp_path)
    _assert_gate("", "SKIP", tmp_path)


def test_actual_gate_skips_triage_only(tmp_path):
    """triage 不是 fix。"""
    _assert_gate("triage", "SKIP", tmp_path)


def test_actual_gate_runs_for_exact_fix(tmp_path):
    """恰好 fix 才 RUN。"""
    _assert_gate("fix", "RUN", tmp_path)


def test_actual_gate_runs_for_fix_member_in_csv(tmp_path):
    """逗号分隔列表中任一名称恰好是 fix 即 RUN，与位置无关。"""
    _assert_gate("triage,fix", "RUN", tmp_path)
    _assert_gate("fix,urgent", "RUN", tmp_path)


def test_actual_gate_skips_near_miss_names(tmp_path):
    """prefix/hotfix/fixme/not-fix/fix-disabled 都只是包含 fix 子串，不是成员 fix。"""
    for labels in ("prefix", "hotfix", "fixme", "not-fix", "fix-disabled"):
        _assert_gate(labels, "SKIP", tmp_path)


def test_actual_gate_treats_injection_style_labels_as_data(tmp_path):
    """注入样式标签只能作为 DATA 参与比较，不得被 shell 执行。"""
    marker = tmp_path / "gate-was-executed"
    labels = "fix; touch gate-was-executed,$(touch gate-was-executed)"
    out = _run_gate(_gate_script(), labels, tmp_path)
    assert _decision(out) == "SKIP", (
        "含分号/命令替换的标签不是恰好 fix，应为 SKIP；stdout=%r" % out)
    assert not marker.exists(), "标签内容被 shell 执行了：出现 %s" % marker

    marker2 = tmp_path / "gate-was-executed-2"
    out = _run_gate(_gate_script(), "fix,$(touch gate-was-executed-2)", tmp_path)
    assert _decision(out) == "RUN", (
        "存在恰好 fix 成员时应 RUN；stdout=%r" % out)
    assert not marker2.exists(), "RUN 分支把兄弟标签当命令执行了：出现 %s" % marker2

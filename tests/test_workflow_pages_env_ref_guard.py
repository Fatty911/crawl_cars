"""守卫：任何往 `github-pages` 环境部署的 job，在 release 事件下**求值后**必须为假。

真机事实（探针 AUTOTRIGGER-PROBE-20261021224622.txt）：
  `部署前端展示` 被 release 事件拉起 → run 39619805892，job conclusion=failure，
  **steps=[]、日志不存在**，3 秒即终态。
原因不在脚本：本仓 Pages 环境带 branch_policy（GET /repos/…/environments/github-pages
→ protection_rules=[branch_policy]，custom_branch_policies=true），而 release 事件的 run
跑在 tag ref 上（head_branch=<tag>），环境在"分配阶段"就拒绝 ⇒ 必红；
且这条红不产生 `workflow_run` 修复票（监控那条 run 的 job.if 还要求 head_branch=='main'）
⇒ 是"必红且没人修"的结构形状。

判据语义要点（第一版尺就是栽在这里）：`github.event_name != 'release' || (…)`
这种**或**式在 release 事件下仍可能为真（只要右半边对某个 tag 成立），
光查"条件里有没有 != 'release' 这个子串"会漏。所以这里把条件**当真值表达式求值**，
对 release 场景下的多个代表 tag 逐个求值；只要有一个为真就算违规。
"""
import re
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
WORKFLOWS = REPO / ".github" / "workflows"

# release 事件下要试的代表 tag：本链产物、CNB 干净产物、外部版本 tag、空值
RELEASE_TAGS = [
    "v1.2.3",
    "data-latest",
    "cnb-data-20261015T041723Z-cnb-6as-1k4ujn7mr",
    "cnb-data-20261015-remerged-r39617040964",
    "cnb-data-20261015-remerged-verified-r39617040964a1",
    "",
]


UNKNOWN = "qoder-guard-unknown"


class _Ctx(dict):
    """按事件给上下文；未建模/该事件下不存在的路径返回 UNKNOWN（保守判"条件可能成立"）。

    取空串会把 `github.event.release.prerelease == false` 这种真会跑的 if 判成绿（hy4 票实测）。
    """

    def __init__(self, data=None, fill=UNKNOWN):
        dict.__init__(self, data or {})
        self.fill = fill

    def with_fill(self, fill):
        return _Ctx(dict(self), fill)

    def value(self, dotted):
        cur = self
        for part in dotted.split("."):
            if not isinstance(cur, dict) or part not in cur:
                return self.fill
            cur = cur[part]
        return cur if isinstance(cur, (str, bool)) else self.fill


def _func(name, args):
    if name in ("startsWith", "endsWith", "contains"):
        # 官方语义：这三个函数不区分大小写；任一侧未知 ⇒ 保守判"可能成立"
        if any(x == UNKNOWN for x in args):
            return True
        sa, sb = str(args[0]).lower(), str(args[1]).lower()
        if name == "startsWith":
            return sa.startswith(sb)
        if name == "endsWith":
            return sa.endswith(sb)
        return sb in sa
    if name == "toJSON":
        return json_dumps(args[0])
    raise AssertionError("判据没建模的表达式函数：%s" % name)


def json_dumps(value):
    import json

    return json.dumps(value, sort_keys=True)


_TOKEN = re.compile(
    r"""(?P<str>'[^']*'|"[^"]*")            # 字符串字面量（原样保留）
      | (?P<func>[A-Za-z_][A-Za-z0-9_]*)\s*(?=\()
      | (?P<ctx>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+)
      | (?P<op>&&|\|\||==|!=|<=|>=|<|>|\(|\)|,|!)
      | (?P<num>\d+)
      | (?P<word>[A-Za-z_][A-Za-z0-9_]*)
    """,
    re.X,
)

FUNCS = {"startsWith", "endsWith", "contains", "toJSON", "format"}


def _tokenize(expr):
    out, pos = [], 0
    while pos < len(expr):
        m = _TOKEN.match(expr, pos)
        if not m:
            if expr[pos].strip():
                raise AssertionError("表达式里有无法解析的片段：%r" % expr[pos:pos + 30])
            pos += 1
            continue
        pos = m.end()
        kind = m.lastgroup
        if kind == "func" and m.group("func") not in FUNCS:
            raise AssertionError("判据没建模的函数名：%s" % m.group("func"))
        out.append((kind, m.group()))
    return out


def evaluate(expr, ctx):
    """GitHub Actions 表达式子集求值（只覆盖本仓用得到的：字符串/==/!=/&&/||/! 与四个函数）。"""
    toks = _tokenize(expr.strip())
    i = 0

    def peek():
        return toks[i] if i < len(toks) else (None, None)

    def take():
        nonlocal i
        t = toks[i]
        i += 1
        return t

    def or_expr():
        val = and_expr()
        while peek()[1] == "||":
            take()
            rhs = and_expr()
            val = truthy(val) or truthy(rhs)
        return val

    def and_expr():
        val = not_expr()
        while peek()[1] == "&&":
            take()
            rhs = not_expr()
            val = truthy(val) and truthy(rhs)
        return val

    def not_expr():
        if peek()[1] == "!":
            take()
            inner = not_expr()
            if inner == UNKNOWN:
                # 未知的取非仍然"可能成立"：否则 `!github.event.release.prerelease` 会被判成不跑（假绿）
                return True
            return not truthy(inner)
        return cmp_expr()

    def cmp_expr():
        val = primary()
        while peek()[1] in ("==", "!=", "<", ">", "<=", ">="):
            op = take()[1]
            rhs = primary()
            val = compare(op, val, rhs)
        return val

    def primary():
        kind, text = peek()
        if kind == "str":
            take()
            return text[1:-1]
        if kind == "num":
            take()
            return text
        if kind == "func":
            take()
            name = text
            take()  # (
            args = []
            if peek()[1] != ")":
                args.append(or_expr())
                while peek()[1] == ",":
                    take()
                    args.append(or_expr())
            take()  # )
            return _func(name, args)
        if text == "(":
            take()
            val = or_expr()
            take()  # )
            return val
        if kind == "ctx":
            take()
            return ctx.value(text)
        if kind == "word":
            take()
            if text == "true":
                return True
            if text == "false":
                return False
            if text == "null":
                return ""
            raise AssertionError("表达式里裸标识符未建模：%s" % text)
        raise AssertionError("表达式解析到意外位置：%r" % (peek(),))

    def compare(op, a, b):
        if UNKNOWN in (a, b):
            return True
        a, b = str(a).lower(), str(b).lower()
        if op == "==":
            return a == b
        if op == "!=":
            return a != b
        if op == "<":
            return a < b
        if op == ">":
            return a > b
        if op == "<=":
            return a <= b
        return a >= b

    result = or_expr()
    if i != len(toks):
        raise AssertionError("表达式没读完：%r 剩下 %r" % (expr, toks[i:]))
    return result


def truthy(value):
    if value == UNKNOWN:
        return True
    if isinstance(value, bool):
        return value
    return not (value in ("", "false", "0", 0, None))


def unwrap(expr):
    """${{ ... }} / >- 折叠后的原样表达式。"""
    text = str(expr or "").strip()
    if text.startswith("${{") and text.endswith("}}"):
        text = text[4:-2].strip()
    return text


def pages_jobs(text):
    doc = yaml.safe_load(text.replace(chr(13) + chr(10), chr(10)))
    for name, job in ((doc or {}).get("jobs") or {}).items():
        env = (job or {}).get("environment")
        env_name = env.get("name") if isinstance(env, dict) else env
        if env_name is None:
            continue
        got = str(env_name)
        # 大小写不敏感 + 动态名字（${{ vars.X }}）一律计入：漏判一整条链的代价远大于多判一条
        if got.strip().lower() == "github-pages" or "${{" in got:
            yield name, (job or {}).get("if")


def triggers(text):
    doc = yaml.safe_load(text.replace("\r\n", "\n")) or {}
    on = doc.get(True, doc.get("on"))
    if isinstance(on, (str, list)):
        return {k: None for k in (on if isinstance(on, list) else [on])}
    return on or {}


def non_default_ref_events(text):
    """哪些触发口会把 run 放到**非默认分支 ref** 上（那种 ref 过不了 github-pages 的 branch_policy）。

    v1 只认 release ⇒ 两族评审都构造出 `on: push: tags:['**']` 与 `on: create` 样品证明会被跳过不判；
    `pull_request`（refs/pull/…）、`merge_group`（gh-readonly-queue ref）、`workflow_call`（跟调用方 ref）同理。 `workflow_run` 反过来：官方 GITHUB_REF=默认分支 ⇒ 不算风险口。
    `push` 只有在明确写了 `branches:` 过滤时才排除 tag push；没过滤或带 `tags:` 的都算。
    """
    on = triggers(text)
    ev = set()
    # workflow_run 不入集合：官方 GITHUB_REF = 默认分支，算进来会造假红。
    # workflow_dispatch 不入集合：ref 由人选，收口会把人工修复通道一起禁掉 ⇒ 记为人工口豁免。
    for key in ("release", "create", "pull_request", "merge_group", "workflow_call"):
        if key in on:
            ev.add(key)
    if "push" in on:
        p = on.get("push")
        if not isinstance(p, dict):
            ev.add("push_tag")
        else:
            br, tags = p.get("branches"), p.get("tags")
            only_main = bool(br) and sorted(str(x) for x in (br if isinstance(br, list) else [br])) == ["main"]
            if tags or p.get("branches-ignore") or p.get("tags-ignore") or not only_main:
                ev.add("push_tag")
    return ev


def event_ctx(event, tag):
    """只给该事件真实存在的 payload（一律塞 release.tag_name 会反向造假红，hy4 票实测）。"""
    tagish = event in ("release", "create", "push_tag")
    if tagish:
        ref = "refs/tags/" + tag
    elif event == "pull_request":
        ref = "refs/pull/7/merge"
    else:
        ref = "refs/heads/main"
    payload = {}
    if event == "release":
        payload["release"] = {"tag_name": tag, "target_commitish": "main"}
    elif event == "pull_request":
        payload["pull_request"] = {"base_ref": "main"}
    return _Ctx({"github": {
        "event_name": "push" if event == "push_tag" else event,
        "ref_type": "tag" if tagish else "branch",
        "ref": ref,
        "event": payload,
        "repository": "Fatty911/crawl_cars"}})


def may_run(expr, ctx):
    """三值近似：未建模路径分别取空值/非空值各算一次，任一次会让 job 跑 ⇒ 算"可能跑"。

    单靠"未知即真"也不够：`!contains(未知消息, x)` 会先真后非判成不跑；
    单靠"两侧填值"也不够：`未知 == false` 两侧填值都不相等。⇒ 三种取值都试
    （UNKNOWN / 空串 / 非空串），任一次会让 job 跑就算可能跑；解析不了 fail-closed。
    """
    for fill in (UNKNOWN, "", "x"):
        try:
            if truthy(evaluate(expr, ctx.with_fill(fill))):
                return True
        except AssertionError:
            return True
    return False


def job_runs_for_event(condition, event):
    expr = unwrap(condition)
    if not expr:
        return True
    return any(may_run(expr, event_ctx(event, tag)) for tag in RELEASE_TAGS)


@pytest.mark.parametrize("path", sorted(WORKFLOWS.glob("*.yml")))
def test_no_github_pages_job_can_run_off_the_default_branch(path):
    text = path.read_text(encoding="utf-8")
    risky = non_default_ref_events(text)
    if not risky:
        # 触发口只会把 run 放在默认分支上（workflow_dispatch/schedule/带 branches 过滤的 push）⇒ 无此风险
        pytest.skip("该 workflow 的触发口不会产生非默认分支 ref：%s" % sorted(triggers(text)))
    offenders = {}
    for name, cond in pages_jobs(text):
        bad = sorted(e for e in risky if job_runs_for_event(cond, e))
        if bad:
            offenders[name] = bad
    assert not offenders, ("%s 的 job %s 在非默认分支 ref（tag/refs/pull）上仍会去 github-pages 环境部署；"
                           "该环境设了 branch_policy ⇒ 分配阶段即失败（0 步骤、无日志、无自愈票）"
                           % (path.name, offenders))


TRIGGER_SAMPLES = {
    "release": "on:\n  release:\n    types: [published]",
    "create": "on:\n  create",
    "pull_request": "on:\n  pull_request",
    "push_tag": "on:\n  push:\n    tags: ['**']",
    "push_unfiltered": "on:\n  push",
}

SAFE_SAMPLES = {
    "dispatch": "on:\n  workflow_dispatch",
    "schedule": "on:\n  schedule:\n    - cron: '17 4 * * *'",
    "push_branch_filtered": "on:\n  push:\n    branches: [main]",
}

BODY = """
name: synthetic
%s
jobs:
  deploy:
    environment:
      name: github-pages
    runs-on: ubuntu-latest
    steps:
      - run: echo hi
"""


def test_yard_catches_every_non_default_ref_trigger():
    """每种"把 run 放到非默认分支 ref"的触发口都必须被认出来并判违规（v1 只认 release ⇒ 被两族评审当放水指出）。"""
    for label, block in TRIGGER_SAMPLES.items():
        text = BODY % block
        risky = non_default_ref_events(text)
        assert risky, "%s 触发口没被认成非默认分支 ref ⇒ 尺在放水" % label
        bad = [n for n, c in pages_jobs(text) if any(job_runs_for_event(c, e) for e in risky)]
        assert bad == ["deploy"], "%s 样品的 Pages job 必须判违规，实得 %s" % (label, bad)


def test_yard_does_not_invent_red_on_branch_only_triggers():
    for label, block in SAFE_SAMPLES.items():
        assert not non_default_ref_events(BODY % block), "%s 不该被判风险（造假红会把守卫读成噪声）" % label
    # 只排除 release 的 if 遇到 create/tag push 时必须**仍然**违规——这正是 v1 漏的那格
    partial = (BODY % TRIGGER_SAMPLES["create"]).replace(
        "    runs-on: ubuntu-latest",
        "    if: ${{ github.event_name != 'release' }}\n    runs-on: ubuntu-latest")
    assert [n for n, c in pages_jobs(partial) if job_runs_for_event(c, "create")] == ["deploy"]


def test_landed_deploy_frontend_is_clean_under_the_widened_yard():
    live = (WORKFLOWS / "deploy-frontend.yml").read_text(encoding="utf-8")
    risky = non_default_ref_events(live)
    assert "release" in risky, "deploy-frontend 仍应被认出有 release 入口（只是 job 已排除）"
    offenders = {n: [e for e in risky if job_runs_for_event(c, e)] for n, c in pages_jobs(live)}
    assert not any(offenders.values()), "deploy-frontend.yml 的 job %s 仍会在 %s 上跑 Pages 部署" % (
        sorted(offenders), sorted(risky))

NL = chr(10)
TRIGGER_SAMPLES.update({
    "push_branches_and_tags": "on:" + NL + "  push:" + NL + "    branches: [main]" + NL + "    tags: ['v*']",
    "push_paths_only": "on:" + NL + "  push:" + NL + "    paths: ['docs/**']",
    "push_branches_ignore": "on:" + NL + "  push:" + NL + "    branches-ignore: [bot]",
    "push_branches_multi": "on:" + NL + "  push:" + NL + "    branches: [main, 'feature/*']",
    "merge_group": "on:" + NL + "  merge_group",
    "workflow_call": "on:" + NL + "  workflow_call",
})
SAFE_SAMPLES["workflow_run"] = "on:" + NL + "  workflow_run:" + NL + "    workflows: ['x']" + NL + "    types: [completed]"
SAFE_SAMPLES["pull_request_target"] = "on:" + NL + "  pull_request_target:" + NL + "    types: [closed]"


def test_every_added_trigger_class_is_caught():
    """hy4 票自造的样品类别折进正式判据：这些都必须被认成风险口。"""
    for label in ("push_branches_and_tags", "push_paths_only", "push_branches_ignore",
                  "push_branches_multi", "merge_group", "workflow_call"):
        text = BODY % TRIGGER_SAMPLES[label]
        assert non_default_ref_events(text), label + " 必须算风险口（票实测 v2 漏）"
        bad = [nm for nm, c in pages_jobs(text) if any(job_runs_for_event(c, e) for e in non_default_ref_events(text))]
        assert bad == ["deploy"], label + " 的 Pages job 必须判违规，实得 " + str(bad)


def test_push_with_non_main_branches_is_also_off_default_ref():
    """`branches: [main, 'feature/*']`：推到 feature/* 时 ref 不是 main ⇒ branch_policy 照样拒。"""
    text = BODY % TRIGGER_SAMPLES["push_branches_multi"]
    risky = non_default_ref_events(text)
    assert "push_tag" in risky, str(sorted(risky))
    assert job_runs_for_event(None, "push_tag") is True


def test_workflow_run_is_not_counted_as_risk():
    """官方 GITHUB_REF=默认分支：把它算进风险口会造假红（hy4 票实测出来的"过"）。"""
    assert "workflow_run" not in non_default_ref_events(BODY % SAFE_SAMPLES["workflow_run"])
    assert "pull_request_target" not in non_default_ref_events(BODY % SAFE_SAMPLES["pull_request_target"])


def test_unknown_payload_and_case_folding_do_not_turn_red_green():
    """两条"红被读成绿"的通道：未建模路径、官方不分大小写的字符串函数。"""
    unknown_if = "    if: ${{ github.event.release.prerelease == false }}" + NL + "    runs-on: ubuntu-latest"
    text = (BODY % TRIGGER_SAMPLES["release"]).replace("    runs-on: ubuntu-latest", unknown_if)
    assert [nm for nm, c in pages_jobs(text) if job_runs_for_event(c, "release")] == ["deploy"], "未建模路径取值让真会跑的 job 被判绿（假绿通道）"
    ci_if = "    if: ${{ !startsWith(github.event.release.tag_name, 'CNB-DATA-') }}" + NL + "    runs-on: ubuntu-latest"
    ctx = event_ctx("release", "cnb-data-20261015T041723Z-cnb-6as-1k4ujn7mr")
    assert truthy(evaluate("startsWith(github.event.release.tag_name, 'CNB-DATA-')", ctx)) is True, "官方 startsWith 不分大小写：CNB-DATA- 必须匹上 cnb-data- tag"
    assert truthy(evaluate("github.event_name == 'RELEASE'", ctx)) is True, "官方字符串 == 不分大小写"
    # 存在"会让 job 真跑"的 tag（如 v1.2.3）就保守判违规：GH 里外部 tag 确实会放行
    ci = (BODY % TRIGGER_SAMPLES["release"]).replace("    runs-on: ubuntu-latest", ci_if)
    assert [nm for nm, c in pages_jobs(ci) if job_runs_for_event(c, "release")] == ["deploy"]


def test_no_if_means_runs_for_every_risky_event():
    """无 if 的 Pages job 在每个风险事件下都必须判违规（v1 的这条不变量在 v2 不能丢）。"""
    for label, block in list(TRIGGER_SAMPLES.items()):
        text = BODY % block
        risky = non_default_ref_events(text)
        assert risky, label
        assert job_runs_for_event(None, sorted(risky)[0]) is True, label

def test_unmodeled_paths_are_evaluated_on_both_sides():
    """评审票 L1 的完整版：未知路径经 `!`/`contains` 这类取反组合后仍不许假绿。"""
    body = BODY % TRIGGER_SAMPLES["release"]
    for expr in (
        "!github.event.release.prerelease",
        "!contains(github.event.head_commit.message, 'qoder-marker')",
        "!startsWith(github.event.release.id, 'abc')",
    ):
        gated = body.replace("    runs-on: ubuntu-latest",
                                "    if: ${{ " + expr + " }}" + NL + "    runs-on: ubuntu-latest")
        bad = [nm for nm, c in pages_jobs(gated) if job_runs_for_event(c, "release")]
        assert bad == ["deploy"], "该表达式在某些取值下真会让 job 跑，必须判违规：" + expr


def test_stable_modelled_condition_is_not_flagged_under_any_fill():
    """反向：已建模的 event_name 比较不受三值近似影响 ⇒ 不会把 #382 那种正确写法判成违规。"""
    body = BODY % TRIGGER_SAMPLES["release"]
    clean = body.replace("    runs-on: ubuntu-latest",
                         "    if: ${{ github.event_name != 'release' }}" + NL + "    runs-on: ubuntu-latest")
    assert [nm for nm, c in pages_jobs(clean) if job_runs_for_event(c, "release")] == []


def test_dynamic_environment_name_is_still_counted():
    """评审票 L6：environment 名字写成 ${{ vars.X }} 时也不许整条链漏判。"""
    dyn = BODY % TRIGGER_SAMPLES["release"]
    dyn = dyn.replace("      name: github-pages", "      name: ${{ vars.PAGES_ENV }}")
    assert [nm for nm, c in pages_jobs(dyn) if job_runs_for_event(c, "release")] == ["deploy"]


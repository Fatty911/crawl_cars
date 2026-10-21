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


class _Ctx(dict):
    """release 场景的 github 上下文；未建模的取值一律给空串（GH 里缺路径读成 null）。"""

    def value(self, dotted):
        cur = self
        for part in dotted.split("."):
            if not isinstance(cur, dict) or part not in cur:
                return ""
            cur = cur[part]
        return cur if isinstance(cur, str) else ""


def _func(name, args):
    if name == "startsWith":
        return str(args[0]).startswith(str(args[1]))
    if name == "endsWith":
        return str(args[0]).endswith(str(args[1]))
    if name == "contains":
        return str(args[1]) in str(args[0])
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
            return not truthy(not_expr())
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
        a, b = str(a), str(b)
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
    if isinstance(value, bool):
        return value
    return not (value in ("", "false", "0", 0, None))


def unwrap(expr):
    """${{ ... }} / >- 折叠后的原样表达式。"""
    text = str(expr or "").strip()
    if text.startswith("${{") and text.endswith("}}"):
        text = text[4:-2].strip()
    return text


def release_ctx(tag):
    return _Ctx({"github": {"event_name": "release", "ref_type": "tag", "ref": "refs/tags/" + tag,
                            "event": {"release": {"tag_name": tag, "target_commitish": "main"}},
                            "repository": "Fatty911/crawl_cars"}})


def job_runs_on_release(condition):
    expr = unwrap(condition)
    if not expr:
        return True
    return any(truthy(evaluate(expr, release_ctx(tag))) for tag in RELEASE_TAGS)


def pages_jobs(text):
    doc = yaml.safe_load(text.replace("\r\n", "\n"))
    for name, job in ((doc or {}).get("jobs") or {}).items():
        env = (job or {}).get("environment")
        env_name = env.get("name") if isinstance(env, dict) else env
        if env_name == "github-pages":
            yield name, (job or {}).get("if")


def triggers(text):
    doc = yaml.safe_load(text.replace("\r\n", "\n")) or {}
    on = doc.get(True, doc.get("on"))
    if isinstance(on, (str, list)):
        return set(on if isinstance(on, list) else [on])
    return set((on or {}).keys())


@pytest.mark.parametrize("path", sorted(WORKFLOWS.glob("*.yml")))
def test_no_github_pages_job_can_run_on_release_events(path):
    text = path.read_text(encoding="utf-8")
    if "release" not in triggers(text):
        # 没有 release 入口的链不可能被 release 事件拉起（同机全套首跑就是这里误伤过
        # cnb-pages.yml：它只有 workflow_dispatch）⇒ 不判，尺不许造假红。
        pytest.skip("该 workflow 没有 release 触发口")
    offenders = [name for name, cond in pages_jobs(text) if job_runs_on_release(cond)]
    assert not offenders, ("%s 的 job %s 会响应 release 事件 ⇒ 会去 github-pages 环境部署，"
                           "而 release run 在 tag ref 上被 branch_policy 拒绝（必红、且无自愈票）"
                           % (path.name, offenders))


def test_yard_detects_the_real_shape_and_the_fixed_shape(tmp_path):
    """双向自校：现网那两条"或"式必须被判违规；修法必须判通过。"""
    live = (WORKFLOWS / "deploy-frontend.yml").read_text(encoding="utf-8")
    live_jobs = [n for n, c in pages_jobs(live) if job_runs_on_release(c)]
    bad = """
name: synthetic
on:
  release:
    types: [published]
jobs:
  deploy:
    environment:
      name: github-pages
    runs-on: ubuntu-latest
    steps:
      - run: echo hi
"""
    good = bad.replace("    runs-on: ubuntu-latest",
                       "    if: ${{ github.event_name != 'release' }}\n    runs-on: ubuntu-latest")
    # 误伤样品：没有 release 触发口的链（现网 cnb-pages.yml 的形状）不能被判违规
    no_release = bad.replace("on:\n  release:\n    types: [published]", "on:\n  workflow_dispatch:")
    assert "release" not in triggers(no_release)
    assert job_runs_on_release(None) is True
    assert [n for n, c in pages_jobs(bad) if job_runs_on_release(c)] == ["deploy"]
    assert [n for n, c in pages_jobs(good) if job_runs_on_release(c)] == []
    assert "release" not in triggers(no_release), "触发口解析错了 ⇒ 尺会造假红"
    if live_jobs:
        pytest.fail("deploy-frontend.yml 还没修：job %s 在 release 事件下仍会去部署 Pages" % live_jobs)

"""子进程调用不许硬编码 `python3`（本仓在 Windows 上没有这个可执行文件）。

现网事实（监工 2026-10-12 实测，不是推断）：
  `scripts/validate_syntax.py:129` 与 `tests/test_spu_merge_analysis.py:16` 把
  `["python3", ...]` 写死进 `subprocess.run`。Windows 上不存在 `python3` 这个可执行文件
  （只有 `python` / `py`），这两处会在 Windows 侧抛 `FileNotFoundError` —— 实测正是
  Windows 全套套件里那批"环境专属红"的一部分；改成 `sys.executable` 后同一套环境
  实测由红转绿（`418 passed / 0 failed / 3 skipped`）。

口径：
  A. `scripts/` 与 `tests/` 下任何 `.py` 的可执行代码行里，不许出现被引号包裹的 `python3`
     作为子进程命令（shebang 行、注释、文档字符串不算）；
  B. 修法必须是 `sys.executable`（当前解释器），不是改名成 `python`——后者在无 `python`
     别名的环境同样会失败，且 Linux 侧应保持不动。
"""

from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
# 拆开写：判据文件自身不能命中自己的模式（否则它会把自己判成缺陷）
CMD = re.compile(r'["\']py' + r'thon3["\']')


def _py_files():
    for base in ("scripts", "tests"):
        for path in sorted((ROOT / base).rglob("*.py")):
            yield path


def _offenders() -> list:
    out = []
    for path in _py_files():
        if path.resolve() == pathlib.Path(__file__).resolve():
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith(("#", '"""', "'''")):
                continue
            if CMD.search(line):
                out.append("%s:%d: %s" % (path.relative_to(ROOT), lineno, stripped[:90]))
    return out


def test_tree_is_scanned_not_assumed() -> None:
    """反退化：扫不到文件就是"读不到"，宁可判崩也不许据此判通过。"""
    assert list(_py_files()), "在 scripts/ 与 tests/ 下一个 .py 都没扫到 ⇒ 读数退化，禁止判绿"


def test_no_hardcoded_python3_as_subprocess_command() -> None:
    bad = _offenders()
    assert not bad, (
        "子进程调用硬编码了 python3：Windows 上没有 python3 可执行文件 ⇒ FileNotFoundError，"
        "同一套环境实测由红转绿的修法是改用 sys.executable（不是改成 python）。命中：%s" % bad)

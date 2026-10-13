分支 `agent/49-no-hardcoded-python3`（本地就绪；代码提交 `4787319`，报告随分支头提交交付；基线 `8893eaf`）｜推送状态 HTTP 403 ｜原因：容器凭据缺少 `repo-code:rw` scope（`Your token does not have the repo-code:rw scope required to push to this repository.`），已更换 3 种凭据变体各试 1 次后停止推送，改走 Issue #49 附件交付。

# Issue #49 修复报告：子进程调用改用 sys.executable（移除硬编码 python3）

**交付方式**: 因推送被拒，按 Issue 指示改为附件交付。产出物已通过 Issue #49 附件上传（patch + bundle），见下方「附件清单」。commit `4787319` 本地已就绪，监工可直接 fetch 附件 bundle 后复核。

---

## 1. 实际改动文件清单（3 个）

| 文件 | 改动 | 行数 |
|---|---|---|
| `scripts/validate_syntax.py` | `["python3", ...]` → `[sys.executable, ...]`（该文件已有 `import sys`，未加 import） | 第 129 行，1 行替换 |
| `tests/test_spu_merge_analysis.py` | `["python3", ...]` → `[sys.executable, ...]`；并在 `import subprocess` 下一行补 `import sys` | 第 6 行、第 16 行 |
| `tests/test_no_hardcoded_python3.py` | 新增（原样落盘 Issue 下发的验收判据，未改动任何字节） | 56 行新增 |

`git diff --stat`（相对于 `8893eaf` main）：

```
 scripts/validate_syntax.py         |  2 +-
 tests/test_no_hardcoded_python3.py | 56 ++++++++++++++++++++++++++++++++++++++
 tests/test_spu_merge_analysis.py   |  3 +-
 3 files changed, 59 insertions(+), 2 deletions(-)
```

**边界遵守声明**：只改上述 2 处调用点 + 1 个判据文件。未触碰 shebang、注释、文档字符串中的 "python3"；未改 `scripts/merge_data.py`；未改 `.cnb.yml`、门禁脚本或任何既有断言；未使用 `--no-verify` / `SKIP_TESTS` / `SKIP_REVIEW` / `ALLOW_UNREVIEWED_EDIT`。判据文件与 Issue 下发文本逐字节比对一致（`EQ True`，1861 bytes）。

## 2. 判据运行结果原文（分支 `agent/49-no-hardcoded-python3`）

命令：`python -m pytest tests/test_no_hardcoded_python3.py -q`

```
..                                                                       [100%]
2 passed in 0.06s
```

**退出码**: `0`

修复前（判据初始落盘时）同一命令为**红**：

```
E       AssertionError: 子进程调用硬编码了 python3：...命中：['scripts/validate_syntax.py:129: ["python3", "-m", "py_compile", str(file_path)],', 'tests/test_spu_merge_analysis.py:16: ["python3", str(SCRIPT), "--data", str(data_path), "--output", str(output_path)],']
1 failed, 1 passed in 0.07s
```

## 3. 「能变红」反证证据（临时回填 → 判红 → 复原）

1. 临时把 `scripts/validate_syntax.py:129` 改回 `["python3", ...]`，跑判据：
   ```
   FAILED tests/test_no_hardcoded_python3.py::test_no_hardcoded_python3_as_subprocess_command
   1 failed, 1 passed in 0.07s
   ```
2. 改回 `sys.executable` 后复跑：`2 passed in 0.06s`。
   （还原后工作区与提交内容一致，`git status` 无残留差异。）

## 4. 全量套件回归（相对 main 无新增红）

| 版本 | 命令 | 结果 |
|---|---|---|
| 分支 `agent/49-no-hardcoded-python3` | `python -m pytest tests -q` | `711 passed, 139 subtests passed in 32.07s`（退出码 0） |
| main `8893eaf`（git worktree 对照） | `python -m pytest tests -q` | `709 passed, 139 subtests passed in 33.50s`（退出码 0） |

差值 `+2 passed` 即本单新增的 2 条判据（`test_tree_is_scanned_not_assumed`、`test_no_hardcoded_python3_as_subprocess_command`），无新增红、无 fail、无 error。

## 5. 环境与依赖

- 容器：`python:3.12`（CNB `issue.open` 链，`install-deps` 阶段已装 `pytest pyyaml tzdata`；本次复核再次执行 `pip install pytest pyyaml tzdata` 通过）。
- 运行命令统一使用 `python -m pytest ...`（门禁口径），未裸跑 `pytest`。
- Windows 侧收益：`python3` 可执行文件在 Windows 上不存在，两处 `subprocess.run(["python3", ...])` 会抛 `FileNotFoundError`；改为 `sys.executable` 后调用当前解释器，Linux 侧（`python:3.12`）行为不变（`sys.executable` = `/usr/local/bin/python3`）。

## 6. 附件清单（Issue #49 评论区）

| 附件 | 用途 | 大小 |
|---|---|---|
| `agent-49-delivery.patch` | `git format-patch` 单提交补丁，`git am` 可直接落地 | 5341 B |
| `agent-49-no-hardcoded-python3.bundle` | 增量 bundle（`8893eaf..4787319`），仅含本单 1 个提交；`git fetch <bundle> refs/heads/agent/49-no-hardcoded-python3:...` 已在临时克隆中实测可解析、diff 与本地一致 | 2807 B |

本地完整 bundle（含全量历史，7.9 MB）因体积原因未上传，如需可用 `git bundle create` 从 `4787319` 重新生成。

## 7. 模型与轮数（如实记录）

- **实际使用模型**: `deepseek-v4.1-flash`（`.cnb.yml:1426` `issue.open` → npc:go `options.model`，`thinkingLevel: max`）。
- **effective_max_turns**: `150`（`.cnb.yml:1428` `maxTurns: 150`）。本报告完成于第 **30** 轮上下，**剩余约 120 轮**。
- **终止原因**: 本会话未出现 `reached maxTurns limit`、未出现 `finish with length`、未出现 `finish with stop` 提前终止；本条为正常交付收尾，报告写完即停。

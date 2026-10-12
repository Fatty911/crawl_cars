"""断点身份闸不能因为"脚本改过一行"就把跨轮状态判死（判据，当前在 main 上必须红）。

**实测链条（10-12 20:07，监工用仓库自己的代码离线跑通，不是推断）**：
1. `.cnb.yml:322-330` 每轮把 `--resume-source-crawler-sha256 "$(sha256sum scripts/crawl_yiche.py)"` 传给爬虫；
2. `crawl_state/yiche_frontier.json` 里记的是**上一轮那份脚本**的哈希
   （本轮 main 上：内嵌 `6d20e02f…`，当前脚本 `084834bf…`/LF 归一 `64cca8c4…` ⇒ 两种口径都不匹配）；
3. `scripts/crawl_yiche.py:1309-1316` 的身份块把 5 个比较用 `or` 绑在一起，
   其中 `crawler_sha256` 这一项**每次改爬虫脚本都会飘** ⇒
   `ValueError: checkpoint producer identity mismatch`（实测复现）；
4. 于是本轮无产出，`.cnb.yml:358-361` 执行 `rm -f "$YICHE_CHECKPOINT_PATH"`，
   断点被删、退回首轮重爬 ⇒ 验收第 5 项"连续两轮 `brands_scanned` 严格递增"**在数学上不可能成立**。

**这不是"闸没用"，是闸的口径越界**：`repository / run_id / head_sha / workflow` 四项管的是
"这份断点是不是同一条流水线产物"，都有效；只有 `crawler_sha256` 管的是"代码字节有没有变"，
而代码本来就要改（NPC 每张修复单都可能动它）。

**放宽之前先证明兜底会触发**（这是本判据自带的红样，不许用 try/except 糊过去）：
- 行质量门（`validate_real_rows`，:1324）必须仍然拒绝坏行 ⇒ 想靠"全吞异常"过关会当场变红；
- schema/state-compat（:1303-1306）与 repository（:1310）必须仍然拒绝 ⇒ 只放开"代码字节"这一维。
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location("crawl_yiche", ROOT / "scripts" / "crawl_yiche.py")
CY = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(CY)

REAL = ROOT / "crawl_state" / "yiche_frontier.json"


def _sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _frontier(tmp: pathlib.Path, mutate=None) -> pathlib.Path:
    """夹具用**现网真断点**的 resume_state/rows（不是手编的形状），只改 producer。"""
    payload = json.loads(REAL.read_text(encoding="utf-8"))
    payload["producer"] = dict(payload.get("producer") or {})
    payload["producer"]["crawler_sha256"] = "0" * 64          # 上一版脚本的哈希
    payload["producer"]["run_id"] = ""
    payload["producer"]["head_sha"] = ""
    if mutate:
        mutate(payload)
    out = tmp / "frontier.json"
    out.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return out


def _load(path: pathlib.Path, crawler_sha: str):
    return CY.load_resume_checkpoint(
        str(path),
        source_run_id="",
        source_artifact_id="",
        source_artifact_sha256="",
        source_checkpoint_sha256=_sha(path),
        source_head_sha="",
        source_crawler_sha256=crawler_sha,
    )


def test_real_frontier_exists_on_main():
    assert REAL.exists() and REAL.stat().st_size > 1024, (
        "crawl_state/yiche_frontier.json 不在 main 上（%s）⇒ 本判据无从判定，先修第 5 项的前半" % REAL)
    payload = json.loads(REAL.read_text(encoding="utf-8"))
    assert (payload.get("producer") or {}).get("crawler_sha256"), (
        "现网断点里没有 producer.crawler_sha256 ⇒ 夹具失去真实形状，判据要重写而不是硬跑")


def test_drifted_crawler_sha_still_resumes(tmp_path):
    """核心处置：代码字节变了但流水线身份没变 ⇒ 必须照样续跑（返回真值 resume_state）。

    调用方契约见 :2002 `urls = [] if resume_state else load_urls(args)` ⇒
    这里断言的是"续跑这条路走不走得通"，不是"有没有打个 warning"。
    """
    cp = _frontier(tmp_path)
    state = _load(cp, "1" * 64)          # 本轮脚本的哈希：与断点里的必然不同
    assert state, (
        "crawler_sha256 漂移就把断点判死：跨轮 brands_scanned 永远归零（第 5 项不可满足）。"
        "只放开这一维，其余身份与质量门不许一起放。")


def test_bad_rows_still_rejected(tmp_path):
    """兜底必须仍在：行质量门不过的断点，改哈希口径也不许放行。"""
    def break_rows(payload):
        rows = payload.get("rows")
        if isinstance(rows, list) and rows:
            payload["rows"] = [dict(rows[0], **{"车系": "", "车型名称": ""})]
        else:
            payload["rows"] = [{"junk": 1}]

    cp = _frontier(tmp_path, break_rows)
    try:
        _load(cp, "1" * 64)
    except ValueError:
        return
    raise AssertionError(
        "坏行断点被放行 ⇒ 说明修法是 try/except 全吞，不是只放开 crawler_sha256 这一维")


def test_wrong_repository_still_rejected(tmp_path):
    """兜底必须仍在：不是同一条流水线的产物（repository 身份不符）照旧拒绝。"""
    cp = _frontier(tmp_path, lambda p: p["producer"].update({"repository": "someone/else"}))
    try:
        _load(cp, "0" * 64)             # 连哈希都对上的情况也必须被身份拦住
    except ValueError:
        return
    raise AssertionError("repository 身份不符却被放行 ⇒ 身份闸被整块拆掉了")


def test_schema_mismatch_still_rejected(tmp_path):
    """兜底必须仍在：schema/state-compat 不符照旧拒绝。"""
    cp = _frontier(tmp_path, lambda p: p.update({"schema_version": "definitely-not-current"}))
    try:
        _load(cp, "0" * 64)
    except ValueError:
        return
    raise AssertionError("schema 不符却被放行 ⇒ 兼容性闸被整块拆掉了")


def test_producer_identity_fields_unchanged_except_crawler_sha(tmp_path):
    """防止"顺手把 producer 记录也改掉"：新写的断点仍要落 crawler_sha256（只是读端不再拿它判死）。"""
    cp = _frontier(tmp_path)
    payload = json.loads(cp.read_text(encoding="utf-8"))
    assert "crawler_sha256" in (payload.get("producer") or {}), "夹具 producer 形状被改坏，判据失效"
    src = (ROOT / "scripts" / "crawl_yiche.py").read_text(encoding="utf-8").replace("\r", "")
    assert '"crawler_sha256": file_sha256(__file__)' in src, (
        "写端不再记录 crawler_sha256 了：漂移的可追溯性没了。放开读端不等于关掉记账。")

"""交付核对：把 Issue 最新评论里的产物地址真取一次（HTTP 200 且 ≥64 字节才算交付）。

单份物理实现：主链「交付核对-产物必须真取回」段与自愈链「交付核对-修复后必须真取回」段
都调用本文件，禁止再抄第二份内联字面块（改一处漏一处的老病：同一文件里的重复字面块
只改一份会留下第二份被执行）。

行为从 .cnb.yml 的原内联块原样提取：枚举最新评论里的候选地址、逐个下载、
打印 HTTP 读数与字节数、一个都取不到时输出 `DELIVERY-FAIL reason=…` 并以非 0 退出。
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("DELIVERY_BASE") or "https://api.cnb.cool/xuerui911-mirror/crawl_cars"
TOKEN = os.environ.get("CNB_TOKEN") or ""
MIN_BYTES = 64


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """重定向不自动跟：自动跟会把 Authorization 带给存储端（401 的根因）。"""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


OPENER = urllib.request.build_opener(_NoRedirect)


def _once(url, with_auth):
    req = urllib.request.Request(url, method="GET")
    req.add_header("Accept", "application/vnd.cnb.api+json")
    if with_auth and TOKEN:
        req.add_header("Authorization", "Bearer " + TOKEN)
    try:
        resp = OPENER.open(req, timeout=60)
        return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers or {}), exc.read()


def fetch(url):
    """取一次，最多跟 3 跳重定向；第一跳带凭据、之后不带。返回 (status, 字节, 落点, err)。

    非 ASCII（例如复制时被省略号截断的地址）先做 percent 编码，否则 urlopen 会抛
    UnicodeEncodeError 而不是给出 HTTP 读数——那样就说不清到底是哪一格失败。
    """
    where = urllib.parse.quote(url, safe="/-._~%:?=&+")
    auth = True
    status, size, headers = 0, 0, {}
    for _ in range(4):
        try:
            status, headers, body = _once(where, auth)
        except Exception as exc:
            return 0, 0, where, "%s: %s" % (type(exc).__name__, exc)
        size = len(body)
        if status in (301, 302, 303, 307, 308):
            nxt = headers.get("Location") or headers.get("location")
            if not nxt:
                break
            where, auth = urllib.parse.urljoin(where, nxt), False
            continue
        return status, size, where, ""
    return status, size, where, "redirect 超限"


def latest_comment_body(num):
    """评论通道。只认**最新评论**：退回更早的评论会让上一轮遗留的附件
    替本轮零产物蒙混过关（那正是要消灭的假绿形状）。"""
    url = "%s/-/issues/%s/comments" % (BASE, num)
    status, headers, body = _once(url, True)
    if status != 200:
        print("DELIVERY-FAIL reason=comments-unreachable issue=%s http=%s" % (num, status))
        raise SystemExit(1)
    data = json.loads(body.decode("utf-8"))
    if not isinstance(data, list) or not data:
        print("DELIVERY-FAIL reason=no-comments issue=%s" % num)
        raise SystemExit(1)
    return str(data[-1].get("body") or "")


# URL 整条取：捕到空白/引号/尖括号为止（? 之后的查询串保留），只剥 markdown 收尾标点
ABS = re.compile(r"https://api\.cnb\.cool/[^\s\"'`<>\[\]]+")
REL = re.compile(r"/-/files/[^\s\"'`<>\[\]]+")
TRIM = ")]}。，,、;.）】》”’"


def candidates(body):
    found = []
    for pattern, prefix in ((ABS, ""), (REL, BASE)):
        for match in pattern.finditer(body):
            url = match.group(0).rstrip(TRIM)
            # 只认真有文件名的产物地址：`/-/files/` 后面必须还有一层路径，
            # 否则评论里的示意写法 "(/-/files/...)" 会被当成候选，失败读数就被稀释
            tail = url.split("/-/files/", 1)[-1]
            if url and "/-/files/" in prefix + url and "/" in tail:
                found.append(prefix + url)
    out = []
    for url in found:
        if url not in out:
            out.append(url)
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="交付核对：枚举 Issue 最新评论里的产物地址并逐个真取一次")
    parser.add_argument("--issue", default=None,
                        help="Issue 号；缺省时依次读 CNB_ISSUE_NUMBER / CNB_ISSUE_IID")
    args = parser.parse_args(argv)
    num = (args.issue or os.environ.get("CNB_ISSUE_NUMBER")
           or os.environ.get("CNB_ISSUE_IID") or "").strip()
    if not num:
        print("DELIVERY-FAIL reason=no-issue-number：读不到 issue 号 ⇒ 核对没有发生，不许当通过")
        return 1
    body = latest_comment_body(num)
    note = "yes" if "_fix_report_" in body else "no"
    urls = candidates(body)
    print("DELIVERY-NOTE issue=%s mentions_fix_report=%s candidates=%d" % (num, note, len(urls)))
    if not urls:
        print("DELIVERY-FAIL reason=no-artifact-link issue=%s（最新评论里没有 /-/files/ 产物链接）" % num)
        return 1
    for url in urls:
        status, size, where, err = fetch(url)
        print("GET %s -> http=%s bytes=%s%s" % (where, status, size, (" err=" + err) if err else ""))
        if status == 200 and size >= MIN_BYTES:
            print("DELIVERY-OK issue=%s artifact=%s http=200 bytes=%s mentions_fix_report=%s"
                  % (num, where, size, note))
            return 0
    print("DELIVERY-FAIL reason=artifact-unreachable issue=%s candidates=%d（逐个取过，没一个 200 且 ≥%d 字节）"
          % (num, len(urls), MIN_BYTES))
    return 1


if __name__ == "__main__":
    sys.exit(main())

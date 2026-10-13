#!/usr/bin/env python3
"""#45 合并补丁：stage 超时对齐 + Codeberg 重试 + 三处回推推送令牌改走 askpass + 回推阶段提前。

运行：python patch_issue45.py <工作树路径>
所有替换都带出现次数断言；失败即不写盘。
"""
import pathlib
import sys

ROOT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".")
P = ROOT / ".cnb.yml"
raw = P.read_text(encoding="utf-8")


def sub(old, new, expect, tag):
    global raw
    n = raw.count(old)
    assert n == expect, "%s expected %d occurrences, got %d" % (tag, expect, n)
    raw = raw.replace(old, new)
    print("%s ok (x%d)" % (tag, n))


# ---------- Part 1: stage 超时与预算对齐 ----------
# 默认跳过：爬虫 stage timeout 已被 Issue #47 认领（另一位监工已取回并验证 NPC 提交
# 77e2fd8），本单不再改那几行，避免同制品重复派发互相踩。需要时加 --with-timeouts。
if "--with-timeouts" in sys.argv:
    sub("        - name: 爬取-汽车之家\n          timeout: 1h\n",
        "        - name: 爬取-汽车之家\n          timeout: 3h\n", 2, "Part1 autohome timeout 1h->3h")
    sub("        - name: 爬取-懂车帝\n          timeout: 2h\n",
        "        - name: 爬取-懂车帝\n          timeout: 5h\n", 2, "Part1 dongchedi timeout 2h->5h")
else:
    print("Part1 skipped (--with-timeouts 未给；超时对齐归 Issue #47)")

# ---------- Part 2: Codeberg 发布加重试（两条爬虫链） ----------
sub('            GIT_ASKPASS=/tmp/cb-askpass.sh git push --force '
    'https://codeberg.org/xuerui911/crawl-cars.git pages:pages\n',
    """            ATTEMPT=1
            MAX_ATTEMPTS=3
            while [ "$ATTEMPT" -le "$MAX_ATTEMPTS" ]; do
              if GIT_ASKPASS=/tmp/cb-askpass.sh git push --force https://codeberg.org/xuerui911/crawl-cars.git pages:pages; then
                break
              fi
              echo "Codeberg 第 ${ATTEMPT} 次尝试失败（TLS/代理抖动），退避后重试"
              sleep $((ATTEMPT * 20))
              ATTEMPT=$((ATTEMPT + 1))
              if [ "$ATTEMPT" -gt "$MAX_ATTEMPTS" ]; then
                echo "Codeberg 发布在 ${MAX_ATTEMPTS} 次尝试后仍失败，本轮判红" >&2
                exit 1
              fi
            done
""", 2, "Part2 codeberg retry loop")

# ---------- Part 2b: 连通性预检 curl 也要进重试（PR #51 交叉评审抓出的半修：
#           实测 code 35 命中的是这条 curl，不是 git push） ----------
old_curl = ('            curl --fail --silent --show-error --location --proxy "$HTTPS_PROXY" '
            '--connect-timeout 20 --max-time 60 https://codeberg.org -o /dev/null\n')
new_curl = """            CB_ATTEMPT=1
            CB_MAX_ATTEMPTS=3
            while [ "$CB_ATTEMPT" -le "$CB_MAX_ATTEMPTS" ]; do
              if curl --fail --silent --show-error --location --proxy "$HTTPS_PROXY" --connect-timeout 20 --max-time 60 https://codeberg.org -o /dev/null; then
                break
              fi
              echo "Codeberg 连通性预检第 ${CB_ATTEMPT} 次失败（TLS/代理抖动），退避后重试"
              sleep $((CB_ATTEMPT * 20))
              CB_ATTEMPT=$((CB_ATTEMPT + 1))
              if [ "$CB_ATTEMPT" -gt "$CB_MAX_ATTEMPTS" ]; then
                echo "Codeberg 连通性预检在 ${CB_MAX_ATTEMPTS} 次尝试后仍失败，本轮判红" >&2
                exit 1
              fi
            done
"""
n = raw.count(old_curl)
assert n == 2, "Part2b expected 2 occurrences, got %d" % n
raw = raw.replace(old_curl, new_curl)
print("Part2b ok (x2): codeberg curl precheck retry loop")

# ---------- Part 3a: 两条爬虫链的回推增量状态（14 空格 push，12 空格 heredoc 基准） ----------
# 注意：YAML 块标量里 heredoc 内容必须与该 **script 块的基准缩进**齐平（仓库既有
# cb-askpass 就是这么写的），写成第 0 列会提前终止块标量，yaml.safe_load 直接报
# "could not find expected ':'"；写成 cat 行所在 if/else 分支的缩进（+2）虽然 YAML 合法，
# 但 dedent 后终止符落在第 2 列 ⇒ shell 侧语法错误（#48 的 NPC 实测抓出这 3 处，教训在此）。
sub('\n              git push "https://${CNB_TOKEN_USER_NAME:-cnb}:${CNB_TOKEN}'
    '@cnb.cool/xuerui911-mirror/crawl_cars.git" HEAD:main\n',
    """
              cat > /tmp/pb-askpass.sh <<'PBASK'
            #!/bin/sh
            case "$1" in
              *sername*) echo "${CNB_TOKEN_USER_NAME:-cnb}" ;;
              *) printf '%s' "$CNB_TOKEN" ;;
            esac
            PBASK
              chmod +x /tmp/pb-askpass.sh
              GIT_ASKPASS=/tmp/pb-askpass.sh git push https://cnb.cool/xuerui911-mirror/crawl_cars.git HEAD:main
              rm -f /tmp/pb-askpass.sh
""", 2, "Part3a crawler pushback askpass")

# ---------- Part 3b: 经销商链的回推报价数据（16 空格 push，14 空格 heredoc 基准） ----------
sub('\n                git push "https://${CNB_TOKEN_USER_NAME:-cnb}:${CNB_TOKEN}'
    '@cnb.cool/xuerui911-mirror/crawl_cars.git" HEAD:main\n',
    """
                cat > /tmp/dl-askpass.sh <<'DLASK'
              #!/bin/sh
              case "$1" in
                *sername*) echo "${CNB_TOKEN_USER_NAME:-cnb}" ;;
                *) printf '%s' "$CNB_TOKEN" ;;
              esac
              DLASK
                chmod +x /tmp/dl-askpass.sh
                GIT_ASKPASS=/tmp/dl-askpass.sh git push https://cnb.cool/xuerui911-mirror/crawl_cars.git HEAD:main
                rm -f /tmp/dl-askpass.sh
""", 1, "Part3b dealer pushback askpass")

# ---------- Part 4: 回推增量状态 移到 组装发布站点 之前（两条爬虫链） ----------
lines = raw.split("\n")
PB_START = "        - name: 回推增量状态"
INSERT_BEFORE = "        - name: 组装发布站点"
FAILSTAGES = "      failStages:"

# 先快照所有块范围，再从后往前移（从后往前移保证前面块的索引不倒；
# 不能在循环里重新搜 PB_START——刚移过来的块会被当成新块反复移）
ranges = []
pos = 0
while True:
    s = next((i for i in range(pos, len(lines)) if lines[i] == PB_START), None)
    if s is None:
        break
    e = next(i for i in range(s + 1, len(lines)) if lines[i].startswith(FAILSTAGES))
    ranges.append((s, e))
    pos = e
assert len(ranges) == 2, "Part4 expected 2 blocks, found %d" % len(ranges)
for s, e in reversed(ranges):
    block = lines[s:e]
    assert block[0] == PB_START, "block head mismatch: %r" % block[0]
    assert block[-1].strip().endswith("fi"), "block tail mismatch: %r" % block[-1]
    # 向前找同一个链里的 组装发布站点（回推原本就排在它后面；不能搜第一个，会插错链）
    ins = max(i for i, l in enumerate(lines[:s]) if l == INSERT_BEFORE)
    del lines[s:e]
    lines[ins:ins] = block
print("Part4 ok (x2): pushback moved before 组装发布站点")

P.write_text("\n".join(lines), encoding="utf-8")
print("written:", P)

"use strict";
/**
 * scan_pages_columns.js — 访问线上 Pages 解析 JS 渲染结果，持续扫描列名并归并。
 *
 * 目标（用户需求）：让 action 访问 Pages、解析 JS 获取数据，持续扫描列名并对列名做归并。
 *
 * 工作方式：
 *   1. 用 headless 浏览器（优先 CHROME_PATH 环境变量，其次自动探测 chromium/chrome，
 *      playwright 安装目录）访问线上 Pages URL，等待 app.js 渲染完成。
 *   2. 从真实 DOM 提取渲染后的表头列名（#tableHead th button span 文本）
 *      以及数据列（全部行的键并集——宽表含稀疏/变体列），同时下载线上 latest.json 作数据源。
 *   3. 对每个扫描到的列名执行归并：
 *        - 命中别名映射（config/column_header_aliases.json column→canonical，
 *          docs/filter_conditions.json columnAliases canonical→[alias]）→ alias→canonical
 *        - 命中规范列/历史记录 → 已归并
 *        - 未命中 → 新增待归并（输出到报告，供 AI 修复链自发现新列名/未归并列名）
 *   4. 输出 JSON 报告（stdout + 可选文件），exit 0 不阻断部署（只采集不阻断）。
 *   5. Pages URL 不写死：--url 显式指定，否则依次取 env PAGES_URL/GITHUB_PAGES_URL、
 *      GitHub API（repos/{owner}/{repo}/pages html_url）、{owner}.github.io/{repo}/ 推导。
 *
 * 用法:
 *   node scripts/scan_pages_columns.js [--url https://<pages-domain>/]
 *       [--data /path/to/latest.json] [--out /path/to/scan-report.json]
 *       [--repo-root .] [--history /path/to/history.json] [--no-browser]
 *
 * 环境变量: CHROME_PATH 浏览器可执行文件；PAGES_URL / GITHUB_PAGES_URL 线上 Pages 根 URL；
 *           GITHUB_REPOSITORY（owner/repo）用于 API 查询/推导 Pages 域名。
 */
const fs = require("node:fs");
const path = require("node:path");
const { execFileSync, spawnSync } = require("node:child_process");

// ---- 参数解析 ----
const args = process.argv.slice(2);
function argValue(name, def) {
  const i = args.indexOf(name);
  return i >= 0 && args[i + 1] ? args[i + 1] : def;
}
const DATA_PATH = argValue("--data", "");
const OUT_PATH = argValue("--out", "");
const REPO_ROOT = argValue("--repo-root", ".");
const HISTORY_PATH = argValue("--history", "");
const NO_BROWSER = args.includes("--no-browser");

// ---- Pages URL 动态解析（不写死域名）----
// 优先级：--url 参数 > env PAGES_URL/GITHUB_PAGES_URL > GitHub API html_url > github.io 推导
function resolvePagesUrl() {
  const explicit = argValue("--url", "");
  if (explicit) return explicit.replace(/\/+$/, "") + "/";

  const envUrl = process.env.PAGES_URL || process.env.GITHUB_PAGES_URL;
  if (envUrl) return envUrl.replace(/\/+$/, "") + "/";

  const repo = process.env.GITHUB_REPOSITORY;
  if (repo) {
    const [owner, name] = repo.split("/");
    // 1) API 查询（自定义域名优先）
    try {
      const token = process.env.GITHUB_TOKEN;
      const curlArgs = ["-fsSL", "--max-time", "15", "https://api.github.com/repos/" + repo + "/pages"];
      if (token) curlArgs.unshift("-H", "Authorization: Bearer " + token);
      const out = execFileSync("curl", curlArgs, { encoding: "utf8", timeout: 20000 });
      const htmlUrl = JSON.parse(out).html_url;
      if (htmlUrl) return htmlUrl.replace(/\/+$/, "") + "/";
    } catch (_) { /* API 失败走推导 */ }
    // 2) github.io 推导
    return "https://" + owner + ".github.io/" + name + "/";
  }
  return "";
}

// ---- 浏览器探测 ----
function probeChrome() {
  const candidates = [];
  if (process.env.CHROME_PATH) candidates.push(process.env.CHROME_PATH);
  if (process.env.CHROMIUM_PATH) candidates.push(process.env.CHROMIUM_PATH);
  for (const bin of ["chromium", "chromium-browser", "google-chrome", "google-chrome-stable", "chrome", "chrome-headless-shell"]) {
    try {
      const r = spawnSync("which", [bin], { encoding: "utf8" });
      if (r.status === 0 && r.stdout.trim()) candidates.push(r.stdout.trim());
    } catch (_) { /* ignore */ }
  }
  // playwright 安装目录
  const home = process.env.HOME || "/root";
  const msDirs = [
    path.join(home, ".cache", "ms-playwright"),
    path.join(home, "Library", "Caches", "ms-playwright"),
    path.join(home, "AppData", "Local", "ms-playwright"),
  ];
  for (const dir of msDirs) {
    try {
      if (!fs.existsSync(dir)) continue;
      for (const sub of fs.readdirSync(dir)) {
        if (!sub.startsWith("chromium")) continue;
        for (const subsub of fs.readdirSync(path.join(dir, sub))) {
          const p = path.join(dir, sub, subsub);
          if (fs.statSync(p).isFile() && fs.existsSync(p)) candidates.push(p);
        }
      }
    } catch (_) { /* ignore */ }
  }
  for (const c of candidates) {
    try {
      fs.accessSync(c, fs.constants.X_OK);
      return c;
    } catch (_) { /* ignore */ }
  }
  return null;
}

// ---- 真实浏览器访问：dump-dom 渲染后的页面 ----
function fetchRenderedDom(chromePath, url, timeoutMs = 60000) {
  const out = execFileSync(
    chromePath,
    [
      "--headless=new",
      "--no-sandbox",
      "--disable-gpu",
      "--disable-dev-shm-usage",
      "--disable-extensions",
      "--virtual-time-budget=12000",
      "--dump-dom",
      url,
    ],
    { encoding: "utf8", timeout: timeoutMs, maxBuffer: 64 * 1024 * 1024 }
  );
  return out;
}

// ---- 从 DOM 提取表头列名 ----
function extractHeadersFromDom(dom) {
  const headers = new Set();
  // 表头: <th><button class="sort-button"><span>列名</span>...
  const thRe = /<th[^>]*>[\s\S]*?<button[^>]*class="[^"]*sort-button[^"]*"[^>]*>[\s\S]*?<span>([\s\S]*?)<\/span>/g;
  let m;
  while ((m = thRe.exec(dom)) !== null) {
    const name = m[1]
      .replace(/<[^>]+>/g, "")
      .replace(/&amp;/g, "&")
      .replace(/&lt;/g, "<")
      .replace(/&gt;/g, ">")
      .replace(/&quot;/g, '"')
      .replace(/&#39;/g, "'")
      .replace(/&nbsp;/g, " ")
      .trim();
    if (name) headers.add(name);
  }
  return [...headers];
}

// ---- 归并知识库 ----
function loadMergeKnowledge(repoRoot, historyPath) {
  const kb = {
    aliasToCanonical: new Map(), // 别名列 -> 规范列
    knownColumns: new Set(),     // 历史出现过的全部列名（canonical + 别名）
    rawCanonicals: [],           // 知识库中声明的规范列（不含常规列骨架）
    staleCandidates: [],         // 别名条目（column, canonical, evidence）
    raw: null,
  };
  // 1. config/column_header_aliases.json（AI 修复链维护的别名映射）
  const aliasPath = path.join(repoRoot, "config", "column_header_aliases.json");
  if (fs.existsSync(aliasPath)) {
    try {
      const cfg = JSON.parse(fs.readFileSync(aliasPath, "utf8"));
      kb.raw = cfg;
      for (const item of cfg.aliases || []) {
        if (item.column && item.canonical) {
          kb.aliasToCanonical.set(item.column, item.canonical);
          kb.knownColumns.add(item.column);
          kb.knownColumns.add(item.canonical);
          kb.rawCanonicals.push(item.canonical);
          kb.staleCandidates.push({ column: item.column, canonical: item.canonical, evidence: item.evidence || "" });
        }
      }
    } catch (e) {
      console.error(`[scan] 读取 ${aliasPath} 失败: ${e.message}`);
    }
  }
  // 2. docs/filter_conditions.json columnAliases (canonical -> [alias])
  const fcPath = path.join(repoRoot, "docs", "filter_conditions.json");
  if (fs.existsSync(fcPath)) {
    try {
      const fc = JSON.parse(fs.readFileSync(fcPath, "utf8"));
      const ca = fc.columnAliases || {};
      for (const [canonical, aliases] of Object.entries(ca)) {
        kb.knownColumns.add(canonical);
        kb.rawCanonicals.push(canonical);
        for (const a of aliases || []) {
          kb.knownColumns.add(a);
          if (!kb.aliasToCanonical.has(a)) kb.aliasToCanonical.set(a, canonical);
        }
      }
    } catch (e) {
      console.error(`[scan] 读取 ${fcPath} 失败: ${e.message}`);
    }
  }
  // 3. 历史扫描记录（跨轮次持续归并：上次未归并的列名视为已知，避免重复报告）
  if (historyPath && fs.existsSync(historyPath)) {
    try {
      const hist = JSON.parse(fs.readFileSync(historyPath, "utf8"));
      const cols = hist.seenColumns || [];
      for (const c of cols) kb.knownColumns.add(c);
    } catch (_) { /* ignore */ }
  }
  return kb;
}

// ---- 归并扫描 ----
// regularColumns = 首行键（发布规范列骨架）；kb = 归并知识库（canonical + alias）
// 规则（按优先级）：
//   1. 列名 ∈ 知识库别名 → 归并命中（alias → canonical）
//   2. 列名 ∈ 知识库 canonical ∪ 常规列骨架 且 历史/知识库见过 → 规范命中（已归并）
//   3. 历史见过（跨轮次已收录）→ 历史命中（不重复报告）
//   4. 否则 → 待归并新列名（首次出现，无论常规列还是稀疏列，都报告）
function mergeScan(columnNames, regularColumns, kb, historyKnown) {
  const canonicalSet = new Set([...regularColumns, ...kb.rawCanonicals]);
  const canonicalHits = [];
  const aliasHits = [];
  const unmapped = [];
  for (const col of columnNames) {
    if (kb.aliasToCanonical.has(col)) {
      aliasHits.push({ column: col, canonical: kb.aliasToCanonical.get(col) });
    } else if (canonicalSet.has(col) && (kb.knownColumns.has(col) || historyKnown.has(col))) {
      canonicalHits.push(col);
    } else if (kb.knownColumns.has(col) || historyKnown.has(col)) {
      canonicalHits.push(col);
    } else {
      unmapped.push(col);
    }
  }
  // 已折叠别名：知识库别名不在当前数据列（已被 publish 归并折叠，或源站改名）
  const current = new Set(columnNames);
  const folded = kb.staleCandidates.filter((s) => !current.has(s.column));
  return { canonicalHits, aliasHits, unmapped, folded };
}

// ---- 主流程 ----
async function main() {
  const startedAt = new Date().toISOString();
  const pagesUrl = resolvePagesUrl();
  const kb = loadMergeKnowledge(REPO_ROOT, HISTORY_PATH);
  let dom = null;
  let browserUsed = null;

  if (!NO_BROWSER) {
    if (!pagesUrl) {
      console.error("[scan] 未指定 Pages URL（用 --url 或设 PAGES_URL/GITHUB_REPOSITORY），跳过浏览器 DOM 扫描");
    } else {
      const chrome = probeChrome();
      if (chrome) {
        try {
          dom = fetchRenderedDom(chrome, pagesUrl);
          browserUsed = chrome;
          console.error(`[scan] 浏览器渲染成功: ${chrome} (${dom.length} 字符)`);
        } catch (e) {
          console.error(`[scan] 浏览器渲染失败，回退数据文件: ${e.message}`);
        }
      } else {
        console.error("[scan] 未探测到浏览器，使用数据文件模式（--no-browser 同效）");
      }
    }
  }

  // 数据列：优先下载线上 latest.json，其次本地文件
  // 注意：必须取「全部行的键并集」——数据是宽表，稀疏/变体列只出现在部分行
  // （首行键 ~198，全行并集 ~1300+；变体列正是列名归并的目标空间）
  let dataColumns = [];
  let regularColumns = []; // 首行键（每行都有的常规列）
  let rowCount = 0;
  let dataSource = "";
  function collectColumns(rows) {
    const keys = new Set();
    for (let i = 0; i < rows.length; i += 1) {
      const r = rows[i];
      if (r && typeof r === "object") for (const k of Object.keys(r)) keys.add(k);
    }
    return [...keys];
  }
  if (DATA_PATH && fs.existsSync(DATA_PATH)) {
    try {
      const d = JSON.parse(fs.readFileSync(DATA_PATH, "utf8"));
      const rows = Array.isArray(d) ? d : d.rows || d.data || [];
      rowCount = rows.length;
      if (rows.length > 0) {
        regularColumns = Object.keys(rows[0]);
        dataColumns = collectColumns(rows);
      }
      dataSource = DATA_PATH;
    } catch (e) {
      console.error(`[scan] 读取 ${DATA_PATH} 失败: ${e.message}`);
    }
  }
  if (dataColumns.length === 0 && pagesUrl) {
    try {
      const raw = execFileSync("curl", ["-fsSL", "--max-time", "60", pagesUrl + "data/latest.json"], {
        encoding: "utf8", timeout: 70000, maxBuffer: 128 * 1024 * 1024,
      });
      const d = JSON.parse(raw);
      const rows = Array.isArray(d) ? d : d.rows || d.data || [];
      rowCount = rows.length;
      if (rows.length > 0) {
        regularColumns = Object.keys(rows[0]);
        dataColumns = collectColumns(rows);
      }
      dataSource = pagesUrl + "data/latest.json";
    } catch (e) {
      console.error(`[scan] 拉取线上数据失败: ${e.message}`);
    }
  }
  if (dataColumns.length === 0) {
    console.error("[scan] 无数据源（--data 文件缺失且无法拉取线上数据），输出空报告");
  }

  // 扫描列名集合：浏览器 DOM 表头 ∪ 数据列
  const domHeaders = dom ? extractHeadersFromDom(dom) : [];
  const scanColumns = [...new Set([...domHeaders, ...dataColumns])];

  // 历史记录（持续归并：未归列名进入历史后不再重复报告；新列名首次出现时报告）
  const histPath = HISTORY_PATH || path.join(REPO_ROOT, "site", "data", "column_scan_history.json");
  let historyKnown = new Set();
  if (fs.existsSync(histPath)) {
    try {
      const hist = JSON.parse(fs.readFileSync(histPath, "utf8"));
      historyKnown = new Set(hist.seenColumns || []);
    } catch (_) { /* ignore */ }
  }
  const result = mergeScan(scanColumns, regularColumns, kb, historyKnown);
  const newColumns = result.unmapped.filter((c) => !historyKnown.has(c));

  // 更新历史记录（本次扫描到的列名全部入历史）
  try {
    const seen = [...new Set([...historyKnown, ...scanColumns])];
    const hist = {
      updatedAt: startedAt,
      seenColumns: seen,
      lastScan: {
        totalScanned: scanColumns.length,
        mappedCount: result.canonicalHits.length + result.aliasHits.length,
        newColumns: newColumns,
      },
    };
    fs.mkdirSync(path.dirname(histPath), { recursive: true });
    fs.writeFileSync(histPath, JSON.stringify(hist, null, 2), "utf8");
  } catch (e) {
    console.error(`[scan] 写历史记录失败: ${e.message}`);
  }

  const report = {
    scannedAt: startedAt,
    url: pagesUrl,
    browserUsed: browserUsed,
    dataSource: dataSource,
    rowCount: rowCount,
    headerCount: domHeaders.length,
    dataColumnCount: dataColumns.length,      // 全行键并集（含稀疏/变体列）
    regularColumnCount: regularColumns.length, // 首行键（常规列）
    sparseColumnCount: dataColumns.length - regularColumns.length,
    totalScanned: scanColumns.length,
    mappedCount: result.canonicalHits.length + result.aliasHits.length,
    aliasMappedCount: result.aliasHits.length,
    newColumns: newColumns.slice(0, 200),     // 本次新出现的未归并列名（持续扫描的核心产出，限长）
    newColumnsTotal: newColumns.length,
    unmappedCount: result.unmapped.length,
    unmapped: result.unmapped.slice(0, 200),  // 知识库+历史均未覆盖的列名
    aliasHits: result.aliasHits,              // 命中别名映射的归并记录
    foldedAliases: result.folded,             // 知识库中已不在数据列出现的别名（已被 publish 折叠，可清理）
    domHeadersOnly: domHeaders.filter((c) => !dataColumns.includes(c)),
  };

  const json = JSON.stringify(report, null, 2);
  console.log(json);
  if (OUT_PATH) {
    fs.mkdirSync(path.dirname(OUT_PATH), { recursive: true });
    fs.writeFileSync(OUT_PATH, json, "utf8");
  }
  // 汇总到 stderr（不污染 stdout 的 JSON）
  console.error(
    `[scan] 扫描列名 ${report.totalScanned} 个：规范命中 ${report.mappedCount - report.aliasMappedCount}，别名归并 ${report.aliasMappedCount}，新增未归并 ${report.newColumns.length}，已折叠别名 ${report.foldedAliases.length}`
  );
  if (report.newColumns.length > 0) {
    console.error(`[scan] 新增列名（待归并）: ${report.newColumns.join(" | ")}`);
  }
  process.exit(0);
}

main().catch((e) => {
  console.error(`[scan] 失败: ${e.message}`);
  process.exit(1);
});

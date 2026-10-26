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
 *        - 命中 filter_conditions.json 明确声明的列名（defaultVisibleColumns、
 *          conditions[].field/fields、filterTaxonomy[].sections[].columns）→ 已归并
 *        - 未命中 → 待审证据，进入完整 pendingColumns 队列；历史仅用于首次通知去重，
 *          永远不能把未知列批准为规范
 *   4. 输出 JSON 报告（stdout + 可选文件），带 inputSha256 / knowledgeSources 供评审绑定；
 *      严格模式下数据、历史或知识库读写/结构失败一律阻断部署。
 *   5. Pages URL 不写死：--url 显式指定，否则依次取 env PAGES_URL/GITHUB_PAGES_URL、
 *      GitHub API（repos/{owner}/{repo}/pages html_url）、{owner}.github.io/{repo}/ 推导。
 *
 * 用法:
 *   node scripts/scan_pages_columns.js [--url https://<pages-domain>/]
 *       [--data /path/to/latest.json] [--out /path/to/scan-report.json]
 *       [--repo-root .] [--history /path/to/history.json] [--no-browser]
 *       [--require-data] 本地数据缺失、损坏、空或历史读写失败时退出 1，禁止回退其它数据
 *
 * 环境变量: CHROME_PATH 浏览器可执行文件；PAGES_URL / GITHUB_PAGES_URL 线上 Pages 根 URL；
 *           GITHUB_REPOSITORY（owner/repo）用于 API 查询/推导 Pages 域名。
 */
const fs = require("node:fs");
const crypto = require("node:crypto");
const path = require("node:path");
const { execFileSync, spawnSync } = require("node:child_process");

// pending 列 id 的 schema 版本：只绑定「版本 + 精确列名」，不含时间/样本，便于跨轮去重
const PENDING_ID_SCHEMA = "pages-column-scan/pending/v1";
const SAMPLE_MAX_CHARS = 120;
const IDENTITY_FIELDS = ["品牌", "车系", "车型名称", "车款ID", "年款"];

function sha256Hex(input) {
  return crypto.createHash("sha256").update(input).digest("hex");
}

function isNonEmptyString(v) {
  return typeof v === "string" && v.trim() !== "";
}

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
const REQUIRE_DATA = args.includes("--require-data");

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
      if (token && /[\x00-\x1f\x7f]/.test(token)) throw new Error("Invalid credential characters");
      const curlArgs = ["--disable", "--config", "-", "-fsSL", "--max-time", "15",
        "https://api.github.com/repos/" + repo + "/pages"];
      // 凭据仅经 stdin 传给 curl；禁止放进 URL/进程参数或临时文件。
      const input = token ? "header = " + JSON.stringify("Authorization: Bearer " + token) + "\n" : "";
      const out = execFileSync("curl", curlArgs, { encoding: "utf8", timeout: 20000, input });
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
// 只收录「配置文件里明确声明的列名」：
//   1. config/column_header_aliases.json 的 aliases[].column（显式别名，优先级最高）
//   2. docs/filter_conditions.json 的 columnAliases（canonical → [alias]）
//   3. docs/filter_conditions.json 明确声明的列名：defaultVisibleColumns、
//      conditions[].field / conditions[].fields[]、filterTaxonomy[].sections[].columns[]
// 明确不收录：label / id / columnPatterns / genericFields / hiddenByDefault /
//             dropIfUniformPositive / 首行键 / 历史 seenColumns（这些都不是「列名声明」）
function readKnowledgeFile(repoRoot, relPath, strict) {
  const abs = path.join(repoRoot, relPath);
  const src = { path: relPath, status: "missing", sha256: null, bytes: 0 };
  if (!fs.existsSync(abs)) return { src, parsed: null };
  let buf;
  try {
    buf = fs.readFileSync(abs);
  } catch (e) {
    src.status = "invalid";
    src.error = `读取失败: ${e.message}`;
    if (strict) throw new Error(`--require-data: 读取知识库 ${relPath} 失败: ${e.message}`);
    process.stderr.write(`[scan] 读取 ${relPath} 失败: ${e.message}\n`);
    return { src, parsed: null };
  }
  src.sha256 = sha256Hex(buf);
  src.bytes = buf.length;
  try {
    const parsed = JSON.parse(buf.toString("utf8"));
    src.status = "ok";
    return { src, parsed };
  } catch (e) {
    src.status = "invalid";
    src.error = `JSON 解析失败: ${e.message}`;
    if (strict) throw new Error(`--require-data: 知识库 ${relPath} 不是合法 JSON: ${e.message}`);
    process.stderr.write(`[scan] 读取 ${abs} 失败: ${e.message}\n`);
    return { src, parsed: null };
  }
}

// 校验并收集「显式列名声明」；结构不符即抛错（strict 由调用方决定是否中止）
function collectDeclaredColumns(fc, fail) {
  const declared = new Set();
  const addList = (value, where) => {
    if (value === undefined) return;
    if (!Array.isArray(value)) fail(`${where} 必须是字符串数组`);
    for (const item of value) {
      if (!isNonEmptyString(item)) fail(`${where} 含非字符串或空白列名: ${JSON.stringify(item)}`);
      declared.add(item);
    }
  };
  if (fc === null || typeof fc !== "object" || Array.isArray(fc)) fail("filter_conditions 顶层必须是对象");
  addList(fc.defaultVisibleColumns, "defaultVisibleColumns");
  if (fc.conditions !== undefined) {
    if (!Array.isArray(fc.conditions)) fail("conditions 必须是数组");
    fc.conditions.forEach((cond, i) => {
      if (!cond || typeof cond !== "object" || Array.isArray(cond)) fail(`conditions[${i}] 必须是对象`);
      if (cond.field !== undefined) addList([cond.field], `conditions[${i}].field`);
      addList(cond.fields, `conditions[${i}].fields`);
    });
  }
  if (fc.filterTaxonomy !== undefined) {
    if (!Array.isArray(fc.filterTaxonomy)) fail("filterTaxonomy 必须是数组");
    fc.filterTaxonomy.forEach((tax, i) => {
      if (!tax || typeof tax !== "object" || Array.isArray(tax)) fail(`filterTaxonomy[${i}] 必须是对象`);
      if (tax.sections === undefined) return;
      if (!Array.isArray(tax.sections)) fail(`filterTaxonomy[${i}].sections 必须是数组`);
      tax.sections.forEach((sec, k) => {
        if (!sec || typeof sec !== "object" || Array.isArray(sec)) fail(`filterTaxonomy[${i}].sections[${k}] 必须是对象`);
        addList(sec.columns, `filterTaxonomy[${i}].sections[${k}].columns`);
      });
    });
  }
  if (fc.columnAliases !== undefined) {
    const ca = fc.columnAliases;
    if (!ca || typeof ca !== "object" || Array.isArray(ca)) fail("columnAliases 必须是对象");
    for (const [canonical, aliases] of Object.entries(ca)) {
      if (!isNonEmptyString(canonical)) fail("columnAliases 含空 canonical");
      addList(aliases, `columnAliases[${canonical}]`);
    }
  }
  return declared;
}

function collectAliasEntries(cfg, fail) {
  if (!cfg || typeof cfg !== "object" || Array.isArray(cfg)) fail("别名文件顶层必须是对象");
  if (!Array.isArray(cfg.aliases)) fail("别名文件缺少 aliases 数组");
  const entries = [];
  cfg.aliases.forEach((item, i) => {
    if (!item || typeof item !== "object" || Array.isArray(item)) fail(`aliases[${i}] 必须是对象`);
    if (!isNonEmptyString(item.column)) fail(`aliases[${i}].column 必须是非空字符串`);
    if (!isNonEmptyString(item.canonical)) fail(`aliases[${i}].canonical 必须是非空字符串`);
    entries.push(item);
  });
  return entries;
}

function loadMergeKnowledge(repoRoot, historyPath, strict) {
  const kb = {
    aliasToCanonical: new Map(), // 别名列 -> 规范列
    knownColumns: new Set(),     // 显式知识库中的规范列与别名
    rawCanonicals: [],           // 知识库中声明的规范列（不含常规列骨架）
    staleCandidates: [],         // 别名条目（column, canonical, evidence）
    sources: {},                 // 实际读取的配置原字节 hash
    errors: [],                  // 宽松模式下的知识库问题（不得据此自称完整）
    raw: null,
  };
  const fail = (relPath) => (msg) => {
    const err = new Error(`--require-data: 知识库 ${relPath} 结构非法: ${msg}`);
    err.knowledgePath = relPath;
    throw err;
  };
  // 1. config/column_header_aliases.json（AI 修复链维护的别名映射）
  const aliasRel = "config/column_header_aliases.json";
  const aliasRead = readKnowledgeFile(repoRoot, aliasRel, strict);
  kb.sources[aliasRel] = aliasRead.src;
  if (aliasRead.src.status === "ok") {
    try {
      const entries = collectAliasEntries(aliasRead.parsed, fail(aliasRel));
      kb.raw = aliasRead.parsed;
      for (const item of entries) {
        kb.aliasToCanonical.set(item.column, item.canonical);
        kb.knownColumns.add(item.column);
        kb.knownColumns.add(item.canonical);
        kb.rawCanonicals.push(item.canonical);
        kb.staleCandidates.push({ column: item.column, canonical: item.canonical, evidence: item.evidence || "" });
      }
    } catch (e) {
      if (strict) throw e;
      aliasRead.src.status = "invalid";
      aliasRead.src.error = e.message;
      kb.errors.push({ path: aliasRel, error: e.message });
      process.stderr.write(`[scan] ${aliasRel} 结构非法: ${e.message}\n`);
    }
  } else if (aliasRead.src.status === "invalid") {
    kb.errors.push({ path: aliasRel, error: aliasRead.src.error });
  }
  // 2. docs/filter_conditions.json：columnAliases + 明确声明的列名
  const fcRel = "docs/filter_conditions.json";
  const fcRead = readKnowledgeFile(repoRoot, fcRel, strict);
  kb.sources[fcRel] = fcRead.src;
  if (fcRead.src.status === "ok") {
    try {
      const fc = fcRead.parsed;
      const declared = collectDeclaredColumns(fc, fail(fcRel));
      for (const col of declared) kb.knownColumns.add(col);
      for (const [canonical, aliases] of Object.entries(fc.columnAliases || {})) {
        kb.knownColumns.add(canonical);
        kb.rawCanonicals.push(canonical);
        for (const a of aliases || []) {
          kb.knownColumns.add(a);
          if (!kb.aliasToCanonical.has(a)) kb.aliasToCanonical.set(a, canonical);
        }
      }
    } catch (e) {
      if (strict) throw e;
      fcRead.src.status = "invalid";
      fcRead.src.error = e.message;
      kb.errors.push({ path: fcRel, error: e.message });
      process.stderr.write(`[scan] ${fcRel} 结构非法: ${e.message}\n`);
    }
  } else if (fcRead.src.status === "invalid") {
    kb.errors.push({ path: fcRel, error: fcRead.src.error });
  }
  // 见过的列不代表已完成映射；历史去重在 newColumns 计算时单独执行。
  return kb;
}

// ---- pending 队列（完整待审证据，不截断）----
// 每条都只是「待审证据」：status 恒为 pending_review，不携带任何批准/映射/隐藏标记。
function buildPendingColumns(unmapped, rows, source) {
  const byColumn = new Map();
  for (const col of unmapped) {
    byColumn.set(col, { occurrences: 0, nonEmptyCount: 0, samples: [], seen: new Set() });
  }
  rows.forEach((row, rowIndex) => {
    if (!row || typeof row !== "object" || Array.isArray(row)) return;
    const identity = {};
    for (const f of IDENTITY_FIELDS) {
      if (row[f] !== undefined && row[f] !== null && String(row[f]).trim() !== "") identity[f] = String(row[f]);
    }
    for (const [col, stat] of byColumn) {
      if (!Object.prototype.hasOwnProperty.call(row, col)) continue;
      stat.occurrences += 1;
      const raw = row[col];
      const jsonValue = JSON.stringify(raw);
      const value = raw === null || raw === undefined ? "" :
        typeof raw === "string" ? raw : jsonValue;
      if (value.trim() === "") continue;
      stat.nonEmptyCount += 1;
      if (stat.samples.length >= 3 || stat.seen.has(jsonValue)) continue;
      stat.seen.add(jsonValue);
      const chars = [...value];
      const truncated = chars.length > SAMPLE_MAX_CHARS;
      stat.samples.push({
        rowIndex,
        value: truncated ? chars.slice(0, SAMPLE_MAX_CHARS).join("") : value,
        truncated,
        originalLength: chars.length,
        valueSha256: sha256Hex(value), // 未截断展示文本；原 JSON 类型另行绑定
        valueType: Array.isArray(raw) ? "array" : typeof raw,
        jsonValueSha256: sha256Hex(jsonValue), // 区分数字/字符串与不同嵌套对象
        dataSource: row["数据来源"] === undefined ? null : row["数据来源"],
        identity,
      });
    }
  });
  return [...byColumn.entries()]
    .sort((a, b) => Buffer.compare(Buffer.from(a[0], "utf8"), Buffer.from(b[0], "utf8")))
    .map(([column, stat]) => ({
      id: sha256Hex(`${PENDING_ID_SCHEMA}\n${column}`),
      column,
      status: "pending_review",
      source,
      occurrences: stat.occurrences,
      nonEmptyCount: stat.nonEmptyCount,
      samples: stat.samples,
    }));
}

// ---- 归并扫描 ----
// regularColumns = 首行键（发布规范列骨架）；kb = 归并知识库（canonical + alias）
// 规则（按优先级）：
//   1. 列名 ∈ 知识库别名 → 归并命中（alias → canonical）
//   2. 列名 ∈ 显式知识库 → 规范命中（已归并）
//   3. 否则 → 仍待归并；历史只决定是否首次通知
function mergeScan(columnNames, regularColumns, kb, historyKnown) {
  const canonicalSet = new Set([...regularColumns, ...kb.rawCanonicals]);
  const canonicalHits = [];
  const aliasHits = [];
  const unmapped = [];
  for (const col of columnNames) {
    if (kb.aliasToCanonical.has(col)) {
      aliasHits.push({ column: col, canonical: kb.aliasToCanonical.get(col) });
    } else if (canonicalSet.has(col) && kb.knownColumns.has(col)) {
      canonicalHits.push(col);
    } else if (kb.knownColumns.has(col)) {
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
  if (REQUIRE_DATA && (!DATA_PATH || !fs.existsSync(DATA_PATH))) {
    throw new Error("--require-data needs an existing local --data file");
  }
  const startedAt = new Date().toISOString();
  const pagesUrl = REQUIRE_DATA ? "" : resolvePagesUrl();
  // 知识库先行：严格模式下坏 JSON/坏结构必须在此中止，不得写历史或覆盖报告
  const kb = loadMergeKnowledge(REPO_ROOT, HISTORY_PATH, REQUIRE_DATA);
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
  let inputSha256 = null;  // 实际本地输入的原字节 hash（未做任何规范化）
  let rowsForEvidence = [];
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
      const dataBuf = fs.readFileSync(DATA_PATH);
      inputSha256 = sha256Hex(dataBuf);
      const d = JSON.parse(dataBuf.toString("utf8"));
      const rows = Array.isArray(d) ? d : d.rows || d.data || [];
      if (REQUIRE_DATA && (!Array.isArray(rows) || rows.some((row) =>
        !row || typeof row !== "object" || Array.isArray(row)))) {
        throw new Error("--require-data needs an array of row objects");
      }
      rowCount = rows.length;
      if (rows.length > 0) {
        regularColumns = Object.keys(rows[0]);
        dataColumns = collectColumns(rows);
      }
      rowsForEvidence = rows;
      dataSource = DATA_PATH;
    } catch (e) {
      console.error(`[scan] 读取 ${DATA_PATH} 失败: ${e.message}`);
    }
  }
  if (REQUIRE_DATA && dataColumns.length === 0) {
    throw new Error("--require-data needs a valid nonempty local row dataset");
  }
  if (dataColumns.length === 0 && pagesUrl) {
    try {
      const raw = execFileSync("curl", ["-fsSL", "--max-time", "60", pagesUrl + "data/latest.json"], {
        encoding: "utf8", timeout: 70000, maxBuffer: 128 * 1024 * 1024,
      });
      inputSha256 = sha256Hex(Buffer.from(raw, "utf8"));
      const d = JSON.parse(raw);
      const rows = Array.isArray(d) ? d : d.rows || d.data || [];
      rowCount = rows.length;
      if (rows.length > 0) {
        regularColumns = Object.keys(rows[0]);
        dataColumns = collectColumns(rows);
      }
      rowsForEvidence = rows;
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

  // 历史只抑制重复首次通知，不能批准未知列。
  const histPath = HISTORY_PATH || path.join(REPO_ROOT, "site", "data", "column_scan_history.json");
  let historyKnown = new Set();
  if (fs.existsSync(histPath)) {
    try {
      const hist = JSON.parse(fs.readFileSync(histPath, "utf8"));
      historyKnown = new Set(hist.seenColumns || []);
    } catch (e) {
      if (REQUIRE_DATA) throw new Error(`--require-data: 读取历史记录失败: ${e.message}`);
    }
  }
  const result = mergeScan(scanColumns, regularColumns, kb, historyKnown);
  const newColumns = result.unmapped.filter((c) => !historyKnown.has(c));
  // 完整待审队列：覆盖每一个 unmapped 列，不截断、按列名排序，可跨轮去重
  const pendingColumns = buildPendingColumns(result.unmapped, rowsForEvidence, dataSource || "unknown");

  // 更新历史记录（本次扫描到的列名全部入历史）
  try {
    const seen = [...new Set([...historyKnown, ...scanColumns])];
    const hist = {
      updatedAt: startedAt,
      seenColumns: seen,
      unmappedColumns: result.unmapped,
      lastScan: {
        totalScanned: scanColumns.length,
        mappedCount: result.canonicalHits.length + result.aliasHits.length,
        newColumns: newColumns,
      },
      pendingColumns: pendingColumns.map((i) => i.column),
    };
    fs.mkdirSync(path.dirname(histPath), { recursive: true });
    fs.writeFileSync(histPath, JSON.stringify(hist, null, 2), "utf8");
  } catch (e) {
    if (REQUIRE_DATA) throw new Error(`--require-data: 写历史记录失败: ${e.message}`);
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
    inputSha256: inputSha256,                 // 实际本地输入原字节 hash（本报告未做任何再采集）
    knowledgeSources: kb.sources,             // 实际读取的配置原字节 hash（缺失/非法明确标注）
    knowledgeErrors: kb.errors,               // 宽松模式下的知识库问题；非空即不可称完整
    complete: kb.errors.length === 0,         // 仅表示知识库读取完整，不代表已闭环修复
    newColumns: newColumns.slice(0, 200),     // 本次新出现的未归并列名（兼容字段，限长）
    newColumnsTotal: newColumns.length,
    unmappedCount: result.unmapped.length,
    unmapped: result.unmapped.slice(0, 200),  // 兼容字段；完整集合见 pendingColumns
    pendingCount: pendingColumns.length,
    pendingColumns: pendingColumns,           // 完整待审证据队列（不截断，按列名排序）
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
    `[scan] 扫描列名 ${report.totalScanned} 个：规范命中 ${report.mappedCount - report.aliasMappedCount}，别名归并 ${report.aliasMappedCount}，新增未归并 ${report.newColumnsTotal}，待审 ${report.pendingCount}，已折叠别名 ${report.foldedAliases.length}`
  );
  if (report.newColumns.length > 0) {
    console.error(`[scan] 新增列名（待归并）: ${report.newColumns.join(" | ")}`);
  }
  // 用 exitCode 而非 process.exit：报告可能很大，立即退出会截断管道中的 stdout
  process.exitCode = 0;
}

main().catch((e) => {
  console.error(`[scan] 失败: ${e.message}`);
  process.exitCode = 1;
});

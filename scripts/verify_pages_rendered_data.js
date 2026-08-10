"use strict";
/**
 * verify_pages_rendered_data.js — 部署后数据验证：用 app.js 的真实渲染逻辑
 * （vm 加载 + CARS_TEST_HOOKS）解析部署产物，断言最终数据符合预期。
 *
 * 用法: node scripts/verify_pages_rendered_data.js <latest.json 路径> [预期行数]
 * 失败 exit 1 → workflow 中止（坏数据不发布）。
 */
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const assert = require("node:assert/strict");

const dataPath = process.argv[2] || "site/data/latest.json";
const minRows = Number(process.argv[3] || 10000);

// ---- 最小 DOM mock（与 tests/pages_ui.test.js 相同模式）----
class FakeElement {
  constructor(tagName = "div") {
    this.children = [];
    this.className = "";
    this.classList = { contains: () => false };
    this.dataset = {};
    this.disabled = false;
    this.hidden = false;
    this.listeners = {};
    this._textContent = "";
    this.value = "";
    this.validity = { valid: true };
    this.attributes = {};
    this.parentNode = null;
    this.tagName = String(tagName).toUpperCase();
  }
  get textContent() { return this._textContent; }
  set textContent(v) { this._textContent = String(v); this.children = []; }
  appendChild(c) { this.children.push(c); return c; }
  removeChild(c) { const i = this.children.indexOf(c); if (i >= 0) this.children.splice(i, 1); return c; }
  addEventListener() {}
  removeEventListener() {}
  setAttribute(k, v) { this.attributes[k] = String(v); }
  getAttribute(k) { return this.attributes[k] == null ? null : String(this.attributes[k]); }
  removeAttribute(k) { delete this.attributes[k]; }
  focus() {}
  closest() { return null; }
  querySelector() { return null; }
  querySelectorAll() { return []; }
  getBoundingClientRect() { return { width: 0, height: 0, top: 0, left: 0 }; }
}

function loadAppHooks() {
  const elements = {};
  const ids = ["dataMeta", "dataTable", "cardList", "filterPanel", "activeFilters",
    "brandFilter", "seriesFilter", "searchInput", "resultCount", "resultList",
    "columnPanel", "downloadList", "centerBrandFilter", "centerSeriesFilter",
    "saveFilterBtn", "restoreFilterBtn", "exportCsvBtn", "exportJsonBtn"];
  ids.forEach((id) => { elements[id] = new FakeElement("div"); });
  elements.searchInput = new FakeElement("input");
  const documentStub = {
    getElementById: (id) => elements[id] || new FakeElement("div"),
    createElement: (t) => new FakeElement(t),
    createDocumentFragment: () => new FakeElement(),
    createTextNode: (text) => ({ textContent: String(text) }),
    querySelector: () => null,
    querySelectorAll: () => [],
    addEventListener: () => {},
    body: new FakeElement("body"),
    documentElement: new FakeElement("html"),
  };
  const context = {
    Blob,
    TextDecoder,
    TextEncoder,
    Uint8Array,
    URL: { createObjectURL: () => "blob:test", revokeObjectURL() {} },
    atob,
    btoa,
    crypto: require("node:crypto").webcrypto,
    document: documentStub,
    fetch: () => new Promise(() => {}),
    localStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} },
    navigator: { clipboard: { writeText: () => Promise.resolve() }, userAgent: "verify" },
    console,
    window: {}
  };
  context.window.window = context.window;
  context.window.crypto = require("node:crypto").webcrypto;
  context.window.document = documentStub;
  const appPath = path.join(__dirname, "..", "docs", "app.js");
  const source = fs.readFileSync(appPath, "utf8").replace(
    /\}\(\)\);\s*$/,
    `window.CARS_TEST_HOOKS = {
      initializeRows: initializeRows,
      groupRowsBySeries: groupRowsBySeries,
      getFilteredRows: getFilteredRows,
      normEnumValue: normEnumValue,
      state: state
    };
  }());`
  );
  try {
    vm.runInNewContext(source, context, { filename: appPath });
  } catch (e) {
    console.error("VM ERROR:", e && e.message);
    process.exit(2);
  }
  if (!context.window.CARS_TEST_HOOKS) {
    console.error("hooks missing; window keys:", Object.keys(context.window).slice(0, 20).join(","));
    process.exit(2);
  }
  return context.window.CARS_TEST_HOOKS;
}

// ---- 验证 ----
const hooks = loadAppHooks();
const rows = JSON.parse(fs.readFileSync(dataPath, "utf8"));
assert.ok(Array.isArray(rows) && rows.length >= minRows,
  `行数不足: ${rows.length} < ${minRows}`);

hooks.initializeRows(rows);
const filteredRows = hooks.getFilteredRows();
const groups = hooks.groupRowsBySeries(filteredRows);


const byName = {};
groups.forEach((g) => { byName[g.name] = g.rows.length; });

// 关键系列预期（dedupe 后）——数据变化时同步更新此断言
const EXPECTED_SERIES = { "别克至境E7": 3, "领克900": 7, "乐道L90": 11 };
let seriesFail = false;
Object.keys(EXPECTED_SERIES).forEach((name) => {
  const actual = byName[name];
  if (actual !== EXPECTED_SERIES[name]) {
    seriesFail = true;
    console.error(`系列 ${name}: 预期 ${EXPECTED_SERIES[name]} 行, 实际 ${actual} 行`);
  }
});
if (seriesFail) { process.exit(1); }

// 能源类型无来源前缀（样本 200 条）
let prefixCount = 0;
let checked = 0;
rows.forEach((r) => {
  const v = r["能源类型"];
  if (v == null) { return; }
  checked += 1;
  if (checked > 200) { return; }
  const norm = hooks.normEnumValue(String(v));
  if (/[:：]/.test(norm)) { prefixCount += 1; }
});
assert.ok(prefixCount === 0,
  `能源类型经 normEnumValue 后仍含来源前缀 ${prefixCount} 条`);

// 数据来源无重复标签（同标签重复 >=3 次视为异常）
let dupSources = 0;
rows.forEach((r) => {
  const label = String(r["数据来源"] || "");
  const parts = label.split("、");
  const seen = new Set();
  parts.forEach((p) => { if (p) seen.add(p); });
  if (seen.size > 0 && parts.length - seen.size >= 3) { dupSources += 1; }
});
assert.ok(dupSources === 0, `数据来源重复标签行 ${dupSources} 条`);

console.log(`✅ 部署数据验证通过: ${rows.length} 行, 系列 ${Object.keys(EXPECTED_SERIES).join("/")} 符合预期, 能源类型/数据来源干净`);

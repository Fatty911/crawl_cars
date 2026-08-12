"use strict";
/**
 * pages_frontend_facts.js — 用 app.js 真实渲染逻辑（vm + CARS_TEST_HOOKS）解析
 * 部署数据，输出"前端视角事实" JSON，供 AI 修复链（single-source-repair）自发现
 * 数据问题（单源分布、999 残留、纯电续航标注、关键系列行数、渲染分组等）。
 *
 * 用法: node scripts/pages_frontend_facts.js <latest.json 路径> [输出 json 路径]
 * 输出: 前端视角事实 JSON（stdout + 可选文件），始终 exit 0（只采集不阻断）。
 */
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const dataPath = process.argv[2] || "site/data/latest.json";
const outPath = process.argv[3] || "";

// ---- 最小 DOM mock（与 verify_pages_rendered_data.js 相同模式）----
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
    querySelector: () => null,
    querySelectorAll: () => [],
    addEventListener: () => {},
    documentElement: new FakeElement("html"),
    body: new FakeElement("body"),
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
    navigator: { clipboard: { writeText: () => Promise.resolve() }, userAgent: "facts" },
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
    throw new Error("VM ERROR: " + (e && e.message));
  }
  const hooks = context.window.CARS_TEST_HOOKS;
  if (!hooks) { throw new Error("CARS_TEST_HOOKS not found in app.js"); }
  return hooks;
}

function main() {
  const rows = JSON.parse(fs.readFileSync(dataPath, "utf8"));
  const hooks = loadAppHooks();
  const facts = { dataPath, rows: rows.length };

  try {
    hooks.initializeRows(rows);
    const filteredRows = hooks.getFilteredRows();
    facts.filteredRows = filteredRows.length;
    const groups = hooks.groupRowsBySeries(filteredRows);
    facts.seriesGroups = groups.length;
    const byName = {};
    groups.forEach((g) => { byName[g.name] = g.rows.length; });
    facts.keySeriesRows = {
      "别克至境E7": byName["别克至境E7"] || 0,
      "领克900": byName["领克900"] || 0,
      "乐道L90": byName["乐道L90"] || 0,
    };
  } catch (e) {
    facts.renderError = String(e && e.message || e);
  }

  // raw data facts
  let zero = 0, nineNineNine = 0, annotated = 0, plainNum = 0, empty = 0;
  const singleSrc = { "仅汽车之家": 0, "仅懂车帝": 0, "仅易车": 0 };
  let multiSrc = 0, energyPrefix = 0, energyChecked = 0;
  rows.forEach((r) => {
    const v = String(r["纯电续航(km)"] || "").trim();
    if (v === "0") zero += 1;
    else if (v === "999") nineNineNine += 1;
    else if (v.indexOf(":") !== -1) annotated += 1;
    else if (v && v !== "-") plainNum += 1;
    else empty += 1;
    const label = String(r["数据来源"] || "");
    if (label === "仅汽车之家") singleSrc["仅汽车之家"] += 1;
    else if (label === "仅懂车帝") singleSrc["仅懂车帝"] += 1;
    else if (label === "仅易车") singleSrc["仅易车"] += 1;
    else if (label) multiSrc += 1;
    const et = r["能源类型"];
    if (et != null && energyChecked < 200) {
      energyChecked += 1;
      try { if (/[:：]/.test(hooks.normEnumValue(String(et)))) energyPrefix += 1; } catch (e) {}
    }
  });
  facts.evRange = { zero, nineNineNine, annotated, plainNum, empty };
  facts.sources = { single: singleSrc, multi: multiSrc };

  // SPU-level single-source analysis (品牌|车系|年款)
  const spuAll = new Map();   // spu -> rows
  const spuSrcs = new Map();  // spu -> set of source labels
  rows.forEach((r) => {
    const spu = `${r["品牌"] || ""}|${r["车系"] || ""}|${r["年款"] || ""}`;
    spuAll.set(spu, (spuAll.get(spu) || 0) + 1);
    const label = String(r["数据来源"] || "");
    if (!spuSrcs.has(spu)) spuSrcs.set(spu, new Set());
    if (label) spuSrcs.get(spu).add(label);
  });
  let pureSingleSpu = 0, mergeableSpu = 0, pureSingleSkus = 0;
  spuSrcs.forEach((srcs, spu) => {
    const hasMulti = Array.from(srcs).some((s) => s.indexOf("+") !== -1);
    if (hasMulti) mergeableSpu += 1;
    else { pureSingleSpu += 1; pureSingleSkus += spuAll.get(spu); }
  });
  facts.spu = { total: spuAll.size, pureSingleSpu, mergeableSpu, pureSingleSkus };
  facts.energyPrefix = energyPrefix;

  const out = JSON.stringify(facts, null, 2);
  console.log(out);
  if (outPath) { fs.writeFileSync(outPath, out); }
}

main();

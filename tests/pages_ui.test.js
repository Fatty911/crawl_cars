"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

class FakeElement {
  constructor(tagName = "div") {
    this.children = [];
    this.className = "";
    this.classList = { contains: (name) => this.className.split(/\s+/).includes(name) };
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
  set textContent(value) {
    this._textContent = String(value);
    this.children = [];
  }

  addEventListener(type, listener) { this.listeners[type] = listener; }
  click() {}
  closest(selector) {
    if (selector.startsWith(".") && this.classList.contains(selector.slice(1))) { return this; }
    return this.parentNode ? this.parentNode.closest(selector) : null;
  }
  querySelectorAll() { return []; }
  remove() {
    if (this.parentNode) {
      this.parentNode.children = this.parentNode.children.filter((child) => child !== this);
    }
  }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  getAttribute(name) { return this.attributes[name]; }

  appendChild(child) {
    child.parentNode = this;
    this.children.push(child);
    return child;
  }

  dispatch(type, event = {}) {
    this.listeners[type](Object.assign({ preventDefault() {}, target: this }, event));
  }
}

function loadAppForTest() {
  const elements = new Map();
  const document = {
    body: new FakeElement(),
    createDocumentFragment: () => new FakeElement(),
    createElement: (tagName) => new FakeElement(tagName),
    createTextNode: (text) => ({ textContent: text }),
    getElementById(id) {
      if (!elements.has(id)) {
        elements.set(id, new FakeElement());
      }
      return elements.get(id);
    }
  };
  const context = {
    Blob,
    TextDecoder,
    TextEncoder,
    Uint8Array,
    URL: { createObjectURL: () => "blob:test", revokeObjectURL() {} },
    atob,
    btoa,
    crypto,
    document,
    fetch: () => new Promise(() => {}),
    localStorage: { getItem: () => null, removeItem() {}, setItem() {} },
    navigator: { clipboard: { writeText: () => Promise.resolve() } },
    window: {}
  };
  context.window.window = context.window;
  context.window.crypto = crypto;

  const appPath = path.join(__dirname, "..", "docs", "app.js");
  const source = fs.readFileSync(appPath, "utf8").replace(
    /\}\(\)\);\s*$/,
    `window.CARS_TEST_HOOKS = {
      atomicSources: typeof atomicSources === "function" ? atomicSources : undefined,
      getFilteredRows: getFilteredRows,
      groupRowsBySeries: groupRowsBySeries,
      initializeRows: initializeRows,
      renderEverything: renderEverything,
      renderResultsOnly: renderResultsOnly,
      renderSelectedTags: renderSelectedTags,
      snapshotFilters: snapshotFilters,
      applySnapshot: applySnapshot,
      getFilteredRows: getFilteredRows,
      state: state
    };
  }());`
  );
  vm.runInNewContext(source, context, { filename: appPath });
  return { elements, hooks: context.window.CARS_TEST_HOOKS };
}

function row(source, year, name) {
  return {
    "数据来源": source,
    "品牌": "测试品牌",
    "车系": "测试车系",
    "车型名称": name,
    "年款": String(year)
  };
}

test("Pages only uses the deduplicated 2022+ display set for source coverage and totals", () => {
  const { elements, hooks } = loadAppForTest();

  assert.equal(typeof hooks.atomicSources, "function");
  assert.deepEqual(
    Array.from(hooks.atomicSources("汽车之家+懂车帝(车系级)")).sort(),
    ["懂车帝", "汽车之家"].sort()
  );
  assert.deepEqual(Array.from(hooks.atomicSources("合作数据源")), ["合作数据源"]);
  assert.deepEqual(
    Array.from(hooks.atomicSources("合作数据源+懂车帝")).sort(),
    ["合作数据源", "懂车帝"].sort()
  );

  hooks.initializeRows([
    row("仅懂车帝", 2021, "旧款"),
    row("汽车之家+懂车帝+易车(车系级)", 2022, "双源款"),
    row("仅懂车帝", 2023, "懂车帝款"),
    row("合作数据源+易车", 2024, "未知来源合并款"),
    row("仅懂车帝", 2024, "未知来源合并款"),
    { "数据来源": "仅易车", "品牌": "测试品牌", "车系": "测试车系", "车型名称": "易车无年款款" },
    row("仅懂车帝", 2025, "分行双源款"),
    row("仅汽车之家+易车", 2025, "分行双源款")
  ]);
  hooks.renderResultsOnly();

  assert.equal(hooks.state.rows.length, 5);
  assert.equal(
    JSON.stringify(hooks.state.rows.map((item) => item["车型名称"]).sort()),
    JSON.stringify(["分行双源款", "双源款", "懂车帝款", "易车无年款款", "未知来源合并款"].sort())
  );

  const verified = hooks.state.rows.find((item) => item["车型名称"] === "双源款");
  assert.equal(verified["交叉核验"], "双源核验");
  assert.deepEqual(
    verified["核验来源"].split(" + ").sort(),
    ["懂车帝", "汽车之家", "易车"].sort()
  );

  const unknown = hooks.state.rows.find((item) => item["车型名称"] === "未知来源合并款");
  assert.equal(unknown["交叉核验"], "双源核验");
  assert.deepEqual(
    unknown["核验来源"].split(" + ").sort(),
    ["合作数据源", "懂车帝", "易车"].sort()
  );

  const splitSource = hooks.state.rows.find((item) => item["车型名称"] === "分行双源款");
  assert.equal(splitSource["交叉核验"], "双源核验");
  assert.deepEqual(
    splitSource["核验来源"].split(" + ").sort(),
    ["懂车帝", "汽车之家", "易车"].sort()
  );

  assert.equal(elements.get("visibleCount").textContent, "5");
  assert.equal(elements.get("totalCount").textContent, "5");
  assert.equal(elements.get("verifiedCount").textContent, "3");
  assert.equal(elements.get("dongchediCount").textContent, "4");
  assert.equal(elements.get("autohomeCount").textContent, "2");
  assert.equal(elements.get("yicheCount").textContent, "4");

  hooks.state.search = "不存在的车型";
  hooks.renderResultsOnly();
  assert.equal(elements.get("visibleCount").textContent, "0");
  assert.equal(elements.get("totalCount").textContent, "5");
  assert.equal(elements.get("verifiedCount").textContent, "3");
  assert.equal(elements.get("dongchediCount").textContent, "4");
  assert.equal(elements.get("autohomeCount").textContent, "2");
  assert.equal(elements.get("yicheCount").textContent, "4");
});

test("Pages page jump rejects invalid values and clamps valid integers", () => {
  const { elements, hooks } = loadAppForTest();
  const rows = Array.from({ length: 250 }, (_, index) => row("仅懂车帝", 2026, "车型" + index));
  const pageJump = elements.get("pageJump");

  hooks.initializeRows(rows);
  hooks.renderResultsOnly();
  assert.equal(elements.get("pageInfo").textContent, "第 1 / 3 页");

  pageJump.value = "2.5";
  pageJump.validity = { valid: false };
  elements.get("goPage").dispatch("click");
  assert.equal(hooks.state.page, 1);
  assert.equal(pageJump.value, "1");

  pageJump.value = "";
  elements.get("goPage").dispatch("click");
  assert.equal(hooks.state.page, 1);
  assert.equal(pageJump.value, "1");

  pageJump.value = "3";
  pageJump.validity = { valid: true };
  elements.get("goPage").dispatch("click");
  assert.equal(hooks.state.page, 3);

  pageJump.value = "99";
  pageJump.validity = { valid: false };
  elements.get("goPage").dispatch("click");
  assert.equal(hooks.state.page, 3);

  pageJump.value = "2";
  pageJump.validity = { valid: true };
  pageJump.dispatch("keydown", { key: "Enter" });
  assert.equal(hooks.state.page, 2);
});

const liveDataPath = process.env.CARS_LIVE_DATA;
test("live Pages data has the expected deduplicated 2022+ source coverage", { skip: !liveDataPath }, () => {
  const { elements, hooks } = loadAppForTest();
  const rows = JSON.parse(fs.readFileSync(liveDataPath, "utf8"));

  hooks.initializeRows(rows);
  hooks.renderResultsOnly();

  assert.equal(elements.get("visibleCount").textContent, "2992");
  assert.equal(elements.get("totalCount").textContent, "2992");
  assert.equal(elements.get("verifiedCount").textContent, "137");
  assert.equal(elements.get("dongchediCount").textContent, "2992");
  assert.equal(elements.get("autohomeCount").textContent, "137");
  assert.equal(Math.min(...hooks.state.rows.map((item) => Number(item["年款"]))), 2022);
});

test("Pages does not expose dedicated brand or series filters", () => {
  const html = fs.readFileSync(path.join(__dirname, "..", "docs", "index.html"), "utf8");
  const css = fs.readFileSync(path.join(__dirname, "..", "docs", "styles.css"), "utf8");
  assert.doesNotMatch(html, /id="(?:brandFilter|centerBrandFilter)"/);
  assert.doesNotMatch(html, /id="(?:seriesFilter|centerSeriesFilter)"/);
  assert.ok(html.indexOf('class="summary-strip"') < html.indexOf('id="filterCenter"'));
  assert.match(html, /核心条件/);
  assert.match(html, /匹配车系/);
  assert.match(css, /\.summary-strip\s*\{[^}]*grid-column:\s*1\s*\/\s*-1/s);
  assert.match(css, /\.center-filters\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)/s);
});


test("Pages custom sort supports multiple levels, keyword order, natural numeric order and snapshots", () => {
  const { hooks } = loadAppForTest();
  hooks.initializeRows([
    Object.assign(row("仅懂车帝", 2026, "A 10"), { "能源类型": "增程", "官方指导价": "30万" }),
    Object.assign(row("仅懂车帝", 2026, "A 2"), { "能源类型": "纯电", "官方指导价": "20万" }),
    Object.assign(row("仅懂车帝", 2026, "A 1"), { "能源类型": "插混", "官方指导价": "25万" }),
    Object.assign(row("仅懂车帝", 2026, "B 1"), { "能源类型": "燃油", "官方指导价": "10万" })
  ]);
  hooks.state.sortLevels = [
    { field: "能源类型", dir: "asc", customOrder: "插混, 纯电, 增程" },
    { field: "车型名称", dir: "asc", customOrder: "" }
  ];
  assert.deepEqual(JSON.parse(JSON.stringify(hooks.getFilteredRows().map((item) => item["车型名称"]))), ["A 1", "A 2", "A 10", "B 1"]);

  hooks.state.sortLevels = [{ field: "官方指导价", dir: "asc", customOrder: "" }];
  assert.deepEqual(JSON.parse(JSON.stringify(hooks.getFilteredRows().map((item) => item["官方指导价"]))), ["10万", "20万", "25万", "30万"]);

  hooks.state.sortLevels = [{ field: "能源类型", dir: "asc", customOrder: "纯电" }];
  const before = hooks.getFilteredRows().map((item) => item["车型名称"]);
  const snap = hooks.snapshotFilters();
  hooks.state.sortLevels = [];
  hooks.applySnapshot(snap);
  assert.deepEqual(JSON.parse(JSON.stringify(hooks.getFilteredRows().map((item) => item["车型名称"]))), JSON.parse(JSON.stringify(before)));
});

test("Pages filter center groups models by series and uses price extrema as representatives", () => {
  const { elements, hooks } = loadAppForTest();
  hooks.initializeRows([
    Object.assign(row("仅懂车帝", 2026, "S1 高配"), { "品牌": "A", "车系": "S1", "官方指导价": "30万" }),
    Object.assign(row("仅懂车帝", 2026, "S1 低配"), { "品牌": "A", "车系": "S1", "官方指导价": "20万" }),
    Object.assign(row("仅懂车帝", 2026, "S2 高配"), { "品牌": "A", "车系": "S2", "官方指导价": "15万" }),
    Object.assign(row("仅懂车帝", 2026, "S2 低配"), { "品牌": "A", "车系": "S2", "官方指导价": "10万" }),
    Object.assign(row("仅懂车帝", 2026, "无价款"), { "品牌": "A", "车系": "S3", "官方指导价": "0万" }),
    Object.assign(row("仅懂车帝", 2025, "独立车型"), { "品牌": "B", "车系": "", "官方指导价": "-" })
  ]);

  hooks.state.sortLevels = [{ field: "官方指导价", dir: "asc", customOrder: "" }];
  let groups = hooks.groupRowsBySeries(hooks.getFilteredRows());
  assert.deepEqual(Array.from(groups, (group) => group.name), ["S2", "S1", "独立车型", "S3"]);
  assert.equal(groups[0].representative["车型名称"], "S2 低配");
  assert.equal(groups[1].representative["车型名称"], "S1 低配");
  assert.equal(groups[2].price, null);
  assert.match(groups[2].key, /^model\|B\|独立车型\|2025$/);

  hooks.renderResultsOnly();
  assert.equal(elements.get("centerVisibleCount").textContent, "4");
  assert.equal(elements.get("cardList").children.length, 4);
  assert.equal(elements.get("tableBody").children.length, 6);
  let firstCard = elements.get("cardList").children[0];
  let toggle = firstCard.children[0];
  assert.equal(toggle.children[0].textContent, "S2");
  assert.equal(toggle.children[1].textContent, "2 款车型符合条件");
  assert.equal(toggle.getAttribute("aria-expanded"), "false");

  elements.get("cardList").dispatch("click", { target: toggle });
  firstCard = elements.get("cardList").children[0];
  toggle = firstCard.children[0];
  assert.equal(toggle.getAttribute("aria-expanded"), "true");
  assert.equal(firstCard.children[2].children.length, 2);
  assert.deepEqual(Array.from(firstCard.children[2].children, (item) => item.children[0].textContent), ["S2 低配", "S2 高配"]);

  hooks.state.search = "S1";
  hooks.renderResultsOnly();
  assert.equal(hooks.state.expandedSeries.size, 0);

  hooks.state.search = "";
  hooks.state.sortLevels = [{ field: "官方指导价", dir: "desc", customOrder: "" }];
  groups = hooks.groupRowsBySeries(hooks.getFilteredRows());
  assert.deepEqual(Array.from(groups, (group) => group.name), ["S1", "S2", "独立车型", "S3"]);
  assert.equal(groups[0].representative["车型名称"], "S1 高配");
  assert.equal(groups[1].representative["车型名称"], "S2 高配");

  hooks.renderResultsOnly();
  hooks.state.cardLimit = 1;
  hooks.renderResultsOnly();
  assert.equal(elements.get("cardList").children.length, 1);
  assert.equal(elements.get("loadMoreCards").hidden, false);
});

test("Pages defaults to filter center and shares filters with table result set", () => {
  const { elements, hooks } = loadAppForTest();
  hooks.state.config.conditions = [{ id: "remote", label: "远程启动", type: "feature", fields: ["远程启动"], keywords: ["支持"] }];
  hooks.initializeRows([
    Object.assign(row("汽车之家+懂车帝", 2026, "甲"), { "品牌": "A", "车系": "S1", "远程启动": "支持" }),
    Object.assign(row("仅懂车帝", 2026, "乙"), { "品牌": "A", "车系": "S2", "远程启动": "-" }),
    Object.assign(row("仅懂车帝", 2026, "丙"), { "品牌": "B", "车系": "S3", "远程启动": "支持" })
  ]);
  hooks.renderResultsOnly();
  assert.equal(hooks.state.mode, "center");
  hooks.state.brand = "A";
  hooks.state.featureFilters.remote = true;
  hooks.renderResultsOnly();
  assert.deepEqual(JSON.parse(JSON.stringify(hooks.getFilteredRows().map((item) => item["车型名称"]))), ["甲"]);
  assert.equal(elements.get("centerVisibleCount").textContent, "1");

  elements.get("centerMode").dispatch("click");
  assert.equal(elements.get("filterCenter").hidden, false);
  assert.equal(elements.get("tableRegion").hidden, true);
  elements.get("tableMode").dispatch("click");
  assert.equal(elements.get("filterCenter").hidden, true);
  assert.equal(elements.get("tableRegion").hidden, false);

  const html = fs.readFileSync(path.join(__dirname, "..", "docs", "index.html"), "utf8");
  const css = fs.readFileSync(path.join(__dirname, "..", "docs", "styles.css"), "utf8");
  assert.doesNotMatch(html, /table-region advanced-hidden/);
  assert.doesNotMatch(css, /\.advanced-hidden\s*,\s*\.center-hidden/);
});


test("Pages enables the eight core filters by default and after reset", () => {
  const { elements, hooks } = loadAppForTest();
  hooks.state.config.conditions = [
    { id: "zero_to_hundred", label: "百公里加速", type: "range", field: "百公里加速(s)", max: 7 },
    { id: "ev_range", label: "纯电续航", type: "range", field: "纯电续航(km)", min: 150 },
    { id: "city_navigation", label: "NOA城市领航", type: "feature", fields: ["NOA城市领航"], keywords: ["支持"] },
    { id: "remote_start", label: "远程启动", type: "feature", fields: ["远程启动"], keywords: ["支持"] },
    { id: "remote_control", label: "手机远程控制", type: "feature", fields: ["远程控制"], keywords: ["支持"] },
    { id: "bluetooth_key", label: "蓝牙/数字钥匙", type: "feature", fields: ["蓝牙/数字钥匙"], keywords: ["支持"] },
    { id: "seat_memory", label: "座椅记忆", type: "feature", fields: ["座椅记忆"], keywords: ["支持"] },
    { id: "mirror_memory", label: "外后视镜记忆", type: "feature", fields: ["外后视镜记忆"], keywords: ["支持"] }
  ];
  const passing = Object.assign(row("仅懂车帝", 2026, "默认通过"), {
    "百公里加速(s)": "6.9",
    "纯电续航(km)": "180",
    "NOA城市领航": "支持",
    "远程启动": "支持",
    "远程控制": "支持",
    "蓝牙/数字钥匙": "支持",
    "座椅记忆": "支持",
    "外后视镜记忆": "支持"
  });
  const failing = Object.assign(row("仅懂车帝", 2026, "默认不过"), passing, { "车型名称": "默认不过", "百公里加速(s)": "8.0" });

  hooks.initializeRows([passing, failing]);
  hooks.renderEverything();

  assert.deepEqual(Object.keys(hooks.state.featureFilters).sort(), [
    "bluetooth_key", "city_navigation", "mirror_memory", "remote_control", "remote_start", "seat_memory"
  ].sort());
  assert.deepEqual(JSON.parse(JSON.stringify(hooks.state.rangeFilters)), { zero_to_hundred: { min: "", max: 7 }, ev_range: { min: 150, max: "" } });
  assert.deepEqual(JSON.parse(JSON.stringify(hooks.getFilteredRows().map((item) => item["车型名称"]))), ["默认通过"]);
  assert.equal(elements.get("selectedTags").children.map((tag) => tag.textContent).join("|"), "百公里加速 ≤7|纯电续航 ≥150|NOA城市领航|远程启动|手机远程控制|蓝牙/数字钥匙|座椅记忆|外后视镜记忆");
  assert.equal(elements.get("conditionList").children[0].children[0].children[0].children[0].textContent, "百公里加速 ≤7");
  assert.equal(elements.get("centerConditionList").children[0].children[1].textContent, "百公里加速 ≤7");
  assert.equal(elements.get("centerConditionList").children.filter((label) => label.children[0].checked).length, 8);

  hooks.state.rangeFilters = {};
  hooks.state.featureFilters = {};
  elements.get("resetFilters").dispatch("click");
  assert.deepEqual(JSON.parse(JSON.stringify(hooks.state.rangeFilters)), { zero_to_hundred: { min: "", max: 7 }, ev_range: { min: 150, max: "" } });
  assert.equal(Object.keys(hooks.state.featureFilters).length, 6);
  assert.equal(elements.get("conditionList").children[0].children.filter((item) => item.children[0].children[0] && item.children[0].children[0].checked).length, 6);
  assert.equal(elements.get("centerConditionList").children.filter((label) => label.children[0].checked).length, 8);
});

test("Pages default visible columns include listing time and core feature columns", () => {
  const config = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "config", "filter_conditions.json"), "utf8"));
  ["官方指导价", "上市时间", "NOA城市领航", "远程启动", "远程控制", "蓝牙/数字钥匙", "座椅记忆", "外后视镜记忆"].forEach((column) => {
    assert.ok(config.defaultVisibleColumns.includes(column), column);
  });
  assert.ok(config.defaultVisibleColumns.indexOf("官方指导价") < config.defaultVisibleColumns.indexOf("上市时间"));
  assert.ok(config.defaultVisibleColumns.indexOf("上市时间") < config.defaultVisibleColumns.indexOf("NOA城市领航"));
});

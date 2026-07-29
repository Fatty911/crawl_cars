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
      defaultRangeFilters: DEFAULT_RANGE_FILTERS,
      normalizeRowColumns: normalizeRowColumns,
      isEquipmentColumn: isEquipmentColumn,
      shouldHideColumn: shouldHideColumn,
      getFilterTaxonomy: getFilterTaxonomy,
      selectedCountForCategory: selectedCountForCategory,
      activateMobileCategory: activateMobileCategory,
      restoreDefaultFilters: restoreDefaultFilters,
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


test("Pages enables the eleven core filters by default and after reset", () => {
  const { elements, hooks } = loadAppForTest();
  hooks.state.config.conditions = [
    { id: "zero_to_hundred", label: "百公里加速", type: "range", field: "百公里加速(s)" },
    { id: "ev_range", label: "纯电续航", type: "range", field: "纯电续航(km)" },
    { id: "city_navigation", label: "NOA城市领航", type: "feature", fields: ["NOA城市领航"], keywords: ["支持"] },
    { id: "remote_start", label: "远程启动", type: "feature", fields: ["远程启动"], keywords: ["支持"] },
    { id: "remote_control", label: "手机远程控制", type: "feature", fields: ["远程控制"], keywords: ["支持"] },
    { id: "bluetooth_key", label: "蓝牙/数字钥匙", type: "feature", fields: ["蓝牙/数字钥匙"], keywords: ["支持"] },
    { id: "seat_memory", label: "座椅记忆", type: "feature", fields: ["座椅记忆"], keywords: ["支持"] },
    { id: "mirror_memory", label: "外后视镜记忆", type: "feature", fields: ["外后视镜记忆"], keywords: ["支持"] },
    { id: "app_remote_control", label: "手机APP远程控制", type: "feature", fields: ["手机App远程控制 - 远程控制"], keywords: ["支持"] },
    { id: "rain_sensor_wiper", label: "雨量感应式雨刷", type: "feature", fields: ["雨量感应式雨刷"], keywords: ["支持"] },
    { id: "auto_headlight", label: "自动头灯", type: "feature", fields: ["自动大灯"], keywords: ["支持"] }
  ];
  hooks.state.config.centerConditionGroups = [
    { id: "performance", label: "性能/续航", conditionIds: ["zero_to_hundred", "ev_range"] },
    { id: "smart", label: "核心配置", conditionIds: ["city_navigation", "remote_start", "remote_control", "bluetooth_key", "seat_memory", "mirror_memory"] },
    { id: "comfort", label: "舒适/便利", conditionIds: ["app_remote_control", "rain_sensor_wiper", "auto_headlight"] }
  ];
  const passing = Object.assign(row("仅懂车帝", 2026, "默认通过"), {
    "百公里加速(s)": "6.9",
    "纯电续航(km)": "180",
    "NOA城市领航": "支持",
    "远程启动": "支持",
    "远程控制": "支持",
    "蓝牙/数字钥匙": "支持",
    "座椅记忆": "支持",
    "外后视镜记忆": "支持",
    "手机App远程控制 - 远程控制": "支持",
    "雨量感应式雨刷": "支持",
    "自动大灯": "支持"
  });
  const failing = Object.assign(row("仅懂车帝", 2026, "默认不过"), passing, { "车型名称": "默认不过", "百公里加速(s)": "8.0" });

  hooks.initializeRows([passing, failing]);
  hooks.renderEverything();

  assert.deepEqual(Object.keys(hooks.state.featureFilters).sort(), [
    "app_remote_control", "auto_headlight", "bluetooth_key", "city_navigation", "mirror_memory", "rain_sensor_wiper", "remote_control", "remote_start", "seat_memory"
  ].sort());
  assert.deepEqual(JSON.parse(JSON.stringify(hooks.state.rangeFilters)), { zero_to_hundred: { min: "", max: "" }, ev_range: { min: "", max: "" } });
  // Without hardcoded range defaults, both rows pass initially
  assert.deepEqual(JSON.parse(JSON.stringify(hooks.getFilteredRows().map((item) => item["车型名称"]))), ["默认通过", "默认不过"]);
  // Set range values manually to verify filtering still works
  hooks.state.rangeFilters.zero_to_hundred = { min: "", max: "7" };
  assert.deepEqual(JSON.parse(JSON.stringify(hooks.getFilteredRows().map((item) => item["车型名称"]))), ["默认通过"]);
  hooks.state.rangeFilters.zero_to_hundred = { min: "", max: "" };
  assert.equal(elements.get("selectedTags").children.map((tag) => tag.textContent).join("|"), "百公里加速|纯电续航|NOA城市领航|远程启动|手机远程控制|蓝牙/数字钥匙|座椅记忆|外后视镜记忆|手机APP远程控制|雨量感应式雨刷|自动头灯");
  // All conditions are in centerConditionGroups, so sidebar conditionList fragment has no items
  assert.equal(elements.get("conditionList").children[0].children.length, 0);
  // centerConditionList renders 3 group divs; collect condition items across groups
  const centerItems = [];
  elements.get("centerConditionList").children.forEach((group) => {
    group.children.forEach((child) => { if (child.className === "center-condition-item") { centerItems.push(child); } });
  });
  assert.equal(centerItems.length, 11);
  assert.equal(centerItems.filter((item) => item.children[0] && item.children[0].children[0] && item.children[0].children[0].checked).length, 11);

  hooks.state.rangeFilters = {};
  hooks.state.featureFilters = {};
  elements.get("resetFilters").dispatch("click");
  assert.deepEqual(JSON.parse(JSON.stringify(hooks.state.rangeFilters)), { zero_to_hundred: { min: "", max: "" }, ev_range: { min: "", max: "" } });
  assert.equal(Object.keys(hooks.state.featureFilters).length, 9);
  assert.equal(elements.get("conditionList").children[0].children.length, 0);
  const centerItemsAfterReset = [];
  elements.get("centerConditionList").children.forEach((group) => {
    group.children.forEach((child) => { if (child.className === "center-condition-item") { centerItemsAfterReset.push(child); } });
  });
  assert.equal(centerItemsAfterReset.filter((item) => item.children[0] && item.children[0].children[0] && item.children[0].children[0].checked).length, 11);
});

test("Pages default visible columns include listing time and core feature columns", () => {
  const config = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "config", "filter_conditions.json"), "utf8"));
  ["官方指导价", "上市时间", "NOA城市领航", "远程启动", "远程控制", "蓝牙/数字钥匙", "座椅记忆", "外后视镜记忆"].forEach((column) => {
    assert.ok(config.defaultVisibleColumns.includes(column), column);
  });
  assert.ok(config.defaultVisibleColumns.indexOf("官方指导价") < config.defaultVisibleColumns.indexOf("上市时间"));
  assert.ok(config.defaultVisibleColumns.indexOf("上市时间") < config.defaultVisibleColumns.indexOf("NOA城市领航"));
});


test("Pages range defaults keep acceleration at most 7, speed at least 180, and EV range at least 150 without a cap", () => {
  const config = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "docs", "filter_conditions.json"), "utf8"));
  const ranges = Object.fromEntries(config.conditions.filter((condition) => condition.type === "range").map((condition) => [
    condition.id,
    { min: condition.defaultMin, max: condition.defaultMax }
  ]));
  assert.deepEqual(ranges.zero_to_hundred, { min: "0", max: "7" });
  assert.deepEqual(ranges.top_speed, { min: "180", max: "" });
  assert.deepEqual(ranges.ev_range, { min: "150", max: "" });

  const { hooks } = loadAppForTest();
  assert.deepEqual(JSON.parse(JSON.stringify(hooks.defaultRangeFilters)), {
    zero_to_hundred: { min: "0", max: "7" },
    top_speed: { min: "180", max: "" },
    ev_range: { min: "150", max: "" }
  });
});

test("Pages never hides configured default-visible or legitimate equipment-related attribute columns", () => {
  const { hooks } = loadAppForTest();
  const config = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "docs", "filter_conditions.json"), "utf8"));
  hooks.state.config = config;
  assert.ok(config.defaultVisibleColumns.includes("前轮胎规格"));
  assert.ok(config.defaultVisibleColumns.includes("后轮胎规格"));
  assert.equal(config.defaultVisibleColumns.includes("前轮胎规格尺寸"), false);
  assert.equal(config.defaultVisibleColumns.includes("后轮胎规格尺寸"), false);
  config.defaultVisibleColumns.forEach((column) => {
    assert.equal(hooks.shouldHideColumn(column, []), false, column);
  });
  ["前轮胎规格", "后轮胎规格", "安全轮胎", "扬声器数量", "车顶行李架"].forEach((column) => {
    assert.equal(hooks.shouldHideColumn(column, []), false, column);
  });
});

test("Pages identifies legacy option-package columns only from structured package data", () => {
  const { hooks } = loadAppForTest();
  hooks.state.config = { hiddenByDefault: [], dropIfUniformPositive: [] };
  const rows = [{
    "冬季包_1": "方向盘加热",
    "选装包列表": JSON.stringify({ "冬季包": { "描述": "方向盘加热", "状态": "选装" } }),
    "冬季包": "方向盘加热",
    "安全轮胎_1": "支持",
    "camera_count_v4_1": "前视",
    "camera_count_v4_2": "后视",
    "camera_count_v4_3": "环视",
    "扬声器数量": "12"
  }];
  assert.equal(hooks.shouldHideColumn("冬季包_1", rows), true);
  assert.equal(hooks.shouldHideColumn("冬季包", rows), true);
  assert.equal(hooks.shouldHideColumn("安全轮胎_1", rows), false);
  assert.equal(hooks.shouldHideColumn("camera_count_v4_1", rows), false);
  assert.equal(hooks.shouldHideColumn("扬声器数量", rows), false);
});

test("Pages canonicalizes value columns and aliases without dropping conflicts", () => {
  const { hooks } = loadAppForTest();
  hooks.state.config = {
    columnAliases: {
      "前轮胎规格": ["前轮胎规格尺寸"],
      "轴距(mm)": ["轴距[mm]"]
    }
  };
  const rows = hooks.normalizeRowColumns([{
    "音响品牌": "Bose",
    "音响品牌 - Harman Kardon": "支持",
    "前轮胎规格": "235/50 R19",
    "前轮胎规格尺寸": "245/45 R20",
    "轴距(mm)": "2800",
    " 轴距[mm] ": "2810"
  }]);
  assert.equal(rows[0]["音响品牌"], "Bose|Harman Kardon");
  assert.equal(rows[0]["前轮胎规格"], "235/50 R19|245/45 R20");
  assert.equal(rows[0]["轴距(mm)"], "2800|2810");
  assert.equal("音响品牌 - Harman Kardon" in rows[0], false);
  assert.equal("前轮胎规格尺寸" in rows[0], false);
  assert.equal(" 轴距[mm] " in rows[0], false);
});


test("Pages config uses existing canonical dimension names and never aliases 0-50 acceleration to 0-100", () => {
  for (const configPath of ["config/filter_conditions.json", "docs/filter_conditions.json"]) {
    const config = JSON.parse(fs.readFileSync(path.join(__dirname, "..", configPath), "utf8"));
    ["长(mm)", "宽(mm)", "高(mm)"].forEach((column) => assert.ok(config.defaultVisibleColumns.includes(column), `${configPath}: ${column}`));
    ["长度(mm)", "宽度(mm)", "高度(mm)"].forEach((column) => assert.equal(config.defaultVisibleColumns.includes(column), false, `${configPath}: ${column}`));
    assert.equal(config.columnAliases["百公里加速(s)"].includes("官方0—50Km/h加速时间(s)"), false);
    assert.ok(config.columnAliases["最高车速(km/h)"].includes("最高车速[km/h]"));
    assert.ok(config.columnAliases["轴距(mm)"].includes("轴距[mm]"));
    assert.ok(config.columnAliases["电池温控(加热)"].includes("battery_temperature_management_system_heating_v3"));
    assert.ok(config.columnAliases["电池组质保"].includes("battery_warranty_v3"));
  }
});


test("Pages mobile layout keeps text readable, controls touchable, and the wide table scrollable", () => {
  const html = fs.readFileSync(path.join(__dirname, "..", "docs", "index.html"), "utf8");
  const css = fs.readFileSync(path.join(__dirname, "..", "docs", "styles.css"), "utf8");
  const viewport = html.match(/<meta\s+name="viewport"\s+content="([^"]+)"/i);
  assert.ok(viewport);
  assert.equal(viewport[1], "width=device-width, initial-scale=1");
  assert.match(css, /body\s*\{[^}]*-webkit-text-size-adjust:\s*100%/s);
  assert.doesNotMatch(css, /\b(?:zoom|transform)\s*:/);

  const mobileStart = css.lastIndexOf("@media (max-width: 640px)");
  assert.notEqual(mobileStart, -1);
  const mobile = css.slice(mobileStart);
  function declarations(source, selector) {
    const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const match = source.match(new RegExp(escaped + "\\s*\\{([^}]*)\\}", "s"));
    assert.ok(match, `missing declarations for ${selector}`);
    return match[1];
  }
  function pixels(block, property) {
    const match = block.match(new RegExp(property + "\\s*:\\s*([0-9.]+)px"));
    assert.ok(match, `missing ${property}`);
    return Number(match[1]);
  }

  assert.ok(pixels(declarations(mobile, "body"), "font-size") >= 16);
  assert.ok(pixels(declarations(mobile, ".brand-block h1"), "font-size") >= 24);
  assert.ok(pixels(declarations(mobile, ".brand-block p"), "font-size") >= 14);
  assert.ok(pixels(declarations(mobile, ".center-hero p"), "font-size") >= 16);
  assert.ok(pixels(declarations(mobile, ".summary-label"), "font-size") >= 14);
  assert.ok(pixels(declarations(mobile, ".card-meta"), "font-size") >= 15);
  assert.ok(pixels(declarations(mobile, ".selected-tags span"), "font-size") >= 15);
  assert.ok(pixels(declarations(mobile, "th,\n  td"), "font-size") >= 14);

  const buttons = declarations(mobile, "\n  button");
  assert.ok(pixels(buttons, "font-size") >= 16);
  assert.ok(pixels(buttons, "min-height") >= 44);
  const controls = declarations(mobile, ".segment,\n  .text-button,\n  .icon-button,\n  .pager button,\n  .field-filter button,\n  .range-controls button,\n  .link-button,\n  .sort-level button,\n  input:not([type=\"checkbox\"]),\n  select,\n  textarea");
  assert.ok(pixels(controls, "font-size") >= 16);
  assert.ok(pixels(controls, "min-height") >= 44);
  const tableWrap = declarations(mobile, ".table-wrap");
  assert.match(tableWrap, /overflow-x:\s*auto/);
  assert.match(tableWrap, /-webkit-overflow-scrolling:\s*touch/);
  assert.match(declarations(mobile, ".toolbar"), /flex-direction:\s*column/);
  assert.match(declarations(mobile, ".center-condition-item"), /max-width:\s*100%/);
  assert.match(declarations(mobile, ".center-range-label"), /flex-wrap:\s*wrap/);

  assert.equal(pixels(declarations(css.slice(0, mobileStart), ".brand-block h1"), "font-size"), 22);
  assert.equal(pixels(declarations(css.slice(0, mobileStart), "th,\ntd"), "font-size"), 13);
});


test("Pages canonicalizes only evidenced legacy heat-pump duplicates and the quick-charge schema key", () => {
  const { hooks } = loadAppForTest();
  for (const configPath of ["config/filter_conditions.json", "docs/filter_conditions.json"]) {
    const config = JSON.parse(fs.readFileSync(path.join(__dirname, "..", configPath), "utf8"));
    assert.deepEqual(config.columnAliases["热泵空调"], [
      "热泵管理系统",
      "CO2热泵空调包",
      "CO2热泵空调系统",
      "CO2热泵空调系统_1",
      "CO2热泵空调系统_2",
      "CO2热泵空调包_1",
      "CO2热泵空调包_2"
    ]);
    assert.ok(config.columnAliases["快充接口"].includes("quick_charge_interface_v3"));
  }

  hooks.state.config = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "docs", "filter_conditions.json"), "utf8"));
  const rows = hooks.normalizeRowColumns([{
    "CO2热泵空调系统_1": "是",
    "CO2热泵空调系统_2": "是",
    "CO2热泵空调包_1": "支持",
    "CO2热泵空调包_2": "支持",
    "quick_charge_interface_v3": "●",
    "安全轮胎_1": "支持"
  }]);
  assert.equal(rows[0]["热泵空调"], "是|支持");
  assert.equal(rows[0]["快充接口"], "●");
  ["CO2热泵空调系统_1", "CO2热泵空调系统_2", "CO2热泵空调包_1", "CO2热泵空调包_2", "quick_charge_interface_v3"].forEach((legacy) => {
    assert.equal(legacy in rows[0], false);
  });
  assert.equal(rows[0]["安全轮胎_1"], "支持");
});


test("Pages mobile filter center exposes a config-driven major/minor taxonomy", () => {
  const configPath = path.join(__dirname, "..", "config", "filter_conditions.json");
  const docsPath = path.join(__dirname, "..", "docs", "filter_conditions.json");
  const config = JSON.parse(fs.readFileSync(configPath, "utf8"));
  const docsConfig = JSON.parse(fs.readFileSync(docsPath, "utf8"));
  assert.deepEqual(config, docsConfig, "deploy and Pages filter schemas must stay identical");
  assert.ok(Array.isArray(config.filterTaxonomy));
  assert.ok(Array.isArray(config.desktopConditionGroups));
  assert.deepEqual(config.filterTaxonomy.map((category) => category.label), [
    "动力参数", "辅助/操控", "外部/防盗", "座椅", "灯光", "玻璃/后视镜", "智能硬件"
  ]);
  const assignments = [];
  config.filterTaxonomy.forEach((category) => {
    assert.ok(category.id);
    assert.ok(category.label);
    assert.ok(Array.isArray(category.sections) && category.sections.length > 0);
    category.sections.forEach((section) => {
      assert.ok(section.id);
      assert.ok(section.label);
      assert.ok(section.desktopGroupId);
      assert.ok(Array.isArray(section.conditionIds) && section.conditionIds.length > 0);
      section.conditionIds.forEach((id) => assignments.push(id));
    });
  });
  const conditionIds = config.conditions.map((condition) => condition.id).sort();
  assert.deepEqual(assignments.slice().sort(), conditionIds);
  assert.equal(new Set(assignments).size, assignments.length, "every condition belongs to exactly one minor section");
  const pagesOnly = ["app_remote_control", "rain_sensor_wiper", "auto_headlight"];
  assert.deepEqual(config.conditions.filter((condition) => pagesOnly.includes(condition.id)).map((condition) => condition.type), [
    "pagesFeature", "pagesFeature", "pagesFeature"
  ], "Pages-only controls must not silently expand the merge-data filter contract");
});

test("Pages mobile filter center has semantic rail, minor pane, live result actions, and safe-area layout", () => {
  const html = fs.readFileSync(path.join(__dirname, "..", "docs", "index.html"), "utf8");
  const css = fs.readFileSync(path.join(__dirname, "..", "docs", "styles.css"), "utf8");
  const app = fs.readFileSync(path.join(__dirname, "..", "docs", "app.js"), "utf8");
  assert.match(html, /id="mobileRestoreDefaults"[^>]*>恢复默认</);
  assert.match(html, /id="mobileViewResults"[^>]*aria-controls="cardList"/);
  assert.match(html, /id="mobileResultCount"/);
  assert.match(app, /createElement\("nav"\)/);
  assert.match(app, /major-category-rail/);
  assert.match(app, /createElement\("section"\)/);
  assert.match(app, /minor-content-pane/);
  assert.match(app, /aria-selected/);
  assert.match(app, /aria-controls/);
  assert.match(app, /event\.key === "Enter" \|\| event\.key === " "/);
  assert.match(app, /scrollIntoView/);
  assert.match(css, /@media \(max-width: 720px\)/);
  assert.match(css, /\.mobile-filter-layout\s*\{[^}]*grid-template-columns:\s*(?:9[0-9]|10[0-4])px\s+minmax\(0,\s*1fr\)/s);
  assert.match(css, /\.mobile-filter-actions\s*\{[^}]*position:\s*fixed[^}]*padding-bottom:\s*calc\([^)]*env\(safe-area-inset-bottom\)/s);
  assert.match(css, /\.center-region\s*\{[^}]*padding-bottom:\s*calc\(/s);
  assert.match(css, /\.major-category-button\s*\{[^}]*min-height:\s*(?:4[4-9]|[5-9][0-9])px/s);
  assert.match(css, /\.minor-content-pane\s*\{[^}]*min-width:\s*0/s);
  assert.match(css, /\.mobile-option-grid[^}]*:has\(input:checked\)\s*\{[^}]*border-color:\s*var\(--accent\)[^}]*background:\s*var\(--accent-soft\)/s);
});

test("Pages mobile category activation and badges use the same filter state", () => {
  const { hooks } = loadAppForTest();
  const config = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "docs", "filter_conditions.json"), "utf8"));
  hooks.state.config = config;
  assert.equal(typeof hooks.selectedCountForCategory, "function");
  assert.equal(typeof hooks.activateMobileCategory, "function");
  hooks.state.rangeFilters = {
    zero_to_hundred: { min: "0", max: "7" },
    top_speed: { min: "180", max: "" },
    ev_range: { min: "150", max: "" }
  };
  hooks.state.featureFilters = { city_navigation: true, auto_headlight: true };
  const taxonomy = hooks.getFilterTaxonomy();
  const power = taxonomy.find((category) => category.id === "power");
  const assist = taxonomy.find((category) => category.id === "assist");
  const lighting = taxonomy.find((category) => category.id === "lighting");
  assert.equal(hooks.selectedCountForCategory(power), 3);
  assert.equal(hooks.selectedCountForCategory(assist), 1);
  assert.equal(hooks.selectedCountForCategory(lighting), 1);
  hooks.activateMobileCategory("lighting", false);
  assert.equal(hooks.state.mobileCategoryId, "lighting");
});

test("Pages restore-default semantics are schema-driven and preserve the three required range defaults", () => {
  const { elements, hooks } = loadAppForTest();
  const config = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "docs", "filter_conditions.json"), "utf8"));
  hooks.state.config = config;
  hooks.state.rangeFilters = { ev_range: { min: "999", max: "1000" } };
  hooks.state.featureFilters = {};
  hooks.state.search = "temporary";
  assert.equal(typeof hooks.restoreDefaultFilters, "function");
  hooks.restoreDefaultFilters();
  assert.deepEqual(JSON.parse(JSON.stringify(hooks.state.rangeFilters)), {
    zero_to_hundred: { min: "0", max: "7" },
    ev_range: { min: "150", max: "" },
    top_speed: { min: "180", max: "" }
  });
  assert.equal(hooks.state.search, "");
  assert.equal(elements.get("globalSearch").value, "");
  assert.equal(Object.keys(hooks.state.featureFilters).length, 9);
});

test("Pages first load renders and applies acceleration, speed, and EV range defaults", () => {
  const { elements, hooks } = loadAppForTest();
  const config = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "docs", "filter_conditions.json"), "utf8"));
  hooks.state.config = config;
  function model(name, acceleration, speed, range) {
    const result = Object.assign(row("仅懂车帝", 2026, name), {
      "百公里加速(s)": String(acceleration),
      "最高车速(km/h)": String(speed),
      "纯电续航(km)": String(range)
    });
    config.conditions.filter((condition) => ["feature", "pagesFeature"].includes(condition.type)).forEach((condition) => {
      result[condition.fields[0]] = condition.requireKeyword ? condition.keywords[0] : "支持";
    });
    return result;
  }
  hooks.initializeRows([
    model("全部通过", 6.9, 181, 151),
    model("加速失败", 7.1, 181, 151),
    model("车速失败", 6.9, 179, 151),
    model("续航失败", 6.9, 181, 149)
  ]);
  hooks.renderEverything();
  assert.deepEqual(JSON.parse(JSON.stringify(hooks.getFilteredRows().map((item) => item["车型名称"]))), ["全部通过"]);
  const tags = elements.get("selectedTags").children.map((tag) => tag.textContent);
  assert.ok(tags.includes("百公里加速 ≤7 ≥0"));
  assert.ok(tags.includes("最高车速 ≥180"));
  assert.ok(tags.includes("纯电续航 ≥150"));
  const values = {};
  elements.get("centerConditionList").children.forEach((group) => group.children.forEach((item) => {
    if (item.className !== "center-condition-item") return;
    item.children.forEach((child) => child.children && child.children.forEach((input) => {
      if (input.dataset && input.dataset.side) values[input.dataset.conditionId + ":" + input.dataset.side] = input.value;
    }));
  }));
  assert.equal(values["zero_to_hundred:max"], "7");
  assert.equal(values["top_speed:min"], "180");
  assert.equal(values["ev_range:min"], "150");
  assert.equal(values["ev_range:max"], "");
});

test("Pages hides the side condition section when every condition lives in the filter center", () => {
  const { elements, hooks } = loadAppForTest();
  const html = fs.readFileSync(path.join(__dirname, "..", "docs", "index.html"), "utf8");
  assert.match(html, /<section id="advancedConditionSection" hidden>/);

  hooks.state.config.conditions = [
    { id: "zero_to_hundred", label: "百公里加速", type: "range", field: "百公里加速(s)" },
    { id: "ev_range", label: "纯电续航", type: "range", field: "纯电续航(km)" },
    { id: "city_navigation", label: "NOA城市领航", type: "feature", fields: ["NOA城市领航"], keywords: ["支持"] }
  ];
  hooks.state.config.centerConditionGroups = [
    { id: "core", label: "核心条件", conditionIds: ["zero_to_hundred", "ev_range", "city_navigation"] }
  ];
  hooks.initializeRows([row("仅懂车帝", 2026, "样例")]);
  hooks.renderEverything();
  assert.equal(elements.get("advancedConditionSection").hidden, true);
  assert.equal(elements.get("conditionList").children[0].children.length, 0);

  hooks.state.config.conditions.push({ id: "heat_pump", label: "热泵管理系统", type: "feature", fields: ["热泵管理系统"], keywords: ["支持"] });
  hooks.renderEverything();
  assert.equal(elements.get("advancedConditionSection").hidden, false);
  assert.equal(elements.get("conditionList").children[0].children.length, 1);
});

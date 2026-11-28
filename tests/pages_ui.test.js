"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

test("header evidence stays internal without hiding unrelated double-underscore fields", () => {
  const hooks = loadAppForTest().hooks;
  assert.equal(hooks.shouldHideColumn("__header_normalization_evidence", []), true);
  assert.equal(hooks.shouldHideColumn("__custom_equipment", []), false);
});

test("display columns render grouped by category without series coverage sort or counts", () => {
  const { hooks, elements } = loadAppForTest();
  hooks.state.columns = ["品牌", "自定义特征"];
  hooks.state.visibleColumns = new Set(["品牌"]);
  hooks.state.rows = [
    { "品牌": "小鹏汽车", "车系": "小鹏G6", "自定义特征": "●" },
    { "品牌": "比亚迪", "车系": "海豹", "自定义特征": "●" },
  ];
  hooks.renderColumnList();
  const labels = descendants(elements.get("columnList")).filter((node) => node.tagName === "SPAN");
  assert.deepEqual(labels.map((node) => node.textContent), ["品牌", "自定义特征"]);
  assert.equal(descendants(elements.get("columnList")).some((node) => node.textContent === "看车款"), false);
});

test("rare and common surround-view fields share a category without losing source values", () => {
  const { hooks } = loadAppForTest();
  hooks.state.config = JSON.parse(fs.readFileSync(path.join(__dirname, "../config/filter_conditions.json"), "utf8"));
  const row = {"180°透明底盘":"○", "透明底盘/540°影像":"●"};
  for (const column of Object.keys(row)) {
    assert.equal(hooks.columnPath(column).minor, "全景影像与底盘透视");
  }
  const source = {...row, ["180°透明底盘系统"]: "汽车之家:○ 3000元|易车:不支持", ["底盘透视"]: "懂车帝:●"};
  const [normalized] = hooks.normalizeRowColumns([source]);
  assert.equal(normalized["底盘透视"], "懂车帝:●|○|汽车之家:○ 3000元|易车:不支持");
  assert.equal(normalized["透明底盘/540°影像"], "●");
  assert.equal(normalized["180°透明底盘"], undefined);
  assert.equal(normalized["180°透明底盘系统"], undefined);
  assert.equal(source["180°透明底盘"], "○");
  for (const alias of ["180°透明底盘", "180°透明底盘系统", "180°透明底盘_2", "底盘透视_2", "透明底盘_2"]) {
    const [optional] = hooks.normalizeRowColumns([{[alias]: "○"}]);
    assert.equal(optional["底盘透视"], "○");
    assert.equal(hooks.columnPath("底盘透视").minor, "全景影像与底盘透视");
  }
});

test("instrument display sizes consolidate inch aliases and preserve real differences", () => {
  const { hooks } = loadAppForTest();
  hooks.state.config = JSON.parse(fs.readFileSync(path.join(__dirname, "../config/filter_conditions.json"), "utf8"));
  const rows = hooks.normalizeRowColumns([
    {"液晶仪表尺寸": "汽车之家:12.30", "液晶仪表尺寸(in)": "12.3英寸|懂车帝:10.25 in"},
    {"液晶仪表尺寸": "●", "液晶仪表尺寸(in)": "10.25"},
    {"液晶仪表尺寸": "—", "液晶仪表尺寸(in)": "○"},
    {"液晶仪表尺寸(in)": "8.88|8.880"},
    {"液晶仪表尺寸": "25.4cm", "液晶仪表尺寸(in)": "10.25"},
  ]);
  assert.equal(rows[0]["液晶仪表尺寸(in)"], "汽车之家:12.3|懂车帝:10.25");
  assert.equal(rows[1]["液晶仪表尺寸(in)"], "10.25");
  assert.equal(rows[2]["液晶仪表尺寸(in)"], undefined);
  assert.equal(rows[3]["液晶仪表尺寸(in)"], "8.88");
  assert.equal(rows[4]["液晶仪表尺寸(in)"], "10.25");
  assert.equal(rows[4]["液晶仪表尺寸"], "25.4cm");
  assert.ok(rows.slice(0, 4).every((row) => !Object.hasOwn(row, "液晶仪表尺寸")));
});

test("instrument size accepts explicit lists without guessing ambiguous measurements", () => {
  const { hooks } = loadAppForTest();
  const rows = hooks.normalizeRowColumns([
    {"液晶仪表尺寸": "汽车之家:3.5英寸 / 9.2英寸 / 10.25英寸|懂车帝:3.50+10.25+9.2"},
    {"液晶仪表尺寸": "7英寸／12.3英寸", "液晶仪表尺寸(in)": "7.00|12.30"},
    {"液晶仪表尺寸": "10.25英寸 / 32cm"},
    {"液晶仪表尺寸": "12 / 3英寸（副屏）"},
    {"液晶仪表尺寸": "10.25英寸 / 12.3英寸|未知", "液晶仪表尺寸(in)": "10.25 in"},
  ]);
  assert.equal(rows[0]["液晶仪表尺寸(in)"], "汽车之家:3.5|汽车之家:9.2|汽车之家:10.25");
  assert.equal(rows[1]["液晶仪表尺寸(in)"], "7|12.3");
  assert.equal(rows[2]["液晶仪表尺寸(in)"], undefined);
  assert.equal(rows[2]["液晶仪表尺寸"], "10.25英寸 / 32cm");
  assert.equal(rows[3]["液晶仪表尺寸"], "12 / 3英寸（副屏）");
  assert.equal(rows[4]["液晶仪表尺寸(in)"], "10.25|12.3");
  assert.ok([rows[0], rows[1], rows[4]].every(row => !Object.hasOwn(row, "液晶仪表尺寸")));
});

test("audited spelling aliases preserve source values and leave different packages separate", () => {
  const { hooks } = loadAppForTest();
  const original = {
    "MBUX 智能人机交互系统实景穿越导航": "●",
    "MBUX 智能人机交互系统实景穿越导航_2": "汽车之家:○ 4100元|○ 4700元",
    "MBUX智能人机交互系统实景穿越导航_2": "懂车帝:不支持|●",
    "AMG 扰流板": "○",
    "AMG扰流板": "○",
    "AMG 外观组件_1": "运动排气系统",
    "AMG外观组件_1": "红色制动卡钳"
  };
  const [row] = hooks.normalizeRowColumns([original]);
  assert.equal(row["MBUX智能人机交互系统实景穿越导航"], "●");
  assert.equal(row["MBUX智能人机交互系统实景穿越导航_2"], "懂车帝:不支持|懂车帝:●|汽车之家:○ 4100元|汽车之家:○ 4700元");
  assert.equal(row["AMG扰流板"], "○");
  assert.equal(row["AMG 外观组件_1"], "运动排气系统");
  assert.equal(row["AMG外观组件_1"], "红色制动卡钳");
  assert.ok(!Object.hasOwn(row, "AMG 扰流板"));
  assert.ok(Object.hasOwn(original, "AMG 扰流板"));
});

test("sensor count aliases combine measurements and preserve unquantified observations", () => {
  const { hooks } = loadAppForTest();
  const [row, zero] = hooks.normalizeRowColumns([
    {"车内摄像头数量":"1个 / 2个","车内摄像头数量(个)":"2.0",
     "激光雷达数量":"汽车之家:1个|懂车帝:●|待查","激光雷达数量(个)":"易车:2",
     "激光雷达数量(2)":"○ 暂无价格","摄像头数量":"5个"},
    {"毫米波雷达数量":"0个","超声波雷达数量":"4 / 8","车外摄像头数量":"5个"},
  ]);
  assert.equal(row["车内摄像头数量(个)"], "2|1");
  assert.equal(row["车内摄像头数量"], undefined);
  assert.equal(row["激光雷达数量(个)"], "易车:2|汽车之家:1");
  assert.equal(row["激光雷达数量"], "懂车帝:●|懂车帝:待查");
  assert.equal(row["激光雷达数量(2)"], "○ 暂无价格");
  assert.equal(row["摄像头数量"], "5个");
  assert.equal(zero["毫米波雷达数量(个)"], "0");
  assert.equal(zero["超声波雷达数量"], "4 / 8");
  assert.equal(zero["车外摄像头数量(个)"], "5");
});

test("sensor count ranges keep numeric controls and exclude unquantified records", () => {
  const { hooks, elements } = loadAppForTest();
  const column = "激光雷达数量(个)";
  const base = row("汽车之家", 2026, "样本");
  const sample = (name, value) => ({...base, "车型名称": name, "车系": name, [column]: value});
  hooks.state.config = {conditions: [], defaultVisibleColumns: [column]};
  hooks.initializeRows([
    sample("混合证据", "汽车之家:2|懂车帝:支持|待查"),
    sample("仅支持", "支持"),
    sample("明确零个", "0"),
    sample("两种数值", "2|3"),
    sample("歧义文本", "2|4 / 8"),
  ]);
  hooks.state.saleScope = "all";
  hooks.state.visibleColumns = new Set([column]);
  hooks.renderTableHead();
  assert.equal(descendants(elements.get("tableHead")).filter(x => x.tagName === "INPUT" && x.type === "number").length, 2);

  hooks.state.columnFilters = {[column]: {operator: "range", min: "2", max: "2"}};
  assert.deepEqual(Array.from(hooks.getFilteredRows(), x => x["车型名称"]), ["混合证据"]);
  hooks.state.columnFilters = {[column]: {operator: "range", min: "0", max: "0"}};
  assert.deepEqual(Array.from(hooks.getFilteredRows(), x => x["车型名称"]), ["明确零个"]);
});

test("verified placeholder-only source columns reappear as soon as a source provides an observation", () => {
  const {hooks} = loadAppForTest();
  hooks.state.config = {conditions: [], defaultVisibleColumns: []};
  const base = row("汽车之家", 2026, "数据样本");
  hooks.initializeRows([
    {...base, "camera_count_v4": "待查", "battery_brand_v4": "懂车帝:未知|易车:暂无", "自定义字段_v4": "待查"},
    {...base, "车型名称": "第二款", "camera_count_v4": "—", "battery_brand_v4": "N/A"},
  ]);
  assert.ok(!hooks.state.columns.includes("camera_count_v4"));
  assert.ok(!hooks.state.columns.includes("battery_brand_v4"));
  assert.ok(hooks.state.columns.includes("自定义字段_v4"));

  hooks.initializeRows([
    {...base, "camera_count_v4": "易车:0", "battery_brand_v4": "汽车之家:待查|懂车帝:宁德时代"},
  ]);
  assert.ok(hooks.state.columns.includes("camera_count_v4"));
  assert.ok(hooks.state.columns.includes("battery_brand_v4"));
});

test("new provider ID columns remain internal", () => {
  const { hooks } = loadAppForTest();
  hooks.state.config = { hiddenByDefault: [], defaultVisibleColumns: [] };
  for (const column of ["车款ID_汽车之家", "车款ID_懂车帝", "车款ID_易车"]) {
    assert.equal(hooks.shouldHideColumn(column, []), true);
  }
});

test("Pages hides only the provider-scoped dongchedi car id metadata column", () => {
  const { hooks } = loadAppForTest();
  hooks.state.config = { hiddenByDefault: [], dropIfUniformPositive: [], defaultVisibleColumns: [] };
  assert.equal(hooks.shouldHideColumn("懂车帝车型ID", []), true);
  ["车型ID", "车系ID", "懂车帝车系ID", "汽车之家车型ID", "易车车型ID", "某陌生配置列", "__custom_equipment"]
    .forEach((column) => {
      assert.equal(hooks.shouldHideColumn(column, []), false, column);
    });
});

function chunkFixture(parts) {
  const files = new Map();
  const chunks = parts.map((rows, index) => {
    const bytes = Buffer.from(JSON.stringify(rows), "utf8");
    const path = "data/latest." + index + ".json";
    files.set(path, bytes);
    return { path, rowCount: rows.length, size: bytes.length,
      sha256: require("node:crypto").createHash("sha256").update(bytes).digest("hex") };
  });
  return { files, manifest: { rowCount: parts.reduce((sum, rows) => sum + rows.length, 0),
    files: { latestJsonChunks: chunks } } };
}

function chunkResponse(bytes) {
  return { ok: true, arrayBuffer: async () => bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) };
}

test("published chunks retain raw sequence despite out-of-order completion and use at most four fetches", async () => {
  const app = loadAppForTest();
  const rows = Array.from({ length: 13 }, (_, index) => ({ id: index, "原始字段": "车型" + index }));
  const fixture = chunkFixture(rows.map((row) => [row]));
  let active = 0;
  let maximum = 0;
  const completion = [];
  app.setFetch(async (path) => {
    active += 1;
    maximum = Math.max(maximum, active);
    const index = Number(path.match(/\.(\d+)\.json$/)[1]);
    await new Promise((resolve) => setTimeout(resolve, index === 0 ? 30 : 1));
    active -= 1;
    completion.push(index);
    return chunkResponse(fixture.files.get(path));
  });
  const loaded = await app.hooks.loadPublishedRows(fixture.manifest);
  assert.deepEqual(JSON.parse(JSON.stringify(loaded)), rows);
  assert.equal(maximum, 4);
  assert.notEqual(completion[0], 0);
  assert.equal(app.hooks.state.rows.length, 0, "loader does not initialize partial UI rows");
});

test("chunked and single-file datasets produce identical display rows and source counts", async () => {
  const raw = [
    row("汽车之家", 2025, "甲车 2025款"),
    row("懂车帝", 2025, "甲车 2025款"),
    row("易车", "", "易车无年款"),
    row("懂车帝", 2020, "过旧车型")
  ];
  const normal = loadAppForTest();
  normal.hooks.initializeRows(raw);
  const chunked = loadAppForTest();
  const fixture = chunkFixture([raw.slice(0, 1), raw.slice(1, 3), raw.slice(3)]);
  chunked.setFetch(async (path) => chunkResponse(fixture.files.get(path)));
  chunked.hooks.initializeRows(await chunked.hooks.loadPublishedRows(fixture.manifest));
  assert.deepEqual(JSON.parse(JSON.stringify(chunked.hooks.state.rows)), JSON.parse(JSON.stringify(normal.hooks.state.rows)));
  normal.hooks.renderResultsOnly();
  chunked.hooks.renderResultsOnly();
  for (const id of ["totalCount", "dongchediCount", "autohomeCount", "yicheCount"]) {
    assert.equal(chunked.elements.get(id).textContent, normal.elements.get(id).textContent);
  }
});

test("published loader keeps normal single-file hosting behavior", async () => {
  const app = loadAppForTest();
  const expected = [{ id: 1 }];
  let requested;
  app.setFetch(async (path) => { requested = path; return { ok: true, json: async () => expected }; });
  assert.equal(await app.hooks.loadPublishedRows({ files: { latestJson: "data/full.json" } }), expected);
  assert.equal(requested, "data/full.json");
});

test("published loader rejects missing, corrupted, truncated, and count-mismatched chunks", async (t) => {
  for (const kind of ["missing", "hash", "size", "partCount", "totalCount", "duplicate", "noCrypto", "nonArray"]) {
    await t.test(kind, async () => {
      const app = loadAppForTest();
      const fixture = chunkFixture([[{ id: 0 }], [{ id: 1 }]]);
      let bytes = fixture.files.get("data/latest.0.json");
      if (kind === "hash") { fixture.manifest.files.latestJsonChunks[0].sha256 = "0".repeat(64); }
      if (kind === "size") { fixture.manifest.files.latestJsonChunks[0].size += 1; }
      if (kind === "partCount") {
        fixture.manifest.files.latestJsonChunks[0].rowCount = 2;
        fixture.manifest.rowCount = 3;
      }
      if (kind === "totalCount") { fixture.manifest.rowCount = 99; }
      if (kind === "duplicate") { fixture.manifest.files.latestJsonChunks[1].path = "data/latest.0.json"; }
      if (kind === "noCrypto") { app.setCrypto({}); }
      if (kind === "nonArray") {
        bytes = Buffer.from("{}");
        const descriptor = fixture.manifest.files.latestJsonChunks[0];
        descriptor.size = bytes.length;
        descriptor.sha256 = require("node:crypto").createHash("sha256").update(bytes).digest("hex");
      }
      app.setFetch(async (path) => {
        if (kind === "missing" && path === "data/latest.1.json") { return { ok: false, status: 404 }; }
        return chunkResponse(path === "data/latest.0.json" ? bytes : fixture.files.get(path));
      });
      await assert.rejects(app.hooks.loadPublishedRows(fixture.manifest));
      assert.equal(app.hooks.state.rows.length, 0);
    });
  }
});

test("chunked full JSON download uses unmodified published rows instead of normalized UI rows", async () => {
  const app = loadAppForTest();
  const raw = [{ "车型名称": "甲", "原始字段": "证据" }, { "车型名称": "乙", "年款": 2020 }];
  app.hooks.state.manifest = { files: { latestJsonChunks: [{ path: "data/latest.0.json" }] } };
  app.hooks.state.publishedRawRows = raw;
  app.hooks.state.rows = [{ "车型名称": "normalized subset" }];
  app.hooks.renderDownloads();
  const link = app.elements.get("downloadList").children.find((child) => child.textContent === "完整 JSON");
  assert.ok(link);
  link.dispatch("click");
  assert.equal(app.downloads.length, 1);
  assert.deepEqual(JSON.parse(await app.downloads[0].text()), raw);
});


function descendants(element) {
  return [element].concat(...(element.children || []).map(descendants));
}

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
    this.style = {};
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
  const downloads = [];
  const frames = [];
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
    URL: { createObjectURL: (blob) => { downloads.push(blob); return "blob:test"; }, revokeObjectURL() {} },
    atob,
    btoa,
    crypto,
    document,
    fetch: () => new Promise(() => {}),
    localStorage: { getItem: () => null, removeItem() {}, setItem() {} },
    navigator: { clipboard: { writeText: () => Promise.resolve() } },
    window: { requestAnimationFrame: (fn) => frames.push(fn) }
  };
  context.window.window = context.window;
  context.window.crypto = crypto;

  const appPath = path.join(__dirname, "..", "docs", "app.js");
  const source = fs.readFileSync(appPath, "utf8").replace(
    /\}\(\)\);\s*$/,
    `window.CARS_TEST_HOOKS = {
      skuProviderConflict: skuProviderConflict,
      atomicSources: typeof atomicSources === "function" ? atomicSources : undefined,
      getFilteredRows: getFilteredRows,
      groupRowsBySeries: groupRowsBySeries,
      sortSeriesGroups: sortSeriesGroups,
      renderCards: renderCards,
      initializeRows: initializeRows,
      loadPublishedRows: loadPublishedRows,
      renderDownloads: renderDownloads,
      renderEverything: renderEverything,
      renderResultsOnly: renderResultsOnly,
      renderSelectedTags: renderSelectedTags,
      snapshotFilters: snapshotFilters,
      applySnapshot: applySnapshot,
      getFilteredRows: getFilteredRows,
      conditionMatches: conditionMatches,
      defaultRangeFilters: DEFAULT_RANGE_FILTERS,
      normalizeRowColumns: normalizeRowColumns,
      isEquipmentColumn: isEquipmentColumn,
      shouldHideColumn: shouldHideColumn,
      classifySkuColumns: classifySkuColumns,
      getFilterTaxonomy: getFilterTaxonomy,
      desktopConditionGroups: desktopConditionGroups,
      selectedCountForCategory: selectedCountForCategory,
      activateMobileCategory: activateMobileCategory,
      restoreDefaultFilters: restoreDefaultFilters,
      formatDataTimestamp: formatDataTimestamp,
      parseAwsRawReleaseTimestamp: parseAwsRawReleaseTimestamp,
      renderDataMeta: renderDataMeta,
      renderTableBody: renderTableBody,
      renderTableHead: renderTableHead,
      tableColumnWidthClass: tableColumnWidthClass,
      syncTableHeaderOffsets: syncTableHeaderOffsets,
      renderColumnList: renderColumnList,
      renderFilters: renderFilters,
      renderCenterFilters: renderCenterFilters,
      columnPath: columnPath,
      conditionTagLabel: conditionTagLabel,
      normEnumValue: normEnumValue,
      exportCurrentCsv: exportCurrentCsv,
      exportCurrentJson: exportCurrentJson,
      skuPrice: skuPrice,
      state: state
    };
  }());`
  );
  vm.runInNewContext(source, context, { filename: appPath });
  return { elements, hooks: context.window.CARS_TEST_HOOKS, downloads,
    setFetch(fn) { context.fetch = fn; },
    setCrypto(value) { context.window.crypto = value; },
    setMatchMedia(matches) { context.window.matchMedia = () => ({ matches, addEventListener() {} }); },
    flushFrames() { let count = 0; while (frames.length) { assert.ok(++count < 10000); frames.shift()(); } },
    pendingFrames() { return frames.length; }
  };
}


test("data generation time formats to minute precision", () => {
  const { elements, hooks } = loadAppForTest();
  // 2026-08-10 11:43 UTC -> local minute precision, no seconds
  const out = hooks.formatDataTimestamp("2026-08-10T11:43:47.546481+00:00");
  assert.match(out, /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/, "YYYY-MM-DD HH:mm");
  assert.ok(!/:\d{2}:\d{2}/.test(out), "no seconds in output");
  assert.equal(hooks.formatDataTimestamp(""), "", "empty iso -> empty");
  assert.equal(hooks.formatDataTimestamp("not-a-date"), "", "invalid iso -> empty");
  assert.equal(hooks.parseAwsRawReleaseTimestamp("aws-raw-20261113T230500Z"), "2026-11-13T23:05:00Z");

  hooks.state.manifest = {
    date: "20261113",
    updatedAt: "2026-11-27T10:12:44.119512+00:00",
    provenance: { awsRawRelease: "aws-raw-20261113T230500Z" },
    publication: { frontendUpdatedAt: "2026-11-28T03:00:00+00:00" },
  };
  hooks.renderDataMeta(hooks.state.manifest, 19174);
  const text = descendants(elements.get("dataMeta")).map((node) => node.textContent).join("|");
  assert.match(text, /数据爬取时间/);
  assert.match(text, /数据处理时间/);
  assert.match(text, /前端格式变化时间/);
  assert.match(text, /综合核验 19174 款车型/);
});
test("Pages combines equivalent measurement values without mixing driving cycles", () => {
  const { hooks } = loadAppForTest();
  const raw = [
    Object.assign(row("懂车帝", 2026, "甲配置"), {
      "车系": "数值样本", "纯电续航(km)": "WLTC:163|163|215 CLTC:640|640", "百公里加速(s)": "7|7.0|7.00"
    }),
    Object.assign(row("懂车帝", 2026, "乙配置"), {
      "车系": "数值样本", "纯电续航(km)": "WLTC:170/230/170|CLTC:163", "百公里加速(s)": "7.00/7.2"
    }),
    Object.assign(row("懂车帝", 2026, "另一个系列"), {
      "车系": "保留样本", "纯电续航(km)": "WLTC:待公布|CLTC:640", "百公里加速(s)": "约7秒"
    }),
    Object.assign(row("懂车帝", 2026, "有来源前缀"), {
      "车系": "保留样本", "纯电续航(km)": "懂车帝: WLTC： 170/170.0|易车:CLTC:170",
      "百公里加速(s)": "懂车帝: 7秒|易车:7.00s"
    }),
  ];
  const original = JSON.stringify(raw);
  hooks.initializeRows(raw);
  const [a, b, c, d] = hooks.state.rows;
  assert.equal(a["纯电续航(km)"], "WLTC:163/215 · CLTC:640");
  assert.equal(b["纯电续航(km)"], "WLTC:170/230 · CLTC:163");
  assert.equal(a["百公里加速(s)"], "7");
  assert.equal(b["百公里加速(s)"], "7/7.2");
  assert.equal(c["纯电续航(km)"], "WLTC:待公布|CLTC:640");
  assert.equal(c["百公里加速(s)"], "约7秒");
  assert.equal(d["纯电续航(km)"], "懂车帝:WLTC:170 · 易车:CLTC:170");
  assert.equal(d["百公里加速(s)"], "懂车帝:7");
  const groups = hooks.groupRowsBySeries(hooks.state.rows).filter((group) => group.name === "数值样本");
  const cards = hooks.renderCards(groups);
  assert.match(cards[0].meta, /WLTC:163\/215\/170\/230 · CLTC:640\/163/);
  assert.match(cards[0].meta, /百公里加速\(s\): 7-7\.2/);
  assert.equal(JSON.stringify(raw), original);
});

test("SKU expands in cards and table with exact source links only", () => {
  const { hooks, elements } = loadAppForTest();
  hooks.state.yicheSkuSlugs = { "测试品牌|链接样本": "jmev-468" };
  const common = { "车系": "链接样本", "跨源归并ID": "links-fixture" };
  hooks.initializeRows([
    Object.assign(row("汽车之家+易车", 2026, "同一车款"), common, { "车款ID": "174772", "车款ID_汽车之家": "76720", "12.3英寸": "●",
      "智慧驾驶包(整包选装)_1": "抬头显示" }),
    Object.assign(row("仅易车", 2026, "同一车款"), common, { "车款ID_易车": "174772",
      "智慧驾驶包(整包选装)_2": "○ 6000元", "易车车型链接": "https://car.yiche.com.evil.invalid/jmev-468/m174772/peizhi/" }),
    Object.assign(row("懂车帝", 2026, "同一车款"), common, { "懂车帝车型ID": "256585",
      "选装包列表": { "舒适包": { "描述": "座椅通风", "状态": "选装" } },
      "某陌生配置列": "实际属性" }),
  ]);
  assert.equal(hooks.state.rows.length, 1);
  const columns = Array.from(hooks.state.columns);
  for (const value of ["12.3英寸", "智慧驾驶包(整包选装)_1", "智慧驾驶包(整包选装)_2", "选装包列表", "易车车型链接"]) {
    assert.ok(!columns.includes(value), value);
  }
  assert.ok(columns.includes("某陌生配置列"));
  const groups = hooks.groupRowsBySeries(hooks.state.rows);
  hooks.state.expandedSeries.add(groups[0].key);
  hooks.renderCards(groups);
  const cardDetails = descendants(elements.get("cardList")).find((node) => node.className === "sku-details");
  assert.equal(cardDetails.children[0].textContent, "来源链接");
  hooks.state.mode = "table";
  hooks.renderTableBody(hooks.state.rows);
  for (const root of [elements.get("cardList"), elements.get("tableBody")]) {
    const details = descendants(root).find((node) => node.className === "sku-details");
    assert.ok(details);
    assert.equal(descendants(details).filter((node) => node.tagName === "A").length, 0);
    details.open = true;
    details.dispatch("toggle");
    details.dispatch("toggle");
    const links = descendants(details).filter((node) => node.tagName === "A");
    assert.deepEqual(links.map((node) => node.href).sort(), [
      "https://car.autohome.com.cn/config/spec/76720.html",
      "https://car.yiche.com/jmev-468/m174772/peizhi/",
      "https://www.dongchedi.com/auto/params-carIds-256585",
    ]);
    assert.ok(links.every((node) => node.rel === "noopener noreferrer"));
    assert.equal(details.children.length, 2);
    assert.ok(!descendants(details).some((node) => /舒适包|智慧驾驶包|抬头显示/.test(node.textContent)));
  }
});

test("package-only circle and dash columns stay hidden, preserving real attributes", () => {
  const { hooks, elements } = loadAppForTest();
  hooks.state.config = JSON.parse(fs.readFileSync(path.join(__dirname, "../config/filter_conditions.json"), "utf8"));
  const dependency = "1外后视镜记忆、防炫目功能：须与记忆座椅和自动防眩目内后视镜一起选";
  const first = Object.assign(row("懂车帝", 2026, "有选装"), {
    [dependency]: "○",
    "灯光扩展包": "●", "定制迎宾投影": "●", "真实布尔属性": "●",
    "零重力座椅": "第一排",
    "选装包列表": { "灯光扩展包": { "描述": "包含：定制迎宾投影、零重力座椅" } },
  });
  const second = Object.assign(row("懂车帝", 2026, "无选装"), {
    [dependency]: "-",
    "灯光扩展包": "-", "定制迎宾投影": "-", "真实布尔属性": "-", "零重力座椅": "●",
  });
  hooks.initializeRows([first, second]);
  const cols = Array.from(hooks.state.columns);
  assert.ok(!cols.includes("灯光扩展包"));
  assert.ok(!cols.includes("定制迎宾投影"));
  assert.ok(!cols.includes(dependency));
  assert.ok(cols.includes("真实布尔属性"));
  assert.ok(cols.includes("零重力座椅"));
  const groups = hooks.groupRowsBySeries(hooks.state.rows);
  hooks.state.expandedSeries.add(groups[0].key);
  hooks.renderCards(groups);
  const details = descendants(elements.get("cardList")).filter((node) => node.className === "sku-details");
  assert.equal(details.length, 2);
  for (const item of details) { item.open = true; item.dispatch("toggle"); }
  assert.ok(details.every((item) => !descendants(item).some((node) => node.className === "sku-option-packages")));
});

test("source-labelled package markers do not promote package content to attributes", () => {
  const { hooks } = loadAppForTest();
  const rows = [
    { "选装包列表": { "灯光扩展包": { "描述": "包含：定制迎宾投影、专属照地灯、真实属性、跨车系通用功能" } },
      "定制迎宾投影": "懂车帝:●", "专属照地灯": "汽车之家:○ 3000元", "真实属性": "汽车之家:前排",
      "独立布尔属性": "懂车帝:●", "跨车系通用功能": "懂车帝:●" },
    { "定制迎宾投影": "易车:-", "专属照地灯": "易车:无", "真实属性": "易车:●" },
    { "车系": "另一个车系", "跨车系通用功能": "懂车帝:●" },
  ];
  assert.equal(hooks.shouldHideColumn("跨车系通用功能", rows), false);
  assert.equal(hooks.shouldHideColumn("定制迎宾投影", rows), true);
  assert.equal(hooks.shouldHideColumn("专属照地灯", rows), true);
  assert.equal(hooks.shouldHideColumn("真实属性", rows), false);
  assert.equal(hooks.shouldHideColumn("独立布尔属性", rows), false);
  assert.equal(rows[0]["专属照地灯"], "汽车之家:○ 3000元");
});

test("named package editions and spaced legacy package pairs stay out of display columns", () => {
  const { hooks } = loadAppForTest();
  const rows = [
    { ...row("仅易车", 2026, "套件样本"), "奥迪全方位辅助包 高端版": "○", "辅助驾驶包 Pro(绑定选择泊车辅助高级版)": "○|选配",
      "豪华冬季包  _1": "前后排座椅加热,方向盘加热", "豪华冬季包  _2": "○ 3500元",
      "奥迪手机盒子": "○", "背包 收纳空间": "4L", "纯文本字段 _2": "第二项" },
    { ...row("仅汽车之家", 2026, "对照样本"), "奥迪全方位辅助包 高端版": "选配", "合法属性(高端版)": "●" },
  ];
  hooks.initializeRows(rows);
  const columns = hooks.state.columns;
  for (const name of ["奥迪全方位辅助包 高端版", "辅助驾驶包 Pro(绑定选择泊车辅助高级版)",
    "豪华冬季包  _1", "豪华冬季包  _2"]) {
    assert.equal(columns.includes(name), false, name);
  }
  for (const name of ["奥迪手机盒子", "背包 收纳空间", "纯文本字段 _2", "合法属性(高端版)"]) {
    assert.equal(columns.includes(name), true, name);
  }
});

test("numeric variants priced as options do not become independent property columns", () => {
  const { hooks } = loadAppForTest();
  hooks.state.config = { defaultVisibleColumns: ["扬声器数量"], hiddenByDefault: [], conditions: [] };
  const samples = {
    "扬声器数量(个)(27)": "○ 15800元",
    "副驾驶屏幕尺寸(14)": "汽车之家:○ 暂无价格",
    "激光雷达数量(2)": "○ 暂无价格",
    "激光雷达数量(1)": "支持|○ 暂无价格",
    "激光雷达数量(3)": "○ 5000元|●",
    "外置扬声器数量(3)": "○ 5000元",
    "扬声器数量": "12",
  };
  const rows = [samples, {"激光雷达数量(2)": "-", "扬声器数量(个)(27)": "—"}];
  for (const column of ["扬声器数量(个)(27)", "副驾驶屏幕尺寸(14)", "激光雷达数量(2)"]) {
    assert.equal(hooks.shouldHideColumn(column, rows), true, column);
  }
  for (const column of ["激光雷达数量(1)", "激光雷达数量(3)", "外置扬声器数量(3)", "扬声器数量"]) {
    assert.equal(hooks.shouldHideColumn(column, rows), false, column);
  }
});

test("concrete audio and wheel choices with only optional observations stay out of display columns", () => {
  const { hooks } = loadAppForTest();
  hooks.state.config = { defaultVisibleColumns: ["扬声器数量"], hiddenByDefault: [], conditions: [] };
  const choices = {
    "14扬声器哈曼卡顿音响":"○",
    "23扬声器":"选配",
    "音响品牌(劲浪)":"○ 暂无价格",
    "5辐V型设计车轮":"选配",
    "前19英寸，后20英寸锻造轮圈，双辐式样825M型，双色":"○|选配",
  };
  const preserved = {
    "扬声器数量":"14",
    "40W外置扬声器":"●",
    "定制轮毂颜色":"选配",
    "20扬声器高级定制音响":"选配|标配",
    "NEVO Sound天枢源声音响系统":"●",
  };
  const rows = [{...choices,...preserved}];
  for (const column of Object.keys(choices)) assert.equal(hooks.shouldHideColumn(column, rows), true, column);
  for (const column of Object.keys(preserved)) assert.equal(hooks.shouldHideColumn(column, rows), false, column);
});

test("branded audio option spellings use the same evidence rule without hiding standard equipment", () => {
  const { hooks } = loadAppForTest();
  hooks.state.config = {defaultVisibleColumns: ["音响品牌"], hiddenByDefault: []};
  const optional = {
    "Bang & Olufsen 豪华音响系统带头枕音响": "○",
    "Bang&Olufsen豪华音响系统+头枕音响": "○|选配",
    "Bowers & Wilkins环绕式音响系统": "易车:○ 暂无价格",
  };
  const retained = {
    "音响品牌": "Bang & Olufsen",
    "Bang & Olufsen豪华音响系统": "○|标配",
    "Bang & Olufsen扬声器数量": "14",
    "NEVO Sound天枢源声音响系统": "●",
  };
  const rows = [{...optional, ...retained}];
  for (const column of Object.keys(optional)) assert.equal(hooks.shouldHideColumn(column, rows), true, column);
  for (const column of Object.keys(retained)) assert.equal(hooks.shouldHideColumn(column, rows), false, column);
});

test("option-only numbered safety systems and home charger packages stay out of display columns", () => {
  const hooks = loadAppForTest().hooks;
  hooks.state.config = { hiddenByDefault: [], defaultVisibleColumns: [], conditions: [] };
  const rows = [
    {"360°全场景安全系统1":"选配", "360°全场景安全系统2":"选装", "7kW智能家充桩套餐_30米_":"选配",
     "21英寸星芒轮毂武士黑版":"选配", "21寸六芒星驰样式":"○", "普通套餐":"选配",
     "180°透明底盘":"●", "360°全景透明影像系统_2":"●", "21英寸光幅轮毂":"●",
     "360°全场景安全系统3":"选配"},
    {"360°全场景安全系统3":"●", "21英寸光幅轮毂":"选配", "7kW智能家充桩套餐_30米_":"-"},
  ];
  const columns = new Set(Object.keys(rows[0]).filter((name) => hooks.shouldHideColumn(name, rows)));
  ["360°全场景安全系统1", "360°全场景安全系统2", "7kW智能家充桩套餐_30米_",
   "21英寸星芒轮毂武士黑版", "21寸六芒星驰样式"].forEach((name) => assert.equal(columns.has(name), true, name));
  ["普通套餐", "180°透明底盘", "360°全景透明影像系统_2", "21英寸光幅轮毂",
   "360°全场景安全系统3"].forEach((name) => assert.equal(columns.has(name), false, name));
});

test("sized option values without package metadata stay out of display columns", () => {
  const { hooks } = loadAppForTest();
  hooks.state.config = JSON.parse(fs.readFileSync(path.join(__dirname, "../config/filter_conditions.json"), "utf8"));
  const choices = {
    "19英寸AMG双五辐轻合金车轮": "○|选配",
    "19英寸M轻合金轮圈": "○|选配",
    "21英寸光幅轮毂": "选配",
    "5幅Y型金属磨砂灰色车轮": "○|选配",
    "12.3寸全彩液晶仪表": "○",
    "7座_2": "选装",
  };
  hooks.initializeRows([
    Object.assign(row("易车", 2026, "有选装"), choices, {
      "180°透明底盘": "○", "轮圈尺寸(英寸)": "19", "座位数(个)": "7",
      "21英寸星芒轮毂": "●", "21英寸实测轮圈": "21",
    }),
    Object.assign(row("汽车之家", 2026, "无选装"), {
      "19英寸AMG双五辐轻合金车轮": "-", "21英寸星芒轮毂": "选装",
      "21英寸实测轮圈": "选配",
    }),
  ]);
  const columns = Array.from(hooks.state.columns);
  for (const name of Object.keys(choices)) assert.ok(!columns.includes(name), name);
  for (const name of ["底盘透视", "轮圈尺寸(英寸)", "座位数(个)", "21英寸星芒轮毂", "21英寸实测轮圈"]) {
    assert.ok(columns.includes(name), name);
  }
});

test("SKU details identify the provider whose exact link is unavailable", () => {
  const { hooks, elements } = loadAppForTest();
  hooks.initializeRows([
    Object.assign(row("汽车之家+懂车帝(车系级)", 2026, "双源样本"), { "车款ID": "76720" }),
  ]);
  const groups = hooks.groupRowsBySeries(hooks.state.rows);
  hooks.state.expandedSeries.add(groups[0].key);
  hooks.renderCards(groups);
  const item = descendants(elements.get("cardList")).find((node) => node.className === "sku-details");
  item.open = true;
  item.dispatch("toggle");
  const content = descendants(item);
  assert.equal(hooks.state.rows[0]["交叉核验"], "多源记录");
  assert.ok(!descendants(elements.get("cardList")).some((node) => node.className === "verified-badge"));
  assert.deepEqual(content.filter((node) => node.tagName === "A").map((node) => node.href),
    ["https://car.autohome.com.cn/config/spec/76720.html"]);
  assert.ok(content.some((node) => node.textContent === "懂车帝 · 暂无可确认的车款链接"));
});

test("dual-source badge requires exact SKU links from two distinct providers", () => {
  const { hooks, elements } = loadAppForTest();
  hooks.initializeRows([
    {...row("汽车之家+懂车帝", 2026, "有两家车款链接"), "车款ID_汽车之家": "76720", "车款ID_懂车帝": "125324"},
    {...row("汽车之家+易车", 2026, "没有车款链接")},
  ]);
  assert.equal(hooks.state.rows[0]["交叉核验"], "双源核验");
  assert.equal(hooks.state.rows[1]["交叉核验"], "多源记录");
  const groups = hooks.groupRowsBySeries(hooks.state.rows);
  groups.forEach(group => hooks.state.expandedSeries.add(group.key));
  hooks.renderCards(groups);
  const badges = descendants(elements.get("cardList")).filter(node => node.className === "verified-badge");
  assert.equal(badges.length, 1);
  const linked = descendants(elements.get("cardList")).find(node => node.className === "sku-details");
  linked.open = true;
  linked.dispatch("toggle");
  assert.equal(descendants(linked).filter(node => node.tagName === "A").length, 2);
});

test("conflicting source links in one annotated SKU do not count towards verification", () => {
  const { hooks, elements } = loadAppForTest();
  const first = {...row("汽车之家+懂车帝", 2026, "组合车款"), "跨源归并ID": "test-conflict",
    "汽车之家车款ID": "76720", "懂车帝车型ID": "125324"};
  const second = {...first, "汽车之家车款ID": "76721"};
  for (const records of [[first, second], [second, first]]) {
    hooks.initializeRows(records);
    assert.equal(hooks.state.rows.length, 1);
    assert.equal(hooks.state.rows[0]["交叉核验"], "多源记录");
    const groups = hooks.groupRowsBySeries(hooks.state.rows);
    hooks.state.expandedSeries.add(groups[0].key);
    hooks.renderCards(groups);
    const details = descendants(elements.get("cardList")).find(node => node.className === "sku-details");
    details.open = true;
    details.dispatch("toggle");
    assert.deepEqual(descendants(details).filter(node => node.tagName === "A").map(node => node.href),
      ["https://www.dongchedi.com/auto/params-carIds-125324"]);
    assert.ok(descendants(details).some(node => node.textContent === "汽车之家 · 暂无可确认的车款链接"));
  }
});

test("911 Cabriolet does not borrow the hardtop's Dongchedi SKU ID or sale status", () => {
  const { hooks, elements } = loadAppForTest();
  const wrong = {...row("汽车之家+懂车帝", 2026, "保时捷911 2026款 Carrera Cabriolet 3.0T"),
    "品牌": "保时捷", "车系": "保时捷911", "车款ID": "75254", "懂车帝车型ID": "252828",
    "车款ID_懂车帝": "252828", "上市状态_懂车帝": "在售"};
  const hardtop = {...wrong, "车型名称": "2026款 Carrera 3.0T", "车款ID": "75250"};
  const correct = {...wrong, "懂车帝车型ID": "252832", "车款ID_懂车帝": "252832"};
  hooks.initializeRows([wrong, hardtop]);
  for (const item of hooks.state.rows) {
    const isCabriolet = item["车型名称"].includes("Cabriolet");
    assert.equal(item["交叉核验"], isCabriolet ? "多源记录" : "双源核验");
    assert.equal(item["懂车帝车型ID"], isCabriolet ? undefined : "252828");
    assert.equal(item["上市状态_懂车帝"], isCabriolet ? undefined : "在售");
  }
  const groups = hooks.groupRowsBySeries(hooks.state.rows);
  hooks.state.expandedSeries.add(groups[0].key);
  hooks.renderCards(groups);
  for (const detail of descendants(elements.get("cardList")).filter(node => node.className === "sku-details")) {
    detail.open = true;
    detail.dispatch("toggle");
    const links = descendants(detail).filter(node => node.tagName === "A").map(node => node.href);
    if (links.includes("https://car.autohome.com.cn/config/spec/75254.html")) {
      assert.deepEqual(links, ["https://car.autohome.com.cn/config/spec/75254.html"]);
    }
  }
  hooks.initializeRows([correct]);
  assert.equal(hooks.state.rows[0]["懂车帝车型ID"], "252832");
  assert.equal(hooks.state.rows[0]["交叉核验"], "双源核验");
  assert.equal(wrong["懂车帝车型ID"], "252828");
});

test("conflicting legacy Dongchedi IDs cannot attach to the same annotated cluster", () => {
  const { hooks } = loadAppForTest();
  const annotation = { "跨源归并ID": "linked-cohort" };
  const max = {...row("仅懂车帝", 2026, "Max"), ...annotation, "懂车帝车型ID": "253768", "官方指导价": "28.99万"};
  const plus = {...row("仅懂车帝", 2026, "Max Plus"), ...annotation, "懂车帝车型ID": "262910", "官方指导价": "26.99万"};
  const autohome = {...row("仅汽车之家", 2026, "Max Plus"), ...annotation, "车款ID_汽车之家": "79167", "官方指导价": "26.99万"};
  for (const rows of [[max, plus, autohome], [autohome, plus, max], [plus, autohome, max]]) {
    hooks.initializeRows(rows);
    assert.equal(hooks.state.rows.length, 3);
    assert.ok(hooks.state.rows.every(r => r["交叉核验"] === "单源数据"));
  }
});

test("frontend preserves distinct provider SKU identities even when names and generic IDs match", () => {
  const { hooks } = loadAppForTest();
  const first = { ...row("仅汽车之家", 2026, "测试款"), "车款ID": "76215", "车款ID_汽车之家": "76215" };
  const other = { ...row("仅懂车帝", 2026, "测试款"), "车款ID": "76215", "车款ID_懂车帝": "76215" };
  const ambiguous = { ...row("汽车之家+懂车帝", 2026, "测试款"), "车款ID": "76215" };
  for (const rows of [[first, ambiguous, other], [ambiguous, other, first]]) {
    hooks.initializeRows(rows);
    assert.equal(hooks.state.rows.length, 3);
  }

  const distinct = { ...other, "车款ID": "162153", "车款ID_懂车帝": "162153" };
  const legacy = row("汽车之家+懂车帝", 2026, "测试款");
  for (const rows of [[first, distinct], [first, legacy, distinct], [distinct, legacy, first]]) {
    hooks.initializeRows(rows);
    assert.equal(hooks.state.rows.length, rows.length);
  }
  const annotated = "跨源归并ID";
  hooks.initializeRows([{ ...first, [annotated]: "verified-1" }, { ...distinct, [annotated]: "verified-1" }]);
  assert.equal(hooks.state.rows.length, 1);

  hooks.initializeRows([first, { ...first, "车款ID_汽车之家": "76216" }]);
  assert.equal(hooks.state.rows.length, 2);

  hooks.initializeRows([first, { ...first }]);
  assert.equal(hooks.state.rows.length, 1);
});

test("SKU links reject a conflicting source ID and do not use an ambiguous mixed ID", () => {
  const { hooks, elements } = loadAppForTest();
  hooks.initializeRows([
    Object.assign(row("汽车之家+懂车帝+易车", 2026, "来源ID冲突"), {
      "车款ID": "174772", "车款ID_汽车之家": "76720", "汽车之家车款ID": "76721",
      "车款ID_易车": "174772", "易车车型ID": "174773",
      "易车车型链接": "https://car.yiche.com/jmev-468/m174772/peizhi/",
    }),
    Object.assign(row("汽车之家+易车", 2026, "来源ID缺失"), { "车款ID": "174772" }),
  ]);
  const groups = hooks.groupRowsBySeries(hooks.state.rows);
  hooks.state.expandedSeries.add(groups[0].key);
  hooks.renderCards(groups);
  const details = descendants(elements.get("cardList")).filter((node) => node.className === "sku-details");
  assert.equal(details.length, 2);
  for (const item of details) {
    item.open = true;
    item.dispatch("toggle");
    assert.ok(!descendants(item).some((node) => node.tagName === "A"));
    assert.ok(descendants(item).some((node) => node.textContent === "汽车之家 · 暂无可确认的车款链接"));
    assert.ok(descendants(item).some((node) => node.textContent === "易车 · 暂无可确认的车款链接"));
  }
});

test("core energy, dimensions and rear-wheel steering have the requested defaults", () => {
  const { hooks, elements } = loadAppForTest();
  hooks.state.config = JSON.parse(fs.readFileSync(path.join(__dirname, "../config/filter_conditions.json"), "utf8"));
  hooks.initializeRows([Object.assign(row("懂车帝", 2026, "尺寸样本"), {
    "能源类型": "纯电动", "长*宽*高(mm)": "5000*1900*1500"
  })]);
  const conditions = Object.fromEntries(hooks.state.config.conditions.map(c => [c.id, c]));
  assert.equal(hooks.state.featureFilters.energy_type.join(","), "bev");
  assert.equal(hooks.state.rangeFilters.vehicle_length.max, "5000");
  assert.equal(hooks.state.rangeFilters.vehicle_height.max, "1500");
  assert.ok(!hooks.state.featureFilters.rear_wheel_steering);
  assert.ok(hooks.conditionMatches(hooks.state.rows[0], conditions.vehicle_length));
  assert.ok(hooks.conditionMatches(hooks.state.rows[0], conditions.vehicle_height));
  assert.equal(hooks.conditionMatches({ "长(mm)": "5001mm" }, conditions.vehicle_length), false);
  assert.equal(hooks.conditionMatches({ "高(mm)": "1501" }, conditions.vehicle_height), false);
  assert.equal(hooks.conditionMatches({}, conditions.vehicle_height), false);
  assert.ok(hooks.conditionMatches({ "能源类型": "纯电动|纯电" }, conditions.energy_type));
  assert.equal(hooks.conditionMatches({ "能源类型": "增程式纯电动" }, conditions.energy_type), false);
  assert.equal(hooks.conditionMatches({ "能源类型": "纯电动|汽油" }, conditions.energy_type), false);
  hooks.renderCenterFilters();
  const inputs = descendants(elements.get("centerConditionList")).filter(node => node.type === "checkbox" && node.dataset.conditionId === "energy_type");
  assert.equal(inputs.filter(node => node.checked).map(node => node.dataset.conditionChoice).join(","), "bev");
  const rangeExtender = inputs.find(node => node.dataset.conditionChoice === "erev");
  rangeExtender.checked = true;
  elements.get("centerConditionList").dispatch("change", { target: rangeExtender });
  assert.ok(hooks.conditionMatches({ "能源类型": "增程式纯电动" }, conditions.energy_type));
  hooks.state.featureFilters.rear_wheel_steering = true;
  assert.ok(hooks.conditionMatches({ "主动后轮转向": "●" }, conditions.rear_wheel_steering));
  assert.equal(hooks.conditionMatches({ "后轮转向": "选装" }, conditions.rear_wheel_steering), false);
  assert.equal(hooks.conditionMatches({ "四轮驱动": "●" }, conditions.rear_wheel_steering), false);
});

test("numeric SKU columns and field filters use inclusive bounds and preserve old equality", () => {
  const { hooks, elements } = loadAppForTest();
  hooks.initializeRows([
    Object.assign(row("懂车帝", 2026, "矮"), { "样本值(mm)": "1495mm" }),
    Object.assign(row("懂车帝", 2026, "中"), { "样本值(mm)": "1500" }),
    Object.assign(row("懂车帝", 2026, "高"), { "样本值(mm)": "1505" }),
    Object.assign(row("懂车帝", 2026, "空"), { "样本值(mm)": "-" }),
  ]);
  hooks.state.saleScope = "all";
  hooks.state.visibleColumns = new Set(["车型名称", "样本值(mm)"]);
  hooks.renderTableHead();
  const inputs = descendants(elements.get("tableHead")).filter(node => node.tagName === "INPUT");
  const numeric = inputs.filter(node => node.dataset.column === "样本值(mm)");
  assert.deepEqual(numeric.map(node => node.dataset.columnBound), ["min", "max"]);
  assert.equal(inputs.filter(node => node.dataset.column === "车型名称").length, 1);
  const names = () => Array.from(hooks.getFilteredRows(), x => x["车型名称"]).sort();
  const selectedField = elements.get("fieldSelect");
  selectedField.value = numeric[0].dataset.column;
  selectedField.dispatch("change");
  numeric[0].value = "1495";
  elements.get("tableHead").dispatch("input", { target: numeric[0] });
  numeric[1].value = "1500";
  elements.get("tableHead").dispatch("input", { target: numeric[1] });
  assert.equal(elements.get("fieldMin").value, "1495");
  assert.equal(elements.get("fieldMax").value, "1500");
  assert.deepEqual(names(), ["中", "矮"]);
  const field = elements.get("fieldSelect");
  field.value = "样本值(mm)";
  field.dispatch("change");
  assert.ok(!elements.get("fieldMin").hidden && !elements.get("fieldMax").hidden);
  elements.get("fieldMin").value = "";
  elements.get("fieldMax").value = "1495";
  elements.get("applyFieldFilter").dispatch("click");
  assert.deepEqual(names(), ["矮"]);
  hooks.state.columnFilters["样本值(mm)"] = { operator: "equals", value: "1500" };
  assert.deepEqual(names(), ["中"]);
});

test("real range aliases retain their cycle and card control reflects inherited price", () => {
  const { hooks, elements } = loadAppForTest();
  hooks.state.config = JSON.parse(fs.readFileSync(path.join(__dirname, "../config/filter_conditions.json"), "utf8"));
  const raw = [
    Object.assign(row("懂车帝", 2026, "元境智行版"), { "车系": "极狐 阿尔法T5", "能源类型": "增程式",
      "纯电续航(km)": "CLTC:215 / WLTC:163", "WLTC纯电续航里程(km)": "163",
      "纯电续航(CLTC)": "215", "纯电续航里程(km)": "163" }),
    Object.assign(row("易车", 2026, "230 Pro"), { "车系": "风云T9L", "能源类型": "插电式混合动力",
      "纯电续航(km)": "CLTC:230 / WLTC:170", "CLTC纯电续航(km)": "230",
      "WLTC纯电续航(km)": "170", "WLTC纯电续航里程(km)": "170" }),
    Object.assign(row("易车", 2026, "200 四驱"), { "车系": "风云T9L", "能源类型": "插电式混合动力",
      "纯电续航(km)": "CLTC:200 / WLTC:140", "CLTC纯电续航(km)": "200",
      "WLTC纯电续航(km)": "140", "WLTC纯电续航里程(km)": "140" }),
    Object.assign(row("懂车帝", 2026, "保留工况差异"), { "车系": "测试工况", "能源类型": "增程式",
      "纯电续航(km)": "CLTC:170 / WLTC:163|163", "WLTC纯电续航里程(km)": "170" }),
  ];
  const expected = ["CLTC:215 · WLTC:163", "CLTC:230 · WLTC:170", "CLTC:200 · WLTC:140", "CLTC:170 · WLTC:163/170"];
  hooks.initializeRows(raw);
  assert.deepEqual(Array.from(hooks.state.rows, (item) => item["纯电续航(km)"]), expected);
  const groups = hooks.groupRowsBySeries(hooks.state.rows);
  const cards = hooks.renderCards(groups);
  const t9 = groups.findIndex((group) => group.name === "风云T9L");
  assert.match(cards[t9].meta, /CLTC:230\/200 · WLTC:170\/140/);
  assert.equal(elements.get("cardSortSelect").value, "官方指导价:asc");
  assert.equal(hooks.state.cardSort, null);
  hooks.state.sortField = "车系";
  hooks.renderCards(groups);
  assert.equal(elements.get("cardSortSelect").value, "default");
  hooks.state.cardSort = { field: "纯电续航(km)", dir: "desc" };
  hooks.renderCards(groups);
  assert.equal(elements.get("cardSortSelect").value, "纯电续航(km):desc");
});

test("card sort by price orders series groups", () => {
  const { hooks } = loadAppForTest();
  hooks.initializeRows([
    Object.assign(row("汽车之家+懂车帝", 2025, "甲系列 2025款"), { "车系": "甲系列", "官方指导价": "20.5", "百公里加速(s)": "5.2", "纯电续航(km)": "600" }),
    Object.assign(row("汽车之家", 2025, "乙系列 2025款"), { "车系": "乙系列", "官方指导价": "12.8", "百公里加速(s)": "6.9", "纯电续航(km)": "400" }),
    Object.assign(row("懂车帝", 2025, "丙系列 2025款"), { "车系": "丙系列", "官方指导价": "30.0", "百公里加速(s)": "3.9", "纯电续航(km)": "700" }),
  ]);
  let groups = hooks.groupRowsBySeries(hooks.getFilteredRows());
  hooks.state.cardSort = { field: "官方指导价", dir: "asc" };
  groups = hooks.sortSeriesGroups(groups);
  assert.equal(groups[0].name.includes("乙"), true);
  assert.equal(groups[2].name.includes("丙"), true);
  hooks.state.cardSort = { field: "百公里加速(s)", dir: "asc" };
  groups = hooks.sortSeriesGroups(groups);
  assert.equal(groups[0].name.includes("丙"), true);
  hooks.state.cardSort = null;
  groups = hooks.groupRowsBySeries(hooks.getFilteredRows());
  assert.equal(groups[0].rows[0]["数据来源"].includes("汽车之家"), true);
});

test("official price is the default for models and series, with unknowns last", () => {
  const { hooks } = loadAppForTest();
  hooks.initializeRows([
    Object.assign(row("汽车之家+易车+懂车帝", 2026, "多源贵车"), { "车系": "贵车系", "官方指导价": "20.00万" }),
    Object.assign(row("懂车帝", 2026, "单源便宜车"), { "车系": "低价车系", "官方指导价": "90000元" }),
    Object.assign(row("懂车帝", 2026, "另一车款"), { "车系": "低价车系", "官方指导价": "15万" }),
    Object.assign(row("懂车帝", 2026, "未定价车"), { "车系": "未定价车系", "官方指导价": "0万" })
  ]);
  const names = () => Array.from(hooks.getFilteredRows(), (item) => item["车型名称"]);
  const groups = () => hooks.groupRowsBySeries(hooks.getFilteredRows());
  assert.deepEqual(names(), ["单源便宜车", "另一车款", "多源贵车", "未定价车"]);
  assert.deepEqual(Array.from(groups(), (group) => group.name), ["低价车系", "贵车系", "未定价车系"]);
  assert.equal(groups()[0].representative["车型名称"], "单源便宜车");

  hooks.state.sortDir = "desc";
  assert.deepEqual(names(), ["多源贵车", "另一车款", "单源便宜车", "未定价车"]);
  const manual = hooks.snapshotFilters();
  hooks.state.cardSort = { field: "数据来源", dir: "desc" };
  hooks.restoreDefaultFilters();
  assert.equal(hooks.state.cardSort, null);
  assert.deepEqual(names(), ["单源便宜车", "另一车款", "多源贵车", "未定价车"]);
  hooks.applySnapshot(manual);
  assert.deepEqual(names(), ["多源贵车", "另一车款", "单源便宜车", "未定价车"]);
  hooks.state.sortField = "";
  hooks.state.sortLevels = [];
  assert.equal(names()[0], "多源贵车", "clearing a sort retains the relevance order");
});

test("per-source range aliases merge only for electrified rows and never treat 999 as a range", () => {
  const { hooks } = loadAppForTest();
  hooks.state.config = Object.assign({}, hooks.state.config, {
    columnAliases: {
      "纯电续航(km)": ["纯电续航里程(km)", "WLTC纯电续航里程(km)", "CLTC纯电续航(km)"]
    }
  });
  hooks.initializeRows([
    Object.assign(row("懂车帝", 2026, "纯电别名"), { "能源类型": "纯电动", "纯电续航(km)": "0", "纯电续航里程(km)": "560" }),
    Object.assign(row("懂车帝", 2026, "插混别名"), { "能源类型": "插电式混合动力", "纯电续航(km)": "0", "纯电续航里程(km)": "155" }),
    Object.assign(row("懂车帝", 2026, "燃油哨兵"), { "能源类型": "汽油", "纯电续航(km)": "0", "WLTC纯电续航里程(km)": "999" }),
    Object.assign(row("懂车帝", 2026, "燃油伪里程"), { "能源类型": "汽油", "纯电续航(km)": "0", "纯电续航里程(km)": "400" })
  ]);
  const byName = {};
  hooks.state.rows.forEach((item) => { byName[item["车型名称"]] = item; });
  assert.equal(Number(byName["纯电别名"]["纯电续航(km)"]), 560);
  assert.equal(Number(byName["插混别名"]["纯电续航(km)"]), 155);
  assert.ok(!(Number(byName["燃油哨兵"]["纯电续航(km)"]) >= 150), "999 sentinel stays unknown");
  assert.notEqual(String(byName["燃油哨兵"]["纯电续航(km)"] || ""), "999");
  assert.ok(!(Number(byName["燃油伪里程"]["纯电续航(km)"]) >= 150), "fuel-only rows never gain electric range from aliases");
});

function row(source, year, name) {
  return {
    "数据来源": source,
    "品牌": "测试品牌",
    "车系": "测试车系",
    "车型名称": name,
    // Explicit synthetic evidence: generic filter fixtures are known in-sale and priced.
    "易车上市状态": "approved",
    "官方指导价": "20万",
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
  assert.equal(verified["交叉核验"], "多源记录");
  assert.deepEqual(
    verified["核验来源"].split(" + ").sort(),
    ["懂车帝", "汽车之家", "易车"].sort()
  );

  const unknown = hooks.state.rows.find((item) => item["车型名称"] === "未知来源合并款");
  assert.equal(unknown["交叉核验"], "多源记录");
  assert.deepEqual(
    unknown["核验来源"].split(" + ").sort(),
    ["合作数据源", "懂车帝", "易车"].sort()
  );

  const splitSource = hooks.state.rows.find((item) => item["车型名称"] === "分行双源款");
  assert.equal(splitSource["交叉核验"], "多源记录");
  assert.deepEqual(
    splitSource["核验来源"].split(" + ").sort(),
    ["懂车帝", "汽车之家", "易车"].sort()
  );

  assert.equal(elements.get("visibleCount").textContent, "4", "unknown sale status is excluded only from the default scope");
  hooks.state.saleScope = "all";
  assert.equal(hooks.getFilteredRows().length, 5, "all recorded rows remain available");
  assert.equal(elements.get("totalCount").textContent, "5");
  assert.equal(elements.get("verifiedCount").textContent, "0");
  assert.equal(elements.get("dongchediCount").textContent, "4");
  assert.equal(elements.get("autohomeCount").textContent, "2");
  assert.equal(elements.get("yicheCount").textContent, "4");

  hooks.state.search = "不存在的车型";
  hooks.renderResultsOnly();
  assert.equal(elements.get("visibleCount").textContent, "0");
  assert.equal(elements.get("totalCount").textContent, "5");
  assert.equal(elements.get("verifiedCount").textContent, "0");
  assert.equal(elements.get("dongchediCount").textContent, "4");
  assert.equal(elements.get("autohomeCount").textContent, "2");
  assert.equal(elements.get("yicheCount").textContent, "4");
});

test("Pages groups only rows carrying the same audited cross-source component id", () => {
  const { hooks } = loadAppForTest();
  const autohome = Object.assign(row("仅汽车之家", 2026, "皓影 2026款 e:HEV 四驱尊耀版"), {
    "车系": "皓影",
    "车款ID": "77904",
    "跨源归并ID": "visible-f-v1:test"
  });
  const yiche = Object.assign(row("仅易车", 2026, "26款 e:HEV 2.0L 四驱锐·尊耀版"), {
    "车系": "皓影",
    "车款ID": "189503",
    "跨源归并ID": "visible-f-v1:test"
  });
  const unrelated = Object.assign(row("仅懂车帝", 2026, "锐·混动 2.0L 四驱至尊版"), {
    "车系": "皓影"
  });

  hooks.initializeRows([autohome, yiche, unrelated]);

  assert.equal(hooks.state.rows.length, 2);
  const merged = hooks.state.rows.find((item) => item["交叉核验"] === "多源记录");
  assert.deepEqual(Array.from(hooks.atomicSources(merged["数据来源"])).sort(), ["易车", "汽车之家"].sort());
  assert.equal(merged["跨源归并ID"], "visible-f-v1:test");
  assert.equal(hooks.state.rows.find((item) => item["交叉核验"] === "单源数据")["车型名称"], unrelated["车型名称"]);
});

test("display merge joins an annotated row with its unannotated same-key twin", () => {
  // 线上 182656 的实况：同一个 车款ID + 同一个车型名称，易车把它同时挂在两个车系名下，
  // 并且只有其中一行带跨源归并ID。旧写法先按"带不带注解"分桶，主键规则只作用在不带注解的桶里，
  // 于是这两张卡永不并，展示层留下同主键的两行（线上验收不变式正是断这条）。
  const { hooks } = loadAppForTest();
  const annotated = Object.assign(row("仅易车", 2025, "25款 改款 GLE 400 e 4MATIC"), {
    "车系": "奔驰GLE 插电混动",
    "车款ID": "182656",
    "跨源归并ID": "visible-f-v3:test",
    "OTA升级": "●"
  });
  const plain = Object.assign(row("仅易车", 2025, "25款 改款 GLE 400 e 4MATIC"), {
    "车系": "奔驰GLE 插电混动(进口)",
    "车款ID": "182656",
    "OTA升级": "●|车机OTA"
  });

  hooks.initializeRows([annotated, plain]);

  assert.equal(hooks.state.rows.length, 1,
    "同主键两行必须并成一条：一行带归并注解、一行不带，不是把它们分开的理由");
  assert.equal(hooks.state.rows[0]["车款ID"], "182656");
});

test("a uniquely matching on-sale observation can join an existing verified SKU", () => {
  const { hooks } = loadAppForTest();
  const shared = { "能源类型": "增程式", "座位数(个)": "6", "官方指导价": "21.98万" };
  const base = {
    "车款ID": "77357", "车款ID_汽车之家": "77357", "城市领航辅助": "●", "哨兵模式": "●"
  };
  const older = Object.assign(row("汽车之家+懂车帝", 2026, "测试车系 2026款 增程400尊享版 六座"), shared, base);
  const duplicate = Object.assign({}, older, { "数据来源": "仅汽车之家" });
  const fresh = Object.assign(row("仅懂车帝", 2026, "增程400尊享版 六座"), shared, {
    "懂车帝车型ID": "257872", "上市状态_懂车帝": "在售"
  });
  hooks.initializeRows([older, duplicate, fresh]);
  assert.equal(hooks.state.rows.length, 1);
  const [merged] = hooks.state.rows;
  assert.equal(merged["车款ID"], "77357");
  assert.equal(merged["懂车帝车型ID"], "257872");
  assert.equal(merged["上市状态_懂车帝"], "在售");
  assert.equal(merged["哨兵模式"], "●");
});

test("on-sale evidence stays separate with conflicting, missing, or ambiguous SKU identity", () => {
  const { hooks } = loadAppForTest();
  const shared = { "能源类型": "增程式", "座位数(个)": "6", "官方指导价": "21.98万" };
  const base = Object.assign(row("汽车之家+懂车帝", 2026, "测试车系 2026款 增程400尊享版 六座"), shared, {
    "车款ID": "77357", "车款ID_汽车之家": "77357"
  });
  const duplicate = Object.assign({}, base, { "数据来源": "仅汽车之家" });
  const fresh = Object.assign(row("仅懂车帝", 2026, "增程400尊享版 六座"), shared, {
    "懂车帝车型ID": "257872", "上市状态_懂车帝": "在售"
  });
  for (const change of [
    { "座位数(个)": "7" }, { "座位数(个)": "-" }, { "官方指导价": "22.98万" }, { "年款": "2025" },
  ]) {
    hooks.initializeRows([base, duplicate, Object.assign({}, fresh, change)]);
    assert.equal(hooks.state.rows.length, 2, JSON.stringify(change));
  }
  const rival = Object.assign({}, base, { "车款ID": "77358", "车款ID_汽车之家": "77358" });
  hooks.initializeRows([base, duplicate, rival, Object.assign({}, rival, { "数据来源": "仅汽车之家" }), fresh]);
  assert.equal(hooks.state.rows.length, 3);
  hooks.initializeRows([base, duplicate, fresh, Object.assign({}, fresh, { "懂车帝车型ID": "257873" })]);
  assert.equal(hooks.state.rows.find(item => item["车款ID"] === "77357")["上市状态_懂车帝"], undefined);
});

test("verified Yuzhong 08 Max Plus pair excludes the distinct Max in its published group", () => {
  const { hooks } = loadAppForTest();
  hooks.state.config = JSON.parse(fs.readFileSync(path.join(__dirname, "../config/filter_conditions.json"), "utf8"));
  const common = { ...row("仅懂车帝", 2026, "Max Plus"), "品牌": "大众", "车系": "与众08",
    "跨源归并ID": "published-mixed", "官方指导价": "26.99万", "能源类型": "纯电动",
    "纯电续航(km)": "700", "座位数(个)": "5", "轴距(mm)": "3030", "电动机总功率(kW)": "370" };
  const dcd = {...common, "懂车帝车型ID": "262910", "上市状态_懂车帝": "在售"};
  const max = {...common, "车型名称": "Max", "官方指导价": "28.99万", "懂车帝车型ID": "253768"};
  const ah = {...common, "数据来源": "仅汽车之家", "车款ID_汽车之家": "79167"};
  for (const rows of [[dcd, max, ah], [max, ah, dcd], [ah, dcd, max]]) {
    hooks.initializeRows(rows);
    assert.equal(hooks.state.rows.length, 2);
    const plus = hooks.state.rows.find(r => r["车款ID_汽车之家"] === "79167");
    assert.equal(plus["懂车帝车型ID"], "262910");
    assert.equal(plus["交叉核验"], "双源核验");
    assert.ok(hooks.state.rows.some(r => r["懂车帝车型ID"] === "253768" && r["车型名称"] === "Max"));
  }
  hooks.initializeRows([ah, {...dcd, "官方指导价": "27.99万"}, max]);
  assert.equal(hooks.state.rows.length, 3);
});

test("verified cross-source EV pair joins one trim and keeps separate powertrains", () => {
  const { hooks } = loadAppForTest();
  const metadata = { "能源类型": "纯电动", "官方指导价": "21.58万", "座位数(个)": "5",
    "轴距(mm)": "2920", "电动机总功率(kW)": "170", "纯电续航(km)": "CLTC:705" };
  hooks.state.config.verifiedEvSkuPairs = [{
    brand: "测试品牌", autohomeId: "75198", dongchediId: "252747", autohomeSeries: "汉",
    dongchediSeries: "汉EV", modelYear: "2025", msrp: "21.58", seats: 5, rangeKm: 705, wheelbaseMm: 2920, motorKw: 170
  }];
  const left = Object.assign(row("仅汽车之家", 2025, "2025款 EV 705KM激光雷达旗舰型"), metadata, {
    "车系": "汉", "车款ID_汽车之家": "75198", "车款ID": "75198", "哨兵模式": "●"
  });
  const right = Object.assign(row("仅懂车帝", 2025, "长续航智驾版705KM激光雷达旗舰型"), metadata, {
    "车系": "汉EV", "懂车帝车型ID": "252747", "上市状态_懂车帝": "在售"
  });
  const hybrid = Object.assign({}, left, { "车款ID_汽车之家": "75192", "车款ID": "75192",
    "能源类型": "插电式混合动力", "车型名称": "2025款 DM-i 245KM旗舰型" });
  hooks.initializeRows([left, right, hybrid]);
  assert.equal(hooks.state.rows.length, 2);
  const joined = hooks.state.rows.find(row => row["车系"] === "汉EV");
  assert.equal(joined["车款ID_汽车之家"], "75198");
  assert.equal(joined["懂车帝车型ID"], "252747");
  assert.equal(joined["哨兵模式"], "●");
  assert.equal(hooks.state.rows.find(row => row["车系"] === "汉")["能源类型"], "插电式混合动力");
  const leftBattery = Object.assign({}, left, { "电池能量(kWh)": "130.15" });
  const rightBattery = Object.assign({}, right, { "电池容量(kWh)": "130.1" });
  hooks.initializeRows([leftBattery, rightBattery]);
  assert.equal(hooks.state.rows.length, 2);
  hooks.state.config.verifiedEvSkuPairs[0].batteryKwh = [130.15, 130.1];
  hooks.initializeRows([leftBattery, rightBattery]);
  assert.equal(hooks.state.rows.length, 1);
  assert.equal(hooks.state.rows[0]["电池能量(kWh)"], "130.15");
  assert.equal(hooks.state.rows[0]["电池容量(kWh)"], "130.1");
  hooks.initializeRows([leftBattery, Object.assign({}, rightBattery, { "电池容量(kWh)": "130.16" })]);
  assert.equal(hooks.state.rows.length, 2);
  for (const change of [{ "电动机总功率(kW)": "240" }, { "纯电续航(km)": "CLTC:635" },
    { "轴距(mm)": "2900" }, { "能源类型": "插电式混合动力" }]) {
    hooks.initializeRows([left, Object.assign({}, right, change)]);
    assert.equal(hooks.state.rows.length, 2, JSON.stringify(change));
  }
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
// 这条原来是**死通道**：`skip: !CARS_LIVE_DATA` 而 CI 从不设这个变量 ⇒ 它一次也没跑过；
// 而且断言写死在某一天的快照上（2992/137/全懂车帝），现网早已是 1.4 万+ 行、三源 ⇒
// 就算把 env 设上它也只会红在"数字与今天不同"，而不是红在"数据不符合预期"。
// 现在断**不变式**：计数自洽、年款在范围内、同一车款ID 不许留两条同归一名的行、三源至少各有人看见。
test("live Pages data satisfies the acceptance invariants (not a frozen snapshot)", { skip: !liveDataPath }, () => {
  const { elements, hooks } = loadAppForTest();
  hooks.state.config = JSON.parse(fs.readFileSync(path.join(__dirname, '../config/filter_conditions.json'), 'utf8'));
  const raw = JSON.parse(fs.readFileSync(liveDataPath, "utf8"));
  const rows = Array.isArray(raw) ? raw : raw.rows;
  assert.ok(Array.isArray(rows) && rows.length > 0, "读到的不是非空行数组 ⇒ 取数面坏了，不许出结论");

  hooks.initializeRows(rows);
  hooks.renderResultsOnly();

  const visible = Number(String(elements.get("visibleCount").textContent).replace(/\D/g, ""));
  const total = Number(String(elements.get("totalCount").textContent).replace(/\D/g, ""));
  // 展示层的契约不是"总数==输入行数"：`initializeRows` 会先 `mergeVerifiedRows`（跨源同一条目的合并）
  // 再按 `keepDisplayYear` 收窄年份（近五年口径）。我第一版就是断在"总数==输入行数"上，
  // 红了之后去读 `docs/app.js:2540-2545` 才发现是**我的判据自造契约**，不是应用丢行。
  assert.ok(total > 0 && visible > 0 && visible <= total,
    `可见 ${visible} / 总 ${total} 不自洽`);
  assert.equal(total, hooks.state.rows.length,
    "展示层自报的总数与它自己手里的行数不一致 ⇒ 标签与口径不同源");
  assert.ok(hooks.state.rows.length <= rows.length,
    `展示层比输入还多（${hooks.state.rows.length} > ${rows.length}）⇒ 有凭空造的行`);
  const merged = rows.length - hooks.state.rows.length;
  assert.ok(merged < rows.length,
    `展示后剩 0 行（输入 ${rows.length} 行全被吞）⇒ 这才是丢光，不是收窄`);
  console.log(`面：输入 ${rows.length} 行 → 展示 ${hooks.state.rows.length} 行（合并/年份收窄共 -${merged}）`);

  const years = rows.map((r) => Number(r["年款"])).filter((n) => Number.isFinite(n));
  assert.ok(years.length > 0, "一行年款都解析不出来 ⇒ 年轴无读数");
  // 不断"最小年款等于某一年"：面上允许停售/更早的车（爬取范围与展示切换是两件事），
  // 写死一年就会在爬取范围一变时假红。这里只要求"年份都是四位数"，并让它把范围报出来。
  assert.ok(years.every((y) => y >= 1900 && y <= 2100),
    `年款里出现不可解析的值（min=${Math.min(...years)} max=${Math.max(...years)}）`);

  const norm = (s) => String(s || "").replace(/\s+/g, "").toLowerCase();
  // 通用 ID 不带来源命名空间。同 ID 同名的行只有在平台身份
  // 阻止归并时才可保留，避免把不同来源的数字 ID 当成同一个 SKU。
  const skuBuckets = new Map();
  for (const r of hooks.state.rows) {
    const id = String(r["车款ID"] || "").trim();
    if (!id || id === "-") continue;
    const key = id + "\u0000" + norm(r["车型名称"]);
    const priorRows = skuBuckets.get(key) || [];
    for (const prior of priorRows) {
      assert.ok(hooks.skuProviderConflict(prior, r, false),
        `展示层仍有可归并的同 ID 同名车款（${id}）`);
    }
    priorRows.push(r);
    skuBuckets.set(key, priorRows);
  }
  const perSource = { 懂车帝: 0, 汽车之家: 0, 易车: 0 };
  for (const r of hooks.state.rows) {
    const lab = String(r["数据来源"] || "");
    for (const s of Object.keys(perSource)) if (lab.includes(s)) perSource[s] += 1;
  }
  for (const [s, n] of Object.entries(perSource)) {
    assert.ok(n > 0, `面上完全没有来源 ${s} ⇒ 三源退化成一/两源，这是覆盖缺陷不是显示差异`);
  }
  const dch = Number(String(elements.get("dongchediCount").textContent).replace(/\D/g, ""));
  assert.ok(dch === perSource["懂车帝"],
    `展示层懂车帝计数 ${dch} 与面上 ${perSource["懂车帝"]} 不符 ⇒ 标签与口径不同源`);
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
  // 默认收起；点击展开后显示每车型差异行
  assert.equal(toggle.getAttribute("aria-expanded"), "false");

  elements.get("cardList").dispatch("click", { target: toggle });
  firstCard = elements.get("cardList").children[0];
  toggle = firstCard.children[0];
  assert.equal(toggle.getAttribute("aria-expanded"), "true");
  assert.equal(firstCard.children[2].children.length, 2);
  assert.deepEqual(Array.from(firstCard.children[2].children, (item) => item.children[0].textContent), ["2026款 低配", "2026款 高配"]);

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
  // 口径变更（负责人 10-16）：切到"数据表/高级模式"必须**保留筛选栏与筛选条件**，
  // 旧语义"整个 #filterCenter 隐藏"作废；改为断言筛选栏仍在、车系卡片专属块让位。
  elements.get("tableMode").dispatch("click");
  assert.equal(elements.get("filterCenter").hidden, false);
  assert.equal(elements.get("tableRegion").hidden, false);
  assert.equal(elements.get("cardList").hidden, true);
  assert.equal(elements.get("cardToolbar").hidden, true);
  // 数据表模式的位置契约：workspace 带 mode-table（CSS 把 table 放回主栏），hero 让位。
  assert.ok(String(elements.get("workspace").className).split(/\s+/).includes("mode-table"));
  assert.equal(elements.get("centerHero").hidden, true);

  const html = fs.readFileSync(path.join(__dirname, "..", "docs", "index.html"), "utf8");
  const css = fs.readFileSync(path.join(__dirname, "..", "docs", "styles.css"), "utf8");
  // shim 的 getElementById 会自动造元素，光靠 JS 断言钉不住 HTML 接线；这里直接断源码。
  assert.match(html, /<main class="workspace" id="workspace">/);
  assert.match(html, /class="center-hero" id="centerHero"/);
  assert.doesNotMatch(html, /table-region advanced-hidden/);
  assert.doesNotMatch(css, /\.advanced-hidden\s*,\s*\.center-hidden/);
  assert.ok(css.includes(".workspace.mode-table .table-region { grid-column: 1; }"),
    "数据表模式必须把表格显式放回主栏（否则会被自动排进 310px 侧栏列）");
  assert.ok(css.includes(".workspace.mode-table .side-panel { grid-column: 2; }"),
    "数据表模式侧栏必须留在右栏");
});

test("Side panels collapse independently and the filter bar survives the mode switch", () => {
  const { elements, hooks } = loadAppForTest();
  hooks.state.config.conditions = [{ id: "remote", label: "远程启动", type: "feature", fields: ["远程启动"], keywords: ["支持"] }];
  hooks.initializeRows([
    Object.assign(row("汽车之家+懂车帝", 2026, "甲"), { "品牌": "A", "车系": "S1", "远程启动": "支持" }),
    Object.assign(row("仅懂车帝", 2026, "乙"), { "品牌": "A", "车系": "S2", "远程启动": "-" })
  ]);
  hooks.renderResultsOnly();

  // 右侧两栏各自可折叠：默认展开 → 收起 → 再展开；两栏互不影响
  assert.equal(elements.get("fieldFilterBody").hidden, false);
  elements.get("toggleFieldFilterPanel").dispatch("click");
  assert.equal(elements.get("fieldFilterBody").hidden, true);
  assert.equal(elements.get("toggleFieldFilterPanel").getAttribute("aria-expanded"), "false");
  elements.get("toggleFieldFilterPanel").dispatch("click");
  assert.equal(elements.get("fieldFilterBody").hidden, false);
  elements.get("toggleHistoryPanel").dispatch("click");
  assert.equal(elements.get("historyBody").hidden, true);
  assert.equal(elements.get("fieldFilterBody").hidden, false);

  // 切到数据表：已选条件与结果集都不许变
  hooks.state.featureFilters.remote = true;
  const before = hooks.getFilteredRows().map((item) => item["车型名称"]);
  elements.get("tableMode").dispatch("click");
  assert.deepEqual(hooks.getFilteredRows().map((item) => item["车型名称"]), before);
  assert.equal(elements.get("filterCenter").hidden, false);
  assert.equal(elements.get("cardList").hidden, true);
  elements.get("centerMode").dispatch("click");
  assert.equal(elements.get("cardList").hidden, false);
  assert.equal(String(elements.get("workspace").className).split(/\s+/).includes("mode-table"), false);
  assert.equal(elements.get("centerHero").hidden, false);
});

test("Sale scope is always visible, defaults to evidenced in-sale, and preserves all recorded scope", () => {
  const {elements, hooks} = loadAppForTest();
  hooks.initializeRows([
    Object.assign(row("汽车之家+易车", 2026, "已上市在售"), {"上市时间":"2025.09"}),
    Object.assign(row("易车", 2026, "未来上市"), {"上市时间":"2099.03"}),
    Object.assign(row("懂车帝", 2026, "状态未知"), {"易车上市状态":"", "上市时间":"2025.01"}),
    Object.assign(row("易车", 2026, "已停售"), {"易车上市状态":"停售", "上市时间":"2025.01"})
  ]);
  assert.equal(elements.get("saleScopeSection").hidden, false);
  assert.equal(hooks.state.saleScope, "onSale");
  assert.equal(hooks.getFilteredRows().map(r => r["车型名称"]).join(","), "已上市在售");
  elements.get("saleScopeAll").dispatch("click");
  assert.equal(hooks.getFilteredRows().length, 4);
  assert.equal(elements.get("saleScopeAll").className, "segment active");
  elements.get("saleScopeOnSale").dispatch("click");
  assert.equal(hooks.getFilteredRows().length, 1);
  hooks.initializeRows([row("易车", 2026, "唯一在售")]);
  assert.equal(elements.get("saleScopeSection").hidden, false, "constant approval must not hide the user control");
  assert.equal(hooks.state.saleScope, "onSale");
});


test("Pages enables the ten distinct core filters by default and after reset", () => {
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
    { id: "rain_sensor_wiper", label: "雨量感应式雨刷", type: "feature", fields: ["雨量感应式雨刷"], keywords: ["支持"] },
    { id: "auto_headlight", label: "自动头灯", type: "feature", fields: ["自动大灯"], keywords: ["支持"] }
  ];
  hooks.state.config.centerConditionGroups = [
    { id: "performance", label: "性能/续航", conditionIds: ["zero_to_hundred", "ev_range"] },
    { id: "smart", label: "核心配置", conditionIds: ["city_navigation", "remote_start", "remote_control", "bluetooth_key", "seat_memory", "mirror_memory"] },
    { id: "comfort", label: "舒适/便利", conditionIds: ["rain_sensor_wiper", "auto_headlight"] }
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
    "auto_headlight", "bluetooth_key", "city_navigation", "mirror_memory", "rain_sensor_wiper", "remote_control", "remote_start", "seat_memory"
  ].sort());
  assert.deepEqual(JSON.parse(JSON.stringify(hooks.state.rangeFilters)), { zero_to_hundred: { min: "", max: "" }, ev_range: { min: "", max: "" } });
  // Without hardcoded range defaults, both rows pass initially
  assert.deepEqual(JSON.parse(JSON.stringify(hooks.getFilteredRows().map((item) => item["车型名称"]))), ["默认通过", "默认不过"]);
  // Set range values manually to verify filtering still works
  hooks.state.rangeFilters.zero_to_hundred = { min: "", max: "7" };
  assert.deepEqual(JSON.parse(JSON.stringify(hooks.getFilteredRows().map((item) => item["车型名称"]))), ["默认通过"]);
  hooks.state.rangeFilters.zero_to_hundred = { min: "", max: "" };
  assert.equal(elements.get("selectedTags").children.map((tag) => tag.textContent).join("|"), "百公里加速|纯电续航|NOA城市领航|远程启动|手机远程控制|蓝牙/数字钥匙|座椅记忆|外后视镜记忆|雨量感应式雨刷|自动头灯");
  // All conditions are in centerConditionGroups, so sidebar conditionList fragment has no items
  assert.equal(elements.get("conditionList").children[0].children.length, 0);
  // Queries follow property nodes through the new category/section/property hierarchy.
  const centerItems = descendants(elements.get("centerConditionList")).filter(item => item.className === "center-condition-item");
  assert.equal(centerItems.length, 10);
  assert.equal(centerItems.filter((item) => item.children[0] && item.children[0].children[0] && item.children[0].children[0].checked).length, 10);

  hooks.state.rangeFilters = {};
  hooks.state.featureFilters = {};
  elements.get("resetFilters").dispatch("click");
  assert.deepEqual(JSON.parse(JSON.stringify(hooks.state.rangeFilters)), { zero_to_hundred: { min: "", max: "" }, ev_range: { min: "", max: "" } });
  assert.equal(Object.keys(hooks.state.featureFilters).length, 8);
  assert.equal(elements.get("conditionList").children[0].children.length, 0);
  const centerItemsAfterReset = descendants(elements.get("centerConditionList")).filter(item => item.className === "center-condition-item");
  assert.equal(centerItemsAfterReset.filter((item) => item.children[0] && item.children[0].children[0] && item.children[0].children[0].checked).length, 10);
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
    msrp: { min: "", max: "35" },
    zero_to_hundred: { min: "0", max: "7" },
    top_speed: { min: "180", max: "" },
    ev_range: { min: "150", max: "" },
    curb_weight: { min: "", max: "2000" }
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
    "零重力座椅": "第一排",
    "零重力座椅_1": "支持一键躺平及按摩",
    "零重力座椅_2": "○ 6000元",
    "不明字段_1": "前视",
    "不明字段_2": "后视",
    "camera_count_v4_1": "前视",
    "camera_count_v4_2": "后视",
    "camera_count_v4_3": "环视",
    "扬声器数量": "12"
  }];
  assert.equal(hooks.shouldHideColumn("冬季包_1", rows), true);
  assert.equal(hooks.shouldHideColumn("冬季包", rows), true);
  assert.equal(hooks.shouldHideColumn("安全轮胎_1", rows), false);
  assert.equal(hooks.shouldHideColumn("零重力座椅", rows), false);
  assert.equal(hooks.shouldHideColumn("零重力座椅_1", rows), true);
  assert.equal(hooks.shouldHideColumn("不明字段_1", rows), false);
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
  const css = fs.readFileSync(path.join(__dirname, "..", "docs", "styles.css"), "utf8").replace(/\r\n?/g, "\n");
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
    "基本信息", "动力参数", "辅助/操控", "外部/防盗", "座椅", "灯光", "玻璃/后视镜", "智能硬件", "底盘与操控", "内饰与舒适"
  ]);
  const assignments = [];
  config.filterTaxonomy.forEach((category) => {
    assert.ok(category.id);
    assert.ok(category.label);
    assert.ok(Array.isArray(category.sections) && category.sections.length > 0);
    category.sections.forEach((section) => {
      assert.ok(section.id);
      assert.ok(section.label);
      assert.ok(Array.isArray(section.conditionIds));
      if (section.conditionIds.length) { assert.ok(section.desktopGroupId); }
      else { assert.ok((section.columns || section.columnPatterns || []).length > 0); }
      section.conditionIds.forEach((id) => assignments.push(id));
    });
  });
  const conditionIds = config.conditions.map((condition) => condition.id).sort();
  assert.deepEqual(assignments.slice().sort(), conditionIds);
  assert.equal(new Set(assignments).size, assignments.length, "every condition belongs to exactly one minor section");
  const pagesOnly = ["rain_sensor_wiper", "auto_headlight"];
  assert.deepEqual(config.conditions.filter((condition) => pagesOnly.includes(condition.id)).map((condition) => condition.type), [
    "pagesFeature", "pagesFeature"
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

test("Pages restore-default semantics are schema-driven for range and energy controls", () => {
  const { elements, hooks } = loadAppForTest();
  const config = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "docs", "filter_conditions.json"), "utf8"));
  hooks.state.config = config;
  hooks.state.rangeFilters = { ev_range: { min: "999", max: "1000" } };
  hooks.state.featureFilters = {};
  hooks.state.search = "temporary";
  assert.equal(typeof hooks.restoreDefaultFilters, "function");
  hooks.restoreDefaultFilters();
  assert.deepEqual(JSON.parse(JSON.stringify(hooks.state.rangeFilters)), {
    msrp: { min: "", max: "35" },
    zero_to_hundred: { min: "0", max: "7" },
    ev_range: { min: "150", max: "" },
    top_speed: { min: "180", max: "" },
    vehicle_length: { min: "", max: "5000" },
    vehicle_height: { min: "", max: "1500" },
    curb_weight: { min: "", max: "2000" }
  });
  assert.equal(hooks.state.featureFilters.energy_type.join(","), "bev");
  assert.equal(hooks.state.search, "");
  assert.equal(elements.get("globalSearch").value, "");
  assert.equal(Object.keys(hooks.state.featureFilters).length,
    config.conditions.filter((condition) => condition.type === "pagesChoice" ||
      ["feature", "pagesFeature", "pagesEquipment"].includes(condition.type) && condition.defaultEnabled !== false).length);
});

test("Pages first load renders and applies acceleration, speed, and EV range defaults", () => {
  const { elements, hooks } = loadAppForTest();
  const config = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "docs", "filter_conditions.json"), "utf8"));
  hooks.state.config = config;
  function model(name, acceleration, speed, range, weight = 1900) {
    const result = Object.assign(row("仅懂车帝", 2026, name), {
      "百公里加速(s)": String(acceleration),
      "最高车速(km/h)": String(speed),
      "纯电续航(km)": String(range),
      "整备质量(kg)": String(weight),
      "能源类型": "纯电动",
      "长x宽x高(mm)": "4900x1900x1450"
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
  assert.ok(tags.includes("百公里加速 ≤7"));
  assert.ok(tags.includes("最高车速 ≥180"));
  assert.ok(tags.includes("纯电续航 ≥150"));
  const values = {};
  descendants(elements.get("centerConditionList")).forEach((input) => {
    if (input.dataset && input.dataset.side) values[input.dataset.conditionId + ":" + input.dataset.side] = input.value;
  });
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

test("series card: common attrs in one meta line, differing attrs per model row", () => {
  const { hooks } = loadAppForTest();
  const layoutGroups = [
    {
      key: "S1",
      name: "系列一",
      representative: { "品牌": "甲", "级别": "中型SUV", "车型名称": "代表车" },
      rows: [
        { "车型名称": "A 1", "年款": 2025, "品牌": "甲", "级别": "中型SUV", "能源类型": "纯电", "官方指导价": "20万", "百公里加速(s)": "5.5", "驱动方式": "四驱", "纯电续航(km)": "600" },
        { "车型名称": "A 2 2026款", "年款": 2026, "品牌": "甲", "级别": "中型SUV", "能源类型": "增程", "官方指导价": "30万", "百公里加速(s)": "6.0", "驱动方式": "后驱", "纯电续航(km)": "200" }
      ]
    }
  ];
  hooks.state.expandedSeries = new Set(["S1"]);
  const snapshots = hooks.renderCards(layoutGroups);
  assert.ok(snapshots.length === 1, "一个车系一张卡片");
  assert.ok(snapshots[0].meta.indexOf("品牌: 甲") !== -1, "卡片 meta 含共性属性品牌（单值一行）");
  assert.ok(snapshots[0].meta.indexOf("级别: 中型SUV") !== -1, "卡片 meta 含共性属性级别（单值一行）");
  assert.ok(snapshots[0].meta.indexOf("能源类型: 纯电动|增程式") !== -1, "能源类型有差异 -> 汇总枚举（同义词已归一）");
  assert.ok(snapshots[0].meta.indexOf("官方指导价: 20-30万") !== -1, "价格有差异 -> 范围");
  assert.ok(snapshots[0].meta.indexOf("百公里加速(s): 5.5-6") !== -1, "加速有差异 -> 范围");
  assert.ok(snapshots[0].meta.indexOf("纯电续航(km): 200-600") !== -1, "续航有差异 -> 范围");
  assert.ok(snapshots[0].rows.length === 2, "展开区每个车型一行");

  // 全一致时按共性显示单值（动态判定）
  const singleGroups = [
    {
      key: "S2",
      name: "系列二",
      representative: { "品牌": "乙", "级别": "中大型车", "车型名称": "代表车" },
      rows: [
        { "车型名称": "B 1", "品牌": "乙", "级别": "中大型车", "能源类型": "纯电", "官方指导价": "25万", "百公里加速(s)": "6.0", "纯电续航(km)": "500" },
        { "车型名称": "B 2", "品牌": "乙", "级别": "中大型车", "能源类型": "纯电", "官方指导价": "25万", "百公里加速(s)": "6.0", "纯电续航(km)": "500" }
      ]
    }
  ];
  const singleSnap = hooks.renderCards(singleGroups);
  assert.ok(singleSnap[0].meta.indexOf("能源类型: 纯电") !== -1 && singleSnap[0].meta.indexOf("纯电/") === -1, "能源全一致 -> 单值");
  assert.ok(singleSnap[0].meta.indexOf("官方指导价: 25万") !== -1 && singleSnap[0].meta.indexOf("-") === -1 || singleSnap[0].meta.indexOf("25万") !== -1, "价格全一致 -> 单值");
  assert.ok(snapshots[0].rows[0].indexOf("2025款 A 1") !== -1, "年款统一前置（2025款）");
  assert.ok(snapshots[0].rows[1].indexOf("A 2 2026款") !== -1, "年款作为型号结尾（2026款）");
  assert.ok(snapshots[0].rows[0].indexOf("年款:") === -1, "年款不再作为独立属性 chip");
  assert.ok(snapshots[0].rows[0].indexOf("2025款 2025款") === -1, "年款后缀不重复");
  assert.ok(snapshots[0].rows[1].indexOf("2026款 2026款") === -1, "名称已含年款时后缀被抑制（真阳性）");
  assert.ok(snapshots[0].rows[0].indexOf("驱动方式") !== -1, "车型行含驱动方式");
  assert.ok(snapshots[0].rows[0].indexOf("纯电续航(km)") !== -1, "车型行含续航");
  assert.ok(snapshots[0].rows[0].indexOf("纯电") !== -1, "车型行含能源值");
  assert.ok(snapshots[0].rows[1].indexOf("增程") !== -1, "第二车型行含不同能源值");
});

test("display normalization: energy synonyms, pipe ranges, brand/series merge", () => {
  const { hooks } = loadAppForTest();
  // 1) brand + series merge: 阿维塔 07 vs 阿维塔07, 小鹏 vs 小鹏汽车
  hooks.initializeRows([
    Object.assign(row("汽车之家", 2026, "阿维塔 07 增程版"), { "品牌": "阿维塔", "车系": "阿维塔 07", "官方指导价": "21.99万" }),
    Object.assign(row("懂车帝", 2026, "阿维塔07 纯电版"), { "品牌": "阿维塔", "车系": "阿维塔07", "官方指导价": "24.99万" }),
    Object.assign(row("汽车之家", 2026, "G6 增程版"), { "品牌": "小鹏", "车系": "G6", "官方指导价": "17.68万" }),
    Object.assign(row("懂车帝", 2026, "G6 纯电版"), { "品牌": "小鹏汽车", "车系": "G6", "官方指导价": "18.68万" })
  ]);
  let groups = hooks.groupRowsBySeries(hooks.getFilteredRows());
  const keys = Array.from(groups, (g) => g.key);
  assert.ok(keys.filter((k) => k.includes("阿维塔")).length === 1, "空格差异车系应合并为一张卡");
  assert.ok(keys.filter((k) => k.includes("G6")).length === 1, "品牌同义词车系应合并为一张卡");
  assert.equal(Array.from(groups, (g) => g.rows.length).sort().join(","), "2,2");

  // 2) summary: energy synonyms + source prefixes + pipe ranges + 999 drop
  const groups2 = [
    {
      key: "S1", name: "S1",
      representative: { "品牌": "甲", "级别": "中型SUV", "车型名称": "代表" },
      rows: [
        { "车型名称": "A 1", "品牌": "甲", "级别": "中型SUV", "能源类型": "插电混合", "官方指导价": "19.99万", "纯电续航(km)": "230|163|230|163" },
        { "车型名称": "A 2", "品牌": "甲", "级别": "中型SUV", "能源类型": "懂车帝:插电式混合动力|易车:插电混合", "官方指导价": "19.99万", "纯电续航(km)": "999" }
      ]
    }
  ];
  const snap = hooks.renderCards(groups2);
  assert.ok(snap[0].meta.indexOf("能源类型: 插电式混合动力") !== -1, "同义词+来源前缀归一为单一写法");
  assert.ok(snap[0].meta.indexOf("插电混合/") === -1, "不应出现未归一写法");
  assert.ok(snap[0].meta.indexOf("纯电续航(km): 163-230") !== -1, "管道多值去重后显示范围");
  assert.ok(snap[0].meta.indexOf("999") === -1, "999 占位不应显示");
});

test("SKU display merge unifies name formats within one SPU and keeps powertrain conflicts apart", () => {
  const app = loadAppForTest();
  const base = {
    "品牌": "别克", "车系": "别克至境E7", "年款": "2026",
    "官方指导价": "19.99万", "纯电续航(km)": "CLTC:230 / WLTC:163",
    "能源类型": "插电式混合动力", "发动机": "1.5T 156马力 L4 涡轮增压",
    "驱动方式": "前置前驱"
  };
  const a = Object.assign(row("汽车之家", 2026, "26款 1.5T 230km 1600 超满配Turbo版"), base, { "车款ID": "186452" });
  const b = Object.assign(row("懂车帝", 2026, "别克至境E7 2026款 1600 超满配Turbo版"), base, { "车款ID": "76217" });
  app.hooks.initializeRows([a, b]);
  assert.equal(app.hooks.state.rows.length, 1, "同一 SKU 的两种命名必须并成一行");
  assert.equal(app.hooks.state.rows[0]["车型名称"], "2026款 1.5T 230km 1600 超满配Turbo版");
  assert.ok(String(app.hooks.state.rows[0]["源车型名称"]).includes("26款 1.5T 230km"));
  assert.ok(String(app.hooks.state.rows[0]["源车型名称"]).includes("别克至境E7 2026款"));

  const c = Object.assign(row("汽车之家", 2026, "26款 2.0T 230km 1600 超满配Turbo版"), base, {
    "车款ID": "900001", "发动机": "2.0T 200马力 L4 涡轮增压"
  });
  app.hooks.initializeRows([a, c]);
  assert.equal(app.hooks.state.rows.length, 2, "动力不同（1.5T vs 2.0T）不许合并");
});

test("Display columns put low-frequency source-specific columns into a separate group", () => {
  const app = loadAppForTest();
  const rows = [];
  for (let i = 0; i < 100; i += 1) {
    rows.push({ "车系": "S" + i, "静享驾乘包": i === 0 ? "●" : "" });
  }
  const groups = app.hooks.classifySkuColumns(["车系", "静享驾乘包"], rows);
  assert.deepEqual(JSON.parse(JSON.stringify(groups.attribute)), ["车系"]);
  assert.deepEqual(JSON.parse(JSON.stringify(groups.option)), ["静享驾乘包"]);
});

test("SKU display merge keeps same 车款ID + same name rows together even when source prices conflict", () => {
  // 线上实测形状（车款ID 171437）：一行是单源价 `11.98万`，另一行是聚合串 `懂车帝:10.89万|易车:11.98万`；
  // 只取第一个数字会把聚合行读成 10.89 ⇒ 与 11.98 判成互斥 ⇒ 展示层留下两行 ⇒ 线上验收不变式直接红。
  const app = loadAppForTest();
  const base = {
    "品牌": "捷途", "车系": "捷途X70", "年款": "2024",
    "能源类型": "汽油", "发动机": "1.5T 156马力 L4", "排量(L)": "1.5", "纯电续航(km)": "0"
  };
  const a = Object.assign(row("易车", 2024, "24款 1.5T 双离合跃享版 5座"), base, {
    "车款ID": "171437", "官方指导价": "11.98万"
  });
  const b = Object.assign(row("懂车帝+易车", 2024, "24款 1.5T 双离合跃享版 5座"), base, {
    "车款ID": "171437", "官方指导价": "懂车帝:10.89万|易车:11.98万"
  });
  app.hooks.initializeRows([a, b]);
  assert.equal(app.hooks.state.rows.length, 1, "同 车款ID 同名必须是同一行（线上验收不变式）");
  assert.ok(String(app.hooks.state.rows[0]["数据来源"]).includes("懂车帝"), "两家来源都要留在来源列");
  assert.ok(String(app.hooks.state.rows[0]["数据来源"]).includes("易车"));
});

test("SKU display merge does not chain conflicting SKUs through a bridging row", () => {
  // step 家族票 P1 的复现形状：A(58.98万/2.0T) + B(缺价缺动力) + C(62.98万/2.4L) 曾被桥接行 B 合成 1 行、C 静默消失。
  // 完全链接下 C 自成一簇；这里钉"不是 1 行"且两档价格都还在面上。
  const app = loadAppForTest();
  const common = {
    "品牌": "测试品牌", "车系": "桥接车系", "年款": "2024", "能源类型": "汽油",
    "纯电续航(km)": "0", "驱动方式": "前置前驱"
  };
  const a = Object.assign(row("汽车之家", 2024, "2024款 2.0T 豪华版"), common, {
    "车款ID": "900011", "官方指导价": "58.98万", "发动机": "2.0T 200马力 L4"
  });
  const b = Object.assign(row("懂车帝", 2024, "2024款 豪华版"), common, { "车款ID": "" });
  const c = Object.assign(row("易车", 2024, "2024款 2.4L 豪华版"), common, {
    "车款ID": "900013", "官方指导价": "62.98万", "发动机": "2.4L 180马力 L4"
  });
  app.hooks.initializeRows([a, b, c]);
  const rows = app.hooks.state.rows;
  assert.notEqual(rows.length, 1, "互斥的 A~C 不许被桥接行 B 合掉（1 行 = C 静默消失）");
  const prices = rows.map((r) => String(r["官方指导价"] || "")).join(" | ");
  assert.ok(prices.includes("62.98万"), "2.4L 那一档的价格必须仍在面上");
  assert.ok(prices.includes("58.98万"), "2.0T 那一档的价格必须仍在面上");
});


test("current saved Song L, Avatr 06 and YU7 records merge equivalent names before any visibility filter", () => {
  const fixture = JSON.parse(fs.readFileSync(path.join(__dirname, "fixtures/user_sku_current_records.json"), "utf8"));
  assert.equal(fixture.source_sha256, "28d606eda93a7f7ff246586931dd9a4721bca1fbf02238662956a89d3cdee6c8");
  const {hooks} = loadAppForTest();
  const original = JSON.stringify(fixture.rows);
  hooks.initializeRows(fixture.rows);
  hooks.state.saleScope = "all";
  hooks.state.rangeFilters = {};
  hooks.state.featureFilters = {};
  const pairs = [
    ["阿维塔06 2025款 Max纯电版", "25款 纯电版 650km 后驱Max"],
    ["阿维塔06 2025款 Pro纯电版", "25款 纯电版 650km 后驱Pro"],
    ["阿维塔06 2025款 Elite纯电版", "25款 纯电版 650km 后驱Elite"],
    ["阿维塔06 2025款 Max增程版", "25款 增程版 230km 后驱Max"],
    ["阿维塔06 2025款 Pro增程版", "25款 增程版 230km 后驱Pro"],
    ["阿维塔06 2025款 Ultra增程版", "25款 增程版 330km 后驱Ultra"],
    ["小米YU7 2025款 四驱Pro版", "25款 770km 四驱Pro"],
    ["小米YU7 2025款 四驱Max版", "25款 760km 四驱Max"],
    ["宋L EV 2025款 智驾版 602km 激光雷达四驱型", "25款 智驾版 602km 四驱激光雷达型"]
  ];
  for (const names of pairs) {
    assert.ok(names.every(name => fixture.rows.some(r => r["车型名称"] === name)));
    const merged = hooks.state.rows.filter(r => names.every(name => String(r["源车型名称"]).split(" / ").includes(name)));
    assert.equal(merged.length, 1, names.join(" versus "));
  }
  assert.equal(JSON.stringify(fixture.rows), original, "raw observations are immutable");
  for (const energy of ["纯电动", "增程式"]) {
    assert.ok(hooks.state.rows.some(r => r["车系"] === "阿维塔06" && /Max/.test(r["车型名称"]) && r["能源类型"] === energy));
  }
  assert.ok(hooks.state.rows.some(r => r["车系"] === "小米YU7" && /38.99/.test(r["官方指导价"])), "over-budget GT is retained before filtering");
});

test("semantic SKU equivalence retains known battery, motor, sensor, drive and intelligent-driving differences", () => {
  const {hooks} = loadAppForTest();
  const base = Object.assign(row("汽车之家", 2026, "测试车系 Pro版"), {"能源类型":"纯电动", "纯电续航(km)":"600", "驱动方式":"后驱"});
  for (const [field, a, b] of [["电池容量(kWh)","70","80"], ["电动机总功率(kW)","200","250"], ["激光雷达数量","0","1"], ["激光雷达数量",0,"1个"], ["激光雷达数量",0,1], ["驱动电机数",0,1], ["驱动方式","后驱","四驱"]]) {
    hooks.initializeRows([Object.assign({},base,{[field]:a}), Object.assign({},base,{"车型名称":"测试车系 Pro",[field]:b})]);
    assert.equal(hooks.state.rows.length, 2, field);
    if (a === 0) {
      const displayed = field === "激光雷达数量" ? "激光雷达数量(个)" : field;
      assert.equal(hooks.state.rows[0][displayed], "0", "known numeric zero count survives display merging");
    }
  }
  hooks.initializeRows([Object.assign({},base,{"官方指导价":"35.8万"}), Object.assign({},base,{"车型名称":"测试车系 Pro", "官方指导价":"35.800000000000001万"})]);
  assert.equal(hooks.state.rows.length,2,"identity price comparison must not round distinct decimal observations");
  hooks.initializeRows([Object.assign({},base,{"官方指导价":"35.8万"}), Object.assign({},base,{"车型名称":"测试车系 Pro", "官方指导价":"358000元"})]);
  assert.equal(hooks.state.rows.length,1,"equivalent monetary units remain the same observed price");
  hooks.initializeRows([base, Object.assign({},base,{"车型名称":"测试车系 智驾Pro版"})]);
  assert.equal(hooks.state.rows.length, 2, "same-price intelligent-driving variant remains distinct");
});

test("energy and exact decimal prices agree in cards, table and current exports without erasing conflicts", async () => {
  const {hooks,elements,downloads} = loadAppForTest();
  hooks.state.config = {conditions:[], hiddenByDefault:[],dropIfUniformPositive:[],defaultVisibleColumns:["车型名称","能源类型","官方指导价"]};
  const raw = [
    Object.assign(row("汽车之家",2026,"等价值"), {"车系":"等价值","能源类型":"纯电动|易车:纯电","官方指导价":"35.80万|35.8万|358000元"}),
    Object.assign(row("汽车之家",2026,"冲突值"), {"车系":"冲突值","能源类型":"汽车之家:纯电动|易车:增程式纯电动","官方指导价":"汽车之家:33.80万|33.8万|易车:35.80万"}),
    Object.assign(row("汽车之家",2026,"精确值"), {"车系":"精确值","官方指导价":"35.8万|35.800000000000001万"})
  ];
  const before = JSON.stringify(raw);
  assert.equal(hooks.normEnumValue("纯电动|易车:纯电"),"纯电动","existing one-argument deployment-checker call remains compatible");
  hooks.initializeRows(raw);
  const equal = hooks.state.rows.find(r=>r["车系"]==="等价值");
  const conflict = hooks.state.rows.find(r=>r["车系"]==="冲突值");
  assert.equal(equal["能源类型"],"纯电动");
  assert.equal(equal["官方指导价"],"35.8万");
  assert.match(conflict["能源类型"],/纯电动/);
  assert.match(conflict["能源类型"],/增程式/);
  assert.match(conflict["官方指导价"],/汽车之家:33\.8万\|易车:35\.8万/);
  assert.match(hooks.state.rows.find(r=>r["车系"]==="精确值")["官方指导价"],/35\.800000000000001万/);
  const cards = hooks.renderCards(hooks.groupRowsBySeries(hooks.state.rows));
  const conflictCard = cards.find(c=>c.meta.includes("增程式"));
  assert.ok(conflictCard && conflictCard.meta.includes("纯电动"), "summary must not reduce a conflict to the dominant energy family");
  hooks.state.mode="table";
  hooks.renderTableBody(hooks.state.rows);
  const text = descendants(elements.get("tableBody")).map(e=>e.textContent).join(" ");
  assert.ok(text.includes("纯电动") && text.includes("增程式") && !text.includes("35.80万"));
  hooks.exportCurrentJson();
  const exported=JSON.parse(await downloads[0].text());
  assert.equal(exported.find(r=>r["车系"]==="等价值")["官方指导价"],"35.8万");
  hooks.exportCurrentCsv();
  const csv=await downloads[1].text();
  assert.ok(csv.includes("纯电动") && csv.includes("增程式") && !csv.includes("35.80万"));
  assert.equal(JSON.stringify(raw),before);
});

test("default price is an adjustable SKU filter, excludes unknown and conflicting above-budget observations, and resets honestly", () => {
  const {hooks,elements}=loadAppForTest();
  const config=JSON.parse(fs.readFileSync(path.join(__dirname,"../config/filter_conditions.json"),"utf8"));
  hooks.state.config=Object.assign({},config,{conditions:config.conditions.filter(c=>c.id==="msrp"),defaultAllowedLevels:null});
  const prices=["34.9万","35万","35.01万","0","-","31万|36万","350000元"];
  hooks.initializeRows(prices.map((price,i)=>Object.assign(row("易车",2026,"价格款"+i),{"官方指导价":price})));
  assert.equal(hooks.state.saleScope,"onSale");
  assert.equal(hooks.state.rangeFilters.msrp.max,"35");
  assert.equal(hooks.getFilteredRows().length,3);
  assert.equal(hooks.groupRowsBySeries(hooks.getFilteredRows())[0].rows.length,3,"filter SKU before SPU summary");
  assert.equal(hooks.state.rows.length,7,"default is not a data deletion rule");
  assert.ok([undefined,"未提供"].includes(hooks.state.rows.find(r=>r["车型名称"]==="价格款3")["官方指导价"]),"zero placeholder is not displayed as a positive 0万元 price");
  hooks.state.rangeFilters.msrp={min:"",max:""};
  assert.equal(hooks.getFilteredRows().length,7,"clearing both bounds also shows unknown prices");
  hooks.state.rangeFilters.msrp={min:"",max:"40"};
  assert.equal(hooks.getFilteredRows().length,5);
  hooks.state.saleScope="all";
  elements.get("resetFilters").dispatch("click");
  assert.equal(hooks.state.saleScope,"onSale");
  assert.equal(hooks.state.rangeFilters.msrp.max,"35");
  assert.equal(hooks.getFilteredRows().length,3);
  hooks.initializeRows([Object.assign(row("易车",2026,"带单位零占位"),{"官方指导价":"0万"})]);
  assert.equal(hooks.state.rows[0]["官方指导价"],"未提供");
  assert.equal(hooks.getFilteredRows().length,0);
});

test("recent-five-year lower bound rolls with the current year instead of freezing 2022", () => {
  const {hooks}=loadAppForTest();
  const year=new Date().getFullYear();
  hooks.initializeRows([row("汽车之家",year-5,"更早"),row("汽车之家",year-4,"下界"),row("汽车之家",year,"当年")]);
  assert.equal(hooks.state.rows.length,2);
  assert.ok(!hooks.state.rows.some(r=>r["车型名称"]==="更早"));
});

test("SKU table supports arbitrary positive page size and untruncated all mode, cancels stale batches and keeps snapshots", () => {
  const app=loadAppForTest(); const {hooks,elements}=app;
  hooks.initializeRows(Array.from({length:1207},(_,i)=>row("易车",2026,"SKU "+String(i).padStart(4,"0"))));
  hooks.state.mode="table";
  elements.get("pageSize").value="37";
  elements.get("applyPageSize").dispatch("click");
  assert.equal(hooks.state.pageSize,37);
  assert.equal(elements.get("tableBody").children.length,37);
  assert.equal(elements.get("pageInfo").textContent,"第 1 / 33 页");
  for (const bad of ["0","-1","2.5","NaN",""]) {
    elements.get("pageSize").value=bad;
    elements.get("pageSize").dispatch("change");
  }
  assert.equal(hooks.state.pageSize,37);
  elements.get("tableDisplayMode").dispatch("change",{target:{value:"all"}});
  assert.ok(app.pendingFrames()>0,"large single-page rendering yields to the browser");
  assert.equal(elements.get("pageJump").disabled,true);
  app.flushFrames();
  assert.equal(elements.get("tableBody").children.length,1207,"no fixed 500-row truncation");
  assert.equal(elements.get("tableBody").getAttribute("aria-busy"),"false");
  hooks.renderResultsOnly();
  assert.ok(app.pendingFrames()>0);
  hooks.state.search="SKU 0000";
  hooks.renderResultsOnly();
  app.flushFrames();
  assert.equal(elements.get("tableBody").children.length,1,"cancelled old frames cannot append stale results");
  const saved=hooks.snapshotFilters();
  assert.equal(saved.tableDisplayMode,"all");
  assert.equal(saved.pageSize,37);
  hooks.applySnapshot(saved);
  app.flushFrames();
  assert.equal(hooks.state.tableDisplayMode,"all");
  elements.get("tableDisplayMode").dispatch("change",{target:{value:"paged"}});
  assert.equal(hooks.state.page,1);
  assert.equal(elements.get("pageSize").disabled,false);
});

test("all table headers, column chooser and field filters share category/section/property order including unknown fields", () => {
  const {hooks,elements}=loadAppForTest();
  hooks.state.config=JSON.parse(fs.readFileSync(path.join(__dirname,"../config/filter_conditions.json"),"utf8"));
  hooks.initializeRows([Object.assign(row("易车",2026,"分类验证"),{"能源类型":"纯电动","电池容量(kWh)":"80","某陌生配置列":"证据","580km尊贵型":"支持","__custom_equipment":"保留","6万公里保养总成本预估":"4200元","4G/5G网络":"5G"})]);
  hooks.state.visibleColumns=new Set(hooks.state.columns);
  hooks.renderTableHead(); hooks.renderColumnList(); hooks.renderFilters(); hooks.state.mode="table"; hooks.renderTableBody(hooks.state.rows);
  const header=elements.get("tableHead").children;
  assert.equal(header[0].className,"table-major-row");
  assert.equal(header[1].className,"table-minor-row");
  assert.equal(header[2].className,"table-column-row");
  assert.equal(header[2].children.length,hooks.state.columns.length);
  assert.equal(header[0].children.reduce((n,c)=>n+c.colSpan,0),hooks.state.columns.length);
  assert.equal(header[1].children.reduce((n,c)=>n+c.colSpan,0),hooks.state.columns.length);
  assert.deepEqual(header[2].children.map(c=>c.children[0].children[0].textContent),Array.from(hooks.state.columns));
  const options=descendants(elements.get("fieldSelect")).filter(e=>e.tagName==="OPTION");
  assert.deepEqual(options.map(e=>e.value),Array.from(hooks.state.columns));
  const checkboxes=descendants(elements.get("columnList")).filter(e=>e.tagName==="INPUT");
  assert.deepEqual(checkboxes.map(e=>e.dataset.column),Array.from(hooks.state.columns));
  const cells=elements.get("tableBody").children[0].children;
  hooks.state.columns.forEach((column, i) => {
    const summary = descendants(cells[i]).find((node) => node.tagName === "SUMMARY");
    assert.equal((summary || cells[i]).textContent, String(hooks.state.rows[0][column] == null ? "-" : hooks.state.rows[0][column]));
  });
  assert.equal(hooks.columnPath("某陌生配置列").major,"未分类/待确认");
  assert.match(hooks.columnPath("580km尊贵型").minor,/疑似属性值/);
  assert.equal(hooks.columnPath("6万公里保养总成本预估").major,"基本信息");
  assert.equal(hooks.columnPath("4G/5G网络").major,"智能硬件");
  assert.doesNotMatch(hooks.columnPath("4G/5G网络").minor,/疑似|待确认/);
  assert.ok(hooks.state.columns.includes("__custom_equipment"));
});

test("range tags omit zero lower bound but preserve meaningful positive or negative bounds", () => {
  const {hooks}=loadAppForTest();
  const condition={id:"zero_to_hundred",type:"range",label:"百公里加速"};
  hooks.state.rangeFilters.zero_to_hundred={min:"0.00",max:"7"};
  assert.equal(hooks.conditionTagLabel(condition),"百公里加速 ≤7");
  for(const min of ["2","-1"]) {
    hooks.state.rangeFilters.zero_to_hundred={min,max:"7"};
    assert.ok(hooks.conditionTagLabel(condition).includes("≥"+min));
    assert.ok(hooks.conditionTagLabel(condition).includes("≤7"));
  }
});


test("Canonical sale status still respects the future listing-time cutoff", () => {
  const { hooks } = loadAppForTest();
  hooks.initializeRows([
    Object.assign(row("汽车之家", 2026, "未来在售"), { "上市状态": "在售", "上市时间": "2099.03" }),
    Object.assign(row("汽车之家", 2026, "已到在售"), { "上市状态": "在售", "上市时间": "2025.01" }),
    Object.assign(row("汽车之家", 2026, "冲突状态"), { "上市状态": "冲突", "上市时间": "2025.01" }),
    Object.assign(row("汽车之家+易车", 2026, "逐源未知"), { "上市状态_汽车之家": "未知", "上市时间": "2025.01" })
  ]);
  assert.equal(hooks.getFilteredRows().map((r) => r["车型名称"]).join(","), "已到在售");
});


test("merged sale status preserves negative and unknown evidence in both source orders", () => {
  const {hooks}=loadAppForTest();
  const base=row("易车",2026,"同一SKU销售冲突");
  for(const negative of ["停售","off_sale","0","已上市"]) {
    for(const statuses of [["approved",negative],[negative,"approved"]]) {
      const original=statuses.map(status=>Object.assign({},base,{"易车上市状态":status}));
      const before=JSON.stringify(original);
      hooks.initializeRows(original);
      assert.equal(hooks.state.rows.length,1);
      assert.ok(hooks.state.rows[0]["易车上市状态"].includes(negative));
      assert.equal(hooks.getFilteredRows().length,0,"one source approval must not mask contrary evidence");
      hooks.state.saleScope="all";
      assert.equal(hooks.getFilteredRows().length,1,"conflicting record remains available in all scope");
      hooks.state.saleScope="onSale";
      assert.equal(JSON.stringify(original),before);
    }
  }
  hooks.initializeRows([base,Object.assign({},base,{"易车上市状态":""})]);
  assert.equal(hooks.getFilteredRows().length,1,"absent observation does not contradict a recorded approval");
});


test("sticky header offsets follow measured row heights including mobile buttons, fractional heights and hidden tables", () => {
  const {hooks,elements}=loadAppForTest();
  hooks.initializeRows([row("易车",2026,"表头高度")]);
  hooks.renderTableHead();
  assert.equal(elements.get("tableHead").getAttribute("data-measured"),"false","unmeasured fallback is ordinary table flow");
  const rows=elements.get("tableHead").children;
  const heights=[28.59375,28.59375,61,57];
  rows.forEach((row,i)=>row.getBoundingClientRect=()=>({height:heights[i]}));
  hooks.syncTableHeaderOffsets();
  assert.equal(elements.get("tableHead").getAttribute("data-measured"),"true");
  assert.equal(rows[0].children[0].style.top,"0px");
  assert.equal(rows[1].children[0].style.top,"28.59375px");
  assert.equal(rows[2].children[0].style.top,"57.1875px");
  assert.equal(rows[3].children[0].style.top,"118.1875px","mobile filter row cannot overlap a 61px title row");
  heights[2]=42;
  hooks.syncTableHeaderOffsets();
  assert.equal(rows[3].children[0].style.top,"99.1875px","viewport/font changes update offsets");
  heights[0]=0;
  hooks.syncTableHeaderOffsets();
  assert.equal(rows[3].children[0].style.top,"99.1875px","hidden rows cannot overwrite a valid offset with zero");
});

test("annotated or interval MSRP observations cannot silently disable the SKU price-conflict guard", () => {
  const {hooks}=loadAppForTest();
  for (const [first, second] of [["15.98万起","12.98万"],["12.98-15.98万","13.98万"],["15.98万(共3款)","16.98万"]]) {
    hooks.initializeRows([
      Object.assign(row("汽车之家",2026,"后驱 Pro"),{"官方指导价":first}),
      Object.assign(row("易车",2026,"Pro版 后驱"),{"官方指导价":second})
    ]);
    assert.equal(hooks.state.rows.length,2,first+" cannot become missing price evidence");
    assert.ok(hooks.state.rows.some(r=>r["官方指导价"]===first),"retained observation must not be guessed into a precise price");
  }
});

test("non-energy summary normalization removes only known source prefixes and preserves measurement cycles", () => {
  const {hooks}=loadAppForTest();
  assert.equal(hooks.normEnumValue("汽车之家:多连杆独立悬架","后悬挂形式"),"多连杆独立悬架");
  assert.equal(hooks.normEnumValue("易车:CLTC:643","纯电续航(km)"),"CLTC:643");
  assert.equal(hooks.normEnumValue("CLTC:643","纯电续航(km)"),"CLTC:643");
  assert.equal(hooks.normEnumValue("WLTC:643","纯电续航(km)"),"WLTC:643");
  assert.equal(hooks.normEnumValue("自定义:真实值","真实属性"),"自定义:真实值");
});

test("noncanonical equality-guard price keys never become NaN numeric representative prices", () => {
  const {hooks}=loadAppForTest();
  assert.equal(hooks.skuPrice({"官方指导价":"12.98-15.98万"}),null);
  assert.equal(hooks.skuPrice({"官方指导价":"15.98万(共3款)|16.98万"}),16.98);
  assert.equal(hooks.skuPrice({"官方指导价":"35.80万|358000元"}),35.8);
});

test("custom energy ordering distinguishes HEV from PHEV and retains mixed-energy observations", () => {
  const {hooks}=loadAppForTest();
  hooks.initializeRows([
    Object.assign(row("易车",2026,"A-PHEV"),{"能源类型":"插电式混合动力"}),
    Object.assign(row("易车",2026,"Z-HEV"),{"能源类型":"油电混合"}),
    Object.assign(row("易车",2026,"B-BEV"),{"能源类型":"纯电动"}),
    Object.assign(row("易车",2026,"C-mixed"),{"能源类型":"纯电动|增程式"})
  ]);
  hooks.state.sortLevels=[{field:"能源类型",dir:"asc",customOrder:"油电混合,插电式混合动力,纯电,增程"}];
  assert.deepEqual(Array.from(hooks.getFilteredRows(),r=>r["车型名称"]),["Z-HEV","A-PHEV","B-BEV","C-mixed"]);
  hooks.state.sortLevels=[{field:"能源类型",dir:"asc",customOrder:"增程,纯电,插混,油电"}];
  assert.deepEqual(Array.from(hooks.getFilteredRows(),r=>r["车型名称"]),["B-BEV","A-PHEV","Z-HEV","C-mixed"]);
});

test("Pages maps every configured default-visible column into a real category instead of the pending bucket", () => {
  const { hooks } = loadAppForTest();
  const config = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "docs", "filter_conditions.json"), "utf8"));
  hooks.state.config = config;
  const pending = config.defaultVisibleColumns.filter((column) => hooks.columnPath(column).major === "未分类/待确认");
  assert.deepEqual(pending, [], "规范列名必须落进现存主/次分类，不得整批落进待确认桶");
  config.defaultVisibleColumns.forEach((column) => {
    assert.doesNotMatch(hooks.columnPath(column).minor, /待核验|待归类/, column);
  });
  assert.equal(hooks.columnPath("长(mm)").major, "外部/防盗");
  assert.equal(hooks.columnPath("宽(mm)").major, "外部/防盗");
  assert.equal(hooks.columnPath("高(mm)").major, "外部/防盗");
  assert.equal(hooks.columnPath("换挡形式").major, "底盘与操控");
  assert.equal(hooks.columnPath("最小转弯半径").major, "底盘与操控");
  assert.equal(hooks.columnPath("最大快充功率(kw)").major, "动力参数");
  assert.equal(hooks.columnPath("VTOL最大对外放电功率").major, "动力参数");
  assert.equal(hooks.columnPath("零整比").major, "基本信息");
  // 陌生列和疑似属性值列仍须留在待确认桶，不能靠硬塞已知类达标
  assert.equal(hooks.columnPath("某陌生配置列").major, "未分类/待确认");
  assert.equal(hooks.columnPath("580km尊贵型").minor.indexOf("疑似属性值"), 0);
});

test("mobile filter center never receives a section whose condition ids all fail to resolve", () => {
  const { elements, hooks, setMatchMedia } = loadAppForTest();
  const config = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "docs", "filter_conditions.json"), "utf8"));
  hooks.state.config = JSON.parse(JSON.stringify(config));
  const power = hooks.state.config.filterTaxonomy.find((category) => category.id === "power");
  power.sections.push({ id: "ghost", label: "幽灵小节", conditionIds: ["ghost_condition"], columnPatterns: ["幽灵"] });
  const mixed = hooks.state.config.filterTaxonomy.find((category) => category.id === "assist");
  mixed.sections[0].conditionIds = mixed.sections[0].conditionIds.concat(["ghost_sibling"]);
  const realConditions = hooks.state.config.conditions.map((condition) => condition.id);
  setMatchMedia(true);
  hooks.initializeRows([Object.assign(row("易车", 2026, "移动端分类"), { "百公里加速(s)": "6.5", "最高车速(km/h)": "200", "纯电续航(km)": "500" })]);
  hooks.renderCenterFilters();
  const list = elements.get("centerConditionList");
  assert.ok(descendants(list).some((node) => node.className === "mobile-filter-layout"), "应走移动端分类布局");
  const sections = descendants(list).filter((node) => node.className === "mobile-minor-section");
  assert.ok(sections.length > 0, "移动端至少渲染一个真实小节");
  sections.forEach((section) => {
    const items = descendants(section).filter((node) => node.className === "center-condition-item");
    assert.ok(items.length > 0, "全悬空小节不得进入移动端：" + section.children[0].textContent);
    items.forEach((item) => assert.ok(realConditions.includes(item.dataset.conditionId), "渲染出的条件必须真实可解析"));
  });
  const titles = sections.map((section) => section.children[0].textContent);
  assert.equal(titles.includes("幽灵小节"), false);
  const assistSection = sections.find((section) => section.children[0].textContent === mixed.sections[0].label);
  assert.ok(assistSection, "同一大类里还有可解析条件的小节必须保留");
  const assistItems = descendants(assistSection).filter((node) => node.className === "center-condition-item");
  assert.deepEqual(assistItems.map((item) => item.dataset.conditionId), mixed.sections[0].conditionIds.filter((id) => realConditions.includes(id)));
});

test("unsubmitted page size draft survives search, column and async renders until the user submits", () => {
  const { elements, hooks } = loadAppForTest();
  hooks.initializeRows(Array.from({ length: 260 }, (_, index) => row("易车", 2026, "草稿 " + index)));
  hooks.state.mode = "table";
  hooks.renderResultsOnly();
  const input = elements.get("pageSize");
  assert.equal(input.value, "100");
  // 用户键入先改的是真实 DOM 值；应用若登记了草稿会收到 input 事件，没登记也要能守住这个值
  input.value = "37";
  if (typeof input.listeners.input === "function") { input.dispatch("input"); }
  elements.get("globalSearch").dispatch("input", { target: { value: "草稿" } });
  assert.equal(input.value, "37", "搜索渲染不得抹掉未提交的每页条数草稿");
  assert.equal(hooks.state.pageSize, 100, "草稿未提交前生效的仍是旧页大小");
  elements.get("columnList").dispatch("change", { target: { tagName: "INPUT", checked: true, dataset: { column: "品牌" } } });
  assert.equal(input.value, "37", "列勾选渲染不得抹掉草稿");
  hooks.renderResultsOnly();
  assert.equal(input.value, "37", "异步刷新渲染不得抹掉草稿");
  input.dispatch("keydown", { key: "Enter" });
  assert.equal(hooks.state.pageSize, 37);
  assert.equal(input.value, "37");
  input.value = "0";
  input.dispatch("change");
  assert.equal(hooks.state.pageSize, 37, "非法值仍按原逻辑回退");
  assert.equal(input.value, "37");
  hooks.renderResultsOnly();
  assert.equal(input.value, "37", "提交后渲染回写当前页大小");
});

test("live saved dataset classifies canonical schema columns instead of the pending bucket", { skip: !liveDataPath }, () => {
  const { hooks } = loadAppForTest();
  const config = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "docs", "filter_conditions.json"), "utf8"));
  hooks.state.config = config;
  const raw = JSON.parse(fs.readFileSync(liveDataPath, "utf8"));
  const rows = Array.isArray(raw) ? raw : raw.rows;
  const normalized = hooks.normalizeRowColumns(rows);
  const columns = new Set();
  normalized.forEach((item) => Object.keys(item).forEach((column) => columns.add(column)));
  const pending = Array.from(columns).filter((column) => hooks.columnPath(column).major === "未分类/待确认");
  config.defaultVisibleColumns.filter((column) => columns.has(column)).forEach((column) => {
    assert.equal(hooks.columnPath(column).major === "未分类/待确认", false, "真实数据里的默认展示列落入待确认：" + column);
  });
  ["长(mm)", "宽(mm)", "高(mm)", "换挡形式", "最小转弯半径", "最大快充功率(kw)", "VTOL最大对外放电功率", "零整比"].forEach((column) => {
    assert.ok(columns.has(column), "真实数据里应有该规范列：" + column);
    assert.equal(hooks.columnPath(column).major === "未分类/待确认", false, column);
  });
  assert.equal(hooks.columnPath("可拓展生态设备：副驾50W无线风冷快充").major, "未分类/待确认",
    "真正陌生的选装包/属性值列仍须留在待确认桶");
  assert.ok(pending.length < columns.size, "整批列不得全部落进待确认桶");
  process.stdout.write(`分类面：真实 ${columns.size} 列，其中待确认 ${pending.length} 列\n`);
});

test("canonical category patterns reject appended values while retaining real unit-bearing properties", () => {
  const { hooks } = loadAppForTest();
  hooks.state.config = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "docs", "filter_conditions.json"), "utf8"));
  ["长(mm)加长版", "电子式换挡", "最小转弯半径4.8m", "最大快充功率250kW",
    "VTOL最大对外放电功率6kW", "零整比经济适用", "141L电动前备箱", "高性能版", "某陌生配置列"]
    .forEach((column) => assert.equal(hooks.columnPath(column).major, "未分类/待确认",
      "属性值式或陌生标题必须可见待确认，不能被新放宽的模式冒认为属性：" + column));
  ["长(mm)", "宽(mm)", "高(mm)", "换挡形式", "最小转弯半径", "最小转弯半径(m)",
    "最大快充功率(kw)", "最大快充功率(kW)", "VTOL最大对外放电功率", "VTOL最大对外放电功率(kW)", "零整比"]
    .forEach((column) => assert.notEqual(hooks.columnPath(column).major, "未分类/待确认",
      "收紧边界不能丢掉规范属性或明确单位：" + column));
});

function strictFilterContext(id) {
  const app = loadAppForTest();
  const config = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "config", "filter_conditions.json"), "utf8"));
  const condition = config.conditions.find((item) => item.id === id);
  assert.ok(condition, "配置里缺少严格筛选：" + id);
  app.hooks.state.config = config;
  app.hooks.state.featureFilters[id] = true;
  return { hooks: app.hooks, condition, config };
}

test("phone control requires actual operations, with independent source evidence", () => {
  const { hooks, condition } = strictFilterContext("remote_control");
  const matches = (row) => hooks.conditionMatches(row, condition);
  [
    [{ "手机App远程控制": "车辆监控|服务预约" }, false],
    [{ "手机App远程控制": "车况查询|车辆定位|寻车" }, false],
    [{ "手机APP远程功能": "车辆监控|服务预约" }, false],
    [{ "手机APP远程功能": "●" }, false],
    [{ "手机App远程控制": "车门控制|车辆监控" }, true],
    [{ "手机APP远程功能": "车窗控制|空调控制|车辆启动|充电控制" }, true],
    [{ "远程控制功能": "标配" }, true],
    [{ "手机远程控制": "●（标配）" }, true],
    [{ "远程控制": "支持（车辆监控）" }, false],
    [{ "手机App远程控制": "不支持车门控制" }, false],
    [{ "手机App远程控制": "车门控制|选装" }, false],
    [{ "手机远程控制": "●（选装）" }, false],
    [{ "销售说明": "手机APP远程控制|车门控制" }, false],
    [{ "手机App远程控制": "车辆监控|服务预约", "远程控制": "空调控制" }, true],
    [{ "手机App远程控制": "不支持", "手机APP远程功能": "车门控制" }, true]
  ].forEach(([input, expected]) => assert.equal(matches(input), expected, JSON.stringify(input)));
});

test("remote start needs its own equipment or a typed explicit startup action", () => {
  const { hooks, condition: control, config } = strictFilterContext("remote_control");
  const start = config.conditions.find((item) => item.id === "remote_start");
  hooks.state.featureFilters.remote_start = true;
  assert.equal(hooks.conditionMatches({ "远程启动": "●" }, start), true);
  assert.equal(hooks.conditionMatches({ "远程启动": "●" }, control), false);
  assert.equal(hooks.conditionMatches({ "手机App远程控制": "车门控制" }, control), true);
  assert.equal(hooks.conditionMatches({ "手机App远程控制": "车门控制" }, start), false);
  assert.equal(hooks.conditionMatches({ "手机APP远程功能": "车辆启动" }, control), true);
  assert.equal(hooks.conditionMatches({ "手机APP远程功能": "车辆启动" }, start), true);
  assert.equal(hooks.conditionMatches({ "远程启动功能": "选装" }, start), false);
  assert.equal(hooks.conditionMatches({ "远程启动": "不支持", "销售说明": "车辆启动" }, start), false);
});

test("merged phone control retains both raw source columns and does not promote optional enums", () => {
  const { hooks, condition } = strictFilterContext("remote_control");
  const original = Object.assign(row("易车", 2026, "独立控制来源"), {
    "级别": "中型车", "手机App远程控制": "车辆监控|服务预约", "手机APP远程功能": "车门控制"
  });
  const raw = [Object.freeze(original)];
  const before = JSON.stringify(raw);
  hooks.state.publishedRawRows = raw;
  hooks.initializeRows(raw);
  assert.equal(hooks.state.rows.length, 1);
  assert.equal(hooks.state.rows[0]["手机App远程控制"], "车辆监控|服务预约");
  assert.equal(hooks.state.rows[0]["手机APP远程功能"], "车门控制");
  assert.equal(hooks.state.columns.includes("手机App远程控制"), true);
  assert.equal(hooks.state.columns.includes("手机APP远程功能"), true);
  assert.equal(hooks.conditionMatches(hooks.state.rows[0], condition), true);
  assert.equal(hooks.state.publishedRawRows, raw);
  assert.equal(JSON.stringify(raw), before);
  const optional = { "手机App远程控制 - 远程控制": "选装" };
  const normalized = hooks.normalizeRowColumns([optional])[0];
  assert.equal(normalized["手机App远程控制 - 远程控制"], "选装");
  assert.equal(hooks.conditionMatches(normalized, condition), false);
  assert.equal(hooks.conditionMatches(hooks.normalizeRowColumns([
    { "手机App远程控制 - 车门控制": "●" }
  ])[0], condition), true);
});

test("saved column preferences follow verified spelling aliases", () => {
  const { hooks } = loadAppForTest();
  hooks.initializeRows([{ ...row("仅汽车之家", 2026, "样本"), "底盘透视": "●" }]);
  const alias = "180°透明底盘";
  const canonical = "底盘透视";
  const filter = Object.freeze({ operator: "contains", value: "●" });
  const snapshot = Object.freeze({
    saleScope: "all",
    visibleColumns: Object.freeze([alias, canonical, "不存在"]),
    columnFilters: Object.freeze({ [alias]: filter }),
    sortField: alias,
    sortLevels: Object.freeze([{ field: alias, dir: "desc" }, { field: canonical, dir: "asc" }]),
  });
  const original = JSON.stringify(snapshot);
  hooks.applySnapshot(snapshot);
  assert.deepEqual(Array.from(hooks.state.visibleColumns), [canonical]);
  assert.equal(hooks.state.columnFilters[canonical], filter);
  assert.equal(hooks.state.columnFilters[alias], undefined);
  assert.equal(hooks.getFilteredRows().length, 1);
  assert.equal(hooks.state.sortField, canonical);
  assert.deepEqual(JSON.parse(JSON.stringify(hooks.state.sortLevels)), [{ field: canonical, dir: "desc" }]);
  assert.equal(JSON.stringify(snapshot), original);

  const explicitFilter = { operator: "contains", value: "○" };
  hooks.applySnapshot({ columnFilters: { [alias]: filter, [canonical]: explicitFilter } });
  assert.equal(hooks.state.columnFilters[canonical], explicitFilter);
});

test("restoring history ignores columns removed from the display inventory", () => {
  const { hooks } = loadAppForTest();
  const pkg = "奥迪全方位辅助包 高端版";
  const price = "官方指导价";
  hooks.initializeRows([
    { ...row("仅易车", 2026, "有套件"), [pkg]: "○", [price]: "28万" },
    { ...row("仅易车", 2026, "无套件"), [pkg]: "-", [price]: "20万" },
  ]);
  const saved = Object.freeze({
    saleScope: "all",
    visibleColumns: Object.freeze([pkg, price]),
    columnFilters: Object.freeze({[pkg]: {operator: "contains", value: "○"}}),
    sortField: pkg,
    sortDir: "desc",
    sortLevels: Object.freeze([{field: pkg, dir: "desc"}]),
  });
  assert.ok(!hooks.state.columns.includes(pkg));
  const original = JSON.stringify(saved);
  hooks.applySnapshot(saved);
  assert.equal(hooks.getFilteredRows().length, 2);
  assert.deepEqual(Array.from(hooks.state.visibleColumns), [price]);
  assert.deepEqual(Object.keys(hooks.state.columnFilters), []);
  assert.equal(hooks.state.sortField, price);
  assert.equal(hooks.state.sortDir, "asc");
  assert.equal(hooks.state.sortLevels.length, 0);
  assert.equal(JSON.stringify(saved), original);
  hooks.applySnapshot({ ...saved, visibleColumns: [pkg], sortLevels: [{field: price, dir: "desc"}] });
  assert.ok(hooks.state.visibleColumns.has(price));
  assert.equal(hooks.state.sortField, "");
  assert.equal(hooks.state.sortLevels[0].dir, "desc");
  hooks.applySnapshot({visibleColumns: []});
  assert.equal(hooks.state.visibleColumns.size, 0);
});

test("historical phone control switches migrate by OR without mutating snapshot input", () => {
  const { hooks } = strictFilterContext("remote_control");
  hooks.initializeRows([]);
  [
    { remote_control: false, app_remote_control: false },
    { remote_control: true, app_remote_control: false },
    { remote_control: false, app_remote_control: true },
    { remote_control: true, app_remote_control: true },
    { app_remote_control: true },
    { app_remote_control: false },
    { remote_control: false }
  ].forEach((old) => {
    const featureFilters = Object.freeze(Object.assign({ remote_start: true, bluetooth_key: false }, old));
    const snapshot = Object.freeze({ featureFilters });
    const before = JSON.stringify(snapshot);
    const expected = Boolean(old.remote_control || old.app_remote_control);
    hooks.applySnapshot(snapshot);
    assert.equal(hooks.state.featureFilters.remote_control, expected);
    assert.equal(Object.hasOwn(hooks.state.featureFilters, "app_remote_control"), false);
    assert.equal(hooks.state.featureFilters.remote_start, true);
    assert.equal(hooks.state.featureFilters.bluetooth_key, false);
    assert.notEqual(hooks.state.featureFilters, featureFilters);
    hooks.state.featureFilters.remote_control = !expected;
    assert.equal(JSON.stringify(snapshot), before);
  });
});

test("phone control has one condition, taxonomy assignment and UI item", () => {
  const { hooks, config } = strictFilterContext("remote_control");
  const { elements, hooks: ui } = loadAppForTest();
  assert.equal(config.conditions.filter((item) => item.id === "remote_control").length, 1);
  assert.equal(config.conditions.some((item) => item.id === "app_remote_control"), false);
  const assigned = config.filterTaxonomy.flatMap((major) => major.sections.flatMap((section) => section.conditionIds));
  assert.equal(assigned.filter((id) => id === "remote_control").length, 1);
  assert.equal(assigned.includes("app_remote_control"), false);
  ui.state.config = config;
  ui.initializeRows([]);
  ui.renderEverything();
  const controls = descendants(elements.get("centerConditionList"));
  assert.equal(controls.filter((item) => item.className === "center-condition-item" && item.dataset.conditionId === "remote_control").length, 1);
  assert.equal(controls.some((item) => item.dataset && item.dataset.conditionId === "app_remote_control"), false);
  assert.equal(Object.hasOwn(ui.state.featureFilters, "app_remote_control"), false);
  assert.equal(hooks.state.featureFilters.remote_control, true);
});

test("city navigation requires dedicated or typed urban driving evidence, never highway or marketing", () => {
  const { hooks, condition } = strictFilterContext("city_navigation");
  [
    [{ "车系": "摩卡PHEV", "车型名称": "Hi4 Max版 四驱长续航", "导航辅助驾驶": "高快领航" }, false],
    [{ "导航辅助驾驶": "高速NOA|高速NOP|高速领航" }, false],
    [{ "导航辅助驾驶": "高快领航|城市领航" }, true],
    [{ "导航辅助驾驶": "懂车帝:高快领航|易车:城市领航" }, true],
    [{ "导航辅助驾驶": "城区NOA" }, true],
    [{ "辅助驾驶路段": "城市路段 / 高速路段" }, false],
    [{ "辅助驾驶路段": "●高速路段 / 城市路段" }, false],
    [{ "辅助驾驶路段": "汽车之家:●城市路段 / 高速路段|易车:○城市路段" }, false],
    [{ "辅助驾驶路段 - 城市路段": "●" }, true],
    [{ "NOA城市领航": "●", "辅助驾驶路段": "易车:○城市路段 / ●高速路段" }, false],
    [{ "NOA城市领航": "●", "辅助驾驶路段 - 城市路段": "不支持" }, false],
    [{ "辅助驾驶路段": "●城市路段 / ○高速路段" }, true],
    [{ "NOA城市领航": "●", "辅助驾驶路段": "不支持高速路段" }, true],
    [{ "导航辅助驾驶": "城市领航", "辅助驾驶路段": "城市路段（选配）" }, false],
    [{ "导航辅助驾驶": "高速导航驾驶辅助 / 城市导航驾驶辅助" }, true],
    [{ "导航辅助驾驶": "城区导航驾驶辅助" }, true],
    [{ "导航辅助驾驶": "高速导航驾驶辅助" }, false],
    [{ "导航辅助驾驶": "城市导航驾驶辅助（选装）" }, false],
    [{ "辅助驾驶路段": "●城市路段 / 高速路段" }, true],
    [{ "辅助驾驶路段": "○城市路段 / 高速路段" }, false],
    [{ "辅助驾驶路段": "不支持城市路段 / 高速路段" }, false],
    [{ "辅助驾驶路段": "高速路段" }, false],
    [{ "辅助驾驶路段": "●" }, false],
    [{ "辅助驾驶路段": "城市路段（选装）" }, false],
    [{ "辅助驾驶路段": "城区路段", "NOA城市领航": "不支持" }, false],
    [{ "导航辅助驾驶": "城市地图|城市导航" }, false],
    [{ "地图导航": "城市领航", "销售说明": "NOA城市领航" }, false],
    [{ "NOA城市领航": "●" }, true],
    [{ "城市领航辅助": "支持" }, true],
    [{ "NOA城市领航": "未知" }, false],
    [{ "NOA城市领航": "选装" }, false],
    [{ "导航辅助驾驶": "城市领航（选装）" }, false],
    [{ "NOA城市领航": "不支持", "导航辅助驾驶": "城市领航" }, false],
    [{ "NOA城市领航": "未知", "导航辅助驾驶": "城市领航" }, true]
  ].forEach(([input, expected]) => assert.equal(hooks.conditionMatches(input, condition), expected, JSON.stringify(input)));
});

test("city alias denial survives display normalization and optional one-hot values stay unproven", () => {
  const { hooks, condition } = strictFilterContext("city_navigation");
  const original = Object.freeze(Object.assign(row("懂车帝", 2026, "城市否定冲突"), {
    "城市领航辅助": "不支持", "导航辅助驾驶": "高快领航|城市领航"
  }));
  const before = JSON.stringify(original);
  hooks.initializeRows([original]);
  assert.equal(hooks.state.rows[0]["城市领航辅助"], "不支持");
  assert.equal(hooks.conditionMatches(hooks.state.rows[0], condition), false);
  assert.equal(JSON.stringify(original), before);
  ["选装", "不支持", "○"].forEach((value) => {
    const normalized = hooks.normalizeRowColumns([{ "导航辅助驾驶 - 城市领航": value }])[0];
    assert.equal(hooks.conditionMatches(normalized, condition), false, value);
  });
  const standard = hooks.normalizeRowColumns([{ "导航辅助驾驶 - 城市领航": "●" }])[0];
  assert.equal(hooks.conditionMatches(standard, condition), true);
  const denied = hooks.normalizeRowColumns([{
    "NOA城市领航 - 城市领航": "不支持", "导航辅助驾驶": "城市领航"
  }])[0];
  assert.equal(hooks.conditionMatches(denied, condition), false, "dedicated one-hot denial cannot be rescued by generic navigation");
});

test("SKU display merging preserves typed negative evidence without changing raw identities", () => {
  const { hooks, condition, config } = strictFilterContext("city_navigation");
  const inputs = [
    Object.assign(row("汽车之家", 2026, "同一车型"), { "车款ID": "887766", "NOA城市领航": "●", "远程控制": "支持" }),
    Object.assign(row("懂车帝", 2026, "同一车型"), { "车款ID": "887766", "NOA城市领航": "不支持", "远程控制": "选装", "手机APP远程功能": "空调控制" })
  ];
  const before = JSON.stringify(inputs);
  hooks.initializeRows(inputs);
  assert.equal(hooks.state.rows.length, 1, "the same SKU still merges once");
  assert.equal(hooks.state.rows[0]["车款ID"], "887766");
  assert.equal(hooks.conditionMatches(hooks.state.rows[0], condition), false);
  hooks.state.featureFilters.remote_control = true;
  const control = config.conditions.find((item) => item.id === "remote_control");
  assert.equal(hooks.conditionMatches(hooks.state.rows[0], control), true, "independent standard operation survives the optional source");
  delete hooks.state.rows[0]["手机APP远程功能"];
  assert.equal(hooks.conditionMatches(hooks.state.rows[0], control), false, "support plus optional in the same source column is not standard");
  assert.equal(JSON.stringify(inputs), before);
});

test("sentry mode requires dedicated affirmative evidence instead of camera or recorder fields", () => {
  const { hooks, condition } = strictFilterContext("sentry_mode");
  const matches = (row) => hooks.conditionMatches(row, condition);
  assert.equal(matches({ "摄像头": "哨兵模式" }), false);
  assert.equal(matches({ "行车记录仪": "支持千里眼" }), false);
  assert.equal(matches({ "哨兵模式": "●" }), true);
  assert.equal(matches({ "哨兵模式/千里眼": "标配" }), true);
  assert.equal(matches({ "千里眼": "是" }), true);
  assert.equal(matches({ "哨兵(千里眼)模式": "支持" }), true);
  assert.equal(matches({ "哨兵（千里眼）模式": "懂车帝:支持|易车:待查" }), true,
    "未知来源段不能抹掉另一来源的明确肯定");
  assert.equal(matches({ "哨兵模式": "待查" }), false);
  assert.equal(matches({ "哨兵模式": "○" }), false);
  assert.equal(matches({ "哨兵模式": "选装" }), false);
  assert.equal(matches({ "哨兵模式": "无" }), false);
});

test("tire pressure display rejects alarms, monitoring dots, optional equipment and composite packages", () => {
  const { hooks, condition } = strictFilterContext("tire_pressure_display");
  const matches = (row) => hooks.conditionMatches(row, condition);
  assert.equal(matches({ "胎压监测系统": "●" }), false, "笼统的监测●不能证明胎压显示");
  assert.equal(matches({ "胎压监测系统": "胎压报警" }), false);
  assert.equal(matches({ "胎压报警": "●" }), false);
  assert.equal(matches({ "胎压监测功能": "支持胎压监测" }), false);
  assert.equal(matches({ "胎压显示": "选装" }), false);
  assert.equal(matches({ "胎压显示": "选配" }), false);
  assert.equal(matches({ "胎压显示": "○" }), false);
  assert.equal(matches({ "精品礼包": "胎压显示+脚垫" }), false, "礼包复合字段不能证明单项已配备");
});

test("tire pressure display accepts explicit generic values and rejects source conflicts", () => {
  const { hooks, condition } = strictFilterContext("tire_pressure_display");
  const matches = (row) => hooks.conditionMatches(row, condition);
  assert.equal(matches({ "胎压监测系统": "胎压显示" }), true);
  assert.equal(matches({ "胎压监测功能": "懂车帝:胎压显示|易车:未知" }), true);
  assert.equal(matches({ "胎压显示": "●" }), true);
  assert.equal(matches({ "胎压显示功能": "标配" }), true);
  assert.equal(matches({ "胎压监测系统": "懂车帝:胎压显示|易车:不支持" }), false);
  assert.equal(matches({ "胎压显示": "懂车帝:●|易车:选装" }), false);
});

test("phone-key negative evidence survives initializeRows and stays isolated by technology", () => {
  const { hooks, condition } = strictFilterContext("bluetooth_key");
  [
    [{ "手机蓝牙钥匙": "不支持", "遥控钥匙类型": "手机蓝牙钥匙" }, false],
    [{ "UWB钥匙": "选装", "遥控钥匙类型": "UWB数字钥匙" }, false],
    [{ "手机蓝牙钥匙": "不支持", "UWB钥匙": "●" }, true],
    [{ "UWB钥匙": "不支持", "手机蓝牙钥匙": "●" }, true],
    [{ "手机蓝牙钥匙": "不支持", "UWB钥匙": "不支持", "遥控钥匙类型": "手机蓝牙钥匙|UWB数字钥匙" }, false],
    [{ "蓝牙/数字钥匙": "NFC钥匙|数字钥匙" }, false],
    [{ "蓝牙": "●" }, false]
  ].forEach(([fields, expected]) => {
    const source = Object.freeze(Object.assign(row("懂车帝", 2026, "钥匙管线反例"), fields));
    const before = JSON.stringify(source);
    hooks.initializeRows([source]);
    assert.equal(hooks.state.rows.length, 1);
    assert.equal(hooks.conditionMatches(hooks.state.rows[0], condition), expected, JSON.stringify(fields));
    ["手机蓝牙钥匙", "UWB钥匙"].forEach((field) => {
      if (Object.hasOwn(fields, field)) assert.equal(hooks.state.rows[0][field], fields[field], "dedicated evidence must survive preparation");
    });
    assert.equal(JSON.stringify(source), before);
  });
});

test("typed App startup actions survive initializeRows without admitting unrelated phone operations", () => {
  const { hooks, condition, config } = strictFilterContext("remote_start");
  const control = config.conditions.find((item) => item.id === "remote_control");
  [
    [{ "手机APP远程功能": "车辆启动" }, true],
    [{ "手机App远程控制": "发动机启动" }, true],
    [{ "手机App远程控制": "远程启动|车况查询" }, true],
    [{ "手机App远程控制": "远程控制" }, false],
    [{ "手机App远程控制": "●" }, false],
    [{ "手机APP远程功能": "支持" }, false],
    [{ "手机App远程控制": "车门控制" }, false],
    [{ "手机App远程控制": "车辆监控|服务预约" }, false],
    [{ "手机App远程控制": "车辆启动|选装" }, false],
    [{ "远程启动功能": "不支持", "手机APP远程功能": "车辆启动" }, false],
    [{ "远程启动": "选装", "手机App远程控制": "发动机启动" }, false],
    [{ "销售说明": "车辆启动" }, false],
    [{ "手机App远程控制 - 车辆启动": "●" }, true],
    [{ "手机App远程控制 - 车辆启动": "选装" }, false]
  ].forEach(([fields, expected]) => {
    const source = Object.freeze(Object.assign(row("懂车帝", 2026, "启动管线反例"), fields));
    const before = JSON.stringify(source);
    hooks.initializeRows([source]);
    hooks.state.featureFilters.remote_control = true;
    assert.equal(hooks.conditionMatches(hooks.state.rows[0], condition), expected, JSON.stringify(fields));
    if (fields["手机App远程控制"] === "发动机启动") {
      assert.equal(hooks.conditionMatches(hooks.state.rows[0], control), true, "an explicit App startup is also an actual phone operation");
    }
    assert.equal(JSON.stringify(source), before);
  });
});

test("phone key accepts either Bluetooth or UWB and requires technology evidence", () => {
  const { hooks, condition } = strictFilterContext("bluetooth_key");
  const matches = (row) => hooks.conditionMatches(row, condition);
  assert.equal(matches({ "蓝牙/数字钥匙": "手机蓝牙钥匙|NFC钥匙" }), true);
  assert.equal(matches({ "遥控钥匙类型": "懂车帝:UWB数字钥匙" }), true);
  assert.equal(matches({ "UWB钥匙": "选装", "手机蓝牙钥匙": "●" }), true);
  assert.equal(matches({ "UWB钥匙": "不支持", "蓝牙/数字钥匙": "UWB数字钥匙" }), false);
  assert.equal(matches({ "蓝牙/数字钥匙": "NFC钥匙|数字钥匙" }), false);
  assert.equal(matches({ "蓝牙/数字钥匙": "支持" }), false);
  assert.equal(matches({ "销售说明": "UWB数字钥匙" }), false);
  assert.equal(matches({ "蓝牙": "●" }), false);
  assert.equal(matches({ "遥控钥匙类型": "遥控钥匙 / 蓝牙钥匙" }), true);
  assert.equal(matches({ "遥控钥匙类型": "○ 暂无价格|手机蓝牙钥匙" }), false);
  assert.equal(matches({ "遥控钥匙类型": "懂车帝:○ 暂无价格|手机蓝牙钥匙|易车:UWB数字钥匙" }), true);
  assert.equal(matches({ "蓝牙/数字钥匙": "○|手机蓝牙钥匙|●|UWB数字钥匙" }), true);
  assert.equal(matches({ "蓝牙/数字钥匙": "汽车之家:遥控钥匙 / 蓝牙钥匙|懂车帝:●|○ 599元" }), true);

  hooks.initializeRows([Object.assign(row("易车", 2026, "UWB 钥匙"), {
    "级别": "中型车", "UWB钥匙": "●"
  })]);
  assert.equal(matches(hooks.state.rows[0]), true);
});

test("BEV heat pump filtering requires dedicated affirmative evidence", () => {
  const { hooks, condition } = strictFilterContext("bev_heat_pump");
  const matches = (row) => hooks.conditionMatches(row, condition);
  assert.equal(matches({ "能源类型": "纯电动", "热泵空调": "●" }), true);
  assert.equal(matches({ "能源类型": "懂车帝:纯电动", "热泵管理系统": "支持" }), true);
  assert.equal(matches({ "能源类型": "纯电动", "CO2热泵空调包": "标配" }), true);
  assert.equal(matches({ "能源类型": "纯电动", "热泵空调": "无" }), false);
  assert.equal(matches({ "能源类型": "纯电动", "热泵空调": "○" }), false);
  assert.equal(matches({ "能源类型": "纯电动", "热泵空调": "待查" }), false);
  assert.equal(matches({ "能源类型": "纯电动" }), false);
  assert.equal(matches({ "能源类型": "纯电动", "220V后备箱电源+热泵空调礼包": "支持" }), false,
    "复合礼包字段不能单独证明热泵空调");
  assert.equal(matches({ "能源类型": "纯电动", "热泵空调": "懂车帝:标配|易车:选装" }), false);
});

test("known non-BEV energy types are exempt without heat pump evidence", () => {
  const { hooks, condition } = strictFilterContext("bev_heat_pump");
  const matches = (energy) => hooks.conditionMatches({ "能源类型": energy }, condition);
  ["插电式混合动力", "增程式", "增程式纯电动", "油电混合", "汽油", "柴油", "48V轻混", "氢燃料"]
    .forEach((energy) => assert.equal(matches(energy), true, energy + " 不应被热泵条件误限"));
  assert.equal(matches("懂车帝:增程式纯电动"), true, "增程式纯电动是增程，不能读成 BEV");
});

test("mixed BEV energy cannot bypass heat pump while unknown energy needs explicit evidence", () => {
  const { hooks, condition } = strictFilterContext("bev_heat_pump");
  const matches = (energy, heat) => hooks.conditionMatches(
    Object.assign({ "能源类型": energy }, heat ? { "热泵空调": heat } : {}), condition);
  assert.equal(matches("纯电动|插电式混合动力"), false);
  assert.equal(matches("纯电动/插电式混合动力"), false);
  assert.equal(matches("纯电动|插电式混合动力", "●"), true);
  assert.equal(matches("增程式纯电动|纯电动"), false, "混合来源含 BEV 不能借增程绕过");
  assert.equal(matches("未知"), false);
  assert.equal(matches("待查"), false);
  assert.equal(matches("未知", "●"), true);
  assert.equal(matches("", "●"), true, "缺失能源类型时只接受明确热泵肯定");
  assert.equal(matches(""), false);
});

test("strict filters reject source-positive/source-negative conflicts while retaining unknown plus positive", () => {
  const sentry = strictFilterContext("sentry_mode");
  assert.equal(sentry.hooks.conditionMatches({ "哨兵模式": "懂车帝:支持|易车:待查" }, sentry.condition), true);
  assert.equal(sentry.hooks.conditionMatches({ "哨兵模式": "懂车帝:未知|易车:●" }, sentry.condition), true);
  assert.equal(sentry.hooks.conditionMatches({ "哨兵模式": "懂车帝:支持|易车:无" }, sentry.condition), false);
  assert.equal(sentry.hooks.conditionMatches({ "哨兵模式": "懂车帝:○|易车:待查" }, sentry.condition), false);
  const tire = strictFilterContext("tire_pressure_display");
  assert.equal(tire.hooks.conditionMatches({ "胎压监测系统": "懂车帝:胎压显示|易车:未知" }, tire.condition), true);
  assert.equal(tire.hooks.conditionMatches({ "胎压监测系统": "懂车帝:胎压显示|易车:不支持" }, tire.condition), false);
  assert.equal(tire.hooks.conditionMatches({ "胎压监测系统": "懂车帝:胎压显示|易车:选装" }, tire.condition), false);
  const heat = strictFilterContext("bev_heat_pump");
  assert.equal(heat.hooks.conditionMatches({ "能源类型": "纯电动", "热泵空调": "懂车帝:标配|易车:待查" }, heat.condition), true);
  assert.equal(heat.hooks.conditionMatches({ "能源类型": "纯电动", "热泵空调": "懂车帝:标配|易车:○" }, heat.condition), false);
});

test("three strict filters default on, remain independently disableable, and keep both configs and taxonomy aligned", () => {
  const app = loadAppForTest();
  const hooks = app.hooks;
  const configPath = path.join(__dirname, "..", "config", "filter_conditions.json");
  const docsPath = path.join(__dirname, "..", "docs", "filter_conditions.json");
  const configText = fs.readFileSync(configPath, "utf8");
  assert.equal(configText, fs.readFileSync(docsPath, "utf8"), "两份筛选配置必须逐字相同");
  const config = JSON.parse(configText);
  const ids = ["sentry_mode", "tire_pressure_display", "bev_heat_pump"];
  ids.forEach((id) => {
    const condition = config.conditions.find((item) => item.id === id);
    assert.ok(condition, "缺少新条件：" + id);
    assert.equal(condition.type, "feature");
    assert.equal(condition.defaultEnabled, true);
    hooks.state.config = config;
    hooks.state.featureFilters[id] = true;
    assert.equal(hooks.conditionMatches({}, condition), false, id + " 开启时无证据应拒绝");
    hooks.state.featureFilters[id] = false;
    assert.equal(hooks.conditionMatches({}, condition), true, id + " 关闭后应放行");
  });
  const assist = config.filterTaxonomy.find((category) => category.id === "assist");
  const safety = assist.sections.find((section) => section.id === "safety");
  assert.equal(safety.label, "安全与制动辅助");
  assert.deepEqual(safety.conditionIds, ["sentry_mode", "tire_pressure_display"]);
  assert.deepEqual(assist.sections.find((section) => section.id === "navigation").conditionIds, ["city_navigation"]);
  const climate = config.filterTaxonomy.find((category) => category.id === "interior")
    .sections.find((section) => section.id === "climate");
  assert.equal(climate.label, "空调与空气");
  assert.deepEqual(climate.conditionIds, ["bev_heat_pump"]);
  assert.ok(config.conditions.some((condition) => condition.id === "auto_headlight" && condition.label === "自动头灯"),
    "旧条件与标题必须保留");
  hooks.state.config = config;
  hooks.initializeRows([Object.assign(row("易车", 2026, "默认三项"), { "级别": "中型车" })]);
  ids.forEach((id) => assert.equal(hooks.state.featureFilters[id], true, "加载配置后应默认勾选：" + id));
  hooks.state.rangeFilters = {};
  hooks.state.featureFilters = { sentry_mode: true, tire_pressure_display: true, bev_heat_pump: true };
  assert.equal(hooks.getFilteredRows().length, 0, "默认三项应共同参与共享结果路径");
  hooks.state.featureFilters = {};
  assert.equal(hooks.getFilteredRows().length, 1, "三项全部关闭后同一车型应放行");
});

test("strict equipment evidence rejects negative compounds before feature words", () => {
  const sentry = strictFilterContext("sentry_mode");
  assert.equal(sentry.hooks.conditionMatches({ "哨兵模式": "不具备哨兵模式" }, sentry.condition), false);
  const tire = strictFilterContext("tire_pressure_display");
  assert.equal(tire.hooks.conditionMatches({ "胎压监测功能": "不带胎压显示" }, tire.condition), false);
  const heat = strictFilterContext("bev_heat_pump");
  assert.equal(heat.hooks.conditionMatches({ "能源类型": "纯电动", "热泵空调": "未标配" }, heat.condition), false);
});

test("legacy desktop groups include each strict condition exactly once in its real group", () => {
  const { hooks } = loadAppForTest();
  const config = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "config", "filter_conditions.json"), "utf8"));
  hooks.state.config = config;
  const groups = hooks.desktopConditionGroups();
  assert.deepEqual(groups.map((group) => group.id), ["performance", "smart", "comfort"]);
  const expected = {
    sentry_mode: ["smart"],
    tire_pressure_display: ["smart"],
    bev_heat_pump: ["comfort"]
  };
  Object.keys(expected).forEach((id) => {
    const owners = groups.filter((group) => group.conditionIds.includes(id)).map((group) => group.id);
    assert.deepEqual(owners, expected[id], id + " 必须且只能出现在实际 legacy desktop 分组一次");
  });
  assert.equal(new Set(groups.flatMap((group) => group.conditionIds)).size,
    groups.reduce((total, group) => total + group.conditionIds.length, 0),
    "legacy desktop 分组内不得重复分配条件");
});
test("common observed property headers use exact existing three-level taxonomy paths", () => {
  const { hooks } = loadAppForTest();
  hooks.state.config = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "config", "filter_conditions.json"), "utf8"));
  const paths = {
    "厂商": "basic/identity",
    "经销商参考价": "basic/budget",
    "整车质保": "basic/ownership",
    "整车保修期限": "basic/ownership",
    "最大功率(kW)": "power/energy",
    "最大扭矩(N·m)": "power/energy",
    "最大净功率(kW)": "power/energy",
    "供油方式": "power/energy",
    "配气机构": "power/energy",
    "缸盖材料": "power/energy",
    "缸体材料": "power/energy",
    "助力类型": "chassis/running",
    "驻车制动类型": "chassis/running"
  };
  Object.entries(paths).forEach(([column, expected]) => {
    assert.equal(hooks.columnPath(column).id, expected, column);
  });
});

test("property taxonomy does not classify raw values or merge dealer and manufacturer facts", () => {
  const { hooks } = loadAppForTest();
  hooks.state.config = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "config", "filter_conditions.json"), "utf8"));
  ["350", "铝合金", "电子液压助力", "三年或10万公里"].forEach((value) => {
    assert.ok(hooks.columnPath(value).id.startsWith("unclassified/"), value);
  });
  // Synthetic values exercise field separation; these are not source observations.
  const original = { "品牌": "合成品牌", "厂商": "合成厂商", "官方指导价": "35.80万", "经销商参考价": "33.8万" };
  const normalized = hooks.normalizeRowColumns([original])[0];
  Object.entries(original).forEach(([column, value]) => assert.equal(normalized[column], value));
});

test("earlier broad category patterns never outrank a later exact declared column", () => {
  const { hooks } = loadAppForTest();
  hooks.state.config = {
    conditions: [],
    filterTaxonomy: [
      { id: "outer", label: "外层", sections: [{ id: "body", label: "车身", columnPatterns: ["^车窗|^车门"] }] },
      { id: "inner", label: "内层", sections: [{ id: "glazing", label: "玻璃", columns: ["车窗防夹手功能"] }] }
    ]
  };
  assert.equal(hooks.columnPath("车窗防夹手功能").id, "inner/glazing");
  assert.equal(hooks.columnPath("车窗装饰条").id, "outer/body", "未声明项仍走原正则");
  assert.equal(hooks.columnPath("车门开启方式").id, "outer/body");
});
test("later exact condition fields outrank broad patterns while exact ties keep configured order", () => {
  const { hooks } = loadAppForTest();
  hooks.state.config = {
    conditions: [
      { id: "remote_start", type: "feature", field: "远程启动", fields: ["远程启动", "发动机远程启动"] },
      { id: "msrp", type: "range", field: "官方指导价" }
    ],
    filterTaxonomy: [
      { id: "power", label: "动力", sections: [{ id: "energy", label: "动力与能源", columnPatterns: ["^发动机|远程"] }] },
      { id: "external", label: "外部", sections: [{ id: "remote", label: "远程与钥匙", conditionIds: ["remote_start"], columnPatterns: ["钥匙"] }] },
      { id: "basic", label: "基本信息", sections: [{ id: "budget", label: "价格", conditionIds: ["msrp"] }] }
    ]
  };
  assert.equal(hooks.columnPath("发动机远程启动").id, "external/remote", "条件 fields 精确命中优先于前面类别正则");
  assert.equal(hooks.columnPath("远程启动").id, "external/remote", "条件 field 精确命中同样优先");
  assert.equal(hooks.columnPath("官方指导价").id, "basic/budget", "较后 section 的条件 field 生效");
  assert.equal(hooks.columnPath("发动机型号").id, "power/energy", "无精确声明时仍按原正则顺序");
  assert.equal(hooks.columnPath("远程钥匙").id, "power/energy", "正则阶段仍按原顺序先到先得");
  const tie = loadAppForTest();
  tie.hooks.state.config = {
    conditions: [],
    filterTaxonomy: [
      { id: "first", label: "先", sections: [{ id: "one", label: "先声明", columns: ["远程启动"] }] },
      { id: "second", label: "后", sections: [{ id: "two", label: "后声明", columns: ["远程启动"] }] }
    ]
  };
  assert.equal(tie.hooks.columnPath("远程启动").id, "first/one", "同级精确命中仍保留配置原顺序");
});
test("the 36 observed property headers resolve through exact declared sections and both config mirrors stay byte-identical", () => {
  const configBytes = fs.readFileSync(path.join(__dirname, "..", "config", "filter_conditions.json"));
  const docsBytes = fs.readFileSync(path.join(__dirname, "..", "docs", "filter_conditions.json"));
  assert.ok(configBytes.equals(docsBytes), "两份配置镜像必须字节一致");
  const config = JSON.parse(configBytes.toString("utf8"));
  const { hooks } = loadAppForTest();
  hooks.state.config = config;
  const expected = {
    "数据来源": "basic/source",
    "车体结构": "external/body",
    "车身结构": "external/body",
    "车门开启方式": "external/body",
    "前制动器类型": "chassis/running",
    "后制动器类型": "chassis/running",
    "驱动形式": "chassis/running",
    "转向类型": "chassis/running",
    "变速箱类型": "chassis/running",
    "挡位数": "chassis/running",
    "ABS防抱死": "assist/safety",
    "驾驶辅助影像": "assist/navigation",
    "巡航系统": "assist/navigation",
    "近光灯": "lighting/headlights",
    "远光灯": "lighting/headlights",
    "日间行车灯": "lighting/headlights",
    "大灯延时关闭": "lighting/headlights",
    "扬声器数量": "hardware/cockpit",
    "车内化妆镜": "interior/convenience",
    "后排杯架": "interior/convenience",
    "无钥匙启动": "external/remote",
    "车内中控锁": "external/remote",
    "车窗防夹手功能": "glass/glazing",
    "内后视镜功能": "glass/mirrors",
    "车内PM2.5过滤装置": "interior/climate",
    "排量(L)": "power/energy",
    "排量(mL)": "power/energy",
    "气缸排列形式": "power/energy",
    "最大马力(Ps)": "power/energy",
    "气缸数": "power/energy",
    "环保标准": "power/energy",
    "燃油标号": "power/energy",
    "发动机型号": "power/energy",
    "进气形式": "power/energy",
    "最大功率转速(rpm)": "power/energy",
    "最大扭矩转速(rpm)": "power/energy"
  };
  assert.equal(Object.keys(expected).length, 36, "36 个真实属性");
  const declared = new Map();
  config.filterTaxonomy.forEach((category) => (category.sections || []).forEach((section) => {
    (section.columns || []).forEach((column) => declared.set(column, category.id + "/" + section.id));
  }));
  Object.keys(expected).forEach((column) => {
    assert.equal(declared.get(column), expected[column], "必须在 section.columns 精确声明：" + column);
  });
  Object.entries(expected).forEach(([column, target]) => {
    assert.equal(hooks.columnPath(column).id, expected[column], column);
    assert.equal(hooks.columnPath(column).major, config.filterTaxonomy.find((category) => category.id === target.split("/")[0]).label, column);
  });
  assert.equal(config.filterTaxonomy.length, 10, "不新增类别");
  config.filterTaxonomy.forEach((category) => assert.ok((category.sections || []).length > 0, category.id));
});
test("declared property names never promote observed values and keep row facts intact", () => {
  const { hooks } = loadAppForTest();
  hooks.state.config = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "config", "filter_conditions.json"), "utf8"));
  ["非承载式", "承载式", "碟式", "通风盘式", "涡轮增压", "2.0", "国VI", "92号", "支持", "●", "8", "L", "6喇叭", "自动防眩目", "1997"]
    .forEach((value) => assert.equal(hooks.columnPath(value).major, "未分类/待确认", value));
  assert.match(hooks.columnPath("2.0").minor, /疑似属性值/, "数字取值仍标疑似");
  assert.match(hooks.columnPath("支持").minor, /疑似属性值/);
  assert.equal(hooks.columnPath("车窗防夹手功能").id, "glass/glazing");
  assert.equal(hooks.columnPath("车窗装饰条").id, "external/body", "只声明精确名，不靠新正则扩散");
  const energy = hooks.state.config.filterTaxonomy.find((category) => category.id === "power")
    .sections.find((section) => section.id === "energy");
  assert.equal(energy.columns.filter((column) => column === "排量(L)").length, 1, "排量(L) 独立声明一次");
  assert.equal(energy.columns.filter((column) => column === "排量(mL)").length, 1, "排量(mL) 独立声明一次");
  assert.equal(energy.columns.includes("排量"), false, "单位不合并");
  assert.equal(JSON.stringify(hooks.state.config.conditions).includes("无钥匙启动"), false, "无钥匙启动不是远程启动");
  const remoteStart = hooks.state.config.conditions.find((condition) => condition.id === "remote_start");
  assert.deepEqual(remoteStart.fields, ["远程启动", "远程启动功能", "发动机远程启动"], "核心条件不改");
  assert.equal(hooks.state.config.hiddenByDefault.includes("ABS防抱死"), true, "隐藏默认值不改");
  assert.equal(hooks.state.config.defaultVisibleColumns.includes("无钥匙启动"), false, "默认展示列不改");
  const original = { "排量(L)": "2.0", "排量(mL)": "1997", "官方指导价": "35.80万", "环保标准": "国VI",
    "燃油标号": "92号", "进气形式": "涡轮增压", "无钥匙启动": "标配", "车窗防夹手功能": "标配" };
  const normalized = hooks.normalizeRowColumns([Object.assign({}, original)])[0];
  Object.entries(original).forEach(([column, value]) => assert.equal(normalized[column], value, column));
});


test("native HTML colSpan zero clamping cannot add phantom columns to the three-level header", () => {
  const descriptor = Object.getOwnPropertyDescriptor(FakeElement.prototype, "colSpan");
  const spans = new WeakMap();
  // Native production th.colSpan clamps the old assignment 0 to 1; the old fake did not.
  Object.defineProperty(FakeElement.prototype, "colSpan", {
    configurable: true,
    get() { return spans.has(this) ? spans.get(this) : 1; },
    set(value) { spans.set(this, Math.max(1, Number(value) || 1)); }
  });
  try {
    const fixtures = [
      { columns: ["品牌", "车型名称", "车窗防夹手功能"], major: [["基本信息", 2], ["玻璃/后视镜", 1]] },
      { columns: ["品牌", "数据来源", "车内化妆镜", "后排杯架"], major: [["基本信息", 2], ["内饰与舒适", 2]] },
      { columns: [], major: [] }
    ];
    fixtures.forEach(({columns, major}) => {
      const app = loadAppForTest();
      app.hooks.state.config = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "config", "filter_conditions.json"), "utf8"));
      app.hooks.state.columns = columns;
      app.hooks.state.visibleColumns = new Set(columns);
      app.hooks.renderTableHead();
      const rows = app.elements.get("tableHead").children;
      assert.equal(rows.length, 4);
      assert.deepEqual(rows[0].children.map(cell => [cell.textContent, cell.colSpan]), major);
      for (const index of [0, 1]) {
        assert.equal(rows[index].children.reduce((sum, cell) => sum + cell.colSpan, 0), columns.length,
          "every grouping row must cover exactly the real leaf-column count");
      }
      assert.equal(rows[2].children.length, columns.length);
      assert.equal(rows[3].children.length, columns.length);
    });
  } finally {
    if (descriptor) Object.defineProperty(FakeElement.prototype, "colSpan", descriptor);
    else delete FakeElement.prototype.colSpan;
  }
});

test("known remote-operation parents prove startup only through explicit start actions", () => {
  const { hooks, condition } = strictFilterContext("remote_start");
  const parents = ["远程控制", "远程操控", "远程控制功能", "手机远程控制"];
  parents.forEach((parent) => {
    [
      ["车门控制 / 车窗控制 / 车辆启动 / 充电管理 / 空调控制 / 车况查询/诊断", true],
      ["发动机启动", true], ["远程启动", true],
      ["车门控制 / 空调控制 / 车况查询/诊断", false],
      ["远程控制", false], ["支持", false], ["●", false],
      ["车辆启动|选装", false], ["车辆启动|不支持", false]
    ].forEach(([value, expected]) => {
      const input = Object.freeze(Object.assign(row("汽车之家", 2026, "已知远程操作父列"), { [parent]: value }));
      const before = JSON.stringify(input);
      hooks.initializeRows([input]);
      assert.equal(hooks.conditionMatches(hooks.state.rows[0], condition), expected, parent + ":" + value);
      assert.equal(JSON.stringify(input), before);
    });
    hooks.initializeRows([Object.assign(row("汽车之家", 2026, "启动否定"), { [parent]: "车辆启动", "远程启动": "不支持" })]);
    assert.equal(hooks.conditionMatches(hooks.state.rows[0], condition), false, "dedicated denial wins");
  });
  hooks.initializeRows([Object.assign(row("汽车之家", 2026, "营销文案"), { "销售说明": "车辆启动" })]);
  assert.equal(hooks.conditionMatches(hooks.state.rows[0], condition), false);
});

test("verified legacy source option groups stay out of the property inventory", () => {
  const { hooks } = loadAppForTest();
  const config = JSON.parse(fs.readFileSync(path.join(__dirname, "../config/filter_conditions.json"), "utf8"));
  hooks.state.config = config;
  const skuRows = [
    { "车系": "英仕派", "安心舒享包PLUS": "○|选配", "座椅记忆": "驾驶位" },
    { "车系": "捷豹E-PACE", "安全控(驾驶辅助包)": "选配" },
    { "车系": "揽胜极光", "安全控(智能驾驶辅助包)": "360°全方位车身影像系统",
      "安全控(智能驾驶辅助包)_1": "自适应巡航ACC", "自适应巡航": "●" },
    { "车系": "熊猫", "安心驾控包": "选配", "安心驾控包_1": "ESP车身稳定控制系统",
      "安芯守护包": "选配", "安芯守护包_1": "宁德时代电池" },
    { "车系": "奥迪S4", "奥迪全方位辅助包 高端版": "选配", "品牌独有驾驶辅助功能": "●" },
  ];
  for (const name of ["安全控(驾驶辅助包)", "安全控(智能驾驶辅助包)", "安全控(智能驾驶辅助包)_1", "安心驾控包", "安心驾控包_1", "安心舒享包PLUS", "安芯守护包", "安芯守护包_1", "奥迪全方位辅助包 高端版"]) {
    assert.equal(hooks.shouldHideColumn(name, skuRows), true, name);
    assert.ok(skuRows.some((row) => Object.hasOwn(row, name)), name);
  }
  for (const name of ["座椅记忆", "自适应巡航", "品牌独有驾驶辅助功能"]) {
    assert.equal(hooks.shouldHideColumn(name, skuRows), false, name);
  }
});

test("legacy package descriptions reuse explicit same-series optional status", () => {
  const { hooks } = loadAppForTest();
  hooks.state.config = { hiddenByDefault: [], dropIfUniformPositive: [] };
  const sourceRows = [
    { "品牌": "哈弗", "车系": "哈弗大狗", "HWA高速智驾辅助包": "汽车之家:选配|易车:○" },
    { "品牌": "哈弗", "车系": "哈弗大狗", "HWA高速智驾辅助包_1": "高速领航、自动变道、前向横穿预警" },
    { "品牌": "大众", "车系": "迈腾PHEV", "前排按摩包": "选配" },
    { "品牌": "大众", "车系": "迈腾PHEV", "前排按摩包_1": "前排按摩、驾驶席记忆、老板键" },
    { "品牌": "大众", "车系": "迈腾PHEV", "老板键": "○" },
    { "品牌": "甲", "车系": "示例", "稀有辅助包": "○" },
    { "品牌": "乙", "车系": "示例", "稀有辅助包_1": "其它品牌的独立功能说明" },
    { "品牌": "甲", "车系": "其他", "底盘增强包": "●" },
    { "品牌": "甲", "车系": "其他", "底盘增强包_1": "明确标配的功能说明" },
    { "品牌": "甲", "车系": "其他", "高速辅助": "选配", "高速辅助_1": "持续保持车道" }
  ];
  for (const name of ["HWA高速智驾辅助包_1", "前排按摩包_1"]) {
    assert.equal(hooks.shouldHideColumn(name, sourceRows), true, name);
  }
  for (const name of ["稀有辅助包_1", "底盘增强包_1", "高速辅助_1", "老板键"]) {
    assert.equal(hooks.shouldHideColumn(name, sourceRows), false, name);
  }
});

test("manufacturer-named option packages and seat variants stay out of displayed columns", () => {
  const { hooks } = loadAppForTest();
  const config = JSON.parse(fs.readFileSync(path.join(__dirname, "../config/filter_conditions.json"), "utf8"));
  hooks.state.config = config;
  const optional = {
    "AMG 动态增强版组件": "选配",
    "科技增强组件_2": "○ 3900元",
    "魏斯阿赫组件": "选配",
    "M碳纤维外装组件": "○",
    "M碳纤维外观组件": "○|选配",
    "前排M碳纤维桶形座椅": "○",
  };
  const row = { "车系": "验证车系", ...optional, "座椅记忆": "驾驶位", "方向盘记忆": "●" };
  for (const name of Object.keys(optional)) {
    assert.equal(hooks.shouldHideColumn(name, [row]), true, name);
    assert.equal(row[name], optional[name]);
  }
  assert.equal(hooks.shouldHideColumn("座椅记忆", [row]), false);
  assert.equal(hooks.shouldHideColumn("方向盘记忆", [row]), false);
});

test("conflicting native and generic IDs on single-source rows expose no source link", () => {
  const { hooks, elements } = loadAppForTest();
  hooks.initializeRows([{
    ...row("仅汽车之家", 2026, "冲突来源车款"),
    "车款ID": "77823", "车款ID_汽车之家": "77981",
  }]);
  assert.equal(hooks.state.rows.length, 1);
  hooks.renderTableBody(hooks.state.rows);
  const details = descendants(elements.get("tableBody")).find(node => node.className === "sku-details");
  details.open = true;
  details.dispatch("toggle");
  assert.equal(descendants(details).filter(node => node.tagName === "A").length, 0);
  assert.ok(descendants(details).some(node => node.textContent === "汽车之家 · 暂无可确认的车款链接"));
});

test("verified cockpit variant names become numeric attributes with equipment status", () => {
  const { hooks } = loadAppForTest();
  const input = [
    {"35.4英寸4K一体远端屏": "懂车帝:●|易车:标配", "中控屏幕尺寸": "15.6"},
    {"48 英寸 Skyline 数字天际线": "●", "远端屏尺寸(in)": "48.0"},
    {"40W外置扬声器": "汽车之家:●", "扬声器数量": "25"},
    {"40W外置扬声器": "○ 2000元", "未核验的60W扬声器": "●"},
    {"40W外置扬声器": "汽车之家:●|易车:不支持"},
  ];
  const out = hooks.normalizeRowColumns(input);
  assert.equal(out[0]["远端屏尺寸(in)"], "懂车帝:35.4|易车:35.4");
  assert.equal(out[0]["中控屏幕尺寸"], "15.6");
  assert.equal(out[1]["远端屏尺寸(in)"], "48.0");
  assert.equal(out[2]["外置扬声器功率(W)"], "汽车之家:40");
  assert.equal(out[2]["扬声器数量"], "25");
  assert.equal(out[3]["40W外置扬声器"], "○ 2000元");
  assert.equal(out[3]["未核验的60W扬声器"], "●");
  assert.equal(out[4]["外置扬声器功率(W)"], undefined);
  assert.equal(out[4]["40W外置扬声器"], "汽车之家:●|易车:不支持");
  assert.equal(input[0]["35.4英寸4K一体远端屏"], "懂车帝:●|易车:标配");
  assert.equal(out[0]["35.4英寸4K一体远端屏"], undefined);
  assert.equal(out[1]["48 英寸 Skyline 数字天际线"], undefined);
  assert.equal(out[2]["40W外置扬声器"], undefined);
});

test("verified MONA catalog pair retains both links and rejects identity drift", () => {
  const { hooks, elements } = loadAppForTest();
  hooks.state.config = JSON.parse(fs.readFileSync(path.join(__dirname, "../config/filter_conditions.json"), "utf8"));
  const pair = hooks.state.config.verifiedCatalogSkuPairs.find(item => item.autohomeId === "79491");
  const fields = { "车系": pair.autohomeSeries, "品牌": pair.brand,
    "官方指导价": "16.48万", "上市时间": "2026-10-29" };
  const left = { ...row("仅汽车之家", 2027, pair.autohomeName), ...fields, "车系ID": "8662",
    "车款ID": "79491", "车款ID_汽车之家": "79491", "能源类型": "纯电动", "纯电续航(km)": "CLTC:635" };
  const right = { ...row("仅懂车帝", 2027, pair.dongchediName), ...fields, "车系ID": "26149",
    "懂车帝车型ID": "263234", "上市时间": "2026.10", "纯电续航(km)": "0" };
  hooks.initializeRows([left, right]);
  assert.equal(hooks.state.rows.length, 1);
  assert.equal(hooks.state.rows[0]["交叉核验"], "双源核验");
  hooks.renderTableBody(hooks.state.rows);
  const details = descendants(elements.get("tableBody")).find(node => node.className === "sku-details");
  details.open = true;
  details.dispatch("toggle");
  assert.deepEqual(descendants(details).filter(node => node.tagName === "A").map(node => node.href).sort(), [
    "https://car.autohome.com.cn/config/spec/79491.html",
    "https://www.dongchedi.com/auto/params-carIds-263234",
  ]);
  for (const changed of [
    { "车型名称": "纯电 635 Ultra SE" }, { "上市时间": "2026.11" }, { "车系ID": "26349" },
    { "官方指导价": "17.68万" }, { "能源类型": "增程式" }, { "纯电续航(km)": "CLTC:535" },
    { "车款ID_懂车帝": "263231" },
  ]) {
    hooks.initializeRows([left, { ...right, ...changed }]);
    assert.equal(hooks.state.rows.length, 2, JSON.stringify(changed));
  }
});


test("stock and per-provider sale conflicts override a stale on-sale summary in either order", () => {
  const {hooks}=loadAppForTest();
  const base = {...row("汽车之家",2026,"同车款库存"), "上市时间":"2026.01"};
  const active = {...base, "上市状态":"在售", "上市状态_汽车之家":"在售"};
  const stock = {...base, "上市状态_汽车之家":"停产在售"};
  for (const records of [[active, stock], [stock, active]]) {
    hooks.initializeRows(records);
    assert.equal(hooks.state.rows.length, 1);
    assert.ok(hooks.state.rows[0]["上市状态_汽车之家"].split("|").includes("停产在售"));
    assert.equal(hooks.getFilteredRows().length, 0);
    hooks.state.saleScope="all";
    assert.equal(hooks.getFilteredRows().length, 1);
    hooks.state.saleScope="onSale";
  }
  const combined = {...active, "数据来源":"汽车之家+懂车帝", "上市状态_懂车帝":"停售"};
  hooks.initializeRows([combined, {...base, "车型名称":"可售", "上市状态":"在售", "上市状态_汽车之家":"-"}]);
  assert.deepEqual(Array.from(hooks.getFilteredRows(), row=>row["车型名称"]), ["可售"]);
});

test("SPU card SKU titles strip redundant series prefix, unify leading year, and align within-SPU km units", () => {
  const { elements, hooks } = loadAppForTest();
  hooks.initializeRows([
    Object.assign(row("仅汽车之家", 2026, "红旗天工05 2026款 650 Max版"), {
      "品牌": "红旗", "车系": "红旗天工05", "能源类型": "纯电动", "官方指导价": "17.18万", "纯电续航(km)": "CLTC:650"
    }),
    Object.assign(row("仅易车", 2026, "26款 750km 长续航版"), {
      "品牌": "红旗", "车系": "红旗天工05", "能源类型": "纯电动", "官方指导价": "18.58万", "纯电续航(km)": "CLTC:750"
    }),
    Object.assign(row("仅易车", 2026, "26款 850km 极充性能版"), {
      "品牌": "红旗", "车系": "红旗天工05", "能源类型": "纯电动", "官方指导价": "22.28万", "纯电续航(km)": "CLTC:850"
    }),
    Object.assign(row("仅汽车之家", 2025, "宋L EV 2025款 智驾版 662km 激光雷达卓越型"), {
      "品牌": "比亚迪", "车系": "宋L EV", "能源类型": "纯电动", "官方指导价": "22.58万", "纯电续航(km)": "CLTC:662"
    }),
    Object.assign(row("懂车帝+易车", 2025, "2025款 智驾版 602km 四驱激光雷达型"), {
      "品牌": "比亚迪", "车系": "宋L EV", "能源类型": "纯电动", "官方指导价": "24.98万", "纯电续航(km)": "CLTC:602"
    }),
    Object.assign(row("懂车帝+易车", 2026, "2026款 625 后驱Max"), {
      "品牌": "小鹏汽车", "车系": "小鹏G9", "能源类型": "纯电动", "官方指导价": "24.88万", "纯电续航(km)": "CLTC:625"
    }),
    Object.assign(row("懂车帝+易车", 2026, "2026款 725 后驱Max"), {
      "品牌": "小鹏汽车", "车系": "小鹏G9", "能源类型": "纯电动", "官方指导价": "25.88万", "纯电续航(km)": "CLTC:725"
    }),
    Object.assign(row("汽车之家+懂车帝+易车", 2026, "小鹏G9 2026款 680 四驱 Max"), {
      "品牌": "小鹏汽车", "车系": "小鹏G9", "能源类型": "纯电动", "官方指导价": "27.88万", "纯电续航(km)": "CLTC:680"
    }),
    Object.assign(row("仅汽车之家", 2026, "途昂Pro 450TSI 四驱纵横版"), {
      "品牌": "大众", "车系": "途昂", "能源类型": "汽油", "官方指导价": "29.90万"
    }),
  ]);
  const groups = hooks.groupRowsBySeries(hooks.getFilteredRows());
  groups.forEach((g) => hooks.state.expandedSeries.add(g.key));
  hooks.renderCards(groups);
  const bySeries = new Map();
  elements.get("cardList").children.forEach((card) => {
    const seriesTitle = card.children[0].children[0].textContent;
    const skuTitles = Array.from(card.children[2].children, (item) => item.children[0].textContent);
    bySeries.set(seriesTitle, skuTitles);
  });
  assert.deepEqual(bySeries.get("红旗天工05"), [
    "2026款 650km Max版",
    "2026款 750km 长续航版",
    "2026款 850km 极充性能版",
  ]);
  assert.deepEqual(bySeries.get("宋L EV"), [
    "2025款 智驾版 662km 激光雷达卓越型",
    "2025款 智驾版 602km 四驱激光雷达型",
  ]);
  assert.deepEqual(bySeries.get("小鹏G9"), [
    "2026款 625 后驱Max",
    "2026款 725 后驱Max",
    "2026款 680 四驱 Max",
  ]);
  assert.deepEqual(bySeries.get("途昂"), [
    "2026款 途昂Pro 450TSI 四驱纵横版",
  ]);
});

test("curb_weight core condition defaults to <= 2000 kg and filters multi-source weights safely", () => {
  const { elements, hooks } = loadAppForTest();
  const config = JSON.parse(fs.readFileSync(path.join(__dirname, "../docs/filter_conditions.json"), "utf8"));
  hooks.state.config = config;
  const base = (name, weight) => {
    const item = Object.assign(row("仅懂车帝", 2026, name), {
      "百公里加速(s)": "5.5",
      "最高车速(km/h)": "200",
      "纯电续航(km)": "500",
      "能源类型": "纯电动",
      "长x宽x高(mm)": "4800x1900x1450"
    });
    if (weight !== undefined) { item["整备质量(kg)"] = weight; }
    config.conditions.filter((c) => ["feature", "pagesFeature"].includes(c.type)).forEach((c) => {
      item[c.fields[0]] = c.requireKeyword ? c.keywords[0] : "支持";
    });
    return item;
  };
  hooks.initializeRows([
    base("轻盈版", "1850"),
    base("临界版", "2000"),
    base("超重版", "2001"),
    base("冲突超重版", "汽车之家:1950|懂车帝:2050"),
    base("缺失质量版", undefined),
  ]);
  hooks.renderEverything();
  assert.deepEqual(Array.from(hooks.getFilteredRows(), (item) => item["车型名称"]), ["轻盈版", "临界版"]);
  const tags = elements.get("selectedTags").children.map((tag) => tag.textContent);
  assert.ok(tags.includes("整备质量 ≤2000"));
});

test("value-as-header cleanup folds paren values and hides low-brand option/package leaks while preserving real specs", () => {
  const { hooks } = loadAppForTest();
  const config = JSON.parse(fs.readFileSync(path.join(__dirname, "../docs/filter_conditions.json"), "utf8"));
  hooks.state.config = config;
  const rows = [
    {
      ...row("汽车之家", 2026, "样车A"),
      "品牌": "品牌甲",
      "车系": "车系甲",
      "车内氛围灯": "多色",
      "车内氛围灯(7色)": "●",
      "音响品牌": "Bose",
      "音响品牌(JBL)": "支持",
      "上坡辅助": "标配",
      "上坡辅助(HAC)": "支持",
      "7座 2-2-3布局+二排座椅加热及通风_1": "7座布局、二排航空座椅、三排座椅加热",
      "奥迪专享黑光包_2": "○ 2000元",
      "19英寸AMG双五辐轻合金车轮": "○|选配",
      "前排座椅通风、加热": "前排座椅通风、加热",
      "气罐容积(L)": "90",
      "氢气装载量(kg)": "3.99",
      "电控系统质保": "首任车主终身质保",
      "坦克转弯": "支持"
    },
    {
      ...row("汽车之家", 2026, "样车B"),
      "品牌": "品牌乙",
      "车系": "车系乙",
      "坦克转弯": "●"
    },
    {
      ...row("汽车之家", 2026, "样车C"),
      "品牌": "品牌丙",
      "车系": "车系丙",
      "坦克转弯": "支持"
    }
  ];
  hooks.initializeRows(rows);
  const cols = hooks.state.columns;
  assert.equal(hooks.state.rows[0]["车内氛围灯"], "多色|7色");
  assert.equal(hooks.state.rows[0]["音响品牌"], "Bose|JBL");
  for (const hiddenCol of [
    "车内氛围灯(7色)",
    "音响品牌(JBL)",
    "上坡辅助(HAC)",
    "7座 2-2-3布局+二排座椅加热及通风_1",
    "奥迪专享黑光包_2",
    "19英寸AMG双五辐轻合金车轮",
    "前排座椅通风、加热"
  ]) {
    assert.equal(cols.includes(hiddenCol), false, hiddenCol);
  }
  for (const keptCol of ["气罐容积(L)", "氢气装载量(kg)", "电控系统质保", "坦克转弯", "车内氛围灯", "音响品牌", "上坡辅助"]) {
    assert.equal(cols.includes(keptCol), true, keptCol);
  }
});

test("table mode uses compact classes for brand, series, and short numeric range columns and supports collapsing side column", () => {
  const { elements, hooks, flushFrames } = loadAppForTest();
  hooks.state.config.conditions = [];
  hooks.state.config.defaultVisibleColumns = ["品牌", "车系", "年款", "官方指导价", "车型名称"];
  hooks.initializeRows([
    Object.assign(row("汽车之家", 2026, "2026款 650 Max版"), { "品牌": "红旗", "车系": "红旗天工05", "官方指导价": "17.18万" })
  ]);
  elements.get("tableMode").dispatch("click");
  hooks.renderEverything();
  flushFrames();

  assert.equal(hooks.tableColumnWidthClass("品牌"), "col-compact-brand");
  assert.equal(hooks.tableColumnWidthClass("车系"), "col-compact-series");
  assert.equal(hooks.tableColumnWidthClass("年款"), "col-compact-range");
  assert.equal(hooks.tableColumnWidthClass("官方指导价"), "col-compact-range");
  assert.equal(hooks.tableColumnWidthClass("车型名称"), "");

  const headRows = elements.get("tableHead").children;
  const titleCells = headRows[2].children;
  const filterCells = headRows[3].children;
  assert.equal(titleCells[0].className, "col-compact-brand");
  assert.equal(titleCells[1].className, "col-compact-series");
  assert.equal(titleCells[2].className, "col-compact-range");
  assert.equal(titleCells[3].className, "col-compact-range");
  assert.equal(filterCells[2].className, "col-compact-range");
  assert.equal(filterCells[3].className, "col-compact-range");
  const bodyCells = elements.get("tableBody").children[0].children;
  assert.equal(bodyCells[0].className, "col-compact-brand");
  assert.equal(bodyCells[3].className, "col-compact-range");

  assert.equal(elements.get("columnPanelBody").hidden, false);
  elements.get("toggleColumnPanel").dispatch("click");
  assert.equal(elements.get("columnPanelBody").hidden, true);
  elements.get("toggleColumnPanel").dispatch("click");
  assert.equal(elements.get("columnPanelBody").hidden, false);

  assert.equal(elements.get("sidePanel").hidden, false);
  elements.get("toggleSidePanel").dispatch("click");
  assert.equal(elements.get("sidePanel").hidden, true);
  assert.equal(elements.get("toggleSidePanel").getAttribute("aria-expanded"), "false");
  assert.equal(elements.get("toggleSidePanel").textContent, "展开侧栏");
  assert.ok(String(elements.get("workspace").className).split(/\s+/).includes("side-panel-collapsed"));

  elements.get("centerMode").dispatch("click");
  assert.equal(elements.get("sidePanel").hidden, false);
  elements.get("tableMode").dispatch("click");
  assert.equal(elements.get("sidePanel").hidden, true);

  elements.get("toggleSidePanel").dispatch("click");
  assert.equal(elements.get("sidePanel").hidden, false);
  assert.equal(elements.get("toggleSidePanel").textContent, "隐藏侧栏");
});

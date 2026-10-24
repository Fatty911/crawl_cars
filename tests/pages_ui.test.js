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
      defaultRangeFilters: DEFAULT_RANGE_FILTERS,
      normalizeRowColumns: normalizeRowColumns,
      isEquipmentColumn: isEquipmentColumn,
      shouldHideColumn: shouldHideColumn,
      classifySkuColumns: classifySkuColumns,
      getFilterTaxonomy: getFilterTaxonomy,
      selectedCountForCategory: selectedCountForCategory,
      activateMobileCategory: activateMobileCategory,
      restoreDefaultFilters: restoreDefaultFilters,
      formatDataTimestamp: formatDataTimestamp,
      conditionTagLabel: conditionTagLabel,
      normEnumValue: normEnumValue,
      renderTableBody: renderTableBody,
      exportCurrentCsv: exportCurrentCsv,
      exportCurrentJson: exportCurrentJson,
      state: state
    };
  }());`
  );
  vm.runInNewContext(source, context, { filename: appPath });
  return { elements, hooks: context.window.CARS_TEST_HOOKS, downloads,
    setFetch(fn) { context.fetch = fn; },
    setCrypto(value) { context.window.crypto = value; }
  };
}


test("data generation time formats to minute precision", () => {
  const { hooks } = loadAppForTest();
  // 2026-08-10 11:43 UTC -> local minute precision, no seconds
  const out = hooks.formatDataTimestamp("2026-08-10T11:43:47.546481+00:00");
  assert.match(out, /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/, "YYYY-MM-DD HH:mm");
  assert.ok(!/:\d{2}:\d{2}/.test(out), "no seconds in output");
  assert.equal(hooks.formatDataTimestamp(""), "", "empty iso -> empty");
  assert.equal(hooks.formatDataTimestamp("not-a-date"), "", "invalid iso -> empty");
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
  const merged = hooks.state.rows.find((item) => item["交叉核验"] === "双源核验");
  assert.deepEqual(Array.from(hooks.atomicSources(merged["数据来源"])).sort(), ["易车", "汽车之家"].sort());
  assert.equal(merged["跨源归并ID"], "visible-f-v1:test");
  assert.equal(hooks.state.rows.find((item) => item["交叉核验"] === "单源数据")["车型名称"], unrelated["车型名称"]);
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
  // 这条也要跑在**展示层之后**的行上：输入面里同 ID 多行是常态（跨源各写一行），
  // `mergeVerifiedRows` 正是为此存在——断在输入上等于要求数据层提前做完展示层的活（我第一版就断错了地方）。
  const seenPair = new Set();
  for (const r of hooks.state.rows) {
    const id = String(r["车款ID"] || "").trim();
    if (!id || id === "-") continue;
    const key = id + "\u0000" + norm(r["车型名称"]);
    assert.ok(!seenPair.has(key), `展示层仍留有同车款ID 同名的两行（${id}）⇒ 合并没生效`);
    seenPair.add(key);
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
  assert.deepEqual(Array.from(firstCard.children[2].children, (item) => item.children[0].textContent), ["S2 低配 2026款", "S2 高配 2026款"]);

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

test("On-sale scope switch drops future-listing models and toggles back", () => {
  const { elements, hooks } = loadAppForTest();
  hooks.initializeRows([
    Object.assign(row("汽车之家+懂车帝", 2026, "已上市款"), { "品牌": "A", "车系": "S1", "上市时间": "2025.09" }),
    Object.assign(row("仅懂车帝", 2026, "未来上市款"), { "品牌": "A", "车系": "S2", "上市时间": "2027.03" }),
    Object.assign(row("仅懂车帝", 2026, "缺上市时间款"), { "品牌": "A", "车系": "S3", "上市时间": "-" })
  ]);
  hooks.renderResultsOnly();
  assert.equal(elements.get("saleScopeSection").hidden, false, "数据能区分（有未来上市行）时开关必须出现");
  const all = hooks.getFilteredRows().map((item) => item["车型名称"]);
  assert.equal(all.length, 3, `默认档（全部车型）不该改变结果集：${all}`);

  elements.get("saleScopeOnSale").dispatch("click");
  assert.equal(hooks.getFilteredRows().map((item) => item["车型名称"]).join(","), "已上市款,缺上市时间款");
  assert.equal(elements.get("saleScopeOnSale").className, "segment active");
  assert.equal(elements.get("saleScopeAll").className, "segment");

  elements.get("saleScopeAll").dispatch("click");
  assert.equal(hooks.getFilteredRows().length, 3);
  assert.equal(elements.get("saleScopeAll").className, "segment active");

  // 数据区分不出来时（现网就是这样：没有在售状态列、也没有未来上市时间的行）
  // 必须**隐藏**这个开关，而不是给用户一个按了没反应的空控件。
  const bare = loadAppForTest();
  bare.hooks.initializeRows([
    Object.assign(row("仅懂车帝", 2026, "已上市款"), { "品牌": "A", "车系": "S1", "上市时间": "2025.09" })
  ]);
  assert.equal(bare.elements.get("saleScopeSection").hidden, true);
  assert.equal(bare.hooks.state.saleScope, "all");
});


test("Sale-scope switch needs real discrimination, not merely the status column", () => {
  // 2026-10-16 浏览器实测：修好"发布身份列被裁掉"之后，面上有了 `易车上市状态` 列，
  // 但爬取阶段只放进售车款 ⇒ 该列恒为 `approved`。当时的开关按下去 99 车系 / 470 行一模一样，
  // 又变回"按了没反应的空控件"。所以判据要认的是**值有区分度**，不是列的存在。
  const constant = loadAppForTest();
  constant.hooks.initializeRows([
    Object.assign(row("懂车帝+易车", 2026, "在售款甲"), { "品牌": "A", "车系": "S1", "上市时间": "2025.09", "易车上市状态": "approved" }),
    Object.assign(row("仅易车", 2026, "在售款乙"), { "品牌": "A", "车系": "S2", "上市时间": "2024.05", "易车上市状态": "approved" })
  ]);
  constant.hooks.renderResultsOnly();
  assert.equal(constant.elements.get("saleScopeSection").hidden, true,
    "状态列恒为 approved（=没有负值）时不许出现开关");

  const discriminating = loadAppForTest();
  discriminating.hooks.initializeRows([
    Object.assign(row("懂车帝+易车", 2026, "在售款甲"), { "品牌": "A", "车系": "S1", "上市时间": "2025.09", "易车上市状态": "approved" }),
    Object.assign(row("仅易车", 2026, "停售款乙"), { "品牌": "A", "车系": "S2", "上市时间": "2024.05", "易车上市状态": "停售" })
  ]);
  discriminating.hooks.renderResultsOnly();
  assert.equal(discriminating.elements.get("saleScopeSection").hidden, false,
    "面上出现非 approved 的状态值时开关必须出现");
  discriminating.elements.get("saleScopeOnSale").dispatch("click");
  assert.equal(discriminating.hooks.getFilteredRows().map((item) => item["车型名称"]).join(","), "在售款甲",
    "只看在售必须把带负值的行滤掉");
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
  assert.ok(tags.includes("百公里加速 ≤7"));
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
  assert.ok(snapshots[0].rows[0].indexOf("A 1 2025款") !== -1, "年款作为型号结尾（2025款）");
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

test("non-energy summary normalization removes only known source prefixes and preserves measurement cycles", () => {
  const {hooks}=loadAppForTest();
  assert.equal(hooks.normEnumValue("汽车之家:多连杆独立悬架","后悬挂形式"),"多连杆独立悬架");
  assert.equal(hooks.normEnumValue("易车:CLTC:643","纯电续航(km)"),"CLTC:643");
  assert.equal(hooks.normEnumValue("CLTC:643","纯电续航(km)"),"CLTC:643");
  assert.equal(hooks.normEnumValue("WLTC:643","纯电续航(km)"),"WLTC:643");
  assert.equal(hooks.normEnumValue("自定义:真实值","真实属性"),"自定义:真实值");
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

(function () {
  "use strict";

  var HISTORY_PROVIDER = window.CARS_FILTER_HISTORY_PROVIDER || "worker";
  var HISTORY_API = window.CARS_FILTER_HISTORY_API || "/api/filter-history";
  var GITHUB_HISTORY = window.CARS_GITHUB_HISTORY || null;
  var DEFAULT_SYNC_ID = window.CARS_DEFAULT_FILTER_SYNC_ID || "";
  var STORAGE_SYNC_KEY = "cars_filter_sync_id";
  var STORAGE_HISTORY_KEY = "cars_filter_history_cache";
  var STORAGE_GITHUB_TOKEN_KEY = "cars_filter_github_token";

  var SAMPLE_ROWS = [
    {
      "数据来源": "示例",
      "品牌": "示例品牌",
      "车系": "示例车系",
      "车型名称": "等待 GitHub Pages 发布最新数据",
      "年款": "2026",
      "长*宽*高(mm)": "4890*1920*1685",
      "百公里加速(s)": "6.8",
      "纯电续航(km)": "200",
      "NOA城市领航": "支持",
      "远程启动": "支持",
      "远程控制": "车门控制|空调控制",
      "蓝牙/数字钥匙": "蓝牙钥匙",
      "座椅记忆": "驾驶位",
      "外后视镜记忆": "支持"
    }
  ];

  var DEFAULT_RANGE_FILTERS = {
    msrp: { min: "", max: "35" },
    zero_to_hundred: { min: "0", max: "7" },
    top_speed: { min: "180", max: "" },
    ev_range: { min: "150", max: "" }
  };
  var VALUE_COLUMN_PATTERN = /^(.+?)\s+-\s+(\S+.*)$/;
  var DEFAULT_FEATURE_FILTERS = {
    city_navigation: true,
    remote_start: true,
    remote_control: true,
    bluetooth_key: true,
    seat_memory: true,
    mirror_memory: true,
    app_remote_control: true,
    rain_sensor_wiper: true,
    auto_headlight: true,
    sentry_mode: true,
    tire_pressure_display: true,
    bev_heat_pump: true
  };

  var fallbackConfig = {
    defaultDataset: "latest",
    hiddenByDefault: ["数据来源", "ABS防抱死", "制动防抱死", "刹车防抱死"],
    dropIfUniformPositive: ["ABS防抱死", "制动防抱死", "刹车防抱死"],
    defaultVisibleColumns: ["品牌", "车系", "车型名称", "年款", "级别", "能源类型", "官方指导价", "上市时间", "交叉核验", "百公里加速(s)", "纯电续航(km)", "NOA城市领航", "远程启动", "远程控制", "蓝牙/数字钥匙", "座椅记忆", "外后视镜记忆", "最高车速(km/h)", "前悬挂形式", "后悬挂形式", "车门数(个)", "驱动方式", "整备质量(kg)", "辅助驾驶级别", "OTA升级", "驱动电机数"],
    conditions: [],
    centerConditionGroups: []
  };

  var state = {
    manifest: null,
    config: fallbackConfig,
    rows: [],
    publishedRawRows: null,
    columns: [],
    visibleColumns: new Set(),
    columnFilters: {},
    rangeFilters: Object.assign({}, DEFAULT_RANGE_FILTERS),
    featureFilters: Object.assign({}, DEFAULT_FEATURE_FILTERS),
    search: "",
    brand: "",
    series: "",
    sortField: "",
    sortDir: "asc",
    sortLevels: [],
    mode: "center",
    cardLimit: 24,
    cardSort: null,
    expandedSeries: new Set(),
    seriesViewSignature: "",
    mobileCategoryId: "",
    page: 1,
    pageSize: 100,
    pageSizeDraft: null,
    tableDisplayMode: "paged",
    tableRenderEpoch: 0,
    lastResultSignature: "",
    columnSearch: "",
    composing: false,
    saleScope: "onSale",
    syncId: "",
    githubToken: "",
    histories: []
  };

  var els = {
    dataMeta: document.getElementById("dataMeta"),
    globalSearch: document.getElementById("globalSearch"),
    resetFilters: document.getElementById("resetFilters"),
    saveHistory: document.getElementById("saveHistory"),
    exportCsv: document.getElementById("exportCsv"),
    exportJson: document.getElementById("exportJson"),
    visibleCount: document.getElementById("visibleCount"),
    totalCount: document.getElementById("totalCount"),
    columnCount: document.getElementById("columnCount"),
    verifiedCount: document.getElementById("verifiedCount"),
    dongchediCount: document.getElementById("dongchediCount"),
    autohomeCount: document.getElementById("autohomeCount"),
    yicheCount: document.getElementById("yicheCount"),
    brandFilter: document.getElementById("brandFilter"),
    seriesFilter: document.getElementById("seriesFilter"),
    pageSize: document.getElementById("pageSize"),
    tableDisplayMode: document.getElementById("tableDisplayMode"),
    applyPageSize: document.getElementById("applyPageSize"),
    tableRenderStatus: document.getElementById("tableRenderStatus"),
    tableHead: document.getElementById("tableHead"),
    tableBody: document.getElementById("tableBody"),
    emptyState: document.getElementById("emptyState"),
    prevPage: document.getElementById("prevPage"),
    nextPage: document.getElementById("nextPage"),
    pageInfo: document.getElementById("pageInfo"),
    pageJump: document.getElementById("pageJump"),
    goPage: document.getElementById("goPage"),
    conditionList: document.getElementById("conditionList"),
    advancedConditionSection: document.getElementById("advancedConditionSection"),
    fieldSelect: document.getElementById("fieldSelect"),
    fieldOperator: document.getElementById("fieldOperator"),
    fieldValue: document.getElementById("fieldValue"),
    applyFieldFilter: document.getElementById("applyFieldFilter"),
    activeFilters: document.getElementById("activeFilters"),
    showCoreColumns: document.getElementById("showCoreColumns"),
    showAllColumns: document.getElementById("showAllColumns"),
    columnSearch: document.getElementById("columnSearch"),
    columnList: document.getElementById("columnList"),
    historySyncId: document.getElementById("historySyncId"),
    githubToken: document.getElementById("githubToken"),
    copySyncId: document.getElementById("copySyncId"),
    loadHistory: document.getElementById("loadHistory"),
    saveGithubToken: document.getElementById("saveGithubToken"),
    clearGithubToken: document.getElementById("clearGithubToken"),
    historyStatus: document.getElementById("historyStatus"),
    historyList: document.getElementById("historyList"),
    toggleFieldFilterPanel: document.getElementById("toggleFieldFilterPanel"),
    fieldFilterBody: document.getElementById("fieldFilterBody"),
    toggleHistoryPanel: document.getElementById("toggleHistoryPanel"),
    historyBody: document.getElementById("historyBody"),
    cardToolbar: document.getElementById("cardToolbar"),
    centerActions: document.getElementById("centerActions"),
    mobileFilterActions: document.getElementById("mobileFilterActions"),
    saleScopeOnSale: document.getElementById("saleScopeOnSale"),
    saleScopeAll: document.getElementById("saleScopeAll"),
    saleScopeSection: document.getElementById("saleScopeSection"),
    downloadList: document.getElementById("downloadList"),
    centerMode: document.getElementById("centerMode"),
    tableMode: document.getElementById("tableMode"),
    filterCenter: document.getElementById("filterCenter"),
    tableRegion: document.getElementById("tableRegion"),
    workspace: document.getElementById("workspace"),
    centerHero: document.getElementById("centerHero"),
    centerBrandFilter: document.getElementById("centerBrandFilter"),
    centerSeriesFilter: document.getElementById("centerSeriesFilter"),
    centerConditionList: document.getElementById("centerConditionList"),
    selectedTags: document.getElementById("selectedTags"),
    cardList: document.getElementById("cardList"),
    centerVisibleCount: document.getElementById("centerVisibleCount"),
    mobileRestoreDefaults: document.getElementById("mobileRestoreDefaults"),
    mobileViewResults: document.getElementById("mobileViewResults"),
    mobileResultCount: document.getElementById("mobileResultCount"),
    loadMoreCards: document.getElementById("loadMoreCards"),
    cardSortSelect: document.getElementById("cardSortSelect"),
    customSortLevels: document.getElementById("customSortLevels"),
    addSortLevel: document.getElementById("addSortLevel"),
    clearSortLevels: document.getElementById("clearSortLevels")
  };

  function fetchJson(url) {
    return fetch(url, { cache: "no-store" }).then(function (response) {
      if (!response.ok) {
        throw new Error("HTTP " + response.status + " " + url);
      }
      return response.json();
    });
  }

  function loadPublishedChunks(chunks, expectedCount) {
    if (!Array.isArray(chunks) || !chunks.length || !Number.isInteger(expectedCount) || expectedCount < 0) {
      return Promise.reject(new Error("分片清单或总行数无效"));
    }
    if (!window.crypto || !window.crypto.subtle) {
      return Promise.reject(new Error("完整数据校验需要支持 WebCrypto 的 HTTPS 浏览器"));
    }
    var seen = new Set();
    var declaredCount = 0;
    for (var i = 0; i < chunks.length; i += 1) {
      var chunk = chunks[i];
      if (!chunk || typeof chunk.path !== "string" || !/^data\/[A-Za-z0-9._/-]+\.json$/.test(chunk.path)
          || chunk.path.split("/").indexOf("..") !== -1 || seen.has(chunk.path)
          || !/^[a-f0-9]{64}$/.test(chunk.sha256 || "") || !Number.isInteger(chunk.rowCount)
          || chunk.rowCount < 0 || !Number.isInteger(chunk.size) || chunk.size < 0) {
        return Promise.reject(new Error("数据分片描述无效"));
      }
      seen.add(chunk.path);
      declaredCount += chunk.rowCount;
    }
    if (declaredCount !== expectedCount) {
      return Promise.reject(new Error("分片清单行数与完整数据不一致"));
    }
    var parts = new Array(chunks.length);
    var nextIndex = 0;
    var failed = false;
    function worker() {
      if (failed || nextIndex >= chunks.length) { return Promise.resolve(); }
      var index = nextIndex++;
      var descriptor = chunks[index];
      return fetch(descriptor.path, { cache: "no-store" }).then(function (response) {
        if (!response.ok) { throw new Error("HTTP " + response.status + " " + descriptor.path); }
        return response.arrayBuffer();
      }).then(function (bytes) {
        if (bytes.byteLength !== descriptor.size) { throw new Error("分片文件大小不符: " + descriptor.path); }
        return window.crypto.subtle.digest("SHA-256", bytes).then(function (hash) {
          var actual = Array.from(new Uint8Array(hash)).map(function (value) {
            return value.toString(16).padStart(2, "0");
          }).join("");
          if (actual !== descriptor.sha256) { throw new Error("分片校验失败: " + descriptor.path); }
          var rows = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
          if (!Array.isArray(rows) || rows.length !== descriptor.rowCount) {
            throw new Error("分片行数不符: " + descriptor.path);
          }
          parts[index] = rows;
        });
      }).then(worker).catch(function (error) {
        failed = true;
        throw error;
      });
    }
    var workers = [];
    for (var j = 0; j < Math.min(4, chunks.length); j += 1) { workers.push(worker()); }
    return Promise.all(workers).then(function () {
      var rows = [];
      parts.forEach(function (part) {
        part.forEach(function (row) { rows.push(row); });
      });
      if (rows.length !== expectedCount) { throw new Error("完整数据行数校验失败"); }
      return rows;
    });
  }

  function loadPublishedRows(manifest) {
    var files = manifest.files || {};
    if (Object.prototype.hasOwnProperty.call(files, "latestJsonChunks")) {
      return loadPublishedChunks(files.latestJsonChunks, manifest.rowCount);
    }
    return fetchJson(files.latestJson || "data/latest.json");
  }

  function normalizeText(value) {
    return String(value == null ? "" : value).toLowerCase();
  }

  function cleanText(value) {
    return String(value == null ? "" : value).replace(/\s+/g, "").toLowerCase();
  }

  function cloneDefaultRangeFilters() {
    var result = {};
    (state.config.conditions || []).forEach(function (condition) {
      if (condition.type === "range") {
        result[condition.id] = {
          min: condition.defaultMin != null ? String(condition.defaultMin) : "",
          max: condition.defaultMax != null ? String(condition.defaultMax) : ""
        };
      }
    });
    return result;
  }

  function isFeatureCondition(condition) {
    return Boolean(condition) && (condition.type === "feature" || condition.type === "pagesFeature");
  }

  function cloneDefaultFeatureFilters() {
    var result = {};
    (state.config.conditions || []).forEach(function (condition) {
      if (isFeatureCondition(condition) && condition.defaultEnabled !== false) {
        result[condition.id] = true;
      }
    });
    return result;
  }

  function cleanModelText(value) {
    return cleanText(value)
      .replace(/改款/g, "")
      .replace(/[·・,，.。/／\\()（）\-_+]/g, "");
  }

  function firstNumber(value) {
    var match = String(value == null ? "" : value).match(/\d+(?:\.\d+)?/);
    return match ? Number(match[0]) : null;
  }

  function uniqueValues(rows, field) {
    return Array.from(new Set(rows.map(function (row) {
      return String(row[field] || "").trim();
    }).filter(Boolean))).sort(function (a, b) {
      return a.localeCompare(b, "zh-Hans", { numeric: true });
    });
  }

  // ---- 可见值规范化（分来源段解析） ----
  // 一根线上值会带多源写法：`懂车帝:纯电动|易车:纯电`、`35.8万|35.80万`。
  // 逐段剥来源前缀后再按语义去重，只去掉"同一件事换写法"，不去掉"真的不同"。
  // 顺序即优先级：`增程式纯电动` 先命中增程，绝不能被后面的纯电规则读成 BEV。
  // 归属（class）用来判"是不是同一种能源"；显示写法保留源里那条（除 `纯电` 统一写 `纯电动`），
  // 所以 增程/增程式、插混/插电式混合动力 各自去重，但油混/插混/增程三者永不互并。
  var ENERGY_CLASS_RULES = [
    { pattern: /增程/, cls: "erev" },
    { pattern: /插电|插混/, cls: "phev" },
    { pattern: /油电|混动/, cls: "hev" },
    { pattern: /纯电/, cls: "bev" },
    { pattern: /汽油|燃油/, cls: "ice" }
  ];
  function energyClassOf(text) {
    var value = String(text == null ? "" : text);
    for (var i = 0; i < ENERGY_CLASS_RULES.length; i += 1) {
      if (ENERGY_CLASS_RULES[i].pattern.test(value)) { return ENERGY_CLASS_RULES[i].cls; }
    }
    return "";
  }

  function splitDisplaySegments(value) {
    return String(value == null ? "" : value).split("|").map(function (part) {
      return part.trim();
    }).filter(Boolean);
  }

  function stripSourceSegmentPrefix(part) {
    return String(part == null ? "" : part).replace(/^\s*(?:汽车之家|懂车帝|易车)\s*[:：]\s*/, "").trim();
  }

  function canonicalEnergyValue(text) {
    var stripped = stripSourceSegmentPrefix(text);
    var synonyms = {
      "纯电": "纯电动", "增程": "增程式", "增程式纯电动": "增程式",
      "插混": "插电式混合动力", "插电混合": "插电式混合动力",
      "油混": "油电混合", "油电混合动力": "油电混合"
    };
    return synonyms[stripped] || stripped;
  }

  function normalizeEnergyText(value) {
    var seen = new Set();
    var items = [];
    String(value == null ? "" : value).split(/[|/]/).forEach(function (part) {
      var canonical = canonicalEnergyValue(part);
      if (!canonical || seen.has(canonical)) { return; }
      seen.add(canonical);
      var prefix = part.trim().match(/^(汽车之家|懂车帝|易车)\s*[:：]/);
      items.push({ value: canonical, source: prefix ? prefix[1] + ":" : "" });
    });
    if (items.length === 1) { return items[0].value; }
    return items.length ? items.map(function (item) { return item.source + item.value; }).join("|") : value;
  }

  function canonicalDecimal(value) {
    var parts = String(value).split(".");
    var integer = parts[0].replace(/^0+(?=\d)/, "");
    var decimal = (parts[1] || "").replace(/0+$/, "");
    return integer + (decimal ? "." + decimal : "");
  }

  function priceSegment(part) {
    var stripped = stripSourceSegmentPrefix(part);
    var match = stripped.match(/^(\d+(?:\.\d+)?)\s*(万元|万|元)?$/);
    if (!match) { return null; }
    var amount = match[1];
    if (match[2] === "元") {
      // Exact decimal shift; no floating-point rounding when deciding equality.
      var pieces = amount.split(".");
      var integer = pieces[0].padStart(5, "0");
      amount = integer.slice(0, -4) + "." + integer.slice(-4) + (pieces[1] || "");
    }
    return canonicalDecimal(amount);
  }

  function normalizePriceText(value) {
    var seen = new Set();
    var items = [];
    splitDisplaySegments(value).forEach(function (part) {
      var number = priceSegment(part);
      var text = number === null ? part : (number === "0" ? "未提供" : number + "万");
      var key = number === null ? part : "price:" + number;
      if (seen.has(key)) { return; }
      seen.add(key);
      var prefix = part.match(/^(汽车之家|懂车帝|易车)\s*[:：]/);
      items.push({value: text, source: number !== null && prefix ? prefix[1] + ":" : ""});
    });
    if (items.length === 1) { return items[0].value; }
    return items.length ? items.map(function (item) { return item.source + item.value; }).join("|") : value;
  }

  function normalizeDisplayValues(rows) {
    // 只在展示行上做：`publishedRawRows` 的完整 JSON/CSV 下载仍是原始值，不进这里。
    return rows.map(function (row) {
      var next = Object.assign({}, row);
      if (next["能源类型"] != null) { next["能源类型"] = normalizeEnergyText(next["能源类型"]); }
      if (next["官方指导价"] != null) { next["官方指导价"] = normalizePriceText(next["官方指导价"]); }
      return next;
    });
  }

  function isDimensionColumn(column) {
    var text = String(column || "").replace(/\s/g, "");
    return text.indexOf("长宽高") !== -1 ||
      text.indexOf("长*宽*高") !== -1 ||
      text.indexOf("长×宽×高") !== -1 ||
      text.indexOf("长x宽x高") !== -1 ||
      text.indexOf("车身尺寸") !== -1 ||
      (text.indexOf("长度") !== -1 && text.indexOf("宽度") !== -1 && text.indexOf("高度") !== -1);
  }

  function parseDimensionValue(value) {
    var numbers = String(value == null ? "" : value).match(/\d+(?:\.\d+)?/g);
    return numbers && numbers.length >= 3 ? numbers.slice(0, 3) : null;
  }

  function hasPositiveValue(value) {
    var text = String(value == null ? "" : value).trim();
    if (!text || text === "-") {
      return false;
    }
    return ["无", "不支持", "否", "没有", "未配备", "不提供", "0", "0.0"].indexOf(text) === -1;
  }

  function modelYear(row) {
    var fields = [row["年款"], row["车型名称"]];
    for (var i = 0; i < fields.length; i += 1) {
      var match = String(fields[i] == null ? "" : fields[i]).match(/(?:19|20)\d{2}/);
      if (match) {
        return match[0];
      }
    }
    return "";
  }

  function atomicSources(value) {
    var text = String(value == null ? "" : value).trim();
    var sources = new Set();
    var knownSources = ["懂车帝", "汽车之家", "易车"];
    text.split(/[+＋/／|、,，;；]+/).forEach(function (part) {
      var item = part.trim();
      var recognized = false;
      knownSources.forEach(function (source) {
        if (item.indexOf(source) !== -1) {
          sources.add(source);
          recognized = true;
        }
      });
      if (item && !recognized) {
        sources.add(item);
      }
    });
    return Array.from(sources);
  }

  function rowHasSource(row, source) {
    return atomicSources(row["核验来源"] || row["数据来源"]).indexOf(source) !== -1;
  }

  function rowAllowsMissingYear(row) {
    return rowHasSource(row, "易车");
  }

  function keepDisplayYear(row) {
    var year = modelYear(row);
    if (!year) {
      return rowAllowsMissingYear(row);
    }
    return Number(year) >= new Date().getFullYear() - 4;
  }

  function canonicalModelName(row) {
    var name = String(row["车型名称"] || "").trim();
    var series = String(row["车系"] || "").trim();
    var year = modelYear(row);
    var cleanName = cleanModelText(name);
    var parts = [];

    if (series && cleanName.indexOf(cleanModelText(series)) === -1) {
      parts.push(series);
    }
    if (year && cleanName.indexOf(year + "款") === -1 && cleanName.indexOf(year) === -1) {
      parts.push(year + "款");
    }
    if (name) {
      parts.push(name);
    }
    return cleanModelText(parts.join(" "));
  }

  function rowKey(row) {
    var auditedComponent = String(row["跨源归并ID"] || "").trim();
    if (auditedComponent) {
      return "audited|" + auditedComponent;
    }
    var modelKey = canonicalModelName(row);
    if (modelKey) {
      return "model|" + modelKey;
    }
    return "fallback|" + [row["品牌"], row["车系"], row["车型名称"], row["年款"]].map(cleanText).join("|");
  }

  var SKU_SOURCE_PREFIX = /^\s*(?:懂车帝|汽车之家|易车)\s*[:：]\s*/;
  var SKU_YEAR_TOKEN = /(^|[\s（(])\s*(?:20\d{2}|\d{2})\s*款/g;
  var SKU_ENGINE_TOKEN = /(\d+(?:\.\d+)?)\s*([TtLl])(?![a-zA-Z])/g;
  var SKU_ENGINE_FIND = /(\d+(?:\.\d+)?)\s*([TtLl])(?![a-zA-Z])/;
  var SKU_RANGE_TOKEN = /\d+(?:\.\d+)?\s*km/ig;
  var SKU_DRIVE_TOKEN = /(前驱|后驱|四驱|两驱|全驱)/;

  function skuStripLead(text, token) {
    var target = cleanText(token);
    if (!target) { return text; }
    var acc = "";
    var index = 0;
    while (index < text.length && acc.length < target.length) {
      var ch = text.charAt(index);
      if (!/\s/.test(ch)) { acc += ch.toLowerCase(); }
      index += 1;
    }
    return acc === target ? text.slice(index).replace(/^\s+/, "") : text;
  }

  function skuTrimName(name, row) {
    var text = String(name == null ? "" : name).replace(SKU_SOURCE_PREFIX, "").trim();
    var tokens = [row["车系"], row["品牌"]].map(cleanText).filter(Boolean)
      .sort(function (a, b) { return b.length - a.length; });
    var changed = true;
    while (changed) {
      changed = false;
      tokens.forEach(function (token) {
        var next = skuStripLead(text, token);
        if (next !== text) { text = next; changed = true; }
      });
    }
    text = text.replace(SKU_YEAR_TOKEN, "$1")
      .replace(SKU_ENGINE_TOKEN, " ")
      .replace(SKU_RANGE_TOKEN, " ")
      .replace(SKU_DRIVE_TOKEN, " ");
    return text.replace(/\s+/g, " ").trim();
  }

  function skuTrim(row) {
    var trimmed = skuTrimName(row["车型名称"], row);
    return trimmed || cleanModelText(row["车型名称"]);
  }

  function skuEngineParts(row) {
    // 排量/进气字母分开记：跨源常一边只有 `排量(L)=1.5`、另一边 `发动机=1.5T`。
    // 合并时"1.5"与"1.5t"其实是同一台增程器，字母差异是缺值产物，不算真实动力冲突；
    // 数字(1.5 vs 2.4)与两边都写明的字母(2.4L vs 2.4T)仍必须一致。
    var fields = [row["发动机"], row["排量(L)"], row["排量"]];
    for (var i = 0; i < fields.length; i += 1) {
      var text = String(fields[i] == null ? "" : fields[i]);
      var match = SKU_ENGINE_FIND.exec(text);
      if (match) { return { size: match[1], letter: match[2].toLowerCase() }; }
      if (i > 0) {
        var number = text.match(/\d+(?:\.\d+)?/);
        if (number) { return { size: number[0], letter: "" }; }
      }
    }
    var name = SKU_ENGINE_FIND.exec(String(row["车型名称"] || ""));
    return name ? { size: name[1], letter: name[2].toLowerCase() } : null;
  }

  function skuPriceSet(row) {
    var values = [];
    splitDisplaySegments(row["官方指导价"]).forEach(function (part) {
      var value = priceSegment(part);
      if (value === null && /[0-9]/.test(part)) {
        // An interval, starting price or numeric annotation is evidence, not an absent price.
        // Preserve it exactly and conservatively refuse equivalence with a different observation.
        value = "unparsed:" + stripSourceSegmentPrefix(part);
      }
      if (value !== null && (value.indexOf("unparsed:") === 0 || Number(value) > 0) && values.indexOf(value) === -1) { values.push(value); }
    });
    return values;
  }

  function skuPrice(row) {
    var values = skuPriceSet(row).map(Number).filter(function (value) { return Number.isFinite(value) && value > 0; });
    return values.length ? Math.min.apply(null, values) : null;
  }

  function skuRangeSet(row) {
    var numbers = String(row["纯电续航(km)"] == null ? "" : row["纯电续航(km)"]).match(/\d+(?:\.\d+)?/g);
    return numbers ? numbers.map(Number) : [];
  }

  function skuDrive(row) {
    var text = normalizeText(row["驱动方式"]) + " " + normalizeText(row["车型名称"]);
    var match = text.match(SKU_DRIVE_TOKEN);
    return match ? match[1] : "";
  }

  function skuEnergy(row) {
    var values = [];
    String(row["能源类型"] || "").split(/[|/]/).forEach(function (part) {
      var value = canonicalEnergyValue(part);
      if (value && values.indexOf(value) === -1) { values.push(value); }
    });
    return values.sort().join("/");
  }

  function skuIdNameKey(row) {
    // 与 tests/pages_ui.test.js 线上不变式同一口径：空白全去掉 + 小写。
    var id = String(row["车款ID"] == null ? "" : row["车款ID"]).trim();
    if (!id || id === "-") { return ""; }
    var name = String(row["车型名称"] == null ? "" : row["车型名称"]).replace(/\s+/g, "").toLowerCase();
    return name ? id + "\u0000" + name : "";
  }

  var SKU_ATOM_WORDS = [
    "激光雷达", "双电机", "三电机", "四电机", "超长续航", "长续航", "高性能",
    "增程", "纯电", "智驾", "猎装", "骑士", "性能", "豪华", "尊贵", "旗舰",
    "卓越", "超越", "领先", "探索", "标准", "舒适", "运动"
  ];
  var SKU_ATOM_SUFFIX = /[版型款]+$/g;

  function skuCjkAtoms(run, out) {
    // 已知词优先切分，其余连续汉字作为一个原子；`版/型/款`只作后缀，不进键。
    var index = 0;
    var buffer = "";
    while (index < run.length) {
      var word = "";
      for (var i = 0; i < SKU_ATOM_WORDS.length; i += 1) {
        if (run.substr(index, SKU_ATOM_WORDS[i].length) === SKU_ATOM_WORDS[i]) { word = SKU_ATOM_WORDS[i]; break; }
      }
      if (word) {
        if (buffer) { out.push(buffer); buffer = ""; }
        out.push(word);
        index += word.length;
      } else {
        buffer += run.charAt(index);
        index += 1;
      }
    }
    if (buffer) { out.push(buffer); }
  }

  function skuNameAtoms(text) {
    var atoms = [];
    var pattern = /[A-Za-z0-9][A-Za-z0-9+._-]*|[\u4e00-\u9fa5]+/g;
    var match;
    while ((match = pattern.exec(String(text == null ? "" : text)))) {
      var token = match[0];
      if (/^[A-Za-z0-9]/.test(token)) { atoms.push(token.toLowerCase()); continue; }
      skuCjkAtoms(token, atoms);
    }
    return atoms.map(function (atom) {
      return atom.replace(SKU_ATOM_SUFFIX, "");
    }).filter(Boolean).sort();
  }

  function skuCoarseKey(row) {
    // 键用**原子集合**（排序后），这样 `Max纯电版` 与 `纯电版 650km 后驱Max`、`Pro版` 与 `Pro`、
    // `激光雷达 型` 与 `激光雷达型` 落在同一组；是否真合并交给 skuCompatible（价格/续航/动力/驱动）。
    // 原子是集合比较，仍然区分 `智驾版 550km 卓越型`（智驾+卓越）与 `550km 卓越型`（卓越），
    // 不会因为同价同续航把智驾/非智驾并掉。
    return [cleanText(row["车系"]), modelYear(row), skuEnergy(row), skuNameAtoms(skuTrim(row)).join("|")].join("|");
  }

  function skuEngineCompatible(a, b) {
    var ea = skuEngineParts(a), eb = skuEngineParts(b);
    if (!ea || !eb) { return true; }
    if (ea.size !== eb.size) { return false; }
    if (ea.letter && eb.letter && ea.letter !== eb.letter) { return false; }
    return true;
  }

  function skuCompatible(a, b) {
    if (!skuEngineCompatible(a, b)) { return false; }
    // Known conflicting hardware must not be swallowed by a name-only equivalence.
    var hardware = [
      ["电池容量(kWh)", "电池能量(kWh)"], ["电动机总功率(kW)"],
      ["激光雷达数量", "激光雷达数量(个)"], ["驱动电机数"]
    ];
    for (var h = 0; h < hardware.length; h += 1) {
      var values = [a, b].map(function (row) {
        var out = [];
        hardware[h].forEach(function (field) {
          var found = String(row[field] == null ? "" : row[field]).match(/\d+(?:\.\d+)?/g) || [];
          found.map(Number).forEach(function (n) { if ((h >= 2 ? n >= 0 : n > 0) && out.indexOf(n) === -1) { out.push(n); } });
        });
        return out;
      });
      if (values[0].length && values[1].length && !values[0].some(function (v) { return values[1].indexOf(v) !== -1; })) { return false; }
    }
    var pa = skuPriceSet(a), pb = skuPriceSet(b);
    if (pa.length && pb.length) {
      var samePrice = pa.some(function (value) { return pb.indexOf(value) !== -1; });
      if (!samePrice) { return false; }
    }
    var ra = skuRangeSet(a), rb = skuRangeSet(b);
    if (ra.length && rb.length) {
      var common = ra.some(function (value) { return rb.indexOf(value) !== -1; });
      if (!common) { return false; }
    }
    var da = skuDrive(a), db = skuDrive(b);
    if (da && db && da !== db) { return false; }
    return true;
  }

  function clusterSkuRows(items) {
    // **完全链接**：一条行只有当它与目标簇里**现有每一条**都兼容时才并入。
    // 单链接并查集（原实现）会被桥接行串成大簇：实测 A(58.98万/2.0T)+B(缺价缺动力)+C(62.98万/2.4L)
    // 经 B 合成 1 行、C 静默消失（step 家族票 P1 的复现形状）。完全链接下 C 留在自己簇里，
    // 互斥的 SKU 不再被桥接行吞掉；偏向"漏合"而不是"误合"。
    var clusters = [];
    items.forEach(function (item) {
      for (var i = 0; i < clusters.length; i += 1) {
        if (clusters[i].every(function (member) { return skuCompatible(member, item); })) {
          clusters[i].push(item);
          return;
        }
      }
      clusters.push([item]);
    });
    return clusters;
  }

  function skuDisplayName(items) {
    var best = items[0];
    var bestScore = -1;
    items.forEach(function (row) {
      var name = String(row["车型名称"] || "");
      // 信息量优先：名字里带动力/续航的那条比只有前缀的更完整（E7 的 1.5T/230km 不能丢）。
      var score = cleanText(name).length
        + (/(\d+(?:\.\d+)?)\s*[TtLl](?![a-zA-Z])/.test(name) ? 20 : 0)
        + (/\d+(?:\.\d+)?\s*km/i.test(name) ? 20 : 0);
      if (score > bestScore) { bestScore = score; best = row; }
    });
    var text = String(best["车型名称"] || "").replace(SKU_SOURCE_PREFIX, "").trim();
    var year = modelYear(best);
    // 年款写法就地归一（26款 -> 2026款），不把车系/动力 token 挪位、也不硬塞没有的年款：
    // 车系列已单列；保留源名里的车系/配置顺序，避免改写展示语义和既有断言。
    text = text.replace(/(^|[\s（(])\s*(?:20\d{2}|\d{2})\s*款/, function (match, prefix) {
      return year ? prefix + year + "款" : match;
    });
    return text.replace(/\s+/g, " ").trim();
  }

  function mergeSkuCluster(items) {
    var merged = {};
    var sources = new Set();
    var rawNames = [];
    items.forEach(function (row) {
      atomicSources(row["数据来源"]).forEach(function (source) { sources.add(source); });
      Object.keys(row).forEach(function (column) {
        if (["易车上市状态", "销售状态", "在售状态", "激光雷达数量", "激光雷达数量(个)", "驱动电机数"].indexOf(column) !== -1) {
          // Negative statuses and numeric zero counts are evidence, not missing values.
          var status = String(row[column] == null ? "" : row[column]).trim();
          var observed = String(merged[column] == null ? "" : merged[column]).split("|").filter(Boolean);
          if (status && status !== "-" && observed.indexOf(status) === -1) { observed.push(status); }
          if (observed.length) { merged[column] = observed.join("|"); }
        } else if ((column === "能源类型" || column === "官方指导价") && hasPositiveValue(row[column])) {
          merged[column] = mergeDistinctColumnValues(merged[column], row[column]);
        } else if (!hasPositiveValue(merged[column]) && hasPositiveValue(row[column])) {
          merged[column] = row[column];
        }
      });
      var name = String(row["车型名称"] || "").trim();
      if (name && rawNames.indexOf(name) === -1) { rawNames.push(name); }
    });
    var sourceList = Array.from(sources).sort(function (a, b) {
      return a.localeCompare(b, "zh-Hans");
    });
    merged["数据来源"] = sourceList.join(" + ") || merged["数据来源"] || "-";
    merged["核验来源"] = sourceList.join(" + ") || "-";
    merged["交叉核验"] = sourceList.length >= 2 ? "双源核验" : "单源数据";
    merged["源车型名称"] = rawNames.join(" / ");
    merged["车型名称"] = skuDisplayName(items);
    return merged;
  }

  function mergeVerifiedRows(rows) {
    var audited = {};
    var rest = [];
    rows.forEach(function (row) {
      var id = String(row["跨源归并ID"] || "").trim();
      if (id) {
        var key = "audited|" + id;
        if (!audited[key]) { audited[key] = []; }
        audited[key].push(row);
      } else {
        rest.push(row);
      }
    });
    var identity = {};
    rest.forEach(function (row) {
      // 同一 车款ID + 同名 = 同一个 SKU（源侧主键），**成组（≥2）时无条件并**：线上验收不变式
      // 就钉在"展示层不许留同车款ID 同名的两行"上；属性值互斥多半是源侧数据问题（实测 171437：
      // 一行价格 `11.98万`、另一行是聚合串 `懂车帝:10.89万|易车:11.98万`），过兼容闸会把它拆开。
      // 单条（该 ID+名只有一行）不吃掉：跨源两行 ID 不同（如 E7 的 186452/76217）仍要走粗键+兼容闸。
      var key = skuIdNameKey(row);
      if (!key) { return; }
      if (!identity[key]) { identity[key] = []; }
      identity[key].push(row);
    });
    var coarse = {};
    rest.forEach(function (row) {
      var key = skuIdNameKey(row);
      if (key && identity[key].length >= 2) { return; }
      var ckey = skuCoarseKey(row);
      if (!coarse[ckey]) { coarse[ckey] = []; }
      coarse[ckey].push(row);
    });
    var clusters = [];
    Object.keys(audited).forEach(function (key) { clusters.push(audited[key]); });
    Object.keys(identity).forEach(function (key) {
      if (identity[key].length >= 2) { clusters.push(identity[key]); }
    });
    Object.keys(coarse).forEach(function (key) {
      clusters = clusters.concat(clusterSkuRows(coarse[key]));
    });
    return clusters.map(mergeSkuCluster);
  }

  function withDerivedDimensions(rows) {
    return rows.map(function (row) {
      var next = Object.assign({}, row);
      var dimensionColumn = Object.keys(row).find(isDimensionColumn);
      var dimensions = dimensionColumn ? parseDimensionValue(row[dimensionColumn]) : null;
      if (dimensions) {
        next["长度(mm)"] = next["长度(mm)"] || dimensions[0];
        next["宽度(mm)"] = next["宽度(mm)"] || dimensions[1];
        next["高度(mm)"] = next["高度(mm)"] || dimensions[2];
      }
      return next;
    });
  }

  var OPTION_SUFFIX_PATTERN = /^(.+?)_(\d+)$/;

  function addOptionPackageColumns(target, name) {
    var base = String(name || "").trim();
    if (!base) { return; }
    target.add(base);
    target.add(base + "_1");
    target.add(base + "_2");
  }

  function collectEquipmentColumns(rows) {
    var columns = new Set();
    (rows || []).forEach(function (row) {
      var rawPackages = row["选装包列表"];
      if (rawPackages && rawPackages !== "-") {
        try {
          var packages = typeof rawPackages === "string" ? JSON.parse(rawPackages) : rawPackages;
          if (packages && typeof packages === "object" && !Array.isArray(packages)) {
            Object.keys(packages).forEach(function (name) { addOptionPackageColumns(columns, name); });
          }
        } catch (error) {
          // Invalid legacy package metadata is ignored instead of hiding unrelated columns.
        }
      }

      var pairs = {};
      Object.keys(row).forEach(function (column) {
        var match = OPTION_SUFFIX_PATTERN.exec(column);
        if (!match) { return; }
        if (!pairs[match[1]]) { pairs[match[1]] = {}; }
        pairs[match[1]][match[2]] = row[column];
      });
      Object.keys(pairs).forEach(function (base) {
        var suffixes = Object.keys(pairs[base]).sort();
        var first = pairs[base]["1"];
        var second = pairs[base]["2"];
        if (suffixes.length === 2 && suffixes[0] === "1" && suffixes[1] === "2" &&
            hasPositiveValue(first) && hasPositiveValue(second) && String(first).trim() !== String(second).trim()) {
          addOptionPackageColumns(columns, base);
        }
      });
    });
    return columns;
  }

  function isEquipmentColumn(column, rows, equipmentColumns) {
    return (equipmentColumns || collectEquipmentColumns(rows)).has(String(column || ""));
  }

  function shouldHideColumn(column, rows, equipmentColumns) {
    var defaultVisible = state.config.defaultVisibleColumns || [];
    var hidden = state.config.hiddenByDefault || [];
    var dropUniform = state.config.dropIfUniformPositive || [];
    if (column === "__header_normalization_evidence") {
      // 内部审计字段（如 __header_normalization_evidence）永不作为列展示。
      return true;
    }
    if (column === "懂车帝车型ID") {
      // 懂车帝来源主键只作身份证据，精确隐藏此列，不影响其它 ID/陌生列。
      return true;
    }
    if (defaultVisible.indexOf(column) !== -1) {
      return false;
    }
    if (hidden.indexOf(column) !== -1) {
      return true;
    }
    if (isEquipmentColumn(column, rows, equipmentColumns)) {
      return true;
    }
    if (dropUniform.indexOf(column) !== -1) {
      var values = rows.map(function (row) { return row[column]; }).filter(function (value) {
        return value != null && value !== "";
      });
      return values.length > 0 && values.every(hasPositiveValue);
    }
    return false;
  }

  function columnAliasMap() {
    var map = {};
    var aliases = (state.config && state.config.columnAliases) || {};
    Object.keys(aliases).forEach(function (standard) {
      (aliases[standard] || []).forEach(function (alias) {
        map[alias] = standard;
      });
    });
    return map;
  }

  function mergeDistinctColumnValues(existing, incoming) {
    if (!hasPositiveValue(existing)) { return incoming; }
    if (!hasPositiveValue(incoming)) { return existing; }
    var incomingText = String(incoming).trim();
    var parts = String(existing).split("|").map(function (part) { return part.trim(); });
    return parts.indexOf(incomingText) === -1 ? String(existing) + "|" + incomingText : existing;
  }

  function normalizeRowColumns(rows) {
    var aliasMap = columnAliasMap();
    return rows.map(function (row) {
      var next = Object.assign({}, row);
      Object.keys(row).forEach(function (sourceColumn) {
        var value = row[sourceColumn];
        var column = String(sourceColumn).trim();
        if (column !== sourceColumn) {
          delete next[sourceColumn];
        }
        var valueMatch = VALUE_COLUMN_PATTERN.exec(column);
        if (valueMatch) {
          var parent = valueMatch[1].trim();
          if (hasPositiveValue(value)) {
            next[parent] = mergeDistinctColumnValues(next[parent], valueMatch[2].trim());
          }
          delete next[column];
          return;
        }
        var standard = aliasMap[column];
        if (standard && standard !== column) {
          if (hasPositiveValue(value)) {
            next[standard] = mergeDistinctColumnValues(next[standard], value);
          }
          delete next[column];
        } else if (column !== sourceColumn && hasPositiveValue(value)) {
          next[column] = mergeDistinctColumnValues(next[column], value);
        }
      });
      return next;
    });
  }

  function buildColumns(rows) {
    var seen = new Set();
    var columns = [];
    var equipmentColumns = collectEquipmentColumns(rows);
    (state.config.defaultVisibleColumns || []).forEach(function (column) {
      if (rows.some(function (row) { return Object.prototype.hasOwnProperty.call(row, column); }) && !shouldHideColumn(column, rows, equipmentColumns)) {
        seen.add(column);
        columns.push(column);
      }
    });
    rows.forEach(function (row) {
      Object.keys(row).forEach(function (column) {
        if (isDimensionColumn(column) || shouldHideColumn(column, rows, equipmentColumns) || seen.has(column)) {
          return;
        }
        seen.add(column);
        columns.push(column);
      });
    });
    return columns;
  }

  function strictEquipmentKey(value) {
    return String(value == null ? "" : value).replace(/\s+/g, "").toLowerCase();
  }

  function strictEquipmentEvidence(value, policy) {
    var options = policy || {};
    var positive = false;
    var negative = false;
    splitDisplaySegments(value).forEach(function (part) {
      var text = stripSourceSegmentPrefix(part).replace(/\s+/g, "");
      if (!text || text === "-") { return; }
      var denied = /不支持|不提供|不具备|不配备|不带|未支持|未标配|未配备|未安装|没有|选装|选配|○/.test(text) ||
        /^无(?!线|钥匙)/.test(text) ||
        /^否(?:$|定|不)/.test(text);
      if (denied) { negative = true; }
      var affirmed = /●|支持|标配|标准配置|配备|具备|已装/.test(text) ||
        /^是(?:$|[（(，,；;、])/.test(text) ||
        /^有(?:$|[（(，,；;、])/.test(text);
      if (options.requireExplicitValue) {
        affirmed = text.indexOf(options.requireExplicitValue) !== -1 && !denied;
      } else if (options.acceptExplicitValue && text.indexOf(options.acceptExplicitValue) !== -1) {
        affirmed = true;
      }
      if (affirmed) { positive = true; }
    });
    return { positive: positive, negative: negative };
  }

  function strictEquipmentFieldEvidence(row, fields, policy) {
    var expected = fields.map(strictEquipmentKey);
    var result = { positive: false, negative: false };
    Object.keys(row).forEach(function (key) {
      if (expected.indexOf(strictEquipmentKey(key)) === -1) { return; }
      var evidence = strictEquipmentEvidence(row[key], policy);
      result.positive = result.positive || evidence.positive;
      result.negative = result.negative || evidence.negative;
    });
    return result;
  }

  function strictEnergyPresence(value) {
    var result = { bev: false, other: false };
    splitDisplaySegments(value).forEach(function (part) {
      part.split(/[\/／]/).forEach(function (piece) {
        var token = String(canonicalEnergyValue(piece)).replace(/\s+/g, "").toLowerCase();
        if (!token) { return; }
        if (/增程|插电|插混|油电|混动|汽油|燃油|柴油|48v|轻混|氢|燃料电池|phev|erev|hev|ice/.test(token)) {
          result.other = true;
        } else if (/纯电|bev/.test(token)) {
          result.bev = true;
        }
      });
    });
    return result;
  }

  function conditionMatches(row, condition) {
    if (condition.type === "range") {
      var filter = state.rangeFilters[condition.id] || {};
      var hasMin = filter.min !== "" && filter.min != null;
      var hasMax = filter.max !== "" && filter.max != null;
      if (!hasMin && !hasMax) { return true; }
      if (condition.field === "官方指导价") {
        // A conflicting cheaper observation cannot mask another observation above the budget.
        var prices = splitDisplaySegments(row[condition.field]).map(priceSegment);
        return prices.length > 0 && prices.every(function (value) {
          if (value === null || !(Number(value) > 0)) { return false; }
          return (!hasMin || Number(value) >= Number(filter.min)) && (!hasMax || Number(value) <= Number(filter.max));
        });
      }
      var rowValue = firstNumber(row[condition.field]);
      if (rowValue == null) {
        return false;
      }
      if (filter.min !== "" && filter.min != null && rowValue < Number(filter.min)) {
        return false;
      }
      if (filter.max !== "" && filter.max != null && rowValue > Number(filter.max)) {
        return false;
      }
      return true;
    }

    if (isFeatureCondition(condition)) {
      if (!state.featureFilters[condition.id]) {
        return true;
      }
      if (condition.id === "sentry_mode") {
        var sentry = strictEquipmentFieldEvidence(row, condition.fields || [], {});
        return sentry.positive && !sentry.negative;
      }
      if (condition.id === "tire_pressure_display") {
        var genericFields = condition.genericFields || [];
        var dedicatedFields = (condition.fields || []).filter(function (field) {
          return genericFields.indexOf(field) === -1;
        });
        var dedicated = strictEquipmentFieldEvidence(row, dedicatedFields, { acceptExplicitValue: "胎压显示" });
        var generic = strictEquipmentFieldEvidence(row, genericFields, { requireExplicitValue: "胎压显示" });
        var tire = {
          positive: dedicated.positive || generic.positive,
          negative: dedicated.negative || generic.negative
        };
        return tire.positive && !tire.negative;
      }
      if (condition.id === "bev_heat_pump") {
        var energy = strictEnergyPresence(row["能源类型"] || row["燃料形式"]);
        if (!energy.bev && energy.other) { return true; }
        var heatPump = strictEquipmentFieldEvidence(row, condition.fields || [], {});
        return heatPump.positive && !heatPump.negative;
      }
      var fields = condition.fields || [];
      var keywords = condition.keywords || [];
      return Object.keys(row).some(function (key) {
        var val = row[key];
        if (!hasPositiveValue(val)) {
          return false;
        }
        var keyHit = fields.some(function (field) { return key.indexOf(field) !== -1 || field.indexOf(key) !== -1; });
        var valHit = keywords.some(function (keyword) { return String(val).indexOf(keyword) !== -1; });
        return condition.requireKeyword ? valHit : (keyHit || valHit);
      });
    }

    return true;
  }

  function rowMatchesDefaultRowType(row) {
    var config = state.config || {};
    var allowedConfig = config.defaultAllowedLevels || null;
    if (!allowedConfig) {
      return true;
    }
    var allowed = allowedConfig.allowed_levels || [];
    if (allowed.length === 0) {
      // 没有指定允许集合 -> 退化兼容：如果存在 _comment/single-key 层，则取全部 values
      allowed = [];
      Object.keys(allowedConfig).forEach(function (k) {
        if (k === "_comment") {
          return;
        }
        var v = allowedConfig[k];
        if (Array.isArray(v)) {
          allowed = allowed.concat(v);
        } else if (typeof v === "object" && v !== null) {
          Object.keys(v).forEach(function (kk) {
            var vv = v[kk];
            if (Array.isArray(vv)) {
              allowed = allowed.concat(vv);
            }
          });
        }
      });
    }
    if (allowed.length > 0) {
      var level = normalizeText(row["级别"] || "");
      if (!level) {
        return true; // 无级别字段时的兼容：不主动剔除
      }
      var match = allowed.some(function (lvl) { return normalizeText(lvl) === level; });
      if (!match) {
        return false;
      }
    }

    var brandPatterns = config.defaultHiddenBrandPatterns || [];
    if (brandPatterns.length > 0) {
      var brand = normalizeText(row["品牌"] || "");
      if (brandPatterns.some(function (p) { return brand.indexOf(normalizeText(p)) !== -1; })) {
        return false;
      }
    }

    var seriesPatterns = config.defaultHiddenSeriesPatterns || [];
    if (seriesPatterns.length > 0) {
      var series = normalizeText(row["车系"] || "");
      if (seriesPatterns.some(function (p) { return series.indexOf(normalizeText(p)) !== -1; })) {
        return false;
      }
    }
    return true;
  }


  function parseCustomOrder(text) {
    return String(text || "").split(/[\n,，]+/).map(function (item) { return normalizeText(item.trim()); }).filter(Boolean);
  }

  function customOrderToken(value, field) {
    var text = normalizeText(value);
    if (field === "能源类型") {
      var classes = [];
      splitDisplaySegments(text).forEach(function (part) {
        var token = energyClassOf(part) || stripSourceSegmentPrefix(part);
        if (token && classes.indexOf(token) === -1) { classes.push(token); }
      });
      return classes.sort().join("|");
    }
    return text;
  }

  function customOrderIndex(value, orderText, field) {
    var valueText = customOrderToken(value, field);
    var order = parseCustomOrder(orderText);
    for (var i = 0; i < order.length; i += 1) {
      var keyword = field === "能源类型" ? customOrderToken(order[i], field) : order[i];
      // Energy classes are exact identities: "hev" is not a substring match for "phev".
      if (field === "能源类型" ? valueText === keyword : valueText.indexOf(keyword) !== -1) {
        return i;
      }
    }
    return order.length;
  }

  function sourceCount(row) {
    var value = String(row["数据来源"] || "").trim();
    if (!value) {
      return 0;
    }
    return value.split("+").length;
  }

  function compareRowsByLevel(a, b, level) {
    var av = a[level.field];
    var bv = b[level.field];
    var order = parseCustomOrder(level.customOrder);
    var result;
    if (level.field === "数据来源") {
      result = sourceCount(a) - sourceCount(b);
      return level.dir === "desc" ? -result : result;
    }
    if (order.length) {
      result = customOrderIndex(av, level.customOrder, level.field) - customOrderIndex(bv, level.customOrder, level.field);
      if (result === 0) {
        result = String(av || "").localeCompare(String(bv || ""), "zh-Hans", { numeric: true });
      }
    } else {
      var an = firstNumber(av);
      var bn = firstNumber(bv);
      result = an !== null && bn !== null ? an - bn : String(av || "").localeCompare(String(bv || ""), "zh-Hans", { numeric: true });
    }
    return level.dir === "desc" ? -result : result;
  }

  function activeSortLevels() {
    var levels = (state.sortLevels || []).filter(function (level) { return level && level.field; });
    if (!levels.length && state.sortField) {
      levels = [{ field: state.sortField, dir: state.sortDir || "asc", customOrder: "" }];
    }
    return levels;
  }

  function sortRows(rows) {
    var levels = activeSortLevels();
    var explicitSource = null;
    for (var levelIndex = 0; levelIndex < levels.length; levelIndex += 1) {
      if (levels[levelIndex].field === "数据来源") {
        explicitSource = levels[levelIndex];
        break;
      }
    }
    return rows.map(function (row, index) { return { row: row, index: index }; }).sort(function (a, b) {
      if (explicitSource) {
        var sourceResult = sourceCount(a.row) - sourceCount(b.row);
        if (sourceResult !== 0) {
          return explicitSource.dir === "desc" ? -sourceResult : sourceResult;
        }
      } else {
        var leftCount = sourceCount(a.row);
        var rightCount = sourceCount(b.row);
        if (leftCount !== rightCount) {
          return rightCount - leftCount;
        }
      }
      for (var i = 0; i < levels.length; i += 1) {
        var result = compareRowsByLevel(a.row, b.row, levels[i]);
        if (result !== 0) {
          return result;
        }
      }
      return a.index - b.index;
    }).map(function (item) { return item.row; });
  }

  function isPriceField(field) {
    return /(?:价格|指导价|售价|报价|落地价|裸车价|补贴价)/.test(String(field || ""));
  }

  function validPrice(row, field) {
    var value = firstNumber(row[field]);
    return value !== null && Number.isFinite(value) && value > 0 ? value : null;
  }

  var BRAND_NORM = {
    "小鹏": "小鹏汽车",
    "AITO": "AITO 问界",
    "岚图": "岚图汽车"
  };
  function normBrand(b) {
    return BRAND_NORM[b] || b;
  }
  function seriesIdentity(row) {
    var brand = normBrand(String(row["品牌"] || "").trim());
    // 跨源写法差异：车系去空格仅用于分组 key（阿维塔 07 == 阿维塔07）；
    // 显示名保留原始写法。
    var seriesRaw = String(row["车系"] || "").trim();
    var seriesKey = seriesRaw.replace(/\s+/g, "");
    var model = String(row["车型名称"] || "").trim();
    var year = String(row["年款"] || "").trim();
    if (seriesKey) {
      return { key: "series|" + brand + "|" + seriesKey, name: seriesRaw || seriesKey };
    }
    return {
      key: "model|" + brand + "|" + model + "|" + year,
      name: model || "未命名车系"
    };
  }

  function groupRowsBySeries(rows) {
    var groups = [];
    var groupMap = new Map();
    rows.forEach(function (row) {
      var identity = seriesIdentity(row);
      var group = groupMap.get(identity.key);
      if (!group) {
        group = {
          key: identity.key,
          name: identity.name,
          rows: [],
          representative: row,
          price: null,
          order: groups.length
        };
        groupMap.set(identity.key, group);
        groups.push(group);
      }
      group.rows.push(row);
    });

    var levels = activeSortLevels();
    var priceLevel = levels.length && isPriceField(levels[0].field) ? levels[0] : null;
    if (!priceLevel) {
      return groups;
    }

    groups.forEach(function (group) {
      group.rows.forEach(function (row) {
        var price = validPrice(row, priceLevel.field);
        if (price === null) {
          return;
        }
        var better = group.price === null ||
          (priceLevel.dir === "desc" ? price > group.price : price < group.price);
        if (better) {
          group.price = price;
          group.representative = row;
        }
      });
    });

    return groups.sort(function (a, b) {
      if (a.price === null || b.price === null) {
        if (a.price === null && b.price !== null) { return 1; }
        if (a.price !== null && b.price === null) { return -1; }
      } else if (a.price !== b.price) {
        return priceLevel.dir === "desc" ? b.price - a.price : a.price - b.price;
      }
      for (var i = 1; i < levels.length; i += 1) {
        var result = compareRowsByLevel(a.representative, b.representative, levels[i]);
        if (result !== 0) {
          return result;
        }
      }
      var nameResult = a.name.localeCompare(b.name, "zh-Hans", { numeric: true });
      return nameResult || a.key.localeCompare(b.key, "zh-Hans", { numeric: true }) || a.order - b.order;
    });
  }

  function currentSeriesViewSignature() {
    return JSON.stringify({
      search: state.search,
      brand: state.brand,
      series: state.series,
      columnFilters: state.columnFilters,
      rangeFilters: state.rangeFilters,
      featureFilters: state.featureFilters,
      sortField: state.sortField,
      sortDir: state.sortDir,
      sortLevels: state.sortLevels,
      saleScope: state.saleScope
    });
  }

  function syncSeriesViewState() {
    var signature = currentSeriesViewSignature();
    if (signature !== state.seriesViewSignature) {
      state.expandedSeries.clear();
      state.cardLimit = 24;
      state.seriesViewSignature = signature;
    }
  }

  function getFilteredRows() {
    var rows = state.rows.slice();

    // 默认隐藏越野车/货车/皮卡/大客车等用户配置的车型分类
    rows = rows.filter(rowMatchesDefaultRowType);

    // Saved sale-page approval is evidence of sale scope; missing status is not.
    if (state.saleScope === "onSale") {
      var onSaleCutoff = currentYearMonthKey();
      rows = rows.filter(function (row) { return rowIsOnSale(row, onSaleCutoff); });
    }

    var search = normalizeText(state.search);

    if (state.source) {
      rows = rows.filter(function (row) { return String(row["数据来源"] || "").indexOf(state.source) !== -1; });
    }
    if (state.brand) {
      rows = rows.filter(function (row) { return row["品牌"] === state.brand; });
    }
    if (state.series) {
      rows = rows.filter(function (row) { return row["车系"] === state.series; });
    }
    if (search) {
      rows = rows.filter(function (row) {
        return Object.keys(row).some(function (key) {
          return normalizeText(row[key]).indexOf(search) !== -1 || normalizeText(key).indexOf(search) !== -1;
        });
      });
    }

    (state.config.conditions || []).forEach(function (condition) {
      var activeRange = state.rangeFilters[condition.id];
      var activeFeature = state.featureFilters[condition.id];
      if (condition.type === "range" && !activeRange) {
        return;
      }
      if (isFeatureCondition(condition) && !activeFeature) {
        return;
      }
      rows = rows.filter(function (row) { return conditionMatches(row, condition); });
    });

    Object.keys(state.columnFilters).forEach(function (column) {
      var filter = state.columnFilters[column];
      if (!filter || filter.value === "") {
        return;
      }
      rows = rows.filter(function (row) {
        var text = normalizeText(row[column]);
        var value = normalizeText(filter.value);
        var number = firstNumber(row[column]);
        if (filter.operator === "contains") {
          return text.indexOf(value) !== -1;
        }
        if (number == null) {
          return false;
        }
        if (filter.operator === "gte") {
          return number >= Number(filter.value);
        }
        if (filter.operator === "lte") {
          return number <= Number(filter.value);
        }
        return filter.operator === "equals" ? text === value : text.indexOf(value) !== -1;
      });
    });

    return sortRows(rows);
  }

  function renderOptions(select, values, label) {
    select.textContent = "";
    var allOption = document.createElement("option");
    allOption.value = "";
    allOption.textContent = "全部" + label;
    select.appendChild(allOption);
    values.forEach(function (value) {
      var option = document.createElement("option");
      option.value = value;
      option.textContent = value;
      select.appendChild(option);
    });
  }

  var columnPaths = new Map();

  function columnPath(column) {
    if (columnPaths.has(column)) { return columnPaths.get(column); }
    var found = null;
    var suspect = /^(?:\d+(?:\.\d+)?(?:\s*(?:英寸|寸|km\b|kW\b|W\b|L\b|°|个|点|座|幅|款)|$)|支持$|不支持$|标配$|选配$|黑色$|白色$)|(?:选装包|套件|套装)/i.test(column);
    // 声明过的精确列名/条件字段优先于任何类别宽正则；同级冲突仍按配置原顺序取第一个命中。
    var declaredFields = function (section) {
      var fields = (section.columns || []).slice();
      (state.config.conditions || []).forEach(function (condition) {
        if ((section.conditionIds || []).indexOf(condition.id) !== -1) {
          fields = fields.concat(condition.fields || [], condition.field || []);
        }
      });
      return fields;
    };
    var accept = function (category, section, major, minor) {
      found = {major: category.label, minor: section.label, rank: [major, minor], id: category.id + "/" + section.id};
    };
    getFilterTaxonomy().some(function (category, major) {
      return (category.sections || []).some(function (section, minor) {
        if (declaredFields(section).indexOf(column) === -1) { return false; }
        accept(category, section, major, minor);
        return true;
      });
    });
    if (!found && !suspect) {
      getFilterTaxonomy().some(function (category, major) {
        return (category.sections || []).some(function (section, minor) {
          var matches = (section.columnPatterns || []).some(function (pattern) {
            return new RegExp(pattern).test(column);
          });
          if (!matches) { return false; }
          accept(category, section, major, minor);
          return true;
        });
      });
    }
    if (!found) {
      found = {major: "未分类/待确认", minor: suspect ? "疑似属性值 · 字段待核验" : "属性待归类",
        rank: [10000, suspect ? 1 : 0], id: "unclassified/" + (suspect ? "suspect" : "unknown")};
    }
    columnPaths.set(column, found);
    return found;
  }

  function orderedColumns(columns) {
    return columns.map(function (name, index) { return {name: name, path: columnPath(name), index: index}; })
      .sort(function (a, b) { return a.path.rank[0] - b.path.rank[0] || a.path.rank[1] - b.path.rank[1] || a.index - b.index; })
      .map(function (entry) { return entry.name; });
  }

  function columnGroups(columns) {
    var groups = [];
    orderedColumns(columns).forEach(function (column) {
      var path = columnPath(column);
      var group = groups[groups.length - 1];
      if (!group || group.id !== path.id) { group = {id: path.id, path: path, columns: []}; groups.push(group); }
      group.columns.push(column);
    });
    return groups;
  }

  function appendColumnOptions(select, columns) {
    select.textContent = "";
    columnGroups(columns).forEach(function (group) {
      var optgroup = document.createElement("optgroup");
      optgroup.label = group.path.major + " / " + group.path.minor;
      group.columns.forEach(function (column) {
        var option = document.createElement("option");
        option.value = column;
        option.textContent = column;
        optgroup.appendChild(option);
      });
      select.appendChild(optgroup);
    });
  }

  function renderFilters() {
    if (els.brandFilter && els.seriesFilter) {
      renderOptions(els.brandFilter, uniqueValues(state.rows, "品牌"), "品牌");
      renderOptions(els.seriesFilter, uniqueValues(state.brand ? state.rows.filter(function (row) {
        return row["品牌"] === state.brand;
      }) : state.rows, "车系"), "车系");
      els.brandFilter.value = state.brand;
      els.seriesFilter.value = state.series;
    }

    appendColumnOptions(els.fieldSelect, state.columns);
  }

  function renderConditions() {
    var fragment = document.createDocumentFragment();
    els.conditionList.textContent = "";
    var centerIds = centerConditionIds();
    var sideConditions = (state.config.conditions || []).filter(function (condition) {
      return !centerIds.has(condition.id);
    });
    if (els.advancedConditionSection) {
      els.advancedConditionSection.hidden = sideConditions.length === 0;
    }
    sideConditions.forEach(function (condition) {
      var item = document.createElement("div");
      item.className = "condition-item";
      item.dataset.conditionId = condition.id;

      var title = document.createElement("label");
      title.className = "condition-title";
      if (isFeatureCondition(condition)) {
        var checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.checked = Boolean(state.featureFilters[condition.id]);
        checkbox.dataset.conditionId = condition.id;
        title.appendChild(checkbox);
      }
      var text = document.createElement("span");
      text.textContent = conditionTagLabel(condition);
      title.appendChild(text);
      item.appendChild(title);

      if (condition.type === "range") {
        var controls = document.createElement("div");
        controls.className = "range-controls";
        ["min", "max"].forEach(function (side) {
          var input = document.createElement("input");
          input.type = "number";
          input.inputMode = "decimal";
          input.placeholder = side === "min" ? "最小" : "最大";
          input.dataset.conditionId = condition.id;
          input.dataset.side = side;
          var active = state.rangeFilters[condition.id] || {};
          input.value = active[side] != null ? active[side] : (condition[side] != null ? condition[side] : "");
          controls.appendChild(input);
        });
        var button = document.createElement("button");
        button.type = "button";
        button.dataset.conditionId = condition.id;
        button.textContent = "筛选";
        controls.appendChild(button);
        item.appendChild(controls);
      }

      fragment.appendChild(item);
    });
    els.conditionList.appendChild(fragment);
  }

  function sortMark(column) {
    if (state.sortField !== column) {
      return "";
    }
    return state.sortDir === "asc" ? "↑" : "↓";
  }

  function syncTableHeaderOffsets() {
    var rows = Array.from(els.tableHead.children);
    var heights = rows.map(function (row) {
      return typeof row.getBoundingClientRect === "function" ? row.getBoundingClientRect().height : 0;
    });
    // Hidden table rows have no layout. Keep the last valid offsets until shown.
    if (!rows.length || heights.some(function (height) { return !(height > 0); })) { return; }
    var top = 0;
    rows.forEach(function (row, index) {
      Array.from(row.children).forEach(function (cell) { cell.style.top = top + "px"; });
      top += heights[index];
    });
    els.tableHead.setAttribute("data-measured", "true");
  }

  function renderTableHead() {
    var visibleColumns = state.columns.filter(function (column) { return state.visibleColumns.has(column); });
    els.tableHead.setAttribute("data-measured", "false");
    els.tableHead.textContent = "";

    var groups = columnGroups(visibleColumns);
    var majorRow = document.createElement("tr");
    majorRow.className = "table-major-row";
    var minorRow = document.createElement("tr");
    minorRow.className = "table-minor-row";
    var majorCell = null;
    var previousMajor = "";
    groups.forEach(function (group) {
      if (previousMajor !== group.path.major) {
        majorCell = document.createElement("th");
        majorCell.scope = "colgroup";
        majorCell.colSpan = 0;
        majorCell.textContent = group.path.major;
        majorRow.appendChild(majorCell);
        previousMajor = group.path.major;
      }
      majorCell.colSpan += group.columns.length;
      var minorCell = document.createElement("th");
      minorCell.scope = "colgroup";
      minorCell.colSpan = group.columns.length;
      minorCell.textContent = group.path.minor;
      minorRow.appendChild(minorCell);
    });
    els.tableHead.appendChild(majorRow);
    els.tableHead.appendChild(minorRow);
    var titleRow = document.createElement("tr");
    titleRow.className = "table-column-row";
    visibleColumns.forEach(function (column) {
      var th = document.createElement("th");
      var button = document.createElement("button");
      button.type = "button";
      button.className = "sort-button";
      button.dataset.column = column;
      th.scope = "col";
      button.title = columnPath(column).major + " / " + columnPath(column).minor + " / " + column + " · 点击排序";
      var name = document.createElement("span");
      name.textContent = column;
      var mark = document.createElement("span");
      mark.textContent = sortMark(column);
      button.appendChild(name);
      button.appendChild(mark);
      th.appendChild(button);
      titleRow.appendChild(th);
    });

    var filterRow = document.createElement("tr");
    filterRow.className = "filter-row";
    visibleColumns.forEach(function (column) {
      var th = document.createElement("th");
      var input = document.createElement("input");
      input.className = "filter-input";
      input.dataset.column = column;
      input.value = state.columnFilters[column] ? state.columnFilters[column].value : "";
      input.placeholder = "筛选 " + column;
      input.setAttribute("aria-label", columnPath(column).major + " / " + columnPath(column).minor + " / " + column);
      th.appendChild(input);
      filterRow.appendChild(th);
    });
    els.tableHead.appendChild(titleRow);
    els.tableHead.appendChild(filterRow);
    syncTableHeaderOffsets();
  }

  function renderTableBody(rows) {
    var epoch = ++state.tableRenderEpoch;
    var visibleColumns = state.columns.filter(function (column) { return state.visibleColumns.has(column); });
    var all = state.tableDisplayMode === "all";
    var start = all ? 0 : (state.page - 1) * state.pageSize;
    var pageRows = all ? rows : rows.slice(start, start + state.pageSize);
    var offset = 0;
    els.tableBody.textContent = "";
    els.emptyState.hidden = rows.length !== 0;
    if (all && state.mode !== "table") {
      els.tableBody.setAttribute("aria-busy", "false");
      if (els.tableRenderStatus) { els.tableRenderStatus.textContent = "进入数据表后显示全部匹配 SKU"; }
      return;
    }
    function appendBatch() {
      if (epoch !== state.tableRenderEpoch) { return; }
      var end = Math.min(pageRows.length, offset + Math.max(1, Math.min(100, Math.floor(1500 / Math.max(1, visibleColumns.length)))));
      for (; offset < end; offset += 1) {
        var row = pageRows[offset];
        var tr = document.createElement("tr");
        visibleColumns.forEach(function (column) {
          var td = document.createElement("td");
          td.textContent = row[column] == null || row[column] === "" ? "-" : row[column];
          tr.appendChild(td);
        });
        els.tableBody.appendChild(tr);
      }
      els.tableBody.setAttribute("aria-busy", offset < pageRows.length ? "true" : "false");
      if (els.tableRenderStatus) { els.tableRenderStatus.textContent = "已显示 " + offset + " / " + pageRows.length + " 条 SKU"; }
      if (offset < pageRows.length) {
        if (typeof window.requestAnimationFrame === "function") { window.requestAnimationFrame(appendBatch); }
        else { setTimeout(appendBatch, 0); }
      }
    }
    appendBatch();
  }

  function classifySkuColumns(columns, rows) {
    var core = new Set(state.config.defaultVisibleColumns || []);
    var sample = (rows || []).slice(0, 2000);
    var result = { attribute: [], option: [] };
    (columns || []).forEach(function (column) {
      if (core.has(column)) { result.attribute.push(column); return; }
      var filled = 0;
      for (var i = 0; i < sample.length; i += 1) {
        var value = String(sample[i][column] == null ? "" : sample[i][column]).trim();
        if (value && value !== "-") { filled += 1; }
      }
      var dense = sample.length > 0 && filled / sample.length >= 0.05;
      (dense ? result.attribute : result.option).push(column);
    });
    return result;
  }

  function renderColumnList() {
    var query = normalizeText(state.columnSearch);
    els.columnList.textContent = "";
    var previousMajor = "";
    var major = null;
    columnGroups(state.columns.filter(function (column) { return !query || normalizeText(column).indexOf(query) !== -1; })).forEach(function (group) {
      if (previousMajor !== group.path.major) {
        major = document.createElement("section");
        major.className = "column-major-group";
        var heading = document.createElement("h3");
        heading.textContent = group.path.major;
        major.appendChild(heading);
        els.columnList.appendChild(major);
        previousMajor = group.path.major;
      }
      var minor = document.createElement("details");
      minor.className = "column-minor-group";
      minor.open = true;
      var summary = document.createElement("summary");
      summary.textContent = group.path.minor + "（" + group.columns.length + "）";
      minor.appendChild(summary);
      group.columns.forEach(function (column) {
        var label = document.createElement("label");
        var checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.checked = state.visibleColumns.has(column);
        checkbox.dataset.column = column;
        var text = document.createElement("span");
        text.textContent = column;
        label.appendChild(checkbox);
        label.appendChild(text);
        minor.appendChild(label);
      });
      major.appendChild(minor);
    });
  }

  function filterLabel(column, filter) {
    if (!filter) {
      return "";
    }
    if (filter.operator === "contains") {
      return column + ": " + filter.value;
    }
    var symbol = filter.operator === "gte" ? "≥" : (filter.operator === "lte" ? "≤" : "=");
    return column + " " + symbol + " " + filter.value;
  }

  function renderActiveFilters() {
    els.activeFilters.textContent = "";
    Object.keys(state.columnFilters).forEach(function (column) {
      var filter = state.columnFilters[column];
      if (!filter || filter.value === "") {
        return;
      }
      var chip = document.createElement("span");
      chip.className = "filter-chip";
      chip.textContent = filterLabel(column, filter);
      var close = document.createElement("button");
      close.type = "button";
      close.dataset.column = column;
      close.textContent = "×";
      chip.appendChild(close);
      els.activeFilters.appendChild(chip);
    });
  }

  function renderDownloads() {
    var files = state.manifest && state.manifest.files ? state.manifest.files : {};
    var links = [["完整 JSON", files.latestJson], ["完整 CSV", files.latestCsv], ["默认筛选 JSON", files.filteredJson], ["默认筛选 CSV", files.filteredCsv]];
    els.downloadList.textContent = "";
    links.forEach(function (item) {
      if (!item[1]) {
        return;
      }
      var anchor = document.createElement("a");
      anchor.href = item[1];
      anchor.textContent = item[0] + (/\.gz$/.test(item[1]) ? "（GZIP）" : "");
      anchor.download = "";
      els.downloadList.appendChild(anchor);
    });
    if (files.latestJsonChunks && !files.latestJson && state.publishedRawRows) {
      var fullJson = document.createElement("a");
      fullJson.href = "#";
      fullJson.textContent = "完整 JSON";
      fullJson.addEventListener("click", function (event) {
        event.preventDefault();
        downloadBlob("car-config-full.json", "application/json;charset=utf-8", JSON.stringify(state.publishedRawRows));
      });
      els.downloadList.appendChild(fullJson);
    }
    if (files.filteredJsonChunks && !files.filteredJson) {
      var filteredJson = document.createElement("a");
      filteredJson.href = "#";
      filteredJson.textContent = "默认筛选 JSON";
      filteredJson.addEventListener("click", function (event) {
        event.preventDefault();
        var count = files.filteredJsonChunks.reduce(function (sum, chunk) { return sum + chunk.rowCount; }, 0);
        loadPublishedChunks(files.filteredJsonChunks, count).then(function (rows) {
          downloadBlob("car-config-default-filtered.json", "application/json;charset=utf-8", JSON.stringify(rows));
        }).catch(function (error) { els.dataMeta.textContent = "下载校验失败：" + error.message; });
      });
      els.downloadList.appendChild(filteredJson);
    }
    if (state.manifest && state.manifest.omittedDownloads && state.manifest.omittedDownloads.length) {
      var note = document.createElement("span");
      note.textContent = "完整车型数据已全部加载；超出托管文件大小限制的 CSV 不提供直链，可导出当前筛选结果。";
      els.downloadList.appendChild(note);
    }
    if (!els.downloadList.children.length) {
      els.downloadList.textContent = "发布后会显示 Release 同款下载文件。";
    }
  }

  function renderHistory() {
    els.historySyncId.value = state.syncId;
    els.historyList.textContent = "";
    if (!state.histories.length) {
      els.historyList.textContent = "暂无筛选历史。";
      return;
    }
    state.histories.slice().reverse().forEach(function (item) {
      var row = document.createElement("div");
      row.className = "history-item";
      var button = document.createElement("button");
      button.type = "button";
      button.dataset.historyId = item.id;
      button.textContent = item.name || "未命名筛选";
      var meta = document.createElement("span");
      meta.textContent = (item.resultCount || 0) + " 辆 · " + new Date(item.createdAt || Date.now()).toLocaleString("zh-CN");
      row.appendChild(button);
      row.appendChild(meta);
      els.historyList.appendChild(row);
    });
  }


  function renderMode() {
    // 负责人 10-16 口径：切到"数据表/高级模式"要**保留筛选条件也保留筛选栏**，
    // 所以两个模式共用 #filterCenter，只把"车系卡片"专属的块让位给数据表。
    var table = state.mode === "table";
    els.filterCenter.hidden = false;
    els.tableRegion.hidden = !table;
    if (els.cardList) { els.cardList.hidden = table; }
    if (els.cardToolbar) { els.cardToolbar.hidden = table; }
    if (els.centerActions) { els.centerActions.hidden = table; }
    if (els.mobileFilterActions) { els.mobileFilterActions.hidden = table; }
    // 筛选栏保留（10-16 口径），但数据表必须回到主栏：隐藏只服务"筛选中心"的 hero，
    // 并给 workspace 一个模式类，由 CSS 把 center 跨两栏、table 放回第一栏（否则自动排布会把
    // table 塞进右侧 310px 的侧栏列，侧栏掉到左下——10-21 实测）。
    if (els.centerHero) { els.centerHero.hidden = table; }
    if (els.workspace) {
      var classes = String(els.workspace.className || "").split(/\s+/).filter(function (name) {
        return name && name !== "mode-table";
      });
      if (table) { classes.push("mode-table"); }
      els.workspace.className = classes.join(" ");
    }
    els.centerMode.className = table ? "segment" : "segment active";
    els.tableMode.className = table ? "segment active" : "segment";
  }

  function bindPanelToggle(toggleEl, bodyEl) {
    // 右侧竖栏折叠：只切 body 的 hidden 与按钮文案，不动筛选状态
    if (!toggleEl || !bodyEl) { return; }
    toggleEl.addEventListener("click", function () {
      var open = bodyEl.hidden;
      bodyEl.hidden = !open;
      toggleEl.setAttribute("aria-expanded", open ? "true" : "false");
      toggleEl.textContent = open ? "收起" : "展开";
    });
  }

  function applySaleScopeButtons() {
    if (!els.saleScopeOnSale || !els.saleScopeAll) { return; }
    var onSale = state.saleScope === "onSale";
    els.saleScopeOnSale.className = onSale ? "segment active" : "segment";
    els.saleScopeAll.className = onSale ? "segment" : "segment active";
  }

  function getFilterTaxonomy() {
    return Array.isArray(state.config.filterTaxonomy) ? state.config.filterTaxonomy : [];
  }

  function taxonomyConditionGroups() {
    var conditionGroup = {};
    getFilterTaxonomy().forEach(function (category) {
      (category.sections || []).forEach(function (section) {
        (section.conditionIds || []).forEach(function (id) {
          conditionGroup[id] = section.desktopGroupId;
        });
      });
    });
    return conditionGroup;
  }

  function desktopConditionGroups() {
    var definitions = state.config.desktopConditionGroups || [];
    var conditionGroup = taxonomyConditionGroups();
    if (!definitions.length || !Object.keys(conditionGroup).length) {
      return state.config.centerConditionGroups || [];
    }
    return definitions.map(function (definition) {
      return {
        id: definition.id,
        label: definition.label,
        conditionIds: (state.config.conditions || []).filter(function (condition) {
          return conditionGroup[condition.id] === definition.id;
        }).map(function (condition) { return condition.id; })
      };
    }).filter(function (group) { return group.conditionIds.length; });
  }

  function centerConditionIds() {
    var ids = new Set();
    getFilterTaxonomy().forEach(function (category) {
      (category.sections || []).forEach(function (section) {
        (section.conditionIds || []).forEach(function (id) { ids.add(id); });
      });
    });
    if (!ids.size) {
      (state.config.centerConditionGroups || []).forEach(function (group) {
        (group.conditionIds || []).forEach(function (id) { ids.add(id); });
      });
    }
    return ids;
  }

  function mobileFilterLayoutMatches() {
    return typeof window.matchMedia === "function" && window.matchMedia("(max-width: 720px)").matches;
  }

  function selectedCountForCategory(category) {
    var count = 0;
    (category.sections || []).forEach(function (section) {
      (section.conditionIds || []).forEach(function (id) {
        if (state.rangeFilters[id] || state.featureFilters[id]) { count += 1; }
      });
    });
    return count;
  }

  function renderMobileCategoryBadges() {
    if (!els.centerConditionList.querySelectorAll) { return; }
    var categories = getFilterTaxonomy();
    els.centerConditionList.querySelectorAll(".major-category-button").forEach(function (button) {
      var category = categories.find(function (item) { return item.id === button.dataset.categoryId; });
      var badge = button.querySelectorAll ? button.querySelectorAll(".major-category-badge")[0] : null;
      if (badge && category) {
        var count = selectedCountForCategory(category);
        badge.textContent = String(count);
        badge.hidden = count === 0;
      }
    });
  }

  function activateMobileCategory(categoryId, focusPane) {
    var categories = getFilterTaxonomy();
    if (!categories.some(function (category) { return category.id === categoryId; })) { return; }
    state.mobileCategoryId = categoryId;
    if (!els.centerConditionList.querySelectorAll) { return; }
    els.centerConditionList.querySelectorAll(".major-category-button").forEach(function (button) {
      var active = button.dataset.categoryId === categoryId;
      button.setAttribute("aria-selected", active ? "true" : "false");
      button.className = active ? "major-category-button active" : "major-category-button";
    });
    els.centerConditionList.querySelectorAll(".mobile-category-panel").forEach(function (panel) {
      var active = panel.dataset.categoryId === categoryId;
      panel.hidden = !active;
      if (active && focusPane && typeof panel.focus === "function") {
        panel.focus({ preventScroll: true });
      }
    });
    var pane = els.centerConditionList.querySelectorAll(".minor-content-pane")[0];
    if (pane) { pane.scrollTop = 0; }
  }

  function renderMobileFilterCenter(conditions, categories) {
    if (!categories.length) {
      conditions.forEach(function (condition) { els.centerConditionList.appendChild(buildCenterConditionItem(condition)); });
      return;
    }
    if (!state.mobileCategoryId || !categories.some(function (category) { return category.id === state.mobileCategoryId; })) {
      state.mobileCategoryId = categories[0].id;
    }
    var layout = document.createElement("div");
    layout.className = "mobile-filter-layout";
    var rail = document.createElement("nav");
    rail.className = "major-category-rail";
    rail.setAttribute("aria-label", "筛选大类");
    rail.setAttribute("role", "tablist");
    var pane = document.createElement("div");
    pane.className = "minor-content-pane";
    pane.setAttribute("aria-label", "筛选具体条件");

    categories.forEach(function (category) {
      var active = category.id === state.mobileCategoryId;
      var button = document.createElement("button");
      button.type = "button";
      button.className = active ? "major-category-button active" : "major-category-button";
      button.dataset.categoryId = category.id;
      button.setAttribute("role", "tab");
      button.setAttribute("aria-selected", active ? "true" : "false");
      button.setAttribute("aria-controls", "mobile-category-pane-" + category.id);
      button.id = "mobile-category-tab-" + category.id;
      var label = document.createElement("span");
      label.className = "major-category-label";
      label.textContent = category.label;
      var badge = document.createElement("span");
      badge.className = "major-category-badge";
      var count = selectedCountForCategory(category);
      badge.textContent = String(count);
      badge.hidden = count === 0;
      button.appendChild(label);
      button.appendChild(badge);
      rail.appendChild(button);

      var categoryPanel = document.createElement("section");
      categoryPanel.className = "mobile-category-panel";
      categoryPanel.id = "mobile-category-pane-" + category.id;
      categoryPanel.dataset.categoryId = category.id;
      categoryPanel.setAttribute("role", "tabpanel");
      categoryPanel.setAttribute("aria-labelledby", "mobile-category-tab-" + category.id);
      categoryPanel.setAttribute("tabindex", "-1");
      categoryPanel.hidden = !active;
      var categoryTitle = document.createElement("h3");
      categoryTitle.className = "mobile-category-title";
      categoryTitle.textContent = category.label;
      categoryPanel.appendChild(categoryTitle);
      (category.sections || []).forEach(function (section) {
        var sectionEl = document.createElement("section");
        sectionEl.className = "mobile-minor-section";
        sectionEl.setAttribute("aria-labelledby", "mobile-minor-title-" + section.id);
        var sectionTitle = document.createElement("h4");
        sectionTitle.className = "mobile-minor-title";
        sectionTitle.id = "mobile-minor-title-" + section.id;
        sectionTitle.textContent = section.label;
        sectionEl.appendChild(sectionTitle);
        var grid = document.createElement("div");
        grid.className = "mobile-option-grid";
        (section.conditionIds || []).forEach(function (conditionId) {
          var condition = conditions.find(function (item) { return item.id === conditionId; });
          if (condition) { grid.appendChild(buildCenterConditionItem(condition)); }
        });
        sectionEl.appendChild(grid);
        categoryPanel.appendChild(sectionEl);
      });
      pane.appendChild(categoryPanel);
    });
    layout.appendChild(rail);
    layout.appendChild(pane);
    els.centerConditionList.appendChild(layout);
  }

  function sectionHasResolvableCondition(section, conditions) {
    return (section.conditionIds || []).some(function (id) {
      return conditions.some(function (condition) { return condition.id === id; });
    });
  }

  function renderCenterFilters() {
    if (els.centerBrandFilter && els.centerSeriesFilter) {
      renderOptions(els.centerBrandFilter, uniqueValues(state.rows, "品牌"), "品牌");
      renderOptions(els.centerSeriesFilter, uniqueValues(state.brand ? state.rows.filter(function (row) { return row["品牌"] === state.brand; }) : state.rows, "车系"), "车系");
      els.centerBrandFilter.value = state.brand;
      els.centerSeriesFilter.value = state.series;
    }
    els.centerConditionList.textContent = "";
    var conditions = state.config.conditions || [];
    var taxonomy = getFilterTaxonomy().filter(function (category) {
      return (category.sections || []).some(function (section) {
        return sectionHasResolvableCondition(section, conditions);
      });
    }).map(function (category) {
      return Object.assign({}, category, {sections: (category.sections || []).filter(function (section) {
        return sectionHasResolvableCondition(section, conditions);
      })});
    });
    if (mobileFilterLayoutMatches() && taxonomy.length) {
      renderMobileFilterCenter(conditions, taxonomy);
      return;
    }
    if (taxonomy.length) {
      taxonomy.forEach(function (category) {
        var sections = (category.sections || []).filter(function (section) { return sectionHasResolvableCondition(section, conditions); });
        if (!sections.length) { return; }
        var major = document.createElement("section");
        major.className = "condition-major-group";
        var heading = document.createElement("h3");
        heading.textContent = category.label;
        major.appendChild(heading);
        sections.forEach(function (section) {
          var minor = document.createElement("div");
          minor.className = "condition-minor-group";
          var subheading = document.createElement("h4");
          subheading.textContent = section.label;
          minor.appendChild(subheading);
          (section.conditionIds || []).forEach(function (id) {
            var condition = conditions.find(function (item) { return item.id === id; });
            if (condition) { minor.appendChild(buildCenterConditionItem(condition)); }
          });
          major.appendChild(minor);
        });
        els.centerConditionList.appendChild(major);
      });
    } else {
      conditions.forEach(function (condition) { els.centerConditionList.appendChild(buildCenterConditionItem(condition)); });
    }
  }

  function buildCenterConditionItem(condition) {
    var wrapper = document.createElement("div");
    wrapper.className = "center-condition-item";
    wrapper.dataset.conditionId = condition.id;
    wrapper.dataset.conditionType = condition.type;
    if (condition.type === "range") {
      var label = document.createElement("label");
      label.className = "center-range-label";
      var checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.dataset.conditionId = condition.id;
      checkbox.dataset.conditionType = "range";
      checkbox.checked = Boolean(state.rangeFilters[condition.id]);
      label.appendChild(checkbox);
      label.appendChild(document.createTextNode(condition.label + (condition.unit ? "(" + condition.unit + ")" : "")));
      wrapper.appendChild(label);
      var rangeInputs = document.createElement("div");
      rangeInputs.className = "center-range-inputs";
      ["min", "max"].forEach(function (side) {
        var input = document.createElement("input");
        input.type = "number";
        input.inputMode = "decimal";
        input.placeholder = side === "min" ? "最小" : "最大";
        input.dataset.conditionId = condition.id;
        input.dataset.side = side;
        var active = state.rangeFilters[condition.id] || {};
        input.value = active[side] != null && active[side] !== "" ? active[side] : "";
        rangeInputs.appendChild(input);
      });
      wrapper.appendChild(rangeInputs);
    } else {
      var label2 = document.createElement("label");
      var input2 = document.createElement("input");
      input2.type = "checkbox";
      input2.dataset.conditionId = condition.id;
      input2.dataset.conditionType = "feature";
      input2.checked = Boolean(state.featureFilters[condition.id]);
      label2.appendChild(input2);
      label2.appendChild(document.createTextNode(condition.label));
      wrapper.appendChild(label2);
    }
    return wrapper;
  }

  function rangeBoundText(value) {
    return String(value == null ? "" : value).trim();
  }

  function isZeroBound(value) {
    var text = rangeBoundText(value);
    return text !== "" && Number(text) === 0;
  }

  function conditionTagLabel(condition) {
    if (condition.type !== "range") {
      return condition.label;
    }
    var filter = state.rangeFilters[condition.id] || {};
    var min = rangeBoundText(filter.min);
    var max = rangeBoundText(filter.max);
    // 下限 0 是没有信息量的边界（"≥0" 恒真），不往标签上写；上限 0 是真条件，照旧显示。
    if (isZeroBound(min)) { min = ""; }
    if (min && max) {
      // 正下限 + 上限：两边都写，语义与改动前一致，只是不再出现 `≥0`。
      return condition.label + " ≥" + min + " ≤" + max;
    }
    if (max) {
      return condition.label + " ≤" + max;
    }
    if (min) {
      return condition.label + " ≥" + min;
    }
    return condition.label;
  }

  function renderSelectedTags() {
    els.selectedTags.textContent = "";
    [["品牌", state.brand], ["车系", state.series]].forEach(function (item) {
      if (!item[1]) { return; }
      var tag = document.createElement("span");
      tag.textContent = item[0] + ": " + item[1];
      els.selectedTags.appendChild(tag);
    });
    (state.config.conditions || []).forEach(function (condition) {
      if (state.featureFilters[condition.id] || state.rangeFilters[condition.id]) {
        var tag = document.createElement("span");
        tag.textContent = conditionTagLabel(condition);
        els.selectedTags.appendChild(tag);
      }
    });
  }

  function appendCardMeta(container, row, fields) {
    fields.forEach(function (field) {
      if (row[field] && row[field] !== "-") {
        var value = row[field];
        if (field === "能源类型") {
          value = normEnumValue(String(value), field);
        }
        var chip = document.createElement("span");
        chip.textContent = field + ": " + value;
        container.appendChild(chip);
      }
    });
    if (row["交叉核验"] === "双源核验" || rowHasSource(row, "汽车之家") && rowHasSource(row, "懂车帝")) {
      var badge = document.createElement("span");
      badge.className = "verified-badge";
      badge.textContent = "双源核验";
      container.appendChild(badge);
    }
  }

  function listingYearMonth(value) {
    // `2025.09` / `2025-9` / `2025年9月` / `2025/09` → 202509；拿不到就返回 null。
    // 不复用 firstNumber：浮点比会把 `2026.11`（11 月）判到 `2026.9`（9 月）之前。
    var m = String(value || "").match(/(\d{4})\s*[.\-\/年]\s*(\d{1,2})/);
    if (m) { return Number(m[1]) * 100 + Number(m[2]); }
    var y = String(value || "").match(/(\d{4})/);
    return y ? Number(y[1]) * 100 + 1 : null;
  }

  function currentYearMonthKey(now) {
    var d = now || new Date();
    return d.getFullYear() * 100 + d.getMonth() + 1;
  }

  function rowIsOnSale(row, cutoffKey) {
    var statuses = [row["易车上市状态"], row["销售状态"], row["在售状态"]];
    var approved = false;
    var rejected = false;
    statuses.forEach(function (value) {
      splitDisplaySegments(value).forEach(function (part) {
        var status = stripSourceSegmentPrefix(part);
        if (/^(approved|在售|销售中)$/.test(status)) { approved = true; }
        else if (status && status !== "-") { rejected = true; }
      });
    });
    var key = listingYearMonth(row["上市时间"]);
    return approved && !rejected && (key === null || key <= cutoffKey);
  }

  function cardSortValue(row, level) {
    if (!level) { return null; }
    if (level.field === "数据来源") { return sourceCount(row); }
    if (level.field === "车系") { return seriesIdentity(row).name; }
    if (level.field === "上市时间") {
      var rawDate = row[level.field];
      if (!rawDate) { return null; }
      var dateNumber = firstNumber(rawDate);
      if (dateNumber != null) { return dateNumber; }
      return String(rawDate);
    }
    var number = firstNumber(row[level.field]);
    return number == null ? null : number;
  }

  function sortSeriesGroups(groups) {
    var level = state.cardSort;
    if (!level || !level.field) { return groups; }
    var dir = level.dir === "desc" ? -1 : 1;
    function compareValues(a, b) {
      if (a == null && b == null) { return 0; }
      if (a == null) { return 1; }
      if (b == null) { return -1; }
      if (typeof a === "number" && typeof b === "number") { return a - b; }
      return String(a).localeCompare(String(b), "zh-Hans");
    }
    function dirCompare(left, right) {
      // nulls always sort last, independent of the direction.
      var leftNull = cardSortValue(left, level) == null;
      var rightNull = cardSortValue(right, level) == null;
      if (leftNull || rightNull) {
        return compareValues(cardSortValue(left, level), cardSortValue(right, level));
      }
      return compareValues(cardSortValue(left, level), cardSortValue(right, level)) * dir;
    }
    groups.forEach(function (group) {
      group.rows.sort(dirCompare);
      group.representative = group.rows[0];
    });
    return groups.slice().sort(function (left, right) {
      var result = dirCompare(left.representative, right.representative);
      if (result !== 0) { return result; }
      return left.order - right.order;
    });
  }

  // Only energy fields use energy aliases; unrelated fields keep their actual values.
  function normEnumValue(s, field) {
    if (field == null || field === "能源类型") { return normalizeEnergyText(s); }
    // A provider prefix is metadata; CLTC/WLTC and unknown labels carry real meaning.
    return stripSourceSegmentPrefix(String(s == null ? "" : s));
  }
  // Summaries and individual cards use the same semantic values.

  function appendCardSummary(container, rows, fields) {
    fields.forEach(function (field) {
      var values = [];
      rows.forEach(function (row) {
        var v = row[field];
        if (v == null) { return; }
        var s = String(v).trim();
        if (s === "" || s === "-") { return; }
        values.push(s);
      });
      if (!values.length) { return; }
      var uniq = [];
      values.forEach(function (v) { if (uniq.indexOf(v) === -1) { uniq.push(v); } });
      var allNumeric = values.every(function (v) { return /^-?[\d.]+/.test(v); });
      var text;
      if (field === "能源类型") {
        text = normalizeEnergyText(values.join("|"));
      } else if (allNumeric && uniq.length > 1) {
        // 管道/斜杠多值拆分（230|163|230|163、420|315|315/202|165/汽车之家:420|315）：取数字集，
        // 去重、排除 999 占位，再求 min-max；后缀取首个非空（如 万）。
        var nums = [];
        var suffix = "";
        values.forEach(function (v) {
          String(v).split(/[|/]/).forEach(function (part) {
            part = part.replace(/^[^:：]*[:：]/, "");
            var m = part.match(/-?[\d.]+/);
            if (!m) { return; }
            var n = parseFloat(m[0]);
            if (n === 999) { return; }
            if (nums.indexOf(n) === -1) { nums.push(n); }
            if (!suffix) {
              var tail = part.replace(/^-?[\d.]+/, "");
              if (tail) { suffix = tail; }
            }
          });
        });
        if (!nums.length) { return; }
        var min = Math.min.apply(null, nums);
        var max = Math.max.apply(null, nums);
        text = min === max ? String(min) + suffix : min + "-" + max + suffix;
      } else if (uniq.length === 1) {
        text = normEnumValue(uniq[0], field);
      } else {
        // 枚举多值：逐值归一 + 去重
        var normalized = [];
        uniq.forEach(function (v) {
          String(v).split(/[|/]/).forEach(function (part) {
            var nv = normEnumValue(part, field);
            if (nv && normalized.indexOf(nv) === -1) { normalized.push(nv); }
          });
        });
        text = normalized.join("/");
      }
      var chip = document.createElement("span");
      chip.textContent = field + ": " + text;
      container.appendChild(chip);
    });
  }

  function renderCards(groups) {
    els.cardList.textContent = "";
    var cardSnapshots = [];
    groups.slice(0, state.cardLimit).forEach(function (group, index) {
      var card = document.createElement("article");
      card.className = "series-card";
      var expanded = state.expandedSeries.has(group.key);
      var detailId = "series-models-" + index;
      var toggle = document.createElement("button");
      toggle.type = "button";
      toggle.className = "series-card-toggle";
      toggle.dataset.seriesKey = group.key;
      toggle.setAttribute("aria-expanded", String(expanded));
      toggle.setAttribute("aria-controls", detailId);
      var title = document.createElement("h3");
      title.textContent = group.name;
      var count = document.createElement("small");
      count.className = "series-match-count";
      count.textContent = group.rows.length + " 款车型符合条件";
      var indicator = document.createElement("span");
      indicator.className = "series-expand-indicator";
      indicator.setAttribute("aria-hidden", "true");
      indicator.textContent = expanded ? "收起" : "查看型号";
      toggle.appendChild(title);
      toggle.appendChild(count);
      toggle.appendChild(indicator);
      card.appendChild(toggle);

      // 全车系共性属性（品牌/级别等所有车型一致）只显示一行；
      // 可能有区别的属性（能源/价格/加速/驱动/续航）在下方每车型分行显示。
      var meta = document.createElement("div");
      meta.className = "card-meta";
      // 动态判定：筛选结果内全一致 -> 单值一行（共性）；数值有差异 -> 范围；
      // 枚举有差异 -> 汇总枚举（如 纯电/插混）。
      appendCardSummary(meta, group.rows, ["品牌", "级别", "能源类型", "官方指导价", "百公里加速(s)", "纯电续航(km)"]);
      card.appendChild(meta);

      var cardSnapshot = { meta: "", rows: [] };
      function collectText(el) {
        if (!el) { return ""; }
        if (el._textContent) { return el._textContent; }
        return Array.from(el.children || []).map(collectText).join("");
      }
      if (meta) { cardSnapshot.meta = collectText(meta); }
      if (expanded) {
        var details = document.createElement("div");
        details.className = "series-model-list";
        details.id = detailId;
        group.rows.forEach(function (row) {
          var model = document.createElement("div");
          model.className = "series-model-row";
          var modelTitle = document.createElement("h4");
          var yearSuffix = row["年款"] ? " " + row["年款"] + "款" : "";
          var baseName = row["车型名称"] || "未命名车型";
          if (yearSuffix && new RegExp("(?:19|20)\\d{2}款").test(baseName)) yearSuffix = "";
          modelTitle.textContent = baseName + yearSuffix;
          var modelMeta = document.createElement("div");
          modelMeta.className = "card-meta";
          appendCardMeta(modelMeta, row, ["能源类型", "官方指导价", "百公里加速(s)", "驱动方式", "纯电续航(km)"]);
          model.appendChild(modelTitle);
          model.appendChild(modelMeta);
          details.appendChild(model);
          if (modelMeta) { cardSnapshot.rows.push(collectText(modelTitle) + " " + collectText(modelMeta)); }
        });
        card.appendChild(details);
      }
      cardSnapshots.push(cardSnapshot);
      els.cardList.appendChild(card);
    });
    els.loadMoreCards.hidden = groups.length <= state.cardLimit;
    if (els.cardSortSelect) {
      var cardLevel = state.cardSort;
      els.cardSortSelect.value = cardLevel && cardLevel.field
        ? cardLevel.field + (cardLevel.dir === "desc" ? ":desc" : ":asc") : "default";
    }
    return cardSnapshots;
  }

  function renderCustomSortPanel() {
    if (!els.customSortLevels) { return; }
    els.customSortLevels.textContent = "";
    (state.sortLevels || []).forEach(function (level, index) {
      var row = document.createElement("div");
      row.className = "sort-level";
      row.dataset.index = String(index);
      row.innerHTML = '<label>字段<select data-role="field"></select></label><label>方向<select data-role="dir"><option value="asc">升序</option><option value="desc">降序</option></select></label><label>自定义关键字顺序<textarea data-role="customOrder" placeholder="插混, 纯电, 增程"></textarea></label><button type="button" data-role="up">上移</button><button type="button" data-role="down">下移</button><button type="button" data-role="remove">删除</button>';
      var select = row.querySelectorAll ? row.querySelectorAll('select[data-role="field"]')[0] : null;
      if (select) {
        appendColumnOptions(select, state.columns);
        select.value = level.field || "";
      }
      var dir = row.querySelectorAll ? row.querySelectorAll('select[data-role="dir"]')[0] : null;
      if (dir) { dir.value = level.dir || "asc"; }
      var custom = row.querySelectorAll ? row.querySelectorAll('textarea[data-role="customOrder"]')[0] : null;
      if (custom) { custom.value = level.customOrder || ""; }
      els.customSortLevels.appendChild(row);
    });
  }

  function renderResultsOnly() {
    syncSeriesViewState();
    var filtered = getFilteredRows();
    var seriesGroups = sortSeriesGroups(groupRowsBySeries(filtered));
    var signature = currentSeriesViewSignature();
    if (state.lastResultSignature !== signature) { state.page = 1; state.lastResultSignature = signature; }
    var allRows = state.tableDisplayMode === "all";
    var pageCount = allRows ? 1 : Math.max(1, Math.ceil(filtered.length / state.pageSize));
    if (state.page > pageCount) {
      state.page = pageCount;
    }
    els.visibleCount.textContent = String(filtered.length);
    els.totalCount.textContent = String(state.rows.length);
    els.columnCount.textContent = String(state.visibleColumns.size);
    els.verifiedCount.textContent = String(state.rows.filter(function (row) { return row["交叉核验"] === "双源核验"; }).length);
    els.dongchediCount.textContent = String(state.rows.filter(function (row) { return rowHasSource(row, "懂车帝"); }).length);
    els.autohomeCount.textContent = String(state.rows.filter(function (row) { return rowHasSource(row, "汽车之家"); }).length);
    els.yicheCount.textContent = String(state.rows.filter(function (row) { return rowHasSource(row, "易车"); }).length);
    els.pageInfo.textContent = allRows ? "单页全部 · " + filtered.length + " 条 SKU" : "第 " + state.page + " / " + pageCount + " 页";
    if (els.tableDisplayMode) { els.tableDisplayMode.value = state.tableDisplayMode; }
    els.pageSize.disabled = allRows;
    if (els.applyPageSize) { els.applyPageSize.disabled = allRows; }
    if (state.pageSizeDraft == null) { els.pageSize.value = String(state.pageSize); }
    els.pageJump.disabled = allRows;
    els.goPage.disabled = allRows;
    els.pageJump.max = String(pageCount);
    els.pageJump.value = String(state.page);
    els.prevPage.disabled = allRows || state.page <= 1;
    els.nextPage.disabled = allRows || state.page >= pageCount;
    els.centerVisibleCount.textContent = String(seriesGroups.length);
    if (els.mobileResultCount) { els.mobileResultCount.textContent = String(seriesGroups.length); }
    renderCards(seriesGroups);
    renderSelectedTags();
    renderTableBody(filtered);
    renderActiveFilters();
  }

  function renderEverything() {
    applySaleScopeButtons();
    renderMode();
    renderFilters();
    renderCenterFilters();
    renderConditions();
    renderTableHead();
    renderColumnList();
    renderDownloads();
    renderHistory();
    renderCustomSortPanel();
    renderResultsOnly();
  }

  function csvEscape(value) {
    var text = String(value == null ? "" : value);
    return /[",\n\r]/.test(text) ? '"' + text.replace(/"/g, '""') + '"' : text;
  }

  function downloadBlob(name, type, content) {
    var blob = new Blob([content], { type: type });
    var url = URL.createObjectURL(blob);
    var anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = name;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  }

  function exportCurrentCsv() {
    var rows = getFilteredRows();
    var columns = state.columns.filter(function (column) { return state.visibleColumns.has(column); });
    var lines = [columns.map(csvEscape).join(",")];
    rows.forEach(function (row) {
      lines.push(columns.map(function (column) { return csvEscape(row[column]); }).join(","));
    });
    downloadBlob("car-config-current.csv", "text/csv;charset=utf-8", "\ufeff" + lines.join("\n"));
  }

  function exportCurrentJson() {
    downloadBlob("car-config-current.json", "application/json;charset=utf-8", JSON.stringify(getFilteredRows(), null, 2));
  }

  function snapshotFilters() {
    return {
      search: state.search,
      brand: state.brand,
      series: state.series,
      columnFilters: state.columnFilters,
      rangeFilters: state.rangeFilters,
      featureFilters: state.featureFilters,
      sortField: state.sortField,
      sortDir: state.sortDir,
      sortLevels: state.sortLevels,
      mode: state.mode,
      saleScope: state.saleScope,
      tableDisplayMode: state.tableDisplayMode,
      pageSize: state.pageSize,
      visibleColumns: Array.from(state.visibleColumns)
    };
  }

  function applySnapshot(snapshot) {
    state.search = snapshot.search || "";
    state.brand = snapshot.brand || "";
    state.series = snapshot.series || "";
    state.columnFilters = snapshot.columnFilters || {};
    state.rangeFilters = snapshot.rangeFilters || {};
    state.featureFilters = snapshot.featureFilters || {};
    state.sortField = snapshot.sortField || "";
    state.sortDir = snapshot.sortDir || "asc";
    state.sortLevels = Array.isArray(snapshot.sortLevels) ? snapshot.sortLevels : [];
    state.mode = snapshot.mode || state.mode || "center";
    state.saleScope = snapshot.saleScope === "all" ? "all" : "onSale";
    state.tableDisplayMode = snapshot.tableDisplayMode === "all" ? "all" : "paged";
    state.pageSize = Number.isSafeInteger(snapshot.pageSize) && snapshot.pageSize > 0 ? snapshot.pageSize : 100;
    state.pageSizeDraft = null;
    if (Array.isArray(snapshot.visibleColumns)) {
      state.visibleColumns = new Set(snapshot.visibleColumns.filter(function (column) {
        return state.columns.indexOf(column) !== -1;
      }));
    }
    els.globalSearch.value = state.search;
    state.page = 1;
    renderEverything();
  }

  function generateSyncId() {
    if (window.crypto && crypto.getRandomValues) {
      var bytes = new Uint8Array(8);
      crypto.getRandomValues(bytes);
      return Array.from(bytes).map(function (byte) {
        return byte.toString(16).padStart(2, "0");
      }).join("");
    }
    return String(Date.now()) + Math.random().toString(16).slice(2);
  }

  function cacheHistories() {
    localStorage.setItem(STORAGE_HISTORY_KEY, JSON.stringify(state.histories));
  }

  function loadCachedHistories() {
    try {
      state.histories = JSON.parse(localStorage.getItem(STORAGE_HISTORY_KEY) || "[]");
    } catch (error) {
      state.histories = [];
    }
  }

  function githubHistoryConfigured() {
    return HISTORY_PROVIDER === "github" &&
      GITHUB_HISTORY &&
      GITHUB_HISTORY.owner &&
      GITHUB_HISTORY.repo &&
      GITHUB_HISTORY.path;
  }

  function githubHistoryApiUrl() {
    return "https://api.github.com/repos/" +
      encodeURIComponent(GITHUB_HISTORY.owner) + "/" +
      encodeURIComponent(GITHUB_HISTORY.repo) + "/contents/" +
      GITHUB_HISTORY.path.split("/").map(encodeURIComponent).join("/");
  }

  function githubHeaders() {
    return {
      Accept: "application/vnd.github+json",
      Authorization: "Bearer " + state.githubToken,
      "X-GitHub-Api-Version": "2022-11-28"
    };
  }

  function decodeBase64Json(content) {
    var clean = String(content || "").replace(/\s/g, "");
    var binary = atob(clean);
    var bytes = new Uint8Array(binary.length);
    for (var i = 0; i < binary.length; i += 1) {
      bytes[i] = binary.charCodeAt(i);
    }
    return JSON.parse(new TextDecoder("utf-8").decode(bytes));
  }

  function encodeBase64Json(data) {
    var json = JSON.stringify(data, null, 2);
    var bytes = new TextEncoder().encode(json);
    var chunk = "";
    var parts = [];
    bytes.forEach(function (byte, index) {
      chunk += String.fromCharCode(byte);
      if (chunk.length >= 8192 || index === bytes.length - 1) {
        parts.push(chunk);
        chunk = "";
      }
    });
    return btoa(parts.join(""));
  }

  function normalizeHistoryStore(store) {
    var next = store && typeof store === "object" ? store : {};
    if (!next.version) {
      next.version = 1;
    }
    if (!next.profiles || typeof next.profiles !== "object") {
      next.profiles = {};
    }
    return next;
  }

  function readGithubHistoryStore() {
    var url = githubHistoryApiUrl() + "?ref=" + encodeURIComponent(GITHUB_HISTORY.branch || "main");
    return fetch(url, {
      cache: "no-store",
      headers: githubHeaders()
    }).then(function (response) {
      if (response.status === 404) {
        return { sha: null, store: normalizeHistoryStore(null) };
      }
      if (!response.ok) {
        throw new Error("GitHub HTTP " + response.status);
      }
      return response.json();
    }).then(function (data) {
      if (data.store) {
        return data;
      }
      return {
        sha: data.sha,
        store: normalizeHistoryStore(decodeBase64Json(data.content))
      };
    });
  }

  function loadGithubHistory() {
    if (!state.githubToken) {
      els.historyStatus.textContent = "GitHub 私有历史仓库已配置，保存 Token 后可跨设备同步";
      renderHistory();
      return Promise.resolve();
    }
    els.historyStatus.textContent = "正在从 GitHub 私有仓库同步...";
    return readGithubHistoryStore().then(function (result) {
      state.histories = Array.isArray(result.store.profiles[state.syncId]) ?
        result.store.profiles[state.syncId] : [];
      cacheHistories();
      els.historyStatus.textContent = "已从 GitHub 同步 " + state.histories.length + " 条历史";
    }).catch(function () {
      els.historyStatus.textContent = "GitHub 同步失败，已使用本机缓存";
    }).then(renderHistory);
  }

  function saveGithubHistory(histories, retries) {
    return readGithubHistoryStore().then(function (result) {
      var store = normalizeHistoryStore(result.store);
      store.profiles[state.syncId] = histories.slice(-50);
      store.updatedAt = new Date().toISOString();
      var body = {
        message: "Update car filter history",
        content: encodeBase64Json(store),
        branch: GITHUB_HISTORY.branch || "main"
      };
      if (result.sha) {
        body.sha = result.sha;
      }
      return fetch(githubHistoryApiUrl(), {
        method: "PUT",
        headers: Object.assign({ "Content-Type": "application/json" }, githubHeaders()),
        body: JSON.stringify(body)
      }).then(function (response) {
        if (response.status === 409 && retries > 0) {
          return saveGithubHistory(histories, retries - 1);
        }
        if (!response.ok) {
          throw new Error("GitHub HTTP " + response.status);
        }
      });
    });
  }

  function loadWorkerHistory() {
    if (!state.syncId) {
      return Promise.resolve();
    }
    els.historyStatus.textContent = "正在同步历史...";
    return fetchJson(HISTORY_API + "?syncId=" + encodeURIComponent(state.syncId))
      .then(function (data) {
        state.histories = Array.isArray(data.histories) ? data.histories : [];
        cacheHistories();
        els.historyStatus.textContent = "已同步 " + state.histories.length + " 条历史";
      })
      .catch(function () {
        els.historyStatus.textContent = "服务端历史暂不可用，已使用本机缓存";
      })
      .then(renderHistory);
  }

  function loadRemoteHistory() {
    if (!state.syncId) {
      return Promise.resolve();
    }
    if (githubHistoryConfigured()) {
      return loadGithubHistory();
    }
    return loadWorkerHistory();
  }

  function saveRemoteHistory() {
    var rows = getFilteredRows();
    var snapshot = snapshotFilters();
    var activeNames = [];
    (state.config.conditions || []).forEach(function (condition) {
      if (state.featureFilters[condition.id] || state.rangeFilters[condition.id]) {
        activeNames.push(condition.label);
      }
    });
    var name = activeNames.length ? activeNames.join(" + ") : (state.search || state.brand || state.series || "自定义筛选");
    var item = {
      id: String(Date.now()),
      name: name,
      state: snapshot,
      resultCount: rows.length,
      createdAt: new Date().toISOString()
    };

    state.histories.push(item);
    state.histories = state.histories.slice(-50);
    cacheHistories();
    renderHistory();
    els.historyStatus.textContent = "正在保存...";

    if (githubHistoryConfigured()) {
      if (!state.githubToken) {
        els.historyStatus.textContent = "已保存在本机；保存 GitHub Token 后可跨设备同步";
        return Promise.resolve();
      }
      return saveGithubHistory(state.histories, 1).then(function () {
        els.historyStatus.textContent = "已保存到 GitHub 私有仓库";
      }).catch(function () {
        els.historyStatus.textContent = "GitHub 保存失败，已保存在本机";
      });
    }

    return fetch(HISTORY_API, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ syncId: state.syncId, history: item })
    }).then(function (response) {
      if (!response.ok) {
        throw new Error("HTTP " + response.status);
      }
      els.historyStatus.textContent = "已保存到服务端";
    }).catch(function () {
      els.historyStatus.textContent = "服务端保存失败，已保存在本机";
    });
  }

  function restoreDefaultFilters() {
    state.columnFilters = {};
    state.rangeFilters = cloneDefaultRangeFilters();
    state.featureFilters = cloneDefaultFeatureFilters();
    state.search = "";
    state.brand = "";
    state.series = "";
    state.sortField = "";
    state.sortDir = "asc";
    state.sortLevels = [];
    state.cardLimit = 24;
    state.page = 1;
    state.saleScope = "onSale";
    els.globalSearch.value = "";
    renderEverything();
  }

  function bindEvents() {

    els.centerMode.addEventListener("click", function () { state.mode = "center"; renderEverything(); });
    els.tableMode.addEventListener("click", function () {
      // 不清 expandedSeries：车系卡片的展开态属于筛选现场，切到数据表再切回来应当还在
      // （负责人 10-16："切换到 SKU 页也应保留这些筛选条件，也应保留筛选栏"）
      state.mode = "table";
      renderEverything();
    });
    bindPanelToggle(els.toggleFieldFilterPanel, els.fieldFilterBody);
    bindPanelToggle(els.toggleHistoryPanel, els.historyBody);
    if (els.saleScopeOnSale && els.saleScopeAll) {
      els.saleScopeOnSale.addEventListener("click", function () { state.saleScope = "onSale"; applySaleScopeButtons(); renderEverything(); });
      els.saleScopeAll.addEventListener("click", function () { state.saleScope = "all"; applySaleScopeButtons(); renderEverything(); });
    }
    if (els.centerBrandFilter && els.centerSeriesFilter) {
      els.centerBrandFilter.addEventListener("change", function (event) { state.brand = event.target.value; state.series = ""; state.page = 1; state.cardLimit = 24; renderEverything(); });
      els.centerSeriesFilter.addEventListener("change", function (event) { state.series = event.target.value; state.page = 1; state.cardLimit = 24; renderResultsOnly(); renderCenterFilters(); });
    }
    els.centerConditionList.addEventListener("click", function (event) {
      var button = event.target.closest(".major-category-button");
      if (button) { activateMobileCategory(button.dataset.categoryId, false); }
    });
    els.centerConditionList.addEventListener("keydown", function (event) {
      var button = event.target.closest(".major-category-button");
      if (!button || !(event.key === "Enter" || event.key === " ")) { return; }
      event.preventDefault();
      activateMobileCategory(button.dataset.categoryId, true);
    });
    els.centerConditionList.addEventListener("change", function (event) {
      if (event.target.type !== "checkbox") { return; }
      var condition = (state.config.conditions || []).find(function (item) { return item.id === event.target.dataset.conditionId; });
      if (!condition) { return; }
      if (condition.type === "range") {
        if (event.target.checked) { state.rangeFilters[condition.id] = { min: "", max: "" }; }
        else { delete state.rangeFilters[condition.id]; }
      } else {
        state.featureFilters[condition.id] = event.target.checked;
        if (!event.target.checked) { delete state.featureFilters[condition.id]; }
      }
      state.page = 1; state.cardLimit = 24; renderConditions(); renderMobileCategoryBadges(); renderResultsOnly();
    });
    els.centerConditionList.addEventListener("input", function (event) {
      if (!event.target.dataset.side) { return; }
      var id = event.target.dataset.conditionId;
      if (!state.rangeFilters[id]) { state.rangeFilters[id] = { min: "", max: "" }; }
      state.rangeFilters[id][event.target.dataset.side] = event.target.value;
      state.page = 1; state.cardLimit = 24; renderMobileCategoryBadges(); renderResultsOnly();
    });
    els.cardList.addEventListener("click", function (event) {
      var toggle = event.target.closest(".series-card-toggle");
      if (!toggle) { return; }
      var key = toggle.dataset.seriesKey;
      if (state.expandedSeries.has(key)) {
        state.expandedSeries.delete(key);
      } else {
        state.expandedSeries.add(key);
      }
      renderResultsOnly();
    });
    els.loadMoreCards.addEventListener("click", function () { state.cardLimit += 24; renderResultsOnly(); });
    if (els.cardSortSelect) {
      els.cardSortSelect.addEventListener("change", function () {
        var raw = els.cardSortSelect.value;
        if (!raw || raw === "default") {
          state.cardSort = null;
        } else {
          var separator = raw.lastIndexOf(":");
          state.cardSort = { field: raw.slice(0, separator), dir: raw.slice(separator + 1) === "desc" ? "desc" : "asc" };
        }
        renderResultsOnly();
      });
    }
    els.addSortLevel.addEventListener("click", function () { state.sortLevels.push({ field: state.columns[0] || "", dir: "asc", customOrder: "" }); state.sortField = ""; renderCustomSortPanel(); renderResultsOnly(); });
    els.clearSortLevels.addEventListener("click", function () { state.sortLevels = []; state.sortField = ""; state.sortDir = "asc"; renderCustomSortPanel(); renderTableHead(); renderResultsOnly(); });
    els.customSortLevels.addEventListener("change", function (event) {
      var row = event.target.closest(".sort-level"); if (!row) { return; }
      var level = state.sortLevels[Number(row.dataset.index)]; if (!level) { return; }
      level[event.target.dataset.role] = event.target.value; state.sortField = ""; renderResultsOnly();
    });
    els.customSortLevels.addEventListener("input", function (event) {
      if (event.target.dataset.role !== "customOrder") { return; }
      var row = event.target.closest(".sort-level"); var level = state.sortLevels[Number(row.dataset.index)]; if (!level) { return; }
      level.customOrder = event.target.value; state.sortField = ""; renderResultsOnly();
    });
    els.customSortLevels.addEventListener("click", function (event) {
      var role = event.target.dataset.role; if (["remove", "up", "down"].indexOf(role) === -1) { return; }
      var row = event.target.closest(".sort-level"); var index = Number(row.dataset.index);
      if (role === "remove") { state.sortLevels.splice(index, 1); }
      if (role === "up" && index > 0) { var prev = state.sortLevels[index - 1]; state.sortLevels[index - 1] = state.sortLevels[index]; state.sortLevels[index] = prev; }
      if (role === "down" && index < state.sortLevels.length - 1) { var next = state.sortLevels[index + 1]; state.sortLevels[index + 1] = state.sortLevels[index]; state.sortLevels[index] = next; }
      renderCustomSortPanel(); renderResultsOnly();
    });

    els.globalSearch.addEventListener("compositionstart", function () { state.composing = true; });
    els.globalSearch.addEventListener("compositionend", function (event) {
      state.composing = false;
      state.search = event.target.value;
      state.page = 1;
      renderResultsOnly();
    });
    els.globalSearch.addEventListener("input", function (event) {
      if (state.composing) {
        return;
      }
      state.search = event.target.value;
      state.page = 1;
      renderResultsOnly();
    });

    if (els.brandFilter && els.seriesFilter) {
      els.brandFilter.addEventListener("change", function (event) {
        state.brand = event.target.value;
        state.series = "";
        state.page = 1;
        renderEverything();
      });

      els.seriesFilter.addEventListener("change", function (event) {
        state.series = event.target.value;
        state.page = 1;
        renderResultsOnly();
      });
    }

    function applyPageSize() {
      var requested = Number(els.pageSize.value);
      state.pageSizeDraft = null;
      if (!Number.isSafeInteger(requested) || requested < 1) { els.pageSize.value = String(state.pageSize); return; }
      state.pageSize = requested;
      state.page = 1;
      renderResultsOnly();
    }
    els.pageSize.addEventListener("input", function (event) {
      var draft = String(event.target.value == null ? "" : event.target.value);
      state.pageSizeDraft = draft === String(state.pageSize) ? null : draft;
    });
    els.pageSize.addEventListener("change", applyPageSize);
    els.pageSize.addEventListener("keydown", function (event) {
      if (event.key === "Enter") { event.preventDefault(); applyPageSize(); }
    });
    if (els.applyPageSize) { els.applyPageSize.addEventListener("click", applyPageSize); }

    if (els.tableDisplayMode) {
      els.tableDisplayMode.addEventListener("change", function (event) {
        state.tableDisplayMode = event.target.value === "all" ? "all" : "paged";
        state.page = 1;
        renderResultsOnly();
      });
    }

    els.tableHead.addEventListener("click", function (event) {
      var button = event.target.closest(".sort-button");
      if (!button) {
        return;
      }
      var column = button.dataset.column;
      state.sortLevels = [];
      if (state.sortField === column) {
        state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
      } else {
        state.sortField = column;
        state.sortDir = "asc";
      }
      renderTableHead();
      renderResultsOnly();
    });

    els.tableHead.addEventListener("compositionstart", function () { state.composing = true; });
    els.tableHead.addEventListener("compositionend", function (event) {
      if (!event.target.classList.contains("filter-input")) {
        return;
      }
      state.composing = false;
      state.columnFilters[event.target.dataset.column] = { operator: "contains", value: event.target.value };
      state.page = 1;
      renderResultsOnly();
    });
    els.tableHead.addEventListener("input", function (event) {
      if (!event.target.classList.contains("filter-input") || state.composing) {
        return;
      }
      state.columnFilters[event.target.dataset.column] = { operator: "contains", value: event.target.value };
      state.page = 1;
      renderResultsOnly();
    });

    els.conditionList.addEventListener("change", function (event) {
      if (event.target.type !== "checkbox") {
        return;
      }
      state.featureFilters[event.target.dataset.conditionId] = event.target.checked;
      if (!event.target.checked) {
        delete state.featureFilters[event.target.dataset.conditionId];
      }
      state.page = 1;
      renderCenterFilters();
      renderSelectedTags();
      renderResultsOnly();
    });

    els.conditionList.addEventListener("click", function (event) {
      if (event.target.tagName !== "BUTTON") {
        return;
      }
      var id = event.target.dataset.conditionId;
      var inputs = els.conditionList.querySelectorAll('input[data-condition-id="' + id + '"][data-side]');
      var value = {};
      inputs.forEach(function (input) {
        value[input.dataset.side] = input.value;
      });
      state.rangeFilters[id] = value;
      state.page = 1;
      renderCenterFilters();
      renderSelectedTags();
      renderResultsOnly();
    });

    els.applyFieldFilter.addEventListener("click", function () {
      if (!els.fieldSelect.value || !els.fieldValue.value) {
        return;
      }
      state.columnFilters[els.fieldSelect.value] = {
        operator: els.fieldOperator.value,
        value: els.fieldValue.value
      };
      els.fieldValue.value = "";
      state.page = 1;
      renderTableHead();
      renderResultsOnly();
    });

    els.activeFilters.addEventListener("click", function (event) {
      if (event.target.tagName !== "BUTTON") {
        return;
      }
      delete state.columnFilters[event.target.dataset.column];
      state.page = 1;
      renderTableHead();
      renderResultsOnly();
    });

    els.columnList.addEventListener("change", function (event) {
      if (event.target.tagName !== "INPUT") {
        return;
      }
      if (event.target.checked) {
        state.visibleColumns.add(event.target.dataset.column);
      } else {
        state.visibleColumns.delete(event.target.dataset.column);
      }
      renderTableHead();
      renderResultsOnly();
    });

    els.columnSearch.addEventListener("input", function (event) {
      state.columnSearch = event.target.value;
      renderColumnList();
    });

    els.showCoreColumns.addEventListener("click", function () {
      state.visibleColumns = new Set();
      (state.config.defaultVisibleColumns || []).forEach(function (column) {
        if (state.columns.indexOf(column) !== -1) {
          state.visibleColumns.add(column);
        }
      });
      renderTableHead();
      renderColumnList();
      renderResultsOnly();
    });

    els.showAllColumns.addEventListener("click", function () {
      state.visibleColumns = new Set(state.columns);
      renderTableHead();
      renderColumnList();
      renderResultsOnly();
    });

    els.resetFilters.addEventListener("click", restoreDefaultFilters);
    if (els.mobileRestoreDefaults) {
      els.mobileRestoreDefaults.addEventListener("click", restoreDefaultFilters);
    }
    if (els.mobileViewResults) {
      els.mobileViewResults.addEventListener("click", function () {
        if (els.cardList && typeof els.cardList.scrollIntoView === "function") {
          els.cardList.scrollIntoView({ behavior: "smooth", block: "start" });
        }
        if (els.cardList && typeof els.cardList.focus === "function") {
          els.cardList.focus({ preventScroll: true });
        }
      });
    }

    els.prevPage.addEventListener("click", function () {
      state.page = Math.max(1, state.page - 1);
      renderResultsOnly();
    });

    els.nextPage.addEventListener("click", function () {
      state.page += 1;
      renderResultsOnly();
    });

    function jumpToPage() {
      var pageCount = state.tableDisplayMode === "all" ? 1 : Math.max(1, Math.ceil(getFilteredRows().length / state.pageSize));
      var rawValue = els.pageJump.value.trim();
      var requested = Number(rawValue);
      if (!rawValue || !Number.isInteger(requested)) {
        els.pageJump.value = String(state.page);
        return;
      }
      state.page = Math.min(pageCount, Math.max(1, requested));
      renderResultsOnly();
    }

    els.goPage.addEventListener("click", jumpToPage);
    els.pageJump.addEventListener("keydown", function (event) {
      if (event.key === "Enter") {
        event.preventDefault();
        jumpToPage();
      }
    });

    els.saveHistory.addEventListener("click", saveRemoteHistory);
    els.copySyncId.addEventListener("click", function () {
      navigator.clipboard.writeText(state.syncId).catch(function () {});
      els.historyStatus.textContent = "同步码已复制";
    });
    els.loadHistory.addEventListener("click", function () {
      state.syncId = els.historySyncId.value.trim();
      localStorage.setItem(STORAGE_SYNC_KEY, state.syncId);
      loadRemoteHistory();
    });
    els.saveGithubToken.addEventListener("click", function () {
      var token = els.githubToken.value.trim();
      if (!token) {
        els.historyStatus.textContent = "Token 留空，继续使用本机已有设置";
        return;
      }
      state.githubToken = token;
      localStorage.setItem(STORAGE_GITHUB_TOKEN_KEY, token);
      els.githubToken.value = "";
      els.githubToken.placeholder = "已保存，留空保持不变";
      loadRemoteHistory();
    });
    els.clearGithubToken.addEventListener("click", function () {
      state.githubToken = "";
      localStorage.removeItem(STORAGE_GITHUB_TOKEN_KEY);
      els.githubToken.value = "";
      els.githubToken.placeholder = "仅保存在本机";
      els.historyStatus.textContent = "GitHub Token 已清除，当前使用本机缓存";
    });
    els.historyList.addEventListener("click", function (event) {
      var button = event.target.closest("button[data-history-id]");
      if (!button) {
        return;
      }
      var item = state.histories.find(function (history) { return history.id === button.dataset.historyId; });
      if (item) {
        applySnapshot(item.state || {});
      }
    });

    els.exportCsv.addEventListener("click", exportCurrentCsv);
    els.exportJson.addEventListener("click", exportCurrentJson);
  }

  function initializeRows(rows) {
    var displayRows = mergeVerifiedRows(Array.isArray(rows) ? rows : []).filter(function (row) {
      return keepDisplayYear(row);
    });
    state.rows = withDerivedDimensions(displayRows);
    state.rows = normalizeRowColumns(state.rows);
    state.rows = normalizeDisplayValues(state.rows);
    state.expandedSeries.clear();
    state.seriesViewSignature = "";
    state.cardLimit = 24;
    state.rangeFilters = cloneDefaultRangeFilters();
    state.featureFilters = cloneDefaultFeatureFilters();
    columnPaths.clear();
    state.columns = orderedColumns(buildColumns(state.rows));
    state.visibleColumns = new Set();
    (state.config.defaultVisibleColumns || []).forEach(function (column) {
      if (state.columns.indexOf(column) !== -1) {
        state.visibleColumns.add(column);
      }
    });
    if (!state.visibleColumns.size) {
      state.visibleColumns = new Set(state.columns.slice(0, Math.min(18, state.columns.length)));
    }
    if (els.saleScopeSection) { els.saleScopeSection.hidden = false; }
    applySaleScopeButtons();
  }

  function formatDataTimestamp(iso) {
    if (!iso) { return ""; }
    var d = new Date(iso);
    if (isNaN(d.getTime())) { return ""; }
    function pad(n) { return (n < 10 ? "0" : "") + n; }
    return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()) +
      " " + pad(d.getHours()) + ":" + pad(d.getMinutes());
  }

  function loadData() {
    return Promise.all([
      fetchJson("filter_conditions.json").catch(function () { return fallbackConfig; }),
      fetchJson("data/manifest.json").catch(function () { return null; })
    ]).then(function (results) {
      state.config = Object.assign({}, fallbackConfig, results[0] || {});
      state.manifest = results[1];
      if (!state.manifest) {
        initializeRows(SAMPLE_ROWS);
        els.dataMeta.textContent = "本地预览示例 · GitHub Pages 部署后自动加载最新 Release 数据";
        return;
      }
      els.dataMeta.textContent = "正在加载并校验完整车型数据…";
      return loadPublishedRows(state.manifest).then(function (latest) {
        state.publishedRawRows = latest;
        initializeRows(latest);
        var updatedText = formatDataTimestamp(state.manifest.updatedAt);
        var dateText = updatedText ? "数据生成时间 " + updatedText
          : (state.manifest.date ? "数据日期 " + state.manifest.date : "最新数据");
        els.dataMeta.textContent = dateText + " · 综合核验 " + state.rows.length + " 款车型";
      });
    });
  }

  function initSync() {
    state.syncId = localStorage.getItem(STORAGE_SYNC_KEY) || DEFAULT_SYNC_ID || generateSyncId();
    localStorage.setItem(STORAGE_SYNC_KEY, state.syncId);
    state.githubToken = localStorage.getItem(STORAGE_GITHUB_TOKEN_KEY) || "";
    if (state.githubToken) {
      els.githubToken.placeholder = "已保存，留空保持不变";
    }
    loadCachedHistories();
    renderHistory();
    return loadRemoteHistory();
  }

  bindEvents();
  if (typeof window.addEventListener === "function") { window.addEventListener("resize", syncTableHeaderOffsets); }
  if (typeof window.ResizeObserver === "function") {
    var tableHeaderObserver = new window.ResizeObserver(syncTableHeaderOffsets);
    tableHeaderObserver.observe(els.tableHead);
  }
  if (typeof window.matchMedia === "function") {
    var mobileFilterMedia = window.matchMedia("(max-width: 720px)");
    if (typeof mobileFilterMedia.addEventListener === "function") {
      mobileFilterMedia.addEventListener("change", renderCenterFilters);
    }
  }
  loadData().then(function () {
    renderEverything();
    initSync();
  }).catch(function (error) {
    els.dataMeta.textContent = "数据加载失败，未展示不完整数据：" + error.message;
  });
}());

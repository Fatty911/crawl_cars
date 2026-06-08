(function () {
  "use strict";

  var CORE_COLUMNS = [
    "车型名称",
    "品牌",
    "车系",
    "年款",
    "数据来源",
    "长度(mm)",
    "宽度(mm)",
    "高度(mm)",
    "零整比",
    "零整比来源明细",
    "百公里加速(s)",
    "纯电续航(km)",
    "NOA城市领航",
    "远程启动",
    "远程控制",
    "蓝牙/数字钥匙",
    "座椅记忆",
    "外后视镜记忆",
  ];

  var SAMPLE_ROWS = [
    {
      "数据来源": "示例",
      "品牌": "示例品牌",
      "车系": "示例车系",
      "车型名称": "等待 GitHub Pages 发布最新数据",
      "年款": "2026",
      "长*宽*高(mm)": "4890*1920*1685",
      "零整比": "336.97%",
      "零整比来源明细": "中国保险行业协会/中国汽车维修行业协会(2019-04) 示例车系: 336.97%",
      "百公里加速(s)": "6.8",
      "纯电续航(km)": "200",
      "NOA城市领航": "支持",
      "远程启动": "支持",
      "远程控制": "车门控制|空调控制",
      "蓝牙/数字钥匙": "蓝牙钥匙",
      "座椅记忆": "驾驶位",
      "外后视镜记忆": "支持",
    },
  ];

  var state = {
    manifest: null,
    dataset: "filtered",
    latestRows: [],
    filteredRows: [],
    rows: [],
    columns: [],
    visibleColumns: new Set(),
    columnFilters: {},
    search: "",
    source: "",
    brand: "",
    series: "",
    sortField: "",
    sortDir: "asc",
    page: 1,
    pageSize: 100,
    columnSearch: "",
  };

  var els = {
    dataMeta: document.getElementById("dataMeta"),
    showAll: document.getElementById("showAll"),
    showFiltered: document.getElementById("showFiltered"),
    globalSearch: document.getElementById("globalSearch"),
    resetFilters: document.getElementById("resetFilters"),
    exportCsv: document.getElementById("exportCsv"),
    exportJson: document.getElementById("exportJson"),
    visibleCount: document.getElementById("visibleCount"),
    totalCount: document.getElementById("totalCount"),
    columnCount: document.getElementById("columnCount"),
    sourceCount: document.getElementById("sourceCount"),
    sourceFilter: document.getElementById("sourceFilter"),
    brandFilter: document.getElementById("brandFilter"),
    seriesFilter: document.getElementById("seriesFilter"),
    pageSize: document.getElementById("pageSize"),
    tableHead: document.getElementById("tableHead"),
    tableBody: document.getElementById("tableBody"),
    emptyState: document.getElementById("emptyState"),
    prevPage: document.getElementById("prevPage"),
    nextPage: document.getElementById("nextPage"),
    pageInfo: document.getElementById("pageInfo"),
    fieldSelect: document.getElementById("fieldSelect"),
    fieldValue: document.getElementById("fieldValue"),
    applyFieldFilter: document.getElementById("applyFieldFilter"),
    activeFilters: document.getElementById("activeFilters"),
    showCoreColumns: document.getElementById("showCoreColumns"),
    showAllColumns: document.getElementById("showAllColumns"),
    columnSearch: document.getElementById("columnSearch"),
    columnList: document.getElementById("columnList"),
    downloadList: document.getElementById("downloadList"),
  };

  function fetchJson(url) {
    return fetch(url, { cache: "no-store" }).then(function (response) {
      if (!response.ok) {
        throw new Error("HTTP " + response.status + " " + url);
      }
      return response.json();
    });
  }

  function uniqueValues(rows, field) {
    var values = Array.from(
      new Set(
        rows
          .map(function (row) {
            return String(row[field] || "").trim();
          })
          .filter(Boolean)
      )
    );
    return values.sort(function (a, b) {
      return a.localeCompare(b, "zh-Hans", { numeric: true });
    });
  }

  function isDimensionColumn(column) {
    var text = String(column || "").replace(/\s/g, "");
    return (
      text.indexOf("长宽高") !== -1 ||
      text.indexOf("长*宽*高") !== -1 ||
      text.indexOf("长×宽×高") !== -1 ||
      text.indexOf("长x宽x高") !== -1 ||
      text.indexOf("车身尺寸") !== -1 ||
      (text.indexOf("长度") !== -1 && text.indexOf("宽度") !== -1 && text.indexOf("高度") !== -1)
    );
  }

  function parseDimensionValue(value) {
    var text = String(value == null ? "" : value).trim();
    if (!text || text === "-") {
      return null;
    }
    var numbers = text.match(/\d+(?:\.\d+)?/g);
    if (!numbers || numbers.length < 3) {
      return null;
    }
    return numbers.slice(0, 3);
  }

  function withDerivedDimensions(rows) {
    return rows.map(function (row) {
      var next = Object.assign({}, row);
      var dimensionColumn = Object.keys(row).find(isDimensionColumn);
      var dimensions = dimensionColumn ? parseDimensionValue(row[dimensionColumn]) : null;

      if (dimensions) {
        if (!next["长度(mm)"]) {
          next["长度(mm)"] = dimensions[0];
        }
        if (!next["宽度(mm)"]) {
          next["宽度(mm)"] = dimensions[1];
        }
        if (!next["高度(mm)"]) {
          next["高度(mm)"] = dimensions[2];
        }
      }

      return next;
    });
  }

  function buildColumns(rows) {
    var seen = new Set();
    var columns = [];

    CORE_COLUMNS.forEach(function (column) {
      if (rows.some(function (row) { return Object.prototype.hasOwnProperty.call(row, column); })) {
        seen.add(column);
        columns.push(column);
      }
    });

    rows.forEach(function (row) {
      Object.keys(row).forEach(function (column) {
        if (isDimensionColumn(column)) {
          return;
        }
        if (!seen.has(column)) {
          seen.add(column);
          columns.push(column);
        }
      });
    });

    return columns;
  }

  function setDataset(dataset) {
    state.dataset = dataset;
    state.rows = dataset === "filtered" ? state.filteredRows : state.latestRows;
    state.columns = buildColumns(state.rows);
    state.visibleColumns = new Set(state.columns.slice(0, Math.min(18, state.columns.length)));
    CORE_COLUMNS.forEach(function (column) {
      if (state.columns.indexOf(column) !== -1) {
        state.visibleColumns.add(column);
      }
    });
    state.columnFilters = {};
    state.page = 1;
    state.showAllClass = dataset === "latest";
    renderEverything();
  }

  function normalizeText(value) {
    return String(value == null ? "" : value).toLowerCase();
  }

  function firstNumber(value) {
    var match = String(value == null ? "" : value).match(/\d+(?:\.\d+)?/);
    return match ? Number(match[0]) : null;
  }

  function getFilteredRows() {
    var rows = state.rows.slice();
    var search = normalizeText(state.search);

    if (state.source) {
      rows = rows.filter(function (row) { return row["数据来源"] === state.source; });
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

    Object.keys(state.columnFilters).forEach(function (column) {
      var value = normalizeText(state.columnFilters[column]);
      if (!value) {
        return;
      }
      rows = rows.filter(function (row) {
        return normalizeText(row[column]).indexOf(value) !== -1;
      });
    });

    if (state.sortField) {
      rows.sort(function (a, b) {
        var av = a[state.sortField];
        var bv = b[state.sortField];
        var an = firstNumber(av);
        var bn = firstNumber(bv);
        var result;

        if (an !== null && bn !== null) {
          result = an - bn;
        } else {
          result = String(av || "").localeCompare(String(bv || ""), "zh-Hans", { numeric: true });
        }

        return state.sortDir === "asc" ? result : -result;
      });
    }

    return rows;
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

  function renderFilters() {
    renderOptions(els.sourceFilter, uniqueValues(state.rows, "数据来源"), "来源");
    renderOptions(els.brandFilter, uniqueValues(state.rows, "品牌"), "品牌");
    renderOptions(els.seriesFilter, uniqueValues(state.rows, "车系"), "车系");

    els.sourceFilter.value = state.source;
    els.brandFilter.value = state.brand;
    els.seriesFilter.value = state.series;

    els.fieldSelect.textContent = "";
    state.columns.forEach(function (column) {
      var option = document.createElement("option");
      option.value = column;
      option.textContent = column;
      els.fieldSelect.appendChild(option);
    });
  }

  function sortMark(column) {
    if (state.sortField !== column) {
      return "";
    }
    return state.sortDir === "asc" ? "↑" : "↓";
  }

  function renderTable(rows) {
    var visibleColumns = state.columns.filter(function (column) {
      return state.visibleColumns.has(column);
    });
    var start = (state.page - 1) * state.pageSize;
    var pageRows = rows.slice(start, start + state.pageSize);

    els.tableHead.textContent = "";
    els.tableBody.textContent = "";

    var titleRow = document.createElement("tr");
    visibleColumns.forEach(function (column) {
      var th = document.createElement("th");
      var button = document.createElement("button");
      button.type = "button";
      button.className = "sort-button";
      button.dataset.column = column;
      button.title = "按 " + column + " 排序";

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
      input.value = state.columnFilters[column] || "";
      input.placeholder = "筛选";
      th.appendChild(input);
      filterRow.appendChild(th);
    });

    els.tableHead.appendChild(titleRow);
    els.tableHead.appendChild(filterRow);

    pageRows.forEach(function (row) {
      var tr = document.createElement("tr");
      visibleColumns.forEach(function (column) {
        var td = document.createElement("td");
        td.textContent = row[column] == null || row[column] === "" ? "-" : row[column];
        tr.appendChild(td);
      });
      els.tableBody.appendChild(tr);
    });

    els.emptyState.hidden = rows.length !== 0;
  }

  function renderColumnList() {
    var query = normalizeText(state.columnSearch);
    var fragment = document.createDocumentFragment();
    els.columnList.textContent = "";

    state.columns
      .filter(function (column) {
        return !query || normalizeText(column).indexOf(query) !== -1;
      })
      .forEach(function (column) {
        var label = document.createElement("label");
        var checkbox = document.createElement("input");
        var text = document.createElement("span");
        checkbox.type = "checkbox";
        checkbox.checked = state.visibleColumns.has(column);
        checkbox.dataset.column = column;
        text.textContent = column;
        label.appendChild(checkbox);
        label.appendChild(text);
        fragment.appendChild(label);
      });

    els.columnList.appendChild(fragment);
  }

  function renderActiveFilters() {
    els.activeFilters.textContent = "";
    Object.keys(state.columnFilters).forEach(function (column) {
      if (!state.columnFilters[column]) {
        return;
      }
      var chip = document.createElement("span");
      chip.className = "filter-chip";
      chip.textContent = column + ": " + state.columnFilters[column];
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
    var links = [
      ["完整 JSON", files.latestJson],
      ["完整 CSV", files.latestCsv],
      ["筛选 JSON", files.filteredJson],
      ["筛选 CSV", files.filteredCsv],
      ["零整比来源", files.zeroRatioJson],
    ];

    els.downloadList.textContent = "";
    links.forEach(function (item) {
      if (!item[1]) {
        return;
      }
      var anchor = document.createElement("a");
      anchor.href = item[1];
      anchor.textContent = item[0];
      anchor.download = "";
      els.downloadList.appendChild(anchor);
    });

    if (!els.downloadList.children.length) {
      els.downloadList.textContent = "发布后会显示 Release 同款下载文件。";
    }
  }

  function renderEverything() {
    var filtered = getFilteredRows();
    var pageCount = Math.max(1, Math.ceil(filtered.length / state.pageSize));
    if (state.page > pageCount) {
      state.page = pageCount;
    }

    els.showAll.classList.toggle("active", state.dataset === "latest");
    els.showFiltered.classList.toggle("active", state.dataset === "filtered");
    els.visibleCount.textContent = String(filtered.length);
    els.totalCount.textContent = String(state.rows.length);
    els.columnCount.textContent = String(state.visibleColumns.size);
    els.sourceCount.textContent = String(uniqueValues(state.rows, "数据来源").length);
    els.pageInfo.textContent = "第 " + state.page + " / " + pageCount + " 页";
    els.prevPage.disabled = state.page <= 1;
    els.nextPage.disabled = state.page >= pageCount;

    renderFilters();
    renderTable(filtered);
    renderColumnList();
    renderActiveFilters();
    renderDownloads();
  }

  function csvEscape(value) {
    var text = String(value == null ? "" : value);
    if (/[",\n\r]/.test(text)) {
      return '"' + text.replace(/"/g, '""') + '"';
    }
    return text;
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
    downloadBlob(
      "car-config-current.json",
      "application/json;charset=utf-8",
      JSON.stringify(getFilteredRows(), null, 2)
    );
  }

  function bindEvents() {
    els.showAll.addEventListener("click", function () { setDataset("latest"); });
    els.showFiltered.addEventListener("click", function () { setDataset("filtered"); });

    els.globalSearch.addEventListener("input", function (event) {
      state.search = event.target.value;
      state.page = 1;
      renderEverything();
    });

    els.sourceFilter.addEventListener("change", function (event) {
      state.source = event.target.value;
      state.page = 1;
      renderEverything();
    });

    els.brandFilter.addEventListener("change", function (event) {
      state.brand = event.target.value;
      state.page = 1;
      renderEverything();
    });

    els.seriesFilter.addEventListener("change", function (event) {
      state.series = event.target.value;
      state.page = 1;
      renderEverything();
    });

    els.pageSize.addEventListener("change", function (event) {
      state.pageSize = Number(event.target.value);
      state.page = 1;
      renderEverything();
    });

    els.tableHead.addEventListener("click", function (event) {
      var button = event.target.closest(".sort-button");
      if (!button) {
        return;
      }
      var column = button.dataset.column;
      if (state.sortField === column) {
        state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
      } else {
        state.sortField = column;
        state.sortDir = "asc";
      }
      renderEverything();
    });

    els.tableHead.addEventListener("input", function (event) {
      if (!event.target.classList.contains("filter-input")) {
        return;
      }
      state.columnFilters[event.target.dataset.column] = event.target.value;
      state.page = 1;
      renderEverything();
    });

    els.applyFieldFilter.addEventListener("click", function () {
      if (!els.fieldSelect.value) {
        return;
      }
      state.columnFilters[els.fieldSelect.value] = els.fieldValue.value;
      els.fieldValue.value = "";
      state.page = 1;
      renderEverything();
    });

    els.activeFilters.addEventListener("click", function (event) {
      if (event.target.tagName !== "BUTTON") {
        return;
      }
      delete state.columnFilters[event.target.dataset.column];
      state.page = 1;
      renderEverything();
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
      renderEverything();
    });

    els.columnSearch.addEventListener("input", function (event) {
      state.columnSearch = event.target.value;
      renderColumnList();
    });

    els.showCoreColumns.addEventListener("click", function () {
      state.visibleColumns = new Set();
      CORE_COLUMNS.forEach(function (column) {
        if (state.columns.indexOf(column) !== -1) {
          state.visibleColumns.add(column);
        }
      });
      renderEverything();
    });

    els.showAllColumns.addEventListener("click", function () {
      state.visibleColumns = new Set(state.columns);
      renderEverything();
    });

    els.resetFilters.addEventListener("click", function () {
      state.columnFilters = {};
      state.search = "";
      state.source = "";
      state.brand = "";
      state.series = "";
      state.sortField = "";
      state.sortDir = "asc";
      state.page = 1;
      els.globalSearch.value = "";
      renderEverything();
    });

    els.prevPage.addEventListener("click", function () {
      state.page = Math.max(1, state.page - 1);
      renderEverything();
    });

    els.nextPage.addEventListener("click", function () {
      state.page += 1;
      renderEverything();
    });

    els.exportCsv.addEventListener("click", exportCurrentCsv);
    els.exportJson.addEventListener("click", exportCurrentJson);
  }

  function loadData() {
    return fetchJson("data/manifest.json")
      .then(function (manifest) {
        state.manifest = manifest;
        return Promise.all([
          fetchJson(manifest.files.latestJson || "data/latest.json"),
          fetchJson(manifest.files.filteredJson || "data/filtered.json").catch(function () { return []; }),
        ]);
      })
      .then(function (datasets) {
        state.latestRows = withDerivedDimensions(Array.isArray(datasets[0]) ? datasets[0] : []);
        state.filteredRows = withDerivedDimensions(Array.isArray(datasets[1]) ? datasets[1] : []);
        var dateText = state.manifest && state.manifest.date ? "数据日期 " + state.manifest.date : "最新数据";
        els.dataMeta.textContent = dateText + " · 完整 " + state.latestRows.length + " 行 · 筛选 " + state.filteredRows.length + " 行";
      })
      .catch(function () {
        state.manifest = null;
        state.latestRows = withDerivedDimensions(SAMPLE_ROWS);
        state.filteredRows = withDerivedDimensions(SAMPLE_ROWS);
        els.dataMeta.textContent = "本地预览示例 · GitHub Pages 部署后自动加载最新 Release 数据";
      });
  }

  bindEvents();
  loadData().then(function () {
    setDataset("filtered");
  });
}());

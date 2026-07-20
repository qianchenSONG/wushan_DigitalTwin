/* =========================================================================
   巫山县城迁建区管网复合风险联动分析
   长江设计集团 | 除险降危实施方案数字化辅助展示
   —— 前端交互逻辑（数据驱动：所有业务数据来自 /data/*.geojson|json）
   ⚠ 页面内所有管网、缺陷、风险数值均为汇报演示样例数据，非实测数据。
   ========================================================================= */

const CFG = {
  center: [31.073, 109.878],
  zoom: 14.4,
  tileUrl: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
  tileAttr: '&copy; OpenStreetMap &copy; CARTO — 底图仅用于空间参考示意',
  colors: {
    stormwater: "#35d6f0",
    sewage: "#b06bd8",
    combined: "#ff9a3d",
    culvert: "#3ad0c2",
    region: "#3a7bd5",
    regionActive: "#e0b467",
    slope: "#ff9a3d",
    building: "#ff4b4f",
    fireaccess: "#ff2d3d",
    waterlog: "#35a7f0",
    outlet: "#e0b467",
  },
  severityColor: {
    "低风险": "#4fd08a",
    "中风险": "#ffd25c",
    "高风险": "#ff9a3d",
    "重大风险": "#ff4b4f",
  },
  severityRadius: {
    "低风险": 5,
    "中风险": 6.5,
    "高风险": 8,
    "重大风险": 10,
  },
};

const STATE = {
  data: {},
  map: null,
  layers: {},           // leaflet layer groups by key
  regionLayerById: {},  // id -> leaflet polygon layer
  selected: { type: null, id: null },
  charts: {},           // echarts instances
  demo: { active: false, step: 0 },
  tileOk: false,
};

/* -------------------------------------------------------------------- */
/*  数据加载                                                              */
/* -------------------------------------------------------------------- */
async function loadAllData() {
  const files = {
    regions: "data/regions.geojson",
    pipes: "data/pipes.geojson",
    outlets: "data/outlets.geojson",
    defects: "data/defects.geojson",
    slopes: "data/slopes.geojson",
    buildings: "data/buildings.geojson",
    fireaccess: "data/fireaccess.geojson",
    waterlogging: "data/waterlogging.geojson",
    relations: "data/relations.json",
    overview: "data/overview.json",
  };
  const entries = Object.entries(files);
  const results = await Promise.all(
    entries.map(([k, url]) =>
      fetch(url).then((r) => {
        if (!r.ok) throw new Error("加载失败: " + url);
        return r.json();
      })
    )
  );
  entries.forEach(([k], i) => (STATE.data[k] = results[i]));
}

/* -------------------------------------------------------------------- */
/*  地图初始化                                                            */
/* -------------------------------------------------------------------- */
function initMap() {
  const map = L.map("map", {
    zoomControl: true,
    attributionControl: true,
    minZoom: 12,
    maxZoom: 18,
  }).setView(CFG.center, CFG.zoom);

  const tiles = L.tileLayer(CFG.tileUrl, {
    subdomains: "abcd",
    attribution: CFG.tileAttr,
    maxZoom: 19,
  });

  let loadedOnce = false;
  tiles.on("load", () => {
    if (!loadedOnce) {
      loadedOnce = true;
      STATE.tileOk = true;
      setTileStatus(true);
    }
  });
  tiles.on("tileerror", () => {
    if (!STATE.tileOk) setTileStatus(false);
  });
  tiles.addTo(map);

  // 若 6 秒后仍未成功加载任何瓦片，判定为离线，启用兜底底图
  setTimeout(() => {
    if (!STATE.tileOk) setTileStatus(false);
  }, 6000);

  STATE.map = map;

  map.on("click", (e) => {
    // 点击空白处：若非点在图层要素上，则重置
    // (Leaflet: 图层要素的 click 会 stopPropagation via L.DomEvent，因此这里安全)
  });
}

function setTileStatus(ok) {
  const badge = document.getElementById("tileStatus");
  const banner = document.getElementById("offlineBanner");
  const mapEl = document.getElementById("map");
  if (ok) {
    badge.textContent = "● 底图在线";
    badge.classList.remove("badge-ghost");
    banner.classList.add("hidden");
    mapEl.classList.remove("map-offline-fallback");
  } else {
    badge.textContent = "○ 底图离线（示意底图）";
    banner.classList.remove("hidden");
    mapEl.classList.add("map-offline-fallback");
  }
}

/* -------------------------------------------------------------------- */
/*  图层构建                                                              */
/* -------------------------------------------------------------------- */
function buildLayers() {
  const { regions, pipes, outlets, defects, slopes, buildings, fireaccess, waterlogging } = STATE.data;

  /* ---- 片区面 ---- */
  const regionLayer = L.geoJSON(regions, {
    style: (f) => regionBaseStyle(f),
    onEachFeature: (feature, layer) => {
      STATE.regionLayerById[feature.properties.id] = layer;
      layer.on("mouseover", () => {
        if (STATE.selected.type !== "region") layer.setStyle({ weight: 2, fillOpacity: 0.42 });
        showRegionTooltip(feature, layer);
      });
      layer.on("mouseout", () => {
        if (STATE.selected.id !== feature.properties.id) layer.setStyle(regionBaseStyle(feature));
      });
      layer.on("click", (e) => {
        L.DomEvent.stopPropagation(e);
        selectRegion(feature.properties.id);
      });
    },
  }).addTo(STATE.map);

  /* ---- 管线（雨水/污水/混错接/箱涵）---- */
  const pipeLayers = { stormwater: L.layerGroup(), sewage: L.layerGroup(), combined: L.layerGroup(), culvert: L.layerGroup() };
  pipes.features.forEach((f) => {
    const type = f.properties.type;
    const color = CFG.colors[type] || "#888";
    const dashed = type === "combined";
    const line = L.geoJSON(f, {
      style: {
        color,
        weight: type === "culvert" ? 5 : 3,
        opacity: type === "culvert" ? 0.55 : 0.85,
        dashArray: dashed ? "6,4" : type === "culvert" ? "1,6" : null,
        lineCap: "round",
      },
    });
    line.on("click", (e) => {
      L.DomEvent.stopPropagation(e);
      selectPipe(f.properties.id);
    });
    line.on("mouseover", () => line.setStyle({ weight: (type === "culvert" ? 5 : 3) + 2 }));
    line.on("mouseout", () => line.setStyle({ weight: type === "culvert" ? 5 : 3 }));
    line.bindTooltip(
      `<b>${f.properties.name}</b><br/>状态：${f.properties.status}<br/>风险等级：${f.properties.riskLevel}`,
      { className: "wushan-tooltip", sticky: true }
    );
    pipeLayers[type].addLayer(line);
  });
  Object.values(pipeLayers).forEach((l) => l.addTo(STATE.map));

  /* ---- 入河排口 ---- */
  const outletLayer = L.geoJSON(outlets, {
    pointToLayer: (f, latlng) =>
      L.circleMarker(latlng, {
        radius: 7,
        color: CFG.colors.outlet,
        weight: 2,
        fillColor: CFG.colors.outlet,
        fillOpacity: 0.5,
      }),
    onEachFeature: (f, layer) => {
      layer.bindTooltip(
        `<b>${f.properties.name}</b><br/>顶托风险：${f.properties.backflowRisk}`,
        { className: "wushan-tooltip" }
      );
    },
  }).addTo(STATE.map);

  /* ---- 管网缺陷点 ---- */
  const defectLayer = L.layerGroup();
  defects.features.forEach((f) => {
    const sev = f.properties.severity;
    const color = CFG.severityColor[sev];
    const r = CFG.severityRadius[sev];
    const marker = L.circleMarker([f.geometry.coordinates[1], f.geometry.coordinates[0]], {
      radius: r,
      color,
      weight: 1.4,
      fillColor: color,
      fillOpacity: 0.75,
      className: sev === "重大风险" ? "defect-critical-pulse" : "",
    });
    marker.bindTooltip(
      `<b>${f.properties.defectType}</b>（${sev}）<br/>${f.properties.regionName} · ${f.properties.id}<br/>建议：${f.properties.suggestedAction}`,
      { className: "wushan-tooltip" }
    );
    marker.on("click", (e) => {
      L.DomEvent.stopPropagation(e);
      selectDefect(f.properties.id);
    });
    defectLayer.addLayer(marker);
  });
  defectLayer.addTo(STATE.map);

  /* ---- 边坡/挡墙风险面 ---- */
  const slopeLayer = L.geoJSON(slopes, {
    style: { color: CFG.colors.slope, weight: 1.5, fillColor: CFG.colors.slope, fillOpacity: 0.22, dashArray: "3,3" },
    onEachFeature: (f, layer) =>
      layer.bindTooltip(`<b>${f.properties.name}</b><br/>类型：${f.properties.type}<br/>状态：${f.properties.status}`, {
        className: "wushan-tooltip",
      }),
  }).addTo(STATE.map);

  /* ---- 房屋风险点 ---- */
  const buildingLayer = L.layerGroup();
  buildings.features.forEach((f) => {
    const icon = L.divIcon({
      className: "",
      html: `<div class="mk mk-building">⌂</div>`,
      iconSize: [16, 16],
    });
    const m = L.marker([f.geometry.coordinates[1], f.geometry.coordinates[0]], { icon });
    m.bindTooltip(`<b>${f.properties.name}</b><br/>问题：${f.properties.issue}<br/>初判：${f.properties.grade}`, {
      className: "wushan-tooltip",
    });
    buildingLayer.addLayer(m);
  });
  buildingLayer.addTo(STATE.map);

  /* ---- 消防瓶颈点 ---- */
  const fireLayer = L.layerGroup();
  fireaccess.features.forEach((f) => {
    const icon = L.divIcon({ className: "", html: `<div class="mk mk-fire">▲</div>`, iconSize: [16, 16] });
    const m = L.marker([f.geometry.coordinates[1], f.geometry.coordinates[0]], { icon });
    m.bindTooltip(`<b>${f.properties.name}</b><br/>${f.properties.issue}`, { className: "wushan-tooltip" });
    fireLayer.addLayer(m);
  });
  fireLayer.addTo(STATE.map);

  /* ---- 内涝点 ---- */
  const waterlogLayer = L.layerGroup();
  waterlogging.features.forEach((f) => {
    const icon = L.divIcon({ className: "", html: `<div class="mk mk-water">💧</div>`, iconSize: [16, 16] });
    const m = L.marker([f.geometry.coordinates[1], f.geometry.coordinates[0]], { icon });
    m.bindTooltip(`<b>${f.properties.name}</b>`, { className: "wushan-tooltip" });
    waterlogLayer.addLayer(m);
  });
  waterlogLayer.addTo(STATE.map);

  STATE.layers = {
    region: regionLayer,
    stormwater: pipeLayers.stormwater,
    sewage: pipeLayers.sewage,
    combined: pipeLayers.combined,
    culvert: pipeLayers.culvert,
    outlet: outletLayer,
    defect: defectLayer,
    slope: slopeLayer,
    building: buildingLayer,
    fireaccess: fireLayer,
    waterlogging: waterlogLayer,
  };

  // 关系连线（虚线）图层，动态绘制
  STATE.relationLayer = L.layerGroup().addTo(STATE.map);
  // 影响缓冲区图层
  STATE.bufferLayer = L.layerGroup().addTo(STATE.map);
}

function regionBaseStyle(feature) {
  const risk = feature.properties.riskLevel;
  const c = CFG.severityColor[risk] || CFG.colors.region;
  return { color: c, weight: 1.6, fillColor: c, fillOpacity: 0.16 };
}

function showRegionTooltip(feature, layer) {
  const p = feature.properties;
  layer
    .bindTooltip(
      `<b>${p.name}</b><span class="badge" style="margin-left:6px">${p.riskLevel}</span>
       <div style="margin-top:4px">缺陷数量：${p.defectCount}　重大：${p.majorDefectCount}</div>
       <div>重点风险：${p.recommendation}</div>
       <div style="color:#e0b467">建议措施优先级：${p.priority}</div>`,
      { className: "wushan-tooltip", sticky: true }
    )
    .openTooltip();
}

/* -------------------------------------------------------------------- */
/*  图层开关 & 片区列表（左侧面板）                                        */
/* -------------------------------------------------------------------- */
const LAYER_DEFS = [
  { key: "region", label: "迁建片区边界", color: CFG.colors.region, checked: true },
  { key: "stormwater", label: "雨水管网", color: CFG.colors.stormwater, checked: true },
  { key: "sewage", label: "污水管网", color: CFG.colors.sewage, checked: true },
  { key: "combined", label: "混错接问题管段", color: CFG.colors.combined, checked: true },
  { key: "culvert", label: "排洪箱涵/渠道", color: CFG.colors.culvert, checked: true },
  { key: "outlet", label: "入河排口", color: CFG.colors.outlet, checked: true },
  { key: "defect", label: "管网缺陷点", color: "#ff4b4f", checked: true },
  { key: "slope", label: "边坡/挡墙受影响区", color: CFG.colors.slope, checked: true },
  { key: "building", label: "房屋风险点", color: CFG.colors.building, checked: true },
  { key: "fireaccess", label: "消防通道瓶颈点", color: CFG.colors.fireaccess, checked: true },
  { key: "waterlogging", label: "内涝易发点", color: CFG.colors.waterlog, checked: false },
];

function renderLayerControls() {
  const box = document.getElementById("layerList");
  box.innerHTML = "";
  LAYER_DEFS.forEach((def) => {
    const row = document.createElement("label");
    row.className = "layer-item";
    row.innerHTML = `
      <input type="checkbox" ${def.checked ? "checked" : ""} data-layer="${def.key}" />
      <span class="layer-swatch" style="background:${def.color}"></span>
      <span>${def.label}</span>`;
    box.appendChild(row);
    if (!def.checked) STATE.map.removeLayer(STATE.layers[def.key]);
  });
  box.addEventListener("change", (e) => {
    const key = e.target.getAttribute("data-layer");
    if (!key) return;
    if (e.target.checked) STATE.layers[key].addTo(STATE.map);
    else STATE.map.removeLayer(STATE.layers[key]);
  });
}

function renderRegionList() {
  const box = document.getElementById("regionList");
  box.innerHTML = "";
  STATE.data.regions.features.forEach((f) => {
    const p = f.properties;
    const row = document.createElement("div");
    row.className = "region-item";
    row.dataset.id = p.id;
    row.innerHTML = `<span>${p.name}</span><span class="region-risk-tag rt-${p.riskLevel}">${p.riskLevel}</span>`;
    row.addEventListener("click", () => selectRegion(p.id));
    box.appendChild(row);
  });
}

/* -------------------------------------------------------------------- */
/*  KPI 卡片                                                              */
/* -------------------------------------------------------------------- */
function renderKPI() {
  const o = STATE.data.overview;
  const cards = [
    { label: "迁建区总面积", value: o.regionArea, unit: "km²" },
    { label: "涉及迁建小区数量", value: o.regionCount, unit: "个" },
    { label: "市政管网总长度", value: o.totalPipeLength, unit: "km" },
    { label: "排洪箱涵/渠道长度", value: o.totalCulvertLength, unit: "km" },
    { label: "管网缺陷总数", value: o.totalDefects, unit: "处" },
    { label: "高风险缺陷点数量", value: o.majorDefects, unit: "处", cls: "red" },
    { label: "受影响边坡/挡墙数量", value: o.affectedSlopes, unit: "处" },
    { label: "建议优先治理片区", value: o.priorityRegions, unit: "个", cls: "gold" },
  ];
  const row = document.getElementById("kpiRow");
  row.innerHTML = cards
    .map(
      (c) => `
    <div class="kpi-card">
      <div class="kpi-label">${c.label}</div>
      <div class="kpi-value ${c.cls || ""}">${c.value}<small>${c.unit}</small></div>
    </div>`
    )
    .join("");
}

/* -------------------------------------------------------------------- */
/*  选中逻辑：片区 / 管线 / 缺陷                                           */
/* -------------------------------------------------------------------- */
function clearSelectionVisuals() {
  Object.values(STATE.regionLayerById).forEach((layer) => {
    layer.setStyle(regionBaseStyle(layer.feature));
  });
  STATE.relationLayer.clearLayers();
  STATE.bufferLayer.clearLayers();
}

function dimAllRegionsExcept(activeId) {
  Object.entries(STATE.regionLayerById).forEach(([id, layer]) => {
    if (id === activeId) {
      layer.setStyle({
        color: CFG.colors.regionActive,
        weight: 3,
        fillColor: CFG.colors.regionActive,
        fillOpacity: 0.32,
      });
      layer.bringToFront();
    } else {
      layer.setStyle({ fillOpacity: 0.04, opacity: 0.18 });
    }
  });
}

function restoreAllRegions() {
  Object.values(STATE.regionLayerById).forEach((layer) => layer.setStyle(regionBaseStyle(layer.feature)));
}

function selectRegion(regionId) {
  STATE.selected = { type: "region", id: regionId };
  document.querySelectorAll(".region-item").forEach((el) => el.classList.toggle("active", el.dataset.id === regionId));

  clearSelectionVisuals();
  dimAllRegionsExcept(regionId);

  const feature = STATE.data.regions.features.find((f) => f.properties.id === regionId);
  const layer = STATE.regionLayerById[regionId];
  STATE.map.fitBounds(layer.getBounds().pad(0.6), { animate: true, duration: 0.6 });

  renderRegionInfo(feature);
}

function selectPipe(pipeId) {
  const feature = STATE.data.pipes.features.find((f) => f.properties.id === pipeId);
  if (!feature) return;
  STATE.selected = { type: "pipe", id: pipeId };
  renderPipeInfo(feature);
}

function selectDefect(defectId) {
  const feature = STATE.data.defects.features.find((f) => f.properties.id === defectId);
  if (!feature) return;
  STATE.selected = { type: "defect", id: defectId };
  renderDefectInfo(feature);
}

function resetView() {
  STATE.selected = { type: null, id: null };
  document.querySelectorAll(".region-item").forEach((el) => el.classList.remove("active"));
  restoreAllRegions();
  STATE.relationLayer.clearLayers();
  STATE.bufferLayer.clearLayers();
  STATE.map.setView(CFG.center, CFG.zoom, { animate: true });
  document.getElementById("infoEmpty").classList.remove("hidden");
  document.getElementById("infoContent").classList.add("hidden");
  document.getElementById("infoContent").innerHTML = "";
  destroyCharts();
}

/* -------------------------------------------------------------------- */
/*  右侧信息面板 —— 片区画像                                              */
/* -------------------------------------------------------------------- */
function destroyCharts() {
  Object.values(STATE.charts).forEach((c) => c && c.dispose && c.dispose());
  STATE.charts = {};
}

function renderRegionInfo(feature) {
  destroyCharts();
  const p = feature.properties;
  const tpl = document.getElementById("tpl-region-info").content.cloneNode(true);
  const content = document.getElementById("infoContent");
  document.getElementById("infoEmpty").classList.add("hidden");
  content.classList.remove("hidden");
  content.innerHTML = "";
  content.appendChild(tpl);

  content.querySelector("#tRegionTitle").textContent = `${p.name}片区 · 管网复合风险画像`;
  content.querySelector("#tRiskScore").textContent = p.riskScore;

  // Tabs
  content.querySelectorAll(".info-tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      content.querySelectorAll(".info-tab").forEach((b) => b.classList.remove("active"));
      content.querySelectorAll(".tab-pane").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      content.querySelector(`.tab-pane[data-pane="${btn.dataset.tab}"]`).classList.add("active");
      // resize echarts on tab switch
      Object.values(STATE.charts).forEach((c) => c && c.resize && c.resize());
    });
  });

  // 模块1 基本信息
  const baseKV = [
    ["片区面积", `${p.area} km²`],
    ["居民人口/户数", `${p.population.toLocaleString()} 人 / ${p.households.toLocaleString()} 户`],
    ["建筑密度", p.affectedBuildingCount > 6 ? "高（老旧建筑集中）" : "中等"],
    ["临近水系", p.nearbyWater],
    ["临近边坡/挡墙", p.nearbySlope],
    ["主要排水去向", p.drainOutlet],
  ];
  content.querySelector("#tBaseGrid").innerHTML = baseKV
    .map(([k, v]) => `<div class="kv-item"><div class="kv-k">${k}</div><div class="kv-v">${v}</div></div>`)
    .join("");

  // 模块2 管网资产
  const assetKV = [
    ["雨水管网长度", `${p.pipeLengthStorm} km`],
    ["污水管网长度", `${p.pipeLengthSewage} km`],
    ["排洪箱涵/渠道长度", `${p.culvertLength} km`],
    ["管网缺陷总数", `${p.defectCount} 处`],
    ["重大风险缺陷", `${p.majorDefectCount} 处`],
    ["受影响边坡/挡墙", `${p.affectedSlopeCount} 处`],
  ];
  content.querySelector("#tAssetGrid").innerHTML = assetKV
    .map(([k, v]) => `<div class="kv-item"><div class="kv-k">${k}</div><div class="kv-v">${v}</div></div>`)
    .join("");

  // 模块3 缺陷统计（环形图）
  const regionDefects = STATE.data.defects.features.filter((d) => d.properties.regionId === p.id);
  const typeCounts = {};
  regionDefects.forEach((d) => {
    typeCounts[d.properties.defectType] = (typeCounts[d.properties.defectType] || 0) + 1;
  });
  renderDonutChart("tDefectChart", typeCounts);

  // 模块4 风险维度（雷达图）
  renderRiskRadar("tRiskChart", p);

  // 模块5 上下游关系
  renderFlowDiagram(content, p);

  // 模块6 治理建议 + 对比图
  renderActionList(content, p);
  renderCompareChart("tCompareChart", p);

  // 模块7 决策提示
  content.querySelector("#tDecisionText").textContent = buildDecisionText(p);
}

function buildDecisionText(p) {
  const patterns = [];
  if (p.affectedSlopeCount > 0) patterns.push("坡体/挡墙滞水");
  if (p.affectedBuildingCount > 0) patterns.push("房屋基础影响");
  if (p.majorDefectCount >= 3) patterns.push("管网缺陷密集");
  const tag = patterns.length ? patterns.join("—") + "叠加型风险区" : "一般管网隐患区";
  const advice =
    p.priority === "近期"
      ? "建议纳入近期优先治理清单，与危房治理/消防通道打通协同实施。"
      : p.priority === "中期"
      ? "建议纳入中期治理计划，加强监测预警作为过渡措施。"
      : "建议纳入长效管护计划，定期巡查复核。";
  return `该片区属于${tag}，综合风险分值 ${p.riskScore} 分（${p.riskLevel}）。${advice}`;
}

/* ---- 环形图：缺陷类型构成 ---- */
function renderDonutChart(domId, typeCounts) {
  const dom = document.getElementById(domId);
  if (!dom) return;
  const chart = echarts.init(dom, null, { renderer: "svg" });
  STATE.charts.defect = chart;
  const entries = Object.entries(typeCounts);
  const palette = ["#35d6f0", "#b06bd8", "#ff9a3d", "#ffd25c", "#ff4b4f", "#4fd08a", "#3a7bd5", "#e0b467", "#6f88a8", "#ff2d3d"];
  chart.setOption({
    backgroundColor: "transparent",
    textStyle: { color: "#a9c0dd", fontFamily: "inherit", fontSize: 11 },
    tooltip: { trigger: "item", backgroundColor: "#0b1b34", borderColor: "#35d6f0", textStyle: { color: "#eaf3ff" } },
    legend: { orient: "vertical", right: 4, top: 10, textStyle: { color: "#a9c0dd", fontSize: 10.5 }, itemWidth: 8, itemHeight: 8 },
    series: [
      {
        type: "pie",
        radius: ["42%", "70%"],
        center: ["36%", "52%"],
        avoidLabelOverlap: true,
        itemStyle: { borderColor: "#0a162a", borderWidth: 2 },
        label: { color: "#eaf3ff", fontSize: 10, formatter: "{b}\n{c}处" },
        labelLine: { lineStyle: { color: "#3a5a80" } },
        data: entries.map(([name, value], i) => ({ name, value, itemStyle: { color: palette[i % palette.length] } })),
      },
    ],
  });
}

/* ---- 雷达图：风险维度 ---- */
function computeRiskDims(p) {
  // 由片区属性派生的示意维度分值（0-100），非真实计算模型
  const base = p.riskScore;
  const slopeF = Math.min(1, p.affectedSlopeCount / 5);
  const buildF = Math.min(1, p.affectedBuildingCount / 12);
  const defectF = Math.min(1, p.majorDefectCount / 8);
  const popF = Math.min(1, p.population / 16000);
  return [
    Math.round(base * 0.6 + defectF * 40), // 管网结构风险
    Math.round(base * 0.5 + defectF * 50), // 排水能力风险
    Math.round(base * 0.4 + defectF * 35 + 15), // 内涝风险
    Math.round(base * 0.4 + slopeF * 60), // 对边坡/挡墙影响
    Math.round(base * 0.35 + buildF * 60), // 对房屋基础影响
    Math.round(base * 0.3 + (p.priority === "近期" ? 35 : 15)), // 对消防救援影响
    Math.round(base * 0.5 + popF * 45), // 居民暴露度
    Math.round(base * 0.8 + (p.priority === "近期" ? 15 : 0)), // 治理紧迫性
  ].map((v) => Math.max(10, Math.min(98, v)));
}

function renderRiskRadar(domId, p) {
  const dom = document.getElementById(domId);
  if (!dom) return;
  const chart = echarts.init(dom, null, { renderer: "svg" });
  STATE.charts.risk = chart;
  const dims = computeRiskDims(p);
  const indicators = ["管网结构风险", "排水能力风险", "内涝风险", "边坡/挡墙影响", "房屋基础影响", "消防救援影响", "居民暴露度", "治理紧迫性"];
  chart.setOption({
    backgroundColor: "transparent",
    tooltip: { backgroundColor: "#0b1b34", borderColor: "#35d6f0", textStyle: { color: "#eaf3ff" } },
    radar: {
      indicator: indicators.map((name) => ({ name, max: 100 })),
      radius: "62%",
      center: ["50%", "54%"],
      axisName: { color: "#a9c0dd", fontSize: 10 },
      splitArea: { areaStyle: { color: ["rgba(53,214,240,0.03)", "rgba(53,214,240,0.06)"] } },
      splitLine: { lineStyle: { color: "rgba(120,170,220,0.25)" } },
      axisLine: { lineStyle: { color: "rgba(120,170,220,0.25)" } },
    },
    series: [
      {
        type: "radar",
        data: [
          {
            value: dims,
            name: p.name,
            areaStyle: { color: "rgba(224,180,103,0.22)" },
            lineStyle: { color: "#e0b467", width: 2 },
            itemStyle: { color: "#e0b467" },
          },
        ],
      },
    ],
  });
}

/* ---- 上下游关系（简化流程图，纯 DOM 实现，兜底稳健） ---- */
function renderFlowDiagram(content, p) {
  const idx = STATE.data.regions.features.findIndex((f) => f.properties.id === p.id);
  const feats = STATE.data.regions.features;
  const upstream = feats[idx - 1] ? feats[idx - 1].properties.name : "上游山体汇水区";
  const downstream = feats[idx + 1] ? feats[idx + 1].properties.name : "下游片区";
  const outlet = STATE.data.outlets.features.find((o) => o.properties.regionId === p.id);
  const hasCulvert = STATE.data.pipes.features.some(
    (pp) => pp.properties.type === "culvert" && pp.properties.upstreamRegion === p.id
  );

  const nodes = [
    { label: `上游汇水区\n（${upstream}方向）`, hot: false },
    { label: `${p.name}片区\n瓶颈节点`, hot: p.riskLevel === "高风险" || p.riskLevel === "重大风险" },
    { label: hasCulvert ? `下游排口/箱涵\n${outlet ? outlet.properties.name : ""}` : `下游片区\n（${downstream}）`, hot: false },
    { label: "长江 / 大宁河", hot: false },
  ];
  content.querySelector("#tFlowDiagram").innerHTML = nodes
    .map((n, i) => {
      const arrow = i > 0 ? `<div class="flow-arrow">➜</div>` : "";
      return `${arrow}<div class="flow-node ${n.hot ? "hot" : ""}">${n.label.replace(/\n/g, "<br/>")}</div>`;
    })
    .join("");

  const backflow = outlet ? outlet.properties.backflowRisk : "低";
  content.querySelector("#tFlowNotes").innerHTML = `
    <div>· 上游来水压力：${p.riskLevel === "重大风险" ? "较大，汛期易形成短时高水位" : "一般"}</div>
    <div>· 当前片区瓶颈节点：<b>${p.majorDefectCount}</b> 处重大缺陷，需重点关注管网结构与排水能力</div>
    <div>· 下游排口顶托风险：<b>${backflow}</b></div>
    <div>· 可能波及：${p.nearbySlope}${p.affectedBuildingCount ? "、周边" + p.affectedBuildingCount + "处房屋基础" : ""}${
    p.priority === "近期" ? "、消防通道通行" : ""
  }</div>`;
}

/* ---- 治理建议列表 ---- */
const ACTION_POOL = [
  ["清淤疏通", "解决淤积/沉积类缺陷，恢复设计过流能力"],
  ["管道修复", "针对破裂、腐蚀、树根侵入等结构性缺陷开展内衬或开挖修复"],
  ["管径扩容", "对过流能力不足 3 年一遇的管段实施扩容改造"],
  ["雨污混错接改造", "解决雨污分流不彻底问题，降低污水入渗对坡体的影响"],
  ["排口防倒灌改造", "针对顶托风险较高的入江排口增设防倒灌设施"],
  ["箱涵结构修复", "对存在脱空、塌陷风险的箱涵实施结构性加固"],
  ["截排水沟增设", "完善坡面/挡墙后部截排水体系，降低坡体滞水风险"],
  ["边坡滞水点治理", "结合场地防护工程稳定性评估同步治理"],
  ["监测预警布设", "针对高风险片区布设自动化位移/水位监测"],
  ["与危房治理/消防通道协同实施", "统筹房屋加固/搬迁与消防通道打通同步推进"],
];
function renderActionList(content, p) {
  const n = p.priority === "近期" ? 6 : p.priority === "中期" ? 4 : 3;
  const list = ACTION_POOL.slice(0, n);
  content.querySelector("#tActionList").innerHTML = list
    .map(([t, d], i) => `<li><b>${t}</b><br/><span>${d}</span></li>`)
    .join("");
}

/* ---- 治理前后风险分值对比 ---- */
function renderCompareChart(domId, p) {
  const dom = document.getElementById(domId);
  if (!dom) return;
  const chart = echarts.init(dom, null, { renderer: "svg" });
  STATE.charts.compare = chart;
  const before = p.riskScore;
  const after = Math.max(15, Math.round(before * 0.58));
  chart.setOption({
    backgroundColor: "transparent",
    grid: { left: 30, right: 16, top: 20, bottom: 24 },
    textStyle: { color: "#a9c0dd", fontSize: 11 },
    tooltip: { backgroundColor: "#0b1b34", borderColor: "#35d6f0", textStyle: { color: "#eaf3ff" } },
    xAxis: { type: "category", data: ["治理前", "治理后（预计）"], axisLine: { lineStyle: { color: "#3a5a80" } } },
    yAxis: { type: "value", max: 100, splitLine: { lineStyle: { color: "rgba(120,170,220,0.12)" } } },
    series: [
      {
        type: "bar",
        data: [
          { value: before, itemStyle: { color: "#ff4b4f" } },
          { value: after, itemStyle: { color: "#4fd08a" } },
        ],
        barWidth: "46%",
        label: { show: true, position: "top", color: "#eaf3ff" },
      },
    ],
  });
}

/* -------------------------------------------------------------------- */
/*  右侧信息面板 —— 管线                                                  */
/* -------------------------------------------------------------------- */
function renderPipeInfo(feature) {
  destroyCharts();
  const p = feature.properties;
  const tpl = document.getElementById("tpl-pipe-info").content.cloneNode(true);
  const content = document.getElementById("infoContent");
  document.getElementById("infoEmpty").classList.add("hidden");
  content.classList.remove("hidden");
  content.innerHTML = "";
  content.appendChild(tpl);

  content.querySelector("#pPipeTitle").textContent = p.name;
  const riskBadge = content.querySelector("#pPipeRisk");
  riskBadge.textContent = p.riskLevel;
  riskBadge.style.color = CFG.severityColor[p.riskLevel] || "#a9c0dd";
  riskBadge.style.borderColor = CFG.severityColor[p.riskLevel] || "#a9c0dd";

  const typeLabel = { stormwater: "雨水管网", sewage: "污水管网", combined: "混错接管段", culvert: "排洪箱涵/渠道" }[p.type];
  const kv = [
    ["管线类型", typeLabel],
    ["管径", p.diameter ? `DN${p.diameter}` : "箱涵（无统一管径）"],
    ["材质", p.material],
    ["长度", `${p.length} m`],
    ["建设年代", `${p.buildYear} 年`],
    ["流向", p.flowDirection],
    ["现状", p.status],
    ["检测方式", p.type === "culvert" ? "人工/无人机三维扫描" : "管道机器人(CCTV) / 管道潜望镜(QV)"],
  ];
  content.querySelector("#pPipeGrid").innerHTML = kv
    .map(([k, v]) => `<div class="kv-item"><div class="kv-k">${k}</div><div class="kv-v">${v}</div></div>`)
    .join("");

  const chainSteps = ["管网缺陷", "渗漏 / 排水不畅", "坡体滞水 / 挡墙变形", "房屋开裂 / 内涝", "居民安全风险"];
  content.querySelector("#pChain").innerHTML = chainSteps
    .map((s, i) => {
      const arrow = i > 0 ? `<span class="chain-arrow">→</span>` : "";
      const isTail = i === chainSteps.length - 1;
      return `${arrow}<span class="chain-node ${isTail ? "tail" : ""}">${s}</span>`;
    })
    .join("");
}

/* -------------------------------------------------------------------- */
/*  右侧信息面板 —— 缺陷点                                                */
/* -------------------------------------------------------------------- */
function renderDefectInfo(feature) {
  destroyCharts();
  const p = feature.properties;
  const tpl = document.getElementById("tpl-defect-info").content.cloneNode(true);
  const content = document.getElementById("infoContent");
  document.getElementById("infoEmpty").classList.add("hidden");
  content.classList.remove("hidden");
  content.innerHTML = "";
  content.appendChild(tpl);

  content.querySelector("#dDefectTitle").textContent = `${p.id} · ${p.defectType}`;
  const sevBadge = content.querySelector("#dDefectSeverity");
  sevBadge.textContent = p.severity;
  sevBadge.style.color = CFG.severityColor[p.severity];
  sevBadge.style.borderColor = CFG.severityColor[p.severity];

  const kv = [
    ["缺陷编号", p.id],
    ["所属管线", p.pipeId],
    ["所属片区", p.regionName],
    ["缺陷类型", p.defectType],
    ["严重程度", p.severity],
    ["CCTV 评分（示意）", p.cctvScore],
    ["QV 检测结果", p.qvResult],
    ["建议影响半径", `${p.impactRadius} m`],
    ["建议处置措施", p.suggestedAction],
    ["处置紧迫性", p.urgency],
  ];
  content.querySelector("#dDefectGrid").innerHTML = kv
    .map(([k, v]) => `<div class="kv-item"><div class="kv-k">${k}</div><div class="kv-v">${v}</div></div>`)
    .join("");

  // 缓冲区 + 关系连线绘制
  STATE.bufferLayer.clearLayers();
  STATE.relationLayer.clearLayers();
  const center = [feature.geometry.coordinates[1], feature.geometry.coordinates[0]];
  L.circle(center, {
    radius: p.impactRadius,
    color: CFG.severityColor[p.severity],
    weight: 1,
    fillOpacity: 0.06,
    dashArray: "4,4",
  }).addTo(STATE.bufferLayer);

  const rels = STATE.data.relations.relations.filter((r) => r.sourceId === p.id);
  const relNodes = [`<span class="chain-node">${p.defectType}缺陷</span>`];
  rels.forEach((r) => {
    relNodes.push(`<span class="chain-arrow">→</span>`);
    relNodes.push(`<span class="chain-node tail">${r.relationType}：${targetLabel(r)}</span>`);
    drawRelationLine(center, r);
  });
  if (!rels.length) relNodes.push(`<span class="chain-arrow">→</span><span class="chain-node">暂无显著关联对象（示意）</span>`);
  content.querySelector("#dRelations").innerHTML = relNodes.join("");
}

function targetLabel(r) {
  const map = { slope: STATE.data.slopes, building: STATE.data.buildings, waterlogging: STATE.data.waterlogging, fireAccess: STATE.data.fireaccess, outlet: STATE.data.outlets };
  const coll = map[r.targetType];
  if (!coll) return r.targetId;
  const f = coll.features.find((x) => x.properties.id === r.targetId);
  return f ? f.properties.name : r.targetId;
}

function targetLatLng(r) {
  const map = { slope: STATE.data.slopes, building: STATE.data.buildings, waterlogging: STATE.data.waterlogging, fireAccess: STATE.data.fireaccess, outlet: STATE.data.outlets };
  const coll = map[r.targetType];
  if (!coll) return null;
  const f = coll.features.find((x) => x.properties.id === r.targetId);
  if (!f) return null;
  if (f.geometry.type === "Point") return [f.geometry.coordinates[1], f.geometry.coordinates[0]];
  // polygon: 取质心近似（首点平均）
  const ring = f.geometry.coordinates[0];
  const lat = ring.reduce((s, c) => s + c[1], 0) / ring.length;
  const lon = ring.reduce((s, c) => s + c[0], 0) / ring.length;
  return [lat, lon];
}

function drawRelationLine(from, r) {
  const to = targetLatLng(r);
  if (!to) return;
  L.polyline([from, to], {
    color: "#e0b467",
    weight: 2,
    dashArray: "5,5",
    opacity: 0.85,
  }).addTo(STATE.relationLayer);
  L.circleMarker(to, { radius: 5, color: "#e0b467", fillColor: "#e0b467", fillOpacity: 0.8 }).addTo(STATE.relationLayer);
}

/* -------------------------------------------------------------------- */
/*  领导汇报演示模式                                                      */
/* -------------------------------------------------------------------- */
const DEMO_STEPS = [
  {
    text: "全区总览：巫山县城迁建区管网—坡体—房屋—消防复合风险一张图",
    run: () => {
      resetView();
    },
  },
  {
    text: "风险聚焦：管网缺陷密集片区高亮，其他片区暗淡，凸显重点治理区域",
    run: () => {
      const hotIds = STATE.data.overview.priorityRegionNames
        .map((name) => STATE.data.regions.features.find((f) => f.properties.name === name)?.properties.id)
        .filter(Boolean);
      Object.entries(STATE.regionLayerById).forEach(([id, layer]) => {
        if (hotIds.includes(id)) {
          layer.setStyle({ color: CFG.colors.regionActive, weight: 2.4, fillColor: CFG.colors.regionActive, fillOpacity: 0.28 });
        } else {
          layer.setStyle({ fillOpacity: 0.03, opacity: 0.15 });
        }
      });
    },
  },
  {
    text: "点击典型片区：以「集仙」片区为例，展示片区管网复合风险画像",
    run: () => {
      const target = STATE.data.regions.features.find((f) => f.properties.name === "集仙");
      if (target) selectRegion(target.properties.id);
    },
  },
  {
    text: "展示风险链：上游汇水 → 管网缺陷 → 箱涵瓶颈 → 边坡/挡墙影响 → 房屋/消防影响",
    run: () => {
      const content = document.getElementById("infoContent");
      const flowTab = content.querySelector('.info-tab[data-tab="flow"]');
      if (flowTab) flowTab.click();
      // 高亮一个重大风险缺陷点的关联关系，作为风险链示例
      const critical = STATE.data.defects.features.find(
        (d) => d.properties.regionName === "集仙" && d.properties.severity === "重大风险"
      );
      if (critical) {
        const rels = STATE.data.relations.relations.filter((r) => r.sourceId === critical.properties.id);
        STATE.relationLayer.clearLayers();
        const center = [critical.geometry.coordinates[1], critical.geometry.coordinates[0]];
        rels.forEach((r) => drawRelationLine(center, r));
      }
    },
  },
  {
    text: "治理建议：清淤疏通、管道修复、雨污分流、排口防倒灌、箱涵修复、监测预警、片区综合治理",
    run: () => {
      const content = document.getElementById("infoContent");
      const actionTab = content.querySelector('.info-tab[data-tab="action"]');
      if (actionTab) actionTab.click();
    },
  },
  {
    text: "返回全区项目库：各片区综合风险分值排序，形成近期 / 中期 / 远期治理建议清单",
    run: () => {
      restoreAllRegions();
      showPriorityRanking();
    },
  },
];

function showPriorityRanking() {
  destroyCharts();
  document.getElementById("infoEmpty").classList.add("hidden");
  const content = document.getElementById("infoContent");
  content.classList.remove("hidden");
  const ranking = STATE.data.overview.regionRanking;
  content.innerHTML = `
    <div class="info-header">
      <div class="info-header-title">迁建区各片区综合风险排序 / 项目优先级建议</div>
    </div>
    <div id="rankChart" class="chart-box" style="height:340px;"></div>
    <div class="flow-notes" style="margin-top:6px;">
      近期（高风险/重大风险，${ranking.filter((r) => r.priority === "近期").length}个）优先纳入除险降危实施方案首批项目清单；
      中期（${ranking.filter((r) => r.priority === "中期").length}个）结合年度投资计划滚动推进；
      远期（${ranking.filter((r) => r.priority === "远期").length}个）纳入长效监测与常规巡查。
    </div>`;
  const dom = document.getElementById("rankChart");
  const chart = echarts.init(dom, null, { renderer: "svg" });
  STATE.charts.rank = chart;
  chart.setOption({
    backgroundColor: "transparent",
    textStyle: { color: "#a9c0dd", fontSize: 11 },
    grid: { left: 70, right: 30, top: 10, bottom: 20 },
    tooltip: { backgroundColor: "#0b1b34", borderColor: "#35d6f0", textStyle: { color: "#eaf3ff" } },
    xAxis: { type: "value", max: 100, splitLine: { lineStyle: { color: "rgba(120,170,220,0.12)" } } },
    yAxis: {
      type: "category",
      data: ranking.map((r) => r.name).reverse(),
      axisLine: { lineStyle: { color: "#3a5a80" } },
    },
    series: [
      {
        type: "bar",
        data: ranking
          .map((r) => ({ value: r.riskScore, itemStyle: { color: CFG.severityColor[r.riskLevel] } }))
          .reverse(),
        barWidth: "56%",
        label: { show: true, position: "right", color: "#eaf3ff", fontSize: 10 },
      },
    ],
  });
}

function goDemoStep(i) {
  if (i < 0 || i >= DEMO_STEPS.length) return;
  STATE.demo.step = i;
  document.getElementById("demoStepLabel").textContent = `第 ${i + 1} / ${DEMO_STEPS.length} 步`;
  document.getElementById("demoText").textContent = DEMO_STEPS[i].text;
  DEMO_STEPS[i].run();
}

function startDemo() {
  STATE.demo.active = true;
  document.getElementById("demoBar").classList.remove("hidden");
  goDemoStep(0);
}
function stopDemo() {
  STATE.demo.active = false;
  document.getElementById("demoBar").classList.add("hidden");
  resetView();
}

/* -------------------------------------------------------------------- */
/*  时钟                                                                  */
/* -------------------------------------------------------------------- */
function tickClock() {
  const el = document.getElementById("clock");
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  el.textContent = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(
    d.getMinutes()
  )}:${pad(d.getSeconds())}`;
}

/* -------------------------------------------------------------------- */
/*  事件绑定 & 启动                                                       */
/* -------------------------------------------------------------------- */
function bindGlobalEvents() {
  document.getElementById("btnReset").addEventListener("click", () => {
    if (STATE.demo.active) stopDemo();
    else resetView();
  });
  document.getElementById("btnDemo").addEventListener("click", () => {
    if (STATE.demo.active) stopDemo();
    else startDemo();
  });
  document.getElementById("demoNext").addEventListener("click", () => goDemoStep(STATE.demo.step + 1));
  document.getElementById("demoPrev").addEventListener("click", () => goDemoStep(STATE.demo.step - 1));
  document.getElementById("demoStop").addEventListener("click", stopDemo);
}

async function main() {
  try {
    await loadAllData();
  } catch (err) {
    document.getElementById("app").innerHTML = `
      <div style="padding:40px;font-family:sans-serif;color:#ffd7d8;">
        数据加载失败：${err.message}<br/>
        请通过本地 HTTP 服务打开本页面（例如：<code>python3 -m http.server</code>），
        浏览器直接以 file:// 方式打开会因跨域限制无法加载 /data 目录下的 JSON 文件。
      </div>`;
    return;
  }
  initMap();
  buildLayers();
  renderLayerControls();
  renderRegionList();
  renderKPI();
  bindGlobalEvents();
  tickClock();
  setInterval(tickClock, 1000);
}

document.addEventListener("DOMContentLoaded", main);

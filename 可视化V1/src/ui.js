import { loadTopicLayer } from "./data-loader.js";

const LAYER_SECTIONS = ["地质", "防护工程", "房屋建筑", "管网", "消防"];

export class SystemUi {
  constructor(mapSystem) {
    this.mapSystem = mapSystem;
    this.catalog = window.LAYER_CATALOG || [];
    this.topicState = new Map();
    this.catalog.forEach((layer) => {
      this.topicState.set(layer.id, { config: layer, visible: false, loading: false, data: null });
    });
  }

  init() {
    this.renderMetrics();
    this.renderTabs();
    this.renderTopicLayers();
    this.renderWaterDetails();
    this.renderLegend();
    this.bindBasics();
    this.updateStatus("系统已就绪：可在左侧选择需要显示的图层。");
  }

  renderMetrics() {
    document.getElementById("metricSectionCount").textContent = LAYER_SECTIONS.length;
    document.getElementById("metricLayerCount").textContent = this.catalog.length + 1;
  }

  renderTabs() {
    document.querySelectorAll(".tab-button").forEach((button) => {
      button.addEventListener("click", () => {
        document.querySelectorAll(".tab-button").forEach((item) => item.classList.toggle("active", item === button));
        document.querySelectorAll(".tab-panel").forEach((panel) => panel.classList.toggle("active", panel.dataset.panel === button.dataset.tab));
      });
    });
  }

  bindBasics() {
    document.getElementById("toggleWater").addEventListener("change", (event) => {
      this.mapSystem.setWaterVisible(event.target.checked);
      this.renderLegend();
    });
    document.getElementById("clearTopicLayers").addEventListener("click", () => this.clearTopicLayers());
    document.getElementById("fitPipes").addEventListener("click", () => this.mapSystem.fitPipes());
    document.getElementById("fitAll").addEventListener("click", () => this.mapSystem.fitAllVisible());
    document.getElementById("toggleBasemap").addEventListener("click", (event) => {
      event.target.textContent = this.mapSystem.toggleBasemap();
    });
  }

  renderWaterDetails() {
    document.getElementById("waterLayerDetails").innerHTML = `
      <dt>来源</dt><dd>供水管线图（2025年测）.ovkml</dd>
      <dt>筛选</dt><dd>JSL 文件夹</dd>
      <dt>总长度</dt><dd>${window.SUMMARY.total_length_km.toFixed(2)} km</dd>
      <dt>坐标</dt><dd>CGCS2000，经纬度直叠</dd>
    `;
  }

  formatLayerMeta(layer) {
    if (layer.id === "drainage-defects-geojson-lines" && Number.isFinite(layer.lengthKm)) {
      return `总长度 ${layer.lengthKm.toFixed(2)} km`;
    }
    if (layer.id === "drainage-defects-geojson-points" && Number.isFinite(layer.pointCount)) {
      return `缺陷点 ${layer.pointCount.toLocaleString()} 个`;
    }
    if ((layer.category === "房屋建筑" || layer.id === "community-fire-risk") && Number.isFinite(layer.polygonCount)) {
      return `块数量 ${layer.polygonCount.toLocaleString()} 个`;
    }
    return layer.file || "";
  }

  renderLayerDetails(layer) {
    const filterRows = layer.sourceFolders?.length ? `<dt>筛选</dt><dd>${layer.sourceFolders.join("、")}</dd>` : "";
    const metricRows = this.renderLayerMetricRows(layer);
    return `
      <dt>来源</dt><dd>${layer.file}</dd>
      <dt>说明</dt><dd>${layer.description || "标准专题图层"}</dd>
      ${metricRows}
      ${filterRows}
    `;
  }

  renderLayerMetricRows(layer) {
    if (layer.id === "drainage-defects-geojson-lines" && Number.isFinite(layer.lengthKm)) {
      return `<dt>总长度</dt><dd>${layer.lengthKm.toFixed(2)} km</dd>`;
    }
    if (layer.id === "drainage-defects-geojson-points" && Number.isFinite(layer.pointCount)) {
      return `<dt>缺陷点</dt><dd>${layer.pointCount.toLocaleString()} 个</dd>`;
    }
    if ((layer.category === "房屋建筑" || layer.id === "community-fire-risk") && Number.isFinite(layer.polygonCount)) {
      return `<dt>块数量</dt><dd>${layer.polygonCount.toLocaleString()} 个</dd>`;
    }
    return "";
  }

  categoryForLayer(layer) {
    if (layer.category) return layer.category;
    if (layer.kind?.includes("drainage") || layer.id?.includes("water")) return "管网";
    if (layer.kind?.includes("building")) return "房屋建筑";
    return "管网";
  }

  renderWaterLayerCard() {
    const card = document.createElement("article");
    card.className = "topic-card layer-card";
    card.id = "waterLayerCard";
    card.innerHTML = `
      <label class="topic-main">
        <input type="checkbox" id="toggleWater">
        <span>
          <h3>供水管线图</h3>
          <div class="topic-meta">总长度 ${window.SUMMARY.total_length_km.toFixed(2)} km</div>
        </span>
      </label>
      <div class="topic-tools">
        <button id="fitPipes">定位</button>
      </div>
      <details class="layer-details">
        <summary>数据概况</summary>
        <dl id="waterLayerDetails"></dl>
      </details>
    `;
    return card;
  }

  renderTopicLayerCard(layer) {
    const card = document.createElement("article");
    card.className = "topic-card layer-card";
    card.dataset.layerId = layer.id;
    card.innerHTML = `
      <label class="topic-main">
        <input type="checkbox" ${layer.enabled ? "checked" : ""} data-layer-toggle="${layer.id}">
        <span>
          <h3>${layer.title}</h3>
          <div class="topic-meta">${this.formatLayerMeta(layer)}</div>
        </span>
      </label>
      <div class="topic-tools">
        <button data-layer-fit="${layer.id}">定位</button>
      </div>
      <details class="layer-details">
        <summary>数据概况</summary>
        <dl>${this.renderLayerDetails(layer)}</dl>
      </details>
    `;
    return card;
  }

  renderTopicLayers() {
    const list = document.getElementById("topicLayerList");
    list.innerHTML = "";
    const sections = new Map();
    LAYER_SECTIONS.forEach((sectionName) => {
      const section = document.createElement("section");
      section.className = "layer-section";
      section.dataset.layerSection = sectionName;
      section.innerHTML = `
        <div class="layer-section-title">
          <h3>${sectionName}</h3>
        </div>
        <div class="layer-section-body"></div>
      `;
      list.appendChild(section);
      sections.set(sectionName, section);
    });

    const appendToSection = (sectionName, card) => {
      const section = sections.get(sectionName);
      const body = section.querySelector(".layer-section-body");
      body.appendChild(card);
    };

    appendToSection("管网", this.renderWaterLayerCard());

    this.catalog.forEach((layer) => {
      appendToSection(this.categoryForLayer(layer), this.renderTopicLayerCard(layer));
    });

    sections.forEach((section) => {
      const body = section.querySelector(".layer-section-body");
      if (!body.children.length) {
        body.innerHTML = `<div class="layer-section-empty">暂无图层</div>`;
      }
    });

    list.addEventListener("change", async (event) => {
      const id = event.target.dataset.layerToggle;
      if (!id) return;
      if (event.target.checked) {
        await this.showTopicLayer(id);
      } else {
        this.hideTopicLayer(id);
      }
    });

    list.addEventListener("click", (event) => {
      const fitId = event.target.dataset.layerFit;
      if (fitId) this.mapSystem.fitLayer(fitId);
    });

    this.catalog.filter((layer) => layer.enabled).forEach((layer) => this.showTopicLayer(layer.id));
  }

  async showTopicLayer(id) {
    const entry = this.topicState.get(id);
    if (!entry || entry.visible || entry.loading) return;
    entry.loading = true;
    this.updateStatus(`正在加载：${entry.config.title}...`);
    try {
      entry.data = await loadTopicLayer(entry.config);
      entry.visible = true;
      this.mapSystem.addTopicLayer(entry.config, entry.data);
      this.updateStatus(`${entry.config.title} 已叠加。`);
    } catch (error) {
      this.updateStatus(`${entry.config.title} 加载失败。`);
      const checkbox = document.querySelector(`[data-layer-toggle="${id}"]`);
      if (checkbox) checkbox.checked = false;
    } finally {
      entry.loading = false;
      this.renderLegend();
    }
  }

  hideTopicLayer(id) {
    const entry = this.topicState.get(id);
    if (!entry) return;
    entry.visible = false;
    this.mapSystem.removeTopicLayer(id);
    this.renderLegend();
    this.updateStatus(`${entry.config.title} 已隐藏。`);
  }

  clearTopicLayers() {
    this.topicState.forEach((entry, id) => {
      entry.visible = false;
      const checkbox = document.querySelector(`[data-layer-toggle="${id}"]`);
      if (checkbox) checkbox.checked = false;
    });
    this.mapSystem.clearTopicLayers();
    this.renderLegend();
    this.updateStatus("专题图层已关闭。");
  }

  renderLegend() {
    const legend = document.getElementById("mapLegend");
    const rows = [];
    if (this.mapSystem.state.waterVisible) rows.push(["管网-供水管线图", "#00e5ff"]);
    [...this.topicState.values()].filter((entry) => entry.visible).forEach((entry) => {
      const category = this.categoryForLayer(entry.config);
      if (entry.config.severityColors) {
        rows.push([`${category}-1级缺陷`, entry.config.severityColors["1"]]);
        rows.push([`${category}-2级缺陷`, entry.config.severityColors["2"]]);
        rows.push([`${category}-3级缺陷`, entry.config.severityColors["3"]]);
        rows.push([`${category}-4级缺陷（严重）`, entry.config.severityColors["4"]]);
        return;
      }
      if (entry.config.riskColors) {
        Object.entries(entry.config.riskColors).forEach(([name, color]) => rows.push([`${category}-${name}`, color]));
        return;
      }
      rows.push([`${category}-${entry.config.title}`, entry.config.color]);
    });
    legend.hidden = rows.length === 0;
    legend.innerHTML = rows.map(([name, color]) => `
      <div class="legend-row">
        <span class="legend-swatch" style="background:${color}"></span>
        <span>${name}</span>
      </div>
    `).join("");
  }

  updateStatus(text) {
    document.getElementById("statusLine").textContent = text;
  }
}

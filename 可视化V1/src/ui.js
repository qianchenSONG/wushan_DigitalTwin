import { loadTopicLayer } from "./data-loader.js";

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
    this.renderWaterDetails();
    this.renderTopicLayers();
    this.renderLegend();
    this.bindBasics();
    this.updateStatus("系统已就绪：供水管线为主图层，专题图层可在左侧打开。");
  }

  renderMetrics() {
    document.getElementById("metricPipeLength").textContent = `${window.SUMMARY.total_length_km.toFixed(2)} km`;
    document.getElementById("metricPipeSegments").textContent = window.SUMMARY.pipe_segment_count.toLocaleString();
    document.getElementById("metricPipeNodes").textContent = window.SUMMARY.node_count.toLocaleString();
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
    document.getElementById("toggleWaterNodes").addEventListener("change", (event) => this.mapSystem.setWaterNodesVisible(event.target.checked));
    document.getElementById("clearTopicLayers").addEventListener("click", () => this.clearTopicLayers());
    document.getElementById("fitPipes").addEventListener("click", () => this.mapSystem.fitPipes());
    document.getElementById("fitAll").addEventListener("click", () => this.mapSystem.fitAllVisible());
    document.getElementById("toggleBasemap").addEventListener("click", (event) => {
      event.target.textContent = this.mapSystem.toggleBasemap();
    });
  }

  renderWaterDetails() {
    document.getElementById("waterLayerMeta").textContent = `${window.SUMMARY.pipe_segment_count.toLocaleString()} 段线 · ${window.SUMMARY.node_count.toLocaleString()} 个节点 · ${window.SUMMARY.total_length_km.toFixed(2)} km`;
    document.getElementById("waterLayerDetails").innerHTML = `
      <dt>来源</dt><dd>供水管线图（2025年测）.geojson</dd>
      <dt>坐标</dt><dd>EPSG:4490，经纬度直叠</dd>
      <dt>线对象</dt><dd>${window.SUMMARY.pipe_segment_count.toLocaleString()} 段</dd>
      <dt>节点</dt><dd>${window.SUMMARY.node_count.toLocaleString()} 个</dd>
      <dt>长度</dt><dd>${window.SUMMARY.total_length_km.toFixed(2)} km</dd>
    `;
  }

  renderTopicLayers() {
    const list = document.getElementById("topicLayerList");
    list.innerHTML = "";
    this.catalog.forEach((layer) => {
      const card = document.createElement("article");
      card.className = "topic-card layer-card";
      card.dataset.layerId = layer.id;
      card.innerHTML = `
        <label class="topic-main">
          <input type="checkbox" ${layer.enabled ? "checked" : ""} data-layer-toggle="${layer.id}">
          <span>
            <h3>${layer.title}</h3>
            <div class="topic-meta">${layer.lineCount.toLocaleString()} 段线 · ${layer.pointCount.toLocaleString()} 个点 · ${layer.lengthKm.toFixed(2)} km</div>
          </span>
        </label>
        <div class="topic-tools">
          <button data-layer-fit="${layer.id}">定位</button>
        </div>
        <details class="layer-details">
          <summary>数据概况</summary>
          <dl>
            <dt>来源</dt><dd>${layer.file}</dd>
            <dt>说明</dt><dd>${layer.description || "标准专题图层"}</dd>
            <dt>原始要素</dt><dd>${layer.recordCount.toLocaleString()} 条</dd>
            <dt>线对象</dt><dd>${layer.lineCount.toLocaleString()} 段</dd>
            <dt>点对象</dt><dd>${layer.pointCount.toLocaleString()} 个</dd>
            <dt>长度</dt><dd>${layer.lengthKm.toFixed(2)} km</dd>
          </dl>
        </details>
      `;
      list.appendChild(card);
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
    if (this.mapSystem.state.waterVisible) rows.push(["供水管线图", "#00e5ff"]);
    rows.push(...[...this.topicState.values()].filter((entry) => entry.visible).map((entry) => [entry.config.title, entry.config.color]));
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

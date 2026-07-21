export class MapSystem {
  constructor({ onStatus, onLayerChange }) {
    this.onStatus = onStatus;
    this.onLayerChange = onLayerChange;
    this.topicLayers = new Map();
    this.initialViewOffset = { x: 0, y: 0 };
    this.localBasemapBounds = L.latLngBounds([[31.027048, 109.80011], [31.125848, 109.940186]]);
    this.state = {
      waterVisible: false,
      basemap: "street"
    };
  }

  init() {
    this.map = L.map("map", { preferCanvas: true, zoomControl: true });
    this.streetLayer = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "© OpenStreetMap"
    });
    this.satelliteLayer = L.tileLayer("./data/basemaps/ditu17/{z}/{x}/{y}.png?v=ditu17-tpk-20260721", {
      minZoom: 0,
      maxNativeZoom: 17,
      maxZoom: 19,
      bounds: this.localBasemapBounds,
      noWrap: true,
      attribution: "奥维导出底图"
    });
    this.streetLayer.addTo(this.map);
    this.map.createPane("firePane");
    this.map.getPane("firePane").style.zIndex = 430;
    this.map.createPane("topicPane");
    this.map.getPane("topicPane").style.zIndex = 450;
    this.map.createPane("buildingPane");
    this.map.getPane("buildingPane").style.zIndex = 460;
    this.map.createPane("defectPane");
    this.map.getPane("defectPane").style.zIndex = 470;
    this.svgRenderer = L.svg({ pane: "firePane" });

    this.pipeBounds = L.latLngBounds(window.SUMMARY.bounds);
    this.initialBounds = this.findInitialBounds() || this.pipeBounds;
    this.pipeLayer = L.geoJSON(window.PIPES, {
      style: () => this.pipeStyle(),
      onEachFeature: (feature, layer) => this.bindPipeLine(feature, layer)
    });

    this.nodeLayer = null;
    this.map.fitBounds(this.initialBounds.pad(0.12));
    this.map.setMaxBounds(this.localBasemapBounds.pad(0.18));
    this.map.options.maxBoundsViscosity = 0.86;
    this.map.panBy([this.initialViewOffset.x, this.initialViewOffset.y], { animate: false });
    this.onStatus?.("系统已就绪，可在左侧选择需要显示的图层。");
  }

  findInitialBounds() {
    const drainageLayer = window.LAYER_CATALOG?.find((layer) => layer.id === "drainage-defects-geojson-lines");
    return drainageLayer?.bounds ? L.latLngBounds(drainageLayer.bounds) : null;
  }

  pipeStyle(highlight = false) {
    return {
      color: highlight ? "#ffffff" : "#00e5ff",
      weight: highlight ? 3.6 : 1.8,
      opacity: highlight ? 1 : 0.92,
      lineCap: "round",
      lineJoin: "round"
    };
  }

  topicLineStyle(color, highlight = false) {
    return {
      color: highlight ? "#ffffff" : color,
      weight: highlight ? 3.2 : 1.6,
      opacity: highlight ? 1 : 0.86,
      lineCap: "round",
      lineJoin: "round"
    };
  }

  topicPathStyle(layerConfig, highlight = false, feature = null) {
    const color = feature?.properties?.color || layerConfig.color || "#6fb2ff";
    const geometryType = feature?.geometry?.type;
    if (layerConfig.geometryType === "polygon" || geometryType === "Polygon" || geometryType === "MultiPolygon") {
      if (layerConfig.patternFill === "diagonal") {
      return {
        color: highlight ? "#ffffff" : color,
        weight: highlight ? 2.4 : 1.2,
        opacity: highlight ? 1 : 0.58,
        fillColor: `url(#${this.patternIdForColor(color)})`,
        fillOpacity: 1
      };
      }
      return {
        color: highlight ? "#ffffff" : color,
        weight: highlight ? 2.6 : 1.4,
        opacity: highlight ? 1 : 0.96,
        fillColor: color,
        fillOpacity: highlight ? 0.62 : 0.38
      };
    }
    return this.topicLineStyle(color, highlight);
  }

  patternIdForColor(color) {
    return `fire-hatch-${color.replace("#", "")}`;
  }

  ensureFirePatterns() {
    const container = this.svgRenderer?._container;
    if (!container || container.querySelector("#fire-hatch-ff0000")) return;
    const defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
    [
      ["fire-hatch-ff0000", "#ff0000"],
      ["fire-hatch-d89b12", "#d89b12"]
    ].forEach(([id, color]) => {
      const pattern = document.createElementNS("http://www.w3.org/2000/svg", "pattern");
      pattern.setAttribute("id", id);
      pattern.setAttribute("patternUnits", "userSpaceOnUse");
      pattern.setAttribute("width", "18");
      pattern.setAttribute("height", "18");
      const base = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      base.setAttribute("width", "18");
      base.setAttribute("height", "18");
      base.setAttribute("fill", color);
      base.setAttribute("fill-opacity", "0");
      const hatch = document.createElementNS("http://www.w3.org/2000/svg", "path");
      hatch.setAttribute("d", "M-4,18 L18,-4");
      hatch.setAttribute("stroke", color);
      hatch.setAttribute("stroke-width", "1.25");
      hatch.setAttribute("stroke-opacity", "0.42");
      hatch.setAttribute("stroke-linecap", "round");
      pattern.append(base, hatch);
      defs.appendChild(pattern);
    });
    container.prepend(defs);
  }

  bindPipeLine(feature, layer) {
    const p = feature.properties;
    const diameter = p.diameter ? `DN${p.diameter}` : "未识别";
    layer.bindPopup(`<b>${p.name}</b><br>材质：${p.material}<br>管径：${diameter}<br>长度：${p.length_m} m<br>编号：${p.id}`);
    layer.on("mouseover", () => layer.setStyle(this.pipeStyle(true)));
    layer.on("mouseout", () => layer.setStyle(this.pipeStyle(false)));
    layer.on("click", () => layer.setStyle(this.pipeStyle(true)));
  }

  setWaterVisible(visible) {
    this.state.waterVisible = visible;
    visible ? this.pipeLayer.addTo(this.map) : this.pipeLayer.remove();
    this.onLayerChange?.();
  }

  async setWaterNodesVisible(visible) {
    if (visible && !window.NODES) {
      this.onStatus?.("正在加载供水管点...");
      await new Promise((resolve, reject) => {
        const script = document.createElement("script");
        script.src = "./data/nodes.js";
        script.onload = resolve;
        script.onerror = reject;
        document.body.appendChild(script);
      });
    }
    if (!this.nodeLayer && window.NODES) {
      this.nodeLayer = L.geoJSON(window.NODES, {
        pointToLayer: (feature, latlng) => L.circleMarker(latlng, {
          radius: 1.7,
          color: "#ffffff",
          weight: 0.55,
          fillColor: "#00e5ff",
          fillOpacity: 0.78,
          opacity: 0.86
        }),
        onEachFeature: (feature, layer) => {
          const p = feature.properties;
          layer.bindPopup(`<b>${p.name || "未命名节点"}</b><br>${p.kind}<br>对象ID：${p.id}`);
        }
      });
    }
    if (this.nodeLayer) {
      visible ? this.nodeLayer.addTo(this.map) : this.nodeLayer.remove();
    }
    this.onStatus?.(visible ? "供水管点已显示。" : "供水管点已隐藏。");
    this.onLayerChange?.();
  }

  addTopicLayer(layerConfig, data) {
    this.removeTopicLayer(layerConfig.id);
    const color = layerConfig.color || "#6fb2ff";
    const pane = this.paneForLayer(layerConfig);
    const renderer = layerConfig.patternFill === "diagonal" ? this.svgRenderer : undefined;
    const group = L.layerGroup();
    const lineFeatures = data.lines?.features || [];
    const pointFeatures = data.points?.features || [];

    if (lineFeatures.length) {
      L.geoJSON(data.lines, {
        pane,
        renderer,
        style: (feature) => this.topicPathStyle(layerConfig, false, feature),
        onEachFeature: (feature, layer) => {
          this.bindTopicPopup(feature, layer);
          layer.on("mouseover", () => layer.setStyle(this.topicPathStyle(layerConfig, true, feature)));
          layer.on("mouseout", () => layer.setStyle(this.topicPathStyle(layerConfig, false, feature)));
          layer.on("click", () => layer.setStyle(this.topicPathStyle(layerConfig, true, feature)));
        }
      }).addTo(group);
    }

    if (pointFeatures.length) {
      L.geoJSON(data.points, {
        pane,
        pointToLayer: (feature, latlng) => L.circleMarker(latlng, {
          pane,
          radius: 2.1,
          color: "#ffffff",
          weight: 0.5,
          fillColor: feature.properties?.color || color,
          fillOpacity: 0.76,
          opacity: 0.84
        }),
        onEachFeature: (feature, layer) => this.bindTopicPopup(feature, layer)
      }).addTo(group);
    }

    group.addTo(this.map);
    if (layerConfig.patternFill === "diagonal") this.ensureFirePatterns();
    this.topicLayers.set(layerConfig.id, { group, data, config: layerConfig, visible: true });
    this.enforceLayerOrder();
    this.onLayerChange?.();
  }

  paneForLayer(layerConfig) {
    if (layerConfig.id === "drainage-defects-geojson-points") return "defectPane";
    if (layerConfig.id === "community-fire-risk") return "firePane";
    if (layerConfig.category === "房屋建筑") return "buildingPane";
    return "topicPane";
  }

  enforceLayerOrder() {
    const defects = this.topicLayers.get("drainage-defects-geojson-points");
    if (defects) defects.group.eachLayer?.((layer) => layer.bringToFront?.());
  }

  bindTopicPopup(feature, layer) {
    const p = feature.properties;
    const length = p.length_m ? `<br>长度：${p.length_m} m` : "";
    const area = p.area_m2 ? `<br>面积：${p.area_m2} m²` : "";
    const risk = p.risk_level ? `<br>隐患等级：${p.risk_level}` : "";
    const severity = p.severity_label ? `<br>缺陷等级：${p.severity_label}` : "";
    const defect = p.defect_category ? `<br>缺陷类型：${p.defect_category}` : "";
    const community = p.community ? `<br>社区：${p.community}` : "";
    layer.bindPopup(`<b>${p.name || "未命名对象"}</b><br>来源：${p.source}<br>类型：${p.kind}${community}${risk}${severity}${defect}${length}${area}`);
  }

  removeTopicLayer(id) {
    const existing = this.topicLayers.get(id);
    if (existing) {
      existing.group.remove();
      this.topicLayers.delete(id);
      this.onLayerChange?.();
    }
  }

  clearTopicLayers() {
    [...this.topicLayers.keys()].forEach((id) => this.removeTopicLayer(id));
  }

  fitPipes() {
    this.map.fitBounds(this.pipeBounds.pad(0.12));
  }

  fitLayer(id) {
    const layer = this.topicLayers.get(id);
    if (!layer) return;
    const bounds = layer.group.getBounds?.();
    if (bounds && bounds.isValid()) this.map.fitBounds(bounds.pad(0.08));
  }

  fitAllVisible() {
    const bounds = L.latLngBounds([]);
    if (this.state.waterVisible) bounds.extend(this.pipeBounds);
    this.topicLayers.forEach((entry) => {
      const layerBounds = entry.group.getBounds?.();
      if (layerBounds && layerBounds.isValid()) bounds.extend(layerBounds);
    });
    if (bounds.isValid()) this.map.fitBounds(bounds.pad(0.08));
  }

  toggleBasemap() {
    if (this.state.basemap === "street") {
      this.streetLayer.remove();
      this.satelliteLayer.addTo(this.map);
      this.state.basemap = "satellite";
      return "底图：奥维";
    }
    this.satelliteLayer.remove();
    this.streetLayer.addTo(this.map);
    this.state.basemap = "street";
    return "底图：街道";
  }
}

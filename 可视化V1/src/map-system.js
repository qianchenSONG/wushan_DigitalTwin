export class MapSystem {
  constructor({ onStatus, onLayerChange }) {
    this.onStatus = onStatus;
    this.onLayerChange = onLayerChange;
    this.topicLayers = new Map();
    this.state = {
      waterVisible: true,
      basemap: "street"
    };
  }

  init() {
    this.map = L.map("map", { preferCanvas: true, zoomControl: true });
    this.streetLayer = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "© OpenStreetMap"
    });
    this.satelliteLayer = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", {
      maxZoom: 19,
      attribution: "Tiles © Esri"
    });
    this.streetLayer.addTo(this.map);

    this.pipeBounds = L.latLngBounds(window.SUMMARY.bounds);
    this.pipeLayer = L.geoJSON(window.PIPES, {
      style: () => this.pipeStyle(),
      onEachFeature: (feature, layer) => this.bindPipeLine(feature, layer)
    }).addTo(this.map);

    this.nodeLayer = null;
    this.map.fitBounds(this.pipeBounds.pad(0.12));
    this.onStatus?.("系统已加载供水管线，可继续叠加专题图层。");
  }

  pipeStyle(highlight = false) {
    return {
      color: highlight ? "#ffffff" : "#00e5ff",
      weight: highlight ? 5.8 : 3.2,
      opacity: highlight ? 1 : 0.98,
      lineCap: "round",
      lineJoin: "round"
    };
  }

  topicLineStyle(color, highlight = false) {
    return {
      color: highlight ? "#ffffff" : color,
      weight: highlight ? 5.2 : 3,
      opacity: highlight ? 1 : 0.93,
      lineCap: "round",
      lineJoin: "round"
    };
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
          radius: 2.5,
          color: "#ffffff",
          weight: 0.9,
          fillColor: "#00e5ff",
          fillOpacity: 0.85,
          opacity: 0.95
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
    const group = L.layerGroup();
    const lineFeatures = data.lines?.features || [];
    const pointFeatures = data.points?.features || [];

    if (lineFeatures.length) {
      L.geoJSON(data.lines, {
        style: () => this.topicLineStyle(color),
        onEachFeature: (feature, layer) => {
          this.bindTopicPopup(feature, layer);
          layer.on("mouseover", () => layer.setStyle(this.topicLineStyle(color, true)));
          layer.on("mouseout", () => layer.setStyle(this.topicLineStyle(color, false)));
          layer.on("click", () => layer.setStyle(this.topicLineStyle(color, true)));
        }
      }).addTo(group);
    }

    if (pointFeatures.length) {
      L.geoJSON(data.points, {
        pointToLayer: (feature, latlng) => L.circleMarker(latlng, {
          radius: 3.2,
          color: "#ffffff",
          weight: 0.8,
          fillColor: color,
          fillOpacity: 0.82,
          opacity: 0.92
        }),
        onEachFeature: (feature, layer) => this.bindTopicPopup(feature, layer)
      }).addTo(group);
    }

    group.addTo(this.map);
    this.topicLayers.set(layerConfig.id, { group, data, config: layerConfig, visible: true });
    this.onLayerChange?.();
  }

  bindTopicPopup(feature, layer) {
    const p = feature.properties;
    const length = p.length_m ? `<br>长度：${p.length_m} m` : "";
    layer.bindPopup(`<b>${p.name || "未命名对象"}</b><br>来源：${p.source}<br>类型：${p.kind}${length}`);
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
      return "底图：卫星";
    }
    this.satelliteLayer.remove();
    this.streetLayer.addTo(this.map);
    this.state.basemap = "street";
    return "底图：街道";
  }
}

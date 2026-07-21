# 巫山城市安全调研数字孪生系统 V1

## 打开方式

### Windows

双击 `start_system.bat`，系统会自动打开浏览器。

### macOS

双击 `start_system.command`，系统会自动启动本地服务并打开浏览器。

如果 macOS 提示脚本不能打开，先在终端执行一次：

```bash
cd /Users/wutang/Developer/wushan_DigitalTwin/可视化V1
chmod +x start_system.command
./start_system.command
```

如果浏览器没有自动弹出，查看窗口里显示的地址，通常是：

`http://127.0.0.1:8765/`

如果 8765 端口已被占用，系统会自动尝试后续端口，最多到 8795；请以终端窗口里显示的地址为准。

## 这版为什么改成“前端系统”

上一版主要是一个单页 HTML 展示。现在已经拆成前端项目结构：

- `index.html`：系统入口。
- `src/`：前端界面、地图、图层加载、统计逻辑。
- `data/`：供水管线、巫山县边界、统计数据。
- `data/layers/`：从 `.ovobj` 提取出来的专题图层。
- `vendor/leaflet/`：本地地图组件库。
- `extract_ovobj_layers.py`：从奥维 `.ovobj` 文件提取专题图层。
- `build_wushan_water_vis.py`：从供水 CSV 生成主供水管线数据。
- `server.cjs` / `start_system.bat`：本地启动入口。
- `extract_tpk_basemap.py` / `build_local_basemap.command`：从奥维导出的 `.tpk` 底图包生成本地网页瓦片。

后续继续叠加专题时，优先把数据放进 `data/layers/`，再在图层目录里登记即可，不需要把所有逻辑塞进一个 HTML。

## 本地奥维底图

当前网页的“底图：奥维”使用奥维导出的局部 TPK 底图。由于底图文件较大，`.tpk` 原始包和解出的瓦片目录不提交到 Git。

本地生成方式：

```bash
cd /Users/wutang/Developer/wushan_DigitalTwin/可视化V1
python3 extract_tpk_basemap.py ../原始数据/ditu17.tpk data/basemaps/ditu17
```

Windows 可以双击运行：

```bat
build_local_basemap.bat
```

如果双击后提示找不到 `python`，需要先安装 Python 3，或把 Python 加入系统 PATH。

macOS 可以双击运行 `build_local_basemap.command`，也可以在终端运行：

```bash
cd /Users/wutang/Developer/wushan_DigitalTwin/可视化V1
chmod +x build_local_basemap.command
./build_local_basemap.command
```

需要先把奥维导出的 `ditu17.tpk` 放在项目的 `原始数据/` 文件夹中。生成后的瓦片目录为 `可视化V1/data/basemaps/ditu17/`。

## 已接入数据

### 主图层

- 供水管线图：来自 `供水管线图（2025年测）.geojson`
- GeoJSON 坐标系：EPSG:4490，经纬度直叠显示
- GeoJSON 要素：20,498 条
- 供水线对象：20,257 段
- 管点/节点：12,544 个
- 管线估算总长：135.22 km
- 说明：这版已使用奥维导出的标准 GeoJSON 真实线几何作为主供水图层，不再依赖 CSV/OVOBJ 连续点重建。

### 专题图层

- 排水管线图：来自 `巫山缺陷分布图.geojson`，82,615 段线，默认关闭。
- 排水管线缺陷分布：来自 `巫山缺陷分布图.geojson`，42,013 个点，默认关闭。
- 防洪排涝通道与排水缺陷分布重合较多，已从当前界面移除。
- 巫山县行政边界、巫山县+小区综合图、按管径显示线宽已按当前需求暂时从界面移除。

## 坐标说明

- 主供水管线按 `.geojson` 中的线几何叠加。
- 供水 CSV 使用 `经度`、`纬度` 字段，仅作为历史处理脚本和对照来源保留。
- `.ovobj` 中识别到的二进制坐标为 WGS84 风格经纬度，结构为“纬度、经度”。
- 当前供水、排水管线和排水管线缺陷均优先使用标准 GeoJSON 几何。`.ovobj` 处理脚本保留在目录中，作为无法导出标准格式时的备用方案。
- 默认底图为 OpenStreetMap；卫星底图使用本地奥维导出 TPK 瓦片，避免不同在线影像底图造成局部错位。

## 后续扩展建议

- 把 13 个迁建小区边界整理成真实面图层，替换当前概略片区。
- 将地灾点、防护工程、高切坡、高挡墙、消防设施继续接入 `data/layers/`。
- 给排水缺陷可继续按缺陷等级、管材、管径做专题筛选。
- 后续如果需要登录、数据编辑、后台管理，可以在当前结构上升级为 React/Vite 项目。

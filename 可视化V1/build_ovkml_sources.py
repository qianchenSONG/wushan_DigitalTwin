import json
import math
import re
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT.parent / "原始数据"
DATA = ROOT / "data"
LAYERS = DATA / "layers"
NS = {"k": "http://www.opengis.net/kml/2.2"}

WATER_OVKML = SRC / "供水管线图（2025年测）.ovkml"
DRAINAGE_OVKML = SRC / "巫山缺陷分布图.ovkml"

PIPE_LINE_FOLDERS = {"YS_LINE", "WS_LINE", "QTPS_LINE"}
DEFECT_FOLDERS = [
    "一级功能性缺陷",
    "一级结构性缺陷",
    "二级功能性缺陷",
    "二级结构性缺陷",
    "三级功能性缺陷",
    "三级结构性缺陷",
    "四级功能性缺陷",
    "四级结构性缺陷",
]
SEVERITY_COLORS = {
    1: "#ffd166",
    2: "#f4a261",
    3: "#ef6f4d",
    4: "#d62828",
}


def haversine_m(a, b):
    lon1, lat1 = map(math.radians, a)
    lon2, lat2 = map(math.radians, b)
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371008.8 * 2 * math.asin(math.sqrt(h))


def line_length(coords):
    return sum(haversine_m(coords[i - 1], coords[i]) for i in range(1, len(coords)))


def round_coord(parts):
    return [round(float(parts[0]), 8), round(float(parts[1]), 8)]


def parse_coordinates(text):
    coords = []
    for raw in (text or "").split():
        parts = raw.split(",")
        if len(parts) >= 2:
            coords.append(round_coord(parts))
    return coords


def update_bounds(bounds, coord):
    lon, lat = coord
    bounds[0] = min(bounds[0], lat)
    bounds[1] = min(bounds[1], lon)
    bounds[2] = max(bounds[2], lat)
    bounds[3] = max(bounds[3], lon)


def bounds_value(bounds, has_coord):
    return [[bounds[0], bounds[1]], [bounds[2], bounds[3]]] if has_coord else None


def folder_name(folder):
    return folder.findtext("k:name", default="", namespaces=NS).strip()


def document_folders(root):
    return root.findall(".//k:Document/k:Folder", NS)


def iter_named_folders(root, wanted):
    for folder in root.findall(".//k:Folder", NS):
        if folder_name(folder) in wanted:
            yield folder_name(folder), folder


def iter_folder_placemarks(folder):
    yield from folder.findall(".//k:Placemark", NS)


def iter_lines(placemark):
    for line in placemark.findall(".//k:LineString", NS):
        coords = parse_coordinates(line.findtext("k:coordinates", default="", namespaces=NS))
        if len(coords) >= 2:
            yield coords


def iter_points(placemark):
    for point in placemark.findall(".//k:Point", NS):
        coords = parse_coordinates(point.findtext("k:coordinates", default="", namespaces=NS))
        if coords:
            yield coords[0]


def write_js(path, var_name, value):
    path.write_text(f"window.{var_name}=" + json.dumps(value, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")


def layer_var_name(layer_id, suffix):
    return f"LAYER_{layer_id.upper().replace('-', '_')}_{suffix.upper()}"


def build_water():
    root = ET.parse(WATER_OVKML).getroot()
    jsl_folder = next((folder for name, folder in iter_named_folders(root, {"JSL"})), None)
    if jsl_folder is None:
        raise RuntimeError("供水 ovkml 中未找到 JSL 文件夹")

    line_features = []
    bounds = [999, 999, -999, -999]
    has_coord = False
    segment_id = 1

    for placemark in jsl_folder.findall("k:Placemark", NS):
        placemark_name = placemark.findtext("k:name", default="JSL", namespaces=NS).strip() or "JSL"
        for coords in iter_lines(placemark):
            for coord in coords:
                update_bounds(bounds, coord)
                has_coord = True
            length = round(line_length(coords), 1)
            line_features.append({
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": coords},
                "properties": {
                    "id": f"JSL-{segment_id:05d}",
                    "name": placemark_name,
                    "material": "JSL",
                    "diameter": None,
                    "length_m": length,
                    "points": len(coords),
                    "source_folder": "JSL",
                },
            })
            segment_id += 1

    pipes = {"type": "FeatureCollection", "features": line_features}
    nodes = {"type": "FeatureCollection", "features": []}
    total_length = sum(feature["properties"]["length_m"] for feature in line_features)
    summary = {
        "source": str(WATER_OVKML),
        "source_folder": "JSL",
        "coordinate_system": "OVKML 标注为 CGCS2000；按经纬度直接叠加。",
        "bounds": bounds_value(bounds, has_coord),
        "record_count": len(jsl_folder.findall("k:Placemark", NS)),
        "pipe_segment_count": len(line_features),
        "node_count": 0,
        "total_length_m": round(total_length, 1),
        "total_length_km": round(total_length / 1000, 2),
        "material_counts": {"JSL": len(line_features)},
        "diameter_counts": {"未识别": len(line_features)},
        "material_lengths_km": {"JSL": round(total_length / 1000, 2)},
        "research_context": {
            "area_km2": 6.8,
            "population_10k": 15.3,
            "risk_note": "迁建区存在地质、防护工程、房屋、供排水、消防等多因素叠加风险；地下管网渗漏是放大地质安全风险的重要因素之一。",
            "communities": ["朝云", "翠屏", "登龙", "飞凤", "集仙", "净坛", "起云", "上升", "神女", "圣泉", "松峦", "宁江", "聚鹤"],
        },
    }

    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "pipes.geojson").write_text(json.dumps(pipes, ensure_ascii=False), encoding="utf-8")
    (DATA / "nodes.geojson").write_text(json.dumps(nodes, ensure_ascii=False), encoding="utf-8")
    (DATA / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_js(DATA / "pipes.js", "PIPES", pipes)
    write_js(DATA / "nodes.js", "NODES", nodes)
    write_js(DATA / "summary.js", "SUMMARY", summary)
    return summary


def defect_severity(folder):
    match = re.search(r"([一二三四])级", folder)
    return {"一": 1, "二": 2, "三": 3, "四": 4}.get(match.group(1), 0) if match else 0


def defect_category(folder):
    if "功能性" in folder:
        return "功能性缺陷"
    if "结构性" in folder:
        return "结构性缺陷"
    return "缺陷"


def build_drainage():
    root = ET.parse(DRAINAGE_OVKML).getroot()
    line_features = []
    point_features = []
    line_bounds = [999, 999, -999, -999]
    point_bounds = [999, 999, -999, -999]
    has_line = False
    has_point = False
    line_id = 1
    point_id = 1
    line_folder_counts = Counter()
    defect_counts = Counter()

    for folder_label, folder in iter_named_folders(root, PIPE_LINE_FOLDERS):
        for placemark in iter_folder_placemarks(folder):
            placemark_name = placemark.findtext("k:name", default=folder_label, namespaces=NS).strip() or folder_label
            for coords in iter_lines(placemark):
                for coord in coords:
                    update_bounds(line_bounds, coord)
                    has_line = True
                line_features.append({
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": coords},
                    "properties": {
                        "id": f"drainage-ovkml-L{line_id:05d}",
                        "name": placemark_name,
                        "source": "巫山缺陷分布图.ovkml",
                        "kind": "drainage-pipe",
                        "source_folder": folder_label,
                        "length_m": round(line_length(coords), 1),
                        "points": len(coords),
                    },
                })
                line_folder_counts[folder_label] += 1
                line_id += 1

    for folder_label, folder in iter_named_folders(root, set(DEFECT_FOLDERS)):
        severity = defect_severity(folder_label)
        category = defect_category(folder_label)
        for placemark in folder.findall("k:Placemark", NS):
            placemark_name = placemark.findtext("k:name", default=folder_label, namespaces=NS).strip() or folder_label
            for coord in iter_points(placemark):
                update_bounds(point_bounds, coord)
                has_point = True
                point_features.append({
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": coord},
                    "properties": {
                        "id": f"drainage-ovkml-P{point_id:05d}",
                        "name": placemark_name,
                        "source": "巫山缺陷分布图.ovkml",
                        "kind": "drainage-defect-point",
                        "source_folder": folder_label,
                        "defect_category": category,
                        "severity": severity,
                        "severity_label": f"{severity}级",
                        "color": SEVERITY_COLORS[severity],
                    },
                })
                defect_counts[folder_label] += 1
                point_id += 1

    lines = {"type": "FeatureCollection", "features": line_features}
    points = {"type": "FeatureCollection", "features": point_features}
    empty_points = {"type": "FeatureCollection", "features": []}
    empty_lines = {"type": "FeatureCollection", "features": []}
    total_length = sum(feature["properties"]["length_m"] for feature in line_features)

    LAYERS.mkdir(parents=True, exist_ok=True)
    base_id = "drainage-defects-geojson"
    (LAYERS / f"{base_id}.lines.geojson").write_text(json.dumps(lines, ensure_ascii=False), encoding="utf-8")
    (LAYERS / f"{base_id}.points.geojson").write_text(json.dumps(points, ensure_ascii=False), encoding="utf-8")
    write_js(LAYERS / f"{base_id}.lines.js", layer_var_name(base_id, "lines"), lines)
    write_js(LAYERS / f"{base_id}.points.js", layer_var_name(base_id, "points"), points)

    catalog = json.loads((LAYERS / "catalog.json").read_text(encoding="utf-8")) if (LAYERS / "catalog.json").exists() else []
    catalog = [entry for entry in catalog if entry.get("id") not in {"drainage-defects-geojson-lines", "drainage-defects-geojson-points"}]
    drainage_entries = [
        {
            "id": "drainage-defects-geojson-lines",
            "title": "排水管线图",
            "file": DRAINAGE_OVKML.name,
            "kind": "drainage-defect-line",
            "category": "管网",
            "color": "#ff6b6b",
            "enabled": False,
            "description": "来自 OVKML 文件夹筛选，仅保留 YS_LINE、WS_LINE、QTPS_LINE 相关内容。",
            "fileSizeMb": round(DRAINAGE_OVKML.stat().st_size / 1024 / 1024, 2),
            "recordCount": sum(line_folder_counts.values()),
            "pointCount": 0,
            "lineCount": len(line_features),
            "lengthKm": round(total_length / 1000, 2),
            "bounds": bounds_value(line_bounds, has_line),
            "topNames": line_folder_counts.most_common(),
            "pointsDataId": base_id,
            "linesDataId": base_id,
            "hasPoints": False,
            "hasLines": True,
            "pointsUrl": f"data/layers/{base_id}.points.geojson",
            "linesUrl": f"data/layers/{base_id}.lines.geojson",
            "sourceFolders": sorted(PIPE_LINE_FOLDERS),
        },
        {
            "id": "drainage-defects-geojson-points",
            "title": "排水管线缺陷分布",
            "file": DRAINAGE_OVKML.name,
            "kind": "drainage-defect-point",
            "category": "管网",
            "color": "#ef6f4d",
            "enabled": False,
            "description": "来自 OVKML 1-4 级结构性/功能性缺陷文件夹；颜色随缺陷等级加深。",
            "fileSizeMb": round(DRAINAGE_OVKML.stat().st_size / 1024 / 1024, 2),
            "recordCount": sum(defect_counts.values()),
            "pointCount": len(point_features),
            "lineCount": 0,
            "lengthKm": 0,
            "bounds": bounds_value(point_bounds, has_point),
            "topNames": defect_counts.most_common(),
            "pointsDataId": base_id,
            "linesDataId": base_id,
            "hasPoints": True,
            "hasLines": False,
            "pointsUrl": f"data/layers/{base_id}.points.geojson",
            "linesUrl": f"data/layers/{base_id}.lines.geojson",
            "severityColors": {str(key): value for key, value in SEVERITY_COLORS.items()},
            "sourceFolders": DEFECT_FOLDERS,
        },
    ]
    insert_at = 0
    for entry in reversed(drainage_entries):
        catalog.insert(insert_at, entry)
    (LAYERS / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    write_js(LAYERS / "catalog.js", "LAYER_CATALOG", catalog)
    return drainage_entries


def main():
    summary = build_water()
    drainage_entries = build_drainage()
    print(json.dumps({
        "water": {
            "source": summary["source"],
            "folder": summary["source_folder"],
            "segments": summary["pipe_segment_count"],
            "lengthKm": summary["total_length_km"],
        },
        "drainage": [
            {
                "id": entry["id"],
                "lines": entry["lineCount"],
                "points": entry["pointCount"],
                "lengthKm": entry["lengthKm"],
                "folders": entry["topNames"],
            }
            for entry in drainage_entries
        ],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

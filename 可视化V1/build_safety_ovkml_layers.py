import json
import math
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OVKML_SRC = ROOT.parent / "原始数据" / "迁建区安全隐患分级.ovkml"
GEOJSON_SRC = ROOT.parent / "原始数据" / "迁建区安全隐患分级.geojson"
OUT = ROOT / "data" / "layers"
CATALOG = OUT / "catalog.json"

NS = {"k": "http://www.opengis.net/kml/2.2"}

# 房屋图层相对底图整体偏右下时，用这个小偏移做校正。
# lon 负值向左，lat 正值向上；单位是经纬度。
BUILDING_COORD_OFFSET = {"lon": 0, "lat": 0}

SAFETY_LAYERS = {
    "存在一定安全隐患的房子": {
        "id": "relocation-safety-moderate-houses",
        "title": "存在一定安全隐患的房子",
        "riskLevel": "一定安全隐患",
        "category": "房屋建筑",
        "color": "#d89b12",
        "description": "坐标来自迁建区安全隐患分级 geojson，分级沿用 ovkml 文件夹分类。",
    },
    "存在有严重安全隐患的房子": {
        "id": "relocation-safety-severe-houses",
        "title": "存在严重安全隐患的房子",
        "riskLevel": "严重安全隐患",
        "category": "房屋建筑",
        "color": "#eb5757",
        "description": "坐标来自迁建区安全隐患分级 geojson，分级沿用 ovkml 文件夹分类。",
    },
}


def round_coord(coord):
    return [
        round(float(coord[0]) + BUILDING_COORD_OFFSET["lon"], 8),
        round(float(coord[1]) + BUILDING_COORD_OFFSET["lat"], 8),
    ]


def update_bounds(bounds, coord):
    lon, lat = coord
    bounds[0] = min(bounds[0], lat)
    bounds[1] = min(bounds[1], lon)
    bounds[2] = max(bounds[2], lat)
    bounds[3] = max(bounds[3], lon)


def polygon_area_m2(ring):
    if len(ring) < 4:
        return 0
    mean_lat = math.radians(sum(point[1] for point in ring) / len(ring))
    meters_per_degree_lat = 111_320
    meters_per_degree_lon = 111_320 * math.cos(mean_lat)
    xy = [(point[0] * meters_per_degree_lon, point[1] * meters_per_degree_lat) for point in ring]
    area = 0
    for index, point in enumerate(xy):
        nxt = xy[(index + 1) % len(xy)]
        area += point[0] * nxt[1] - nxt[0] * point[1]
    return abs(area) / 2


def parse_coordinates(text):
    coords = []
    for raw in (text or "").split():
        parts = raw.split(",")
        if len(parts) >= 2:
            coords.append(round_coord(parts))
    if coords and coords[0] != coords[-1]:
        coords.append(coords[0])
    return coords


def find_named_folders(root):
    folders = {}
    for folder in root.findall(".//k:Folder", NS):
        name = folder.findtext("k:name", default="", namespaces=NS).strip()
        if name in SAFETY_LAYERS:
            folders[name] = folder
    return folders


def feature_name(feature):
    return str((feature.get("properties") or {}).get("name") or "").strip()


def iter_polygon_rings(geometry):
    gtype = geometry.get("type")
    coords = geometry.get("coordinates") or []
    if gtype == "Polygon":
        for ring in coords[:1]:
            yield [round_coord(coord) for coord in ring if len(coord) >= 2]
    elif gtype == "MultiPolygon":
        for polygon in coords:
            for ring in polygon[:1]:
                yield [round_coord(coord) for coord in ring if len(coord) >= 2]


def build_folder_lookup(folders):
    lookup = {}
    for folder_name, folder in folders.items():
        for placemark in folder.findall("k:Placemark", NS):
            name = placemark.findtext("k:name", default="", namespaces=NS).strip()
            if name:
                lookup[name] = folder_name
    return lookup


def build_features_from_geojson(folder_name, source_features, config):
    features = []
    bounds = [999, 999, -999, -999]
    name_counts = Counter()

    for index, feature in enumerate(source_features, start=1):
        name = feature_name(feature) or "未命名房屋"
        for ring in iter_polygon_rings(feature.get("geometry") or {}):
            if len(ring) < 4:
                continue
            if ring[0] != ring[-1]:
                ring.append(ring[0])
            for coord in ring:
                update_bounds(bounds, coord)
            name_counts[name] += 1
            features.append({
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [ring]},
                "properties": {
                    "id": f"{config['id']}-A{index:04d}",
                    "name": name,
                    "source": "迁建区安全隐患分级.geojson",
                    "kind": "building-safety-risk",
                    "folder": folder_name,
                    "risk_level": config["riskLevel"],
                    "area_m2": round(polygon_area_m2(ring), 1),
                    "points": len(ring),
                },
            })

    return {
        "collection": {"type": "FeatureCollection", "features": features},
        "bounds": [[bounds[0], bounds[1]], [bounds[2], bounds[3]]] if features else None,
        "topNames": name_counts.most_common(12),
    }


def write_js(path, var_name, value):
    path.write_text(f"window.{var_name}=" + json.dumps(value, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")


def layer_var_name(layer_id, suffix):
    return f"LAYER_{layer_id.upper().replace('-', '_')}_{suffix.upper()}"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    root = ET.parse(OVKML_SRC).getroot()
    folders = find_named_folders(root)
    if set(folders) != set(SAFETY_LAYERS):
        missing = sorted(set(SAFETY_LAYERS) - set(folders))
        raise RuntimeError(f"Missing ovkml folders: {missing}")
    folder_lookup = build_folder_lookup(folders)
    geojson = json.loads(GEOJSON_SRC.read_text(encoding="utf-8"))
    features_by_folder = {folder_name: [] for folder_name in SAFETY_LAYERS}
    unmatched = []
    for feature in geojson.get("features", []):
        name = feature_name(feature)
        folder_name = folder_lookup.get(name)
        if folder_name in features_by_folder:
            features_by_folder[folder_name].append(feature)
        else:
            unmatched.append(name)
    if unmatched:
        raise RuntimeError(f"GeoJSON features missing OVKML folder mapping: {unmatched[:10]}")

    catalog = json.loads(CATALOG.read_text(encoding="utf-8")) if CATALOG.exists() else []
    new_ids = {config["id"] for config in SAFETY_LAYERS.values()}
    catalog = [entry for entry in catalog if entry.get("id") not in new_ids]

    for folder_name, config in SAFETY_LAYERS.items():
        built = build_features_from_geojson(folder_name, features_by_folder[folder_name], config)
        layer_id = config["id"]
        empty_points = {"type": "FeatureCollection", "features": []}
        geojson_path = OUT / f"{layer_id}.lines.geojson"
        points_path = OUT / f"{layer_id}.points.geojson"
        geojson_path.write_text(json.dumps(built["collection"], ensure_ascii=False, indent=2), encoding="utf-8")
        points_path.write_text(json.dumps(empty_points, ensure_ascii=False), encoding="utf-8")
        write_js(OUT / f"{layer_id}.lines.js", layer_var_name(layer_id, "lines"), built["collection"])
        write_js(OUT / f"{layer_id}.points.js", layer_var_name(layer_id, "points"), empty_points)
        catalog.append({
            "id": layer_id,
            "title": config["title"],
            "file": GEOJSON_SRC.name,
            "kind": "building-safety-risk",
            "geometryType": "polygon",
            "category": config["category"],
            "color": config["color"],
            "enabled": False,
            "description": config["description"],
            "fileSizeMb": round(GEOJSON_SRC.stat().st_size / 1024 / 1024, 2),
            "recordCount": len(built["collection"]["features"]),
            "polygonCount": len(built["collection"]["features"]),
            "pointCount": 0,
            "lineCount": 0,
            "lengthKm": 0,
            "bounds": built["bounds"],
            "topNames": built["topNames"],
            "hasPoints": False,
            "hasLines": True,
            "pointsUrl": f"data/layers/{layer_id}.points.geojson",
            "linesUrl": f"data/layers/{layer_id}.lines.geojson",
            "featureUnit": "栋房屋",
        })

    CATALOG.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    write_js(OUT / "catalog.js", "LAYER_CATALOG", catalog)
    print(json.dumps([entry["id"] for entry in catalog], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

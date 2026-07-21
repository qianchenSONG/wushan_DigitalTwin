import json
import math
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT.parent / "原始数据" / "各社区消防安全风险分布.ovkml"
OUT = ROOT / "data" / "layers"
CATALOG = OUT / "catalog.json"
NS = {"k": "http://www.opengis.net/kml/2.2"}

LAYER_ID = "community-fire-risk"
HIGH_RISK = "#ff0000"
KML_MEDIUM_RISK = "#ffff00"
MEDIUM_RISK = "#d89b12"


def kml_color_to_hex(value):
    value = (value or "").strip()
    if len(value) != 8:
        return None
    # KML stores color as alpha-blue-green-red.
    blue = value[2:4]
    green = value[4:6]
    red = value[6:8]
    return f"#{red}{green}{blue}".lower()


def risk_level(color):
    if color == HIGH_RISK:
        return "高风险"
    if color in {KML_MEDIUM_RISK, MEDIUM_RISK}:
        return "中风险"
    return "风险边界"


def display_risk_color(color):
    if color == KML_MEDIUM_RISK:
        return MEDIUM_RISK
    return color


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


def haversine_m(a, b):
    lon1, lat1 = map(math.radians, a)
    lon2, lat2 = map(math.radians, b)
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371008.8 * 2 * math.asin(math.sqrt(h))


def line_length(coords):
    return sum(haversine_m(coords[i - 1], coords[i]) for i in range(1, len(coords)))


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


def folder_name(folder):
    return folder.findtext("k:name", default="", namespaces=NS).strip()


def placemark_name(placemark):
    return placemark.findtext("k:name", default="未命名对象", namespaces=NS).strip() or "未命名对象"


def style_color(placemark, style_name):
    return kml_color_to_hex(placemark.findtext(f".//k:{style_name}/k:color", default="", namespaces=NS))


def iter_community_folders(root):
    yield from root.findall(".//k:Document/k:Folder/k:Folder", NS)


def write_js(path, var_name, value):
    path.write_text(f"window.{var_name}=" + json.dumps(value, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")


def layer_var_name(layer_id, suffix):
    return f"LAYER_{layer_id.upper().replace('-', '_')}_{suffix.upper()}"


def build():
    root = ET.parse(SRC).getroot()
    features = []
    bounds = [999, 999, -999, -999]
    has_coord = False
    risk_counts = Counter()
    community_counts = Counter()
    skipped_points = 0
    skipped_lines = 0
    feature_id = 1

    for folder in iter_community_folders(root):
        community = folder_name(folder)
        for placemark in folder.findall("k:Placemark", NS):
            name = placemark_name(placemark)
            point_count = len(placemark.findall(".//k:Point", NS))
            skipped_points += point_count
            skipped_lines += len(placemark.findall(".//k:LineString", NS))

            for polygon in placemark.findall(".//k:Polygon", NS):
                ring = parse_coordinates(polygon.findtext(".//k:outerBoundaryIs/k:LinearRing/k:coordinates", default="", namespaces=NS))
                if len(ring) < 4:
                    continue
                if ring[0] != ring[-1]:
                    ring.append(ring[0])
                for coord in ring:
                    update_bounds(bounds, coord)
                    has_coord = True
                color = display_risk_color(style_color(placemark, "PolyStyle") or MEDIUM_RISK)
                risk = risk_level(color)
                risk_counts[risk] += 1
                community_counts[community] += 1
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "Polygon", "coordinates": [ring]},
                    "properties": {
                        "id": f"{LAYER_ID}-A{feature_id:04d}",
                        "name": name,
                        "source": SRC.name,
                        "kind": "fire-risk-area",
                        "community": community,
                        "risk_level": risk,
                        "color": color,
                        "area_m2": round(polygon_area_m2(ring), 1),
                    },
                })
                feature_id += 1

    return {
        "collection": {"type": "FeatureCollection", "features": features},
        "catalog": {
            "id": LAYER_ID,
            "title": "各社区消防安全风险分布",
            "file": SRC.name,
            "kind": "fire-risk",
            "category": "消防",
            "geometryType": "mixed",
            "patternFill": "diagonal",
            "color": HIGH_RISK,
            "enabled": False,
            "description": "保留风险块，已排除图钉标记和含义不确定的线；块颜色表示风险等级。",
            "fileSizeMb": round(SRC.stat().st_size / 1024 / 1024, 2),
            "recordCount": len(features),
            "pointCount": 0,
            "lineCount": 0,
            "polygonCount": sum(1 for feature in features if feature["geometry"]["type"] == "Polygon"),
            "lengthKm": 0,
            "bounds": bounds_value(bounds, has_coord),
            "topNames": community_counts.most_common(),
            "hasPoints": False,
            "hasLines": True,
            "pointsUrl": f"data/layers/{LAYER_ID}.points.geojson",
            "linesUrl": f"data/layers/{LAYER_ID}.lines.geojson",
            "riskColors": {
                "高风险": HIGH_RISK,
                "中风险": MEDIUM_RISK,
            },
            "filteredOut": {"图钉": skipped_points, "线": skipped_lines},
        },
        "riskCounts": dict(risk_counts),
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    built = build()
    empty_points = {"type": "FeatureCollection", "features": []}
    (OUT / f"{LAYER_ID}.lines.geojson").write_text(json.dumps(built["collection"], ensure_ascii=False), encoding="utf-8")
    (OUT / f"{LAYER_ID}.points.geojson").write_text(json.dumps(empty_points, ensure_ascii=False), encoding="utf-8")
    write_js(OUT / f"{LAYER_ID}.lines.js", layer_var_name(LAYER_ID, "lines"), built["collection"])
    write_js(OUT / f"{LAYER_ID}.points.js", layer_var_name(LAYER_ID, "points"), empty_points)

    catalog = json.loads(CATALOG.read_text(encoding="utf-8")) if CATALOG.exists() else []
    catalog = [entry for entry in catalog if entry.get("id") != LAYER_ID]
    catalog.append(built["catalog"])
    CATALOG.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    write_js(OUT / "catalog.js", "LAYER_CATALOG", catalog)
    print(json.dumps({
        "id": LAYER_ID,
        "features": built["catalog"]["recordCount"],
        "polygons": built["catalog"]["polygonCount"],
        "lines": built["catalog"]["lineCount"],
        "filteredOut": built["catalog"]["filteredOut"],
        "riskCounts": built["riskCounts"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT.parent / "原始数据" / "供水管线图（2025年测）.geojson"
CSV_SRC = ROOT.parent / "原始数据" / "供水管线图（2025年测）.csv"
OUT = ROOT / "data"


def haversine_m(a, b):
    lon1, lat1 = map(math.radians, a)
    lon2, lat2 = map(math.radians, b)
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371008.8 * 2 * math.asin(math.sqrt(h))


def line_length(coords):
    return sum(haversine_m(coords[i - 1], coords[i]) for i in range(1, len(coords)))


def parse_pipe_name(name):
    material = "未识别"
    diameter = None
    m = re.search(r"JS\s*(.*?)\s*DN\s*(\d+)", name or "", flags=re.I)
    if m:
        material = m.group(1).strip() or "未识别"
        diameter = int(m.group(2))
    return material, diameter


def round_coord(coord):
    return [round(float(coord[0]), 8), round(float(coord[1]), 8)]


def normalize_lines(feature):
    geom = feature.get("geometry") or {}
    coords = geom.get("coordinates") or []
    if geom.get("type") == "LineString":
        return [coords]
    if geom.get("type") == "MultiLineString":
        return coords
    return []


def normalize_points(feature):
    geom = feature.get("geometry") or {}
    if geom.get("type") == "Point":
        return geom.get("coordinates")
    return None


def load_geojson():
    return json.loads(SRC.read_text(encoding="utf-8"))


def build():
    source = load_geojson()
    line_features = []
    point_features = []
    bounds = [999, 999, -999, -999]
    material_counter = Counter()
    diameter_counter = Counter()
    material_lengths = defaultdict(float)
    feature_id = 1
    point_id = 1

    def touch(coord):
        lon, lat = coord
        bounds[0] = min(bounds[0], lat)
        bounds[1] = min(bounds[1], lon)
        bounds[2] = max(bounds[2], lat)
        bounds[3] = max(bounds[3], lon)

    for feature in source.get("features", []):
        name = str((feature.get("properties") or {}).get("name") or "")
        for raw_line in normalize_lines(feature):
            coords = [round_coord(c) for c in raw_line if len(c) >= 2]
            if len(coords) < 2:
                continue
            for coord in coords:
                touch(coord)
            material, diameter = parse_pipe_name(name)
            length = round(line_length(coords), 1)
            if material != "未识别":
                material_counter[material] += 1
                material_lengths[material] += length
            else:
                material_counter["未识别"] += 1
                material_lengths["未识别"] += length
            diameter_counter[str(diameter) if diameter else "未识别"] += 1
            line_features.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": coords},
                    "properties": {
                        "id": f"G{feature_id:05d}",
                        "name": name,
                        "material": material,
                        "diameter": diameter,
                        "length_m": length,
                        "points": len(coords),
                    },
                }
            )
            feature_id += 1

        point = normalize_points(feature)
        if point:
            coord = round_coord(point)
            touch(coord)
            point_features.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": coord},
                    "properties": {
                        "id": f"GN{point_id:05d}",
                        "name": name,
                        "kind": "供水管点/节点",
                    },
                }
            )
            point_id += 1

    pipes = {"type": "FeatureCollection", "features": line_features}
    nodes = {"type": "FeatureCollection", "features": point_features}
    total_length = sum(f["properties"]["length_m"] for f in line_features)
    summary = {
        "source": str(SRC),
        "coordinate_system": "GeoJSON声明为EPSG:4490；按经纬度直接叠加，和WGS84底图在本项目精度范围内匹配。",
        "bounds": [[bounds[0], bounds[1]], [bounds[2], bounds[3]]],
        "record_count": len(source.get("features", [])),
        "pipe_segment_count": len(line_features),
        "node_count": len(point_features),
        "total_length_m": round(total_length, 1),
        "total_length_km": round(total_length / 1000, 2),
        "material_counts": dict(material_counter.most_common()),
        "diameter_counts": dict(sorted(diameter_counter.items(), key=lambda kv: (kv[0] == "未识别", int(kv[0]) if kv[0].isdigit() else 9999))),
        "material_lengths_km": {k: round(v / 1000, 2) for k, v in sorted(material_lengths.items())},
        "research_context": {
            "area_km2": 6.8,
            "population_10k": 15.3,
            "risk_note": "迁建区存在地质、防护工程、房屋、供排水、消防等多因素叠加风险；地下管网渗漏是放大地质安全风险的重要因素之一。",
            "communities": ["朝云", "翠屏", "登龙", "飞凤", "集仙", "净坛", "起云", "上升", "神女", "圣泉", "松峦", "宁江", "聚鹤"],
        },
    }
    return pipes, nodes, summary


def write_js(path, var_name, value):
    path.write_text(f"window.{var_name}=" + json.dumps(value, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    pipes, nodes, summary = build()
    (OUT / "pipes.geojson").write_text(json.dumps(pipes, ensure_ascii=False), encoding="utf-8")
    (OUT / "nodes.geojson").write_text(json.dumps(nodes, ensure_ascii=False), encoding="utf-8")
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_js(OUT / "pipes.js", "PIPES", pipes)
    write_js(OUT / "nodes.js", "NODES", nodes)
    write_js(OUT / "summary.js", "SUMMARY", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

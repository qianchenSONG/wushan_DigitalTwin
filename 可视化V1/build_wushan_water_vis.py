import csv
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT.parent / "原始数据" / "供水管线图（2025年测）.csv"
BOUNDARY = ROOT / "wushan-boundary.raw.json"
OUT_DATA = ROOT / "data"


def clean_text(value):
    return (value or "").strip()


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
    m = re.search(r"JS\s*(.*?)\s*DN\s*(\d+)", name, flags=re.I)
    if m:
        material = m.group(1).strip() or "未识别"
        diameter = int(m.group(2))
    return material, diameter


def read_rows():
    with SRC.open("r", encoding="gbk", newline="") as f:
        reader = csv.DictReader(f)
        rows = []
        for idx, row in enumerate(reader):
            try:
                lon = float(row["经度"])
                lat = float(row["纬度"])
            except (KeyError, TypeError, ValueError):
                continue
            if not (70 <= lon <= 140 and 10 <= lat <= 60):
                continue
            row["_idx"] = idx
            row["_coord"] = [round(lon, 8), round(lat, 8)]
            row["_name"] = clean_text(row.get("名称"))
            rows.append(row)
        return rows


def build_features(rows):
    line_features = []
    node_features = []
    current = []
    current_name = None
    segment_id = 1

    def flush():
        nonlocal segment_id, current, current_name
        if len(current) >= 2:
            material, diameter = parse_pipe_name(current_name)
            coords = [r["_coord"] for r in current]
            length = line_length(coords)
            feature = {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": coords},
                "properties": {
                    "id": f"P{segment_id:04d}",
                    "name": current_name,
                    "material": material,
                    "diameter": diameter,
                    "length_m": round(length, 1),
                    "points": len(coords),
                },
            }
            line_features.append(feature)
            segment_id += 1
        elif len(current) == 1:
            r = current[0]
            node_features.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": r["_coord"]},
                    "properties": {
                        "id": clean_text(r.get("对象ID")) or f"N{r['_idx']}",
                        "name": current_name,
                        "kind": "单点管线记录",
                    },
                }
            )
        current = []
        current_name = None

    for row in rows:
        name = row["_name"]
        if re.search(r"\bDN\s*\d+", name, flags=re.I):
            if current_name == name or not current:
                current.append(row)
                current_name = name
            else:
                flush()
                current.append(row)
                current_name = name
        else:
            flush()
            node_features.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": row["_coord"]},
                    "properties": {
                        "id": clean_text(row.get("对象ID")) or f"N{row['_idx']}",
                        "name": name,
                        "kind": "管点/节点",
                    },
                }
            )
    flush()
    return line_features, node_features


def summarize(rows, line_features, node_features):
    lons = [r["_coord"][0] for r in rows]
    lats = [r["_coord"][1] for r in rows]
    by_material = Counter()
    by_diameter = Counter()
    length_by_material = defaultdict(float)
    for feature in line_features:
        p = feature["properties"]
        mat = p["material"]
        dia = p["diameter"] or "未识别"
        length = p["length_m"]
        by_material[mat] += 1
        by_diameter[str(dia)] += 1
        length_by_material[mat] += length

    total_length = sum(f["properties"]["length_m"] for f in line_features)
    return {
        "source": str(SRC),
        "coordinate_system": "CSV经纬度字段按WGS84经纬度直叠处理；页面默认使用WGS84底图，避免国内GCJ偏移底图造成错位。",
        "bounds": [[min(lats), min(lons)], [max(lats), max(lons)]],
        "record_count": len(rows),
        "pipe_segment_count": len(line_features),
        "node_count": len(node_features),
        "total_length_m": round(total_length, 1),
        "total_length_km": round(total_length / 1000, 2),
        "material_counts": dict(by_material.most_common()),
        "diameter_counts": dict(sorted(by_diameter.items(), key=lambda kv: (kv[0] == "未识别", int(kv[0]) if kv[0].isdigit() else 9999))),
        "material_lengths_km": {k: round(v / 1000, 2) for k, v in sorted(length_by_material.items())},
        "research_context": {
            "area_km2": 6.8,
            "population_10k": 15.3,
            "risk_note": "迁建区存在地质、防护工程、房屋、供排水、消防等多因素叠加风险；地下管网渗漏是放大地质安全风险的重要因素之一。",
            "communities": ["朝云", "翠屏", "登龙", "飞凤", "集仙", "净坛", "起云", "上升", "神女", "圣泉", "松峦", "宁江", "聚鹤"],
        },
    }


def write_js(name, value):
    path = OUT_DATA / name
    path.write_text("window." + name.removesuffix(".js").upper().replace("-", "_") + "=" + json.dumps(value, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")


def main():
    OUT_DATA.mkdir(parents=True, exist_ok=True)
    rows = read_rows()
    line_features, node_features = build_features(rows)
    pipe_geojson = {"type": "FeatureCollection", "features": line_features}
    node_geojson = {"type": "FeatureCollection", "features": node_features}
    summary = summarize(rows, line_features, node_features)

    boundary = json.loads(BOUNDARY.read_text(encoding="utf-8")) if BOUNDARY.exists() else None
    (OUT_DATA / "pipes.geojson").write_text(json.dumps(pipe_geojson, ensure_ascii=False), encoding="utf-8")
    (OUT_DATA / "nodes.geojson").write_text(json.dumps(node_geojson, ensure_ascii=False), encoding="utf-8")
    (OUT_DATA / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    if boundary:
        (OUT_DATA / "wushan-boundary.geojson").write_text(json.dumps(boundary, ensure_ascii=False), encoding="utf-8")

    write_js("pipes.js", pipe_geojson)
    write_js("nodes.js", node_geojson)
    write_js("summary.js", summary)
    if boundary:
        write_js("boundary.js", boundary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

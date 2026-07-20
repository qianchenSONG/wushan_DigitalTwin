import json
import math
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT.parent / "原始数据"
OUT = ROOT / "data" / "layers"


LAYER_SOURCES = [
    {
        "id": "drainage-defects-geojson",
        "title": "排水管线图",
        "file": "巫山缺陷分布图.geojson",
        "kind": "drainage-defect",
        "color": "#ff6b6b",
        "enabled": False,
        "description": "奥维导出的标准 GeoJSON，包含排水管线、缺陷点和标注对象。",
        "excludeLineNamePattern": r"^[一二三四五六七八九十]+级(?:结构性|功能性)缺陷.*",
    },
]


FLOOD_MATERIAL_PREFIXES = (
    "砖混",
    "塑料",
    "铸铁",
    "砖",
    "砼",
    "混凝土",
    "钢筋混凝土",
    "PVC",
    "PE",
    "HDPE",
    "球墨铸铁",
    "钢管",
    "镀锌",
    "陶土",
)

FLOOD_PLACE_NAMES = {
    "渝发汽修",
    "秀峰中学西北门",
    "龙门",
    "FM广场",
    "平湖桥",
    "龙潭名都",
    "增辉再生资源回收有限公司",
    "鸿运楼",
    "汉庭酒店",
    "山水江岸1号楼",
    "山水江岸2号楼",
    "古城码头右侧",
    "丽景尚城",
    "三江六景外侧江边",
    "三江六景2号楼",
    "登龙街出露点",
    "胡家包公交站",
    "巫山县交通局",
    "巫山县烟草公司",
    "巫山九码头",
    "圣泉小区4栋",
    "江临天下",
    "旅游局",
    "西坪货运码头",
    "希尔顿酒店",
    "神女汽修厂",
    "巫山县村镇规划建筑勘察设计室",
    "巫山县市政广场",
    "巫山县审计局",
    "望霞公园东门",
    "巫峡市场",
    "卫建委",
    "消防队",
    "磷肥厂宿舍",
    "西坪水厂",
    "西坪货运码头",
    "巫山巫水处理厂",
    "神女广场",
    "神女市场",
    "南峰小学",
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


def round_coord(coord):
    return [round(float(coord[0]), 8), round(float(coord[1]), 8)]


def update_bounds(bounds, coord):
    lon, lat = coord
    bounds[0] = min(bounds[0], lat)
    bounds[1] = min(bounds[1], lon)
    bounds[2] = max(bounds[2], lat)
    bounds[3] = max(bounds[3], lon)


def iter_lines(geometry):
    gtype = geometry.get("type")
    coords = geometry.get("coordinates") or []
    if gtype == "LineString":
        yield coords
    elif gtype == "MultiLineString":
        yield from coords


def iter_points(geometry):
    gtype = geometry.get("type")
    coords = geometry.get("coordinates") or []
    if gtype == "Point":
        yield coords
    elif gtype == "MultiPoint":
        yield from coords


def should_skip_line(source, name):
    pattern = source.get("excludeLineNamePattern")
    return bool(pattern and re.match(pattern, name or ""))


def should_skip_point(source, name):
    if source["id"] != "flood-drainage-geojson":
        return False
    clean_name = (name or "").strip()
    return (
        clean_name.startswith(("底高", "顶高"))
        or clean_name.startswith(FLOOD_MATERIAL_PREFIXES)
        or clean_name in FLOOD_PLACE_NAMES
    )


def feature_name(feature):
    return str((feature.get("properties") or {}).get("name") or "")


def feature_bounds(features):
    bounds = [999, 999, -999, -999]
    has_coord = False
    for feature in features:
        geometry = feature.get("geometry") or {}
        gtype = geometry.get("type")
        coords = geometry.get("coordinates") or []
        if gtype == "Point":
            update_bounds(bounds, coords)
            has_coord = True
        elif gtype == "LineString":
            for coord in coords:
                update_bounds(bounds, coord)
                has_coord = True
    return [[bounds[0], bounds[1]], [bounds[2], bounds[3]]] if has_coord else None


def build_layer(source):
    geo = json.loads((SRC / source["file"]).read_text(encoding="utf-8"))
    line_features = []
    point_features = []
    name_counts = Counter()
    bounds = [999, 999, -999, -999]
    line_id = 1
    point_id = 1

    for feature in geo.get("features", []):
      props = feature.get("properties") or {}
      name = str(props.get("name") or "")
      name_counts[name] += 1
      geometry = feature.get("geometry") or {}
      for raw_line in iter_lines(geometry):
          if should_skip_line(source, name):
              continue
          coords = [round_coord(coord) for coord in raw_line if len(coord) >= 2]
          if len(coords) < 2:
              continue
          for coord in coords:
              update_bounds(bounds, coord)
          line_features.append({
              "type": "Feature",
              "geometry": {"type": "LineString", "coordinates": coords},
              "properties": {
                  "id": f"{source['id']}-L{line_id:05d}",
                  "name": name,
                  "source": source["title"],
                  "kind": source["kind"],
                  "length_m": round(line_length(coords), 1),
                  "points": len(coords),
              },
          })
          line_id += 1
      for raw_point in iter_points(geometry):
          if should_skip_point(source, name):
              continue
          coord = round_coord(raw_point)
          update_bounds(bounds, coord)
          point_features.append({
              "type": "Feature",
              "geometry": {"type": "Point", "coordinates": coord},
              "properties": {
                  "id": f"{source['id']}-P{point_id:05d}",
                  "name": name,
                  "source": source["title"],
                  "kind": source["kind"],
              },
          })
          point_id += 1

    total_length = sum(feature["properties"]["length_m"] for feature in line_features)
    return {
        "points": {"type": "FeatureCollection", "features": point_features},
        "lines": {"type": "FeatureCollection", "features": line_features},
        "catalog": {
            **source,
            "fileSizeMb": round((SRC / source["file"]).stat().st_size / 1024 / 1024, 2),
            "recordCount": len(geo.get("features", [])),
            "pointCount": len(point_features),
            "lineCount": len(line_features),
            "lengthKm": round(total_length / 1000, 2),
            "bounds": [[bounds[0], bounds[1]], [bounds[2], bounds[3]]] if line_features or point_features else None,
            "topNames": [
                item
                for item in name_counts.most_common()
                if not should_skip_line(source, item[0]) and not should_skip_point(source, item[0])
            ][:12],
            "pointsUrl": f"data/layers/{source['id']}.points.geojson",
            "linesUrl": f"data/layers/{source['id']}.lines.geojson",
        },
    }


def write_js(path, var_name, value):
    path.write_text(f"window.{var_name}=" + json.dumps(value, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")


def catalog_entries_for(source, catalog_entry):
    if source["id"] != "drainage-defects-geojson":
        return [catalog_entry]
    base = {
        key: value
        for key, value in catalog_entry.items()
        if key not in {"id", "title", "enabled", "pointCount", "lineCount", "lengthKm", "description"}
    }
    return [
        {
            **base,
            "id": "drainage-defects-geojson-lines",
            "title": "排水管线图",
            "kind": "drainage-defect-line",
            "color": "#ff6b6b",
            "enabled": False,
            "description": "排水管线线对象，已隐藏一级/二级/三级/四级结构性与功能性缺陷线。",
            "pointsDataId": source["id"],
            "linesDataId": source["id"],
            "hasPoints": False,
            "hasLines": True,
            "pointCount": 0,
            "lineCount": catalog_entry["lineCount"],
            "lengthKm": catalog_entry["lengthKm"],
        },
        {
            **base,
            "id": "drainage-defects-geojson-points",
            "title": "排水管线缺陷分布",
            "kind": "drainage-defect-point",
            "color": "#ff9f43",
            "enabled": False,
            "description": "排水管线缺陷点对象，和排水管线图拆分为独立开关。",
            "pointsDataId": source["id"],
            "linesDataId": source["id"],
            "hasPoints": True,
            "hasLines": False,
            "pointCount": catalog_entry["pointCount"],
            "lineCount": 0,
            "lengthKm": 0,
        },
    ]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    catalog = []
    for source in LAYER_SOURCES:
        built = build_layer(source)
        catalog.extend(catalog_entries_for(source, built["catalog"]))
        (OUT / f"{source['id']}.points.geojson").write_text(json.dumps(built["points"], ensure_ascii=False), encoding="utf-8")
        (OUT / f"{source['id']}.lines.geojson").write_text(json.dumps(built["lines"], ensure_ascii=False), encoding="utf-8")
        write_js(OUT / f"{source['id']}.points.js", f"LAYER_{source['id'].upper().replace('-', '_')}_POINTS", built["points"])
        write_js(OUT / f"{source['id']}.lines.js", f"LAYER_{source['id'].upper().replace('-', '_')}_LINES", built["lines"])
    (OUT / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    write_js(OUT / "catalog.js", "LAYER_CATALOG", catalog)
    print(json.dumps(catalog, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

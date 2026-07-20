import json
import math
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT.parent / "原始数据"
OUT = ROOT / "data" / "layers"


LAYER_SOURCES = [
    {
        "id": "flood-drainage-geojson",
        "title": "防洪排涝通道",
        "file": "防洪排涝通道.geojson",
        "kind": "flood-drainage",
        "color": "#48e17f",
        "enabled": True,
        "description": "奥维导出的标准 GeoJSON，包含线状通道和点状标注。",
    },
    {
        "id": "drainage-defects-geojson",
        "title": "巫山排水缺陷分布",
        "file": "巫山缺陷分布图.geojson",
        "kind": "drainage-defect",
        "color": "#ff6b6b",
        "enabled": True,
        "description": "奥维导出的标准 GeoJSON，包含排水管线、缺陷点和标注对象。",
    },
]


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
            "topNames": name_counts.most_common(12),
            "pointsUrl": f"data/layers/{source['id']}.points.geojson",
            "linesUrl": f"data/layers/{source['id']}.lines.geojson",
        },
    }


def write_js(path, var_name, value):
    path.write_text(f"window.{var_name}=" + json.dumps(value, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    catalog = []
    for source in LAYER_SOURCES:
        built = build_layer(source)
        catalog.append(built["catalog"])
        (OUT / f"{source['id']}.points.geojson").write_text(json.dumps(built["points"], ensure_ascii=False), encoding="utf-8")
        (OUT / f"{source['id']}.lines.geojson").write_text(json.dumps(built["lines"], ensure_ascii=False), encoding="utf-8")
        write_js(OUT / f"{source['id']}.points.js", f"LAYER_{source['id'].upper().replace('-', '_')}_POINTS", built["points"])
        write_js(OUT / f"{source['id']}.lines.js", f"LAYER_{source['id'].upper().replace('-', '_')}_LINES", built["lines"])
    (OUT / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    write_js(OUT / "catalog.js", "LAYER_CATALOG", catalog)
    print(json.dumps(catalog, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

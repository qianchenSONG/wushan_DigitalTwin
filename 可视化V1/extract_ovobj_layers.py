import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from struct import unpack_from


ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT.parent / "原始数据"
OUT = ROOT / "data" / "layers"
MARKER = b"\x00\x00\x00\x01\x03\x00\x00"


SOURCES = [
    {
        "id": "water-ovobj",
        "title": "供水管线图（OVOBJ校验）",
        "file": "供水管线图（2025年测）.ovobj",
        "kind": "water",
        "color": "#51d6ff",
        "enabled": False,
    },
    {
        "id": "community-composite",
        "title": "巫山县+小区综合图",
        "file": "巫山县+小区综合图07.ovobj",
        "kind": "community",
        "color": "#f2b84b",
        "enabled": False,
    },
    {
        "id": "drainage-defects",
        "title": "市政排水缺陷分布",
        "file": "巫山市政排水缺陷分布图.ovobj",
        "kind": "drainage-defect",
        "color": "#ff6b6b",
        "enabled": True,
    },
    {
        "id": "flood-drainage",
        "title": "防洪排涝通道",
        "file": "防洪排涝通道.ovobj",
        "kind": "flood-drainage",
        "color": "#5ad07d",
        "enabled": True,
    },
]


def read_name(data, start, size):
    if size <= 0 or size > 180 or start + size > len(data):
        return None
    raw = data[start : start + size]
    if b"\x00" in raw:
        raw = raw.split(b"\x00", 1)[0]
    try:
        text = raw.decode("utf-8").strip()
    except UnicodeDecodeError:
        return None
    if not text:
        return None
    if any(ord(ch) < 32 for ch in text):
        return None
    return text


def extract_records(path):
    data = path.read_bytes()
    records = []
    cursor = 0
    while True:
        marker = data.find(MARKER, cursor)
        if marker < 24:
            break
        lat = unpack_from("<d", data, marker - 24)[0]
        lon = unpack_from("<d", data, marker - 16)[0]
        size = data[marker + 7]
        name = read_name(data, marker + 8, size)
        if name and 30.0 <= lat <= 32.0 and 109.0 <= lon <= 111.0:
            records.append(
                {
                    "name": name,
                    "lat": round(lat, 8),
                    "lon": round(lon, 8),
                    "offset": marker,
                }
            )
        cursor = marker + 8
    return records


def haversine_m(a, b):
    lon1, lat1 = map(math.radians, a)
    lon2, lat2 = map(math.radians, b)
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371008.8 * 2 * math.asin(math.sqrt(h))


def line_length(coords):
    return sum(haversine_m(coords[i - 1], coords[i]) for i in range(1, len(coords)))


def should_line(name, kind):
    pipe_pattern = bool(
        re.search(r"\bDN\s*\d+", name, flags=re.I)
        or re.search(r"[Φφ]\s*\d+", name)
        or re.search(r"(雨水|污水|输水|给水).*(PVC|PE|砼|钢|铸铁|塑料|砖石)", name)
        or re.search(r"(PVC|PE|砼|钢|铸铁|塑料|砖石).*(雨水|污水|输水|给水)", name)
    )
    if kind in {"water", "flood-drainage"}:
        return pipe_pattern or any(x in name for x in ["通道", "箱涵", "管", "沟", "渠"])
    if kind in {"drainage-defect", "community"}:
        return pipe_pattern
    return False


def build_geojson(records, source):
    kind = source["kind"]
    points = []
    lines = []
    current = []
    current_name = None
    line_id = 1

    def flush():
        nonlocal current, current_name, line_id
        if len(current) >= 2:
            coords = [[r["lon"], r["lat"]] for r in current]
            lines.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": coords},
                    "properties": {
                        "id": f"{source['id']}-L{line_id:04d}",
                        "name": current_name,
                        "source": source["title"],
                        "kind": kind,
                        "length_m": round(line_length(coords), 1),
                        "points": len(coords),
                    },
                }
            )
            line_id += 1
        elif len(current) == 1:
            add_point(current[0], "单点记录")
        current = []
        current_name = None

    def add_point(row, point_kind=None):
        points.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [row["lon"], row["lat"]]},
                "properties": {
                    "id": f"{source['id']}-P{len(points) + 1:05d}",
                    "name": row["name"],
                    "source": source["title"],
                    "kind": point_kind or kind,
                },
            }
        )

    for row in records:
        if should_line(row["name"], kind):
            if current_name == row["name"] or not current:
                current.append(row)
                current_name = row["name"]
            else:
                flush()
                current.append(row)
                current_name = row["name"]
        else:
            flush()
            add_point(row)
    flush()

    return {
        "points": {"type": "FeatureCollection", "features": points},
        "lines": {"type": "FeatureCollection", "features": lines},
    }


def bounds_for(records):
    if not records:
        return None
    return [
        [min(r["lat"] for r in records), min(r["lon"] for r in records)],
        [max(r["lat"] for r in records), max(r["lon"] for r in records)],
    ]


def write_js(path, var_name, value):
    path.write_text(f"window.{var_name}=" + json.dumps(value, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    catalog = []
    for source in SOURCES:
        path = SRC_DIR / source["file"]
        records = extract_records(path)
        geo = build_geojson(records, source)
        point_count = len(geo["points"]["features"])
        line_count = len(geo["lines"]["features"])
        length_m = sum(f["properties"]["length_m"] for f in geo["lines"]["features"])
        top_names = Counter(r["name"] for r in records).most_common(12)
        entry = {
            **source,
            "fileSizeMb": round(path.stat().st_size / 1024 / 1024, 2),
            "recordCount": len(records),
            "pointCount": point_count,
            "lineCount": line_count,
            "lengthKm": round(length_m / 1000, 2),
            "bounds": bounds_for(records),
            "topNames": top_names,
            "pointsUrl": f"data/layers/{source['id']}.points.geojson",
            "linesUrl": f"data/layers/{source['id']}.lines.geojson",
        }
        catalog.append(entry)
        (OUT / f"{source['id']}.points.geojson").write_text(json.dumps(geo["points"], ensure_ascii=False), encoding="utf-8")
        (OUT / f"{source['id']}.lines.geojson").write_text(json.dumps(geo["lines"], ensure_ascii=False), encoding="utf-8")
        write_js(OUT / f"{source['id']}.points.js", f"LAYER_{source['id'].upper().replace('-', '_')}_POINTS", geo["points"])
        write_js(OUT / f"{source['id']}.lines.js", f"LAYER_{source['id'].upper().replace('-', '_')}_LINES", geo["lines"])
    (OUT / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    write_js(OUT / "catalog.js", "LAYER_CATALOG", catalog)
    print(json.dumps(catalog, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

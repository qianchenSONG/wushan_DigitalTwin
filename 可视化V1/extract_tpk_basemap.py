import json
import re
import shutil
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEFAULT_SRC = ROOT.parent / "原始数据" / "ditu.tpk"
DEFAULT_OUT = ROOT / "data" / "basemaps" / "ditu"

BUNDLE_RE = re.compile(r"/L(?P<level>\d{2})/R(?P<row>[0-9a-fA-F]+)C(?P<col>[0-9a-fA-F]+)\.bundle$")
PACKET_SIZE = 128
INDEX_HEADER_SIZE = 16
INDEX_RECORD_SIZE = 5


def parse_extent(zip_file):
    info_xml = ET.fromstring(zip_file.read("esriinfo/iteminfo.xml"))
    extent = info_xml.find("extent")
    if extent is None:
        return None
    return {
        "west": float(extent.findtext("xmin")),
        "south": float(extent.findtext("ymin")),
        "east": float(extent.findtext("xmax")),
        "north": float(extent.findtext("ymax")),
    }


def parse_level(name):
    match = BUNDLE_RE.search(name)
    if not match:
        return None
    return {
        "level": int(match.group("level")),
        "row_base": int(match.group("row"), 16),
        "col_base": int(match.group("col"), 16),
    }


def tile_extension(tile):
    if tile.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if tile.startswith(b"\xff\xd8\xff"):
        return "jpg"
    return "bin"


def extract_bundle(zip_file, bundle_name, out_dir):
    parsed = parse_level(bundle_name)
    if not parsed:
        return []
    bundlx_name = bundle_name[:-6] + "bundlx"
    bundle = zip_file.read(bundle_name)
    bundlx = zip_file.read(bundlx_name)
    extracted = []

    for index in range(PACKET_SIZE * PACKET_SIZE):
        offset_start = INDEX_HEADER_SIZE + index * INDEX_RECORD_SIZE
        offset = int.from_bytes(bundlx[offset_start:offset_start + INDEX_RECORD_SIZE], "little")
        if not offset or offset + 4 > len(bundle):
            continue
        size = int.from_bytes(bundle[offset:offset + 4], "little")
        if not size or offset + 4 + size > len(bundle):
            continue
        row = parsed["row_base"] + index % PACKET_SIZE
        col = parsed["col_base"] + index // PACKET_SIZE
        tile = bundle[offset + 4:offset + 4 + size]
        extension = tile_extension(tile)
        if extension == "bin":
            continue
        tile_path = out_dir / str(parsed["level"]) / str(col) / f"{row}.{extension}"
        tile_path.parent.mkdir(parents=True, exist_ok=True)
        tile_path.write_bytes(tile)
        extracted.append({
            "z": parsed["level"],
            "x": col,
            "y": row,
            "path": str(tile_path.relative_to(out_dir)),
        })

    return extracted


def main():
    src = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DEFAULT_SRC
    out_dir = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else DEFAULT_OUT
    if not src.exists():
        raise FileNotFoundError(src)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(src) as zip_file:
        bundle_names = sorted(name for name in zip_file.namelist() if name.endswith(".bundle"))
        extent = parse_extent(zip_file)
        tiles = []
        for bundle_name in bundle_names:
            tiles.extend(extract_bundle(zip_file, bundle_name, out_dir))

    levels = sorted({tile["z"] for tile in tiles})
    manifest = {
        "source": src.name,
        "tileUrl": f"data/basemaps/{out_dir.name}/{{z}}/{{x}}/{{y}}.png",
        "minZoom": min(levels) if levels else None,
        "maxZoom": max(levels) if levels else None,
        "tileCount": len(tiles),
        "extent": extent,
    }
    (out_dir / "metadata.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

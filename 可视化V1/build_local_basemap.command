#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

TPK_SOURCE="../原始数据/ditu17.tpk"
OUTPUT_DIR="data/basemaps/ditu17"

if [ ! -f "$TPK_SOURCE" ]; then
  echo "未找到 $TPK_SOURCE"
  echo "请先把奥维导出的 ditu17.tpk 放到项目的 原始数据 文件夹中。"
  exit 1
fi

python3 extract_tpk_basemap.py "$TPK_SOURCE" "$OUTPUT_DIR"
echo "本地奥维底图已生成：$OUTPUT_DIR"

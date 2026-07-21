@echo off
setlocal

cd /d "%~dp0"

set "TPK_SOURCE=..\原始数据\ditu17.tpk"
set "OUTPUT_DIR=data\basemaps\ditu17"

if not exist "%TPK_SOURCE%" (
  echo 未找到 %TPK_SOURCE%
  echo 请先把奥维导出的 ditu17.tpk 放到项目的 原始数据 文件夹中。
  exit /b 1
)

python extract_tpk_basemap.py "%TPK_SOURCE%" "%OUTPUT_DIR%"
if errorlevel 1 (
  echo.
  echo 生成失败。如果系统找不到 python，请安装 Python 3，或把 python 命令加入 PATH。
  exit /b 1
)

echo.
echo 本地奥维底图已生成：%OUTPUT_DIR%
pause

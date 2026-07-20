@echo off
setlocal
cd /d "%~dp0"
set "BUNDLED_NODE=C:\Users\13355\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe"
if exist "%BUNDLED_NODE%" (
  "%BUNDLED_NODE%" server.cjs
) else (
  node server.cjs
)
pause

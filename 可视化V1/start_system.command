#!/bin/zsh

cd "$(dirname "$0")" || exit 1

BUNDLED_NODE="$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"

if [ -x "$BUNDLED_NODE" ]; then
  "$BUNDLED_NODE" server.cjs
elif command -v node >/dev/null 2>&1; then
  node server.cjs
else
  echo "未找到 Node.js。"
  echo "请先安装 Node.js，或在 Codex 环境中运行本脚本。"
  echo "下载地址：https://nodejs.org/"
  read "?按回车键退出..."
  exit 1
fi

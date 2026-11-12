#!/usr/bin/env bash
# gh 入口包装：优先 HOME 持久副本 -> /tmp 副本 -> 都不存在时重跑安装器。
# 用法：  ./gh.sh --version     ./gh.sh auth status
set -e
WS="$(cd "$(dirname "$0")" && pwd)"
PY=python3

CANDIDATES=(
  "$HOME/.local/bin/gh"
  "/tmp/gh/bin/gh"
)

for g in "${CANDIDATES[@]}"; do
  if [ -x "$g" ]; then
    exec "$g" "$@"
  fi
done

echo "[gh.sh] no gh binary found, re-running installer..." >&2
"$PY" "$WS/install_gh.py" >&2

# install_gh.py 装到 /tmp/gh/bin/gh，同时复制回 HOME 持久副本
if [ -x /tmp/gh/bin/gh ]; then
  mkdir -p "$HOME/.local/bin"
  cp /tmp/gh/bin/gh "$HOME/.local/bin/gh"
  chmod 755 "$HOME/.local/bin/gh"
  exec "$HOME/.local/bin/gh" "$@"
fi

echo "[gh.sh] install failed" >&2
exit 1
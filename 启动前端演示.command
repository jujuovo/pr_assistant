#!/bin/zsh
cd "$(dirname "$0")/frontend" || exit 1
# Prefer the working Node installation on this Mac.
export PATH="/usr/local/bin:$PATH"
if [[ ! -f node_modules/vite/bin/vite.js ]]; then
  npm ci --no-audit --no-fund || exit 1
fi
npm run demo -- --open

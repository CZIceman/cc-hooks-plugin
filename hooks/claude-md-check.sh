#!/usr/bin/env bash
# SessionStart hook (plugin) — upozorní, když repu chybí CLAUDE.md, nebo když
# existuje, ale není commitnutý.
#
# Proč: CLAUDE.md, který zůstane netrackovaný, se ztratí při každém klonu,
# přesunu i úklidu — a nikdo si toho nevšimne, protože lokálně funguje dál.
#
# Přenositelný: mimo git repo tiše končí. Nikdy nesmí rozbít start session.
set -uo pipefail

d="${CLAUDE_PROJECT_DIR:-$PWD}"
cd "$d" 2>/dev/null || exit 0
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0

if [ ! -f CLAUDE.md ]; then
  echo "⚠ CLAUDE.md v tomto repu CHYBÍ — zvaž /init a výsledek hned commitni (jinak zůstane netrackovaný a ztratí se)."
elif ! git ls-files --error-unmatch CLAUDE.md >/dev/null 2>&1; then
  echo "⚠ CLAUDE.md existuje, ale NENÍ commitnutý v gitu (untracked) — commitni ho, ať se neztratí."
fi
exit 0

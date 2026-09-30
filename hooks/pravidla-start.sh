#!/usr/bin/env bash
# SessionStart hook (plugin) — při startu, obnově i po zhuštění kontextu vloží do kontextu
# globální pravidla pro všechny projekty (soubor pravidla.txt vedle skriptu).
#
# Proč: ~/.claude/CLAUDE.md se přes účet claude.ai nesynchronizuje a plugin CLAUDE.md dodat
# nemůže. Hook je jediná cesta, kudy se stejná pravidla dostanou na každý stroj. Zdroj pravdy
# je pravidla.txt; lokální ~/.claude/CLAUDE.md s týmž obsahem se nesmí držet (pravidla by
# přišla dvakrát). Stdout se vloží do kontextu. Nikdy nesmí rozbít start session.
set -uo pipefail
f="$(dirname "${BASH_SOURCE[0]}")/pravidla.txt"
[ -r "$f" ] && cat "$f"
exit 0

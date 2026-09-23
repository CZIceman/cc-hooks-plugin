#!/usr/bin/env bash
# PreCompact hook — dlouhá session → kompakce → norma i „dluh na docs" by zmizely.
# Tenhle hook je po kompakci znovu vloží do kontextu (stdout se přidá modelu).
# NEBLOKUJE, jen připomíná + shrne nezarovnané změny. Musí být rychlý a nesmí
# nikdy selhat tak, aby rozbil session (vše best-effort, exit 0).
set -uo pipefail
IN=$(cat 2>/dev/null || true)

# cwd z JSON vstupu (jq, jinak python, jinak aktuální adresář) — best-effort
CWD="."
if command -v jq >/dev/null 2>&1; then
  CWD=$(printf '%s' "$IN" | jq -r '.cwd // "."' 2>/dev/null || echo ".")
elif command -v python3 >/dev/null 2>&1; then
  CWD=$(printf '%s' "$IN" | python3 -c 'import sys,json;
try: print(json.load(sys.stdin).get("cwd") or ".")
except: print(".")' 2>/dev/null || echo ".")
fi
[ -d "$CWD" ] || CWD="."

echo "[Připomínka dokumentace — kontext se právě zhušťoval, ať nezmizí]"
echo "Dokumentace je vedlejší produkt commitu, ne úklid na konci. Než budeš pokračovat:"
echo "- zarovnej dotčené dokumenty se změnami TÉTO session (volatilní fakt = jeden zdroj pravdy, jinde odkaz);"
echo "- u další věcné změny nech v těle commitu řádek: co + PROČ + značka [T]/[K]/[D]/[O];"
echo "- na konci spusť /handoff (skládá docs z commit historie, nerekonstruuje z paměti)."

# Best-effort přehled toho, co ještě není commitnuté (proxy pro „nezarovnaný dluh").
if git -C "$CWD" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  UNCOMMITTED=$(git -C "$CWD" status --short 2>/dev/null | head -30)
  if [ -n "$UNCOMMITTED" ]; then
    echo
    echo "Necommitnuté změny právě teď (zkontroluj, jestli k nim patří i dokumentace):"
    printf '%s\n' "$UNCOMMITTED"
  fi
fi
exit 0

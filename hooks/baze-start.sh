#!/usr/bin/env bash
# SessionStart hook (plugin) — každé nové session připomene znalostní bázi Second Brain.
#
# Proč: hlavní smysl báze je, aby agent nejdřív levně hledal (možná jsme to už řešili,
# nebo víme, co nefunguje) a teprve pak utrácel tokeny řešením od nuly; a aby se každé
# zjištění, včetně slepých uliček, propsalo zpátky do báze. Od 0.10.0 až po předložení výsledku
# Markovi (dřív „hned“: zápisy předbíhaly výsledek a poznámky se přepisovaly). Stdout se vloží do kontextu.
#
# Zmiňuje JEN bázi (žádné repo ani projekt). Nikdy nesmí rozbít start session.
set -uo pipefail
cat <<'TEXT'
[Znalostní báze Second Brain]
Máme sdílenou znalostní bázi Second Brain (konektor MCP). Než začneš řešit problém nebo cokoli hledat,
zavolej `pravidla` (jednou za session) a `hledej` (1–3 klíčová slova). Je to levné a často to ušetří
práci: možná jsme to už řešili, nebo víme, co nefunguje. Výsledek nejdřív předlož Markovi; do báze (`zapis`)
zapisuj až po jeho reakci, jednou za téma, včetně slepých uliček a chyb (ať se neopakují).
Nástroje konektoru mohou být odložené: načti je přes ToolSearch (dotaz „Second Brain“). Teprve když je
nenajde ani ToolSearch, řekni, že konektor chybí.
TEXT
exit 0

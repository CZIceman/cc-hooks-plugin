#!/usr/bin/env bash
# PreCompact hook (plugin) — těsně před zhuštěním kontextu připomene zápis do báze.
#
# Proč: při zhuštění se detaily session ztratí; zjištění, která nejsou v bázi,
# jsou pak pryč. Tohle je poslední chvíle, kdy je model ještě zná.
#
# Zmiňuje JEN bázi (žádné repo ani projekt). Neblokuje, vždy exit 0.
set -uo pipefail
cat <<'TEXT'
[Znalostní báze Second Brain]
Kontext se zhušťuje a detaily se ztratí. Zapiš teď do báze (`hledej` → `zapis`) vše důležité z této
session, co tam ještě není: zjištění, závěry, slepé uličky a chyby i s hláškou, ať se neopakují.
TEXT
exit 0

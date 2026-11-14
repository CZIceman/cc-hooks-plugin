#!/usr/bin/env bash
# PreCompact hook (plugin) — těsně před zhuštěním kontextu připomene zápis do báze.
#
# Proč: při zhuštění se detaily session ztratí; zjištění, která nejsou v bázi,
# jsou pak pryč. Tohle je poslední chvíle, kdy je model ještě zná. Od 0.10.0 se zapisuje jen to,
# co Marek už viděl; zbytek jde do shrnutí jako čekající na zápis.
#
# Zmiňuje JEN bázi (žádné repo ani projekt). Neblokuje, vždy exit 0.
set -uo pipefail
cat <<'TEXT'
[Znalostní báze Second Brain]
Kontext se zhušťuje a detaily se ztratí. Do báze (`hledej` → `zapis`) zapiš jen to z této session, co Marek
už viděl a nerozporoval a v bázi to ještě není: zjištění, závěry, slepé uličky a chyby i s hláškou. Co ještě
neviděl, nezapisuj; uveď to ve shrnutí jako čekající na zápis do báze.
TEXT
exit 0

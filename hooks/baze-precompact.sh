#!/usr/bin/env bash
# PreCompact hook (plugin) — instrukce pro shrnutí při zhuštění kontextu (od 0.13.0).
#
# Dokumentace Claude Code: „PreCompact: your stdout becomes instructions for the compaction summary“
# (https://code.claude.com/docs/en/hooks). Text tedy čte model, který píše shrnutí, ne pracující agent:
# nástroje volat nemůže, proto se tu NEŽÁDÁ zápis do báze (do 0.12.0 tu bylo „zapiš teď do báze“, což při
# shrnování nejde). Cíl (Marek 20. 11. 2026): práce na mnoho hodin musí po kompaktu pokračovat tam, kde skončila.
# Neblokuje, vždy exit 0. Limit stdout 10 000 znaků.
set -uo pipefail
cat <<'TEXT'
Pokyny pro shrnutí (marek-cc-hooks): práce musí po zhuštění pokračovat přesně tam, kde skončila. Ve shrnutí zachovej:
1. Markovo zadání doslova (citace jeho zpráv, ne parafráze) a všechna jeho rozhodnutí a souhlasy, s datem.
2. Hotovo / zbývá / přesně další krok. U hotového i čím bylo ověřeno (test, příkaz, výstup).
3. Běžící delegace: subagenti, příkazy na pozadí a úkoly jiných session s jejich ID, popisem, smlouvou (HOTOVO, PŘI CHYBĚ)
   a co se od nich čeká; naplánované budíky (CronCreate) s ID a intervalem.
4. Cestu ke stavovému souboru práce (HANDOFF.md apod.), klíčové soubory, větve a commity.
5. Slepé uličky a chyby s hláškou, ať se neopakují.
6. Co Marek viděl, ale ještě není v bázi Second Brain: označ „čeká na zápis do báze“ (kam a co).
TEXT
exit 0

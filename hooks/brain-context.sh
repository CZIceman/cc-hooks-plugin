#!/usr/bin/env bash
# SessionStart hook (plugin) — vloží kontext znalostní báze (pravidla + obory).
# Přenositelný: sám najde brain-context v obvyklých umístěních báze. Když žádnou
# nenajde (stroj bez Second Brain), tiše skončí — nesmí nikdy rozbít session.
set -uo pipefail
for p in \
  "${BRAIN_PATH:-/nonexistent}/bin/brain-context" \
  "$HOME/SecondBrain/bin/brain-context" \
  "$HOME"/mnt/*/bin/brain-context \
  /srv/brain/bin/brain-context
do
  [ -x "$p" ] && exec "$p"
done
exit 0

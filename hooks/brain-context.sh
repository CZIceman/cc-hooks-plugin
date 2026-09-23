#!/usr/bin/env bash
# SessionStart hook (plugin) — připomene agentovi znalostní bázi Second Brain.
# Od 23. 9. 2026 žije báze JEN na Google Drive; čte a zapisuje se přes Google
# Drive konektor skilly /hledej a /zapis. Hook NEPOUŽÍVÁ git ani lokální kopii
# (Markovo pravidlo: git jen pro čtecí kopii Obsidianu a zálohu vaultu) — jen
# vypíše krátký statický kontext. Nesmí nikdy rozbít session: vždy exit 0.
cat <<'EOF'
## Znalostní báze Second Brain (Google Drive)

Sdílená báze znalostí je na Google Drive, složka `SecondBrain` (ID ve skillech).
Pracuj s ní **jen přes Google Drive
konektor** (`mcp__claude_ai_Google_Drive__*`) a skilly:
- **`/hledej`** — než začneš řešit netriviální problém, podívej se, jestli už nebyl vyřešen;
- **`/zapis`** — co ses dozvěděl a stálo to čas, zapiš (nová verze + stará do koše, kontrola souběhu).
Pravidla: `_AI_INSTRUCTIONS.md` v kořeni báze. Rozcestník: `INDEX.md` (píše ho jen hlídač — needituj).
Git ani lokální kopii báze k práci nepoužívej. Když konektor v téhle session chybí,
session vznikla dřív, než se připojil — pomůže nová session.
EOF
exit 0

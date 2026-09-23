#!/usr/bin/env bash
# SessionStart hook (plugin) — doručí agentovi pravidla znalostní báze Second Brain.
# Od 23. 9. 2026 žije báze JEN na Google Drive; čte a zapisuje se přes Google
# Drive konektor skilly /hledej a /zapis. Hook NEPOUŽÍVÁ git ani lokální kopii
# (Markovo pravidlo: git jen pro čtecí kopii Obsidianu a zálohu vaultu). Sám na
# Drive nedosáhne, proto agentovi NAŘÍDÍ přečíst pravidla přes konektor (ID souboru
# není tajemství — soubor je soukromý, bez přihlášení účtem ho nikdo neotevře).
# Chat na claude.ai a Cowork hooky nespouští — tam totéž vynucuje krok 0 skillů.
# Nesmí nikdy rozbít session: vždy exit 0.
cat <<'EOF'
## Znalostní báze Second Brain (Google Drive) — POVINNÉ

Sdílená báze znalostí je na Google Drive, složka `SecondBrain`. Pracuj s ní **jen přes
Google Drive konektor** (`mcp__claude_ai_Google_Drive__*`) a skilly `/hledej` a `/zapis`.

**Než s bází cokoli uděláš (hledání i zápis), MUSÍŠ si v této session přečíst pravidla**
`_AI_INSTRUCTIONS.md`: `read_file_content(fileId="1T8rpxOYYiJk3wGu2J9dEw3Up9h6HLE-g")`
— a **striktně se jimi řídit** (přepis místo přílepku, slovník oborů a tagů, přílohy,
přístupové údaje). Stačí jednou za session.

- **`/hledej`** — než začneš řešit netriviální problém, podívej se, jestli už nebyl vyřešen;
- **`/zapis`** — co ses dozvěděl a stálo to čas, zapiš.
`INDEX.md` a `_brain-*.md` píše jen hlídač — needituj. Git ani lokální kopii báze k práci
nepoužívej. Když konektor v téhle session chybí, vznikla dřív, než se připojil — pomůže nová session.
EOF
exit 0

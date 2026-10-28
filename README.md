# marek-cc-hooks — přenosné Claude Code hooky

Plugin, který nese hooky používané napříč projekty, aby se **nemusely ručně
nastavovat na každém novém stroji**. Distribuce jde přes účet claude.ai: když je
plugin v účtu povolený, synchronizuje se na každý stroj, kde běží Claude Code.

## Co je uvnitř

Hooky nesou znalostní bázi Second Brain a **globální pravidla pro všechny projekty**
(od 0.4.0; Marek 1. 10. 2026 zrušil dřívější pravidlo „hooky jen o bázi“). Pravidla jsou
v souboru `hooks/pravidla.txt`, to je jediný zdroj pravdy. Plugin `CLAUDE.md` dodat nemůže
(Plugin manifest reference: „A `CLAUDE.md` at the plugin root isn't loaded as context“)
a `~/.claude/CLAUDE.md` se přes účet nesynchronizuje, proto jdou pravidla hookem.

| Hook | Událost | Co dělá |
|---|---|---|
| `baze-start.sh` | `SessionStart` | připomene bázi: než se začne cokoli řešit, nejdřív `pravidla` a `hledej` (levné, možná jsme to už řešili nebo víme, co nefunguje); vše důležité včetně slepých uliček zapisovat hned |
| `pravidla-start.sh` | `SessionStart` | vloží do kontextu obsah `pravidla.txt` (komunikace česky, dokumentace průběžně, nevymýšlej si, hotovo až po ověření, samostatná práce bez zbytečných dotazů, git, utrácení a volby, citlivé údaje, dílna); běží při startu, obnově i po zhuštění kontextu (bez matcheru) |
| `baze-precompact.sh` | `PreCompact` | těsně před zhuštěním kontextu připomene zapsat do báze, co z této session ještě v bázi není. Neblokuje |
| `pretool-guard.py` | `PreToolUse` | **vynucuje pravidla před akcí** (od 0.6.0): rizikové akce vrací jako `ask` (okno oprávnění), tajné soubory a bránu báze; od 0.7.0 bez dotazů na push a běhy modelů a se zamítnutím zbytečného `AskUserQuestion` (viz níže) |
| `stop-guard.py` | `Stop` | po odpovědi upozorní na „hotovo“ bez příkazu/testu a na změnu bez zápisu do báze nebo dokumentu (`MAREK_STOP_MODE=block` by blokoval); od 0.7.0 jednou zablokuje tah končící zbytečnou otázkou na uživatele |
| `ack-guard.py` | `UserPromptSubmit` | od 0.7.0: pozná zprávu od jiného agenta a agentovi vloží pokyn odpovědět odesílateli `[ACK] Přijato HH:MM`; nepotvrzuje potvrzení (bez smyčky); formát příchozí zprávy je zatím předpoklad (viz níže) |

Tři původní hooky jen vypíšou text (stdout jde do kontextu), vždy `exit 0`. Hooky od 0.6.0 text vkládají jen jako důvod rozhodnutí nebo kontext; při chybě skriptu akce pokračuje (`exit 0` bez výstupu).

## Instalace (jednou, ať se pak synchronizuje sama)

Přesná cesta k účtové synchronizaci závisí na tom, kde marketplace hostuje —
viz `INSTALACE.md`. Lokální ověření na tomto stroji:

```
claude plugin marketplace add /home/marek/claude/cc-hooks-plugin
claude plugin install marek-cc-hooks@marek-hooks
```

## Pozor: pravidla nedržet i v lokálním CLAUDE.md

Když má stroj `~/.claude/CLAUDE.md` se stejným obsahem jako `pravidla.txt`, přijdou pravidla
dvakrát a vznikne druhá kopie, která se časem rozejde. Na strojích s pluginem ho zruš.
Změna znění = úprava `hooks/pravidla.txt`, verze, push a obnova marketplace v claude.ai.

## Pozor: dvojí spuštění

Když jsou hooky zároveň v `~/.claude/settings.json` nebo je plugin nainstalovaný
i lokálně (`plugin install`), spustí se **dvakrát**. Na strojích má běžet jen `@synced`.

## Offline

Plugin synchronizovaný přes účet se načítá online. Na stroji bez konektivity
se nově nenačte; už stažený zůstává. Naše stroje jsou online, ale je to důvod
nespoléhat na hook jako na jedinou pojistku.

## Vynucení (od 0.6.0, upraveno 0.7.0)

Souhlas nehlídá model ani text: hook nezjistí, že uživatel řekl „ano“. Rizikovou akci proto vrací jako
`permissionDecision: "ask"` a souhlasem je okno oprávnění Claude Code. `ask` platí i proti pravidlu `allow`
a ve všech režimech oprávnění (default, acceptEdits, auto, dontAsk, bypassPermissions); ověřeno 16. 10. 2026
v Claude Code 2.1.300 přes `claude -p`, v interaktivním režimu okno neověřeno.

### Od 0.7.0: samostatná práce (rozhodnutí Marka, 28. 10. 2026)

Agenti se ptali zbytečně. Příčinou byl hlavně text `pravidla.txt` („před každou změnou se zeptej“, push jen na pokyn,
běh modelu jen po „ano“), ne samotné okno oprávnění. Nově se agent smí ptát jen na **mazání nebo přepis dat** a na
**hesla, tokeny a klíče**; nabídka dílny a volby `FORMULAR` zůstaly beze změny. Otázky k zadání patří řídící session
(pravidla báze, bod 0), ne uživateli.

`pretool-guard.py` (PreToolUse) vrací:
- `ask` pro `sudo`, instalaci a odebrání balíčků, změny služeb, destruktivní git (`reset --hard`, `clean -f`, `branch -D`,
  `--force`), změny konfigurace systému, práva a disky, zápisy do `/etc`, `/usr`, `~/.bashrc*`, `~/.claude/settings*`
  a podobně, `rm`/`rmdir`/`shred`/`truncate` mimo scratchpad;
- `ask` pro příkazy sahající na tajné soubory (`.bash_history`, `~/.ssh`, `.env` a podobně);
- **bez dotazu** (od 0.7.0): `git push`, běhy modelů (`Agent`, `Workflow`, `zadej_ukol`, `claude`/`codex`/`agy` s `-p`/`exec`),
  `mv` a `sed -i`/`perl -i` ve scratchpadu a v adresáři projektu. Projekt = `cwd` session; domovský adresář a `/`
  se za projekt nepovažují. Cesta ven z projektu (`../`, `~/.bashrc`, `/srv/…`) se ptá dál;
- `deny` pro `AskUserQuestion` bez rizikového tématu: agent dostane důvod „rozhodni sám a pokračuj“. Projdou otázky
  s mazáním/přepisem, hesly, tokeny, klíči, dílnou, a vše, co následuje po nabídce `FORMULAR` v přepisu. Je to heuristika
  podle textu otázky; nejistota = propustit. Vypnutí: `MAREK_ASK_MODE=off`;
- `deny` bránu báze: dokud session nezavolala `pravidla`, zamítne nástroje kromě `ToolSearch`, `AskUserQuestion`,
  `ReadNotifications` a nástrojů báze; po 2 zamítnutích propustí (konektor nemusí být dostupný). Subagenty brána
  nehlídá (větev `AskUserQuestion` je hlídá také). Stav je v `$XDG_RUNTIME_DIR/marek-hooks/<session_id>.baze`.

Tajné cesty specifické pro stroj (např. soubory s tokeny) **nejsou v repu** (repo je veřejné). Jsou v lokálním souboru
`~/.config/marek-hooks/tajne.txt`: jeden regulární výraz na řádek, `#` komentář. Chybí-li soubor, platí jen obecné vzory.

`stop-guard.py` (Stop):
- upozornění „hotovo bez ověření“ a „změna bez dokumentace“ jdou jako `additionalContext`;
- **od 0.7.0** tah, který končí otázkou na uživatele (a nepoužil okno `AskUserQuestion` ani se neptá na mazání,
  hesla/tokeny/klíče, dílnu), se jednou zablokuje s důvodem „rozhodni sám a pokračuj“. Vypnutí: `MAREK_STOP_QUESTIONS=off`;
- druhé volání v téže odpovědi (`stop_hook_active`) mlčí, takže se nezacyklí. Potřebuje přepis session
  (`--no-session-persistence` ho nevytvoří).

### Potvrzování zpráv od jiných agentů (od 0.7.0)

Přes Remote Control (`SendMessage`/`ListAgents`) nechodí potvrzení o přečtení, odesílatel neví, zda zpráva dorazila.
`ack-guard.py` (UserPromptSubmit) zprávu pozná a agentovi vloží pokyn odpovědět odesílateli (`to` = `from`)
jedním řádkem `[ACK] Přijato HH:MM, zpracovávám.` Potvrzení **neznamená souhlas ani splnění**: souhlas přes jiného agenta
není souhlas člověka. Zpráva obsahující `[ACK]` se nepotvrzuje (žádný ping-pong).

**Neověřeno (28. 10. 2026):** jakou událostí a v jakém tvaru příchozí `SendMessage` do session dorazí a zda ho
`UserPromptSubmit` vůbec uvidí. Výchozí vzor (`<… from="jméno" …>`) je předpoklad podle báze („atribut `from` příchozí
zprávy“). Postup ověření na reálné zprávě:
1. v session spustit s `MAREK_ACK_CAPTURE=1` a poslat jí zprávu od jiné session;
2. přečíst `$XDG_RUNTIME_DIR/marek-hooks/ack-capture.jsonl` (začátek promptu, nalezený `from`; tmpfs, zaniká s restartem);
3. nevidí-li hook zprávu nebo má jiný tvar, doplnit vzor v `~/.config/marek-hooks/ack.json`
   (`{"enabled": true, "patterns": ["…(?P<from>…)…"]}`), případně zvolit jinou událost.

Trvale běžící agenti startují s `--settings '{"disableAllHooks": true}'` (báze); v nich plugin neběží a potvrzování
tam nefunguje. Pro ně by pravidlo patřilo do jejich vlastního `CLAUDE.md`.

**ntfy:** `hooks/ntfy-ack.py <klíč>` pošle `[ACK] Přijato HH:MM` na tajný topic z `~/.config/marek-hooks/ntfy.json`
(`{"server": "https://ntfy.lumatech.cz", "topics": {"<klíč>": "<topic ≥ 26 znaků [a-z0-9]>"}}`, práva 600, mimo repo).
Server je otevřený a bezpečnost stojí na tajném jménu topicu (báze: `znalosti/site/ntfy-lumatech-server.md`), proto se
topic nikdy nevypisuje, neloguje ani neukládá do repa či báze. Hook ho zapojí, až je v `ack.json` klíč `ntfy_patterns`
(regex s pojmenovanou skupinou `klic`); do té doby je ntfy větev vypnutá, protože tvar příchozích ntfy zpráv není znám.
Test odeslání: `MAREK_TEST_NET=1 python3 tests/test-ack.py` (náhodný testovací topic, 12 h na serveru).

Testy bez modelu: `python3 tests/test-hooks.py`, `python3 tests/test-stop.py`, `python3 tests/test-ack.py`.

Vrácení: obnovit verzi 0.6.0 (commit `e9f00ca`, dotazy jako dřív) nebo 0.5.1 (commit `af41bd2`) a marketplace.
Nouzově odeber `PreToolUse`, `Stop` a `UserPromptSubmit` z `hooks/hooks.json`.

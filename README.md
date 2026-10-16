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
| `pravidla-start.sh` | `SessionStart` | vloží do kontextu obsah `pravidla.txt` (komunikace česky, dokumentace průběžně, nevymýšlej si, hotovo až po ověření, před změnou se zeptej, git, utrácení a volby, citlivé údaje, dílna); běží při startu, obnově i po zhuštění kontextu (bez matcheru) |
| `baze-precompact.sh` | `PreCompact` | těsně před zhuštěním kontextu připomene zapsat do báze, co z této session ještě v bázi není. Neblokuje |
| `pretool-guard.py` | `PreToolUse` | **vynucuje pravidla před akcí** (od 0.6.0): rizikové akce vrací jako `ask` (okno oprávnění), běhy modelů, tajné soubory a bránu báze (viz níže) |
| `stop-guard.py` | `Stop` | po odpovědi upozorní na „hotovo“ bez příkazu/testu a na změnu bez zápisu do báze nebo dokumentu; neblokuje (`MAREK_STOP_MODE=block` by blokoval) |

Tři původní hooky jen vypíšou text (stdout jde do kontextu), vždy `exit 0`. Nové dva (0.6.0) text vkládají jen jako důvod rozhodnutí; při chybě skriptu akce pokračuje (`exit 0` bez výstupu).

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

## Vynucení (od 0.6.0)

Souhlas nehlídá model ani text: hook nezjistí, že uživatel řekl „ano“. Rizikovou akci proto vrací jako
`permissionDecision: "ask"` a souhlasem je okno oprávnění Claude Code. `ask` platí i proti pravidlu `allow`
a ve všech režimech oprávnění (default, acceptEdits, auto, dontAsk, bypassPermissions); ověřeno 16. 10. 2026
v Claude Code 2.1.300 přes `claude -p`, v interaktivním režimu okno neověřeno.

`pretool-guard.py` (PreToolUse) vrací:
- `ask` pro `sudo`, instalaci a odebrání balíčků, změny služeb, `git push` a destruktivní git, změny konfigurace
  systému (`setpci`, `nmcli`, `tuned-adm`, `xdg-user-dirs-update` a podobně), práva a disky, zápisy do `/etc`, `/usr`,
  `~/.bashrc*`, `~/.claude/settings*` a podobně, `rm`/`mv`/`sed -i` mimo scratchpad;
- `ask` pro běhy modelů: `Agent`, `Workflow`, `zadej_ukol` a `claude`/`codex`/`agy` s `-p`/`exec`;
- `ask` pro příkazy sahající na tajné soubory (`.bash_history`, `~/.ssh`, `.env` a podobně);
- `deny` bránu báze: dokud session nezavolala `pravidla`, zamítne nástroje kromě `ToolSearch`, `AskUserQuestion`,
  `ReadNotifications` a nástrojů báze; po 2 zamítnutích propustí (konektor nemusí být dostupný). Subagenty nehlídá.
  Stav je v `$XDG_RUNTIME_DIR/marek-hooks/<session_id>.baze`.

Tajné cesty specifické pro stroj (např. soubory s tokeny) **nejsou v repu** (repo je veřejné). Jsou v lokálním souboru
`~/.config/marek-hooks/tajne.txt`: jeden regulární výraz na řádek, `#` komentář. Chybí-li soubor, platí jen obecné vzory.

`stop-guard.py` (Stop): upozornění jde jako `additionalContext`, model ho dostane a opraví se; druhé volání v téže odpovědi
(`stop_hook_active`) mlčí, takže se nezacyklí. Potřebuje přepis session (`--no-session-persistence` ho nevytvoří).

Testy bez modelu: `python3 tests/test-hooks.py` a `python3 tests/test-stop.py`.

Vrácení: obnovit verzi 0.5.1 (commit `af41bd2`) a marketplace. Nouzově odeber `PreToolUse` a `Stop` z `hooks/hooks.json`.

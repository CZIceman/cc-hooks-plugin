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
| `pravidla-start.sh` | `SessionStart` | vloží do kontextu obsah `pravidla.txt` (dokumentace průběžně, nevymýšlej si, před změnou se zeptej, dílna); běží při startu, obnově i po zhuštění kontextu (bez matcheru) |
| `baze-precompact.sh` | `PreCompact` | těsně před zhuštěním kontextu připomene zapsat do báze, co z této session ještě v bázi není. Neblokuje |

Všechny tři jen vypíšou text (stdout jde do kontextu), vždy `exit 0`.

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

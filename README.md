# marek-cc-hooks — přenosné Claude Code hooky

Plugin, který nese hooky používané napříč projekty, aby se **nemusely ručně
nastavovat na každém novém stroji**. Distribuce jde přes účet claude.ai: když je
plugin v účtu povolený, synchronizuje se na každý stroj, kde běží Claude Code.

## Co je uvnitř

Hooky zmiňují **jen znalostní bázi Second Brain**. Nic o repu, gitu ani projektu:
to patří do `CLAUDE.md` projektu nebo do skillu.

| Hook | Událost | Co dělá |
|---|---|---|
| `baze-start.sh` | `SessionStart` | připomene bázi: než se začne cokoli řešit, nejdřív `pravidla` a `hledej` (levné, možná jsme to už řešili nebo víme, co nefunguje); vše důležité včetně slepých uliček zapisovat hned |
| `baze-precompact.sh` | `PreCompact` | těsně před zhuštěním kontextu připomene zapsat do báze, co z této session ještě v bázi není. Neblokuje |

Oba jen vypíšou text (stdout jde do kontextu), vždy `exit 0`.

## Instalace (jednou, ať se pak synchronizuje sama)

Přesná cesta k účtové synchronizaci závisí na tom, kde marketplace hostuje —
viz `INSTALACE.md`. Lokální ověření na tomto stroji:

```
claude plugin marketplace add /home/marek/claude/cc-hooks-plugin
claude plugin install marek-cc-hooks@marek-hooks
```

## Pozor: dvojí spuštění

Když jsou hooky zároveň v `~/.claude/settings.json` nebo je plugin nainstalovaný
i lokálně (`plugin install`), spustí se **dvakrát**. Na strojích má běžet jen `@synced`.

## Offline

Plugin synchronizovaný přes účet se načítá online. Na stroji bez konektivity
se nově nenačte; už stažený zůstává. Naše stroje jsou online, ale je to důvod
nespoléhat na hook jako na jedinou pojistku.

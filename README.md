# marek-cc-hooks — přenosné Claude Code hooky

Plugin, který nese hooky používané napříč projekty, aby se **nemusely ručně
nastavovat na každém novém stroji**. Distribuce jde přes účet claude.ai: když je
plugin v účtu povolený, synchronizuje se na každý stroj, kde běží Claude Code.

## Co je uvnitř

| Hook | Událost | Co dělá |
|---|---|---|
| `brain-context.sh` | `SessionStart` | vloží kontext znalostní báze (pravidla + obory). Sám najde bázi (`BRAIN_PATH` → `~/SecondBrain` → `$HOME/mnt/*` → `/srv/brain`); bez báze tiše mlčí |
| `docs-norm-precompact.sh` | `PreCompact` | po zhuštění kontextu znovu vloží dokumentační normu + přehled necommitnutých změn. Neblokuje, best-effort, vždy `exit 0` |

Oba jsou přenosné: na stroji bez Second Brain báze se `brain-context` neozve,
`docs-norm` funguje v jakémkoli git projektu.

## Instalace (jednou, ať se pak synchronizuje sama)

Přesná cesta k účtové synchronizaci závisí na tom, kde marketplace hostuje —
viz `INSTALACE.md`. Lokální ověření na tomto stroji:

```
claude plugin marketplace add /home/marek/claude/cc-hooks-plugin
claude plugin install marek-cc-hooks@marek-hooks
```

## Pozor: dvojí spuštění

Dokud jsou tytéž hooky i v `~/.claude/settings.json`, spustí se **dvakrát**.
Po povolení pluginu na stroji odeber z `~/.claude/settings.json` bloky
`SessionStart`/`PreCompact`, které volají `brain-context` a `docs-norm-precompact.sh`.

## Offline

Plugin synchronizovaný přes účet se načítá online. Na stroji bez konektivity
se nově nenačte; už stažený zůstává. Naše stroje jsou online, ale je to důvod
nespoléhat na hook jako na jedinou pojistku.

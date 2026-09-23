# Instalace a distribuce pluginu

Cíl: hooky napsat jednou a mít je na **každém stroji** bez ručního nastavování
`~/.claude/settings.json`. Plugin je nosič; otázka je, kudy se rozveze.

## Tři cesty distribuce — a co u které víme

| Cesta | Jak | Rozveze se sama? | Míra jistoty |
|---|---|---|---|
| **A. Účet + marketplace na GitHubu** | repo na GitHub → `claude plugin marketplace add <gh>` → povolit v účtu claude.ai | ano, na každý stroj po přihlášení | `[O]` — účtová distribuce pluginů je zdokumentovaná cesta, ale u nás neověřená |
| **B. Účet + marketplace na Forgejo** | repo na `git.airvisions.cz` → `marketplace add <url>` → povolit v účtu | **nejisté** — jestli účet claude.ai umí táhnout z vlastního Forgejo | `[O]` — neověřeno; hlavní nejistota |
| **C. Ruční `marketplace add` na každém stroji** | na každém stroji `marketplace add <url>` + `install` | ne, krok na stroj (jako dřív hooky) | `[K]` — funguje lokálně (ověřeno validací + instalací) |

**Rozhodnutí patří Markovi:** kam marketplace hostovat. Zbytek repa je hotový
a na host-neutrální. Skilly (`/hledej`, `/zapis`, `/vytah`) se přes účet
synchronizují prokazatelně — plugin je jejich analogie pro hooky; jestli účtová
synchronizace pluginů jede i z Forgejo, je jediný neověřený článek.

## Postup po rozhodnutí o hostu

```
# 1. založit vzdálené repo (GitHub nebo git.airvisions.cz) a pushnout
git remote add origin <URL>
git push -u origin main

# 2. registrovat marketplace (lokálně nebo na stroji)
claude plugin marketplace add <URL nebo cesta>

# 3a. buď ruční instalace na stroji:
claude plugin install marek-cc-hooks@marek-hooks

# 3b. nebo povolit v účtu claude.ai (Settings → Plugins) → synchronizace na stroje
```

## Po zapnutí na stroji: odstranit dvojí hook

Plugin i `~/.claude/settings.json` nesou tytéž hooky → spustí se **dvakrát**.
Po ověření, že plugin na stroji běží (`claude plugin list`), odeber z
`~/.claude/settings.json` bloky `SessionStart` (`brain-context`) a `PreCompact`
(`docs-norm-precompact.sh`). Ostatní nastavení nech.

## Ověřeno

- `claude plugin validate --strict` — plugin i marketplace manifest projdou `[T]`
- oba hook skripty samostatně: `brain-context.sh` najde bázi a vypíše kontext;
  bez báze tiše `exit 0`; `docs-norm-precompact.sh` vypíše normu + necommitnuté
  změny, `exit 0` `[T]`
- co zatím **není** ověřeno: účtová synchronizace pluginu (cesty A/B výše)

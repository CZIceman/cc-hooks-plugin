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
| `baze-start.sh` | `SessionStart` | připomene bázi: než se začne cokoli řešit, nejdřív `pravidla` a `hledej` (levné, možná jsme to už řešili nebo víme, co nefunguje); výsledek nejdřív předložit Markovi, do báze zapisovat až po jeho reakci, jednou za téma (od 0.10.0) |
| `pravidla-start.sh` | `SessionStart` | vloží do kontextu obsah `pravidla.txt` (komunikace česky, dokumentace průběžně, nevymýšlej si, hotovo až po ověření, nejdřív výsledek a pak zápis do báze, samostatná práce bez zbytečných dotazů, git, utrácení a volby, citlivé údaje, dílna); běží při startu, obnově i po zhuštění kontextu (bez matcheru) |
| `baze-precompact.sh` | `PreCompact` | těsně před zhuštěním kontextu připomene zapsat do báze to, co Marek už viděl a v bázi ještě není; ostatní má jít do shrnutí jako čekající na zápis (od 0.10.0). Neblokuje |
| `pretool-guard.py` | `PreToolUse` | **okno oprávnění (`ask`) jen na mazání a přepis dat, čtení tajemství a změnu nastavení Claude** (od 0.8.0, viz níže), brána báze a brzda zápisu do báze (od 0.10.0) |
| `stop-guard.py` | `Stop` | po odpovědi upozorní na „hotovo“ bez příkazu/testu a na `git commit` bez dotčené dokumentace projektu (od 0.10.0; `MAREK_STOP_MODE=block` by blokoval) |
| `ack-guard.py` | `UserPromptSubmit` | od 0.7.0: pozná zprávu od jiného agenta a agentovi vloží pokyn odpovědět odesílateli `[ACK] Přijato HH:MM`; nepotvrzuje potvrzení (bez smyčky); formát příchozí zprávy je zatím předpoklad (viz níže) |
| `statusline-start.py` | `SessionStart` | od 0.9.0: nainstaluje stavovou řádku (`statusline/statusline.py`) do `~/.claude/marek-statusline/` a doplní `statusLine` do `~/.claude/settings.json` (pravidla viz „Stavová řádka“); nic nevypisuje, vždy `exit 0`; `MAREK_STATUSLINE=0` ho vypne |

Tři původní hooky jen vypíšou text (stdout jde do kontextu), vždy `exit 0`. Hooky od 0.6.0 text vkládají jen jako důvod rozhodnutí nebo kontext; při chybě skriptu akce pokračuje (`exit 0` bez výstupu).

## Stavová řádka (`statusline/`)

Skript `statusline/statusline.py` na stroje rozváží plugin hookem `statusline-start.py`
(od 0.9.0). Ukazuje, kolik práce ještě zbývá:

`Opus 5.5 · high │ ██░░░░░░░░ zbývá 78% │ ⧗ 12 min │ 5h zbývá 27% · 1:48 ⚠ dojde za 0:40 │ týden zbývá 69% · 2d 5h │ ~/claude │ master ±2 +1 ↑1 │ 📁 scratch`

| Segment | Zdroj (stdin JSON Claude Code) | Pravidlo |
|---|---|---|
| model a úsilí | `model.display_name`, `effort.level` | vždy, např. `Opus 5.5 · high` |
| kontext této session | `context_window.used_percentage` / `remaining_percentage` | pruh podle spotřeby, text „zbývá“; zelená < 50 %, žlutá < 80 %, jinak červená |
| cache | `prompt_cache.warm`, `ttl`, `expires_at` | jen teplá a do vypršení ≤ 15 min (ttl 5m: ≤ 2 min); pod 5 min červeně |
| 5h a týden | `rate_limits.five_hour` / `seven_day`: `used_percentage`, `resets_at` | zbývá % (> 50 zelená, > 20 žlutá, jinak červená) a čas do resetu; „⚠ dojde za …“, když by při dosavadním tempu v okně (used / uplynulý čas) limit došel před resetem; počítá se až po 10 min (5h) resp. 6 h (týden) okna |
| projekt | `workspace.project_dir` | `~/…`, klikací odkaz OSC 8 |
| git | `git status --porcelain -b` v `cwd` | větev, `🌿` v odděleném worktree, `±N` změněné, `+N` nesledované (žlutě), `↑N` neodeslané commity |
| odkládací složka | `scratchpad_dir` | jen když v ní něco je, klikací |

Chybějící pole segment vynechá, skript nikdy nespadne a nic nezapisuje. Tvar vstupu ověřen na
Claude Code 2.1.319 (`statusline/tests/vzorek-2.1.319.json`). Test:
`python3 statusline/tests/test-statusline.py`.

### Jak se na stroj dostane (`hooks/statusline-start.py`, `SessionStart`)

Plugin nemůže nastavit hlavní `statusLine` přes vlastní `settings.json`: podporuje jen
`agent` a `subagentStatusLine` (ověřeno v binárce Claude Code 2.1.319). Také cesta
synchronizovaného pluginu se mění s verzí. Proto hook při každém startu session:

1. Zkopíruje `statusline/statusline.py` z pluginu do `~/.claude/marek-statusline/statusline.py`
   (stálá cesta; atomicky, práva 0755; stejný obsah = nic neděláno).
2. Zajistí v `~/.claude/settings.json` záznam
   `{"type": "command", "command": "python3 ~/.claude/marek-statusline/statusline.py" (absolutní cesta), "refreshInterval": 30}`:
   - soubor chybí: vytvoří se jen s klíčem `statusLine`;
   - klíč `statusLine` chybí: doplní se;
   - `command` obsahuje `marek-statusline/statusline.py` nebo `cc-hooks-plugin/statusline/statusline.py`
     (naše starší ruční nasazení) a liší se od standardní hodnoty: nahradí se standardní hodnotou;
   - **cizí `statusLine` se nikdy nepřepíše**;
   - soubor není platný JSON nebo to není objekt: nic se nemění;
   - zapisuje se jen při změně, atomicky, s původními právy; ostatní klíče a jejich pořadí zůstanou.
3. `MAREK_STATUSLINE=0` v prostředí = hook nedělá nic.

Hook nikdy nic nevypíše na stdout (šlo by do kontextu) ani na stderr a vždy skončí `exit 0`; každá chyba je tichá.
Změna se projeví nejpozději v další **nové** session po aktualizaci pluginu (hook běží až při startu
session, která už nový plugin načetla). Test:
`python3 tests/test-statusline-start.py`.

Ruční zapnutí jen pro stroj bez pluginu (v `~/.claude/settings.json`, klon repa např. v `~/cc-hooks-plugin`):

```json
"statusLine": {"type": "command", "command": "python3 /home/marek/cc-hooks-plugin/statusline/statusline.py", "refreshInterval": 30}
```

`refreshInterval` překresluje řádku každých 30 s i bez nové zprávy (odpočty). Jeden běh trvá
~0,05 s.

## Instalace (jednou, ať se pak synchronizuje sama)

Přesná cesta k účtové synchronizaci závisí na tom, kde marketplace hostuje —
viz `INSTALACE.md`. Lokální ověření na tomto stroji:

```
claude plugin marketplace add /home/marek/cc-hooks-plugin
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

## Vynucení (od 0.6.0, přepracováno 0.8.0)

Souhlas nehlídá model ani text: hook nezjistí, že uživatel řekl „ano“. Rizikovou akci proto vrací jako
`permissionDecision: "ask"` a souhlasem je okno oprávnění Claude Code. `ask` platí i proti pravidlu `allow`
a ve všech režimech oprávnění (default, acceptEdits, auto, dontAsk, bypassPermissions); ověřeno 16. 10. 2026
v Claude Code 2.1.300 přes `claude -p`. V režimu `auto` jsou okna z tohoto hooku prakticky jediná okna, která
uživatel vidí (měření 29. 10. 2026: 83 z 83 oken na notebooku za 15.–29. 10., 89 z 91 na pve 28. 10.).

### Od 0.8.0: okno jen tam, kde jde o data (rozhodnutí Marka, 29. 10. 2026)

0.6.0 a 0.7.0 hledaly rizikové slovo v celém textu příkazu, takže okno vyvolalo i `sudo -n true`, `mount | grep`,
`echo '== sudo pam'`, `chmod` uvnitř heredocu, `ssh -i ~/.ssh/klic` nebo `rm` ve složce projektu. Ze 83 oken na notebooku
by jich 0.7.0 vrátila 74. 0.8.0 jich ze stejných příkazů vrátí 3, a to skutečné mazání na NAS. Ze všech 912 volání Bash/Edit/Write
za stejné období jich vrátí 12 (mazání a přepis souborů na NAS, zápis do `tajne.txt`, čtení tajných souborů).

`pretool-guard.py` posuzuje jen to, co shell spustí: příkaz rozloží na jednoduché příkazy (`;`, `&&`, `|`, nový řádek,
`$( )`), těla heredoců přeskočí, řetězce zůstanou jedním slovem, rozbalí `sudo`, `timeout`, `env`, `xargs`, `bash -c '…'`,
dosadí jednoduchá přiřazení (`S=…; rm $S/x`) a sleduje `cd`. Kód skriptů (`python3 -c`, heredoc) nehodnotí.

Pracovní místa (mazat a přepisovat se tu smí bez dotazu): scratchpad, `/tmp`, `/var/tmp`, `/run/user/<uid>` (mimo `gvfs`),
adresář projektu (`CLAUDE_PROJECT_DIR` i aktuální `cwd`; domovský adresář a `/` se za projekt nepovažují), `~/.cache`
a paměť Claude (`~/.claude/projects/*/memory`). Data: domovský adresář, `/mnt`, `/media`, `/run/media`, `/srv`, gvfs.

`ask` vrací jen pro:
- **(a) mazání mimo pracovní místa:** `rm`, `rmdir`, `unlink`, `shred`, `truncate`, `find -delete`/`-exec rm`, `xargs rm`,
  `rsync --delete`; neznámou cílovou cestu (nedosazená proměnná) bere jako mimo. **Přepis existujícího souboru v datech**
  mimo pracovní místa: `>`, `tee` (bez `-a`), cíl `mv`/`cp`/`install`, `sed -i`/`perl -i`. Destruktivní git (`reset --hard`,
  `clean -f`, `branch -D`, `push --force`, `checkout --`, `restore`, `stash drop|clear`; mimo scratchpad a `/tmp`) a operace
  ničící disky (`mkfs`, `wipefs`, `parted`, `fdisk`, `dd of=/dev/…`, `cryptsetup luksFormat|erase`, `lvremove`…);
- **(b) čtení obsahu tajných souborů** (`.bash_history`, soukromé klíče v `~/.ssh`, `.gnupg`, `.netrc`, `.env` a vzory
  z `~/.config/marek-hooks/tajne.txt`). Neptá se u příkazů, které soubor jen použijí nebo vypíšou jméno (`ssh -i`, `ls`,
  `stat`, `chmod`, `git`…), ani u veřejných částí `~/.ssh` (`config`, `known_hosts`, `*.pub`, `authorized_keys`);
- **(c) změnu nastavení a hooků Claude Code a klíčů:** zápis, úprava i mazání v `~/.claude/settings*.json`, `~/.claude/hooks`,
  `~/.claude/plugins`, `~/.config/marek-hooks`, `/etc/claude-code`, `~/.ssh`, `~/.gnupg` (i přes Edit/Write).

**Bez dotazu:** `sudo` a systémové změny (`dnf`, `systemctl`, zápis do `/etc`, `chmod`, `mount`), `git push`, běhy modelů
a agentů, Edit/Write mimo nastavení Claude (Claude Code je umí vrátit přes checkpoint), `AskUserQuestion`.
Příkazy uvnitř `ssh host '…'` a `pct exec N -- …` se hodnotí jako vzdálené: pracovní místa tam jsou jen `/tmp` a `/var/tmp`,
přepis a tajemství se tam nehodnotí.

Zahazování `AskUserQuestion` podle textu otázky a blok otázky na konci tahu (oboje 0.7.0) jsou zrušené: heuristika by
zamítla 22 z 35 skutečných otázek, i schválení kopírování dat, které si Marek vyhradil. Kdy se ptát, určuje `pravidla.txt`.

Brána báze: dokud session nezavolala `pravidla`, hook zamítne nástroje kromě `ToolSearch`, `AskUserQuestion`,
`ReadNotifications` a nástrojů báze; po 2 zamítnutích propustí (konektor nemusí být dostupný). Subagenty nehlídá.
Stav je v `$XDG_RUNTIME_DIR/marek-hooks/<session_id>.baze`.

Tajné cesty specifické pro stroj (např. soubory s tokeny) **nejsou v repu** (repo je veřejné). Jsou v lokálním souboru
`~/.config/marek-hooks/tajne.txt`: jeden regulární výraz na řádek, `#` komentář. Chybí-li soubor, platí jen obecné vzory.

`stop-guard.py` (Stop): upozornění „hotovo bez ověření“ a „commit bez dokumentace“ jdou jako `additionalContext`;
druhé volání v téže odpovědi (`stop_hook_active`) mlčí. Potřebuje přepis session (`--no-session-persistence` ho nevytvoří).

**Nová verze platí až v nové session.** Běžící session drží verzi pluginu, se kterou startovala
(`…/synced/<bucket>/marek-cc-hooks~gN/.in_use/<PID>`); ověřeno 29. 10. 2026: dvě session z 26. 10. a 29. 10. 13:38 běžely
s 0.6.0, ačkoli 0.7.0 už byla stažená.

### Od 0.10.0: nejdřív výsledek, pak zápis do báze (rozhodnutí Marka, 14. 11. 2026)

Do 0.9.0 plugin nařizoval zapisovat do báze „hned“ (`baze-start.sh`) a `stop-guard.py` to po každé změně
připomínal. Měření z přepisů session na notebooku fedora za 30 dní do 14. 11. 2026 (25 session): 594 volání
`zapis`, z toho 544 ve stejném tahu jako práce (dřív, než Marek výsledek viděl), 490 opakovaných přepisů téže
poznámky v jedné session, průměrně 13 594 znaků na zápis (posílá se celá poznámka). Při nesouhlasu s výsledkem
se tak zapisovalo a opravovalo zbytečně.

Od 0.10.0 platí pořadí: výsledek Markovi, po jeho reakci (souhlas, nebo pokračování bez námitky) zápis do báze,
jednu poznámku jednou za téma. Dokumentace projektu (README, HANDOFF, docs/) zůstává ve stejném commitu se změnou.

| Místo | Změna |
|---|---|
| `pravidla.txt` | nová sekce „Nejdřív výsledek, pak zápis do báze“ (znění platí i pro profil claude.ai) |
| `baze-start.sh` | místo „zapisuj hned“: výsledek nejdřív Markovi, zápis po jeho reakci |
| `baze-precompact.sh` | zapsat jen to, co Marek už viděl; ostatní do shrnutí jako čekající na zápis |
| `stop-guard.py` | upozornění (b) už nepřipomíná bázi a spouští se jen při `git commit` bez dotčené dokumentace projektu (dokument upravený přes Edit/Write nebo zmíněný v příkazu) |
| `pretool-guard.py` | brzda zápisu, viz níže |

Brzda zápisu: `zapis` v tahu, kde už běžel jiný nástroj než báze (`ToolSearch`, `AskUserQuestion` a
`ReadNotifications` se nepočítají), hook poprvé zamítne s odkazem na pravidlo. Projde, když Marek v poslední
zprávě o zápis výslovně požádal (slova zapiš, zapsat, do báze, výtah), a při opakovaném volání v témže tahu
(session bez Marka: naplánovaná úloha, práce pro řídící session). Subagenty nehlídá; nejde-li přepis session
přečíst, zápis projde. Stav je v `$XDG_RUNTIME_DIR/marek-hooks/<session_id>.zapis`.
Cena brzdy: zamítnuté volání už nese celý text poznámky, který model vygeneroval zbytečně.
Vypnutí bez nové verze: proměnná prostředí `MAREK_ZAPIS_BRZDA=off`. Návrat celé změny: `git revert` commitu 0.10.0.

Mimo plugin musí stejné pořadí říkat profil claude.ai (chat a Cowork hooky nemají) a pravidla báze (§10, mění
správce na serveru).

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

Vrácení: obnovit verzi 0.7.0 (commit `f1d458b`), 0.6.0 (commit `e9f00ca`, dotazy jako dřív) nebo 0.5.1 (commit `af41bd2`) a marketplace.
Nouzově odeber `PreToolUse`, `Stop` a `UserPromptSubmit` z `hooks/hooks.json`.

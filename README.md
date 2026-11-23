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
| `pravidla-start.sh` | `SessionStart` | vloží do kontextu obsah `pravidla.txt` (komunikace česky, dokumentace průběžně, nevymýšlej si, hotovo až po ověření, nejdřív výsledek a pak zápis do báze, samostatná práce bez zbytečných dotazů, git, utrácení a volby, citlivé údaje, dílna); běží při startu, obnově i po zhuštění kontextu (bez matcheru); od 0.13.0 po zhuštění (`source` `compact`) přidá připomínku: přečíst stavový soubor, ověřit delegace a budíky, pokračovat bez dotazů |
| `baze-precompact.sh` | `PreCompact` | od 0.13.0 **instrukce pro shrnutí** (stdout PreCompact čte model, který píše shrnutí): zadání Marka doslova, jeho rozhodnutí, hotovo/zbývá/další krok, běžící delegace a budíky s ID, cesta ke stavovému souboru, slepé uličky, co čeká na zápis do báze. Neblokuje (viz „Od 0.13.0“) |
| `pretool-guard.py` | `PreToolUse` | **jediný strážce: okno oprávnění (`ask`) jen na nevratnou ztrátu dat, čtení tajemství a změnu nastavení Claude, ostatní výslovně povolí (`allow`)** (od 0.11.0, viz níže), brána báze a brzda zápisu do báze (od 0.10.0); od 0.12.0 zamítne `Agent` v popředí nebo bez smlouvy a dlouhé `SendMessage` bez smlouvy (dohled, viz níže) |
| `stop-guard.py` | `Stop` | po odpovědi upozorní na „hotovo“ bez příkazu/testu a na `git commit` bez dotčené dokumentace projektu (od 0.10.0; `MAREK_STOP_MODE=block` by blokoval); od 0.12.0 **vždy zablokuje, když je otevřená delegace (subagent, příkaz na pozadí, zadání jiné session) a žádný naplánovaný budík** (modul `dohled.py`, vypínač `MAREK_DOHLED=off`) |
| `dohled-start.py` | `SessionStart` | od 0.12.0: při `resume` a `compact` vypíše otevřené delegace z minula (odvozené z přepisu session), ať je šéf před pokračováním ověří |
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

### Od 0.11.0: plugin jediný strážce, okno jen na nevratnou ztrátu dat (rozhodnutí Marka, 18. 11. 2026)

Agenti běžící bez Marka (v noci) stáli na zbytečných oknech: mazání `__pycache__` a pomocných souborů v pracovním
adresáři agenta v kontejneru (`pct exec 900 … rm /srv/cfd/…`), v `/dev/shm`, v `~/.claude/jobs/<id>/tmp`, `sed -i` na souboru
v gitu. Vedle toho vyskakovala běžná okna Claude Code a projekty si ručně povolovaly příkazy v `settings.local.json`.
Marek: „vyřešit systémově a jednou provždy“. Přepočet na 129 uložených oknech (30. 10.–18. 11. 2026): 0.10.0 by jich
otevřela 74, 0.11.0 jich otevře 34 (vše skutečná data, klíče a nastavení: `/config/.storage` a skripty HA, NAS, Frigate,
skripty v domově mimo git, `~/.claude/settings.json`, `~/.ssh`). Nástroj přepočtu: přehrát `tool_input` a `cwd`
z přepisů session proti `hooks/pretool-guard.py`.

- **Co není rizikové, hook výslovně povolí** (`permissionDecision: "allow"`), takže se neukáže ani běžné okno Claude Code.
  Výjimka: `AskUserQuestion`, `ExitPlanMode`, `EnterPlanMode` (hook mlčí, ať allow neobejde dialog). Vypínač bez nové
  verze: `MAREK_HOOK_ALLOW=off` (chování jako 0.10.0). Chyba skriptu = bez výstupu (bez allow).
  Neověřeno: zda hook `allow` v režimu `auto` přeskočí i klasifikátor; ověřit na první session s 0.11.0.
- **Kořen `/` a `/*` je vždy riziko**; vzdálené `~` = `/home/~`; `cd` na neznámý cíl = neznámý adresář.
- **Mazání a přepis vyvolá okno jen v datovém úložišti a jen když nejde vrátit.**
  - Vratné: `/tmp`, `/var/tmp`, `/dev/shm`, `/run/user/<uid>` (mimo `gvfs` a `doc`), scratchpad, `~/.cache`,
    `~/.claude/jobs/*/tmp`, paměť Claude, adresář projektu (`CLAUDE_PROJECT_DIR` i `cwd`; domov a `/` ne), `__pycache__`
    a `*.pyc` kdekoli; lokálně i soubor sledovaný v gitu a čistý (`git status --porcelain --ignored` prázdné, timeout 3 s).
  - Datová úložiště lokálně: domov, `/home`, `/root`, `/mnt`, `/media`, `/run/media`, `/srv`, gvfs.
  - Vzdáleně (`ssh host '…'`, `pct exec N -- …`, sleduje se `cd`): `/mnt`, `/media`, `/home`, `/srv/dev-disk-*`, `/export`,
    `/var/lib/vz`, `/var/lib/pve`, `/etc/pve`, `/config` (HA); vratné je tam navíc `*.log`, `*.log.N` a každá cesta se
    segmentem obsahujícím `claude` (`/root/claude`, `/config/zalohy-claude`). Jinde (např. `/srv/cfd`, `/opt`) bez okna.
  - Proměnné: dosadí se přiřazení v příkazu a `${X:-výchozí}` (známá hodnota, jinak výchozí); neznámá proměnná rozhodne
    podle pevného začátku cesty, bez něj okno. Od 0.15.1 i proměnná smyčky `for X in SLOVA` (= společný adresář slov
    + `*`, např. `data/*.csv`); se `$(…)` ve slovech zůstane neznámá. Důvod: Winglety 20. 11. 2026, okno „mv do cesty
    s neznámou proměnnou ($f)“ u `for f in data/*_zatizeni.csv; do … mv data/$b.novy $f; done` v projektu.
- Nově hlídá i nástroj `Read` na tajné soubory; `~/.ssh/known_hosts*` je veřejný, zápis do něj se neptá.

`ask` vrací jen pro:
- **(a) nevratnou ztrátu dat:** `rm`, `rmdir`, `unlink`, `shred`, `truncate`, `find -delete`/`-exec rm`, `xargs rm`,
  `rsync --delete` a přepis (`>`, `tee` bez `-a`, cíl `mv`/`cp`/`install`, `sed -i`/`perl -i`) v datovém úložišti, které
  nejde vrátit (viz výše). Destruktivní git (`reset --hard`,
  `clean -f`, `branch -D`, `push --force`, `checkout --`, `restore`, `stash drop|clear`; mimo scratchpad a `/tmp`) a operace
  ničící disky (`mkfs`, `wipefs`, `parted`, `fdisk`, `dd of=/dev/…`, `cryptsetup luksFormat|erase`, `lvremove`…);
- **(b) čtení obsahu tajných souborů** (`.bash_history`, soukromé klíče v `~/.ssh`, `.gnupg`, `.netrc`, `.env` a vzory
  z `~/.config/marek-hooks/tajne.txt`). Od 0.16.1 se u obou klientů kontroluje i vstupní přesměrování (`<`, `0<`)
  a skutečný cíl symbolického odkazu. Neptá se u příkazů, které soubor jen použijí nebo vypíšou jméno (`ssh -i`, `ls`,
  `stat`, `chmod`, `git`…), ani u veřejných částí `~/.ssh` (`config`, `known_hosts`, `*.pub`, `authorized_keys`);
- **(c) změnu nastavení a hooků Claude Code a klíčů:** zápis, úprava i mazání v `~/.claude/settings*.json`, `~/.claude/hooks`,
  `~/.claude/plugins`, `~/.config/marek-hooks`, `/etc/claude-code`, `~/.ssh`, `~/.gnupg` (i přes Edit/Write).

**Bez dotazu:** `sudo` a systémové změny (`dnf`, `systemctl`, zápis do `/etc`, `chmod`, `mount`), `git push`, běhy modelů
a agentů, Edit/Write mimo nastavení Claude (Claude Code je umí vrátit přes checkpoint), `AskUserQuestion`.
Příkazy uvnitř `ssh host '…'` a `pct exec N -- …` se hodnotí podle vzdálených datových úložišť (viz 0.11.0);
tajemství se tam nehodnotí.

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

### Od 0.14.0: stejná pravidla pro Codex a ChatGPT; od 0.15.0 rovnocenná alternativa a křížová kontrola (rozhodnutí Marka, 20. 11. 2026)

**Proč.** Hlavní asistent je Claude; ChatGPT chat a Codex chce Marek používat se stejnými pravidly práce, a to (od 0.15.0)
nejen na jednoduché úkoly, ale jako rovnocennou alternativu se silnými modely (šetří drahé tokeny Claude) a pro
křížovou kontrolu kódu a závěrů Claude. Ruční `~/.codex/AGENTS.md` z 10. 10. 2026 se s pravidly Claude rozešel (ptal se před každou změnou,
zakazoval push i běhy modelů). **Marek zvolil:** úkoly do Codexu a ChatGPT posílá on i Claude; Codex a ChatGPT mají
bázi Second Brain se čtením i zápisem; pravidla Codexu se synchronizují automaticky z pluginu. **Od 0.15.0:** je-li Marek
u práce, přesun do Codexu, model a effort vybírá on (výběrové okno); bez Marka rozhoduje Claude sám. Křížová kontrola
Codexem u významných změn a závěrů. Model se neváže na verzi: nejvyšší verze rodiny z `~/.codex/models_cache.json`
(Astra na analýzu, těžkou práci a kontrolu, Sol na běžnou); effort `medium` na běžnou práci a kódování, `high` na analýzu, diagnostiku, návrh, kontrolu a kód s dopadem. Zákaz Astry
platí dál jen v dílně.

- **`codex/AGENTS.md`:** pravidla pro Codex. Odvozená z `hooks/pravidla.txt` bez částí vázaných na Claude Code (hooky,
  AskUserQuestion, subagenti, CronCreate, dílna) a s rolí Codexu (rovnocenná alternativa pro jednoduchou i těžkou práci; zadání od
  Claude se smlouvou končí `STAV: hotovo/chyba`; při křížové kontrole nezávislé nálezy s doklady) a sekcí Second Brain (`kdo` = `codex-<stroj>`). **Mění se ve stejném
  commitu s `pravidla.txt`.**
- **Rozvoz do Codexu:** 0.14.0–0.16.1 zapisoval plugin pro Claude (`hooks/codex-start.py`) do `~/.codex`. Od 0.17.0 je
  repo zároveň nativní plugin Codexu, viz sekce [Codex](#codex-od-0170-nativní-plugin).
- **`chatgpt/vlastni-pokyny.md`:** text vlastních pokynů ChatGPT (Nastavení → Personalizace → Vlastní pokyny →
  ChatGPT: velké pole pokynů 1 145 znaků, Přezdívka, Více o vás 190 znaků; rozložení podle snímku 20. 11. 2026, limit délky
  neověřen). ChatGPT nemá hooky, text vkládá Marek ručně po každé změně.
- **`pravidla.txt`, sekce „Claude, Codex a ChatGPT“:** Claude Code posílá do Codexu samostatně vymezenou práci,
  hlavně hromadnou a dlouhou; s Markem u práce po jeho volbě, bez něj sám (`codex exec … -m <model> -c model_reasoning_effort=<effort> --dangerously-bypass-approvals-and-sandbox -o <soubor>
  "<zadání>" < /dev/null`, na pozadí, hlídaný jako každá delegace) a výsledek sám zkontroluje; před pushem nebo nasazením
  významné změny a u závěrů s dopadem spustí křížovou kontrolu Codexem (Astra) bez svého zdůvodnění, nálezy ověří a
  u neshody předloží Markovi oba názory. Dostupné modely: `~/.codex/models_cache.json` (20. 11. 2026 obě `gpt-6.2-astra`
  i `gpt-6-astra` odpověděly přes `codex exec -m`).
- **Strážce také v Codexu (od 0.15.2):** původně jen pro Bash. Aktuální instalace a pokrytí jsou v sekci [Codex](#codex-od-0170-nativní-plugin).
- **Báze v Codexu (na každém stroji jednou ručně):** `codex mcp add second-brain --url https://edge.lumatech.cz/mcp`
  (otevře přihlášení OAuth do báze v prohlížeči) a v `~/.codex/config.toml` pod `[mcp_servers.second-brain]` řádek
  `default_tools_approval_mode = "approve"`, jinak `codex exec` volání báze odmítne („vyžaduje schválení, které politika
  ‚never‘ neumožňuje“). Ověřeno 20. 11. 2026 na fedoře (Codex 0.171.0): `codex exec` bez obcházení schválení zavolal
  `pravidla` a `hledej` a vrátil správnou cestu poznámky. **Past:** `codex exec` spuštěný bez `< /dev/null` zůstal viset na
  „Reading additional input from stdin...“.
- **Báze v ChatGPT:** připojuje Marek v ChatGPT (vlastní konektor na `https://edge.lumatech.cz/mcp`, OAuth); postup
  a výsledek v bázi (`hledej` ChatGPT konektor).
- Testy: `tests/test-codex-parita.py` (manifest a hooky pluginu Codexu, úklid staré instalace, pravidla při startu, strážce, brána a brzda, Stop, dohled, ACK).

### Od 0.13.0: navázání po zhuštění kontextu (rozhodnutí Marka, 20. 11. 2026)

**Proč.** Marek chce zadat práci na mnoho hodin a po automatickém zhuštění (autokompakt) pokračovat tam, kde skončila.
**Co platí bez pluginu (ověřeno 20. 11.):** Claude Code ukládá všechny zprávy do přepisu session na disk (JSONL v
`~/.claude/projects/…`); kompakt z něj nic nemaže a shrnutí na přepis odkazuje cestou. Shrnutí samo obsahuje „Current Work“,
„Next Step“ a pokyn pokračovat bez dotazů. Běžící subagenti a budíky (CronCreate) žijí v procesu session, kompakt je neruší
(neověřeno měřením, plyne z toho, že kompakt session nerestartuje).
**Co dělá plugin:**
- **(a) `baze-precompact.sh`:** dokumentace: „`PreCompact`: your stdout becomes instructions for the compaction summary“
  (https://code.claude.com/docs/en/hooks). Text proto říká, co musí shrnutí zachovat (zadání doslova, rozhodnutí, hotovo/zbývá/
  další krok, delegace a budíky s ID, stavový soubor, slepé uličky, co čeká na zápis do báze). Do 0.12.0 tu bylo „zapiš teď do
  báze“, což shrnující model udělat nemůže (nevolá nástroje).
- **(b) `pravidla.txt`, sekce „Dlouhá práce a zhuštění kontextu“:** práce nad hodinu vede `HANDOFF.md` v kořeni projektu a
  aktualizuje ho po každém kroku; přežije i pád session, nejen kompakt.
- **(c) `pravidla-start.sh`:** při `source` `compact` přidá připomínku: přečíst stavový soubor, ověřit delegace a budíky
  (CronList), pokračovat bez dotazů, detaily hledat v přepisu. Otevřené delegace vypíše `dohled-start.py` (0.12.0).
- PostCompact hook se nepoužívá: podle dokumentace nemá vliv na výsledek kompaktu a shrnutí je v přepisu tak jako tak.
**Testy:** `tests/test-dohled.py` (compact → připomínka; startup/resume/clear bez ní; prázdný vstup; text PreCompact bez pokynu
k zápisu a pod limitem 10 000 znaků).

### Od 0.12.0: dohled nad delegovanou prací (rozhodnutí Marka, 19. 11. 2026)

**Proč.** V noci 18./19. 11. (projekt Winglet) řídící session delegovala sérii výpočtů, všech 6 variant spadlo a server od 7:11
stál. Nikdo to nehlídal: jediná „kontrola“ byla smyčka čekající na soubor s jiným jménem, než jaké výsledek dostal. Stejná chyba
hrozí všude, kde šéf deleguje (subagenti, agenti jiných session, procesy na pozadí): podřízený potichu stojí a nikdo se to nedozví.
Cíl není 100 % spolehlivost, ale aby žádná delegovaná práce nestála nepozorovaně déle než 30 min (šéf ji opraví, nebo dostane
Marek notifikaci). Návrh: `NAVRH_dohled_agentu.md` (session Winglety), schválený rozsah A + B1–B4 (B3 zúžené podle Marka); B5 (signál
pro vnějšího hlídače) a C (ntfy, vnější hlídač) se nedělají.

**Co přibylo.**
- **A, `pravidla.txt`: sekce „Kdo deleguje, ten hlídá“.** Zadání má HOTOVO / ODHAD / SIGNÁL / PŘI CHYBĚ; každý subagent běží na pozadí;
  budík `CronCreate` (nejvýš po 15 min) se zakládá s první otevřenou delegací a ruší po poslední; při probuzení šéf kontroluje skutečný
  stav (u subagenta `stat` jeho výstupního souboru, beze změny déle než 15 min = stojí); nejde-li to vyřešit, píše Markovi přes
  `PushNotification` (nativní notifikace Claude na telefon přes Remote Control; ne ntfy).
- **B1 + B2, `stop-guard.py` + sdílený modul `hooks/dohled.py`: Stop blokuje, když je otevřená delegace a žádný budík.**
  Kniha delegací se **nevede v souboru ani novými hooky**; Stop ji při každém volání odvodí z přepisu session (`transcript_path`).
  Blok je vždy `decision: block`, i při `MAREK_STOP_MODE=advisory`; při `stop_hook_active` hook mlčí (žádná smyčka).
  - *Otevřená delegace:* (a) `Agent`, který se opravdu spustil na pozadí (`toolUseResult.status == "async_launched"`);
    parametr `run_in_background` se od 0.17.1 nevyžaduje, jen výslovné `false` znamená popředí a nesleduje se; (b) `Bash` s `run_in_background` true (`toolUseResult.backgroundTaskId`);
    (c) `SendMessage` jiné session (`recipient_kind` `session` nebo `name`, ne `main`, ne `agent`), jehož `message` obsahuje
    `HOTOVO:` a nezačíná `[ACK]`, `STAV:` ani `ODPOVĚĎ:`.
  - *Uzavření:* `<task-notification>` se stavem `completed`/`failed`/`killed`/`stopped` (user záznam i attachment `queued_command`),
    mezitímní oznámení („is waiting on its own background work“, „has not reported yet“) neuzavírá; sběrné oznámení po restartu
    („didn't finish before the previous session ended“, víc `<task-id>`, `status stopped`) uzavře všechna uvedená ID; `TaskStop` s ID
    (i když skončí chybou „not running“, úloha už neběží); u (c) příchozí zpráva od téže session (`origin.from` nebo `origin.name` =
    adresát) obsahující `STAV: hotovo` / `STAV: zrušeno`, nebo vlastní odchozí zpráva tomuto adresátovi začínající `STAV: zrušeno`.
  - *Aktivní budík:* `CronCreate` recurring (výchozí true) nesmazaný `CronDelete` a mladší než 7 dní (po 7 dnech ho Claude Code
    ruší sám), nebo one-shot nesmazaný s `nextFireAt` v budoucnosti. Interval se nekontroluje (pravidlo „nejvýš po 15 min“ je v textu
    pravidel, ne v hooku).
  - *Výkon:* přepis se čte po řádcích jako bajty a JSON se parsuje jen u řádků s klíčovými slovy; 377 MB přepis 0,5 s, 77 MB
    syntetický 0,05 s; rozpočet 1 s, po jeho překročení nebo při chybě fail-open (nic se neblokuje). Nedopsaný poslední řádek se přeskočí.
- **B3, `pretool-guard.py`: zadání musí mít smlouvu.** `Agent` (jakýkoli `subagent_type`, i volaný subagentem) musí mít
  prompt s `HOTOVO:` i `PŘI CHYBĚ:` a nesmí mít `run_in_background: false`, jinak `deny` („Subagent musí běžet na pozadí … Agent
  v popředí blokuje tah a během něj se nespustí žádný budík, takže by ho nikdo nehlídal“). Chybí-li `run_in_background`, hook ho
  od 0.17.1 doplní na `true` (`updatedInput`) a volání povolí; dřív ho zamítal, viz [0.17.1](#0171). Důvod (Marek): i krátký subagent může běžet hodiny;
  agent v popředí drží tah šéfa a `CronCreate` se spouští jen při nečinnosti. `SendMessage` delší než 300 znaků musí obsahovat oba
  štítky, jinak `deny` („Zadání bez smlouvy … začni zprávu STAV: nebo ODPOVĚĎ:“); výjimky: `[ACK]`, `STAV:`, `ODPOVĚĎ:` na začátku,
  `to` = `main`, nestringová zpráva. Zbytek `pretool-guard.py` (0.11.0) beze změny.
- **B4, `dohled-start.py` (SessionStart):** při `source` `resume` a `compact` projde přepis toutéž funkcí a vypíše „Otevřené delegace
  z minula: … – ověř jejich stav, než budeš pokračovat.“ Při `startup`/`clear` mlčí. Budík se tu nezohledňuje (po restartu je mrtvý).
- **Vypínač:** `MAREK_DOHLED=off` vypne vše (Stop, PreToolUse i SessionStart).

**Odkud jsou ověřené tvary** (skutečné přepisy `~/.claude/projects/*/*.jsonl` z 26. 10. až 19. 11. 2026, Claude Code 2.1.327; sessions
Winglet `1efe5b0c…`, `b406091a…`, `af1c44aa…`, `394fc24e…`, `24b4069d…`):
- `Agent` tool_use: `input.run_in_background` je v přepisu **řetězec `"true"`** i bool; výsledek: záznam `user` s `toolUseResult`
  `{isAsync, status: "async_launched", agentId, outputFile, …}` a textem „Async agent launched successfully … agentId: …“.
- `Bash` tool_use s `run_in_background: true`; výsledek: `toolUseResult.backgroundTaskId` a text „Command running in background with ID: …“.
  Příkaz, který přesáhl 120 s a Claude Code ho sám přesunul na pozadí („was moved to the background“), se **nesleduje** (v tool_use
  není `run_in_background`).
- `<task-notification>`: `<task-id>`, `<tool-use-id>`, `<output-file>`, `<status>`, `<summary>`, `<result>`; v přepisu jako `user` (obsah
  řetězec, `origin.kind: task-notification`), jako `attachment` (`queued_command`, `commandMode: task-notification`) a jako
  `queue-operation` (ten se ignoruje, je to jen fronta). Stavy v přepisech: completed, failed, killed, stopped.
- `CronCreate`: `input {cron, prompt, recurring}`; výsledek `toolUseResult {id, humanSchedule, recurring, durable, nextFireAt}`
  (`nextFireAt` v ms), text „Scheduled one-shot task …“ / „Scheduled recurring job … Auto-expires after 7 days“. `CronDelete`:
  `input.id`, výsledek „Cancelled job …“. `TaskStop`: `input.task_id`.
- `SendMessage`: `input {to, message, summary, type, recipient, recipient_kind (session|name|agent), content}`; `content` je zkrácená
  kopie, proto se čte `message`; výsledek `toolUseResult {success, msg_id}`. Příchozí zpráva od jiné session: záznam `user` (`isMeta`)
  nebo `attachment` s `origin {kind: "peer", from, name, fromMode, body}`; text obaluje `<cross-session-message from=… from-name=…>`.

**Neověřeno / omezení.**
- `ScheduleWakeup` se **nezohledňuje**: v žádném z přepisů na tomto stroji není jeho `tool_use` (jen ve výpisech nástrojů), tvar neznáme.
- Zda `CronCreate` budí session spolehlivě i během dlouhé nečinnosti a při uspaném notebooku (návrh počítal s vrstvou C, která se nedělá).
- Zda je při `resume` `transcript_path` souborem, který obsahuje i starý průběh. V přepisech se resume jeví jako pokračování téhož souboru
  (sběrné oznámení „didn't finish before the previous session ended“ je v něm hned za restartem), ale přímo ze SessionStart hooku
  to neověřeno; nenajde-li hook historii, mlčí.
- Recurring budík vytvořený před restartem session se v přepisu tváří jako aktivní, i když je po restartu mrtvý (session-only);
  Stop pak neblokuje (chyba je ve směru fail-open).
- Delegace podřízeným v jiné session se páruje jen podle adresy/jména odesílatele: odpoví-li peer z jiné adresy než `to` (např. zadání
  přes `uds:`, odpověď z `bridge:` bez shodného jména), delegace se neuzavře samočinně; uzavře se `STAV: zrušeno` odchozí zprávou.
  Zprávy subagentům (`recipient_kind: agent`) se nesledují.
- Zda hooky vidí zprávy od peerů během běžícího tahu (týká se jen `ack-guard.py`, dohled čte přepis).
- Tvary byly ověřeny na přepisech hlavní session; přepisy subagentů (`…/subagents/agent-*.jsonl`) se nepoužívají.

Testy: `python3 tests/test-dohled.py` (60 případů nad syntetickými přepisy ve výše uvedeném tvaru; Stop, SessionStart, výkon, skutečné přepisy),
doplněné případy v `tests/test-hooks.py` (Agent, SendMessage) a `tests/test-stop.py`.

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

Testy bez modelu: `python3 tests/test-hooks.py`, `python3 tests/test-stop.py`, `python3 tests/test-ack.py`, `python3 tests/test-dohled.py`, `python3 tests/test-statusline-start.py`.

Vrácení: obnovit verzi 0.7.0 (commit `f1d458b`), 0.6.0 (commit `e9f00ca`, dotazy jako dřív) nebo 0.5.1 (commit `af41bd2`) a marketplace.
Nouzově odeber `PreToolUse`, `Stop` a `UserPromptSubmit` z `hooks/hooks.json`.

## Codex (od 0.17.0: nativní plugin)

**Proč (Marek, 22. 11. 2026):** Codex má být samostatný, nezávislý na Claude Code a sám se aktualizovat.
0.14.0–0.16.1 instaloval pravidla a hooky do `~/.codex` plugin pro Claude (SessionStart `codex-start.py`,
nebo ručně `--install` z klonu repa); bez běžícího Claude Code se Codex neaktualizoval.

**Jak:** Codex 0.171.0 umí pluginy z Git marketplace i s hooky (zdroj `codex-rs/core-plugins/src/manifest.rs`,
pole `hooks`) a marketplace z Gitu při každém startu na pozadí sám aktualizuje (`manager.rs`,
`plugins-marketplace-auto-upgrade`, `PluginGitMode::Automatic`). Manifest hledá v pořadí `.codex-plugin/plugin.json`,
`.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json` (`exec-server-protocol/src/protocol.rs`), marketplace čte i z `.claude-plugin/marketplace.json`.
Repo je proto plugin pro oba klienty: Claude čte `.claude-plugin/plugin.json` a `hooks/hooks.json`, Codex
`.codex-plugin/plugin.json` a `hooks/codex-hooks.json`. Skripty jsou společné, Codex je spouští s `MAREK_HOOK_KLIENT=codex`
přes `${PLUGIN_ROOT}` (Codex nastavuje hookům pluginu `PLUGIN_ROOT` i `CLAUDE_PLUGIN_ROOT`, `hooks/src/engine/discovery.rs`). Verze v obou manifestech je stejná.

**Instalace (na každém stroji jednou, bez Claude Code):**

```sh
codex plugin marketplace add CZIceman/cc-hooks-plugin
codex plugin add marek-cc-hooks@marek-hooks
```

Pak nová relace Codexu: schválit hooky pluginu (okno „Hooks need review“ → „Trust all and continue“, nebo `/hooks`);
neschválené hooky neběží. Další verze stáhne Codex sám při startu; změněné hooky chtějí nové schválení.
Ruční aktualizace: `codex plugin marketplace upgrade marek-hooks`. Báze Second Brain se v Codexu připojuje zvlášť (viz výše).

**Pravidla** vkládá hook `pravidla-start.sh` při každém startu: `codex/AGENTS.md` (bez řádku s komentářem) + místní
doplněk `~/.config/marek-hooks/codex-mistni.md`. Do `~/.codex/AGENTS.md` se nic nezapisuje; vlastní ruční pokyny
v něm zůstanou a Codex je načte vedle pravidel pluginu.

**Úklid staré instalace (`hooks/codex-uklid.py`, SessionStart):** z `~/.codex/hooks.json` odebere jen naše záznamy
`env MAREK_HOOK_KLIENT=codex … <CODEX_HOME>/marek-hooks/…` (cizí zůstanou), smaže `~/.codex/AGENTS.md` se značkou
„Generuje plugin marek-cc-hooks“ (ruční soubor zůstane) a adresář `~/.codex/marek-hooks/`, ten až při dalším startu:
Codex načte `hooks.json` před hooky, takže v první relaci staré záznamy ještě běží (vedle nových) a jejich skripty
musí existovat. Ověřeno živě 22. 11. 2026 (Codex 0.171.0, izolovaný `CODEX_HOME`): první relace staré záznamy a
`AGENTS.md` odebrala (Codex ohlásil „The previously provided AGENTS.md instructions no longer apply“), druhá smazala
`marek-hooks/`; všechny tři hooky SessionStart `Completed`, v kontextu připomínka báze i pravidla, `rm ~/Dokumenty/…`
zamítnut s příkazem `!rm …` pro Marka. Claude plugin do `~/.codex` od 0.17.0 nesahá. Starší běžící session Claude
(do 0.16.1) ale při zhuštění kontextu starou instalaci znovu zapíšou; další start Codexu ji zase uklidí.

**Past:** výstup hooku SessionStart, který začíná `[` (nebo `{`), bere Codex jako JSON; když JSON není, hook skončí
„Failed“ a text se do kontextu nedostane. `baze-start.sh` proto v Codexu začíná `# Znalostní báze Second Brain`.

| Kdy | Chování Codexu |
|---|---|
| `SessionStart` | Připomene bázi. Při `compact` připomene `HANDOFF.md`, při obnově a zhuštění upozorní na otevřené delegace zaznamenané v přepisu. |
| `PreToolUse`, `PermissionRequest` | Bash, `apply_patch` a podporované souborové MCP nástroje používají stejná pravidla pro citlivé cesty. Strážce kontroluje i konfiguraci a přihlašovací soubory Codexu (`~/.codex/{AGENTS.md,auth.json,config.toml,hooks.json,marek-hooks,rules,plugins}` a `/etc/codex`). Codex z `PreToolUse` schvalovací okno nevyvolá, rizikovou akci proto zamítne. `PermissionRequest` schvaluje dosavadní nerizikové Bash případy. Ostatní typy ponechá Codexu. Kontrola se vztahuje na volání dostupná hookům a shell zkoumá jen jako text. |
| Brána a brzda báze | Úspěšné `pravidla` zaznamená `PostToolUse`. V izolovaném běhu Codexu 0.171.0 s testovacím MCP předal klient hooku jméno `mcp__second_brain__pravidla`. Brána uvolní práci po dvou zamítnutích. Brzda `zapis` zachovává stávající výjimky včetně opakovaného volání a nedostupného přepisu (viz výše). |
| `PreCompact` | Codex hookem neposkytuje instrukce modelu, který shrnuje. K navázání slouží `HANDOFF.md` a `SessionStart` po zhuštění. |
| `Stop` | Upozornění „hotovo“ bez ověření a commit bez dokumentace hlásí přes `systemMessage`. Je-li v přepisu známá otevřená delegace, požádá o pokračování a kontrolu podle ID. Pojistka proti opakování ponechává kontrolu na jeden pokus. |
| `UserPromptSubmit` | Při předání přes `codex queue` může zpráva nést níže uvedený obal pro ACK. Nativní zprávy mezi subagenty tímto hookem neprocházejí. |
| Stavová řádka | Použij nativní `/statusline`, např. kontext, pětihodinový a týdenní limit a větev Git. |
| Delegace | Subagent má smlouvu a rodič sleduje stav podle jeho ID. U příkazů zůstává k dispozici ID terminálové relace, pokud ho Codex uvede v přepisu. Stav dřívější delegace je při obnově nutné ověřit. V samotném CLI se neregistruje pravidelný budík. |

Pro místní předání přes textový vstup má obal první řádek
`<codex-peer from="UUID odesílatele" id="UUID zprávy">`, následuje text a
samostatný řádek `</codex-peer>`. Hook vloží pokyn k potvrzení `[ACK]` s ID původní
zprávy. Odeslání přes `codex queue` patří jen do výslovně povolené komunikace.
Tvrzený odesílatel v obalu sám neověřuje identitu. Zprávy přes ntfy se řídí místními
pravidly dané relace.

### 0.17.2

- **Deník do projektu, poučení do báze** (rozhodnutí Marka 23. 11. 2026). Měření báze ukázalo 47 poznámek přepsaných víc než
  10× (nejvíc 63×), které sloužily jako deník nebo dokumentace projektu. Příčina: hranice v pravidlech chyběla a `pravidla.txt`
  s bází jako dokumentací projektu přímo počítal („ani když je báze dokumentací projektu“).
- Nová sekce `pravidla.txt` „Deník do projektu, poučení do báze“: rozhoduje, kdo to bude číst. Deník práce (stav, plán, otevřené
  body, průběh, měření z jednotlivých dnů, zadání) patří do projektu (`HANDOFF.md`, README, dokumentace v gitu); do báze jen to,
  co potřebuje někdo jiný a co platí i po skončení práce (poučení, rozhodnutí s důvody, postupy, popis systému) a rozcestník
  projektu. Výjimka na Markův pokyn: krátký seznam otevřených bodů v bázi. Totéž zkráceně v `codex/AGENTS.md`,
  `chatgpt/vlastni-pokyny.md` a v připomínce `baze-start.sh`.
- Pravidlo hooky nevynucují. Odmítnutí nové poznámky s datem v názvu souboru na serveru báze je zadané session edge (23. 11. 2026, při vydání 0.17.2 nenasazeno).
- Marek: po změně `chatgpt/vlastni-pokyny.md` vložit nový text do ChatGPT ručně; profil claude.ai doplnit o novou sekci.

### 0.17.1

- **Oprava: hook zamítal každého subagenta.** `pretool-guard.py` od 0.12.0 vyžadoval u nástroje `Agent` parametr
  `run_in_background: true`. Claude Code ale parametr z nástroje někdy odebírá (režim „fork“: schéma ho nemá, agent běží vždy
  na pozadí) a hodnotu poslanou modelem zahodí dřív, než ji hook uvidí. Zjištěno 23. 11. 2026 v session na Fable 5.2
  (Claude Code 2.1.329): čtyři volání `Agent` zamítnuta, dvě z nich měla v přepisu `run_in_background: "true"`. O režimu rozhoduje
  brána v Claude Code (`CLAUDE_CODE_FORK_SUBAGENT`, příznak na straně Anthropic), ne verze; hook ji nevidí.
- **Nové pravidlo:** smlouva (`HOTOVO:`, `PŘI CHYBĚ:`) se vyžaduje dál; `run_in_background: false` = `deny`; chybějící parametr
  hook doplní na `true` přes `updatedInput` a volání povolí. `dohled.py` pozná agenta na pozadí podle výsledku spuštění
  (`async_launched`), ne podle parametru, jinak by Stop hook delegace v režimu bez parametru nehlídal.
- **Ověřeno živě** (23. 11. 2026, Claude Code 2.1.330, `claude -p` ve zkušebním projektu s hookem z repa): Fable 5.2 i Opus 5.5
  bez parametru → hook vrátil `allow` + `updatedInput`, výsledek „Async agent launched successfully“, žádná chyba kvůli klíči navíc.
  **Neověřeno:** že `updatedInput` vynutí pozadí tam, kde by agent bez parametru běžel v popředí. Kontrolní běh Opus 5.5 bez
  hooku spustil agenta na pozadí taky, režim s výchozím popředím (19. 11. 2026) se 23. 11. nepodařilo navodit.
- **Slepá ulička:** poznat z přepisu, co model poslal, nejde. Volání nástroje se do přepisu zapíše až po hooku `PreToolUse`
  (ověřeno značkou v příkazu: 0 výskytů v přepisu ve chvíli běhu nástroje).

### 0.17.0

- Nativní plugin Codexu (`.codex-plugin/plugin.json`, `hooks/codex-hooks.json`), aktualizace z GitHubu sama.
- `hooks/codex-start.py` a `tests/test-codex-start.py` odebrány, Claude plugin do `~/.codex` nesahá; nový `hooks/codex-uklid.py`.
- Pravidla Codexu vkládá `pravidla-start.sh`; `baze-start.sh` v Codexu bez úvodní `[`.

Před nasazením projdi stávající testy v `tests/` a `python3 tests/test-codex-parita.py`.
Pro izolované živé ověření důvěry použij `codex exec --dangerously-bypass-hook-trust … < /dev/null`
nad předem zkontrolovanými testovacími hooky. Běžná relace používá schválení přes
`/hooks`. Pro brzdu zápisu, dohled a kontrolu dokončení musí mít relace přepis. V Codexu 0.171.0 výstup `exec --json` nezahrnuje zprávy o běhu hooků.

### 0.16.1

- Sdílený strážce používá stejné kontroly vstupního přesměrování a symbolických odkazů u obou klientů.
- Aktualizace Codexu zálohuje jen původní uživatelskou konfiguraci podle pravidel výše.
- Při zamítnutí Codex uvede jednou větou co a proč a přidá přesný příkaz pro Marka nebo popis ruční úpravy.
  Ručně zadaný `!příkaz` v TUI podléhá platným oprávněním. [Klávesové zkratky CLI](https://learn.chatgpt.com/docs/cli/reference#interactive-shortcuts)
- Místní přepisy obsahují `collaboration.spawn_agent` s polem `message`. U nativního
  `spawn_agent` strážce ověřuje smlouvu také ve strukturovaném vstupu `items`, který podporuje
  Codex v1. [Schéma nástroje](https://github.com/openai/codex/blob/rust-v0.171.0/codex-rs/core/src/tools/handlers/multi_agents_spec.rs#L571-L580)
- Pole `agent_id` ve vstupu `PreToolUse` pro nativního subagenta potvrzuje zdroj Codexu 0.171.0.
  Prohlédnuté přepisy neobsahovaly vstup tohoto hooku od subagenta. [Zdroj Codexu](https://github.com/openai/codex/blob/rust-v0.171.0/codex-rs/core/src/hook_runtime.rs#L207-L210), [jen u subagenta](https://github.com/openai/codex/blob/rust-v0.171.0/codex-rs/core/src/hook_runtime.rs#L1088-L1106)

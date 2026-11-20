#!/usr/bin/env python3
"""PreToolUse hook (marek-cc-hooks 0.12.0) — plugin je jediný strážce: rizikové ptá, ostatní výslovně povolí.

Rozhodnutí Marka 18. 11. 2026 (0.11.0): „vyřešit systémově a jednou provždy“. Agenti, kteří běží bez člověka
(v noci), se zastavovali na zbytečných oknech: za 3 týdny 65 oken, skoro všechna zbytečná (pracovní adresář agenta
v kontejneru, dočasné složky, soubor v gitu). Navíc vedle oken hooku vyskakovala běžná okna Claude Code.

Princip: souhlas nehlídá model, ale okno oprávnění Claude Code. Rizikovou akci hook vrátí jako
permissionDecision "ask" (Marek potvrdí). Co rizikové není, hook od 0.11.0 VÝSLOVNĚ POVOLÍ ("allow"),
takže se neukáže ani běžné okno Claude Code. Výjimka: interaktivní nástroje (AskUserQuestion, ExitPlanMode,
EnterPlanMode) hook nechává bez výstupu, ať allow neobejde dialog s uživatelem. Vypínač: MAREK_HOOK_ALLOW=off
(pak se allow nevypisuje, chování jako do 0.10.0). Chyba skriptu = exit 0 bez výstupu (bez allow).

Okno (ask) jen na:
  (a) NEVRATNOU ZTRÁTU DAT: mazání/přepis cesty, která leží v datovém úložišti A NEJDE VRÁTIT.
      Vratné: dočasné složky (/tmp, /var/tmp, /dev/shm, /run/user/N kromě gvfs a doc), ~/.cache, scratchpad,
      ~/.claude/jobs/*/tmp, paměť Claude, adresář projektu, __pycache__ a *.pyc, lokálně i čistý sledovaný soubor
      v git pracovní kopii. Datová úložiště lokálně: domov, /home, /root, /mnt, /media, /run/media, /srv, gvfs;
      vzdáleně (ssh, pct exec): /mnt, /media, /home, /srv/dev-disk-*, /export, /var/lib/vz, /var/lib/pve, /etc/pve,
      /config; vzdáleně je navíc vratný log (*.log, *.log.N) a cesta se segmentem „claude“.
      Mimo datová úložiště (lokálně /opt, /etc, vzdáleně /srv/cfd, /root…) se mazání neptá.
      Dále destruktivní git (mimo scratchpad a /tmp) a operace s disky, které ničí data;
  (b) čtení obsahu tajných souborů (klíče, historie, tokeny), Bash i nástroj Read;
  (c) změnu nastavení a hooků Claude Code (~/.claude/settings*, hooks, plugins, ~/.config/marek-hooks,
      /etc/claude-code) a klíčů (.ssh, .gnupg); výjimka: ~/.ssh/known_hosts* je veřejný soubor.
Systémové změny (sudo, dnf, systemctl, zápis do /etc), push a běhy modelů se neptají.
Od 0.10.0 navíc brzda zápisu do báze: `zapis` v tahu, kde se pracovalo, se poprvé zamítne (nejdřív výsledek
Markovi, pak zápis; rozhodnutí Marka 14. 11. 2026). Podrobnosti u kódu brzdy.
Zahazování otázek AskUserQuestion podle textu (0.7.0) je zrušené: kdy se ptát, určují pravidla.
Od 0.12.0 navíc dohled nad delegací: Agent musí běžet na pozadí a mít smlouvu (HOTOVO:, PŘI CHYBĚ:), dlouhá zpráva
jiné session (SendMessage nad 300 znaků) také; jinak deny. Vypínač MAREK_DOHLED=off. Viz blok „dohled“ u kódu.

Hodnotí se jen to, co shell skutečně spustí: příkaz se rozloží na jednoduché příkazy, těla heredoců
se přeskočí, řetězce zůstanou jedním slovem (slovo „rm“ v echo/grep nebo v kódu Pythonu nevadí),
`sudo`, `timeout`, `env`, `bash -c '…'` se rozbalí, jednoduchá přiřazení (S=…; rm $S/x) se dosadí.
Příkazy uvnitř `ssh host …` a `pct exec N -- …` běží jinde (vzdálená pravidla, sleduje se `cd` od „/“).
Kód skriptů (python3 -c, heredoc) se nehodnotí.
"""
import glob, json, os, re, shlex, subprocess, sys, time

# Chyba skriptu = akce pokračuje (exit 0 bez výstupu, bez allow).
sys.excepthook = lambda *a: os._exit(0)


def out(decision, reason):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
          "permissionDecision": decision, "permissionDecisionReason": reason}}, ensure_ascii=False))
    sys.exit(0)


# Interaktivní nástroje: allow by mohlo obejít dialog s uživatelem, hook u nich mlčí.
INTERACTIVE = ("AskUserQuestion", "ExitPlanMode", "EnterPlanMode")
HOOK_ALLOW = os.environ.get("MAREK_HOOK_ALLOW", "on") != "off"


def finish():
    """Nic rizikového nenalezeno: výslovné povolení (plugin je jediný strážce), jinak mlčení."""
    if HOOK_ALLOW and tool not in INTERACTIVE:
        out("allow", "marek-cc-hooks: bez rizika")
    sys.exit(0)


try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)
if not isinstance(d, dict):
    sys.exit(0)

tool = d.get("tool_name", "")
ti = d.get("tool_input") or {}
sid = d.get("session_id", "x")
scratch = d.get("scratchpad_dir") or ""
home = os.path.realpath(os.path.expanduser("~"))

# Adresáře projektu = CLAUDE_PROJECT_DIR (kde session začala) a aktuální cwd (mění se po `cd`);
# domovský adresář a "/" za projekt nepovažujeme.
cwd = d.get("cwd") or ""
projs = []
for _p in (os.environ.get("CLAUDE_PROJECT_DIR") or "", cwd):
    _rc = os.path.realpath(_p) if _p else ""
    if _rc and _rc not in ("/", home) and _rc not in projs:
        projs.append(_rc)

# ---------- brána báze: nejdřív `pravidla` (jednou za session) ----------
# Subagenti se nehlídají. Po 2 zamítnutích brána povolí (konektor nemusí být dostupný).
if not d.get("agent_id"):
    st = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "marek-hooks")
    os.makedirs(st, exist_ok=True)
    f = os.path.join(st, re.sub(r"[^A-Za-z0-9_-]", "", sid) + ".baze")
    if "Second_Brain__pravidla" in tool:
        open(f, "w").write("ok")
    elif not os.path.exists(f):
        free = tool in ("ToolSearch", "AskUserQuestion", "ReadNotifications") or "Second_Brain" in tool
        if not free:
            n = int(open(f + ".n").read() or 0) if os.path.exists(f + ".n") else 0
            if n < 2:
                open(f + ".n", "w").write(str(n + 1))
                out("deny", "Pravidlo báze: než začneš cokoli řešit, zavolej `pravidla` (a `hledej`). "
                    "Nástroje načti přes ToolSearch (dotaz „Second Brain“).")

    # ---------- brzda zápisu do báze (0.10.0): nejdřív výsledek Markovi, pak `zapis` ----------
    # V tahu, kde se pracovalo (běžel i jiný nástroj než báze), se první `zapis` zamítne. Projde, když
    # Marek o zápis v poslední zprávě výslovně požádal, nebo při opakovaném volání v témže tahu (session
    # bez Marka). Subagenti se nehlídají. Vypnutí: MAREK_ZAPIS_BRZDA=off. Nejde-li přepis přečíst, zápis projde.
    if "Second_Brain__zapis" in tool and os.environ.get("MAREK_ZAPIS_BRZDA", "on") != "off":
        turn_id, worked, asked = "", False, False
        try:
            for n, line in enumerate(open(d.get("transcript_path") or "", encoding="utf-8")):
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                m = r.get("message")
                if not isinstance(m, dict):
                    continue
                c = m.get("content")
                if r.get("type") == "user":
                    txt = c if isinstance(c, str) else " ".join(
                        b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text") \
                        if isinstance(c, list) else ""
                    if txt or (isinstance(c, list) and any(isinstance(b, dict) and b.get("type") == "image" for b in c)):
                        turn_id, worked = str(r.get("uuid") or n), False
                        asked = bool(re.search(r"zapi[sš]|zapsat|do b[aá]ze|v[yý]tah", txt, re.I))
                elif r.get("type") == "assistant" and isinstance(c, list):
                    for b in c:
                        if isinstance(b, dict) and b.get("type") == "tool_use" and "Second_Brain" not in b.get("name", "") \
                                and b.get("name") not in ("ToolSearch", "AskUserQuestion", "ReadNotifications"):
                            worked = True
        except Exception:
            worked = False
        if worked and not asked:
            zf = os.path.join(st, re.sub(r"[^A-Za-z0-9_-]", "", sid) + ".zapis")
            if (open(zf).read() if os.path.exists(zf) else None) != turn_id:
                open(zf, "w").write(turn_id)
                out("deny", "Pravidlo: nejdřív výsledek předlož Markovi, do báze zapiš až po jeho reakci, jednou za téma. "
                    "V tomto tahu se pracovalo, zápis proto odlož a na konec hlášení napiš jedním řádkem, co a kam zapíšeš. "
                    "Výjimka: session běží bez Marka (naplánovaná úloha, práce pro řídící session); pak volání zopakuj, projde.")

# ---------- dohled nad delegovanou prací (0.12.0): zadání musí mít smlouvu ----------
# Agent: VŽDY run_in_background true (jakýkoli subagent_type) a prompt s „HOTOVO:“ i „PŘI CHYBĚ:“. Agent v popředí
# drží tah šéfa a budík (CronCreate) se spouští jen při nečinnosti, zaseknutého by nikdo nehlídal (Marek 19. 11.).
# SendMessage nad 300 znaků musí mít oba štítky, kromě zpráv začínajících [ACK] / STAV: / ODPOVĚĎ: a zpráv „main“.
# Vypínač: MAREK_DOHLED=off.
if os.environ.get("MAREK_DOHLED", "on").strip().lower() != "off":
    if tool == "Agent":
        _bg = ti.get("run_in_background")
        _bg = _bg is True or (isinstance(_bg, str) and _bg.strip().lower() == "true")
        _pr = ti.get("prompt") if isinstance(ti.get("prompt"), str) else ""
        if not _bg or "HOTOVO:" not in _pr or "PŘI CHYBĚ:" not in _pr:
            out("deny", "Subagent musí běžet na pozadí (run_in_background: true) a mít smlouvu HOTOVO, ODHAD, SIGNÁL, "
                "PŘI CHYBĚ. Agent v popředí blokuje tah a během něj se nespustí žádný budík, takže by ho nikdo nehlídal.")
    elif tool == "SendMessage":
        _m = ti.get("message")
        if isinstance(_m, str) and len(_m) > 300 and str(ti.get("to", "")).lower() != "main" \
                and not _m.lstrip().startswith(("[ACK]", "STAV:", "ODPOVĚĎ:")) \
                and not ("HOTOVO:" in _m and "PŘI CHYBĚ:" in _m):
            out("deny", "Zadání bez smlouvy (HOTOVO, ODHAD, SIGNÁL, PŘI CHYBĚ) – doplň je, nebo pokud jde o hlášení "
                "či odpověď, začni zprávu STAV: nebo ODPOVĚĎ:.")

# ---------- místa ----------
def under(p, base):
    return bool(base) and (p == base or p.startswith(base.rstrip("/") + "/"))

# Nastavení a hooky Claude Code a klíče: každý zápis i mazání se ptá.
PROTECT = [r"^%s/\.claude/(settings[^/]*\.json|hooks|plugins)(/|$)" % re.escape(home),
           r"^%s/\.config/marek-hooks(/|$)" % re.escape(home),
           r"^/etc/claude-code(/|$)", r"/\.ssh(/|$)", r"/\.gnupg(/|$)"]
# Veřejný soubor, zápis do něj (ssh přidává hostitele) se neptá.
KNOWN_HOSTS = re.compile(r"/\.ssh/known_hosts[^/]*$")
# Datová úložiště lokálně: domovský adresář a připojená úložiště (gvfs viz in_data).
DATA = [home, "/home", "/root", "/mnt", "/media", "/run/media", "/srv"]
# Datová úložiště vzdáleně (ssh, pct exec): NAS/OMV, domovy, Proxmox, Home Assistant.
DATA_REMOTE = [r"^/(mnt|media|home|export|config)(/|$)", r"^/srv/dev-disk-[^/]*(/|$)",
               r"^/var/lib/(vz|pve)(/|$)", r"^/etc/pve(/|$)"]

def protected(p):
    return not KNOWN_HOSTS.search(p) and any(re.search(x, p) for x in PROTECT)

def in_data(p, remote=False):
    if p == "/" or p.startswith("/*"):
        return True  # kořen (rm -rf /, /*) je vždy riziko
    if remote:
        return any(re.search(x, p) for x in DATA_REMOTE)
    return any(under(p, b) for b in DATA) or bool(re.match(r"^/run/user/\d+/gvfs/", p))

_git_cache = {}

def git_clean(p):
    """Lokálně: cesta (i glob) je v git pracovní kopii sledovaná a čistá, tedy jde vrátit z gitu.
    Čisté = `git status --porcelain --ignored` prázdné (nebo jen __pycache__/.pyc). Chyba či timeout = False."""
    if p not in _git_cache:
        try:
            _git_cache[p] = _git_clean(p)
        except Exception:
            _git_cache[p] = False
    return _git_cache[p]

def _git_clean(p):
    if any(c in p for c in "*?["):
        paths = sorted(glob.glob(p))
    else:
        paths = [p] if os.path.lexists(p) else []
    if not paths or len(paths) > 500:
        return False
    groups = {}
    for q in paths:
        groups.setdefault(os.path.dirname(q), []).append(q)
    if len(groups) > 5:
        return False
    end = time.monotonic() + 3  # celkový rozpočet na jednu cestu

    def git(dr, *a):
        t = end - time.monotonic()
        if t <= 0:
            raise subprocess.TimeoutExpired("git", 3)
        return subprocess.run(["git", "--no-optional-locks", "--literal-pathspecs", "-C", dr, *a],
                              capture_output=True, text=True, timeout=t, stdin=subprocess.DEVNULL,
                              env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    for dr, ps in groups.items():
        # sledovaná: každá z cest musí odpovídat něčemu v indexu
        if git(dr, "ls-files", "--error-unmatch", "--", *ps).returncode != 0:
            return False
        st = git(dr, "status", "--porcelain", "--ignored", "--", *ps)
        if st.returncode != 0:
            return False
        for ln in st.stdout.splitlines():
            q = ln[3:]
            if "__pycache__" not in q.split("/") and not q.rstrip("/").endswith(".pyc"):
                return False
    return True

def reversible(p, remote=False, use_git=True):
    """Ztrátu dat v cestě p jde vrátit (dočasné místo, projekt, cache, pycache, log, čistý git)."""
    if p == "/dev/null" or any(under(p, b) for b in ("/tmp", "/var/tmp", "/dev/shm")):
        return True
    segs = p.split("/")
    if "__pycache__" in segs or p.endswith(".pyc"):
        return True
    if remote:
        return bool(re.search(r"\.log(\.\d+)?$", p)) or any("claude" in sg.lower() for sg in segs)
    if re.match(r"^/run/user/\d+/", p) and not re.match(r"^/run/user/\d+/(gvfs|doc)(/|$)", p):
        return True  # XDG_RUNTIME_DIR (tmpfs), kromě připojených sdílení
    if (under(p, scratch) or any(under(p, b) for b in projs) or under(p, home + "/.cache")
            or re.match(r"^%s/\.claude/projects/[^/]+/memory(/|$)" % re.escape(home), p)
            or re.match(r"^%s/\.claude/jobs/[^/]+/tmp(/|$)" % re.escape(home), p)):
        return True
    return use_git and git_clean(p)

def risky(p, remote=False, use_git=True):
    """Okno jen když cesta leží v datovém úložišti A NEJDE VRÁTIT."""
    if KNOWN_HOSTS.search(p):
        return False  # veřejný soubor, ssh do něj zapisuje sám
    return protected(p) or (in_data(p, remote) and not reversible(p, remote, use_git))

# ---------- Edit/Write: Claude Code je umí vrátit (checkpoint), hlídá se jen nastavení a klíče ----------
if tool in ("Edit", "Write", "NotebookEdit"):
    p = os.path.realpath(os.path.expanduser(ti.get("file_path") or ti.get("notebook_path") or ""))
    if protected(p):
        out("ask", f"Změna nastavení/hooků Claude Code nebo klíčů ({p}).")
    finish()

# ---------- tajné soubory (Bash i Read): vzory ----------
SECRET = [r"\.bash_history", r"/\.ssh/", r"\.gnupg", r"\.netrc", r"(^|/)\.env$", r"id_(rsa|ed25519|ecdsa)"]
try:
    for ln in open(os.path.expanduser("~/.config/marek-hooks/tajne.txt"), encoding="utf-8"):
        ln = ln.strip()
        if ln and not ln.startswith("#"):
            SECRET.append(ln)
except OSError:
    pass
# Veřejné části ~/.ssh (konfigurace, známé hostitele, veřejné klíče) tajné nejsou.
SECRET_OK = re.compile(r"/\.ssh/(config|known_hosts[^/]*|authorized_keys|[^/]*\.pub)$")

def _ok(rx):
    try:
        re.compile(rx)
        return True
    except re.error:
        return False

def is_secret(a):
    return not SECRET_OK.search(a) and any(re.search(rx, a) for rx in SECRET if _ok(rx))

if tool == "Read":
    fp = ti.get("file_path") or ""
    if fp and any(is_secret(x) for x in {fp, os.path.expanduser(fp), os.path.realpath(os.path.expanduser(fp))}):
        out("ask", "Čtení tajného souboru (klíče, historie, tokeny).")
    finish()

if tool != "Bash":
    finish()

cmd = ti.get("command") or ""

# ---------- rozklad příkazu na jednoduché příkazy ----------
def strip_heredocs(c):
    """Těla heredoců (<<EOF … EOF) nejsou příkazy shellu, vyhodí se."""
    lines, outl, ends = c.split("\n"), [], []
    for ln in lines:
        if ends:
            t = ln.strip() if ends[0][1] else ln
            if t == ends[0][0]:
                ends.pop(0)
            continue
        outl.append(ln)
        for m in re.finditer(r"<<(-?)\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\2", ln):
            if not ln[max(0, m.start() - 1):m.start()] == "<":  # <<< je here-string
                ends.append((m.group(3), m.group(1) == "-"))
    return "\n".join(outl)

SEP = {";", "&&", "||", "|", "&", "(", ")", "\n", ";;", "|&", "{", "}", "!"}

def tokens(c):
    try:
        lx = shlex.shlex(c, posix=True, punctuation_chars="();<>|&\n")
        lx.whitespace = " \t\r"
        lx.whitespace_split = True
        return list(lx)
    except ValueError:
        return c.replace("\n", " ; ").split()

def simple_commands(c):
    cur, res = [], []
    for t in tokens(strip_heredocs(c)):
        if t in SEP or t in ("then", "do", "else", "elif", "fi", "done", "if", "while", "until"):
            if cur:
                res.append(cur)
            cur = []
        else:
            cur.append(t)
    if cur:
        res.append(cur)
    return res

VARS = {"HOME": home}

def expand(w):
    # ${X:-výchozí} / ${X-výchozí}: známá hodnota X, jinak výchozí (např. ${XDG_RUNTIME_DIR:-/tmp})
    w = re.sub(r"\$\{(\w+):?-([^}$`]*)\}", lambda m: VARS.get(m.group(1)) or os.environ.get(m.group(1)) or m.group(2), w)
    w = re.sub(r"\$\{(\w+)\}|\$(\w+)", lambda m: VARS.get(m.group(1) or m.group(2), m.group(0)), w)
    return w

def _abs(w, ecwd, remote):
    """Absolutní cesta ze slova; ~ vzdáleně = domov neznámého stroje (bere se jako /home/~, tedy data)."""
    if w == "~" or w.startswith("~/"):
        w = (("/home/~" if remote else home) + w[1:])
    elif w.startswith("~") and not remote:
        w = os.path.expanduser(w)
    if not os.path.isabs(w):
        if not ecwd:
            return None  # cwd neznámé: relativní cestu nelze určit
        w = os.path.join(ecwd, w)
    # Vzdálené cesty se neřeší přes symlinky tohoto stroje.
    return os.path.normpath(w) if remote else os.path.realpath(w)

def real(w, ecwd, remote=False):
    w = expand(w)
    if "$" in w or "`" in w:
        return None  # neznámá proměnná: místo nelze určit
    return _abs(w, ecwd, remote)

def need_window(w, ecwd, remote):
    """Mazání/přepis cesty `w`: vrátí popis, když to má vyvolat okno (v datech a nejde vrátit), jinak None."""
    p = real(w, ecwd, remote)
    if p is not None:
        return p if risky(p, remote) else None
    # neznámá proměnná: rozhodne pevný začátek cesty před prvním `$`; bez něj nelze určit = okno
    pre = re.split(r"[$`]", expand(w), 1)[0]
    if not pre:
        return w
    base = _abs(pre[:pre.rfind("/") + 1] or ".", ecwd, remote)
    if base is None or base == "/":
        return w
    return w if risky(base, remote, use_git=False) else None

WRAP_OPT = {"sudo": {"-u", "-g", "-C", "-D", "-h", "-p", "-r", "-t", "-U"},
            "timeout": {"-s", "-k", "--signal", "--kill-after"},
            "nice": {"-n"}, "ionice": {"-c", "-n"}, "stdbuf": set(), "nohup": set(), "env": {"-u", "-C"},
            "command": set(), "exec": set(), "time": set(), "doas": {"-u"}, "chronic": set(),
            "flock": {"-w", "-E"}, "xargs": {"-n", "-I", "-d", "-P", "-L", "-a", "-s", "-E"}}

DESTR_GIT = re.compile(r"^git\b.*\s(reset\s+--hard|clean\s+-\S*f|branch\s+-D|push\s.*(--force|\s-f\b)|"
                       r"checkout\s+--\s|restore\s|stash\s+(drop|clear))")
DISK = re.compile(r"^(mkfs\S*|wipefs|parted|fdisk|sfdisk|sgdisk|blkdiscard|vgremove|lvremove|pvremove)$")

# Příkazy, které tajný soubor jen použijí nebo vypíšou jeho jméno, ne obsah.
NONREAD = {"ls", "stat", "ssh", "ssh-add", "ssh-keygen", "chmod", "chown", "test", "[", "file", "du",
           "find", "mkdir", "touch", "sftp", "git", "realpath", "readlink", "basename", "dirname", "mosh",
           "ssh-copy-id"}

problems = []

def check(words, ecwd, remote):
    """Jeden jednoduchý příkaz; vrátí nový efektivní cwd (cd)."""
    # přiřazení VAR=… na začátku
    while words and re.match(r"^[A-Za-z_]\w*=", words[0]):
        k, v = words[0].split("=", 1)
        VARS[k] = expand(v)
        words = words[1:]
    # for VAR in SLOVA (0.15.1): proměnná smyčky = společný adresář slov + „*“ (např. data/*.csv -> data/*.csv),
    # aby `mv x $f` uvnitř smyčky šlo posoudit podle místa. Bez slov, se `$(…)`/`$` nebo `for ((…))` zůstane neznámá.
    if words and words[0] == "for":
        if len(words) >= 4 and re.match(r"^[A-Za-z_]\w*$", words[1]) and words[2] == "in":
            items = [expand(w) for w in words[3:]]
            if items and not any("$" in w or "`" in w for w in items):
                pre = os.path.commonprefix(items) if len(items) > 1 else items[0]
                if len(items) > 1:
                    pre = pre[:pre.rfind("/") + 1] + "*" if "/" in pre else "*"
                VARS[words[1]] = pre
            else:
                VARS.pop(words[1], None)
        return ecwd
    if words and words[0] in ("export", "local", "declare", "readonly"):
        for w in words[1:]:
            if re.match(r"^[A-Za-z_]\w*=", w):
                k, v = w.split("=", 1)
                VARS[k] = expand(v)
        return ecwd
    # obaly: sudo, timeout 10, env A=b, xargs …
    stdin_targets = False
    while words and words[0] in WRAP_OPT:
        w0 = words.pop(0)
        stdin_targets |= w0 == "xargs"
        while words and (words[0].startswith("-") or re.match(r"^[A-Za-z_]\w*=", words[0])
                         or (w0 == "timeout" and re.match(r"^\d+[smhd]?$", words[0]))):
            o = words.pop(0)
            if o in WRAP_OPT[w0] and words:
                words.pop(0)
    if not words:
        return ecwd
    head = os.path.basename(words[0])
    args = words[1:]

    # vnořený shell a vzdálené příkazy
    if head in ("bash", "sh", "zsh", "dash") and "-c" in args:
        i = args.index("-c")
        if i + 1 < len(args):
            run_all(args[i + 1], ecwd, remote)
        return ecwd
    if head == "ssh":
        pos = [a for j, a in enumerate(args) if not a.startswith("-")
               and not (j and args[j - 1] in ("-i", "-o", "-p", "-l", "-F", "-J", "-L", "-R", "-D", "-W", "-b"))]
        if len(pos) > 1:
            run_all(" ".join(pos[1:]), "/", True)
    if head == "pct" and args[:1] == ["exec"] and "--" in args:
        rest = args[args.index("--") + 1:]
        if rest:
            check(rest, "/", True)
        return ecwd
    if head == "cd":
        if args and args[0] != "-":
            return real(args[0], ecwd, remote)  # neznámý cíl = neznámé cwd (relativní cesty pak vyvolají okno)
        return "/home/~" if remote else home

    # redirekce: > přepíše, >> připojí
    clean, i = [], 0
    while i < len(args):
        a = args[i]
        if re.fullmatch(r"[0-9]*[<>&]+", a) and ">" in a and i + 1 < len(args):
            tgt = args[i + 1]
            i += 2
            if a.endswith("&") or re.fullmatch(r"\d+", tgt) or tgt == "-":
                continue  # 2>&1
            p = real(tgt, ecwd, remote)
            if p is None:
                if ">>" not in a and need_window(tgt, ecwd, remote):
                    problems.append(f"přepis souboru s neznámou cestou ({tgt})")
                continue
            if protected(p):
                problems.append(f"zápis do nastavení Claude nebo klíčů ({p})")
            elif ">>" not in a and risky(p, remote) and (remote or os.path.isfile(p)):
                problems.append(f"přepis souboru v datech, který nejde vrátit ({p})")
            continue
        if re.fullmatch(r"[0-9]*<+", a) and i + 1 < len(args):
            i += 2
            continue
        clean.append(a)
        i += 1
    args = clean
    pos = [a for a in args if not a.startswith("-")]
    if "--" in args:
        pos = [a for a in args[:args.index("--")] if not a.startswith("-")] + args[args.index("--") + 1:]

    def must_be_safe(paths, what):
        bad = [x for x in (need_window(w, ecwd, remote) for w in paths) if x]
        if bad:
            problems.append(f"{what}: {', '.join(bad[:3])}")

    # (a) mazání
    if head in ("rm", "rmdir", "unlink", "shred", "srm"):
        if pos:
            must_be_safe(pos, "nevratné mazání dat")
        elif stdin_targets and (not ecwd or risky(ecwd, remote)):
            problems.append("nevratné mazání souborů ze vstupu (xargs) v datovém úložišti")
    elif head == "truncate":
        must_be_safe([a for j, a in enumerate(args) if not a.startswith("-")
                      and not (j and args[j - 1] in ("-s", "--size", "-r", "--reference"))], "nevratné zkrácení souboru")
    elif head == "find" and ("-delete" in args or any(a in ("rm", "/bin/rm") for a in args)):
        starts = [a for a in args if not a.startswith(("-", "(", ")", "!"))][:1] or ["."]
        must_be_safe(starts, "find -delete na datech, která nejdou vrátit")
    elif head == "rsync" and any(a.startswith("--delete") or a.startswith("--remove-source") for a in args):
        if pos and ":" not in pos[-1]:
            must_be_safe(pos[-1:], "rsync --delete na datech, která nejdou vrátit")
    elif head in ("mv", "cp", "install", "ln") and len(pos) >= 2:
        # přepis cíle (existující soubor v datech) a u mv i odebrání zdroje z dat
        t_dir = next((args[j + 1] for j, a in enumerate(args) if a in ("-t", "--target-directory") and j + 1 < len(args)), None)
        dst = t_dir or pos[-1]
        srcs = pos if t_dir else pos[:-1]
        dp = real(dst, ecwd, remote)
        if dp is not None:
            targets = [os.path.join(dp, os.path.basename(x.rstrip("/"))) for x in srcs] \
                if not remote and os.path.isdir(dp) else [dp]
            for tp in targets:
                if protected(tp):
                    problems.append(f"zápis do nastavení Claude nebo klíčů ({tp})")
                elif head != "ln" and risky(tp, remote) and (remote or os.path.isfile(tp)):
                    problems.append(f"{head} přepíše soubor v datech, který nejde vrátit ({tp})")
        elif head != "ln" and need_window(dst, ecwd, remote):
            problems.append(f"{head} do cesty s neznámou proměnnou ({dst})")
        if head == "mv":
            for s in srcs:
                sp = real(s, ecwd, remote)
                if sp is not None and protected(sp):
                    problems.append(f"přesun nastavení Claude nebo klíčů ({sp})")
    elif head in ("sed", "perl") and any(re.match(r"^-[a-zA-Z]*i", a) or a.startswith("--in-place") for a in args):
        files = pos[1:] if head == "sed" and not any(a in ("-e", "-f") or a.startswith("--expression") for a in args) else pos
        if head == "perl":  # skript není soubor: lokálně existující cesty, vzdáleně cesty vypadající jako cesty
            files = [a for a in pos if (re.match(r"^[~/.]", a) if remote else os.path.exists(real(a, ecwd) or ""))]
        for w in files:
            p = real(w, ecwd, remote)
            if p is None:
                continue
            if protected(p):
                problems.append(f"úprava nastavení Claude nebo klíčů ({p})")
            elif risky(p, remote):
                problems.append(f"úprava souboru na místě v datech, který nejde vrátit ({p})")
    elif head == "tee":
        for w in pos:
            p = real(w, ecwd, remote)
            if p is None:
                continue
            if protected(p):
                problems.append(f"zápis do nastavení Claude nebo klíčů ({p})")
            elif not any(a in ("-a", "--append") for a in args) and risky(p, remote) and (remote or os.path.isfile(p)):
                problems.append(f"tee přepíše soubor v datech, který nejde vrátit ({p})")
    elif DISK.match(head) or (head == "dd" and any(a.startswith("of=/dev/") for a in args)) \
            or (head == "cryptsetup" and any(a in ("luksFormat", "erase", "luksErase") for a in args)):
        problems.append(f"operace s diskem, která ničí data ({head})")
    elif head == "git" and DESTR_GIT.search(" ".join(words)):
        repo = ecwd
        if "-C" in args and args.index("-C") + 1 < len(args):
            repo = real(args[args.index("-C") + 1], ecwd, remote) or ""
        if not (repo and (under(repo, scratch) or under(repo, "/tmp"))):
            problems.append("git: destruktivní operace (reset --hard, clean -f, branch -D, push --force, checkout --, restore)")

    # (b) čtení tajných souborů
    if not remote and head not in NONREAD:
        for j, a in enumerate(args):
            if j and args[j - 1] == "-i" and head in ("scp", "rsync", "sftp", "ssh"):
                continue
            if is_secret(a):
                problems.append("čtení tajného souboru (klíče, historie, tokeny)")
                break
    return ecwd


def run_all(c, ecwd, remote):
    for words in simple_commands(c):
        ecwd = check(list(words), ecwd, remote)


try:
    run_all(cmd, cwd, False)
except Exception:
    sys.exit(0)  # chyba skriptu: fail-open bez allow

if problems:
    seen = list(dict.fromkeys(problems))
    out("ask", "Riziková akce: " + "; ".join(seen[:3]) + ".")
finish()

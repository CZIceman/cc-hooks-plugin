#!/usr/bin/env python3
"""PreToolUse hook (marek-cc-hooks 0.8.0) — okno oprávnění jen tam, kde jde o data nebo tajemství.

Princip: souhlas nehlídá model, ale okno oprávnění Claude Code. Rizikovou akci hook vrátí jako
permissionDecision "ask" (Marek potvrdí), nic dalšího neschvaluje. Ostatní akce propustí mlčky.

Rozhodnutí Marka 29. 10. 2026 (0.8.0): okno jen na
  (a) mazání nebo přepis dat mimo pracovní místa (scratchpad, /tmp, /var/tmp, adresář projektu = cwd),
      destruktivní git a operace s disky, které ničí data,
  (b) čtení obsahu tajných souborů (klíče, historie, tokeny),
  (c) změnu nastavení a hooků Claude Code (~/.claude/settings*, hooks, plugins, ~/.config/marek-hooks).
Systémové změny (sudo, dnf, systemctl, zápis do /etc), push a běhy modelů se neptají.
Zahazování otázek AskUserQuestion podle textu (0.7.0) je zrušené: kdy se ptát, určují pravidla.

Hodnotí se jen to, co shell skutečně spustí: příkaz se rozloží na jednoduché příkazy, těla heredoců
se přeskočí, řetězce zůstanou jedním slovem (slovo „rm“ v echo/grep nebo v kódu Pythonu nevadí),
`sudo`, `timeout`, `env`, `bash -c '…'` se rozbalí, jednoduchá přiřazení (S=…; rm $S/x) se dosadí.
Příkazy uvnitř `ssh host …` a `pct exec N -- …` běží jinde: pracovní místa tam jsou jen /tmp a /var/tmp.
Kód skriptů (python3 -c, heredoc) se nehodnotí. Chyba skriptu = akce pokračuje (exit 0 bez výstupu).
"""
import glob, json, os, re, shlex, sys


def out(decision, reason):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
          "permissionDecision": decision, "permissionDecisionReason": reason}}, ensure_ascii=False))
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

# ---------- místa ----------
def under(p, base):
    return bool(base) and (p == base or p.startswith(base.rstrip("/") + "/"))

# Nastavení a hooky Claude Code a klíče: každý zápis i mazání se ptá.
PROTECT = [r"^%s/\.claude/(settings[^/]*\.json|hooks|plugins)(/|$)" % re.escape(home),
           r"^%s/\.config/marek-hooks(/|$)" % re.escape(home),
           r"^/etc/claude-code(/|$)", r"/\.ssh(/|$)", r"/\.gnupg(/|$)"]
# Data: domovský adresář a připojená úložiště. Přepis existujícího souboru tady se ptá.
DATA = [home, "/home", "/root", "/mnt", "/media", "/run/media", "/srv"]

def protected(p):
    return any(re.search(x, p) for x in PROTECT)

def safe(p, remote=False):
    """Pracovní místo: mazat a přepisovat se tu smí bez dotazu."""
    if protected(p):
        return False
    if under(p, "/tmp") or under(p, "/var/tmp") or p == "/dev/null":
        return True
    if remote:
        return False
    if re.match(r"^/run/user/\d+/", p) and not re.match(r"^/run/user/\d+/(gvfs|doc)(/|$)", p):
        return True  # XDG_RUNTIME_DIR (tmpfs), kromě připojených sdílení
    return (under(p, scratch) or any(under(p, b) for b in projs) or under(p, home + "/.cache")
            or bool(re.match(r"^%s/\.claude/projects/[^/]+/memory(/|$)" % re.escape(home), p)))

def in_data(p):
    return any(under(p, b) for b in DATA) or bool(re.match(r"^/run/user/\d+/gvfs/", p))

# ---------- Edit/Write: Claude Code je umí vrátit (checkpoint), hlídá se jen nastavení a klíče ----------
if tool in ("Edit", "Write", "NotebookEdit"):
    p = os.path.realpath(os.path.expanduser(ti.get("file_path") or ti.get("notebook_path") or ""))
    if protected(p):
        out("ask", f"Změna nastavení/hooků Claude Code nebo klíčů ({p}).")
    sys.exit(0)

if tool != "Bash":
    sys.exit(0)

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
    w = re.sub(r"\$\{(\w+)\}|\$(\w+)", lambda m: VARS.get(m.group(1) or m.group(2), m.group(0)), w)
    return w

def real(w, ecwd):
    w = os.path.expanduser(expand(w))
    if "$" in w or "`" in w:
        return None  # neznámá proměnná: místo nelze určit
    if not os.path.isabs(w):
        w = os.path.join(ecwd or "/nonexistent-cwd", w)
    return os.path.realpath(w)

WRAP_OPT = {"sudo": {"-u", "-g", "-C", "-D", "-h", "-p", "-r", "-t", "-U"},
            "timeout": {"-s", "-k", "--signal", "--kill-after"},
            "nice": {"-n"}, "ionice": {"-c", "-n"}, "stdbuf": set(), "nohup": set(), "env": {"-u", "-C"},
            "command": set(), "exec": set(), "time": set(), "doas": {"-u"}, "chronic": set(),
            "flock": {"-w", "-E"}, "xargs": {"-n", "-I", "-d", "-P", "-L", "-a", "-s", "-E"}}

DESTR_GIT = re.compile(r"^git\b.*\s(reset\s+--hard|clean\s+-\S*f|branch\s+-D|push\s.*(--force|\s-f\b)|"
                       r"checkout\s+--\s|restore\s|stash\s+(drop|clear))")
DISK = re.compile(r"^(mkfs\S*|wipefs|parted|fdisk|sfdisk|sgdisk|blkdiscard|vgremove|lvremove|pvremove)$")

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
            r = real(args[0], ecwd)
            return r or ecwd
        return home

    # redirekce: > přepíše, >> připojí
    clean, i = [], 0
    while i < len(args):
        a = args[i]
        if re.fullmatch(r"[0-9]*[<>&]+", a) and ">" in a and i + 1 < len(args):
            tgt = args[i + 1]
            i += 2
            if a.endswith("&") or re.fullmatch(r"\d+", tgt) or tgt == "-":
                continue  # 2>&1
            p = real(tgt, ecwd)
            if p is None:
                continue
            if protected(p):
                problems.append(f"zápis do nastavení Claude nebo klíčů ({p})")
            elif ">>" not in a and not safe(p, remote) and in_data(p) and os.path.isfile(p) and not remote:
                problems.append(f"přepis existujícího souboru {p}")
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
        bad = []
        for w in paths:
            p = real(w, ecwd)
            if p is None or not safe(p, remote):
                bad.append(p or w)
        if bad:
            problems.append(f"{what}: {', '.join(bad[:3])}")

    # (a) mazání
    if head in ("rm", "rmdir", "unlink", "shred", "srm"):
        if pos:
            must_be_safe(pos, "mazání mimo pracovní místa")
        elif stdin_targets and not (ecwd and safe(ecwd, remote)):
            problems.append("mazání souborů ze vstupu (xargs) mimo pracovní místa")
    elif head == "truncate":
        must_be_safe([a for j, a in enumerate(args) if not a.startswith("-")
                      and not (j and args[j - 1] in ("-s", "--size", "-r", "--reference"))], "zkrácení souboru")
    elif head == "find" and ("-delete" in args or any(a in ("rm", "/bin/rm") for a in args)):
        starts = [a for a in args if not a.startswith(("-", "(", ")", "!"))][:1] or ["."]
        must_be_safe(starts, "find -delete mimo pracovní místa")
    elif head == "rsync" and any(a.startswith("--delete") or a.startswith("--remove-source") for a in args):
        if pos and ":" not in pos[-1]:
            must_be_safe(pos[-1:], "rsync --delete mimo pracovní místa")
    elif head in ("mv", "cp", "install", "ln") and len(pos) >= 2:
        # přepis cíle (existující soubor v datech) a u mv i odebrání zdroje z dat
        t_dir = next((args[j + 1] for j, a in enumerate(args) if a in ("-t", "--target-directory") and j + 1 < len(args)), None)
        dst = t_dir or pos[-1]
        srcs = pos if t_dir else pos[:-1]
        dp = real(dst, ecwd)
        if dp is not None:
            targets = [os.path.join(dp, os.path.basename(s.rstrip("/"))) for s in srcs] if os.path.isdir(dp) else [dp]
            for tp in targets:
                if protected(tp):
                    problems.append(f"zápis do nastavení Claude nebo klíčů ({tp})")
                elif head != "ln" and not safe(tp, remote) and in_data(tp) and os.path.isfile(tp) and not remote:
                    problems.append(f"{head} přepíše existující soubor {tp}")
        if head == "mv":
            for s in srcs:
                sp = real(s, ecwd)
                if sp is not None and protected(sp):
                    problems.append(f"přesun nastavení Claude nebo klíčů ({sp})")
    elif head in ("sed", "perl") and any(re.match(r"^-[a-zA-Z]*i", a) or a.startswith("--in-place") for a in args):
        files = pos[1:] if head == "sed" and not any(a in ("-e", "-f") or a.startswith("--expression") for a in args) else pos
        if head == "perl":
            files = [a for a in pos if os.path.exists(real(a, ecwd) or "")]
        for w in files:
            p = real(w, ecwd)
            if p is None:
                continue
            if protected(p):
                problems.append(f"úprava nastavení Claude nebo klíčů ({p})")
            elif not safe(p, remote) and in_data(p) and not remote:
                problems.append(f"úprava souboru na místě mimo pracovní místa ({p})")
    elif head == "tee":
        for w in pos:
            p = real(w, ecwd)
            if p is None:
                continue
            if protected(p):
                problems.append(f"zápis do nastavení Claude nebo klíčů ({p})")
            elif "-a" not in args and not safe(p, remote) and in_data(p) and os.path.isfile(p) and not remote:
                problems.append(f"tee přepíše existující soubor {p}")
    elif DISK.match(head) or (head == "dd" and any(a.startswith("of=/dev/") for a in args)) \
            or (head == "cryptsetup" and any(a in ("luksFormat", "erase", "luksErase") for a in args)):
        problems.append(f"operace s diskem, která ničí data ({head})")
    elif head == "git" and DESTR_GIT.search(" ".join(words)):
        repo = ecwd
        if "-C" in args and args.index("-C") + 1 < len(args):
            repo = real(args[args.index("-C") + 1], ecwd) or ""
        if not (repo and (under(repo, scratch) or under(repo, "/tmp"))):
            problems.append("git: destruktivní operace (reset --hard, clean -f, branch -D, push --force, checkout --, restore)")

    # (b) čtení tajných souborů
    if not remote and head not in NONREAD:
        for j, a in enumerate(args):
            if j and args[j - 1] == "-i" and head in ("scp", "rsync", "sftp", "ssh"):
                continue
            if not SECRET_OK.search(a) and any(re.search(rx, a) for rx in SECRET if _ok(rx)):
                problems.append("čtení tajného souboru (klíče, historie, tokeny)")
                break
    return ecwd


def _ok(rx):
    try:
        re.compile(rx)
        return True
    except re.error:
        return False


def run_all(c, ecwd, remote):
    for words in simple_commands(c):
        ecwd = check(list(words), ecwd, remote)


try:
    run_all(cmd, cwd, False)
except Exception:
    sys.exit(0)

if problems:
    seen = list(dict.fromkeys(problems))
    out("ask", "Riziková akce: " + "; ".join(seen[:3]) + ".")
sys.exit(0)

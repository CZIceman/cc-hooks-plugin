#!/usr/bin/env python3
"""PreToolUse hook (marek-cc-hooks 0.7.0) — vynucení pravidel před akcí, bez zbytečných dotazů.

Princip: souhlas nehlídá model, ale okno oprávnění Claude Code. Rizikovou akci hook vrátí jako
permissionDecision "ask" (Marek potvrdí), nic dalšího neschvaluje. Neznámé a neškodné akce
propustí mlčky (normální tok oprávnění).

Od 0.7.0 (rozhodnutí Marka 28. 10. 2026): agent se smí ptát jen na mazání/přepis dat a na
hesla, tokeny a klíče. Push a běhy modelů/agentů (utrácení tokenů) se neptají.

Třídy: (1) rizikový Bash, (2) rizikové cesty pro Edit/Write, (4) tajné soubory,
(5) brána báze (pravidla před prací), (6) AskUserQuestion: zbytečná otázka se zamítne
(agent má rozhodnout sám). mv a sed -i uvnitř adresáře projektu (cwd) se neptají.
Chyba skriptu = akce pokračuje (exit 0 bez výstupu); nikdy nesmí rozbít práci.
Vypnutí větve (6): MAREK_ASK_MODE=off.
"""
import json, os, re, shlex, sys

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
home = os.path.expanduser("~")

# Adresář projektu = cwd session; domovský adresář a "/" za projekt nepovažujeme.
cwd = d.get("cwd") or ""
proj = ""
if cwd:
    _rc = os.path.realpath(cwd)
    if _rc not in ("/", os.path.realpath(home)):
        proj = _rc

def under(p, base):
    p = os.path.realpath(os.path.expanduser(p))
    return bool(base) and (p == base or p.startswith(base.rstrip("/") + "/"))

def inside_work(w):
    """Cesta leží ve scratchpadu nebo v adresáři projektu (relativní cesty se berou od cwd)."""
    p = os.path.expanduser(w)
    if not os.path.isabs(p) and cwd:
        p = os.path.join(cwd, p)
    return under(p, scratch) or under(p, proj)

# ---------- (5) brána báze: nejdřív `pravidla` (jednou za session) ----------
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

# ---------- (6) AskUserQuestion: ptát se jen na mazání a hesla/tokeny/klíče ----------
# Propustí se i otázky dílny (nabídka dílny a volby FORMULAR zůstaly v pravidlech beze změny).
# Heuristika podle textu otázky; nejistota = propustit (lepší otázka navíc než zablokovaný agent).
ASK_OK = re.compile(r"smaz|vymaz|odstra|delet|\brm\b|\bdrop\b|wipe|přeps|nevratn|irrevers|"
                    r"hesl|token|kl[ií]č|password|secret|credential|api[ -]?key|tajn|"
                    r"d[ií]ln|formul[aá]ř|zadej_ukol", re.I)

def recent_formular(path):
    """Dílna: v posledních ~60 kB přepisu je nabídka FORMULAR (otázky se pak musí zobrazit)."""
    try:
        with open(path, "rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - 60000))
            return "FORMULAR" in fh.read().decode("utf-8", "ignore")
    except (OSError, TypeError):
        return False

if tool == "AskUserQuestion":
    if os.environ.get("MAREK_ASK_MODE", "deny") == "off":
        sys.exit(0)
    txt = json.dumps(ti, ensure_ascii=False)
    if ASK_OK.search(txt) or recent_formular(d.get("transcript_path")):
        sys.exit(0)
    out("deny", "Neptej se: rozhodni sám podle nejrozumnějšího předpokladu, předpoklad uveď v hlášení "
        "a pokračuj. Ptát se smíš jen na mazání nebo přepis dat, na hesla, tokeny a klíče (a u dílny). "
        "Otázky k zadání patří řídící session, ne uživateli.")

# ---------- (2) Edit/Write na rizikových cestách ----------
RISKY_PATHS = [r"^/(etc|usr|boot|var|opt|root)(/|$)", r"/\.ssh(/|$)", r"/\.gnupg(/|$)",
               r"/\.bashrc(\.d)?(/|$)|/\.bash_profile$|/\.profile$|/\.zshrc$|/\.gitconfig$",
               r"/\.claude/(settings|plugins|hooks)", r"/\.config/(systemd|autostart|environment\.d|user-dirs)",
               r"/\.local/share/applications"]
if tool in ("Edit", "Write", "NotebookEdit"):
    p = ti.get("file_path") or ti.get("notebook_path") or ""
    rp = os.path.realpath(os.path.expanduser(p))
    if scratch and under(rp, scratch):
        sys.exit(0)
    if any(re.search(x, rp) for x in RISKY_PATHS):
        out("ask", f"Změna konfigurace mimo projekt ({rp}): nejdřív říct co, kde a proč, a zeptat se.")
    sys.exit(0)

if tool != "Bash":
    sys.exit(0)

cmd = ti.get("command") or ""

# ---------- (4) tajné soubory ----------
# Obecné vzory jsou tady (repo je veřejné); specifické (cesty k tokenům apod.) jsou v lokálním
# souboru ~/.config/marek-hooks/tajne.txt mimo repo: jeden regulární výraz na řádek, # = komentář.
SECRET = [r"\.bash_history", r"/\.ssh/", r"\.gnupg", r"\.netrc", r"\.env\b", r"id_(rsa|ed25519)"]
try:
    for ln in open(os.path.expanduser("~/.config/marek-hooks/tajne.txt"), encoding="utf-8"):
        ln = ln.strip()
        if ln and not ln.startswith("#"):
            SECRET.append(ln)
except OSError:
    pass
for rx in SECRET:
    try:
        hit = re.search(rx, cmd)
    except re.error:
        continue
    if hit:
        out("ask", "Příkaz sahá na tajné soubory (historie, klíče, tokeny). Nikdy nevypisovat hesla/tokeny.")

# ---------- (1) rizikový Bash ----------
# Běhy modelů (claude/codex -p, Agent, zadej_ukol) a samotný git push se od 0.7.0 neptají.
RISKY_CMDS = [
    (r"\bsudo\b", "sudo vždy jen od Marka"),
    (r"\b(dnf|yum|rpm|flatpak|snap|pip3?|pipx)\b[^;&|]*\b(install|remove|erase|autoremove|upgrade|update|swap|reinstall)\b", "instalace/odebrání balíčků"),
    (r"\bsystemctl\b[^;&|]*\b(enable|disable|start|stop|restart|mask|unmask|daemon-reload|edit|set-default|isolate|reload)\b", "změna služeb"),
    (r"\bgit\s+reset\s+--hard\b|\bgit\s+clean\b[^;&|]*-[a-z]*f|\bgit\s+branch\s+-D\b|--force\b", "git: destruktivní operace (reset --hard, clean -f, branch -D, --force)"),
    (r"\b(setpci|modprobe|rmmod|insmod|grub2?-\w+|dracut|kernel-install|mokutil|sbctl|efibootmgr|tuned-adm|hostnamectl|timedatectl|localectl|nmcli|firewall-cmd|nft|iptables|ufw|sysctl|authselect|dconf|gsettings|xdg-user-dirs-update|fwupdmgr|crontab|visudo)\b", "změna konfigurace systému"),
    (r"\b(chmod|chown|chattr|setfacl|usermod|userdel|useradd|passwd)\b", "změna práv/uživatelů"),
    (r"\b(mkfs\w*|wipefs|dd|parted|fdisk|mount|umount|cryptsetup|lvm|vgremove|lvremove)\b", "disky a svazky"),
    (r"(>>?|\btee\b(\s+-a)?)\s*(/etc|/usr|/boot|/var|/opt|~/|\$HOME/|/home/[^/]+/\.)", "zápis do systému/konfigurace"),
]
for rx, why in RISKY_CMDS:
    if re.search(rx, cmd):
        out("ask", f"Rizikový příkaz ({why}). Nejdřív říct co, kde a proč, a zeptat se.")

def split_words(c):
    try:
        return shlex.split(c.replace(";", " ; ").replace("&&", " && ").replace("|", " | "))
    except ValueError:
        return c.split()

# rm/rmdir/shred/truncate = mazání: bez dotazu jen když všechny cesty leží ve scratchpadu
if re.search(r"\b(rm|rmdir|shred|truncate)\b", cmd):
    words = split_words(cmd)
    paths = [w for w in words if w.startswith(("/", "~", ".")) and not w.startswith("-")]
    if not (scratch and paths and all(under(w, scratch) for w in paths)):
        out("ask", "Mazání souborů mimo scratchpad. Nejdřív říct co, kde a proč, a zeptat se.")

# mv, sed -i, perl -i: bez dotazu ve scratchpadu a v adresáři projektu (cwd); mimo ně se ptá.
# Holé názvy souborů (bez lomítka) se berou od cwd, proto je pouštíme jen když cwd je projekt.
if re.search(r"\b(mv|sed\s+-i\S*|perl\s+-\S*i\S*)\b", cmd):
    words = split_words(cmd)
    cand = [w for w in words if not w.startswith("-") and ("/" in w or w.startswith(("~", ".")))]
    ok = all(inside_work(w) for w in cand) and (bool(cand) or bool(proj))
    if not ok:
        out("ask", "Přesun nebo úprava souborů mimo scratchpad a projekt. Nejdřív říct co, kde a proč, a zeptat se.")

sys.exit(0)

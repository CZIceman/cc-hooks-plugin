#!/usr/bin/env python3
"""PreToolUse hook (návrh, marek-cc-hooks 0.6.0) — vynucení pravidel před akcí.

Princip: souhlas nehlídá model, ale okno oprávnění Claude Code. Rizikovou akci hook
vrátí jako permissionDecision "ask" (Marek potvrdí), nic dalšího neschvaluje. Neznámé
a neškodné akce propustí mlčky (normální tok oprávnění).

Třídy: (1) rizikový Bash, (2) rizikové cesty pro Edit/Write, (3) běhy modelů,
(4) tajné soubory, (5) brána báze (pravidla před prací).
Chyba skriptu = akce pokračuje (exit 0 bez výstupu); nikdy nesmí rozbít práci.
"""
import json, os, re, shlex, sys, time

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

# ---------- (3) běhy modelů ----------
if tool in ("Agent", "Workflow") or tool.endswith("D_lna__zadej_ukol"):
    out("ask", "Běh modelu utrácí tokeny: jen po výslovném „ano“ Marka.")

def under(p, base):
    p = os.path.realpath(os.path.expanduser(p))
    return bool(base) and (p == base or p.startswith(base.rstrip("/") + "/"))

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

# ---------- (3b) běhy modelů přes CLI ----------
if re.search(r"(^|[;&|\s])(claude|codex|agy|gemini)\b[^;&|]*\s(-p|--print|--prompt|exec)\b", cmd):
    out("ask", "Běh modelu přes CLI utrácí tokeny: jen po výslovném „ano“ Marka.")

# ---------- (1) rizikový Bash ----------
RISKY_CMDS = [
    (r"\bsudo\b", "sudo vždy jen od Marka"),
    (r"\b(dnf|yum|rpm|flatpak|snap|pip3?|pipx)\b[^;&|]*\b(install|remove|erase|autoremove|upgrade|update|swap|reinstall)\b", "instalace/odebrání balíčků"),
    (r"\bsystemctl\b[^;&|]*\b(enable|disable|start|stop|restart|mask|unmask|daemon-reload|edit|set-default|isolate|reload)\b", "změna služeb"),
    (r"\bgit\s+push\b|\bgit\s+reset\s+--hard\b|\bgit\s+clean\b[^;&|]*-[a-z]*f|\bgit\s+branch\s+-D\b|--force\b", "git: push a destruktivní operace jen na výslovný pokyn"),
    (r"\b(setpci|modprobe|rmmod|insmod|grub2?-\w+|dracut|kernel-install|mokutil|sbctl|efibootmgr|tuned-adm|hostnamectl|timedatectl|localectl|nmcli|firewall-cmd|nft|iptables|ufw|sysctl|authselect|dconf|gsettings|xdg-user-dirs-update|fwupdmgr|crontab|visudo)\b", "změna konfigurace systému"),
    (r"\b(chmod|chown|chattr|setfacl|usermod|userdel|useradd|passwd)\b", "změna práv/uživatelů"),
    (r"\b(mkfs\w*|wipefs|dd|parted|fdisk|mount|umount|cryptsetup|lvm|vgremove|lvremove)\b", "disky a svazky"),
    (r"(>>?|\btee\b(\s+-a)?)\s*(/etc|/usr|/boot|/var|/opt|~/|\$HOME/|/home/[^/]+/\.)", "zápis do systému/konfigurace"),
]
for rx, why in RISKY_CMDS:
    if re.search(rx, cmd):
        out("ask", f"Rizikový příkaz ({why}). Nejdřív říct co, kde a proč, a zeptat se.")

# rm/mv/cp/sed -i/truncate: bez dotazu jen když všechny cesty leží ve scratchpadu
if re.search(r"\b(rm|rmdir|shred|truncate|mv|sed\s+-i\S*|perl\s+-\S*i\S*)\b", cmd):
    try:
        words = shlex.split(cmd.replace(";", " ; ").replace("&&", " && ").replace("|", " | "))
    except ValueError:
        words = cmd.split()
    paths = [w for w in words if w.startswith(("/", "~", ".")) and not w.startswith("-")]
    if not (scratch and paths and all(under(w, scratch) for w in paths)):
        out("ask", "Mazání, přesun nebo úprava souborů mimo scratchpad. Nejdřív říct co, kde a proč, a zeptat se.")

sys.exit(0)

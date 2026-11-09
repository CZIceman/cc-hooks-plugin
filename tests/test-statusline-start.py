#!/usr/bin/env python3
"""Test statusline-start.py (SessionStart) bez modelu, s dočasným HOME; skutečné ~/.claude se nedotkne."""
import json, os, shutil, subprocess, sys, tempfile, time
REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
HOOK = os.path.join(REPO, "hooks", "statusline-start.py")

def nove_home(settings=None):
    h = tempfile.mkdtemp()
    if settings is not None:
        os.makedirs(os.path.join(h, ".claude"))
        with open(os.path.join(h, ".claude", "settings.json"), "wb") as f:
            f.write(settings if isinstance(settings, bytes) else settings.encode("utf-8"))
    return h

def cesty(h):
    return os.path.join(h, ".claude", "settings.json"), os.path.join(h, ".claude", "marek-statusline", "statusline.py")

def spust(h, root=REPO, env=None):
    e = {**os.environ, "HOME": h, "CLAUDE_PLUGIN_ROOT": root, **(env or {})}
    e.pop("MAREK_STATUSLINE", None) if not (env and "MAREK_STATUSLINE" in env) else None
    r = subprocess.run([sys.executable, HOOK], capture_output=True, text=True, env=e, input="{}")
    return r

def cti(p):
    with open(p, "rb") as f:
        return f.read()

bad = 0
def chk(n, got, exp):
    global bad
    ok = got == exp
    bad += not ok
    kratce = lambda v: (lambda t: t if len(t) <= 90 else t[:90] + "…")(repr(v))
    print("OK  " if ok else "CHYBA", f"{n:58} -> {kratce(got)}" + ("" if ok else f" (čekáno {kratce(exp)})"))

def cisty(n, r):
    chk(n + ": rc 0, stdout i stderr prázdné", (r.returncode, r.stdout, r.stderr), (0, "", ""))

STD = lambda h: {"type": "command", "command": "python3 " + cesty(h)[1], "refreshInterval": 30}

# 1. settings.json chybí
h = nove_home(); s, c = cesty(h); r = spust(h)
cisty("chybí settings", r)
chk("  vznikl jen s klíčem statusLine", json.loads(cti(s)) if os.path.exists(s) else None, {"statusLine": STD(h)})
chk("  koncový \\n", cti(s).endswith(b"\n"), True)
chk("  skript zkopírován, shodný se zdrojem", cti(c) == cti(os.path.join(REPO, "statusline", "statusline.py")), True)
chk("  práva skriptu 0755", os.stat(c).st_mode & 0o777, 0o755)

# 2. druhý běh beze změny
ms, mc = os.stat(s).st_mtime_ns, os.stat(c).st_mtime_ns; bs = cti(s); time.sleep(0.05)
cisty("druhý běh", spust(h))
chk("  mtime settings i cíle beze změny", (os.stat(s).st_mtime_ns, os.stat(c).st_mtime_ns), (ms, mc))
chk("  settings bajtově stejný", cti(s), bs)

# 3. existuje bez statusLine, jiné klíče a jejich pořadí
orig = {"zeta": 1, "permissions": {"allow": ["Bash(ls)"]}, "env": {"A": "č"}, "alfa": [1, 2]}
h = nove_home(json.dumps(orig)); s, c = cesty(h); os.chmod(s, 0o600)
cisty("settings bez statusLine", spust(h))
d = json.loads(cti(s))
chk("  statusLine doplněn", d.get("statusLine"), STD(h))
chk("  ostatní klíče a pořadí beze změny", list(d.items())[:4], list(orig.items()))
chk("  statusLine je poslední (pořadí zachováno)", list(d)[-1], "statusLine")
chk("  práva souboru zachována (0600)", os.stat(s).st_mode & 0o777, 0o600)
chk("  ensure_ascii=False (č ve výstupu)", "č".encode("utf-8") in cti(s), True)
chk("  indent 2 + koncový \\n", cti(s).endswith(b"}\n") and b'\n  "zeta": 1' in cti(s), True)

# 4. náš starý ruční záznam
for stary in ("/home/marek/cc-hooks-plugin/statusline/statusline.py", "/x/marek-statusline/statusline.py"):
    h = nove_home(json.dumps({"a": 1, "statusLine": {"type": "command", "command": stary, "refreshInterval": 60}, "b": 2}))
    s, c = cesty(h); cisty("starý ruční záznam " + stary[-30:], spust(h))
    d = json.loads(cti(s))
    chk("  nahrazen standardní hodnotou", d["statusLine"], STD(h))
    chk("  pořadí klíčů zachováno", list(d), ["a", "statusLine", "b"])

# 5. cizí statusLine
cizi = json.dumps({"statusLine": {"type": "command", "command": "~/bin/moje-radka.sh"}, "x": 1}, indent=4)
h = nove_home(cizi); s, c = cesty(h); b = cti(s)
cisty("cizí statusLine", spust(h))
chk("  soubor bajtově stejný", cti(s), b)
chk("  skript přesto zkopírován", os.path.exists(c), True)
h = nove_home(json.dumps({"statusLine": "text"})); s, c = cesty(h); b = cti(s)
cisty("statusLine není objekt (cizí)", spust(h)); chk("  bajtově stejný", cti(s), b)

# 6. nevalidní JSON / ne objekt
for n, obsah in (("nevalidní JSON", b"{nejson"), ("pole místo objektu", b"[1, 2]"), ("prázdný soubor", b""), ("není UTF-8", b'{"a": "\xff"}')):
    h = nove_home(obsah); s, c = cesty(h); cisty(n, spust(h)); chk("  bajtově stejný", cti(s), obsah)

# 7. změna zdroje -> cíl se aktualizuje
root = tempfile.mkdtemp(); os.makedirs(os.path.join(root, "statusline"))
src = os.path.join(root, "statusline", "statusline.py")
shutil.copy(os.path.join(REPO, "statusline", "statusline.py"), src)
h = nove_home(); s, c = cesty(h); spust(h, root=root)
chk("kopie z CLAUDE_PLUGIN_ROOT", cti(c), cti(src))
with open(src, "ab") as f: f.write(b"# nova verze\n")
bs = cti(s); r = spust(h, root=root)
cisty("změna zdroje", r)
chk("  cíl aktualizován", cti(c), cti(src))
chk("  práva cíle 0755", os.stat(c).st_mode & 0o777, 0o755)
chk("  settings beze změny", cti(s), bs)
chk("  v adresáři cíle nezůstal tmp soubor", sorted(os.listdir(os.path.dirname(c))), ["statusline.py"])

# 8. proměnná chybí -> adresář nad hooks/ podle __file__
h = nove_home(); e = {**os.environ, "HOME": h}; e.pop("CLAUDE_PLUGIN_ROOT", None); e.pop("MAREK_STATUSLINE", None)
r = subprocess.run([sys.executable, HOOK], capture_output=True, text=True, env=e, input="{}")
cisty("bez CLAUDE_PLUGIN_ROOT", r); chk("  skript zkopírován", os.path.exists(cesty(h)[1]), True)

# 9. MAREK_STATUSLINE=0
h = nove_home(); r = spust(h, env={"MAREK_STATUSLINE": "0"})
cisty("MAREK_STATUSLINE=0", r); chk("  nevzniklo nic (~/.claude)", os.path.exists(os.path.join(h, ".claude")), False)
h = nove_home(); r = spust(h, env={"MAREK_STATUSLINE": "1"})
chk("MAREK_STATUSLINE=1 normálně instaluje", os.path.exists(cesty(h)[1]), True)

# 10. chybějící zdroj a nezapisovatelný HOME: tiše, rc 0, nic nevznikne
h = nove_home(); r = spust(h, root=tempfile.mkdtemp())
cisty("chybí zdrojový skript", r); chk("  settings nevznikl", os.path.exists(cesty(h)[0]), False)
h = nove_home(); os.chmod(h, 0o500)
cisty("nezapisovatelný HOME", spust(h)); os.chmod(h, 0o700)

# 11. zkopírovaný skript je spustitelný a na {} vrátí rc 0
h = nove_home(); spust(h); c = cesty(h)[1]
r = subprocess.run([c], capture_output=True, text=True, input="{}", env={**os.environ, "HOME": h})
chk("zkopírovaný skript spustitelný, na {} rc 0, stderr prázdný", (r.returncode, r.stderr), (0, ""))
r = subprocess.run(["python3", c], capture_output=True, text=True, input="{}", env={**os.environ, "HOME": h})
chk("  přes python3 (jako v settings) rc 0", r.returncode, 0)

# 12. hooks.json: hook zapsán jako třetí v SessionStart
hk = json.load(open(os.path.join(REPO, "hooks", "hooks.json")))["hooks"]["SessionStart"][0]["hooks"]
chk("hooks.json: třetí hook SessionStart", (len(hk), hk[2]["command"], hk[2]["timeout"]),
    (3, 'python3 "${CLAUDE_PLUGIN_ROOT}/hooks/statusline-start.py"', 10))

print("statusline-start: selhalo", bad)
sys.exit(1 if bad else 0)

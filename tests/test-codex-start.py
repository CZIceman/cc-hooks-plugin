#!/usr/bin/env python3
"""Testy hooks/codex-start.py (0.14.0) v dočasném HOME; skutečný ~/.codex se nedotkne."""
import os, subprocess, sys, tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(REPO, "hooks", "codex-start.py")
SRC = open(os.path.join(REPO, "codex", "AGENTS.md"), encoding="utf-8").read()
bad = 0


def chk(name, got, exp):
    global bad
    ok = got == exp
    bad += not ok
    print(("OK  " if ok else "CHYBA"), name, "" if ok else "-> %r (čekáno %r)" % (got, exp))


def run(home, env=None):
    return subprocess.run([sys.executable, HOOK], input='{"source":"startup"}', capture_output=True, text=True,
                          env={**os.environ, "HOME": home, **(env or {})})


def rd(p):
    return open(p, encoding="utf-8").read() if os.path.exists(p) else None


# 1. bez ~/.codex nic nevznikne
h = tempfile.mkdtemp()
r = run(h)
chk("bez ~/.codex: rc 0, bez výstupu, nic nevzniklo", (r.returncode, r.stdout, os.path.exists(os.path.join(h, ".codex"))), (0, "", False))

# 2. prázdný ~/.codex: zápis, práva 600, značka
os.mkdir(os.path.join(h, ".codex"))
dst = os.path.join(h, ".codex", "AGENTS.md")
r = run(h)
chk("nový AGENTS.md = codex/AGENTS.md", rd(dst), SRC.rstrip("\n") + "\n")
chk("práva 600", oct(os.stat(dst).st_mode & 0o777), "0o600")
chk("značka pluginu v souboru", "Generuje plugin marek-cc-hooks" in rd(dst), True)
m1 = os.stat(dst).st_mtime_ns

# 3. beze změny se nepřepisuje
run(h)
chk("beze změny se nezapisuje (mtime stejný)", os.stat(dst).st_mtime_ns, m1)

# 4. místní doplněk se připojí na konec
os.makedirs(os.path.join(h, ".config", "marek-hooks"))
open(os.path.join(h, ".config", "marek-hooks", "codex-mistni.md"), "w").write("## Místní\n- tajný topic\n")
run(h)
chk("místní doplněk na konci", rd(dst).endswith("\n## Místní\n- tajný topic\n"), True)
chk("před přepsáním i spravovaný soubor zálohujeme", os.path.exists(dst + ".pred-pluginem"), True)

# 5. ruční soubor bez značky se zazálohuje, druhá záloha s časem
h2 = tempfile.mkdtemp(); os.mkdir(os.path.join(h2, ".codex")); d2 = os.path.join(h2, ".codex", "AGENTS.md")
open(d2, "w").write("# starý ruční\n")
run(h2)
chk("ruční soubor zazálohován", rd(d2 + ".pred-pluginem"), "# starý ruční\n")
chk("a nahrazen verzí z pluginu", "Generuje plugin marek-cc-hooks" in rd(d2), True)
open(d2, "w").write("# znovu ručně\n")
run(h2)
baks = sorted(f for f in os.listdir(os.path.join(h2, ".codex")) if f.startswith("AGENTS.md.pred-pluginem-"))
chk("druhá záloha s časem, první nepřepsána", (len(baks), rd(d2 + ".pred-pluginem")), (1, "# starý ruční\n"))

# 6. vypínač
h3 = tempfile.mkdtemp(); os.mkdir(os.path.join(h3, ".codex"))
run(h3, {"MAREK_CODEX_AGENTS": "0"})
chk("MAREK_CODEX_AGENTS=0: nic nezapíše", os.path.exists(os.path.join(h3, ".codex", "AGENTS.md")), False)

# 7. chyba (AGENTS.md je adresář) -> rc 0, bez výstupu
h4 = tempfile.mkdtemp(); os.makedirs(os.path.join(h4, ".codex", "AGENTS.md"))
r = run(h4)
chk("chyba zápisu: rc 0, bez výstupu", (r.returncode, r.stdout, r.stderr), (0, "", ""))

# 8. obsah: bez prvků vázaných na Claude Code, bez tajemství
for slovo in ("AskUserQuestion", "CronCreate", "run_in_background", "ntfy.lumatech", "agents-"):
    chk("codex/AGENTS.md neobsahuje %s" % slovo, slovo in SRC, False)

# 9. strážce pro Codex (0.15.2): kopie guardu + hooks.json, cizí hooky zůstanou, vypínač odebere jen naše
import json
h5 = tempfile.mkdtemp(); os.mkdir(os.path.join(h5, ".codex"))
hj = os.path.join(h5, ".codex", "hooks.json")
json.dump({"hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": "cizi.sh"}]}],
                     "Stop": [{"hooks": [{"type": "command", "command": "stop.sh"}]}]}}, open(hj, "w"))
run(h5)
cfg = json.load(open(hj))
cmds = lambda ev: [x["command"] for g in cfg["hooks"].get(ev, []) for x in g["hooks"]]
guard = os.path.join(h5, ".codex", "marek-hooks", "pretool-guard.py")
chk("kopie guardu shodná se zdrojem", rd(guard) == rd(os.path.join(REPO, "hooks", "pretool-guard.py")), True)
chk("PreToolUse: cizí + náš", cmds("PreToolUse"), ["cizi.sh", "env MAREK_HOOK_KLIENT=codex python3 " + guard])
chk("PermissionRequest: náš", cmds("PermissionRequest"), ["env MAREK_HOOK_KLIENT=codex python3 " + guard])
chk("Stop: cizí + náš", cmds("Stop"), ["stop.sh", "env MAREK_HOOK_KLIENT=codex python3 " + os.path.join(h5, ".codex", "marek-hooks", "stop-guard.py")])
m5 = os.stat(hj).st_mtime_ns; run(h5)
chk("hooks.json beze změny se nepřepisuje", os.stat(hj).st_mtime_ns, m5)
run(h5, {"MAREK_CODEX_HOOKS": "0"}); cfg = json.load(open(hj))
chk("MAREK_CODEX_HOOKS=0: naše pryč, cizí zůstanou", (cmds("PreToolUse"), "PermissionRequest" in cfg["hooks"], cmds("Stop")),
    (["cizi.sh"], False, ["stop.sh"]))
h6 = tempfile.mkdtemp(); os.mkdir(os.path.join(h6, ".codex")); open(os.path.join(h6, ".codex", "hooks.json"), "w").write("{rozbité")
run(h6)
chk("rozbitý hooks.json se nepřepíše", rd(os.path.join(h6, ".codex", "hooks.json")), "{rozbité")

print("codex-start: selhalo", bad)
sys.exit(1 if bad else 0)

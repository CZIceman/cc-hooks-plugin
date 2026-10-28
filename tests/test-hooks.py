#!/usr/bin/env python3
"""Test hooků bez spuštění modelu: do skriptů se pošle vzorový JSON a porovná se výsledek."""
import json, os, subprocess, sys, tempfile
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hooks")
SCR = "/tmp/claude-1000/x/scratchpad"
os.environ["XDG_RUNTIME_DIR"] = tempfile.mkdtemp()
def run(script, inp):
    r = subprocess.run([sys.executable, os.path.join(D, script)], input=json.dumps(inp), capture_output=True, text=True)
    o = r.stdout.strip()
    dec = json.loads(o)["hookSpecificOutput"].get("permissionDecision") if o and "permissionDecision" in o else ("block" if '"block"' in o else ("ctx" if o else "-"))
    return r.returncode, dec
def pre(tool, ti, sid="s1", **kw): return run("pretool-guard.py", {"tool_name": tool, "tool_input": ti, "session_id": sid, "scratchpad_dir": SCR, **kw})
# báze si odemknu nejdřív (jinak by brána zamítla vše)
pre("mcp__claude_ai_Marek_Second_Brain__pravidla", {}, sid="s1")
T = [  # (popis, výsledek, očekávané)
 ("ls", pre("Bash", {"command": "ls -la ~"}), "-"),
 ("grep journal", pre("Bash", {"command": "journalctl -b | grep -i error"}), "-"),
 ("git status", pre("Bash", {"command": "git status --short"}), "-"),
 ("git push (od 0.7.0 bez dotazu)", pre("Bash", {"command": "git push origin master"}), "-"),
 ("git push --force", pre("Bash", {"command": "git push --force origin master"}), "ask"),
 ("git reset --hard", pre("Bash", {"command": "git reset --hard HEAD~3"}), "ask"),
 ("git commit (nechat)", pre("Bash", {"command": "git commit -m x"}), "-"),
 ("sudo dnf", pre("Bash", {"command": "sudo dnf install -y htop"}), "ask"),
 ("dnf bez sudo", pre("Bash", {"command": "dnf remove acpica-tools"}), "ask"),
 ("dnf list (čtení)", pre("Bash", {"command": "dnf list installed | grep ripgrep"}), "-"),
 ("systemctl status", pre("Bash", {"command": "systemctl status sshd"}), "-"),
 ("systemctl disable", pre("Bash", {"command": "systemctl disable --now cups"}), "ask"),
 ("setpci", pre("Bash", {"command": "setpci -s 33:00.5 CAP_MSI+2.w"}), "ask"),
 ("rm mimo scratchpad", pre("Bash", {"command": "rm -rf ~/Hudba"}), "ask"),
 ("rm ve scratchpadu", pre("Bash", {"command": f"rm -f {SCR}/a.txt"}), "-"),
 ("mv ve scratchpadu", pre("Bash", {"command": f"mv {SCR}/a {SCR}/b"}), "-"),
 ("sed -i mimo", pre("Bash", {"command": "sed -i s/a/b/ ~/.bashrc"}), "ask"),
 ("> /etc", pre("Bash", {"command": "echo x > /etc/foo.conf"}), "ask"),
 ("bash_history", pre("Bash", {"command": "grep token ~/.bash_history"}), "ask"),
 ("claude -p (bez dotazu)", pre("Bash", {"command": "claude -p 'ahoj'"}), "-"),
 ("agy -p (bez dotazu)", pre("Bash", {"command": "agy --mode plan -p 'x'"}), "-"),
 ("agy models (čtení)", pre("Bash", {"command": "agy models"}), "-"),
 ("Agent (bez dotazu)", pre("Agent", {"prompt": "x"}), "-"),
 ("zadej_ukol (bez dotazu)", pre("mcp__claude_ai_D_lna__zadej_ukol", {}), "-"),
 ("Dílna stav (čtení)", pre("mcp__claude_ai_D_lna__stav", {}), "-"),
 ("Edit /etc", pre("Edit", {"file_path": "/etc/dnf/dnf.conf"}), "ask"),
 ("Write .bashrc.d", pre("Write", {"file_path": os.path.expanduser("~/.bashrc.d/x.sh")}), "ask"),
 ("Write v projektu", pre("Write", {"file_path": "/home/marek/claude/styblo/x.md"}), "-"),
 ("Write scratchpad", pre("Write", {"file_path": SCR + "/y.txt"}), "-"),
 ("Read (nehlídá)", pre("Read", {"file_path": "/etc/passwd"}), "-"),
]

# mv / sed -i / rm vůči adresáři projektu (cwd); HOME jako cwd se za projekt nepovažuje
PRJ = "/home/marek/claude/styblo"
T += [
 ("mv v projektu (relativní)", pre("Bash", {"command": "mv a.txt b.txt"}, cwd=PRJ), "-"),
 ("mv v projektu (cesty)", pre("Bash", {"command": f"mv {PRJ}/a {PRJ}/docs/a"}, cwd=PRJ), "-"),
 ("sed -i v projektu", pre("Bash", {"command": "sed -i s/a/b/ main.py"}, cwd=PRJ), "-"),
 ("sed -i ~/.bashrc z projektu", pre("Bash", {"command": "sed -i s/a/b/ ~/.bashrc"}, cwd=PRJ), "ask"),
 ("mv z projektu ven", pre("Bash", {"command": f"mv {PRJ}/a /srv/a"}, cwd=PRJ), "ask"),
 ("mv ../ ven z projektu", pre("Bash", {"command": "mv a ../a"}, cwd=PRJ), "ask"),
 ("mv holé názvy bez cwd", pre("Bash", {"command": "mv a.txt b.txt"}), "ask"),
 ("mv holé názvy, cwd = HOME", pre("Bash", {"command": "mv a.txt b.txt"}, cwd=os.path.expanduser("~")), "ask"),
 ("rm v projektu se ptá dál", pre("Bash", {"command": f"rm -f {PRJ}/a.txt"}, cwd=PRJ), "ask"),
]

# AskUserQuestion: ptát se jen na mazání a hesla/tokeny/klíče (a dílnu)
def q(text, **kw): return pre("AskUserQuestion", {"questions": [{"question": text, "options": [{"label": "A"}, {"label": "B"}]}]}, **kw)
def tr_with(text):
    f = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False)
    f.write(json.dumps({"type": "user", "message": {"content": [{"type": "tool_result", "content": text}]}}) + "\n")
    f.close(); return f.name
T += [
 ("otázka: zbytečná -> deny", q("Mám použít knihovnu A, nebo B?"), "deny"),
 ("otázka: zbytečná (push)", q("Smím pushnout do repa?"), "deny"),
 ("otázka: mazání projde", q("Smazat starou zálohu /srv/zaloha?"), "-"),
 ("otázka: heslo projde", q("Vložit heslo do konfigurace?"), "-"),
 ("otázka: token projde", q("Použít produkční token?"), "-"),
 ("otázka: dílna projde", q("Zadat úkol do dílny?"), "-"),
 ("otázka: FORMULAR v přepisu projde", q("Který model?", transcript_path=tr_with("FORMULAR\nQ model\n- a: x")), "-"),
 ("otázka: přepis bez FORMULAR -> deny", q("Který model?", transcript_path=tr_with("nic")), "deny"),
 ("otázka: subagent se hlídá také", q("Mám pokračovat?", agent_id="a1"), "deny"),
]
os.environ["MAREK_ASK_MODE"] = "off"
T += [("otázka: MAREK_ASK_MODE=off", q("Mám použít A, nebo B?"), "-")]
del os.environ["MAREK_ASK_MODE"]
# brána báze: nová session bez `pravidla`
T += [("brána 1. pokus", pre("Bash", {"command": "ls"}, sid="s2"), "deny"),
      ("brána 2. pokus", pre("Bash", {"command": "ls"}, sid="s2"), "deny"),
      ("brána 3. pokus (uvolní)", pre("Bash", {"command": "ls"}, sid="s2"), "-"),
      ("brána: ToolSearch volný", pre("ToolSearch", {"query": "x"}, sid="s3"), "-"),
      ("brána: konektor volný", pre("mcp__claude_ai_Marek_Second_Brain__hledej", {}, sid="s3"), "-"),
      ("brána: subagent se nehlídá", pre("Bash", {"command": "ls"}, sid="s4", agent_id="a1"), "-"),
      ("rozbitý vstup = nic", run("pretool-guard.py", "{nejson"), "-")]

# lokální soubor tajných cest mimo repo (HOME přepsán na prázdný adresář)
_home = tempfile.mkdtemp(); os.makedirs(_home + "/.config/marek-hooks")
open(_home + "/.config/marek-hooks/tajne.txt", "w").write("# komentář\nsupertajnasoubor\n[neplatny-regex\n")
_old = os.environ.get("HOME"); os.environ["HOME"] = _home
T += [("tajne.txt: shoda", pre("Bash", {"command": "cat /x/supertajnasoubor"}), "ask"),
      ("tajne.txt: neplatný regex nevadí", pre("Bash", {"command": "ls"}), "-")]
os.environ["HOME"] = _old
os.environ["HOME"] = tempfile.mkdtemp()
T += [("bez tajne.txt: obecné vzory", pre("Bash", {"command": "cat ~/.bash_history"}), "ask"),
      ("bez tajne.txt: běžný příkaz", pre("Bash", {"command": "ls"}), "-")]
os.environ["HOME"] = _old
bad = 0
for n, (rc, dec), exp in T:
    ok = rc == 0 and dec == exp
    bad += not ok
    print(("OK  " if ok else "CHYBA"), f"{n:34} -> {dec:6} (čekáno {exp}, rc={rc})")
print("pretool: selhalo", bad, "z", len(T))

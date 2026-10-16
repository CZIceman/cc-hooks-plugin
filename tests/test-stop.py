#!/usr/bin/env python3
"""Test Stop hooku na syntetických přepisech a na skutečném přepisu (jen čtení)."""
import json, os, subprocess, sys, tempfile
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hooks")
def tr(items):
    f = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False)
    for i in items: f.write(json.dumps(i) + "\n")
    f.close(); return f.name
U = lambda t: {"type": "user", "message": {"role": "user", "content": t}}
A = lambda *b: {"type": "assistant", "message": {"role": "assistant", "content": list(b)}}
TXT = lambda t: {"type": "text", "text": t}
TU = lambda n, i: {"type": "tool_use", "id": "t", "name": n, "input": i}
def run(items, final, **kw):
    r = subprocess.run([sys.executable, os.path.join(D, "stop-guard.py")], capture_output=True, text=True,
        input=json.dumps({"transcript_path": tr(items), "last_assistant_message": final, **kw}), env={**os.environ, **kw.pop("env", {})})
    o = r.stdout.strip()
    return r.returncode, ("-" if not o else ("block" if '"block"' in o else "ctx")), o
cases = [
 ("hotovo bez příkazu", [U("oprav"), A(TXT("Je to hotovo."))], "Je to hotovo.", "ctx"),
 ("hotovo s Bash", [U("oprav"), A(TU("Bash", {"command": "pytest"}), TXT("Hotovo"))], "Hotovo, testy prošly.", "-"),
 ("změna bez dokumentace", [U("x"), A(TU("Bash", {"command": "sudo dnf install -y htop"}), TXT("Nainstalováno."))], "Nainstalováno.", "ctx"),
 ("změna + zápis do báze", [U("x"), A(TU("Bash", {"command": "sudo dnf install -y htop"}), TU("mcp__claude_ai_Marek_Second_Brain__zapis", {}), TXT("Ok"))], "Ok", "-"),
 ("jen čtení", [U("x"), A(TU("Bash", {"command": "ls -la"}), TXT("Vidím 3 soubory."))], "Vidím 3 soubory.", "-"),
 ("starý tah se nepočítá", [U("a"), A(TU("Bash", {"command": "rm x"})), U("b"), A(TXT("Odpověď bez změn."))], "Odpověď bez změn.", "-"),
]
bad = 0
for n, items, fin, exp in cases:
    rc, dec, _ = run(items, fin); ok = rc == 0 and dec == exp; bad += not ok
    print("OK  " if ok else "CHYBA", f"{n:28} -> {dec:5} (čekáno {exp})")
rc, dec, _ = run(cases[0][1], "hotovo", stop_hook_active=True); ok = dec == "-"; bad += not ok
print("OK  " if ok else "CHYBA", f"{'stop_hook_active mlčí':28} -> {dec}")
r = subprocess.run([sys.executable, os.path.join(D, "stop-guard.py")], input="{špatně", capture_output=True, text=True)
ok = r.returncode == 0 and not r.stdout; bad += not ok
print("OK  " if ok else "CHYBA", "rozbitý vstup = nic, rc", r.returncode)
rc, dec, o = run(cases[0][1], "hotovo", env={"MAREK_STOP_MODE": "block"})
print("režim block ->", dec)
print("stop: selhalo", bad)

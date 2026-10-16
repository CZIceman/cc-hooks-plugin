#!/usr/bin/env python3
"""Stop hook (návrh, marek-cc-hooks 0.6.0) — fáze 1: jen UPOZORNĚNÍ, neblokuje.

Kontroluje poslední tah (od posledního textu uživatele):
 (a) odpověď tvrdí „hotovo/funguje/ověřeno…“, ale v tahu neproběhl žádný Bash ani test,
 (b) tah měnil soubory nebo konfiguraci, ale nezapsal do báze (`zapis`) ani neupravil
     dokument (*.md, README, HANDOFF, docs/).
Fáze 2 (po zkušenosti, na Markův pokyn): MODE=block místo advisory.
Ochrana proti smyčce: stop_hook_active -> mlčí. Chyba skriptu = exit 0 bez výstupu.
"""
import json, os, re, sys

MODE = os.environ.get("MAREK_STOP_MODE", "advisory")  # advisory | block

try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)
if not isinstance(d, dict):
    sys.exit(0)
if d.get("stop_hook_active"):
    sys.exit(0)

tp = d.get("transcript_path")
if not tp or not os.path.exists(tp):
    sys.exit(0)

turn = []  # bloky asistenta od posledního textového vstupu uživatele
try:
    for line in open(tp, encoding="utf-8"):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        m = r.get("message")
        if r.get("type") == "user" and isinstance(m, dict):
            c = m.get("content")
            is_text = isinstance(c, str) or (isinstance(c, list) and any(
                isinstance(b, dict) and b.get("type") in ("text", "image") for b in c))
            if is_text:
                turn = []
        elif r.get("type") == "assistant" and isinstance(m, dict) and isinstance(m.get("content"), list):
            turn += [b for b in m["content"] if isinstance(b, dict)]
except Exception:
    sys.exit(0)

tools = [b for b in turn if b.get("type") == "tool_use"]
final = d.get("last_assistant_message") or " ".join(b.get("text", "") for b in turn if b.get("type") == "text")

def is_bash(b): return b.get("name") == "Bash"
MUT = re.compile(r"\b(sudo|dnf|flatpak|systemctl\s+(enable|disable|start|stop|restart|mask)|tee|sed\s+-i|git\s+commit|mkdir|cp|mv|rm|install)\b|>\s*\S")
def mutating(b):
    n = b.get("name", ""); i = b.get("input") or {}
    if n in ("Edit", "Write", "NotebookEdit"):
        return not re.search(r"/scratchpad/|^/tmp/", i.get("file_path", ""))
    c = i.get("command", "")
    if "/scratchpad" in c and not re.search(r"(^|[;&|(]\s*)sudo\s", c):
        return False  # práce ve scratchpadu není změna systému
    c = re.sub(r"\d*>>?\s*/dev/null|\d*>&\d|<<\s*'?\w+'?", " ", c)  # přesměrování do /dev/null a heredoc nejsou změna
    return is_bash(b) and bool(MUT.search(c))
def doc_write(b):
    i = b.get("input") or {}
    return "Second_Brain__zapis" in b.get("name", "") or (
        b.get("name") in ("Edit", "Write") and re.search(r"\.md$|README|HANDOFF|/docs?/", i.get("file_path", "")))

problems = []
if re.search(r"\b(hotovo|dokončen[oa]|funguje|opraven[oa]|vyřešen[oa]|ověřen[oa]|nasazen[oa])\b", final, re.I) \
        and not any(is_bash(b) or "mcp__" in b.get("name", "") for b in tools):
    problems.append("Odpověď tvrdí hotovo/ověřeno, ale v tomto tahu neproběhl žádný příkaz ani test. "
                    "Pravidlo: hotovo až po ověření — spusť kontrolu, nebo napiš, co ověřeno není.")
if any(mutating(b) for b in tools) and not any(doc_write(b) for b in tools):
    problems.append("Tah měnil soubory nebo konfiguraci a nezapsal do báze ani do dokumentace. "
                    "Pravidlo: dokumentace se píše hned (báze `zapis`, README/HANDOFF) — nebo napiš proč není potřeba.")

if not problems:
    sys.exit(0)
msg = " ".join(problems)
if MODE == "block":
    print(json.dumps({"decision": "block", "reason": msg}, ensure_ascii=False))
else:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": msg}}, ensure_ascii=False))
sys.exit(0)

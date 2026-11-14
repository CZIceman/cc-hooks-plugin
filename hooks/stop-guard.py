#!/usr/bin/env python3
"""Stop hook (marek-cc-hooks 0.10.0).

Kontroluje poslední tah (od posledního textu uživatele):
 (a) odpověď tvrdí „hotovo/funguje/ověřeno…“, ale v tahu neproběhl žádný Bash ani test    [upozornění],
 (b) tah commitoval (`git commit`), ale nedotkl se dokumentace projektu
     (*.md, README, HANDOFF, docs/)                                                       [upozornění],
     Do 0.9.0 se (b) spouštělo po každé změně a připomínalo i zápis do báze; od 0.10.0 se do báze
     zapisuje až po Markově reakci na výsledek (pravidla.txt), proto ji Stop nepřipomíná.
 Blok otázky na konci tahu (0.7.0) je od 0.8.0 zrušený: kdy se ptát, určují pravidla (pravidla.txt).
Upozornění (a), (b): MAREK_STOP_MODE=advisory|block, výchozí advisory.
Ochrana proti smyčce: stop_hook_active -> mlčí.
Chyba skriptu = exit 0 bez výstupu.
"""
import json, os, re, sys

MODE = os.environ.get("MAREK_STOP_MODE", "advisory")          # advisory | block

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
def cmd(b): return (b.get("input") or {}).get("command", "") if is_bash(b) else ""
COMMIT = re.compile(r"\bgit(\s+-[Cc]\s+\S+)*\s+commit\b")
DOC = re.compile(r"\.md\b|README|HANDOFF|(^|[\s/'\"])docs?/")
def commits(b): return bool(COMMIT.search(cmd(b)))
def doc_touch(b):
    # dokument upravený nástrojem (Edit/Write) nebo zmíněný v příkazu (sed, heredoc, git add README.md)
    i = b.get("input") or {}
    return bool(DOC.search(i.get("file_path", "") if b.get("name") in ("Edit", "Write") else cmd(b)))

problems = []
if re.search(r"\b(hotovo|dokončen[oa]|funguje|opraven[oa]|vyřešen[oa]|ověřen[oa]|nasazen[oa])\b", final, re.I) \
        and not any(is_bash(b) or "mcp__" in b.get("name", "") for b in tools):
    problems.append("Odpověď tvrdí hotovo/ověřeno, ale v tomto tahu neproběhl žádný příkaz ani test. "
                    "Pravidlo: hotovo až po ověření — spusť kontrolu, nebo napiš, co ověřeno není.")
if any(commits(b) for b in tools) and not any(doc_touch(b) for b in tools):
    problems.append("Tah commitoval změnu a nedotkl se dokumentace projektu (README, HANDOFF, docs/). "
                    "Pravidlo: dokumentace patří do stejného commitu — nebo napiš, proč ji nebylo potřeba měnit.")

if not problems:
    sys.exit(0)
msg = " ".join(problems)
if MODE == "block":
    print(json.dumps({"decision": "block", "reason": msg}, ensure_ascii=False))
else:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": msg}}, ensure_ascii=False))
sys.exit(0)

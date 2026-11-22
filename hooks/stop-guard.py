#!/usr/bin/env python3
"""Stop hook (marek-cc-hooks 0.12.0).

Kontroluje poslední tah (od posledního textu uživatele):
 (a) odpověď tvrdí „hotovo/funguje/ověřeno…“, ale v tahu neproběhl žádný Bash ani test    [upozornění],
 (b) tah commitoval (`git commit`), ale nedotkl se dokumentace projektu
     (*.md, README, HANDOFF, docs/)                                                       [upozornění],
     Do 0.9.0 se (b) spouštělo po každé změně a připomínalo i zápis do báze; od 0.10.0 se do báze
     zapisuje až po Markově reakci na výsledek (pravidla.txt), proto ji Stop nepřipomíná.
 Blok otázky na konci tahu (0.7.0) je od 0.8.0 zrušený: kdy se ptát, určují pravidla (pravidla.txt).
 (c) od 0.12.0: existuje otevřená delegace (subagent/příkaz na pozadí, zadání jiné session s „HOTOVO:“)
     a žádný aktivní budík (CronCreate)                                                    [VŽDY blok]
     Kniha delegací se odvozuje z přepisu, viz hooks/dohled.py. Vypínač: MAREK_DOHLED=off.
Upozornění (a), (b): MAREK_STOP_MODE=advisory|block, výchozí advisory.
Ochrana proti smyčce: stop_hook_active -> mlčí.
Chyba skriptu = exit 0 bez výstupu.
"""
import json, os, re, sys

CODEX = os.environ.get("MAREK_HOOK_KLIENT") == "codex"
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

# (c) od 0.12.0: dohled nad delegovanou prací. Otevřená delegace bez naplánovaného probuzení = blok
# (vždy block, bez ohledu na MAREK_STOP_MODE). Kniha se odvozuje z přepisu (hooks/dohled.py); chyba = bez bloku.
dohled_msg = ""
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import dohled
    _s = dohled.scan(tp, codex=CODEX)
    if _s and _s["open"] and CODEX:
        dohled_msg = ("Dohled: otevřené delegace: %s. Ověř stav podle ID nebo dokonči jejich hlídání, "
                      "než ukončíš tah. V případě chyby uveď konkrétní stav." % dohled.describe(_s["open"]))
    elif _s and _s["open"] and not _s["alarm"]:
        _o = _s["open"]
        dohled_msg = ("Dohled: máš %d otevřených delegací a žádné naplánované probuzení: %s. "
                      "Naplánuj kontrolu (CronCreate nejvýš po 15 min), nebo delegace uzavři "
                      "(subagent/příkaz: TaskStop; zadání jiné session: její zpráva „STAV: hotovo“, "
                      "nebo ji zrušíš zprávou „STAV: zrušeno“)." % (len(_o), dohled.describe(_o)))
except Exception:
    dohled_msg = ""

if CODEX:
    import codex_transcript
    try:
        parsed = codex_transcript.turn(tp, d.get("turn_id"))
    except (OSError, ValueError):
        parsed = None
    turn = parsed[1] if parsed else []
    if parsed is None and not dohled_msg:
        sys.exit(0)
else:
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
    if CODEX and b.get("name") == "apply_patch":
        return any(DOC.search(path) for path in codex_transcript.patch_paths(i.get("command") or ""))
    return bool(DOC.search(i.get("file_path", "") if b.get("name") in ("Edit", "Write") else cmd(b)))

problems = []
if re.search(r"\b(hotovo|dokončen[oa]|funguje|opraven[oa]|vyřešen[oa]|ověřen[oa]|nasazen[oa])\b", final, re.I) \
        and not any(is_bash(b) or "mcp__" in b.get("name", "") for b in tools):
    problems.append("Odpověď tvrdí hotovo/ověřeno, ale v tomto tahu neproběhl žádný příkaz ani test. "
                    "Pravidlo: hotovo až po ověření — spusť kontrolu, nebo napiš, co ověřeno není.")
if any(commits(b) for b in tools) and not any(doc_touch(b) for b in tools):
    problems.append("Tah commitoval změnu a nedotkl se dokumentace projektu (README, HANDOFF, docs/). "
                    "Pravidlo: dokumentace patří do stejného commitu — nebo napiš, proč ji nebylo potřeba měnit.")

if not problems and not dohled_msg:
    sys.exit(0)
msg = " ".join(([dohled_msg] if dohled_msg else []) + problems)
if MODE == "block" or dohled_msg:
    print(json.dumps({"decision": "block", "reason": msg}, ensure_ascii=False))
elif CODEX:
    print(json.dumps({"systemMessage": msg}, ensure_ascii=False))
else:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": msg}}, ensure_ascii=False))
sys.exit(0)

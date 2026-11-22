#!/usr/bin/env python3
"""SessionStart hook (marek-cc-hooks 0.12.0): otevřené delegace z minula.

Při source resume a compact projde přepis session (transcript_path) toutéž funkcí jako Stop hook
(hooks/dohled.py, bez kopie kódu) a když v něm zůstaly otevřené delegace, vypíše do kontextu, co to je.
Proč: restart session zabije subagenty i procesy na pozadí a po zhuštění kontextu model na delegace zapomene
(stalo se 18. 11. 2026 ve 23:50: rozpracovaný subagent zanikl a nikdo to nezjistil).
Při startup/clear se nic nevypisuje. Vypínač: MAREK_DOHLED=off. Chyba = bez výstupu, exit 0.
"""
import json, os, sys

try:
    d = json.load(sys.stdin)
    if not isinstance(d, dict) or d.get("source") not in ("resume", "compact"):
        sys.exit(0)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import dohled
    codex = os.environ.get("MAREK_HOOK_KLIENT") == "codex"
    s = dohled.scan(d.get("transcript_path"), codex=codex)
    if s and s["open"] and codex:
        print("Otevřené delegace z minula: %s. Ověř stav podle ID; u subagenta použij jeho stav, "
              "u příkazu ověř běh procesu a výsledek. Vyřeš chyby a pokračuj." % dohled.describe(s["open"]))
    elif s and s["open"]:
        print("Otevřené delegace z minula: %s – ověř jejich stav (běží proces, čerstvý výstup, zpráva od "
              "podřízeného), než budeš pokračovat. Neběží-li, uzavři je (TaskStop) a zadej práci znovu; "
              "při běhu naplánuj kontrolu (CronCreate nejvýš po 15 min)." % dohled.describe(s["open"]))
except SystemExit:
    raise
except Exception:
    pass
sys.exit(0)

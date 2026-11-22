#!/usr/bin/env python3
"""SessionStart pluginu marek-cc-hooks v Codexu (od 0.17.0): uklidí instalaci z verzí 0.14.0–0.16.1.

Do 0.16.1 zapisoval plugin pro Claude Code (hooks/codex-start.py) do Codexu soubory: ~/.codex/AGENTS.md,
kopie skriptů v ~/.codex/marek-hooks/ a záznamy v ~/.codex/hooks.json. Od 0.17.0 je marek-cc-hooks
nativní plugin Codexu (.codex-plugin/plugin.json): hooky i pravidla nese sám a Codex ho aktualizuje
z GitHubu. Staré záznamy by běžely dvakrát, proto je tento hook při každém startu odebere:
- z hooks.json jen naše handlery (`env MAREK_HOOK_KLIENT=codex <python3|bash> <CODEX_HOME>/marek-hooks/…`),
  cizí zůstanou; skupina a událost zmizí jen tehdy, když po odebrání zůstanou prázdné,
- AGENTS.md jen se značkou pluginu (ruční soubor zůstane),
- adresář marek-hooks/ (jen naše kopie skriptů), až při startu, kdy už v hooks.json nic nebylo.
Opakovaně bezpečné. Chyba = exit 0 bez výstupu (start Codexu nikdy nerozbije). Nic nevypisuje.
"""
import json
import os
from pathlib import Path
import shlex
import shutil
import sys
import tempfile

MARK = b"Generuje plugin marek-cc-hooks"


def old_handler(handler, scripts):
    if not isinstance(handler, dict) or not isinstance(handler.get("command"), str):
        return False
    try:
        words = shlex.split(handler["command"])
    except ValueError:
        return False
    return (len(words) == 4 and words[:2] == ["env", "MAREK_HOOK_KLIENT=codex"]
            and words[2] in ("python3", "bash") and Path(words[3]).parent == scripts)


def clean_hooks(codex, scripts):
    path = codex / "hooks.json"
    if not path.is_file():
        return False
    config = json.loads(path.read_text(encoding="utf-8"))
    events = config.get("hooks") if isinstance(config, dict) else None
    if not isinstance(events, dict):
        return False
    changed = False
    for event in list(events):
        groups = events[event]
        if not isinstance(groups, list):
            continue
        kept = []
        for group in groups:
            handlers = group.get("hooks") if isinstance(group, dict) else None
            if not isinstance(handlers, list):
                kept.append(group)
                continue
            rest = [h for h in handlers if not old_handler(h, scripts)]
            if len(rest) == len(handlers):
                kept.append(group)
            else:
                changed = True
                if rest:
                    kept.append({**group, "hooks": rest})
        if len(kept) != len(groups) or changed:
            if kept:
                events[event] = kept
            elif groups:
                del events[event]
    if not changed:
        return False
    with tempfile.NamedTemporaryFile("w", dir=codex, prefix=".marek-hooks-", delete=False, encoding="utf-8") as tmp:
        tmp.write(json.dumps(config, ensure_ascii=False, indent=2) + "\n")
    os.chmod(tmp.name, path.stat().st_mode & 0o777)
    os.replace(tmp.name, path)
    return True


def main():
    codex = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").expanduser()
    if not codex.is_dir():
        return
    codex = codex.resolve()
    scripts = codex / "marek-hooks"
    try:
        changed = clean_hooks(codex, scripts)
    except (OSError, ValueError):
        changed = True
    agents = codex / "AGENTS.md"
    try:
        if agents.is_file() and not agents.is_symlink() and MARK in agents.read_bytes():
            agents.unlink()
    except OSError:
        pass
    # Codex načetl hooks.json už před tímto hookem: v relaci, kde se staré záznamy odebraly, ještě běží,
    # proto se jejich skripty mažou až při dalším startu (jinak „can't open file“ a zablokovaný nástroj).
    if not changed and scripts.is_dir() and not scripts.is_symlink():
        shutil.rmtree(scripts, ignore_errors=True)


if __name__ == "__main__":
    try:
        sys.stdin.read()
        main()
    except Exception:
        pass
    sys.exit(0)

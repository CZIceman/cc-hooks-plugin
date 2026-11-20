#!/usr/bin/env python3
"""SessionStart hook (marek-cc-hooks 0.14.0): nainstaluje pravidla pro Codex do ~/.codex/AGENTS.md.

Proč (Marek 20. 11. 2026): Codex a ChatGPT mají pracovat podle stejných pravidel jako Claude; ruční
~/.codex/AGENTS.md z 10. 10. se rozešel s pravidly Claude (ptal se před každou změnou, zakazoval push).
Zdroj je codex/AGENTS.md v pluginu; na konec se připojí místní doplněk stroje
~/.config/marek-hooks/codex-mistni.md (např. tajný topic ntfy, který nesmí do veřejného repa).
Zapisuje jen při změně obsahu. Soubor, který plugin nevytvořil (bez značky), se jednou zazálohuje
do ~/.codex/AGENTS.md.pred-pluginem[-<čas>]. Bez ~/.codex (Codex na stroji není) nic nedělá.
Nic nevypisuje, vždy exit 0. Vypínač: MAREK_CODEX_AGENTS=0.
"""
import os, sys, time

MARK = "Generuje plugin marek-cc-hooks"


def main():
    if os.environ.get("MAREK_CODEX_AGENTS", "1").strip() == "0":
        return
    home = os.path.expanduser("~")
    codex = os.path.join(home, ".codex")
    if not os.path.isdir(codex):
        return
    src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "codex", "AGENTS.md")
    text = open(src, encoding="utf-8").read().rstrip("\n") + "\n"
    local = os.path.join(home, ".config", "marek-hooks", "codex-mistni.md")
    if os.path.isfile(local):
        extra = open(local, encoding="utf-8").read().strip("\n")
        if extra:
            text += "\n" + extra + "\n"
    dst = os.path.join(codex, "AGENTS.md")
    old = None
    if os.path.exists(dst):
        old = open(dst, encoding="utf-8").read()
    if old == text:
        return
    if old is not None and MARK not in old:
        bak = dst + ".pred-pluginem"
        if os.path.exists(bak):
            bak += "-" + time.strftime("%Y%m%d-%H%M%S")
        with open(bak, "w", encoding="utf-8") as f:
            f.write(old)
        os.chmod(bak, 0o600)
    tmp = dst + ".tmp-marek-hooks"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.chmod(tmp, 0o600)
    os.replace(tmp, dst)


try:
    main()
except Exception:
    pass
sys.exit(0)

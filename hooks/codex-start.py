#!/usr/bin/env python3
"""SessionStart hook (marek-cc-hooks 0.14.0): nainstaluje pravidla pro Codex do ~/.codex/AGENTS.md.

Proč (Marek 20. 11. 2026): Codex a ChatGPT mají pracovat podle stejných pravidel jako Claude; ruční
~/.codex/AGENTS.md z 10. 10. se rozešel s pravidly Claude (ptal se před každou změnou, zakazoval push).
Zdroj je codex/AGENTS.md v pluginu; na konec se připojí místní doplněk stroje
~/.config/marek-hooks/codex-mistni.md (např. tajný topic ntfy, který nesmí do veřejného repa).
Zapisuje jen při změně obsahu. Soubor, který plugin nevytvořil (bez značky), se jednou zazálohuje
do ~/.codex/AGENTS.md.pred-pluginem[-<čas>]. Bez ~/.codex (Codex na stroji není) nic nedělá.
Od 0.15.2 instaluje i strážce: kopii hooks/pretool-guard.py do ~/.codex/marek-hooks/ (stálá cesta, synced složka
pluginu se mění) a do ~/.codex/hooks.json události PreToolUse a PermissionRequest s `MAREK_HOOK_KLIENT=codex`
(vlastní záznamy pozná podle cesty, cizí hooky nechá). Vypínač strážce: MAREK_CODEX_HOOKS=0 (záznamy odebere).
Nic nevypisuje, vždy exit 0. Vypínač pravidel: MAREK_CODEX_AGENTS=0.
"""
import json, os, shutil, sys, time

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


def write_if_changed(path, text, mode=0o600):
    if os.path.exists(path) and open(path, encoding="utf-8").read() == text:
        return
    tmp = path + ".tmp-marek-hooks"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.chmod(tmp, mode)
    os.replace(tmp, path)


def hooks():
    """Strážce pro Codex: kopie pretool-guard.py + záznamy v ~/.codex/hooks.json."""
    codex = os.path.join(os.path.expanduser("~"), ".codex")
    if not os.path.isdir(codex):
        return
    on = os.environ.get("MAREK_CODEX_HOOKS", "1").strip() != "0"
    dst_dir = os.path.join(codex, "marek-hooks")
    guard = os.path.join(dst_dir, "pretool-guard.py")
    if on:
        os.makedirs(dst_dir, exist_ok=True)
        src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pretool-guard.py")
        write_if_changed(guard, open(src, encoding="utf-8").read(), 0o700)
    hj = os.path.join(codex, "hooks.json")
    try:
        cfg = json.load(open(hj, encoding="utf-8")) if os.path.exists(hj) else {}
    except ValueError:
        return  # rozbitý cizí soubor nepřepisovat
    if not isinstance(cfg, dict):
        return
    hk = cfg.setdefault("hooks", {})
    cmd = "env MAREK_HOOK_KLIENT=codex python3 " + guard
    for ev in ("PreToolUse", "PermissionRequest"):
        lst = [g for g in hk.get(ev, []) if not any("marek-hooks/pretool-guard.py" in (h.get("command") or "")
                                                    for h in g.get("hooks", []) if isinstance(h, dict))]
        if on:
            lst.append({"hooks": [{"type": "command", "command": cmd}]})
        if lst:
            hk[ev] = lst
        else:
            hk.pop(ev, None)
    write_if_changed(hj, json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")


for _f in (main, hooks):
    try:
        _f()
    except Exception:
        pass
sys.exit(0)

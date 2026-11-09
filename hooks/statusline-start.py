#!/usr/bin/env python3
"""SessionStart: nainstaluje stavovou řádku (statusline/statusline.py) na tento stroj.

Plugin neumí nastavit hlavní `statusLine` přes vlastní settings.json (podporuje jen `agent`
a `subagentStatusLine`), proto to dělá tento hook:
  1. zkopíruje skript pluginu do ~/.claude/marek-statusline/statusline.py (jen když se liší;
     cesta v pluginu se mění s verzí, kopie má stálou cestu),
  2. doplní `statusLine` do ~/.claude/settings.json, pokud chybí, nebo pokud je to náš starší
     ruční záznam. Cizí statusLine nechá být; neplatný settings.json nechá být.
MAREK_STATUSLINE=0 = hook nedělá nic.
Jen standardní knihovna. Nikdy nic na stdout ani stderr (stdout by šel do kontextu), vždy exit 0.
"""
import json
import os
import shlex
import sys
import tempfile

ZNACKY = ("marek-statusline/statusline.py", "cc-hooks-plugin/statusline/statusline.py")


def zapis_atomicky(cesta, data, mod):
    """Zapíše bajty přes dočasný soubor ve stejném adresáři + os.replace."""
    adresar = os.path.dirname(cesta)
    fd, tmp = tempfile.mkstemp(dir=adresar, prefix=".tmp-statusline-")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.chmod(tmp, mod)
        os.replace(tmp, cesta)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def zkopiruj_skript(zdroj, cil):
    """Vrátí True, když cíl po běhu existuje a odpovídá zdroji."""
    with open(zdroj, "rb") as f:
        novy = f.read()
    try:
        with open(cil, "rb") as f:
            if f.read() == novy:
                return True
    except OSError:
        pass
    os.makedirs(os.path.dirname(cil), exist_ok=True)
    zapis_atomicky(cil, novy, 0o755)
    return True


def uprav_settings(cesta, standard):
    cesta = os.path.realpath(cesta)  # symlink zachovat (replace by ho jinak přepsalo souborem)
    if not os.path.exists(cesta):
        os.makedirs(os.path.dirname(cesta), exist_ok=True)
        zapis_atomicky(cesta, (json.dumps({"statusLine": standard}, indent=2, ensure_ascii=False) + "\n").encode("utf-8"), 0o644)
        return
    with open(cesta, "rb") as f:
        syrove = f.read()
    try:
        data = json.loads(syrove.decode("utf-8"))
    except ValueError:
        return
    if not isinstance(data, dict):
        return
    if "statusLine" not in data:
        data["statusLine"] = standard
    else:
        sl = data["statusLine"]
        prikaz = sl.get("command") if isinstance(sl, dict) else None
        nase = isinstance(prikaz, str) and any(z in prikaz for z in ZNACKY)
        if not nase or sl == standard:
            return
        data["statusLine"] = standard
    novy = (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    if novy == syrove:
        return
    zapis_atomicky(cesta, novy, os.stat(cesta).st_mode & 0o7777)


def main():
    if os.environ.get("MAREK_STATUSLINE") == "0":
        return
    koren = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    zdroj = os.path.join(koren, "statusline", "statusline.py")
    domov = os.path.expanduser("~")
    cil = os.path.join(domov, ".claude", "marek-statusline", "statusline.py")
    if not zkopiruj_skript(zdroj, cil):
        return
    standard = {"type": "command", "command": "python3 " + shlex.quote(cil), "refreshInterval": 30}
    uprav_settings(os.path.join(domov, ".claude", "settings.json"), standard)


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        pass
    sys.exit(0)

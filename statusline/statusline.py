#!/usr/bin/env python3
"""Stavová řádka (statusLine) pro Claude Code.

Claude Code pošle na stdin JSON a zobrazí první řádek stdoutu. Skript nikdy nepadá
a nic nepíše na stderr; každý segment je ve vlastním try, takže chyba jednoho
segmentu neovlivní ostatní. Jen standardní knihovna.

Segmenty (oddělené šedým ' │ '): model, kontext (kolik zbývá), cache, 5h okno, týdenní okno
(obě s předpovědí vyčerpání), projekt (odkaz OSC 8), git, odkládací složka (odkaz OSC 8).
Nic se nikam nezapisuje.
"""
import json
import math
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote

ZELENA, ZLUTA, CERVENA, SEDA = "32", "33", "31", "90"
RESET = "\033[0m"
ODDELOVAC = f"\033[{SEDA}m │ {RESET}"


def barva(kod, text):
    return f"\033[{kod}m{text}{RESET}"


def odkaz(url, text):
    """Klikací odkaz OSC 8."""
    return f"\033]8;;{url}\033\\{text}\033]8;;\033\\"


def file_url(cesta):
    return "file://" + quote(os.path.abspath(cesta), safe="/")


def pole(data, *klice):
    """Bezpečné čtení vnořeného pole; chybějící/null vrací None."""
    for k in klice:
        if not isinstance(data, dict):
            return None
        data = data.get(k)
    return data


def cislo(v):
    """Číslo, nebo None (bool a řetězce se nepřijímají)."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return v


def nyni():
    try:
        return float(os.environ["MAREK_SL_NOW"])
    except (KeyError, ValueError):
        return time.time()


def barva_prahu(pct):
    return ZELENA if pct < 50 else ZLUTA if pct < 80 else CERVENA


# ---------------------------------------------------------------- segmenty

def seg_model(d, now):
    n = pole(d, "model", "display_name")
    n = n if isinstance(n, str) and n else ""
    e = pole(d, "effort", "level")          # úsilí: low / medium / high / …
    if isinstance(e, str) and e:
        n = f"{n} · {e}" if n else e
    return n


def seg_kontext(d, now):
    used = cislo(pole(d, "context_window", "used_percentage"))
    zbyva = cislo(pole(d, "context_window", "remaining_percentage"))
    if used is None and zbyva is None:
        return ""
    if used is None:
        used = 100 - zbyva
    if zbyva is None:
        zbyva = 100 - used
    plne = max(0, min(10, int(used / 10 + 0.5)))   # pruh se plní podle spotřeby
    return barva(barva_prahu(used), "█" * plne + "░" * (10 - plne) + f" zbývá {int(round(zbyva))}%")


def seg_cache(d, now):
    c = pole(d, "prompt_cache")
    if not isinstance(c, dict) or c.get("warm") is not True:
        return ""
    exp = cislo(c.get("expires_at"))
    if exp is None:
        return ""
    zbyva = exp - now
    ttl5 = c.get("ttl") == "5m"
    if zbyva <= 0 or zbyva > (120 if ttl5 else 900):
        return ""
    if zbyva < 60:
        text = "⧗ <1 min"
    else:
        text = f"⧗ {math.ceil(zbyva / 60)} min"
    return barva(CERVENA if ttl5 or zbyva < 300 else ZLUTA, text)


def doba(sekundy):
    """Pod 24 h H:MM, jinak Nd Nh."""
    sekundy = max(0, int(sekundy))
    if sekundy < 86400:
        return f"{sekundy // 3600}:{sekundy % 3600 // 60:02d}"
    return f"{sekundy // 86400}d {sekundy % 86400 // 3600}h"


def okno(d, now, klic, delka, popisek, min_uplynulo):
    """Segment okna předplatného: '<popisek> zbývá NN% · čas do resetu [⚠ dojde za …]'."""
    used = cislo(pole(d, "rate_limits", klic, "used_percentage"))
    if used is None:
        return ""
    zbyva = max(0, min(100, 100 - used))
    text = f"{popisek} zbývá " + barva(ZELENA if zbyva > 50 else ZLUTA if zbyva > 20 else CERVENA, f"{int(round(zbyva))}%")
    resets = cislo(pole(d, "rate_limits", klic, "resets_at"))
    if resets is None:
        return text
    do_resetu = resets - now
    text += " · " + doba(do_resetu)
    uplynulo = delka - do_resetu
    if uplynulo >= min_uplynulo and used > 0:
        dojde = (100 - used) / (used / uplynulo)   # zbývající % při dosavadním tempu
        if dojde < do_resetu:
            text += " " + barva(CERVENA, f"⚠ dojde za {doba(dojde)}")
    return text


def seg_5h(d, now):
    return okno(d, now, "five_hour", 5 * 3600, "5h", 600)


def seg_tyden(d, now):
    return okno(d, now, "seven_day", 7 * 86400, "týden", 6 * 3600)


def seg_projekt(d, now):
    p = pole(d, "workspace", "project_dir")
    if not (isinstance(p, str) and p):
        return ""
    text = p
    home = os.path.expanduser("~").rstrip("/")
    if home and (p == home or p.startswith(home + "/")):
        text = "~" + p[len(home):]
    return odkaz(file_url(p), text)


def _git(cwd, args):
    r = subprocess.run(["git", "--no-optional-locks", "-C", cwd, *args], capture_output=True,
                       text=True, timeout=1, env={**os.environ, "LC_ALL": "C"}, stdin=subprocess.DEVNULL)
    return r.stdout if r.returncode == 0 else None


def seg_git(d, now):
    cwd = d.get("cwd")
    if not (isinstance(cwd, str) and os.path.isdir(cwd)):
        return ""
    with ThreadPoolExecutor(2) as ex:
        f_stav = ex.submit(_git, cwd, ["status", "--porcelain", "-b"])
        f_dir = ex.submit(_git, cwd, ["rev-parse", "--git-dir", "--git-common-dir"])
        try:
            stav, dirs = f_stav.result(), f_dir.result()
        except Exception:
            return ""
    if stav is None:
        return ""
    radky = stav.splitlines()
    if not radky or not radky[0].startswith("## "):
        return ""
    hlavicka = radky[0][3:]
    m = re.match(r"(?:No commits yet on |Initial commit on )(.+)$", hlavicka)
    if m:
        vetev = m.group(1)
    elif hlavicka.startswith("HEAD (no branch)"):
        vetev = "HEAD"
    else:
        vetev = re.split(r"\.\.\.| \[", hlavicka)[0]
    pred = 0
    m = re.search(r"\[ahead (\d+)", hlavicka)
    if m:
        pred = int(m.group(1))
    zmeneno = sum(1 for r in radky[1:] if r and not r.startswith("??"))
    nove = sum(1 for r in radky[1:] if r.startswith("??"))
    worktree = False
    if dirs:
        r = dirs.splitlines()
        if len(r) >= 2:
            worktree = (os.path.realpath(os.path.join(cwd, r[0])) != os.path.realpath(os.path.join(cwd, r[1])))
    text = ("🌿 " if worktree else "") + vetev
    cisla = []
    if zmeneno:
        cisla.append(f"±{zmeneno}")
    if nove:
        cisla.append(f"+{nove}")
    if cisla:
        text += " " + barva(ZLUTA, " ".join(cisla))
    if pred:
        text += f" ↑{pred}"
    return text


def seg_scratch(d, now):
    s = d.get("scratchpad_dir")
    if isinstance(s, str) and s and os.path.isdir(s) and os.listdir(s):
        return odkaz(file_url(s), "📁 scratch")
    return ""


SEGMENTY = (seg_model, seg_kontext, seg_cache, seg_5h, seg_tyden, seg_projekt, seg_git, seg_scratch)


def main():
    sys.stderr = open(os.devnull, "w")
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    try:
        d = json.load(sys.stdin)
    except Exception:
        d = {}
    if not isinstance(d, dict):
        d = {}
    now = nyni()
    casti = []
    for seg in SEGMENTY:
        try:
            t = seg(d, now)
            if t:
                casti.append(t)
        except Exception:
            pass
    print(ODDELOVAC.join(casti))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)

#!/usr/bin/env python3
"""Pošle potvrzení příjmu „[ACK] Přijato HH:MM“ na tajný topic ntfy.

Použití: ntfy-ack.py <klíč>            (klíč = název záznamu v ~/.config/marek-hooks/ntfy.json)
Konfigurace (mimo repo, práva 600):
  {"server": "https://ntfy.lumatech.cz", "topics": {"<klíč>": "<tajný topic, ≥ 26 znaků [a-z0-9]>"}}
Server je otevřený (anonymní čtení i zápis), bezpečnost stojí na tajném jménu topicu (báze:
znalosti/site/ntfy-lumatech-server.md). Proto: topic se nikdy nevypisuje ani neloguje, zpráva nenese
nic citlivého. MAREK_NTFY_DRYRUN=1 nic neodesílá, jen vypíše, že by odeslal (bez topicu).
Návratové kódy: 0 odesláno, 2 chybná konfigurace nebo klíč, 3 server neodpověděl 200.
"""
import json, os, re, sys, time, urllib.request, urllib.error

if len(sys.argv) != 2:
    print("Použití: ntfy-ack.py <klíč>", file=sys.stderr); sys.exit(2)
key = sys.argv[1]
try:
    cfg = json.load(open(os.path.expanduser("~/.config/marek-hooks/ntfy.json"), encoding="utf-8"))
    topic = cfg["topics"][key]
    server = (cfg.get("server") or "https://ntfy.lumatech.cz").rstrip("/")
except (OSError, ValueError, KeyError, TypeError):
    print("Chyba: chybí ~/.config/marek-hooks/ntfy.json nebo v něm klíč „%s“." % key, file=sys.stderr); sys.exit(2)
if not isinstance(topic, str) or not re.fullmatch(r"[a-z0-9]{26,}", topic):
    print("Chyba: topic pro klíč „%s“ nemá požadovaný tvar (≥ 26 znaků [a-z0-9])." % key, file=sys.stderr); sys.exit(2)

payload = {"topic": topic, "title": "Potvrzení příjmu", "message": "[ACK] Přijato %s" % time.strftime("%H:%M"),
           "priority": 2, "tags": ["white_check_mark"]}
if os.environ.get("MAREK_NTFY_DRYRUN") == "1":
    print("DRYRUN: odeslal bych potvrzení na %s (klíč %s)" % (server, key)); sys.exit(0)
req = urllib.request.Request(server + "/", data=json.dumps(payload).encode("utf-8"),
                             headers={"Content-Type": "application/json"}, method="POST")
try:
    with urllib.request.urlopen(req, timeout=10) as r:
        body = json.loads(r.read().decode("utf-8"))
        if r.status != 200:
            print("Chyba: server vrátil HTTP %s." % r.status, file=sys.stderr); sys.exit(3)
except (urllib.error.URLError, OSError, ValueError) as e:
    print("Chyba: odeslání selhalo (%s)." % type(e).__name__, file=sys.stderr); sys.exit(3)
print("Potvrzení odesláno (id %s)." % body.get("id", "?"))

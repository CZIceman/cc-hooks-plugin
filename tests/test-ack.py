#!/usr/bin/env python3
"""Test ack-guard.py (UserPromptSubmit) a ntfy-ack.py bez modelu. Síťový test jen s MAREK_TEST_NET=1."""
import json, os, secrets, subprocess, sys, tempfile, urllib.request
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hooks")
RT = tempfile.mkdtemp()

def home_with(ack=None, ntfy=None):
    h = tempfile.mkdtemp(); c = os.path.join(h, ".config", "marek-hooks"); os.makedirs(c)
    if ack is not None: open(os.path.join(c, "ack.json"), "w").write(ack if isinstance(ack, str) else json.dumps(ack))
    if ntfy is not None: open(os.path.join(c, "ntfy.json"), "w").write(json.dumps(ntfy))
    return h

def ack(prompt, home=None, raw=None, env=None):
    e = {**os.environ, "HOME": home or home_with(), "XDG_RUNTIME_DIR": RT, **(env or {})}
    r = subprocess.run([sys.executable, os.path.join(D, "ack-guard.py")], capture_output=True, text=True, env=e,
                       input=raw if raw is not None else json.dumps({"prompt": prompt, "session_id": "s1", "hook_event_name": "UserPromptSubmit"}))
    o = r.stdout.strip()
    return r.returncode, ("-" if not o else "ctx"), o

bad = 0
def chk(n, got, exp, extra=True, why=""):
    global bad
    ok = got == exp and extra
    bad += not ok
    print("OK  " if ok else "CHYBA", f"{n:44} -> {got} (čekáno {exp}){'' if extra else ' ' + why}")

MSG = '<message from="agent-dc" id="7">Spusť test sítě</message>'
rc, dec, o = ack(MSG);                       chk("zpráva s atributem from -> ctx", (rc, dec), (0, "ctx"))
chk("  pokyn: SendMessage to = from, [ACK]", True, True, "to = agent-dc" in o and "[ACK] Přijato" in o, o)
chk("  pokyn: potvrzení není souhlas", True, True, "není souhlas člověka" in o, o)
rc, dec, o = ack('<message from="agent-dc">[ACK] Přijato 10:00</message>'); chk("zpráva s [ACK] se nepotvrzuje (bez smyčky)", (rc, dec), (0, "-"))
rc, dec, o = ack("Oprav chybu v main.py");  chk("běžný prompt uživatele -> nic", (rc, dec), (0, "-"))
rc, dec, o = ack("x", raw="{nejson");        chk("rozbitý vstup = nic, rc 0", (rc, dec), (0, "-"))
rc, dec, o = ack("x", raw=json.dumps({"session_id": "s"})); chk("bez pole prompt = nic", (rc, dec), (0, "-"))
rc, dec, o = ack(MSG, home=home_with(ack={"enabled": False})); chk("enabled=false -> nic", (rc, dec), (0, "-"))
rc, dec, o = ack("[od: agent-x] ahoj", home=home_with(ack={"patterns": [r"\[od: (?P<from>[\w-]+)\]"]}))
chk("vlastní vzor z ack.json", (rc, dec), (0, "ctx"), "to = agent-x" in o, o)
rc, dec, o = ack("[od: agent-x] ahoj", home=home_with(ack={"patterns": ["[neplatny", r"\[od: (?P<from>[\w-]+)\]"]}))
chk("neplatný regex se přeskočí", (rc, dec), (0, "ctx"))
rc, dec, o = ack("ntfy#abc: hotovo", home=home_with(ack={"ntfy_patterns": [r"ntfy#(?P<klic>\w+):"]}))
chk("ntfy vzor -> pokyn s ntfy-ack.py", (rc, dec), (0, "ctx"), "ntfy-ack.py" in o and " abc`" in o, o)
rc, dec, o = ack("ntfy#abc: hotovo")
chk("ntfy bez konfigurace = vypnuto", (rc, dec), (0, "-"))
cap = os.path.join(RT, "marek-hooks", "ack-capture.jsonl")
chk("capture je výchozně vypnutý", os.path.exists(cap), False)
ack("tajný text " + "x" * 600, env={"MAREK_ACK_CAPTURE": "1"})
rec = json.loads(open(cap).readline()) if os.path.exists(cap) else {}
chk("capture zapnutý: záznam, prompt ořezán na 400", len(rec.get("prompt_zacatek", "")), 400)

# --- ntfy-ack.py ---
def ntfy(key, home, env=None):
    r = subprocess.run([sys.executable, os.path.join(D, "ntfy-ack.py"), key], capture_output=True, text=True,
                       env={**os.environ, "HOME": home, **(env or {})})
    return r.returncode, r.stdout + r.stderr
TOPIC = "t" + secrets.token_hex(15)           # 31 znaků [a-z0-9], jen pro test
h = home_with(ntfy={"topics": {"k1": TOPIC, "kratky": "abc"}})
rc, o = ntfy("k1", h, {"MAREK_NTFY_DRYRUN": "1"}); chk("ntfy-ack dry-run rc 0", rc, 0); chk("  topic se nevypíše", TOPIC in o, False)
rc, o = ntfy("kratky", h);                          chk("ntfy-ack: topic ve špatném tvaru -> rc 2", rc, 2)
rc, o = ntfy("neexistuje", h);                      chk("ntfy-ack: neznámý klíč -> rc 2", rc, 2)
rc, o = ntfy("k1", home_with());                    chk("ntfy-ack: bez konfigurace -> rc 2", rc, 2)
if os.environ.get("MAREK_TEST_NET") == "1":
    rc, o = ntfy("k1", h);                          chk("SÍŤ: ntfy-ack odeslal (rc 0)", rc, 0); chk("  výstup nevypíše topic", TOPIC in o, False)
    body = urllib.request.urlopen(f"https://ntfy.lumatech.cz/{TOPIC}/json?poll=1", timeout=10).read().decode()
    msg = json.loads(body.strip().splitlines()[-1]).get("message", "")
    chk("SÍŤ: zpráva dorazila a nese [ACK]", msg.startswith("[ACK] Přijato"), True)
print("ack: selhalo", bad)
sys.exit(1 if bad else 0)

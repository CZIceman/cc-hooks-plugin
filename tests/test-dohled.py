#!/usr/bin/env python3
"""Test dohledu nad delegovanou prací (0.12.0): Stop hook (blok), SessionStart (otevřené delegace z minula)
a modul dohled.py na syntetických přepisech. Tvary záznamů jsou převzaté ze skutečných přepisů
(~/.claude/projects/*/*.jsonl, viz README „Od 0.12.0“)."""
import json, os, subprocess, sys, tempfile, time
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hooks")
sys.path.insert(0, D)
import dohled

NOW = time.time()
iso = lambda t: time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(t))
J = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":"))
_n = [0]
def nid(p="toolu_"):
    _n[0] += 1; return "%s%04d" % (p, _n[0])

def use(name, inp, tid, ts=None):
    return {"type": "assistant", "timestamp": iso(ts or NOW), "message": {"role": "assistant", "content": [
        {"type": "tool_use", "id": tid, "name": name, "input": inp, "caller": {"type": "direct"}}]}}
def res(tid, text, tur=None, err=False, ts=None):
    r = {"type": "user", "timestamp": iso(ts or NOW), "message": {"role": "user", "content": [
        {"tool_use_id": tid, "type": "tool_result", "content": text, **({"is_error": True} if err else {})}]}}
    if tur is not None: r["toolUseResult"] = tur
    return r
def agent(desc="Výpočet A", bg=True, tid=None, aid="a0123456789abcdef", ok=True):
    tid = tid or nid()
    inp = {"description": desc, "prompt": "HOTOVO: x PŘI CHYBĚ: y"}
    if bg is not None: inp["run_in_background"] = bg
    items = [use("Agent", inp, tid)]
    if ok:
        items.append(res(tid, "Async agent launched successfully.\nagentId: %s (internal ID)" % aid,
                         {"isAsync": True, "status": "async_launched", "agentId": aid, "description": desc}))
    else:
        items.append(res(tid, "chyba", "Error: chyba", err=True))
    return tid, aid, items
def bash(desc="Čekat na soubor", bid="bq1abcdef", tid=None):
    tid = tid or nid()
    return tid, bid, [use("Bash", {"command": "sleep 100", "description": desc, "run_in_background": True}, tid),
        res(tid, "Command running in background with ID: %s. Output is being written to: /tmp/x.output." % bid,
            {"stdout": "", "stderr": "", "backgroundTaskId": bid})]
def note(task, tid, status="completed", summary="Agent finished", result=""):
    body = ("<task-notification>\n<task-id>%s</task-id>\n<tool-use-id>%s</tool-use-id>\n<output-file>/tmp/o</output-file>\n"
            "<status>%s</status>\n<summary>%s</summary>\n<result>%s</result>\n</task-notification>" % (task, tid, status, summary, result))
    return {"type": "user", "message": {"role": "user", "content": body}, "origin": {"kind": "task-notification"}}
def note_att(task, tid):
    body = note(task, tid)["message"]["content"]
    return {"type": "attachment", "attachment": {"type": "queued_command", "prompt": body, "commandMode": "task-notification"}}
def orphan(*tasks):
    body = ("<task-notification>\n%s\n<task-id>__orphan_summary__:shell</task-id>\n<status>stopped</status>\n"
            "<summary>2 background shell command tasks didn't finish before the previous session ended.</summary>\n</task-notification>"
            % "\n".join("<task-id>%s</task-id>" % t for t in tasks))
    return {"type": "user", "message": {"role": "user", "content": body}, "origin": {"kind": "task-notification"}}
def stop(task):
    tid = nid(); return [use("TaskStop", {"task_id": task}, tid), res(tid, "{\"message\":\"Successfully stopped task\"}", {"task_id": task})]
def cron(rec=True, nxt=None, age=0, cid=None):
    tid, cid = nid(), cid or nid("c")
    inp = {"cron": "*/10 * * * *", "prompt": "zkontroluj"}
    if rec is not None: inp["recurring"] = rec
    ts = NOW - age
    return cid, [use("CronCreate", inp, tid, ts), res(tid, "Scheduled job %s" % cid,
        {"id": cid, "recurring": bool(rec), "durable": False, "nextFireAt": (nxt if nxt is not None else (NOW + 600) * 1000)}, ts=ts)]
def crondel(cid):
    tid = nid(); return [use("CronDelete", {"id": cid}, tid), res(tid, "Cancelled job %s." % cid, {"id": cid})]
def send(to, msg, kind="session", tid=None, ok=True):
    tid = tid or nid()
    return [use("SendMessage", {"to": to, "message": msg, "summary": "Zadání výpočtu", "type": "message",
                                "recipient": to, "recipient_kind": kind, "content": msg[:40] + "…"}, tid),
            res(tid, "{\"success\":true}", {"success": ok, "msg_id": "m1"})]
def peer(frm, name, body):
    return {"type": "user", "isMeta": True, "message": {"role": "user", "content": "Another Claude session sent a message:\n<cross-session-message>…"},
            "origin": {"kind": "peer", "from": frm, "name": name, "fromMode": "prompting", "body": body}}
def peer_att(frm, name, body):
    return {"type": "attachment", "attachment": {"type": "queued_command", "prompt": "<cross-session-message>", "commandMode": "prompt",
            "origin": {"kind": "peer", "from": frm, "name": name, "body": body}}}
USER = {"type": "user", "message": {"role": "user", "content": "uděláš to?"}}
FINAL = {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "Zadáno."}]}}

def tr(items, raw=None):
    f = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8")
    for i in items: f.write(J(i) + "\n")
    if raw: f.write(raw)
    f.close(); return f.name
def cat(*parts):
    out = []
    for p in parts: out += p
    return out
def stopdec(items, env=None, **kw):
    r = subprocess.run([sys.executable, os.path.join(D, "stop-guard.py")], capture_output=True, text=True,
        input=json.dumps({"transcript_path": tr(items + [FINAL]), "last_assistant_message": "Zadáno.", **kw}),
        env={**os.environ, **(env or {})})
    o = r.stdout.strip()
    return r.returncode, ("-" if not o else ("block" if '"block"' in o else "ctx")), o
def start(items, source):
    r = subprocess.run([sys.executable, os.path.join(D, "dohled-start.py")], capture_output=True, text=True,
        input=json.dumps({"transcript_path": tr(items), "source": source, "hook_event_name": "SessionStart"}))
    return r.returncode, r.stdout.strip()

bad = 0; total = 0
def check(name, got, exp):
    global bad, total
    total += 1; ok = got == exp; bad += not ok
    print("OK  " if ok else "CHYBA", f"{name:52} -> {got!s:7} (čekáno {exp})")

t1, a1, ag1 = agent()
t2, b2, ba2 = bash()
cid1, cr1 = cron()
# ---------- Stop: kniha z přepisu ----------
check("Agent na pozadí bez budíku -> block", stopdec([USER] + ag1)[1], "block")
check("  důvod nese popis a počet", all(s in stopdec([USER] + ag1)[2] for s in ("1 otevřených", "Výpočet A", a1, "CronCreate")), True)
check("  + recurring budík -> nic", stopdec([USER] + ag1 + cr1)[1], "-")
check("  + one-shot v budoucnu -> nic", stopdec([USER] + ag1 + cron(False, (NOW + 3600) * 1000)[1])[1], "-")
check("  + one-shot už prošlý -> block", stopdec([USER] + ag1 + cron(False, (NOW - 60) * 1000)[1])[1], "block")
check("  + recurring starší 7 dní -> block", stopdec([USER] + ag1 + cron(True, age=8 * 86400)[1])[1], "block")
check("  + recurring 6 dní starý -> nic", stopdec([USER] + ag1 + cron(True, age=6 * 86400)[1])[1], "-")
check("  + budík smazaný CronDelete -> block", stopdec([USER] + ag1 + cr1 + crondel(cid1))[1], "block")
check("  recurring bez klíče recurring (výchozí true)", stopdec([USER] + ag1 + cron(None, nxt=None)[1])[1], "-")
check("task-notification completed -> nic", stopdec([USER] + ag1 + [note(a1, t1)])[1], "-")
check("task-notification failed -> nic", stopdec([USER] + ag1 + [note(a1, t1, "failed")])[1], "-")
check("task-notification killed -> nic", stopdec([USER] + ag1 + [note(a1, t1, "killed")])[1], "-")
check("task-notification jako attachment -> nic", stopdec([USER] + ag1 + [note_att(a1, t1)])[1], "-")
check("mezitímní oznámení (waiting on…) -> block", stopdec([USER] + ag1 + [note(a1, t1, "completed",
      'Agent "x" is waiting on its own background work', "This agent has not reported yet: it is waiting on its own background work")])[1], "block")
check("  pak konečné oznámení -> nic", stopdec([USER] + ag1 + [note(a1, t1, "completed", "waiting on its own background work", "has not reported yet"), note(a1, t1)])[1], "-")
check("oznámení jiného ID nic nezavře", stopdec([USER] + ag1 + [note("jine", "toolu_jine")])[1], "block")
check("TaskStop uzavře", stopdec([USER] + ag1 + stop(a1))[1], "-")
check("Bash na pozadí bez budíku -> block", stopdec([USER] + ba2)[1], "block")
check("  oznámení uzavře (podle task-id)", stopdec([USER] + ba2 + [note(b2, t2, summary="Background command completed")])[1], "-")
check("  sběrné oznámení po restartu uzavře", stopdec([USER] + ba2 + [orphan(b2, "bjine")])[1], "-")
check("  TaskStop uzavře", stopdec([USER] + ba2 + stop(b2))[1], "-")
check("Agent v popředí není delegace", stopdec([USER] + agent(bg=None)[2])[1], "-")
check("Agent run_in_background \"true\" (řetězec)", stopdec([USER] + agent(bg="true")[2])[1], "block")
check("Agent run_in_background false", stopdec([USER] + agent(bg=False)[2])[1], "-")
check("spuštění selhalo (is_error) není delegace", stopdec([USER] + agent(ok=False)[2])[1], "-")
check("dvě delegace, jedna uzavřena -> block s 1", "1 otevřených" in stopdec([USER] + ag1 + agent("B", aid="ab")[2] + [note(a1, t1)])[2], True)
# (c) zadání jiné session
PEER = "bridge:session_017ABC"
M = "HOTOVO: soubor tabulka.csv. ODHAD: 30 min. SIGNÁL: každých 10 min. PŘI CHYBĚ: opravit a hlásit."
check("zadání jiné session s HOTOVO: -> block", stopdec([USER] + send(PEER, M))[1], "block")
check("  zpráva [ACK] se nepočítá", stopdec([USER] + send(PEER, "[ACK] přijato, HOTOVO: …"))[1], "-")
check("  zpráva STAV: se nepočítá", stopdec([USER] + send(PEER, "STAV: běží; HOTOVO: …"))[1], "-")
check("  zpráva bez HOTOVO: se nepočítá", stopdec([USER] + send(PEER, "Pošli mi stav"))[1], "-")
check("  zpráva pro main se nepočítá", stopdec([USER] + send("main", M, kind="name"))[1], "-")
check("  adresát podle jména (recipient_kind name)", stopdec([USER] + send("Worker", M, kind="name"))[1], "block")
check("  zpráva subagentovi (kind agent) se nepočítá", stopdec([USER] + send("a1234", M, kind="agent"))[1], "-")
check("  odeslání nepotvrzeno -> není delegace", stopdec([USER] + send(PEER, M, ok=False))[1], "-")
check("  STAV: hotovo od téže session uzavře", stopdec([USER] + send(PEER, M) + [peer(PEER, "Worker", "STAV: hotovo. Výsledek v /x")])[1], "-")
check("  STAV: zrušeno od téže session uzavře", stopdec([USER] + send(PEER, M) + [peer(PEER, "Worker", "STAV: zrušeno")])[1], "-")
check("  STAV: hotovo jako attachment uzavře", stopdec([USER] + send(PEER, M) + [peer_att(PEER, "Worker", "STAV: hotovo")])[1], "-")
check("  uzavření podle jména odesílatele", stopdec([USER] + send("Worker", M, kind="name") + [peer(PEER, "Worker", "STAV: hotovo")])[1], "-")
check("  STAV: hotovo od jiné session neuzavře", stopdec([USER] + send(PEER, M) + [peer("bridge:session_JINA", "Jina", "STAV: hotovo")])[1], "block")
check("  zpráva od téže session bez STAV: neuzavře", stopdec([USER] + send(PEER, M) + [peer(PEER, "Worker", "[ACK] přijato")])[1], "block")
check("  vlastní odchozí STAV: zrušeno uzavře", stopdec([USER] + send(PEER, M) + send(PEER, "STAV: zrušeno, úkol neplatí"))[1], "-")
check("  příchozí STAV: hotovo PŘED zadáním neuzavře", stopdec([USER, peer(PEER, "Worker", "STAV: hotovo")] + send(PEER, M))[1], "block")
# ---------- ochrany ----------
check("stop_hook_active mlčí", stopdec([USER] + ag1, stop_hook_active=True)[1], "-")
check("MAREK_DOHLED=off vypíná", stopdec([USER] + ag1, env={"MAREK_DOHLED": "off"})[1], "-")
check("MAREK_STOP_MODE=advisory: dohled blokuje i tak", stopdec([USER] + ag1, env={"MAREK_STOP_MODE": "advisory"})[1], "block")
check("rozbité řádky v přepisu -> rc 0", subprocess.run([sys.executable, os.path.join(D, "stop-guard.py")], capture_output=True, text=True,
      input=json.dumps({"transcript_path": tr([USER] + ag1, raw='{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Agent"\n{špatně\n')})).returncode, 0)
check("chybějící přepis -> nic", subprocess.run([sys.executable, os.path.join(D, "stop-guard.py")], capture_output=True, text=True,
      input=json.dumps({"transcript_path": "/nonexistent/x.jsonl"})).stdout.strip(), "")
bad_line = tr([USER] + ag1, raw='{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Agent","input":{"run_in_background":true\n')
check("scan: polámaný řádek se přeskočí, delegace zůstane", (lambda r: len(r["open"]))(dohled.scan(bad_line)), 1)
check("scan: nečitelný soubor (adresář) -> None", dohled.scan("/tmp"), None)
# ---------- SessionStart ----------
rc, o = start([USER] + ag1 + ba2, "resume")
check("resume s otevřenými delegacemi vypíše", rc == 0 and o.startswith("Otevřené delegace z minula:") and "Výpočet A" in o and "ověř jejich stav" in o, True)
check("compact s otevřenými delegacemi vypíše", start([USER] + ag1, "compact")[1].startswith("Otevřené delegace z minula:"), True)
check("startup nevypíše nic", start([USER] + ag1, "startup")[1], "")
check("clear nevypíše nic", start([USER] + ag1, "clear")[1], "")
check("resume bez otevřených delegací nevypíše nic", start([USER] + ag1 + [note(a1, t1)], "resume")[1], "")
check("resume po sběrném oznámení nevypíše nic", start([USER] + ba2 + [orphan(b2)], "resume")[1], "")
check("resume: budík nevadí (po restartu je mrtvý)", start([USER] + ag1 + cr1, "resume")[1].startswith("Otevřené"), True)
check("resume s MAREK_DOHLED=off nevypíše nic", subprocess.run([sys.executable, os.path.join(D, "dohled-start.py")], capture_output=True, text=True,
      input=json.dumps({"transcript_path": tr([USER] + ag1), "source": "resume"}), env={**os.environ, "MAREK_DOHLED": "off"}).stdout.strip(), "")
check("resume: rozbitý vstup -> nic, rc 0", (lambda r: (r.returncode, r.stdout))(subprocess.run([sys.executable, os.path.join(D, "dohled-start.py")],
      input="{špatně", capture_output=True, text=True)), (0, ""))
# ---------- 0.13.0: navázání po zhuštění kontextu (pravidla-start.sh, baze-precompact.sh) ----------
def sh(name, payload):
    return subprocess.run(["bash", os.path.join(D, name)], input=payload, capture_output=True, text=True)
r = sh("pravidla-start.sh", json.dumps({"source": "compact", "hook_event_name": "SessionStart"}))
check("pravidla-start: compact -> pravidla + připomínka navázání", (r.returncode, "## Dlouhá práce a zhuštění kontextu" in r.stdout,
      "[Po zhuštění kontextu]" in r.stdout), (0, True, True))
for src in ("startup", "resume", "clear"):
    r = sh("pravidla-start.sh", json.dumps({"source": src}))
    check("pravidla-start: %s -> pravidla bez připomínky" % src, (r.returncode, "## Komunikace" in r.stdout,
          "[Po zhuštění kontextu]" in r.stdout), (0, True, False))
r = sh("pravidla-start.sh", "")
check("pravidla-start: prázdný vstup -> pravidla, rc 0", (r.returncode, "## Komunikace" in r.stdout), (0, True))
r = sh("baze-precompact.sh", json.dumps({"trigger": "auto"}))
check("precompact: instrukce pro shrnutí, bez pokynu zapisovat do báze", (r.returncode, "Markovo zadání doslova" in r.stdout,
      "budíky" in r.stdout, "čeká na zápis do báze" in r.stdout, "Zapiš teď" in r.stdout, len(r.stdout) < 10000),
      (0, True, True, True, False, True))
# ---------- výkon: velký přepis ----------
filler = {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "toolu_x", "content": "x" * 3000}]}}
big = tr([USER] + ag1 + [filler] * 25000 + [FINAL])  # ~80 MB
t = time.time(); r = dohled.scan(big); dt = time.time() - t
check("výkon: ~%d MB přepis do 1 s (%.2f s)" % (os.path.getsize(big) // 1e6, dt), bool(r) and len(r["open"]) == 1 and dt < 1.0, True)
# ---------- skutečné přepisy (jen čtení, pokud existují): nesmí spadnout ----------
import glob
reals = sorted(glob.glob(os.path.expanduser("~/.claude/projects/*/*.jsonl")), key=os.path.getsize)[:5]
fails = [p for p in reals if dohled.scan(p, budget=10) is None]
check("skutečné přepisy (%d) se projdou" % len(reals), fails, [])
print("dohled: selhalo", bad, "z", total)
sys.exit(1 if bad else 0)

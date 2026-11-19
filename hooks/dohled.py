"""Sdílený modul dohledu nad delegovanou prací (marek-cc-hooks 0.12.0).

Používá ho Stop hook (stop-guard.py) a SessionStart hook (dohled-start.py). Kniha delegací se NEVEDE v souboru:
odvozuje se při každém volání z přepisu session (JSONL, `transcript_path` ve vstupu hooku).

Otevřená delegace:
  (a) volání Agent s run_in_background true, které se opravdu spustilo (toolUseResult.status == async_launched),
  (b) Bash s run_in_background true, které se opravdu spustilo (toolUseResult.backgroundTaskId),
  (c) SendMessage jiné session (recipient_kind session nebo name, ne „main“), jehož text obsahuje „HOTOVO:“
      a nezačíná [ACK] / STAV: / ODPOVĚĎ:.
Uzavření:
  (a), (b) <task-notification> se stavem completed/failed/killed/stopped (mezitímní „waiting on its own
      background work“ delegaci NEuzavírá), nebo TaskStop s tím ID;
  (c) příchozí zpráva od téže session (origin.from nebo origin.name == adresát) s „STAV: hotovo“ / „STAV: zrušeno“,
      nebo vlastní odchozí zpráva tomuto adresátovi začínající „STAV: zrušeno“.
Aktivní budík:
  CronCreate recurring (výchozí true) nesmazaný CronDelete a mladší než 7 dní (Claude Code ho po 7 dnech sám ruší),
  nebo one-shot CronCreate nesmazaný, s nextFireAt v budoucnosti.
  ScheduleWakeup se nezohledňuje: v žádném přepisu na tomto stroji není jeho tool_use, tvar neznáme.

Výkon: přepis se čte po řádcích jako bajty a JSON se parsuje jen u řádků s klíčovými slovy. Při překročení
rozpočtu nebo jakékoli chybě vrací scan() None (fail-open: hook nic neblokuje).
Vypínač: MAREK_DOHLED=off.
"""
import json, os, re, time

TERMINAL = {"completed", "failed", "killed", "stopped"}
INTERIM = re.compile(r"waiting on its own background work|has not reported yet", re.I)
NAME_RX = re.compile(rb'"name"\s*:\s*"(Agent|Bash|CronCreate|CronDelete|TaskStop|SendMessage)"')
NOTE_RX = re.compile(r"<task-notification>(.*?)</task-notification>", re.S)
STAV_END = re.compile(r"STAV:\s*(hotovo|zrušeno)", re.I)
CONTRACT_EXEMPT = ("[ACK]", "STAV:", "ODPOVĚĎ:")
RECURRING_TTL = 7 * 86400
PENDING_LINES = 400  # po tolika řádcích od tool_use už výsledek nečekáme


def disabled():
    return os.environ.get("MAREK_DOHLED", "on").strip().lower() == "off"


def truthy(v):
    return v is True or (isinstance(v, str) and v.strip().lower() == "true")


def _ts(r):
    try:
        t = r.get("timestamp")
        if isinstance(t, str):
            import calendar
            return calendar.timegm(time.strptime(t[:19], "%Y-%m-%dT%H:%M:%S"))
    except Exception:
        pass
    return None


def _tag(txt, name):
    m = re.search(r"<%s>(.*?)</%s>" % (name, name), txt, re.S)
    return m.group(1).strip() if m else ""


def _blocks(r):
    m = r.get("message")
    c = m.get("content") if isinstance(m, dict) else None
    return [b for b in c if isinstance(b, dict)] if isinstance(c, list) else []


def _load(l):
    """Řádek přepisu jako dict; nedopsaný nebo rozbitý řádek (poslední řádek při zápisu) se přeskočí."""
    try:
        r = json.loads(l)
    except ValueError:
        return None
    return r if isinstance(r, dict) else None


def _short(s, n=70):
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[:n - 1] + "…"


def scan(path, now=None, budget=1.0):
    """Vrátí {"open": [{kind, desc, id}], "alarm": bool} nebo None (chyba, vypnuto, překročený rozpočet)."""
    if disabled() or not path or not os.path.exists(path):
        return None
    try:
        return _scan(path, time.time() if now is None else now, budget)
    except Exception:
        return None


def _scan(path, now, budget):
    deadline = time.monotonic() + budget
    deleg = {}     # klíč (tool_use id nebo odeslání) -> dict
    by_task = {}   # task_id -> klíč
    pending = {}   # tool_use id -> (druh, data, číslo řádku)
    alarms = {}    # id cronu -> dict
    seq = 0
    with open(path, "rb") as f:
        for n, l in enumerate(f):
            if n % 2000 == 0 and time.monotonic() > deadline:
                return None
            if l.startswith((b'{"type":"api-request', b'{"type":"queue-operation')):
                continue

            # ---- výsledky nástrojů, na které čekáme ----
            if pending and b"tool_result" in l:
                hit = [pid for pid in pending if pid.encode() in l]
                if hit:
                    r = _load(l)
                    if r is None:
                        continue
                    tur = r.get("toolUseResult")
                    for b in _blocks(r):
                        pid = b.get("tool_use_id")
                        if b.get("type") != "tool_result" or pid not in pending:
                            continue
                        kind, data, _ = pending.pop(pid)
                        if b.get("is_error"):
                            continue
                        c = b.get("content")
                        text = c if isinstance(c, str) else " ".join(
                            x.get("text", "") for x in c if isinstance(x, dict)) if isinstance(c, list) else ""
                        tur_d = tur if isinstance(tur, dict) else {}
                        if kind == "agent":
                            tid = tur_d.get("agentId") if tur_d.get("status") == "async_launched" else None
                            if not tid and "Async agent launched" in text:
                                mm = re.search(r"agentId:\s*(\S+)", text)
                                tid = mm.group(1) if mm else None
                            if tid:
                                data["task_id"] = tid
                                deleg[pid] = data; by_task[tid] = pid
                        elif kind == "bash":
                            tid = tur_d.get("backgroundTaskId")
                            if not tid:
                                mm = re.search(r"running in background with ID:\s*(\S+?)\.?\s", text + " ")
                                tid = mm.group(1) if mm else None
                            if tid:
                                data["task_id"] = tid
                                deleg[pid] = data; by_task[tid] = pid
                        elif kind == "msg":
                            if tur_d.get("success", True) is not False:
                                deleg[pid] = data
                        elif kind == "cron":
                            cid = tur_d.get("id")
                            if not cid:
                                mm = re.search(r"(?:task|job)\s+([0-9a-f]{6,})", text)
                                cid = mm.group(1) if mm else None
                            if cid:
                                rec = tur_d.get("recurring")
                                alarms[cid] = {"recurring": data["recurring"] if data["recurring"] is not None
                                               else (True if rec is None else bool(rec)),
                                               "ts": _ts(r) or data["ts"] or now,
                                               "next": tur_d.get("nextFireAt"), "deleted": False}
            if pending and n % 50 == 0:  # výsledek, který nepřišel (přerušený tah), nečekáme donekonečna
                for pid in [p for p, v in pending.items() if n - v[2] > PENDING_LINES]:
                    pending.pop(pid)

            # ---- volání nástrojů (assistant) ----
            if b'"tool_use"' in l:
                m = NAME_RX.search(l)
                if m:
                    name = m.group(1).decode()
                    if name in ("Agent", "Bash") and b"run_in_background" not in l:
                        continue
                    r = _load(l)
                    if r is None or r.get("type") != "assistant":
                        continue
                    for b in _blocks(r):
                        if b.get("type") != "tool_use" or b.get("name") != name:
                            continue
                        inp = b.get("input") if isinstance(b.get("input"), dict) else {}
                        bid = b.get("id") or ("n%d" % n)
                        if name in ("Agent", "Bash") and truthy(inp.get("run_in_background")):
                            desc = inp.get("description") or inp.get("prompt") or inp.get("command")
                            pending[bid] = ("agent" if name == "Agent" else "bash",
                                            {"kind": "agent" if name == "Agent" else "bash",
                                             "desc": _short(desc), "id": bid, "task_id": None, "seq": seq}, n)
                            seq += 1
                        elif name == "SendMessage":
                            to = inp.get("to")
                            msg = inp.get("message")
                            if not isinstance(to, str) or not isinstance(msg, str) or to.lower() == "main":
                                continue
                            if inp.get("recipient_kind") not in ("session", "name", None):
                                continue
                            if re.match(r"\s*STAV:\s*zrušeno", msg, re.I):
                                for k, v in deleg.items():
                                    if v["kind"] == "msg" and v["peer"].lower() == to.lower():
                                        v["closed"] = True
                            elif "HOTOVO:" in msg and not msg.lstrip().startswith(CONTRACT_EXEMPT):
                                pending[bid] = ("msg", {"kind": "msg", "peer": to, "id": bid, "seq": seq,
                                                        "desc": _short(inp.get("summary") or msg.split("HOTOVO:", 1)[1])
                                                        + " → " + _short(to, 40)}, n)
                                seq += 1
                        elif name == "CronCreate":
                            rec = inp.get("recurring")
                            pending[bid] = ("cron", {"recurring": None if rec is None else truthy(rec),
                                                     "ts": _ts(r)}, n)
                        elif name == "CronDelete":
                            cid = inp.get("id")
                            if cid in alarms:
                                alarms[cid]["deleted"] = True
                        elif name == "TaskStop":
                            tid = inp.get("task_id") or inp.get("shell_id")
                            if tid in by_task:
                                deleg[by_task[tid]]["closed"] = True
                    continue

            # ---- task-notification (user záznam nebo attachment queued_command) ----
            if b"<task-notification>" in l:
                r = _load(l)
                if r is None:
                    continue
                text = ""
                if r.get("type") == "user":
                    m = r.get("message") or {}
                    c = m.get("content") if isinstance(m, dict) else None
                    text = c if isinstance(c, str) else " ".join(
                        x.get("text", "") for x in c if isinstance(x, dict)) if isinstance(c, list) else ""
                elif r.get("type") == "attachment":
                    a = r.get("attachment") or {}
                    if a.get("type") == "queued_command" and isinstance(a.get("prompt"), str):
                        text = a["prompt"]
                if text.lstrip().startswith("<task-notification>"):
                    for blk in NOTE_RX.findall(text):
                        st = _tag(blk, "status").lower()
                        if st not in TERMINAL or INTERIM.search(_tag(blk, "summary") + " " + _tag(blk, "result")):
                            continue
                        # sběrné oznámení po restartu („didn't finish before the previous session ended“)
                        # nese víc <task-id>; běžné oznámení jedno a k němu <tool-use-id>
                        keys = [by_task.get(t.strip()) for t in re.findall(r"<task-id>(.*?)</task-id>", blk)]
                        keys.append(_tag(blk, "tool-use-id"))
                        for key in keys:
                            if key in deleg:
                                deleg[key]["closed"] = True
                continue

            # ---- příchozí zpráva od jiné session ----
            if b'"peer"' in l and b"origin" in l:
                r = _load(l)
                if r is None:
                    continue
                o = r.get("origin")
                if not isinstance(o, dict):
                    a = r.get("attachment")
                    o = a.get("origin") if isinstance(a, dict) else None
                if isinstance(o, dict) and o.get("kind") == "peer" and isinstance(o.get("body"), str) \
                        and STAV_END.search(o["body"]):
                    who = {str(o.get("from") or "").lower(), str(o.get("name") or "").lower()} - {""}
                    for v in deleg.values():
                        if v["kind"] == "msg" and v["peer"].lower() in who:
                            v["closed"] = True

    opened = sorted((v for v in deleg.values() if not v.get("closed")), key=lambda v: v["seq"])
    alarm = False
    for a in alarms.values():
        if a["deleted"]:
            continue
        if a["recurring"]:
            alarm = alarm or (a["ts"] + RECURRING_TTL > now)
        else:
            nxt = a["next"]
            alarm = alarm or (not isinstance(nxt, (int, float)) or nxt / 1000.0 > now)
    return {"open": [{"kind": v["kind"], "desc": v["desc"], "id": v.get("task_id") or v["id"]} for v in opened],
            "alarm": alarm}


def describe(opened):
    """Lidský výpis otevřených delegací pro hlášení hooku."""
    out = []
    for o in opened:
        if o["kind"] == "msg":
            out.append("zadání jiné session (%s)" % o["desc"])
        else:
            out.append("%s %s (%s)" % ("subagent" if o["kind"] == "agent" else "příkaz na pozadí", o["id"], o["desc"]))
    return "; ".join(out)

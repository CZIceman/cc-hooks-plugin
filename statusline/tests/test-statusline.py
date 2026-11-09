#!/usr/bin/env python3
"""Test statusline.py bez modelu a bez sítě. Čas je pevný přes MAREK_SL_NOW, HOME je v tempdiru; skript nic nezapisuje (kontrolujeme i to)."""
import copy, json, os, re, subprocess, sys, tempfile
T = os.path.dirname(os.path.abspath(__file__))
SKRIPT = os.path.join(T, "..", "statusline.py")
VZOREK = json.load(open(os.path.join(T, "vzorek-2.1.319.json")))
TMP = tempfile.mkdtemp()
HOME = os.path.join(TMP, "home"); os.makedirs(HOME)
STAV = os.path.join(TMP, "stav")   # XDG_STATE_HOME; po testech musí zůstat prázdný
NEGIT = os.path.join(TMP, "mimo-git"); os.makedirs(NEGIT)   # cwd bez gitu (tempdir není v repu)
EXP = VZOREK["prompt_cache"]["expires_at"]
NOW0 = EXP - 3600                                            # cache má ještě hodinu

OSC = re.compile(r"\x1b\]8;;[^\x1b]*\x1b\\")
CSI = re.compile(r"\x1b\[[0-9;]*m")

def strip(s): return CSI.sub("", OSC.sub("", s)).rstrip("\n")
def col(s, text):
    """Kód SGR těsně před textem (None = bez barvy)."""
    m = re.search(r"\x1b\[(\d+)m" + re.escape(text), s)
    return m.group(1) if m else None
def odkazy(s): return re.findall(r"\x1b\]8;;([^\x1b]*)\x1b\\([^\x1b]*)\x1b\]8;;\x1b\\", s)

def vzorek(**zmeny):
    """Kopie vzorku; cwd bez gitu, scratchpad neexistuje. zmeny: 'a.b.c' = hodnota (None = smazat klíč)."""
    d = copy.deepcopy(VZOREK)
    d["cwd"] = NEGIT; d["scratchpad_dir"] = os.path.join(TMP, "neexistuje")
    for cesta, v in zmeny.items():
        k = cesta.split("."); o = d
        for p in k[:-1]: o = o.setdefault(p, {})
        if v is None: o.pop(k[-1], None)
        else: o[k[-1]] = v
    return d

def run(data=None, now=NOW0, raw=None, state=STAV, home=HOME):
    e = {**os.environ, "HOME": home, "XDG_STATE_HOME": state, "MAREK_SL_NOW": str(now)}
    r = subprocess.run([sys.executable, SKRIPT], input=raw if raw is not None else json.dumps(data),
                       capture_output=True, text=True, env=e)
    return r.returncode, r.stdout, r.stderr

bad = 0
def chk(n, got, exp, extra=True, why=""):
    global bad
    ok = got == exp and extra
    bad += not ok
    print("OK  " if ok else "CHYBA", f"{n:52} -> {got!r} (čekáno {exp!r}){'' if extra else ' ' + why}")


# --- vzorek, model, kontext
rc, o, err = run(vzorek())
t = strip(o)
chk("vzorek: rc 0, stderr prázdný, jeden řádek", (rc, err, o.count("\n")), (0, "", 1))
chk("  model Haiku 5.5 · medium (úsilí) na začátku", t.startswith("Haiku 5.5 · medium │ "), True)
chk("úsilí high", strip(run(vzorek(**{"effort.level": "high"}))[1]).startswith("Haiku 5.5 · high │ "), True)
chk("bez úsilí jen model", strip(run(vzorek(effort=None))[1]).startswith("Haiku 5.5 │ "), True)
chk("  kontext: pruh dle used 6 %, text zbývá 94 % (zelená)", ("█░░░░░░░░░ zbývá 94%" in t, col(o, "█░░░░░░░░░ zbývá 94%")), (True, "32"))
chk("  cache se neukáže (zbývá 60 min)", "⧗" in t, False)
chk("  5h: zbývá 93 % (zelená) · 1:30, bez předpovědi", ("5h zbývá 93% · 1:30" in t, col(o, "93%")), (True, "32"))
chk("  týden: zbývá 69 % (zelená) · 1d 15h", ("týden zbývá 69% · 1d 15h" in t, col(o, "69%")), (True, "32"))
chk("  žádné ⚠ ani ↑ ani náklady", any(x in t for x in ("⚠", "↑", "$", "Σ")), False)
chk("  oddělovač šedě", "\x1b[90m │ \x1b[0m" in o, True)
chk("  pořadí: model, kontext, 5h, týden", [x.split(" ")[0] for x in t.split(" │ ")[:4]], ["Haiku", "█░░░░░░░░░", "5h", "týden"])

# --- cache
for zbyva, text, kod, nazev in ((600, "⧗ 10 min", "33", "10 min žlutě"), (180, "⧗ 3 min", "31", "3 min červeně"),
                                (30, "⧗ <1 min", "31", "pod minutou"), (61, "⧗ 2 min", "31", "61 s zaokrouhleno nahoru"),
                                (900, "⧗ 15 min", "33", "přesně 15 min = hranice zahrnuta")):
    _, o, _ = run(vzorek(), now=EXP - zbyva)
    chk(f"cache {nazev}", (text in strip(o), col(o, text)), (True, kod))
_, o, _ = run(vzorek(), now=EXP - 901);                      chk("cache 15 min 1 s -> nic", "⧗" in strip(o), False)
_, o, _ = run(vzorek(**{"prompt_cache.warm": False}), now=EXP - 600); chk("cold cache -> nic", "⧗" in strip(o), False)
_, o, _ = run(vzorek(**{"prompt_cache.warm": None}), now=EXP - 600);  chk("cache bez pole warm -> nic", "⧗" in strip(o), False)
_, o, _ = run(vzorek(), now=EXP + 10);                       chk("cache už vypršela -> nic", "⧗" in strip(o), False)
_, o, _ = run(vzorek(**{"prompt_cache.ttl": "5m"}), now=EXP - 100)
chk("ttl 5m, zbývá 100 s -> červeně", (("⧗ 2 min" in strip(o)), col(o, "⧗ 2 min")), (True, "31"))
_, o, _ = run(vzorek(**{"prompt_cache.ttl": "5m"}), now=EXP - 600); chk("ttl 5m, zbývá 10 min -> nic", "⧗" in strip(o), False)

# --- kontext barvy
_, o, _ = run(vzorek(**{"context_window.used_percentage": 55, "context_window.remaining_percentage": 45}))
chk("kontext used 55 -> žlutá, zbývá 45 %", (col(o, "██████░░░░ zbývá 45%")), "33")
_, o, _ = run(vzorek(**{"context_window.used_percentage": 85, "context_window.remaining_percentage": 15}))
chk("kontext used 85 -> červená, zbývá 15 %", (col(o, "█████████░ zbývá 15%")), "31")
_, o, _ = run(vzorek(**{"context_window.used_percentage": 49, "context_window.remaining_percentage": 51}))
_, o2, _ = run(vzorek(**{"context_window.used_percentage": 50, "context_window.remaining_percentage": 50}))
chk("kontext used 49 -> zelená; 50 -> žlutá", (col(o, "█████░░░░░ zbývá 51%"), col(o2, "█████░░░░░ zbývá 50%")), ("32", "33"))
_, o, _ = run(vzorek(**{"context_window.used_percentage": 79, "context_window.remaining_percentage": 21}))
_, o2, _ = run(vzorek(**{"context_window.used_percentage": 80, "context_window.remaining_percentage": 20}))
chk("kontext used 79 žlutá; 80 červená", (col(o, "████████░░ zbývá 21%"), col(o2, "████████░░ zbývá 20%")), ("33", "31"))
_, o, _ = run(vzorek(**{"context_window.used_percentage": 100, "context_window.remaining_percentage": 0}))
chk("kontext 100 -> plný pruh, zbývá 0 %", "██████████ zbývá 0%" in strip(o), True)
_, o, _ = run(vzorek(**{"context_window.used_percentage": 30, "context_window.remaining_percentage": None}))
chk("bez remaining_percentage -> 100 - used", "███░░░░░░░ zbývá 70%" in strip(o), True, why=strip(o))
_, o, _ = run(vzorek(**{"context_window.used_percentage": None, "context_window.remaining_percentage": 40}))
chk("bez used_percentage jen remaining -> pruh z 100 - remaining", "██████░░░░ zbývá 40%" in strip(o), True, why=strip(o))
_, o, _ = run(vzorek(**{"context_window": None}))
chk("bez context_window -> bez segmentu (pruh)", "█" in strip(o) or "░" in strip(o), False)

# --- okna předplatného: 5h a týden
now = 1_000_000_000
H = 3600; D = 86400
def rl(f=None, w=None):
    """Vzorek jen s okny f / w = (used, za kolik s reset), bez cache; vrací (text bez ANSI, surově)."""
    r = {}
    if f: r["five_hour"] = {"used_percentage": f[0], "resets_at": now + f[1]}
    if w: r["seven_day"] = {"used_percentage": w[0], "resets_at": now + w[1]}
    o = run(vzorek(**{"rate_limits": r or None, "prompt_cache": None}), now=now)[1]
    return strip(o), o

t, o = rl(f=(40, 3 * H), w=(10, 3 * D))
chk("obě okna zobrazená", ("5h zbývá 60% · 3:00" in t, "týden zbývá 90% · 3d 0h" in t), (True, True), why=t)
chk("  5h před týdnem", t.index("5h zbývá") < t.index("týden zbývá"), True)
t, o = rl(f=(40, 3 * H))
chk("jen five_hour -> jen 5h segment", ("5h zbývá" in t, "týden" in t), (True, False))
t, o = rl(w=(40, 3 * D))
chk("jen seven_day -> jen týden segment", ("5h zbývá" in t, "týden zbývá 60% · 3d 0h" in t), (False, True), why=t)
t, o = rl(f=(20, 6300), w=(10, 3 * D))
chk("čas pod 24 h jako H:MM (1:45)", "5h zbývá 80% · 1:45" in t, True, why=t)
t, o = rl(f=(20, 3 * H), w=(60, 2 * D + 5 * H))
chk("čas nad 24 h jako Nd Nh (2d 5h)", "týden zbývá 40% · 2d 5h" in t, True, why=t)
t, o = rl(f=(20, 3 * H), w=(60, 23 * H + 59 * 60 + 59))
chk("čas těsně pod 24 h -> 23:59", "týden zbývá 40% · 23:59" in t, True, why=t)
t, o = rl(f=(20, 3 * H), w=(60, D))
chk("přesně 24 h -> 1d 0h", "· 1d 0h" in t, True, why=t)
t = strip(run(vzorek(**{"rate_limits": {"five_hour": {"used_percentage": 20, "resets_at": now - 50}}, "prompt_cache": None}), now=now)[1])
chk("5h: reset v minulosti -> 0:00, bez pádu", ("5h zbývá 80% · 0:00" in t, "⚠" in t), (True, False), why=t)
t = strip(run(vzorek(**{"rate_limits": {"five_hour": {"used_percentage": 20}}, "prompt_cache": None}), now=now)[1])
chk("bez resets_at -> jen zbývá NN %", ("5h zbývá 80%" in t, "80% ·" in t, "⚠" in t), (True, False, False), why=t)
_, o, _ = run(vzorek(**{"rate_limits": None}))
chk("chybějící rate_limits -> bez obou segmentů", ("5h zbývá" in strip(o), "týden" in strip(o), "Haiku 5.5" in strip(o)), (False, False, True))
_, o, _ = run(vzorek(**{"rate_limits": {}}))
chk("prázdné rate_limits -> bez obou segmentů", ("5h zbývá" in strip(o), "týden" in strip(o)), (False, False))
_, o, _ = run(vzorek(**{"rate_limits.five_hour": None}))
chk("chybí jen five_hour -> zůstane týden", ("5h zbývá" in strip(o), "týden zbývá 69%" in strip(o)), (False, True))

# barvy zbývajícího: > 50 zelená, > 20 žlutá, jinak červená (hranice 50 a 20)
for used, kod, n in ((49, "32", "zbývá 51 -> zelená"), (50, "33", "zbývá 50 -> žlutá (ne > 50)"), (79, "33", "zbývá 21 -> žlutá"),
                     (80, "31", "zbývá 20 -> červená (ne > 20)"), (100, "31", "zbývá 0 -> červená"), (0, "32", "zbývá 100 -> zelená")):
    t, o = rl(f=(used, 3 * H), w=(used, 3 * D))
    chk(f"barva {n} (5h i týden)", (col(o, f"{100 - used}%"), o.count(f"\x1b[{kod}m{100 - used}%")), (kod, 2))
t, o = rl(f=(50, 3 * H))
chk("  barva se týká jen čísla (text 'zbývá' bez barvy)", "5h zbývá \x1b[33m50%\x1b[0m · 3:00" in o, True)

# předpověď vyčerpání
t, o = rl(f=(60, 4 * H))
chk("předpověď ano: 5h used 60 % po 1 h -> dojde za 0:40, reset za 4:00", "5h zbývá 40% · 4:00 ⚠ dojde za 0:40" in t, True, why=t)
chk("  ⚠ text červeně", col(o, "⚠ dojde za 0:40"), "31")
chk("  barva zbývajícího podle zbývajícího (žlutá)", col(o, "40%"), "33")
t, o = rl(f=(10, 3 * H))
chk("předpověď ne: used 10 % po 2 h (dojde za 18 h > reset)", ("⚠" in t, "5h zbývá 90% · 3:00" in t), (False, True), why=t)
t, o = rl(f=(5, 5 * H - 9 * 60))
chk("5h těsně po začátku (uplynulo 9 min) -> bez předpovědi", "⚠" in t, False, why=t)
t, o = rl(f=(30, 5 * H - 9 * 60))
chk("  i při vysokém tempu před 10 min -> bez předpovědi", "⚠" in t, False, why=t)
t, o = rl(f=(5, 5 * H - 10 * 60))
chk("5h uplynulo přesně 10 min, used 5 % -> dojde za 3:10", "5h zbývá 95% · 4:50 ⚠ dojde za 3:10" in t, True, why=t)
t, o = rl(f=(0, 3 * H))
chk("used 0 -> bez předpovědi, zbývá 100 % zelená", ("⚠" in t, "5h zbývá 100% · 3:00" in t, col(o, "100%")), (False, True, "32"), why=t)
t, o = rl(w=(50, 7 * D - 5 * H - 59 * 60))
chk("týden uplynulo 5 h 59 min -> bez předpovědi", "⚠" in t, False, why=t)
t, o = rl(w=(10, 7 * D - 6 * H))
chk("týden uplynulo přesně 6 h, used 10 % -> dojde za 2d 6h", "týden zbývá 90% · 6d 18h ⚠ dojde za 2d 6h" in t, True, why=t)
t, o = rl(w=(30, 4 * D))
chk("týden used 30 % po 3 d (dojde za 7 d > reset 4 d) -> ne", "⚠" in t, False, why=t)
t, o = rl(w=(70, 4 * D))
chk("týden used 70 % po 3 d -> dojde za 1d 6h (zaokrouhleno dolů)", "týden zbývá 30% · 4d 0h ⚠ dojde za 1d 6h" in t, True, why=t)
t, o = rl(f=(40, 3 * H), w=(70, 4 * D))
chk("5h bez předpovědi, týden s předpovědí: nezávisle", (t.count("⚠"), t.index("⚠") > t.index("týden")), (1, True), why=t)
t, o = rl(f=(100, 3 * H))
chk("used 100 % -> zbývá 0 %, dojde za 0:00", "5h zbývá 0% · 3:00 ⚠ dojde za 0:00" in t, True, why=t)
t, o = rl(f=(50, 6 * H))
chk("resets_at za víc než délku okna -> bez předpovědi", "⚠" in t, False, why=t)

# --- odolnost vstupu
for n, raw in (("prázdný JSON {}", "{}"), ("nevalidní vstup", "{nejson"), ("prázdný stdin", ""), ("pole místo objektu", "[1,2]"),
               ("null", "null"), ("samé null hodnoty", json.dumps({"model": None, "context_window": None, "cost": None,
                "rate_limits": None, "prompt_cache": None, "workspace": None, "cwd": None, "scratchpad_dir": None})),
               ("špatné typy polí", json.dumps({"model": "x", "context_window": {"used_percentage": "moc"},
                "prompt_cache": {"warm": True, "expires_at": "brzy"}, "rate_limits": {"five_hour": 5},
                "cost": {"total_cost_usd": "1"}, "workspace": [], "cwd": 5}))):
    rc, o, err = run(raw=raw)
    chk(f"{n}: rc 0, stderr prázdný", (rc, err), (0, ""))
rc, o, err = run(raw="{}");                  chk("{} -> prázdný řádek", o, "\n")
rc, o, err = run(vzorek(**{"model": None}));  chk("bez modelu zbytek zůstane", ("zbývá 94%" in strip(o), "Haiku" in strip(o)), (True, False))

# --- projekt (odkaz OSC 8)
_, o, _ = run(vzorek(**{"workspace.project_dir": HOME + "/moje projekty/x"}))
chk("projekt pod $HOME -> ~ a klikací file:// (kódovaný)", (odkazy(o)), [("file://" + HOME + "/moje%20projekty/x", "~/moje projekty/x")])
_, o, _ = run(vzorek(**{"workspace.project_dir": "/opt/xyz"}))
chk("projekt mimo $HOME -> celá cesta", odkazy(o), [("file:///opt/xyz", "/opt/xyz")])
_, o, _ = run(vzorek(**{"workspace.project_dir": HOME + "-jiny/x"}))
chk("prefix $HOME bez hranice adresáře se nezkracuje", odkazy(o)[0][1], HOME + "-jiny/x")
_, o, _ = run(vzorek(**{"workspace.project_dir": HOME}))
chk("projekt = $HOME -> ~", odkazy(o)[0][1], "~")
_, o, _ = run(vzorek(**{"workspace.project_dir": None}))
chk("bez project_dir -> bez odkazu", odkazy(o), [])
_, o, _ = run(vzorek(**{"workspace.project_dir": "/opt/xyz"}))
chk("  surový formát OSC 8", "\x1b]8;;file:///opt/xyz\x1b\\/opt/xyz\x1b]8;;\x1b\\" in o, True)

# --- git
GENV = {**os.environ, "HOME": HOME, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
        "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"}
def git(cwd, *a): subprocess.run(["git", "-C", cwd, *a], check=True, capture_output=True, env=GENV)
def gt(cwd, **kw):
    _, o, err = run(vzorek(cwd=cwd, **kw))
    return strip(o), o, err
R = os.path.join(TMP, "repo"); os.makedirs(R)
git(R, "init", "-q", "-b", "hlavni")
open(os.path.join(R, "a.txt"), "w").write("a\n"); open(os.path.join(R, "b.txt"), "w").write("b\n")
git(R, "add", "."); git(R, "commit", "-q", "-m", "x")
t, o, _ = gt(R);  chk("čistý repo: jen větev", t.endswith(" │ hlavni"), True, why=t)
chk("  bez 🌿 u hlavního worktree", "🌿" in t, False)
open(os.path.join(R, "a.txt"), "w").write("zmena\n"); open(os.path.join(R, "nove.txt"), "w").write("n\n")
t, o, _ = gt(R);  chk("1 změněný + 1 nesledovaný: hlavni ±1 +1", t.endswith("hlavni ±1 +1"), True, why=t)
chk("  počty žlutě", col(o, "±1 +1"), "33")
git(R, "add", "a.txt")
t, o, _ = gt(R);  chk("změna ve stage se počítá jako ±1", t.endswith("hlavni ±1 +1"), True, why=t)
open(os.path.join(R, "b.txt"), "w").write("bb\n"); os.makedirs(os.path.join(R, "d")); open(os.path.join(R, "d", "x"), "w").write("1")
t, o, _ = gt(R);  chk("dva změněné, dva nesledovaná (adresář = 1)", t.endswith("hlavni ±2 +2"), True, why=t)
git(R, "add", "."); git(R, "commit", "-q", "-m", "y")
t, o, _ = gt(R);  chk("po commitu čisto", t.endswith(" │ hlavni"), True, why=t)
# upstream a ahead
U = os.path.join(TMP, "upstream.git"); subprocess.run(["git", "init", "-q", "--bare", "-b", "hlavni", U], check=True, env=GENV)
git(R, "remote", "add", "origin", U); git(R, "push", "-q", "-u", "origin", "hlavni")
t, o, _ = gt(R);  chk("s upstreamem a bez předstihu: bez ↑N", t.endswith(" │ hlavni"), True, why=t)
open(os.path.join(R, "c.txt"), "w").write("c\n"); git(R, "add", "."); git(R, "commit", "-q", "-m", "z")
t, o, _ = gt(R);  chk("1 neodeslaný commit: ↑1", t.endswith("hlavni ↑1"), True, why=t)
open(os.path.join(R, "c.txt"), "w").write("cc\n")
t, o, _ = gt(R);  chk("↑1 i ±1 současně; barva jen u počtů", (t.endswith("hlavni ±1 ↑1"), col(o, "±1")), (True, "33"))
git(R, "commit", "-q", "-am", "w")
# linked worktree
W = os.path.join(TMP, "wt"); git(R, "worktree", "add", "-q", "-b", "vedlejsi", W)
t, o, _ = gt(W);  chk("linked worktree -> 🌿 větev", t.endswith("🌿 vedlejsi"), True, why=t)
os.makedirs(os.path.join(W, "pod")); t, o, _ = gt(os.path.join(W, "pod"))
chk("  z podadresáře worktree také 🌿", t.endswith("🌿 vedlejsi"), True, why=t)
os.makedirs(os.path.join(R, "pod")); t, o, _ = gt(os.path.join(R, "pod"))
chk("  podadresář hlavního repa bez 🌿 (2 neodeslané commity)", t.endswith(" │ hlavni ↑2") and "🌿" not in t, True, why=t)
# detached, bez commitů
git(R, "checkout", "-q", "--detach");  t, o, _ = gt(R); chk("detached HEAD", t.endswith(" │ HEAD"), True, why=t)
E = os.path.join(TMP, "prazdny"); os.makedirs(E); git(E, "init", "-q", "-b", "novy")
t, o, _ = gt(E);  chk("repo bez commitů -> jméno větve", t.endswith(" │ novy"), True, why=t)
# mimo git
t, o, err = gt(NEGIT);  chk("mimo git -> žádný git segment", (t.count(" │ "), err), (t.count(" │ "), ""))
chk("  (poslední segment není větev)", re.search(r" │ (hlavni|vedlejsi|HEAD)$", t) is None, True, why=t)
t, o, err = gt(os.path.join(TMP, "nikde")); chk("neexistující cwd -> bez git segmentu, stderr prázdný", (err, "master" in t or "hlavni" in t), ("", False))

# --- odkládací složka
S = os.path.join(TMP, "scratch dir"); os.makedirs(S)
_, o, _ = run(vzorek(scratchpad_dir=S));        chk("prázdný scratchpad -> nic", ("📁" in o), False)
open(os.path.join(S, "f.txt"), "w").write("x")
_, o, _ = run(vzorek(scratchpad_dir=S))
chk("scratchpad s souborem -> 📁 scratch odkaz", odkazy(o)[-1], ("file://" + S.replace(" ", "%20"), "📁 scratch"))
chk("  je posledním segmentem", strip(o).rstrip("\n").endswith("📁 scratch"), True)
_, o, _ = run(vzorek(scratchpad_dir=os.path.join(TMP, "neni")));  chk("neexistující scratchpad -> nic", ("📁" in o), False)

# --- nic se nezapisuje: stavový adresář nevznikl, v HOME nic nevzniklo
chk("žádný zápis do XDG_STATE_HOME ani HOME", (os.path.exists(STAV), os.listdir(HOME)), (False, []))

print("\nCHYB:", bad if bad else 0)
sys.exit(1 if bad else 0)

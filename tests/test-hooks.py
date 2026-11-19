#!/usr/bin/env python3
"""Test hooků bez spuštění modelu: do skriptů se pošle vzorový JSON a porovná se výsledek.
Výsledek: allow (bez rizika, od 0.11.0), ask, deny, nebo „-“ (hook mlčí: interaktivní nástroje, chyba, vypínač)."""
import json, os, subprocess, sys, tempfile
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hooks")
SCR = "/tmp/claude-1000/x/scratchpad"
os.environ["XDG_RUNTIME_DIR"] = tempfile.mkdtemp()
os.environ.pop("CLAUDE_PROJECT_DIR", None)  # projekt určuje jen cwd v testu
def run(script, inp):
    r = subprocess.run([sys.executable, os.path.join(D, script)], input=json.dumps(inp), capture_output=True, text=True)
    o = r.stdout.strip()
    dec = json.loads(o)["hookSpecificOutput"].get("permissionDecision") if o and "permissionDecision" in o else ("block" if '"block"' in o else ("ctx" if o else "-"))
    return r.returncode, dec
def pre(tool, ti, sid="s1", **kw): return run("pretool-guard.py", {"tool_name": tool, "tool_input": ti, "session_id": sid, "scratchpad_dir": SCR, **kw})
# báze si odemknu nejdřív (jinak by brána zamítla vše)
pre("mcp__claude_ai_Marek_Second_Brain__pravidla", {}, sid="s1")
H = os.path.expanduser("~")
PRJ = "/home/marek/claude/styblo"
T = [  # (popis, výsledek, očekávané)
 # čtení a běžná práce
 ("ls", pre("Bash", {"command": "ls -la ~"}), "allow"),
 ("grep journal", pre("Bash", {"command": "journalctl -b | grep -i error"}), "allow"),
 ("git status", pre("Bash", {"command": "git status --short"}), "allow"),
 ("git push", pre("Bash", {"command": "git push origin master"}), "allow"),
 ("git commit", pre("Bash", {"command": "git commit -m x"}), "allow"),
 ("claude -p", pre("Bash", {"command": "claude -p 'ahoj'"}), "allow"),
 ("zadej_ukol", pre("mcp__claude_ai_D_lna__zadej_ukol", {}), "allow"),
 ("Read /etc/passwd", pre("Read", {"file_path": "/etc/passwd"}), "allow"),
 ("Read ~/.ssh/id_rsa", pre("Read", {"file_path": H + "/.ssh/id_rsa"}), "ask"),
 ("Read ~/.ssh/id_rsa.pub", pre("Read", {"file_path": H + "/.ssh/id_rsa.pub"}), "allow"),
 ("Read ~/.bash_history", pre("Read", {"file_path": H + "/.bash_history"}), "ask"),
 # systémové změny se od 0.8.0 neptají (rozhodnutí 29. 10. 2026)
 ("sudo dnf install", pre("Bash", {"command": "sudo dnf install -y htop"}), "allow"),
 ("sudo dnf5 upgrade", pre("Bash", {"command": "sudo dnf5 upgrade -y 2>&1 | tail -25"}), "allow"),
 ("systemctl disable", pre("Bash", {"command": "systemctl disable --now cups"}), "allow"),
 ("sudo -n true", pre("Bash", {"command": "sudo -n true 2>&1 && echo SUDO_OK; id"}), "allow"),
 ("sudo smartctl (čtení)", pre("Bash", {"command": "sudo smartctl -H -A /dev/nvme0 2>/dev/null | grep -Ei overall"}), "allow"),
 ("sudo grubby", pre("Bash", {"command": "sudo grubby --default-kernel"}), "allow"),
 ("sudo tee /etc", pre("Bash", {"command": "echo x | sudo tee /etc/foo.conf"}), "allow"),
 ("echo > /etc", pre("Bash", {"command": "echo x > /etc/foo.conf"}), "allow"),
 ("setpci", pre("Bash", {"command": "setpci -s 33:00.5 CAP_MSI+2.w"}), "allow"),
 ("chmod 600 klíč", pre("Bash", {"command": "chmod 600 ~/.config/app/agent.key"}), "allow"),
 ("mount | grep", pre("Bash", {"command": "mount | grep /mnt/nas"}), "allow"),
 ("Edit /etc", pre("Edit", {"file_path": "/etc/dnf/dnf.conf"}), "allow"),
 ("Edit ~/.bashrc.d", pre("Write", {"file_path": H + "/.bashrc.d/x.sh"}), "allow"),
 ("Write /root/projekt (pve)", pre("Write", {"file_path": "/root/hevcpipe/hevcpipe/runner.py"}), "allow"),
 # slova v textu, který shell nespouští
 ("echo se slovem sudo", pre("Bash", {"command": "echo '== sudo pam'; ls /etc/pam.d"}), "allow"),
 ("grep na chown", pre("Bash", {"command": "grep -n chown README.md"}), "allow"),
 ("heredoc s rm a dd", pre("Bash", {"command": "python3 - <<'EOF'\nimport os\nos.rmdir('/x')\nfor depth,dd in []: pass\nprint('rm -rf /')\nEOF\necho ok"}), "allow"),
 ("heredoc, pak skutečné rm", pre("Bash", {"command": "cat > x.sh <<'E'\nrm -rf /\nE\nrm -rf ~/Hudba"}), "ask"),
 ("python3 -c s rm", pre("Bash", {"command": "python3 -c 'import os; print(\"rm -rf /\")'"}), "allow"),
 ("dd jako test rychlosti", pre("Bash", {"command": f"dd if=/dev/zero of={SCR}/t.bin bs=8M count=64"}), "allow"),
 # (a) mazání
 ("rm mimo pracovní místa", pre("Bash", {"command": "rm -rf ~/Hudba"}), "ask"),
 ("rm ve scratchpadu", pre("Bash", {"command": f"rm -f {SCR}/a.txt"}), "allow"),
 ("rm přes proměnnou ve scratchpadu", pre("Bash", {"command": f"S={SCR}; D=$S/pkg; rm -rf $D; mkdir -p $D"}), "allow"),
 ("rm neznámá proměnná", pre("Bash", {"command": "rm -rf $NEZNAMA/x"}), "ask"),
 ("rm v /tmp", pre("Bash", {"command": "rm -rf /tmp/x"}), "allow"),
 ("rm v projektu", pre("Bash", {"command": f"rm -f {PRJ}/a.txt"}, cwd=PRJ), "allow"),
 ("rm relativně v projektu", pre("Bash", {"command": "rm -f a.txt"}, cwd=PRJ), "allow"),
 ("cd do projektu a rm", pre("Bash", {"command": f"cd {PRJ}/sub && rm -rf dodavka"}, cwd=PRJ), "allow"),
 ("rm, cwd = HOME", pre("Bash", {"command": "rm a.txt"}, cwd=H), "ask"),
 ("rm na NAS", pre("Bash", {"command": "rm -rf /mnt/nas/data/_Vymena/test"}), "ask"),
 ("sudo rm /etc (systém, ne data)", pre("Bash", {"command": "sudo rm -f /etc/foo.conf"}), "allow"),
 ("bash -c rm", pre("Bash", {"command": "bash -c 'rm -rf ~/Hudba'"}), "ask"),
 ("find -delete mimo", pre("Bash", {"command": "find ~/Fotky -name '*.tmp' -delete"}), "ask"),
 ("find -delete scratchpad", pre("Bash", {"command": f"find {SCR} -name '*.tmp' -delete"}), "allow"),
 ("xargs rm, cwd HOME", pre("Bash", {"command": "ls | xargs rm"}, cwd=H), "ask"),
 ("rsync --delete mimo", pre("Bash", {"command": "rsync -a --delete src/ /mnt/nas/data/x/"}), "ask"),
 ("git reset --hard", pre("Bash", {"command": "git reset --hard HEAD~3"}, cwd=PRJ), "ask"),
 ("git push --force", pre("Bash", {"command": "git push --force origin master"}, cwd=PRJ), "ask"),
 ("git reset --hard ve scratchpadu", pre("Bash", {"command": f"cd {SCR}/repo && git reset --hard"}), "allow"),
 ("mkfs", pre("Bash", {"command": "sudo mkfs.ext4 /dev/sdb1"}), "ask"),
 ("dd na disk", pre("Bash", {"command": "sudo dd if=x.img of=/dev/sda bs=4M"}), "ask"),
 # pve: příkazy v kontejneru
 ("pct exec rm /var/tmp", pre("Bash", {"command": "pct exec 109 -- bash -c 'rm -f /var/tmp/avcheck/enc/*'"}), "allow"),
 ("pct exec systemctl", pre("Bash", {"command": "pct exec 109 -- bash -c 'systemctl stop hevcpipe-pilot; systemctl reset-failed hevcpipe-pilot'"}), "allow"),
 ("pct exec > /var/tmp log", pre("Bash", {"command": "pct exec 109 -- python3 /var/tmp/u.py > /var/tmp/u.log"}), "allow"),
 ("pct exec rm média", pre("Bash", {"command": "pct exec 109 -- bash -c 'rm -rf /media/nas/filmy/x'"}), "ask"),
 ("ssh host rm mimo datové úložiště", pre("Bash", {"command": "ssh root@nas 'rm -rf /srv/data/x'"}), "allow"),
 ("ssh host čtení", pre("Bash", {"command": "ssh -i ~/.ssh/klic_ed25519 user@h 'hostname; df -h'"}), "allow"),
 # přepis existujících souborů v datech
 ("mv ve scratchpadu", pre("Bash", {"command": f"mv {SCR}/a {SCR}/b"}), "allow"),
 ("sed -i v projektu", pre("Bash", {"command": "sed -i s/a/b/ main.py"}, cwd=PRJ), "allow"),
 ("sed -i v datech mimo projekt", pre("Bash", {"command": f"sed -i s/a/b/ {H}/.bashrc"}, cwd=PRJ), "ask"),
 ("echo >> paměť Claude", pre("Bash", {"command": f"echo x >> {H}/.claude/projects/p/memory/MEMORY.md"}), "allow"),
 # (c) nastavení Claude Code
 ("Edit ~/.claude/settings.json", pre("Edit", {"file_path": H + "/.claude/settings.json"}), "ask"),
 ("Write ~/.claude/hooks", pre("Write", {"file_path": H + "/.claude/hooks/x.py"}), "ask"),
 ("echo >> settings.json", pre("Bash", {"command": f"echo x >> {H}/.claude/settings.json"}), "ask"),
 ("sed -i settings.local.json", pre("Bash", {"command": f"sed -i s/a/b/ {H}/.claude/settings.local.json"}), "ask"),
 ("Write ~/.ssh/config", pre("Write", {"file_path": H + "/.ssh/config"}), "ask"),
 # (b) tajné soubory: čtení obsahu ano, použití klíče a výpis jmen ne
 ("cat bash_history", pre("Bash", {"command": "grep token ~/.bash_history"}), "ask"),
 ("cat soukromý klíč", pre("Bash", {"command": "cat ~/.ssh/id_rsa"}), "ask"),
 ("ls ~/.ssh", pre("Bash", {"command": "ls ~/.ssh"}), "allow"),
 ("ssh -i klíč", pre("Bash", {"command": "timeout 8 ssh -o BatchMode=yes -i ~/.ssh/klic_ed25519 user@h true"}), "allow"),
 ("grep ~/.ssh/config", pre("Bash", {"command": "grep -A4 pve ~/.ssh/config"}), "allow"),
 ("grep known_hosts", pre("Bash", {"command": "grep -rl chytrolin ~/.ssh/known_hosts"}), "allow"),
 # AskUserQuestion se od 0.8.0 nezamítá (kdy se ptát, určují pravidla)
 ("AskUserQuestion projde", pre("AskUserQuestion", {"questions": [{"question": "Mám použít A, nebo B?"}]}), "-"),
 ("AskUserQuestion subagent", pre("AskUserQuestion", {"questions": [{"question": "Pokračovat?"}]}, agent_id="a1"), "-"),
]


# 0.11.0: okno jen na nevratnou ztrátu dat; ostatní hook výslovně povolí (rozhodnutí Marka 18. 11. 2026)
import atexit, shutil
_g = tempfile.mkdtemp(dir=H, prefix=".guardtest-")  # git repo pod domovem mimo projekt
atexit.register(shutil.rmtree, _g, ignore_errors=True)  # uklidí i při pádu testu
def _git(*a): subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", "-C", _g, *a],
                             capture_output=True, check=True)
_git("init", "-q"); open(_g + "/cisty.txt", "w").write("a\n"); open(_g + "/zmeneny.txt", "w").write("a\n")
os.makedirs(_g + "/__pycache__"); open(_g + "/m.py", "w").write("x=1\n")
_git("add", "."); _git("commit", "-q", "-m", "x")
open(_g + "/zmeneny.txt", "a").write("b\n"); open(_g + "/necommitnuty.txt", "w").write("n\n")
open(_g + "/__pycache__/m.cpython-314.pyc", "w").write("c")
T += [
 ("pct exec: pracovní adresář agenta", pre("Bash", {"command": "pct exec 900 -- bash -c 'cd /srv/cfd/winglet/cfd; rm -f skripty/__pycache__/konv* skripty/a.pyc'"}), "allow"),
 ("ssh: rm v /srv/cfd po cd", pre("Bash", {"command": "ssh root@192.168.252.108 'cd /srv/cfd/profil_analyza && rm -f runs/*.pol'"}), "allow"),
 ("ssh: relativní cesta bez cd v /root", pre("Bash", {"command": "ssh h 'rm -f runs/a.pol'"}), "allow"),
 ("rm -rf /dev/shm/lit", pre("Bash", {"command": "rm -rf /dev/shm/lit"}), "allow"),
 ("přepis states.json v jobs/tmp", pre("Write", {"file_path": H + "/.claude/jobs/db76bcba/tmp/states.json"}), "allow"),
 ("echo > jobs/tmp", pre("Bash", {"command": "echo {} > ~/.claude/jobs/db76bcba/tmp/states.json"}), "allow"),
 ("rm v jobs/ mimo tmp", pre("Bash", {"command": "rm ~/.claude/jobs/db76bcba/vysledek.json"}), "ask"),
 ("sed -i README v git repu (čistý)", pre("Bash", {"command": f"sed -i s/a/b/ {_g}/cisty.txt"}), "allow"),
 ("sed -i změněný soubor v gitu", pre("Bash", {"command": f"sed -i s/a/b/ {_g}/zmeneny.txt"}), "ask"),
 ("rm čistého sledovaného souboru", pre("Bash", {"command": f"rm {_g}/cisty.txt"}), "allow"),
 ("rm téhož souboru po úpravě", pre("Bash", {"command": f"rm {_g}/zmeneny.txt"}), "ask"),
 ("rm necommitnutého souboru", pre("Bash", {"command": f"rm {_g}/necommitnuty.txt"}), "ask"),
 ("rm glob čistých souborů (cd + glob)", pre("Bash", {"command": f"cd {_g} && rm m.p*"}), "allow"),
 ("rm glob s necommitnutým", pre("Bash", {"command": f"rm {_g}/*.txt"}), "ask"),
 ("rm pycache v necommitnutém stavu", pre("Bash", {"command": f"rm -rf {_g}/__pycache__"}), "allow"),
 ("rm neexistující soubor v domově", pre("Bash", {"command": "rm ~/Dokumenty/x.pdf"}), "ask"),
 ("rm -rf /", pre("Bash", {"command": "rm -rf /"}), "ask"),
 ("ssh: OMV data", pre("Bash", {"command": "ssh host 'rm -rf /srv/dev-disk-by-uuid-x/Data/a'"}), "ask"),
 ("ssh: HA /config", pre("Bash", {"command": "ssh ha 'rm /config/.storage/core.config'"}), "ask"),
 ("ssh: HA zálohy claude (xargs rm)", pre("Bash", {"command": "ssh ha 'cd /config/zalohy-claude && ls -t x* | tail -n +4 | xargs -r rm'"}), "allow"),
 ("ssh: xargs rm v datech", pre("Bash", {"command": "ssh ha 'cd /config/packages && ls | xargs rm'"}), "ask"),
 ("ssh: HA log.1", pre("Bash", {"command": "ssh ha 'rm /config/home-assistant.log.1'"}), "allow"),
 ("ssh: segment claude (/root/claude)", pre("Bash", {"command": "ssh h 'rm -rf /home/u/Claude/tmp'"}), "allow"),
 ("ssh: /mnt a pycache", pre("Bash", {"command": "ssh h 'rm -rf /mnt/x/__pycache__; rm -rf /mnt/nas/y'"}), "ask"),
 ("ssh: neznámá proměnná v datech", pre("Bash", {"command": "ssh h 'rm -rf /mnt/nas/$X'"}), "ask"),
 ("ssh: neznámá proměnná mimo data", pre("Bash", {"command": "ssh h 'rm -rf /srv/cfd/$X'"}), "allow"),
 ("ssh: rm $F bez určení", pre("Bash", {"command": "ssh h 'rm $F'"}), "ask"),
 ("ssh: přepis souboru v /config", pre("Bash", {"command": "ssh ha 'echo x > /config/configuration.yaml'"}), "ask"),
 ("ssh: přepis souboru v /srv/cfd", pre("Bash", {"command": "ssh h 'echo x > /srv/cfd/a.txt'"}), "allow"),
 ("lokálně /opt a /var/lib bez okna", pre("Bash", {"command": "rm -rf /opt/x /var/lib/foo/bar"}), "allow"),
 ("zápis do known_hosts", pre("Bash", {"command": "echo x >> ~/.ssh/known_hosts; sed -i /h/d ~/.ssh/known_hosts"}), "allow"),
 ("Write known_hosts", pre("Write", {"file_path": H + "/.ssh/known_hosts"}), "allow"),
 ("rm ${XDG_RUNTIME_DIR:-/tmp}/x", pre("Bash", {"command": 'rm -f "${XDG_RUNTIME_DIR:-/tmp}"/marek-hooks/q.baze.n'}), "allow"),
 ("rm ${NEZNAMA:-~/Dokumenty}/x", pre("Bash", {"command": 'rm -f ${NEZNAMA_X:-/home/marek/Dokumenty}/x.pdf'}), "ask"),
 ("Write ~/.ssh/authorized_keys", pre("Write", {"file_path": H + "/.ssh/authorized_keys"}), "ask"),
 ("pycache kdekoli lokálně", pre("Bash", {"command": f"rm -rf {H}/Dokumenty/proj/__pycache__"}), "allow"),
 ("ExitPlanMode mlčí", pre("ExitPlanMode", {"plan": "x"}), "-"),
 ("EnterPlanMode mlčí", pre("EnterPlanMode", {}), "-"),
 ("Agent (od 0.12.0 na pozadí se smlouvou): allow", pre("Agent", {"prompt": "HOTOVO: x PŘI CHYBĚ: y", "run_in_background": True}), "allow"),
]
# vypínač: MAREK_HOOK_ALLOW=off = chování jako do 0.10.0 (bez výstupu)
os.environ["MAREK_HOOK_ALLOW"] = "off"
T += [("MAREK_HOOK_ALLOW=off: ls", pre("Bash", {"command": "ls"}), "-"),
      ("MAREK_HOOK_ALLOW=off: rm v datech dál ask", pre("Bash", {"command": "rm -rf ~/Hudba"}), "ask")]
del os.environ["MAREK_HOOK_ALLOW"]

# brána báze: nová session bez `pravidla`
T += [("brána 1. pokus", pre("Bash", {"command": "ls"}, sid="s2"), "deny"),
      ("brána 2. pokus", pre("Bash", {"command": "ls"}, sid="s2"), "deny"),
      ("brána 3. pokus (uvolní)", pre("Bash", {"command": "ls"}, sid="s2"), "allow"),
      ("brána: ToolSearch volný", pre("ToolSearch", {"query": "x"}, sid="s3"), "allow"),
      ("brána: konektor volný", pre("mcp__claude_ai_Marek_Second_Brain__hledej", {}, sid="s3"), "allow"),
      ("brána: subagent se nehlídá", pre("Bash", {"command": "ls"}, sid="s4", agent_id="a1"), "allow"),
      ("rozbitý vstup = nic", run("pretool-guard.py", "{nejson"), "-")]

# lokální soubor tajných cest mimo repo (HOME přepsán na prázdný adresář)
_home = tempfile.mkdtemp(); os.makedirs(_home + "/.config/marek-hooks")
open(_home + "/.config/marek-hooks/tajne.txt", "w").write("# komentář\nsupertajnasoubor\n[neplatny-regex\n")
_old = os.environ.get("HOME"); os.environ["HOME"] = _home
T += [("tajne.txt: shoda", pre("Bash", {"command": "cat /x/supertajnasoubor"}), "ask"),
      ("tajne.txt: neplatný regex nevadí", pre("Bash", {"command": "ls"}), "allow")]
os.environ["HOME"] = _old
os.environ["HOME"] = tempfile.mkdtemp()
T += [("bez tajne.txt: obecné vzory", pre("Bash", {"command": "cat ~/.bash_history"}), "ask"),
      ("bez tajne.txt: běžný příkaz", pre("Bash", {"command": "ls"}), "allow")]
os.environ["HOME"] = _old
# brzda zápisu do báze (0.10.0): `zapis` v tahu, kde se pracovalo, se poprvé zamítne
def tr(*items):
    f = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False)
    for i in items: f.write(json.dumps(i) + "\n")
    f.close(); return f.name
U = lambda t, u: {"type": "user", "uuid": u, "message": {"role": "user", "content": t}}
A = lambda *names: {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "t", "name": n, "input": {}} for n in names]}}
ZAPIS, HLEDEJ = "mcp__claude_ai_Marek_Second_Brain__zapis", "mcp__claude_ai_Marek_Second_Brain__hledej"
zap = lambda t, **kw: pre(ZAPIS, {}, sid="s1", transcript_path=t, **kw)
t_prace = tr(U("oprav to", "u1"), A("Bash", "Edit"))
t_prace2 = tr(U("oprav to", "u1"), A("Bash"), U("a ještě tohle", "u2"), A("Bash"))
t_baze = tr(U("oprav to", "u1"), A("Bash"), U("ano, souhlasím", "u2"), A(HLEDEJ, "ToolSearch"))
t_zadost = tr(U("změř to a zapiš do báze", "u1"), A("Bash"))
t_vytah = tr(U("udělej výtah z přílohy", "u1"), A("Bash"))
T += [("brzda: zápis po práci v tahu", zap(t_prace), "deny"),
      ("brzda: opakování v témže tahu", zap(t_prace), "allow"),
      ("brzda: nový tah s prací", zap(t_prace2), "deny"),
      ("brzda: tah jen s bází", zap(t_baze), "allow"),
      ("brzda: výslovná žádost o zápis", zap(t_zadost), "allow"),
      ("brzda: výtah dokumentu", zap(t_vytah), "allow"),
      ("brzda: subagent se nehlídá", pre(ZAPIS, {}, sid="s5", transcript_path=t_prace, agent_id="a1"), "allow"),
      ("brzda: bez přepisu projde", pre(ZAPIS, {}, sid="s1"), "allow"),
      ("brzda: jiný nástroj báze projde", pre(HLEDEJ, {}, sid="s1", transcript_path=t_prace2), "allow")]
os.environ["MAREK_ZAPIS_BRZDA"] = "off"
T += [("brzda: vypnutá proměnnou", pre(ZAPIS, {}, sid="s6", transcript_path=tr(U("x", "u9"), A("Bash")), agent_id=None), "allow")]
del os.environ["MAREK_ZAPIS_BRZDA"]
# dohled nad delegací (0.12.0): Agent jen na pozadí a se smlouvou, dlouhé zadání jiné session se smlouvou
SM = "HOTOVO: soubor x. ODHAD: 10 min. SIGNÁL: každých 5 min. PŘI CHYBĚ: opravit a hlásit. "
LONG = "Výpočet variant a tabulka výsledků. " * 12  # > 300 znaků
T += [("Agent v popředí se smlouvou", pre("Agent", {"prompt": SM}), "deny"),
      ("Agent v popředí (false) se smlouvou", pre("Agent", {"prompt": SM, "run_in_background": False}), "deny"),
      ("Agent na pozadí bez smlouvy", pre("Agent", {"prompt": "x", "run_in_background": True}), "deny"),
      ("Agent na pozadí jen s HOTOVO", pre("Agent", {"prompt": "HOTOVO: x", "run_in_background": True}), "deny"),
      ("Agent na pozadí jen s PŘI CHYBĚ", pre("Agent", {"prompt": "PŘI CHYBĚ: x", "run_in_background": True}), "deny"),
      ("Agent na pozadí se smlouvou", pre("Agent", {"prompt": SM, "run_in_background": True}), "allow"),
      ("Agent na pozadí se smlouvou (řetězec true)", pre("Agent", {"prompt": SM, "run_in_background": "true"}), "allow"),
      ("Agent Explore v popředí taky deny", pre("Agent", {"prompt": SM, "subagent_type": "Explore"}), "deny"),
      ("Agent volaný subagentem se hlídá taky", pre("Agent", {"prompt": "x"}, agent_id="a1"), "deny"),
      ("SendMessage dlouhá bez smlouvy", pre("SendMessage", {"to": "bridge:session_X", "message": LONG}), "deny"),
      ("SendMessage dlouhá jen s HOTOVO", pre("SendMessage", {"to": "bridge:session_X", "message": LONG + "HOTOVO: x"}), "deny"),
      ("SendMessage dlouhá se smlouvou", pre("SendMessage", {"to": "bridge:session_X", "message": LONG + SM}), "allow"),
      ("SendMessage krátká bez smlouvy", pre("SendMessage", {"to": "bridge:session_X", "message": "Pošli stav."}), "allow"),
      ("SendMessage [ACK] dlouhá", pre("SendMessage", {"to": "bridge:session_X", "message": "[ACK] " + LONG}), "allow"),
      ("SendMessage STAV: dlouhá", pre("SendMessage", {"to": "bridge:session_X", "message": "STAV: " + LONG}), "allow"),
      ("SendMessage ODPOVĚĎ: dlouhá", pre("SendMessage", {"to": "bridge:session_X", "message": "ODPOVĚĎ: " + LONG}), "allow"),
      ("SendMessage dlouhá pro main", pre("SendMessage", {"to": "main", "message": LONG}), "allow"),
      ("SendMessage strukturovaná zpráva", pre("SendMessage", {"to": "x", "message": {"type": "shutdown_request"}}), "allow")]
os.environ["MAREK_DOHLED"] = "off"
T += [("dohled vypnutý: Agent v popředí", pre("Agent", {"prompt": "x"}), "allow"),
      ("dohled vypnutý: SendMessage dlouhá", pre("SendMessage", {"to": "bridge:session_X", "message": LONG}), "allow")]
del os.environ["MAREK_DOHLED"]
import shutil; shutil.rmtree(_g, ignore_errors=True)
bad = 0
for n, (rc, dec), exp in T:
    ok = rc == 0 and dec == exp
    bad += not ok
    print(("OK  " if ok else "CHYBA"), f"{n:34} -> {dec:6} (čekáno {exp}, rc={rc})")
print("pretool: selhalo", bad, "z", len(T))

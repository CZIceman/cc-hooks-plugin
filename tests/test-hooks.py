#!/usr/bin/env python3
"""Test hooků bez spuštění modelu: do skriptů se pošle vzorový JSON a porovná se výsledek."""
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
 ("ls", pre("Bash", {"command": "ls -la ~"}), "-"),
 ("grep journal", pre("Bash", {"command": "journalctl -b | grep -i error"}), "-"),
 ("git status", pre("Bash", {"command": "git status --short"}), "-"),
 ("git push", pre("Bash", {"command": "git push origin master"}), "-"),
 ("git commit", pre("Bash", {"command": "git commit -m x"}), "-"),
 ("claude -p", pre("Bash", {"command": "claude -p 'ahoj'"}), "-"),
 ("Agent", pre("Agent", {"prompt": "x"}), "-"),
 ("zadej_ukol", pre("mcp__claude_ai_D_lna__zadej_ukol", {}), "-"),
 ("Read /etc/passwd", pre("Read", {"file_path": "/etc/passwd"}), "-"),
 # systémové změny se od 0.8.0 neptají (rozhodnutí 29. 10. 2026)
 ("sudo dnf install", pre("Bash", {"command": "sudo dnf install -y htop"}), "-"),
 ("sudo dnf5 upgrade", pre("Bash", {"command": "sudo dnf5 upgrade -y 2>&1 | tail -25"}), "-"),
 ("systemctl disable", pre("Bash", {"command": "systemctl disable --now cups"}), "-"),
 ("sudo -n true", pre("Bash", {"command": "sudo -n true 2>&1 && echo SUDO_OK; id"}), "-"),
 ("sudo smartctl (čtení)", pre("Bash", {"command": "sudo smartctl -H -A /dev/nvme0 2>/dev/null | grep -Ei overall"}), "-"),
 ("sudo grubby", pre("Bash", {"command": "sudo grubby --default-kernel"}), "-"),
 ("sudo tee /etc", pre("Bash", {"command": "echo x | sudo tee /etc/foo.conf"}), "-"),
 ("echo > /etc", pre("Bash", {"command": "echo x > /etc/foo.conf"}), "-"),
 ("setpci", pre("Bash", {"command": "setpci -s 33:00.5 CAP_MSI+2.w"}), "-"),
 ("chmod 600 klíč", pre("Bash", {"command": "chmod 600 ~/.config/app/agent.key"}), "-"),
 ("mount | grep", pre("Bash", {"command": "mount | grep /mnt/nas"}), "-"),
 ("Edit /etc", pre("Edit", {"file_path": "/etc/dnf/dnf.conf"}), "-"),
 ("Edit ~/.bashrc.d", pre("Write", {"file_path": H + "/.bashrc.d/x.sh"}), "-"),
 ("Write /root/projekt (pve)", pre("Write", {"file_path": "/root/hevcpipe/hevcpipe/runner.py"}), "-"),
 # slova v textu, který shell nespouští
 ("echo se slovem sudo", pre("Bash", {"command": "echo '== sudo pam'; ls /etc/pam.d"}), "-"),
 ("grep na chown", pre("Bash", {"command": "grep -n chown README.md"}), "-"),
 ("heredoc s rm a dd", pre("Bash", {"command": "python3 - <<'EOF'\nimport os\nos.rmdir('/x')\nfor depth,dd in []: pass\nprint('rm -rf /')\nEOF\necho ok"}), "-"),
 ("heredoc, pak skutečné rm", pre("Bash", {"command": "cat > x.sh <<'E'\nrm -rf /\nE\nrm -rf ~/Hudba"}), "ask"),
 ("python3 -c s rm", pre("Bash", {"command": "python3 -c 'import os; print(\"rm -rf /\")'"}), "-"),
 ("dd jako test rychlosti", pre("Bash", {"command": f"dd if=/dev/zero of={SCR}/t.bin bs=8M count=64"}), "-"),
 # (a) mazání
 ("rm mimo pracovní místa", pre("Bash", {"command": "rm -rf ~/Hudba"}), "ask"),
 ("rm ve scratchpadu", pre("Bash", {"command": f"rm -f {SCR}/a.txt"}), "-"),
 ("rm přes proměnnou ve scratchpadu", pre("Bash", {"command": f"S={SCR}; D=$S/pkg; rm -rf $D; mkdir -p $D"}), "-"),
 ("rm neznámá proměnná", pre("Bash", {"command": "rm -rf $NEZNAMA/x"}), "ask"),
 ("rm v /tmp", pre("Bash", {"command": "rm -rf /tmp/x"}), "-"),
 ("rm v projektu", pre("Bash", {"command": f"rm -f {PRJ}/a.txt"}, cwd=PRJ), "-"),
 ("rm relativně v projektu", pre("Bash", {"command": "rm -f a.txt"}, cwd=PRJ), "-"),
 ("cd do projektu a rm", pre("Bash", {"command": f"cd {PRJ}/sub && rm -rf dodavka"}, cwd=PRJ), "-"),
 ("rm, cwd = HOME", pre("Bash", {"command": "rm a.txt"}, cwd=H), "ask"),
 ("rm na NAS", pre("Bash", {"command": "rm -rf /mnt/nas/data/_Vymena/test"}), "ask"),
 ("sudo rm /etc", pre("Bash", {"command": "sudo rm -f /etc/foo.conf"}), "ask"),
 ("bash -c rm", pre("Bash", {"command": "bash -c 'rm -rf ~/Hudba'"}), "ask"),
 ("find -delete mimo", pre("Bash", {"command": "find ~/Fotky -name '*.tmp' -delete"}), "ask"),
 ("find -delete scratchpad", pre("Bash", {"command": f"find {SCR} -name '*.tmp' -delete"}), "-"),
 ("xargs rm, cwd HOME", pre("Bash", {"command": "ls | xargs rm"}, cwd=H), "ask"),
 ("rsync --delete mimo", pre("Bash", {"command": "rsync -a --delete src/ /mnt/nas/data/x/"}), "ask"),
 ("git reset --hard", pre("Bash", {"command": "git reset --hard HEAD~3"}, cwd=PRJ), "ask"),
 ("git push --force", pre("Bash", {"command": "git push --force origin master"}, cwd=PRJ), "ask"),
 ("git reset --hard ve scratchpadu", pre("Bash", {"command": f"cd {SCR}/repo && git reset --hard"}), "-"),
 ("mkfs", pre("Bash", {"command": "sudo mkfs.ext4 /dev/sdb1"}), "ask"),
 ("dd na disk", pre("Bash", {"command": "sudo dd if=x.img of=/dev/sda bs=4M"}), "ask"),
 # pve: příkazy v kontejneru
 ("pct exec rm /var/tmp", pre("Bash", {"command": "pct exec 109 -- bash -c 'rm -f /var/tmp/avcheck/enc/*'"}), "-"),
 ("pct exec systemctl", pre("Bash", {"command": "pct exec 109 -- bash -c 'systemctl stop hevcpipe-pilot; systemctl reset-failed hevcpipe-pilot'"}), "-"),
 ("pct exec > /var/tmp log", pre("Bash", {"command": "pct exec 109 -- python3 /var/tmp/u.py > /var/tmp/u.log"}), "-"),
 ("pct exec rm média", pre("Bash", {"command": "pct exec 109 -- bash -c 'rm -rf /media/nas/filmy/x'"}), "ask"),
 ("ssh host rm", pre("Bash", {"command": "ssh root@nas 'rm -rf /srv/data/x'"}), "ask"),
 ("ssh host čtení", pre("Bash", {"command": "ssh -i ~/.ssh/klic_ed25519 user@h 'hostname; df -h'"}), "-"),
 # přepis existujících souborů v datech
 ("mv ve scratchpadu", pre("Bash", {"command": f"mv {SCR}/a {SCR}/b"}), "-"),
 ("sed -i v projektu", pre("Bash", {"command": "sed -i s/a/b/ main.py"}, cwd=PRJ), "-"),
 ("sed -i v datech mimo projekt", pre("Bash", {"command": f"sed -i s/a/b/ {H}/.bashrc"}, cwd=PRJ), "ask"),
 ("echo >> paměť Claude", pre("Bash", {"command": f"echo x >> {H}/.claude/projects/p/memory/MEMORY.md"}), "-"),
 # (c) nastavení Claude Code
 ("Edit ~/.claude/settings.json", pre("Edit", {"file_path": H + "/.claude/settings.json"}), "ask"),
 ("Write ~/.claude/hooks", pre("Write", {"file_path": H + "/.claude/hooks/x.py"}), "ask"),
 ("echo >> settings.json", pre("Bash", {"command": f"echo x >> {H}/.claude/settings.json"}), "ask"),
 ("sed -i settings.local.json", pre("Bash", {"command": f"sed -i s/a/b/ {H}/.claude/settings.local.json"}), "ask"),
 ("Write ~/.ssh/config", pre("Write", {"file_path": H + "/.ssh/config"}), "ask"),
 # (b) tajné soubory: čtení obsahu ano, použití klíče a výpis jmen ne
 ("cat bash_history", pre("Bash", {"command": "grep token ~/.bash_history"}), "ask"),
 ("cat soukromý klíč", pre("Bash", {"command": "cat ~/.ssh/id_rsa"}), "ask"),
 ("ls ~/.ssh", pre("Bash", {"command": "ls ~/.ssh"}), "-"),
 ("ssh -i klíč", pre("Bash", {"command": "timeout 8 ssh -o BatchMode=yes -i ~/.ssh/klic_ed25519 user@h true"}), "-"),
 ("grep ~/.ssh/config", pre("Bash", {"command": "grep -A4 pve ~/.ssh/config"}), "-"),
 ("grep known_hosts", pre("Bash", {"command": "grep -rl chytrolin ~/.ssh/known_hosts"}), "-"),
 # AskUserQuestion se od 0.8.0 nezamítá (kdy se ptát, určují pravidla)
 ("AskUserQuestion projde", pre("AskUserQuestion", {"questions": [{"question": "Mám použít A, nebo B?"}]}), "-"),
 ("AskUserQuestion subagent", pre("AskUserQuestion", {"questions": [{"question": "Pokračovat?"}]}, agent_id="a1"), "-"),
]

# brána báze: nová session bez `pravidla`
T += [("brána 1. pokus", pre("Bash", {"command": "ls"}, sid="s2"), "deny"),
      ("brána 2. pokus", pre("Bash", {"command": "ls"}, sid="s2"), "deny"),
      ("brána 3. pokus (uvolní)", pre("Bash", {"command": "ls"}, sid="s2"), "-"),
      ("brána: ToolSearch volný", pre("ToolSearch", {"query": "x"}, sid="s3"), "-"),
      ("brána: konektor volný", pre("mcp__claude_ai_Marek_Second_Brain__hledej", {}, sid="s3"), "-"),
      ("brána: subagent se nehlídá", pre("Bash", {"command": "ls"}, sid="s4", agent_id="a1"), "-"),
      ("rozbitý vstup = nic", run("pretool-guard.py", "{nejson"), "-")]

# lokální soubor tajných cest mimo repo (HOME přepsán na prázdný adresář)
_home = tempfile.mkdtemp(); os.makedirs(_home + "/.config/marek-hooks")
open(_home + "/.config/marek-hooks/tajne.txt", "w").write("# komentář\nsupertajnasoubor\n[neplatny-regex\n")
_old = os.environ.get("HOME"); os.environ["HOME"] = _home
T += [("tajne.txt: shoda", pre("Bash", {"command": "cat /x/supertajnasoubor"}), "ask"),
      ("tajne.txt: neplatný regex nevadí", pre("Bash", {"command": "ls"}), "-")]
os.environ["HOME"] = _old
os.environ["HOME"] = tempfile.mkdtemp()
T += [("bez tajne.txt: obecné vzory", pre("Bash", {"command": "cat ~/.bash_history"}), "ask"),
      ("bez tajne.txt: běžný příkaz", pre("Bash", {"command": "ls"}), "-")]
os.environ["HOME"] = _old
bad = 0
for n, (rc, dec), exp in T:
    ok = rc == 0 and dec == exp
    bad += not ok
    print(("OK  " if ok else "CHYBA"), f"{n:34} -> {dec:6} (čekáno {exp}, rc={rc})")
print("pretool: selhalo", bad, "z", len(T))

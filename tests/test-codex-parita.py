#!/usr/bin/env python3
"""Regrese Codex hooků na syntetických vstupech 0.171.0; bez účtu a bez sítě."""

from concurrent.futures import ThreadPoolExecutor
import json
import shlex
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HOOKS = Path(__file__).resolve().parents[1] / "hooks"
BRAIN = "mcp__second_brain__"
PEER = "aabbccdd-aabb-4cdd-8abb-112233445566"
MESSAGE = "bbccddee-bbcc-4dee-8bcc-223344556677"


class CodexHooks(unittest.TestCase):
    def setUp(self):
        tmp = self.enterContext(tempfile.TemporaryDirectory(prefix="test-codex-parita-"))
        self.root = Path(tmp)
        self.codex = self.root / "Codex home"
        self.env = dict(os.environ, HOME=tmp, CODEX_HOME=str(self.codex), XDG_RUNTIME_DIR=tmp,
                        MAREK_HOOK_KLIENT="codex", PYTHONDONTWRITEBYTECODE="1")
        self.transcript = self.root / "rollout.jsonl"
        self.turn = "turn-1"

    def hook(self, script, **payload):
        interpreter = "bash" if script.endswith(".sh") else sys.executable
        data = {"cwd": str(self.root), "session_id": "session-1", "turn_id": self.turn,
                "transcript_path": str(self.transcript), **payload}
        result = subprocess.run([interpreter, HOOKS / script], env=self.env, input=json.dumps(data),
                                capture_output=True, text=True, check=True)
        self.assertEqual(result.stderr, "")
        return result.stdout

    def guard(self, tool, event="PreToolUse", response=None, **arguments):
        output = self.hook("pretool-guard.py", hook_event_name=event, tool_name=tool,
                           tool_input=arguments, tool_response=response)
        return json.loads(output)["hookSpecificOutput"] if output else {}

    def rules(self, response=None):
        if response is None:
            response = {"content": [{"type": "text", "text": "test"}]}
        return self.guard(BRAIN + "pravidla", "PostToolUse", response)

    def rollout(self, *records):
        with self.transcript.open("w") as stream:
            for kind, payload in records:
                stream.write(json.dumps({"type": kind, "payload": payload}) + "\n")

    def event(self, event, **data):
        return ("event_msg", {"type": event, **data})

    def user(self, text):
        return ("response_item", {"type": "message", "role": "user",
                                  "content": [{"type": "input_text", "text": text}]})

    def call(self, name, **arguments):
        return ("response_item", {"type": "function_call", "name": name,
                                  "arguments": json.dumps(arguments)})

    def uklid(self):
        subprocess.run([sys.executable, HOOKS / "codex-uklid.py"], env=self.env, input="{}", text=True,
                       capture_output=True, check=True)

    def test_manifest_pluginu_codexu(self):
        manifest = json.loads((HOOKS.parent / ".codex-plugin/plugin.json").read_text())
        claude = json.loads((HOOKS.parent / ".claude-plugin/plugin.json").read_text())
        self.assertEqual((manifest["name"], manifest["version"]), (claude["name"], claude["version"]))
        self.assertEqual(manifest["hooks"], "./hooks/codex-hooks.json")
        events = json.loads((HOOKS / "codex-hooks.json").read_text())["hooks"]
        self.assertEqual(set(events), {"SessionStart", "PreToolUse", "PermissionRequest", "PostToolUse",
                                       "Stop", "UserPromptSubmit"})
        for groups in events.values():
            for group in groups:
                for handler in group["hooks"]:
                    words = handler["command"].split()
                    self.assertEqual(words[:2], ["env", "MAREK_HOOK_KLIENT=codex"])
                    script = words[3].strip('"').replace("${PLUGIN_ROOT}", str(HOOKS.parent))
                    self.assertTrue(Path(script).is_file(), script)
        claude_hooks = (HOOKS / "hooks.json").read_text()
        self.assertNotIn("codex", claude_hooks)

    def test_uklid_stare_instalace(self):
        self.codex.mkdir()
        scripts = self.codex / "marek-hooks"
        scripts.mkdir()
        (scripts / "pretool-guard.py").write_text("# stará kopie\n")
        old = shlex.join(["env", "MAREK_HOOK_KLIENT=codex", "python3", str(scripts / "pretool-guard.py")])
        old_quoted = f'env MAREK_HOOK_KLIENT=codex bash "{scripts / "baze-start.sh"}"'
        foreign = {"type": "command", "command": "cizi prikaz"}
        hooks = self.codex / "hooks.json"
        hooks.write_text(json.dumps({"hooks": {
            "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": old}, foreign]}],
            "SessionStart": [{"hooks": [{"type": "command", "command": old_quoted}]}],
            "SessionEnd": []}}))
        (self.codex / "AGENTS.md").write_text("<!-- Generuje plugin marek-cc-hooks -->\n# staré\n")
        self.uklid()
        cleaned = json.loads(hooks.read_text())["hooks"]
        self.assertEqual(cleaned, {"PreToolUse": [{"matcher": "Bash", "hooks": [foreign]}], "SessionEnd": []})
        self.assertFalse((self.codex / "AGENTS.md").exists())
        self.assertTrue(scripts.exists())  # běžící relace má staré hooky ještě načtené
        stamp = hooks.stat().st_mtime_ns
        self.uklid()
        self.assertFalse(scripts.exists())
        self.assertEqual(hooks.stat().st_mtime_ns, stamp)
        self.assertEqual(list(self.codex.glob("*pred-pluginem*")), [])

    def test_uklid_necha_cizi_soubory(self):
        self.codex.mkdir()
        (self.codex / "AGENTS.md").write_text("# můj ruční soubor\n")
        (self.codex / "hooks.json").write_text("{rozbité")
        self.uklid()
        self.assertEqual((self.codex / "AGENTS.md").read_text(), "# můj ruční soubor\n")
        self.assertEqual((self.codex / "hooks.json").read_text(), "{rozbité")
        self.codex.joinpath("AGENTS.md").unlink()
        self.codex.joinpath("hooks.json").unlink()
        self.codex.rmdir()
        self.uklid()
        self.assertFalse(self.codex.exists())

    def test_sessionstart_a_kompakt(self):
        message = self.hook("baze-start.sh", source="startup")
        self.assertIn("až po jeho reakci", message)
        self.assertIn("second-brain", message)
        self.assertFalse(message.startswith(("[", "{")))
        local = self.root / ".config/marek-hooks"
        local.mkdir(parents=True)
        (local / "codex-mistni.md").write_text("Místní doplněk testu\n")
        rules = self.hook("pravidla-start.sh", source="startup")
        self.assertTrue(rules.startswith("# Pravidla pro Codex"))
        self.assertNotIn("<!--", rules)
        self.assertTrue(rules.endswith("Místní doplněk testu\n"))
        self.assertNotIn("HANDOFF.md v projektu, je-li", rules)
        self.assertIn("[Po zhuštění kontextu]", self.hook("pravidla-start.sh", source="compact"))

    def test_brana_a_vypadek_konektoru(self):
        self.rules({"content": [], "isError": True})
        self.assertEqual(self.guard(BRAIN + "pravidla"), {})
        with ThreadPoolExecutor(max_workers=3) as pool:
            got = list(pool.map(lambda _: self.guard("Bash", command="ls").get("permissionDecision"), range(3)))
        self.assertEqual(got.count("deny"), 2)
        self.assertEqual(got.count(None), 1)

    def test_brana_uspesna_pravidla(self):
        self.assertEqual(self.guard("Bash", command="ls")["permissionDecision"], "deny")
        self.rules()
        self.assertEqual(self.guard("Bash", command="ls"), {})

    def test_nedostupny_stav_baze_nevyrazuje_strazce(self):
        bad_runtime = self.root / "nedostupny"
        bad_runtime.write_text("")
        self.env["XDG_RUNTIME_DIR"] = str(bad_runtime)
        decision = self.guard("Bash", command="cat ~/.ssh/id_rsa")
        self.assertIn("čtení tajného souboru", decision["permissionDecisionReason"])

    def test_brzda_a_vyjimky(self):
        self.rollout(self.event("task_started", turn_id=self.turn), self.user("Změř to."),
                     self.call("exec_command", cmd="ls"))
        self.assertEqual(self.guard(BRAIN + "zapis")["permissionDecision"], "deny")
        self.assertEqual(self.guard(BRAIN + "zapis"), {})
        for name, prompt in (("turn-2", "Ano, zapiš výsledek."), ("turn-3", "Nezávislý dotaz")):
            self.turn = name
            self.rollout(self.event("task_started", turn_id=name), self.user(prompt),
                         self.call("exec_command", cmd="ls"))
            result = self.guard(BRAIN + "zapis")
            self.assertEqual(result.get("permissionDecision"), "deny" if name == "turn-3" else None)
        self.turn = "chybejici"
        self.assertEqual(self.guard(BRAIN + "zapis"), {})

    def test_ochrana_cest(self):
        self.rules()
        for command in ("cat ~/.ssh/id_rsa", "cat < ~/.ssh/id_rsa", 'cat "$CODEX_HOME/auth.json"',
                        f'cat "{self.codex / "auth.json"}"',
                        f'echo test >> "{self.codex / "config.toml"}"'):
            self.assertIn("Rizikovou akci", self.guard("Bash", command=command)["permissionDecisionReason"])
        self.assertEqual(self.guard("Bash", command="ls ~/.ssh/id_rsa"), {})
        self.assertEqual(self.guard("mcp__filesystem__read_file", path="~/.ssh/id_rsa")["permissionDecision"], "deny")
        self.assertEqual(self.guard("mcp__filesystem__read_file", path="~/.ssh/id_ed25519.pub"), {})
        patch = f"*** Begin Patch\n*** Update File: normal.py\n*** Move to: {self.codex}/config.toml\n*** End Patch"
        self.assertEqual(self.guard("apply_patch", command=patch)["permissionDecision"], "deny")
        self.assertEqual(self.guard("apply_patch", command="*** Add File: test.txt\n+test"), {})
        permission = self.guard("Bash", "PermissionRequest", command="ls")
        self.assertEqual(permission.get("decision"), {"behavior": "allow"})
        self.assertEqual(self.guard("apply_patch", "PermissionRequest", command=patch), {})

    def test_zamitnuti_popise_rucni_krok(self):
        self.rules()
        decision = self.guard("Bash", command="cat < ~/.ssh/id_rsa")
        self.assertEqual(decision["permissionDecision"], "deny")
        reason = decision["permissionDecisionReason"]
        for part in ("Jednou větou", "co se zastavilo a proč", "jeden přesný příkaz", "Marek spustí sám",
                     "`!příkaz`", "co a kde má změnit", "Pojistku neobcházej"):
            self.assertIn(part, reason)

    def test_stop_a_dokumentace(self):
        start = self.event("task_started", turn_id=self.turn)
        self.rollout(start, self.user("Oprav to."))
        warning = json.loads(self.hook("stop-guard.py", last_assistant_message="Hotovo."))
        self.assertIn("neproběhl", warning["systemMessage"])
        self.assertEqual(self.hook("stop-guard.py", last_assistant_message="Hotovo.", stop_hook_active=True), "")
        git_commit = self.call("exec_command", cmd="git commit -am oprava")
        self.rollout(start, self.user("Oprav to."), git_commit)
        self.assertIn("nedotkl se dokumentace", self.hook("stop-guard.py", last_assistant_message="Dokončeno."))
        doc = ("response_item", {"type": "custom_tool_call", "name": "apply_patch",
                                 "input": "*** Update File: README.md\n@@\n+oprava"})
        self.rollout(start, self.user("Oprav to."), doc, git_commit)
        self.assertEqual(self.hook("stop-guard.py", last_assistant_message="Dokončeno."), "")

    def test_dohled(self):
        self.rules()
        self.assertEqual(self.guard("spawn_agent", message="Zpracuj úkol.")["permissionDecision"], "deny")
        self.assertEqual(self.guard("spawn_agent", message="HOTOVO: výsledek. PŘI CHYBĚ: napiš."), {})
        items = [{"type": "text", "text": "HOTOVO: výsledek."},
                 {"type": "text", "text": "PŘI CHYBĚ: napiš."}]
        self.assertEqual(self.guard("spawn_agent", items=items), {})
        image = {"type": "image", "text": "HOTOVO: PŘI CHYBĚ:"}
        self.assertEqual(self.guard("spawn_agent", items=[image])["permissionDecision"], "deny")
        start = self.event("task_started", turn_id=self.turn)
        spawn = self.event("collab_agent_spawn_end", new_thread_id=PEER, status="running")
        process = self.event("exec_command_begin", call_id="call-1", process_id="1234")
        self.rollout(start, spawn, process)
        self.assertIn("1234", self.hook("dohled-start.py", source="resume"))
        self.assertIn(PEER, self.hook("dohled-start.py", source="compact"))
        self.assertEqual(json.loads(self.hook("stop-guard.py"))["decision"], "block")
        active_v2 = self.event("sub_agent_activity", agent_thread_id=PEER, kind="started")
        done_v2 = self.event("sub_agent_activity", agent_thread_id=PEER, kind="completed")
        self.rollout(start, active_v2)
        self.assertIn(PEER, self.hook("dohled-start.py", source="resume"))
        self.rollout(start, active_v2, done_v2)
        self.assertEqual(self.hook("stop-guard.py"), "")
        done = self.event("collab_waiting_end", statuses={PEER: {"completed": "výsledek"}})
        stop = self.event("exec_command_end", call_id="call-1", exit_code=0)
        self.rollout(start, spawn, process, done, stop)
        self.assertEqual(self.hook("stop-guard.py"), "")

    def test_ack(self):
        start = f'<codex-peer from="{PEER}" id="{MESSAGE}">\n'
        body = start + "Zkušební příchozí zpráva\n</codex-peer>"
        output = json.loads(self.hook("ack-guard.py", prompt=body))["hookSpecificOutput"]
        self.assertIn(f"reply_to={MESSAGE}", output["additionalContext"])
        self.assertIn("výslovně povolil", output["additionalContext"])
        self.assertEqual(self.hook("ack-guard.py", prompt=start + "[ACK] Přijato\n</codex-peer>"), "")
        self.assertEqual(self.hook("ack-guard.py", prompt=body, session_id=PEER), "")
        self.assertEqual(self.hook("ack-guard.py", prompt="citace zprávy:\n" + body), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)

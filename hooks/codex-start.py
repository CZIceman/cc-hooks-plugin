#!/usr/bin/env python3
"""Nainstaluje pravidla a hooky Codexu ručně nebo tiše při startu Claude Code."""

import fcntl
import json
import os
from pathlib import Path
import shlex
import sys
import tempfile
import time

SOURCE = Path(__file__).resolve().parent
GUARD = ("python3", "pretool-guard.py")
EVENTS = {
    "SessionStart": (
        ("bash", "baze-start.sh", None),
        ("bash", "pravidla-start.sh", "^compact$"),
        ("python3", "dohled-start.py", "^(resume|compact)$"),
    ),
    "PreToolUse": ((*GUARD, None),),
    "PermissionRequest": ((*GUARD, "^Bash$"),),
    "PostToolUse": ((*GUARD, r"(?i)^mcp__second[-_]brain__pravidla$"),),
    "Stop": (("python3", "stop-guard.py", None),),
    "UserPromptSubmit": (("python3", "ack-guard.py", None),),
}
SUPPORT = ("codex_transcript.py", "dohled.py")
CLIENT = ("env", "MAREK_HOOK_KLIENT=codex")

def enabled(name):
    return os.environ.get(name, "1").strip() != "0"


def write_if_changed(path, data, mode=0o600):
    previous = path.read_bytes() if path.exists() else None
    if previous == data:
        return
    if previous is not None:
        backup = path.with_name(path.name + ".pred-pluginem")
        if backup.exists():
            backup = backup.with_name(backup.name + "-" + time.strftime("%Y%m%d-%H%M%S"))
            if backup.exists():
                backup = backup.with_name(backup.name + "-" + str(time.time_ns()))
        fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as saved:
            saved.write(previous)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".marek-hooks-", delete=False) as tmp:
        tmp.write(data)
        staged = Path(tmp.name)
    try:
        staged.chmod(mode)
        staged.replace(path)
    finally:
        staged.unlink(missing_ok=True)


def install_agents(codex, config_dir):
    if not enabled("MAREK_CODEX_AGENTS"):
        return
    rules = (SOURCE.parent / "codex" / "AGENTS.md").read_text(encoding="utf-8").rstrip("\n")
    local = config_dir / "codex-mistni.md"
    if local.is_file():
        extra = local.read_text(encoding="utf-8").strip("\n")
        if extra:
            rules += "\n\n" + extra
    write_if_changed(codex / "AGENTS.md", (rules + "\n").encode())


def managed_handler(handler, commands):
    if not isinstance(handler, dict) or not isinstance(handler.get("command"), str):
        return False
    try:
        return tuple(shlex.split(handler["command"])) in commands
    except ValueError:
        return False


def install_hooks(codex):
    path = codex / "hooks.json"
    config = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if not isinstance(config, dict) or not isinstance(config.get("hooks", {}), dict):
        raise ValueError("hooks.json musí obsahovat objekt hooks.")
    hook_config = config.setdefault("hooks", {})
    before = json.dumps(config, ensure_ascii=False)
    scripts = codex / "marek-hooks"
    commands = {(*CLIENT, interpreter, str(scripts / name))
                for entries in EVENTS.values() for interpreter, name, _ in entries}
    on = enabled("MAREK_CODEX_HOOKS")
    for event, entries in EVENTS.items():
        old_groups = hook_config.get(event, [])
        if not isinstance(old_groups, list):
            raise ValueError(f"hooks.json má neplatnou událost {event}.")
        groups = []
        for group in old_groups:
            if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                raise ValueError(f"hooks.json má neplatnou skupinu {event}.")
            remaining = [handler for handler in group["hooks"] if not managed_handler(handler, commands)]
            if len(remaining) == len(group["hooks"]):
                groups.append(group)
            elif remaining:
                groups.append({**group, "hooks": remaining})
        if on:
            for interpreter, name, matcher in entries:
                command = shlex.join((*CLIENT, interpreter, str(scripts / name)))
                group = {"hooks": [{"type": "command", "command": command, "timeout": 10}]}
                if matcher is not None:
                    group["matcher"] = matcher
                groups.append(group)
        if groups:
            hook_config[event] = groups
        else:
            hook_config.pop(event, None)
    if on:
        assets = set(SUPPORT) | {name for entries in EVENTS.values() for _, name, _ in entries}
        scripts.mkdir(mode=0o700, exist_ok=True)
        for name in sorted(assets):
            write_if_changed(scripts / name, (SOURCE / name).read_bytes(), 0o700)
    if before != json.dumps(config, ensure_ascii=False):
        write_if_changed(path, (json.dumps(config, ensure_ascii=False, indent=2) + "\n").encode())


def main():
    manual = sys.argv[1:] == ["--install"]
    if sys.argv[1:] and not manual:
        print("Použití: python3 hooks/codex-start.py --install", file=sys.stderr)
        return 2
    codex = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").expanduser().resolve()
    config_dir = Path.home() / ".config" / "marek-hooks"
    try:
        if manual:
            codex.mkdir(mode=0o700, parents=True, exist_ok=True)
        if not codex.is_dir():
            return 0
        fd = os.open(codex, os.O_RDONLY | os.O_DIRECTORY)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            # Claude při startu nadále pokračuje i při chybě jedné části instalace.
            failed = False
            for install in (lambda: install_agents(codex, config_dir), lambda: install_hooks(codex)):
                try:
                    install()
                except (OSError, ValueError):
                    failed = True
            if manual and failed:
                print("Instalace nebyla úplná. Zkontroluj práva a formát hooks.json.", file=sys.stderr)
                return 1
        finally:
            os.close(fd)
    except OSError:
        if manual:
            print("Adresář Codexu se nepodařilo vytvořit nebo zamknout.", file=sys.stderr)
            return 1
    if manual:
        print("Pravidla a hooky Codexu jsou aktualizované podle nastavených vypínačů. Zkontroluj je v /hooks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

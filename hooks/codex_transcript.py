"""Vstupy Codexu 0.171.0 pro sdílené hooky. Přepis se čte po řádcích."""

import json
import re
import time

BRAIN = re.compile(r"^mcp__second[-_]brain__(\w+)$", re.I)
PATCH_PATH = re.compile(r"^\*\*\* (?:Add File|Update File|Delete File|Move to): (.+)$", re.M)


def brain_method(name):
    match = BRAIN.fullmatch(name)
    return match[1].lower() if match else ""


def patch_paths(patch):
    return PATCH_PATH.findall(patch)


def records(path, budget=1.0):
    deadline = time.monotonic() + budget
    with open(path, "rb") as stream:
        for index, line in enumerate(stream):
            if index % 256 == 0 and time.monotonic() > deadline:
                raise TimeoutError("Čtení přepisu překročilo časový rozpočet")
            if not any(tag in line for tag in (b'"event_msg"', b'"response_item"')):
                continue
            try:
                record = json.loads(line)
            except (ValueError, UnicodeError):
                continue
            if not isinstance(record, dict):
                continue
            payload = record.get("payload")
            if isinstance(payload, dict):
                yield record.get("type"), payload


def turn(path, turn_id):
    """Poslední uživatelský vstup a volání nástrojů v konkrétním tahu."""
    prompt = ""
    tools = []
    active = False
    found = False
    for kind, payload in records(path):
        event = payload.get("type")
        if kind == "event_msg":
            if event in ("task_started", "turn_started"):
                active = bool(turn_id) and payload.get("turn_id") == turn_id
                found |= active
            elif event in ("task_complete", "turn_complete", "turn_aborted"):
                active = False
            continue
        if not active or kind != "response_item":
            continue
        if event == "message" and payload.get("role") == "user":
            content = payload.get("content") or []
            typed_input = [part for part in content if isinstance(part, dict)
                           and part.get("type") in ("input_text", "input_image")]
            if typed_input:
                prompt = " ".join(part.get("text", "") for part in typed_input)
                tools.clear()
        if event not in ("function_call", "custom_tool_call", "tool_search_call"):
            continue
        name = payload.get("name") or ""
        namespace = payload.get("namespace")
        if namespace and namespace.startswith("mcp__") and not name.startswith("mcp__"):
            name = f"{namespace.rstrip('_')}__{name.lstrip('_')}"
        if event == "tool_search_call":
            name = "tool_search"
        if event == "custom_tool_call":
            args = {"command": payload.get("input") or ""}
        else:
            try:
                args = json.loads(payload.get("arguments") or "{}")
            except (ValueError, TypeError):
                args = {}
        if name in ("shell", "shell_command", "local_shell", "exec_command", "Bash"):
            name = "Bash"
            if isinstance(args, dict):
                command = args.get("command") or args.get("cmd") or ""
                args["command"] = " ".join(command) if isinstance(command, list) else command
        tools.append({"type": "tool_use", "name": name, "input": args if isinstance(args, dict) else {}})
    return (prompt, tools) if found else None

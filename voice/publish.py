#!/usr/bin/env python3
"""Publish voice/agents/netagym-voice.jsonc to AssemblyAI.

Standard library only. Follows AssemblyAI's starter convention: the .jsonc
file is the request body for POST /agents; ${VARS} come from the
environment (.env loaded if present). With AGENT_ID set, PUTs over the
existing agent instead of creating a new one.

    ASSEMBLYAI_API_KEY=... ASK_TOOL_URL=https://app.onrender.com/tools/ask \
        python voice/publish.py
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from pathlib import Path

AGENT_FILE = Path(__file__).parent / "agents" / "netagym-voice.jsonc"
ENV_FILE = Path(__file__).parent.parent / ".env"


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def parse_jsonc(text: str) -> dict:
    text = re.sub(r"//[^\n]*", "", text)
    return json.loads(text)


def interpolate(obj):
    if isinstance(obj, str):
        return re.sub(r"\$\{([A-Z0-9_]+)\}",
                      lambda m: os.environ.get(m.group(1), m.group(0)), obj)
    if isinstance(obj, list):
        return [interpolate(x) for x in obj]
    if isinstance(obj, dict):
        return {k: interpolate(v) for k, v in obj.items()}
    return obj


def main() -> None:
    load_env(ENV_FILE)
    key = os.environ.get("ASSEMBLYAI_API_KEY", "").strip()
    if not key:
        sys.exit("ASSEMBLYAI_API_KEY not set - get one at "
                 "https://www.assemblyai.com/dashboard/api-keys")
    agent = interpolate(parse_jsonc(AGENT_FILE.read_text()))
    unresolved = re.findall(r"\$\{[A-Z0-9_]+\}", json.dumps(agent))
    if unresolved:
        sys.exit(f"Unresolved variables in agent file: {', '.join(unresolved)}")
    base = os.environ.get("AGENTS_API_BASE",
                          "https://agents.assemblyai.com/v1").rstrip("/")
    agent_id = os.environ.get("AGENT_ID", "").strip()
    url = f"{base}/agents/{agent_id}" if agent_id else f"{base}/agents"
    req = urllib.request.Request(
        url,
        data=json.dumps(agent).encode(),
        method="PUT" if agent_id else "POST",
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req) as res:
            body = json.loads(res.read().decode() or "{}")
    except urllib.error.HTTPError as err:
        sys.exit(f"publish failed ({err.code}): {err.read().decode()}")
    verb = "Updated" if agent_id else "Created"
    new_id = body.get("id") or body.get("agent_id") or agent_id
    print(f'{verb} agent "{agent.get("name")}" -> id: {new_id}')
    print("Save it: AGENT_ID=" + str(new_id) + " in .env")


if __name__ == "__main__":
    main()

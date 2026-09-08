"""AssemblyAI Voice Agent API transport - thin, optional, key-gated.

Mirrors the GLM client pattern: without ASSEMBLYAI_API_KEY the voice path
is disabled and everything else (text Q&A, tools, tests) runs offline.
Data answers never depend on this client.

API reference: https://www.assemblyai.com/docs/voice-agents/voice-agent-api
Base URL: https://agents.assemblyai.com/v1 (regional override via
AGENTS_API_BASE, same variable name AssemblyAI's own starter uses).

Configuration (environment variables):
    ASSEMBLYAI_API_KEY   AssemblyAI API key (dashboard/api-keys).
    AGENTS_API_BASE      Override the agents API base URL.
    ASSEMBLYAI_TIMEOUT   Request timeout in seconds (default 30).
"""

from __future__ import annotations

import os

import aiohttp

_DEFAULT_BASE = "https://agents.assemblyai.com/v1"


def aai_config() -> tuple[str, str] | None:
    """Return (api_key, base_url) if AssemblyAI is configured, else None."""
    key = os.environ.get("ASSEMBLYAI_API_KEY", "").strip()
    if not key:
        return None
    base = os.environ.get("AGENTS_API_BASE", "").strip() or _DEFAULT_BASE
    return key, base.rstrip("/")


def _headers(key: str) -> dict:
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _timeout() -> aiohttp.ClientTimeout:
    secs = float(os.environ.get("ASSEMBLYAI_TIMEOUT", "30"))
    return aiohttp.ClientTimeout(total=secs)


async def publish_agent(agent: dict, agent_id: str | None = None) -> dict:
    """Create an agent (POST /agents) or replace one (PUT /agents/<id>)."""
    cfg = aai_config()
    if cfg is None:
        raise RuntimeError("ASSEMBLYAI_API_KEY is not set")
    key, base = cfg
    async with aiohttp.ClientSession(timeout=_timeout()) as s:
        if agent_id:
            req = s.put(f"{base}/agents/{agent_id}", json=agent,
                        headers=_headers(key))
        else:
            req = s.post(f"{base}/agents", json=agent, headers=_headers(key))
        async with req as r:
            body = await r.text()
            if r.status >= 400:
                raise RuntimeError(f"publish failed ({r.status}): {body}")
            return await r.json() if body else {}


async def get_agent(agent_id: str) -> dict:
    cfg = aai_config()
    if cfg is None:
        raise RuntimeError("ASSEMBLYAI_API_KEY is not set")
    key, base = cfg
    async with aiohttp.ClientSession(timeout=_timeout()) as s:
        async with s.get(f"{base}/agents/{agent_id}",
                         headers=_headers(key)) as r:
            r.raise_for_status()
            return await r.json()


async def mint_session_token(expires_in_seconds: int = 60) -> dict:
    """Short-lived token so the browser opens the voice session directly;
    the API key never leaves the server."""
    cfg = aai_config()
    if cfg is None:
        raise RuntimeError("ASSEMBLYAI_API_KEY is not set")
    key, base = cfg
    async with aiohttp.ClientSession(timeout=_timeout()) as s:
        async with s.get(
            f"{base}/token?product=voice_agent&expires_in_seconds={expires_in_seconds}",
            headers=_headers(key),
        ) as r:
            r.raise_for_status()
            return await r.json()

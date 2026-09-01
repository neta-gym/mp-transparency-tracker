"""GLM-5.3 Flash (Z.ai) client for LLM-assisted classification.

Used by the MPLADS pipeline to classify eSAKSHI work descriptions into
sectors when the rule-based keyword classifier falls through to "other".
This is a real, optional call: if no API key is configured, the pipeline
runs exactly as before (keyword-only classification).

Configuration (environment variables):
    GLM_API_KEY        Z.ai API key (https://z.ai). Preferred provider.
    OPENROUTER_API_KEY OpenRouter API key (https://openrouter.ai). Used if
                       GLM_API_KEY is not set.
    GLM_BASE_URL       Override the chat-completions base URL.
    GLM_MODEL          Override the model slug.
    GLM_TIMEOUT        Request timeout in seconds (default 30).

Defaults:
    Z.ai:       base https://api.z.ai/api/paas/v4, model glm-5.3-flash
    OpenRouter: base https://openrouter.ai/api/v1, model z-ai/glm-5.3-flash
"""

from __future__ import annotations

import json
import os
import re

import aiohttp

from ..config import settings
from .logger import get_logger

log = get_logger(__name__)

_ZAI_BASE_URL = "https://api.z.ai/api/paas/v4"
_ZAI_MODEL = "glm-5.3-flash"
_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
_OPENROUTER_MODEL = "z-ai/glm-5.3-flash"

VALID_SECTORS = (
    "education",
    "health",
    "infrastructure",
    "water",
    "community",
    "sports",
    "other",
)


def glm_config() -> tuple[str, str, str] | None:
    """Return (api_key, base_url, model) if a GLM-5.3 provider is configured.

    Prefers a direct Z.ai key, then OpenRouter. Returns None when neither
    is set — callers must treat that as "LLM assist disabled".
    """
    # Settings cover both real environment variables and .env entries.
    base_override = (settings.glm_base_url or os.environ.get("GLM_BASE_URL", "")).strip()
    model_override = (settings.glm_model or os.environ.get("GLM_MODEL", "")).strip()

    zai_key = (settings.glm_api_key or os.environ.get("GLM_API_KEY", "")).strip()
    if zai_key:
        return (
            zai_key,
            base_override or _ZAI_BASE_URL,
            model_override or _ZAI_MODEL,
        )

    openrouter_key = (settings.openrouter_api_key or os.environ.get("OPENROUTER_API_KEY", "")).strip()
    if openrouter_key:
        return (
            openrouter_key,
            base_override or _OPENROUTER_BASE_URL,
            model_override or _OPENROUTER_MODEL,
        )

    return None


def _build_prompt(descriptions: list[str]) -> list[dict[str, str]]:
    sector_list = ", ".join(VALID_SECTORS)
    numbered = "\n".join(f"{i + 1}. {d}" for i, d in enumerate(descriptions))
    return [
        {
            "role": "system",
            "content": (
                "You classify Indian MPLADS (Members of Parliament Local Area "
                "Development Scheme) work descriptions into exactly one sector "
                f"each. Valid sectors: {sector_list}. "
                "Reply with a JSON array of sector strings only, in the same "
                "order as the inputs, one per input. No prose, no markdown."
            ),
        },
        {
            "role": "user",
            "content": f"Classify these {len(descriptions)} work descriptions:\n{numbered}",
        },
    ]


def _parse_sectors(content: str, expected: int) -> list[str] | None:
    """Parse a JSON array of sectors out of the model reply."""
    text = content.strip()
    # Strip markdown fences if the model added them despite instructions
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", text, flags=re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    if not isinstance(data, list) or len(data) != expected:
        return None
    sectors: list[str] = []
    for item in data:
        sector = str(item).strip().lower()
        sectors.append(sector if sector in VALID_SECTORS else "other")
    return sectors


async def _post_chat_completion(
    base_url: str, api_key: str, payload: dict, timeout: float
) -> dict | None:
    """POST to an OpenAI-compatible chat-completions endpoint.

    Returns the parsed JSON body, or None on any failure (HTTP error,
    network error, timeout, bad JSON). Never raises — LLM assist must
    never break the data pipeline.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    client_timeout = aiohttp.ClientTimeout(total=timeout)
    try:
        async with aiohttp.ClientSession(timeout=client_timeout) as session, session.post(
            f"{base_url.rstrip('/')}/chat/completions",
            json=payload,
            headers=headers,
        ) as resp:
            if resp.status != 200:
                body = await resp.text()
                log.warning(f"GLM-5.3 Flash returned HTTP {resp.status}: {body[:200]}")
                return None
            data = await resp.json()
            return data if isinstance(data, dict) else None
    except Exception as exc:  # network errors, timeouts, bad JSON
        log.warning(f"GLM-5.3 Flash call failed, keeping keyword sectors: {exc}")
        return None


async def classify_work_sectors(descriptions: list[str]) -> list[str] | None:
    """Classify MPLADS work descriptions into sectors via GLM-5.3 Flash.

    Returns a list of sector strings (same length/order as input), or None
    if no provider is configured or the call fails. Never raises — LLM
    assist must never break the data pipeline.
    """
    if not descriptions:
        return []

    config = glm_config()
    if config is None:
        log.info("GLM assist skipped: set GLM_API_KEY or OPENROUTER_API_KEY to enable")
        return None

    api_key, base_url, model = config
    timeout = float(os.environ.get("GLM_TIMEOUT", "") or settings.glm_timeout or 30)
    payload = {
        "model": model,
        "messages": _build_prompt(descriptions),
        "temperature": 0,
    }

    data = await _post_chat_completion(base_url, api_key, payload, timeout)
    if data is None:
        return None

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        log.warning("GLM-5.3 Flash response missing choices[0].message.content")
        return None

    sectors = _parse_sectors(content, len(descriptions))
    if sectors is None:
        log.warning("GLM-5.3 Flash returned unparseable sectors, keeping keyword sectors")
    return sectors

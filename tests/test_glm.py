"""Tests for the GLM-5.3 Flash sector-classification assist.

The HTTP transport (`_post_chat_completion`) is monkeypatched in these
tests so the suite stays hermetic and independent of aiohttp internals.
"""

from __future__ import annotations

import pytest

from tracker.models.schemas import MPLADSWork
from tracker.tools.esakshi import _apply_glm_sector_fallback
from tracker.utils import glm


@pytest.fixture(autouse=True)
def _clear_glm_env(monkeypatch):
    for var in ("GLM_API_KEY", "OPENROUTER_API_KEY", "GLM_BASE_URL", "GLM_MODEL", "GLM_TIMEOUT"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(glm.settings, "glm_api_key", "", raising=False)
    monkeypatch.setattr(glm.settings, "openrouter_api_key", "", raising=False)
    monkeypatch.setattr(glm.settings, "glm_base_url", "", raising=False)
    monkeypatch.setattr(glm.settings, "glm_model", "", raising=False)


def _fake_glm_response(content: str) -> dict:
    return {"choices": [{"message": {"content": content}}]}


def test_no_key_returns_none():
    assert glm.glm_config() is None


def test_zai_key_preferred_over_openrouter(monkeypatch):
    monkeypatch.setattr(glm.settings, "glm_api_key", "zai-key", raising=False)
    monkeypatch.setattr(glm.settings, "openrouter_api_key", "or-key", raising=False)
    key, base, model = glm.glm_config()
    assert key == "zai-key"
    assert base == "https://api.z.ai/api/paas/v4"
    assert model == "glm-5.3-flash"


def test_openrouter_fallback(monkeypatch):
    monkeypatch.setattr(glm.settings, "openrouter_api_key", "or-key", raising=False)
    key, base, model = glm.glm_config()
    assert key == "or-key"
    assert base == "https://openrouter.ai/api/v1"
    assert model == "z-ai/glm-5.3-flash"


def test_parse_sectors_plain_json():
    out = glm._parse_sectors('["health", "education"]', 2)
    assert out == ["health", "education"]


def test_parse_sectors_fenced_and_invalid():
    out = glm._parse_sectors('```json\n["Health", "banana"]\n```', 2)
    assert out == ["health", "other"]


def test_parse_sectors_wrong_length():
    assert glm._parse_sectors('["health"]', 2) is None


@pytest.mark.asyncio
async def test_classify_without_key_is_graceful():
    assert await glm.classify_work_sectors(["construction of school building"]) is None


@pytest.mark.asyncio
async def test_classify_with_mocked_zai(monkeypatch):
    monkeypatch.setattr(glm.settings, "glm_api_key", "zai-key", raising=False)
    calls = {}

    async def fake_post(base_url, api_key, payload, timeout):
        calls["base_url"] = base_url
        calls["api_key"] = api_key
        return _fake_glm_response('["health", "education"]')

    monkeypatch.setattr(glm, "_post_chat_completion", fake_post)
    out = await glm.classify_work_sectors(["new PHC building", "school classroom"])
    assert out == ["health", "education"]
    assert calls["base_url"] == "https://api.z.ai/api/paas/v4"
    assert calls["api_key"] == "zai-key"


@pytest.mark.asyncio
async def test_http_error_is_graceful(monkeypatch):
    monkeypatch.setattr(glm.settings, "glm_api_key", "zai-key", raising=False)

    async def failed_post(base_url, api_key, payload, timeout):
        return None

    monkeypatch.setattr(glm, "_post_chat_completion", failed_post)
    assert await glm.classify_work_sectors(["x"]) is None


@pytest.mark.asyncio
async def test_fallback_reclassifies_only_other(monkeypatch):
    monkeypatch.setattr(glm.settings, "glm_api_key", "zai-key", raising=False)
    works = [
        MPLADSWork(description="road resurfacing", sector="infrastructure"),
        MPLADSWork(description="construction of primary health centre", sector="other"),
        MPLADSWork(description="anganwadi classroom repair", sector="other"),
    ]

    async def fake_post(base_url, api_key, payload, timeout):
        return _fake_glm_response('["health", "education"]')

    monkeypatch.setattr(glm, "_post_chat_completion", fake_post)
    updated = await _apply_glm_sector_fallback(works)
    assert updated == 2
    assert works[0].sector == "infrastructure"  # untouched
    assert works[1].sector == "health"
    assert works[2].sector == "education"


@pytest.mark.asyncio
async def test_fallback_no_key_keeps_sectors():
    works = [MPLADSWork(description="mystery work", sector="other")]
    assert await _apply_glm_sector_fallback(works) == 0
    assert works[0].sector == "other"

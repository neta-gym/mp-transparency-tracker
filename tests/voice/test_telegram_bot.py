"""Telegram update handler - pure, no network."""

from voice.telegram_bot import handle_update, verify_secret
from voice.watch import WatchStore

import pytest


@pytest.fixture()
def store(tmp_path):
    return WatchStore(tmp_path / "watches.json")


def _update(chat_id, text):
    return {"message": {"chat": {"id": chat_id}, "text": text}}


def test_start(store, index):
    out = handle_update(_update(1, "/start"), index, store)
    assert "watch" in out[0].text.lower()


def test_watch_flow(store, index):
    out = handle_update(_update(1, "/watch Asha Verma"), index, store)
    assert "Watching Asha Verma" in out[0].text
    assert store.watches("1") == ["asha-verma"]
    out = handle_update(_update(1, "/watches"), index, store)
    assert "Asha Verma" in out[0].text
    out = handle_update(_update(1, "/unwatch Asha Verma"), index, store)
    assert "Stopped watching" in out[0].text


def test_watch_unknown_mp(store, index):
    out = handle_update(_update(1, "/watch Zyx Qwerty"), index, store)
    assert "Could not find" in out[0].text


def test_free_text_question(store, index):
    out = handle_update(_update(1, "attendance of Asha Verma"), index, store)
    assert "88 percent" in out[0].text


def test_free_text_hindi(store, index):
    out = handle_update(_update(1, "Asha Verma ki haziri kaisi hai"), index, store)
    assert "haziri" in out[0].text


def test_empty_update(store, index):
    assert handle_update({"message": {"chat": {"id": 1}}}, index, store) == []
    assert handle_update({}, index, store) == []


def test_verify_secret():
    assert verify_secret({"x-telegram-bot-api-secret-token": "abc"}, "abc")
    assert not verify_secret({"x-telegram-bot-api-secret-token": "nope"}, "abc")
    assert not verify_secret({}, "abc")
    assert not verify_secret({"x-telegram-bot-api-secret-token": "abc"}, "")

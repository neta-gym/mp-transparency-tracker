"""Telegram bot for NetaGym Watch - alerts and Q&A over the MP records.

The handler (handle_update) is pure and fully testable offline: it takes a
Telegram update dict plus the data index and watch store, and returns the
messages to send. Network lives only in TelegramClient.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import aiohttp

from .answers import answer
from .answers import SITE
from .data_index import MPDataIndex
from .intents import parse
from .watch import WatchStore

BOT_NAME = "NetaGym Watch"

START_TEXT = (
    "Namaste! I am NetaGym Watch - the MP Transparency Tracker's alert bot.\n"
    "\n"
    "- /watch <MP or constituency> - get an alert when their public record changes\n"
    "- /unwatch <name> - stop an alert\n"
    "- /watches - what you are watching\n"
    "- /digest - your MP report card digest, on demand\n"
    "- Or just ask: \"attendance of my MP\", \"criminal cases against <name>\" - "
    "Hindi or English.\n"
    "\n"
    f"Every answer comes from public records, with the source: {SITE}"
)


@dataclass
class Outgoing:
    chat_id: str
    text: str


class TelegramClient:
    """Minimal Bot API client (aiohttp, no extra deps)."""

    def __init__(self, token: str | None = None):
        self.token = (token or os.environ.get("TELEGRAM_BOT_TOKEN", "")).strip()

    @property
    def configured(self) -> bool:
        return bool(self.token)

    def _url(self, method: str) -> str:
        return f"https://api.telegram.org/bot{self.token}/{method}"

    async def send_message(self, chat_id: str, text: str) -> bool:
        if not self.configured:
            return False
        async with aiohttp.ClientSession() as sess:
            async with sess.post(self._url("sendMessage"), json={
                "chat_id": chat_id, "text": text,
                "disable_web_page_preview": True,
            }) as resp:
                return resp.status == 200

    async def set_webhook(self, url: str, secret: str) -> dict:
        async with aiohttp.ClientSession() as sess:
            async with sess.post(self._url("setWebhook"), json={
                "url": url, "secret_token": secret, "drop_pending_updates": True,
            }) as resp:
                return await resp.json()


def _resolve(index: MPDataIndex, raw: str):
    return index.find(raw.strip()) if raw.strip() else None


def handle_update(update: dict, index: MPDataIndex, store: WatchStore) -> list[Outgoing]:
    """Turn one Telegram update into zero or more replies. No network here."""
    msg = update.get("message") or update.get("edited_message") or {}
    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    text = (msg.get("text") or "").strip()
    if chat_id is None or not text:
        return []
    chat_id = str(chat_id)

    if text.startswith("/start") or text.startswith("/help"):
        return [Outgoing(chat_id, START_TEXT)]

    if text.startswith("/watch") and not text.startswith("/watches"):
        rec = _resolve(index, text[len("/watch"):])
        if rec is None:
            return [Outgoing(chat_id, "Could not find that MP - try the full name or the constituency.")]
        new = store.watch(chat_id, rec.slug)
        state = "Watching" if new else "Already watching"
        return [Outgoing(chat_id,
                         f"{state} {rec.name} ({rec.constituency}, {rec.state_label}). "
                         f"You will get an alert here when their public record changes. "
                         f"Full record: {SITE}/mp/{rec.slug}/")]

    if text.startswith("/unwatch"):
        rec = _resolve(index, text[len("/unwatch"):])
        if rec is None or not store.unwatch(chat_id, rec.slug):
            return [Outgoing(chat_id, "That MP was not on your watch list.")]
        return [Outgoing(chat_id, f"Stopped watching {rec.name}.")]

    if text.startswith("/watches"):
        slugs = store.watches(chat_id)
        if not slugs:
            return [Outgoing(chat_id, "You are not watching any MPs yet. Try /watch <name>.")]
        by_slug = {r.slug: r for r in index.records}
        names = [by_slug[s].name for s in slugs if s in by_slug]
        return [Outgoing(chat_id, "You are watching: " + ", ".join(names))]

    if text.startswith("/digest"):
        from .digest import compose_digest
        return [Outgoing(chat_id, compose_digest(chat_id, index, store))]

    # Anything else is a question for the same deterministic brain as voice.
    result = answer(parse(text), index)
    return [Outgoing(chat_id, result["text"])]


def verify_secret(update_headers: dict, expected: str) -> bool:
    """Telegram signs webhook calls with the secret we set at registration."""
    if not expected:
        return False
    got = update_headers.get("x-telegram-bot-api-secret-token", "")
    return got == expected

"""Strands tools over the MP Transparency Tracker dataset.

Each tool is a thin wrapper over voice.answers - the deterministic answer
engine. Unknown MPs return an honest "no record" string instead of a guess;
that is what makes the refusal evals pass.
"""

from __future__ import annotations

from pathlib import Path

from strands import tool

from voice import answers
from voice.data_index import MPDataIndex
from voice.digest import compose_digest
from voice.watch import WatchStore

_INDEX: MPDataIndex | None = None
_STORE: WatchStore | None = None


def get_index() -> MPDataIndex:
    global _INDEX
    if _INDEX is None:
        _INDEX = MPDataIndex()
    return _INDEX


def get_store() -> WatchStore:
    global _STORE
    if _STORE is None:
        _STORE = WatchStore(path=Path.home() / ".netagym_watches.json")
    return _STORE


def _resolve(mp_name: str, language: str):
    rec = get_index().find(mp_name)
    return rec if rec else None


@tool
def mp_attendance(mp_name: str, language: str = "en") -> str:
    """Get an MP's Parliament attendance record.

    Args:
        mp_name: Name of the MP, e.g. "Rahul Gandhi" or "Mamata Thakur".
        language: "en" for English or "hi" for Hindi - match the user's language.
    """
    rec = _resolve(mp_name, language)
    if rec is None:
        return answers.unknown_mp(mp_name, language)
    return answers.answer_attendance(rec, language)


@tool
def mp_funds(mp_name: str, language: str = "en") -> str:
    """Get an MP's MPLADS local-area development fund usage (received vs spent).

    Args:
        mp_name: Name of the MP.
        language: "en" for English or "hi" for Hindi - match the user's language.
    """
    rec = _resolve(mp_name, language)
    if rec is None:
        return answers.unknown_mp(mp_name, language)
    return answers.answer_funds(rec, language)


@tool
def mp_criminal_cases(mp_name: str, language: str = "en") -> str:
    """Get the criminal cases declared in an MP's sworn election affidavit.

    Args:
        mp_name: Name of the MP.
        language: "en" for English or "hi" for Hindi - match the user's language.
    """
    rec = _resolve(mp_name, language)
    if rec is None:
        return answers.unknown_mp(mp_name, language)
    return answers.answer_criminal(rec, language)


@tool
def mp_assets(mp_name: str, language: str = "en") -> str:
    """Get an MP's declared net worth / assets from their election affidavit.

    Args:
        mp_name: Name of the MP.
        language: "en" for English or "hi" for Hindi - match the user's language.
    """
    rec = _resolve(mp_name, language)
    if rec is None:
        return answers.unknown_mp(mp_name, language)
    return answers.answer_assets(rec, language)


@tool
def mp_questions(mp_name: str, language: str = "en") -> str:
    """Get how many questions an MP has asked in Parliament.

    Args:
        mp_name: Name of the MP.
        language: "en" for English or "hi" for Hindi - match the user's language.
    """
    rec = _resolve(mp_name, language)
    if rec is None:
        return answers.unknown_mp(mp_name, language)
    return answers.answer_questions(rec, language)


@tool
def mp_report_card(mp_name: str, language: str = "en") -> str:
    """Get an MP's overall transparency report card: score, national rank, headline stats.

    Args:
        mp_name: Name of the MP.
        language: "en" for English or "hi" for Hindi - match the user's language.
    """
    rec = _resolve(mp_name, language)
    if rec is None:
        return answers.unknown_mp(mp_name, language)
    return answers.answer_score(rec, language)


@tool
def compare_mps(mp_name_a: str, mp_name_b: str, language: str = "en") -> str:
    """Compare two MPs side by side on attendance, funds, cases, and score.

    Args:
        mp_name_a: First MP's name.
        mp_name_b: Second MP's name.
        language: "en" for English or "hi" for Hindi - match the user's language.
    """
    index = get_index()
    a, b = index.find(mp_name_a), index.find(mp_name_b)
    if a and b:
        return answers.answer_compare(a, b, language)
    missing = mp_name_a if not a else mp_name_b
    return answers.unknown_mp(missing, language)


@tool
def state_leaderboard(state: str, best: bool = True, language: str = "en") -> str:
    """Get the top (or bottom) MPs of an Indian state by transparency score.

    Args:
        state: State name, e.g. "Bihar" or "West Bengal".
        best: True for the highest-scoring MPs, False for the lowest.
        language: "en" for English or "hi" for Hindi - match the user's language.
    """
    return answers.answer_state(get_index(), state, best, language)


@tool
def watch_mp(mp_name: str, contact: str) -> str:
    """Watch an MP: the contact gets a digest and an alert when the public record changes.

    Args:
        mp_name: Name of the MP to watch.
        contact: An email address or Telegram chat id to deliver alerts to.
    """
    index = get_index()
    rec = index.find(mp_name)
    if rec is None:
        return answers.unknown_mp(mp_name, "en")
    get_store().watch(contact, rec.slug)
    return (f"Watching {rec.name} ({rec.constituency}, {rec.state_label}). "
            f"Digests and change alerts go to {contact}. "
            f"Audit page: {answers.SITE}/mp/{rec.slug}/")


@tool
def mp_digest(contact: str) -> str:
    """Get the current digest for a watcher: headline numbers for every MP they watch.

    Args:
        contact: The email address or Telegram chat id the watches are registered under.
    """
    return compose_digest(contact, get_index(), get_store())


ALL_TOOLS = [
    mp_attendance, mp_funds, mp_criminal_cases, mp_assets, mp_questions,
    mp_report_card, compare_mps, state_leaderboard, watch_mp, mp_digest,
]

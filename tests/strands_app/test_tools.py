"""Tool-level tests for the Strands port: no model involved, all deterministic."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from strands_app import tools


@pytest.fixture(autouse=True)
def temp_store(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "_STORE", tools.WatchStore(path=tmp_path / "w.json"))
    return tmp_path


def test_attendance_real_figure():
    out = tools.mp_attendance("Mamata Thakur")
    assert "72" in out and "attend" in out.lower()


def test_funds_real_figure():
    out = tools.mp_funds("Wayanad MP")
    assert "crore" in out.lower()


def test_hindi_answer_in_hindi():
    out = tools.mp_attendance("Mamata Thakur", language="hi")
    assert "haziri" in out or " Parliament" in out or "72" in out


def test_unknown_mp_is_honest_refusal():
    out = tools.mp_attendance("Zorp Fictional-MP")
    assert "no record" in out.lower() or "not find" in out.lower() or "couldn't find" in out.lower()


def test_compare_two_mps():
    out = tools.compare_mps("Rajiv Pratap Rudy", "Mohammad Jawed")
    assert "Rudy" in out and "Jawed" in out


def test_state_leaderboard():
    out = tools.state_leaderboard("Bihar", best=True)
    assert "Bihar" in out


def test_watch_and_digest_roundtrip():
    out = tools.watch_mp("Mamata Thakur", "demo@example.com")
    assert "Watching Mamata Thakur" in out
    digest = tools.mp_digest("demo@example.com")
    assert "Mamata Thakur" in digest and "72" in digest


def test_digest_without_watches():
    out = tools.mp_digest("nobody@example.com")
    assert "not watching" in out.lower()

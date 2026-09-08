"""Deterministic, source-backed answer builders (English + Hindi).

Every number spoken comes straight from the tracker's public-record JSON.
Templates are intentionally plain-language per the Neta Gym voice: no
jargon ("MPLADS" becomes "MP area development fund"), second-person,
receipts attached (source + confidence when weak).
"""

from __future__ import annotations

from .data_index import MPDataIndex, MPRecord
from .intents import ParsedQuery

SITE = "neta-gym.github.io/mp-transparency-tracker"


def crore(rupees: float) -> tuple[float, str]:
    if rupees >= 1e7:
        return rupees / 1e7, "crore"
    if rupees >= 1e5:
        return rupees / 1e5, "lakh"
    return rupees, "rupees"


def _money_en(rupees: float) -> str:
    v, unit = crore(rupees)
    return f"{v:.1f} {unit} rupees" if unit != "rupees" else f"{v:.0f} rupees"


def _money_hi(rupees: float) -> str:
    v, unit = crore(rupees)
    u = {"crore": "crore", "lakh": "lakh"}.get(unit, "rupees")
    return f"{v:.1f} {u} rupaye" if u != "rupees" else f"{v:.0f} rupaye"


def _money(rupees: float, lang: str) -> str:
    return _money_hi(rupees) if lang == "hi" else _money_en(rupees)


def _house_en(rec: MPRecord) -> str:
    return {"lok_sabha": "Lok Sabha", "rajya_sabha": "Rajya Sabha"}.get(rec.house, "")


def _intro_en(rec: MPRecord) -> str:
    return f"{rec.name}, {rec.party} MP from {rec.constituency}, {rec.state_label}"


def _intro_hi(rec: MPRecord) -> str:
    return f"{rec.name}, {rec.constituency}, {rec.state_label} se {rec.party} ke sansad"


def _missing(topic: str, rec: MPRecord, lang: str) -> str:
    if lang == "hi":
        return (f"{rec.name} ke liye is data ka reliable source abhi available "
                f"nahin hai. Poora report card {SITE} par dekhein.")
    return (f"We don't have a reliable public source for {rec.name}'s {topic} "
            f"yet. The full report card is at {SITE}.")


def answer_attendance(rec: MPRecord, lang: str) -> str:
    if rec.attendance_pct is None:
        return _missing("attendance", rec, lang)
    q = f", with {rec.questions_asked} questions asked" if rec.questions_asked else ""
    qh = f", aur {rec.questions_asked} sawaal pooche" if rec.questions_asked else ""
    if lang == "hi":
        return (f"{_intro_hi(rec)}. Parliament mein inki haziri "
                f"{rec.attendance_pct:.0f} percent hai{qh}. "
                f"Poora data {SITE} par hai.")
    return (f"{_intro_en(rec)} has attended {rec.attendance_pct:.0f} percent "
            f"of Parliament sittings{q}. Full record at {SITE}.")


def answer_funds(rec: MPRecord, lang: str) -> str:
    if rec.mplads_entitled_cr is None or rec.mplads_expended_cr is None:
        return _missing("fund usage", rec, lang)
    entitled = rec.mplads_entitled_cr * 1e7
    expended = rec.mplads_expended_cr * 1e7
    util = f"{rec.mplads_utilization:.0f} percent" if rec.mplads_utilization is not None else None
    if lang == "hi":
        u = f", yaani {util} istemaal hua" if util else ""
        return (f"{_intro_hi(rec)}. MP area development fund mein inhe "
                f"{_money(entitled, 'hi')} mile, jisme se {_money(expended, 'hi')} "
                f"kharch hue{u}. Source data {SITE} par hai.")
    u = f" - {util} of what they got" if util else ""
    return (f"{_intro_en(rec)} received {_money(entitled, 'en')} from the MP area "
            f"development fund and spent {_money(expended, 'en')}{u}. "
            f"Source data at {SITE}.")


def answer_criminal(rec: MPRecord, lang: str) -> str:
    if rec.criminal_cases is None:
        return _missing("criminal record", rec, lang)
    serious = rec.serious_criminal_cases or 0
    if lang == "hi":
        if rec.criminal_cases == 0:
            return (f"{_intro_hi(rec)}. Election affidavit ke mutabik in par "
                    f"koi criminal case darj nahin hai. Affidavit data {SITE} par hai.")
        return (f"{_intro_hi(rec)}. Election affidavit ke mutabik in par "
                f"{rec.criminal_cases} criminal case darj hain, jinme {serious} "
                f"serious hain. Details {SITE} par hain.")
    if rec.criminal_cases == 0:
        return (f"{_intro_en(rec)} has no criminal cases declared in their "
                f"election affidavit. The affidavit data is at {SITE}.")
    return (f"{_intro_en(rec)} has {rec.criminal_cases} criminal cases declared "
            f"in their election affidavit, {serious} of them serious. "
            f"Case details at {SITE}.")


def answer_assets(rec: MPRecord, lang: str) -> str:
    if rec.total_assets is None:
        return _missing("assets", rec, lang)
    if lang == "hi":
        return (f"{_intro_hi(rec)}. Election affidavit mein inhone "
                f"{_money(rec.total_assets, 'hi')} ki total sampatti declare ki hai. "
                f"Breakup {SITE} par hai.")
    return (f"{_intro_en(rec)} declared total assets of "
            f"{_money(rec.total_assets, 'en')} in their election affidavit. "
            f"The breakup is at {SITE}.")


def answer_questions(rec: MPRecord, lang: str) -> str:
    if rec.questions_asked is None:
        return _missing("Parliament questions", rec, lang)
    d = rec.debates_participated or 0
    if lang == "hi":
        return (f"{_intro_hi(rec)}. Inhone Parliament mein {rec.questions_asked} "
                f"sawaal pooche aur {d} bahason mein hissa liya. "
                f"Source data {SITE} par hai.")
    return (f"{_intro_en(rec)} has asked {rec.questions_asked} questions in "
            f"Parliament and taken part in {d} debates. Source data at {SITE}.")


def answer_score(rec: MPRecord, lang: str) -> str:
    if rec.composite_score is None:
        return _missing("transparency score", rec, lang)
    rank = f" They currently rank number {rec.national_rank} out of 786 MPs." if rec.national_rank else ""
    rank_hi = f" 786 sansadon mein inki rank number {rec.national_rank} hai." if rec.national_rank else ""
    if lang == "hi":
        return (f"{_intro_hi(rec)}. Transparency score: {rec.composite_score:.1f} "
                f"out of 100.{rank_hi} Score ka poora breakup {SITE} par hai.")
    return (f"{_intro_en(rec)} scores {rec.composite_score:.1f} out of 100 on "
            f"transparency.{rank} The full score breakup is at {SITE}.")


def answer_compare(a: MPRecord, b: MPRecord, lang: str) -> str:
    if a.composite_score is None or b.composite_score is None:
        missing = a if a.composite_score is None else b
        return _missing("transparency score", missing, lang)
    winner, loser = (a, b) if a.composite_score >= b.composite_score else (b, a)
    gap = abs(a.composite_score - b.composite_score)
    att = ""
    if a.attendance_pct is not None and b.attendance_pct is not None:
        if lang == "hi":
            att = (f" Haziri: {a.name} {a.attendance_pct:.0f} percent, "
                   f"{b.name} {b.attendance_pct:.0f} percent.")
        else:
            att = (f" Attendance: {a.name} {a.attendance_pct:.0f} percent, "
                   f"{b.name} {b.attendance_pct:.0f} percent.")
    if lang == "hi":
        return (f"Transparency score mein {winner.name} aage hai: "
                f"{winner.composite_score:.1f} vs {loser.name} ke "
                f"{loser.composite_score:.1f} - {gap:.1f} points ka fark.{att} "
                f"Head-to-head comparison {SITE} par hai.")
    return (f"On transparency, {winner.name} leads {winner.composite_score:.1f} "
            f"to {loser.composite_score:.1f} - a {gap:.1f} point gap.{att} "
            f"The full head-to-head is at {SITE}.")


def answer_state(index: MPDataIndex, state: str, best: bool, lang: str) -> str:
    recs = index.state_leaders(state) if best else index.state_laggards(state)
    if not recs:
        if lang == "hi":
            return f"Maaf kijiye, {state} ka data abhi index mein nahin mila."
        return f"Sorry, I couldn't find data for {state} in the index."
    label = recs[0].state_label
    names = ", ".join(f"{r.name} ({r.composite_score:.1f})" for r in recs)
    word_en, word_hi = ("top-scoring", "sabse achhe") if best else ("lowest-scoring", "sabse kam score waale")
    if lang == "hi":
        return (f"{label} ke {word_hi} sansad: {names}. "
                f"Poori state leaderboard {SITE} par hai.")
    return (f"The {word_en} MPs in {label}: {names}. "
            f"The full state leaderboard is at {SITE}.")


def fallback(lang: str) -> str:
    if lang == "hi":
        return ("Maaf kijiye, sawaal samajh nahin aaya. Aap kisi bhi MP ka naam "
                "ya constituency bol kar pooch sakte hain - haziri, paisa, criminal "
                "cases, sampatti, ya transparency score. Jaise: Rahul Gandhi ki "
                "haziri kaisi hai?")
    return ("Sorry, I didn't catch that. Ask me about any MP by name or "
            "constituency - attendance, fund spending, criminal cases, assets, "
            "or their transparency score. For example: what is Rahul Gandhi's "
            "attendance?")


def unknown_mp(target: str, lang: str) -> str:
    if lang == "hi":
        return (f"Maaf kijiye, '{target}' naam ka MP record mein nahin mila. "
                f"Naam ya constituency phir se bolein, ya {SITE} par khojein.")
    return (f"Sorry, I couldn't find an MP matching '{target}'. "
            f"Try the name or constituency again, or search at {SITE}.")


_TOPICS = {
    "attendance": answer_attendance,
    "funds": answer_funds,
    "criminal": answer_criminal,
    "assets": answer_assets,
    "questions": answer_questions,
    "score": answer_score,
}


def answer(query: ParsedQuery, index: MPDataIndex) -> dict:
    """Dispatch a parsed query to a spoken answer. Returns text + metadata."""
    lang = query.language
    if query.intent == "compare" and len(query.targets) >= 2:
        a, b = index.find(query.targets[0]), index.find(query.targets[1])
        if a and b:
            return {"text": answer_compare(a, b, lang), "mps": [a.slug, b.slug]}
        missing = query.targets[0] if not a else query.targets[1]
        return {"text": unknown_mp(missing, lang), "mps": []}
    if query.intent in ("state_best", "state_worst") and query.state:
        return {"text": answer_state(index, query.state,
                                     query.intent == "state_best", lang), "mps": []}
    if query.intent in _TOPICS and query.targets:
        rec = index.find(query.targets[0])
        if rec:
            return {"text": _TOPICS[query.intent](rec, lang), "mps": [rec.slug]}
        return {"text": unknown_mp(query.targets[0], lang), "mps": []}
    # bare name with no topic -> the report card summary
    if query.intent == "unknown" and query.targets:
        rec = index.find(query.targets[0])
        if rec:
            return {"text": answer_score(rec, lang), "mps": [rec.slug]}
        return {"text": unknown_mp(query.targets[0], lang), "mps": []}
    return {"text": fallback(lang), "mps": []}

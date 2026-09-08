"""Rule-based intent parsing for voice questions about MPs.

No LLM dependency: the same invariant as the scoring pipeline. Spoken
queries are messy, so parsing is keyword-driven over normalized text with
Devanagari detection for Hindi. Anything unparsable falls back to a
"try rephrasing" answer that names what the agent can do.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")

_HINDI_HINTS = (
    "kitna", "kitni", "kitne", "kaisa", "kaisi", "kaun", "kya", "mere",
    "hamare", "sansaad", "sadsya", "paisa", "paise", "sampatti", "mukadma",
    "haziri", "batao", "bataiye", "dikhao",
)

_TOPIC_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("attendance", ("attendance", "attend", "present", "showed up", "show up",
                    "haziri", "upasthiti", "kitni baar aaye", "kitne din aaye",
                    "हाजिरी", "उपस्थिति")),
    ("funds", ("fund", "funds", "money", "mplads", "spent", "spend", "utili",
               "paisa", "paise", "kahaan gaya", "kahan gaya", "kharch",
               "पैसा", "पैसे", "फंड", "खर्च")),
    ("criminal", ("criminal", "case", "cases", "charges", "conviction", "fir",
                  "mukadma", "mukadme", "apraadh", "मुकदमा", "मुकदमे", "आपराधिक")),
    ("assets", ("asset", "assets", "wealth", "net worth", "networth", "rich",
                "sampatti", "daulat", "property", "संपत्ति", "दौलत")),
    ("questions", ("question", "questions", "debate", "debates", "spoke",
                   "sawaal", "sawal", "bahas", "सवाल", "प्रश्न", "बहस")),
    ("score", ("score", "rank", "ranking", "report card", "grade", "rated",
               "number", "rank kya", "score kya", "स्कोर", "रैंक")),
]

_STATE_WORDS = re.compile(
    r"\b(?:in|of|from|ke|ki|ka)\s+([a-z][a-z ]+?)(?:\?|$)", re.IGNORECASE
)


@dataclass
class ParsedQuery:
    intent: str  # attendance|funds|criminal|assets|questions|score|compare|state_best|state_worst|unknown
    language: str  # en | hi
    targets: list[str] = field(default_factory=list)  # raw MP/constituency name spans
    state: str | None = None
    raw: str = ""


def detect_language(text: str) -> str:
    if _DEVANAGARI.search(text):
        return "hi"
    low = f" {unicodedata.normalize('NFKC', text).lower()} "
    hits = sum(1 for h in _HINDI_HINTS if f" {h} " in low)
    return "hi" if hits >= 2 else "en"


def _strip_fillers(text: str) -> str:
    t = text.lower()
    for kw_group in (k for _, kws in _TOPIC_KEYWORDS for k in kws):
        t = t.replace(kw_group, " ")
    for w in ("what", "whats", "what's", "is", "the", "of", "mp", "mp's", "mps",
              "tell", "me", "about", "how", "many", "much", "does", "do", "did",
              "has", "have", "his", "her", "their", "a", "an", "kya", "hai",
              "ka", "ki", "ke", "ko", "mere", "hamare", "batao", "bataiye",
              "compare", "versus", "vs", "better", "against", "my", "in", "on",
              "vote", "votes", "voted", "voting",
              "kaisa", "kaisi", "kitna", "kitni", "kitne", "dikhao", "please"):
        t = re.sub(rf"\b{re.escape(w)}\b", " ", t)
    t = re.sub(r"(\w+)['\u2019]s\b", r"\1", t)  # possessives: "Rudy's" -> "Rudy"
    t = re.sub(r"\s+", " ", t).strip()
    return t.strip(" ?.!,")


def parse(text: str) -> ParsedQuery:
    raw = text.strip()
    low = unicodedata.normalize("NFKC", raw).lower()
    lang = detect_language(raw)

    intent = "unknown"
    for topic, kws in _TOPIC_KEYWORDS:
        if any(k in low for k in kws):
            intent = topic
            break

    # comparisons: "X vs Y", "X versus Y", "compare X and Y", "X ya Y"
    parts = re.split(r"\s+(?:vs\.?|versus|against|ya)\s+|,\s*(?:and|aur)\s+", low)
    parts = [p.strip() for p in parts if p.strip()]
    if len(parts) >= 2 and ("compare" in low or " vs" in low or " versus" in low
                            or " better" in low or " ya " in low):
        intent = "compare"
        targets = [_strip_fillers(p) for p in parts[:2]]
        return ParsedQuery(intent=intent, language=lang,
                           targets=[t for t in targets if t], raw=raw)

    if m := re.search(r"(?:best|top|sabse achha|sabse accha)\b.*", low):
        intent = "state_best"
    elif re.search(r"(?:worst|lowest|bottom|sabse bura|sabse kharaab)\b", low):
        intent = "state_worst"

    state = None
    if intent in ("state_best", "state_worst"):
        if sm := _STATE_WORDS.search(low):
            state = sm.group(1).strip()

    remainder = _strip_fillers(low) if intent != "unknown" else _strip_fillers(low)
    targets = [remainder] if remainder else []

    return ParsedQuery(intent=intent, language=lang, targets=targets,
                       state=state, raw=raw)

"""Rule-based Devanagari -> Latin transliteration for name matching.

Voice callers speaking Hindi get transcribed in Devanagari, but the MP
index stores Latin-script names and constituencies. This transliterator
converts a Devanagari span to an approximate Latin form so the existing
substring/fuzzy matching in data_index can resolve it. No LLM, no
dependency - same invariant as the rest of the pipeline.

Simplifications (fine for fuzzy name matching, not for display):
- inherent 'a' is emitted after bare consonants and one trailing 'a' per
  word is dropped (Hindi final-schwa deletion); medial schwa deletion is
  left to the fuzzy matcher
- anusvara/chandrabindu -> 'n', visarga -> 'h'
"""

from __future__ import annotations

import re
import unicodedata

DEVANAGARI_RE = re.compile(r"[ऀ-ॿ]")

_INDEPENDENT_VOWELS = {
    "अ": "a", "आ": "aa", "इ": "i", "ई": "i", "उ": "u", "ऊ": "u",
    "ऋ": "ri", "ॠ": "ri", "ऌ": "lri", "ए": "e", "ऐ": "ai", "ओ": "o",
    "औ": "au",
}

_MATRAS = {
    "ा": "aa", "ि": "i", "ी": "i", "ु": "u", "ू": "u", "ृ": "ri",
    "ॄ": "ri", "ॢ": "lri", "े": "e", "ै": "ai", "ो": "o", "ौ": "au",
}

_CONSONANTS = {
    "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "n",
    "च": "ch", "छ": "chh", "ज": "j", "झ": "jh", "ञ": "n",
    "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n",
    "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n",
    "प": "p", "फ": "ph", "ब": "b", "भ": "bh", "म": "m",
    "य": "y", "र": "r", "ल": "l", "व": "v",
    "श": "sh", "ष": "sh", "स": "s", "ह": "h", "ळ": "l",
    # nukta forms
    "क़": "q", "ख़": "kh", "ग़": "gh", "ज़": "z", "फ़": "f",
    "ड़": "r", "ढ़": "rh",
}

_HALANT = "्"
_ANUSVARA = {"ं", "ँ"}
_VISARGA = "ः"


def _transliterate_word(word: str) -> str:
    out: list[str] = []
    schwa_at = -1
    i = 0
    while i < len(word):
        ch = word[i]
        if ch in _CONSONANTS:
            out.append(_CONSONANTS[ch])
            nxt = word[i + 1] if i + 1 < len(word) else ""
            if nxt in _MATRAS:
                out.append(_MATRAS[nxt])
                i += 2
                continue
            if nxt == _HALANT:
                i += 2  # conjunct: no inherent vowel
                continue
            out.append("a")  # inherent schwa
            schwa_at = len(out) - 1
            i += 1
            continue
        if ch in _INDEPENDENT_VOWELS:
            out.append(_INDEPENDENT_VOWELS[ch])
        elif ch in _MATRAS:
            out.append(_MATRAS[ch])  # stray matra: keep the vowel
        elif ch in _ANUSVARA:
            out.append("n")
        elif ch == _VISARGA:
            out.append("h")
        else:
            out.append(ch)
        i += 1
    latin = "".join(out)
    # collapse doubled vowels (aa/ee/oo) - matching-friendly, not display-grade
    latin = re.sub(r"([aeiou])\1", r"\1", latin)
    # final-schwa deletion: drop a trailing 'a' only when it was the inherent
    # vowel of a bare final consonant (राहुल -> rahul), never a real matra
    # vowel (प्रियंका keeps its final a).
    if schwa_at == len(out) - 1 and latin.endswith("a") and len(latin) > 1:
        latin = latin[:-1]
    return latin


def to_latin(text: str) -> str:
    """Transliterate Devanagari spans in text to Latin; pass the rest through."""
    if not DEVANAGARI_RE.search(text):
        return text
    words = []
    for word in re.split(r"(\s+)", unicodedata.normalize("NFC", text)):
        words.append(_transliterate_word(word) if DEVANAGARI_RE.search(word) else word)
    return "".join(words)

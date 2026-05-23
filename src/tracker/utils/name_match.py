"""Shared name and state normalization utilities.

Consolidates duplicated matching logic from prs.py, mplads.py, mp_discovery.py.
"""

from __future__ import annotations

import re


# State alias map — maps variant spellings to canonical lowercase form
_STATE_ALIASES: dict[str, str] = {
    "nct of delhi": "delhi",
    "national capital territory of delhi": "delhi",
    "jammu & kashmir": "jammu and kashmir",
    "j&k": "jammu and kashmir",
    "j & k": "jammu and kashmir",
    "dadra & nagar haveli and daman & diu": "dadra and nagar haveli and daman and diu",
    "dadra and nagar haveli & daman and diu": "dadra and nagar haveli and daman and diu",
    "a & n islands": "andaman and nicobar islands",
    "andaman & nicobar islands": "andaman and nicobar islands",
    "andaman & nicobar": "andaman and nicobar islands",
    "up": "uttar pradesh",
    "mp": "madhya pradesh",
    "hp": "himachal pradesh",
    "ap": "andhra pradesh",
    "wb": "west bengal",
    "tn": "tamil nadu",
    "uk": "uttarakhand",
}

# Title prefixes to strip during name normalization
_TITLE_PREFIXES = re.compile(
    r"^(shri|smt|dr|mr|mrs|ms|prof|adv|capt|col|gen|justice|hon|sri|shrimati|kumari)\b\.?\s*",
    re.IGNORECASE,
)


def normalize_name(name: str) -> str:
    """Normalize a name for matching: lowercase, strip titles, remove punctuation."""
    n = name.strip().lower()
    # Strip title prefixes (may appear multiple times: "Dr. Shri X")
    for _ in range(3):
        n = _TITLE_PREFIXES.sub("", n).strip()
    # Remove punctuation except spaces
    n = re.sub(r"[^a-z\s]", "", n)
    # Collapse whitespace
    n = re.sub(r"\s+", " ", n).strip()
    return n


def normalize_state(state: str) -> str:
    """Normalize state name: lowercase, collapse whitespace, resolve aliases."""
    s = re.sub(r"\s+", " ", state.strip().lower())
    return _STATE_ALIASES.get(s, s)


def name_matches(a: str, b: str, min_confidence: float = 0.6) -> bool:
    """Check if two names match using token overlap.

    Args:
        a: First name
        b: Second name
        min_confidence: Minimum Jaccard-like overlap ratio (0.0-1.0).
            Default 0.6 means 60% of the smaller token set must overlap.

    Returns:
        True if the names are considered a match.
    """
    na = normalize_name(a)
    nb = normalize_name(b)

    if na == nb:
        return True

    a_tokens = set(na.split())
    b_tokens = set(nb.split())

    if not a_tokens or not b_tokens:
        return False

    overlap = a_tokens & b_tokens
    min_len = min(len(a_tokens), len(b_tokens))

    if min_len == 0:
        return False

    # Require at least 2 tokens to overlap, or all tokens if one name has only 1 token
    if min_len == 1:
        return len(overlap) >= 1 and overlap == a_tokens or overlap == b_tokens

    ratio = len(overlap) / min_len
    return ratio >= min_confidence

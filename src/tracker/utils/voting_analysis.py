"""Voting alignment and party loyalty analysis for MPs."""

from __future__ import annotations

from collections import defaultdict

from ..models.schemas import VoteRecord, VotingAnalysis
from ..utils.logger import get_logger

log = get_logger(__name__)

# Bills of national importance — missing these is flagged
KEY_BILL_KEYWORDS = {
    "budget", "finance bill", "appropriation", "constitution amendment",
    "no confidence", "confidence motion", "president's address",
}


def analyze_voting(
    records: list[VoteRecord],
    party: str,
    all_party_votes: dict[str, list[VoteRecord]] | None = None,
) -> VotingAnalysis:
    """Analyze an MP's voting patterns and party alignment.

    Args:
        records: This MP's vote records.
        party: The MP's party name.
        all_party_votes: Optional dict of {party: [all_records]} for cross-referencing
                         party majority position. If not provided, party alignment
                         cannot be computed.
    """
    if not records:
        return VotingAnalysis(confidence=0.0)

    total = len(records)
    absences = sum(1 for r in records if r.vote == "absent")
    abstentions = sum(1 for r in records if r.vote == "abstain")
    actual_votes = [r for r in records if r.vote in ("yes", "no")]

    # Identify key bills missed
    key_missed = []
    for r in records:
        bill_lower = r.bill_name.lower()
        if r.vote == "absent" and any(kw in bill_lower for kw in KEY_BILL_KEYWORDS):
            key_missed.append(r.bill_name)

    # Party alignment analysis
    votes_with = 0
    votes_against = 0
    cross_party = []

    if all_party_votes and party in all_party_votes:
        # Build party majority position per bill
        party_majority = _compute_party_majority(all_party_votes[party])

        for r in actual_votes:
            majority_vote = party_majority.get(r.bill_name)
            if majority_vote is None:
                continue
            if r.vote == majority_vote:
                votes_with += 1
            else:
                votes_against += 1
                cross_party.append(r)
    else:
        # Without party-wide data, we can't determine alignment
        votes_with = len(actual_votes)

    loyalty_pct = None
    if votes_with + votes_against > 0:
        loyalty_pct = round((votes_with / (votes_with + votes_against)) * 100, 1)

    return VotingAnalysis(
        total_votes=total,
        votes_with_party=votes_with,
        votes_against_party=votes_against,
        abstentions=abstentions,
        absences=absences,
        party_loyalty_pct=loyalty_pct,
        cross_party_votes=cross_party[:10],
        key_bills_missed=key_missed[:10],
        confidence=0.7 if total >= 5 else 0.4 if total > 0 else 0.0,
    )


def _compute_party_majority(party_records: list[VoteRecord]) -> dict[str, str]:
    """Given all party members' votes, compute the majority position per bill."""
    bill_votes: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in party_records:
        if r.vote in ("yes", "no"):
            bill_votes[r.bill_name][r.vote] += 1

    majority: dict[str, str] = {}
    for bill, votes in bill_votes.items():
        if votes.get("yes", 0) >= votes.get("no", 0):
            majority[bill] = "yes"
        else:
            majority[bill] = "no"
    return majority

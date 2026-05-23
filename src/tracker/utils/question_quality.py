"""Question quality scoring — differentiates high-impact from routine questions."""

from __future__ import annotations

from ..models.schemas import QuestionQuality
from ..utils.logger import get_logger

log = get_logger(__name__)


def assess_question_quality(
    questions_asked: int,
    starred: int = 0,
    unstarred: int = 0,
    short_notice: int = 0,
    topics: list[str] | None = None,
    constituency_name: str = "",
    notable_questions: list[str] | None = None,
) -> QuestionQuality:
    """Score question quality based on type, diversity, and constituency relevance.

    Starred questions (oral answers in Parliament) are higher-impact than unstarred.
    Short notice questions indicate urgency awareness.
    Topic diversity and constituency relevance show breadth and local focus.
    """
    topics = topics or []
    notable_questions = notable_questions or []

    # If breakdown not available, assume all are unstarred
    if starred == 0 and unstarred == 0 and questions_asked > 0:
        unstarred = questions_asked

    unique_topics = len(set(t.lower().strip() for t in topics)) if topics else 0

    # Count questions mentioning the MP's constituency
    constituency_relevant = 0
    if constituency_name and notable_questions:
        const_lower = constituency_name.lower()
        for q in notable_questions:
            if const_lower in q.lower():
                constituency_relevant += 1

    # Quality score: weighted composite
    # Starred questions worth 2x, short notice worth 3x, unstarred worth 1x
    raw_score = starred * 2.0 + short_notice * 3.0 + unstarred * 1.0

    # Topic diversity bonus: up to +15 for 10+ unique topics
    diversity_bonus = min(15.0, unique_topics * 1.5)

    # Constituency relevance bonus: up to +10
    relevance_bonus = min(10.0, constituency_relevant * 2.5)

    # Normalize to 0-100 scale
    # Benchmark: 50 questions with good mix ≈ 100
    quality_score = min(100.0, (raw_score / 50.0) * 75.0 + diversity_bonus + relevance_bonus)

    confidence = 0.6 if questions_asked > 0 else 0.0

    return QuestionQuality(
        total_questions=questions_asked,
        starred_questions=starred,
        unstarred_questions=unstarred,
        short_notice_questions=short_notice,
        unique_topics=unique_topics,
        constituency_relevant=constituency_relevant,
        follow_up_rate=0.0,  # requires detailed Q&A data to compute
        quality_score=round(quality_score, 1),
        confidence=confidence,
    )

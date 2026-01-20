"""Scoring logic for OOLONG benchmark answers."""

import re
from typing import Callable

from .models import AnswerType


def normalize_answer(answer: str) -> str:
    """Normalize answer for comparison."""
    # Strip whitespace and lowercase
    normalized = answer.strip().lower()
    # Remove common formatting artifacts
    normalized = re.sub(r"[*_`]", "", normalized)
    # Remove leading/trailing quotes
    normalized = normalized.strip("\"'")
    return normalized


def is_numeric(answer: str) -> bool:
    """Check if answer is numeric."""
    try:
        float(answer.replace(",", ""))
        return True
    except ValueError:
        return False


def parse_numeric(answer: str) -> float | None:
    """Parse numeric answer, handling commas."""
    try:
        return float(answer.replace(",", "").strip())
    except ValueError:
        return None


def numeric_score(expected: float, actual: float) -> float:
    """Score numeric answer using 0.75^|error| formula."""
    error = abs(expected - actual)
    return 0.75**error


def label_score(expected: str, actual: str) -> float:
    """Score label answer using exact match (case-insensitive)."""
    return 1.0 if normalize_answer(expected) == normalize_answer(actual) else 0.0


def comparison_score(expected: str, actual: str) -> float:
    """Score comparison answers (more/less/same)."""
    expected_norm = normalize_answer(expected)
    actual_norm = normalize_answer(actual)

    # Map common variations
    more_variants = {"more", "more common", "greater", "higher", "larger"}
    less_variants = {"less", "less common", "smaller", "lower", "fewer"}
    same_variants = {"same", "equal", "same frequency", "tied"}

    def categorize(text: str) -> str | None:
        if any(v in text for v in more_variants):
            return "more"
        if any(v in text for v in less_variants):
            return "less"
        if any(v in text for v in same_variants):
            return "same"
        return None

    expected_cat = categorize(expected_norm)
    actual_cat = categorize(actual_norm)

    if expected_cat is None or actual_cat is None:
        # Fall back to exact match if we can't categorize
        return label_score(expected, actual)

    return 1.0 if expected_cat == actual_cat else 0.0


def map_answer_type_str(answer_type_str: str) -> AnswerType:
    """Map string to AnswerType enum."""
    mapping = {
        "NUMERIC": AnswerType.NUMERIC,
        "NUMERIC_ONE_CLASS": AnswerType.NUMERIC,
        "LABEL": AnswerType.LABEL,
        "COMPARISON": AnswerType.COMPARISON,
        "DATE": AnswerType.DATE,
    }
    return mapping.get(answer_type_str.upper(), AnswerType.LABEL)


def detect_answer_type(expected: str) -> AnswerType:
    """Detect answer type from expected answer."""
    normalized = normalize_answer(expected)

    # Check for comparison words
    comparison_words = {"more", "less", "same", "common", "greater", "fewer"}
    if any(word in normalized for word in comparison_words):
        return AnswerType.COMPARISON

    # Check for numeric
    if is_numeric(expected):
        return AnswerType.NUMERIC

    # Default to label
    return AnswerType.LABEL


def get_scorer(answer_type: AnswerType) -> Callable[[str, str], float]:
    """Get scoring function for answer type."""
    scorers: dict[AnswerType, Callable[[str, str], float]] = {
        AnswerType.NUMERIC: _score_numeric,
        AnswerType.LABEL: label_score,
        AnswerType.COMPARISON: comparison_score,
        AnswerType.DATE: label_score,  # Exact match for dates
    }
    return scorers.get(answer_type, label_score)


def _score_numeric(expected: str, actual: str) -> float:
    """Wrapper for numeric scoring with parsing."""
    exp_val = parse_numeric(expected)
    act_val = parse_numeric(actual)

    if exp_val is None or act_val is None:
        # Fall back to exact match if parsing fails
        return label_score(expected, actual)

    return numeric_score(exp_val, act_val)


def score_answer(expected: str, actual: str, answer_type: AnswerType | None = None) -> float:
    """Score an answer against expected.

    Args:
        expected: The expected/gold answer
        actual: The actual/predicted answer
        answer_type: Type of answer (auto-detected if not provided)

    Returns:
        Score between 0.0 and 1.0
    """
    if not actual or not actual.strip():
        return 0.0

    if answer_type is None:
        answer_type = detect_answer_type(expected)

    scorer = get_scorer(answer_type)
    return scorer(expected, actual)

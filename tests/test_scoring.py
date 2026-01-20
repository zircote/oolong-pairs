"""Tests for scoring logic."""

from oolong_pairs.models import AnswerType
from oolong_pairs.scoring import (
    comparison_score,
    detect_answer_type,
    label_score,
    map_answer_type_str,
    normalize_answer,
    numeric_score,
    parse_numeric,
    score_answer,
)


class TestNormalizeAnswer:
    """Tests for answer normalization."""

    def test_strips_whitespace(self):
        assert normalize_answer("  hello  ") == "hello"

    def test_lowercases(self):
        assert normalize_answer("HELLO") == "hello"

    def test_removes_markdown(self):
        assert normalize_answer("**bold**") == "bold"
        assert normalize_answer("_italic_") == "italic"
        assert normalize_answer("`code`") == "code"

    def test_removes_quotes(self):
        assert normalize_answer('"quoted"') == "quoted"
        assert normalize_answer("'quoted'") == "quoted"


class TestParseNumeric:
    """Tests for numeric parsing."""

    def test_parses_integer(self):
        assert parse_numeric("42") == 42.0

    def test_parses_float(self):
        assert parse_numeric("3.14") == 3.14

    def test_handles_commas(self):
        assert parse_numeric("1,234") == 1234.0
        assert parse_numeric("1,234,567") == 1234567.0

    def test_returns_none_for_non_numeric(self):
        assert parse_numeric("hello") is None
        assert parse_numeric("") is None


class TestNumericScore:
    """Tests for numeric scoring using 0.75^|error| formula."""

    def test_exact_match(self):
        assert numeric_score(10.0, 10.0) == 1.0

    def test_off_by_one(self):
        assert numeric_score(10.0, 11.0) == 0.75
        assert numeric_score(10.0, 9.0) == 0.75

    def test_off_by_two(self):
        expected = 0.75**2
        assert numeric_score(10.0, 12.0) == expected
        assert numeric_score(10.0, 8.0) == expected

    def test_larger_errors(self):
        # Error of 5 -> 0.75^5 ≈ 0.2373
        result = numeric_score(10.0, 15.0)
        assert abs(result - 0.75**5) < 0.0001


class TestLabelScore:
    """Tests for label scoring using exact match."""

    def test_exact_match(self):
        assert label_score("cat", "cat") == 1.0

    def test_case_insensitive(self):
        assert label_score("Cat", "cat") == 1.0
        assert label_score("CAT", "cat") == 1.0

    def test_with_whitespace(self):
        assert label_score(" cat ", "cat") == 1.0

    def test_no_match(self):
        assert label_score("cat", "dog") == 0.0


class TestComparisonScore:
    """Tests for comparison answer scoring."""

    def test_more_variants(self):
        assert comparison_score("more", "more") == 1.0
        assert comparison_score("more", "more common") == 1.0
        assert comparison_score("greater", "more") == 1.0
        assert comparison_score("higher", "more") == 1.0

    def test_less_variants(self):
        assert comparison_score("less", "less") == 1.0
        assert comparison_score("less", "fewer") == 1.0
        assert comparison_score("smaller", "less") == 1.0
        assert comparison_score("lower", "less") == 1.0

    def test_same_variants(self):
        assert comparison_score("same", "same") == 1.0
        assert comparison_score("equal", "same") == 1.0
        assert comparison_score("tied", "same") == 1.0

    def test_mismatch(self):
        assert comparison_score("more", "less") == 0.0
        assert comparison_score("same", "more") == 0.0


class TestDetectAnswerType:
    """Tests for automatic answer type detection."""

    def test_detects_numeric(self):
        assert detect_answer_type("42") == AnswerType.NUMERIC
        assert detect_answer_type("3.14") == AnswerType.NUMERIC
        assert detect_answer_type("1,234") == AnswerType.NUMERIC

    def test_detects_comparison(self):
        assert detect_answer_type("more common") == AnswerType.COMPARISON
        assert detect_answer_type("less") == AnswerType.COMPARISON
        assert detect_answer_type("same") == AnswerType.COMPARISON

    def test_defaults_to_label(self):
        assert detect_answer_type("cat") == AnswerType.LABEL
        assert detect_answer_type("hello world") == AnswerType.LABEL


class TestMapAnswerTypeStr:
    """Tests for string to AnswerType mapping."""

    def test_maps_numeric(self):
        assert map_answer_type_str("NUMERIC") == AnswerType.NUMERIC
        assert map_answer_type_str("numeric") == AnswerType.NUMERIC
        assert map_answer_type_str("NUMERIC_ONE_CLASS") == AnswerType.NUMERIC

    def test_maps_label(self):
        assert map_answer_type_str("LABEL") == AnswerType.LABEL

    def test_maps_comparison(self):
        assert map_answer_type_str("COMPARISON") == AnswerType.COMPARISON

    def test_maps_date(self):
        assert map_answer_type_str("DATE") == AnswerType.DATE

    def test_unknown_defaults_to_label(self):
        assert map_answer_type_str("UNKNOWN") == AnswerType.LABEL


class TestScoreAnswer:
    """Integration tests for the main scoring function."""

    def test_numeric_exact(self):
        score = score_answer("42", "42", AnswerType.NUMERIC)
        assert score == 1.0

    def test_numeric_close(self):
        score = score_answer("10", "11", AnswerType.NUMERIC)
        assert score == 0.75

    def test_label_match(self):
        score = score_answer("cat", "Cat", AnswerType.LABEL)
        assert score == 1.0

    def test_label_mismatch(self):
        score = score_answer("cat", "dog", AnswerType.LABEL)
        assert score == 0.0

    def test_comparison_match(self):
        score = score_answer("more", "more common", AnswerType.COMPARISON)
        assert score == 1.0

    def test_auto_detects_type(self):
        # Should auto-detect numeric
        score = score_answer("42", "42")
        assert score == 1.0

        # Should auto-detect comparison
        score = score_answer("more common", "more")
        assert score == 1.0

    def test_empty_answer_returns_zero(self):
        assert score_answer("42", "", AnswerType.NUMERIC) == 0.0
        assert score_answer("cat", "  ", AnswerType.LABEL) == 0.0

"""Unit tests for fuzzy search functionality."""

import pytest

from app.services.fuzzy_search import (
    levenshtein_distance,
    similarity_ratio,
    tokenize,
    token_set_similarity,
    prefix_match_score,
    calculate_match_score,
    fuzzy_search,
    fuzzy_search_legislators,
)


class TestLevenshteinDistance:
    """Tests for Levenshtein distance calculation."""

    def test_identical_strings(self):
        """Identical strings should have distance 0."""
        assert levenshtein_distance("hello", "hello") == 0
        assert levenshtein_distance("", "") == 0

    def test_empty_string(self):
        """Distance to empty string is length of other string."""
        assert levenshtein_distance("hello", "") == 5
        assert levenshtein_distance("", "world") == 5

    def test_single_insertion(self):
        """Single character insertion should have distance 1."""
        assert levenshtein_distance("helo", "hello") == 1

    def test_single_deletion(self):
        """Single character deletion should have distance 1."""
        assert levenshtein_distance("hello", "helo") == 1

    def test_single_substitution(self):
        """Single character substitution should have distance 1."""
        assert levenshtein_distance("hello", "hallo") == 1

    def test_multiple_edits(self):
        """Multiple edits should accumulate."""
        assert levenshtein_distance("kitten", "sitting") == 3

    def test_common_typos(self):
        """Common typos should have small distances."""
        assert levenshtein_distance("Pelosi", "Polosi") == 1
        assert levenshtein_distance("McConnell", "McConnel") == 1
        assert levenshtein_distance("Schumer", "Shumer") == 1


class TestSimilarityRatio:
    """Tests for similarity ratio calculation."""

    def test_identical_strings(self):
        """Identical strings should have ratio 1.0."""
        assert similarity_ratio("hello", "hello") == 1.0

    def test_completely_different(self):
        """Very different strings should have low ratio."""
        ratio = similarity_ratio("abc", "xyz")
        assert ratio < 0.5

    def test_similar_strings(self):
        """Similar strings should have high ratio."""
        ratio = similarity_ratio("Pelosi", "Polosi")
        assert ratio > 0.8

    def test_case_insensitive(self):
        """Comparison should be case-insensitive."""
        assert similarity_ratio("PELOSI", "pelosi") == 1.0

    def test_empty_strings(self):
        """Empty strings should return 1.0."""
        assert similarity_ratio("", "") == 1.0

    def test_one_empty(self):
        """One empty string should return 0.0."""
        assert similarity_ratio("hello", "") == 0.0
        assert similarity_ratio("", "world") == 0.0


class TestTokenize:
    """Tests for tokenization."""

    def test_simple_tokenize(self):
        """Should split on whitespace."""
        assert tokenize("Nancy Pelosi") == ["nancy", "pelosi"]

    def test_removes_punctuation(self):
        """Should remove punctuation."""
        assert tokenize("Pelosi, Nancy") == ["pelosi", "nancy"]

    def test_lowercase(self):
        """Should convert to lowercase."""
        assert tokenize("JOHN DOE") == ["john", "doe"]

    def test_empty_string(self):
        """Empty string should return empty list."""
        assert tokenize("") == []

    def test_multiple_spaces(self):
        """Should handle multiple spaces."""
        assert tokenize("Nancy   Pelosi") == ["nancy", "pelosi"]


class TestTokenSetSimilarity:
    """Tests for token set similarity."""

    def test_identical_tokens(self):
        """Identical token sets should have ratio 1.0."""
        assert token_set_similarity("Nancy Pelosi", "Nancy Pelosi") == 1.0

    def test_reordered_tokens(self):
        """Reordered tokens should still match well."""
        score = token_set_similarity("Nancy Pelosi", "Pelosi, Nancy")
        assert score >= 0.9

    def test_partial_match(self):
        """Partial token match should have reasonable score."""
        score = token_set_similarity("Pelosi", "Nancy Pelosi")
        assert score >= 0.8

    def test_fuzzy_token_match(self):
        """Fuzzy token matching should work."""
        score = token_set_similarity("Polosi", "Pelosi")
        assert score > 0.5


class TestPrefixMatchScore:
    """Tests for prefix matching."""

    def test_exact_prefix(self):
        """Exact prefix should score high."""
        score = prefix_match_score("Pelo", "Pelosi")
        assert score > 0.5

    def test_full_match(self):
        """Full match should score highest."""
        score = prefix_match_score("Pelosi", "Pelosi")
        assert score == 1.0

    def test_no_prefix_match(self):
        """No prefix match should return 0."""
        score = prefix_match_score("xyz", "Pelosi")
        assert score == 0.0

    def test_token_prefix(self):
        """Should match prefix of any token."""
        score = prefix_match_score("Nan", "Pelosi, Nancy")
        assert score > 0.0


class TestCalculateMatchScore:
    """Tests for overall match score calculation."""

    def test_exact_match(self):
        """Exact substring match should score highest."""
        score = calculate_match_score("Pelosi", "Nancy Pelosi")
        assert score >= 0.9

    def test_typo_tolerance(self):
        """Common typos should still match."""
        score = calculate_match_score("Polosi", "Nancy Pelosi")
        assert score > 0.4

    def test_partial_name(self):
        """Partial name should match."""
        score = calculate_match_score("Nancy", "Nancy Pelosi")
        assert score >= 0.9

    def test_state_match(self):
        """State code should match."""
        score = calculate_match_score("CA", "Nancy Pelosi", state="CA")
        assert score >= 0.8

    def test_no_match(self):
        """Completely unrelated should score low."""
        score = calculate_match_score("xyz123", "Nancy Pelosi")
        assert score < 0.3

    def test_case_insensitive(self):
        """Matching should be case-insensitive."""
        score1 = calculate_match_score("PELOSI", "Nancy Pelosi")
        score2 = calculate_match_score("pelosi", "Nancy Pelosi")
        assert score1 == score2


class TestFuzzySearch:
    """Tests for the fuzzy_search function."""

    @pytest.fixture
    def sample_items(self):
        """Sample items for testing."""
        return [
            {"name": "Nancy Pelosi", "state": "CA"},
            {"name": "Mitch McConnell", "state": "KY"},
            {"name": "Chuck Schumer", "state": "NY"},
            {"name": "Kevin McCarthy", "state": "CA"},
            {"name": "Hakeem Jeffries", "state": "NY"},
        ]

    def test_exact_match_first(self, sample_items):
        """Exact matches should be ranked first."""
        results = fuzzy_search(
            "Pelosi",
            sample_items,
            key_func=lambda x: x["name"],
            threshold=0.3,
        )
        assert len(results) > 0
        assert results[0][0]["name"] == "Nancy Pelosi"

    def test_fuzzy_match_typo(self, sample_items):
        """Should find matches despite typos."""
        results = fuzzy_search(
            "Polosi",
            sample_items,
            key_func=lambda x: x["name"],
            threshold=0.3,
        )
        assert len(results) > 0
        assert any("Pelosi" in item["name"] for item, _ in results)

    def test_respects_threshold(self, sample_items):
        """Should filter by threshold."""
        results = fuzzy_search(
            "xyz",
            sample_items,
            key_func=lambda x: x["name"],
            threshold=0.5,
        )
        assert len(results) == 0

    def test_respects_limit(self, sample_items):
        """Should respect result limit."""
        results = fuzzy_search(
            "a",  # Matches multiple names
            sample_items,
            key_func=lambda x: x["name"],
            threshold=0.1,
            limit=2,
        )
        assert len(results) <= 2

    def test_sorted_by_score(self, sample_items):
        """Results should be sorted by score descending."""
        results = fuzzy_search(
            "Mc",
            sample_items,
            key_func=lambda x: x["name"],
            threshold=0.1,
        )
        if len(results) > 1:
            scores = [score for _, score in results]
            assert scores == sorted(scores, reverse=True)

    def test_empty_query(self, sample_items):
        """Empty query should return empty list."""
        results = fuzzy_search(
            "",
            sample_items,
            key_func=lambda x: x["name"],
        )
        assert results == []

    def test_empty_items(self):
        """Empty items list should return empty."""
        results = fuzzy_search(
            "test",
            [],
            key_func=lambda x: x["name"],
        )
        assert results == []


class TestFuzzySearchLegislators:
    """Tests for legislator-specific fuzzy search."""

    @pytest.fixture
    def legislators(self):
        """Sample legislator data in Congress API format."""
        return [
            {"name": "Pelosi, Nancy", "state": "CA", "bioguideId": "P000197"},
            {"name": "McConnell, Mitch", "state": "KY", "bioguideId": "M000355"},
            {"name": "Schumer, Charles E.", "state": "NY", "bioguideId": "S000148"},
            {"name": "McCarthy, Kevin", "state": "CA", "bioguideId": "M001165"},
            {"name": "Jeffries, Hakeem", "state": "NY", "bioguideId": "J000294"},
        ]

    def test_search_by_last_name(self, legislators):
        """Should find legislator by last name."""
        results = fuzzy_search_legislators("Pelosi", legislators)
        assert len(results) > 0
        assert "Pelosi" in results[0][0]["name"]

    def test_search_by_first_name(self, legislators):
        """Should find legislator by first name."""
        results = fuzzy_search_legislators("Nancy", legislators)
        assert len(results) > 0
        assert "Nancy" in results[0][0]["name"]

    def test_search_with_typo(self, legislators):
        """Should find legislator despite typo."""
        results = fuzzy_search_legislators("Shumer", legislators)
        assert len(results) > 0
        assert "Schumer" in results[0][0]["name"]

    def test_search_by_state(self, legislators):
        """Should match state code."""
        results = fuzzy_search_legislators("CA", legislators)
        assert len(results) > 0
        assert all(r[0]["state"] == "CA" for r in results[:2])

    def test_partial_name(self, legislators):
        """Should find with partial name."""
        results = fuzzy_search_legislators("McC", legislators)
        assert len(results) > 0
        # Should match both McConnell and McCarthy
        names = [r[0]["name"] for r in results]
        assert any("McConnell" in n for n in names) or any("McCarthy" in n for n in names)

    def test_handles_directOrderName(self):
        """Should handle directOrderName format."""
        legislators = [
            {"directOrderName": "Nancy Pelosi", "state": "CA"},
            {"directOrderName": "Mitch McConnell", "state": "KY"},
        ]
        results = fuzzy_search_legislators("Pelosi", legislators)
        assert len(results) > 0


class TestRealWorldScenarios:
    """Tests for real-world search scenarios."""

    @pytest.fixture
    def legislators(self):
        """More realistic legislator data."""
        return [
            {"name": "Pelosi, Nancy", "state": "CA"},
            {"name": "Peters, Gary C.", "state": "MI"},
            {"name": "Peterson, John E.", "state": "PA"},
            {"name": "Pence, Mike", "state": "IN"},
        ]

    def test_user_types_pelo(self, legislators):
        """User typing 'pelo' should find Pelosi first."""
        results = fuzzy_search_legislators("pelo", legislators)
        assert results[0][0]["name"] == "Pelosi, Nancy"

    def test_user_misspells_pelosi(self, legislators):
        """User misspelling 'Pelosy' should still find Pelosi."""
        results = fuzzy_search_legislators("Pelosy", legislators)
        assert len(results) > 0
        assert results[0][0]["name"] == "Pelosi, Nancy"

    def test_user_searches_peter(self, legislators):
        """User searching 'peter' should find Peters and Peterson."""
        results = fuzzy_search_legislators("peter", legislators)
        assert len(results) >= 2
        names = [r[0]["name"] for r in results]
        assert any("Peters" in n for n in names)
        assert any("Peterson" in n for n in names)

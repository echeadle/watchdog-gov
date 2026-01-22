"""Fuzzy search utilities for matching legislator names.

Implements fuzzy matching with:
- Levenshtein distance for typo tolerance
- Token-based matching for partial name matches
- Score-based ranking for relevance
"""

import re
from dataclasses import dataclass
from typing import Callable, TypeVar

T = TypeVar("T")


def levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate the Levenshtein (edit) distance between two strings.

    Returns the minimum number of single-character edits (insertions,
    deletions, or substitutions) required to change s1 into s2.
    """
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            # Cost is 0 if characters match, 1 otherwise
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def similarity_ratio(s1: str, s2: str) -> float:
    """Calculate similarity ratio between two strings (0.0 to 1.0).

    Uses Levenshtein distance normalized by the length of the longer string.
    """
    if not s1 and not s2:
        return 1.0
    if not s1 or not s2:
        return 0.0

    s1_lower = s1.lower()
    s2_lower = s2.lower()

    max_len = max(len(s1_lower), len(s2_lower))
    distance = levenshtein_distance(s1_lower, s2_lower)

    return 1.0 - (distance / max_len)


def tokenize(text: str) -> list[str]:
    """Split text into lowercase tokens, removing punctuation."""
    # Remove punctuation and split on whitespace
    cleaned = re.sub(r"[^\w\s]", " ", text.lower())
    return [t for t in cleaned.split() if t]


def token_set_similarity(s1: str, s2: str) -> float:
    """Calculate similarity based on matching tokens.

    Good for matching names where word order may vary or
    middle names may be present/absent.
    """
    tokens1 = set(tokenize(s1))
    tokens2 = set(tokenize(s2))

    if not tokens1 or not tokens2:
        return 0.0

    # Find matching tokens (exact or fuzzy)
    matched = 0
    for t1 in tokens1:
        for t2 in tokens2:
            if t1 == t2:
                matched += 1
                break
            elif len(t1) > 2 and len(t2) > 2 and similarity_ratio(t1, t2) >= 0.8:
                matched += 0.8  # Partial credit for fuzzy token match
                break

    # Normalize by the smaller set size (allows partial name matches)
    min_tokens = min(len(tokens1), len(tokens2))
    return matched / min_tokens if min_tokens > 0 else 0.0


def prefix_match_score(query: str, text: str) -> float:
    """Score based on prefix matching (good for autocomplete).

    Returns 1.0 if query is exact prefix, scaled down for longer texts.
    """
    query_lower = query.lower()
    text_lower = text.lower()

    if text_lower.startswith(query_lower):
        # Exact prefix match - score based on how much of the text is covered
        return len(query_lower) / len(text_lower)

    # Check if query matches start of any token
    tokens = tokenize(text)
    for token in tokens:
        if token.startswith(query_lower):
            return 0.8 * (len(query_lower) / len(token))

    return 0.0


@dataclass
class FuzzyMatch:
    """Result of a fuzzy match with relevance score."""

    item: object
    score: float
    matched_field: str


def calculate_match_score(query: str, name: str, state: str = "") -> float:
    """Calculate overall match score for a legislator.

    Combines multiple matching strategies:
    1. Exact substring match (highest priority)
    2. Prefix match (good for autocomplete)
    3. Token set similarity (handles word order, partial names)
    4. Full string similarity (handles typos)
    """
    query_lower = query.lower()
    name_lower = name.lower()

    # Exact substring match - highest score
    if query_lower in name_lower:
        # Bonus for matching at word boundaries
        if name_lower.startswith(query_lower) or f" {query_lower}" in name_lower:
            return 1.0
        return 0.95

    # State match
    if state and query_lower == state.lower():
        return 0.9

    # Prefix match
    prefix_score = prefix_match_score(query, name)
    if prefix_score > 0.5:
        return 0.85 + (prefix_score * 0.1)

    # Token similarity (handles "Nancy Pelosi" vs "Pelosi, Nancy")
    token_score = token_set_similarity(query, name)
    if token_score >= 0.8:
        return 0.7 + (token_score * 0.15)

    # Full string similarity (handles typos like "Polosi" -> "Pelosi")
    string_score = similarity_ratio(query, name)
    if string_score >= 0.6:
        return 0.5 + (string_score * 0.3)

    # Check individual tokens for partial matches
    query_tokens = tokenize(query)
    name_tokens = tokenize(name)

    for qt in query_tokens:
        if len(qt) >= 3:  # Only check tokens with 3+ chars
            for nt in name_tokens:
                if similarity_ratio(qt, nt) >= 0.75:
                    return 0.4 + (similarity_ratio(qt, nt) * 0.2)

    return 0.0


def fuzzy_search(
    query: str,
    items: list[T],
    key_func: Callable[[T], str],
    state_func: Callable[[T], str] | None = None,
    threshold: float = 0.3,
    limit: int = 20,
) -> list[tuple[T, float]]:
    """Perform fuzzy search on a list of items.

    Args:
        query: Search query string
        items: List of items to search
        key_func: Function to extract searchable text from item
        state_func: Optional function to extract state from item
        threshold: Minimum score to include in results (0.0-1.0)
        limit: Maximum number of results to return

    Returns:
        List of (item, score) tuples sorted by score descending
    """
    if not query or not items:
        return []

    results = []
    for item in items:
        name = key_func(item)
        state = state_func(item) if state_func else ""
        score = calculate_match_score(query, name, state)

        if score >= threshold:
            results.append((item, score))

    # Sort by score descending, then by name length (prefer shorter/more specific)
    results.sort(key=lambda x: (-x[1], len(key_func(x[0]))))

    return results[:limit]


def fuzzy_search_legislators(
    query: str,
    legislators: list[dict],
    threshold: float = 0.3,
    limit: int = 20,
) -> list[tuple[dict, float]]:
    """Fuzzy search specifically for legislator dictionaries.

    Handles the common Congress.gov API response format with
    "name" and "state" fields.
    """
    return fuzzy_search(
        query=query,
        items=legislators,
        key_func=lambda m: m.get("name", "") or m.get("directOrderName", ""),
        state_func=lambda m: m.get("state", ""),
        threshold=threshold,
        limit=limit,
    )

"""
Pattern Matcher for Learning System

Provides sophisticated pattern matching for learning corrections:
- Token-based similarity (Jaccard similarity)
- Context-aware matching (fact type, surrounding text)
- Confidence scoring for matches
- Fuzzy matching for minor variations

Used by FeedbackManager to determine when to apply learning corrections.
"""

import re
import logging
from typing import List, Dict, Optional, Set, Tuple
from difflib import SequenceMatcher

from ..core.data_models import HybridClinicalFact, LearningFeedback

logger = logging.getLogger(__name__)


class PatternMatcher:
    """
    Sophisticated pattern matching for learning corrections

    Matching Strategies:
    1. Exact match (100% confidence)
    2. Token overlap (Jaccard similarity)
    3. Fuzzy string matching (Levenshtein-like)
    4. Context-aware (surrounding text, fact type)

    Performance: <1ms per match check
    """

    def __init__(self):
        """Initialize pattern matcher"""
        self.min_token_overlap = 0.70  # 70% minimum overlap
        self.min_fuzzy_score = 0.80  # 80% minimum fuzzy match
        logger.info("Pattern matcher initialized")

    # ========================================================================
    # SIMILARITY MATCHING
    # ========================================================================

    def find_matching_patterns(
        self,
        fact: HybridClinicalFact,
        patterns: List[LearningFeedback],
        min_confidence: float = 0.70
    ) -> List[Tuple[LearningFeedback, float]]:
        """
        Find all patterns that match a fact with confidence scores

        Args:
            fact: Fact to match against
            patterns: List of learning patterns to check
            min_confidence: Minimum match confidence (0.0-1.0)

        Returns:
            List of (pattern, confidence) tuples sorted by confidence (descending)
        """
        matches = []

        for pattern in patterns:
            confidence = self.calculate_match_confidence(fact, pattern)

            if confidence >= min_confidence:
                matches.append((pattern, confidence))

        # Sort by confidence (highest first)
        matches = sorted(matches, key=lambda x: x[1], reverse=True)

        return matches

    def calculate_match_confidence(
        self,
        fact: HybridClinicalFact,
        pattern: LearningFeedback
    ) -> float:
        """
        Calculate match confidence between fact and pattern

        Scoring:
        - Exact match: 1.0
        - Type mismatch: 0.0
        - Token overlap: 0.0-0.9
        - Fuzzy match: 0.0-0.85
        - Context match: +0.1 bonus

        Args:
            fact: Fact to match
            pattern: Learning pattern

        Returns:
            Confidence score (0.0-1.0)
        """
        # Type must match
        if fact.fact_type != pattern.context.get('fact_type'):
            return 0.0

        fact_text = fact.fact.lower()
        pattern_text = pattern.original_extraction.lower()

        # Check exact match
        if pattern_text in fact_text or fact_text in pattern_text:
            # Exact substring match
            return 1.0

        # Calculate token overlap (Jaccard similarity)
        token_score = self._calculate_token_similarity(fact_text, pattern_text)

        # Calculate fuzzy string similarity
        fuzzy_score = self._calculate_fuzzy_similarity(fact_text, pattern_text)

        # Take maximum of token and fuzzy scores
        base_score = max(token_score, fuzzy_score)

        # Context bonus (if surrounding context matches)
        context_bonus = 0.0
        if self._check_context_match(fact, pattern):
            context_bonus = 0.1

        final_score = min(1.0, base_score + context_bonus)

        return final_score

    def _calculate_token_similarity(
        self,
        text1: str,
        text2: str
    ) -> float:
        """
        Calculate Jaccard similarity between token sets

        Jaccard = |A ∩ B| / |A ∪ B|

        Args:
            text1: First text
            text2: Second text

        Returns:
            Similarity score (0.0-1.0)
        """
        # Tokenize (remove punctuation, split on whitespace)
        tokens1 = set(re.findall(r'\w+', text1.lower()))
        tokens2 = set(re.findall(r'\w+', text2.lower()))

        if not tokens1 or not tokens2:
            return 0.0

        intersection = len(tokens1 & tokens2)
        union = len(tokens1 | tokens2)

        return intersection / union if union > 0 else 0.0

    def _calculate_fuzzy_similarity(
        self,
        text1: str,
        text2: str
    ) -> float:
        """
        Calculate fuzzy string similarity using SequenceMatcher

        This handles minor variations (typos, abbreviations)

        Args:
            text1: First text
            text2: Second text

        Returns:
            Similarity score (0.0-1.0)
        """
        return SequenceMatcher(None, text1, text2).ratio()

    def _check_context_match(
        self,
        fact: HybridClinicalFact,
        pattern: LearningFeedback
    ) -> bool:
        """
        Check if context matches (beyond just text similarity)

        Context includes:
        - Source document type
        - Surrounding text (if available)
        - Clinical specialty

        Args:
            fact: Fact to check
            pattern: Learning pattern

        Returns:
            True if context matches
        """
        # Check source document type similarity
        fact_source = fact.source_doc.lower()
        pattern_source = pattern.context.get('source_doc', '').lower()

        if pattern_source and pattern_source in fact_source:
            return True

        # Check surrounding context (if available)
        fact_context = fact.clinical_context.get('surrounding_context', '')
        pattern_context = pattern.context.get('surrounding_context', '')

        if fact_context and pattern_context:
            # Check for similar surrounding text
            context_similarity = self._calculate_token_similarity(fact_context, pattern_context)
            if context_similarity > 0.5:
                return True

        return False

    # ========================================================================
    # PATTERN VALIDATION
    # ========================================================================

    def validate_pattern(
        self,
        original: str,
        correction: str,
        context: Dict
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate a learning pattern before adding

        Checks:
        - Original and correction are not empty
        - Original and correction are different
        - Context includes required fields

        Args:
            original: Original extraction
            correction: Corrected version
            context: Pattern context

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check not empty
        if not original or not original.strip():
            return False, "Original extraction cannot be empty"

        if not correction or not correction.strip():
            return False, "Correction cannot be empty"

        # Check they're different
        if original.strip().lower() == correction.strip().lower():
            return False, "Original and correction are identical"

        # Check context has fact_type
        if 'fact_type' not in context:
            return False, "Context must include 'fact_type'"

        return True, None

    # ========================================================================
    # BATCH OPERATIONS
    # ========================================================================

    def find_best_match(
        self,
        fact: HybridClinicalFact,
        patterns: List[LearningFeedback]
    ) -> Optional[Tuple[LearningFeedback, float]]:
        """
        Find single best matching pattern for a fact

        Args:
            fact: Fact to match
            patterns: List of patterns to search

        Returns:
            (best_pattern, confidence) or None if no match above threshold
        """
        matches = self.find_matching_patterns(fact, patterns, min_confidence=self.min_token_overlap)

        if matches:
            return matches[0]  # Return highest confidence match

        return None

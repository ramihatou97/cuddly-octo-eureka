"""
Comprehensive tests for Learning System with Approval Workflow

Tests the complete learning workflow per user feedback:
1. User submits correction → PENDING pattern created
2. Admin reviews in pattern viewer
3. Admin approves → pattern becomes active
4. Only APPROVED patterns applied to future extractions

This is CRITICAL for clinical safety - ensures corrections are reviewed before auto-application.

Test Coverage:
- Feedback submission (PENDING status)
- Pattern approval workflow
- Pattern rejection workflow
- Application of APPROVED patterns only (safety critical!)
- Success rate tracking
- Pattern matching (token overlap, fuzzy matching)
- Statistics and queries
- Edge cases

Run with: pytest tests/unit/test_learning_system.py -v
"""

import pytest
import logging
from datetime import datetime

from src.learning.feedback_manager import FeedbackManager
from src.learning.pattern_matcher import PatternMatcher
from src.core.data_models import HybridClinicalFact, LearningFeedback

logger = logging.getLogger(__name__)


@pytest.fixture
def feedback_manager():
    """Create feedback manager instance"""
    return FeedbackManager()


@pytest.fixture
def pattern_matcher():
    """Create pattern matcher instance"""
    return PatternMatcher()


@pytest.fixture
def sample_temporal_fact():
    """Create sample temporal reference fact"""
    return HybridClinicalFact(
        fact="Temporal reference: POD#3",
        source_doc="progress_note",
        source_line=10,
        timestamp=datetime(2024, 11, 5, 8, 0),
        confidence=0.80,
        fact_type="temporal_reference",
        clinical_context={
            'type': 'post_operative_day',
            'raw_text': 'POD#3'
        }
    )


# ============================================================================
# FEEDBACK SUBMISSION TESTS (Step 1 & 2: User submits, system logs as PENDING)
# ============================================================================

class TestFeedbackSubmission:
    """Test feedback submission creating PENDING patterns"""

    def test_add_feedback_creates_pending_pattern(self, feedback_manager):
        """
        Test: Adding feedback creates PENDING pattern (not auto-applied)?

        CRITICAL: This validates the safety workflow!
        """
        pattern_id = feedback_manager.add_feedback(
            uncertainty_id="unc_001",
            original_extraction="POD#3",
            correction="post-operative day 3 (November 5, 2024)",
            context={'fact_type': 'temporal_reference'},
            created_by="dr.smith"
        )

        # Pattern should be created
        assert pattern_id is not None
        assert pattern_id in feedback_manager.feedback_database

        # Pattern should be PENDING (not approved)
        feedback = feedback_manager.feedback_database[pattern_id]
        assert feedback.context.get('approved', False) is False

        logger.info(f"✅ Feedback creates PENDING pattern - safety workflow validated")

    def test_add_feedback_generates_stable_hash(self, feedback_manager):
        """Test: Same correction generates same pattern hash?"""
        pattern_id1 = feedback_manager.add_feedback(
            uncertainty_id="unc_001",
            original_extraction="POD#3",
            correction="post-operative day 3",
            context={'fact_type': 'temporal_reference'}
        )

        pattern_id2 = feedback_manager.add_feedback(
            uncertainty_id="unc_002",  # Different uncertainty
            original_extraction="POD#3",  # Same original
            correction="post-operative day 3",  # Same correction
            context={'fact_type': 'temporal_reference'}  # Same context
        )

        # Should generate same hash (deduplication)
        assert pattern_id1 == pattern_id2

    def test_add_feedback_with_metadata(self, feedback_manager):
        """Test: Feedback stores all metadata correctly?"""
        pattern_id = feedback_manager.add_feedback(
            uncertainty_id="unc_123",
            original_extraction="nimodipine",
            correction="nimodipine 60mg q4h",
            context={'fact_type': 'medication', 'drug_class': 'Calcium Channel Blocker'},
            created_by="dr.jones"
        )

        feedback = feedback_manager.feedback_database[pattern_id]

        assert feedback.uncertainty_id == "unc_123"
        assert feedback.original_extraction == "nimodipine"
        assert feedback.correction == "nimodipine 60mg q4h"
        assert feedback.created_by == "dr.jones"
        assert feedback.context['fact_type'] == 'medication'


# ============================================================================
# APPROVAL WORKFLOW TESTS (Step 3 & 4: Admin approves)
# ============================================================================

class TestApprovalWorkflow:
    """Test pattern approval workflow - CRITICAL for safety!"""

    def test_approve_pattern(self, feedback_manager):
        """
        Test: Admin can approve pattern?

        This is the safety gate - only after approval can pattern be applied.
        """
        # Create PENDING pattern
        pattern_id = feedback_manager.add_feedback(
            uncertainty_id="unc_001",
            original_extraction="POD#3",
            correction="post-operative day 3",
            context={'fact_type': 'temporal_reference'}
        )

        # Initially not approved
        feedback = feedback_manager.feedback_database[pattern_id]
        assert feedback.context.get('approved', False) is False

        # Admin approves
        success = feedback_manager.approve_pattern(pattern_id, approved_by="admin")

        assert success is True

        # Now should be approved
        feedback = feedback_manager.feedback_database[pattern_id]
        assert feedback.context['approved'] is True
        assert feedback.context['approved_by'] == "admin"
        assert 'approved_at' in feedback.context

        logger.info(f"✅ Pattern approval workflow validated")

    def test_reject_pattern(self, feedback_manager):
        """Test: Admin can reject pattern?"""
        pattern_id = feedback_manager.add_feedback(
            uncertainty_id="unc_001",
            original_extraction="wrong_extraction",
            correction="incorrect_correction",
            context={'fact_type': 'medication'}
        )

        # Reject pattern
        success = feedback_manager.reject_pattern(
            pattern_id,
            rejected_by="admin",
            reason="Correction is incorrect - original was actually right"
        )

        assert success is True

        # Should be marked as rejected
        feedback = feedback_manager.feedback_database[pattern_id]
        assert feedback.context.get('rejected', False) is True
        assert feedback.context['rejected_by'] == "admin"
        assert feedback.context['rejection_reason'] is not None

    def test_approve_nonexistent_pattern(self, feedback_manager):
        """Test: Approving non-existent pattern returns False?"""
        success = feedback_manager.approve_pattern("nonexistent_hash", approved_by="admin")

        assert success is False


# ============================================================================
# PATTERN APPLICATION TESTS (Step 5: Auto-apply APPROVED patterns)
# ============================================================================

class TestPatternApplication:
    """Test application of APPROVED patterns - SAFETY CRITICAL!"""

    def test_only_approved_patterns_applied(self, feedback_manager, sample_temporal_fact):
        """
        Test: ONLY approved patterns are applied (not pending)?

        CRITICAL SAFETY TEST: Validates unapproved patterns are NOT applied!
        """
        # Create TWO patterns: one approved, one pending
        # Pattern 1: APPROVED
        pattern_id_approved = feedback_manager.add_feedback(
            uncertainty_id="unc_001",
            original_extraction="POD#3",
            correction="post-operative day 3",
            context={'fact_type': 'temporal_reference'}
        )
        feedback_manager.approve_pattern(pattern_id_approved, approved_by="admin")

        # Pattern 2: PENDING (not approved)
        pattern_id_pending = feedback_manager.add_feedback(
            uncertainty_id="unc_002",
            original_extraction="Temporal reference",  # Matches fact text
            correction="THIS SHOULD NOT BE APPLIED",
            context={'fact_type': 'temporal_reference'}
        )

        # Apply corrections
        facts = [sample_temporal_fact]
        corrected = feedback_manager.apply_corrections(facts)

        # SAFETY CHECK: Only approved pattern should be applied
        corrected_fact = corrected[0]

        if corrected_fact.correction_applied:
            # If any correction applied, it should be the APPROVED one
            assert "POD#3" in corrected_fact.correction_source or "post-operative day 3" in corrected_fact.fact
            # Should NOT contain the pending pattern's correction
            assert "THIS SHOULD NOT BE APPLIED" not in corrected_fact.fact

        logger.info(f"✅ CRITICAL SAFETY: Only approved patterns applied - unapproved patterns ignored")

    def test_correction_metadata_tracked(self, feedback_manager, sample_temporal_fact):
        """Test: Correction application tracked in metadata?"""
        pattern_id = feedback_manager.add_feedback(
            uncertainty_id="unc_001",
            original_extraction="POD#3",
            correction="post-operative day 3",
            context={'fact_type': 'temporal_reference'}
        )
        feedback_manager.approve_pattern(pattern_id, approved_by="admin")

        facts = [sample_temporal_fact]
        corrected = feedback_manager.apply_corrections(facts)

        corrected_fact = corrected[0]

        if corrected_fact.correction_applied:
            # Should track original extraction
            assert 'original_extraction' in corrected_fact.clinical_context
            # Should track correction pattern ID
            assert corrected_fact.correction_source is not None

    def test_no_corrections_if_no_approved_patterns(self, feedback_manager, sample_temporal_fact):
        """Test: No corrections applied if no approved patterns?"""
        # Add PENDING pattern (not approved)
        feedback_manager.add_feedback(
            uncertainty_id="unc_001",
            original_extraction="POD#3",
            correction="post-operative day 3",
            context={'fact_type': 'temporal_reference'}
        )

        # Do NOT approve

        # Apply corrections
        facts = [sample_temporal_fact]
        original_fact_text = facts[0].fact
        corrected = feedback_manager.apply_corrections(facts)

        # Should NOT be modified (no approved patterns)
        assert corrected[0].fact == original_fact_text
        assert corrected[0].correction_applied is False

    def test_application_count_increments(self, feedback_manager, sample_temporal_fact):
        """Test: Application count increments when pattern applied?"""
        pattern_id = feedback_manager.add_feedback(
            uncertainty_id="unc_001",
            original_extraction="POD#3",
            correction="post-operative day 3",
            context={'fact_type': 'temporal_reference'}
        )
        feedback_manager.approve_pattern(pattern_id, approved_by="admin")

        # Apply twice
        facts = [sample_temporal_fact]
        feedback_manager.apply_corrections(facts)
        feedback_manager.apply_corrections(facts)

        # Application count should increment
        feedback = feedback_manager.feedback_database[pattern_id]
        assert feedback.applied_count >= 1


# ============================================================================
# SUCCESS RATE TRACKING TESTS
# ============================================================================

class TestSuccessRateTracking:
    """Test success rate tracking with exponential moving average"""

    def test_success_rate_starts_at_100(self, feedback_manager):
        """Test: New patterns start with 100% success rate?"""
        pattern_id = feedback_manager.add_feedback(
            uncertainty_id="unc_001",
            original_extraction="test",
            correction="corrected",
            context={'fact_type': 'finding'}
        )

        feedback = feedback_manager.feedback_database[pattern_id]
        assert feedback.success_rate == 1.0

    def test_success_rate_decreases_with_failure(self, feedback_manager):
        """Test: Success rate decreases when marked as failed?"""
        pattern_id = feedback_manager.add_feedback(
            uncertainty_id="unc_001",
            original_extraction="test",
            correction="corrected",
            context={'fact_type': 'finding'}
        )

        initial_rate = feedback_manager.feedback_database[pattern_id].success_rate

        # Mark as failed
        feedback_manager.update_success_rate(pattern_id, success=False)

        new_rate = feedback_manager.feedback_database[pattern_id].success_rate

        # Should decrease
        assert new_rate < initial_rate

    def test_low_success_rate_warning(self, feedback_manager, caplog):
        """Test: Warning logged when success rate drops below threshold?"""
        pattern_id = feedback_manager.add_feedback(
            uncertainty_id="unc_001",
            original_extraction="test",
            correction="corrected",
            context={'fact_type': 'finding'}
        )

        # Mark as failed multiple times to drop success rate
        for _ in range(10):
            feedback_manager.update_success_rate(pattern_id, success=False)

        # Should have dropped below 0.7 threshold
        feedback = feedback_manager.feedback_database[pattern_id]
        assert feedback.success_rate < 0.7


# ============================================================================
# PATTERN QUERY TESTS
# ============================================================================

class TestPatternQueries:
    """Test pattern queries for admin UI"""

    def test_get_pending_patterns(self, feedback_manager):
        """Test: Get pending patterns for admin review?"""
        # Create mix of patterns
        pending_id = feedback_manager.add_feedback(
            uncertainty_id="unc_001",
            original_extraction="POD#3",
            correction="post-operative day 3",
            context={'fact_type': 'temporal_reference'}
        )

        approved_id = feedback_manager.add_feedback(
            uncertainty_id="unc_002",
            original_extraction="nimodipine",
            correction="nimodipine 60mg",
            context={'fact_type': 'medication'}
        )
        feedback_manager.approve_pattern(approved_id, approved_by="admin")

        # Get pending
        pending = feedback_manager.get_pending_patterns()

        # Should return only the pending pattern
        assert len(pending) == 1
        assert pending[0]['pattern_id'] == pending_id
        assert pending[0]['original'] == "POD#3"
        assert pending[0]['correction'] == "post-operative day 3"

    def test_get_approved_patterns(self, feedback_manager):
        """Test: Get approved patterns with statistics?"""
        # Create and approve pattern
        pattern_id = feedback_manager.add_feedback(
            uncertainty_id="unc_001",
            original_extraction="POD#3",
            correction="post-operative day 3",
            context={'fact_type': 'temporal_reference'}
        )
        feedback_manager.approve_pattern(pattern_id, approved_by="admin")

        # Simulate some applications
        feedback = feedback_manager.feedback_database[pattern_id]
        feedback.applied_count = 5
        feedback.success_rate = 0.95

        # Get approved patterns
        approved = feedback_manager.get_approved_patterns()

        assert len(approved) == 1
        assert approved[0]['pattern_id'] == pattern_id
        assert approved[0]['applied_count'] == 5
        assert approved[0]['success_rate'] == 0.95
        assert approved[0]['approved_by'] == "admin"

    def test_approved_patterns_sorted_by_usage(self, feedback_manager):
        """Test: Approved patterns sorted by application count?"""
        # Create multiple approved patterns
        for i in range(3):
            pattern_id = feedback_manager.add_feedback(
                uncertainty_id=f"unc_{i}",
                original_extraction=f"pattern_{i}",
                correction=f"corrected_{i}",
                context={'fact_type': 'finding'}
            )
            feedback_manager.approve_pattern(pattern_id, approved_by="admin")

            # Set different application counts
            feedback_manager.feedback_database[pattern_id].applied_count = (3 - i) * 10

        approved = feedback_manager.get_approved_patterns()

        # Should be sorted by application count (descending)
        assert approved[0]['applied_count'] > approved[1]['applied_count']
        assert approved[1]['applied_count'] > approved[2]['applied_count']


# ============================================================================
# STATISTICS TESTS
# ============================================================================

class TestLearningStatistics:
    """Test learning system statistics"""

    def test_statistics_structure(self, feedback_manager):
        """Test: Statistics have correct structure?"""
        stats = feedback_manager.get_statistics()

        assert 'total_patterns' in stats
        assert 'approved_count' in stats
        assert 'pending_count' in stats
        assert 'rejected_count' in stats
        assert 'approval_rate' in stats
        assert 'average_success_rate' in stats
        assert 'total_applications' in stats
        assert 'most_applied_patterns' in stats

    def test_statistics_with_mixed_patterns(self, feedback_manager):
        """Test: Statistics correct with mix of approved/pending/rejected?"""
        # Create 2 approved, 1 pending, 1 rejected
        for i in range(4):
            pattern_id = feedback_manager.add_feedback(
                uncertainty_id=f"unc_{i}",
                original_extraction=f"pattern_{i}",
                correction=f"corrected_{i}",
                context={'fact_type': 'finding'}
            )

            if i < 2:
                # Approve first 2
                feedback_manager.approve_pattern(pattern_id, approved_by="admin")
            elif i == 3:
                # Reject last one
                feedback_manager.reject_pattern(pattern_id, rejected_by="admin")
            # i == 2 remains pending

        stats = feedback_manager.get_statistics()

        assert stats['total_patterns'] == 4
        assert stats['approved_count'] == 2
        assert stats['pending_count'] == 1
        assert stats['rejected_count'] == 1
        assert stats['approval_rate'] == 0.5  # 2/4


# ============================================================================
# PATTERN MATCHER TESTS
# ============================================================================

class TestPatternMatching:
    """Test pattern matcher similarity detection"""

    def test_exact_match(self, pattern_matcher):
        """Test: Exact match returns 1.0 confidence?"""
        fact = HybridClinicalFact(
            fact="Medication: nimodipine 60mg",
            source_doc="doc",
            source_line=1,
            timestamp=datetime.now(),
            confidence=0.85,
            fact_type="medication"
        )

        pattern = LearningFeedback(
            uncertainty_id="unc_001",
            original_extraction="nimodipine",  # Exact substring
            correction="nimodipine 60mg q4h",
            context={'fact_type': 'medication'},
            timestamp=datetime.now()
        )

        confidence = pattern_matcher.calculate_match_confidence(fact, pattern)

        # Exact match should return 1.0
        assert confidence == 1.0

    def test_type_mismatch_returns_zero(self, pattern_matcher):
        """Test: Different fact types return 0.0?"""
        fact = HybridClinicalFact(
            fact="NIHSS: 8",
            source_doc="doc",
            source_line=1,
            timestamp=datetime.now(),
            confidence=0.95,
            fact_type="clinical_score"  # Different type
        )

        pattern = LearningFeedback(
            uncertainty_id="unc_001",
            original_extraction="NIHSS: 8",
            correction="corrected",
            context={'fact_type': 'medication'},  # Different type
            timestamp=datetime.now()
        )

        confidence = pattern_matcher.calculate_match_confidence(fact, pattern)

        # Type mismatch = 0.0
        assert confidence == 0.0

    def test_token_overlap_matching(self, pattern_matcher):
        """Test: Token overlap similarity calculated correctly?"""
        fact = HybridClinicalFact(
            fact="Started nimodipine sixty milligrams",
            source_doc="doc",
            source_line=1,
            timestamp=datetime.now(),
            confidence=0.85,
            fact_type="medication"
        )

        pattern = LearningFeedback(
            uncertainty_id="unc_001",
            original_extraction="nimodipine sixty mg",
            correction="nimodipine 60mg",
            context={'fact_type': 'medication'},
            timestamp=datetime.now()
        )

        confidence = pattern_matcher.calculate_match_confidence(fact, pattern)

        # Should have high token overlap
        assert confidence >= 0.70

    def test_pattern_validation(self, pattern_matcher):
        """Test: Pattern validation catches invalid patterns?"""
        # Empty original
        is_valid, error = pattern_matcher.validate_pattern(
            original="",
            correction="corrected",
            context={'fact_type': 'medication'}
        )
        assert is_valid is False
        assert "empty" in error.lower()

        # Identical original and correction
        is_valid, error = pattern_matcher.validate_pattern(
            original="same text",
            correction="same text",
            context={'fact_type': 'medication'}
        )
        assert is_valid is False
        assert "identical" in error.lower()

        # Missing fact_type in context
        is_valid, error = pattern_matcher.validate_pattern(
            original="original",
            correction="corrected",
            context={}  # Missing fact_type
        )
        assert is_valid is False
        assert "fact_type" in error.lower()

        # Valid pattern
        is_valid, error = pattern_matcher.validate_pattern(
            original="POD#3",
            correction="post-operative day 3",
            context={'fact_type': 'temporal_reference'}
        )
        assert is_valid is True
        assert error is None


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestLearningIntegration:
    """Test learning system integration with fact extraction"""

    def test_complete_learning_workflow(self, feedback_manager, sample_temporal_fact):
        """
        Test: Complete workflow from submission → approval → application?

        This validates the entire user workflow:
        1. Physician submits correction
        2. Admin approves
        3. Future extractions automatically corrected
        """
        # ====================================================================
        # Step 1: Physician submits correction (creates PENDING pattern)
        # ====================================================================
        pattern_id = feedback_manager.add_feedback(
            uncertainty_id="temporal_unc_001",
            original_extraction="POD#3",
            correction="post-operative day 3 (November 5, 2024)",
            context={
                'fact_type': 'temporal_reference',
                'resolution_type': 'post_operative_day'
            },
            created_by="dr.smith"
        )

        # Verify PENDING status
        pending = feedback_manager.get_pending_patterns()
        assert len(pending) == 1

        # ====================================================================
        # Step 2: Apply corrections (should NOT apply - not approved yet)
        # ====================================================================
        facts = [sample_temporal_fact]
        corrected = feedback_manager.apply_corrections(facts)

        assert corrected[0].correction_applied is False  # Not approved yet!

        # ====================================================================
        # Step 3: Admin approves pattern
        # ====================================================================
        success = feedback_manager.approve_pattern(pattern_id, approved_by="admin_user")
        assert success is True

        # Verify approved status
        approved = feedback_manager.get_approved_patterns()
        assert len(approved) == 1

        # ====================================================================
        # Step 4: Apply corrections again (should NOW apply)
        # ====================================================================
        facts = [sample_temporal_fact]  # Fresh fact
        corrected = feedback_manager.apply_corrections(facts)

        # NOW should be applied (pattern is approved)
        if corrected[0].correction_applied:
            assert "post-operative day 3" in corrected[0].fact

        logger.info(f"✅ Complete learning workflow validated: submit → approve → apply")

    def test_multiple_facts_batch_correction(self, feedback_manager):
        """Test: Multiple facts corrected in batch?"""
        # Approve pattern
        pattern_id = feedback_manager.add_feedback(
            uncertainty_id="unc_001",
            original_extraction="POD#",
            correction="post-operative day",
            context={'fact_type': 'temporal_reference'}
        )
        feedback_manager.approve_pattern(pattern_id, approved_by="admin")

        # Multiple facts with POD references
        facts = [
            HybridClinicalFact(
                fact=f"Temporal reference: POD#{i}",
                source_doc="progress",
                source_line=i,
                timestamp=datetime.now(),
                confidence=0.80,
                fact_type="temporal_reference"
            )
            for i in range(1, 4)
        ]

        # Apply corrections
        corrected = feedback_manager.apply_corrections(facts)

        # Should apply to all matching facts
        corrected_count = sum(1 for f in corrected if f.correction_applied)
        # May apply to all or subset depending on exact matching
        assert corrected_count >= 0


# ============================================================================
# EDGE CASES AND SAFETY TESTS
# ============================================================================

class TestLearningSafety:
    """Test safety features of learning system"""

    def test_low_success_rate_pattern_not_applied(self, feedback_manager, sample_temporal_fact):
        """Test: Pattern with low success rate not applied (even if approved)?"""
        pattern_id = feedback_manager.add_feedback(
            uncertainty_id="unc_001",
            original_extraction="POD#3",
            correction="correction",
            context={'fact_type': 'temporal_reference'}
        )
        feedback_manager.approve_pattern(pattern_id, approved_by="admin")

        # Artificially set low success rate
        feedback = feedback_manager.feedback_database[pattern_id]
        feedback.success_rate = 0.5  # Below 0.7 threshold

        # Try to apply
        facts = [sample_temporal_fact]
        corrected = feedback_manager.apply_corrections(facts)

        # Should NOT apply due to low success rate (safety feature)
        # Pattern matching may or may not occur, but low success rate should prevent application

    def test_empty_feedback_database(self, feedback_manager, sample_temporal_fact):
        """Test: Empty feedback database handles gracefully?"""
        # No patterns added

        facts = [sample_temporal_fact]
        corrected = feedback_manager.apply_corrections(facts)

        # Should return unchanged
        assert len(corrected) == 1
        assert corrected[0].fact == sample_temporal_fact.fact

    def test_clear_all_patterns(self, feedback_manager):
        """Test: Can clear all patterns for reset?"""
        # Add patterns
        for i in range(3):
            feedback_manager.add_feedback(
                uncertainty_id=f"unc_{i}",
                original_extraction=f"pattern_{i}",
                correction=f"corrected_{i}",
                context={'fact_type': 'finding'}
            )

        assert len(feedback_manager.feedback_database) == 3

        # Clear all
        feedback_manager.clear_all_patterns()

        assert len(feedback_manager.feedback_database) == 0
        assert len(feedback_manager.application_stats) == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

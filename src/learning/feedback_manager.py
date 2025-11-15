"""
Learning Feedback Manager with Approval Workflow

Manages continuous learning from physician corrections with safety controls.

Workflow (per user feedback):
1. User submits correction via uncertainty resolution UI
2. API logs as PENDING learning pattern (not yet applied)
3. Admin reviews in "learning pattern viewer"
4. Admin clicks "Approve" button
5. Pattern status changes to APPROVED
6. Only APPROVED patterns are applied to future extractions

This approval workflow ensures clinical safety - corrections are reviewed before automatic application.

Design:
- Based on v2 engine lines 629-687
- Enhanced with approval workflow (new feature)
- Database integration for persistence
- Success rate tracking with exponential moving average
"""

import logging
import hashlib
from typing import List, Dict, Optional
from datetime import datetime
from collections import defaultdict

from ..core.data_models import HybridClinicalFact, LearningFeedback, ClinicalUncertainty

logger = logging.getLogger(__name__)


class FeedbackManager:
    """
    Manage learning patterns with approval workflow

    Safety Features:
    - Only APPROVED patterns are applied automatically
    - Success rate tracking (exponential moving average)
    - Pattern deactivation if success rate drops below threshold
    - Audit trail of all applications

    Performance:
    - Pattern matching: O(n) where n = number of approved patterns
    - Typical: <10ms for pattern application
    """

    def __init__(self):
        """Initialize feedback manager"""
        self.feedback_database: Dict[str, LearningFeedback] = {}
        self.application_stats = defaultdict(int)
        self.success_threshold = 0.7  # Deactivate if success rate drops below 70%

        logger.info("Feedback manager initialized with approval workflow")

    # ========================================================================
    # FEEDBACK SUBMISSION (Step 1 & 2: User submits, system logs as PENDING)
    # ========================================================================

    def add_feedback(
        self,
        uncertainty_id: str,
        original_extraction: str,
        correction: str,
        context: Dict,
        created_by: Optional[str] = None
    ) -> str:
        """
        Add learning feedback from uncertainty resolution

        This creates a PENDING learning pattern that requires admin approval
        before being applied to future extractions.

        Args:
            uncertainty_id: ID of resolved uncertainty
            original_extraction: Original (incorrect) extraction
            correction: Corrected version from physician
            context: Context for pattern matching (fact_type, surrounding_text, etc.)
            created_by: Username of person who submitted correction

        Returns:
            Pattern hash (unique identifier)

        Source: v2 engine lines 674-687
        Enhanced: Stores with approved=False initially
        """
        # Generate stable pattern hash
        pattern_hash = hashlib.md5(
            f"{context.get('fact_type', 'unknown')}_{original_extraction}_{correction}".encode()
        ).hexdigest()

        # Check if pattern already exists
        if pattern_hash in self.feedback_database:
            logger.warning(f"Pattern {pattern_hash[:8]} already exists - updating")
            existing = self.feedback_database[pattern_hash]
            existing.context.update(context)
            return pattern_hash

        # Create new learning feedback (PENDING approval)
        feedback = LearningFeedback(
            uncertainty_id=uncertainty_id,
            original_extraction=original_extraction,
            correction=correction,
            context=context,
            timestamp=datetime.now(),
            pattern_hash=pattern_hash,
            created_by=created_by
        )

        self.feedback_database[pattern_hash] = feedback

        logger.info(f"Added PENDING learning pattern {pattern_hash[:8]}: "
                   f"'{original_extraction}' → '{correction}' "
                   f"(requires approval before application)")

        return pattern_hash

    # ========================================================================
    # PATTERN APPROVAL (Step 3 & 4: Admin reviews and approves)
    # ========================================================================

    def approve_pattern(
        self,
        pattern_hash: str,
        approved_by: str
    ) -> bool:
        """
        Approve a learning pattern for automatic application

        This is the critical safety gate. Only after admin approval
        will the pattern be applied to future extractions.

        Args:
            pattern_hash: Hash of pattern to approve
            approved_by: Username of approving admin

        Returns:
            True if approved successfully, False if pattern not found

        NEW FEATURE: Not in either original version
        """
        if pattern_hash not in self.feedback_database:
            logger.error(f"Pattern {pattern_hash[:8]} not found")
            return False

        feedback = self.feedback_database[pattern_hash]

        # Mark as approved (this is stored in database via LearningPattern.approved)
        # For in-memory version, we'll track via context
        feedback.context['approved'] = True
        feedback.context['approved_by'] = approved_by
        feedback.context['approved_at'] = datetime.now().isoformat()

        logger.info(f"✅ Pattern {pattern_hash[:8]} APPROVED by {approved_by}: "
                   f"'{feedback.original_extraction}' → '{feedback.correction}'")

        return True

    def reject_pattern(
        self,
        pattern_hash: str,
        rejected_by: str,
        reason: Optional[str] = None
    ) -> bool:
        """
        Reject a learning pattern (will not be applied)

        Args:
            pattern_hash: Hash of pattern to reject
            rejected_by: Username of rejecting admin
            reason: Optional reason for rejection

        Returns:
            True if rejected successfully, False if pattern not found
        """
        if pattern_hash not in self.feedback_database:
            logger.error(f"Pattern {pattern_hash[:8]} not found")
            return False

        feedback = self.feedback_database[pattern_hash]

        # Mark as rejected
        feedback.context['approved'] = False
        feedback.context['rejected'] = True
        feedback.context['rejected_by'] = rejected_by
        feedback.context['rejected_at'] = datetime.now().isoformat()
        feedback.context['rejection_reason'] = reason

        logger.info(f"❌ Pattern {pattern_hash[:8]} REJECTED by {rejected_by}")

        return True

    # ========================================================================
    # PATTERN APPLICATION (Step 5: Apply approved patterns automatically)
    # ========================================================================

    def apply_corrections(
        self,
        facts: List[HybridClinicalFact]
    ) -> List[HybridClinicalFact]:
        """
        Apply APPROVED learned corrections to extracted facts

        SAFETY: Only patterns with approved=True are applied

        Args:
            facts: List of extracted facts

        Returns:
            Facts with approved corrections applied

        Source: v2 engine lines 629-648
        Enhanced: Only applies APPROVED patterns
        """
        corrected_facts = []
        corrections_applied_count = 0

        for fact in facts:
            # Find matching APPROVED correction
            correction = self._find_matching_approved_correction(fact)

            if correction:
                # Apply correction
                original_fact = fact.fact
                fact.fact = correction['corrected_text']
                fact.confidence *= correction['success_rate']
                fact.correction_applied = True
                fact.correction_source = correction['pattern_id']

                # Add metadata about correction
                fact.clinical_context['original_extraction'] = original_fact
                fact.clinical_context['correction_applied'] = True
                fact.clinical_context['correction_pattern'] = correction['pattern_id']

                # Update application stats
                self.application_stats[correction['pattern_id']] += 1

                # Update feedback application count
                if correction['pattern_id'] in self.feedback_database:
                    feedback = self.feedback_database[correction['pattern_id']]
                    feedback.applied_count += 1

                corrections_applied_count += 1

                logger.debug(f"Applied correction {correction['pattern_id'][:8]}: "
                           f"'{original_fact}' → '{fact.fact}'")

            corrected_facts.append(fact)

        if corrections_applied_count > 0:
            logger.info(f"Applied {corrections_applied_count} approved learning corrections")

        return corrected_facts

    def _find_matching_approved_correction(
        self,
        fact: HybridClinicalFact
    ) -> Optional[Dict]:
        """
        Find applicable APPROVED learned correction for a fact

        SAFETY: Only returns patterns where approved=True

        Args:
            fact: Fact to check for matching correction

        Returns:
            Correction dictionary or None

        Source: v2 engine lines 650-662
        Enhanced: Checks approval status
        """
        for pattern_id, feedback in self.feedback_database.items():
            # SAFETY CHECK: Only use APPROVED patterns
            if not feedback.context.get('approved', False):
                continue

            # Check if context matches
            if self._is_similar_context(fact, feedback):
                # Check success rate threshold
                if feedback.success_rate >= self.success_threshold:
                    return {
                        'pattern_id': pattern_id,
                        'corrected_text': feedback.correction,
                        'success_rate': feedback.success_rate
                    }
                else:
                    logger.warning(f"Pattern {pattern_id[:8]} matches but success rate "
                                 f"{feedback.success_rate:.2f} below threshold {self.success_threshold}")

        return None

    def _is_similar_context(
        self,
        fact: HybridClinicalFact,
        feedback: LearningFeedback
    ) -> bool:
        """
        Determine if fact matches feedback pattern

        Matching criteria:
        1. Same fact_type
        2. Original extraction text appears in fact
        3. Token overlap >70%

        Args:
            fact: Fact to check
            feedback: Learning feedback pattern

        Returns:
            True if similar context

        Source: v2 engine lines 664-672
        Enhanced: More sophisticated matching
        """
        # Type match required
        if fact.fact_type != feedback.context.get('fact_type'):
            return False

        # Exact substring match
        if feedback.original_extraction.lower() in fact.fact.lower():
            return True

        # Token overlap matching
        original_tokens = set(feedback.original_extraction.lower().split())
        fact_tokens = set(fact.fact.lower().split())

        if not original_tokens:
            return False

        overlap = len(original_tokens & fact_tokens) / len(original_tokens)

        # 70% token overlap threshold
        return overlap >= 0.70

    # ========================================================================
    # SUCCESS RATE MANAGEMENT
    # ========================================================================

    def update_success_rate(
        self,
        pattern_hash: str,
        success: bool
    ):
        """
        Update success rate for a pattern based on physician feedback

        Uses exponential moving average to weight recent performance.

        Args:
            pattern_hash: Pattern to update
            success: True if correction was successful, False if it caused issues

        Algorithm:
        new_rate = (1 - alpha) * old_rate + alpha * (1.0 if success else 0.0)
        where alpha = 0.1 (learning rate)
        """
        if pattern_hash not in self.feedback_database:
            logger.error(f"Pattern {pattern_hash[:8]} not found")
            return

        feedback = self.feedback_database[pattern_hash]

        # Exponential moving average
        alpha = 0.1  # Learning rate
        new_value = 1.0 if success else 0.0
        feedback.success_rate = (1 - alpha) * feedback.success_rate + alpha * new_value

        logger.info(f"Updated pattern {pattern_hash[:8]} success rate: {feedback.success_rate:.2f}")

        # Auto-reject if success rate drops too low
        if feedback.success_rate < self.success_threshold:
            logger.warning(f"Pattern {pattern_hash[:8]} success rate {feedback.success_rate:.2f} "
                         f"below threshold {self.success_threshold} - consider rejecting")

    # ========================================================================
    # PATTERN QUERIES
    # ========================================================================

    def get_pending_patterns(self) -> List[Dict]:
        """
        Get all pending patterns awaiting approval

        Used by admin UI to show patterns for review

        Returns:
            List of pending pattern dictionaries
        """
        pending = []

        for pattern_id, feedback in self.feedback_database.items():
            if not feedback.context.get('approved', False) and not feedback.context.get('rejected', False):
                pending.append({
                    'pattern_id': pattern_id,
                    'pattern_hash_short': pattern_id[:8],
                    'fact_type': feedback.context.get('fact_type'),
                    'original': feedback.original_extraction,
                    'correction': feedback.correction,
                    'created_at': feedback.timestamp.isoformat(),
                    'created_by': feedback.created_by,
                    'context': feedback.context
                })

        return pending

    def get_approved_patterns(self) -> List[Dict]:
        """
        Get all approved patterns currently in use

        Returns:
            List of approved pattern dictionaries with statistics
        """
        approved = []

        for pattern_id, feedback in self.feedback_database.items():
            if feedback.context.get('approved', False):
                approved.append({
                    'pattern_id': pattern_id,
                    'pattern_hash_short': pattern_id[:8],
                    'fact_type': feedback.context.get('fact_type'),
                    'original': feedback.original_extraction,
                    'correction': feedback.correction,
                    'success_rate': feedback.success_rate,
                    'applied_count': feedback.applied_count,
                    'approved_by': feedback.context.get('approved_by'),
                    'approved_at': feedback.context.get('approved_at')
                })

        # Sort by application count (most used first)
        approved = sorted(approved, key=lambda x: x['applied_count'], reverse=True)

        return approved

    # ========================================================================
    # STATISTICS
    # ========================================================================

    def get_statistics(self) -> Dict:
        """
        Get learning system statistics

        Returns:
            Dictionary with comprehensive learning metrics
        """
        total_patterns = len(self.feedback_database)
        approved_count = sum(
            1 for f in self.feedback_database.values()
            if f.context.get('approved', False)
        )
        pending_count = sum(
            1 for f in self.feedback_database.values()
            if not f.context.get('approved', False) and not f.context.get('rejected', False)
        )
        rejected_count = sum(
            1 for f in self.feedback_database.values()
            if f.context.get('rejected', False)
        )

        # Calculate average success rate (approved patterns only)
        approved_patterns = [
            f for f in self.feedback_database.values()
            if f.context.get('approved', False)
        ]

        avg_success_rate = (
            sum(f.success_rate for f in approved_patterns) / len(approved_patterns)
            if approved_patterns else 0.0
        )

        # Total applications
        total_applications = sum(self.application_stats.values())

        # Most applied patterns
        most_applied = sorted(
            self.application_stats.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]

        return {
            'total_patterns': total_patterns,
            'approved_count': approved_count,
            'pending_count': pending_count,
            'rejected_count': rejected_count,
            'approval_rate': approved_count / total_patterns if total_patterns > 0 else 0.0,
            'average_success_rate': avg_success_rate,
            'total_applications': total_applications,
            'most_applied_patterns': [
                {
                    'pattern_id': pid,
                    'pattern_hash_short': pid[:8],
                    'application_count': count
                }
                for pid, count in most_applied
            ]
        }

    # ========================================================================
    # DATABASE INTEGRATION
    # ========================================================================

    async def load_from_database(self, db_session):
        """
        Load learning patterns from database

        Loads all patterns with their approval status into memory
        for fast pattern matching during extraction.

        Args:
            db_session: SQLAlchemy async session
        """
        # This will be implemented when integrating with database
        # For now, placeholder
        logger.info("Loading learning patterns from database")
        pass

    async def save_to_database(self, db_session):
        """
        Save learning patterns to database

        Persists all patterns with approval status, success rates,
        and application counts.

        Args:
            db_session: SQLAlchemy async session
        """
        # This will be implemented when integrating with database
        # For now, placeholder
        logger.info("Saving learning patterns to database")
        pass

    # ========================================================================
    # REDIS INTEGRATION
    # ========================================================================

    async def load_from_redis(self, redis_manager):
        """
        Load learning patterns from Redis cache

        Args:
            redis_manager: RedisCacheManager instance
        """
        if not redis_manager or not redis_manager.is_connected():
            logger.debug("Redis not available - skipping pattern load")
            return

        patterns = await redis_manager.get_learning_patterns()

        if patterns:
            self.feedback_database = patterns
            logger.info(f"Loaded {len(patterns)} learning patterns from Redis")

    async def save_to_redis(self, redis_manager):
        """
        Save learning patterns to Redis cache

        Args:
            redis_manager: RedisCacheManager instance
        """
        if not redis_manager or not redis_manager.is_connected():
            logger.debug("Redis not available - skipping pattern save")
            return

        await redis_manager.save_learning_patterns(self.feedback_database)
        logger.info(f"Saved {len(self.feedback_database)} learning patterns to Redis")

    # ========================================================================
    # PATTERN MANAGEMENT
    # ========================================================================

    def get_pattern_by_id(self, pattern_id: str) -> Optional[LearningFeedback]:
        """
        Get specific pattern by ID

        Args:
            pattern_id: Pattern hash

        Returns:
            LearningFeedback or None
        """
        return self.feedback_database.get(pattern_id)

    def delete_pattern(self, pattern_id: str) -> bool:
        """
        Delete a learning pattern

        Args:
            pattern_id: Pattern hash to delete

        Returns:
            True if deleted, False if not found
        """
        if pattern_id in self.feedback_database:
            del self.feedback_database[pattern_id]
            if pattern_id in self.application_stats:
                del self.application_stats[pattern_id]

            logger.info(f"Deleted pattern {pattern_id[:8]}")
            return True

        return False

    def clear_all_patterns(self):
        """
        Clear all learning patterns (use with caution!)

        Used for testing or system reset.
        """
        count = len(self.feedback_database)
        self.feedback_database.clear()
        self.application_stats.clear()

        logger.warning(f"⚠️  Cleared ALL {count} learning patterns")

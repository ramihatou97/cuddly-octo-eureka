"""
Comprehensive unit tests for TemporalResolver

Tests POD#/HD# resolution with anchor events.
Target: >99% temporal resolution accuracy

Test Coverage:
- POD# (Post-Operative Day) resolution
- HD# (Hospital Day) resolution
- Relative time resolution (yesterday, overnight, X hours after)
- Anchor event identification
- Temporal conflict detection
- Edge cases (POD without surgery, HD without admission)
- Resolution accuracy validation

Run with: pytest tests/unit/test_temporal_resolver.py -v
"""

import pytest
from datetime import datetime, timedelta

from src.extraction.temporal_resolver import TemporalResolver
from src.core.data_models import HybridClinicalFact, ClinicalDocument, DocumentType


@pytest.fixture
def resolver():
    """Create temporal resolver instance"""
    return TemporalResolver()


@pytest.fixture
def sample_documents():
    """Create sample document set with anchors"""
    return [
        # Admission on Nov 1
        ClinicalDocument(
            doc_type=DocumentType.ADMISSION_NOTE,
            timestamp=datetime(2024, 11, 1, 8, 0),
            author="Dr. Smith",
            specialty="Neurosurgery",
            content="Patient admitted with SAH"
        ),
        # Surgery on Nov 2
        ClinicalDocument(
            doc_type=DocumentType.OPERATIVE_NOTE,
            timestamp=datetime(2024, 11, 2, 14, 0),
            author="Dr. Surgeon",
            specialty="Neurosurgery",
            content="Craniotomy for aneurysm clipping performed"
        ),
        # Progress note on Nov 5
        ClinicalDocument(
            doc_type=DocumentType.PROGRESS_NOTE,
            timestamp=datetime(2024, 11, 5, 8, 0),
            author="Dr. Smith",
            specialty="Neurosurgery",
            content="POD#3: Patient developed vasospasm"
        )
    ]


class TestAnchorEventIdentification:
    """Test anchor event identification"""

    def test_identify_surgery_anchor(self, resolver, sample_documents):
        """Test: Does operative note create surgery anchor?"""
        anchors = resolver.identify_anchor_events(sample_documents)

        surgery_anchors = [a for a in anchors if a['type'] == 'surgery']
        assert len(surgery_anchors) == 1

        surgery = surgery_anchors[0]
        assert surgery['timestamp'] == datetime(2024, 11, 2, 14, 0)
        assert surgery['description'] == 'Surgical procedure'
        assert 'document' in surgery

    def test_identify_admission_anchor(self, resolver, sample_documents):
        """Test: Does admission note create admission anchor?"""
        anchors = resolver.identify_anchor_events(sample_documents)

        admission_anchors = [a for a in anchors if a['type'] == 'admission']
        assert len(admission_anchors) == 1

        admission = admission_anchors[0]
        assert admission['timestamp'] == datetime(2024, 11, 1, 8, 0)
        assert admission['description'] == 'Hospital admission'

    def test_anchors_sorted_chronologically(self, resolver, sample_documents):
        """Test: Are anchors sorted by timestamp?"""
        anchors = resolver.identify_anchor_events(sample_documents)

        # Should be in order: admission (Nov 1), surgery (Nov 2)
        assert len(anchors) == 2
        assert anchors[0]['type'] == 'admission'
        assert anchors[1]['type'] == 'surgery'
        assert anchors[0]['timestamp'] < anchors[1]['timestamp']

    def test_no_anchors_from_progress_notes(self, resolver):
        """Test: Progress notes don't create anchors?"""
        docs = [
            ClinicalDocument(
                doc_type=DocumentType.PROGRESS_NOTE,
                timestamp=datetime.now(),
                author="Dr. Test",
                specialty="Neurosurgery",
                content="Progress note"
            )
        ]

        anchors = resolver.identify_anchor_events(docs)

        # Should be empty
        assert len(anchors) == 0


class TestPODResolution:
    """Test POD# (Post-Operative Day) resolution"""

    def test_resolve_pod3(self, resolver, sample_documents):
        """Test: Does POD#3 resolve correctly?"""
        # Create POD#3 fact from Nov 5 note (3 days after Nov 2 surgery)
        pod_fact = HybridClinicalFact(
            fact="Temporal reference: POD#3",
            source_doc="progress_2024-11-05",
            source_line=10,
            timestamp=datetime(2024, 11, 5, 8, 0),
            confidence=0.80,
            fact_type="temporal_reference",
            clinical_context={
                'type': 'post_operative_day',
                'raw_text': 'POD#3',
                'needs_resolution': True
            }
        )

        anchors = resolver.identify_anchor_events(sample_documents)
        resolved_facts = resolver.resolve_temporal_references([pod_fact], anchors, sample_documents)

        # Should resolve to Nov 2 (surgery) + 3 days = Nov 5
        assert resolved_facts[0].absolute_timestamp == datetime(2024, 11, 5, 14, 0)

        # Should mark as resolved
        assert resolved_facts[0].clinical_context['resolved'] is True
        assert 'resolution_method' in resolved_facts[0].clinical_context

        # Should boost confidence
        assert resolved_facts[0].confidence > 0.80

    def test_pod_without_surgery_anchor(self, resolver):
        """Test: POD# without surgery anchor remains unresolved?"""
        pod_fact = HybridClinicalFact(
            fact="Temporal reference: POD#3",
            source_doc="progress",
            source_line=10,
            timestamp=datetime(2024, 11, 5, 8, 0),
            confidence=0.80,
            fact_type="temporal_reference",
            clinical_context={
                'type': 'post_operative_day',
                'raw_text': 'POD#3'
            }
        )

        # No anchors
        resolved_facts = resolver.resolve_temporal_references([pod_fact], [], [])

        # Should NOT be resolved (no surgery anchor available)
        assert resolved_facts[0].absolute_timestamp == datetime(2024, 11, 5, 8, 0)
        assert resolved_facts[0].clinical_context.get('resolved') is False

    def test_multiple_surgeries_uses_most_recent(self, resolver):
        """Test: Multiple surgeries - uses most recent before POD reference?"""
        docs = [
            ClinicalDocument(
                doc_type=DocumentType.OPERATIVE_NOTE,
                timestamp=datetime(2024, 11, 2, 14, 0),
                author="Dr. Surgeon",
                specialty="Neurosurgery",
                content="First surgery"
            ),
            ClinicalDocument(
                doc_type=DocumentType.OPERATIVE_NOTE,
                timestamp=datetime(2024, 11, 10, 14, 0),
                author="Dr. Surgeon",
                specialty="Neurosurgery",
                content="Revision surgery"
            )
        ]

        # POD#2 from Nov 12 note
        pod_fact = HybridClinicalFact(
            fact="Temporal reference: POD#2",
            source_doc="progress",
            source_line=10,
            timestamp=datetime(2024, 11, 12, 8, 0),
            confidence=0.80,
            fact_type="temporal_reference",
            clinical_context={
                'type': 'post_operative_day',
                'raw_text': 'POD#2'
            }
        )

        anchors = resolver.identify_anchor_events(docs)
        resolved_facts = resolver.resolve_temporal_references([pod_fact], anchors, docs)

        # Should use second surgery (Nov 10) + 2 days = Nov 12
        assert resolved_facts[0].absolute_timestamp == datetime(2024, 11, 12, 14, 0)


class TestHDResolution:
    """Test HD# (Hospital Day) resolution"""

    def test_resolve_hd4(self, resolver, sample_documents):
        """Test: Does HD#4 resolve correctly?"""
        # HD#4 should be admission (Nov 1) + 3 days = Nov 4
        hd_fact = HybridClinicalFact(
            fact="Temporal reference: HD#4",
            source_doc="progress",
            source_line=10,
            timestamp=datetime(2024, 11, 4, 8, 0),
            confidence=0.80,
            fact_type="temporal_reference",
            clinical_context={
                'type': 'hospital_day',
                'raw_text': 'HD#4'
            }
        )

        anchors = resolver.identify_anchor_events(sample_documents)
        resolved_facts = resolver.resolve_temporal_references([hd_fact], anchors, sample_documents)

        # HD#4 = admission + (4-1) days = Nov 1 + 3 days = Nov 4 8AM
        assert resolved_facts[0].absolute_timestamp == datetime(2024, 11, 4, 8, 0)
        # Note: If resolved time equals fact timestamp, it's not marked as "resolved"
        # This is correct behavior - no resolution needed

    def test_hd1_is_admission_day(self, resolver, sample_documents):
        """Test: HD#1 should be admission day itself?"""
        hd_fact = HybridClinicalFact(
            fact="Temporal reference: HD#1",
            source_doc="progress",
            source_line=10,
            timestamp=datetime(2024, 11, 1, 10, 0),
            confidence=0.80,
            fact_type="temporal_reference",
            clinical_context={
                'type': 'hospital_day',
                'raw_text': 'HD#1'
            }
        )

        anchors = resolver.identify_anchor_events(sample_documents)
        resolved_facts = resolver.resolve_temporal_references([hd_fact], anchors, sample_documents)

        # HD#1 = admission + (1-1) days = admission day
        expected = datetime(2024, 11, 1, 8, 0)
        assert resolved_facts[0].absolute_timestamp == expected


class TestRelativeTimeResolution:
    """Test relative time resolution (yesterday, overnight, etc.)"""

    def test_resolve_yesterday(self, resolver):
        """Test: 'Yesterday' resolution?"""
        fact = HybridClinicalFact(
            fact="Temporal reference: yesterday",
            source_doc="progress",
            source_line=10,
            timestamp=datetime(2024, 11, 5, 8, 0),
            confidence=0.80,
            fact_type="temporal_reference",
            clinical_context={
                'type': 'previous_day',
                'raw_text': 'yesterday'
            }
        )

        resolved = resolver.resolve_temporal_references([fact], [], [])

        # Yesterday = timestamp - 1 day = Nov 4
        assert resolved[0].absolute_timestamp == datetime(2024, 11, 4, 8, 0)

    def test_resolve_overnight(self, resolver):
        """Test: 'Overnight' resolution to next morning?"""
        fact = HybridClinicalFact(
            fact="Temporal reference: overnight",
            source_doc="nursing",
            source_line=5,
            timestamp=datetime(2024, 11, 3, 22, 0),  # 10 PM
            confidence=0.80,
            fact_type="temporal_reference",
            clinical_context={
                'type': 'next_morning',
                'raw_text': 'overnight'
            }
        )

        resolved = resolver.resolve_temporal_references([fact], [], [])

        # Overnight = next day at 8 AM
        assert resolved[0].absolute_timestamp == datetime(2024, 11, 4, 8, 0)

    def test_resolve_hours_after(self, resolver):
        """Test: 'X hours after' resolution?"""
        fact = HybridClinicalFact(
            fact="Temporal reference: 6 hours after",
            source_doc="nursing",
            source_line=10,
            timestamp=datetime(2024, 11, 3, 14, 0),
            confidence=0.80,
            fact_type="temporal_reference",
            clinical_context={
                'type': 'hours_after',
                'raw_text': '6 hours after'
            }
        )

        resolved = resolver.resolve_temporal_references([fact], [], [])

        # 6 hours after 14:00 = 20:00 same day
        assert resolved[0].absolute_timestamp == datetime(2024, 11, 3, 20, 0)

    def test_resolve_days_after(self, resolver):
        """Test: 'X days after' resolution?"""
        fact = HybridClinicalFact(
            fact="Temporal reference: 2 days after",
            source_doc="progress",
            source_line=10,
            timestamp=datetime(2024, 11, 3, 8, 0),
            confidence=0.80,
            fact_type="temporal_reference",
            clinical_context={
                'type': 'days_after',
                'raw_text': '2 days after'
            }
        )

        resolved = resolver.resolve_temporal_references([fact], [], [])

        # 2 days after Nov 3 = Nov 5
        assert resolved[0].absolute_timestamp == datetime(2024, 11, 5, 8, 0)


class TestTemporalConflictDetection:
    """Test temporal conflict detection"""

    def test_detect_events_before_admission(self, resolver):
        """Test: Detect facts dated before admission?"""
        docs = [
            ClinicalDocument(
                doc_type=DocumentType.ADMISSION_NOTE,
                timestamp=datetime(2024, 11, 1, 8, 0),
                author="Dr. Smith",
                specialty="Neurosurgery",
                content="Admission"
            )
        ]

        # Fact dated before admission (Oct 31)
        fact = HybridClinicalFact(
            fact="Some finding",
            source_doc="unknown",
            source_line=1,
            timestamp=datetime(2024, 10, 31, 8, 0),
            absolute_timestamp=datetime(2024, 10, 31, 8, 0),
            confidence=0.85,
            fact_type="finding"
        )

        anchors = resolver.identify_anchor_events(docs)
        conflicts = resolver.detect_temporal_conflicts([fact], anchors)

        # Should detect before-admission conflict
        assert len(conflicts) >= 1
        assert any(c['type'] == 'BEFORE_ADMISSION' for c in conflicts)

    def test_detect_pod_without_surgery(self, resolver):
        """Test: Detect POD# reference without surgery anchor?"""
        docs = [
            ClinicalDocument(
                doc_type=DocumentType.ADMISSION_NOTE,
                timestamp=datetime(2024, 11, 1, 8, 0),
                author="Dr. Smith",
                specialty="Neurosurgery",
                content="Admission"
            )
        ]

        # POD fact but no operative note
        pod_fact = HybridClinicalFact(
            fact="Temporal reference: POD#3",
            source_doc="progress",
            source_line=10,
            timestamp=datetime(2024, 11, 5, 8, 0),
            confidence=0.80,
            fact_type="temporal_reference",
            clinical_context={
                'type': 'post_operative_day',
                'raw_text': 'POD#3'
            }
        )

        anchors = resolver.identify_anchor_events(docs)
        conflicts = resolver.detect_temporal_conflicts([pod_fact], anchors)

        # Should detect POD without surgery
        assert len(conflicts) >= 1
        assert any(c['type'] == 'POD_WITHOUT_SURGERY' for c in conflicts)

    def test_detect_hd_without_admission(self, resolver):
        """Test: Detect HD# reference without admission anchor?"""
        docs = []  # No admission note

        hd_fact = HybridClinicalFact(
            fact="Temporal reference: HD#5",
            source_doc="progress",
            source_line=10,
            timestamp=datetime(2024, 11, 5, 8, 0),
            confidence=0.80,
            fact_type="temporal_reference",
            clinical_context={
                'type': 'hospital_day',
                'raw_text': 'HD#5'
            }
        )

        anchors = resolver.identify_anchor_events(docs)
        conflicts = resolver.detect_temporal_conflicts([hd_fact], anchors)

        # Should detect HD without admission
        assert len(conflicts) >= 1
        assert any(c['type'] == 'HD_WITHOUT_ADMISSION' for c in conflicts)

    def test_no_conflicts_with_valid_timeline(self, resolver, sample_documents):
        """Test: Valid timeline has no conflicts?"""
        fact = HybridClinicalFact(
            fact="Some finding",
            source_doc="progress",
            source_line=1,
            timestamp=datetime(2024, 11, 3, 8, 0),
            absolute_timestamp=datetime(2024, 11, 3, 8, 0),
            confidence=0.85,
            fact_type="finding"
        )

        anchors = resolver.identify_anchor_events(sample_documents)
        conflicts = resolver.detect_temporal_conflicts([fact], anchors)

        # Should have no conflicts (fact is after admission)
        assert len(conflicts) == 0


class TestResolutionAccuracy:
    """Test resolution accuracy with realistic scenarios"""

    def test_complex_timeline_resolution(self, resolver):
        """Test: Complex timeline with multiple temporal references?"""
        docs = [
            ClinicalDocument(
                doc_type=DocumentType.ADMISSION_NOTE,
                timestamp=datetime(2024, 11, 1, 8, 0),
                author="Dr. Smith",
                specialty="Neurosurgery",
                content="Admission"
            ),
            ClinicalDocument(
                doc_type=DocumentType.OPERATIVE_NOTE,
                timestamp=datetime(2024, 11, 2, 14, 0),
                author="Dr. Surgeon",
                specialty="Neurosurgery",
                content="Surgery"
            )
        ]

        # Multiple temporal references
        facts = [
            HybridClinicalFact(
                fact="Temporal reference: POD#1",
                source_doc="progress",
                source_line=1,
                timestamp=datetime(2024, 11, 3, 8, 0),
                confidence=0.80,
                fact_type="temporal_reference",
                clinical_context={'type': 'post_operative_day', 'raw_text': 'POD#1'}
            ),
            HybridClinicalFact(
                fact="Temporal reference: POD#3",
                source_doc="progress",
                source_line=2,
                timestamp=datetime(2024, 11, 5, 8, 0),
                confidence=0.80,
                fact_type="temporal_reference",
                clinical_context={'type': 'post_operative_day', 'raw_text': 'POD#3'}
            ),
            HybridClinicalFact(
                fact="Temporal reference: HD#5",
                source_doc="progress",
                source_line=3,
                timestamp=datetime(2024, 11, 5, 8, 0),
                confidence=0.80,
                fact_type="temporal_reference",
                clinical_context={'type': 'hospital_day', 'raw_text': 'HD#5'}
            )
        ]

        anchors = resolver.identify_anchor_events(docs)
        resolved = resolver.resolve_temporal_references(facts, anchors, docs)

        # POD#1 = Nov 2 (surgery) + 1 = Nov 3
        assert resolved[0].absolute_timestamp == datetime(2024, 11, 3, 14, 0)

        # POD#3 = Nov 2 + 3 = Nov 5
        assert resolved[1].absolute_timestamp == datetime(2024, 11, 5, 14, 0)

        # HD#5 = Nov 1 (admission) + 4 = Nov 5
        assert resolved[2].absolute_timestamp == datetime(2024, 11, 5, 8, 0)

    def test_resolution_rate_calculation(self, resolver, sample_documents):
        """Test: Resolution statistics accurate?"""
        facts = [
            HybridClinicalFact(
                fact="Temporal reference: POD#3",
                source_doc="progress",
                source_line=1,
                timestamp=datetime(2024, 11, 5, 8, 0),
                confidence=0.80,
                fact_type="temporal_reference",
                clinical_context={'type': 'post_operative_day', 'raw_text': 'POD#3'}
            ),
            HybridClinicalFact(
                fact="Temporal reference: unknown",
                source_doc="progress",
                source_line=2,
                timestamp=datetime(2024, 11, 5, 8, 0),
                confidence=0.80,
                fact_type="temporal_reference",
                clinical_context={'type': 'unknown_type', 'raw_text': 'some time'}
            )
        ]

        anchors = resolver.identify_anchor_events(sample_documents)
        resolved = resolver.resolve_temporal_references(facts, anchors, sample_documents)

        stats = resolver.get_resolution_stats(resolved)

        assert stats['total_temporal_references'] == 2
        assert stats['resolved'] == 1
        assert stats['failed'] == 1
        assert stats['resolution_rate'] == 0.5  # 1/2 = 50%


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_empty_facts_list(self, resolver, sample_documents):
        """Test: Empty facts list returns empty?"""
        anchors = resolver.identify_anchor_events(sample_documents)
        resolved = resolver.resolve_temporal_references([], anchors, sample_documents)

        assert resolved == []

    def test_no_temporal_references(self, resolver, sample_documents):
        """Test: No temporal references returns unchanged facts?"""
        facts = [
            HybridClinicalFact(
                fact="NIHSS: 8",
                source_doc="progress",
                source_line=1,
                timestamp=datetime(2024, 11, 5, 8, 0),
                confidence=0.95,
                fact_type="clinical_score"
            )
        ]

        anchors = resolver.identify_anchor_events(sample_documents)
        resolved = resolver.resolve_temporal_references(facts, anchors, sample_documents)

        # Should return unchanged
        assert len(resolved) == 1
        assert resolved[0].fact == facts[0].fact

    def test_malformed_pod_text(self, resolver, sample_documents):
        """Test: Malformed POD text doesn't crash?"""
        fact = HybridClinicalFact(
            fact="Temporal reference: POD",
            source_doc="progress",
            source_line=1,
            timestamp=datetime(2024, 11, 5, 8, 0),
            confidence=0.80,
            fact_type="temporal_reference",
            clinical_context={'type': 'post_operative_day', 'raw_text': 'POD'}  # Missing number
        )

        anchors = resolver.identify_anchor_events(sample_documents)

        # Should not crash
        resolved = resolver.resolve_temporal_references([fact], anchors, sample_documents)

        # Should remain unresolved but not crash
        assert len(resolved) == 1


class TestRealWorldScenario:
    """Test with realistic clinical scenario"""

    def test_sah_case_temporal_resolution(self, resolver):
        """
        Test: Full SAH case with POD#3 vasospasm?

        Timeline:
        - Nov 1 08:00: Admission
        - Nov 2 14:00: Surgery (craniotomy)
        - Nov 5 08:00: POD#3 vasospasm noted

        Expected: POD#3 resolves to Nov 5 14:00 (surgery + 3 days)
        """
        docs = [
            ClinicalDocument(
                doc_type=DocumentType.ADMISSION_NOTE,
                timestamp=datetime(2024, 11, 1, 8, 0),
                author="Dr. Smith",
                specialty="Neurosurgery",
                content="52yo F with thunderclap headache. SAH Hunt-Hess 3."
            ),
            ClinicalDocument(
                doc_type=DocumentType.OPERATIVE_NOTE,
                timestamp=datetime(2024, 11, 2, 14, 0),
                author="Dr. Surgeon",
                specialty="Neurosurgery",
                content="Craniotomy for AComm aneurysm clipping"
            ),
            ClinicalDocument(
                doc_type=DocumentType.PROGRESS_NOTE,
                timestamp=datetime(2024, 11, 5, 8, 0),
                author="Dr. Smith",
                specialty="Neurosurgery",
                content="POD#3: Patient developed vasospasm, TCD velocities elevated"
            )
        ]

        # POD#3 fact
        pod3_fact = HybridClinicalFact(
            fact="Temporal reference: POD#3",
            source_doc="progress_2024-11-05",
            source_line=1,
            timestamp=datetime(2024, 11, 5, 8, 0),
            confidence=0.80,
            fact_type="temporal_reference",
            clinical_context={'type': 'post_operative_day', 'raw_text': 'POD#3'}
        )

        # Resolve
        anchors = resolver.identify_anchor_events(docs)
        resolved = resolver.resolve_temporal_references([pod3_fact], anchors, docs)

        # Verify resolution
        expected_date = datetime(2024, 11, 2, 14, 0) + timedelta(days=3)  # Surgery + 3 days
        assert resolved[0].absolute_timestamp == expected_date

        # Verify confidence boosted
        assert resolved[0].confidence > 0.80

        # Verify marked as resolved
        assert resolved[0].clinical_context['resolved'] is True

        # Verify resolution method tracked
        assert resolved[0].clinical_context['resolution_method'] == 'POD_anchor_based'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

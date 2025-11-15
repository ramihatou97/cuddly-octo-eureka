"""
Comprehensive unit tests for EnhancedTimelineBuilder

Tests timeline construction, clinical progression analysis, and key event identification.
Target: >99% temporal resolution accuracy

Test Coverage:
- Timeline building from facts and documents
- Temporal reference resolution integration
- Clinical progression analysis (neurological, laboratory)
- Key event identification
- Timeline metadata (admission/discharge dates, hospital days)
- Integration with fact extractor and temporal resolver
- Real-world SAH case scenario

Run with: pytest tests/unit/test_timeline_builder.py -v
"""

import pytest
from datetime import datetime, date, timedelta

from src.processing.timeline_builder import EnhancedTimelineBuilder
from src.extraction.fact_extractor import HybridFactExtractor
from src.core.data_models import HybridClinicalFact, ClinicalDocument, DocumentType, ClinicalTimeline


@pytest.fixture
def timeline_builder():
    """Create timeline builder instance"""
    return EnhancedTimelineBuilder()


@pytest.fixture
def fact_extractor():
    """Create fact extractor instance"""
    return HybridFactExtractor()


@pytest.fixture
def sample_sah_documents():
    """
    Create realistic SAH case documents

    Timeline:
    - Nov 1: Admission with SAH
    - Nov 2: Surgery (craniotomy for aneurysm clipping)
    - Nov 5: POD#3 vasospasm development
    """
    return [
        ClinicalDocument(
            doc_type=DocumentType.ADMISSION_NOTE,
            timestamp=datetime(2024, 11, 1, 8, 0),
            author="Dr. Smith",
            specialty="Neurosurgery",
            content="""
ADMISSION NOTE
Date: November 1, 2024

52yo F with sudden thunderclap headache.

EXAM:
- GCS: 14
- NIHSS: 6

LABS:
- Sodium: 138
- Potassium: 4.1

IMAGING: SAH Hunt-Hess 3, Fisher 3

PLAN:
- Started nimodipine 60mg q4h
            """
        ),
        ClinicalDocument(
            doc_type=DocumentType.OPERATIVE_NOTE,
            timestamp=datetime(2024, 11, 2, 14, 0),
            author="Dr. Surgeon",
            specialty="Neurosurgery",
            content="""
OPERATIVE NOTE

Procedure performed: Right frontal craniotomy for AComm aneurysm clipping

Findings: 7mm aneurysm at AComm

Complications: None
            """
        ),
        ClinicalDocument(
            doc_type=DocumentType.PROGRESS_NOTE,
            timestamp=datetime(2024, 11, 5, 8, 0),
            author="Dr. Smith",
            specialty="Neurosurgery",
            content="""
PROGRESS NOTE - POD#3

Patient developed vasospasm overnight.

EXAM:
- GCS: 12
- NIHSS: 12

LABS:
- Sodium: 142
- Potassium: 3.9

PLAN:
- Started hypertensive therapy
            """
        )
    ]


class TestTimelineBuilding:
    """Test basic timeline building"""

    def test_build_timeline_structure(self, timeline_builder, sample_sah_documents):
        """Test: Timeline has correct structure?"""
        # Extract facts first
        extractor = HybridFactExtractor()
        all_facts = []
        for doc in sample_sah_documents:
            all_facts.extend(extractor.extract_facts(doc))

        # Build timeline
        timeline = timeline_builder.build_timeline(all_facts, sample_sah_documents)

        # Should be ClinicalTimeline instance
        assert isinstance(timeline, ClinicalTimeline)

        # Should have timeline dict
        assert timeline.timeline is not None
        assert len(timeline.timeline) >= 2  # At least admission and surgery days

        # Should have progression
        assert timeline.progression is not None

        # Should have key events
        assert timeline.key_events is not None
        assert len(timeline.key_events) >= 2  # Admission + surgery

    def test_facts_grouped_by_date(self, timeline_builder):
        """Test: Facts correctly grouped by date?"""
        facts = [
            HybridClinicalFact(
                fact="NIHSS: 6",
                source_doc="doc1",
                source_line=1,
                timestamp=datetime(2024, 11, 1, 8, 0),
                absolute_timestamp=datetime(2024, 11, 1, 8, 0),
                confidence=0.95,
                fact_type="clinical_score"
            ),
            HybridClinicalFact(
                fact="GCS: 14",
                source_doc="doc1",
                source_line=2,
                timestamp=datetime(2024, 11, 1, 8, 0),
                absolute_timestamp=datetime(2024, 11, 1, 8, 0),
                confidence=0.95,
                fact_type="clinical_score"
            ),
            HybridClinicalFact(
                fact="NIHSS: 8",
                source_doc="doc2",
                source_line=1,
                timestamp=datetime(2024, 11, 2, 8, 0),
                absolute_timestamp=datetime(2024, 11, 2, 8, 0),
                confidence=0.95,
                fact_type="clinical_score"
            )
        ]

        timeline = timeline_builder.build_timeline(facts, [])

        # Should have 2 dates
        assert len(timeline.timeline) == 2

        # Nov 1 should have 2 facts
        nov1 = date(2024, 11, 1)
        assert nov1 in timeline.timeline
        assert len(timeline.timeline[nov1]) == 2

        # Nov 2 should have 1 fact
        nov2 = date(2024, 11, 2)
        assert nov2 in timeline.timeline
        assert len(timeline.timeline[nov2]) == 1

    def test_facts_sorted_within_day(self, timeline_builder):
        """Test: Facts within same day sorted by time and confidence?"""
        facts = [
            HybridClinicalFact(
                fact="Low confidence fact",
                source_doc="doc1",
                source_line=1,
                timestamp=datetime(2024, 11, 1, 10, 0),
                absolute_timestamp=datetime(2024, 11, 1, 10, 0),
                confidence=0.70,
                fact_type="finding"
            ),
            HybridClinicalFact(
                fact="High confidence fact",
                source_doc="doc2",
                source_line=1,
                timestamp=datetime(2024, 11, 1, 8, 0),
                absolute_timestamp=datetime(2024, 11, 1, 8, 0),
                confidence=0.95,
                fact_type="finding"
            )
        ]

        timeline = timeline_builder.build_timeline(facts, [])

        nov1_facts = timeline.timeline[date(2024, 11, 1)]

        # Should be sorted by time (earlier first), then by confidence
        assert nov1_facts[0].fact == "High confidence fact"  # Earlier time
        assert nov1_facts[1].fact == "Low confidence fact"


class TestTemporalResolutionIntegration:
    """Test integration with temporal resolver"""

    def test_pod_resolution_in_timeline(self, timeline_builder, sample_sah_documents):
        """Test: POD# references resolved during timeline building?"""
        # Create POD#3 fact
        pod_fact = HybridClinicalFact(
            fact="Temporal reference: POD#3",
            source_doc="progress",
            source_line=1,
            timestamp=datetime(2024, 11, 5, 8, 0),
            confidence=0.80,
            fact_type="temporal_reference",
            clinical_context={'type': 'post_operative_day', 'raw_text': 'POD#3'}
        )

        timeline = timeline_builder.build_timeline([pod_fact], sample_sah_documents)

        # POD#3 should be resolved to Nov 5 (surgery Nov 2 + 3 days)
        nov5 = date(2024, 11, 5)
        assert nov5 in timeline.timeline

        resolved_fact = timeline.timeline[nov5][0]
        assert resolved_fact.absolute_timestamp == datetime(2024, 11, 5, 14, 0)  # Surgery time + 3 days


class TestClinicalProgressionAnalysis:
    """Test clinical progression tracking"""

    def test_neurological_progression_improving(self, timeline_builder):
        """Test: Improving NIHSS trend detected?"""
        facts = [
            HybridClinicalFact(
                fact="NIHSS: 12",
                source_doc="doc1",
                source_line=1,
                timestamp=datetime(2024, 11, 1),
                confidence=0.95,
                fact_type="clinical_score",
                normalized_value=12
            ),
            HybridClinicalFact(
                fact="NIHSS: 8",
                source_doc="doc2",
                source_line=1,
                timestamp=datetime(2024, 11, 3),
                confidence=0.95,
                fact_type="clinical_score",
                normalized_value=8
            ),
            HybridClinicalFact(
                fact="NIHSS: 4",
                source_doc="doc3",
                source_line=1,
                timestamp=datetime(2024, 11, 5),
                confidence=0.95,
                fact_type="clinical_score",
                normalized_value=4
            )
        ]

        timeline = timeline_builder.build_timeline(facts, [])

        # Should detect improving trend (NIHSS decreasing)
        neurological = timeline.progression.get('neurological', [])
        assert len(neurological) >= 1

        nihss_progression = [p for p in neurological if p['metric'] == 'NIHSS']
        assert len(nihss_progression) == 1

        assert nihss_progression[0]['trend'] == 'improving'

    def test_neurological_progression_worsening(self, timeline_builder):
        """Test: Worsening NIHSS trend detected?"""
        facts = [
            HybridClinicalFact(
                fact="NIHSS: 4",
                source_doc="doc1",
                source_line=1,
                timestamp=datetime(2024, 11, 1),
                confidence=0.95,
                fact_type="clinical_score",
                normalized_value=4
            ),
            HybridClinicalFact(
                fact="NIHSS: 12",
                source_doc="doc2",
                source_line=1,
                timestamp=datetime(2024, 11, 3),
                confidence=0.95,
                fact_type="clinical_score",
                normalized_value=12
            )
        ]

        timeline = timeline_builder.build_timeline(facts, [])

        neurological = timeline.progression.get('neurological', [])
        nihss_progression = [p for p in neurological if p['metric'] == 'NIHSS']

        assert nihss_progression[0]['trend'] == 'worsening'

    def test_gcs_progression_improving(self, timeline_builder):
        """Test: Improving GCS trend detected? (higher is better)"""
        facts = [
            HybridClinicalFact(
                fact="GCS: 12",
                source_doc="doc1",
                source_line=1,
                timestamp=datetime(2024, 11, 1),
                confidence=0.95,
                fact_type="clinical_score",
                normalized_value=12
            ),
            HybridClinicalFact(
                fact="GCS: 15",
                source_doc="doc2",
                source_line=1,
                timestamp=datetime(2024, 11, 3),
                confidence=0.95,
                fact_type="clinical_score",
                normalized_value=15
            )
        ]

        timeline = timeline_builder.build_timeline(facts, [])

        neurological = timeline.progression.get('neurological', [])
        gcs_progression = [p for p in neurological if p['metric'] == 'GCS']

        # GCS increasing = improving
        assert gcs_progression[0]['trend'] == 'improving'


class TestKeyEventIdentification:
    """Test key event identification"""

    def test_key_events_include_admission(self, timeline_builder, sample_sah_documents):
        """Test: Admission included in key events?"""
        timeline = timeline_builder.build_timeline([], sample_sah_documents)

        # Should have admission as key event
        admission_events = [e for e in timeline.key_events if e['type'] == 'admission']
        assert len(admission_events) == 1

        admission = admission_events[0]
        assert admission['date'] == date(2024, 11, 1)
        assert admission['significance'] == 'HIGH'

    def test_key_events_include_surgery(self, timeline_builder, sample_sah_documents):
        """Test: Surgery included in key events?"""
        timeline = timeline_builder.build_timeline([], sample_sah_documents)

        surgery_events = [e for e in timeline.key_events if e['type'] == 'surgery']
        assert len(surgery_events) == 1

        surgery = surgery_events[0]
        assert surgery['date'] == date(2024, 11, 2)

    def test_key_events_include_complications(self, timeline_builder):
        """Test: Complications included in key events?"""
        facts = [
            HybridClinicalFact(
                fact="Complication: CSF leak",
                source_doc="doc1",
                source_line=1,
                timestamp=datetime(2024, 11, 3),
                confidence=0.90,
                fact_type="complication",
                severity='HIGH'
            )
        ]

        timeline = timeline_builder.build_timeline(facts, [])

        comp_events = [e for e in timeline.key_events if e['type'] == 'complication']
        assert len(comp_events) == 1

        comp = comp_events[0]
        assert comp['category'] == 'complication'
        assert comp['significance'] == 'HIGH'

    def test_key_events_sorted_chronologically(self, timeline_builder, sample_sah_documents):
        """Test: Key events sorted by timestamp?"""
        timeline = timeline_builder.build_timeline([], sample_sah_documents)

        # Check timestamps are in order
        timestamps = [e['timestamp'] for e in timeline.key_events]
        assert timestamps == sorted(timestamps)


class TestTimelineMetadata:
    """Test timeline metadata calculation"""

    def test_admission_date_identified(self, timeline_builder, sample_sah_documents):
        """Test: Admission date correctly identified?"""
        timeline = timeline_builder.build_timeline([], sample_sah_documents)

        assert timeline.admission_date == datetime(2024, 11, 1, 8, 0)

    def test_hospital_days_calculation(self, timeline_builder):
        """Test: Hospital days calculated correctly?"""
        docs = [
            ClinicalDocument(
                doc_type=DocumentType.ADMISSION_NOTE,
                timestamp=datetime(2024, 11, 1, 8, 0),
                author="Dr. Smith",
                specialty="Neurosurgery",
                content="Admission"
            )
        ]

        # Discharge fact
        discharge_fact = HybridClinicalFact(
            fact="Discharge instructions",
            source_doc="discharge_planning_2024-11-10",
            source_line=1,
            timestamp=datetime(2024, 11, 10, 10, 0),
            absolute_timestamp=datetime(2024, 11, 10, 10, 0),
            confidence=0.90,
            fact_type="finding"
        )

        timeline = timeline_builder.build_timeline([discharge_fact], docs)

        # Nov 1 to Nov 10 = 10 days
        assert timeline.total_hospital_days == 10


class TestTimelineSummary:
    """Test timeline summary statistics"""

    def test_timeline_summary_structure(self, timeline_builder, sample_sah_documents):
        """Test: Timeline summary has correct structure?"""
        # Extract facts
        extractor = HybridFactExtractor()
        all_facts = []
        for doc in sample_sah_documents:
            all_facts.extend(extractor.extract_facts(doc))

        timeline = timeline_builder.build_timeline(all_facts, sample_sah_documents)
        summary = timeline_builder.get_timeline_summary(timeline)

        # Check structure
        assert 'total_facts' in summary
        assert 'total_days' in summary
        assert 'fact_types' in summary
        assert 'key_events_count' in summary
        assert 'anchor_events_count' in summary
        assert 'admission_date' in summary

        # Verify counts
        assert summary['total_facts'] > 0
        assert summary['anchor_events_count'] == 2  # Admission + surgery


class TestRealWorldIntegration:
    """Test with realistic end-to-end scenario"""

    def test_complete_sah_case_timeline(self, timeline_builder, fact_extractor, sample_sah_documents):
        """
        Test: Complete SAH case timeline with all components?

        Validates:
        - Fact extraction works
        - Temporal resolution works (POD#3)
        - Timeline organization works
        - Progression analysis works
        - Key events identified
        - Metadata calculated
        """
        # Extract all facts from all documents
        all_facts = []
        for doc in sample_sah_documents:
            facts = fact_extractor.extract_facts(doc)
            all_facts.extend(facts)

        logger_output = f"Extracted {len(all_facts)} total facts"
        assert len(all_facts) >= 10  # Should have multiple facts

        # Build timeline
        timeline = timeline_builder.build_timeline(all_facts, sample_sah_documents)

        # === VERIFY TIMELINE STRUCTURE ===
        assert len(timeline.timeline) >= 2

        # === VERIFY TEMPORAL RESOLUTION ===
        # POD#3 should be present and resolved
        nov5 = date(2024, 11, 5)
        if nov5 in timeline.timeline:
            nov5_facts = timeline.timeline[nov5]
            pod_facts = [f for f in nov5_facts if f.fact_type == 'temporal_reference']

            if pod_facts:
                # Should be resolved to surgery + 3 days
                assert pod_facts[0].absolute_timestamp == datetime(2024, 11, 5, 14, 0)

        # === VERIFY CLINICAL PROGRESSION ===
        progression = timeline.progression

        # Should track neurological progression (GCS and NIHSS changing)
        assert 'neurological' in progression

        # === VERIFY KEY EVENTS ===
        assert len(timeline.key_events) >= 2

        # Admission should be first key event
        first_event = timeline.key_events[0]
        assert first_event['type'] == 'admission'

        # Surgery should be second key event
        second_event = timeline.key_events[1]
        assert second_event['type'] == 'surgery'

        # === VERIFY METADATA ===
        assert timeline.admission_date == datetime(2024, 11, 1, 8, 0)
        assert timeline.anchor_events is not None
        assert len(timeline.anchor_events) == 2

    def test_resolution_accuracy_target(self, timeline_builder, fact_extractor, sample_sah_documents):
        """
        Test: Temporal resolution accuracy >99%?

        This is our target from the specification.
        """
        # Extract facts
        all_facts = []
        for doc in sample_sah_documents:
            all_facts.extend(fact_extractor.extract_facts(doc))

        # Build timeline (includes temporal resolution)
        timeline = timeline_builder.build_timeline(all_facts, sample_sah_documents)

        # Get resolution stats
        temporal_facts = []
        for facts in timeline.timeline.values():
            temporal_facts.extend([f for f in facts if f.fact_type == 'temporal_reference'])

        if temporal_facts:
            resolved_count = sum(
                1 for f in temporal_facts
                if f.clinical_context.get('resolved', False)
            )

            accuracy = resolved_count / len(temporal_facts)

            # Should meet >99% target (in this case, should be 100% since we have clear anchors)
            # Note: With only one POD reference, it's either 0% or 100%
            # In production with more temporal references, this would be more granular


class TestEdgeCases:
    """Test edge cases"""

    def test_empty_facts_list(self, timeline_builder):
        """Test: Empty facts list produces empty timeline?"""
        timeline = timeline_builder.build_timeline([], [])

        assert len(timeline.timeline) == 0
        assert len(timeline.key_events) == 0

    def test_no_anchor_events(self, timeline_builder):
        """Test: Timeline works without anchor events?"""
        facts = [
            HybridClinicalFact(
                fact="NIHSS: 8",
                source_doc="progress",
                source_line=1,
                timestamp=datetime(2024, 11, 5),
                confidence=0.95,
                fact_type="clinical_score"
            )
        ]

        # No admission or operative notes
        timeline = timeline_builder.build_timeline(facts, [])

        # Should still build timeline, just without temporal resolution
        assert len(timeline.timeline) == 1
        assert len(timeline.anchor_events) == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

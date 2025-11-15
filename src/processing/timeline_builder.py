"""
Clinical Timeline Builder with Progression Analysis

Builds comprehensive clinical timeline from extracted facts with:
- Temporal ordering and resolution
- Clinical progression tracking
- Key event identification
- Timeline conflict resolution

Integrates:
- complete_1: Timeline structure and clinical progression analysis (lines 393-463)
- v2: Temporal resolution with anchor events
- Hybrid: Enhanced with both approaches

Target Accuracy: >99% for temporal ordering
"""

import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, date
from collections import defaultdict

from ..core.data_models import HybridClinicalFact, ClinicalDocument, ClinicalTimeline
from ..extraction.temporal_resolver import TemporalResolver

logger = logging.getLogger(__name__)


class EnhancedTimelineBuilder:
    """
    Build comprehensive clinical timeline with progression analysis

    Process:
    1. Identify anchor events (admission, surgery dates)
    2. Resolve temporal references (POD#, HD#)
    3. Group facts by date
    4. Sort by confidence and time
    5. Analyze clinical progression
    6. Identify key events
    7. Detect timeline conflicts
    """

    def __init__(self):
        """Initialize timeline builder with temporal resolver"""
        self.temporal_resolver = TemporalResolver()
        logger.info("Enhanced timeline builder initialized")

    # ========================================================================
    # MAIN TIMELINE BUILDING
    # ========================================================================

    def build_timeline(
        self,
        facts: List[HybridClinicalFact],
        documents: List[ClinicalDocument]
    ) -> ClinicalTimeline:
        """
        Build comprehensive clinical timeline

        Args:
            facts: List of extracted facts
            documents: List of clinical documents

        Returns:
            ClinicalTimeline with organized facts, progression analysis, and key events

        Source: complete_1 engine lines 395-425, enhanced with v2 temporal resolution
        """
        logger.info(f"Building timeline from {len(facts)} facts and {len(documents)} documents")

        # Step 1: Identify anchor events
        anchors = self.temporal_resolver.identify_anchor_events(documents)

        # Step 2: Resolve temporal references
        resolved_facts = self.temporal_resolver.resolve_temporal_references(
            facts, anchors, documents
        )

        # Step 3: Build chronological timeline
        timeline_dict = self._build_chronological_timeline(resolved_facts)

        # Step 4: Identify clinical progression patterns
        progression = self._identify_clinical_progression(timeline_dict)

        # Step 5: Identify key events
        key_events = self._identify_key_events(timeline_dict, anchors)

        # Step 6: Calculate timeline metadata
        admission_date, discharge_date = self._calculate_timeline_bounds(timeline_dict, anchors)
        total_days = self._calculate_hospital_days(admission_date, discharge_date)

        # Step 7: Detect temporal conflicts
        temporal_conflicts = self.temporal_resolver.detect_temporal_conflicts(resolved_facts, anchors)

        # Construct ClinicalTimeline object
        clinical_timeline = ClinicalTimeline(
            timeline=timeline_dict,
            progression=progression,
            key_events=key_events,
            anchor_events=anchors,
            admission_date=admission_date,
            discharge_date=discharge_date,
            total_hospital_days=total_days
        )

        logger.info(f"Timeline built successfully: {len(timeline_dict)} days, "
                   f"{len(key_events)} key events, {len(temporal_conflicts)} conflicts")

        return clinical_timeline

    def _build_chronological_timeline(
        self,
        facts: List[HybridClinicalFact]
    ) -> Dict[date, List[HybridClinicalFact]]:
        """
        Build chronological timeline grouped by date

        Source: complete_1 engine lines 400-413
        """
        timeline = defaultdict(list)

        # Group facts by date (using resolved absolute_timestamp)
        for fact in facts:
            date_key = fact.absolute_timestamp.date() if fact.absolute_timestamp else fact.timestamp.date()
            timeline[date_key].append(fact)

        # Sort each day's facts by time and confidence
        for date_key in timeline:
            timeline[date_key] = sorted(
                timeline[date_key],
                key=lambda x: (
                    x.absolute_timestamp if x.absolute_timestamp else x.timestamp,
                    -x.confidence  # Negative for descending confidence
                )
            )

        return dict(timeline)

    # ========================================================================
    # CLINICAL PROGRESSION ANALYSIS
    # ========================================================================

    def _identify_clinical_progression(
        self,
        timeline: Dict[date, List[HybridClinicalFact]]
    ) -> Dict[str, List[Dict]]:
        """
        Identify patterns in clinical progression

        Tracks:
        - Neurological: Score changes (NIHSS, GCS, mRS)
        - Laboratory: Lab value trends
        - Complications: Onset and management
        - Interventions: Procedures and treatments

        Source: complete_1 engine lines 427-463
        Enhanced with v2's clinical concept analysis
        """
        progression = {
            'neurological': [],
            'laboratory': [],
            'complications': [],
            'interventions': []
        }

        # Track clinical scores over time
        scores_over_time = defaultdict(list)
        labs_over_time = defaultdict(list)

        for date_key in sorted(timeline.keys()):
            for fact in timeline[date_key]:
                # Track neurological scores
                if fact.fact_type == 'clinical_score':
                    score_name = fact.fact.split(':')[0]
                    score_value = fact.normalized_value if fact.normalized_value else fact.fact.split(':')[1].strip()

                    scores_over_time[score_name].append({
                        'date': date_key,
                        'value': score_value,
                        'source': fact.source_doc,
                        'confidence': fact.confidence
                    })

                # Track lab values (v2 enhancement: use normalized values)
                elif fact.fact_type == 'lab_value' and fact.normalized_value:
                    concept = fact.normalized_value
                    labs_over_time[concept.name].append({
                        'date': date_key,
                        'value': concept.value,
                        'severity': concept.severity,
                        'source': fact.source_doc
                    })

                # Track complications
                elif fact.fact_type == 'complication':
                    progression['complications'].append({
                        'date': date_key,
                        'complication': fact.fact,
                        'severity': fact.severity,
                        'source': fact.source_doc
                    })

                # Track interventions (procedures, major medications)
                elif fact.fact_type in ['procedure', 'recommendation']:
                    progression['interventions'].append({
                        'date': date_key,
                        'intervention': fact.fact,
                        'type': fact.fact_type,
                        'source': fact.source_doc
                    })

        # Analyze score trends (complete_1 approach)
        for score_name, values in scores_over_time.items():
            if len(values) > 1:
                trend = self._analyze_score_trend(score_name, values)
                progression['neurological'].append({
                    'metric': score_name,
                    'trend': trend,
                    'values': values
                })

        # Analyze lab trends (v2 enhancement with knowledge base)
        for lab_name, values in labs_over_time.items():
            if len(values) > 1:
                # Use knowledge base for trend interpretation
                from ..core.knowledge_base import ClinicalKnowledgeBase
                kb = ClinicalKnowledgeBase()

                value_tuples = [(v['date'], v['value']) for v in values]
                trend = kb.interpret_lab_trend(lab_name, value_tuples)

                progression['laboratory'].append({
                    'lab': lab_name,
                    'trend': trend,
                    'values': values
                })

        return progression

    def _analyze_score_trend(self, score_name: str, values: List[Dict]) -> str:
        """
        Analyze trend in clinical scores

        For scores where lower is better (NIHSS, mRS):
        - Decreasing = improving
        - Increasing = worsening

        For scores where higher is better (GCS):
        - Increasing = improving
        - Decreasing = worsening

        Args:
            score_name: Name of clinical score
            values: List of score values over time

        Returns:
            Trend string: 'improving', 'worsening', 'stable'
        """
        if len(values) < 2:
            return 'insufficient_data'

        first_val = values[0]['value']
        last_val = values[-1]['value']

        # Convert to int if possible
        try:
            first_val = int(first_val) if isinstance(first_val, str) else first_val
            last_val = int(last_val) if isinstance(last_val, str) else last_val
        except (ValueError, TypeError):
            return 'unable_to_analyze'

        # Calculate change
        if abs(last_val - first_val) <= 1:  # Minimal change
            return 'stable'

        # Score-specific interpretation
        if score_name in ['NIHSS', 'mRS']:
            # Lower is better
            if last_val < first_val:
                return 'improving'
            else:
                return 'worsening'

        elif score_name == 'GCS':
            # Higher is better
            if last_val > first_val:
                return 'improving'
            else:
                return 'worsening'

        # Default: just report direction
        return 'increasing' if last_val > first_val else 'decreasing'

    # ========================================================================
    # KEY EVENT IDENTIFICATION
    # ========================================================================

    def _identify_key_events(
        self,
        timeline: Dict[date, List[HybridClinicalFact]],
        anchors: List[Dict]
    ) -> List[Dict]:
        """
        Identify key clinical events

        Key events include:
        - Admission and discharge
        - Surgeries
        - Complications
        - Critical lab values
        - Significant interventions

        Source: complete_1 engine lines 424
        """
        key_events = []

        # Add anchor events (admission, surgery)
        for anchor in anchors:
            key_events.append({
                'date': anchor['timestamp'].date(),
                'timestamp': anchor['timestamp'],
                'type': anchor['type'],
                'description': anchor['description'],
                'significance': 'HIGH',
                'category': 'milestone'
            })

        # Add complications
        for date_key, facts in timeline.items():
            complications = [f for f in facts if f.fact_type == 'complication']
            for comp in complications:
                key_events.append({
                    'date': date_key,
                    'timestamp': comp.absolute_timestamp,
                    'type': 'complication',
                    'description': comp.fact,
                    'significance': 'HIGH',
                    'category': 'complication'
                })

        # Add critical lab values
        for date_key, facts in timeline.items():
            critical_labs = [
                f for f in facts
                if f.fact_type == 'lab_value' and f.severity == 'CRITICAL'
            ]
            for lab in critical_labs:
                key_events.append({
                    'date': date_key,
                    'timestamp': lab.absolute_timestamp,
                    'type': 'critical_lab',
                    'description': lab.fact,
                    'significance': 'HIGH',
                    'category': 'laboratory'
                })

        # Add major procedures
        for date_key, facts in timeline.items():
            procedures = [f for f in facts if f.fact_type == 'procedure']
            for proc in procedures:
                key_events.append({
                    'date': date_key,
                    'timestamp': proc.absolute_timestamp,
                    'type': 'procedure',
                    'description': proc.fact,
                    'significance': 'HIGH',
                    'category': 'intervention'
                })

        # Sort by timestamp
        key_events = sorted(key_events, key=lambda x: x['timestamp'])

        return key_events

    # ========================================================================
    # TIMELINE METADATA CALCULATION
    # ========================================================================

    def _calculate_timeline_bounds(
        self,
        timeline: Dict[date, List[HybridClinicalFact]],
        anchors: List[Dict]
    ) -> Tuple[Optional[datetime], Optional[datetime]]:
        """
        Calculate admission and discharge dates

        Args:
            timeline: Date-keyed timeline
            anchors: Anchor events

        Returns:
            Tuple of (admission_date, discharge_date)
        """
        admission_date = None
        discharge_date = None

        # Get admission from anchors
        admission_anchors = [a for a in anchors if a['type'] == 'admission']
        if admission_anchors:
            admission_date = admission_anchors[0]['timestamp']

        # Get discharge from discharge planning docs
        discharge_facts = []
        for facts in timeline.values():
            discharge_facts.extend([
                f for f in facts
                if 'discharge' in f.source_doc.lower() and f.fact_type != 'temporal_reference'
            ])

        if discharge_facts:
            # Use latest discharge-related fact
            discharge_date = max(f.absolute_timestamp for f in discharge_facts)

        return admission_date, discharge_date

    def _calculate_hospital_days(
        self,
        admission_date: Optional[datetime],
        discharge_date: Optional[datetime]
    ) -> int:
        """
        Calculate total hospital days

        Args:
            admission_date: Admission datetime
            discharge_date: Discharge datetime

        Returns:
            Number of hospital days (0 if dates not available)
        """
        if not admission_date or not discharge_date:
            return 0

        delta = discharge_date - admission_date
        return delta.days + 1  # Include admission day

    # ========================================================================
    # UTILITY METHODS
    # ========================================================================

    def get_timeline_summary(self, timeline: ClinicalTimeline) -> Dict:
        """
        Get summary statistics about the timeline

        Returns:
            Dictionary with timeline metrics
        """
        total_facts = sum(len(facts) for facts in timeline.timeline.values())

        fact_types = defaultdict(int)
        for facts in timeline.timeline.values():
            for fact in facts:
                fact_types[fact.fact_type] += 1

        return {
            'total_facts': total_facts,
            'total_days': len(timeline.timeline),
            'fact_types': dict(fact_types),
            'key_events_count': len(timeline.key_events),
            'anchor_events_count': len(timeline.anchor_events),
            'admission_date': timeline.admission_date.isoformat() if timeline.admission_date else None,
            'discharge_date': timeline.discharge_date.isoformat() if timeline.discharge_date else None,
            'total_hospital_days': timeline.total_hospital_days
        }

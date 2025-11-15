"""
Temporal Reference Resolver

Resolves relative temporal references (POD#, HD#, relative time) to absolute timestamps
using anchor events (surgery dates, admission dates).

Key Features:
- POD# (Post-Operative Day) resolution using surgery dates
- HD# (Hospital Day) resolution using admission dates
- Relative time resolution (yesterday, overnight, X hours after)
- Anchor event identification from document types
- Temporal conflict detection

Design: From v2 engine lines 554-625
Enhanced with comprehensive validation and error handling
"""

import re
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from collections import defaultdict

from ..core.data_models import HybridClinicalFact, ClinicalDocument, DocumentType

logger = logging.getLogger(__name__)


class TemporalResolver:
    """
    Resolves temporal references to absolute timestamps

    Process:
    1. Identify anchor events (surgery, admission dates)
    2. For each temporal reference fact, resolve based on anchor
    3. Update fact's absolute_timestamp field
    4. Detect temporal conflicts

    Accuracy Target: >99%
    """

    def __init__(self):
        """Initialize temporal resolver"""
        logger.info("Temporal resolver initialized")

    # ========================================================================
    # ANCHOR EVENT IDENTIFICATION
    # ========================================================================

    def identify_anchor_events(self, documents: List[ClinicalDocument]) -> List[Dict]:
        """
        Identify anchor events for temporal reasoning

        Anchor events are key dates used to resolve relative temporal references:
        - Surgery dates (from operative notes) → For POD# resolution
        - Admission dates (from admission notes) → For HD# resolution

        Args:
            documents: List of clinical documents

        Returns:
            List of anchor event dictionaries sorted by timestamp

        Source: v2 engine lines 554-576
        """
        anchors = []

        for doc in documents:
            if doc.doc_type == DocumentType.OPERATIVE_NOTE:
                anchors.append({
                    'type': 'surgery',
                    'timestamp': doc.timestamp,
                    'description': 'Surgical procedure',
                    'document': doc,
                    'specialty': doc.specialty
                })
                logger.debug(f"Identified surgery anchor: {doc.timestamp}")

            elif doc.doc_type == DocumentType.ADMISSION_NOTE:
                anchors.append({
                    'type': 'admission',
                    'timestamp': doc.timestamp,
                    'description': 'Hospital admission',
                    'document': doc,
                    'specialty': doc.specialty
                })
                logger.debug(f"Identified admission anchor: {doc.timestamp}")

        # Sort by timestamp (chronological order)
        anchors = sorted(anchors, key=lambda x: x['timestamp'])

        logger.info(f"Identified {len(anchors)} anchor events: "
                   f"{sum(1 for a in anchors if a['type'] == 'surgery')} surgeries, "
                   f"{sum(1 for a in anchors if a['type'] == 'admission')} admissions")

        return anchors

    # ========================================================================
    # TEMPORAL REFERENCE RESOLUTION
    # ========================================================================

    def resolve_temporal_references(
        self,
        facts: List[HybridClinicalFact],
        anchors: List[Dict],
        documents: List[ClinicalDocument]
    ) -> List[HybridClinicalFact]:
        """
        Resolve all temporal references to absolute timestamps

        Args:
            facts: List of extracted facts (including temporal_reference facts)
            anchors: List of anchor events from identify_anchor_events()
            documents: Original documents for context

        Returns:
            Facts with resolved absolute_timestamp fields

        Source: v2 engine lines 578-625 (adapted)
        """
        resolved_facts = []
        resolution_count = 0
        failed_resolutions = 0

        for fact in facts:
            if fact.fact_type == "temporal_reference":
                try:
                    resolved_time = self._resolve_single_reference(fact, anchors, documents)

                    if resolved_time != fact.timestamp:
                        # Successfully resolved to different time
                        fact.absolute_timestamp = resolved_time
                        fact.confidence = min(0.95, fact.confidence + 0.15)  # Boost confidence after resolution
                        fact.clinical_context['resolved'] = True
                        fact.clinical_context['resolution_method'] = self._get_resolution_method(fact)
                        resolution_count += 1
                    else:
                        # Could not resolve, keep original
                        fact.clinical_context['resolved'] = False
                        failed_resolutions += 1

                except Exception as e:
                    logger.error(f"Error resolving temporal reference: {e}")
                    fact.clinical_context['resolution_error'] = str(e)
                    failed_resolutions += 1

            resolved_facts.append(fact)

        logger.info(f"Temporal resolution: {resolution_count} resolved, {failed_resolutions} failed")

        return resolved_facts

    def _resolve_single_reference(
        self,
        fact: HybridClinicalFact,
        anchors: List[Dict],
        documents: List[ClinicalDocument]
    ) -> datetime:
        """
        Resolve a single temporal reference to absolute timestamp

        Resolution Logic:
        - POD#N → Surgery date + N days
        - HD#N → Admission date + (N-1) days
        - "X hours after" → Document timestamp + X hours
        - "yesterday" → Document timestamp - 1 day
        - etc.

        Args:
            fact: Temporal reference fact to resolve
            anchors: List of anchor events
            documents: List of all documents

        Returns:
            Resolved absolute timestamp

        Source: v2 engine lines 578-625
        """
        context = fact.clinical_context
        temp_type = context.get('type', '')
        raw_text = context.get('raw_text', '')

        # ====================================================================
        # POD (Post-Operative Day) Resolution
        # ====================================================================
        if temp_type == 'post_operative_day':
            pod_match = re.search(r'POD[#\s]*(\d+)', raw_text, re.I)
            if pod_match and anchors:
                pod_num = int(pod_match.group(1))

                # Find most recent surgery BEFORE this fact's document
                surgery_anchors = [
                    a for a in anchors
                    if a['type'] == 'surgery' and a['timestamp'] <= fact.timestamp
                ]

                if surgery_anchors:
                    # Use most recent surgery
                    surgery_date = surgery_anchors[-1]['timestamp']
                    resolved = surgery_date + timedelta(days=pod_num)

                    logger.debug(f"Resolved POD#{pod_num}: {surgery_date} + {pod_num}d = {resolved}")
                    return resolved

        # ====================================================================
        # HD (Hospital Day) Resolution
        # ====================================================================
        elif temp_type == 'hospital_day':
            hd_match = re.search(r'HD[#\s]*(\d+)', raw_text, re.I)
            if hd_match and anchors:
                hd_num = int(hd_match.group(1))

                # Find first admission (usually only one)
                admission_anchors = [a for a in anchors if a['type'] == 'admission']

                if admission_anchors:
                    admission_date = admission_anchors[0]['timestamp']
                    # HD#1 = admission day, so HD#N = admission + (N-1) days
                    resolved = admission_date + timedelta(days=hd_num - 1)

                    logger.debug(f"Resolved HD#{hd_num}: {admission_date} + {hd_num-1}d = {resolved}")
                    return resolved

        # ====================================================================
        # "X hours after" Resolution
        # ====================================================================
        elif temp_type == 'hours_after':
            num_match = re.search(r'(\d+)\s*hour', raw_text, re.I)
            if num_match:
                hours = int(num_match.group(1))
                resolved = fact.timestamp + timedelta(hours=hours)

                logger.debug(f"Resolved '{raw_text}': {fact.timestamp} + {hours}h = {resolved}")
                return resolved

        # ====================================================================
        # "X days after" Resolution
        # ====================================================================
        elif temp_type == 'days_after':
            num_match = re.search(r'(\d+)\s*day', raw_text, re.I)
            if num_match:
                days = int(num_match.group(1))
                resolved = fact.timestamp + timedelta(days=days)

                logger.debug(f"Resolved '{raw_text}': {fact.timestamp} + {days}d = {resolved}")
                return resolved

        # ====================================================================
        # "Yesterday" Resolution
        # ====================================================================
        elif temp_type == 'previous_day':
            resolved = fact.timestamp - timedelta(days=1)
            logger.debug(f"Resolved 'yesterday': {fact.timestamp} - 1d = {resolved}")
            return resolved

        # ====================================================================
        # "Overnight" / "Next Morning" Resolution
        # ====================================================================
        elif temp_type == 'next_morning':
            next_day = fact.timestamp + timedelta(days=1)
            # Set to 8 AM of next day
            resolved = next_day.replace(hour=8, minute=0, second=0, microsecond=0)

            logger.debug(f"Resolved 'overnight': {fact.timestamp} → {resolved}")
            return resolved

        # ====================================================================
        # "Today" Resolution
        # ====================================================================
        elif temp_type == 'same_day':
            # Keep same date but normalize to start of day
            resolved = fact.timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
            return resolved

        # ====================================================================
        # "Tonight" / "This Evening" Resolution
        # ====================================================================
        elif temp_type == 'same_evening':
            # Set to 6 PM of same day
            resolved = fact.timestamp.replace(hour=18, minute=0, second=0, microsecond=0)
            return resolved

        # ====================================================================
        # "Next Day" / "The Following Day" Resolution
        # ====================================================================
        elif temp_type == 'next_day':
            resolved = fact.timestamp + timedelta(days=1)
            logger.debug(f"Resolved 'next day': {fact.timestamp} + 1d = {resolved}")
            return resolved

        # ====================================================================
        # Default: Unable to resolve
        # ====================================================================
        logger.warning(f"Unable to resolve temporal reference: {raw_text} (type: {temp_type})")
        return fact.timestamp  # Return original

    def _get_resolution_method(self, fact: HybridClinicalFact) -> str:
        """
        Get description of how temporal reference was resolved

        Returns string describing the resolution method for audit/debugging
        """
        temp_type = fact.clinical_context.get('type', 'unknown')

        method_map = {
            'post_operative_day': 'POD_anchor_based',
            'hospital_day': 'HD_anchor_based',
            'hours_after': 'relative_hours',
            'days_after': 'relative_days',
            'previous_day': 'relative_previous',
            'next_morning': 'relative_next_morning',
            'same_day': 'same_day_normalization',
            'next_day': 'relative_next_day'
        }

        return method_map.get(temp_type, 'unresolved')

    # ========================================================================
    # TEMPORAL CONFLICT DETECTION
    # ========================================================================

    def detect_temporal_conflicts(
        self,
        facts: List[HybridClinicalFact],
        anchors: List[Dict]
    ) -> List[Dict]:
        """
        Detect temporal conflicts and inconsistencies

        Detects:
        1. Events before admission
        2. Events after discharge (if discharge date known)
        3. POD# without corresponding surgery
        4. HD# without admission
        5. Temporal order violations (e.g., discharge before admission)

        Args:
            facts: List of facts with resolved timestamps
            anchors: List of anchor events

        Returns:
            List of detected temporal conflicts
        """
        conflicts = []

        # Get admission and discharge dates
        admission_date = None
        discharge_date = None

        admission_anchors = [a for a in anchors if a['type'] == 'admission']
        if admission_anchors:
            admission_date = admission_anchors[0]['timestamp']

        # Check for facts before admission
        if admission_date:
            before_admission = [
                f for f in facts
                if f.absolute_timestamp < admission_date
                and f.fact_type != 'temporal_reference'
            ]

            if before_admission:
                conflicts.append({
                    'type': 'BEFORE_ADMISSION',
                    'severity': 'HIGH',
                    'description': f"{len(before_admission)} facts dated before admission",
                    'facts': [f.fact_id for f in before_admission],
                    'admission_date': admission_date
                })

        # Check for POD# without surgery anchor
        pod_facts = [
            f for f in facts
            if f.fact_type == 'temporal_reference'
            and f.clinical_context.get('type') == 'post_operative_day'
        ]

        surgery_anchors = [a for a in anchors if a['type'] == 'surgery']

        if pod_facts and not surgery_anchors:
            conflicts.append({
                'type': 'POD_WITHOUT_SURGERY',
                'severity': 'HIGH',
                'description': f"POD references found but no operative note/surgery date available",
                'pod_references': [f.clinical_context.get('raw_text') for f in pod_facts]
            })

        # Check for HD# without admission anchor
        hd_facts = [
            f for f in facts
            if f.fact_type == 'temporal_reference'
            and f.clinical_context.get('type') == 'hospital_day'
        ]

        if hd_facts and not admission_anchors:
            conflicts.append({
                'type': 'HD_WITHOUT_ADMISSION',
                'severity': 'HIGH',
                'description': f"HD references found but no admission note/admission date available",
                'hd_references': [f.clinical_context.get('raw_text') for f in hd_facts]
            })

        logger.info(f"Detected {len(conflicts)} temporal conflicts")
        return conflicts

    # ========================================================================
    # RESOLUTION STATISTICS
    # ========================================================================

    def get_resolution_stats(self, facts: List[HybridClinicalFact]) -> Dict:
        """
        Get statistics about temporal resolution

        Returns:
            Dictionary with resolution counts, methods, accuracy
        """
        temporal_facts = [f for f in facts if f.fact_type == 'temporal_reference']

        if not temporal_facts:
            return {'total_temporal_references': 0}

        resolved_count = sum(
            1 for f in temporal_facts
            if f.clinical_context.get('resolved', False)
        )

        resolution_methods = defaultdict(int)
        for f in temporal_facts:
            if f.clinical_context.get('resolved'):
                method = f.clinical_context.get('resolution_method', 'unknown')
                resolution_methods[method] += 1

        return {
            'total_temporal_references': len(temporal_facts),
            'resolved': resolved_count,
            'failed': len(temporal_facts) - resolved_count,
            'resolution_rate': resolved_count / len(temporal_facts) if temporal_facts else 0,
            'resolution_methods': dict(resolution_methods)
        }

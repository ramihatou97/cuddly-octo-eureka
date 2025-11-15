"""
Clinical Knowledge Base for neurosurgical domain

Provides domain-specific medical knowledge including:
- Lab value normalization and interpretation
- Medication classification and monitoring requirements
- Temporal pattern recognition
- Clinical decision support rules

Adapted from: v2 engine lines 95-203
"""

from typing import Dict, List, Optional, Tuple
import re
from datetime import datetime
from .data_models import ClinicalConcept


class ClinicalKnowledgeBase:
    """
    Domain-specific medical knowledge for neurosurgical discharge summaries

    Provides structured clinical knowledge for:
    1. Lab value interpretation with severity grading
    2. Medication classification with indications/contraindications
    3. Temporal pattern recognition for date resolution
    4. Clinical decision support rules
    """

    def __init__(self):
        """Initialize knowledge base with domain data"""
        self._initialize_lab_ranges()
        self._initialize_medication_classes()
        self._initialize_temporal_patterns()
        self._initialize_clinical_scores()

    def _initialize_lab_ranges(self):
        """
        Initialize lab value reference ranges and critical thresholds
        Source: v2 engine lines 99-107
        """
        self.lab_ranges = {
            'sodium': {
                'range': (135, 145),
                'unit': 'mmol/L',
                'critical_low': 125,
                'critical_high': 155,
                'implications': {
                    'critical_low': 'Risk of seizures, altered mental status',
                    'low': 'Monitor for neurological symptoms',
                    'critical_high': 'Risk of central pontine myelinolysis with rapid correction'
                }
            },
            'potassium': {
                'range': (3.5, 5.0),
                'unit': 'mmol/L',
                'critical_low': 2.5,
                'critical_high': 6.5,
                'implications': {
                    'critical_low': 'Risk of cardiac arrhythmias, muscle weakness',
                    'low': 'Monitor cardiac rhythm',
                    'high': 'Risk of cardiac arrest',
                    'critical_high': 'Immediate treatment required - life-threatening'
                }
            },
            'glucose': {
                'range': (70, 110),
                'unit': 'mg/dL',
                'critical_low': 40,
                'critical_high': 500,
                'implications': {
                    'critical_low': 'Risk of seizures, loss of consciousness',
                    'low': 'Monitor for hypoglycemic symptoms',
                    'high': 'Risk of DKA, infection complications',
                    'critical_high': 'Hyperosmolar state risk'
                }
            },
            'hemoglobin': {
                'range': (12, 16),
                'unit': 'g/dL',
                'critical_low': 7,
                'critical_high': 20,
                'implications': {
                    'critical_low': 'Transfusion may be required',
                    'low': 'Monitor for symptoms of anemia',
                    'high': 'Risk of hyperviscosity',
                    'critical_high': 'Phlebotomy may be indicated'
                }
            },
            'platelets': {
                'range': (150, 400),
                'unit': 'K/uL',
                'critical_low': 50,
                'critical_high': 1000,
                'implications': {
                    'critical_low': 'High bleeding risk - consider transfusion',
                    'low': 'Monitor for bleeding',
                    'high': 'Monitor for thrombosis',
                    'critical_high': 'Risk of thrombosis - consider platelet reduction'
                }
            },
            'inr': {
                'range': (0.8, 1.2),
                'unit': '',
                'critical_low': 0.5,
                'critical_high': 5.0,
                'implications': {
                    'low': 'May indicate hypercoagulable state',
                    'high': 'Bleeding risk - review anticoagulation',
                    'critical_high': 'High bleeding risk - immediate management required'
                }
            },
            'wbc': {
                'range': (4.5, 11.0),
                'unit': 'K/uL',
                'critical_low': 2.0,
                'critical_high': 30.0,
                'implications': {
                    'critical_low': 'Severe immunosuppression - infection risk',
                    'low': 'Monitor for infection',
                    'high': 'Possible infection or inflammatory process',
                    'critical_high': 'Severe infection or leukemia - urgent evaluation'
                }
            },
            'creatinine': {
                'range': (0.6, 1.2),
                'unit': 'mg/dL',
                'critical_low': 0.3,
                'critical_high': 5.0,
                'implications': {
                    'high': 'Renal dysfunction - adjust medication doses',
                    'critical_high': 'Acute kidney injury - nephrology consultation'
                }
            }
        }

    def _initialize_medication_classes(self):
        """
        Initialize medication classification database
        Source: v2 engine lines 109-137
        Enhanced with additional neurosurgical medications
        """
        self.medication_classes = {
            # Vasospasm prevention/treatment
            'nimodipine': {
                'class': 'Calcium Channel Blocker',
                'subclass': 'Dihydropyridine',
                'indications': ['Vasospasm prophylaxis', 'SAH', 'Aneurysmal SAH'],
                'contraindications': ['Hypotension', 'Severe hepatic impairment'],
                'monitoring': ['Blood pressure', 'Heart rate', 'Hepatic function'],
                'high_risk': True
            },

            # Antiepileptics
            'levetiracetam': {
                'class': 'Antiepileptic',
                'subclass': 'SV2A ligand',
                'indications': ['Seizure prophylaxis', 'Post-craniotomy', 'Seizure disorder'],
                'contraindications': ['Hypersensitivity'],
                'monitoring': ['Renal function', 'Mood changes', 'Behavioral changes']
            },
            'phenytoin': {
                'class': 'Antiepileptic',
                'subclass': 'Sodium channel blocker',
                'indications': ['Seizure prophylaxis', 'Status epilepticus'],
                'contraindications': ['Heart block', 'Sinus bradycardia'],
                'monitoring': ['Phenytoin level', 'CBC', 'LFTs'],
                'high_risk': True
            },

            # Cerebral edema management
            'dexamethasone': {
                'class': 'Corticosteroid',
                'subclass': 'Glucocorticoid',
                'indications': ['Cerebral edema', 'Brain tumor', 'Elevated ICP'],
                'contraindications': ['Systemic infection', 'GI bleeding', 'Uncontrolled diabetes'],
                'monitoring': ['Glucose', 'Blood pressure', 'GI symptoms', 'Mood changes']
            },
            'mannitol': {
                'class': 'Osmotic diuretic',
                'indications': ['Elevated ICP', 'Cerebral edema', 'Herniation'],
                'contraindications': ['Anuria', 'Severe dehydration', 'Pulmonary edema'],
                'monitoring': ['Serum osmolality', 'Renal function', 'Electrolytes', 'Fluid balance'],
                'high_risk': True
            },

            # Anticoagulation (high risk)
            'heparin': {
                'class': 'Anticoagulant',
                'subclass': 'Unfractionated',
                'indications': ['DVT prophylaxis', 'DVT/PE treatment'],
                'contraindications': ['Active bleeding', 'Thrombocytopenia', 'Recent neurosurgery'],
                'monitoring': ['PTT', 'Platelet count', 'Signs of bleeding'],
                'high_risk': True
            },
            'enoxaparin': {
                'class': 'Anticoagulant',
                'subclass': 'Low molecular weight heparin',
                'indications': ['DVT prophylaxis', 'DVT/PE treatment'],
                'contraindications': ['Active bleeding', 'Severe renal impairment'],
                'monitoring': ['Renal function', 'Platelet count', 'Signs of bleeding'],
                'high_risk': True
            },
            'warfarin': {
                'class': 'Anticoagulant',
                'subclass': 'Vitamin K antagonist',
                'indications': ['DVT/PE', 'Atrial fibrillation', 'Mechanical valve'],
                'contraindications': ['Active bleeding', 'Pregnancy'],
                'monitoring': ['INR', 'Signs of bleeding', 'Drug interactions'],
                'high_risk': True
            },

            # Pain management
            'morphine': {
                'class': 'Opioid analgesic',
                'indications': ['Pain management', 'Post-operative pain'],
                'contraindications': ['Respiratory depression', 'Head injury with altered consciousness'],
                'monitoring': ['Respiratory rate', 'Pain level', 'Mental status'],
                'high_risk': True
            },
            'fentanyl': {
                'class': 'Opioid analgesic',
                'indications': ['Pain management', 'Procedural sedation'],
                'contraindications': ['Respiratory depression'],
                'monitoring': ['Respiratory rate', 'Blood pressure', 'Sedation level'],
                'high_risk': True
            },

            # Infection prophylaxis
            'vancomycin': {
                'class': 'Antibiotic',
                'subclass': 'Glycopeptide',
                'indications': ['MRSA coverage', 'Post-operative prophylaxis'],
                'contraindications': ['Hypersensitivity'],
                'monitoring': ['Trough levels', 'Renal function', 'Hearing']
            },
            'cefazolin': {
                'class': 'Antibiotic',
                'subclass': 'Cephalosporin (1st gen)',
                'indications': ['Surgical prophylaxis'],
                'contraindications': ['Beta-lactam allergy'],
                'monitoring': ['Allergic reactions', 'Renal function']
            }
        }

    def _initialize_temporal_patterns(self):
        """
        Initialize temporal pattern recognition rules
        Source: v2 engine lines 139-148
        """
        self.temporal_patterns = {
            r'POD[#\s]*(\d+)': 'post_operative_day',
            r'HD[#\s]*(\d+)': 'hospital_day',
            r'(\d+)\s*hour[s]?\s*(?:later|after|post)': 'hours_after',
            r'(\d+)\s*day[s]?\s*(?:later|after|post)': 'days_after',
            r'overnight': 'next_morning',
            r'this morning': 'today_morning',
            r'yesterday': 'previous_day',
            r'last night': 'previous_night',
            r'today': 'same_day',
            r'tonight': 'same_evening',
            r'the following day': 'next_day',
            r'two days (?:later|after)': 'two_days_after'
        }

    def _initialize_clinical_scores(self):
        """
        Initialize valid ranges for clinical scores
        From: complete_1 validation rules
        """
        self.clinical_score_ranges = {
            'NIHSS': (0, 42),
            'GCS': (3, 15),
            'mRS': (0, 6),
            'Hunt-Hess': (1, 5),
            'Fisher': (1, 4),
            'WFNS': (1, 5),
            'Spetzler-Martin': (1, 5)
        }

    # ============================================================================
    # PUBLIC METHODS
    # ============================================================================

    def normalize_lab_value(self, lab_name: str, value: float) -> ClinicalConcept:
        """
        Normalize and interpret lab values with clinical implications

        Args:
            lab_name: Name of the lab (e.g., "sodium", "potassium")
            value: Numeric value

        Returns:
            ClinicalConcept with normalized value, severity, and clinical implications

        Source: v2 engine lines 150-192
        """
        lab_name_lower = lab_name.lower()

        if lab_name_lower in self.lab_ranges:
            lab_info = self.lab_ranges[lab_name_lower]
            normal_range = lab_info['range']

            # Determine severity
            # Note: Using <= and >= for critical thresholds to include boundary values
            if value <= lab_info['critical_low']:
                severity = 'CRITICAL'
                implication_key = 'critical_low'
            elif value >= lab_info['critical_high']:
                severity = 'CRITICAL'
                implication_key = 'critical_high'
            elif value < normal_range[0]:
                severity = 'LOW'
                implication_key = 'low'
            elif value > normal_range[1]:
                severity = 'HIGH'
                implication_key = 'high'
            else:
                severity = 'NORMAL'
                implication_key = None

            # Get clinical implications
            implications = []
            if implication_key and implication_key in lab_info.get('implications', {}):
                implications.append(lab_info['implications'][implication_key])

            return ClinicalConcept(
                concept_type='lab',
                name=lab_name,
                value=value,
                unit=lab_info['unit'],
                normal_range=normal_range,
                severity=severity,
                clinical_implications=implications
            )

        # Unknown lab - return basic concept
        return ClinicalConcept(
            concept_type='lab',
            name=lab_name,
            value=value,
            severity='UNKNOWN'
        )

    def classify_medication(self, med_name: str) -> Dict:
        """
        Get medication classification and clinical context

        Args:
            med_name: Medication name

        Returns:
            Dictionary with class, indications, contraindications, and monitoring requirements

        Source: v2 engine lines 194-202
        Enhanced with high_risk flag
        """
        med_lower = med_name.lower()

        for key, info in self.medication_classes.items():
            if key in med_lower:
                return info

        # Unknown medication
        return {
            'class': 'Unknown',
            'monitoring': [],
            'high_risk': False
        }

    def is_high_risk_medication(self, med_name: str) -> bool:
        """
        Check if medication is high-risk

        High-risk medications include:
        - Anticoagulants
        - Opioids
        - Certain neurosurgical medications

        From: complete_1 engine lines 935-943
        """
        med_info = self.classify_medication(med_name)

        # Check if classified as high-risk
        if med_info.get('high_risk', False):
            return True

        # Additional pattern-based checking
        high_risk_patterns = [
            'warfarin', 'heparin', 'enoxaparin', 'insulin',
            'morphine', 'fentanyl', 'methotrexate',
            'tpa', 'alteplase', 'chemotherapy'
        ]

        med_lower = med_name.lower()
        return any(pattern in med_lower for pattern in high_risk_patterns)

    def get_temporal_pattern_type(self, text: str) -> Optional[Tuple[str, str]]:
        """
        Identify temporal pattern type from text

        Args:
            text: Text containing potential temporal reference

        Returns:
            Tuple of (pattern_type, matched_text) or None
        """
        for pattern, pattern_type in self.temporal_patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return pattern_type, match.group(0)
        return None

    def validate_clinical_score(self, score_name: str, value: int) -> Tuple[bool, Optional[str]]:
        """
        Validate that a clinical score is within acceptable range

        Args:
            score_name: Name of the clinical score
            value: Numeric value

        Returns:
            Tuple of (is_valid, error_message)
        """
        if score_name not in self.clinical_score_ranges:
            return True, None  # Unknown score, can't validate

        min_val, max_val = self.clinical_score_ranges[score_name]
        if not (min_val <= value <= max_val):
            return False, f"{score_name} score {value} outside valid range [{min_val}-{max_val}]"

        return True, None

    def get_medication_interactions(self, med_list: List[str]) -> List[Dict]:
        """
        Check for known medication interactions

        Args:
            med_list: List of medication names

        Returns:
            List of interaction warnings

        Note: This is a simplified implementation. In production, use a
        comprehensive drug interaction database.
        """
        interactions = []

        # Check for anticoagulant + recent neurosurgery
        has_anticoagulant = any(
            self.classify_medication(med).get('class') == 'Anticoagulant'
            for med in med_list
        )

        if has_anticoagulant:
            interactions.append({
                'severity': 'HIGH',
                'description': 'Anticoagulant use in neurosurgical patient - verify appropriateness',
                'recommendation': 'Review timing of anticoagulation initiation post-surgery'
            })

        # Check for multiple opioids
        opioid_count = sum(
            1 for med in med_list
            if 'opioid' in self.classify_medication(med).get('class', '').lower()
        )

        if opioid_count > 1:
            interactions.append({
                'severity': 'MEDIUM',
                'description': 'Multiple opioid medications',
                'recommendation': 'Monitor for excessive sedation and respiratory depression'
            })

        return interactions

    def interpret_lab_trend(self, lab_name: str, values: List[Tuple[datetime, float]]) -> Dict:
        """
        Interpret trend in lab values over time

        Args:
            lab_name: Name of the lab
            values: List of (datetime, value) tuples

        Returns:
            Dictionary with trend analysis
        """
        if len(values) < 2:
            return {'trend': 'insufficient_data'}

        # Sort by date
        sorted_values = sorted(values, key=lambda x: x[0])
        first_val = sorted_values[0][1]
        last_val = sorted_values[-1][1]

        # Calculate trend
        if abs(last_val - first_val) / first_val < 0.1:  # Less than 10% change
            trend = 'stable'
        elif last_val > first_val:
            trend = 'increasing'
        else:
            trend = 'decreasing'

        # Clinical interpretation
        lab_info = self.lab_ranges.get(lab_name.lower(), {})
        normal_range = lab_info.get('range')

        if normal_range:
            first_status = 'normal' if normal_range[0] <= first_val <= normal_range[1] else 'abnormal'
            last_status = 'normal' if normal_range[0] <= last_val <= normal_range[1] else 'abnormal'

            if first_status == 'abnormal' and last_status == 'normal':
                clinical_significance = 'improving_to_normal'
            elif first_status == 'normal' and last_status == 'abnormal':
                clinical_significance = 'worsening_from_normal'
            else:
                clinical_significance = trend
        else:
            clinical_significance = trend

        return {
            'trend': trend,
            'clinical_significance': clinical_significance,
            'first_value': first_val,
            'last_value': last_val,
            'change_percent': abs((last_val - first_val) / first_val * 100) if first_val != 0 else 0
        }

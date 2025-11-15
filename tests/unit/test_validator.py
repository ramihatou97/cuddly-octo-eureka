"""
Comprehensive unit tests for 6-Stage Validation Pipeline

Tests all validation stages for clinical safety.
Target: 100% detection of critical issues

Test Coverage:
- Stage 1: Format validation
- Stage 2: Clinical rule validation
- Stage 3: Temporal validation
- Stage 4: Cross-fact validation
- Stage 5: Contradiction detection (NEW)
- Stage 6: Completeness check

Each stage tested independently and then integrated.

Run with: pytest tests/unit/test_validator.py -v
"""

import pytest
from datetime import datetime, date, timedelta

from src.processing.validator import ComprehensiveValidator
from src.core.data_models import (
    HybridClinicalFact,
    ClinicalUncertainty,
    ClinicalTimeline,
    ClinicalConcept
)


@pytest.fixture
def validator():
    """Create validator instance"""
    return ComprehensiveValidator()


@pytest.fixture
def sample_timeline():
    """Create sample clinical timeline"""
    return ClinicalTimeline(
        timeline={
            date(2024, 11, 1): [],
            date(2024, 11, 2): [],
            date(2024, 11, 3): []
        },
        admission_date=datetime(2024, 11, 1, 8, 0),
        discharge_date=datetime(2024, 11, 10, 10, 0),
        total_hospital_days=10
    )


# ============================================================================
# STAGE 1: FORMAT VALIDATION TESTS
# ============================================================================

class TestFormatValidation:
    """Test Stage 1: Format validation"""

    def test_valid_format_passes(self, validator):
        """Test: Valid fact passes format validation?"""
        facts = [
            HybridClinicalFact(
                fact="NIHSS: 8",
                source_doc="doc1",
                source_line=10,
                timestamp=datetime(2024, 11, 1, 8, 0),
                confidence=0.95,
                fact_type="clinical_score"
            )
        ]

        validated, issues = validator._validate_format(facts)

        assert len(validated) == 1
        assert len(issues) == 0

    def test_empty_fact_text_rejected(self, validator):
        """Test: Empty fact text generates issue?"""
        facts = [
            HybridClinicalFact(
                fact="",  # Empty
                source_doc="doc1",
                source_line=10,
                timestamp=datetime.now(),
                confidence=0.95,
                fact_type="finding"
            )
        ]

        validated, issues = validator._validate_format(facts)

        # Should be rejected
        assert len(validated) == 0
        assert len(issues) == 1
        assert issues[0].severity == "MEDIUM"

    def test_invalid_confidence_caught_at_creation(self, validator):
        """Test: Invalid confidence score caught at data model level?"""
        # HybridClinicalFact __post_init__ validates confidence
        # This is GOOD - prevents invalid data from being created

        with pytest.raises(ValueError, match="Confidence must be between 0.0 and 1.0"):
            HybridClinicalFact(
                fact="Test fact",
                source_doc="doc1",
                source_line=10,
                timestamp=datetime.now(),
                confidence=1.5,  # Invalid (>1.0)
                fact_type="finding"
            )

        # This test validates that the data model enforces constraints
        # Validator Stage 1 handles facts that pass initial creation


# ============================================================================
# STAGE 2: CLINICAL RULE VALIDATION TESTS
# ============================================================================

class TestClinicalRuleValidation:
    """Test Stage 2: Clinical rule validation"""

    def test_critical_lab_value_detected(self, validator):
        """Test: Critical lab value (Sodium 125) generates HIGH severity issue?"""
        # Create critical sodium fact
        concept = ClinicalConcept(
            concept_type='lab',
            name='Sodium',
            value=125.0,
            unit='mmol/L',
            normal_range=(135, 145),
            severity='CRITICAL',
            clinical_implications=['Risk of seizures, altered mental status']
        )

        facts = [
            HybridClinicalFact(
                fact="Lab: Sodium = 125.0 mmol/L",
                source_doc="lab_report",
                source_line=5,
                timestamp=datetime.now(),
                confidence=0.95,
                fact_type="lab_value",
                normalized_value=concept,
                severity='CRITICAL'
            )
        ]

        validated, issues = validator._validate_clinical_rules(facts)

        # Should generate HIGH severity issue
        assert len(issues) >= 1

        critical_lab_issues = [i for i in issues if 'CRITICAL_LAB_VALUE' in i.issue_type]
        assert len(critical_lab_issues) == 1

        issue = critical_lab_issues[0]
        assert issue.severity == "HIGH"
        assert 'Sodium' in issue.description
        assert '125' in issue.description

    def test_invalid_clinical_score_detected(self, validator):
        """Test: Invalid NIHSS score (99) generates HIGH severity issue?"""
        facts = [
            HybridClinicalFact(
                fact="NIHSS: 99",  # Invalid - max is 42
                source_doc="progress",
                source_line=10,
                timestamp=datetime.now(),
                confidence=0.95,
                fact_type="clinical_score",
                normalized_value=99
            )
        ]

        validated, issues = validator._validate_clinical_rules(facts)

        # Should detect invalid score
        assert len(issues) >= 1

        score_issues = [i for i in issues if 'INVALID_SCORE_RANGE' in i.issue_type]
        assert len(score_issues) == 1

        issue = score_issues[0]
        assert issue.severity == "HIGH"
        assert 'NIHSS' in issue.description
        assert '99' in issue.description

    def test_excessive_medication_dose_detected(self, validator):
        """Test: Excessive medication dose generates HIGH severity issue?"""
        facts = [
            HybridClinicalFact(
                fact="Medication: heparin 100000 units",  # Exceeds max 50000
                source_doc="medication_list",
                source_line=5,
                timestamp=datetime.now(),
                confidence=0.85,
                fact_type="medication",
                normalized_value='heparin'
            )
        ]

        validated, issues = validator._validate_clinical_rules(facts)

        # Should detect excessive dose
        assert len(issues) >= 1

        dose_issues = [i for i in issues if 'EXCESSIVE_MEDICATION_DOSE' in i.issue_type]
        assert len(dose_issues) == 1

        issue = dose_issues[0]
        assert issue.severity == "HIGH"
        assert 'heparin' in issue.description.lower()

    def test_normal_lab_no_issue(self, validator):
        """Test: Normal lab value does NOT generate issue?"""
        concept = ClinicalConcept(
            concept_type='lab',
            name='Sodium',
            value=140.0,
            unit='mmol/L',
            normal_range=(135, 145),
            severity='NORMAL',
            clinical_implications=[]
        )

        facts = [
            HybridClinicalFact(
                fact="Lab: Sodium = 140.0 mmol/L",
                source_doc="lab_report",
                source_line=5,
                timestamp=datetime.now(),
                confidence=0.95,
                fact_type="lab_value",
                normalized_value=concept,
                severity='NORMAL'
            )
        ]

        validated, issues = validator._validate_clinical_rules(facts)

        # Should NOT generate issues for normal values
        assert len(issues) == 0


# ============================================================================
# STAGE 3: TEMPORAL VALIDATION TESTS
# ============================================================================

class TestTemporalValidation:
    """Test Stage 3: Temporal validation"""

    def test_discharge_before_admission_detected(self, validator):
        """Test: Discharge before admission generates HIGH severity issue?"""
        timeline = ClinicalTimeline(
            timeline={},
            admission_date=datetime(2024, 11, 5, 8, 0),
            discharge_date=datetime(2024, 11, 1, 10, 0),  # BEFORE admission!
            total_hospital_days=0
        )

        issues = validator._validate_temporal_consistency(timeline)

        # Should detect temporal inconsistency
        assert len(issues) >= 1

        temporal_issues = [i for i in issues if 'TEMPORAL_INCONSISTENCY' in i.issue_type]
        assert len(temporal_issues) >= 1

        issue = temporal_issues[0]
        assert issue.severity == "HIGH"
        assert 'before admission' in issue.description.lower()

    def test_large_documentation_gap_flagged(self, validator):
        """Test: Large gap in timeline (>3 days) generates MEDIUM severity issue?"""
        timeline = ClinicalTimeline(
            timeline={
                date(2024, 11, 1): [],
                date(2024, 11, 8): []  # 7-day gap
            },
            admission_date=datetime(2024, 11, 1, 8, 0),
            total_hospital_days=8
        )

        issues = validator._validate_temporal_consistency(timeline)

        # Should detect gap
        gap_issues = [i for i in issues if 'gap' in i.description.lower()]
        assert len(gap_issues) >= 1

        issue = gap_issues[0]
        assert issue.severity == "MEDIUM"
        assert '7 days' in issue.description or '7-day' in issue.description

    def test_valid_timeline_no_issues(self, validator, sample_timeline):
        """Test: Valid timeline generates no issues?"""
        issues = validator._validate_temporal_consistency(sample_timeline)

        # Should have no issues
        assert len(issues) == 0


# ============================================================================
# STAGE 4: CROSS-FACT VALIDATION TESTS
# ============================================================================

class TestCrossFactValidation:
    """Test Stage 4: Cross-fact validation"""

    def test_conflicting_scores_detected(self, validator):
        """Test: Conflicting NIHSS scores within 1 hour detected?"""
        facts = [
            HybridClinicalFact(
                fact="NIHSS: 6",
                source_doc="doc1",
                source_line=10,
                timestamp=datetime(2024, 11, 1, 8, 0),
                confidence=0.95,
                fact_type="clinical_score",
                normalized_value=6
            ),
            HybridClinicalFact(
                fact="NIHSS: 12",  # Different value, same time
                source_doc="doc2",
                source_line=15,
                timestamp=datetime(2024, 11, 1, 8, 30),  # 30 minutes later
                confidence=0.95,
                fact_type="clinical_score",
                normalized_value=12
            )
        ]

        issues = validator._validate_cross_facts(facts)

        # Should detect conflict
        assert len(issues) >= 1

        conflict_issues = [i for i in issues if 'CONFLICTING_INFORMATION' in i.issue_type]
        assert len(conflict_issues) >= 1

        issue = conflict_issues[0]
        assert issue.severity == "HIGH"
        assert 'NIHSS' in issue.description

    def test_no_conflict_different_times(self, validator):
        """Test: Same scores at different times (>1 hour) not flagged?"""
        facts = [
            HybridClinicalFact(
                fact="NIHSS: 6",
                source_doc="admission",
                source_line=10,
                timestamp=datetime(2024, 11, 1, 8, 0),
                confidence=0.95,
                fact_type="clinical_score",
                normalized_value=6
            ),
            HybridClinicalFact(
                fact="NIHSS: 12",  # Different value, different day
                source_doc="progress",
                source_line=15,
                timestamp=datetime(2024, 11, 3, 8, 0),  # 2 days later
                confidence=0.95,
                fact_type="clinical_score",
                normalized_value=12
            )
        ]

        issues = validator._validate_cross_facts(facts)

        # Should NOT flag as conflict (legitimate progression)
        conflict_issues = [i for i in issues if 'CONFLICTING_INFORMATION' in i.issue_type and 'NIHSS' in i.description]
        assert len(conflict_issues) == 0

    def test_medication_interaction_detected(self, validator):
        """Test: High-risk medication combinations flagged?"""
        # Anticoagulant in neurosurgical patient
        facts = [
            HybridClinicalFact(
                fact="Medication: heparin 5000 units",
                source_doc="meds",
                source_line=1,
                timestamp=datetime.now(),
                confidence=0.85,
                fact_type="medication",
                normalized_value='heparin'
            )
        ]

        issues = validator._validate_cross_facts(facts)

        # Should flag anticoagulant use (from knowledge base interaction checking)
        # Note: This depends on knowledge_base.get_medication_interactions() implementation
        interaction_issues = [i for i in issues if 'anticoagulant' in i.description.lower()]
        assert len(interaction_issues) >= 1


# ============================================================================
# STAGE 5: CONTRADICTION DETECTION TESTS (NEW)
# ============================================================================

class TestContradictionDetection:
    """Test Stage 5: NEW contradiction detection"""

    def test_no_complications_vs_actual_complications(self, validator, sample_timeline):
        """
        Test: "No complications" statement contradicts documented complications?

        This is a critical safety check!
        """
        facts = [
            HybridClinicalFact(
                fact="Procedure completed without complications",
                source_doc="operative_note",
                source_line=20,
                timestamp=datetime(2024, 11, 2, 14, 0),
                confidence=0.95,
                fact_type="finding"
            ),
            HybridClinicalFact(
                fact="Complication: CSF leak noted POD#1",
                source_doc="progress_note",
                source_line=5,
                timestamp=datetime(2024, 11, 3, 8, 0),
                absolute_timestamp=datetime(2024, 11, 3, 8, 0),
                confidence=0.90,
                fact_type="complication",
                severity='HIGH'
            )
        ]

        issues = validator._detect_contradictions(facts, sample_timeline)

        # Should detect contradiction
        assert len(issues) >= 1

        contradiction_issues = [i for i in issues if 'CONTRADICTORY_STATEMENTS' in i.issue_type]
        assert len(contradiction_issues) >= 1

        issue = contradiction_issues[0]
        assert issue.severity == "HIGH"
        assert 'no complication' in issue.description.lower()

    def test_successful_procedure_vs_revision(self, validator, sample_timeline):
        """Test: Successful procedure followed by revision flagged?"""
        facts = [
            HybridClinicalFact(
                fact="Procedure: Craniotomy successful",
                source_doc="operative_note",
                source_line=50,
                timestamp=datetime(2024, 11, 2, 14, 0),
                absolute_timestamp=datetime(2024, 11, 2, 14, 0),
                confidence=0.95,
                fact_type="procedure"
            ),
            HybridClinicalFact(
                fact="Procedure: Revision craniotomy for CSF leak repair",
                source_doc="operative_note_2",
                source_line=10,
                timestamp=datetime(2024, 11, 5, 14, 0),
                absolute_timestamp=datetime(2024, 11, 5, 14, 0),
                confidence=0.95,
                fact_type="procedure"
            )
        ]

        issues = validator._detect_contradictions(facts, sample_timeline)

        # Should detect contradictory outcomes
        assert len(issues) >= 1

        outcome_issues = [i for i in issues if 'CONTRADICTORY_OUTCOMES' in i.issue_type]
        assert len(outcome_issues) >= 1

        issue = outcome_issues[0]
        assert issue.severity == "MEDIUM"
        assert 'revision' in issue.description.lower()

    def test_stable_discharge_vs_critical_findings(self, validator, sample_timeline):
        """Test: Stable discharge vs recent critical labs flagged?"""
        facts = [
            HybridClinicalFact(
                fact="Patient stable for discharge",
                source_doc="discharge_summary",
                source_line=1,
                timestamp=datetime(2024, 11, 10, 10, 0),
                absolute_timestamp=datetime(2024, 11, 10, 10, 0),
                confidence=0.90,
                fact_type="finding"
            ),
            HybridClinicalFact(
                fact="Lab: Sodium = 125.0 mmol/L",  # Critical
                source_doc="lab_report",
                source_line=5,
                timestamp=datetime(2024, 11, 9, 8, 0),  # 1 day before discharge
                absolute_timestamp=datetime(2024, 11, 9, 8, 0),
                confidence=0.95,
                fact_type="lab_value",
                severity='CRITICAL',
                clinical_significance='CRITICAL'
            )
        ]

        issues = validator._detect_contradictions(facts, sample_timeline)

        # Should detect discharge status contradiction
        assert len(issues) >= 1

        discharge_issues = [i for i in issues if 'DISCHARGE_STATUS_CONTRADICTION' in i.issue_type]
        assert len(discharge_issues) >= 1

        issue = discharge_issues[0]
        assert issue.severity == "HIGH"
        assert 'stable' in issue.description.lower()
        assert 'critical' in issue.description.lower()

    def test_no_contradictions_in_valid_case(self, validator, sample_timeline):
        """Test: Valid case with no contradictions generates no issues?"""
        facts = [
            HybridClinicalFact(
                fact="Procedure: Craniotomy completed",
                source_doc="operative",
                source_line=1,
                timestamp=datetime(2024, 11, 2),
                confidence=0.95,
                fact_type="procedure"
            ),
            HybridClinicalFact(
                fact="Patient progressing well",
                source_doc="progress",
                source_line=1,
                timestamp=datetime(2024, 11, 5),
                confidence=0.90,
                fact_type="finding"
            )
        ]

        issues = validator._detect_contradictions(facts, sample_timeline)

        # Should have no contradictions
        contradiction_types = [
            'CONTRADICTORY_STATEMENTS',
            'CONTRADICTORY_OUTCOMES',
            'DISCHARGE_STATUS_CONTRADICTION'
        ]

        contradiction_issues = [
            i for i in issues
            if any(ct in i.issue_type for ct in contradiction_types)
        ]

        assert len(contradiction_issues) == 0


# ============================================================================
# STAGE 6: COMPLETENESS CHECK TESTS
# ============================================================================

class TestCompletenessCheck:
    """Test Stage 6: Completeness validation"""

    def test_missing_diagnosis_flagged(self, validator, sample_timeline):
        """Test: Missing diagnosis generates HIGH severity issue?"""
        facts = [
            # No diagnosis fact
            HybridClinicalFact(
                fact="Medication: nimodipine 60mg",
                source_doc="meds",
                source_line=1,
                timestamp=datetime.now(),
                confidence=0.85,
                fact_type="medication"
            )
        ]

        issues = validator._check_completeness(facts, sample_timeline)

        # Should detect missing diagnosis
        missing_issues = [i for i in issues if 'MISSING_INFORMATION' in i.issue_type and 'diagnosis' in i.description.lower()]
        assert len(missing_issues) >= 1

        issue = missing_issues[0]
        assert issue.severity == "HIGH"  # Diagnosis is critical

    def test_missing_procedure_flagged(self, validator, sample_timeline):
        """Test: Missing procedure info flagged?"""
        facts = [
            HybridClinicalFact(
                fact="NIHSS: 8",
                source_doc="progress",
                source_line=1,
                timestamp=datetime.now(),
                confidence=0.95,
                fact_type="clinical_score"
            )
        ]

        issues = validator._check_completeness(facts, sample_timeline)

        # Should detect missing procedure
        procedure_issues = [i for i in issues if 'procedure' in i.description.lower()]
        assert len(procedure_issues) >= 1

    def test_missing_discharge_medications_flagged(self, validator, sample_timeline):
        """Test: Missing discharge medications generates HIGH severity issue?"""
        facts = [
            HybridClinicalFact(
                fact="Diagnosis: SAH",
                source_doc="admission",
                source_line=1,
                timestamp=datetime.now(),
                confidence=0.90,
                fact_type="diagnosis"
            )
            # No discharge medications
        ]

        issues = validator._check_completeness(facts, sample_timeline)

        # Should detect missing discharge meds
        med_issues = [i for i in issues if 'discharge medication' in i.description.lower()]
        assert len(med_issues) >= 1

        # At least one should be HIGH severity
        high_severity_med_issues = [i for i in med_issues if i.severity == "HIGH"]
        assert len(high_severity_med_issues) >= 1

    def test_complete_case_minimal_issues(self, validator, sample_timeline):
        """Test: Complete case generates minimal completeness issues?"""
        facts = [
            HybridClinicalFact(
                fact="Diagnosis: SAH",
                source_doc="admission",
                source_line=1,
                timestamp=datetime.now(),
                confidence=0.90,
                fact_type="diagnosis"
            ),
            HybridClinicalFact(
                fact="Procedure: Craniotomy for aneurysm clipping",
                source_doc="operative",
                source_line=1,
                timestamp=datetime.now(),
                confidence=0.95,
                fact_type="procedure"
            ),
            HybridClinicalFact(
                fact="Medication: nimodipine 60mg q4h",
                source_doc="discharge_medications",
                source_line=1,
                timestamp=datetime.now(),
                confidence=0.85,
                fact_type="medication"
            )
        ]

        issues = validator._check_completeness(facts, sample_timeline)

        # May have some minor issues (follow-up, instructions), but not major ones
        high_severity = [i for i in issues if i.severity == "HIGH"]
        assert len(high_severity) == 0  # No HIGH severity if all major fields present


# ============================================================================
# INTEGRATED VALIDATION TESTS
# ============================================================================

class TestFullValidationPipeline:
    """Test complete validation pipeline (all 6 stages)"""

    def test_full_validation_clean_case(self, validator, sample_timeline):
        """Test: Clean case with minimal issues?"""
        facts = [
            HybridClinicalFact(
                fact="Diagnosis: SAH Hunt-Hess 3",
                source_doc="admission",
                source_line=1,
                timestamp=datetime(2024, 11, 1, 8, 0),
                confidence=0.90,
                fact_type="diagnosis"
            ),
            HybridClinicalFact(
                fact="NIHSS: 6",
                source_doc="admission",
                source_line=10,
                timestamp=datetime(2024, 11, 1, 8, 0),
                confidence=0.95,
                fact_type="clinical_score",
                normalized_value=6
            ),
            HybridClinicalFact(
                fact="Procedure: Craniotomy for aneurysm clipping",
                source_doc="operative",
                source_line=1,
                timestamp=datetime(2024, 11, 2, 14, 0),
                confidence=0.95,
                fact_type="procedure"
            ),
            HybridClinicalFact(
                fact="Medication: nimodipine 60mg q4h",
                source_doc="discharge_meds",
                source_line=1,
                timestamp=datetime(2024, 11, 10, 10, 0),
                confidence=0.85,
                fact_type="medication"
            )
        ]

        validated_facts, uncertainties = validator.validate(facts, sample_timeline)

        # Should validate all facts
        assert len(validated_facts) == len(facts)

        # Should have minimal high-severity issues
        high_severity = [u for u in uncertainties if u.severity == "HIGH"]
        assert len(high_severity) <= 2  # Maybe missing follow-up or discharge instructions

    def test_full_validation_problematic_case(self, validator, sample_timeline):
        """Test: Problematic case generates appropriate issues?"""
        facts = [
            # Invalid NIHSS
            HybridClinicalFact(
                fact="NIHSS: 99",  # Invalid
                source_doc="progress",
                source_line=10,
                timestamp=datetime.now(),
                confidence=0.95,
                fact_type="clinical_score",
                normalized_value=99
            ),
            # Critical sodium
            HybridClinicalFact(
                fact="Lab: Sodium = 120.0 mmol/L",
                source_doc="lab",
                source_line=5,
                timestamp=datetime.now(),
                confidence=0.95,
                fact_type="lab_value",
                normalized_value=ClinicalConcept(
                    concept_type='lab',
                    name='Sodium',
                    value=120.0,
                    unit='mmol/L',
                    normal_range=(135, 145),
                    severity='CRITICAL',
                    clinical_implications=['Risk of seizures']
                ),
                severity='CRITICAL'
            ),
            # No diagnosis, procedure, or discharge meds (missing required)
        ]

        validated_facts, uncertainties = validator.validate(facts, sample_timeline)

        # Should generate multiple HIGH severity issues
        high_severity = [u for u in uncertainties if u.severity == "HIGH"]
        assert len(high_severity) >= 3  # Invalid score, critical lab, missing required fields

    def test_validation_summary_structure(self, validator, sample_timeline):
        """Test: Validation summary has correct structure?"""
        facts = [
            HybridClinicalFact(
                fact="Test fact",
                source_doc="doc",
                source_line=1,
                timestamp=datetime.now(),
                confidence=0.90,
                fact_type="finding"
            )
        ]

        validated_facts, uncertainties = validator.validate(facts, sample_timeline)
        summary = validator.get_validation_summary(uncertainties)

        # Check structure
        assert 'total_uncertainties' in summary
        assert 'high_severity_count' in summary
        assert 'medium_severity_count' in summary
        assert 'low_severity_count' in summary
        assert 'by_type' in summary
        assert 'requires_review' in summary


# ============================================================================
# EDGE CASES AND SAFETY TESTS
# ============================================================================

class TestValidationSafety:
    """Test safety and edge cases"""

    def test_empty_facts_list(self, validator, sample_timeline):
        """Test: Empty facts list handled gracefully?"""
        validated, uncertainties = validator.validate([], sample_timeline)

        # Should not crash
        assert validated == []
        # Will have completeness issues
        assert len(uncertainties) >= 1

    def test_validation_does_not_modify_facts(self, validator, sample_timeline):
        """Test: Validation doesn't modify original facts (except confidence fixes)?"""
        original_fact = HybridClinicalFact(
            fact="NIHSS: 8",
            source_doc="progress",
            source_line=10,
            timestamp=datetime(2024, 11, 1, 8, 0),
            confidence=0.95,
            fact_type="clinical_score",
            normalized_value=8
        )

        original_fact_text = original_fact.fact
        original_confidence = original_fact.confidence

        validated, uncertainties = validator.validate([original_fact], sample_timeline)

        # Fact text should not change
        assert validated[0].fact == original_fact_text

        # Confidence should not change (unless it was invalid)
        assert validated[0].confidence == original_confidence

    def test_all_stages_run_even_with_errors(self, validator, sample_timeline):
        """Test: All validation stages run even if earlier stages find issues?"""
        facts = [
            # Format issue (empty fact text)
            HybridClinicalFact(
                fact="",  # Empty - will be caught in Stage 1
                source_doc="doc",
                source_line=1,
                timestamp=datetime.now(),
                confidence=0.90,
                fact_type="finding"
            )
        ]

        # All stages should still run
        validated, uncertainties = validator.validate(facts, sample_timeline)

        # Should have run all stages (will have completeness issues even with format issues)
        assert len(uncertainties) >= 2  # Format + completeness


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

"""
Unit tests for database models

Tests SQLAlchemy model definitions, relationships, and basic operations.
Ensures database schema is correct before proceeding to Phase 2.

Run with: pytest tests/unit/test_database_models.py
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import uuid

from src.database.models import (
    Base, User, ProcessingSession, Document, Uncertainty,
    LearningPattern, AuditLog, ProcessingMetric,
    create_tables, drop_tables, get_table_names
)


@pytest.fixture(scope='function')
def engine():
    """Create in-memory SQLite database for testing"""
    engine = create_engine('sqlite:///:memory:', echo=False)
    create_tables(engine)
    yield engine
    drop_tables(engine)


@pytest.fixture(scope='function')
def session(engine):
    """Create database session for testing"""
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestTableCreation:
    """Test table creation and schema"""

    def test_all_tables_created(self, engine):
        """Verify all expected tables are created"""
        table_names = get_table_names()

        expected_tables = {
            'users', 'processing_sessions', 'documents',
            'uncertainties', 'learning_patterns', 'audit_log',
            'processing_metrics'
        }

        assert set(table_names) == expected_tables, \
            f"Expected tables {expected_tables}, got {set(table_names)}"

    def test_table_creation_no_errors(self, engine):
        """Ensure tables can be created without errors"""
        # This implicitly tests via the fixture
        # If tables couldn't be created, fixture would fail
        assert engine is not None


class TestUserModel:
    """Test User model"""

    def test_create_user(self, session):
        """Test creating a user"""
        user = User(
            username='test_doctor',
            email='doctor@hospital.com',
            hashed_password='hashed_pw_123',
            full_name='Dr. Test Doctor',
            department='Neurosurgery',
            role='attending',
            permissions={'read': True, 'write': True, 'approve': True}
        )

        session.add(user)
        session.commit()

        assert user.id is not None
        assert user.username == 'test_doctor'
        assert user.role == 'attending'
        assert user.is_active is True

    def test_user_unique_username(self, session):
        """Test username uniqueness constraint"""
        user1 = User(username='doctor1', email='doc1@hospital.com', hashed_password='pw1')
        user2 = User(username='doctor1', email='doc2@hospital.com', hashed_password='pw2')

        session.add(user1)
        session.commit()

        session.add(user2)
        with pytest.raises(Exception):  # SQLite raises IntegrityError
            session.commit()

    def test_user_relationships(self, session):
        """Test user relationships to other tables"""
        user = User(username='test_user', email='test@test.com', hashed_password='pw')
        session.add(user)
        session.commit()

        # Create related session
        proc_session = ProcessingSession(
            user_id=user.id,
            status='completed',
            document_count=3
        )
        session.add(proc_session)
        session.commit()

        # Test relationship
        assert len(user.sessions) == 1
        assert user.sessions[0].document_count == 3


class TestProcessingSessionModel:
    """Test ProcessingSession model"""

    def test_create_session(self, session):
        """Test creating a processing session"""
        user = User(username='test_user', email='test@test.com', hashed_password='pw')
        session.add(user)
        session.commit()

        proc_session = ProcessingSession(
            user_id=user.id,
            status='processing',
            document_count=5,
            confidence_score=0.95,
            requires_review=False,
            custom_metadata={'test': 'data'}
        )

        session.add(proc_session)
        session.commit()

        assert proc_session.id is not None
        assert isinstance(proc_session.id, uuid.UUID)
        assert float(proc_session.confidence_score) == 0.95  # Convert Decimal to float for comparison
        assert proc_session.custom_metadata == {'test': 'data'}

    def test_session_user_relationship(self, session):
        """Test session belongs to user"""
        user = User(username='test_user', email='test@test.com', hashed_password='pw')
        session.add(user)
        session.commit()

        proc_session = ProcessingSession(user_id=user.id, status='completed')
        session.add(proc_session)
        session.commit()

        assert proc_session.user.username == 'test_user'


class TestDocumentModel:
    """Test Document model"""

    def test_create_document(self, session):
        """Test creating a document cache entry"""
        user = User(username='test_user', email='test@test.com', hashed_password='pw')
        session.add(user)
        session.commit()

        proc_session = ProcessingSession(user_id=user.id, status='processing')
        session.add(proc_session)
        session.commit()

        doc = Document(
            session_id=proc_session.id,
            doc_hash='abc123def456',
            doc_type='admission',
            content_summary='Patient admitted with...',
            extraction_cache={'facts': []}
        )

        session.add(doc)
        session.commit()

        assert doc.id is not None
        assert doc.doc_hash == 'abc123def456'
        assert doc.doc_type == 'admission'

    def test_document_hash_unique(self, session):
        """Test document hash uniqueness constraint"""
        user = User(username='test_user', email='test@test.com', hashed_password='pw')
        session.add(user)
        session.commit()

        proc_session = ProcessingSession(user_id=user.id, status='processing')
        session.add(proc_session)
        session.commit()

        doc1 = Document(session_id=proc_session.id, doc_hash='same_hash', doc_type='admission')
        doc2 = Document(session_id=proc_session.id, doc_hash='same_hash', doc_type='operative')

        session.add(doc1)
        session.commit()

        session.add(doc2)
        with pytest.raises(Exception):  # IntegrityError for unique constraint
            session.commit()


class TestUncertaintyModel:
    """Test Uncertainty model"""

    def test_create_uncertainty(self, session):
        """Test creating an uncertainty"""
        user = User(username='test_user', email='test@test.com', hashed_password='pw')
        session.add(user)
        session.commit()

        proc_session = ProcessingSession(user_id=user.id, status='processing')
        session.add(proc_session)
        session.commit()

        uncertainty = Uncertainty(
            session_id=proc_session.id,
            uncertainty_type='CONFLICTING_INFORMATION',
            description='Conflicting medication dosages',
            conflicting_sources=['doc1', 'doc2'],
            suggested_resolution='Verify with pharmacy',
            severity='HIGH',
            context={'field': 'medication'}
        )

        session.add(uncertainty)
        session.commit()

        assert uncertainty.id is not None
        assert uncertainty.uncertainty_type == 'CONFLICTING_INFORMATION'
        assert uncertainty.severity == 'HIGH'
        assert uncertainty.resolved is False

    def test_uncertainty_resolution(self, session):
        """Test resolving an uncertainty"""
        user = User(username='test_user', email='test@test.com', hashed_password='pw')
        resolver = User(username='resolver', email='resolver@test.com', hashed_password='pw')
        session.add_all([user, resolver])
        session.commit()

        proc_session = ProcessingSession(user_id=user.id, status='processing')
        session.add(proc_session)
        session.commit()

        uncertainty = Uncertainty(
            session_id=proc_session.id,
            uncertainty_type='MISSING_INFORMATION',
            description='Missing follow-up date',
            conflicting_sources=[],
            suggested_resolution='Add follow-up date',
            severity='MEDIUM',
            context={}
        )
        session.add(uncertainty)
        session.commit()

        # Resolve uncertainty
        uncertainty.resolved = True
        uncertainty.resolved_by = resolver.id
        uncertainty.resolved_at = datetime.utcnow()
        uncertainty.resolution = 'Follow-up scheduled for 2024-12-01'
        session.commit()

        assert uncertainty.resolved is True
        assert uncertainty.resolver.username == 'resolver'
        assert uncertainty.resolution is not None


class TestLearningPatternModel:
    """Test LearningPattern model"""

    def test_create_learning_pattern(self, session):
        """Test creating a learning pattern"""
        user = User(username='test_user', email='test@test.com', hashed_password='pw')
        session.add(user)
        session.commit()

        pattern = LearningPattern(
            pattern_hash='pattern123',
            fact_type='temporal_reference',
            original_pattern='POD#3',
            correction='post-operative day 3',
            context={'type': 'temporal'},
            success_rate=1.0,
            applied_count=0,
            created_by=user.id
        )

        session.add(pattern)
        session.commit()

        assert pattern.id is not None
        assert pattern.fact_type == 'temporal_reference'
        assert pattern.approved is False  # Default value

    def test_learning_pattern_approval_workflow(self, session):
        """Test learning pattern approval workflow"""
        creator = User(username='creator', email='creator@test.com', hashed_password='pw')
        approver = User(username='approver', email='approver@test.com', hashed_password='pw')
        session.add_all([creator, approver])
        session.commit()

        pattern = LearningPattern(
            pattern_hash='pattern456',
            fact_type='medication',
            original_pattern='nimodipine',
            correction='nimodipine 60mg',
            context={},
            created_by=creator.id
        )
        session.add(pattern)
        session.commit()

        # Initially not approved
        assert pattern.approved is False

        # Approve pattern
        pattern.approved = True
        pattern.approved_by = approver.id
        pattern.approved_at = datetime.utcnow()
        session.commit()

        assert pattern.approved is True
        assert pattern.approver.username == 'approver'


class TestAuditLogModel:
    """Test AuditLog model"""

    def test_create_audit_log(self, session):
        """Test creating an audit log entry"""
        user = User(username='test_user', email='test@test.com', hashed_password='pw')
        session.add(user)
        session.commit()

        audit = AuditLog(
            user_id=user.id,
            action='PROCESS_DOCUMENTS',
            resource_type='session',
            resource_id=uuid.uuid4(),
            details={'document_count': 5},
            ip_address='192.168.1.100',
            user_agent='Mozilla/5.0'
        )

        session.add(audit)
        session.commit()

        assert audit.id is not None
        assert audit.action == 'PROCESS_DOCUMENTS'
        assert audit.details == {'document_count': 5}

    def test_audit_log_user_relationship(self, session):
        """Test audit log belongs to user"""
        user = User(username='test_user', email='test@test.com', hashed_password='pw')
        session.add(user)
        session.commit()

        audit = AuditLog(
            user_id=user.id,
            action='LOGIN',
            resource_type='user',
            resource_id=uuid.uuid4()
        )
        session.add(audit)
        session.commit()

        assert audit.user.username == 'test_user'


class TestProcessingMetricModel:
    """Test ProcessingMetric model"""

    def test_create_metric(self, session):
        """Test creating a processing metric"""
        user = User(username='test_user', email='test@test.com', hashed_password='pw')
        session.add(user)
        session.commit()

        proc_session = ProcessingSession(user_id=user.id, status='completed')
        session.add(proc_session)
        session.commit()

        metric = ProcessingMetric(
            session_id=proc_session.id,
            metric_type='processing_time',
            value=1234.56,
            unit='ms',
            custom_metadata={'stage': 'extraction'}
        )

        session.add(metric)
        session.commit()

        assert metric.id is not None
        assert metric.metric_type == 'processing_time'
        assert float(metric.value) == 1234.56
        assert metric.unit == 'ms'


class TestCascadeDelete:
    """Test cascade deletion of related records"""

    def test_delete_user_cascades_to_sessions(self, session):
        """Test that deleting user deletes their sessions"""
        user = User(username='test_user', email='test@test.com', hashed_password='pw')
        session.add(user)
        session.commit()

        proc_session = ProcessingSession(user_id=user.id, status='completed')
        session.add(proc_session)
        session.commit()

        session_id = proc_session.id

        # Delete user
        session.delete(user)
        session.commit()

        # Session should be deleted
        deleted_session = session.query(ProcessingSession).filter_by(id=session_id).first()
        assert deleted_session is None

    def test_delete_session_cascades_to_documents(self, session):
        """Test that deleting session deletes related documents"""
        user = User(username='test_user', email='test@test.com', hashed_password='pw')
        session.add(user)
        session.commit()

        proc_session = ProcessingSession(user_id=user.id, status='completed')
        session.add(proc_session)
        session.commit()

        doc = Document(
            session_id=proc_session.id,
            doc_hash='hash123',
            doc_type='admission'
        )
        session.add(doc)
        session.commit()

        doc_id = doc.id

        # Delete session
        session.delete(proc_session)
        session.commit()

        # Document should be deleted
        deleted_doc = session.query(Document).filter_by(id=doc_id).first()
        assert deleted_doc is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

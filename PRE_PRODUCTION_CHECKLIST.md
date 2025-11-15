# Pre-Production Deployment Checklist

**Repository**: Neurosurgical Discharge Summary System  
**Current Status**: Production-Ready (92/100) with fixes needed  
**Target**: 100% Production-Ready  
**Timeline**: 3-5 days  

---

## 🔴 CRITICAL - MUST FIX (Day 1-2) - BLOCKERS

### Security Issue #1: Default Admin Credentials
**Status**: [ ] Not Started / [ ] In Progress / [ ] Complete

**Current State**:
```python
# api/app.py line 297
admin_user = UserModel(
    username="admin",
    hashed_password=pwd_context.hash("admin123"),  # ❌ DEFAULT PASSWORD
    ...
)
```

**Required Fix**:
```python
# api/app.py - Update startup event
admin_password = os.getenv("ADMIN_DEFAULT_PASSWORD")
if not admin_password:
    raise ValueError("ADMIN_DEFAULT_PASSWORD must be set")
if admin_password in ["admin123", "password", "changeme"]:
    raise ValueError("Cannot use default/weak password")

admin_user = UserModel(
    username="admin",
    hashed_password=pwd_context.hash(admin_password),
    ...
)
```

**Steps**:
1. [ ] Edit `api/app.py` lines 297-308
2. [ ] Add ADMIN_DEFAULT_PASSWORD to `.env`
3. [ ] Generate strong password: `openssl rand -base64 24`
4. [ ] Document password in secure password manager
5. [ ] Test login with new credentials
6. [ ] Verify old credentials don't work

**Verification**:
```bash
# Test old credentials fail
curl -X POST http://localhost:8000/api/auth/login \
  -d "username=admin&password=admin123"
# Expected: 401 Unauthorized

# Test new credentials work
curl -X POST http://localhost:8000/api/auth/login \
  -d "username=admin&password=<new-password>"
# Expected: 200 OK with token
```

**Effort**: 1 hour  
**Risk if not fixed**: 🔴 **CRITICAL** - Complete system compromise

---

### Security Issue #2: Default SECRET_KEY
**Status**: [ ] Not Started / [ ] In Progress / [ ] Complete

**Current State**:
```python
# api/app.py line 52
SECRET_KEY = os.getenv("SECRET_KEY", "default-fallback-secret-key-CHANGE-ME")
# ❌ Has fallback default
```

**Required Fix**:
```python
# api/app.py line 52-57
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable must be set")
if any(word in SECRET_KEY.lower() for word in ["default", "change", "example", "test"]):
    raise ValueError("SECRET_KEY appears to be a default/example value")
if len(SECRET_KEY) < 32:
    raise ValueError("SECRET_KEY must be at least 32 characters")

ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))
```

**Steps**:
1. [ ] Generate strong secret: `openssl rand -hex 32`
2. [ ] Add SECRET_KEY to `.env` file
3. [ ] Edit `api/app.py` to validate SECRET_KEY
4. [ ] Remove fallback default value
5. [ ] Test that app refuses to start without valid SECRET_KEY
6. [ ] Document SECRET_KEY in secure location

**Verification**:
```bash
# Test app requires SECRET_KEY
unset SECRET_KEY
python -m uvicorn api.app:app
# Expected: ValueError about SECRET_KEY

# Test app rejects default values
export SECRET_KEY="default-secret-key"
python -m uvicorn api.app:app
# Expected: ValueError about default value

# Test app starts with valid key
export SECRET_KEY="<generated-hex-string>"
python -m uvicorn api.app:app
# Expected: Server starts successfully
```

**Effort**: 30 minutes  
**Risk if not fixed**: 🔴 **CRITICAL** - Token forgery, session hijacking

---

### Environment Configuration Checklist
**Status**: [ ] Not Started / [ ] In Progress / [ ] Complete

**Create Production `.env` File**:
```bash
# .env (production)

# === CRITICAL: Change all of these ===
SECRET_KEY=<generate with: openssl rand -hex 32>
ADMIN_DEFAULT_PASSWORD=<generate with: openssl rand -base64 24>
DB_PASSWORD=<generate strong password>
REDIS_PASSWORD=<generate strong password>

# === Database Configuration ===
DATABASE_URL=postgresql://dcs_user:${DB_PASSWORD}@postgres:5432/neurosurgical_dcs

# === Redis Configuration ===
REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0

# === Security ===
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=480

# === CORS (Update for production domain) ===
CORS_ORIGINS=https://your-domain.com,https://api.your-domain.com

# === Features ===
ENABLE_LEARNING_SYSTEM=true
REQUIRE_LEARNING_APPROVAL=true
USE_CACHE=true
USE_PARALLEL_PROCESSING=true
```

**Steps**:
1. [ ] Copy `.env.example` to `.env`
2. [ ] Generate SECRET_KEY (32+ characters)
3. [ ] Generate ADMIN_DEFAULT_PASSWORD
4. [ ] Generate DB_PASSWORD
5. [ ] Generate REDIS_PASSWORD
6. [ ] Update CORS_ORIGINS with production domain
7. [ ] Store all secrets in secure password manager
8. [ ] Add `.env` to `.gitignore` (verify it's there)
9. [ ] Test configuration loads correctly

**Verification**:
```bash
# Verify .env is not tracked
git status
# .env should NOT appear in untracked files

# Verify secrets are loaded
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('SECRET_KEY length:', len(os.getenv('SECRET_KEY', '')))"
# Expected: Length should be 64 (32 bytes hex)
```

**Effort**: 1 hour  
**Risk if not fixed**: 🔴 **CRITICAL** - Insecure deployment

---

## 🟡 HIGH PRIORITY - FIX BEFORE PROD (Day 3-4)

### Test Issue #3: Integration Test Failures
**Status**: [ ] Not Started / [ ] In Progress / [ ] Complete

**Current State**:
```
✗ 4 integration tests failing
Error: sqlite3.OperationalError: no such table: users
```

**Root Cause**: Test fixtures not initializing database tables

**Required Fix**:
```python
# tests/integration/test_auth_and_learning_fixes.py
import pytest
from api.app import app
from src.database.models import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

@pytest.fixture
def test_engine():
    # Create in-memory SQLite for tests
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    # ✅ CREATE ALL TABLES
    Base.metadata.create_all(bind=engine)
    return engine

@pytest.fixture
def test_db_session(test_engine):
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def client(test_engine, test_db_session):
    # Override get_db dependency
    def override_get_db():
        try:
            yield test_db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)
```

**Steps**:
1. [ ] Open `tests/integration/test_auth_and_learning_fixes.py`
2. [ ] Add `Base.metadata.create_all()` in test fixtures
3. [ ] Ensure each test gets fresh database
4. [ ] Run integration tests: `pytest tests/integration/test_auth_and_learning_fixes.py -v`
5. [ ] Verify all 4 tests pass

**Verification**:
```bash
pytest tests/integration/test_auth_and_learning_fixes.py -v
# Expected output:
# test_database_backed_login_success PASSED
# test_database_backed_login_failure PASSED
# test_get_current_user_from_db PASSED
# test_submit_feedback_with_auto_approve PASSED
# 4 passed

# Run full test suite
pytest tests/ -v
# Expected: 196/196 passing (100%)
```

**Effort**: 2 hours  
**Risk if not fixed**: 🟡 HIGH - Cannot validate API authentication

---

### Frontend Issue #4: npm Vulnerabilities
**Status**: [ ] Not Started / [ ] In Progress / [ ] Complete

**Current State**:
```
9 vulnerabilities (8 moderate, 1 critical)
```

**Steps**:
1. [ ] Navigate to frontend: `cd frontend`
2. [ ] Check details: `npm audit`
3. [ ] Review critical vulnerability
4. [ ] Attempt automatic fix: `npm audit fix`
5. [ ] If that fails, try: `npm audit fix --force`
6. [ ] Test build: `npm run build`
7. [ ] Test dev server: `npm run dev`
8. [ ] Verify no regressions

**Verification**:
```bash
cd frontend

# Before fix
npm audit
# Note the vulnerabilities

# Run fix
npm audit fix

# Check results
npm audit
# Expected: Reduced vulnerability count

# Test build still works
npm run build
# Expected: Successful build

# Test dev server
npm run dev
# Expected: Server starts, app works
```

**Notes**:
- Most are dev dependencies (lower risk)
- Some may require manual review
- Document any unfixable vulnerabilities

**Effort**: 4 hours  
**Risk if not fixed**: 🟡 HIGH - Potential XSS or other frontend attacks

---

### Code Quality Issue #5: Deprecated datetime.utcnow()
**Status**: [ ] Not Started / [ ] In Progress / [ ] Complete

**Current State**:
```
44 warnings: datetime.utcnow() is deprecated
Will break in Python 3.12+
```

**Required Fix**:
```python
# OLD (deprecated)
from datetime import datetime
timestamp = datetime.utcnow()

# NEW (Python 3.11+)
from datetime import datetime, UTC
timestamp = datetime.now(UTC)
```

**Steps**:
1. [ ] Find all occurrences: `grep -r "datetime.utcnow()" src/ api/ tests/`
2. [ ] Replace in `api/app.py` (2 occurrences)
3. [ ] Replace in `tests/unit/test_database_models.py` (2 occurrences)
4. [ ] Replace in any other files found
5. [ ] Update imports to include `UTC`
6. [ ] Run tests to verify: `pytest tests/`

**Verification**:
```bash
# Find all occurrences
grep -r "datetime.utcnow()" src/ api/ tests/
# Expected: No matches

# Run tests
pytest tests/ -v
# Expected: 196/196 passing, no deprecation warnings

# Check warnings specifically
pytest tests/ -v -W default 2>&1 | grep -i "utcnow"
# Expected: No output
```

**Effort**: 3 hours  
**Risk if not fixed**: 🟡 MEDIUM - Will break in Python 3.12+

---

## 🟢 OPTIONAL - NICE TO HAVE (Week 1-2)

### Enhancement #6: Initialize Alembic Migrations
**Status**: [ ] Not Started / [ ] In Progress / [ ] Complete

**Current State**: Tables created via `Base.metadata.create_all()` (works but not best practice)

**Steps**:
1. [ ] Install alembic: `pip install alembic` (already in requirements.txt)
2. [ ] Initialize: `alembic init alembic`
3. [ ] Edit `alembic.ini` with database URL
4. [ ] Create initial migration: `alembic revision --autogenerate -m "Initial schema"`
5. [ ] Review generated migration
6. [ ] Test upgrade: `alembic upgrade head`
7. [ ] Document migration workflow

**Verification**:
```bash
alembic current
# Expected: Shows current revision

alembic history
# Expected: Shows migration history
```

**Effort**: 2 hours  
**Impact**: Better schema change tracking

---

### Enhancement #7: Add Redis to CI/CD
**Status**: [ ] Not Started / [ ] In Progress / [ ] Complete

**Current State**: 17 Redis integration tests skipped

**Steps**:
1. [ ] Create `docker-compose.test.yml`
2. [ ] Add Redis service for testing
3. [ ] Update CI/CD pipeline to start Redis
4. [ ] Run Redis tests: `pytest tests/unit/test_redis_cache.py -v`
5. [ ] Verify 17/17 Redis tests pass

**Verification**:
```bash
# Start Redis for testing
docker-compose -f docker-compose.test.yml up -d redis

# Run Redis tests
pytest tests/unit/test_redis_cache.py -v
# Expected: 17/17 passing

# Full test suite with Redis
pytest tests/ -v
# Expected: 213/213 passing (100%)
```

**Effort**: 4 hours  
**Impact**: Complete test coverage

---

### Enhancement #8: Migrate to FastAPI Lifespan
**Status**: [ ] Not Started / [ ] In Progress / [ ] Complete

**Current State**: Using deprecated `@app.on_event("startup")`

**Required Fix**:
```python
# OLD (deprecated)
@app.on_event("startup")
async def startup_event():
    # initialization
    pass

@app.on_event("shutdown")
async def shutdown_event():
    # cleanup
    pass

# NEW (recommended)
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global engine
    engine = HybridNeurosurgicalDCSEngine(...)
    await engine.initialize()
    
    yield
    
    # Shutdown
    if engine:
        await engine.shutdown()

app = FastAPI(lifespan=lifespan)
```

**Steps**:
1. [ ] Refactor `api/app.py` startup/shutdown
2. [ ] Use `@asynccontextmanager` and lifespan parameter
3. [ ] Test startup and shutdown
4. [ ] Verify no deprecation warnings

**Effort**: 2 hours  
**Impact**: Future-proof API

---

## 📋 Pre-Deployment Testing Checklist

### Unit & Integration Tests
- [ ] All 196 tests passing: `pytest tests/ -v`
- [ ] No test failures
- [ ] No deprecation warnings
- [ ] Test coverage >95%: `pytest --cov=src tests/`

### Security Testing
- [ ] Cannot login with default admin/admin123
- [ ] Cannot use default SECRET_KEY
- [ ] JWT tokens expire correctly (8 hours)
- [ ] Role-based access control works (test resident vs admin)
- [ ] Audit logs being written to database

### Functional Testing
- [ ] Can login with new admin credentials
- [ ] Can process sample documents
- [ ] Can submit learning feedback
- [ ] Admin can approve/reject patterns
- [ ] Only approved patterns auto-applied
- [ ] Cache improves performance (10x+)

### Performance Testing
- [ ] Process 3 documents: <100ms
- [ ] Process 10 documents: <1s (with cache)
- [ ] First request: <8s (no cache)
- [ ] Subsequent: <1s (cached)

### Frontend Testing
- [ ] Frontend builds: `cd frontend && npm run build`
- [ ] Dev server starts: `npm run dev`
- [ ] Can login via UI
- [ ] Can upload documents
- [ ] Results display correctly
- [ ] Learning pattern viewer works
- [ ] Approve button functions

### Deployment Testing
- [ ] Docker compose up: `docker-compose up -d`
- [ ] All services healthy: `docker-compose ps`
- [ ] API health check: `curl http://localhost:8000/api/system/health`
- [ ] Frontend loads: Open http://localhost
- [ ] Can login via frontend
- [ ] Process document end-to-end

---

## 🚀 Production Deployment Steps

### Step 1: Final Configuration Review
- [ ] Review `.env` file
- [ ] All secrets generated and documented
- [ ] CORS_ORIGINS set to production domains
- [ ] Database URL configured
- [ ] Redis URL configured
- [ ] SSL certificates ready

### Step 2: Database Setup
```bash
# PostgreSQL
createdb neurosurgical_dcs

# Run migrations (if using Alembic)
alembic upgrade head

# Or let app auto-create tables
# Tables will be created on first startup
```

### Step 3: Deploy Application
```bash
# Option 1: Docker Compose
docker-compose up -d

# Option 2: Production script
./deploy.sh --deploy

# Option 3: Manual
uvicorn api.app:app --host 0.0.0.0 --port 8000 --workers 4
```

### Step 4: Verify Deployment
- [ ] Health check returns 200
- [ ] Can login with admin credentials
- [ ] Process sample document successfully
- [ ] No errors in logs
- [ ] Performance within targets

### Step 5: Post-Deployment
- [ ] Set up monitoring (Prometheus/Grafana)
- [ ] Configure backups (database + Redis)
- [ ] Set up alerting
- [ ] Document runbook for common issues
- [ ] Train users on system

---

## 📊 Progress Tracking

### Overall Progress: [ ] 0% → [ ] 100%

**Day 1-2: Security Hardening**
- [ ] Issue #1: Default admin credentials (1h)
- [ ] Issue #2: Default SECRET_KEY (30min)
- [ ] Environment configuration (1h)
**Progress**: 0/3 complete

**Day 3: Fix Tests**
- [ ] Issue #3: Integration tests (2h)
**Progress**: 0/1 complete

**Day 4: Frontend Security**
- [ ] Issue #4: npm vulnerabilities (4h)
**Progress**: 0/1 complete

**Day 5: Optional Improvements**
- [ ] Issue #5: Deprecated datetime (3h)
- [ ] Enhancement #6: Alembic migrations (2h)
- [ ] Enhancement #7: Redis CI/CD (4h)
- [ ] Enhancement #8: FastAPI lifespan (2h)
**Progress**: 0/4 complete

**Day 5: Final Verification**
- [ ] All tests passing
- [ ] Deployment to staging
- [ ] Manual smoke test
- [ ] Performance validation
- [ ] Go/No-Go decision
**Progress**: 0/5 complete

---

## ✅ Sign-Off

### Critical Issues Fixed
- [ ] Issue #1: Default admin credentials - **BLOCKER** 🔴
- [ ] Issue #2: Default SECRET_KEY - **BLOCKER** 🔴
- [ ] Issue #3: Integration tests - HIGH 🟡
- [ ] Issue #4: npm vulnerabilities - HIGH 🟡

### Testing Complete
- [ ] 196/196 tests passing (100%)
- [ ] No security vulnerabilities
- [ ] Performance targets met
- [ ] Manual smoke test passed

### Documentation
- [ ] Production credentials documented
- [ ] Deployment runbook created
- [ ] User training completed

### Approvals
- [ ] Technical Lead: _____________________ Date: _______
- [ ] Security Team: _____________________ Date: _______
- [ ] Product Owner: _____________________ Date: _______

### Production Deployment
- [ ] Staging deployment successful
- [ ] Production deployment scheduled
- [ ] Rollback plan documented
- [ ] Monitoring configured
- [ ] **GO FOR PRODUCTION** ✅

---

**Checklist Version**: 1.0  
**Last Updated**: November 15, 2024  
**Next Review**: After each issue completion

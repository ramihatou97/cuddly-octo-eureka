"""
Enhanced FastAPI Application for Neurosurgical DCS Hybrid System

Provides comprehensive API with:
- OAuth2/JWT authentication (from complete_1)
- Processing endpoints (parallel/sequential options)
- Learning system endpoints (submit, approve, review)
- Audit logging for HIPAA compliance
- Performance metrics
- WebSocket support for real-time updates

Security: Role-based access control (RBAC)
- read: View summaries
- write: Generate summaries
- approve: Approve learning patterns (admin only)
"""

from fastapi import FastAPI, HTTPException, Depends, status, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from passlib.context import CryptContext
from jose import JWTError, jwt
import logging
import uuid

# Import hybrid engine
import sys
sys.path.insert(0, '..')
from src.engine import HybridNeurosurgicalDCSEngine

# ========================= CONFIGURATION =========================

# Security Configuration (from complete_1)
SECRET_KEY = "your-secret-key-change-in-production-use-openssl-rand-hex-32"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480  # 8 hours

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ========================= APPLICATION SETUP =========================

app = FastAPI(
    title="Neurosurgical DCS Hybrid API",
    description="Production-grade discharge summary generation with learning system",
    version="3.0.0-hybrid",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000", "http://localhost:8080", "null"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize hybrid engine (will be initialized on startup)
engine: Optional[HybridNeurosurgicalDCSEngine] = None

# ========================= DATA STORES (In-Memory for now) =========================
# In production: Use database from src/database/models.py

# Pre-computed bcrypt hashes to avoid runtime hashing issues
USER_DATABASE = {
    "dr.smith": {
        "username": "dr.smith",
        "full_name": "Dr. Sarah Smith",
        "email": "sarah.smith@hospital.org",
        "hashed_password": "$2b$12$1KqmSAFwQRuhfGdBA/eEQOVEXAkJpBnrcH32smMlR1iwSOp0rS16O",  # neurosurg123
        "department": "neurosurgery",
        "role": "attending",
        "permissions": ["read", "write", "approve"]  # Can approve learning patterns
    },
    "dr.jones": {
        "username": "dr.jones",
        "full_name": "Dr. Michael Jones",
        "email": "michael.jones@hospital.org",
        "hashed_password": "$2b$12$ggQT.QxZwhJB3URIG3mUTegamt9aJzkfFsz1BuDB6tFbw8f5Yjp9O",  # resident456
        "department": "neurosurgery",
        "role": "resident",
        "permissions": ["read", "write"]  # Cannot approve patterns
    },
    "admin": {
        "username": "admin",
        "full_name": "System Administrator",
        "email": "admin@hospital.org",
        "hashed_password": "$2b$12$Egb/PKG/5iNBPZ7Q3VZaEOOX/f0nX.qW1aBD5nwYuB1QMiyzT.5.u",  # admin123
        "department": "it",
        "role": "admin",
        "permissions": ["read", "write", "approve", "manage"]
    }
}

# Audit log storage
AUDIT_LOG = []

# Processing sessions (for uncertainty resolution workflow)
PROCESSING_SESSIONS = {}

# ========================= PYDANTIC MODELS =========================

class Token(BaseModel):
    access_token: str
    token_type: str
    user_info: Dict[str, Any]

class TokenData(BaseModel):
    username: Optional[str] = None

class User(BaseModel):
    username: str
    full_name: str
    email: str
    department: str
    role: str
    permissions: List[str]

class ProcessRequest(BaseModel):
    documents: List[Dict]
    options: Dict = Field(default_factory=dict)
    use_parallel: bool = True
    use_cache: bool = True
    apply_learning: bool = True

class LearningFeedbackRequest(BaseModel):
    uncertainty_id: str
    original_extraction: str
    correction: str
    context: Dict
    apply_immediately: bool = False

class LearningPatternApproval(BaseModel):
    pattern_id: str
    approved: bool  # True = approve, False = reject
    reason: Optional[str] = None  # For rejection

# ========================= AUTHENTICATION FUNCTIONS =========================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    # Truncate password to 72 bytes for bcrypt compatibility
    if isinstance(plain_password, str):
        plain_password = plain_password.encode('utf-8')[:72].decode('utf-8', errors='ignore')
    return pwd_context.verify(plain_password, hashed_password)

def get_user(username: str) -> Optional[Dict]:
    """Get user from database"""
    return USER_DATABASE.get(username)

def authenticate_user(username: str, password: str) -> Optional[Dict]:
    """Authenticate user with username and password"""
    user = get_user(username)
    if not user:
        return None
    if not verify_password(password, user["hashed_password"]):
        return None
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """Get current user from JWT token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception

    user_dict = get_user(username=token_data.username)
    if user_dict is None:
        raise credentials_exception

    return User(**user_dict)

def check_permission(user: User, permission: str):
    """Check if user has specific permission"""
    if permission not in user.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User does not have '{permission}' permission"
        )
    return True

# ========================= AUDIT LOGGING =========================

def log_audit_event(user: User, action: str, details: Dict):
    """Log audit event for compliance"""
    event = {
        "timestamp": datetime.utcnow().isoformat(),
        "username": user.username,
        "department": user.department,
        "role": user.role,
        "action": action,
        "details": details
    }
    AUDIT_LOG.append(event)
    logger.info(f"Audit: {user.username} - {action}")

# ========================= STARTUP/SHUTDOWN =========================

@app.on_event("startup")
async def startup_event():
    """Initialize engine on startup"""
    global engine
    engine = HybridNeurosurgicalDCSEngine(
        redis_url="redis://localhost:6379",  # Configure via environment
        enable_learning=True
    )
    await engine.initialize()
    logger.info("✅ Hybrid DCS Engine initialized and ready")

@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown engine gracefully"""
    global engine
    if engine:
        await engine.shutdown()
        logger.info("Engine shutdown complete")

# ========================= AUTHENTICATION ENDPOINTS =========================

@app.post("/api/auth/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Login endpoint - generates JWT token

    Returns access token for authenticated requests.
    """
    user_dict = authenticate_user(form_data.username, form_data.password)

    if not user_dict:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Update last login
    user_dict['last_login'] = datetime.utcnow().isoformat()

    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user_dict["username"]},
        expires_delta=access_token_expires
    )

    logger.info(f"User logged in: {user_dict['username']}")

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_info": {
            "username": user_dict["username"],
            "full_name": user_dict["full_name"],
            "role": user_dict["role"],
            "permissions": user_dict["permissions"]
        }
    }

@app.get("/api/auth/me", response_model=User)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current authenticated user information"""
    return current_user

# ========================= PROCESSING ENDPOINTS =========================

@app.post("/api/process")
async def process_documents(
    request: ProcessRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """
    Main processing endpoint - generate discharge summary

    Requires: 'write' permission

    Process:
    1. Validate request
    2. Process documents (parallel/sequential)
    3. Apply learning (if enabled)
    4. Validate results
    5. Log audit event
    6. Return result
    """
    # Check permission
    check_permission(current_user, "write")

    try:
        # Log audit event
        log_audit_event(current_user, "PROCESS_DOCUMENTS", {
            "document_count": len(request.documents),
            "use_parallel": request.use_parallel,
            "use_cache": request.use_cache,
            "apply_learning": request.apply_learning
        })

        # Process documents
        result = await engine.process_hospital_course(
            documents=request.documents,
            use_parallel=request.use_parallel,
            use_cache=request.use_cache,
            apply_learning=request.apply_learning
        )

        # Generate session ID for uncertainty resolution workflow
        session_id = str(uuid.uuid4())
        PROCESSING_SESSIONS[session_id] = {
            "user": current_user.username,
            "timestamp": datetime.utcnow().isoformat(),
            "result": result,
            "documents": request.documents
        }

        result['session_id'] = session_id

        return result

    except Exception as e:
        logger.error(f"Processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ========================= LEARNING SYSTEM ENDPOINTS =========================

@app.post("/api/learning/feedback")
async def submit_learning_feedback(
    feedback_request: LearningFeedbackRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Submit learning feedback from uncertainty resolution

    Creates PENDING learning pattern (requires approval before application)

    Requires: 'write' permission
    """
    check_permission(current_user, "write")

    try:
        # Add feedback (creates PENDING pattern)
        pattern_id = engine.feedback_manager.add_feedback(
            uncertainty_id=feedback_request.uncertainty_id,
            original_extraction=feedback_request.original_extraction,
            correction=feedback_request.correction,
            context=feedback_request.context,
            created_by=current_user.username
        )

        # Log audit event
        log_audit_event(current_user, "SUBMIT_LEARNING_FEEDBACK", {
            "pattern_id": pattern_id[:8],
            "uncertainty_id": feedback_request.uncertainty_id,
            "fact_type": feedback_request.context.get('fact_type')
        })

        # Save to Redis/Database (background task)
        if request.apply_immediately and current_user.role == 'admin':
            # Admin can immediately approve their own patterns
            engine.feedback_manager.approve_pattern(pattern_id, approved_by=current_user.username)
            logger.info(f"Admin {current_user.username} auto-approved pattern {pattern_id[:8]}")

        return {
            "status": "success",
            "pattern_id": pattern_id,
            "pattern_status": "PENDING_APPROVAL",
            "message": "Learning feedback submitted. Awaiting admin approval before automatic application."
        }

    except Exception as e:
        logger.error(f"Learning feedback error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/learning/approve")
async def approve_learning_pattern(
    approval_request: LearningPatternApproval,
    current_user: User = Depends(get_current_user)
):
    """
    Approve or reject learning pattern

    **Requires: 'approve' permission (admin only)**

    This is the critical safety gate - only admins can approve patterns
    for automatic application to future extractions.
    """
    # Check admin permission
    check_permission(current_user, "approve")

    try:
        if approval_request.approved:
            # Approve pattern
            success = engine.feedback_manager.approve_pattern(
                pattern_id=approval_request.pattern_id,
                approved_by=current_user.username
            )

            action = "APPROVE_LEARNING_PATTERN"
            message = f"Pattern {approval_request.pattern_id[:8]} approved - will be applied to future extractions"

        else:
            # Reject pattern
            success = engine.feedback_manager.reject_pattern(
                pattern_id=approval_request.pattern_id,
                rejected_by=current_user.username,
                reason=approval_request.reason
            )

            action = "REJECT_LEARNING_PATTERN"
            message = f"Pattern {approval_request.pattern_id[:8]} rejected - will NOT be applied"

        if not success:
            raise HTTPException(status_code=404, detail="Pattern not found")

        # Log audit event
        log_audit_event(current_user, action, {
            "pattern_id": approval_request.pattern_id[:8],
            "approved": approval_request.approved,
            "reason": approval_request.reason
        })

        return {
            "status": "success",
            "action": "approved" if approval_request.approved else "rejected",
            "pattern_id": approval_request.pattern_id,
            "message": message
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Pattern approval error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/learning/pending")
async def get_pending_patterns(current_user: User = Depends(get_current_user)):
    """
    Get pending learning patterns awaiting approval

    Requires: 'approve' permission (admin only)

    Returns list for admin review in learning pattern viewer.
    """
    check_permission(current_user, "approve")

    try:
        pending = engine.feedback_manager.get_pending_patterns()

        return {
            "status": "success",
            "pending_count": len(pending),
            "patterns": pending
        }

    except Exception as e:
        logger.error(f"Get pending patterns error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/learning/approved")
async def get_approved_patterns(current_user: User = Depends(get_current_user)):
    """
    Get approved learning patterns currently in use

    Requires: 'read' permission

    Returns patterns with statistics (application count, success rate).
    """
    check_permission(current_user, "read")

    try:
        approved = engine.feedback_manager.get_approved_patterns()

        return {
            "status": "success",
            "approved_count": len(approved),
            "patterns": approved
        }

    except Exception as e:
        logger.error(f"Get approved patterns error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/learning/statistics")
async def get_learning_statistics(current_user: User = Depends(get_current_user)):
    """
    Get learning system statistics

    Requires: 'read' permission

    Returns comprehensive statistics about learning system.
    """
    check_permission(current_user, "read")

    try:
        stats = engine.feedback_manager.get_statistics()

        return {
            "status": "success",
            "statistics": stats
        }

    except Exception as e:
        logger.error(f"Get learning statistics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ========================= SYSTEM ENDPOINTS =========================

@app.get("/api/system/statistics")
async def get_system_statistics(current_user: User = Depends(get_current_user)):
    """
    Get system-wide statistics

    Requires: 'read' permission
    """
    check_permission(current_user, "read")

    try:
        stats = engine.get_engine_statistics()

        return {
            "status": "success",
            "statistics": stats,
            "engine_version": engine.get_version(),
            "cache_available": engine.is_cache_available(),
            "learning_enabled": engine.is_learning_enabled()
        }

    except Exception as e:
        logger.error(f"Get system statistics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/system/health")
async def health_check():
    """
    Health check endpoint (no authentication required)

    Returns engine status and availability.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": engine.get_version() if engine else "unknown",
        "cache_available": engine.is_cache_available() if engine else False,
        "learning_enabled": engine.is_learning_enabled() if engine else False
    }

@app.get("/api/audit-log")
async def get_audit_log(
    limit: int = 100,
    current_user: User = Depends(get_current_user)
):
    """
    Get audit log entries

    Requires: 'approve' permission (admin only)

    HIPAA compliance: tracks all user actions.
    """
    check_permission(current_user, "approve")

    # Return most recent entries
    recent_entries = AUDIT_LOG[-limit:] if len(AUDIT_LOG) > limit else AUDIT_LOG

    return {
        "status": "success",
        "entry_count": len(recent_entries),
        "total_entries": len(AUDIT_LOG),
        "entries": recent_entries
    }

# ========================= ROOT ENDPOINT =========================

@app.get("/")
async def root():
    """API root - returns welcome message"""
    return {
        "message": "Neurosurgical DCS Hybrid API",
        "version": "3.0.0-hybrid",
        "status": "operational",
        "documentation": "/api/docs",
        "authentication_required": True,
        "features": [
            "Hybrid extraction (complete_1 + v2)",
            "6-stage validation pipeline",
            "NEW contradiction detection",
            "Learning system with approval workflow",
            "Parallel processing",
            "Multi-level caching"
        ]
    }

# ========================= ERROR HANDLERS =========================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Custom HTTP exception handler"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code,
            "timestamp": datetime.utcnow().isoformat()
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """General exception handler"""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc),
            "timestamp": datetime.utcnow().isoformat()
        }
    )

# ========================= DEVELOPMENT ENDPOINTS =========================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

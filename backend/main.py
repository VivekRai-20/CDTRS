import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    status,
    UploadFile,
    File,
    Form,
    WebSocket,
    WebSocketDisconnect
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

import models
import schemas
import crud

from database import engine, get_db
from models import UserRole, AttachmentType, SourceType, Priority


# =========================================================
# DATABASE TABLE CREATION
# =========================================================

models.Base.metadata.create_all(bind=engine)


# =========================================================
# FILE STORAGE — uploads/<year>/<doc_id>/<filename>
# =========================================================

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB
ALLOWED_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "image/jpeg",
    "image/png",
    "text/plain",
}


# =========================================================
# FASTAPI APPLICATION
# =========================================================

app = FastAPI(
    title="CDTRS V2 Backend",
    description="Centralized Document Tracking and Routing System — Complete V2 API",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


# =========================================================
# CORS MIDDLEWARE
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# AUTHENTICATION & ROLE GUARDS
# =========================================================

bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    token = credentials.credentials
    payload = crud.decode_access_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload missing user identity.",
        )

    user = crud.get_user_by_id(db, int(user_id))
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or account is inactive.",
        )

    return user


def require_roles(*roles: UserRole):
    """Enforces server-side role-based access control."""
    def _check(current_user: models.User = Depends(get_current_user)):
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role(s): {[r.value for r in roles]}",
            )
        return current_user
    return _check


# =========================================================
# SECURITY & ISOLATION HELPERS
# =========================================================

def _get_authorized_doc_or_404(db: Session, doc_id: int, user: models.User) -> models.Document:
    doc = crud.get_document(db, doc_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    if not crud.is_document_accessible(db, doc, user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this document.")

    return doc


def _assert_not_closed(doc: models.Document) -> None:
    if doc.current_stage == models.WorkflowStage.CLOSED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document is already closed. Normal workflow mutations are rejected.",
        )


API_V1 = "/api/v1"


# =========================================================
# BASIC / HEALTH CHECK
# =========================================================

@app.get("/", tags=["Health"])
def root():
    return {"message": "CDTRS V2 Backend is running", "version": "2.0.0"}


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "healthy", "version": "2.0.0"}


# =========================================================
# LIVE EVENT WEBSOCKET & FALLBACK EVENT STREAM
# =========================================================

@app.websocket(f"{API_V1}/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket connection endpoint for real-time live event streaming to connected PySide6 clients.
    Broadcasts events (DOCUMENT_CREATED, ROUTED, REMARK_UPDATED, PROGRESS_SUBMITTED, etc.)
    """
    await crud.event_manager.connect(websocket)
    try:
        while True:
            # Keep connection open and listen for client heartbeats
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        crud.event_manager.disconnect(websocket)
    except Exception:
        crud.event_manager.disconnect(websocket)


@app.get(
    f"{API_V1}/events/recent",
    tags=["Events"],
    summary="Get recent live events (Polling fallback)"
)
def get_recent_events(
    limit: int = 20,
    current_user: models.User = Depends(get_current_user)
):
    return crud.event_manager.get_recent_events(limit=limit)


# =========================================================
# AUTHENTICATION
# =========================================================

@app.post(
    f"{API_V1}/auth/login",
    response_model=schemas.LoginResponse,
    tags=["Authentication"],
    summary="Login and receive a JWT bearer token",
)
def login(
    login_data: schemas.LoginRequest,
    db: Session = Depends(get_db),
):
    user = crud.authenticate_user(db, login_data.username, login_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    token = crud.create_access_token(
        data={"sub": str(user.id), "role": user.role.value}
    )

    crud.create_audit_log(
        db=db,
        user_id=user.id,
        action="USER_LOGIN",
        entity_type="User",
        entity_id=user.id,
        description=f"User '{user.username}' logged in."
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user,
    }


@app.get(
    f"{API_V1}/auth/me",
    response_model=schemas.UserResponse,
    tags=["Authentication"],
    summary="Get current authenticated user",
)
def get_me(current_user: models.User = Depends(get_current_user)):
    return current_user


@app.post(
    f"{API_V1}/auth/logout",
    tags=["Authentication"],
    summary="Logout (client discards token)",
)
def logout(current_user: models.User = Depends(get_current_user)):
    return {"message": "Logged out successfully. Please discard your token."}


# =========================================================
# USERS & ROLES
# =========================================================

@app.post(
    f"{API_V1}/users",
    response_model=schemas.UserResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Users"],
    summary="Create a user account (DS only)",
)
def create_user(
    user: schemas.UserCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.DS)),
):
    existing = crud.get_user_by_username(db, user.username)
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already exists.")
    return crud.create_user(db, user)


@app.get(
    f"{API_V1}/users",
    response_model=List[schemas.UserResponse],
    tags=["Users"],
    summary="List all users (DS only)",
)
def get_users(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.DS)),
):
    return crud.get_users(db)


# =========================================================
# DEPARTMENTS
# =========================================================

@app.post(
    f"{API_V1}/departments",
    response_model=schemas.DepartmentResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Departments"],
    summary="Create a department (DS only)",
)
def create_department(
    dept: schemas.DepartmentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.DS)),
):
    return crud.create_department(db, dept)


@app.get(
    f"{API_V1}/departments",
    response_model=List[schemas.DepartmentResponse],
    tags=["Departments"],
    summary="List all active departments",
)
def get_departments(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return crud.get_departments(db)


@app.get(
    f"{API_V1}/departments/{{department_id}}/employees",
    response_model=List[schemas.EmployeeResponse],
    tags=["Departments"],
    summary="Get employees in a department",
)
def get_department_employees(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    dept = crud.get_department_by_id(db, department_id)
    if not dept:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found.")
    return crud.get_employees_by_department(db, department_id)


# =========================================================
# EMPLOYEES
# =========================================================

@app.post(
    f"{API_V1}/employees",
    response_model=schemas.EmployeeResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Employees"],
    summary="Create an employee record (DS only)",
)
def create_employee(
    emp: schemas.EmployeeCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.DS)),
):
    dept = crud.get_department_by_id(db, emp.department_id)
    if not dept:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found.")
    return crud.create_employee(db, emp)


@app.get(
    f"{API_V1}/employees",
    response_model=List[schemas.EmployeeResponse],
    tags=["Employees"],
    summary="List all active employees",
)
def get_employees(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return crud.get_employees(db)


# =========================================================
# INTAKE & MAIL INGESTION
# =========================================================

@app.get(
    f"{API_V1}/intake",
    response_model=List[schemas.IntakeResponse],
    tags=["Intake"],
    summary="DS: Get incoming mail/intake items",
)
def get_intake_items(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.DS)),
):
    return crud.get_incoming_messages(db)


@app.post(
    f"{API_V1}/intake/manual-upload",
    response_model=schemas.DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Intake"],
    summary="DS: Manual document upload via intake pipeline",
)
async def manual_intake_upload(
    title: str = Form(...),
    received_date: str = Form(...),
    mode: str = Form(default="Manual Upload"),
    priority: str = Form(default="MEDIUM"),
    description: Optional[str] = Form(default=None),
    source: Optional[str] = Form(default="Manual Intake"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.DS)),
):
    # 1. Create intake record
    intake_record = crud.create_incoming_message(
        db=db,
        intake=schemas.IntakeCreate(
            source_type=SourceType.MANUAL_UPLOAD,
            sender_name=source,
            subject=title,
            body_reference=description
        ),
        has_attachments=True
    )

    # 2. Create canonical document
    doc_create = schemas.DocumentCreate(
        title=title,
        description=description,
        received_date=datetime.strptime(received_date, "%Y-%m-%d").date(),
        source=source,
        mode=mode,
        priority=Priority(priority),
        source_message_id=intake_record.id
    )
    doc = crud.create_document(db, doc_create, created_by=current_user.id)

    # 3. Read and save file attachment with checksum
    contents = await file.read()
    checksum = crud.compute_checksum(contents)

    dest_dir = UPLOAD_DIR / str(datetime.utcnow().year) / str(doc.doc_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / Path(file.filename).name

    with open(dest_path, "wb") as f:
        f.write(contents)

    storage_key = str(dest_path.relative_to(UPLOAD_DIR))

    crud.create_attachment(
        db=db,
        doc_id=doc.doc_id,
        progress_update_id=None,
        uploaded_by=current_user.id,
        file_name=file.filename,
        storage_key=storage_key,
        file_type=file.content_type,
        file_size=len(contents),
        checksum=checksum,
        attachment_type=AttachmentType.ORIGINAL,
        source_message_id=intake_record.id
    )

    # 4. Automatically trigger OCR extraction
    crud.trigger_ocr_processing(db, doc.doc_id)

    # Broadcast event
    await crud.event_manager.broadcast("DOCUMENT_CREATED", document_id=doc.doc_id, user_id=current_user.id)

    db.refresh(doc)
    return doc


@app.post(
    f"{API_V1}/intake/{{id}}/process",
    response_model=schemas.DocumentResponse,
    tags=["Intake"],
    summary="DS: Process incoming mail item into canonical document",
)
async def process_intake(
    id: int,
    proc_req: schemas.IntakeProcessRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.DS)),
):
    doc = crud.process_intake_to_document(db, id, proc_req, current_user)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intake item not found.")

    crud.trigger_ocr_processing(db, doc.doc_id)
    await crud.event_manager.broadcast("DOCUMENT_CREATED", document_id=doc.doc_id, user_id=current_user.id)
    return doc


# =========================================================
# DOCUMENTS
# =========================================================

@app.post(
    f"{API_V1}/documents",
    response_model=schemas.DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Documents"],
    summary="DS: Register a new document",
)
async def create_document(
    doc: schemas.DocumentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.DS)),
):
    db_doc = crud.create_document(db, doc, created_by=current_user.id)
    crud.trigger_ocr_processing(db, db_doc.doc_id)
    await crud.event_manager.broadcast("DOCUMENT_CREATED", document_id=db_doc.doc_id, user_id=current_user.id)
    return db_doc


@app.get(
    f"{API_V1}/documents",
    response_model=List[schemas.DocumentListResponse],
    tags=["Documents"],
    summary="DS: Get all documents",
)
def get_documents(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.DS)),
):
    return crud.get_documents(db)


@app.get(
    f"{API_V1}/documents/inbox",
    response_model=List[schemas.DocumentListResponse],
    tags=["Documents"],
    summary="Get role-scoped inbox (DS, Director, HOD, Employee)",
)
def get_inbox(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return crud.get_inbox(db, current_user)


@app.get(
    f"{API_V1}/documents/{{document_id}}",
    response_model=schemas.DocumentResponse,
    tags=["Documents"],
    summary="Get a single document by ID (Authorized)",
)
def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return _get_authorized_doc_or_404(db, document_id, current_user)


# =========================================================
# WORKFLOW TRANSITIONS & CONCURRENCY
# =========================================================

@app.post(
    f"{API_V1}/documents/{{document_id}}/route",
    response_model=schemas.DocumentResponse,
    tags=["Documents — Workflow"],
    summary="DS: Route document to Director / HOD / Employee",
)
async def route_document(
    document_id: int,
    route_req: schemas.RouteRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.DS)),
):
    doc = _get_authorized_doc_or_404(db, document_id, current_user)
    _assert_not_closed(doc)

    result = crud.route_document(db, document_id, route_req, current_user)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conflict: Document state has been modified concurrently or invalid parameters.",
        )

    await crud.event_manager.broadcast("DOCUMENT_ROUTED", document_id=document_id, user_id=current_user.id)
    return result


@app.put(
    f"{API_V1}/documents/{{document_id}}/director-remark",
    response_model=schemas.DocumentResponse,
    tags=["Documents — Workflow"],
    summary="Director: Save/edit Director remark",
)
async def save_director_remark(
    document_id: int,
    body: schemas.DirectorRemarkUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.DIRECTOR)),
):
    doc = _get_authorized_doc_or_404(db, document_id, current_user)
    _assert_not_closed(doc)

    result = crud.save_director_remark(db, document_id, body.director_remark, current_user, body.expected_version)
    if not result:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Concurrency conflict or document not found.")

    await crud.event_manager.broadcast("REMARK_UPDATED", document_id=document_id, user_id=current_user.id)
    return result


@app.post(
    f"{API_V1}/documents/{{document_id}}/return-to-ds",
    response_model=schemas.DocumentResponse,
    tags=["Documents — Workflow"],
    summary="Director: Return document to DS",
)
async def return_to_ds(
    document_id: int,
    body: schemas.ReturnToDSRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.DIRECTOR)),
):
    doc = _get_authorized_doc_or_404(db, document_id, current_user)
    _assert_not_closed(doc)

    ds_user_id = doc.created_by
    result = crud.return_to_ds(db, document_id, ds_user_id, body.remarks, current_user, body.expected_version)
    if not result:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Concurrency conflict or document not found.")

    await crud.event_manager.broadcast("DOCUMENT_ROUTED", document_id=document_id, user_id=current_user.id)
    return result


@app.put(
    f"{API_V1}/documents/{{document_id}}/hod-remark",
    response_model=schemas.DocumentResponse,
    tags=["Documents — Workflow"],
    summary="HOD: Save/edit HOD remark",
)
async def save_hod_remark(
    document_id: int,
    body: schemas.HODRemarkUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.HOD)),
):
    doc = _get_authorized_doc_or_404(db, document_id, current_user)
    _assert_not_closed(doc)

    result = crud.save_hod_remark(db, document_id, body.hod_remark, current_user, body.expected_version)
    if not result:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Concurrency conflict or document not found.")

    await crud.event_manager.broadcast("REMARK_UPDATED", document_id=document_id, user_id=current_user.id)
    return result


@app.post(
    f"{API_V1}/documents/{{document_id}}/assign",
    response_model=schemas.AssignmentResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Documents — Workflow"],
    summary="HOD: Assign an employee to a document",
)
async def assign_employee(
    document_id: int,
    assign_req: schemas.AssignmentRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.HOD)),
):
    doc = _get_authorized_doc_or_404(db, document_id, current_user)
    _assert_not_closed(doc)

    target_user = crud.get_user_by_id(db, assign_req.assigned_to_user_id)
    if not target_user or target_user.role != UserRole.EMPLOYEE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target user must be an active EMPLOYEE.")

    result = crud.assign_employee(db, document_id, assign_req, current_user)
    if not result:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Concurrency conflict or document not found.")

    await crud.event_manager.broadcast("ASSIGNMENT_CREATED", document_id=document_id, user_id=current_user.id)
    return result


@app.post(
    f"{API_V1}/documents/{{document_id}}/progress",
    response_model=schemas.ProgressResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Documents — Progress"],
    summary="Employee: Submit progress update",
)
async def submit_progress(
    document_id: int,
    prog: schemas.ProgressCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.EMPLOYEE)),
):
    doc = _get_authorized_doc_or_404(db, document_id, current_user)
    _assert_not_closed(doc)

    result = crud.create_progress_update(db, document_id, prog, current_user)
    if not result:
        raise HTTPException(status_code=404, detail="Document not found.")

    await crud.event_manager.broadcast("PROGRESS_SUBMITTED", document_id=document_id, user_id=current_user.id)
    return result


@app.get(
    f"{API_V1}/documents/{{document_id}}/progress",
    response_model=List[schemas.ProgressResponse],
    tags=["Documents — Progress"],
    summary="Get all progress updates for a document",
)
def get_progress(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _get_authorized_doc_or_404(db, document_id, current_user)
    return crud.get_progress_updates(db, document_id)


@app.post(
    f"{API_V1}/documents/{{document_id}}/follow-up",
    response_model=schemas.DocumentResponse,
    tags=["Documents — Workflow"],
    summary="DS: Forward progress follow-up to Director",
)
async def follow_up_to_director(
    document_id: int,
    body: schemas.FollowUpRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.DS)),
):
    doc = _get_authorized_doc_or_404(db, document_id, current_user)
    _assert_not_closed(doc)

    directors = crud.get_users_by_role(db, UserRole.DIRECTOR)
    if not directors:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No active Director found.")

    result = crud.follow_up_to_director(db, document_id, directors[0], body.remarks, current_user, body.expected_version)
    if not result:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Concurrency conflict or document not found.")

    await crud.event_manager.broadcast("DOCUMENT_ROUTED", document_id=document_id, user_id=current_user.id)
    return result


@app.post(
    f"{API_V1}/documents/{{document_id}}/close",
    response_model=schemas.DocumentResponse,
    tags=["Documents — Workflow"],
    summary="DS: Close a document",
)
async def close_document(
    document_id: int,
    body: schemas.CloseRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.DS)),
):
    doc = _get_authorized_doc_or_404(db, document_id, current_user)
    if doc.current_stage == models.WorkflowStage.CLOSED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Document is already closed.")

    result = crud.close_document(db, document_id, body.remarks, current_user, body.expected_version)
    if not result:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Concurrency conflict or document not found.")

    await crud.event_manager.broadcast("DOCUMENT_CLOSED", document_id=document_id, user_id=current_user.id)
    return result


# =========================================================
# REMARK HISTORY
# =========================================================

@app.get(
    f"{API_V1}/documents/{{document_id}}/remarks",
    response_model=List[schemas.DocumentRemarkResponse],
    tags=["Documents — Workflow"],
    summary="Get remark edit history for a document",
)
def get_document_remarks(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _get_authorized_doc_or_404(db, document_id, current_user)
    return crud.get_document_remarks(db, document_id)


# =========================================================
# OCR PIPELINE & VERIFICATION
# =========================================================

@app.post(
    f"{API_V1}/documents/{{document_id}}/process-ocr",
    tags=["OCR"],
    summary="Start / run asynchronous OCR extraction",
)
async def process_ocr(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.DS)),
):
    doc = _get_authorized_doc_or_404(db, document_id, current_user)
    ocr_result = crud.trigger_ocr_processing(db, document_id)
    if not ocr_result:
        raise HTTPException(status_code=404, detail="Document not found.")

    await crud.event_manager.broadcast("OCR_COMPLETED", document_id=document_id, user_id=current_user.id)
    return {"message": "OCR processing completed", "ocr_status": ocr_result.ocr_status.value, "confidence": ocr_result.confidence}


@app.get(
    f"{API_V1}/documents/{{document_id}}/ocr",
    response_model=schemas.OCRResponse,
    tags=["OCR"],
    summary="Get OCR text and extracted structured fields",
)
def get_ocr_details(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    doc = _get_authorized_doc_or_404(db, document_id, current_user)
    ocr = crud.get_document_ocr(db, document_id)
    fields = db.query(models.DocumentExtractedField).filter(models.DocumentExtractedField.document_id == document_id).all()

    if not ocr:
        return schemas.OCRResponse(document_id=document_id, ocr_status=doc.ocr_status, extracted_fields=[])

    return schemas.OCRResponse(
        id=ocr.id,
        document_id=document_id,
        ocr_status=ocr.ocr_status,
        ocr_engine=ocr.ocr_engine,
        confidence=ocr.confidence,
        extracted_text=ocr.extracted_text,
        processed_at=ocr.processed_at,
        error_message=ocr.error_message,
        extracted_fields=fields
    )


@app.post(
    f"{API_V1}/documents/{{document_id}}/verify-field",
    response_model=schemas.ExtractedFieldResponse,
    tags=["OCR"],
    summary="DS: Verify/edit an extracted OCR field",
)
def verify_ocr_field(
    document_id: int,
    req: schemas.FieldVerifyRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.DS)),
):
    _get_authorized_doc_or_404(db, document_id, current_user)
    field = crud.verify_extracted_field(db, document_id, req.field_name, req.verified_value, current_user)
    return field


@app.post(
    f"{API_V1}/documents/{{document_id}}/reanalyze",
    tags=["OCR"],
    summary="DS: Re-analyze document without overwriting verified fields",
)
async def reanalyze_ocr(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.DS)),
):
    _get_authorized_doc_or_404(db, document_id, current_user)
    ocr_result = crud.reanalyze_document_ocr(db, document_id)
    await crud.event_manager.broadcast("OCR_COMPLETED", document_id=document_id, user_id=current_user.id)
    return {"message": "Re-analysis completed. Verified fields were preserved.", "confidence": ocr_result.confidence}


# =========================================================
# ROUTING INTELLIGENCE & ADVISORY SUGGESTIONS
# =========================================================

@app.post(
    f"{API_V1}/documents/{{document_id}}/analyze-routing",
    response_model=schemas.RoutingSuggestionResponse,
    tags=["Routing Intelligence"],
    summary="Generate advisory routing suggestions based on OCR & Director remarks",
)
def analyze_routing(
    document_id: int,
    body: schemas.RoutingAnalyzeRequest = schemas.RoutingAnalyzeRequest(),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.DS)),
):
    _get_authorized_doc_or_404(db, document_id, current_user)
    suggestion = crud.generate_routing_suggestion(db, document_id, body.include_director_remark)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Document not found.")

    dept_name = suggestion.suggested_department.name if suggestion.suggested_department else None
    emp_name = suggestion.suggested_employee.full_name if suggestion.suggested_employee else None

    return schemas.RoutingSuggestionResponse(
        id=suggestion.id,
        document_id=suggestion.document_id,
        suggested_department_id=suggestion.suggested_department_id,
        suggested_department_name=dept_name,
        suggested_employee_id=suggestion.suggested_employee_id,
        suggested_employee_name=emp_name,
        routing_confidence=suggestion.routing_confidence,
        routing_reason=suggestion.routing_reason,
        routing_source=suggestion.routing_source,
        is_director_instruction=suggestion.is_director_instruction,
        generated_at=suggestion.generated_at,
        confirmed_by=suggestion.confirmed_by,
        confirmed_at=suggestion.confirmed_at
    )


@app.get(
    f"{API_V1}/documents/{{document_id}}/routing-suggestion",
    response_model=schemas.RoutingSuggestionResponse,
    tags=["Routing Intelligence"],
    summary="Get current routing suggestion for a document",
)
def get_routing_suggestion_endpoint(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _get_authorized_doc_or_404(db, document_id, current_user)
    suggestion = crud.get_routing_suggestion(db, document_id)
    if not suggestion:
        suggestion = crud.generate_routing_suggestion(db, document_id)

    dept_name = suggestion.suggested_department.name if suggestion.suggested_department else None
    emp_name = suggestion.suggested_employee.full_name if suggestion.suggested_employee else None

    return schemas.RoutingSuggestionResponse(
        id=suggestion.id,
        document_id=suggestion.document_id,
        suggested_department_id=suggestion.suggested_department_id,
        suggested_department_name=dept_name,
        suggested_employee_id=suggestion.suggested_employee_id,
        suggested_employee_name=emp_name,
        routing_confidence=suggestion.routing_confidence,
        routing_reason=suggestion.routing_reason,
        routing_source=suggestion.routing_source,
        is_director_instruction=suggestion.is_director_instruction,
        generated_at=suggestion.generated_at,
        confirmed_by=suggestion.confirmed_by,
        confirmed_at=suggestion.confirmed_at
    )


# =========================================================
# ATTACHMENTS & SECURE DOWNLOAD
# =========================================================

@app.post(
    f"{API_V1}/documents/{{document_id}}/attachments",
    response_model=schemas.AttachmentResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Attachments"],
    summary="Upload an attachment for a document",
)
async def upload_attachment(
    document_id: int,
    file: UploadFile = File(...),
    progress_update_id: Optional[int] = Form(default=None),
    attachment_type: str = Form(default="SUPPORTING_DOCUMENT"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    doc = _get_authorized_doc_or_404(db, document_id, current_user)
    _assert_not_closed(doc)

    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type '{file.content_type}' is not allowed.",
        )

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File exceeds 20 MB limit.")

    checksum = crud.compute_checksum(contents)

    dest_dir = UPLOAD_DIR / str(datetime.utcnow().year) / str(document_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / Path(file.filename).name

    counter = 1
    stem = Path(file.filename).stem
    suffix = Path(file.filename).suffix
    while dest_path.exists():
        dest_path = dest_dir / f"{stem}_{counter}{suffix}"
        counter += 1

    with open(dest_path, "wb") as f:
        f.write(contents)

    storage_key = str(dest_path.relative_to(UPLOAD_DIR))

    att_type_enum = AttachmentType.PROGRESS_ATTACHMENT if progress_update_id else AttachmentType(attachment_type)

    attachment = crud.create_attachment(
        db=db,
        doc_id=document_id,
        progress_update_id=progress_update_id,
        uploaded_by=current_user.id,
        file_name=file.filename,
        storage_key=storage_key,
        file_type=file.content_type,
        file_size=len(contents),
        checksum=checksum,
        attachment_type=att_type_enum,
    )

    await crud.event_manager.broadcast("ATTACHMENT_ADDED", document_id=document_id, user_id=current_user.id)
    return attachment


@app.get(
    f"{API_V1}/documents/{{document_id}}/attachments",
    response_model=List[schemas.AttachmentResponse],
    tags=["Attachments"],
    summary="List all attachments for a document",
)
def get_document_attachments(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _get_authorized_doc_or_404(db, document_id, current_user)
    return crud.get_attachments(db, document_id)


@app.get(
    f"{API_V1}/attachments/{{attachment_id}}",
    response_model=schemas.AttachmentResponse,
    tags=["Attachments"],
    summary="Get attachment metadata",
)
def get_attachment(
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    att = crud.get_attachment(db, attachment_id)
    if not att:
        raise HTTPException(status_code=404, detail="Attachment not found.")
    _get_authorized_doc_or_404(db, att.document_id, current_user)
    return att


@app.get(
    f"{API_V1}/attachments/{{attachment_id}}/download",
    tags=["Attachments"],
    summary="Authorized file download",
)
def download_attachment(
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    att = crud.get_attachment(db, attachment_id)
    if not att:
        raise HTTPException(status_code=404, detail="Attachment not found.")

    # Strict authorization check against parent document
    _get_authorized_doc_or_404(db, att.document_id, current_user)

    file_path = UPLOAD_DIR / att.storage_key
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found on server storage.")

    return FileResponse(
        path=str(file_path),
        filename=att.file_name,
        media_type=att.file_type or "application/octet-stream",
    )


# =========================================================
# DOCUMENT HISTORY
# =========================================================

@app.get(
    f"{API_V1}/documents/{{document_id}}/history",
    response_model=List[schemas.WorkflowHistoryResponse],
    tags=["Documents"],
    summary="Get workflow history for a document",
)
def get_document_history(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _get_authorized_doc_or_404(db, document_id, current_user)
    return crud.get_document_history(db, document_id)


# =========================================================
# REMINDERS & DEADLINE ESCALATION
# =========================================================

@app.get(
    f"{API_V1}/reminders",
    response_model=List[schemas.ReminderResponse],
    tags=["Reminders"],
    summary="Get action/deadline reminders for current user",
)
def get_user_reminders(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return crud.get_reminders(db, current_user.id)


@app.post(
    f"{API_V1}/reminders/check",
    response_model=schemas.ReminderCheckResponse,
    tags=["Reminders"],
    summary="Trigger reminder generation & escalation scan",
)
def trigger_reminder_check(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.DS)),
):
    created = crud.generate_reminders(db)
    return schemas.ReminderCheckResponse(reminders_created=len(created), reminders=created)


@app.patch(
    f"{API_V1}/reminders/{{reminder_id}}/read",
    response_model=schemas.ReminderResponse,
    tags=["Reminders"],
    summary="Mark a reminder as read",
)
def mark_reminder_read_endpoint(
    reminder_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    rem = crud.mark_reminder_read(db, reminder_id, current_user.id)
    if not rem:
        raise HTTPException(status_code=404, detail="Reminder not found.")
    return rem


# =========================================================
# NOTIFICATIONS
# =========================================================

@app.get(
    f"{API_V1}/notifications",
    response_model=List[schemas.NotificationResponse],
    tags=["Notifications"],
    summary="Get all notifications for current user",
)
def get_notifications(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return crud.get_notifications(db, current_user.id)


@app.get(
    f"{API_V1}/notifications/unread",
    response_model=List[schemas.NotificationResponse],
    tags=["Notifications"],
    summary="Get unread notifications for current user",
)
def get_unread_notifications(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return crud.get_unread_notifications(db, current_user.id)


@app.patch(
    f"{API_V1}/notifications/{{notification_id}}/read",
    response_model=schemas.NotificationResponse,
    tags=["Notifications"],
    summary="Mark a notification as read",
)
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    notif = crud.mark_notification_read(db, notification_id, current_user.id)
    if not notif:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found.")
    return notif


@app.patch(
    f"{API_V1}/notifications/read-all",
    tags=["Notifications"],
    summary="Mark all notifications as read",
)
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    count = crud.mark_all_notifications_read(db, current_user.id)
    return {"message": f"{count} notification(s) marked as read."}


# =========================================================
# DASHBOARD
# =========================================================

@app.get(
    f"{API_V1}/dashboard",
    response_model=schemas.DashboardResponse,
    tags=["Dashboard"],
    summary="Get role-specific dashboard statistics",
)
def get_dashboard(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return crud.get_dashboard_stats(db, current_user)


# =========================================================
# STARTUP HOOK & SEED DATA
# =========================================================

@app.on_event("startup")
def on_startup():
    if os.getenv("SEED_DB", "false").lower() == "true":
        from database import SessionLocal
        db = SessionLocal()
        try:
            crud.seed_data(db)
        finally:
            db.close()
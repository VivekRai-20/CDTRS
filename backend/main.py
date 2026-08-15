import os
import shutil
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
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

import models
import schemas
import crud

from database import engine, get_db
from models import UserRole


# =========================================================
# DATABASE TABLE CREATION
# =========================================================

models.Base.metadata.create_all(bind=engine)


# =========================================================
# FILE STORAGE  — uploads/<year>/<doc_id>/<filename>
# =========================================================

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE = 20 * 1024 * 1024          # 20 MB
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
    title       = "CDTRS V2 Backend",
    description = "Centralized Document Tracking and Routing System — V2 API",
    version     = "2.0.0",
    docs_url    = "/docs",
    redoc_url   = "/redoc",
)


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],   # Lock down in production
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)


# =========================================================
# JWT AUTH DEPENDENCY
# =========================================================

bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> models.User:

    token   = credentials.credentials
    payload = crud.decode_access_token(token)

    if payload is None:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail      = "Invalid or expired token.",
            headers     = {"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail      = "Token payload missing user identity.",
        )

    user = crud.get_user_by_id(db, int(user_id))
    if not user or not user.is_active:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail      = "User not found or inactive.",
        )

    return user


def require_roles(*roles: UserRole):
    """Returns a dependency that enforces role-based access."""

    def _check(current_user: models.User = Depends(get_current_user)):
        if current_user.role not in roles:
            raise HTTPException(
                status_code = status.HTTP_403_FORBIDDEN,
                detail      = f"Access denied. Required role(s): {[r.value for r in roles]}",
            )
        return current_user

    return _check


# =========================================================
# HELPER — document access guard
# =========================================================

def _get_doc_or_404(db: Session, doc_id: int) -> models.Document:
    doc = crud.get_document(db, doc_id)
    if not doc:
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail      = "Document not found.",
        )
    return doc


def _assert_not_closed(doc: models.Document) -> None:
    if doc.current_stage == models.WorkflowStage.CLOSED:
        raise HTTPException(
            status_code = status.HTTP_409_CONFLICT,
            detail      = "Document is already closed. Workflow actions are disabled.",
        )


# =========================================================
# API PREFIX
# =========================================================

API_V1 = "/api/v1"


# =========================================================
# BASIC / HEALTH
# =========================================================

@app.get("/", tags=["Health"])
def root():
    return {"message": "CDTRS V2 Backend is running", "version": "2.0.0"}


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "healthy", "version": "2.0.0"}


# =========================================================
# AUTH
# =========================================================

@app.post(
    f"{API_V1}/auth/login",
    response_model = schemas.LoginResponse,
    tags           = ["Authentication"],
    summary        = "Login and receive a bearer token",
)
def login(
    login_data: schemas.LoginRequest,
    db: Session = Depends(get_db),
):
    user = crud.authenticate_user(db, login_data.username, login_data.password)

    if not user:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail      = "Invalid username or password.",
        )

    token = crud.create_access_token(
        data={"sub": str(user.id), "role": user.role.value}
    )

    crud.create_audit_log(
        db          = db,
        user_id     = user.id,
        action      = "USER_LOGIN",
        entity_type = "User",
        entity_id   = user.id,
        description = f"User '{user.username}' logged in."
    )

    return {
        "access_token": token,
        "token_type":   "bearer",
        "user":         user,
    }


@app.get(
    f"{API_V1}/auth/me",
    response_model = schemas.UserResponse,
    tags           = ["Authentication"],
    summary        = "Get current authenticated user",
)
def get_me(current_user: models.User = Depends(get_current_user)):
    return current_user


@app.post(
    f"{API_V1}/auth/logout",
    tags    = ["Authentication"],
    summary = "Logout (client should discard token)",
)
def logout(current_user: models.User = Depends(get_current_user)):
    # JWT is stateless; client discards token. We log the event.
    return {"message": "Logged out successfully. Please discard your token."}


# =========================================================
# USERS
# =========================================================

@app.post(
    f"{API_V1}/users",
    response_model = schemas.UserResponse,
    status_code    = status.HTTP_201_CREATED,
    tags           = ["Users"],
    summary        = "Create a new user account (DS only)",
)
def create_user(
    user: schemas.UserCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.DS)),
):
    existing = crud.get_user_by_username(db, user.username)
    if existing:
        raise HTTPException(
            status_code = status.HTTP_400_BAD_REQUEST,
            detail      = "Username already exists.",
        )

    return crud.create_user(db, user)


@app.get(
    f"{API_V1}/users",
    response_model = List[schemas.UserResponse],
    tags           = ["Users"],
    summary        = "List all users (DS only)",
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
    response_model = schemas.DepartmentResponse,
    status_code    = status.HTTP_201_CREATED,
    tags           = ["Departments"],
    summary        = "Create a department (DS only)",
)
def create_department(
    dept: schemas.DepartmentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.DS)),
):
    return crud.create_department(db, dept)


@app.get(
    f"{API_V1}/departments",
    response_model = List[schemas.DepartmentResponse],
    tags           = ["Departments"],
    summary        = "List all active departments",
)
def get_departments(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return crud.get_departments(db)


@app.get(
    f"{API_V1}/departments/{{department_id}}/employees",
    response_model = List[schemas.EmployeeResponse],
    tags           = ["Departments"],
    summary        = "Get employees in a department",
)
def get_department_employees(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    dept = crud.get_department_by_id(db, department_id)
    if not dept:
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail      = "Department not found.",
        )
    return crud.get_employees_by_department(db, department_id)


# =========================================================
# EMPLOYEES
# =========================================================

@app.post(
    f"{API_V1}/employees",
    response_model = schemas.EmployeeResponse,
    status_code    = status.HTTP_201_CREATED,
    tags           = ["Employees"],
    summary        = "Create an employee record (DS only)",
)
def create_employee(
    emp: schemas.EmployeeCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.DS)),
):
    dept = crud.get_department_by_id(db, emp.department_id)
    if not dept:
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail      = "Department not found.",
        )
    return crud.create_employee(db, emp)


@app.get(
    f"{API_V1}/employees",
    response_model = List[schemas.EmployeeResponse],
    tags           = ["Employees"],
    summary        = "List all active employees",
)
def get_employees(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return crud.get_employees(db)


# =========================================================
# DOCUMENTS
# =========================================================

@app.post(
    f"{API_V1}/documents",
    response_model = schemas.DocumentResponse,
    status_code    = status.HTTP_201_CREATED,
    tags           = ["Documents"],
    summary        = "DS: Register / intake a new document",
)
def create_document(
    doc: schemas.DocumentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.DS)),
):
    return crud.create_document(db, doc, created_by=current_user.id)


@app.get(
    f"{API_V1}/documents",
    response_model = List[schemas.DocumentListResponse],
    tags           = ["Documents"],
    summary        = "DS: Get all documents",
)
def get_documents(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.DS)),
):
    return crud.get_documents(db)


@app.get(
    f"{API_V1}/documents/inbox",
    response_model = List[schemas.DocumentListResponse],
    tags           = ["Documents"],
    summary        = "Get role-specific inbox (all roles)",
)
def get_inbox(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return crud.get_inbox(db, current_user)


@app.get(
    f"{API_V1}/documents/{{document_id}}",
    response_model = schemas.DocumentResponse,
    tags           = ["Documents"],
    summary        = "Get a single document by ID",
)
def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return _get_doc_or_404(db, document_id)


# --------------------------------------------------------
# ROUTING  (DS → Director / HOD / Employee)
# --------------------------------------------------------

@app.post(
    f"{API_V1}/documents/{{document_id}}/route",
    response_model = schemas.DocumentResponse,
    tags           = ["Documents — Workflow"],
    summary        = "DS: Route document to Director / HOD / Employee",
)
def route_document(
    document_id: int,
    route_req: schemas.RouteRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.DS)),
):
    doc = _get_doc_or_404(db, document_id)
    _assert_not_closed(doc)

    result = crud.route_document(db, document_id, route_req, current_user)
    if not result:
        raise HTTPException(
            status_code = status.HTTP_400_BAD_REQUEST,
            detail      = "Document cannot be routed with the given parameters.",
        )
    return result


# --------------------------------------------------------
# DIRECTOR REMARK  (save independently)
# --------------------------------------------------------

@app.put(
    f"{API_V1}/documents/{{document_id}}/director-remark",
    response_model = schemas.DocumentResponse,
    tags           = ["Documents — Workflow"],
    summary        = "Director: Save / update Director remark",
)
def save_director_remark(
    document_id: int,
    body: schemas.DirectorRemarkUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.DIRECTOR)),
):
    doc = _get_doc_or_404(db, document_id)
    _assert_not_closed(doc)

    result = crud.save_director_remark(db, document_id, body.director_remark, current_user)
    if not result:
        raise HTTPException(status_code=404, detail="Document not found.")
    return result


# --------------------------------------------------------
# DIRECTOR RETURN TO DS
# --------------------------------------------------------

@app.post(
    f"{API_V1}/documents/{{document_id}}/return-to-ds",
    response_model = schemas.DocumentResponse,
    tags           = ["Documents — Workflow"],
    summary        = "Director: Return document to Director Secretary",
)
def return_to_ds(
    document_id: int,
    body: schemas.ReturnToDSRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.DIRECTOR)),
):
    doc = _get_doc_or_404(db, document_id)
    _assert_not_closed(doc)

    # Find the DS who owns this document (original creator)
    ds_user_id = doc.created_by

    result = crud.return_to_ds(db, document_id, ds_user_id, body.remarks, current_user)
    if not result:
        raise HTTPException(status_code=404, detail="Document not found.")
    return result


# --------------------------------------------------------
# HOD REMARK  (save independently)
# --------------------------------------------------------

@app.put(
    f"{API_V1}/documents/{{document_id}}/hod-remark",
    response_model = schemas.DocumentResponse,
    tags           = ["Documents — Workflow"],
    summary        = "HOD: Save / update HOD remark",
)
def save_hod_remark(
    document_id: int,
    body: schemas.HODRemarkUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.HOD)),
):
    doc = _get_doc_or_404(db, document_id)
    _assert_not_closed(doc)

    result = crud.save_hod_remark(db, document_id, body.hod_remark, current_user)
    if not result:
        raise HTTPException(status_code=404, detail="Document not found.")
    return result


# --------------------------------------------------------
# HOD ASSIGN EMPLOYEE
# --------------------------------------------------------

@app.post(
    f"{API_V1}/documents/{{document_id}}/assign",
    response_model = schemas.AssignmentResponse,
    status_code    = status.HTTP_201_CREATED,
    tags           = ["Documents — Workflow"],
    summary        = "HOD: Assign an employee to a document",
)
def assign_employee(
    document_id: int,
    assign_req: schemas.AssignmentRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.HOD)),
):
    doc = _get_doc_or_404(db, document_id)
    _assert_not_closed(doc)

    # Validate target is an EMPLOYEE
    target_user = crud.get_user_by_id(db, assign_req.assigned_to_user_id)
    if not target_user or target_user.role != UserRole.EMPLOYEE:
        raise HTTPException(
            status_code = status.HTTP_400_BAD_REQUEST,
            detail      = "Target user must be an active EMPLOYEE.",
        )

    result = crud.assign_employee(db, document_id, assign_req, current_user)
    if not result:
        raise HTTPException(status_code=404, detail="Document not found.")
    return result


# --------------------------------------------------------
# EMPLOYEE — PROGRESS UPDATES
# --------------------------------------------------------

@app.post(
    f"{API_V1}/documents/{{document_id}}/progress",
    response_model = schemas.ProgressResponse,
    status_code    = status.HTTP_201_CREATED,
    tags           = ["Documents — Progress"],
    summary        = "Employee: Submit a progress update",
)
def submit_progress(
    document_id: int,
    prog: schemas.ProgressCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.EMPLOYEE)),
):
    doc = _get_doc_or_404(db, document_id)
    _assert_not_closed(doc)

    result = crud.create_progress_update(db, document_id, prog, current_user)
    if not result:
        raise HTTPException(status_code=404, detail="Document not found.")
    return result


@app.get(
    f"{API_V1}/documents/{{document_id}}/progress",
    response_model = List[schemas.ProgressResponse],
    tags           = ["Documents — Progress"],
    summary        = "Get all progress updates for a document",
)
def get_progress(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _get_doc_or_404(db, document_id)
    return crud.get_progress_updates(db, document_id)


# --------------------------------------------------------
# ATTACHMENTS — UPLOAD
# --------------------------------------------------------

@app.post(
    f"{API_V1}/documents/{{document_id}}/attachments",
    response_model = schemas.AttachmentResponse,
    status_code    = status.HTTP_201_CREATED,
    tags           = ["Attachments"],
    summary        = "Upload an attachment for a document",
)
async def upload_attachment(
    document_id:        int,
    file:               UploadFile = File(...),
    progress_update_id: Optional[int] = Form(default=None),
    db:                 Session = Depends(get_db),
    current_user:       models.User = Depends(get_current_user),
):
    doc = _get_doc_or_404(db, document_id)
    _assert_not_closed(doc)

    # Validate content type
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code = status.HTTP_400_BAD_REQUEST,
            detail      = f"File type '{file.content_type}' is not allowed. "
                          f"Allowed: PDF, DOCX, DOC, JPEG, PNG, TXT.",
        )

    # Read and size-check
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code = status.HTTP_400_BAD_REQUEST,
            detail      = f"File exceeds maximum allowed size of 20 MB.",
        )

    # Save to disk
    dest_dir = UPLOAD_DIR / str(datetime.utcnow().year) / str(document_id)
    dest_dir.mkdir(parents=True, exist_ok=True)

    safe_name   = Path(file.filename).name
    dest_path   = dest_dir / safe_name

    # Avoid overwrite by appending counter
    counter = 1
    stem    = Path(safe_name).stem
    suffix  = Path(safe_name).suffix
    while dest_path.exists():
        dest_path = dest_dir / f"{stem}_{counter}{suffix}"
        counter  += 1

    with open(dest_path, "wb") as f:
        f.write(contents)

    storage_key = str(dest_path.relative_to(UPLOAD_DIR))

    attachment = crud.create_attachment(
        db                 = db,
        doc_id             = document_id,
        progress_update_id = progress_update_id,
        uploaded_by        = current_user.id,
        file_name          = file.filename,
        storage_key        = storage_key,
        file_type          = file.content_type,
        file_size          = len(contents),
    )

    return attachment


@app.get(
    f"{API_V1}/documents/{{document_id}}/attachments",
    response_model = List[schemas.AttachmentResponse],
    tags           = ["Attachments"],
    summary        = "List all attachments for a document",
)
def get_document_attachments(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _get_doc_or_404(db, document_id)
    return crud.get_attachments(db, document_id)


# --------------------------------------------------------
# ATTACHMENTS — GET / DOWNLOAD
# --------------------------------------------------------

@app.get(
    f"{API_V1}/attachments/{{attachment_id}}",
    response_model = schemas.AttachmentResponse,
    tags           = ["Attachments"],
    summary        = "Get attachment metadata",
)
def get_attachment(
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    att = crud.get_attachment(db, attachment_id)
    if not att:
        raise HTTPException(status_code=404, detail="Attachment not found.")
    return att


@app.get(
    f"{API_V1}/attachments/{{attachment_id}}/download",
    tags    = ["Attachments"],
    summary = "Download an attachment file",
)
def download_attachment(
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    att = crud.get_attachment(db, attachment_id)
    if not att:
        raise HTTPException(status_code=404, detail="Attachment not found.")

    file_path = UPLOAD_DIR / att.storage_key
    if not file_path.exists():
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail      = "File not found on server.",
        )

    return FileResponse(
        path             = str(file_path),
        filename         = att.file_name,
        media_type       = att.file_type or "application/octet-stream",
    )


# --------------------------------------------------------
# DS — FOLLOW-UP TO DIRECTOR
# --------------------------------------------------------

@app.post(
    f"{API_V1}/documents/{{document_id}}/follow-up",
    response_model = schemas.DocumentResponse,
    tags           = ["Documents — Workflow"],
    summary        = "DS: Forward progress follow-up to Director",
)
def follow_up_to_director(
    document_id: int,
    body: schemas.FollowUpRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.DS)),
):
    doc = _get_doc_or_404(db, document_id)
    _assert_not_closed(doc)

    # Find any active Director user
    directors = crud.get_users_by_role(db, UserRole.DIRECTOR)
    if not directors:
        raise HTTPException(
            status_code = status.HTTP_400_BAD_REQUEST,
            detail      = "No active Director user found in the system.",
        )

    director = directors[0]

    result = crud.follow_up_to_director(
        db, document_id, director, body.remarks, current_user
    )
    if not result:
        raise HTTPException(status_code=404, detail="Document not found.")
    return result


# --------------------------------------------------------
# DOCUMENT HISTORY
# --------------------------------------------------------

@app.get(
    f"{API_V1}/documents/{{document_id}}/history",
    response_model = List[schemas.WorkflowHistoryResponse],
    tags           = ["Documents"],
    summary        = "Get workflow history for a document",
)
def get_document_history(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _get_doc_or_404(db, document_id)
    return crud.get_document_history(db, document_id)


# --------------------------------------------------------
# DS — CLOSE DOCUMENT
# --------------------------------------------------------

@app.post(
    f"{API_V1}/documents/{{document_id}}/close",
    response_model = schemas.DocumentResponse,
    tags           = ["Documents — Workflow"],
    summary        = "DS: Close a document (final action)",
)
def close_document(
    document_id: int,
    body: schemas.CloseRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(UserRole.DS)),
):
    doc = _get_doc_or_404(db, document_id)

    if doc.current_stage == models.WorkflowStage.CLOSED:
        raise HTTPException(
            status_code = status.HTTP_409_CONFLICT,
            detail      = "Document is already closed.",
        )

    result = crud.close_document(db, document_id, body.remarks, current_user)
    if not result:
        raise HTTPException(status_code=404, detail="Document not found.")
    return result


# =========================================================
# NOTIFICATIONS
# =========================================================

@app.get(
    f"{API_V1}/notifications",
    response_model = List[schemas.NotificationResponse],
    tags           = ["Notifications"],
    summary        = "Get all notifications for current user",
)
def get_notifications(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return crud.get_notifications(db, current_user.id)


@app.get(
    f"{API_V1}/notifications/unread",
    response_model = List[schemas.NotificationResponse],
    tags           = ["Notifications"],
    summary        = "Get unread notifications for current user",
)
def get_unread_notifications(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return crud.get_unread_notifications(db, current_user.id)


@app.patch(
    f"{API_V1}/notifications/{{notification_id}}/read",
    response_model = schemas.NotificationResponse,
    tags           = ["Notifications"],
    summary        = "Mark a notification as read",
)
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    notif = crud.mark_notification_read(db, notification_id, current_user.id)
    if not notif:
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail      = "Notification not found.",
        )
    return notif


@app.patch(
    f"{API_V1}/notifications/read-all",
    tags    = ["Notifications"],
    summary = "Mark all notifications as read",
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
    response_model = schemas.DashboardResponse,
    tags           = ["Dashboard"],
    summary        = "Get role-specific dashboard statistics",
)
def get_dashboard(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return crud.get_dashboard_stats(db, current_user)


# =========================================================
# STARTUP — OPTIONAL SEED DATA
# Set environment variable SEED_DB=true to populate test data
# =========================================================

from datetime import datetime

@app.on_event("startup")
def on_startup():
    if os.getenv("SEED_DB", "false").lower() == "true":
        from database import SessionLocal
        db = SessionLocal()
        try:
            crud.seed_data(db)
        finally:
            db.close()
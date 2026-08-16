import os
import hashlib
import re
from datetime import datetime, timedelta, date
from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_

import bcrypt
from jose import jwt

import models
import schemas
from models import (
    UserRole, DocumentStatus, WorkflowStage, Priority, RouteType,
    SourceType, MessageProcessingStatus, AttachmentType, OCRStatus,
    RoutingSource, RemarkType, ReminderReason
)


# =========================================================
# CONFIGURATION & CONSTANTS
# =========================================================

SECRET_KEY = os.getenv("SECRET_KEY", "cdtrs-super-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))


# =========================================================
# LIVE EVENT MANAGER (WebSocket & Event Broadcast)
# =========================================================

class LiveEventManager:
    def __init__(self):
        self._active_connections: List[Any] = []
        self._recent_events: List[Dict[str, Any]] = []
        self._max_recent = 100

    async def connect(self, websocket: Any):
        await websocket.accept()
        self._active_connections.append(websocket)

    def disconnect(self, websocket: Any):
        if websocket in self._active_connections:
            self._active_connections.remove(websocket)

    async def broadcast(self, event_type: str, document_id: Optional[int] = None,
                        user_id: Optional[int] = None, payload: Optional[dict] = None):
        event = {
            "event_type": event_type,
            "document_id": document_id,
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat(),
            "payload": payload or {}
        }
        self._recent_events.append(event)
        if len(self._recent_events) > self._max_recent:
            self._recent_events.pop(0)

        # Broadcast to all live WebSocket connections safely
        for connection in list(self._active_connections):
            try:
                await connection.send_json(event)
            except Exception:
                self.disconnect(connection)

    def get_recent_events(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self._recent_events[-limit:]


# Global singleton event manager
event_manager = LiveEventManager()


# =========================================================
# PASSWORD & JWT HELPERS
# =========================================================

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except Exception:
        return None


# =========================================================
# USER OPERATIONS
# =========================================================

def create_user(db: Session, user: schemas.UserCreate) -> models.User:
    db_user = models.User(
        username=user.username,
        password_hash=hash_password(user.password),
        full_name=user.full_name,
        role=user.role,
        department_id=user.department_id,
        employee_id=user.employee_id,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def get_user_by_username(db: Session, username: str) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.username == username).first()


def get_user_by_id(db: Session, user_id: int) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.id == user_id).first()


def get_users(db: Session) -> List[models.User]:
    return db.query(models.User).order_by(models.User.full_name).all()


def get_users_by_role(db: Session, role: UserRole) -> List[models.User]:
    return (
        db.query(models.User)
        .filter(models.User.role == role, models.User.is_active == True)
        .order_by(models.User.full_name)
        .all()
    )


def authenticate_user(db: Session, username: str, password: str) -> Optional[models.User]:
    user = get_user_by_username(db, username)
    if not user or not verify_password(password, user.password_hash) or not user.is_active:
        return None
    return user


# =========================================================
# DEPARTMENT OPERATIONS
# =========================================================

def create_department(db: Session, dept: schemas.DepartmentCreate) -> models.Department:
    db_dept = models.Department(name=dept.name, code=dept.code)
    db.add(db_dept)
    db.commit()
    db.refresh(db_dept)
    return db_dept


def get_departments(db: Session) -> List[models.Department]:
    return db.query(models.Department).filter(models.Department.is_active == True).order_by(models.Department.name).all()


def get_department_by_id(db: Session, dept_id: int) -> Optional[models.Department]:
    return db.query(models.Department).filter(models.Department.id == dept_id).first()


# =========================================================
# EMPLOYEE OPERATIONS
# =========================================================

def create_employee(db: Session, emp: schemas.EmployeeCreate) -> models.Employee:
    db_emp = models.Employee(
        employee_code=emp.employee_code,
        full_name=emp.full_name,
        department_id=emp.department_id,
        designation=emp.designation,
        user_id=emp.user_id,
    )
    db.add(db_emp)
    db.commit()
    db.refresh(db_emp)
    return db_emp


def get_employees(db: Session) -> List[models.Employee]:
    return db.query(models.Employee).filter(models.Employee.is_active == True).order_by(models.Employee.full_name).all()


def get_employees_by_department(db: Session, department_id: int) -> List[models.Employee]:
    return (
        db.query(models.Employee)
        .filter(models.Employee.department_id == department_id, models.Employee.is_active == True)
        .order_by(models.Employee.full_name)
        .all()
    )


# =========================================================
# INTAKE & INCOMING MESSAGES
# =========================================================

def create_incoming_message(db: Session, intake: schemas.IntakeCreate, has_attachments: bool = False) -> models.IncomingMessage:
    # De-duplication check using external_message_id
    if intake.external_message_id:
        existing = db.query(models.IncomingMessage).filter(
            models.IncomingMessage.external_message_id == intake.external_message_id
        ).first()
        if existing:
            return existing

    msg = models.IncomingMessage(
        source_type=intake.source_type,
        external_message_id=intake.external_message_id,
        sender_name=intake.sender_name,
        sender_email=intake.sender_email,
        subject=intake.subject,
        received_at=intake.received_at or datetime.utcnow(),
        body_reference=intake.body_reference,
        has_attachments=has_attachments,
        processing_status=MessageProcessingStatus.NEW
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def get_incoming_messages(db: Session) -> List[models.IncomingMessage]:
    return db.query(models.IncomingMessage).order_by(models.IncomingMessage.created_at.desc()).all()


def get_incoming_message_by_id(db: Session, msg_id: int) -> Optional[models.IncomingMessage]:
    return db.query(models.IncomingMessage).filter(models.IncomingMessage.id == msg_id).first()


def process_intake_to_document(db: Session, msg_id: int, proc_req: schemas.IntakeProcessRequest, user: models.User) -> models.Document:
    msg = get_incoming_message_by_id(db, msg_id)
    if not msg:
        return None

    # Title fallback from message subject
    title = proc_req.title or msg.subject or f"Incoming Message #{msg.id}"
    doc_create = schemas.DocumentCreate(
        title=title,
        description=msg.body_reference,
        received_date=msg.received_at.date() if msg.received_at else date.today(),
        deadline=proc_req.deadline,
        source=msg.sender_name or msg.sender_email or "External Intake",
        mode=msg.source_type.value,
        priority=proc_req.priority,
        source_message_id=msg.id
    )

    doc = create_document(db, doc_create, created_by=user.id)
    msg.processing_status = MessageProcessingStatus.PROCESSED
    db.commit()
    return doc


# =========================================================
# REFERENCE NUMBER GENERATOR
# =========================================================

def _generate_reference_no(db: Session) -> str:
    year = datetime.utcnow().year
    prefix = f"CDTRS-{year}-"
    count = (
        db.query(func.count(models.Document.doc_id))
        .filter(models.Document.reference_no.like(f"{prefix}%"))
        .scalar()
    ) or 0
    sequence = str(count + 1).zfill(4)
    return f"{prefix}{sequence}"


# =========================================================
# OPTIMISTIC CONCURRENCY HELPER
# =========================================================

def check_concurrency(doc: models.Document, expected_version: Optional[int]) -> bool:
    if expected_version is not None and doc.version != expected_version:
        return False
    return True


# =========================================================
# DOCUMENT CRUD
# =========================================================

def create_document(db: Session, doc: schemas.DocumentCreate, created_by: int) -> models.Document:
    reference_no = _generate_reference_no(db)

    db_doc = models.Document(
        reference_no=reference_no,
        title=doc.title,
        description=doc.description,
        received_date=doc.received_date,
        deadline=doc.deadline,
        source=doc.source,
        mode=doc.mode,
        priority=doc.priority,
        status=DocumentStatus.RECEIVED,
        current_stage=WorkflowStage.DS,
        current_owner_id=created_by,
        created_by=created_by,
        source_message_id=doc.source_message_id,
        ocr_status=OCRStatus.NONE,
        version=1
    )

    db.add(db_doc)
    db.commit()
    db.refresh(db_doc)

    # Workflow history entry
    _add_workflow_history(
        db=db,
        document_id=db_doc.doc_id,
        user_id=created_by,
        action="DOCUMENT_RECEIVED",
        from_role="DS",
        to_role=None,
        details=f"Document registered as {reference_no}"
    )

    return db_doc


def get_document(db: Session, doc_id: int) -> Optional[models.Document]:
    return db.query(models.Document).filter(models.Document.doc_id == doc_id).first()


def get_documents(db: Session) -> List[models.Document]:
    return db.query(models.Document).order_by(models.Document.created_at.desc()).all()


# =========================================================
# STRICT ROLE & DEPARTMENT SCOPING / INBOX
# =========================================================

def get_inbox(db: Session, user: models.User) -> List[models.Document]:
    """
    Hard-enforced backend scoping:
    - DS: All documents they created or are current owner of
    - DIRECTOR: Only documents routed to Director (current_stage = DIRECTOR and current_owner = user)
    - HOD: Only documents routed to HOD's department (current_stage = HOD and target_dept = user.department_id)
    - EMPLOYEE: Only documents actively assigned to user or directly routed to user
    """
    if user.role == UserRole.DS:
        return (
            db.query(models.Document)
            .filter(
                or_(
                    models.Document.created_by == user.id,
                    models.Document.current_owner_id == user.id
                )
            )
            .order_by(models.Document.updated_at.desc())
            .all()
        )

    elif user.role == UserRole.DIRECTOR:
        return (
            db.query(models.Document)
            .filter(
                models.Document.current_stage == WorkflowStage.DIRECTOR,
                models.Document.current_owner_id == user.id
            )
            .order_by(models.Document.updated_at.desc())
            .all()
        )

    elif user.role == UserRole.HOD:
        if not user.department_id:
            return []
        return (
            db.query(models.Document)
            .filter(
                models.Document.current_stage == WorkflowStage.HOD,
                models.Document.target_department_id == user.department_id
            )
            .order_by(models.Document.updated_at.desc())
            .all()
        )

    elif user.role == UserRole.EMPLOYEE:
        assigned_doc_ids = (
            db.query(models.WorkAssignment.document_id)
            .filter(
                models.WorkAssignment.assigned_to_user_id == user.id,
                models.WorkAssignment.is_active == True
            )
            .all()
        )
        assigned_doc_ids = [r[0] for r in assigned_doc_ids]

        return (
            db.query(models.Document)
            .filter(
                or_(
                    models.Document.doc_id.in_(assigned_doc_ids),
                    and_(
                        models.Document.current_owner_id == user.id,
                        models.Document.current_stage == WorkflowStage.EMPLOYEE
                    )
                )
            )
            .order_by(models.Document.updated_at.desc())
            .all()
        )

    return []


def is_document_accessible(db: Session, doc: models.Document, user: models.User) -> bool:
    """Check if the user is authorized to view this document and its attachments/history."""
    if user.role == UserRole.DS:
        return True
    elif user.role == UserRole.DIRECTOR:
        # Director can view documents routed to them or that have ever been reviewed by Director
        has_route = db.query(models.DocumentRoute).filter(
            models.DocumentRoute.document_id == doc.doc_id,
            or_(
                models.DocumentRoute.to_user_id == user.id,
                models.DocumentRoute.from_user_id == user.id
            )
        ).first()
        return (doc.current_owner_id == user.id or has_route is not None)
    elif user.role == UserRole.HOD:
        # HOD can view documents targeted to their department
        return (user.department_id is not None and doc.target_department_id == user.department_id)
    elif user.role == UserRole.EMPLOYEE:
        # Employee can view assigned or directly owned documents
        has_assignment = db.query(models.WorkAssignment).filter(
            models.WorkAssignment.document_id == doc.doc_id,
            models.WorkAssignment.assigned_to_user_id == user.id
        ).first()
        return (doc.current_owner_id == user.id or has_assignment is not None)
    return False


# =========================================================
# DOCUMENT WORKFLOW TRANSITIONS
# =========================================================

def route_document(db: Session, doc_id: int, route_req: schemas.RouteRequest, current_user: models.User) -> Optional[models.Document]:
    doc = get_document(db, doc_id)
    if not doc or not check_concurrency(doc, route_req.expected_version):
        return None

    if route_req.route_type == RouteType.INITIAL_DIRECTOR_REVIEW:
        new_stage = WorkflowStage.DIRECTOR
        new_status = DocumentStatus.UNDER_DIRECTOR_REVIEW
        new_owner = route_req.to_user_id

    elif route_req.route_type == RouteType.POST_REVIEW_TO_HOD:
        new_stage = WorkflowStage.HOD
        new_status = DocumentStatus.UNDER_HOD_PROCESSING
        new_owner = None
        if route_req.to_department_id:
            doc.target_department_id = route_req.to_department_id

    elif route_req.route_type == RouteType.POST_REVIEW_TO_EMPLOYEE:
        new_stage = WorkflowStage.EMPLOYEE
        new_status = DocumentStatus.ASSIGNED_FOR_EXECUTION
        new_owner = route_req.to_user_id

    elif route_req.route_type == RouteType.FOLLOW_UP_TO_DIRECTOR:
        new_stage = WorkflowStage.DIRECTOR
        new_status = DocumentStatus.UNDER_DIRECTOR_REVIEW
        new_owner = route_req.to_user_id
    else:
        return None

    doc.current_stage = new_stage
    doc.status = new_status
    doc.current_owner_id = new_owner
    doc.updated_at = datetime.utcnow()
    doc.version += 1

    # Record Route entry
    db_route = models.DocumentRoute(
        document_id=doc_id,
        from_user_id=current_user.id,
        to_user_id=route_req.to_user_id,
        to_department_id=route_req.to_department_id,
        route_type=route_req.route_type,
        remarks=route_req.remarks,
    )
    db.add(db_route)
    db.commit()
    db.refresh(doc)

    # Workflow history
    event = _add_workflow_history(
        db=db,
        document_id=doc_id,
        user_id=current_user.id,
        action=f"ROUTED_{route_req.route_type.value}",
        from_role=current_user.role.value,
        to_role=new_stage.value,
        details=route_req.remarks
    )

    # Send Notification to recipient
    if route_req.to_user_id:
        _create_notification(
            db=db,
            user_id=route_req.to_user_id,
            document_id=doc_id,
            workflow_event_id=event.id,
            title=f"Document routed: {doc.reference_no}",
            message=f"Document '{doc.title}' routed to you by DS."
        )
    elif route_req.to_department_id:
        # Notify active HODs of that department
        dept_hods = db.query(models.User).filter(
            models.User.department_id == route_req.to_department_id,
            models.User.role == UserRole.HOD,
            models.User.is_active == True
        ).all()
        for hod in dept_hods:
            _create_notification(
                db=db,
                user_id=hod.id,
                document_id=doc_id,
                workflow_event_id=event.id,
                title=f"New Department Document: {doc.reference_no}",
                message=f"Document '{doc.title}' routed to your department."
            )

    return doc


def save_director_remark(db: Session, doc_id: int, remark: str, current_user: models.User,
                         expected_version: Optional[int] = None) -> Optional[models.Document]:
    doc = get_document(db, doc_id)
    if not doc or not check_concurrency(doc, expected_version):
        return None

    doc.director_remark = remark
    doc.updated_at = datetime.utcnow()
    doc.version += 1

    # Add to DocumentRemark history table
    remark_entry = models.DocumentRemark(
        document_id=doc_id,
        author_user_id=current_user.id,
        role=UserRole.DIRECTOR,
        remark_text=remark,
        remark_type=RemarkType.DIRECTOR
    )
    db.add(remark_entry)
    db.commit()
    db.refresh(doc)

    _add_workflow_history(
        db=db,
        document_id=doc_id,
        user_id=current_user.id,
        action="DIRECTOR_REMARK_SAVED",
        from_role="DIRECTOR",
        to_role=None,
        details="Director remark updated"
    )

    # Automatically generate/update routing intelligence suggestions based on Director remark
    generate_routing_suggestion(db, doc_id, include_director_remark=True)

    return doc


def return_to_ds(db: Session, doc_id: int, ds_user_id: int, remarks: Optional[str],
                 current_user: models.User, expected_version: Optional[int] = None) -> Optional[models.Document]:
    doc = get_document(db, doc_id)
    if not doc or not check_concurrency(doc, expected_version):
        return None

    doc.current_stage = WorkflowStage.DS
    doc.status = DocumentStatus.DIRECTOR_REVIEW_COMPLETED
    doc.current_owner_id = ds_user_id
    doc.updated_at = datetime.utcnow()
    doc.version += 1

    db_route = models.DocumentRoute(
        document_id=doc_id,
        from_user_id=current_user.id,
        to_user_id=ds_user_id,
        route_type=RouteType.RETURN_TO_DS,
        remarks=remarks,
    )
    db.add(db_route)
    db.commit()
    db.refresh(doc)

    event = _add_workflow_history(
        db=db,
        document_id=doc_id,
        user_id=current_user.id,
        action="RETURNED_TO_DS",
        from_role="DIRECTOR",
        to_role="DS",
        details=remarks
    )

    _create_notification(
        db=db,
        user_id=ds_user_id,
        document_id=doc_id,
        workflow_event_id=event.id,
        title=f"Document returned: {doc.reference_no}",
        message=f"Director has returned '{doc.title}' to DS."
    )

    return doc


def save_hod_remark(db: Session, doc_id: int, remark: str, current_user: models.User,
                    expected_version: Optional[int] = None) -> Optional[models.Document]:
    doc = get_document(db, doc_id)
    if not doc or not check_concurrency(doc, expected_version):
        return None

    doc.hod_remark = remark
    doc.updated_at = datetime.utcnow()
    doc.version += 1

    remark_entry = models.DocumentRemark(
        document_id=doc_id,
        author_user_id=current_user.id,
        role=UserRole.HOD,
        remark_text=remark,
        remark_type=RemarkType.HOD
    )
    db.add(remark_entry)
    db.commit()
    db.refresh(doc)

    _add_workflow_history(
        db=db,
        document_id=doc_id,
        user_id=current_user.id,
        action="HOD_REMARK_SAVED",
        from_role="HOD",
        to_role=None,
        details="HOD remark updated"
    )

    return doc


def assign_employee(db: Session, doc_id: int, assign_req: schemas.AssignmentRequest,
                    current_user: models.User) -> Optional[models.WorkAssignment]:
    doc = get_document(db, doc_id)
    if not doc or not check_concurrency(doc, assign_req.expected_version):
        return None

    # Deactivate any previous active assignment
    (
        db.query(models.WorkAssignment)
        .filter(models.WorkAssignment.document_id == doc_id, models.WorkAssignment.is_active == True)
        .update({"is_active": False})
    )

    assignment = models.WorkAssignment(
        document_id=doc_id,
        assigned_by_user_id=current_user.id,
        assigned_to_user_id=assign_req.assigned_to_user_id,
        instructions=assign_req.instructions,
        is_active=True,
    )
    db.add(assignment)

    doc.current_stage = WorkflowStage.EMPLOYEE
    doc.status = DocumentStatus.ASSIGNED_FOR_EXECUTION
    doc.current_owner_id = assign_req.assigned_to_user_id
    doc.updated_at = datetime.utcnow()
    doc.version += 1

    db.commit()
    db.refresh(assignment)

    event = _add_workflow_history(
        db=db,
        document_id=doc_id,
        user_id=current_user.id,
        action="EMPLOYEE_ASSIGNED",
        from_role="HOD",
        to_role="EMPLOYEE",
        details=assign_req.instructions
    )

    _create_notification(
        db=db,
        user_id=assign_req.assigned_to_user_id,
        document_id=doc_id,
        workflow_event_id=event.id,
        title=f"Task assigned: {doc.reference_no}",
        message=f"You have been assigned to document '{doc.title}'."
    )

    return assignment


def create_progress_update(db: Session, doc_id: int, prog: schemas.ProgressCreate,
                           current_user: models.User) -> Optional[models.ProgressUpdate]:
    doc = get_document(db, doc_id)
    if not doc:
        return None

    db_progress = models.ProgressUpdate(
        document_id=doc_id,
        submitted_by_user_id=current_user.id,
        description=prog.description,
    )
    db.add(db_progress)

    doc.status = DocumentStatus.IN_PROGRESS
    doc.updated_at = datetime.utcnow()
    doc.version += 1

    db.commit()
    db.refresh(db_progress)

    event = _add_workflow_history(
        db=db,
        document_id=doc_id,
        user_id=current_user.id,
        action="PROGRESS_UPDATED",
        from_role="EMPLOYEE",
        to_role=None,
        details=prog.description[:200]
    )

    # Notify DS creator
    if doc.created_by:
        _create_notification(
            db=db,
            user_id=doc.created_by,
            document_id=doc_id,
            workflow_event_id=event.id,
            title=f"Progress update on {doc.reference_no}",
            message=f"Employee updated progress on '{doc.title}'."
        )

    return db_progress


def get_progress_updates(db: Session, doc_id: int) -> List[models.ProgressUpdate]:
    return db.query(models.ProgressUpdate).filter(models.ProgressUpdate.document_id == doc_id).order_by(models.ProgressUpdate.created_at).all()


def follow_up_to_director(db: Session, doc_id: int, director_user: models.User,
                          remarks: Optional[str], current_user: models.User,
                          expected_version: Optional[int] = None) -> Optional[models.Document]:
    doc = get_document(db, doc_id)
    if not doc or not check_concurrency(doc, expected_version):
        return None

    doc.current_stage = WorkflowStage.DIRECTOR
    doc.status = DocumentStatus.PROGRESS_UPDATED
    doc.current_owner_id = director_user.id
    doc.updated_at = datetime.utcnow()
    doc.version += 1

    db_route = models.DocumentRoute(
        document_id=doc_id,
        from_user_id=current_user.id,
        to_user_id=director_user.id,
        route_type=RouteType.FOLLOW_UP_TO_DIRECTOR,
        remarks=remarks,
    )
    db.add(db_route)
    db.commit()
    db.refresh(doc)

    event = _add_workflow_history(
        db=db,
        document_id=doc_id,
        user_id=current_user.id,
        action="FOLLOW_UP_TO_DIRECTOR",
        from_role="DS",
        to_role="DIRECTOR",
        details=remarks
    )

    _create_notification(
        db=db,
        user_id=director_user.id,
        document_id=doc_id,
        workflow_event_id=event.id,
        title=f"Follow-up for review: {doc.reference_no}",
        message=f"DS forwarded employee progress for '{doc.title}'."
    )

    return doc


def close_document(db: Session, doc_id: int, remarks: Optional[str],
                   current_user: models.User, expected_version: Optional[int] = None) -> Optional[models.Document]:
    doc = get_document(db, doc_id)
    if not doc or not check_concurrency(doc, expected_version):
        return None

    doc.status = DocumentStatus.CLOSED
    doc.current_stage = WorkflowStage.CLOSED
    doc.closed_at = datetime.utcnow()
    doc.updated_at = datetime.utcnow()
    doc.version += 1

    db.commit()
    db.refresh(doc)

    _add_workflow_history(
        db=db,
        document_id=doc_id,
        user_id=current_user.id,
        action="DOCUMENT_CLOSED",
        from_role="DS",
        to_role="CLOSED",
        details=remarks
    )

    return doc


# =========================================================
# REMARK HISTORY
# =========================================================

def get_document_remarks(db: Session, doc_id: int) -> List[models.DocumentRemark]:
    return (
        db.query(models.DocumentRemark)
        .filter(models.DocumentRemark.document_id == doc_id)
        .order_by(models.DocumentRemark.created_at.desc())
        .all()
    )


# =========================================================
# ATTACHMENTS & CHECKSUM
# =========================================================

def compute_checksum(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def create_attachment(
    db: Session,
    doc_id: int,
    progress_update_id: Optional[int],
    uploaded_by: int,
    file_name: str,
    storage_key: str,
    file_type: Optional[str],
    file_size: Optional[int],
    checksum: Optional[str] = None,
    attachment_type: AttachmentType = AttachmentType.ORIGINAL,
    source_message_id: Optional[int] = None
) -> models.Attachment:
    att = models.Attachment(
        document_id=doc_id,
        progress_update_id=progress_update_id,
        uploaded_by_user_id=uploaded_by,
        file_name=file_name,
        storage_key=storage_key,
        file_type=file_type,
        file_size=file_size,
        checksum=checksum,
        attachment_type=attachment_type,
        source_message_id=source_message_id,
    )
    db.add(att)
    db.commit()
    db.refresh(att)

    _add_workflow_history(
        db=db,
        document_id=doc_id,
        user_id=uploaded_by,
        action="ATTACHMENT_UPLOADED",
        from_role=None,
        to_role=None,
        details=f"File uploaded: {file_name} ({attachment_type.value})"
    )

    return att


def get_attachments(db: Session, doc_id: int) -> List[models.Attachment]:
    return db.query(models.Attachment).filter(models.Attachment.document_id == doc_id).order_by(models.Attachment.created_at).all()


def get_attachment(db: Session, attachment_id: int) -> Optional[models.Attachment]:
    return db.query(models.Attachment).filter(models.Attachment.id == attachment_id).first()


# =========================================================
# OCR & STRUCTURED EXTRACTION PIPELINE
# =========================================================

def trigger_ocr_processing(db: Session, doc_id: int) -> Optional[models.DocumentOCR]:
    doc = get_document(db, doc_id)
    if not doc:
        return None

    ocr_record = db.query(models.DocumentOCR).filter(models.DocumentOCR.document_id == doc_id).first()
    if not ocr_record:
        ocr_record = models.DocumentOCR(
            document_id=doc_id,
            ocr_status=OCRStatus.PROCESSING,
            ocr_engine="PaddleOCR/Tesseract-v5-Engine"
        )
        db.add(ocr_record)
    else:
        ocr_record.ocr_status = OCRStatus.PROCESSING
        ocr_record.error_message = None

    doc.ocr_status = OCRStatus.PROCESSING
    db.commit()

    # Simulate intelligent text extraction from document metadata/description
    extracted_text = (
        f"CENTRAL DOCUMENT RECORD\n"
        f"Subject: {doc.title}\n"
        f"Reference No: {doc.reference_no}\n"
        f"Date of Receipt: {doc.received_date}\n"
        f"Originating Source: {doc.source or 'Internal'}\n"
        f"Description: {doc.description or 'Official correspondence requiring department review and verification.'}\n"
        f"Priority Level: {doc.priority.value}\n"
    )

    ocr_record.extracted_text = extracted_text
    ocr_record.confidence = 0.94
    ocr_record.ocr_status = OCRStatus.COMPLETED
    ocr_record.processed_at = datetime.utcnow()
    doc.ocr_status = OCRStatus.COMPLETED

    # Extract standard structured fields
    fields_data = [
        {"name": "TITLE", "value": doc.title, "conf": 0.96, "page": 1, "text": f"Subject: {doc.title}"},
        {"name": "REFERENCE_NO", "value": doc.reference_no, "conf": 0.98, "page": 1, "text": f"Reference No: {doc.reference_no}"},
        {"name": "SOURCE", "value": doc.source or "External", "conf": 0.90, "page": 1, "text": f"Originating Source: {doc.source}"},
        {"name": "PRIORITY", "value": doc.priority.value, "conf": 0.95, "page": 1, "text": f"Priority Level: {doc.priority.value}"},
    ]

    for f_item in fields_data:
        existing_f = db.query(models.DocumentExtractedField).filter(
            models.DocumentExtractedField.document_id == doc_id,
            models.DocumentExtractedField.field_name == f_item["name"]
        ).first()

        if not existing_f:
            new_f = models.DocumentExtractedField(
                document_id=doc_id,
                field_name=f_item["name"],
                extracted_value=f_item["value"],
                confidence=f_item["conf"],
                source_page=f_item["page"],
                source_text=f_item["text"]
            )
            db.add(new_f)
        else:
            # Update only if not already verified by DS
            if not existing_f.verified_value:
                existing_f.extracted_value = f_item["value"]
                existing_f.confidence = f_item["conf"]
                existing_f.source_text = f_item["text"]

    db.commit()
    db.refresh(ocr_record)

    # Automatically generate routing suggestion
    generate_routing_suggestion(db, doc_id, include_director_remark=True)

    return ocr_record


def get_document_ocr(db: Session, doc_id: int) -> Optional[models.DocumentOCR]:
    return db.query(models.DocumentOCR).filter(models.DocumentOCR.document_id == doc_id).first()


def verify_extracted_field(db: Session, doc_id: int, field_name: str, verified_value: str, user: models.User) -> Optional[models.DocumentExtractedField]:
    field = db.query(models.DocumentExtractedField).filter(
        models.DocumentExtractedField.document_id == doc_id,
        models.DocumentExtractedField.field_name == field_name
    ).first()

    if not field:
        field = models.DocumentExtractedField(
            document_id=doc_id,
            field_name=field_name,
            extracted_value=verified_value,
            confidence=1.0,
            source_page=1
        )
        db.add(field)

    field.verified_value = verified_value
    field.verified_by = user.id
    field.verified_at = datetime.utcnow()

    # If title was verified, update canonical document
    doc = get_document(db, doc_id)
    if doc and field_name == "TITLE":
        doc.title = verified_value
        doc.version += 1

    db.commit()
    db.refresh(field)
    return field


def reanalyze_document_ocr(db: Session, doc_id: int) -> Optional[models.DocumentOCR]:
    """Re-runs OCR extraction without overwriting fields that have been verified by DS."""
    return trigger_ocr_processing(db, doc_id)


# =========================================================
# ROUTING INTELLIGENCE & ADVISORY SUGGESTIONS
# =========================================================

def generate_routing_suggestion(db: Session, doc_id: int, include_director_remark: bool = True) -> Optional[models.RoutingSuggestion]:
    doc = get_document(db, doc_id)
    if not doc:
        return None

    suggested_dept_id: Optional[int] = None
    suggested_emp_id: Optional[int] = None
    confidence = 0.75
    reason = "Extracted from document content keywords."
    source = RoutingSource.DOCUMENT_CONTENT
    is_director_instruction = False

    # 1. Check for Explicit Director Instruction first
    if include_director_remark and doc.director_remark:
        remark_lower = doc.director_remark.lower()

        # Find if any department name or code is mentioned
        depts = get_departments(db)
        for dept in depts:
            if dept.name.lower() in remark_lower or (dept.code and dept.code.lower() in remark_lower):
                suggested_dept_id = dept.id
                confidence = 0.92
                reason = f"Explicit instruction in Director's remark referencing {dept.name} department."
                source = RoutingSource.DIRECTOR_REMARK
                is_director_instruction = True
                break

        # Find if any employee name is mentioned
        employees = get_employees(db)
        for emp in employees:
            if emp.full_name.lower() in remark_lower:
                suggested_emp_id = emp.user_id or (
                    db.query(models.User.id).filter(models.User.employee_id == emp.id).scalar()
                )
                suggested_dept_id = emp.department_id
                confidence = 0.95
                reason = f"Explicit instruction in Director's remark directing assignment to {emp.full_name} ({emp.department.name})."
                source = RoutingSource.DIRECTOR_REMARK
                is_director_instruction = True
                break

    # 2. Fallback to Content / Metadata keywords if Director remark had no specific match
    if not suggested_dept_id:
        text_to_search = f"{doc.title} {doc.description or ''} {doc.source or ''}".lower()
        depts = get_departments(db)
        for dept in depts:
            if dept.name.lower() in text_to_search or (dept.code and dept.code.lower() in text_to_search):
                suggested_dept_id = dept.id
                confidence = 0.82
                reason = f"Content matched keywords for {dept.name} Department."
                source = RoutingSource.DOCUMENT_CONTENT
                break

    # If still not found, default to first department if exists
    if not suggested_dept_id:
        first_dept = db.query(models.Department).filter(models.Department.is_active == True).first()
        if first_dept:
            suggested_dept_id = first_dept.id
            confidence = 0.60
            reason = "General administrative routing default."
            source = RoutingSource.SOURCE_METADATA

    # Upsert routing suggestion
    suggestion = db.query(models.RoutingSuggestion).filter(models.RoutingSuggestion.document_id == doc_id).first()
    if not suggestion:
        suggestion = models.RoutingSuggestion(
            document_id=doc_id,
            suggested_department_id=suggested_dept_id,
            suggested_employee_id=suggested_emp_id,
            routing_confidence=confidence,
            routing_reason=reason,
            routing_source=source,
            is_director_instruction=is_director_instruction,
            generated_at=datetime.utcnow()
        )
        db.add(suggestion)
    else:
        # Update advisory values if not already confirmed
        if not suggestion.confirmed_at:
            suggestion.suggested_department_id = suggested_dept_id
            suggestion.suggested_employee_id = suggested_emp_id
            suggestion.routing_confidence = confidence
            suggestion.routing_reason = reason
            suggestion.routing_source = source
            suggestion.is_director_instruction = is_director_instruction
            suggestion.generated_at = datetime.utcnow()

    db.commit()
    db.refresh(suggestion)
    return suggestion


def get_routing_suggestion(db: Session, doc_id: int) -> Optional[models.RoutingSuggestion]:
    return db.query(models.RoutingSuggestion).filter(models.RoutingSuggestion.document_id == doc_id).first()


# =========================================================
# REMINDERS & DEADLINE ESCALATION LOGIC
# =========================================================

def generate_reminders(db: Session) -> List[models.Reminder]:
    """
    Scans documents needing action and generates reminders using recipient escalation:
    1. If active employee assigned -> Remind assigned employee
    2. Elif target department exists -> Remind active HOD of target department
    3. Else -> Remind DS creator
    """
    today = date.today()
    active_docs = db.query(models.Document).filter(
        models.Document.status != DocumentStatus.CLOSED
    ).all()

    created_reminders = []

    for doc in active_docs:
        # Determine reason based on deadline
        reason = ReminderReason.ACTION_REQUIRED
        if doc.deadline:
            if doc.deadline < today:
                reason = ReminderReason.OVERDUE
            elif doc.deadline <= today + timedelta(days=2):
                reason = ReminderReason.DUE_SOON

        # Recipient Resolution:
        recipient_id: Optional[int] = None

        # 1. Check active work assignment for employee
        active_assignment = db.query(models.WorkAssignment).filter(
            models.WorkAssignment.document_id == doc.doc_id,
            models.WorkAssignment.is_active == True
        ).first()

        if active_assignment:
            recipient_id = active_assignment.assigned_to_user_id
        elif doc.target_department_id:
            # 2. Check active HOD of target department
            hod = db.query(models.User).filter(
                models.User.department_id == doc.target_department_id,
                models.User.role == UserRole.HOD,
                models.User.is_active == True
            ).first()
            if hod:
                recipient_id = hod.id
        elif doc.current_owner_id:
            recipient_id = doc.current_owner_id
        else:
            recipient_id = doc.created_by

        if recipient_id:
            dedup_key = f"DOC_{doc.doc_id}_USER_{recipient_id}_{reason.value}_{today.isoformat()}"
            existing = db.query(models.Reminder).filter(models.Reminder.deduplication_key == dedup_key).first()

            if not existing:
                reminder = models.Reminder(
                    document_id=doc.doc_id,
                    recipient_user_id=recipient_id,
                    reason=reason,
                    due_at=datetime.combine(doc.deadline, datetime.min.time()) if doc.deadline else None,
                    sent_at=datetime.utcnow(),
                    is_read=False,
                    deduplication_key=dedup_key
                )
                db.add(reminder)
                created_reminders.append(reminder)

    if created_reminders:
        db.commit()

    return created_reminders


def get_reminders(db: Session, user_id: int) -> List[models.Reminder]:
    return (
        db.query(models.Reminder)
        .filter(models.Reminder.recipient_user_id == user_id)
        .order_by(models.Reminder.sent_at.desc())
        .all()
    )


def mark_reminder_read(db: Session, reminder_id: int, user_id: int) -> Optional[models.Reminder]:
    rem = db.query(models.Reminder).filter(
        models.Reminder.id == reminder_id,
        models.Reminder.recipient_user_id == user_id
    ).first()
    if rem:
        rem.is_read = True
        db.commit()
        db.refresh(rem)
    return rem


# =========================================================
# WORKFLOW HISTORY
# =========================================================

def _add_workflow_history(
    db: Session,
    document_id: int,
    user_id: int,
    action: str,
    from_role: Optional[str] = None,
    to_role: Optional[str] = None,
    details: Optional[str] = None
) -> models.WorkflowHistory:
    entry = models.WorkflowHistory(
        document_id=document_id,
        performed_by_user_id=user_id,
        action=action,
        from_role=from_role,
        to_role=to_role,
        details=details,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_document_history(db: Session, doc_id: int) -> List[models.WorkflowHistory]:
    return (
        db.query(models.WorkflowHistory)
        .filter(models.WorkflowHistory.document_id == doc_id)
        .order_by(models.WorkflowHistory.created_at)
        .all()
    )


# =========================================================
# NOTIFICATIONS
# =========================================================

def _create_notification(
    db: Session,
    user_id: int,
    document_id: Optional[int],
    workflow_event_id: Optional[int],
    title: str,
    message: str
) -> models.Notification:
    notif = models.Notification(
        user_id=user_id,
        document_id=document_id,
        workflow_event_id=workflow_event_id,
        title=title,
        message=message,
        is_read=False,
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)
    return notif


def get_notifications(db: Session, user_id: int) -> List[models.Notification]:
    return db.query(models.Notification).filter(models.Notification.user_id == user_id).order_by(models.Notification.created_at.desc()).all()


def get_unread_notifications(db: Session, user_id: int) -> List[models.Notification]:
    return db.query(models.Notification).filter(models.Notification.user_id == user_id, models.Notification.is_read == False).order_by(models.Notification.created_at.desc()).all()


def mark_notification_read(db: Session, notification_id: int, user_id: int) -> Optional[models.Notification]:
    notif = db.query(models.Notification).filter(models.Notification.id == notification_id, models.Notification.user_id == user_id).first()
    if not notif:
        return None
    notif.is_read = True
    db.commit()
    db.refresh(notif)
    return notif


def mark_all_notifications_read(db: Session, user_id: int) -> int:
    updated = (
        db.query(models.Notification)
        .filter(models.Notification.user_id == user_id, models.Notification.is_read == False)
        .update({"is_read": True})
    )
    db.commit()
    return updated


# =========================================================
# AUDIT LOG
# =========================================================

def create_audit_log(
    db: Session,
    user_id: int,
    action: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    description: Optional[str] = None
) -> models.AuditLog:
    audit = models.AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        description=description,
    )
    db.add(audit)
    db.commit()
    return audit


# =========================================================
# DASHBOARD STATS
# =========================================================

def get_dashboard_stats(db: Session, user: models.User) -> dict:
    unread_notifs = (
        db.query(func.count(models.Notification.id))
        .filter(models.Notification.user_id == user.id, models.Notification.is_read == False)
        .scalar()
    ) or 0

    unread_reminders = (
        db.query(func.count(models.Reminder.id))
        .filter(models.Reminder.recipient_user_id == user.id, models.Reminder.is_read == False)
        .scalar()
    ) or 0

    if user.role == UserRole.DS:
        total = (
            db.query(func.count(models.Document.doc_id))
            .filter(models.Document.created_by == user.id)
            .scalar()
        ) or 0

        under_director = (
            db.query(func.count(models.Document.doc_id))
            .filter(models.Document.created_by == user.id, models.Document.current_stage == WorkflowStage.DIRECTOR)
            .scalar()
        ) or 0

        under_hod = (
            db.query(func.count(models.Document.doc_id))
            .filter(models.Document.created_by == user.id, models.Document.current_stage == WorkflowStage.HOD)
            .scalar()
        ) or 0

        in_progress = (
            db.query(func.count(models.Document.doc_id))
            .filter(models.Document.created_by == user.id, models.Document.current_stage == WorkflowStage.EMPLOYEE)
            .scalar()
        ) or 0

        closed = (
            db.query(func.count(models.Document.doc_id))
            .filter(models.Document.created_by == user.id, models.Document.current_stage == WorkflowStage.CLOSED)
            .scalar()
        ) or 0

        intake_pending = (
            db.query(func.count(models.IncomingMessage.id))
            .filter(models.IncomingMessage.processing_status == MessageProcessingStatus.NEW)
            .scalar()
        ) or 0

        pending = total - closed

        return {
            "role": user.role.value,
            "total_documents": total,
            "pending_action": pending,
            "unread_notifications": unread_notifs,
            "unread_reminders": unread_reminders,
            "under_director_review": under_director,
            "under_hod_processing": under_hod,
            "in_progress": in_progress,
            "closed_documents": closed,
            "intake_pending": intake_pending
        }

    elif user.role == UserRole.DIRECTOR:
        for_review = (
            db.query(func.count(models.Document.doc_id))
            .filter(models.Document.current_owner_id == user.id, models.Document.current_stage == WorkflowStage.DIRECTOR)
            .scalar()
        ) or 0

        return {
            "role": user.role.value,
            "total_documents": for_review,
            "pending_action": for_review,
            "unread_notifications": unread_notifs,
            "unread_reminders": unread_reminders,
            "documents_for_review": for_review,
        }

    elif user.role == UserRole.HOD:
        dept_docs = 0
        pending_assignment = 0
        if user.department_id:
            dept_docs = (
                db.query(func.count(models.Document.doc_id))
                .filter(models.Document.target_department_id == user.department_id, models.Document.current_stage == WorkflowStage.HOD)
                .scalar()
            ) or 0

            pending_assignment = (
                db.query(func.count(models.Document.doc_id))
                .filter(models.Document.target_department_id == user.department_id, models.Document.status == DocumentStatus.UNDER_HOD_PROCESSING)
                .scalar()
            ) or 0

        return {
            "role": user.role.value,
            "total_documents": dept_docs,
            "pending_action": pending_assignment,
            "unread_notifications": unread_notifs,
            "unread_reminders": unread_reminders,
            "pending_assignment": pending_assignment,
        }

    elif user.role == UserRole.EMPLOYEE:
        active = (
            db.query(func.count(models.WorkAssignment.id))
            .filter(models.WorkAssignment.assigned_to_user_id == user.id, models.WorkAssignment.is_active == True)
            .scalar()
        ) or 0

        return {
            "role": user.role.value,
            "total_documents": active,
            "pending_action": active,
            "unread_notifications": unread_notifs,
            "unread_reminders": unread_reminders,
            "active_assignments": active,
        }

    return {
        "role": user.role.value,
        "total_documents": 0,
        "pending_action": 0,
        "unread_notifications": unread_notifs,
        "unread_reminders": unread_reminders
    }


# =========================================================
# COMPREHENSIVE SEED DATA (Includes 2 HODs for Isolation Testing)
# =========================================================

def seed_data(db: Session) -> None:
    """
    Populates the database with:
    - 4 Departments: Administration, Finance, Procurement, Technical
    - 2 distinct HODs from different departments (Finance & Procurement) for isolation testing
    - Multiple employees across both departments
    - DS and Director accounts
    """
    # 1. Departments
    depts_data = [
        {"name": "Administration", "code": "ADMIN"},
        {"name": "Finance", "code": "FIN"},
        {"name": "Procurement", "code": "PROC"},
        {"name": "Technical", "code": "TECH"},
    ]

    dept_map = {}
    for d in depts_data:
        existing = db.query(models.Department).filter(models.Department.name == d["name"]).first()
        if not existing:
            dept = models.Department(name=d["name"], code=d["code"])
            db.add(dept)
            db.commit()
            db.refresh(dept)
            dept_map[d["name"]] = dept.id
        else:
            dept_map[d["name"]] = existing.id

    # 2. Employees (Records)
    employees_data = [
        {"code": "EMP-001", "name": "Rahul Sharma", "dept": "Finance", "designation": "Accounts Officer"},
        {"code": "EMP-002", "name": "Priya Verma", "dept": "Procurement", "designation": "Procurement Specialist"},
        {"code": "EMP-003", "name": "Anil Kumar", "dept": "Technical", "designation": "Systems Engineer"},
    ]

    emp_map = {}
    for emp_d in employees_data:
        existing = db.query(models.Employee).filter(models.Employee.employee_code == emp_d["code"]).first()
        if not existing:
            emp = models.Employee(
                employee_code=emp_d["code"],
                full_name=emp_d["name"],
                department_id=dept_map[emp_d["dept"]],
                designation=emp_d["designation"]
            )
            db.add(emp)
            db.commit()
            db.refresh(emp)
            emp_map[emp_d["code"]] = emp.id
        else:
            emp_map[emp_d["code"]] = existing.id

    # 3. Users (Accounts)
    users_data = [
        {
            "username": "ds_user",
            "password": "cdtrs@ds",
            "full_name": "Director Secretary",
            "role": UserRole.DS,
            "department_id": dept_map["Administration"],
            "employee_id": None
        },
        {
            "username": "director",
            "password": "cdtrs@director",
            "full_name": "The Director",
            "role": UserRole.DIRECTOR,
            "department_id": None,
            "employee_id": None
        },
        {
            "username": "hod_finance",
            "password": "cdtrs@hod",
            "full_name": "Head of Finance",
            "role": UserRole.HOD,
            "department_id": dept_map["Finance"],
            "employee_id": None
        },
        {
            "username": "hod_procurement",
            "password": "cdtrs@hod",
            "full_name": "Head of Procurement",
            "role": UserRole.HOD,
            "department_id": dept_map["Procurement"],
            "employee_id": None
        },
        {
            "username": "emp_rahul",
            "password": "cdtrs@emp",
            "full_name": "Rahul Sharma",
            "role": UserRole.EMPLOYEE,
            "department_id": dept_map["Finance"],
            "employee_id": emp_map.get("EMP-001")
        },
        {
            "username": "emp_priya",
            "password": "cdtrs@emp",
            "full_name": "Priya Verma",
            "role": UserRole.EMPLOYEE,
            "department_id": dept_map["Procurement"],
            "employee_id": emp_map.get("EMP-002")
        }
    ]

    for u in users_data:
        existing = get_user_by_username(db, u["username"])
        if not existing:
            user = models.User(
                username=u["username"],
                password_hash=hash_password(u["password"]),
                full_name=u["full_name"],
                role=u["role"],
                department_id=u["department_id"],
                employee_id=u["employee_id"],
            )
            db.add(user)
            db.commit()
            db.refresh(user)

            # Link employee back to user
            if u["employee_id"]:
                db_emp = db.query(models.Employee).filter(models.Employee.id == u["employee_id"]).first()
                if db_emp and not db_emp.user_id:
                    db_emp.user_id = user.id
                    db.commit()

    print("Seed data inserted successfully.")
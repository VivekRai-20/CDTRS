import os
from datetime import datetime, timedelta
from typing import Optional, List

from sqlalchemy.orm import Session
from sqlalchemy import func

import bcrypt
from jose import jwt

import models
import schemas
from models import (
    UserRole, DocumentStatus, WorkflowStage, Priority, RouteType
)

SECRET_KEY    = os.getenv("SECRET_KEY", "cdtrs-super-secret-key-change-in-production")
ALGORITHM     = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))


# =========================================================
# PASSWORD HELPERS
# Using bcrypt directly — passlib is incompatible with bcrypt 4.x+
# =========================================================

def hash_password(password: str) -> str:
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(
        plain.encode("utf-8"),
        hashed.encode("utf-8")
    )


# =========================================================
# JWT TOKEN HELPERS
# =========================================================

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire    = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except Exception:
        return None


# =========================================================
# USER
# =========================================================

def create_user(db: Session, user: schemas.UserCreate) -> models.User:

    db_user = models.User(
        username      = user.username,
        password_hash = hash_password(user.password),
        full_name     = user.full_name,
        role          = user.role,
        department_id = user.department_id,
        employee_id   = user.employee_id,
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def get_user_by_username(db: Session, username: str) -> Optional[models.User]:
    return (
        db.query(models.User)
        .filter(models.User.username == username)
        .first()
    )


def get_user_by_id(db: Session, user_id: int) -> Optional[models.User]:
    return (
        db.query(models.User)
        .filter(models.User.id == user_id)
        .first()
    )


def get_users(db: Session) -> List[models.User]:
    return (
        db.query(models.User)
        .order_by(models.User.full_name)
        .all()
    )


def get_users_by_role(db: Session, role: UserRole) -> List[models.User]:
    return (
        db.query(models.User)
        .filter(
            models.User.role      == role,
            models.User.is_active == True
        )
        .order_by(models.User.full_name)
        .all()
    )


def authenticate_user(
    db: Session,
    username: str,
    password: str
) -> Optional[models.User]:

    user = get_user_by_username(db, username)

    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    if not user.is_active:
        return None

    return user


# =========================================================
# DEPARTMENT
# =========================================================

def create_department(
    db: Session,
    dept: schemas.DepartmentCreate
) -> models.Department:

    db_dept = models.Department(
        name = dept.name,
        code = dept.code,
    )

    db.add(db_dept)
    db.commit()
    db.refresh(db_dept)
    return db_dept


def get_departments(db: Session) -> List[models.Department]:
    return (
        db.query(models.Department)
        .filter(models.Department.is_active == True)
        .order_by(models.Department.name)
        .all()
    )


def get_department_by_id(db: Session, dept_id: int) -> Optional[models.Department]:
    return (
        db.query(models.Department)
        .filter(models.Department.id == dept_id)
        .first()
    )


# =========================================================
# EMPLOYEE
# =========================================================

def create_employee(
    db: Session,
    emp: schemas.EmployeeCreate
) -> models.Employee:

    db_emp = models.Employee(
        employee_code = emp.employee_code,
        full_name     = emp.full_name,
        department_id = emp.department_id,
        designation   = emp.designation,
        user_id       = emp.user_id,
    )

    db.add(db_emp)
    db.commit()
    db.refresh(db_emp)
    return db_emp


def get_employees(db: Session) -> List[models.Employee]:
    return (
        db.query(models.Employee)
        .filter(models.Employee.is_active == True)
        .order_by(models.Employee.full_name)
        .all()
    )


def get_employees_by_department(
    db: Session,
    department_id: int
) -> List[models.Employee]:
    return (
        db.query(models.Employee)
        .filter(
            models.Employee.department_id == department_id,
            models.Employee.is_active     == True
        )
        .order_by(models.Employee.full_name)
        .all()
    )


# =========================================================
# REFERENCE NUMBER GENERATOR
# Format: CDTRS-{YEAR}-{sequence padded to 4 digits}
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
# DOCUMENT — CREATE
# =========================================================

def create_document(
    db: Session,
    doc: schemas.DocumentCreate,
    created_by: int
) -> models.Document:

    reference_no = _generate_reference_no(db)

    db_doc = models.Document(
        reference_no         = reference_no,
        title                = doc.title,
        description          = doc.description,
        received_date        = doc.received_date,
        deadline             = doc.deadline,
        source               = doc.source,
        mode                 = doc.mode,
        priority             = doc.priority,
        status               = DocumentStatus.RECEIVED,
        current_stage        = WorkflowStage.DS,
        current_owner_id     = created_by,
        created_by           = created_by,
    )

    db.add(db_doc)
    db.commit()
    db.refresh(db_doc)

    # Workflow history entry
    _add_workflow_history(
        db          = db,
        document_id = db_doc.doc_id,
        user_id     = created_by,
        action      = "DOCUMENT_RECEIVED",
        from_role   = "DS",
        to_role     = None,
        details     = f"Document received and registered as {reference_no}"
    )

    return db_doc


# =========================================================
# DOCUMENT — READ
# =========================================================

def get_document(db: Session, doc_id: int) -> Optional[models.Document]:
    return (
        db.query(models.Document)
        .filter(models.Document.doc_id == doc_id)
        .first()
    )


def get_documents(db: Session) -> List[models.Document]:
    return (
        db.query(models.Document)
        .order_by(models.Document.created_at.desc())
        .all()
    )


def get_inbox(db: Session, user: models.User) -> List[models.Document]:
    """
    Returns the inbox for the authenticated user based on their role.

    DS        → all documents they are responsible for (created_by = user OR
                current_owner = user)
    DIRECTOR  → documents with current_stage = DIRECTOR and current_owner = user
    HOD       → documents routed to this user's department (target_department_id)
                with current_stage = HOD
    EMPLOYEE  → documents assigned to this user (work_assignments) OR
                routed directly (current_owner = user, current_stage = EMPLOYEE)
    """

    if user.role == UserRole.DS:
        return (
            db.query(models.Document)
            .filter(
                (models.Document.created_by == user.id) |
                (models.Document.current_owner_id == user.id)
            )
            .order_by(models.Document.updated_at.desc())
            .all()
        )

    elif user.role == UserRole.DIRECTOR:
        return (
            db.query(models.Document)
            .filter(
                models.Document.current_stage    == WorkflowStage.DIRECTOR,
                models.Document.current_owner_id == user.id
            )
            .order_by(models.Document.updated_at.desc())
            .all()
        )

    elif user.role == UserRole.HOD:
        return (
            db.query(models.Document)
            .filter(
                models.Document.current_stage        == WorkflowStage.HOD,
                models.Document.target_department_id == user.department_id
            )
            .order_by(models.Document.updated_at.desc())
            .all()
        )

    elif user.role == UserRole.EMPLOYEE:
        # Documents assigned via HOD → Employee assignment
        assigned_doc_ids = (
            db.query(models.WorkAssignment.document_id)
            .filter(
                models.WorkAssignment.assigned_to_user_id == user.id,
                models.WorkAssignment.is_active           == True
            )
            .all()
        )
        assigned_doc_ids = [r[0] for r in assigned_doc_ids]

        return (
            db.query(models.Document)
            .filter(
                (models.Document.doc_id.in_(assigned_doc_ids)) |
                (
                    (models.Document.current_owner_id == user.id) &
                    (models.Document.current_stage    == WorkflowStage.EMPLOYEE)
                )
            )
            .order_by(models.Document.updated_at.desc())
            .all()
        )

    return []


# =========================================================
# DOCUMENT — ROUTE  (DS action)
# DS → Director, DS → HOD, DS → Employee
# =========================================================

def route_document(
    db: Session,
    doc_id:     int,
    route_req:  schemas.RouteRequest,
    current_user: models.User
) -> models.Document:

    doc = get_document(db, doc_id)

    if not doc:
        return None

    # Determine new stage and owner from route type
    if route_req.route_type == RouteType.INITIAL_DIRECTOR_REVIEW:
        new_stage  = WorkflowStage.DIRECTOR
        new_status = DocumentStatus.UNDER_DIRECTOR_REVIEW
        new_owner  = route_req.to_user_id

    elif route_req.route_type == RouteType.POST_REVIEW_TO_HOD:
        new_stage  = WorkflowStage.HOD
        new_status = DocumentStatus.UNDER_HOD_PROCESSING
        new_owner  = None   # HOD department-level routing
        if route_req.to_department_id:
            doc.target_department_id = route_req.to_department_id

    elif route_req.route_type == RouteType.POST_REVIEW_TO_EMPLOYEE:
        new_stage  = WorkflowStage.EMPLOYEE
        new_status = DocumentStatus.ASSIGNED_FOR_EXECUTION
        new_owner  = route_req.to_user_id

    elif route_req.route_type == RouteType.FOLLOW_UP_TO_DIRECTOR:
        new_stage  = WorkflowStage.DIRECTOR
        new_status = DocumentStatus.UNDER_DIRECTOR_REVIEW
        new_owner  = route_req.to_user_id

    else:
        return None

    doc.current_stage    = new_stage
    doc.status           = new_status
    doc.current_owner_id = new_owner
    doc.updated_at       = datetime.utcnow()

    # Create route record
    db_route = models.DocumentRoute(
        document_id      = doc_id,
        from_user_id     = current_user.id,
        to_user_id       = route_req.to_user_id,
        to_department_id = route_req.to_department_id,
        route_type       = route_req.route_type,
        remarks          = route_req.remarks,
    )
    db.add(db_route)

    db.commit()
    db.refresh(doc)

    # Workflow history
    event = _add_workflow_history(
        db          = db,
        document_id = doc_id,
        user_id     = current_user.id,
        action      = f"ROUTED_{route_req.route_type.value}",
        from_role   = current_user.role.value,
        to_role     = new_stage.value,
        details     = route_req.remarks
    )

    # Notify recipient
    if route_req.to_user_id:
        _create_notification(
            db                = db,
            user_id           = route_req.to_user_id,
            document_id       = doc_id,
            workflow_event_id = event.id,
            title             = f"New document: {doc.reference_no}",
            message           = f"Document '{doc.title}' has been routed to you."
        )

    return doc


# =========================================================
# DOCUMENT — DIRECTOR REMARK  (independent of return-to-DS)
# =========================================================

def save_director_remark(
    db: Session,
    doc_id:       int,
    remark:       str,
    current_user: models.User
) -> Optional[models.Document]:

    doc = get_document(db, doc_id)
    if not doc:
        return None

    doc.director_remark = remark
    doc.updated_at      = datetime.utcnow()
    db.commit()
    db.refresh(doc)

    _add_workflow_history(
        db          = db,
        document_id = doc_id,
        user_id     = current_user.id,
        action      = "DIRECTOR_REMARK_SAVED",
        from_role   = "DIRECTOR",
        to_role     = None,
        details     = f"Director remark updated"
    )

    return doc


# =========================================================
# DOCUMENT — DIRECTOR RETURN TO DS
# =========================================================

def return_to_ds(
    db: Session,
    doc_id:       int,
    ds_user_id:   int,
    remarks:      Optional[str],
    current_user: models.User
) -> Optional[models.Document]:

    doc = get_document(db, doc_id)
    if not doc:
        return None

    doc.current_stage    = WorkflowStage.DS
    doc.status           = DocumentStatus.DIRECTOR_REVIEW_COMPLETED
    doc.current_owner_id = ds_user_id
    doc.updated_at       = datetime.utcnow()

    # Route record
    db_route = models.DocumentRoute(
        document_id  = doc_id,
        from_user_id = current_user.id,
        to_user_id   = ds_user_id,
        route_type   = RouteType.RETURN_TO_DS,
        remarks      = remarks,
    )
    db.add(db_route)
    db.commit()
    db.refresh(doc)

    event = _add_workflow_history(
        db          = db,
        document_id = doc_id,
        user_id     = current_user.id,
        action      = "RETURNED_TO_DS",
        from_role   = "DIRECTOR",
        to_role     = "DS",
        details     = remarks
    )

    _create_notification(
        db                = db,
        user_id           = ds_user_id,
        document_id       = doc_id,
        workflow_event_id = event.id,
        title             = f"Document returned: {doc.reference_no}",
        message           = f"Director has returned '{doc.title}' to you."
    )

    return doc


# =========================================================
# DOCUMENT — HOD REMARK  (independent of assignment)
# =========================================================

def save_hod_remark(
    db: Session,
    doc_id:       int,
    remark:       str,
    current_user: models.User
) -> Optional[models.Document]:

    doc = get_document(db, doc_id)
    if not doc:
        return None

    doc.hod_remark = remark
    doc.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(doc)

    _add_workflow_history(
        db          = db,
        document_id = doc_id,
        user_id     = current_user.id,
        action      = "HOD_REMARK_SAVED",
        from_role   = "HOD",
        to_role     = None,
        details     = "HOD remark updated"
    )

    return doc


# =========================================================
# DOCUMENT — HOD ASSIGN EMPLOYEE
# =========================================================

def assign_employee(
    db: Session,
    doc_id:       int,
    assign_req:   schemas.AssignmentRequest,
    current_user: models.User
) -> Optional[models.WorkAssignment]:

    doc = get_document(db, doc_id)
    if not doc:
        return None

    # Deactivate any previous active assignment for this document
    (
        db.query(models.WorkAssignment)
        .filter(
            models.WorkAssignment.document_id == doc_id,
            models.WorkAssignment.is_active   == True
        )
        .update({"is_active": False})
    )

    assignment = models.WorkAssignment(
        document_id         = doc_id,
        assigned_by_user_id = current_user.id,
        assigned_to_user_id = assign_req.assigned_to_user_id,
        instructions        = assign_req.instructions,
        is_active           = True,
    )
    db.add(assignment)

    doc.current_stage    = WorkflowStage.EMPLOYEE
    doc.status           = DocumentStatus.ASSIGNED_FOR_EXECUTION
    doc.current_owner_id = assign_req.assigned_to_user_id
    doc.updated_at       = datetime.utcnow()

    db.commit()
    db.refresh(assignment)

    event = _add_workflow_history(
        db          = db,
        document_id = doc_id,
        user_id     = current_user.id,
        action      = "EMPLOYEE_ASSIGNED",
        from_role   = "HOD",
        to_role     = "EMPLOYEE",
        details     = assign_req.instructions
    )

    _create_notification(
        db                = db,
        user_id           = assign_req.assigned_to_user_id,
        document_id       = doc_id,
        workflow_event_id = event.id,
        title             = f"Task assigned: {doc.reference_no}",
        message           = f"You have been assigned document '{doc.title}'."
    )

    return assignment


# =========================================================
# PROGRESS UPDATES  (Employee)
# =========================================================

def create_progress_update(
    db: Session,
    doc_id:       int,
    prog:         schemas.ProgressCreate,
    current_user: models.User
) -> Optional[models.ProgressUpdate]:

    doc = get_document(db, doc_id)
    if not doc:
        return None

    db_progress = models.ProgressUpdate(
        document_id          = doc_id,
        submitted_by_user_id = current_user.id,
        description          = prog.description,
    )
    db.add(db_progress)

    doc.status     = DocumentStatus.IN_PROGRESS
    doc.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(db_progress)

    event = _add_workflow_history(
        db          = db,
        document_id = doc_id,
        user_id     = current_user.id,
        action      = "PROGRESS_UPDATED",
        from_role   = "EMPLOYEE",
        to_role     = None,
        details     = prog.description[:200]
    )

    # Notify DS (created_by) and HOD (target_department HODs)
    if doc.created_by:
        _create_notification(
            db                = db,
            user_id           = doc.created_by,
            document_id       = doc_id,
            workflow_event_id = event.id,
            title             = f"Progress update: {doc.reference_no}",
            message           = f"Employee submitted a progress update on '{doc.title}'."
        )

    return db_progress


def get_progress_updates(
    db: Session,
    doc_id: int
) -> List[models.ProgressUpdate]:
    return (
        db.query(models.ProgressUpdate)
        .filter(models.ProgressUpdate.document_id == doc_id)
        .order_by(models.ProgressUpdate.created_at)
        .all()
    )


# =========================================================
# ATTACHMENTS
# =========================================================

def create_attachment(
    db: Session,
    doc_id:             int,
    progress_update_id: Optional[int],
    uploaded_by:        int,
    file_name:          str,
    storage_key:        str,
    file_type:          Optional[str],
    file_size:          Optional[int]
) -> models.Attachment:

    att = models.Attachment(
        document_id         = doc_id,
        progress_update_id  = progress_update_id,
        uploaded_by_user_id = uploaded_by,
        file_name           = file_name,
        storage_key         = storage_key,
        file_type           = file_type,
        file_size           = file_size,
    )
    db.add(att)
    db.commit()
    db.refresh(att)

    _add_workflow_history(
        db          = db,
        document_id = doc_id,
        user_id     = uploaded_by,
        action      = "ATTACHMENT_UPLOADED",
        from_role   = None,
        to_role     = None,
        details     = f"File uploaded: {file_name}"
    )

    return att


def get_attachments(
    db: Session,
    doc_id: int
) -> List[models.Attachment]:
    return (
        db.query(models.Attachment)
        .filter(models.Attachment.document_id == doc_id)
        .order_by(models.Attachment.created_at)
        .all()
    )


def get_attachment(
    db: Session,
    attachment_id: int
) -> Optional[models.Attachment]:
    return (
        db.query(models.Attachment)
        .filter(models.Attachment.id == attachment_id)
        .first()
    )


# =========================================================
# FOLLOW-UP  (DS → Director with employee progress context)
# =========================================================

def follow_up_to_director(
    db: Session,
    doc_id:        int,
    director_user: models.User,
    remarks:       Optional[str],
    current_user:  models.User
) -> Optional[models.Document]:

    doc = get_document(db, doc_id)
    if not doc:
        return None

    doc.current_stage    = WorkflowStage.DIRECTOR
    doc.status           = DocumentStatus.UNDER_DIRECTOR_REVIEW
    doc.current_owner_id = director_user.id
    doc.updated_at       = datetime.utcnow()

    db_route = models.DocumentRoute(
        document_id  = doc_id,
        from_user_id = current_user.id,
        to_user_id   = director_user.id,
        route_type   = RouteType.FOLLOW_UP_TO_DIRECTOR,
        remarks      = remarks,
    )
    db.add(db_route)
    db.commit()
    db.refresh(doc)

    event = _add_workflow_history(
        db          = db,
        document_id = doc_id,
        user_id     = current_user.id,
        action      = "FOLLOW_UP_TO_DIRECTOR",
        from_role   = "DS",
        to_role     = "DIRECTOR",
        details     = remarks
    )

    _create_notification(
        db                = db,
        user_id           = director_user.id,
        document_id       = doc_id,
        workflow_event_id = event.id,
        title             = f"Follow-up required: {doc.reference_no}",
        message           = f"DS has forwarded a follow-up on '{doc.title}' for your review."
    )

    return doc


# =========================================================
# CLOSE DOCUMENT  (DS)
# =========================================================

def close_document(
    db: Session,
    doc_id:       int,
    remarks:      Optional[str],
    current_user: models.User
) -> Optional[models.Document]:

    doc = get_document(db, doc_id)
    if not doc:
        return None

    doc.status        = DocumentStatus.CLOSED
    doc.current_stage = WorkflowStage.CLOSED
    doc.closed_at     = datetime.utcnow()
    doc.updated_at    = datetime.utcnow()

    db.commit()
    db.refresh(doc)

    _add_workflow_history(
        db          = db,
        document_id = doc_id,
        user_id     = current_user.id,
        action      = "DOCUMENT_CLOSED",
        from_role   = "DS",
        to_role     = "CLOSED",
        details     = remarks
    )

    return doc


# =========================================================
# WORKFLOW HISTORY
# =========================================================

def _add_workflow_history(
    db: Session,
    document_id: int,
    user_id:     int,
    action:      str,
    from_role:   Optional[str] = None,
    to_role:     Optional[str] = None,
    details:     Optional[str] = None
) -> models.WorkflowHistory:

    entry = models.WorkflowHistory(
        document_id          = document_id,
        performed_by_user_id = user_id,
        action               = action,
        from_role            = from_role,
        to_role              = to_role,
        details              = details,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_document_history(
    db: Session,
    doc_id: int
) -> List[models.WorkflowHistory]:
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
    user_id:           int,
    document_id:       Optional[int],
    workflow_event_id: Optional[int],
    title:             str,
    message:           str
) -> models.Notification:

    notif = models.Notification(
        user_id           = user_id,
        document_id       = document_id,
        workflow_event_id = workflow_event_id,
        title             = title,
        message           = message,
        is_read           = False,
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)
    return notif


def get_notifications(
    db: Session,
    user_id: int
) -> List[models.Notification]:
    return (
        db.query(models.Notification)
        .filter(models.Notification.user_id == user_id)
        .order_by(models.Notification.created_at.desc())
        .all()
    )


def get_unread_notifications(
    db: Session,
    user_id: int
) -> List[models.Notification]:
    return (
        db.query(models.Notification)
        .filter(
            models.Notification.user_id == user_id,
            models.Notification.is_read == False
        )
        .order_by(models.Notification.created_at.desc())
        .all()
    )


def mark_notification_read(
    db: Session,
    notification_id: int,
    user_id:         int
) -> Optional[models.Notification]:

    notif = (
        db.query(models.Notification)
        .filter(
            models.Notification.id      == notification_id,
            models.Notification.user_id == user_id
        )
        .first()
    )

    if not notif:
        return None

    notif.is_read = True
    db.commit()
    db.refresh(notif)
    return notif


def mark_all_notifications_read(
    db: Session,
    user_id: int
) -> int:
    """Returns count of notifications marked as read."""
    updated = (
        db.query(models.Notification)
        .filter(
            models.Notification.user_id == user_id,
            models.Notification.is_read == False
        )
        .update({"is_read": True})
    )
    db.commit()
    return updated


# =========================================================
# AUDIT LOG
# =========================================================

def create_audit_log(
    db: Session,
    user_id:     int,
    action:      str,
    entity_type: Optional[str] = None,
    entity_id:   Optional[int] = None,
    description: Optional[str] = None
) -> models.AuditLog:

    audit = models.AuditLog(
        user_id     = user_id,
        action      = action,
        entity_type = entity_type,
        entity_id   = entity_id,
        description = description,
    )
    db.add(audit)
    db.commit()
    return audit


# =========================================================
# DASHBOARD STATS
# =========================================================

def get_dashboard_stats(
    db: Session,
    user: models.User
) -> dict:

    unread_count = (
        db.query(func.count(models.Notification.id))
        .filter(
            models.Notification.user_id == user.id,
            models.Notification.is_read == False
        )
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
            .filter(
                models.Document.created_by    == user.id,
                models.Document.current_stage == WorkflowStage.DIRECTOR
            )
            .scalar()
        ) or 0

        under_hod = (
            db.query(func.count(models.Document.doc_id))
            .filter(
                models.Document.created_by    == user.id,
                models.Document.current_stage == WorkflowStage.HOD
            )
            .scalar()
        ) or 0

        in_progress = (
            db.query(func.count(models.Document.doc_id))
            .filter(
                models.Document.created_by    == user.id,
                models.Document.current_stage == WorkflowStage.EMPLOYEE
            )
            .scalar()
        ) or 0

        closed = (
            db.query(func.count(models.Document.doc_id))
            .filter(
                models.Document.created_by    == user.id,
                models.Document.current_stage == WorkflowStage.CLOSED
            )
            .scalar()
        ) or 0

        pending = total - closed

        return {
            "role": user.role.value,
            "total_documents": total,
            "pending_action": pending,
            "unread_notifications": unread_count,
            "under_director_review": under_director,
            "under_hod_processing": under_hod,
            "in_progress": in_progress,
            "closed_documents": closed,
        }

    elif user.role == UserRole.DIRECTOR:
        for_review = (
            db.query(func.count(models.Document.doc_id))
            .filter(
                models.Document.current_owner_id == user.id,
                models.Document.current_stage    == WorkflowStage.DIRECTOR
            )
            .scalar()
        ) or 0

        return {
            "role": user.role.value,
            "total_documents": for_review,
            "pending_action": for_review,
            "unread_notifications": unread_count,
            "documents_for_review": for_review,
        }

    elif user.role == UserRole.HOD:
        dept_docs = (
            db.query(func.count(models.Document.doc_id))
            .filter(
                models.Document.target_department_id == user.department_id,
                models.Document.current_stage        == WorkflowStage.HOD
            )
            .scalar()
        ) or 0

        pending_assignment = (
            db.query(func.count(models.Document.doc_id))
            .filter(
                models.Document.target_department_id == user.department_id,
                models.Document.status               == DocumentStatus.UNDER_HOD_PROCESSING
            )
            .scalar()
        ) or 0

        return {
            "role": user.role.value,
            "total_documents": dept_docs,
            "pending_action": pending_assignment,
            "unread_notifications": unread_count,
            "pending_assignment": pending_assignment,
        }

    elif user.role == UserRole.EMPLOYEE:
        active = (
            db.query(func.count(models.WorkAssignment.id))
            .filter(
                models.WorkAssignment.assigned_to_user_id == user.id,
                models.WorkAssignment.is_active           == True
            )
            .scalar()
        ) or 0

        return {
            "role": user.role.value,
            "total_documents": active,
            "pending_action": active,
            "unread_notifications": unread_count,
            "active_assignments": active,
        }

    return {
        "role": user.role.value,
        "total_documents": 0,
        "pending_action": 0,
        "unread_notifications": unread_count,
    }


# =========================================================
# SEED DATA  (dev/testing only — call with SEED_DB=true)
# =========================================================

def seed_data(db: Session) -> None:
    """
    Populates the database with test users for all four roles.
    Safe to call multiple times — skips existing usernames.
    """

    # Departments
    depts_data = [
        {"name": "Administration",  "code": "ADMIN"},
        {"name": "Finance",         "code": "FIN"},
        {"name": "Human Resources", "code": "HR"},
        {"name": "Technical",       "code": "TECH"},
    ]

    dept_map = {}
    for d in depts_data:
        existing = (
            db.query(models.Department)
            .filter(models.Department.name == d["name"])
            .first()
        )
        if not existing:
            dept = models.Department(name=d["name"], code=d["code"])
            db.add(dept)
            db.commit()
            db.refresh(dept)
            dept_map[d["name"]] = dept.id
        else:
            dept_map[d["name"]] = existing.id

    # Test users
    users_data = [
        {
            "username":      "ds_user",
            "password":      "cdtrs@ds",
            "full_name":     "Director Secretary",
            "role":          UserRole.DS,
            "department_id": dept_map["Administration"],
        },
        {
            "username":  "director",
            "password":  "cdtrs@director",
            "full_name": "The Director",
            "role":      UserRole.DIRECTOR,
        },
        {
            "username":      "hod_finance",
            "password":      "cdtrs@hod",
            "full_name":     "HOD Finance",
            "role":          UserRole.HOD,
            "department_id": dept_map["Finance"],
        },
        {
            "username":      "emp_rahul",
            "password":      "cdtrs@emp",
            "full_name":     "Rahul Sharma",
            "role":          UserRole.EMPLOYEE,
            "department_id": dept_map["Finance"],
        },
    ]

    for u in users_data:
        if not get_user_by_username(db, u["username"]):
            user = models.User(
                username      = u["username"],
                password_hash = hash_password(u["password"]),
                full_name     = u["full_name"],
                role          = u["role"],
                department_id = u.get("department_id"),
            )
            db.add(user)
            db.commit()

    print("Seed data inserted successfully.")
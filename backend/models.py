from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Date,
    DateTime,
    Boolean,
    BigInteger,
    ForeignKey,
    Enum as SAEnum,
)
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from database import Base


# =========================================================
# ENUMS
# =========================================================

class UserRole(str, enum.Enum):
    DS       = "DS"
    DIRECTOR = "DIRECTOR"
    HOD      = "HOD"
    EMPLOYEE = "EMPLOYEE"


class DocumentStatus(str, enum.Enum):
    RECEIVED                  = "RECEIVED"
    UNDER_DIRECTOR_REVIEW     = "UNDER_DIRECTOR_REVIEW"
    DIRECTOR_REVIEW_COMPLETED = "DIRECTOR_REVIEW_COMPLETED"
    UNDER_HOD_PROCESSING      = "UNDER_HOD_PROCESSING"
    ASSIGNED_FOR_EXECUTION    = "ASSIGNED_FOR_EXECUTION"
    IN_PROGRESS               = "IN_PROGRESS"
    PROGRESS_UPDATED          = "PROGRESS_UPDATED"
    REVIEW_COMPLETED          = "REVIEW_COMPLETED"
    CLOSED                    = "CLOSED"


class WorkflowStage(str, enum.Enum):
    DS       = "DS"
    DIRECTOR = "DIRECTOR"
    HOD      = "HOD"
    EMPLOYEE = "EMPLOYEE"
    CLOSED   = "CLOSED"


class Priority(str, enum.Enum):
    HIGH   = "HIGH"
    MEDIUM = "MEDIUM"
    LOW    = "LOW"


class RouteType(str, enum.Enum):
    INITIAL_DIRECTOR_REVIEW   = "INITIAL_DIRECTOR_REVIEW"
    RETURN_TO_DS              = "RETURN_TO_DS"
    POST_REVIEW_TO_HOD        = "POST_REVIEW_TO_HOD"
    POST_REVIEW_TO_EMPLOYEE   = "POST_REVIEW_TO_EMPLOYEE"
    FOLLOW_UP_TO_DIRECTOR     = "FOLLOW_UP_TO_DIRECTOR"


# =========================================================
# DEPARTMENT
# =========================================================

class Department(Base):

    __tablename__ = "departments"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    name = Column(
        String(100),
        unique=True,
        nullable=False
    )

    # Optional short code e.g. "FIN", "HR"
    code = Column(
        String(20),
        unique=True,
        nullable=True
    )

    is_active = Column(
        Boolean,
        default=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    # Relationships
    users      = relationship("User",     back_populates="department")
    employees  = relationship("Employee", back_populates="department")


# =========================================================
# EMPLOYEE
# =========================================================

class Employee(Base):

    __tablename__ = "employees"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    # Unique employee code e.g. "EMP-001"
    employee_code = Column(
        String(50),
        unique=True,
        nullable=False
    )

    full_name = Column(
        String(100),
        nullable=False
    )

    department_id = Column(
        Integer,
        ForeignKey("departments.id"),
        nullable=False
    )

    designation = Column(
        String(100),
        nullable=False
    )

    # Linked user account (nullable — employee may not have login yet)
    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True
    )

    is_active = Column(
        Boolean,
        default=True
    )

    # Relationships
    department = relationship("Department", back_populates="employees")
    user       = relationship("User", foreign_keys=[user_id], back_populates="employee_record")


# =========================================================
# USER
# =========================================================

class User(Base):

    __tablename__ = "users"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    username = Column(
        String(50),
        unique=True,
        nullable=False,
        index=True
    )

    password_hash = Column(
        String(255),
        nullable=False
    )

    full_name = Column(
        String(100),
        nullable=False
    )

    role = Column(
        SAEnum(UserRole, name="user_role"),
        nullable=False
    )

    department_id = Column(
        Integer,
        ForeignKey("departments.id"),
        nullable=True
    )

    # If the user is also an Employee record
    employee_id = Column(
        Integer,
        nullable=True
    )

    is_active = Column(
        Boolean,
        default=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # Relationships
    department     = relationship("Department", back_populates="users")
    employee_record = relationship(
        "Employee",
        foreign_keys="Employee.user_id",
        back_populates="user",
        uselist=False
    )
    notifications  = relationship("Notification", back_populates="user", cascade="all, delete-orphan")


# =========================================================
# DOCUMENT (main document table — V2)
# =========================================================

class Document(Base):

    __tablename__ = "documents"

    doc_id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    # Human-readable CDTRS reference e.g. CDTRS-2026-001
    reference_no = Column(
        String(50),
        unique=True,
        nullable=False,
        index=True
    )

    title = Column(
        String(255),
        nullable=False
    )

    description = Column(
        Text,
        nullable=True
    )

    # Date the external document was received
    received_date = Column(
        Date,
        nullable=False
    )

    deadline = Column(
        Date,
        nullable=True
    )

    # External / internal source
    source = Column(
        String(255),
        nullable=True
    )

    # Mode: Email, Fax, Physical, Intranet, etc.
    mode = Column(
        String(50),
        nullable=False
    )

    priority = Column(
        SAEnum(Priority, name="priority_enum"),
        default=Priority.MEDIUM,
        nullable=False
    )

    status = Column(
        SAEnum(DocumentStatus, name="document_status"),
        default=DocumentStatus.RECEIVED,
        nullable=False
    )

    # Internal routing stage
    current_stage = Column(
        SAEnum(WorkflowStage, name="workflow_stage"),
        default=WorkflowStage.DS,
        nullable=False
    )

    # User currently responsible for the document
    current_owner_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True
    )

    target_department_id = Column(
        Integer,
        ForeignKey("departments.id"),
        nullable=True
    )

    created_by = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )

    # Latest Director remark (updated in-place; full history in workflow_history)
    director_remark = Column(
        Text,
        nullable=True
    )

    # Latest HOD remark
    hod_remark = Column(
        Text,
        nullable=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    closed_at = Column(
        DateTime,
        nullable=True
    )

    # Relationships
    creator          = relationship("User",            foreign_keys=[created_by])
    current_owner    = relationship("User",            foreign_keys=[current_owner_id])
    target_department = relationship("Department",     foreign_keys=[target_department_id])
    routes           = relationship("DocumentRoute",   back_populates="document",  cascade="all, delete-orphan")
    assignments      = relationship("WorkAssignment",  back_populates="document",  cascade="all, delete-orphan")
    progress_updates = relationship("ProgressUpdate",  back_populates="document",  cascade="all, delete-orphan")
    attachments      = relationship("Attachment",      back_populates="document",  cascade="all, delete-orphan")
    workflow_history = relationship("WorkflowHistory", back_populates="document",  cascade="all, delete-orphan")
    notifications    = relationship("Notification",    back_populates="document",  cascade="all, delete-orphan")


# =========================================================
# DOCUMENT ROUTES
# DS decides where the document goes (routing ≠ assignment)
# =========================================================

class DocumentRoute(Base):

    __tablename__ = "document_routes"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    document_id = Column(
        Integer,
        ForeignKey("documents.doc_id"),
        nullable=False
    )

    from_user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )

    # Recipient user (if routed to a specific person)
    to_user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True
    )

    # Recipient department (if routed to a department)
    to_department_id = Column(
        Integer,
        ForeignKey("departments.id"),
        nullable=True
    )

    route_type = Column(
        SAEnum(RouteType, name="route_type_enum"),
        nullable=False
    )

    remarks = Column(
        Text,
        nullable=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    # Relationships
    document   = relationship("Document",   back_populates="routes")
    from_user  = relationship("User",       foreign_keys=[from_user_id])
    to_user    = relationship("User",       foreign_keys=[to_user_id])
    to_department = relationship("Department", foreign_keys=[to_department_id])


# =========================================================
# WORK ASSIGNMENTS
# HOD → Employee assignment (separate from routing)
# =========================================================

class WorkAssignment(Base):

    __tablename__ = "work_assignments"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    document_id = Column(
        Integer,
        ForeignKey("documents.doc_id"),
        nullable=False
    )

    assigned_by_user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )

    assigned_to_user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )

    instructions = Column(
        Text,
        nullable=True
    )

    is_active = Column(
        Boolean,
        default=True
    )

    assigned_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    completed_at = Column(
        DateTime,
        nullable=True
    )

    # Relationships
    document     = relationship("Document", back_populates="assignments")
    assigned_by  = relationship("User",     foreign_keys=[assigned_by_user_id])
    assigned_to  = relationship("User",     foreign_keys=[assigned_to_user_id])


# =========================================================
# PROGRESS UPDATES
# Employee submits free-text progress. Never overwritten.
# =========================================================

class ProgressUpdate(Base):

    __tablename__ = "progress_updates"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    document_id = Column(
        Integer,
        ForeignKey("documents.doc_id"),
        nullable=False
    )

    submitted_by_user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )

    description = Column(
        Text,
        nullable=False
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    # Relationships
    document     = relationship("Document",    back_populates="progress_updates")
    submitted_by = relationship("User",        foreign_keys=[submitted_by_user_id])
    attachments  = relationship("Attachment",  back_populates="progress_update")


# =========================================================
# ATTACHMENTS
# progress_update_id = NULL  → original document attachment
# progress_update_id = <id>  → employee progress attachment
# =========================================================

class Attachment(Base):

    __tablename__ = "attachments"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    document_id = Column(
        Integer,
        ForeignKey("documents.doc_id"),
        nullable=False
    )

    progress_update_id = Column(
        Integer,
        ForeignKey("progress_updates.id"),
        nullable=True
    )

    uploaded_by_user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )

    # Original filename as uploaded
    file_name = Column(
        String(255),
        nullable=False
    )

    # Server-side storage path / key
    storage_key = Column(
        String(500),
        nullable=False
    )

    file_type = Column(
        String(100),
        nullable=True
    )

    file_size = Column(
        BigInteger,
        nullable=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    # Relationships
    document        = relationship("Document",       back_populates="attachments")
    progress_update = relationship("ProgressUpdate", back_populates="attachments")
    uploaded_by     = relationship("User",           foreign_keys=[uploaded_by_user_id])


# =========================================================
# WORKFLOW HISTORY
# Document-centric. User-visible audit trail.
# =========================================================

class WorkflowHistory(Base):

    __tablename__ = "workflow_history"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    document_id = Column(
        Integer,
        ForeignKey("documents.doc_id"),
        nullable=False
    )

    performed_by_user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )

    action = Column(
        String(150),
        nullable=False
    )

    from_role = Column(
        String(50),
        nullable=True
    )

    to_role = Column(
        String(50),
        nullable=True
    )

    details = Column(
        Text,
        nullable=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    # Relationships
    document      = relationship("Document", back_populates="workflow_history")
    performed_by  = relationship("User",     foreign_keys=[performed_by_user_id])


# =========================================================
# AUDIT LOG
# System / security / administrative events.
# Separate from workflow_history.
# =========================================================

class AuditLog(Base):

    __tablename__ = "audit_logs"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )

    action = Column(
        String(100),
        nullable=False
    )

    entity_type = Column(
        String(50),
        nullable=True
    )

    entity_id = Column(
        Integer,
        nullable=True
    )

    description = Column(
        Text,
        nullable=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )


# =========================================================
# NOTIFICATIONS
# =========================================================

class Notification(Base):

    __tablename__ = "notifications"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )

    document_id = Column(
        Integer,
        ForeignKey("documents.doc_id"),
        nullable=True
    )

    # Optional reference to the workflow event that triggered this
    workflow_event_id = Column(
        Integer,
        ForeignKey("workflow_history.id"),
        nullable=True
    )

    title = Column(
        String(200),
        nullable=False
    )

    message = Column(
        Text,
        nullable=False
    )

    is_read = Column(
        Boolean,
        default=False
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    # Relationships
    user     = relationship("User",     back_populates="notifications")
    document = relationship("Document", back_populates="notifications")
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Date,
    DateTime,
    Boolean,
    Float,
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


class SourceType(str, enum.Enum):
    OUTLOOK                  = "OUTLOOK"
    GOVERNMENT_MAIL          = "GOVERNMENT_MAIL"
    MANUAL_UPLOAD            = "MANUAL_UPLOAD"
    OTHER_APPROVED_SOURCE    = "OTHER_APPROVED_SOURCE"


class MessageProcessingStatus(str, enum.Enum):
    NEW        = "NEW"
    PROCESSING = "PROCESSING"
    PROCESSED  = "PROCESSED"
    FAILED     = "FAILED"
    IGNORED    = "IGNORED"


class AttachmentType(str, enum.Enum):
    ORIGINAL            = "ORIGINAL"
    EMAIL_ATTACHMENT    = "EMAIL_ATTACHMENT"
    SUPPORTING_DOCUMENT = "SUPPORTING_DOCUMENT"
    PROGRESS_ATTACHMENT = "PROGRESS_ATTACHMENT"


class OCRStatus(str, enum.Enum):
    NONE       = "NONE"
    PENDING    = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED  = "COMPLETED"
    FAILED     = "FAILED"


class RoutingSource(str, enum.Enum):
    DOCUMENT_CONTENT = "DOCUMENT_CONTENT"
    DIRECTOR_REMARK  = "DIRECTOR_REMARK"
    SOURCE_METADATA  = "SOURCE_METADATA"
    MANUAL           = "MANUAL"


class RemarkType(str, enum.Enum):
    DIRECTOR = "DIRECTOR"
    HOD      = "HOD"
    OTHER    = "OTHER"


class ReminderReason(str, enum.Enum):
    DUE_SOON        = "DUE_SOON"
    OVERDUE         = "OVERDUE"
    ACTION_REQUIRED = "ACTION_REQUIRED"


# =========================================================
# DEPARTMENT
# =========================================================

class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    code = Column(String(20), unique=True, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    users      = relationship("User", back_populates="department")
    employees  = relationship("Employee", back_populates="department")


# =========================================================
# EMPLOYEE
# =========================================================

class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    employee_code = Column(String(50), unique=True, nullable=False)
    full_name = Column(String(100), nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False)
    designation = Column(String(100), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    is_active = Column(Boolean, default=True)

    # Relationships
    department = relationship("Department", back_populates="employees")
    user       = relationship("User", foreign_keys=[user_id], back_populates="employee_record")


# =========================================================
# USER
# =========================================================

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    role = Column(SAEnum(UserRole, name="user_role"), nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    employee_id = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    department      = relationship("Department", back_populates="users")
    employee_record = relationship(
        "Employee",
        foreign_keys="Employee.user_id",
        back_populates="user",
        uselist=False
    )
    notifications   = relationship("Notification", back_populates="user", cascade="all, delete-orphan")


# =========================================================
# INCOMING MESSAGES (Mail Intake & Provenance)
# =========================================================

class IncomingMessage(Base):
    __tablename__ = "incoming_messages"

    id = Column(Integer, primary_key=True, index=True)
    source_type = Column(SAEnum(SourceType, name="source_type_enum"), default=SourceType.MANUAL_UPLOAD, nullable=False)
    external_message_id = Column(String(255), unique=True, nullable=True, index=True)  # Deduplication key
    sender_name = Column(String(150), nullable=True)
    sender_email = Column(String(255), nullable=True)
    subject = Column(String(500), nullable=True)
    received_at = Column(DateTime, default=datetime.utcnow)
    body_reference = Column(Text, nullable=True)
    has_attachments = Column(Boolean, default=False)
    processing_status = Column(SAEnum(MessageProcessingStatus, name="msg_status_enum"), default=MessageProcessingStatus.NEW, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    documents   = relationship("Document", back_populates="source_message")
    attachments = relationship("Attachment", back_populates="source_message")


# =========================================================
# DOCUMENT (Main Canonical Document Table)
# =========================================================

class Document(Base):
    __tablename__ = "documents"

    doc_id = Column(Integer, primary_key=True, index=True)
    reference_no = Column(String(50), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    received_date = Column(Date, nullable=False)
    deadline = Column(Date, nullable=True)
    source = Column(String(255), nullable=True)
    mode = Column(String(50), nullable=False)
    priority = Column(SAEnum(Priority, name="priority_enum"), default=Priority.MEDIUM, nullable=False)
    status = Column(SAEnum(DocumentStatus, name="document_status"), default=DocumentStatus.RECEIVED, nullable=False)
    current_stage = Column(SAEnum(WorkflowStage, name="workflow_stage"), default=WorkflowStage.DS, nullable=False)
    current_owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    target_department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Source & OCR linkages
    source_message_id = Column(Integer, ForeignKey("incoming_messages.id"), nullable=True)
    ocr_status = Column(SAEnum(OCRStatus, name="ocr_status_enum"), default=OCRStatus.NONE, nullable=False)

    # Optimistic Concurrency Control
    version = Column(Integer, default=1, nullable=False)

    # Latest remarks for fast UI lookup
    director_remark = Column(Text, nullable=True)
    hod_remark = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)

    # Relationships
    creator            = relationship("User", foreign_keys=[created_by])
    current_owner      = relationship("User", foreign_keys=[current_owner_id])
    target_department  = relationship("Department", foreign_keys=[target_department_id])
    source_message     = relationship("IncomingMessage", back_populates="documents")
    routes             = relationship("DocumentRoute", back_populates="document", cascade="all, delete-orphan")
    assignments        = relationship("WorkAssignment", back_populates="document", cascade="all, delete-orphan")
    progress_updates   = relationship("ProgressUpdate", back_populates="document", cascade="all, delete-orphan")
    attachments        = relationship("Attachment", back_populates="document", cascade="all, delete-orphan")
    workflow_history   = relationship("WorkflowHistory", back_populates="document", cascade="all, delete-orphan")
    notifications      = relationship("Notification", back_populates="document", cascade="all, delete-orphan")
    ocr_record         = relationship("DocumentOCR", back_populates="document", uselist=False, cascade="all, delete-orphan")
    extracted_fields   = relationship("DocumentExtractedField", back_populates="document", cascade="all, delete-orphan")
    routing_suggestion = relationship("RoutingSuggestion", back_populates="document", uselist=False, cascade="all, delete-orphan")
    remarks_history    = relationship("DocumentRemark", back_populates="document", cascade="all, delete-orphan")
    reminders          = relationship("Reminder", back_populates="document", cascade="all, delete-orphan")


# =========================================================
# DOCUMENT ROUTES (DS Decisions)
# =========================================================

class DocumentRoute(Base):
    __tablename__ = "document_routes"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.doc_id"), nullable=False)
    from_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    to_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    to_department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    route_type = Column(SAEnum(RouteType, name="route_type_enum"), nullable=False)
    remarks = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    document      = relationship("Document", back_populates="routes")
    from_user     = relationship("User", foreign_keys=[from_user_id])
    to_user       = relationship("User", foreign_keys=[to_user_id])
    to_department = relationship("Department", foreign_keys=[to_department_id])


# =========================================================
# WORK ASSIGNMENTS (HOD -> Employee)
# =========================================================

class WorkAssignment(Base):
    __tablename__ = "work_assignments"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.doc_id"), nullable=False)
    assigned_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    assigned_to_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    instructions = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    assigned_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    document    = relationship("Document", back_populates="assignments")
    assigned_by = relationship("User", foreign_keys=[assigned_by_user_id])
    assigned_to = relationship("User", foreign_keys=[assigned_to_user_id])


# =========================================================
# PROGRESS UPDATES (Employee free-text updates)
# =========================================================

class ProgressUpdate(Base):
    __tablename__ = "progress_updates"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.doc_id"), nullable=False)
    submitted_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    description = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    document     = relationship("Document", back_populates="progress_updates")
    submitted_by = relationship("User", foreign_keys=[submitted_by_user_id])
    attachments  = relationship("Attachment", back_populates="progress_update")


# =========================================================
# ATTACHMENTS (Storage & Provenance)
# =========================================================

class Attachment(Base):
    __tablename__ = "attachments"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.doc_id"), nullable=False)
    progress_update_id = Column(Integer, ForeignKey("progress_updates.id"), nullable=True)
    uploaded_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    file_name = Column(String(255), nullable=False)
    storage_key = Column(String(500), nullable=False)
    file_type = Column(String(100), nullable=True)
    file_size = Column(BigInteger, nullable=True)
    checksum = Column(String(64), nullable=True)  # SHA-256 integrity hash
    attachment_type = Column(SAEnum(AttachmentType, name="att_type_enum"), default=AttachmentType.ORIGINAL, nullable=False)
    source_message_id = Column(Integer, ForeignKey("incoming_messages.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    document        = relationship("Document", back_populates="attachments")
    progress_update = relationship("ProgressUpdate", back_populates="attachments")
    uploaded_by     = relationship("User", foreign_keys=[uploaded_by_user_id])
    source_message  = relationship("IncomingMessage", back_populates="attachments")


# =========================================================
# DOCUMENT REMARKS (Complete History of Remarks)
# =========================================================

class DocumentRemark(Base):
    __tablename__ = "document_remarks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.doc_id"), nullable=False)
    author_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(SAEnum(UserRole, name="user_role_remark"), nullable=False)
    remark_text = Column(Text, nullable=False)
    remark_type = Column(SAEnum(RemarkType, name="remark_type_enum"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    document = relationship("Document", back_populates="remarks_history")
    author   = relationship("User", foreign_keys=[author_user_id])


# =========================================================
# DOCUMENT OCR (Full OCR Artifact)
# =========================================================

class DocumentOCR(Base):
    __tablename__ = "document_ocr"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.doc_id"), unique=True, nullable=False)
    extracted_text = Column(Text, nullable=True)
    ocr_status = Column(SAEnum(OCRStatus, name="ocr_record_status_enum"), default=OCRStatus.PENDING, nullable=False)
    ocr_engine = Column(String(100), default="Tesseract-v5/PaddleOCR", nullable=False)
    confidence = Column(Float, nullable=True)
    processed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)

    # Relationships
    document = relationship("Document", back_populates="ocr_record")


# =========================================================
# DOCUMENT EXTRACTED FIELDS (Structured Key-Values & Verification)
# =========================================================

class DocumentExtractedField(Base):
    __tablename__ = "document_extracted_fields"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.doc_id"), nullable=False)
    field_name = Column(String(100), nullable=False)  # TITLE, REFERENCE_NO, DEPARTMENT, EMPLOYEE, DEADLINE, PRIORITY
    extracted_value = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    source_page = Column(Integer, default=1, nullable=True)
    source_text = Column(Text, nullable=True)
    verified_value = Column(Text, nullable=True)  # DS-verified value (preserved upon re-analysis)
    verified_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    verified_at = Column(DateTime, nullable=True)

    # Relationships
    document      = relationship("Document", back_populates="extracted_fields")
    verifier_user = relationship("User", foreign_keys=[verified_by])


# =========================================================
# ROUTING SUGGESTIONS (Advisory Routing Intelligence)
# =========================================================

class RoutingSuggestion(Base):
    __tablename__ = "routing_suggestions"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.doc_id"), unique=True, nullable=False)
    suggested_department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    suggested_employee_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    routing_confidence = Column(Float, nullable=False)  # 0.0 to 1.0
    routing_reason = Column(Text, nullable=False)
    routing_source = Column(SAEnum(RoutingSource, name="routing_source_enum"), default=RoutingSource.DOCUMENT_CONTENT, nullable=False)
    is_director_instruction = Column(Boolean, default=False)  # Highlighted alert for DS
    generated_at = Column(DateTime, default=datetime.utcnow)
    confirmed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    confirmed_at = Column(DateTime, nullable=True)

    # Relationships
    document             = relationship("Document", back_populates="routing_suggestion")
    suggested_department = relationship("Department", foreign_keys=[suggested_department_id])
    suggested_employee   = relationship("User", foreign_keys=[suggested_employee_id])
    confirmer            = relationship("User", foreign_keys=[confirmed_by])


# =========================================================
# REMINDERS (Deadline & Action Escalation)
# =========================================================

class Reminder(Base):
    __tablename__ = "reminders"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.doc_id"), nullable=False)
    recipient_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reason = Column(SAEnum(ReminderReason, name="reminder_reason_enum"), nullable=False)
    due_at = Column(DateTime, nullable=True)
    sent_at = Column(DateTime, default=datetime.utcnow)
    is_read = Column(Boolean, default=False)
    deduplication_key = Column(String(200), unique=True, nullable=False, index=True)

    # Relationships
    document       = relationship("Document", back_populates="reminders")
    recipient_user = relationship("User", foreign_keys=[recipient_user_id])


# =========================================================
# WORKFLOW HISTORY (Document-centric Audit Trail)
# =========================================================

class WorkflowHistory(Base):
    __tablename__ = "workflow_history"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.doc_id"), nullable=False)
    performed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String(150), nullable=False)
    from_role = Column(String(50), nullable=True)
    to_role = Column(String(50), nullable=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    document     = relationship("Document", back_populates="workflow_history")
    performed_by = relationship("User", foreign_keys=[performed_by_user_id])


# =========================================================
# AUDIT LOG (System/Security/Administrative Logs)
# =========================================================

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String(100), nullable=False)
    entity_type = Column(String(50), nullable=True)
    entity_id = Column(Integer, nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# =========================================================
# NOTIFICATIONS (In-App Notifications)
# =========================================================

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    document_id = Column(Integer, ForeignKey("documents.doc_id"), nullable=True)
    workflow_event_id = Column(Integer, ForeignKey("workflow_history.id"), nullable=True)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user     = relationship("User", back_populates="notifications")
    document = relationship("Document", back_populates="notifications")
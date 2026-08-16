from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Any
from datetime import date, datetime

from models import (
    UserRole, DocumentStatus, WorkflowStage, Priority, RouteType,
    SourceType, MessageProcessingStatus, AttachmentType, OCRStatus,
    RoutingSource, RemarkType, ReminderReason
)


# =========================================================
# DEPARTMENT
# =========================================================

class DepartmentCreate(BaseModel):
    name: str
    code: Optional[str] = None


class DepartmentResponse(BaseModel):
    id:         int
    name:       str
    code:       Optional[str] = None
    is_active:  bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# =========================================================
# EMPLOYEE
# =========================================================

class EmployeeCreate(BaseModel):
    employee_code: str
    full_name:     str
    department_id: int
    designation:   str
    user_id:       Optional[int] = None


class EmployeeResponse(BaseModel):
    id:            int
    employee_code: str
    full_name:     str
    department_id: int
    designation:   str
    user_id:       Optional[int] = None
    is_active:     bool

    model_config = ConfigDict(from_attributes=True)


# =========================================================
# USER
# =========================================================

class UserCreate(BaseModel):
    username:      str
    password:      str
    full_name:     str
    role:          UserRole
    department_id: Optional[int] = None
    employee_id:   Optional[int] = None


class UserResponse(BaseModel):
    id:            int
    username:      str
    full_name:     str
    role:          UserRole
    department_id: Optional[int] = None
    employee_id:   Optional[int] = None
    is_active:     bool
    created_at:    datetime
    updated_at:    datetime

    model_config = ConfigDict(from_attributes=True)


# =========================================================
# AUTH / LOGIN
# =========================================================

class LoginRequest(BaseModel):
    username: str
    password: str


class TokenData(BaseModel):
    user_id:  int
    username: str
    role:     UserRole


class LoginResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    user:         UserResponse


# =========================================================
# INCOMING MESSAGES (Mail Intake)
# =========================================================

class IntakeCreate(BaseModel):
    source_type:         SourceType = SourceType.OUTLOOK
    external_message_id: Optional[str] = None
    sender_name:         Optional[str] = None
    sender_email:        Optional[str] = None
    subject:             Optional[str] = None
    received_at:         Optional[datetime] = None
    body_reference:      Optional[str] = None


class IntakeProcessRequest(BaseModel):
    title:               Optional[str] = None
    deadline:            Optional[date] = None
    priority:            Priority = Priority.MEDIUM


class IntakeResponse(BaseModel):
    id:                  int
    source_type:         SourceType
    external_message_id: Optional[str] = None
    sender_name:         Optional[str] = None
    sender_email:        Optional[str] = None
    subject:             Optional[str] = None
    received_at:         datetime
    body_reference:      Optional[str] = None
    has_attachments:     bool
    processing_status:   MessageProcessingStatus
    created_at:          datetime

    model_config = ConfigDict(from_attributes=True)


# =========================================================
# DOCUMENT
# =========================================================

class DocumentCreate(BaseModel):
    title:               str
    description:         Optional[str] = None
    received_date:       date
    deadline:            Optional[date] = None
    source:              Optional[str] = None
    mode:                str = "Manual Upload"
    priority:            Priority = Priority.MEDIUM
    source_message_id:   Optional[int] = None


class DocumentResponse(BaseModel):
    doc_id:              int
    reference_no:        str
    title:               str
    description:         Optional[str] = None
    received_date:       date
    deadline:            Optional[date] = None
    source:              Optional[str] = None
    mode:                str
    priority:            Priority
    status:              DocumentStatus
    current_stage:       WorkflowStage
    current_owner_id:    Optional[int] = None
    target_department_id: Optional[int] = None
    created_by:          int
    source_message_id:   Optional[int] = None
    ocr_status:          OCRStatus
    version:             int
    director_remark:     Optional[str] = None
    hod_remark:          Optional[str] = None
    created_at:          datetime
    updated_at:          datetime
    closed_at:           Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class DocumentListResponse(BaseModel):
    doc_id:        int
    reference_no:  str
    title:         str
    priority:      Priority
    status:        DocumentStatus
    current_stage: WorkflowStage
    ocr_status:    OCRStatus
    version:       int
    received_date: date
    deadline:      Optional[date] = None
    created_at:    datetime
    updated_at:    datetime

    model_config = ConfigDict(from_attributes=True)


# =========================================================
# DOCUMENT ROUTING (DS -> Director / HOD / Employee)
# =========================================================

class RouteRequest(BaseModel):
    route_type:       RouteType
    to_user_id:       Optional[int] = None
    to_department_id: Optional[int] = None
    remarks:          Optional[str] = None
    expected_version: Optional[int] = None  # Optimistic concurrency check


# =========================================================
# DIRECTOR REMARK
# =========================================================

class DirectorRemarkUpdate(BaseModel):
    director_remark:  str
    expected_version: Optional[int] = None


class ReturnToDSRequest(BaseModel):
    remarks:          Optional[str] = None
    expected_version: Optional[int] = None


# =========================================================
# HOD REMARK & ASSIGNMENT
# =========================================================

class HODRemarkUpdate(BaseModel):
    hod_remark:       str
    expected_version: Optional[int] = None


class AssignmentRequest(BaseModel):
    assigned_to_user_id: int
    instructions:        Optional[str] = None
    expected_version:    Optional[int] = None


class AssignmentResponse(BaseModel):
    id:                  int
    document_id:         int
    assigned_by_user_id: int
    assigned_to_user_id: int
    instructions:        Optional[str] = None
    is_active:           bool
    assigned_at:         datetime
    completed_at:        Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# =========================================================
# DOCUMENT REMARKS (History)
# =========================================================

class DocumentRemarkResponse(BaseModel):
    id:             int
    document_id:    int
    author_user_id: int
    role:           UserRole
    remark_text:    str
    remark_type:    RemarkType
    created_at:     datetime
    updated_at:     datetime

    model_config = ConfigDict(from_attributes=True)


# =========================================================
# PROGRESS UPDATES (Employee)
# =========================================================

class ProgressCreate(BaseModel):
    description: str


class ProgressResponse(BaseModel):
    id:                   int
    document_id:          int
    submitted_by_user_id: int
    description:          str
    created_at:           datetime

    model_config = ConfigDict(from_attributes=True)


# =========================================================
# FOLLOW-UP & CLOSURE
# =========================================================

class FollowUpRequest(BaseModel):
    remarks:          Optional[str] = None
    expected_version: Optional[int] = None


class CloseRequest(BaseModel):
    remarks:          Optional[str] = None
    expected_version: Optional[int] = None


# =========================================================
# ATTACHMENTS
# =========================================================

class AttachmentResponse(BaseModel):
    id:                  int
    document_id:         int
    progress_update_id:  Optional[int] = None
    uploaded_by_user_id: int
    file_name:           str
    file_type:           Optional[str] = None
    file_size:           Optional[int] = None
    checksum:            Optional[str] = None
    attachment_type:     AttachmentType
    source_message_id:   Optional[int] = None
    created_at:          datetime

    model_config = ConfigDict(from_attributes=True)


# =========================================================
# OCR & EXTRACTED FIELDS
# =========================================================

class ExtractedFieldResponse(BaseModel):
    id:              int
    document_id:     int
    field_name:      str
    extracted_value: Optional[str] = None
    confidence:      Optional[float] = None
    source_page:     Optional[int] = None
    source_text:     Optional[str] = None
    verified_value:  Optional[str] = None
    verified_by:     Optional[int] = None
    verified_at:     Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class FieldVerifyRequest(BaseModel):
    field_name:     str
    verified_value: str


class OCRResponse(BaseModel):
    id:               Optional[int] = None
    document_id:      int
    ocr_status:       OCRStatus
    ocr_engine:       Optional[str] = None
    confidence:       Optional[float] = None
    extracted_text:   Optional[str] = None
    processed_at:     Optional[datetime] = None
    error_message:    Optional[str] = None
    extracted_fields: List[ExtractedFieldResponse] = []

    model_config = ConfigDict(from_attributes=True)


# =========================================================
# ROUTING SUGGESTIONS
# =========================================================

class RoutingSuggestionResponse(BaseModel):
    id:                      Optional[int] = None
    document_id:             int
    suggested_department_id: Optional[int] = None
    suggested_department_name: Optional[str] = None
    suggested_employee_id:   Optional[int] = None
    suggested_employee_name: Optional[str] = None
    routing_confidence:      float
    routing_reason:          str
    routing_source:          RoutingSource
    is_director_instruction: bool
    generated_at:            datetime
    confirmed_by:            Optional[int] = None
    confirmed_at:            Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class RoutingAnalyzeRequest(BaseModel):
    include_director_remark: bool = True


# =========================================================
# REMINDERS
# =========================================================

class ReminderResponse(BaseModel):
    id:                int
    document_id:       int
    recipient_user_id: int
    reason:            ReminderReason
    due_at:            Optional[datetime] = None
    sent_at:           datetime
    is_read:           bool
    deduplication_key: str

    model_config = ConfigDict(from_attributes=True)


class ReminderCheckResponse(BaseModel):
    reminders_created: int
    reminders:         List[ReminderResponse]


# =========================================================
# WORKFLOW HISTORY
# =========================================================

class WorkflowHistoryResponse(BaseModel):
    id:                  int
    document_id:         int
    performed_by_user_id: int
    action:              str
    from_role:           Optional[str] = None
    to_role:             Optional[str] = None
    details:             Optional[str] = None
    created_at:          datetime

    model_config = ConfigDict(from_attributes=True)


# =========================================================
# NOTIFICATIONS
# =========================================================

class NotificationResponse(BaseModel):
    id:                int
    user_id:           int
    document_id:       Optional[int] = None
    workflow_event_id: Optional[int] = None
    title:             str
    message:           str
    is_read:           bool
    created_at:        datetime

    model_config = ConfigDict(from_attributes=True)


# =========================================================
# LIVE EVENTS
# =========================================================

class LiveEventMessage(BaseModel):
    event_type:  str
    document_id: Optional[int] = None
    user_id:     Optional[int] = None
    timestamp:   datetime = datetime.utcnow()
    payload:     Optional[dict] = None


# =========================================================
# DASHBOARD
# =========================================================

class DashboardResponse(BaseModel):
    role:                  str
    total_documents:       int
    pending_action:        int
    unread_notifications:  int
    unread_reminders:      int = 0
    # DS-specific
    under_director_review: Optional[int] = None
    under_hod_processing:  Optional[int] = None
    in_progress:           Optional[int] = None
    closed_documents:      Optional[int] = None
    intake_pending:        Optional[int] = None
    # Director-specific
    documents_for_review:  Optional[int] = None
    # HOD-specific
    pending_assignment:    Optional[int] = None
    # Employee-specific
    active_assignments:    Optional[int] = None
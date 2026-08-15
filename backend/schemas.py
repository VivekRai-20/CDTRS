from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import date, datetime

from models import UserRole, DocumentStatus, WorkflowStage, Priority, RouteType


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
# DOCUMENT
# =========================================================

class DocumentCreate(BaseModel):
    title:               str
    description:         Optional[str] = None
    received_date:       date
    deadline:            Optional[date] = None
    source:              Optional[str] = None
    mode:                str
    priority:            Priority = Priority.MEDIUM


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
    received_date: date
    deadline:      Optional[date] = None
    created_at:    datetime
    updated_at:    datetime

    model_config = ConfigDict(from_attributes=True)


# =========================================================
# DOCUMENT ROUTING  (DS → Director / HOD / Employee)
# =========================================================

class RouteRequest(BaseModel):
    route_type:      RouteType
    to_user_id:      Optional[int] = None    # specific user target
    to_department_id: Optional[int] = None   # department target
    remarks:         Optional[str] = None


# =========================================================
# DIRECTOR REMARK (save independently of return-to-ds)
# =========================================================

class DirectorRemarkUpdate(BaseModel):
    director_remark: str


# =========================================================
# DIRECTOR — RETURN TO DS
# =========================================================

class ReturnToDSRequest(BaseModel):
    remarks: Optional[str] = None


# =========================================================
# HOD REMARK (save independently of assignment)
# =========================================================

class HODRemarkUpdate(BaseModel):
    hod_remark: str


# =========================================================
# WORK ASSIGNMENT  (HOD → Employee)
# =========================================================

class AssignmentRequest(BaseModel):
    assigned_to_user_id: int
    instructions:        Optional[str] = None


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
# PROGRESS UPDATES  (Employee — free-text, multiple)
# =========================================================

class ProgressCreate(BaseModel):
    description: str


class ProgressResponse(BaseModel):
    id:                  int
    document_id:         int
    submitted_by_user_id: int
    description:         str
    created_at:          datetime

    model_config = ConfigDict(from_attributes=True)


# =========================================================
# FOLLOW-UP (DS → Director)
# =========================================================

class FollowUpRequest(BaseModel):
    remarks: Optional[str] = None


# =========================================================
# CLOSE DOCUMENT (DS)
# =========================================================

class CloseRequest(BaseModel):
    remarks: Optional[str] = None


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
    created_at:          datetime

    model_config = ConfigDict(from_attributes=True)


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
# DASHBOARD
# =========================================================

class DashboardResponse(BaseModel):
    role:                    str
    total_documents:         int
    pending_action:          int
    unread_notifications:    int
    # DS-specific
    under_director_review:   Optional[int] = None
    under_hod_processing:    Optional[int] = None
    in_progress:             Optional[int] = None
    closed_documents:        Optional[int] = None
    # Director-specific
    documents_for_review:    Optional[int] = None
    # HOD-specific
    pending_assignment:      Optional[int] = None
    # Employee-specific
    active_assignments:      Optional[int] = None
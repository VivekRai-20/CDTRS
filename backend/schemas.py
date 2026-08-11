from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import date, datetime


# =========================================================
# DEPARTMENT
# =========================================================

class DepartmentCreate(BaseModel):

    d_name: str


class DepartmentResponse(BaseModel):

    d_id: int
    d_name: str
    is_active: bool

    model_config = ConfigDict(
        from_attributes=True
    )


# =========================================================
# EMPLOYEE
# =========================================================

class EmployeeCreate(BaseModel):

    name: str
    designation: str
    d_id: int


class EmployeeResponse(BaseModel):

    e_id: int
    name: str
    designation: str
    d_id: int

    model_config = ConfigDict(
        from_attributes=True
    )


# =========================================================
# USER
# =========================================================

class UserCreate(BaseModel):

    username: str
    full_name: str
    email: Optional[str] = None
    password: str
    role: str


class UserResponse(BaseModel):

    id: int
    username: str
    full_name: str
    email: Optional[str] = None
    role: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )


# =========================================================
# LOGIN
# =========================================================

class LoginRequest(BaseModel):

    username: str
    password: str


class LoginResponse(BaseModel):

    id: int
    username: str
    full_name: str
    role: str


# =========================================================
# DOCUMENT
# =========================================================

class DocumentCreate(BaseModel):

    date: date
    mode: str
    title: str
    source: Optional[str] = None

    suggested_department_id: Optional[int] = None

    action: Optional[str] = None
    remarks: Optional[str] = None

    status: str = "New"

    deadline: Optional[date] = None

    priority: str = "Green"

    file_path: Optional[str] = None

    assigned_employee_id: Optional[int] = None

    created_by: Optional[int] = None


class DocumentResponse(BaseModel):

    doc_id: int

    date: date
    mode: str
    title: str
    source: Optional[str] = None

    suggested_department_id: Optional[int] = None

    action: Optional[str] = None
    remarks: Optional[str] = None

    status: str

    deadline: Optional[date] = None

    priority: str

    file_path: Optional[str] = None

    assigned_employee_id: Optional[int] = None

    created_by: Optional[int] = None

    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )


# =========================================================
# DOCUMENT STATUS
# =========================================================

class DocumentStatusUpdate(BaseModel):

    status: str


# =========================================================
# WORKFLOW
# =========================================================

class WorkflowCreate(BaseModel):

    document_id: int

    action: str

    from_role: Optional[str] = None

    to_role: Optional[str] = None

    remarks: Optional[str] = None

    performed_by: int


class WorkflowResponse(BaseModel):

    id: int

    document_id: int

    action: str

    from_role: Optional[str] = None

    to_role: Optional[str] = None

    remarks: Optional[str] = None

    performed_by: int

    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )
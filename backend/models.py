from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Date,
    DateTime,
    Boolean,
    ForeignKey
)

from sqlalchemy.orm import relationship
from datetime import datetime

from database import Base


# =========================================================
# DEPARTMENT
# =========================================================

class Department(Base):

    __tablename__ = "departments"

    d_id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    d_name = Column(
        String(100),
        unique=True,
        nullable=False
    )

    is_active = Column(
        Boolean,
        default=True
    )

    # One department → many employees
    employees = relationship(
        "Employee",
        back_populates="department"
    )


# =========================================================
# EMPLOYEE
# =========================================================

class Employee(Base):

    __tablename__ = "employees"

    e_id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    name = Column(
        String(100),
        nullable=False
    )

    designation = Column(
        String(100),
        nullable=False
    )

    d_id = Column(
        Integer,
        ForeignKey("departments.d_id"),
        nullable=False
    )

    # Relationship
    department = relationship(
        "Department",
        back_populates="employees"
    )


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

    full_name = Column(
        String(100),
        nullable=False
    )

    email = Column(
        String(150),
        unique=True,
        nullable=True
    )

    password_hash = Column(
        String(255),
        nullable=False
    )

    role = Column(
        String(30),
        nullable=False
    )

    is_active = Column(
        Boolean,
        default=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )


# =========================================================
# MAIN DOCUMENT TABLE
# =========================================================

class Document(Base):

    __tablename__ = "documents"

    # Doc-id
    doc_id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    # Date
    date = Column(
        Date,
        nullable=False
    )

    # Mode
    # Example: Email, Fax, Intranet, Physical/Scan
    mode = Column(
        String(50),
        nullable=False
    )

    # Title
    title = Column(
        String(255),
        nullable=False
    )

    # Source - from where the document came
    source = Column(
        String(255),
        nullable=True
    )

    # Department suggested by OCR
    suggested_department_id = Column(
        Integer,
        ForeignKey("departments.d_id"),
        nullable=True
    )

    # Final action
    action = Column(
        Text,
        nullable=True
    )

    # Remarks
    remarks = Column(
        Text,
        nullable=True
    )

    # Current status
    status = Column(
        String(50),
        default="New",
        nullable=False
    )

    # Deadline
    deadline = Column(
        Date,
        nullable=True
    )

    # Priority
    priority = Column(
        String(20),
        default="Green",
        nullable=False
    )

    # Original document location
    file_path = Column(
        String(500),
        nullable=True
    )

    # Employee currently responsible
    assigned_employee_id = Column(
        Integer,
        ForeignKey("employees.e_id"),
        nullable=True
    )

    # User who entered the document
    created_by = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )


# =========================================================
# WORKFLOW HISTORY
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

    action = Column(
        String(100),
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

    remarks = Column(
        Text,
        nullable=True
    )

    performed_by = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )


# =========================================================
# AUDIT LOG
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
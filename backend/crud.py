from sqlalchemy.orm import Session
from datetime import datetime

import bcrypt

import models
import schemas


# =========================================================
# PASSWORD FUNCTIONS
# =========================================================

def hash_password(password: str) -> str:

    hashed = bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt()
    )

    return hashed.decode("utf-8")


def verify_password(
    password: str,
    password_hash: str
) -> bool:

    return bcrypt.checkpw(
        password.encode("utf-8"),
        password_hash.encode("utf-8")
    )


# =========================================================
# USER
# =========================================================

def create_user(
    db: Session,
    user: schemas.UserCreate
):

    hashed_password = hash_password(
        user.password
    )

    db_user = models.User(
        username=user.username,
        full_name=user.full_name,
        email=user.email,
        password_hash=hashed_password,
        role=user.role
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return db_user


def get_user_by_username(
    db: Session,
    username: str
):

    return (
        db.query(models.User)
        .filter(
            models.User.username == username
        )
        .first()
    )


def authenticate_user(
    db: Session,
    username: str,
    password: str
):

    user = get_user_by_username(
        db,
        username
    )

    if not user:
        return None

    if not verify_password(
        password,
        user.password_hash
    ):
        return None

    if not user.is_active:
        return None

    return user


def get_users(db: Session):

    return (
        db.query(models.User)
        .order_by(models.User.id)
        .all()
    )


# =========================================================
# DEPARTMENT
# =========================================================

def create_department(
    db: Session,
    department: schemas.DepartmentCreate
):

    db_department = models.Department(
        d_name=department.d_name
    )

    db.add(db_department)
    db.commit()
    db.refresh(db_department)

    return db_department


def get_departments(db: Session):

    return (
        db.query(models.Department)
        .filter(
            models.Department.is_active == True
        )
        .order_by(
            models.Department.d_name
        )
        .all()
    )


# =========================================================
# EMPLOYEE
# =========================================================

def create_employee(
    db: Session,
    employee: schemas.EmployeeCreate
):

    db_employee = models.Employee(
        name=employee.name,
        designation=employee.designation,
        d_id=employee.d_id
    )

    db.add(db_employee)
    db.commit()
    db.refresh(db_employee)

    return db_employee


def get_employees(db: Session):

    return (
        db.query(models.Employee)
        .order_by(models.Employee.name)
        .all()
    )


def get_employees_by_department(
    db: Session,
    department_id: int
):

    return (
        db.query(models.Employee)
        .filter(
            models.Employee.d_id == department_id
        )
        .order_by(models.Employee.name)
        .all()
    )


# =========================================================
# DOCUMENT
# =========================================================

def create_document(
    db: Session,
    document: schemas.DocumentCreate
):

    db_document = models.Document(
        date=document.date,
        mode=document.mode,
        title=document.title,
        source=document.source,
        suggested_department_id=(
            document.suggested_department_id
        ),
        action=document.action,
        remarks=document.remarks,
        status=document.status,
        deadline=document.deadline,
        priority=document.priority,
        file_path=document.file_path,
        assigned_employee_id=(
            document.assigned_employee_id
        ),
        created_by=document.created_by
    )

    db.add(db_document)
    db.commit()
    db.refresh(db_document)

    return db_document


def get_documents(db: Session):

    return (
        db.query(models.Document)
        .order_by(
            models.Document.created_at.desc()
        )
        .all()
    )


def get_document(
    db: Session,
    document_id: int
):

    return (
        db.query(models.Document)
        .filter(
            models.Document.doc_id == document_id
        )
        .first()
    )


def update_document_status(
    db: Session,
    document_id: int,
    status: str
):

    document = get_document(
        db,
        document_id
    )

    if not document:
        return None

    document.status = status

    db.commit()
    db.refresh(document)

    return document


# =========================================================
# WORKFLOW HISTORY
# =========================================================

def create_workflow_history(
    db: Session,
    workflow: schemas.WorkflowCreate
):

    db_history = models.WorkflowHistory(
        document_id=workflow.document_id,
        action=workflow.action,
        from_role=workflow.from_role,
        to_role=workflow.to_role,
        remarks=workflow.remarks,
        performed_by=workflow.performed_by
    )

    db.add(db_history)
    db.commit()
    db.refresh(db_history)

    return db_history


def get_document_history(
    db: Session,
    document_id: int
):

    return (
        db.query(models.WorkflowHistory)
        .filter(
            models.WorkflowHistory.document_id
            == document_id
        )
        .order_by(
            models.WorkflowHistory.created_at
        )
        .all()
    )


# =========================================================
# AUDIT LOG
# =========================================================

def create_audit_log(
    db: Session,
    user_id: int,
    action: str,
    entity_type: str = None,
    entity_id: int = None,
    description: str = None
):

    audit = models.AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        description=description
    )

    db.add(audit)
    db.commit()

    return audit
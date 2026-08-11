from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session

import models
import schemas
import crud

from database import engine, get_db


# =========================================================
# DATABASE TABLE CREATION
# =========================================================

models.Base.metadata.create_all(
    bind=engine
)


# =========================================================
# FASTAPI APPLICATION
# =========================================================

app = FastAPI(
    title="CDTRS Backend",
    description="Centralized Document Tracking and Routing System",
    version="1.0"
)


# =========================================================
# BASIC
# =========================================================

@app.get("/")
def root():

    return {
        "message": "CDTRS Backend is running"
    }


@app.get("/health")
def health_check():

    return {
        "status": "healthy"
    }


# =========================================================
# LOGIN
# =========================================================

@app.post(
    "/login",
    response_model=schemas.LoginResponse
)
def login(
    login_data: schemas.LoginRequest,
    db: Session = Depends(get_db)
):

    user = crud.authenticate_user(
        db,
        login_data.username,
        login_data.password
    )

    if not user:

        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )

    return user


# =========================================================
# USERS
# =========================================================

@app.post(
    "/users",
    response_model=schemas.UserResponse
)
def create_user(
    user: schemas.UserCreate,
    db: Session = Depends(get_db)
):

    existing_user = crud.get_user_by_username(
        db,
        user.username
    )

    if existing_user:

        raise HTTPException(
            status_code=400,
            detail="Username already exists"
        )

    return crud.create_user(
        db,
        user
    )


@app.get(
    "/users",
    response_model=list[schemas.UserResponse]
)
def get_users(
    db: Session = Depends(get_db)
):

    return crud.get_users(db)


# =========================================================
# DEPARTMENTS
# =========================================================

@app.post(
    "/departments",
    response_model=schemas.DepartmentResponse
)
def create_department(
    department: schemas.DepartmentCreate,
    db: Session = Depends(get_db)
):

    return crud.create_department(
        db,
        department
    )


@app.get(
    "/departments",
    response_model=list[schemas.DepartmentResponse]
)
def get_departments(
    db: Session = Depends(get_db)
):

    return crud.get_departments(db)


# =========================================================
# EMPLOYEES
# =========================================================

@app.post(
    "/employees",
    response_model=schemas.EmployeeResponse
)
def create_employee(
    employee: schemas.EmployeeCreate,
    db: Session = Depends(get_db)
):

    department = (
        db.query(models.Department)
        .filter(
            models.Department.d_id
            == employee.d_id
        )
        .first()
    )

    if not department:

        raise HTTPException(
            status_code=404,
            detail="Department not found"
        )

    return crud.create_employee(
        db,
        employee
    )


@app.get(
    "/employees",
    response_model=list[schemas.EmployeeResponse]
)
def get_employees(
    db: Session = Depends(get_db)
):

    return crud.get_employees(db)


@app.get(
    "/departments/{department_id}/employees",
    response_model=list[schemas.EmployeeResponse]
)
def get_department_employees(
    department_id: int,
    db: Session = Depends(get_db)
):

    return crud.get_employees_by_department(
        db,
        department_id
    )


# =========================================================
# DOCUMENTS
# =========================================================

@app.post(
    "/documents",
    response_model=schemas.DocumentResponse
)
def create_document(
    document: schemas.DocumentCreate,
    db: Session = Depends(get_db)
):

    return crud.create_document(
        db,
        document
    )


@app.get(
    "/documents",
    response_model=list[schemas.DocumentResponse]
)
def get_documents(
    db: Session = Depends(get_db)
):

    return crud.get_documents(db)


@app.get(
    "/documents/{document_id}",
    response_model=schemas.DocumentResponse
)
def get_document(
    document_id: int,
    db: Session = Depends(get_db)
):

    document = crud.get_document(
        db,
        document_id
    )

    if not document:

        raise HTTPException(
            status_code=404,
            detail="Document not found"
        )

    return document


@app.patch(
    "/documents/{document_id}/status",
    response_model=schemas.DocumentResponse
)
def update_document_status(
    document_id: int,
    status_data: schemas.DocumentStatusUpdate,
    db: Session = Depends(get_db)
):

    document = crud.update_document_status(
        db,
        document_id,
        status_data.status
    )

    if not document:

        raise HTTPException(
            status_code=404,
            detail="Document not found"
        )

    return document


# =========================================================
# WORKFLOW
# =========================================================

@app.post(
    "/workflow",
    response_model=schemas.WorkflowResponse
)
def create_workflow(
    workflow: schemas.WorkflowCreate,
    db: Session = Depends(get_db)
):

    return crud.create_workflow_history(
        db,
        workflow
    )


@app.get(
    "/documents/{document_id}/history",
    response_model=list[schemas.WorkflowResponse]
)
def get_document_history(
    document_id: int,
    db: Session = Depends(get_db)
):

    return crud.get_document_history(
        db,
        document_id
    )
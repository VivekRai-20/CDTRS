# CDTRS Backend

Backend for the **Centralized Document Tracking and Routing System (CDTRS)**.

This is the initial/basic backend implementation. It is intentionally kept simple so that additional features can be added later as the project develops.

---

# 1. Current Backend Structure

```text
backend/
│
├── database.py
├── models.py
├── schemas.py
├── crud.py
├── main.py
└── README.md
```

Each file has one primary responsibility.

```text
database.py
     ↓
PostgreSQL Connection
     ↓
models.py
     ↓
Database Tables
     ↓
crud.py
     ↓
Database Operations
     ↓
schemas.py
     ↓
Request / Response Validation
     ↓
main.py
     ↓
FastAPI Endpoints
```

---

# 2. Technologies Used

The current backend uses:

- **Python** – Backend programming language
- **FastAPI** – REST API framework
- **SQLAlchemy** – ORM for PostgreSQL
- **PostgreSQL** – Database
- **Pydantic** – Request and response validation
- **Uvicorn** – Development server
- **bcrypt** – Password hashing

---

# 3. Database Design

The current basic database consists of the following tables:

```text
Department
Employee
User
Document
WorkflowHistory
AuditLog
```

The main relationship is:

```text
Department
    │
    │ One Department
    │
    ▼
Employee
    │
    │ Employee can be assigned to
    │
    ▼
Document
```

The document can also be associated with:

- A suggested department
- An assigned employee
- The user who created the document
- Workflow history
- Audit logs

---

# 4. Department Table

The `departments` table stores department information.

Current fields:

```text
d_id
d_name
is_active
```

### Example

```text
D-id     D-name
-------------------------
1        Administration
2        Finance
3        HR
4        Technical
```

One department can have multiple employees.

---

# 5. Employee Table

The `employees` table stores employee information.

Current fields:

```text
e_id
name
designation
d_id
```

The `d_id` connects the employee to a department.

Relationship:

```text
Department
    │
    ├── Employee 1
    ├── Employee 2
    ├── Employee 3
    └── Employee 4
```

Example:

```text
E-id     Name          Designation        D-id
------------------------------------------------
1        John Doe      Manager            1
2        Jane Smith    Engineer           4
```

---

# 6. User Table

The `users` table is used for basic application users and login.

Current fields:

```text
id
username
full_name
email
password_hash
role
is_active
created_at
```

Passwords are not stored directly.

The backend uses `bcrypt` to convert passwords into password hashes before storing them.

Current flow:

```text
User Password
      ↓
bcrypt Hashing
      ↓
password_hash stored in database
```

---

# 7. Main Document Table

The main table of the system is the `documents` table.

It follows the basic document structure currently defined for CDTRS.

Current fields:

```text
doc_id
date
mode
title
source
suggested_department_id
action
remarks
status
deadline
priority
file_path
assigned_employee_id
created_by
created_at
```

---

## Document Field Explanation

| Field | Description |
|---|---|
| `doc_id` | Unique document ID |
| `date` | Date of the document |
| `mode` | Mode through which the document was received |
| `title` | Title of the document |
| `source` | From where the document came |
| `suggested_department_id` | Department suggested for the document |
| `action` | Action to be taken |
| `remarks` | Additional remarks |
| `status` | Current status of the document |
| `deadline` | Deadline associated with the document |
| `priority` | Priority of the document |
| `file_path` | Location of the original document |
| `assigned_employee_id` | Employee currently handling the document |
| `created_by` | User who entered the document |
| `created_at` | Time when the document record was created |

The basic structure is:

```text
Document
│
├── Doc ID
├── Date
├── Mode
├── Title
├── Source
├── Suggested Department
├── Action
├── Remarks
├── Status
├── Deadline
├── Priority
├── File Path
├── Assigned Employee
├── Created By
└── Created At
```

---

# 8. Suggested Department

The current backend stores:

```text
suggested_department_id
```

instead of storing the department name directly.

The relationship is:

```text
Document
     │
     │ suggested_department_id
     ▼
Department
     │
     ├── d_id
     └── d_name
```

For example:

```text
Document
    suggested_department_id = 3
                ↓
Department
    d_id = 3
    d_name = Technical
```

This structure will be useful later when OCR-based department suggestions are implemented.

**OCR functionality is not implemented yet.**

---

# 9. Assigned Employee

The document contains:

```text
assigned_employee_id
```

This represents the employee currently responsible for handling the document.

The relationship is:

```text
Document
    │
    │ assigned_employee_id
    ▼
Employee
    │
    │ d_id
    ▼
Department
```

This makes it possible to determine:

- Which employee is handling a document
- Which department the employee belongs to

---

# 10. Workflow History

The `workflow_history` table stores basic actions performed on documents.

Current fields:

```text
id
document_id
action
from_role
to_role
remarks
performed_by
created_at
```

Example workflow history:

```text
Document Created
       ↓
Forwarded
       ↓
Reviewed
       ↓
Assigned
       ↓
Completed
```

The backend currently stores workflow history.

Complete workflow rules and automatic routing are not implemented yet.

---

# 11. Audit Log

The `audit_logs` table provides a basic structure for recording important system activities.

Current fields:

```text
id
user_id
action
entity_type
entity_id
description
created_at
```

The audit log structure is currently available.

Automatic logging for every system action will be expanded later.

---

# 12. `database.py`

### Purpose

`database.py` handles the connection between the backend and PostgreSQL.

It currently contains:

- PostgreSQL database URL
- SQLAlchemy engine
- Database session
- SQLAlchemy `Base`
- `get_db()` dependency for FastAPI

### Flow

```text
FastAPI Request
      ↓
get_db()
      ↓
SQLAlchemy Session
      ↓
PostgreSQL
```

The database URL is configured in this file:

```python
DATABASE_URL = "postgresql+psycopg2://postgres:your_password@localhost:5432/cdtrs"
```

Replace:

```text
your_password
```

with your PostgreSQL password.

---

# 13. `models.py`

### Purpose

`models.py` defines the PostgreSQL database tables using SQLAlchemy.

Currently, the following models are created:

```text
Department
Employee
User
Document
WorkflowHistory
AuditLog
```

These Python models are converted into PostgreSQL tables.

---

# 14. `schemas.py`

### Purpose

`schemas.py` contains the Pydantic schemas used for API requests and responses.

It separates API validation from database models.

For example:

```text
models.py
    ↓
Defines how data is stored in PostgreSQL

schemas.py
    ↓
Defines how data is received and returned through the API
```

Current schemas include:

```text
DepartmentCreate
DepartmentResponse

EmployeeCreate
EmployeeResponse

UserCreate
UserResponse

LoginRequest
LoginResponse

DocumentCreate
DocumentResponse

DocumentStatusUpdate

WorkflowCreate
WorkflowResponse
```

---

# 15. `crud.py`

### Purpose

`crud.py` contains the actual database operations.

CRUD means:

```text
C → Create
R → Read
U → Update
D → Delete
```

The current CRUD operations are divided into the following sections.

---

## User Operations

Currently implemented:

```python
create_user()
get_user_by_username()
authenticate_user()
get_users()
```

These handle:

- Creating users
- Finding users
- Authenticating users
- Getting all users

Passwords are hashed using bcrypt before being stored.

---

## Department Operations

Currently implemented:

```python
create_department()
get_departments()
```

These handle:

- Creating departments
- Retrieving active departments

---

## Employee Operations

Currently implemented:

```python
create_employee()
get_employees()
get_employees_by_department()
```

These handle:

- Creating employees
- Getting all employees
- Getting employees belonging to a specific department

---

## Document Operations

Currently implemented:

```python
create_document()
get_documents()
get_document()
update_document_status()
```

These handle:

- Creating a document record
- Getting all documents
- Getting one document
- Updating document status

At this stage, the backend stores document information and an optional file path.

Actual file upload functionality will be added later.

---

## Workflow Operations

Currently implemented:

```python
create_workflow_history()
get_document_history()
```

These handle:

- Recording workflow actions
- Retrieving the history of a document

---

## Audit Operations

Currently implemented:

```python
create_audit_log()
```

This provides the basic function for creating audit log records.

---

# 16. `main.py`

### Purpose

`main.py` is the entry point of the FastAPI application.

It currently:

- Creates the FastAPI application
- Creates database tables during initial development
- Defines API routes
- Receives requests
- Validates requests
- Calls CRUD functions
- Returns API responses

---

# 17. Current API Endpoints

## Basic

```text
GET /
GET /health
```

### `/`

Checks whether the backend is running.

Response:

```json
{
    "message": "CDTRS Backend is running"
}
```

### `/health`

Basic health check.

Response:

```json
{
    "status": "healthy"
}
```

---

# 18. Authentication

### Login

```text
POST /login
```

Example request:

```json
{
    "username": "admin",
    "password": "password"
}
```

The backend:

```text
Login Request
     ↓
Find User
     ↓
Check Password
     ↓
Check Active Status
     ↓
Return User Information
```

Passwords are verified against the stored bcrypt hash.

---

# 19. User API

### Create User

```text
POST /users
```

### Get Users

```text
GET /users
```

The current user API provides the basic foundation for user and role management.

Advanced role-based authorization will be added later.

---

# 20. Department API

### Create Department

```text
POST /departments
```

Example:

```json
{
    "d_name": "Technical"
}
```

### Get Departments

```text
GET /departments
```

---

# 21. Employee API

### Create Employee

```text
POST /employees
```

Example:

```json
{
    "name": "John Doe",
    "designation": "Manager",
    "d_id": 1
}
```

### Get All Employees

```text
GET /employees
```

### Get Employees by Department

```text
GET /departments/{department_id}/employees
```

---

# 22. Document API

### Create Document

```text
POST /documents
```

Example request:

```json
{
    "date": "2026-08-11",
    "mode": "Email",
    "title": "Document Title",
    "source": "Official Email",
    "suggested_department_id": 2,
    "action": "Review document",
    "remarks": "Urgent document",
    "status": "New",
    "deadline": "2026-08-15",
    "priority": "High",
    "file_path": null,
    "assigned_employee_id": null,
    "created_by": 1
}
```

### Get All Documents

```text
GET /documents
```

### Get One Document

```text
GET /documents/{document_id}
```

### Update Document Status

```text
PATCH /documents/{document_id}/status
```

Example:

```json
{
    "status": "In Progress"
}
```

---

# 23. Workflow API

### Create Workflow History

```text
POST /workflow
```

### Get Document History

```text
GET /documents/{document_id}/history
```

---

# 24. Current Backend Flow

For example, when creating a document:

```text
Frontend
   │
   │ POST /documents
   ▼
main.py
   │
   │ Validate request
   ▼
schemas.py
   │
   ▼
crud.py
   │
   │ Create database object
   ▼
models.py
   │
   ▼
database.py
   │
   ▼
PostgreSQL
```

The response then returns back through the API to the frontend.

---

# 25. How to Run the Backend

## Step 1 — Create PostgreSQL Database

Create a PostgreSQL database named:

```text
cdtrs
```

---

## Step 2 — Install Dependencies

```bash
pip install fastapi uvicorn sqlalchemy psycopg2-binary pydantic bcrypt
```

---

## Step 3 — Configure PostgreSQL

Open:

```text
database.py
```

Update:

```python
DATABASE_URL = "postgresql+psycopg2://postgres:your_password@localhost:5432/cdtrs"
```

with your PostgreSQL password.

---

## Step 4 — Start the Server

From the `backend` directory:

```bash
uvicorn main:app --reload
```

The backend will run at:

```text
http://127.0.0.1:8000
```

---

# 26. API Testing

FastAPI automatically provides Swagger documentation.

Open:

```text
http://127.0.0.1:8000/docs
```

From there, all currently implemented API endpoints can be tested without connecting the frontend.

The recommended testing order is:

```text
1. Health Check
       ↓
2. Create Department
       ↓
3. Create Employee
       ↓
4. Create User
       ↓
5. Login
       ↓
6. Create Document
       ↓
7. Get Documents
       ↓
8. Update Document Status
       ↓
9. Add Workflow History
       ↓
10. View Workflow History
```

---

# 27. What Is Currently Implemented

| Feature | Status |
|---|---|
| FastAPI setup | ✅ Done |
| PostgreSQL connection | ✅ Done |
| SQLAlchemy setup | ✅ Done |
| Department model | ✅ Done |
| Employee model | ✅ Done |
| User model | ✅ Done |
| Document model | ✅ Done |
| Workflow History model | ✅ Basic |
| Audit Log model | ✅ Basic |
| Pydantic schemas | ✅ Done |
| CRUD layer | ✅ Basic |
| User creation | ✅ Done |
| User retrieval | ✅ Done |
| Password hashing | ✅ Done |
| Basic login | ✅ Done |
| Department creation | ✅ Done |
| Department retrieval | ✅ Done |
| Employee creation | ✅ Done |
| Employee retrieval | ✅ Done |
| Document creation | ✅ Basic |
| Document retrieval | ✅ Basic |
| Document status update | ✅ Done |
| Workflow history | ✅ Basic |
| Frontend integration | ⏳ Later |
| File upload | ⏳ Later |
| OCR | ⏳ Later |
| Automatic department suggestion | ⏳ Later |
| Automatic routing | ⏳ Later |
| Advanced RBAC | ⏳ Later |
| Deadline reminders | ⏳ Later |
| Email/Fax/Intranet integration | ⏳ Later |

---

# 28. Current Limitations

This is the initial backend, so several features are intentionally not implemented yet.

### Authentication

The current backend provides basic username/password authentication.

Full JWT or session-based authentication will be added later if required.

### Authorization

Roles are stored with users, but complete role-based permission enforcement is not implemented yet.

### Documents

The backend currently creates and manages document database records.

Actual document file upload and processing are not implemented yet.

### OCR

No OCR processing is currently included.

The `suggested_department_id` field is only prepared for future OCR or routing functionality.

### Automatic Routing

The backend does not automatically route documents yet.

### Workflow

Workflow history can be recorded, but complete workflow rules are not enforced yet.

### Audit Logging

The audit log structure exists, but automatic logging of every important action has not yet been connected to all endpoints.

---

# 29. Planned Development

The backend will be expanded gradually.

```text
Current Basic Backend
        │
        ▼
Connect Frontend
        │
        ▼
Document File Upload
        │
        ▼
Document Processing
        │
        ▼
OCR
        │
        ▼
Department Suggestion
        │
        ▼
Employee Assignment
        │
        ▼
Workflow Implementation
        │
        ▼
Deadline and Priority Management
        │
        ▼
Reminders and Notifications
        │
        ▼
Advanced Authentication and RBAC
        │
        ▼
Audit and Reporting
```

The current five-file structure is the foundation of the backend.

As the project becomes larger, additional modules can be introduced when required.

---

# 30. Important Development Note

During the current initial development stage:

```python
Base.metadata.create_all(bind=engine)
```

is used to create database tables.

If the SQLAlchemy models are changed after the tables already exist, `create_all()` will not automatically modify the existing database tables.

Since the project is still in the early development stage, the database can be recreated if major model changes are made and no important data exists.

Once the database structure becomes stable, **Alembic migrations** should be introduced for proper database schema changes.

---

# 31. Important

This README describes the **current basic backend only**.

It does not claim that all CDTRS features have already been implemented.

The following major features are planned for future development:

- Document file upload
- OCR
- Automatic department suggestion
- Automatic routing
- Advanced workflow rules
- Role-based access control
- Deadline reminders
- Email integration
- Fax integration
- Intranet integration
- Advanced audit and reporting

The backend is being developed incrementally, and the database models, APIs, and folder structure may change as new features are implemented.

---

## Current Backend Philosophy

```text
Keep the backend simple
        ↓
Build the basic database structure
        ↓
Test the APIs
        ↓
Connect the frontend
        ↓
Add features one by one
        ↓
Refactor when required
```

The current implementation is the **foundation of the CDTRS backend**, not the final implementation of the complete system.
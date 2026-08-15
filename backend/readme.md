# CDTRS V2 — Backend

**Centralized Document Tracking and Routing System — Version 2**

This is the complete backend implementation for CDTRS V2. It is built with Python and FastAPI, stores data in PostgreSQL, enforces role-based access control, issues JWT bearer tokens for authentication, supports file uploads, sends in-app notifications, and exposes a full REST API for the PySide6 frontend to consume.

---

# 1. Current Backend Structure

```text
backend/
│
├── database.py        ← PostgreSQL connection and session management
├── models.py          ← All database table definitions (SQLAlchemy ORM)
├── schemas.py         ← All request and response data shapes (Pydantic)
├── crud.py            ← All database operations and workflow business logic
├── main.py            ← FastAPI application, all API routes, middleware
│
├── requirements.txt   ← Python package dependencies
├── .env.example       ← Environment variable template (copy to .env)
└── README.md          ← This file
```

Each file has exactly one responsibility.

```text
database.py
     ↓  Establishes the connection to PostgreSQL
models.py
     ↓  Defines what the database tables look like
crud.py
     ↓  Contains all logic that reads/writes the database
schemas.py
     ↓  Validates what comes into and goes out of the API
main.py
     ↓  Wires everything together into HTTP endpoints
```

---

# 2. Technologies Used

| Package | Purpose |
|---|---|
| **Python 3.10+** | Backend programming language |
| **FastAPI** | REST API framework. Automatically generates Swagger docs. |
| **Uvicorn** | ASGI server that runs FastAPI in development and production |
| **SQLAlchemy 2.x** | ORM — maps Python classes to PostgreSQL tables |
| **PostgreSQL 14–16** | Relational database |
| **Pydantic v2** | Validates the shape of data coming in and out of the API |
| **passlib[bcrypt]** | Securely hashes passwords using the bcrypt algorithm |
| **python-jose[cryptography]** | Creates and verifies JWT (JSON Web Token) bearer tokens |
| **python-multipart** | Enables multipart/form-data file uploads in FastAPI |
| **python-dotenv** | Loads environment variables from a `.env` file |

---

# 3. Installation and Setup

### Step 1 — Prerequisites

Before starting, make sure you have:

- Python 3.10 or higher installed
- PostgreSQL 14, 15, or 16 installed and running
- `pip` available

### Step 2 — Install Python dependencies

Open a terminal, navigate to the backend directory, and run:

```bash
pip install -r requirements.txt
```

This installs all packages listed in `requirements.txt`.

### Step 3 — Create the PostgreSQL database

Open psql or pgAdmin and run:

```sql
CREATE DATABASE cdtrs;
```

You do not need to create any tables manually. SQLAlchemy creates all tables automatically when the server first starts.

### Step 4 — Configure the environment

Copy the example environment file:

```bash
copy .env.example .env
```

Open `.env` and set your PostgreSQL password:

```text
DATABASE_URL=postgresql+psycopg2://postgres:YOUR_PASSWORD_HERE@localhost:5432/cdtrs
```

The other variables have sensible defaults for development but should be changed for production.

### Step 5 — Start the server

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The `--reload` flag restarts the server automatically when you save a file. This is for development only.

### Step 6 — Seed test accounts (optional but recommended)

To create the four test users automatically on startup:

```bash
# Windows
set SEED_DB=true
uvicorn main:app --reload

# Or inline
SEED_DB=true uvicorn main:app --reload
```

After first startup you can set `SEED_DB=false` again. The seed function skips existing usernames so it is safe to run multiple times.

---

# 4. Verifying the Server is Running

After starting the server, open a browser and go to:

```
http://localhost:8000/
```

You should see:

```json
{
  "message": "CDTRS V2 Backend is running",
  "version": "2.0.0"
}
```

Go to the health check:

```
http://localhost:8000/health
```

Response:

```json
{
  "status": "healthy",
  "version": "2.0.0"
}
```

Open the interactive API documentation:

```
http://localhost:8000/docs
```

This is the Swagger UI. Every endpoint is listed here. You can test any endpoint directly from the browser by clicking it, filling in the values, and pressing Execute.

---

# 5. Environment Variables

These are the variables read from the `.env` file.

| Variable | Default | What It Does |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg2://postgres:your_password@localhost:5432/cdtrs` | Full PostgreSQL connection string. Change `your_password` to match your PostgreSQL password. |
| `SECRET_KEY` | `cdtrs-super-secret-key-change-in-production` | The key used to sign JWT tokens. If someone knows this key they can forge tokens. Change it to a long random string in production. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | How many minutes a login token stays valid. After this time the user must log in again. |
| `UPLOAD_DIR` | `./uploads` | The folder on the server where uploaded files are saved. |
| `SEED_DB` | `false` | Set to `true` to create test users and departments on startup. |

To generate a strong `SECRET_KEY`:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

# 6. Database Design

CDTRS V2 uses **11 database tables**. SQLAlchemy creates all of them automatically from the models defined in `models.py` when the server starts for the first time.

---

## 6.1 Enums (Controlled Values)

These Python enums are stored as string columns in PostgreSQL. They enforce that only valid values are saved.

### UserRole
```text
DS         →  Director Secretary
DIRECTOR   →  The Director
HOD        →  Head of Department
EMPLOYEE   →  Employee
```

### DocumentStatus (the user-facing status shown in the UI)
```text
RECEIVED                   →  Document registered by DS
UNDER_DIRECTOR_REVIEW      →  DS has sent it to the Director
DIRECTOR_REVIEW_COMPLETED  →  Director returned it to DS
UNDER_HOD_PROCESSING       →  DS has routed it to a HOD
ASSIGNED_FOR_EXECUTION     →  HOD has assigned an Employee
IN_PROGRESS                →  Employee has submitted progress
PROGRESS_UPDATED           →  Additional progress submitted
REVIEW_COMPLETED           →  Director completed a follow-up review
CLOSED                     →  DS has permanently closed the document
```

### WorkflowStage (internal — who currently holds the document)
```text
DS         →  With Director Secretary
DIRECTOR   →  With Director
HOD        →  With HOD
EMPLOYEE   →  With Employee
CLOSED     →  Document is closed
```

### Priority
```text
HIGH    →  Urgent
MEDIUM  →  Normal (default)
LOW     →  Low priority
```

### RouteType (the type of routing action DS performs)
```text
INITIAL_DIRECTOR_REVIEW   →  DS sends document to Director for first review
RETURN_TO_DS              →  Director returns document to DS
POST_REVIEW_TO_HOD        →  DS routes to a HOD after Director review
POST_REVIEW_TO_EMPLOYEE   →  DS routes directly to an Employee
FOLLOW_UP_TO_DIRECTOR     →  DS forwards employee progress to Director
```

---

## 6.2 `departments` Table

Stores the organization's departments.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer | Primary key, auto-incremented |
| `name` | String(100) | Department name, unique, required |
| `code` | String(20) | Short code like "FIN" or "HR", unique, optional |
| `is_active` | Boolean | Defaults to `true`. Inactive departments are hidden from lists. |
| `created_at` | DateTime | Set automatically when the record is created |

Relationships:
- One department → many users (`users.department_id`)
- One department → many employees (`employees.department_id`)

---

## 6.3 `employees` Table

Stores employee records. An employee record can optionally be linked to a user account.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer | Primary key |
| `employee_code` | String(50) | Unique code like "EMP-001" |
| `full_name` | String(100) | Employee's full name |
| `department_id` | Integer (FK) | Links to `departments.id` |
| `designation` | String(100) | Job title |
| `user_id` | Integer (FK) | Nullable. Links to `users.id` if the employee has a login account |
| `is_active` | Boolean | Defaults to `true` |

---

## 6.4 `users` Table

Stores login accounts. Every person who logs into the system has a user record.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer | Primary key |
| `username` | String(50) | Login username, unique |
| `password_hash` | String(255) | The password stored as a bcrypt hash. The plain password is never saved. |
| `full_name` | String(100) | Display name |
| `role` | Enum(UserRole) | One of DS / DIRECTOR / HOD / EMPLOYEE |
| `department_id` | Integer (FK) | Nullable. Which department this user belongs to |
| `employee_id` | Integer | Nullable. Reference to the employee record if applicable |
| `is_active` | Boolean | Defaults to `true`. Inactive users cannot log in. |
| `created_at` | DateTime | Set automatically on creation |
| `updated_at` | DateTime | Updated automatically on any change |

How password hashing works:

```text
User types "mypassword"
           ↓
bcrypt.hash("mypassword")
           ↓
"$2b$12$..." (stored in password_hash)
```

On login, bcrypt compares the typed password against the stored hash without ever reversing the hash. This means even if someone reads the database, they cannot recover the original passwords.

---

## 6.5 `documents` Table

The central table of the entire system. There is always **one canonical record per document** regardless of how many people handle it.

| Column | Type | Notes |
|---|---|---|
| `doc_id` | Integer | Primary key |
| `reference_no` | String(50) | Human-readable ID like `CDTRS-2026-0001`. Generated automatically. |
| `title` | String(255) | Document title |
| `description` | Text | Optional longer description |
| `received_date` | Date | The date the external document was physically received |
| `deadline` | Date | Nullable. The deadline for action |
| `source` | String(255) | Where the document came from (e.g. "Ministry of Finance") |
| `mode` | String(50) | How it was received: Email / Fax / Physical / Intranet |
| `priority` | Enum(Priority) | HIGH / MEDIUM / LOW. Defaults to MEDIUM |
| `status` | Enum(DocumentStatus) | The user-facing status. Defaults to RECEIVED. |
| `current_stage` | Enum(WorkflowStage) | Internal stage. Defaults to DS. |
| `current_owner_id` | Integer (FK) | Nullable. The user currently responsible for action. |
| `target_department_id` | Integer (FK) | Nullable. Set when DS routes to a HOD department. |
| `created_by` | Integer (FK) | The DS user who registered the document. Never changes. |
| `director_remark` | Text | Nullable. Latest Director remark. Saved in-place. |
| `hod_remark` | Text | Nullable. Latest HOD remark. Saved in-place. |
| `created_at` | DateTime | When DS registered the document |
| `updated_at` | DateTime | Updated automatically on any workflow action |
| `closed_at` | DateTime | Nullable. Set when DS closes the document. |

The `reference_no` is generated inside `crud.py` by the `_generate_reference_no()` function:

```text
Current year: 2026
Count of existing CDTRS-2026-* documents: 3
New reference_no: CDTRS-2026-0004
```

---

## 6.6 `document_routes` Table

Every time DS routes a document (to Director, HOD, or Employee), a new row is inserted here. This table is a permanent, append-only log of all routing decisions. DS cannot delete a route.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer | Primary key |
| `document_id` | Integer (FK) | Links to `documents.doc_id` |
| `from_user_id` | Integer (FK) | The user who performed the routing (always DS or Director for RETURN_TO_DS) |
| `to_user_id` | Integer (FK) | Nullable. The specific user being routed to |
| `to_department_id` | Integer (FK) | Nullable. The department being routed to |
| `route_type` | Enum(RouteType) | What kind of routing action this was |
| `remarks` | Text | Nullable. DS note attached to the routing |
| `created_at` | DateTime | When the route was created |

Example: DS sends document to Director:
```text
id=1, document_id=5, from_user_id=1 (DS), to_user_id=2 (Director),
route_type=INITIAL_DIRECTOR_REVIEW, remarks="Please review urgently"
```

---

## 6.7 `work_assignments` Table

When HOD assigns a document to an Employee, a row is inserted here. This is separate from routing because HOD → Employee is a work delegation, not a routing decision.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer | Primary key |
| `document_id` | Integer (FK) | The document being assigned |
| `assigned_by_user_id` | Integer (FK) | The HOD who made the assignment |
| `assigned_to_user_id` | Integer (FK) | The Employee being assigned |
| `instructions` | Text | Nullable. HOD's instructions for the employee |
| `is_active` | Boolean | `true` = current active assignment. When HOD re-assigns, the old row is set to `false`. |
| `assigned_at` | DateTime | When the assignment was made |
| `completed_at` | DateTime | Nullable. Not used in V2 — reserved for future use. |

---

## 6.8 `progress_updates` Table

Each time an Employee submits a progress update, a new row is added. Old rows are never modified. The full history is always preserved.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer | Primary key |
| `document_id` | Integer (FK) | The document this progress is for |
| `submitted_by_user_id` | Integer (FK) | The Employee who submitted it |
| `description` | Text | Free-text update (no percentage field) |
| `created_at` | DateTime | Timestamp of the submission |

Example for one document:
```text
Progress Update 1 → "Verification has started."
Progress Update 2 → "All records have been verified."
Progress Update 3 → "Final report has been prepared."
```
All three rows exist. The first two are never overwritten.

---

## 6.9 `attachments` Table

Stores metadata about uploaded files. The actual file is saved to the server disk. The database stores only a reference path (`storage_key`).

| Column | Type | Notes |
|---|---|---|
| `id` | Integer | Primary key |
| `document_id` | Integer (FK) | Which document this file belongs to |
| `progress_update_id` | Integer (FK) | Nullable. If this file was attached to a specific progress update, this links to it. If NULL, it is an original document attachment. |
| `uploaded_by_user_id` | Integer (FK) | Who uploaded the file |
| `file_name` | String(255) | The original filename as uploaded by the user |
| `storage_key` | String(500) | The relative path on the server where the file is saved |
| `file_type` | String(100) | MIME type (e.g. "application/pdf") |
| `file_size` | BigInteger | File size in bytes |
| `created_at` | DateTime | Upload timestamp |

The relationship between attachments and progress updates:

```text
attachment.progress_update_id = NULL    →  Original document file
attachment.progress_update_id = 3      →  File attached to progress update #3
```

---

## 6.10 `workflow_history` Table

Every meaningful action on a document creates a row here. This is the document-centric audit trail that DS, HOD, Director, and Employee can all see through the API.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer | Primary key |
| `document_id` | Integer (FK) | The document this event belongs to |
| `performed_by_user_id` | Integer (FK) | Who performed this action |
| `action` | String(150) | What happened (see action strings below) |
| `from_role` | String(50) | Nullable. The role sending the action |
| `to_role` | String(50) | Nullable. The role receiving |
| `details` | Text | Nullable. Extra context (the remark text, filename, etc.) |
| `created_at` | DateTime | When this event happened |

Action strings used in V2:

```text
DOCUMENT_RECEIVED           DS registered the document
ROUTED_INITIAL_DIRECTOR_REVIEW   DS sent to Director
DIRECTOR_REMARK_SAVED       Director updated their remark
RETURNED_TO_DS              Director returned to DS
ROUTED_POST_REVIEW_TO_HOD   DS routed to HOD
ROUTED_POST_REVIEW_TO_EMPLOYEE  DS routed to Employee
HOD_REMARK_SAVED            HOD updated their remark
EMPLOYEE_ASSIGNED           HOD assigned an Employee
PROGRESS_UPDATED            Employee submitted a progress update
ATTACHMENT_UPLOADED         A file was uploaded
FOLLOW_UP_TO_DIRECTOR       DS forwarded progress to Director
DOCUMENT_CLOSED             DS closed the document
```

---

## 6.11 `audit_logs` Table

A system-level log that is separate from `workflow_history`. Workflow history is for document lifecycle events that users see. Audit log is for system/security events like logins.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer | Primary key |
| `user_id` | Integer (FK) | Who triggered the event |
| `action` | String(100) | What happened (e.g. "USER_LOGIN") |
| `entity_type` | String(50) | Nullable. What kind of object was affected |
| `entity_id` | Integer | Nullable. The ID of the affected object |
| `description` | Text | Nullable. Human-readable description |
| `created_at` | DateTime | Timestamp |

Currently, `USER_LOGIN` is the main event recorded. More events can be added.

---

## 6.12 `notifications` Table

Every major workflow action automatically creates a notification for the relevant user.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer | Primary key |
| `user_id` | Integer (FK) | The user who should see this notification |
| `document_id` | Integer (FK) | Nullable. The related document |
| `workflow_event_id` | Integer (FK) | Nullable. Links to the workflow_history event that triggered it |
| `title` | String(200) | Short notification title |
| `message` | Text | Full notification message |
| `is_read` | Boolean | Defaults to `false`. Set to `true` when user reads it. |
| `created_at` | DateTime | When the notification was created |

Notifications are created automatically — you do not need to create them manually. For example, when DS routes a document to the Director, the backend automatically creates a notification for the Director.

---

# 7. `database.py` — How It Works

`database.py` is responsible for one thing: connecting Python to PostgreSQL.

```python
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:your_password@localhost:5432/cdtrs")
```

It reads the connection string from the environment variable `DATABASE_URL`. If the variable is not set, it falls back to the localhost default. The connection string format is:

```text
postgresql+psycopg2://  ← Driver (psycopg2 talks to PostgreSQL)
postgres:               ← PostgreSQL username
your_password@          ← PostgreSQL password
localhost:5432/         ← Host and port
cdtrs                   ← Database name
```

Then it creates:

```python
engine = create_engine(DATABASE_URL, echo=False)
```

The `engine` is the low-level connection to PostgreSQL. `echo=False` means SQL queries are not printed to the console. Set it to `True` if you want to see what SQL is being sent to PostgreSQL during debugging.

```python
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
```

`SessionLocal` is a factory. Every time FastAPI needs to talk to the database, it calls `SessionLocal()` to create a new database session.

```python
Base = declarative_base()
```

`Base` is the parent class that all SQLAlchemy models inherit from. When you call `Base.metadata.create_all(bind=engine)` in `main.py`, SQLAlchemy looks at all classes that inherit from `Base` and creates the corresponding tables in PostgreSQL if they do not already exist.

```python
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

`get_db()` is a FastAPI dependency. Every endpoint that needs the database declares `db: Session = Depends(get_db)`. FastAPI calls this function, opens a session, passes it to the endpoint, and automatically closes it when the request is done — even if an exception is raised.

---

# 8. `models.py` — How It Works

`models.py` defines all database tables as Python classes. SQLAlchemy reads these class definitions and converts them into CREATE TABLE statements for PostgreSQL.

Each model class:
- Inherits from `Base`
- Has a `__tablename__` that sets the PostgreSQL table name
- Has `Column(...)` attributes that map to database columns
- Has `relationship(...)` attributes that let you navigate between related records in Python without writing SQL

Example — navigating relationships in code:

```python
document = db.query(Document).filter(Document.doc_id == 5).first()

# Access related data without extra queries
creator_name = document.creator.full_name
dept_name    = document.target_department.name
routes       = document.routes            # List of DocumentRoute objects
progress     = document.progress_updates  # List of ProgressUpdate objects
```

SQLAlchemy handles all the SQL JOINs automatically behind the scenes.

---

# 9. `schemas.py` — How It Works

`schemas.py` contains Pydantic models (called "schemas"). These are the data shapes that the API accepts and returns.

There are two types of schemas:

**Request schemas** — validate data coming into the API:
```python
class DocumentCreate(BaseModel):
    title:         str           # Required
    received_date: date          # Required
    mode:          str           # Required
    description:   Optional[str] = None   # Optional, defaults to None
    priority:      Priority = Priority.MEDIUM  # Optional, defaults to MEDIUM
```

If the frontend sends a request without `title`, FastAPI rejects it with a `422 Unprocessable Entity` error before the code even runs.

**Response schemas** — shape the data returned by the API:
```python
class DocumentResponse(BaseModel):
    doc_id:        int
    reference_no:  str
    title:         str
    status:        DocumentStatus
    ...
    model_config = ConfigDict(from_attributes=True)
```

`from_attributes=True` tells Pydantic to read data from SQLAlchemy model objects instead of dictionaries. This lets FastAPI convert an ORM object directly into a JSON response.

The separation between models (database shape) and schemas (API shape) means:
- You can change the database without breaking the API contract
- You can hide internal fields (like `password_hash`) from API responses
- You can rename fields between database and API

---

# 10. `crud.py` — How It Works

`crud.py` contains all functions that interact with the database. No endpoint in `main.py` writes SQL directly — they all call a function from `crud.py`.

CRUD stands for:
```text
C → Create  (INSERT)
R → Read    (SELECT)
U → Update  (UPDATE)
D → Delete  (DELETE — not commonly used in CDTRS)
```

`crud.py` is organized into sections:

---

## Password and JWT Section

```python
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
```

`pwd_context` is the passlib object that handles bcrypt hashing.

```python
def hash_password(password: str) -> str:
    return pwd_context.hash(password)
```

Takes a plain password string, returns the bcrypt hash string.

```python
def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)
```

Takes the plain password typed by the user and the stored hash. Returns `True` if they match.

```python
def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
```

Creates a JWT token. The token contains:
- `sub` — the user's ID
- `role` — the user's role
- `exp` — when the token expires

The token is signed with `SECRET_KEY` using the HS256 algorithm. Anyone can decode the token and read its contents, but only the server can verify the signature.

```python
def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except Exception:
        return None
```

Decodes and verifies a token. Returns the payload if valid, `None` if expired or tampered.

---

## User Section

```python
def create_user(db, user) -> User
```
Hashes the password and inserts a new user row.

```python
def get_user_by_username(db, username) -> Optional[User]
```
Finds a user by username. Used during login.

```python
def get_user_by_id(db, user_id) -> Optional[User]
```
Finds a user by their numeric ID. Used to load the current user from a token.

```python
def get_users(db) -> List[User]
```
Returns all users ordered alphabetically by name.

```python
def get_users_by_role(db, role) -> List[User]
```
Returns all active users with a specific role. Used by the follow-up endpoint to find the Director automatically.

```python
def authenticate_user(db, username, password) -> Optional[User]
```
The login check. Performs three checks in order:
1. Does the username exist?
2. Does the password match the stored hash?
3. Is the account active?

Returns the user object if all three pass, otherwise `None`.

---

## Department Section

```python
def create_department(db, dept) -> Department
```
Inserts a new department.

```python
def get_departments(db) -> List[Department]
```
Returns all departments where `is_active = true`, sorted alphabetically.

```python
def get_department_by_id(db, dept_id) -> Optional[Department]
```
Finds a single department by ID. Used to validate that a department exists before routing.

---

## Employee Section

```python
def create_employee(db, emp) -> Employee
```
Inserts a new employee record.

```python
def get_employees(db) -> List[Employee]
```
Returns all active employees alphabetically.

```python
def get_employees_by_department(db, department_id) -> List[Employee]
```
Returns all active employees in a specific department. Useful for the frontend when showing which employees the HOD can assign.

---

## Reference Number Generator

```python
def _generate_reference_no(db) -> str
```

This internal function (prefixed with `_` to show it is private) generates the unique document reference number:

```text
Year: 2026
Count of CDTRS-2026-* documents: 7
Sequence: 7 + 1 = 8 → padded to 4 digits = "0008"
Reference: CDTRS-2026-0008
```

It queries the database to count existing documents for the current year, then increments.

---

## Document Section

```python
def create_document(db, doc, created_by) -> Document
```

Creates the initial document record:
1. Generates a reference number
2. Sets `status = RECEIVED` and `current_stage = DS`
3. Sets `current_owner_id = created_by` (the DS user)
4. Inserts the document row
5. Immediately writes a `DOCUMENT_RECEIVED` entry to `workflow_history`

```python
def get_document(db, doc_id) -> Optional[Document]
```
Returns a single document by its primary key.

```python
def get_documents(db) -> List[Document]
```
Returns all documents ordered by `created_at` descending (newest first). Used by DS to see all documents.

```python
def get_inbox(db, user) -> List[Document]
```
Returns the appropriate inbox for the logged-in user. The query is different for each role:

```text
DS       →  All documents where created_by = me OR current_owner = me
DIRECTOR →  Documents where current_stage = DIRECTOR AND current_owner = me
HOD      →  Documents where current_stage = HOD AND target_department_id = my department
EMPLOYEE →  Documents where I have an active work_assignment
             OR current_owner = me AND current_stage = EMPLOYEE
```

---

## Workflow Action Functions

These are the core business logic functions. Each one:
1. Loads the document
2. Updates the document's `status`, `current_stage`, `current_owner_id`
3. Creates a `DocumentRoute` or `WorkAssignment` record
4. Writes to `workflow_history`
5. Creates notifications for affected users
6. Commits and returns the updated document

```python
def route_document(db, doc_id, route_req, current_user) -> Document
```

Handles all routing actions done by DS. The `route_type` field in the request determines what happens:

```text
INITIAL_DIRECTOR_REVIEW   →  stage = DIRECTOR, status = UNDER_DIRECTOR_REVIEW
POST_REVIEW_TO_HOD        →  stage = HOD, status = UNDER_HOD_PROCESSING, sets target_department_id
POST_REVIEW_TO_EMPLOYEE   →  stage = EMPLOYEE, status = ASSIGNED_FOR_EXECUTION
FOLLOW_UP_TO_DIRECTOR     →  stage = DIRECTOR, status = UNDER_DIRECTOR_REVIEW
```

```python
def save_director_remark(db, doc_id, remark, current_user) -> Document
```

Updates `documents.director_remark` in-place. This is completely separate from returning the document. The Director can save a remark without triggering any routing.

```python
def return_to_ds(db, doc_id, ds_user_id, remarks, current_user) -> Document
```

Director returns the document to DS:
1. Sets `current_stage = DS`
2. Sets `status = DIRECTOR_REVIEW_COMPLETED`
3. Sets `current_owner_id = ds_user_id` (the original creator)
4. Creates a `RETURN_TO_DS` route record
5. Notifies DS

```python
def save_hod_remark(db, doc_id, remark, current_user) -> Document
```

Updates `documents.hod_remark` in-place. Independent of assignment.

```python
def assign_employee(db, doc_id, assign_req, current_user) -> WorkAssignment
```

HOD assigns an Employee:
1. Deactivates any existing active assignment (`is_active = False`)
2. Creates a new `WorkAssignment` row
3. Sets `current_stage = EMPLOYEE`
4. Sets `status = ASSIGNED_FOR_EXECUTION`
5. Sets `current_owner_id = the Employee's user ID`
6. Notifies the Employee

```python
def create_progress_update(db, doc_id, prog, current_user) -> ProgressUpdate
```

Employee submits progress:
1. Inserts a new `ProgressUpdate` row (old rows untouched)
2. Sets `status = IN_PROGRESS`
3. Notifies DS (the document creator)

```python
def create_attachment(db, ...) -> Attachment
```

Saves attachment metadata to the database (the file itself is saved to disk in `main.py`).

```python
def follow_up_to_director(db, doc_id, director_user, remarks, current_user) -> Document
```

DS forwards the employee's progress to the Director:
1. Sets `current_stage = DIRECTOR`
2. Sets `current_owner_id = director.id`
3. Creates a `FOLLOW_UP_TO_DIRECTOR` route record
4. Notifies the Director

```python
def close_document(db, doc_id, remarks, current_user) -> Document
```

DS permanently closes the document:
1. Sets `status = CLOSED`
2. Sets `current_stage = CLOSED`
3. Sets `closed_at = now`
4. Writes `DOCUMENT_CLOSED` to workflow history

---

## Notification Functions

```python
def _create_notification(db, user_id, document_id, workflow_event_id, title, message)
```
Private function. Called internally by all workflow action functions. Creates one notification row for the specified user.

```python
def get_notifications(db, user_id) -> List[Notification]
```
All notifications for a user, newest first.

```python
def get_unread_notifications(db, user_id) -> List[Notification]
```
Only unread notifications.

```python
def mark_notification_read(db, notification_id, user_id) -> Optional[Notification]
```
Sets `is_read = true` for a single notification. Only works if the notification belongs to the requesting user.

```python
def mark_all_notifications_read(db, user_id) -> int
```
Sets `is_read = true` for all unread notifications. Returns the count of notifications updated.

---

## Dashboard Function

```python
def get_dashboard_stats(db, user) -> dict
```

Returns role-specific statistics by running multiple COUNT queries. Each role gets different numbers:

```text
DS        →  total documents created, breakdown by stage, closed count
DIRECTOR  →  documents currently waiting for review
HOD       →  documents in their department, pending assignment count
EMPLOYEE  →  active work assignments count
All roles →  unread notification count always included
```

---

## Seed Data Function

```python
def seed_data(db) -> None
```

Called on startup when `SEED_DB=true`. Creates:
- 4 departments: Administration, Finance, Human Resources, Technical
- 4 users: one for each role

It checks for existing records before inserting, so it is safe to call multiple times.

---

# 11. `main.py` — How It Works

`main.py` is the entry point of the application. It wires all other components together.

---

## Application Setup

```python
models.Base.metadata.create_all(bind=engine)
```

This runs when the server starts. SQLAlchemy looks at every model defined in `models.py` and creates its table in PostgreSQL if the table does not already exist. Existing tables are never dropped or modified.

```python
app = FastAPI(title="CDTRS V2 Backend", version="2.0.0")
```

Creates the FastAPI application.

```python
app.add_middleware(CORSMiddleware, allow_origins=["*"], ...)
```

Enables CORS (Cross-Origin Resource Sharing). This allows the frontend running on a different origin (different machine or port) to make HTTP requests to the API. In development, `allow_origins=["*"]` allows any origin.

---

## Authentication Dependency

```python
bearer_scheme = HTTPBearer()
```

Tells FastAPI to look for an `Authorization: Bearer <token>` header.

```python
def get_current_user(credentials, db) -> User:
```

This is the auth dependency used by almost every endpoint. It:
1. Reads the token from the `Authorization` header
2. Calls `crud.decode_access_token()` to verify the token
3. Extracts the user ID from the token payload
4. Loads the user from the database
5. Checks the user is still active
6. Returns the user object

If any step fails, it raises `HTTP 401 Unauthorized`.

```python
def require_roles(*roles):
```

A factory that returns a dependency for role-based access control. Example:

```python
current_user = Depends(require_roles(UserRole.DS))
```

This means the endpoint only accepts requests from users with the DS role. If a HOD tries to access it, they get `HTTP 403 Forbidden`.

---

## File Upload Handling

```python
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./uploads"))
MAX_FILE_SIZE = 20 * 1024 * 1024   # 20 MB
ALLOWED_TYPES = {"application/pdf", "application/msword", ...}
```

The upload endpoint validates:
1. **File type** — must be in `ALLOWED_TYPES`. Rejects anything else with `400 Bad Request`.
2. **File size** — reads the entire file into memory and checks it is under 20 MB.
3. **Filename collision** — if a file with the same name already exists, it appends a counter (`_1`, `_2`, etc.)

Files are stored at:
```text
uploads/
└── 2026/
    └── 5/               ← document ID
        ├── report.pdf
        └── scan_1.pdf   ← renamed to avoid collision
```

The database stores only the relative path: `2026/5/report.pdf`. The full path is reconstructed when downloading.

---

## API Prefix

All endpoints are under `/api/v1`:

```python
API_V1 = "/api/v1"

@app.post(f"{API_V1}/documents")
```

This makes the full URL `POST http://localhost:8000/api/v1/documents`.

---

## Startup Hook

```python
@app.on_event("startup")
def on_startup():
    if os.getenv("SEED_DB", "false").lower() == "true":
        db = SessionLocal()
        crud.seed_data(db)
        db.close()
```

Runs once when the server starts. If `SEED_DB=true`, it seeds the database with test data.

---

# 12. How Authentication Works End-to-End

```text
Step 1 — Frontend sends:
    POST /api/v1/auth/login
    {"username": "ds_user", "password": "cdtrs@ds"}

Step 2 — Backend:
    crud.authenticate_user() → checks username, password, is_active
    crud.create_access_token() → creates JWT with {sub: "1", role: "DS", exp: ...}
    Returns: {"access_token": "eyJ...", "token_type": "bearer", "user": {...}}

Step 3 — Frontend saves the access_token

Step 4 — Frontend sends every subsequent request with:
    Authorization: Bearer eyJ...

Step 5 — Backend's get_current_user():
    Reads the token
    crud.decode_access_token() → verifies signature and expiry
    Extracts user_id from payload
    crud.get_user_by_id() → loads user from DB
    Returns user object to the endpoint

Step 6 — Endpoint runs with current_user available
```

---

# 13. How the Workflow Works End-to-End

Below is a complete example of a document going through the full lifecycle. Document ID is 1, DS user ID is 1, Director user ID is 2, Finance HOD user ID is 3, Employee user ID is 4.

### Step 1 — DS Registers Document

```
POST /api/v1/documents
Auth: Bearer <ds_token>
Body: {"title": "Annual Audit Report", "received_date": "2026-08-15", "mode": "Email", "priority": "HIGH"}
```

Result:
- Document created: `reference_no = CDTRS-2026-0001`
- `status = RECEIVED`, `current_stage = DS`, `current_owner_id = 1`
- Workflow history: `DOCUMENT_RECEIVED`

### Step 2 — DS Routes to Director

```
POST /api/v1/documents/1/route
Auth: Bearer <ds_token>
Body: {"route_type": "INITIAL_DIRECTOR_REVIEW", "to_user_id": 2, "remarks": "Please review"}
```

Result:
- `status = UNDER_DIRECTOR_REVIEW`, `current_stage = DIRECTOR`, `current_owner_id = 2`
- DocumentRoute row created
- Notification sent to Director (user 2)
- Workflow history: `ROUTED_INITIAL_DIRECTOR_REVIEW`

### Step 3 — Director Saves Remark

```
PUT /api/v1/documents/1/director-remark
Auth: Bearer <director_token>
Body: {"director_remark": "Route to Finance HOD for verification."}
```

Result:
- `documents.director_remark = "Route to Finance HOD for verification."`
- Workflow history: `DIRECTOR_REMARK_SAVED`
- Document stage/status unchanged

### Step 4 — Director Returns to DS

```
POST /api/v1/documents/1/return-to-ds
Auth: Bearer <director_token>
Body: {"remarks": "Reviewed. Please route to Finance."}
```

Result:
- `status = DIRECTOR_REVIEW_COMPLETED`, `current_stage = DS`, `current_owner_id = 1`
- DocumentRoute row created (RETURN_TO_DS)
- Notification sent to DS (user 1)
- Workflow history: `RETURNED_TO_DS`

### Step 5 — DS Routes to HOD

```
POST /api/v1/documents/1/route
Auth: Bearer <ds_token>
Body: {"route_type": "POST_REVIEW_TO_HOD", "to_department_id": 2, "to_user_id": 3}
```

Result:
- `status = UNDER_HOD_PROCESSING`, `current_stage = HOD`
- `target_department_id = 2`, `current_owner_id = 3`
- Notification sent to HOD (user 3)
- Workflow history: `ROUTED_POST_REVIEW_TO_HOD`

### Step 6 — HOD Saves Remark (Optional)

```
PUT /api/v1/documents/1/hod-remark
Auth: Bearer <hod_token>
Body: {"hod_remark": "Assigned to Rahul for verification."}
```

Result:
- `documents.hod_remark = "Assigned to Rahul for verification."`
- Workflow history: `HOD_REMARK_SAVED`

### Step 7 — HOD Assigns Employee

```
POST /api/v1/documents/1/assign
Auth: Bearer <hod_token>
Body: {"assigned_to_user_id": 4, "instructions": "Complete the audit verification by Friday."}
```

Result:
- WorkAssignment row created
- `status = ASSIGNED_FOR_EXECUTION`, `current_stage = EMPLOYEE`, `current_owner_id = 4`
- Notification sent to Employee (user 4)
- Workflow history: `EMPLOYEE_ASSIGNED`

### Step 8 — Employee Submits Progress

```
POST /api/v1/documents/1/progress
Auth: Bearer <employee_token>
Body: {"description": "Verification has started. Reviewing FY2025 records."}
```

Result:
- ProgressUpdate row inserted (previous updates untouched)
- `status = IN_PROGRESS`
- DS notified
- Workflow history: `PROGRESS_UPDATED`

### Step 9 — Employee Uploads Attachment

```
POST /api/v1/documents/1/attachments
Auth: Bearer <employee_token>
Form: file=<report.pdf>, progress_update_id=1
```

Result:
- File saved to `uploads/2026/1/report.pdf`
- Attachment row created with `progress_update_id = 1`
- Workflow history: `ATTACHMENT_UPLOADED`

### Step 10 — DS Forwards Follow-up to Director

```
POST /api/v1/documents/1/follow-up
Auth: Bearer <ds_token>
Body: {"remarks": "Employee has completed verification. Please review."}
```

Result:
- `status = UNDER_DIRECTOR_REVIEW`, `current_stage = DIRECTOR`, `current_owner_id = 2`
- Director notified
- Workflow history: `FOLLOW_UP_TO_DIRECTOR`

### Step 11 — Director Reviews and Returns to DS Again

Director saves final remark, then returns to DS (same as Steps 3 and 4).

### Step 12 — DS Closes the Document

```
POST /api/v1/documents/1/close
Auth: Bearer <ds_token>
Body: {"remarks": "Document closed after final director review."}
```

Result:
- `status = CLOSED`, `current_stage = CLOSED`
- `closed_at = now`
- Workflow history: `DOCUMENT_CLOSED`

---

# 14. Complete API Reference

All endpoints require `Authorization: Bearer <token>` in the header unless marked as public.

---

## Authentication

### POST `/api/v1/auth/login` — Public
Login with username and password.

Request:
```json
{
  "username": "ds_user",
  "password": "cdtrs@ds"
}
```

Response (200 OK):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "username": "ds_user",
    "full_name": "Director Secretary",
    "role": "DS",
    "department_id": 1,
    "employee_id": null,
    "is_active": true,
    "created_at": "2026-08-15T10:00:00",
    "updated_at": "2026-08-15T10:00:00"
  }
}
```

Errors:
- `401` — Invalid username or password

---

### GET `/api/v1/auth/me` — All Roles
Returns the currently authenticated user.

Response (200 OK): Same as `user` in the login response.

---

### POST `/api/v1/auth/logout` — All Roles
Returns a success message. The client must discard its token.

Response (200 OK):
```json
{"message": "Logged out successfully. Please discard your token."}
```

---

## Users

### POST `/api/v1/users` — DS only
Create a new user account.

Request:
```json
{
  "username": "hod_hr",
  "password": "some_password",
  "full_name": "HR Head",
  "role": "HOD",
  "department_id": 3
}
```

Valid roles: `DS`, `DIRECTOR`, `HOD`, `EMPLOYEE`

Response (201 Created): `UserResponse`

Errors:
- `400` — Username already exists

---

### GET `/api/v1/users` — DS only
Returns all users alphabetically.

Response (200 OK): Array of `UserResponse`

---

## Departments

### POST `/api/v1/departments` — DS only
Create a department.

Request:
```json
{
  "name": "Information Technology",
  "code": "IT"
}
```

Response (201 Created): `DepartmentResponse`

---

### GET `/api/v1/departments` — All Roles
Returns all active departments alphabetically.

Response (200 OK): Array of `DepartmentResponse`

---

### GET `/api/v1/departments/{id}/employees` — All Roles
Returns all active employees in the department.

Response (200 OK): Array of `EmployeeResponse`

Errors:
- `404` — Department not found

---

## Employees

### POST `/api/v1/employees` — DS only
Create an employee record.

Request:
```json
{
  "employee_code": "EMP-005",
  "full_name": "Priya Mehta",
  "department_id": 2,
  "designation": "Financial Analyst",
  "user_id": 4
}
```

`user_id` is optional. It links the employee record to an existing user account.

Response (201 Created): `EmployeeResponse`

Errors:
- `404` — Department not found

---

### GET `/api/v1/employees` — All Roles
Returns all active employees alphabetically.

Response (200 OK): Array of `EmployeeResponse`

---

## Documents

### POST `/api/v1/documents` — DS only
Register a new document (DS intake).

Request:
```json
{
  "title": "Annual Audit Report FY2025",
  "description": "Detailed audit report from the Finance Ministry",
  "received_date": "2026-08-15",
  "deadline": "2026-09-01",
  "source": "Ministry of Finance",
  "mode": "Email",
  "priority": "HIGH"
}
```

Valid `priority` values: `HIGH`, `MEDIUM`, `LOW`
Valid `mode` values: any string, e.g. `Email`, `Fax`, `Physical`, `Intranet`

Response (201 Created): `DocumentResponse`

---

### GET `/api/v1/documents` — DS only
Returns all documents newest first.

Response (200 OK): Array of `DocumentListResponse` (lighter version with fewer fields)

---

### GET `/api/v1/documents/inbox` — All Roles
Returns the role-appropriate inbox. Each role sees only what is relevant to them.

Response (200 OK): Array of `DocumentListResponse`

---

### GET `/api/v1/documents/{id}` — All Roles
Returns the full details of a document.

Response (200 OK): `DocumentResponse`

Errors:
- `404` — Document not found

---

### POST `/api/v1/documents/{id}/route` — DS only
Route the document. The `route_type` controls the routing action.

**To Director (first review):**
```json
{
  "route_type": "INITIAL_DIRECTOR_REVIEW",
  "to_user_id": 2,
  "remarks": "Please review and provide your remark."
}
```

**To HOD (after Director review):**
```json
{
  "route_type": "POST_REVIEW_TO_HOD",
  "to_user_id": 3,
  "to_department_id": 2,
  "remarks": "Route to Finance as per Director's instruction."
}
```

**Directly to Employee:**
```json
{
  "route_type": "POST_REVIEW_TO_EMPLOYEE",
  "to_user_id": 4,
  "remarks": "Assign directly as employee was identified."
}
```

Response (200 OK): `DocumentResponse` (with updated stage/status)

Errors:
- `404` — Document not found
- `409` — Document is already closed

---

### PUT `/api/v1/documents/{id}/director-remark` — DIRECTOR only
Save or update the Director's remark. This does NOT route the document.

Request:
```json
{
  "director_remark": "Please verify all records for FY2025 and report back."
}
```

Response (200 OK): `DocumentResponse`

---

### POST `/api/v1/documents/{id}/return-to-ds` — DIRECTOR only
Return the document to DS. This IS a routing action.

Request:
```json
{
  "remarks": "Reviewed. Route to Finance HOD."
}
```

Response (200 OK): `DocumentResponse`

---

### PUT `/api/v1/documents/{id}/hod-remark` — HOD only
Save or update the HOD's remark. This does NOT assign an Employee.

Request:
```json
{
  "hod_remark": "Rahul should handle this. Verification needed."
}
```

Response (200 OK): `DocumentResponse`

---

### POST `/api/v1/documents/{id}/assign` — HOD only
Assign an Employee to the document. The Employee must have the `EMPLOYEE` role.

Request:
```json
{
  "assigned_to_user_id": 4,
  "instructions": "Please complete verification by Friday and upload the report."
}
```

Response (201 Created): `AssignmentResponse`

Errors:
- `400` — Target user is not an EMPLOYEE
- `404` — Document not found
- `409` — Document is closed

---

### POST `/api/v1/documents/{id}/progress` — EMPLOYEE only
Submit a progress update. Every call adds a new entry — previous entries are never modified.

Request:
```json
{
  "description": "Verification has started. Reviewing FY2025 general ledger records."
}
```

Response (201 Created): `ProgressResponse`

---

### GET `/api/v1/documents/{id}/progress` — All Roles
Returns all progress updates for a document, ordered from oldest to newest.

Response (200 OK): Array of `ProgressResponse`

---

### POST `/api/v1/documents/{id}/attachments` — All Roles
Upload a file. Uses `multipart/form-data`.

Form fields:
- `file` — the file itself (required)
- `progress_update_id` — integer (optional). If provided, links the attachment to a specific progress update.

Allowed file types: PDF, DOC, DOCX, JPEG, PNG, TXT

Maximum file size: 20 MB

Response (201 Created): `AttachmentResponse`

Errors:
- `400` — File type not allowed
- `400` — File exceeds 20 MB

---

### GET `/api/v1/documents/{id}/attachments` — All Roles
Returns all attachments for a document.

Response (200 OK): Array of `AttachmentResponse`

---

### POST `/api/v1/documents/{id}/follow-up` — DS only
Forward employee progress to the Director. The backend automatically picks the active Director user.

Request:
```json
{
  "remarks": "Employee has completed verification. Please review the attached report."
}
```

Response (200 OK): `DocumentResponse`

Errors:
- `400` — No active Director found
- `409` — Document is closed

---

### GET `/api/v1/documents/{id}/history` — All Roles
Returns the full workflow history for a document, ordered from oldest to newest.

Response (200 OK): Array of `WorkflowHistoryResponse`

```json
[
  {
    "id": 1,
    "document_id": 1,
    "performed_by_user_id": 1,
    "action": "DOCUMENT_RECEIVED",
    "from_role": "DS",
    "to_role": null,
    "details": "Document received and registered as CDTRS-2026-0001",
    "created_at": "2026-08-15T10:00:00"
  },
  ...
]
```

---

### POST `/api/v1/documents/{id}/close` — DS only
Permanently close the document. After closing, no workflow actions can be performed. The document and all its history remain viewable.

Request:
```json
{
  "remarks": "Document closed after completion of all required actions."
}
```

Response (200 OK): `DocumentResponse` with `status = CLOSED` and `closed_at` set.

Errors:
- `409` — Document is already closed

---

## Attachments

### GET `/api/v1/attachments/{id}` — All Roles
Get the metadata for a single attachment (filename, type, size, etc.).

Response (200 OK): `AttachmentResponse`

---

### GET `/api/v1/attachments/{id}/download` — All Roles
Download the actual file. The browser will receive the file as a download.

Response: The file binary with appropriate `Content-Type` and `Content-Disposition` headers.

Errors:
- `404` — Attachment record not found OR file no longer on disk

---

## Notifications

### GET `/api/v1/notifications` — All Roles
All notifications for the current user, newest first.

Response (200 OK): Array of `NotificationResponse`

---

### GET `/api/v1/notifications/unread` — All Roles
Only unread notifications for the current user.

Response (200 OK): Array of `NotificationResponse`

---

### PATCH `/api/v1/notifications/{id}/read` — All Roles
Mark a single notification as read. Only works on notifications belonging to the current user.

Response (200 OK): `NotificationResponse` with `is_read = true`

---

### PATCH `/api/v1/notifications/read-all` — All Roles
Mark all unread notifications as read.

Response (200 OK):
```json
{"message": "5 notification(s) marked as read."}
```

---

## Dashboard

### GET `/api/v1/dashboard` — All Roles
Returns role-specific statistics.

**DS Dashboard:**
```json
{
  "role": "DS",
  "total_documents": 25,
  "pending_action": 20,
  "unread_notifications": 3,
  "under_director_review": 5,
  "under_hod_processing": 8,
  "in_progress": 7,
  "closed_documents": 5
}
```

**DIRECTOR Dashboard:**
```json
{
  "role": "DIRECTOR",
  "total_documents": 5,
  "pending_action": 5,
  "unread_notifications": 2,
  "documents_for_review": 5
}
```

**HOD Dashboard:**
```json
{
  "role": "HOD",
  "total_documents": 8,
  "pending_action": 3,
  "unread_notifications": 1,
  "pending_assignment": 3
}
```

**EMPLOYEE Dashboard:**
```json
{
  "role": "EMPLOYEE",
  "total_documents": 2,
  "pending_action": 2,
  "unread_notifications": 0,
  "active_assignments": 2
}
```

---

# 15. HTTP Status Codes

| Code | When it is returned |
|---|---|
| `200 OK` | Request succeeded, response body contains the result |
| `201 Created` | A new record was created successfully |
| `400 Bad Request` | Something in the request is wrong (duplicate username, invalid file type, etc.) |
| `401 Unauthorized` | No token provided, token is expired, or token is invalid |
| `403 Forbidden` | Token is valid but the user's role does not have permission |
| `404 Not Found` | The requested record does not exist |
| `409 Conflict` | Workflow conflict such as trying to route a closed document |
| `422 Unprocessable Entity` | Request body fails Pydantic validation (missing required field, wrong type) |
| `500 Internal Server Error` | Unexpected server error |

All error responses use this format:
```json
{
  "detail": "Human-readable error message explaining what went wrong."
}
```

---

# 16. Test Credentials

Run the server once with `SEED_DB=true` to create these accounts.

| Role | Username | Password | Department |
|---|---|---|---|
| DS | `ds_user` | `cdtrs@ds` | Administration |
| DIRECTOR | `director` | `cdtrs@director` | — |
| HOD | `hod_finance` | `cdtrs@hod` | Finance |
| EMPLOYEE | `emp_rahul` | `cdtrs@emp` | Finance |

---

# 17. How to Test Using Swagger UI

Swagger UI at `http://localhost:8000/docs` is the easiest way to test.

### Step 1 — Login

1. Click on `POST /api/v1/auth/login`
2. Click **Try it out**
3. Enter:
```json
{
  "username": "ds_user",
  "password": "cdtrs@ds"
}
```
4. Click **Execute**
5. Copy the `access_token` value from the response

### Step 2 — Authorize in Swagger

1. Click the **Authorize** button at the top right of the Swagger page (lock icon)
2. In the `HTTPBearer` section, paste your token
3. Click **Authorize** then **Close**

All subsequent requests in Swagger will automatically include your token.

### Step 3 — Test Endpoints

Click any endpoint, click **Try it out**, fill in the values, and click **Execute**.

---

# 18. How to Test Using curl (Command Line)

### Login and capture token (PowerShell)

```powershell
$response = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/auth/login" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"username":"ds_user","password":"cdtrs@ds"}'

$token = ($response.Content | ConvertFrom-Json).access_token
$headers = @{ Authorization = "Bearer $token" }
```

### Create a document

```powershell
Invoke-WebRequest -Uri "http://localhost:8000/api/v1/documents" `
  -Method POST `
  -Headers $headers `
  -ContentType "application/json" `
  -Body '{
    "title": "Test Document",
    "received_date": "2026-08-15",
    "mode": "Email",
    "priority": "HIGH"
  }'
```

### Get inbox

```powershell
Invoke-WebRequest -Uri "http://localhost:8000/api/v1/documents/inbox" `
  -Method GET `
  -Headers $headers
```

---

# 19. File Storage Location

Uploaded files are stored on the server under the `uploads/` directory inside the backend folder.

```text
backend/
└── uploads/
    └── 2026/
        └── 1/            ← document ID = 1
            ├── report.pdf
            └── scan.jpg
```

The database does **not** store the file itself. It stores only the relative path:
```text
storage_key = "2026/1/report.pdf"
```

When the frontend requests a download, `main.py` reconstructs the full path:
```python
file_path = UPLOAD_DIR / att.storage_key
# = "./uploads/2026/1/report.pdf"
```

And returns it using `FileResponse`.

---

# 20. Architectural Principles

1. **Document-centric** — There is one canonical document record throughout the entire workflow. No separate DirectorDocument, HODDocument, or EmployeeDocument tables. Everything links back to the same `doc_id`.

2. **Routing is separate from Assignment** — `POST /route` is DS routing decisions (DS chooses where the document goes). `POST /assign` is HOD delegating work to an Employee. These use different tables (`document_routes` vs `work_assignments`).

3. **Director remark is independent of Return-to-DS** — `PUT /director-remark` saves the text. `POST /return-to-ds` is the separate workflow action. The Director can edit the remark multiple times before returning.

4. **HOD remark is independent of Assignment** — Same principle. `PUT /hod-remark` and `POST /assign` are separate actions.

5. **Progress updates are append-only** — Every `POST /progress` creates a new row. Old rows are never modified. The full history is always available.

6. **Employee does not directly contact Director** — The flow is: Employee → Progress Update → DS sees it → DS calls `POST /follow-up` → Director sees it. No direct path from Employee to Director.

7. **HOD does not return documents to DS** — HOD is not a workflow transit point back to DS. Only Director can return to DS.

8. **PostgreSQL is never exposed to the frontend** — Only the FastAPI API is accessible. The frontend never needs database credentials.

9. **Workflow history is user-visible** — `workflow_history` records every document lifecycle event for display in the UI. `audit_logs` records system/security events and is separate.

10. **Notifications are automatic** — Every workflow action that affects another user automatically creates a notification for them. The frontend polls `/notifications/unread`.

---

# 21. How to Use Swagger UI (Step-by-Step)

Swagger UI is the interactive browser-based interface to test every API endpoint without writing any code.

Open it at: **`http://localhost:8000/docs`**

---

## Step 1 — Login and Get Your Token

1. Scroll to the **Authentication** section
2. Click **`POST /api/v1/auth/login`**
3. Click **Try it out** (top right of the endpoint panel)
4. In the **Request body** field, enter:

```json
{
  "username": "ds_user",
  "password": "cdtrs@ds"
}
```

5. Click **Execute**
6. Scroll to the **Response body** section below. You will see:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "username": "ds_user",
    "full_name": "Director Secretary",
    "role": "DS",
    ...
  }
}
```

7. **Copy the entire `access_token` string** (the long text starting with `eyJ...`, do not include the quotation marks)

---

## Step 2 — Authorize in Swagger

1. Click the **Authorize 🔒** button at the top right of the Swagger page (next to the title)
2. A popup appears. Find the section titled **HTTPBearer (http, Bearer)**
3. Paste your token into the **Value** field
4. Click **Authorize**
5. Click **Close**

The lock icons next to every endpoint will now appear filled/closed 🔒. This means all your requests will automatically include the token.

---

## Step 3 — Test Any Endpoint

Example — get your current user info:

1. Click **`GET /api/v1/auth/me`**
2. Click **Try it out**
3. Click **Execute**
4. You will get your user details in the response — no body needed

Example — create a document (DS role):

1. Click **`POST /api/v1/documents`**
2. Click **Try it out**
3. In the **Request body**, enter:

```json
{
  "title": "Annual Audit Report FY2025",
  "description": "Audit report received from Finance Ministry",
  "received_date": "2026-08-15",
  "deadline": "2026-09-01",
  "source": "Ministry of Finance",
  "mode": "Email",
  "priority": "HIGH"
}
```

4. Click **Execute**
5. The response will include the generated `reference_no` (e.g. `CDTRS-2026-0001`) and `doc_id`

---

## Step 4 — Switch Roles

To test endpoints for a different role:

1. Login as the other role first (use the login endpoint with different credentials)
2. Copy the new `access_token`
3. Click **Authorize 🔒** again
4. Click **Logout** on the existing entry
5. Paste the new token and click **Authorize**

---

## Test Credentials for All Roles

| Role | Username | Password | What they can test |
|---|---|---|---|
| `DS` | `ds_user` | `cdtrs@ds` | Create documents, route, follow-up, close |
| `DIRECTOR` | `director` | `cdtrs@director` | Save remark, return to DS |
| `HOD` | `hod_finance` | `cdtrs@hod` | Save remark, assign employee |
| `EMPLOYEE` | `emp_rahul` | `cdtrs@emp` | Submit progress, upload attachments |

---

## Complete Quick Test Flow in Swagger

Here is the order to test the full workflow from start to close:

```text
1.  Login as ds_user         → POST /api/v1/auth/login
2.  Authorize with DS token
3.  Create document          → POST /api/v1/documents
    (note the doc_id returned, e.g. 1)
4.  View inbox               → GET /api/v1/documents/inbox
5.  Route to Director        → POST /api/v1/documents/1/route
    body: {"route_type": "INITIAL_DIRECTOR_REVIEW", "to_user_id": 2}

6.  Login as director        → POST /api/v1/auth/login
7.  Authorize with Director token
8.  Check Director inbox     → GET /api/v1/documents/inbox
9.  Save remark              → PUT /api/v1/documents/1/director-remark
    body: {"director_remark": "Route to Finance HOD."}
10. Return to DS             → POST /api/v1/documents/1/return-to-ds
    body: {"remarks": "Reviewed."}

11. Authorize with DS token again
12. Route to HOD             → POST /api/v1/documents/1/route
    body: {"route_type": "POST_REVIEW_TO_HOD", "to_user_id": 3, "to_department_id": 2}

13. Login as hod_finance     → POST /api/v1/auth/login
14. Authorize with HOD token
15. Assign employee          → POST /api/v1/documents/1/assign
    body: {"assigned_to_user_id": 4, "instructions": "Complete verification."}

16. Login as emp_rahul       → POST /api/v1/auth/login
17. Authorize with Employee token
18. Submit progress          → POST /api/v1/documents/1/progress
    body: {"description": "Verification started."}
19. Upload attachment        → POST /api/v1/documents/1/attachments
    (use the file picker in Swagger)

20. Authorize with DS token
21. Follow-up to Director    → POST /api/v1/documents/1/follow-up
    body: {"remarks": "Employee done. Please review."}

22. Authorize with Director token
23. Save final remark        → PUT /api/v1/documents/1/director-remark
24. Return to DS             → POST /api/v1/documents/1/return-to-ds

25. Authorize with DS token
26. Close document           → POST /api/v1/documents/1/close
    body: {"remarks": "Closed after completion."}

27. View history             → GET /api/v1/documents/1/history
    (all 10+ events visible in order)
```

---

# 22. Frontend Developer Integration Guide

This section is specifically for the **PySide6 frontend developer**. It explains everything you need to know to integrate the frontend with this backend API.

---

## 22.1 What You Need From Backend

You do **not** need:
- PostgreSQL access or credentials
- pgAdmin or any database tool
- SQLAlchemy or any ORM
- Any Python backend knowledge

You **only** need:
- The API Base URL
- The Swagger documentation URL
- The authentication contract (explained below)
- Test accounts (provided below)

---

## 22.2 Connection Information

| Item | Value |
|---|---|
| API Base URL | `http://localhost:8000/api/v1` |
| Swagger UI | `http://localhost:8000/docs` |
| Health Check | `http://localhost:8000/health` |
| Auth Method | JWT Bearer Token |
| Token Lifetime | 60 minutes |
| CORS | All origins allowed (development) |

> When the backend is deployed to a remote server, replace `localhost:8000` with the deployed server URL.

---

## 22.3 Authentication Flow

### Login

Send a POST request to:
```
POST http://localhost:8000/api/v1/auth/login
Content-Type: application/json
```

Request body:
```json
{
  "username": "ds_user",
  "password": "cdtrs@ds"
}
```

Successful response (200 OK):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "username": "ds_user",
    "full_name": "Director Secretary",
    "role": "DS",
    "department_id": 1,
    "employee_id": null,
    "is_active": true,
    "created_at": "2026-08-15T10:00:00",
    "updated_at": "2026-08-15T10:00:00"
  }
}
```

Failed response (401 Unauthorized):
```json
{
  "detail": "Invalid username or password."
}
```

### Save the token

After a successful login, save `access_token` and `user` in your application state (in-memory, not to disk). You will need the token for every subsequent request.

### Send the token

Every API request (except `/auth/login`) must include this HTTP header:

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### Token Expiry

Tokens expire after **60 minutes**. When you receive a `401` response, the token has expired. The correct behavior is to redirect the user back to the login page. Do not try to silently refresh — simply require the user to log in again.

### Logout

Call `POST /api/v1/auth/logout` to log the event on the backend, then clear the token from your application state and navigate to the login page. Since JWT is stateless, logging out is primarily a client-side action.

---

## 22.4 Recommended Frontend Architecture

The root README specifies this structure for the PySide6 frontend:

```text
PySide6 App
│
├── pages/          ← UI only. No HTTP requests here.
│   ├── LoginPage
│   ├── DashboardPage
│   ├── InboxPage
│   ├── DocumentDetailPage
│   └── ...
│
├── services/       ← Business-facing operations
│   ├── auth_service.py
│   ├── document_service.py
│   ├── notification_service.py
│   └── ...
│
├── api_client.py   ← Single place for all HTTP requests
│
└── config.py       ← API_BASE_URL and other settings
```

### `config.py`

```python
API_BASE_URL = "http://localhost:8000/api/v1"
```

Change only this one line when the backend is deployed.

### `api_client.py`

This is the only file that makes HTTP requests. All other code calls this.

```python
import requests
from config import API_BASE_URL

class APIClient:
    def __init__(self):
        self._token = None

    def set_token(self, token: str):
        self._token = token

    def clear_token(self):
        self._token = None

    def _headers(self):
        headers = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def get(self, endpoint: str, params=None):
        response = requests.get(
            f"{API_BASE_URL}{endpoint}",
            headers=self._headers(),
            params=params
        )
        return self._handle(response)

    def post(self, endpoint: str, body: dict = None):
        response = requests.post(
            f"{API_BASE_URL}{endpoint}",
            headers=self._headers(),
            json=body
        )
        return self._handle(response)

    def put(self, endpoint: str, body: dict = None):
        response = requests.put(
            f"{API_BASE_URL}{endpoint}",
            headers=self._headers(),
            json=body
        )
        return self._handle(response)

    def patch(self, endpoint: str, body: dict = None):
        response = requests.patch(
            f"{API_BASE_URL}{endpoint}",
            headers=self._headers(),
            json=body
        )
        return self._handle(response)

    def upload_file(self, endpoint: str, file_path: str, progress_update_id: int = None):
        """Upload a file using multipart/form-data"""
        with open(file_path, "rb") as f:
            files  = {"file": (file_path.split("/")[-1], f)}
            data   = {}
            if progress_update_id:
                data["progress_update_id"] = str(progress_update_id)
            headers = {}
            if self._token:
                headers["Authorization"] = f"Bearer {self._token}"
            response = requests.post(
                f"{API_BASE_URL}{endpoint}",
                headers=headers,
                files=files,
                data=data
            )
        return self._handle(response)

    def _handle(self, response):
        if response.status_code == 401:
            raise UnauthorizedError("Session expired. Please log in again.")
        if response.status_code == 403:
            raise ForbiddenError("You do not have permission to perform this action.")
        if response.status_code == 404:
            raise NotFoundError(response.json().get("detail", "Resource not found."))
        if response.status_code == 409:
            raise ConflictError(response.json().get("detail", "Workflow conflict."))
        if response.status_code >= 400:
            raise APIError(response.json().get("detail", "An error occurred."))
        return response.json()

# Custom exceptions
class APIError(Exception): pass
class UnauthorizedError(APIError): pass
class ForbiddenError(APIError): pass
class NotFoundError(APIError): pass
class ConflictError(APIError): pass

# Singleton
api_client = APIClient()
```

### `services/auth_service.py`

```python
from api_client import api_client

class AuthService:

    def login(self, username: str, password: str) -> dict:
        """Returns the user dict on success. Raises APIError on failure."""
        response = api_client.post("/auth/login", {
            "username": username,
            "password": password
        })
        api_client.set_token(response["access_token"])
        return response["user"]

    def logout(self):
        try:
            api_client.post("/auth/logout")
        except Exception:
            pass
        api_client.clear_token()

    def get_current_user(self) -> dict:
        return api_client.get("/auth/me")

auth_service = AuthService()
```

### `services/document_service.py`

```python
from api_client import api_client

class DocumentService:

    def get_inbox(self) -> list:
        return api_client.get("/documents/inbox")

    def get_all_documents(self) -> list:
        """DS only"""
        return api_client.get("/documents")

    def get_document(self, doc_id: int) -> dict:
        return api_client.get(f"/documents/{doc_id}")

    def create_document(self, title, received_date, mode,
                        description=None, deadline=None,
                        source=None, priority="MEDIUM") -> dict:
        return api_client.post("/documents", {
            "title":         title,
            "received_date": received_date,   # "YYYY-MM-DD"
            "mode":          mode,
            "description":   description,
            "deadline":      deadline,
            "source":        source,
            "priority":      priority
        })

    def route_to_director(self, doc_id: int, director_user_id: int, remarks=None) -> dict:
        return api_client.post(f"/documents/{doc_id}/route", {
            "route_type": "INITIAL_DIRECTOR_REVIEW",
            "to_user_id": director_user_id,
            "remarks":    remarks
        })

    def route_to_hod(self, doc_id: int, hod_user_id: int, department_id: int, remarks=None) -> dict:
        return api_client.post(f"/documents/{doc_id}/route", {
            "route_type":       "POST_REVIEW_TO_HOD",
            "to_user_id":       hod_user_id,
            "to_department_id": department_id,
            "remarks":          remarks
        })

    def route_to_employee(self, doc_id: int, employee_user_id: int, remarks=None) -> dict:
        return api_client.post(f"/documents/{doc_id}/route", {
            "route_type": "POST_REVIEW_TO_EMPLOYEE",
            "to_user_id": employee_user_id,
            "remarks":    remarks
        })

    def save_director_remark(self, doc_id: int, remark: str) -> dict:
        return api_client.put(f"/documents/{doc_id}/director-remark", {
            "director_remark": remark
        })

    def return_to_ds(self, doc_id: int, remarks=None) -> dict:
        return api_client.post(f"/documents/{doc_id}/return-to-ds", {
            "remarks": remarks
        })

    def save_hod_remark(self, doc_id: int, remark: str) -> dict:
        return api_client.put(f"/documents/{doc_id}/hod-remark", {
            "hod_remark": remark
        })

    def assign_employee(self, doc_id: int, employee_user_id: int, instructions=None) -> dict:
        return api_client.post(f"/documents/{doc_id}/assign", {
            "assigned_to_user_id": employee_user_id,
            "instructions":        instructions
        })

    def submit_progress(self, doc_id: int, description: str) -> dict:
        return api_client.post(f"/documents/{doc_id}/progress", {
            "description": description
        })

    def get_progress(self, doc_id: int) -> list:
        return api_client.get(f"/documents/{doc_id}/progress")

    def upload_attachment(self, doc_id: int, file_path: str,
                          progress_update_id: int = None) -> dict:
        return api_client.upload_file(
            f"/documents/{doc_id}/attachments",
            file_path,
            progress_update_id
        )

    def get_attachments(self, doc_id: int) -> list:
        return api_client.get(f"/documents/{doc_id}/attachments")

    def download_attachment_url(self, attachment_id: int) -> str:
        """Returns the URL to pass to requests.get() for downloading."""
        from config import API_BASE_URL
        return f"{API_BASE_URL}/attachments/{attachment_id}/download"

    def follow_up_to_director(self, doc_id: int, remarks=None) -> dict:
        return api_client.post(f"/documents/{doc_id}/follow-up", {
            "remarks": remarks
        })

    def get_history(self, doc_id: int) -> list:
        return api_client.get(f"/documents/{doc_id}/history")

    def close_document(self, doc_id: int, remarks=None) -> dict:
        return api_client.post(f"/documents/{doc_id}/close", {
            "remarks": remarks
        })

document_service = DocumentService()
```

### `services/notification_service.py`

```python
from api_client import api_client

class NotificationService:

    def get_all(self) -> list:
        return api_client.get("/notifications")

    def get_unread(self) -> list:
        return api_client.get("/notifications/unread")

    def mark_read(self, notification_id: int) -> dict:
        return api_client.patch(f"/notifications/{notification_id}/read")

    def mark_all_read(self) -> dict:
        return api_client.patch("/notifications/read-all")

notification_service = NotificationService()
```

---

## 22.5 How Pages Use Services

Pages only call services — they never call `api_client` directly.

```python
# pages/login_page.py

from services.auth_service import auth_service
from api_client import UnauthorizedError

class LoginPage:

    def on_login_button_clicked(self):
        username = self.username_field.text()
        password = self.password_field.text()

        try:
            user = auth_service.login(username, password)
            # Save user role to show the correct dashboard
            self.navigate_to_dashboard(user["role"])

        except UnauthorizedError:
            self.show_error("Invalid username or password.")
        except Exception as e:
            self.show_error(f"Connection error: {str(e)}")
```

```python
# pages/inbox_page.py

from services.document_service import document_service

class InboxPage:

    def load_inbox(self):
        try:
            documents = document_service.get_inbox()
            self.populate_table(documents)
        except Exception as e:
            self.show_error(str(e))
```

---

## 22.6 Role-Based Page Routing

After login, check `user["role"]` to show the correct page:

```python
role = user["role"]   # "DS" | "DIRECTOR" | "HOD" | "EMPLOYEE"

if role == "DS":
    show_ds_dashboard()
elif role == "DIRECTOR":
    show_director_dashboard()
elif role == "HOD":
    show_hod_dashboard()
elif role == "EMPLOYEE":
    show_employee_dashboard()
```

---

## 22.7 What Each Role Sees

### DS Pages
- **Dashboard** — `GET /dashboard` → counts of documents by stage
- **Inbox** — `GET /documents/inbox` → all documents they manage
- **All Documents** — `GET /documents` → full list
- **Document Detail** — `GET /documents/{id}`, history, attachments, progress
- **New Document** — `POST /documents`
- **Route Document** — `POST /documents/{id}/route`
- **Follow-up** — `POST /documents/{id}/follow-up`
- **Close Document** — `POST /documents/{id}/close`
- **Notifications** — `GET /notifications/unread`

### DIRECTOR Pages
- **Dashboard** — `GET /dashboard` → count waiting for review
- **Inbox** — `GET /documents/inbox` → documents routed to them
- **Document Detail** — full view with Director remark field, history
- **Save Remark** — `PUT /documents/{id}/director-remark`
- **Return to DS** — `POST /documents/{id}/return-to-ds`
- **Notifications** — `GET /notifications/unread`

### HOD Pages
- **Dashboard** — `GET /dashboard` → department documents, pending assignment count
- **Inbox** — `GET /documents/inbox` → documents routed to their department
- **Document Detail** — with HOD remark field, assignment section
- **Save Remark** — `PUT /documents/{id}/hod-remark`
- **Assign Employee** — `POST /documents/{id}/assign` (pick from `GET /departments/{id}/employees`)
- **Notifications** — `GET /notifications/unread`

### EMPLOYEE Pages
- **Dashboard** — `GET /dashboard` → active assignments
- **Inbox** — `GET /documents/inbox` → assigned documents
- **Document Detail** — view-only for remarks and history, progress section
- **Submit Progress** — `POST /documents/{id}/progress`
- **Upload Attachment** — `POST /documents/{id}/attachments`
- **View Progress History** — `GET /documents/{id}/progress`
- **Notifications** — `GET /notifications/unread`

---

## 22.8 Handling Errors in the UI

Every API call can fail. Always wrap service calls in try/except.

```python
from api_client import (
    UnauthorizedError, ForbiddenError,
    NotFoundError, ConflictError, APIError
)

try:
    result = document_service.route_to_director(doc_id=1, director_user_id=2)
    show_success("Document sent to Director.")

except UnauthorizedError:
    # Token expired — force re-login
    show_login_page()

except ForbiddenError:
    # Wrong role
    show_error("You do not have permission to do this.")

except ConflictError as e:
    # e.g. document already closed
    show_error(str(e))

except APIError as e:
    # All other API errors
    show_error(str(e))

except Exception as e:
    # Network error, server down, etc.
    show_error(f"Cannot connect to server: {str(e)}")
```

---

## 22.9 File Download

To download an attachment:

```python
import requests
from api_client import api_client
from config import API_BASE_URL

def download_attachment(attachment_id: int, save_path: str):
    url = f"{API_BASE_URL}/attachments/{attachment_id}/download"
    headers = {"Authorization": f"Bearer {api_client._token}"}

    response = requests.get(url, headers=headers, stream=True)

    if response.status_code == 200:
        with open(save_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
    else:
        raise Exception("Download failed.")
```

---

## 22.10 Polling for Notifications

The frontend should periodically check for new notifications and update the notification badge.

```python
import threading
import time
from services.notification_service import notification_service

class NotificationPoller:

    def __init__(self, on_new_notifications):
        self._callback   = on_new_notifications
        self._running    = False
        self._thread     = None
        self.POLL_EVERY  = 30   # seconds

    def start(self):
        self._running = True
        self._thread  = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def _poll_loop(self):
        while self._running:
            try:
                unread = notification_service.get_unread()
                if unread:
                    self._callback(unread)
            except Exception:
                pass   # Server down — silently retry
            time.sleep(self.POLL_EVERY)

# Usage — start polling after login
poller = NotificationPoller(on_new_notifications=self.update_notification_badge)
poller.start()
```

---

## 22.11 Date Format

The API expects and returns dates in **ISO 8601 format**:

```text
Date only:   "2026-08-15"          (YYYY-MM-DD)
DateTime:    "2026-08-15T10:30:00" (YYYY-MM-DDTHH:MM:SS)
```

In Python:

```python
from datetime import date, datetime

# Sending a date to the API
"received_date": date.today().isoformat()   # "2026-08-15"

# Parsing a datetime from the API
created_at = datetime.fromisoformat(doc["created_at"])
```

---

## 22.12 Reference Number Display

Every document has a `reference_no` like `CDTRS-2026-0001`. Use this as the human-readable identifier in all UI labels, tables, and search fields. The `doc_id` (integer) is used in API URLs but should not be shown to users directly.

---

## 22.13 Document Status Display

Map `status` values to user-friendly labels:

```python
STATUS_LABELS = {
    "RECEIVED":                  "Received",
    "UNDER_DIRECTOR_REVIEW":     "Under Director Review",
    "DIRECTOR_REVIEW_COMPLETED": "Director Review Completed",
    "UNDER_HOD_PROCESSING":      "Under HOD Processing",
    "ASSIGNED_FOR_EXECUTION":    "Assigned to Employee",
    "IN_PROGRESS":               "In Progress",
    "PROGRESS_UPDATED":          "Progress Updated",
    "REVIEW_COMPLETED":          "Review Completed",
    "CLOSED":                    "Closed",
}

display = STATUS_LABELS.get(doc["status"], doc["status"])
```

---

## 22.14 Priority Display and Colour Coding

```python
PRIORITY_COLOURS = {
    "HIGH":   "#E53935",   # Red
    "MEDIUM": "#FB8C00",   # Orange
    "LOW":    "#43A047",   # Green
}
```

---

## 22.15 Summary — Things the Frontend Developer Must NOT Do

| ❌ Do NOT | ✅ Do Instead |
|---|---|
| Connect to PostgreSQL directly | Call the REST API |
| Store the token in a file on disk | Keep it in memory (app state) |
| Call `api_client` from a Page | Call a Service from a Page |
| Hardcode the API URL in pages | Use `config.py → API_BASE_URL` |
| Send percentage for progress | Send only free-text `description` |
| Create a new document per workflow step | All steps use the same `doc_id` |
| Let Employee send progress to Director | DS must use `/follow-up` |
| Assume token never expires | Handle `401` by redirecting to login |
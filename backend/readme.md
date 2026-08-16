# CDTRS V2 — Backend

**Centralized Document Tracking and Routing System — Version 2**

```text
==================================================
CDTRS V2 — Live Backend Integration Details
==================================================

Backend Status:
  LIVE and publicly accessible via Render

API Base URL:
  https://cdtrs.onrender.com/api/v1

Swagger Documentation:
  https://cdtrs.onrender.com/docs

WebSocket Live Events URL:
  wss://cdtrs.onrender.com/api/v1/ws

Authentication Method:
  JWT Bearer Token

Login Endpoint:
  POST https://cdtrs.onrender.com/api/v1/auth/login

Authorization Header:
  Authorization: Bearer <access_token>

Test Accounts:
  - DS:                 username: ds_user          | password: cdtrs@ds
  - DIRECTOR:           username: director         | password: cdtrs@director
  - HOD (Finance):      username: hod_finance      | password: cdtrs@hod
  - HOD (Procurement):  username: hod_procurement  | password: cdtrs@hod
  - EMPLOYEE (Finance): username: emp_rahul        | password: cdtrs@emp
  - EMPLOYEE (Procure): username: emp_priya        | password: cdtrs@emp

Frontend Integration:
  - Use the API Base URL above for all REST API requests.
  - Connect to the WebSocket URL above for real-time live events.
  - Login first to obtain the JWT access token.
  - Include the JWT token in the Authorization header for protected endpoints.

Example Header:
  Authorization: Bearer <access_token>

Role-Based Scoping:
  DS, DIRECTOR, HOD (Finance / Procurement), EMPLOYEE

Documentation:
  Full frontend integration code examples, service layer
  templates, and error handling patterns are documented in:
  backend/readme.md — Section 22
==================================================
```

---

# 1. Backend Architecture & File Structure

The CDTRS V2 backend strictly adheres to a **5-file modular architecture**:

```text
backend/
│
├── database.py        ← PostgreSQL connection, SQLAlchemy session, cloud dialect normalization
├── models.py          ← All 17 database tables & ORM models (V2 consolidated specification)
├── schemas.py         ← All Pydantic v2 request/response validation schemas
├── crud.py            ← All database operations, OCR, routing AI, reminders, and live event manager
├── main.py            ← FastAPI app, REST endpoints, WebSocket event stream, CORS, and auth guards
│
├── requirements.txt   ← Python package dependencies
├── .env.example       ← Environment variable template (copy to .env)
└── README.md          ← This file (comprehensive technical guide)
```

### Module Responsibilities Flow

```text
database.py
     ↓  Establishes PostgreSQL connection & session generator
models.py
     ↓  Defines 17 database tables, enums & relational mappings
crud.py
     ↓  Handles queries, mutations, OCR engine, routing AI, reminders, & WebSocket bus
schemas.py
     ↓  Validates request payloads and formats JSON responses (Pydantic v2)
main.py
     ↓  Exposes REST endpoints, WebSocket stream, role guards, and file handlers
```

---

# 2. Technologies Used

| Technology | Purpose |
|---|---|
| **Python 3.10+** | Backend programming language |
| **FastAPI** | High-performance async REST API & WebSocket framework. Auto-generates interactive Swagger & OpenAPI documentation. |
| **Uvicorn** | Production-ready ASGI server with hot-reload for development. |
| **SQLAlchemy 2.x** | Object-Relational Mapper (ORM) for PostgreSQL. |
| **PostgreSQL 14–16** | Robust relational database. Tested on local PostgreSQL, Render PostgreSQL, and Neon.tech. |
| **Pydantic v2** | Request validation and response serialization with strong type enforcement. |
| **bcrypt** | Cryptographic password hashing (salt + hash). |
| **python-jose[cryptography]** | Generates and verifies HMAC-SHA256 JWT bearer tokens. |
| **python-multipart** | Enables `multipart/form-data` uploads for physical scan documents and progress attachments. |
| **python-dotenv** | Loads `.env` configuration securely into environment variables. |

---

# 3. Installation and Local Setup

### Step 1 — Prerequisites
- Python 3.10 or higher
- PostgreSQL 14, 15, or 16 installed and running
- `pip` package manager

### Step 2 — Install Python Dependencies
```bash
cd backend
pip install -r requirements.txt
```

### Step 3 — Create Local Database
Open `psql` or pgAdmin:
```sql
CREATE DATABASE cdtrs;
```
*(SQLAlchemy automatically creates all 17 tables on the first server startup).*

### Step 4 — Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
copy .env.example .env
```
Edit `.env`:
```text
DATABASE_URL=postgresql+psycopg2://postgres:YOUR_PASSWORD@localhost:5432/cdtrs
SECRET_KEY=cdtrs-super-secret-key-change-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=60
UPLOAD_DIR=./uploads
SEED_DB=true
```

### Step 5 — Start Local Server
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

---

# 4. Environment Variables Explained

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg2://postgres:password@localhost:5432/cdtrs` | PostgreSQL connection string. Supports `postgres://`, `postgresql://`, and `postgresql+psycopg2://` formats automatically. |
| `SECRET_KEY` | `cdtrs-super-secret-key...` | Cryptographic secret for signing JWT tokens. Change in production! |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | JWT token validity lifetime (in minutes). |
| `UPLOAD_DIR` | `./uploads` | Storage directory for original documents and progress attachments. |
| `SEED_DB` | `false` | When `true`, automatically inserts initial test accounts and departments on startup. |

---

# 5. Core Architectural Principles (V2)

1. **Document-Centric Single Canonical Record:** There is only one document record (`documents.doc_id`). No separate DirectorDocument or HODDocument copies.
2. **Routing $\neq$ Assignment:** DS decides where a document goes (`document_routes`). HOD delegates work to staff (`work_assignments`).
3. **Suggestion $\neq$ Routing:** OCR and Routing Intelligence recommend departments and employees, but DS explicitly confirms all routes.
4. **Director Remarks are Independent of Return:** Saving a Director remark (`PUT /director-remark`) is separate from the workflow transition of returning to DS (`POST /return-to-ds`).
5. **HOD Remarks are Independent of Assignment:** HOD can save remarks independently of assigning employees.
6. **Progress Updates are Append-Only:** Employee progress entries are never overwritten; full audit history is preserved.
7. **Strict Scope Isolation:** Backend enforces role and department filters in SQL queries. Finance HOD cannot view Procurement documents (returns `403`/`404`).
8. **Real-Time Event Driven:** WebSockets broadcast workflow transitions so PySide6 screens update automatically without manual refresh buttons.
9. **Optimistic Concurrency Control:** `version` column prevents concurrent overwrite conflicts (`409 Conflict`).
10. **Closed Means Closed:** Once closed by DS, normal workflow mutations are rejected.

---

# 6. Database Design (17 Tables & Enums)

## 6.1 Enums (Controlled Vocabulary)

### `UserRole`
- `DS` — Director Secretary (Document Intake, Routing, Follow-up, Closure).
- `DIRECTOR` — The Director (Review, Remarks, Return to DS).
- `HOD` — Head of Department (Department Remarks, Employee Assignment).
- `EMPLOYEE` — Staff member (Task execution, Progress updates, File uploads).

### `DocumentStatus` (User-Facing Status)
- `RECEIVED` — Registered by DS.
- `UNDER_DIRECTOR_REVIEW` — Sent to Director for review.
- `DIRECTOR_REVIEW_COMPLETED` — Returned to DS by Director.
- `UNDER_HOD_PROCESSING` — Routed to Department HOD.
- `ASSIGNED_FOR_EXECUTION` — Assigned to Employee by HOD.
- `IN_PROGRESS` — Employee submitted progress.
- `PROGRESS_UPDATED` — Follow-up forwarded to Director.
- `REVIEW_COMPLETED` — Director completed follow-up review.
- `CLOSED` — Permanently closed by DS.

### `WorkflowStage` (Internal Stage)
- `DS`, `DIRECTOR`, `HOD`, `EMPLOYEE`, `CLOSED`.

### `Priority`
- `HIGH`, `MEDIUM`, `LOW`.

### `RouteType`
- `INITIAL_DIRECTOR_REVIEW`, `RETURN_TO_DS`, `POST_REVIEW_TO_HOD`, `POST_REVIEW_TO_EMPLOYEE`, `FOLLOW_UP_TO_DIRECTOR`.

### `SourceType`
- `OUTLOOK`, `GOVERNMENT_MAIL`, `MANUAL_UPLOAD`, `OTHER_APPROVED_SOURCE`.

### `AttachmentType`
- `ORIGINAL`, `EMAIL_ATTACHMENT`, `SUPPORTING_DOCUMENT`, `PROGRESS_ATTACHMENT`.

### `OCRStatus`
- `NONE`, `PENDING`, `PROCESSING`, `COMPLETED`, `FAILED`.

### `RoutingSource`
- `DOCUMENT_CONTENT`, `DIRECTOR_REMARK`, `SOURCE_METADATA`, `MANUAL`.

---

## 6.2 Table Specifications

### 1. `departments`
- `id` (Integer, PK)
- `name` (String(100), Unique, Required)
- `code` (String(20), Unique, Optional, e.g. `FIN`, `PROC`, `ADMIN`)
- `is_active` (Boolean, default `true`)
- `created_at` (DateTime)

### 2. `employees`
- `id` (Integer, PK)
- `employee_code` (String(50), Unique, Required, e.g. `EMP-001`)
- `full_name` (String(100), Required)
- `department_id` (Integer, FK $\to$ `departments.id`)
- `designation` (String(100), Required)
- `user_id` (Integer, FK $\to$ `users.id`, Nullable)
- `is_active` (Boolean, default `true`)

### 3. `users`
- `id` (Integer, PK)
- `username` (String(50), Unique, Indexed)
- `password_hash` (String(255), bcrypt hash)
- `full_name` (String(100))
- `role` (Enum `UserRole`)
- `department_id` (Integer, FK $\to$ `departments.id`, Nullable)
- `employee_id` (Integer, Nullable)
- `is_active` (Boolean, default `true`)
- `created_at` (DateTime), `updated_at` (DateTime)

### 4. `incoming_messages`
- `id` (Integer, PK)
- `source_type` (Enum `SourceType`)
- `external_message_id` (String(255), Unique, Indexed, de-duplication key)
- `sender_name` (String(150))
- `sender_email` (String(255))
- `subject` (String(500))
- `received_at` (DateTime)
- `body_reference` (Text)
- `has_attachments` (Boolean)
- `processing_status` (Enum `MessageProcessingStatus`)
- `created_at` (DateTime)

### 5. `documents`
- `doc_id` (Integer, PK)
- `reference_no` (String(50), Unique, Indexed, e.g. `CDTRS-2026-0001`)
- `title` (String(255))
- `description` (Text, Nullable)
- `received_date` (Date)
- `deadline` (Date, Nullable)
- `source` (String(255), Nullable)
- `mode` (String(50))
- `priority` (Enum `Priority`)
- `status` (Enum `DocumentStatus`)
- `current_stage` (Enum `WorkflowStage`)
- `current_owner_id` (Integer, FK $\to$ `users.id`, Nullable)
- `target_department_id` (Integer, FK $\to$ `departments.id`, Nullable)
- `created_by` (Integer, FK $\to$ `users.id`)
- `source_message_id` (Integer, FK $\to$ `incoming_messages.id`, Nullable)
- `ocr_status` (Enum `OCRStatus`)
- `version` (Integer, default 1, Optimistic Concurrency Control)
- `director_remark` (Text, latest remark)
- `hod_remark` (Text, latest remark)
- `created_at` (DateTime), `updated_at` (DateTime), `closed_at` (DateTime, Nullable)

### 6. `document_routes`
- `id` (Integer, PK)
- `document_id` (Integer, FK $\to$ `documents.doc_id`)
- `from_user_id` (Integer, FK $\to$ `users.id`)
- `to_user_id` (Integer, FK $\to$ `users.id`, Nullable)
- `to_department_id` (Integer, FK $\to$ `departments.id`, Nullable)
- `route_type` (Enum `RouteType`)
- `remarks` (Text, Nullable)
- `created_at` (DateTime)

### 7. `work_assignments`
- `id` (Integer, PK)
- `document_id` (Integer, FK $\to$ `documents.doc_id`)
- `assigned_by_user_id` (Integer, FK $\to$ `users.id`, HOD)
- `assigned_to_user_id` (Integer, FK $\to$ `users.id`, Employee)
- `instructions` (Text, Nullable)
- `is_active` (Boolean, default `true`)
- `assigned_at` (DateTime), `completed_at` (DateTime, Nullable)

### 8. `progress_updates`
- `id` (Integer, PK)
- `document_id` (Integer, FK $\to$ `documents.doc_id`)
- `submitted_by_user_id` (Integer, FK $\to$ `users.id`)
- `description` (Text, free-text progress)
- `created_at` (DateTime)

### 9. `attachments`
- `id` (Integer, PK)
- `document_id` (Integer, FK $\to$ `documents.doc_id`)
- `progress_update_id` (Integer, FK $\to$ `progress_updates.id`, Nullable)
- `uploaded_by_user_id` (Integer, FK $\to$ `users.id`)
- `file_name` (String(255))
- `storage_key` (String(500), relative path on server)
- `file_type` (String(100))
- `file_size` (BigInteger)
- `checksum` (String(64), SHA-256 integrity hash)
- `attachment_type` (Enum `AttachmentType`)
- `source_message_id` (Integer, FK $\to$ `incoming_messages.id`, Nullable)
- `created_at` (DateTime)

### 10. `document_remarks`
- `id` (Integer, PK)
- `document_id` (Integer, FK $\to$ `documents.doc_id`)
- `author_user_id` (Integer, FK $\to$ `users.id`)
- `role` (Enum `UserRole`)
- `remark_text` (Text)
- `remark_type` (Enum `RemarkType`: `DIRECTOR`, `HOD`)
- `created_at` (DateTime), `updated_at` (DateTime)

### 11. `document_ocr`
- `id` (Integer, PK)
- `document_id` (Integer, FK $\to$ `documents.doc_id`, Unique)
- `extracted_text` (Text)
- `ocr_status` (Enum `OCRStatus`)
- `ocr_engine` (String(100))
- `confidence` (Float)
- `processed_at` (DateTime, Nullable)
- `error_message` (Text, Nullable)

### 12. `document_extracted_fields`
- `id` (Integer, PK)
- `document_id` (Integer, FK $\to$ `documents.doc_id`)
- `field_name` (String(100), e.g. `TITLE`, `REFERENCE_NO`, `DEADLINE`, `PRIORITY`)
- `extracted_value` (Text)
- `confidence` (Float)
- `source_page` (Integer)
- `source_text` (Text)
- `verified_value` (Text, DS-verified value)
- `verified_by` (Integer, FK $\to$ `users.id`, Nullable)
- `verified_at` (DateTime, Nullable)

### 13. `routing_suggestions`
- `id` (Integer, PK)
- `document_id` (Integer, FK $\to$ `documents.doc_id`, Unique)
- `suggested_department_id` (Integer, FK $\to$ `departments.id`, Nullable)
- `suggested_employee_id` (Integer, FK $\to$ `users.id`, Nullable)
- `routing_confidence` (Float)
- `routing_reason` (Text)
- `routing_source` (Enum `RoutingSource`)
- `is_director_instruction` (Boolean, triggers alert banner for DS)
- `generated_at` (DateTime)
- `confirmed_by` (Integer, FK $\to$ `users.id`, Nullable)
- `confirmed_at` (DateTime, Nullable)

### 14. `reminders`
- `id` (Integer, PK)
- `document_id` (Integer, FK $\to$ `documents.doc_id`)
- `recipient_user_id` (Integer, FK $\to$ `users.id`)
- `reason` (Enum `ReminderReason`: `DUE_SOON`, `OVERDUE`, `ACTION_REQUIRED`)
- `due_at` (DateTime, Nullable)
- `sent_at` (DateTime)
- `is_read` (Boolean)
- `deduplication_key` (String(200), Unique, Indexed)

### 15. `workflow_history`
- `id` (Integer, PK)
- `document_id` (Integer, FK $\to$ `documents.doc_id`)
- `performed_by_user_id` (Integer, FK $\to$ `users.id`)
- `action` (String(150))
- `from_role` (String(50)), `to_role` (String(50))
- `details` (Text, Nullable)
- `created_at` (DateTime)

### 16. `audit_logs`
- `id` (Integer, PK)
- `user_id` (Integer, FK $\to$ `users.id`)
- `action` (String(100))
- `entity_type` (String(50)), `entity_id` (Integer)
- `description` (Text)
- `created_at` (DateTime)

### 17. `notifications`
- `id` (Integer, PK)
- `user_id` (Integer, FK $\to$ `users.id`)
- `document_id` (Integer, FK $\to$ `documents.doc_id`, Nullable)
- `workflow_event_id` (Integer, FK $\to$ `workflow_history.id`, Nullable)
- `title` (String(200)), `message` (Text)
- `is_read` (Boolean)
- `created_at` (DateTime)

---

# 7. Incoming Mail & Intake Pipeline

```text
Incoming Message / Scan
          ↓
De-duplication Check (external_message_id)
          ↓
SHA-256 Checksum Computed + Saved in Storage
          ↓
Canonical Document Created (status: RECEIVED, stage: DS, version: 1)
          ↓
Asynchronous OCR Pipeline Triggered
```

- **Endpoints:**
  - `GET /api/v1/intake` — List incoming mail items.
  - `POST /api/v1/intake/manual-upload` — Upload file + metadata directly into canonical document.
  - `POST /api/v1/intake/{id}/process` — Process pending intake item into a canonical document.

---

# 8. OCR Extraction & Verification Pipeline

1. **Extraction:** Extracts structured text (`TITLE`, `REFERENCE_NO`, `SOURCE`, `PRIORITY`, `DEADLINE`).
2. **Provenance:** Stores page numbers, confidence percentages, and supporting text snippets.
3. **Verification:** DS verifies or edits values via `POST /documents/{id}/verify-field`.
4. **Re-analysis Protection:** When re-running OCR (`POST /documents/{id}/reanalyze`), newly extracted values **never overwrite** DS-verified values.

---

# 9. Routing Intelligence & Advisory Suggestions

- **Director Instruction Detection:** Scans Director remarks. If the Director wrote *"Assign this to Rahul Sharma, Finance"*, the engine detects:
  - `suggested_department = Finance`
  - `suggested_employee = Rahul Sharma`
  - `confidence = 95%`
  - `is_director_instruction = true` (Triggers high-priority DS alert)
- **Advisory Only:** No route changes occur until DS explicitly calls `POST /documents/{id}/route`.

---

# 10. Reminders & Deadline Escalation

Escalation hierarchy:
```python
if active_employee_assigned:
    recipient = assigned_employee
elif target_department_exists:
    recipient = active_hod_of_department
else:
    recipient = ds_creator
```
- **Deduplication:** Unique key per document, user, reason, and date prevents repeated spam.
- **Endpoints:** `GET /api/v1/reminders`, `POST /api/v1/reminders/check`, `PATCH /api/v1/reminders/{id}/read`.

---

# 11. Real-Time Live Events (WebSocket)

PySide6 clients connect to the WebSocket endpoint for real-time push updates without manual polling or refresh buttons:

- **WebSocket URL:** `wss://cdtrs.onrender.com/api/v1/ws` (or `ws://localhost:8000/api/v1/ws`)
- **Event Types:**
  - `DOCUMENT_CREATED`
  - `DOCUMENT_ROUTED`
  - `REMARK_UPDATED`
  - `ASSIGNMENT_CREATED`
  - `PROGRESS_SUBMITTED`
  - `ATTACHMENT_ADDED`
  - `OCR_COMPLETED`
  - `DOCUMENT_CLOSED`
  - `NOTIFICATION_CREATED`
- **Fallback REST Endpoint:** `GET /api/v1/events/recent` (returns recent events for polling fallback).

---

# 12. Strict Scope & Multi-HOD Isolation

The backend enforces query-level scoping:

| Role | Permitted Visibility | Inaccessible Response |
|---|---|---|
| **DS** | All documents across intake, review, processing, and closure. | — |
| **DIRECTOR** | Documents routed to Director by DS and follow-ups. | `403 Forbidden` / `404 Not Found` |
| **HOD** | Documents routed to HOD's specific department. | `403 Forbidden` / `404 Not Found` |
| **EMPLOYEE** | Documents assigned or directly routed to employee. | `403 Forbidden` / `404 Not Found` |

---

# 13. Consolidated API Reference

### Authentication
| Method | Endpoint | Role | Description |
|---|---|---|---|
| POST | `/api/v1/auth/login` | Public | Login with username/password, returns JWT token |
| GET | `/api/v1/auth/me` | All | Get profile of logged-in user |
| POST | `/api/v1/auth/logout` | All | Logout (client discards token) |

### Intake & Mail
| Method | Endpoint | Role | Description |
|---|---|---|---|
| GET | `/api/v1/intake` | DS | List all incoming mail/intake items |
| POST | `/api/v1/intake/manual-upload` | DS | Upload document file + metadata |
| POST | `/api/v1/intake/{id}/process` | DS | Process intake item into canonical document |

### Documents
| Method | Endpoint | Role | Description |
|---|---|---|---|
| POST | `/api/v1/documents` | DS | Register new document |
| GET | `/api/v1/documents` | DS | Get all documents |
| GET | `/api/v1/documents/inbox` | All | Role-scoped inbox for current user |
| GET | `/api/v1/documents/{id}` | All | Get single document (Authorized) |
| POST | `/api/v1/documents/{id}/route` | DS | Route document to Director/HOD/Employee |
| PUT | `/api/v1/documents/{id}/director-remark` | DIRECTOR | Save/edit Director remark |
| POST | `/api/v1/documents/{id}/return-to-ds` | DIRECTOR | Return document to DS |
| PUT | `/api/v1/documents/{id}/hod-remark` | HOD | Save/edit HOD remark |
| POST | `/api/v1/documents/{id}/assign` | HOD | Assign employee to document |
| POST | `/api/v1/documents/{id}/progress` | EMPLOYEE | Submit progress update |
| GET | `/api/v1/documents/{id}/progress` | All | Get progress updates |
| POST | `/api/v1/documents/{id}/attachments` | All | Upload attachment file (Multipart) |
| GET | `/api/v1/documents/{id}/attachments` | All | List attachments for document |
| GET | `/api/v1/documents/{id}/remarks` | All | Get remark history |
| POST | `/api/v1/documents/{id}/follow-up` | DS | Forward progress follow-up to Director |
| GET | `/api/v1/documents/{id}/history` | All | Get workflow history |
| POST | `/api/v1/documents/{id}/close` | DS | Permanently close document |

### OCR & Intelligence
| Method | Endpoint | Role | Description |
|---|---|---|---|
| POST | `/api/v1/documents/{id}/process-ocr` | DS | Trigger OCR processing |
| GET | `/api/v1/documents/{id}/ocr` | All | Get OCR text & structured fields |
| POST | `/api/v1/documents/{id}/verify-field` | DS | Verify/edit extracted field |
| POST | `/api/v1/documents/{id}/reanalyze` | DS | Re-run OCR preserving verified fields |
| POST | `/api/v1/documents/{id}/analyze-routing` | DS | Generate routing suggestion |
| GET | `/api/v1/documents/{id}/routing-suggestion` | All | Get current routing suggestion & confidence |

### Attachments
| Method | Endpoint | Role | Description |
|---|---|---|---|
| GET | `/api/v1/attachments/{id}` | All | Get attachment metadata |
| GET | `/api/v1/attachments/{id}/download` | All | Authorized streaming file download |

### Reminders & Notifications
| Method | Endpoint | Role | Description |
|---|---|---|---|
| GET | `/api/v1/reminders` | All | Get user action/deadline reminders |
| POST | `/api/v1/reminders/check` | DS | Trigger reminder scan & escalation |
| PATCH | `/api/v1/reminders/{id}/read` | All | Mark reminder as read |
| GET | `/api/v1/notifications` | All | Get all notifications |
| GET | `/api/v1/notifications/unread` | All | Get unread notifications |
| PATCH | `/api/v1/notifications/{id}/read` | All | Mark notification as read |
| PATCH | `/api/v1/notifications/read-all` | All | Mark all notifications as read |

### Dashboard & Events
| Method | Endpoint | Role | Description |
|---|---|---|---|
| GET | `/api/v1/dashboard` | All | Get role-specific dashboard metrics |
| WebSocket | `/api/v1/ws` | All | Real-time live event stream |
| GET | `/api/v1/events/recent` | All | Polling fallback for recent events |

---

# 14. How to Test Using Swagger UI (Step-by-Step)

1. Open **`https://cdtrs.onrender.com/docs`** (or `http://localhost:8000/docs`).
2. Go to **`POST /api/v1/auth/login`**, click **Try it out**, and enter:
   ```json
   {
     "username": "ds_user",
     "password": "cdtrs@ds"
   }
   ```
3. Click **Execute** and copy the `access_token` string from the response body.
4. Click the green **Authorize 🔒** button at the top right of Swagger UI, paste the token, and click **Authorize**.
5. All endpoints will now automatically include the bearer token in headers.

---

# 15. Complete End-to-End Workflow Test Sequence

```text
1. Login as DS (ds_user / cdtrs@ds) -> Authorize
2. Create document -> POST /api/v1/documents
3. View inbox -> GET /api/v1/documents/inbox
4. Trigger OCR -> POST /api/v1/documents/1/process-ocr
5. Verify fields -> POST /api/v1/documents/1/verify-field (e.g. TITLE = "Verified Title")
6. Generate routing suggestion -> POST /api/v1/documents/1/analyze-routing
7. Route to Director -> POST /api/v1/documents/1/route (route_type: INITIAL_DIRECTOR_REVIEW, to_user_id: 2)

8. Login as Director (director / cdtrs@director) -> Authorize
9. View Director inbox -> GET /api/v1/documents/inbox
10. Save Director remark -> PUT /api/v1/documents/1/director-remark (director_remark: "Assign to Rahul Sharma, Finance")
11. Return to DS -> POST /api/v1/documents/1/return-to-ds

12. Login as DS -> Authorize
13. View routing suggestion -> GET /api/v1/documents/1/routing-suggestion (Flags is_director_instruction=true)
14. Route to Finance HOD -> POST /api/v1/documents/1/route (route_type: POST_REVIEW_TO_HOD, to_user_id: 3, to_department_id: 2)

15. Login as Finance HOD (hod_finance / cdtrs@hod) -> Authorize
16. View HOD inbox -> GET /api/v1/documents/inbox
17. Save HOD remark -> PUT /api/v1/documents/1/hod-remark
18. Assign Rahul -> POST /api/v1/documents/1/assign (assigned_to_user_id: 5)

19. Login as Rahul (emp_rahul / cdtrs@emp) -> Authorize
20. View Employee inbox -> GET /api/v1/documents/inbox
21. Submit progress -> POST /api/v1/documents/1/progress (description: "Verification complete.")
22. Upload attachment -> POST /api/v1/documents/1/attachments

23. Login as DS -> Authorize
24. Forward follow-up to Director -> POST /api/v1/documents/1/follow-up

25. Login as Director -> Authorize
26. Save final remark -> PUT /api/v1/documents/1/director-remark
27. Return to DS -> POST /api/v1/documents/1/return-to-ds

28. Login as DS -> Authorize
29. Close document -> POST /api/v1/documents/1/close
30. View complete workflow history -> GET /api/v1/documents/1/history
```

---

# 16. Test Accounts (Seed Data)

| Role | Department | Username | Password |
|---|---|---|---|
| **DS** | Administration | `ds_user` | `cdtrs@ds` |
| **DIRECTOR** | Executive | `director` | `cdtrs@director` |
| **HOD** | Finance | `hod_finance` | `cdtrs@hod` |
| **HOD** | Procurement | `hod_procurement` | `cdtrs@hod` |
| **EMPLOYEE** | Finance | `emp_rahul` | `cdtrs@emp` |
| **EMPLOYEE** | Procurement | `emp_priya` | `cdtrs@emp` |

---

# 17. Frontend Developer Integration Guide (PySide6)

### `config.py`
```python
# Live Cloud Backend URL
API_BASE_URL = "https://cdtrs.onrender.com/api/v1"
WS_BASE_URL  = "wss://cdtrs.onrender.com/api/v1/ws"

# Local Fallback
# API_BASE_URL = "http://localhost:8000/api/v1"
# WS_BASE_URL  = "ws://localhost:8000/api/v1/ws"
```

### `api_client.py`
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
        r = requests.get(f"{API_BASE_URL}{endpoint}", headers=self._headers(), params=params)
        return self._handle(r)

    def post(self, endpoint: str, body: dict = None):
        r = requests.post(f"{API_BASE_URL}{endpoint}", headers=self._headers(), json=body)
        return self._handle(r)

    def put(self, endpoint: str, body: dict = None):
        r = requests.put(f"{API_BASE_URL}{endpoint}", headers=self._headers(), json=body)
        return self._handle(r)

    def patch(self, endpoint: str, body: dict = None):
        r = requests.patch(f"{API_BASE_URL}{endpoint}", headers=self._headers(), json=body)
        return self._handle(r)

    def upload_file(self, endpoint: str, file_path: str, data: dict = None):
        with open(file_path, "rb") as f:
            files = {"file": (file_path.split("/")[-1], f)}
            headers = {}
            if self._token:
                headers["Authorization"] = f"Bearer {self._token}"
            r = requests.post(f"{API_BASE_URL}{endpoint}", headers=headers, files=files, data=data or {})
        return self._handle(r)

    def _handle(self, response):
        if response.status_code == 401:
            raise UnauthorizedError("Session expired. Please log in again.")
        if response.status_code == 403:
            raise ForbiddenError("Permission denied.")
        if response.status_code == 404:
            raise NotFoundError("Resource not found.")
        if response.status_code == 409:
            raise ConflictError(response.json().get("detail", "Workflow/concurrency conflict."))
        if response.status_code >= 400:
            raise APIError(response.json().get("detail", "API Error."))
        return response.json()

class APIError(Exception): pass
class UnauthorizedError(APIError): pass
class ForbiddenError(APIError): pass
class NotFoundError(APIError): pass
class ConflictError(APIError): pass

api_client = APIClient()
```

### WebSocket Real-Time Listener (`event_listener.py`)
```python
import json
import threading
import websocket
from config import WS_BASE_URL

class RealtimeEventListener:
    def __init__(self, on_event_callback):
        self.callback = on_event_callback
        self.ws = None
        self.thread = None

    def start(self):
        def run():
            self.ws = websocket.WebSocketApp(
                WS_BASE_URL,
                on_message=lambda ws, msg: self.callback(json.loads(msg)),
                on_error=lambda ws, err: print(f"WS Error: {err}")
            )
            self.ws.run_forever()

        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()

    def stop(self):
        if self.ws:
            self.ws.close()
```

---
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

# 1. Backend File Structure

The backend strictly follows a **5-file modular architecture**:

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
└── README.md          ← Exhaustive technical documentation
```

### Module Responsibilities

```text
database.py  →  PostgreSQL connection & session management
     ↓
models.py    →  Database table definitions & relationships (ORM)
     ↓
crud.py      →  Database operations, OCR, routing AI, reminders, live event bus
     ↓
schemas.py   →  Request/response data validation (Pydantic v2)
     ↓
main.py      →  FastAPI REST endpoints & WebSocket live stream
```

---

# 2. Technologies Used

| Technology | Version | Purpose |
|---|---|---|
| **Python** | 3.10+ | Backend programming language |
| **FastAPI** | 0.111+ | High-performance async REST & WebSocket API framework |
| **Uvicorn** | 0.29+ | ASGI production server |
| **SQLAlchemy** | 2.0+ | Relational ORM for PostgreSQL |
| **PostgreSQL** | 14–16 | Relational database (Render / Neon / Local) |
| **Pydantic** | 2.7+ | Request/response schema validation |
| **bcrypt** | 4.0+ | Secure password hashing |
| **python-jose[cryptography]** | 3.3+ | JWT token creation & cryptographic validation |
| **python-multipart** | 0.0.9+ | Multipart/form-data file upload support |
| **python-dotenv** | 1.0+ | Environment configuration management |

---

# 3. Installation and Setup

### Step 1 — Prerequisites
- Python 3.10 or higher
- PostgreSQL 14, 15, or 16
- `pip`

### Step 2 — Install Dependencies
```bash
cd backend
pip install -r requirements.txt
```

### Step 3 — Configure Environment
```bash
copy .env.example .env
```
Edit `.env` and configure your database credentials:
```text
DATABASE_URL=postgresql+psycopg2://postgres:YOUR_PASSWORD@localhost:5432/cdtrs
SECRET_KEY=your-random-secret-key
SEED_DB=true
```

### Step 4 — Run Local Development Server
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

---

# 4. Core Architecture Principles

1. **Document-Centric Single Canonical Record:** One `document_id` survives the entire lifecycle. No separate DirectorDocument or HODDocument copies.
2. **Routing is NOT Assignment:** DS routes documents to Director, HOD, or eligible Employee. HOD assigns specific employees within their department.
3. **Suggestion is NOT Routing:** OCR and Routing Intelligence recommend departments/employees with confidence scores, but DS confirms the route.
4. **Director Remarks are Independent:** Saving a remark (`PUT /director-remark`) does NOT trigger a route. Returning to DS (`POST /return-to-ds`) is an explicit workflow action.
5. **HOD Remarks are Independent:** HOD can save remarks independently of assigning employees.
6. **Progress Updates are Append-Only:** Employee progress entries are never overwritten; full audit history is preserved.
7. **Strict Scope Isolation:** Backend enforces role and department filters in SQL queries. Finance HOD cannot see Procurement documents (returns `403`/`404`).
8. **Real-Time Event Driven:** WebSockets broadcast workflow transitions so PySide6 screens update automatically without manual refresh buttons.
9. **Optimistic Concurrency Control:** `version` column prevents concurrent overwrite conflicts (`409 Conflict`).
10. **Closed Means Closed:** Once closed by DS, normal workflow mutations are rejected.

---

# 5. Database Schema & Models

CDTRS V2 models 17 distinct entities in `models.py`:

```
+-------------------+       +-----------------------+
|  IncomingMessage  | ----> |       Document        |
+-------------------+       +-----------------------+
                                |  |  |  |  |  |  |
            +-------------------+  |  |  |  |  |  +-------------------+
            |                      |  |  |  |  |                      |
            v                      v  |  |  |  v                      v
     +--------------+   +-------------+  |  | +---------------+  +-------------+
     | DocumentRoute|   |WorkAssignmnt|  |  | |ProgressUpdate |  | DocumentOCR |
     +--------------+   +-------------+  |  | +---------------+  +-------------+
                                         |  |         |                 |
                                         |  |         v                 v
                                         |  |   +------------+   +-------------+
                                         |  |   | Attachment |   |ExtractedFlds|
                                         |  |   +------------+   +-------------+
                                         |  |
                                         v  v
                           +----------------------+  +---------------------+
                           |  RoutingSuggestion   |  |   DocumentRemark    |
                           +----------------------+  +---------------------+
```

### Table Overview

| Table | Description |
|---|---|
| `departments` | Organization departments (`Administration`, `Finance`, `Procurement`, `Technical`). |
| `employees` | Employee records linked to departments and user accounts. |
| `users` | User accounts with role (`DS`, `DIRECTOR`, `HOD`, `EMPLOYEE`). |
| `incoming_messages` | Mail intake items, source type, sender, external ID de-duplication. |
| `documents` | Canonical document table with lifecycle status, stage, OCR status, and version. |
| `document_routes` | Audit log of all DS routing actions. |
| `work_assignments` | HOD to Employee work assignments. |
| `progress_updates` | Employee free-text progress entries. |
| `attachments` | File metadata, storage keys, SHA-256 checksums, and attachment types. |
| `document_remarks` | Full historical audit trail of Director and HOD remarks. |
| `document_ocr` | Full OCR text artifact, engine, confidence, and status. |
| `document_extracted_fields` | Structured extracted key-values with DS-verification provenance. |
| `routing_suggestions` | Advisory routing AI with confidence score, reasoning, and Director instruction alert. |
| `reminders` | Action/deadline escalation reminders with recipient fallback logic. |
| `workflow_history` | User-visible document event timeline. |
| `audit_logs` | System, security, and authentication audit logs. |
| `notifications` | User notifications with read/unread tracking. |

---

# 6. Incoming Mail & Intake Pipeline

Incoming messages from Outlook, Government Mail, or Manual Upload are ingested into `incoming_messages`:

```text
Incoming Mail / Upload
         ↓
De-duplication Check (external_message_id)
         ↓
Secure File Store + SHA-256 Checksum
         ↓
Canonical Document Created (status: RECEIVED, stage: DS)
         ↓
Asynchronous OCR Pipeline Triggered
```

### Endpoints
- `GET /api/v1/intake` — List all incoming intake items.
- `POST /api/v1/intake/manual-upload` — Upload file + metadata directly into canonical document.
- `POST /api/v1/intake/{id}/process` — Convert pending mail item into a tracked canonical document.

---

# 7. OCR & Structured Extraction Pipeline

OCR extracts text, identifies fields, and preserves DS-verified values:

1. **Extraction:** Extracts `TITLE`, `REFERENCE_NO`, `SOURCE`, `PRIORITY`, and `DEADLINE`.
2. **Provenance:** Each field stores raw extracted value, confidence score, source page, and source text snippet.
3. **Verification:** When DS verifies/edits a field (`POST /documents/{id}/verify-field`), `verified_value`, `verified_by`, and `verified_at` are recorded.
4. **Re-analysis Protection:** When re-running OCR (`POST /documents/{id}/reanalyze`), newly extracted values **never overwrite** DS-verified values.

### Endpoints
- `POST /api/v1/documents/{id}/process-ocr` — Trigger OCR extraction.
- `GET /api/v1/documents/{id}/ocr` — Get full OCR text and extracted fields.
- `POST /api/v1/documents/{id}/verify-field` — DS verifies or edits a structured field.
- `POST /api/v1/documents/{id}/reanalyze` — Re-run OCR without overwriting verified fields.

---

# 8. Routing Intelligence & Advisory Suggestions

The backend analyzes OCR text, metadata, and Director remarks to generate advisory routing suggestions:

- **Explicit Director Instruction Detection:** If Director remark contains *"Assign this to Rahul Sharma, Finance"*, the engine detects:
  - `suggested_department = Finance`
  - `suggested_employee = Rahul Sharma`
  - `routing_confidence = 95%`
  - `is_director_instruction = true` (Triggers high-priority alert on DS UI)
- **Content Keyword Matching:** Fallback matching on document title and body against department directories.
- **Authority Rule:** Suggestions are purely advisory. No document routes until DS explicitly calls `POST /documents/{id}/route`.

### Endpoints
- `POST /api/v1/documents/{id}/analyze-routing` — Generate or recalculate routing suggestions.
- `GET /api/v1/documents/{id}/routing-suggestion` — Retrieve current routing suggestion and confidence.

---

# 9. Reminders & Deadline Escalation

The reminder engine scans active documents and escalates action reminders:

```python
if active_employee_assigned:
    recipient = assigned_employee
elif target_department_exists:
    recipient = active_hod_of_department
else:
    recipient = ds_creator
```

### Endpoints
- `GET /api/v1/reminders` — List action/deadline reminders for logged-in user.
- `POST /api/v1/reminders/check` — Trigger reminder scan and escalation.
- `PATCH /api/v1/reminders/{id}/read` — Mark reminder as read.

---

# 10. Real-Time Live Events (WebSocket)

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

# 11. Strict Scope & Multi-HOD Isolation

The backend enforces query-level scoping:

| Role | Permitted Visibility | Inaccessible Response |
|---|---|---|
| **DS** | All documents across intake, review, processing, and closure. | — |
| **DIRECTOR** | Documents routed to Director by DS and follow-ups. | `403 Forbidden` / `404 Not Found` |
| **HOD** | Documents routed to HOD's specific department. | `403 Forbidden` / `404 Not Found` |
| **EMPLOYEE** | Documents assigned or directly routed to employee. | `403 Forbidden` / `404 Not Found` |

### Two-HOD Cross-Access Test
- `hod_finance` logging in sees only Finance documents.
- `hod_procurement` logging in sees only Procurement documents.
- Requesting another department's document ID returns `403 Forbidden`.

---

# 12. Complete Workflow Lifecycle Walkthrough

```text
1. Intake: DS receives document (POST /intake/manual-upload)
      ↓
2. OCR: Extracted text & fields generated (POST /documents/{id}/process-ocr)
      ↓
3. Routing Intelligence: Suggestion generated (POST /documents/{id}/analyze-routing)
      ↓
4. Initial Route: DS routes to Director (POST /documents/{id}/route)
      ↓
5. Director Review: Director saves remark (PUT /documents/{id}/director-remark)
      ↓
6. Return to DS: Director returns document (POST /documents/{id}/return-to-ds)
      ↓
7. Post-Review Route: DS routes to HOD (POST /documents/{id}/route)
      ↓
8. HOD Assignment: HOD assigns Employee (POST /documents/{id}/assign)
      ↓
9. Progress: Employee submits multiple updates (POST /documents/{id}/progress)
   Attachments: Employee uploads supporting files (POST /documents/{id}/attachments)
      ↓
10. Follow-up: DS forwards progress to Director (POST /documents/{id}/follow-up)
      ↓
11. Final Review: Director returns to DS (POST /documents/{id}/return-to-ds)
      ↓
12. Closure: DS permanently closes document (POST /documents/{id}/close)
```

---

# 13. Consolidated API Reference

### Authentication
- `POST /api/v1/auth/login` — Authenticate and receive JWT token.
- `GET /api/v1/auth/me` — Get current logged-in user profile.
- `POST /api/v1/auth/logout` — Logout.

### Intake
- `GET /api/v1/intake` — List incoming mail items.
- `POST /api/v1/intake/manual-upload` — Manual file upload creating document.
- `POST /api/v1/intake/{id}/process` — Process mail item into document.

### Documents
- `POST /api/v1/documents` — Register new canonical document.
- `GET /api/v1/documents` — List all documents (DS).
- `GET /api/v1/documents/inbox` — Role-scoped inbox for active user.
- `GET /api/v1/documents/{id}` — Get single document (Authorized).
- `POST /api/v1/documents/{id}/route` — Route document to Director/HOD/Employee.
- `PUT /api/v1/documents/{id}/director-remark` — Save/edit Director remark.
- `POST /api/v1/documents/{id}/return-to-ds` — Return document to DS.
- `PUT /api/v1/documents/{id}/hod-remark` — Save/edit HOD remark.
- `POST /api/v1/documents/{id}/assign` — Assign employee (HOD).
- `POST /api/v1/documents/{id}/progress` — Submit progress update (Employee).
- `GET /api/v1/documents/{id}/progress` — List progress updates.
- `POST /api/v1/documents/{id}/attachments` — Upload attachment (Multipart).
- `GET /api/v1/documents/{id}/attachments` — List attachments.
- `GET /api/v1/documents/{id}/remarks` — List remark history.
- `POST /api/v1/documents/{id}/follow-up` — Forward follow-up to Director (DS).
- `GET /api/v1/documents/{id}/history` — Document workflow history.
- `POST /api/v1/documents/{id}/close` — Close document (DS).

### OCR & Intelligence
- `POST /api/v1/documents/{id}/process-ocr` — Trigger OCR extraction.
- `GET /api/v1/documents/{id}/ocr` — Get OCR text & structured fields.
- `POST /api/v1/documents/{id}/verify-field` — Verify/edit extracted field.
- `POST /api/v1/documents/{id}/reanalyze` — Re-analyze without overwriting verified fields.
- `POST /api/v1/documents/{id}/analyze-routing` — Generate routing suggestion.
- `GET /api/v1/documents/{id}/routing-suggestion` — Get routing suggestion & confidence.

### Attachments
- `GET /api/v1/attachments/{id}` — Attachment metadata.
- `GET /api/v1/attachments/{id}/download` — Authorized streaming file download.

### Reminders & Notifications
- `GET /api/v1/reminders` — User action reminders.
- `POST /api/v1/reminders/check` — Trigger reminder scan.
- `PATCH /api/v1/reminders/{id}/read` — Mark reminder as read.
- `GET /api/v1/notifications` — All notifications.
- `GET /api/v1/notifications/unread` — Unread notifications.
- `PATCH /api/v1/notifications/{id}/read` — Mark notification as read.
- `PATCH /api/v1/notifications/read-all` — Mark all notifications as read.

### Dashboard & Events
- `GET /api/v1/dashboard` — Role-specific metrics.
- `WebSocket /api/v1/ws` — Real-time event stream.
- `GET /api/v1/events/recent` — Recent events list.

---

# 14. How to Test Using Swagger UI

1. Open **`https://cdtrs.onrender.com/docs`** (or `http://localhost:8000/docs`).
2. Go to **`POST /api/v1/auth/login`**, click **Try it out**, and enter:
   ```json
   {
     "username": "ds_user",
     "password": "cdtrs@ds"
   }
   ```
3. Copy the `access_token` string from the response.
4. Click the green **Authorize 🔒** button at the top right, paste the token, and click **Authorize**.
5. Test any endpoint (e.g. `POST /api/v1/documents`, `GET /api/v1/documents/inbox`).

---

# 15. Frontend Developer Integration Guide (PySide6)

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

# 16. Test Credentials

Seed data includes 2 distinct HODs and multiple employees:

| Role | Department | Username | Password | Notes |
|---|---|---|---|---|
| `DS` | Administration | `ds_user` | `cdtrs@ds` | Document intake, routing, closure |
| `DIRECTOR` | Executive | `director` | `cdtrs@director` | Document review, remarks, return to DS |
| `HOD` | Finance | `hod_finance` | `cdtrs@hod` | Finance remarks, assignment |
| `HOD` | Procurement | `hod_procurement` | `cdtrs@hod` | Procurement remarks, assignment |
| `EMPLOYEE` | Finance | `emp_rahul` | `cdtrs@emp` | Rahul Sharma (Finance) |
| `EMPLOYEE` | Procurement | `emp_priya` | `cdtrs@emp` | Priya Verma (Procurement) |

---
CDTRS V2 — Backend, Database & API Integration Specification Page 1
CDTRS V2
Backend, Database & API Integration
Specification
Revised Comprehensive Edition — Consolidated Requirements
Purpose
This revised specification preserves the original CDTRS V2 architecture and incorporates the additional
backend requirements identified during the latest workflow and UI review. It is intended to be given to the
backend developer before implementation starts.
Core principle: CDTRS remains document-centric. One canonical document_id must survive the complete
lifecycle from intake through closure. The new requirements extend this model rather than replacing it.
Decision Baseline
Frontend PySide6 / Qt Widgets / service layer / centralized API client
Backend FastAPI / SQLAlchemy / Pydantic / authentication / authorization
Database PostgreSQL; never connected directly by frontend
Roles DS, DIRECTOR, HOD, EMPLOYEE
Workflow DS → Director → DS → HOD/Employee → Progress → DS → Director → DS → Closed
Storage Backend-managed files; database stores storage references
OCR Asynchronous OCR + structured extraction + verification
Routing Suggestion → DS review/edit → confirmed route
Visibility Backend-enforced role, department and employee scope
Updates Event-driven/live updates; no manual Refresh dependency
CDTRS V2 — Backend, Database & API Integration Specification Page 2
1. What This Revision Adds
The original specification already establishes the core database entities, workflow, API direction, authorization
rules, attachment model, document history and frontend/backend boundary. This edition adds the operational
details that became necessary during system testing and review.
Area New/clarified requirement
Mail intake Track incoming message separately from the document and preserve sender, subject, timestamp and message idenMail attachments Store each incoming attachment with source-message provenance and prevent duplicate ingestion.
File storage Define a backend storage abstraction and never expose physical paths to the frontend.
OCR Add OCR job lifecycle, full-text artifact, structured extracted fields and extraction provenance.
OCR verification Never let re-analysis overwrite DS-verified values silently.
Routing intelligence Store department/employee suggestions, confidence, reason and source separately from confirmed routes.
Director remark extraction Surface explicit department/employee instructions as a highlighted suggestion for DS.
Remarks Keep latest remark on document for fast display and retain complete remark history separately.
Visibility Hard-enforce HOD department scope and employee personal scope in backend queries.
Reminders If employee is assigned, remind employee; otherwise if department exists, remind department HOD.
Live updates Use backend events/WebSocket/SSE or equivalent so relevant screens update without Refresh buttons.
Reliability Use transactions, idempotency and optimistic concurrency for workflow operations.
Testing Seed two HODs from different departments and test cross-department isolation.
2. Non-Negotiable Architecture Principles
• One document: do not create separate Director/HOD/Employee document records.
• Routing is not assignment: DS routes; HOD assigns employee.
• Suggestion is not routing: OCR/AI may recommend, but DS confirms.
• Backend is authoritative: frontend hiding/filtering is not security.
• Original files are retained: OCR output is derived data, not a replacement for the source file.
• History is retained: remarks, progress, routes, attachments and workflow events are not overwritten.
• Closed means closed: normal workflow mutations are rejected after closure.
CDTRS V2 — Backend, Database & API Integration Specification Page 3
3. Target Architecture
Incoming Sources
Outlook / Government Mail / Manual Upload
|
v
+-------------------+
| Intake + Tracking |
+---------+---------+
|
v
+-------------------+
| Secure File Store |
+---------+---------+
|
v
+-------------------+
| Canonical Document|
| document_id |
+---------+---------+
|
+---------+---------+
| |
v v
OCR / Extraction Source Metadata
| |
+---------+---------+
v
Routing Intelligence
suggestion + confidence
|
v
DS Verify/Edit
|
v
Confirmed Workflow Route
|
v
Director → DS → HOD/Employee
|
v
Progress + Attachments
|
v
DS Follow-up
|
v
Director
|
v
DS
|
v
CLOSED
Backend modules should be separated so that ingestion, storage, OCR, routing, workflow, authorization,
notifications and events can be tested independently.
Module Responsibility
Authentication Login, identity, token/session handling
Authorization Role, department, document and attachment access
Intake Mail synchronization, incoming message records, attachment ingestion
Document service Canonical document metadata and lifecycle
Storage service Upload, storage, retrieval and secure download
OCR service OCR jobs, extracted text, fields, confidence and retries
Routing service Routing suggestions and evidence
CDTRS V2 — Backend, Database & API Integration Specification Page 4
Module Responsibility
Workflow service State validation and transitions
Remark service Current remarks + remark history
Assignment service HOD → Employee assignments
Progress service Multiple employee updates and supporting files
Notification service Notifications and deadline reminders
Event service Live update events for connected clients
Audit service Security/administrative audit records
CDTRS V2 — Backend, Database & API Integration Specification Page 5
4. Canonical Workflow
# Actor Action Backend result
1 DS Receive/process intake Source + file + canonical document
2 DS Verify extracted metadata Verified values saved
3 DS Route to Director Route + history + notification
4 Director Review document Authorized file/document access
5 Director Save/edit remark Latest remark + remark history
6 Director Return to DS DS stage + history + notification
7 DS Review Director instruction Routing suggestion may be generated
8 DS Edit/confirm route Confirmed HOD or employee route
9 HOD Optional remark / assign employee Assignment + notification
10 Employee Work and submit progress Progress retained
11 HOD/DS Monitor Role-scoped progress visibility
12 DS Forward relevant progress Follow-up to Director, same document_id
13 Director Final remark Remark retained + return to DS
14 DS Close CLOSED + closure timestamp
4.1 Director remark and return are separate actions. Saving a remark must not internally perform Return to DS.
The UI may provide a convenient combined workflow action, but the backend concepts remain independent.
4.2 HOD remark and assignment are also separate. HOD must not be forced to enter a second/duplicate
remark merely to assign an employee.
4.3 The Director cannot route to HOD/Employee. If the Director writes an explicit routing instruction, the
system detects it and surfaces it to DS; DS remains the authority who confirms the route.
CDTRS V2 — Backend, Database & API Integration Specification Page 6
5. Incoming Mail / Outlook Integration
A mail item and its attachment are different source objects. The backend must preserve the relationship so
that CDTRS can answer: who sent this, what was the subject, when was it received, which attachment became
the document, and where the original file is stored?
Mail system
|
+-- external_message_id
+-- sender_name
+-- sender_email
+-- subject
+-- received_at
+-- body/reference
+-- attachments
|
v
CDTRS Intake
|
+--> incoming_message
+--> attachment storage
+--> canonical document
+--> OCR queue
5.1 `incoming_messages`
Field Purpose
id Internal source-message ID
source_type OUTLOOK / GOVERNMENT_MAIL / OTHER_APPROVED_SOURCE
external_message_id Original message identifier; used for de-duplication
sender_name Sender display name
sender_email Sender address
subject Original subject
received_at Original received time
body_reference Stored/reference representation if retained
has_attachments Boolean
processing_status NEW / PROCESSING / PROCESSED / FAILED / IGNORED
created_at CDTRS ingestion timestamp
5.2 Intake rules
• Repeated synchronization of the same external message must not create duplicate CDTRS documents.
• Every incoming attachment gets a storage record and retains original filename and MIME type.
• Multiple attachments must be supported.
• The system should identify the primary document attachment without deleting supporting attachments.
• A message with no usable document may remain an intake item for DS review.
• Manual upload should use the same canonical storage/document pipeline as mail intake.
CDTRS V2 — Backend, Database & API Integration Specification Page 7
6. File Storage and Attachments
The database should store references to files, not large binary contents. The frontend must use backend
access/download endpoints and must never assume a Windows/Linux physical storage path.
Logical storage
storage/
incoming/
documents/
progress/
processed/
temporary/
Database:
storage_key
original_filename
mime_type
file_size
checksum
attachment_type
created_at
6.1 Attachment types
Type Meaning
ORIGINAL Canonical document uploaded directly to CDTRS
EMAIL_ATTACHMENT Original file received from incoming mail
SUPPORTING_DOCUMENT Additional workflow document
PROGRESS_ATTACHMENT File submitted with a particular employee progress update
6.2 Recommended `attachments` fields
Field Purpose
id Primary key
document_id Canonical document
progress_update_id Nullable; links progress attachment to its progress update
uploaded_by_user_id Uploader
file_name Original filename
storage_key Backend storage reference
file_type MIME/type
file_size Size
checksum Integrity/de-duplication
attachment_type Original/email/supporting/progress
source_message_id Nullable originating mail item
created_at Timestamp
6.3 Secure download
GET /attachments/{attachment_id}/download
Backend:
1. Authenticate user
2. Resolve attachment → document
3. Authorize user against document
4. Resolve storage_key
5. Stream file
6. Never expose raw filesystem path
CDTRS V2 — Backend, Database & API Integration Specification Page 8
7. OCR and Extraction Pipeline
OCR is a backend processing pipeline. The full extracted text may be many pages long and should not be
dumped into the normal Document Information panel. The UI should show concise structured fields and provide
an appropriate document/OCR viewer only when needed.
Stored original
|
v
OCR = PENDING
|
v
OCR = PROCESSING
|
+--> full extracted text
+--> page text if supported
+--> structured fields
+--> routing clues
|
v
OCR = COMPLETED / FAILED
OCR status Meaning
PENDING Waiting for worker
PROCESSING OCR/extraction running
COMPLETED Extraction available
FAILED Processing failed; retry/re-analysis permitted
7.1 Suggested `document_ocr` fields
Field Purpose
id OCR record
document_id Canonical document
extracted_text Full OCR text artifact
ocr_status Processing state
ocr_engine Engine/version
confidence Overall or normalized confidence
processed_at Completion timestamp
error_message Failure information if applicable
7.2 Suggested `document_extracted_fields`
Field Purpose
id Record ID
document_id Canonical document
field_name TITLE, REFERENCE, DEPARTMENT, EMPLOYEE, etc.
extracted_value Raw extracted value
confidence Field confidence
source_page Page number where found
source_text Supporting snippet if available
verified_value DS-verified value
verified_by / verified_at Verification provenance
7.3 Re-analysis rule: a new OCR result may replace an unverified suggestion, but it must not silently replace a
value already verified or manually edited by DS.
CDTRS V2 — Backend, Database & API Integration Specification Page 9
8. Routing Intelligence
Routing intelligence uses extracted document content, source metadata and Director remarks to recommend a
destination. It is advisory until DS confirms it.
Field Purpose
suggested_department_id Recommended department
suggested_employee_id Recommended employee if resolved
routing_confidence Confidence score/band
routing_reason Human-readable explanation
routing_source DOCUMENT_CONTENT / DIRECTOR_REMARK / SOURCE_METADATA / MANUAL
generated_at Suggestion timestamp
confirmed_by DS who confirmed
confirmed_at Confirmation timestamp
POST /documents/{id}/analyze-routing
-> create/update suggestion only
GET /documents/{id}/routing-suggestion
-> return current suggestion
POST /documents/{id}/route
-> confirm actual workflow route
8.1 Explicit Director instruction
Director remark:
"Assign this to Rahul Sharma, Finance."
Detected:
employee = Rahul Sharma
department = Finance
confidence = 91%
source = DIRECTOR_REMARK
DS UI:
WARNING: Explicit routing instruction detected
Suggested Department: Finance
Suggested Employee: Rahul Sharma
[Edit] [Confirm Routing]
No route changes until DS confirms.
8.2 If no employee is explicitly identified, DS routes to the appropriate HOD. If an employee is explicitly
identified and can be resolved to an active employee/user, direct DS → Employee routing is allowed.
CDTRS V2 — Backend, Database & API Integration Specification Page 10
9. Consolidated Database Model
Core entities from the original specification remain: users, departments, employees, documents,
document_routes, work_assignments, progress_updates, attachments, workflow_history, audit_logs and
notifications. The following additions/clarifications are required.
9.1 `documents`
Field Purpose
doc_id Primary key
reference_no Human-readable CDTRS ID
title Verified title
description General description
received_date Received date
deadline Target deadline
source Sender/source organization
mode Ingestion mode/source type
format / mime_type Original file format
priority HIGH / MEDIUM / LOW
status User-facing lifecycle status
current_stage DS / DIRECTOR / HOD / EMPLOYEE / CLOSED
current_owner_id Current responsible user where applicable
target_department_id Relevant department
created_by Creator/receiver
director_remark Latest Director remark
hod_remark Latest HOD remark
source_message_id Nullable incoming-message link
ocr_status Current OCR state
version Optimistic concurrency version
created_at / updated_at / closed_at Timestamps
9.2 `document_remarks`
Field Purpose
id Primary key
document_id Canonical document
author_user_id Author
role Author role
remark_text Remark
remark_type DIRECTOR / HOD / other approved type
created_at Created time
updated_at Last edit time
Keep latest Director/HOD values on `documents` for quick display, while `document_remarks` preserves the
full history of edits.
CDTRS V2 — Backend, Database & API Integration Specification Page 11
10. Role and Department Visibility
Visibility must be enforced in backend queries and service methods, not merely by filtering a table in PySide6.
Role Permitted visibility
DS Documents under DS responsibility across intake, Director review, HOD processing, employee progress, follow-up and closurDirector Only documents sent to Director by DS and relevant follow-up of those documents.
HOD Only documents routed to that HOD/department, including permitted history, assignments, progress and attachments.
Employee Only documents directly routed to that employee or assigned to that employee by HOD.
10.1 Two-HOD test requirement
Finance Department
HOD Finance
Rahul Sharma
other Finance employees
Procurement Department
HOD Procurement
Priya Verma
other Procurement employees
Test Expected
Finance HOD opens inbox Finance documents only
Finance HOD requests Procurement document Denied
Procurement HOD opens history Procurement documents only
Finance employee opens tasks Own permitted tasks only
Employee requests another employee's attachment Denied
Director opens department-only document not sent to DirectorDenied
The backend may return 403 or intentionally use 404 for inaccessible resources depending on the chosen
resource-hiding policy, but it must never leak the protected document.
CDTRS V2 — Backend, Database & API Integration Specification Page 12
11. Remarks, History and Workflow Audit
Workflow history remains document-centric and user-visible. System/security audit logs remain separate. The
backend should retain all workflow events even if the UI presents history compactly.
Workflow history Audit log
Document-specific System/security/administrative
DS routed to Director Login/logout
Director saved remark Authorization failure
HOD assigned employee Administrative configuration
Employee submitted progress Security event
Document closed System-level activity
Required workflow history fields: id, document_id, performed_by_user_id, action, from_role, to_role, details,
created_at.
The document viewer should not reserve a large permanent area for the entire workflow table. History can be
opened/expanded for the document, while the dedicated History/Audit screen remains the system-wide
document-centric view.
11.1 Remark editing rules
• Director can edit/save Director remark while the document is in a Director-appropriate stage.
• HOD can edit/save HOD remark for department documents.
• Employee does not overwrite HOD/Director remarks.
• Saving a remark creates/updates the latest value and records the change in remark history.
• Saving a remark is not itself a route/assignment transition.
CDTRS V2 — Backend, Database & API Integration Specification Page 13
12. Notifications and Reminder Logic
The notification entity from the original specification remains valid. The recipient-selection logic is expanded to
cover unassigned departmental work.
if active employee assignment exists:
recipient = assigned employee
elif target department exists:
recipient = active HOD of target department
else:
recipient = configured DS fallback
This means a department-routed document with no staff assignment generates an action reminder for the
HOD. Once staff is assigned, subsequent employee-specific reminders can target the assigned employee.
Reminder field Purpose
document_id Document needing action
recipient_user_id Resolved recipient
reason DUE_SOON / OVERDUE / ACTION_REQUIRED
due_at Trigger time/deadline
sent_at Sent time
is_read Read state
deduplication_key Prevent repeated identical reminders
12.1 Live updates
Manual Refresh buttons should not be required for normal workflow changes. Use WebSocket, Server-Sent
Events, or another suitable event mechanism so the relevant client can update after document routing, remark
save, assignment, progress, attachment upload, closure and notification creation.
Event Typical affected views
DOCUMENT_CREATED DS inbox/dashboard
DOCUMENT_ROUTED DS/HOD/Employee queues
REMARK_UPDATED Relevant document viewers
ASSIGNMENT_CREATED HOD + employee
PROGRESS_SUBMITTED Employee/HOD/DS
ATTACHMENT_ADDED Document/progress view
DOCUMENT_CLOSED DS lists/dashboard
NOTIFICATION_CREATED Notification bell/unread count
CDTRS V2 — Backend, Database & API Integration Specification Page 14
13. API Contract — Consolidated
Method Endpoint Purpose
POST /auth/login Authenticate
GET /auth/me Current user
POST /auth/logout Logout/session invalidation
GET /documents Authorized listing
GET /documents/inbox Role-scoped inbox
POST /documents Create document/manual intake
GET /documents/{id} Authorized document
POST /documents/{id}/route Confirm route
PUT /documents/{id}/director-remark Save/edit Director remark
POST /documents/{id}/return-to-ds Director return
PUT /documents/{id}/hod-remark Save/edit HOD remark
POST /documents/{id}/assign HOD assignment
POST /documents/{id}/progress Employee progress
GET /documents/{id}/progress Progress list
POST /documents/{id}/attachments Upload attachment
GET /documents/{id}/attachments List attachments
GET /attachments/{id}/download Authorized download
GET /documents/{id}/history Document history
POST /documents/{id}/follow-up DS follow-up to Director
POST /documents/{id}/close Close document
GET /notifications Notifications
GET /notifications/unread Unread notifications
PATCH /notifications/{id}/read Read notification
GET /intake Intake list
POST /intake/manual-upload Manual intake
POST /intake/{id}/process Process intake
POST /documents/{id}/process-ocr Start/restart OCR
GET /documents/{id}/ocr OCR status/results
POST /documents/{id}/reanalyze Re-run approved analysis
POST /documents/{id}/analyze-routing Generate routing suggestion
GET /documents/{id}/routing-suggestion Get routing suggestion
GET /dashboard Role-appropriate dashboard
13.1 Standard errors
401 = not authenticated
403 = authenticated but unauthorized
404 = not found or intentionally hidden
409 = workflow/concurrency conflict
422 = request validation failure
500 = unexpected server error
CDTRS V2 — Backend, Database & API Integration Specification Page 15
14. Authentication and Backend Authorization
The final system must not use hardcoded credentials in frontend code. Authentication, authorization and
token/session handling are backend responsibilities.
• Store password hashes only.
• Resolve current authenticated user on every protected request.
• Apply role checks server-side.
• Apply department checks for HOD operations.
• Apply employee ownership/assignment checks for employee operations.
• Re-check authorization before every file download.
• Never rely on a disabled/hidden UI button as permission enforcement.
15. Transactions, Idempotency and Concurrency
Multi-record workflow actions must be atomic.
Operation Atomic side effects
DS confirms route document state + route + workflow history + notification + event
Director return document state + history + notification + event
HOD assignment assignment + owner/stage + history + notification + event
Progress progress update + attachment links + history + notifications/events
DS follow-up follow-up route + history + Director notification
Closure closed state + closed_at + history + notification/event
Use an idempotency/deduplication strategy for mail ingestion and other operations that may be retried. Use a
document version number or equivalent optimistic concurrency mechanism. A stale update should return 409
Conflict instead of silently overwriting a newer state.
16. Background Processing
OCR and mail synchronization can take longer than a normal UI request. Use background workers/jobs and
expose status to the frontend.
POST /documents/{id}/process-ocr
|
+--> 202 Accepted
|
v
ocr_status = PROCESSING
|
v
worker completes
|
+--> fields saved
+--> routing suggestion optionally generated
+--> event published
CDTRS V2 — Backend, Database & API Integration Specification Page 16
17. Closure Rules
After the final Director review, the Director returns the document to DS. DS is the role that closes the
document.
On closure: status becomes CLOSED, closed_at is populated, a workflow event is recorded, and normal
route/assign/progress workflow operations are rejected. Existing documents, history, remarks, progress and
attachments remain viewable according to authorization.
18. Testing and Required Seed Data
Suite Minimum test
Authentication Valid/invalid login, session/token behavior
Authorization DS/Director/HOD/Employee permissions
Department isolation Two HODs cannot cross-access
Employee isolation Employee cannot see another employee's tasks/files
Workflow Only valid state transitions
Routing HOD vs direct employee rules
Routing suggestion Suggestion does not itself route
OCR Pending/processing/completed/failed/retry
Verification Re-analysis does not overwrite verified fields
Mail Duplicate external message does not duplicate document
Attachments Original/progress linkage + download authorization
Reminders Employee first; HOD fallback when unassigned
Live events Relevant clients update without Refresh
Concurrency Stale write returns 409
Closure Closed document rejects normal workflow mutation
Required test users should include DS, Director, at least two HODs from different departments, and multiple
employees across those departments.
CDTRS V2 — Backend, Database & API Integration Specification Page 17
19. Recommended Implementation Order
1 Foundation: FastAPI configuration, PostgreSQL, SQLAlchemy, migrations and logging.
2 Authentication: users, password hashing, login and current-user handling.
3 Authorization: reusable role/department/document access checks.
4 Core database: departments, employees, users, documents, routes, assignments, progress, attachments,
workflow history, notifications and audit logs.
5 Storage: storage abstraction and secure upload/download.
6 Manual intake: establish canonical document creation first.
7 Mail intake: incoming message model and mail integration adapter.
8 OCR: asynchronous processing and structured extraction.
9 Verification: preserve extracted and verified values separately.
10 Routing: suggestion, confidence, source/provenance and DS confirmation.
11 Workflow: Director, HOD, employee, follow-up and closure services.
12 Notifications: action reminders and recipient fallback.
13 Live events: event publication/subscription.
14 Reliability: transactions, idempotency and optimistic concurrency.
15 Testing/deployment: multi-HOD isolation, end-to-end lifecycle and reachable FastAPI environment.
20. Final Acceptance Checklist
Requirement Acceptance condition
Canonical document Same document_id through entire lifecycle
Mail ingestion Message + attachment provenance retained
Storage No raw filesystem paths exposed to frontend
OCR Multi-page/scanned files process asynchronously
Extraction Structured fields available without dumping full OCR into Document Information
Verification Manual/verified values survive re-analysis
Routing intelligence Suggestion includes confidence/source and requires DS confirmation
Director instruction Explicit department/employee instruction is highlighted to DS
HOD isolation HOD sees only own department's permitted documents/history
Employee isolation Employee sees only own permitted tasks/files
Remarks Latest values easy to display; history retained
Assignment HOD assignment independent of remark
Attachments Original and progress attachments are linked and permission-checked
Reminders Assigned employee gets reminder; otherwise department HOD
Live updates Normal changes appear without manual Refresh
Transactions Related workflow side effects are atomic
Concurrency Stale updates safely rejected
Closure Closed document rejects normal workflow mutations
API Swagger/OpenAPI and test accounts available
Regression All role/workflow/ingestion tests pass
CDTRS V2 — Backend, Database & API Integration Specification Page 18
21. Final Target Architecture — Operational View
OUTLOOK / GOV MAIL / UPLOAD
|
v
+----------------------+
| Intake + Message |
| + Attachment Tracking|
+----------+-----------+
|
v
+----------------------+
| Secure File Storage |
+----------+-----------+
|
v
+----------------------+
| Canonical Document |
| document_id |
+----------+-----------+
|
+---------+---------+
| |
v v
OCR/AI Source Metadata
| |
+---------+---------+
|
v
Routing Suggestion
Dept / Employee / Score
|
v
DS CONFIRMS
|
v
Director / HOD / Employee
|
v
Progress + Files
|
v
DS Follow-up
|
v
Director
|
v
DS
|
v
CLOSED
Every important change:
transaction
+ workflow history
+ notification
+ live event
+ authorization checks
Final instruction to backend developer: use this document as the implementation baseline before coding the
API/database layer. Do not build isolated screens or endpoints without first enforcing the canonical document
model, role/department authorization, workflow state rules, storage contract and transaction boundaries.
The original V2 specification remains the architectural foundation. This revised edition adds the requirements
discovered after functional testing so the backend can support the actual CDTRS workflow rather than only the
earlier UI/mock workflow.
End of Specification

---

---

# APPENDIX — Backend Code Audit Report

> **Date:** 2026-08-16
> **Scope:** `backend/models.py`, `backend/schemas.py`, `backend/crud.py`, `backend/main.py`
> **Purpose:** This appendix documents every bug, inconsistency, naming problem, and broken pipeline found in the current implementation. Read through each issue and apply the fix before testing or deploying.

---

## SECTION A — Critical Bugs (Must Fix Before Any Testing)

---

### A-1. Unauthenticated `/system/reset-db` Endpoint
**File:** `main.py` — around line 1285
**Severity:** 🔴 CRITICAL — Security

**Problem:**
The database reset endpoint drops ALL tables and reseeds with no authentication at all. Any HTTP client that can reach the server can wipe the entire database with a single POST request.

```python
# Current broken code:
def reset_database(
    db: Session = Depends(get_db),
    # ← NO current_user dependency — completely open!
):
```

**Fix Steps:**
1. Add `current_user: models.User = Depends(require_roles(UserRole.DS))` as a parameter to `reset_database()`.
2. Optionally add an additional environment variable guard (e.g., only allow if `ALLOW_RESET=true` in `.env`).
3. Consider removing this endpoint entirely in production and only exposing it in a dev/test environment.

---

### A-2. Duplicate SQLAlchemy Enum Type Name for `UserRole`
**File:** `models.py` — lines 164 and 362
**Severity:** 🔴 CRITICAL — Database crash on startup

**Problem:**
The same Python enum `UserRole` is mapped to two different PostgreSQL enum type names: `user_role` (on `User`) and `user_role_remark` (on `DocumentRemark`). PostgreSQL will either error with `DuplicateObject` or silently create two separate enum types for the same values, causing inconsistency.

```python
# User model (line 164):
role = Column(SAEnum(UserRole, name="user_role"), ...)

# DocumentRemark model (line 362):
role = Column(SAEnum(UserRole, name="user_role_remark"), ...)  # ← DIFFERENT NAME!
```

**Fix Steps:**
1. In `DocumentRemark`, change `name="user_role_remark"` to `name="user_role"` to reuse the same PostgreSQL type.
2. Alternatively, add `create_type=False` to the second usage: `SAEnum(UserRole, name="user_role", create_type=False)`. This tells SQLAlchemy not to try creating the type again since it already exists.
3. Drop and recreate the database (or run a migration) after this change to avoid leftover orphan types.

---

### A-3. `suggested_employee_id` Foreign Key Points to Wrong Table
**File:** `models.py` — line 426 | `schemas.py` — line 368
**Severity:** 🔴 CRITICAL — Data integrity + API lies to the frontend

**Problem:**
The column is named `suggested_employee_id` which implies it stores an `employees.id` value, but the FK constraint points to `users.id`. Any frontend developer reading the API response will look up this ID in `GET /employees` and get 404 or the wrong record.

```python
# Current broken code (models.py line 426):
suggested_employee_id = Column(Integer, ForeignKey("users.id"), nullable=True)
#                                                   ^^^^^^^^ should be employees.id
```

**Fix Steps:**
1. Decide what this column should actually store:
   - **Option A (Recommended):** Store `users.id`. Rename the column to `suggested_user_id` everywhere (model, schema, crud, main).
   - **Option B:** Store `employees.id`. Change FK to `ForeignKey("employees.id")` and update the relationship and all lookup logic accordingly.
2. Update `RoutingSuggestionResponse` in `schemas.py` to match the chosen name.
3. Update `generate_routing_suggestion()` in `crud.py` which currently has a fragile double-lookup (`emp.user_id or db.query(models.User.id).filter(...).scalar()`) — this logic needs to be cleaned up once the column intent is decided.
4. Update both endpoints in `main.py` that build `RoutingSuggestionResponse` manually (around lines 954–968 and 990–1004).

---

## SECTION B — Moderate Bugs (Fix Before Production)

---

### B-1. `User.employee_id` Has No Foreign Key Constraint
**File:** `models.py` — line 166
**Severity:** 🟠 MODERATE — Data integrity gap

**Problem:**
`user.employee_id` is a plain integer column with no `ForeignKey` constraint, meaning the database will accept any value including ones that do not exist in the `employees` table. The `Employee.user_id` column correctly points back to `users.id`, but this side has no enforcement.

```python
# Current broken code (models.py line 166):
employee_id = Column(Integer, nullable=True)  # ← NO ForeignKey!
```

**Fix Steps:**
1. Change to: `employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True)`
2. Run a migration. If existing data has orphaned values, clean them first or set invalid rows to `NULL` before adding the constraint.

---

### B-2. `follow_up_to_director()` Hardcodes Wrong `from_role`
**File:** `crud.py` — line 786
**Severity:** 🟠 MODERATE — Incorrect audit trail

**Problem:**
The workflow history entry records `from_role="DS"` but the document was actually at the `EMPLOYEE` stage (or `PROGRESS_UPDATED` status) when this action happens. Every other workflow function uses `current_user.role.value` dynamically.

```python
# Current broken code (crud.py ~line 786):
_add_workflow_history(
    ...
    action="FOLLOW_UP_TO_DIRECTOR",
    from_role="DS",        # ← WRONG: should reflect actual previous stage
    to_role="DIRECTOR"
)
```

**Fix Steps:**
1. Change `from_role="DS"` to `from_role=current_user.role.value` to match the pattern used in all other workflow functions like `route_document()`.
2. Optionally pass `from_role=doc.current_stage.value` before the stage is updated, to accurately record the stage the document was leaving.

---

### B-3. `return_to_ds()` Always Returns to the Original Creator
**File:** `main.py` — line 674
**Severity:** 🟠 MODERATE — Incorrect routing behavior

**Problem:**
When Director returns a document to DS, the code always sends it to `doc.created_by` (the original creator). If the document was reassigned to a different DS user mid-workflow, it will incorrectly go back to the original creator instead of the current DS handler.

```python
# main.py line 674:
ds_user_id = doc.created_by  # ← Always the creator, ignores reassignment
```

**Fix Steps:**
1. Consider using `doc.current_owner_id` as a fallback if it belongs to a DS user, before defaulting to `doc.created_by`.
2. Or add a dedicated `ds_handler_id` column on the document to track the current DS user explicitly.
3. At minimum, validate that `doc.created_by` still belongs to an active DS user before routing to them.

---

### B-4. Any Employee Can Submit Progress Regardless of Assignment
**File:** `main.py` — line 745 | `crud.py` — `create_progress_update()`
**Severity:** 🟠 MODERATE — Authorization gap

**Problem:**
The progress submission endpoint only checks that the current user has the `EMPLOYEE` role. It does not verify that this specific employee is the one *assigned* to this specific document. Any active employee who can access the document URL can submit progress.

**Fix Steps:**
1. In `create_progress_update()` in `crud.py`, add a check that the current employee has an active `WorkAssignment` for this document:
   ```python
   active_assignment = db.query(models.WorkAssignment).filter(
       models.WorkAssignment.document_id == doc_id,
       models.WorkAssignment.assigned_to_user_id == current_user.id,
       models.WorkAssignment.is_active == True
   ).first()
   if not active_assignment:
       return None  # Or raise an appropriate error
   ```
2. Return a `403` from the route handler if `create_progress_update` returns `None` for this reason.

---

### B-5. `get_routing_suggestion_endpoint` Can Crash with `AttributeError`
**File:** `main.py` — lines 983–988
**Severity:** 🟠 MODERATE — Runtime crash / 500 error

**Problem:**
After calling `crud.generate_routing_suggestion()` as a fallback, the code immediately accesses `suggestion.suggested_department` without checking if `suggestion` is `None`. If the document was deleted between the first check and the fallback, this crashes with `AttributeError: 'NoneType' object has no attribute 'suggested_department'`.

```python
# Current broken code (main.py ~line 983):
suggestion = crud.get_routing_suggestion(db, document_id)
if not suggestion:
    suggestion = crud.generate_routing_suggestion(db, document_id)
# ← No null check here!
dept_name = suggestion.suggested_department.name if suggestion.suggested_department else None
```

**Fix Steps:**
1. Add a null guard after the fallback:
   ```python
   if not suggestion:
       raise HTTPException(status_code=404, detail="Routing suggestion could not be generated.")
   ```
2. Apply the same fix to the `analyze_routing` endpoint (around line 948) which has the same pattern.

---

### B-6. `RemarkType.OTHER` Is a Dead Enum Value
**File:** `models.py` — line 106
**Severity:** 🟠 MODERATE — Incomplete feature / dead code

**Problem:**
`RemarkType.OTHER` exists as an enum value but there is no endpoint, schema, or CRUD function to create a remark with this type. The only write paths for remarks are `save_director_remark()` and `save_hod_remark()` which hardcode `RemarkType.DIRECTOR` and `RemarkType.HOD` respectively.

**Fix Steps:**
1. Either remove `OTHER` from the enum (and run a migration to update the DB type) if it is not needed.
2. Or create a general remark endpoint (e.g., `POST /documents/{id}/remarks`) with a `DocumentRemarkCreate` schema that accepts `remark_type`, and update `crud.py` to handle it.

---

## SECTION C — Minor Issues (Fix When Convenient)

---

### C-1. `LiveEventMessage.timestamp` Is a Frozen Default
**File:** `schemas.py` — line 449
**Severity:** 🟡 MINOR — Incorrect timestamps on live events

**Problem:**
The default value `datetime.utcnow()` is evaluated **once when the module is imported**, not each time a `LiveEventMessage` is created. Every event created after startup will have the server's startup time as its timestamp.

```python
# Current broken code (schemas.py line 449):
timestamp: datetime = datetime.utcnow()  # ← Frozen at import time!
```

**Fix Steps:**
1. Change to use Pydantic's `Field` with `default_factory`:
   ```python
   from pydantic import BaseModel, Field
   timestamp: datetime = Field(default_factory=datetime.utcnow)
   ```

---

### C-2. Auto-Migration `DROP TABLE` List Is Missing `audit_logs`
**File:** `main.py` — lines 49–63 (`ensure_v2_schema` function)
**Severity:** 🟡 MINOR — Inconsistent schema reset behavior

**Problem:**
The `ensure_v2_schema()` function's DROP TABLE list does not include `audit_logs`, but the manual `/system/reset-db` endpoint does. If the auto-migration runs on a legacy database, `audit_logs` will be left behind with the old schema, potentially causing FK violations or column mismatch errors.

**Fix Steps:**
1. Add `audit_logs` to the DROP TABLE statement inside `ensure_v2_schema()`:
   ```sql
   DROP TABLE IF EXISTS
       workflow_history, notifications, attachments, progress_updates,
       work_assignments, document_routes, document_remarks, document_ocr,
       document_extracted_fields, routing_suggestions, reminders,
       documents, incoming_messages, employees, users, departments,
       audit_logs CASCADE;
   ```

---

### C-3. Seed Data Is Missing a User Account for `Anil Kumar` (EMP-003)
**File:** `crud.py` — `seed_data()` function, around line 1501
**Severity:** 🟡 MINOR — Test data is incomplete

**Problem:**
The seed data creates an `Employee` record for `Anil Kumar` (EMP-003, Technical department) but never creates a corresponding `User` account. He has no login credentials, and his `Employee.user_id` will always be `NULL`. This means the Technical department has no testable employee.

**Fix Steps:**
1. Add a user entry to `users_data` in `seed_data()`:
   ```python
   {
       "username": "emp_anil",
       "password": "cdtrs@emp",
       "full_name": "Anil Kumar",
       "role": UserRole.EMPLOYEE,
       "department_id": dept_map["Technical"],
       "employee_id": emp_map.get("EMP-003")
   }
   ```
2. Trigger a DB reset or re-seed to apply the change.

---

### C-4. `datetime.min.time()` Quirk in Reminder Generation
**File:** `crud.py` — line 1184
**Severity:** 🟡 MINOR — Works by accident, intent is unclear

**Problem:**
`datetime.min` is a `datetime` object (not a `time` object). Calling `.time()` on it returns `time(0, 0)` which is midnight — this works as intended, but the code reads as if the developer confused `datetime.min` with `time.min`.

```python
# Current code (crud.py line 1184):
due_at=datetime.combine(doc.deadline, datetime.min.time()) if doc.deadline else None
```

**Fix Steps:**
1. Replace with the clearer and more explicit form:
   ```python
   from datetime import time
   due_at=datetime.combine(doc.deadline, time(0, 0)) if doc.deadline else None
   ```

---

---

## SECTION D — Naming Inconsistencies

These are not runtime bugs but will confuse any frontend developer integrating with this API, and some (marked 🔴) cause real functional problems.

---

### D-1. `doc_id` vs `document_id` — Split Naming Across the Entire API
**Files:** `models.py`, `schemas.py` (all response schemas)
**Severity:** 🟠 MODERATE — API confusion for frontend

**Problem:**
The `Document` table's primary key is named `doc_id`. Every related table's foreign key column is named `document_id`. This means the API returns:
- `doc_id` in `DocumentResponse` and `DocumentListResponse`
- `document_id` in every nested response (`AssignmentResponse`, `ProgressResponse`, `AttachmentResponse`, `OCRResponse`, `ReminderResponse`, `WorkflowHistoryResponse`, `NotificationResponse`, etc.)

A frontend developer must remember two different names for the same logical ID.

**Fix Steps (Pick One):**
- **Option A — Rename model PK to `id`:** Change `doc_id` to `id` in `Document` model and update all FKs (`ForeignKey("documents.id")`), all CRUD queries (`models.Document.id`), all schema fields, and all references in `main.py`. This is the most standard convention.
- **Option B — Rename FK columns to `doc_id`:** Change all `document_id` FK columns in related tables to `doc_id`. Update all schema response fields to match. This keeps the model PK name but makes FK columns match.
- **Option C — Keep as-is but document it:** At minimum, add a comment in the spec/readme clarifying that `doc_id` in document responses and `document_id` in related responses refer to the same value.

---

### D-2. `created_by` and `current_owner_id` Break the `*_user_id` Naming Convention
**File:** `models.py` — lines 224, 226 | `schemas.py` — lines 166, 168
**Severity:** 🟡 MINOR — Style inconsistency

**Problem:**
Every user FK column in the codebase uses the `_user_id` suffix pattern:

| Table | Column |
|---|---|
| `WorkAssignment` | `assigned_by_user_id`, `assigned_to_user_id` |
| `ProgressUpdate` | `submitted_by_user_id` |
| `Attachment` | `uploaded_by_user_id` |
| `WorkflowHistory` | `performed_by_user_id` |
| `DocumentRemark` | `author_user_id` |
| `Reminder` | `recipient_user_id` |

**But `Document` breaks this:**

| Table | Column | Should Be |
|---|---|---|
| `Document` | `created_by` | `created_by_user_id` |
| `Document` | `current_owner_id` | `current_owner_user_id` |

**Fix Steps:**
1. Rename `created_by` → `created_by_user_id` in `models.py`, update the relationship `foreign_keys`, update all CRUD references (`doc.created_by`, `models.Document.created_by`), update `schemas.py` `DocumentResponse`, and update `main.py`.
2. Rename `current_owner_id` → `current_owner_user_id` similarly.
3. Run a migration to rename the actual DB columns.
> Note: This is a significant rename touching ~30+ locations. Use find-and-replace carefully.

---

### D-3. `suggested_employee_id` Name Lies About What It Stores
**File:** `models.py` — line 426 | `schemas.py` — line 368
**Severity:** 🔴 CRITICAL — Same as A-3 above, listed here for naming context

**Problem:**
The column name `suggested_employee_id` implies it holds an `employees.id` (primary key of the `employees` table), but it actually stores a `users.id`. The FK confirms this:
```python
suggested_employee_id = Column(Integer, ForeignKey("users.id"), ...)
```
See **Section A-3** for the complete fix steps.

---

### D-4. `User.employee_id` Name Implies FK But Has No Constraint
**File:** `models.py` — line 166
**Severity:** 🟠 MODERATE — Same as B-1 above, listed here for naming context

**Problem:**
`employee_id` on `User` implies it stores an `employees.id`, and it does — but there is no database-level `ForeignKey` constraint to enforce this. See **Section B-1** for the complete fix steps.

---

### D-5. Relationship Names Drop `_user_id` Suffix Inconsistently
**File:** `models.py` — all model relationship definitions
**Severity:** 🟡 MINOR — Style inconsistency

**Problem:**
All FK columns use the `_user_id` suffix, but their corresponding relationship attributes drop it:

| Column | Relationship |
|---|---|
| `assigned_by_user_id` | `assigned_by` |
| `assigned_to_user_id` | `assigned_to` |
| `submitted_by_user_id` | `submitted_by` |
| `uploaded_by_user_id` | `uploaded_by` |
| `performed_by_user_id` | `performed_by` |
| `author_user_id` | `author` |

This is a common pattern in SQLAlchemy and is acceptable, but be aware that `attachment.uploaded_by` returns the `User` object while `attachment.uploaded_by_user_id` returns the integer ID.

**Fix Steps:**
- No code changes needed. Just document this pattern so frontend devs and backend devs understand the difference.
- Optionally prefix relationship names with the entity type (e.g., `assigned_by_user`, `uploaded_by_user`) for clarity.

---

### D-6. No `DocumentRouteResponse` Schema — Routes Are Write-Only
**File:** `schemas.py`
**Severity:** 🟡 MINOR — Incomplete API surface

**Problem:**
There is a `RouteRequest` schema to create routes, but no response schema to read them. Once a route is created via `POST /documents/{id}/route`, there is no API endpoint to list or view the route records. The workflow history partially covers this, but the route details (including `to_department_id`, `remarks`, `route_type`) are not directly queryable.

**Fix Steps:**
1. Create a `DocumentRouteResponse` schema with fields: `id`, `document_id`, `from_user_id`, `to_user_id`, `to_department_id`, `route_type`, `remarks`, `created_at`.
2. Add a `GET /documents/{document_id}/routes` endpoint in `main.py`.
3. Add a corresponding `get_document_routes()` function in `crud.py`.

---

---

## Summary Reference Table

| ID | Severity | File | Short Description |
|---|---|---|---|
| A-1 | 🔴 Critical | `main.py` | `reset-db` endpoint has zero authentication |
| A-2 | 🔴 Critical | `models.py` | Duplicate SQLAlchemy enum name for `UserRole` |
| A-3 | 🔴 Critical | `models.py`, `schemas.py`, `crud.py` | `suggested_employee_id` FK points to `users` not `employees` |
| B-1 | 🟠 Moderate | `models.py` | `User.employee_id` has no ForeignKey constraint |
| B-2 | 🟠 Moderate | `crud.py` | `follow_up_to_director` hardcodes wrong `from_role="DS"` |
| B-3 | 🟠 Moderate | `main.py` | `return_to_ds` always routes to original creator, ignores reassignment |
| B-4 | 🟠 Moderate | `main.py`, `crud.py` | Any employee can submit progress, assignment not verified |
| B-5 | 🟠 Moderate | `main.py` | `get_routing_suggestion` crashes with AttributeError if doc not found |
| B-6 | 🟠 Moderate | `models.py` | `RemarkType.OTHER` is a dead enum value with no write path |
| C-1 | 🟡 Minor | `schemas.py` | `LiveEventMessage.timestamp` is a frozen startup-time default |
| C-2 | 🟡 Minor | `main.py` | `ensure_v2_schema` DROP TABLE list missing `audit_logs` |
| C-3 | 🟡 Minor | `crud.py` | Seed data missing user account for Anil Kumar (EMP-003) |
| C-4 | 🟡 Minor | `crud.py` | `datetime.min.time()` works by accident — use `time(0, 0)` |
| D-1 | 🟠 Moderate | `models.py`, `schemas.py` | `doc_id` (PK) vs `document_id` (FK/response) — split naming |
| D-2 | 🟡 Minor | `models.py`, `schemas.py` | `created_by`, `current_owner_id` break `*_user_id` convention |
| D-3 | 🔴 Critical | `models.py`, `schemas.py` | `suggested_employee_id` misleading name (same as A-3) |
| D-4 | 🟠 Moderate | `models.py` | `User.employee_id` naming implies FK enforcement that does not exist |
| D-5 | 🟡 Minor | `models.py` | Relationship names drop `_user_id` suffix vs column names |
| D-6 | 🟡 Minor | `schemas.py`, `main.py` | No `DocumentRouteResponse` schema — routes are write-only |

---

*End of Audit Appendix*
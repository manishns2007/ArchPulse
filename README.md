# ArchScale — Module 1: Communication Ingestion Layer

> **ArchScale Hackathon Project**
> An AI-powered Project Communication Agent — built modularly.

---

## Purpose

This is **Module 1** of the ArchScale Communication Agent.

It provides a clean, self-contained **ingestion layer** that accepts raw project
communications and converts them into a normalized internal representation
(`CommunicationRecord`).

> ⚠️ **This module does NOT perform AI extraction, summarization, task detection,
> or any analysis.** Its only purpose is to reliably ingest, validate, store, and
> expose raw communications. Later modules will consume the `CommunicationRecord`
> produced here.

---

## Module 1 Scope

| Capability | Status |
|---|---|
| Paste raw text | ✅ |
| Ingest meeting transcripts | ✅ |
| Ingest `.txt` files | ✅ |
| Ingest `.pdf` files (text-based) | ✅ |
| PDF page metadata | ✅ |
| Normalized `CommunicationRecord` output | ✅ |
| Persistent raw file storage | ✅ |
| Persistent normalized JSON storage | ✅ |
| Retrieve by communication ID | ✅ |
| List all communications for a project | ✅ |
| Input validation & error handling | ✅ |
| Basic security (filename sanitization, size limits) | ✅ |
| AI extraction / analysis | ❌ (Module 2+) |
| Database | ❌ (filesystem only) |
| Authentication | ❌ (not required at this stage) |

---

## Requirements

- Python 3.11+
- pip

---

## Installation

```bash
# 1. Clone or navigate to the project directory
cd archscale

# 2. Create and activate a virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
```

---

## Environment Configuration

Copy the example environment file and adjust as needed:

```bash
cp .env.example .env
```

| Variable | Default | Description |
|---|---|---|
| `STORAGE_ROOT` | `storage` | Root directory for all storage |
| `RAW_STORAGE_DIR` | `raw` | Sub-directory for original uploaded files |
| `PROCESSED_STORAGE_DIR` | `processed` | Sub-directory for normalized JSON records |
| `MAX_UPLOAD_SIZE_BYTES` | `20971520` | Maximum upload size (20 MB) |
| `ALLOWED_EXTENSIONS` | `.txt,.pdf` | Comma-separated allowed file extensions |

---

## Running the API

```bash
uvicorn app.main:app --reload
```

The server starts at: **http://localhost:8000**

---

## Swagger UI

Interactive API documentation is available at:

```
http://localhost:8000/docs
```

ReDoc alternative:

```
http://localhost:8000/redoc
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/api/v1/ingest/text` | Ingest pasted text or transcript |
| `POST` | `/api/v1/ingest/file` | Ingest `.txt` or `.pdf` file upload |
| `GET` | `/api/v1/ingest/{communication_id}` | Retrieve record by ID |
| `GET` | `/api/v1/ingest/project/{project_id}` | List all records for a project |

---

## Example Requests

### Ingest pasted text

```bash
curl -X POST http://localhost:8000/api/v1/ingest/text \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "proj-bridge-001",
    "content": "The concrete pour for pier 3 is scheduled for Thursday morning.",
    "source_type": "text"
  }'
```

### Ingest a meeting transcript

```bash
curl -X POST http://localhost:8000/api/v1/ingest/text \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "proj-bridge-001",
    "content": "PM: Timeline is now Q3.\nLead Eng: Materials ordered.\nClient: Approved.",
    "source_type": "transcript"
  }'
```

### Upload a `.txt` file

```bash
curl -X POST http://localhost:8000/api/v1/ingest/file \
  -F "project_id=proj-bridge-001" \
  -F "file=@meeting_notes.txt"
```

### Upload a `.pdf` file

```bash
curl -X POST http://localhost:8000/api/v1/ingest/file \
  -F "project_id=proj-bridge-001" \
  -F "file=@design_report.pdf"
```

### Retrieve by communication ID

```bash
curl http://localhost:8000/api/v1/ingest/{communication_id}
```

### List all communications for a project

```bash
curl http://localhost:8000/api/v1/ingest/project/proj-bridge-001
```

---

## CommunicationRecord Schema

```json
{
  "project_id": "proj-bridge-001",
  "communication_id": "550e8400-e29b-41d4-a716-446655440000",
  "source_type": "pdf_file",
  "timestamp": "2026-09-15T14:30:00+00:00",
  "raw_content": "--- Page 1 ---\nThe concrete...",
  "metadata": {
    "filename": "design_report.pdf",
    "file_extension": ".pdf",
    "page_count": 5,
    "char_count": 12400,
    "pages": [
      { "page_number": 1, "char_count": 3200, "text_preview": "The concrete..." }
    ]
  },
  "storage_path": "raw/550e8400_design_report.pdf",
  "status": "ingested"
}
```

---

## Storage Structure

```
storage/
├── raw/          ← Original uploaded files (named by communication_id + original filename)
└── processed/    ← Normalized CommunicationRecord JSON files (named by communication_id)
```

Raw and processed data are kept strictly separate.
The `storage_path` field in each record points to the original file in `raw/`.

---

## Running Tests

```bash
py -m pytest tests/ -v --tb=short
# Expected: 132 passed (83 Module 1 + 49 Module 2)
```

All Module 2 tests use `FakeLLMProvider` — **no real API calls required**.

---

## Project Structure

```
archscale/
├── app/
│   ├── main.py                          # FastAPI app entry point
│   ├── config.py                        # Settings (storage + LLM) via env vars
│   ├── api/
│   │   ├── __init__.py
│   │   ├── action_extraction.py         # Module 3: Action extraction endpoints
│   │   ├── ingestion.py                 # Module 1: Ingestion endpoints
│   │   └── understanding.py             # Module 2: Understanding endpoints
│   ├── models/
│   │   ├── __init__.py
│   │   ├── action_extraction.py         # ExtractedAction, ActionExtractionResult
│   │   ├── communication.py             # CommunicationRecord, SourceType
│   │   └── understanding.py             # UnderstandingResult
│   ├── services/
│   │   ├── __init__.py
│   │   ├── action_extraction_service.py # Action extraction business logic
│   │   ├── ingestion_service.py         # Ingestion orchestration
│   │   └── understanding_service.py     # Understanding orchestration
│   ├── llm/
│   │   ├── base.py                      # LLMProvider abstract class
│   │   └── provider.py                  # Gemini, FakeLLMProvider, factory
│   ├── prompts/
│   │   ├── action_extraction.py         # Action extraction system & user prompts
│   │   └── understanding.py             # Understanding system & user prompts
│   └── utils/
│       ├── pdf_extractor.py             # PDF text extraction (pypdf)
│       └── validators.py                # Reusable input validation helpers
├── storage/
│   ├── raw/                             # Original uploaded files
│   └── processed/                       # Normalized CommunicationRecord JSON
├── tests/
│   ├── conftest.py                      # Shared fixtures (storage, PDF builder)
│   ├── test_ingestion_api.py            # Module 1 HTTP tests
│   ├── test_ingestion_service.py        # Module 1 service tests
│   ├── test_validators.py               # Validator unit tests
│   ├── test_llm_provider.py             # Module 2 LLM provider tests
│   ├── test_understanding_service.py    # Module 2 service tests
│   ├── test_understanding_api.py        # Module 2 HTTP tests
│   ├── test_action_extraction_service.py# Module 3 service tests
│   └── test_action_extraction_api.py    # Module 3 HTTP tests
├── requirements.txt
├── .env.example
└── README.md
```

---

## Module 2 — Communication Understanding

### Purpose

Answer: *"What is this communication about, who is involved, what type is it, and what context should later modules know?"*

> ⚠️ No task, deadline, responsibility, or decision extraction is performed in Module 2. Those belong to Module 3+.

### Architecture

```
CommunicationRecord (Module 1)
    ↓
CommunicationUnderstandingService
    ↓
LLMProvider  (Gemini / OpenAI / Fake — injected)
    ↓
UnderstandingResult  →  Module 3+
```

### Configuration

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `gemini` | `gemini` or `fake` |
| `LLM_MODEL` | `gemini-2.0-flash` | Model name |
| `LLM_API_KEY` | _(empty)_ | API key — **never commit** |
| `LLM_TIMEOUT_SECONDS` | `30` | Timeout in seconds |
| `LLM_MAX_RETRIES` | `2` | Retry count |

Set `LLM_PROVIDER=fake` to run without any API key.

### Endpoint

```
POST /api/v1/understanding/analyze
```

**Request:**
```json
{ "communication_id": "<uuid from Module 1>" }
```

**Response:**
```json
{
  "success": true,
  "data": {
    "project_id": "villa-001",
    "communication_id": "abc-123",
    "concise_summary": "The client approved the revised kitchen layout...",
    "detailed_summary": "...",
    "topics": ["kitchen layout", "structural drawing"],
    "stakeholders": ["client", "architect"],
    "communication_type": "mixed",
    "important_context": ["The revised kitchen layout has been approved."],
    "analyzed_at": "2026-09-15T14:30:00Z",
    "llm_model": "gemini"
  }
}
```

---

## Module 3 — Action Extraction

### Purpose

Answer: *"What actions/tasks are being requested, committed to, assigned, or clearly expected to happen?"*

Converts unstructured action statements from project communications into structured action objects.

> ⚠️ **Important Module Boundary:**
> Module 3 is ONLY responsible for identifying actions.
> It does **NOT** extract:
> - `owner` / `responsible_person` (Module 4)
> - `deadline` / `due_date` (Module 4)
> - `decision` / `approval` (later modules)
> - Reminders, notifications, memory, or execution.

### Key Principles

1. **Source of Truth**: The raw communication from Module 1 is the authoritative evidence. Module 2 understanding provides contextual grounding.
2. **Controlled Errors**: If Module 2 understanding is unavailable or fails, a controlled error (HTTP 502) is returned instead of silently falling back.
3. **Server-Side Action IDs**: UUID4 identifiers are generated server-side for each action to ensure consistency and prevent hallucinations.
4. **Action vs Fact vs Discussion**:
   - **Action**: *"Architect will send the structural drawing by Friday."* → Action: *"Send the structural drawing"*
   - **Fact**: *"The structural drawing was sent yesterday."* → `actions: []`
   - **Discussion**: *"The team discussed the revised kitchen layout."* → `actions: []`

### Endpoint

```
POST /api/v1/actions/extract
```

**Request:**
```json
{
  "communication_id": "7e5381ee-59f4-427f-88ac-3dcf6982d218"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "project_id": "villa-001",
    "communication_id": "7e5381ee-59f4-427f-88ac-3dcf6982d218",
    "actions": [
      {
        "action_id": "4e183707-ca90-4c7b-b380-60298a09fca9",
        "action": "Send the structural drawing",
        "evidence": "Architect will send the structural drawing by Friday.",
        "confidence": 0.95,
        "action_type": "deliverable"
      }
    ],
    "extracted_at": "2026-09-15T17:10:00Z",
    "llm_model": "gemini"
  }
}
```

### Action Types

- `task`: Routine or direct work item
- `request`: Explicit request from a participant
- `follow_up`: Checking back or monitoring progress
- `review`: Evaluating, checking, or reviewing drawings/specs
- `deliverable`: Artifact, drawing, document, or physical deliverable
- `coordination`: Syncing or cross-discipline coordination
- `other`: Fallback when classification is uncertain

---

## Module 4: Responsibility Detection

Determines **who is responsible for performing each already-extracted action** from Module 3.

- **Strict Boundary**: Handles strictly responsibility assignments, classification (`person`, `role`, `team`, `organization`, `group`, `unknown`), supporting verbatim evidence, and confidence. Rejects all deadline, decision, and priority fields (`extra="forbid"`).
- **Anti-Hallucination**: Never assigns ownership merely because an entity appears in conversation; requires explicit evidence.
- **Server-Side ID Generation**: Action linking preserves Module 3 `action_id`, and `responsibility_id` is generated server-side via UUID4.

### Endpoint

```http
POST /api/v1/responsibilities/extract
```

**Request:**
```json
{
  "communication_id": "7e5381ee-59f4-427f-88ac-3dcf6982d218",
  "include_understanding_context": true
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "project_id": "villa-001",
    "communication_id": "7e5381ee-59f4-427f-88ac-3dcf6982d218",
    "assignments": [
      {
        "responsibility_id": "8f3b3810-7798-4ca9-9686-353246ebec21",
        "action_id": "4e183707-ca90-4c7b-b380-60298a09fca9",
        "responsible_party": "Architect",
        "responsibility_type": "role",
        "evidence": "Architect will send the structural drawing by Friday.",
        "confidence": 0.95
      }
    ],
    "extracted_at": "2026-09-15T17:15:00Z",
    "llm_model": "gemini"
  }
}
```

---

## Testing

```powershell
# Run all tests across Modules 1, 2, 3, and 4
py -m pytest tests/ -v --tb=short
```

Current test status: **196 tests passing** (83 Module 1 + 49 Module 2 + 32 Module 3 + 32 Module 4).

---

## Roadmap

- **Module 1**: Communication Ingestion ✅
- **Module 2**: Communication Understanding ✅
- **Module 3**: Action Extraction ✅
- **Module 4**: Responsibility Detection ✅
- **Module 5**: Deadline Detection
- **Module 6**: Decision / Approval Extraction
- **Module 7**: Conversation → Structured Task

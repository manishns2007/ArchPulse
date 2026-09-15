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
pytest tests/ -v --tb=short
```

Test coverage includes:

- Text and transcript ingestion
- TXT and PDF file upload
- PDF page metadata extraction
- Unsupported file type rejection
- Empty and malformed input rejection
- project_id validation (format, blank, missing)
- Retrieve by communication ID (found and 404)
- Project communication listing (isolation, ordering)
- Raw file persistence verification
- Processed JSON persistence verification
- Path traversal protection
- Health endpoint

---

## Project Structure

```
archscale/
├── app/
│   ├── main.py                  # FastAPI application entry point
│   ├── config.py                # Settings via environment variables
│   ├── models/
│   │   └── communication.py     # CommunicationRecord + enums + request/response schemas
│   ├── api/
│   │   └── ingestion.py         # HTTP route handlers (thin layer)
│   ├── services/
│   │   └── ingestion_service.py # Core ingestion business logic
│   └── utils/
│       ├── pdf_extractor.py     # PDF text extraction (pypdf)
│       └── validators.py        # Reusable input validation helpers
├── storage/
│   ├── raw/                     # Original uploaded files
│   └── processed/               # Normalized JSON records
├── tests/
│   ├── conftest.py              # Shared fixtures (isolated storage, PDF builder)
│   ├── test_ingestion_api.py    # HTTP endpoint tests
│   ├── test_ingestion_service.py# Service layer unit tests
│   └── test_validators.py       # Validator unit tests
├── requirements.txt
├── .env.example
└── README.md
```

---

## Next Steps (Module 2+)

Module 1 produces `CommunicationRecord` objects. Future modules will:

- **Module 2**: AI extraction — tasks, deadlines, decisions, responsibilities
- **Module 3**: Project memory & semantic search (RAG)
- **Module 4**: Autonomous communication agent & notifications
- **Module 5**: Dashboard & reporting

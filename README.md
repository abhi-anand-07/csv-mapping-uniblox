# AI Mapping Copilot

> End-to-end AI-powered column mapping system for insurance operations.
> Users upload messy CSVs. A multi-step AI agent proposes mappings to a canonical schema. Humans review, edit, and approve before publishing clean data.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Tech Stack](#tech-stack)
4. [Project Structure](#project-structure)
5. [The Multi-Step Agent (Deep Dive)](#the-multi-step-agent-deep-dive)
6. [Gemini Prompts](#gemini-prompts)
7. [Fallback / Rule-Based Mapper](#fallback--rule-based-mapper)
8. [Validation & Guardrails](#validation--guardrails)
9. [API Reference](#api-reference)
10. [Frontend Components](#frontend-components)
11. [Canonical Schema](#canonical-schema)
12. [Setup & Installation](#setup--installation)
13. [Running the Application](#running-the-application)
14. [Test Data](#test-data)
15. [Edge Cases Handled](#edge-cases-handled)
16. [Future Improvements](#future-improvements)

---

## Overview

Insurance companies receive spreadsheets from brokers, employers, and third parties. Every sender uses different column names:

| Sender A | Sender B | Sender C | **Canonical** |
|----------|----------|----------|---------------|
| `Emp ID` | `employee#` | `EID` | `employee_id` |
| `F Name` | `given name` | `fname` | `first_name` |
| `DOB` | `Birth Dt` | `BDate` | `date_of_birth` |
| `Annual Pay` | `compensation` | `salary` | `annual_salary` |

**AI Mapping Copilot** automates this normalization:

1. **Upload** — User drops a CSV into the browser
2. **Ingest** — Backend parses headers, sample rows, detects data types
3. **Map** — Gemini LLM proposes mappings with confidence scores and reasoning
4. **Validate** — Backend checks for conflicts, missing required fields, low confidence
5. **Review** — User sees a table of proposals, can edit any mapping via dropdown
6. **Approve** — User confirms the mappings are correct
7. **Publish** — Backend generates a clean CSV with canonical column names
8. **Download** — User downloads the normalized file

---

## Architecture

```
┌─────────────────┐      HTTP POST /api/upload
│   React UI      │──────────────────────────────┐
│  (localhost     │                              │
│    :5173)       │◀─────────────────────────────┘
└─────────────────┘      JSON: proposed mappings
         │
         │ PATCH /api/mappings/{id}
         │ POST  /api/approve/{id}
         │ POST  /api/publish/{id}
         │ GET   /api/download/{id}
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Backend                           │
│                   (localhost :8000)                          │
│                                                              │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐      │
│  │  CSV Parser │─▶│  AI Agent    │─▶│  Validator    │      │
│  │             │  │  (Gemini)    │  │               │      │
│  └─────────────┘  └──────────────┘  └───────────────┘      │
│         │                  │                 │              │
│         │                  │                 ▼              │
│         │                  │          ┌──────────────┐      │
│         │                  │          │  Conflict    │      │
│         │                  │          │  Detection   │      │
│         │                  │          └──────────────┘      │
│         │                  │                                │
│         ▼                  ▼                                │
│  ┌────────────────────────────────────┐                     │
│  │   Session Store (in-memory +       │                     │
│  │   filesystem for CSVs)             │                     │
│  └────────────────────────────────────┘                     │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ generateContent
                              ▼
                    ┌───────────────────┐
                    │   Google Gemini   │
                    │   (LLM)           │
                    └───────────────────┘
```

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Frontend** | React 18 + TypeScript | UI components |
| **Frontend** | Vite | Build tool & dev server |
| **Frontend** | Axios | HTTP client |
| **Backend** | FastAPI | API framework |
| **Backend** | Pandas | CSV parsing & type detection |
| **Backend** | Google Generative AI | Gemini LLM integration |
| **Backend** | python-dotenv | Environment configuration |

---

## Project Structure

```
apm-uniblox/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI routes & endpoints
│   │   ├── agent.py             # Multi-step AI agent (Gemini + fallback)
│   │   ├── csv_parser.py        # CSV ingestion & type detection
│   │   ├── models.py            # Pydantic data models
│   │   ├── database.py          # Session storage (in-memory)
│   │   └── config.py            # Canonical schema & env vars
│   ├── data/                    # Runtime storage for uploaded/published CSVs
│   ├── test_data/
│   │   ├── messy_sample.csv     # Common messy headers
│   │   └── tricky_sample.csv    # Ambiguous / conflicting columns
│   ├── venv/                    # Python virtual environment
│   ├── requirements.txt
│   ├── .env                     # API keys (gitignored)
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── index.css
│   │   ├── types.ts
│   │   ├── vite-env.d.ts
│   │   └── components/
│   │       ├── Upload.tsx
│   │       ├── MappingReview.tsx
│   │       ├── ConfidenceBadge.tsx
│   │       └── ExplanationPanel.tsx
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   └── tsconfig.json
├── start.sh                     # One-command startup script
└── README.md                    # This file
```

---

## The Multi-Step Agent (Deep Dive)

The agent lives in `backend/app/agent.py` and runs a 4-step pipeline:

### Step 1: Ingestion (`csv_parser.py`)

**What it does:**
- Reads the CSV file with encoding fallback (`utf-8` → `latin1` → `cp1252`)
- Handles unnamed columns (`Unnamed: 0` → `unnamed_col_1`)
- Handles duplicate column names (`status` → `status`, `status_dup2`)
- Extracts first 5 rows as sample data
- Detects the semantic data type of each column

**Type detection heuristics:**

```python
def detect_type(series: pd.Series) -> str:
    # 1. Boolean check: yes/no, true/false, 1/0, y/n, t/f
    # 2. Numeric check: parses as number after stripping $ and ,
    #    - If all whole numbers → "integer"
    #    - If decimals → "numeric"
    # 3. Date check: pd.to_datetime with 80% success threshold
    # 4. State check: 2-letter US state codes
    # 5. ZIP check: 5-digit numeric strings
    # 6. Default → "string"
```

**Safety consideration:** We only extract headers + 5 sample rows. The full dataset never leaves the server.

### Step 2: Mapping Proposal (Gemini)

**What it does:**
Constructs a detailed prompt and sends it to Gemini. The prompt includes:
- The full canonical schema with descriptions and types
- Column metadata (detected type, null percentage, sample values)
- First 5 sample rows as JSON
- Strict instructions on output format

**See [Gemini Prompts](#gemini-prompts) below for the exact prompt text.**

**What Gemini returns:**
A JSON object with:
- `mappings`: array of `{source_column, target_column, confidence, reasoning, warnings}`
- `unmapped_columns`: columns with no good match
- `missing_required_fields`: required canonical fields not found
- `summary`: human-readable paragraph about mapping quality

### Step 3: Validation

**What it does:**
Takes Gemini's proposal and hardens it:

1. **Conflict detection:**
   - Multiple sources → same target? Flag warning, reduce confidence
   - Same source → multiple targets? Flag warning, reduce confidence

2. **Confidence scoring:**
   - `≥ 0.85` → `HIGH`
   - `0.60 – 0.84` → `MEDIUM`
   - `0.30 – 0.59` → `LOW`
   - `< 0.30` → `UNCERTAIN`

3. **Required field check:**
   - Computes which required fields (`employee_id`, `first_name`, `last_name`, `date_of_birth`) are missing

4. **Post-processing:**
   - Attaches sample values from ingestion to each mapping for UI display

### Step 4: Explanation

**What it does:**
- Generates overall summary from Gemini's response
- Enriches each mapping with human-readable reasoning
- Surfaces warnings in the UI (conflicts, type mismatches, high null rates)

---

## Gemini Prompts

### Primary Mapping Prompt

This is the exact prompt sent to Gemini in `agent.py`:

```
You are an expert data mapping AI for an insurance operations platform.
Your task is to map messy, inconsistent spreadsheet column headers to a canonical schema.

## Canonical Schema
- employee_id: Unique identifier for the employee (type: string, required: true)
- first_name: Employee's first name (type: string, required: true)
- last_name: Employee's last name (type: string, required: true)
- date_of_birth: Employee's date of birth YYYY-MM-DD preferred (type: date, required: true)
- state: US state abbreviation or full name (type: string, required: false)
- zip: 5-digit ZIP code (type: string, required: false)
- annual_salary: Annual salary in USD numeric (type: numeric, required: false)
- hire_date: Date hired YYYY-MM-DD preferred (type: date, required: false)
- employment_status: Employment status e.g. active terminated on-leave (type: string, required: false)
- coverage_amount: Insurance coverage amount in USD (type: numeric, required: false)
- smoker: Whether employee is a smoker yes/no true/false 1/0 (type: boolean, required: false)
- dependent_count: Number of dependents integer (type: integer, required: false)

## Input Spreadsheet Information
- Total rows: {row_count}
- Columns ({count}):
  - 'Emp ID': detected_type=string, null_pct=0%, samples=["E001", "E002"]
  - 'F Name': detected_type=string, null_pct=0%, samples=["John", "Jane"]
  ... (one per column)

## First 5 Sample Rows
{json sample rows}

## Instructions
For each input column, decide:
1. Which canonical field it maps to (or null if no good match)
2. Confidence score (0.0 to 1.0)
3. Brief reasoning (1-2 sentences)
4. Any warnings (e.g., "High null rate", "Ambiguous header")

Rules:
- A source column can map to at most ONE canonical field.
- Multiple source columns CAN map to the same canonical field (flag as warning if >1).
- If no canonical field matches well, set target_column to null.
- For required fields that are missing, still include them in your output with source_column set to null.
- Confidence should reflect: header similarity, data type match, sample value coherence, null rate.
- smoker field: map columns with yes/no, true/false, 1/0 values.

## Output Format
Return ONLY a valid JSON object with this exact structure (no markdown, no extra text):

{
  "mappings": [
    {
      "source_column": "original header name or null",
      "target_column": "canonical name or null",
      "confidence": 0.95,
      "reasoning": "Why this mapping makes sense",
      "warnings": ["optional warning"]
    }
  ],
  "unmapped_columns": ["header1", "header2"],
  "missing_required_fields": ["field1"],
  "summary": "One paragraph summary of the mapping quality and any concerns."
}
```

**Generation config:**
- Temperature: `0.2` (low creativity, high consistency)
- Max output tokens: `4096`

---

## Fallback / Rule-Based Mapper

If Gemini is unavailable (no API key, network error, rate limit), the system falls back to a rule-based mapper.

### Header Aliases

The mapper maintains a dictionary of common abbreviations:

```python
HEADER_ALIASES = {
    "employee_id": ["id", "emp id", "employee id", "emp_id", "eid", "employee#", "emp#"],
    "first_name": ["fname", "first name", "first", "given name", "name first"],
    "last_name": ["lname", "last name", "last", "surname", "family name", "name last"],
    "date_of_birth": ["dob", "birth date", "birthdate", "birth_dt", "bdate", "date of birth"],
    "state": ["st", "state_code", "state code", "province"],
    "zip": ["zipcode", "zip code", "postal", "postal code"],
    "annual_salary": ["salary", "pay", "compensation", "wage", "income", "annual pay", "salary_annual"],
    "hire_date": ["hired", "date hired", "start date", "employment date", "hire dt"],
    "employment_status": ["status", "emp status", "work status", "job status"],
    "coverage_amount": ["coverage", "insurance amount", "coverage amt", "benefit amount"],
    "smoker": ["smoking", "tobacco", "is_smoker", "smoker status", "smokes"],
    "dependent_count": ["dependents", "num dependents", "dependent #", "children", "num children"],
}
```

### Matching Logic

1. **Alias matching** — Strip punctuation, lowercase, check if header contains alias (or vice versa)
   - Exact match → confidence `0.98`
   - Substring match → confidence `0.85`

2. **Fuzzy token matching** — Split header and target into words, count overlapping tokens
   - Score = `0.5 + (matching_tokens / max_tokens) * 0.4`

3. **Type validation** — If detected type doesn't match expected type, add warning and reduce confidence

4. **Null rate warning** — If `null_percentage > 50%`, add warning

### Scoring

```
Best score > 0.60  → Map with confidence = score
Best score ≤ 0.60  → Leave unmapped (confidence = 0.0)
```

---

## Validation & Guardrails

### Human-in-the-Loop Requirements

| Guardrail | Implementation |
|-----------|----------------|
| **No raw data to LLM** | Only headers + 5 sample rows sent to Gemini |
| **Required fields** | Publish blocked until `employee_id`, `first_name`, `last_name`, `date_of_birth` are mapped |
| **Confidence display** | Every mapping shows visual badge: High / Medium / Low / Uncertain |
| **Conflict detection** | Warnings shown when multiple sources → same target |
| **Approval gate** | User must explicitly click "Approve & Publish" |
| **Edit capability** | Any mapping can be changed or unmapped before approval |
| **Fallback mode** | Works without API key; never fails silently |

### Conflict Detection Example

If a CSV has both `date hired` and `start date`, both might map to `hire_date`:

```
⚠️ Conflict: 'hire_date' is mapped by multiple sources: ['date hired', 'start date']
```

The system:
- Keeps both mappings
- Reduces confidence by `0.2`
- Downgrades confidence level
- Surfaces warning in UI

---

## API Reference

### `POST /api/upload`
Upload a CSV file and trigger the AI agent.

**Request:** `multipart/form-data` with `file` field

**Response:** `MappingProposal`
```json
{
  "session_id": "uuid",
  "file_name": "data.csv",
  "ingestion": { "headers": [...], "sample_rows": [...], "row_count": 100 },
  "mappings": [
    {
      "source_column": "Emp ID",
      "target_column": "employee_id",
      "confidence": 1.0,
      "confidence_level": "high",
      "reasoning": "Clear match...",
      "sample_values": ["E001", "E002"],
      "warnings": []
    }
  ],
  "unmapped_columns": ["Extra Col"],
  "missing_required_fields": [],
  "overall_confidence": 1.0,
  "summary": "Mapping quality is excellent...",
  "status": "proposed"
}
```

### `GET /api/schema`
Returns the canonical schema for dynamic UI dropdowns.

**Response:**
```json
{
  "schema": {
    "employee_id": { "type": "string", "required": true, "description": "..." }
  },
  "required_fields": ["employee_id", "first_name", "last_name", "date_of_birth"]
}
```

### `GET /api/mappings/{session_id}`
Retrieve the current mapping proposal.

### `PATCH /api/mappings/{session_id}`
Edit mappings. Send array of updates:
```json
[
  { "source_column": "F Name", "target_column": "first_name" },
  { "source_column": "Extra Col", "target_column": null }
]
```

### `POST /api/approve/{session_id}`
Mark mappings as approved.

### `POST /api/publish/{session_id}`
Generate the canonical CSV.

**Response:** `PublishResult`
```json
{
  "session_id": "uuid",
  "download_url": "/api/download/uuid",
  "row_count": 100,
  "column_count": 12,
  "mapped_fields": ["employee_id", "first_name", ...],
  "unmapped_fields": []
}
```

### `GET /api/download/{session_id}`
Download the published CSV file.

---

## Frontend Components

### `App.tsx`
- Root component. Holds `proposal` state.
- Clears old proposal before showing new upload (prevents stale data flash)
- Renders `Upload` + `MappingReview` (with `key={session_id}` to force remount)

### `Upload.tsx`
- Drag-and-drop zone with click fallback
- File type validation (`.csv` only)
- Size validation (max 10MB)
- Shows spinner while waiting for AI agent
- Calls `POST /api/upload`

### `MappingReview.tsx`
- Fetches `/api/schema` on mount for dynamic dropdown options
- Displays mapping table with:
  - Source column name
  - Sample values (first 3 non-null)
  - Dropdown to edit target (built from live schema)
  - Confidence badge
  - AI reasoning
  - Warning badges
- Tracks `edits` state for unsaved changes
- "Save Edits" button calls `PATCH /api/mappings/{id}`
- "Approve & Publish" button:
  - Disabled if required fields are missing
  - Calls `POST /api/approve` then `POST /api/publish`
  - Shows success card with download link

### `ConfidenceBadge.tsx`
- Visual indicator with color dot
- Shows level name + percentage
- Colors: Green (High), Yellow (Medium), Orange (Low), Red (Uncertain)

### `ExplanationPanel.tsx`
- Shows AI-generated summary paragraph
- Displays three metric cards:
  - Overall Confidence
  - Unmapped Columns
  - Missing Required Fields
- Shows red alert banner if required fields are missing

---

## Canonical Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `employee_id` | string | ✅ | Unique identifier |
| `first_name` | string | ✅ | Employee's first name |
| `last_name` | string | ✅ | Employee's last name |
| `date_of_birth` | date | ✅ | YYYY-MM-DD preferred |
| `state` | string | ❌ | US state abbreviation or full name |
| `zip` | string | ❌ | 5-digit ZIP code |
| `annual_salary` | numeric | ❌ | Annual salary in USD |
| `hire_date` | date | ❌ | Date hired |
| `employment_status` | string | ❌ | active, terminated, on-leave |
| `coverage_amount` | numeric | ❌ | Insurance coverage amount |
| `smoker` | boolean | ❌ | yes/no, true/false, 1/0 |
| `dependent_count` | integer | ❌ | Number of dependents |

---

## Setup & Installation

### Prerequisites
- Python 3.11+
- Node.js 18+

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Add your Gemini API key (optional - fallback works without it)
cp .env.example .env
# Edit .env and set GEMINI_API_KEY
```

### Frontend

```bash
cd frontend
npm install
```

---

## Running the Application

### Option 1: Manual Start

Terminal 1 (Backend):
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Terminal 2 (Frontend):
```bash
cd frontend
npm run dev
```

### Option 2: Startup Script

```bash
./start.sh
```

### Access
- **Frontend UI**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs (Swagger UI)

---

## Test Data

Two sample CSVs are included for testing:

### `test_data/messy_sample.csv`
Common real-world messy headers:
- `Emp ID`, `F Name`, `LName`, `BirthDt`
- `St`, `Zip Code`, `Annual Pay`, `Hired`
- `Smokes?`, `Num Dependents`

**Expected behavior:** All map cleanly to canonical fields. `Extra Col` remains unmapped.

### `test_data/tricky_sample.csv`
Columns that force tradeoffs:
- `date hired` vs `start date` → both want `hire_date` (conflict)
- `department` → no canonical match (unmapped)
- `tobacco use` → maps to `smoker`
- `children count` → maps to `dependent_count`

**Expected behavior:** Conflict warning on `hire_date`. `department` left unmapped.

---

## Edge Cases Handled

| Edge Case | How It's Handled |
|-----------|------------------|
| **Empty CSV** | Rejected with 400 error |
| **Non-CSV file** | Rejected with 400 error |
| **File > 10MB** | Rejected with 400 error |
| **Wrong encoding** | Tries utf-8 → latin1 → cp1252 |
| **Unnamed columns** | Renamed to `unnamed_col_1`, etc. |
| **Duplicate headers** | Renamed to `name_dup2`, `name_dup3` |
| **Epoch integer false positives** | Type detector checks numeric before date (so `0`, `1`, `2` don't become dates) |
| **Gemini API failure** | Automatic fallback to rule-based mapper |
| **Gemini returns invalid JSON** | Extracts JSON from markdown blocks, falls back if parsing fails |
| **User edits then uploads new file** | Old state fully cleared via `key={session_id}` remount |
| **Missing required fields** | Publish button disabled with tooltip explanation |
| **Multiple users uploading simultaneously** | Each gets unique session ID (UUID v4) |

---

## Future Improvements

1. **Persistent storage** — Replace in-memory sessions with PostgreSQL/MongoDB
2. **Authentication** — Add login so users only see their own uploads
3. **Batch processing** — Support multiple file uploads at once
4. **Custom schemas** — Let users define their own canonical schemas per tenant
5. **Learning loop** — Store user corrections to improve future suggestions
6. **Column transformation** — Apply data cleaning during publish (date formatting, currency normalization)
7. **Audit log** — Track who approved what and when
8. **Export formats** — Support Excel, JSON, Parquet in addition to CSV

---

## License

Internal use only. Built for insurance operations data normalization.

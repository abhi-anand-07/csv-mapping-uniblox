import io
import json
import os
from typing import List

import pandas as pd
from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.config import CANONICAL_SCHEMA, REQUIRED_FIELDS, ALLOWED_ORIGINS
from app.database import (
    create_session,
    get_session,
    update_session,
    set_session_status,
    save_csv,
    get_csv_path,
    save_published_csv,
    get_published_csv_path,
)
from app.csv_parser import parse_csv
from app.agent import run_mapping_agent
from app.models import (
    MappingProposal,
    MappingUpdateRequest,
    PublishResult,
    ColumnMapping,
)

app = FastAPI(title="AI Mapping Copilot", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/schema")
def get_schema():
    """Return the canonical schema and required fields so the UI can build dynamic dropdowns."""
    return {
        "schema": CANONICAL_SCHEMA,
        "required_fields": REQUIRED_FIELDS,
    }


@app.post("/api/upload", response_model=MappingProposal)
async def upload_csv(file: UploadFile = File(...)):
    """
    Upload a CSV file and trigger the multi-step AI mapping agent.
    Returns the proposed mappings with confidence and reasoning.
    """
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")

    session_id = create_session()
    save_csv(session_id, content)

    try:
        ingestion = parse_csv(content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    proposal = run_mapping_agent(ingestion, session_id, file.filename)

    update_session(session_id, {"proposal": proposal.model_dump(), "file_name": file.filename})
    set_session_status(session_id, "proposed")

    return proposal


@app.get("/api/mappings/{session_id}", response_model=MappingProposal)
def get_mappings(session_id: str):
    """Retrieve the current mapping proposal for a session."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    proposal_data = session["data"].get("proposal")
    if not proposal_data:
        raise HTTPException(status_code=404, detail="No mapping proposal found for this session")
    return MappingProposal(**proposal_data)


@app.patch("/api/mappings/{session_id}")
def update_mapping(session_id: str, updates: List[MappingUpdateRequest]):
    """
    Allow user to edit mappings. Each update specifies a source_column and its new target.
    target_column can be null to unmap a column.
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    proposal_data = session["data"].get("proposal")
    if not proposal_data:
        raise HTTPException(status_code=404, detail="No mapping proposal found")

    proposal = MappingProposal(**proposal_data)
    set_session_status(session_id, "edited")

    # Build lookup of existing mappings by source column
    mapping_lookup = {m.source_column: m for m in proposal.mappings}

    for upd in updates:
        if upd.source_column in mapping_lookup:
            mapping_lookup[upd.source_column].target_column = upd.target_column
            if upd.target_column is None:
                mapping_lookup[upd.source_column].confidence = 0.0
                mapping_lookup[upd.source_column].confidence_level = "uncertain"
                mapping_lookup[upd.source_column].reasoning = "Unmapped by user during review."
            else:
                mapping_lookup[upd.source_column].confidence = 1.0
                mapping_lookup[upd.source_column].confidence_level = "high"
                mapping_lookup[upd.source_column].reasoning = "Confirmed by user during review."
        else:
            # New mapping for a previously unmapped or new source
            new_map = ColumnMapping(
                source_column=upd.source_column,
                target_column=upd.target_column,
                confidence=1.0,
                confidence_level="high",
                reasoning="Added by user during review.",
                sample_values=[],
            )
            proposal.mappings.append(new_map)

    # Recalculate unmapped and missing required
    mapped_targets = {m.target_column for m in proposal.mappings if m.target_column}
    proposal.unmapped_columns = [
        m.source_column for m in proposal.mappings if not m.target_column and m.source_column
    ]
    proposal.missing_required_fields = [
        f for f in [k for k, v in CANONICAL_SCHEMA.items() if v["required"]] if f not in mapped_targets
    ]

    mapped_scores = [m.confidence for m in proposal.mappings if m.target_column]
    proposal.overall_confidence = round(sum(mapped_scores) / len(mapped_scores), 2) if mapped_scores else 0.0

    update_session(session_id, {"proposal": proposal.model_dump()})
    return proposal


@app.post("/api/approve/{session_id}")
def approve_mappings(session_id: str):
    """User approves the current mappings."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    set_session_status(session_id, "approved")
    return {"status": "approved", "session_id": session_id}


@app.post("/api/publish/{session_id}", response_model=PublishResult)
def publish_mappings(session_id: str):
    """
    Generate the final mapped CSV based on approved mappings.
    Returns a download URL and metadata.
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    proposal_data = session["data"].get("proposal")
    if not proposal_data:
        raise HTTPException(status_code=404, detail="No mapping proposal found")

    proposal = MappingProposal(**proposal_data)
    csv_path = get_csv_path(session_id)
    if not csv_path:
        raise HTTPException(status_code=404, detail="Original CSV not found")

    df = pd.read_csv(csv_path)
    # Apply header deduplication same as parser
    headers = list(df.columns)
    seen = set()
    deduped = []
    counts = {}
    for h in headers:
        h_str = str(h).strip()
        if h_str.startswith("Unnamed:"):
            counts[h_str] = counts.get(h_str, 0) + 1
            deduped.append(f"unnamed_col_{counts[h_str]}")
        elif h_str in seen:
            counts[h_str] = counts.get(h_str, 1) + 1
            deduped.append(f"{h_str}_dup{counts[h_str]}")
        else:
            seen.add(h_str)
            deduped.append(h_str)
    df.columns = deduped

    # Build target -> source mapping
    target_to_source: dict = {}
    for m in proposal.mappings:
        if m.target_column and m.source_column:
            # If multiple sources map to same target, prefer first or concatenate
            if m.target_column not in target_to_source:
                target_to_source[m.target_column] = m.source_column

    # Create output dataframe with canonical columns
    output_data = {}
    mapped_fields = []
    unmapped_fields = []

    for canonical_field in CANONICAL_SCHEMA.keys():
        if canonical_field in target_to_source:
            src = target_to_source[canonical_field]
            if src in df.columns:
                output_data[canonical_field] = df[src]
                mapped_fields.append(canonical_field)
            else:
                output_data[canonical_field] = None
                unmapped_fields.append(canonical_field)
        else:
            output_data[canonical_field] = None
            unmapped_fields.append(canonical_field)

    output_df = pd.DataFrame(output_data)

    # Save published CSV
    csv_buffer = io.StringIO()
    output_df.to_csv(csv_buffer, index=False)
    save_published_csv(session_id, csv_buffer.getvalue().encode("utf-8"))
    set_session_status(session_id, "published")

    return PublishResult(
        session_id=session_id,
        download_url=f"/api/download/{session_id}",
        row_count=len(output_df),
        column_count=len(output_df.columns),
        mapped_fields=mapped_fields,
        unmapped_fields=unmapped_fields,
    )


@app.get("/api/download/{session_id}")
def download_published_csv(session_id: str):
    """Download the published canonical CSV."""
    path = get_published_csv_path(session_id)
    if not path:
        raise HTTPException(status_code=404, detail="Published file not found")
    return FileResponse(
        path,
        media_type="text/csv",
        filename=f"mapped_{session_id[:8]}.csv",
    )


# ── Static files + SPA fallback (production single-service deploy) ──
# Check multiple possible static locations (local dev vs Docker)
_static_candidates = [
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static")),
    "/app/static",
]
static_dir = next((d for d in _static_candidates if os.path.isdir(d)), None)
static_index = os.path.join(static_dir, "index.html") if static_dir else None

if static_dir and os.path.isdir(static_dir):
    # Serve Vite-generated assets
    app.mount("/assets", StaticFiles(directory=os.path.join(static_dir, "assets")), name="assets")

    @app.get("/")
    def serve_root():
        return FileResponse(static_index)

    @app.get("/logo.jpeg")
    def serve_logo():
        return FileResponse(os.path.join(static_dir, "logo.jpeg"))

    @app.get("/{path:path}")
    def serve_spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(status_code=404)
        if path.startswith("assets/"):
            raise HTTPException(status_code=404)
        # Serve actual static files (sample.csv, logo.jpeg, etc.)
        file_path = os.path.join(static_dir, path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
        # SPA fallback for client-side routes
        return FileResponse(static_index)

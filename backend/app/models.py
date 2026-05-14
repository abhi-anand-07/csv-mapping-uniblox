from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNCERTAIN = "uncertain"


class ColumnMapping(BaseModel):
    source_column: str = Field(..., description="Original column header from the CSV")
    target_column: Optional[str] = Field(None, description="Mapped canonical field name")
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="Confidence score 0-1")
    confidence_level: ConfidenceLevel = Field(ConfidenceLevel.UNCERTAIN, description="Human-readable confidence level")
    reasoning: str = Field("", description="Explanation for why this mapping was chosen")
    suggested_alternative: Optional[str] = Field(None, description="Alternative target if user disagrees")
    sample_values: List[str] = Field(default_factory=list, description="First few non-null values from this column")
    warnings: List[str] = Field(default_factory=list, description="Any validation warnings")


class IngestionResult(BaseModel):
    headers: List[str]
    sample_rows: List[Dict[str, Any]]
    row_count: int
    column_stats: Dict[str, Dict[str, Any]]
    parsing_warnings: List[str] = Field(default_factory=list)


class MappingProposal(BaseModel):
    session_id: str
    file_name: str
    ingestion: IngestionResult
    mappings: List[ColumnMapping]
    unmapped_columns: List[str] = Field(default_factory=list)
    missing_required_fields: List[str] = Field(default_factory=list)
    overall_confidence: float = Field(0.0)
    summary: str = Field("", description="Overall summary of the mapping proposal")
    status: str = Field("proposed")  # proposed, edited, approved, published


class MappingUpdateRequest(BaseModel):
    source_column: str
    target_column: Optional[str] = None


class ApproveRequest(BaseModel):
    session_id: str


class PublishResult(BaseModel):
    session_id: str
    download_url: str
    row_count: int
    column_count: int
    mapped_fields: List[str]
    unmapped_fields: List[str]

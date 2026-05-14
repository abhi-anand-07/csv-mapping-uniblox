import json
import re
from typing import List, Dict, Optional, Any
import google.generativeai as genai

from app.config import GEMINI_API_KEY, GEMINI_MODEL, CANONICAL_SCHEMA, REQUIRED_FIELDS
from app.models import IngestionResult, ColumnMapping, ConfidenceLevel, MappingProposal


# Configure Gemini if key is available
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


def _build_mapping_prompt(ingestion: IngestionResult) -> str:
    """Construct a rich prompt for the Gemini model to propose column mappings."""

    schema_description = "\n".join(
        f"- {name}: {info['description']} (type: {info['type']}, required: {info['required']})"
        for name, info in CANONICAL_SCHEMA.items()
    )

    sample_rows_text = json.dumps(ingestion.sample_rows, indent=2, default=str)

    column_info_lines = []
    for col in ingestion.headers:
        stats = ingestion.column_stats[col]
        samples = stats["sample_values"]
        sample_str = ", ".join(f'"{s}"' for s in samples[:3])
        column_info_lines.append(
            f"  - '{col}': detected_type={stats['detected_type']}, "
            f"null_pct={stats['null_percentage']}%, samples=[{sample_str}]"
        )
    column_info = "\n".join(column_info_lines)

    prompt = f"""You are an expert data mapping AI for an insurance operations platform.
Your task is to map messy, inconsistent spreadsheet column headers to a canonical schema.

## Canonical Schema
{schema_description}

## Input Spreadsheet Information
- Total rows: {ingestion.row_count}
- Columns ({len(ingestion.headers)}):
{column_info}

## First 5 Sample Rows
```json
{sample_rows_text}
```

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
- For required fields that are missing, still include them in your output with source_column set to null and note they are missing.
- Confidence should reflect: header similarity, data type match, sample value coherence, null rate.
- smoker field: map columns with yes/no, true/false, 1/0 values.

## Output Format
Return ONLY a valid JSON object with this exact structure (no markdown, no extra text):

{{
  "mappings": [
    {{
      "source_column": "original header name or null",
      "target_column": "canonical name or null",
      "confidence": 0.95,
      "reasoning": "Why this mapping makes sense",
      "warnings": ["optional warning"]
    }}
  ],
  "unmapped_columns": ["header1", "header2"],
  "missing_required_fields": ["field1"],
  "summary": "One paragraph summary of the mapping quality and any concerns."
}}
"""
    return prompt


def _parse_gemini_response(text: str) -> Dict[str, Any]:
    """Parse and clean the Gemini response to extract valid JSON."""
    # Try to extract JSON from markdown code blocks
    code_block_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if code_block_match:
        text = code_block_match.group(1).strip()

    # Sometimes the model wraps in extra brackets or text
    text = text.strip()
    if text.startswith("[") and text.endswith("]"):
        # Sometimes it returns an array, try first element
        text = text[1:-1].strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Fallback: find first { and last }
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            return json.loads(text[start:end+1])
        raise ValueError(f"Could not parse Gemini response as JSON: {text[:500]}")


def _fallback_mock_mapping(ingestion: IngestionResult) -> Dict[str, Any]:
    """
    Fallback rule-based mapping when Gemini is unavailable.
    Uses header name similarity heuristics.
    """
    from difflib import SequenceMatcher

    canonical_keys = list(CANONICAL_SCHEMA.keys())
    mappings = []
    unmapped = []
    mapped_targets = set()

    header_aliases = {
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

    for col in ingestion.headers:
        col_lower = re.sub(r"[^a-z0-9\s]", "", col.lower().replace("_", " ").strip())
        best_target = None
        best_score = 0.0
        best_reason = ""

        # Check aliases first
        for target, aliases in header_aliases.items():
            for alias in aliases:
                if alias in col_lower or col_lower in alias:
                    score = 0.85
                    if alias == col_lower:
                        score = 0.98
                    if score > best_score:
                        best_score = score
                        best_target = target
                        best_reason = f"Header '{col}' closely matches alias for '{target}'"

        # Fallback to fuzzy matching
        if best_score < 0.8:
            for target in canonical_keys:
                target_parts = target.lower().split("_")
                col_parts = col_lower.replace("-", " ").split()
                match_count = sum(1 for p in target_parts if any(p in c for c in col_parts))
                if match_count > 0:
                    score = 0.5 + (match_count / max(len(target_parts), 1)) * 0.4
                    if score > best_score:
                        best_score = score
                        best_target = target
                        best_reason = f"Header '{col}' shares tokens with '{target}'"

        stats = ingestion.column_stats[col]
        warnings = []
        if stats["null_percentage"] > 50:
            warnings.append(f"High null rate ({stats['null_percentage']}%)")
        if stats["detected_type"] != CANONICAL_SCHEMA.get(best_target, {}).get("type", "string"):
            if best_target and best_score < 0.95:
                warnings.append(f"Type mismatch: detected {stats['detected_type']} vs expected {CANONICAL_SCHEMA[best_target]['type']}")

        if best_score > 0.6:
            mappings.append({
                "source_column": col,
                "target_column": best_target,
                "confidence": round(best_score, 2),
                "reasoning": best_reason,
                "warnings": warnings,
            })
            mapped_targets.add(best_target)
        else:
            unmapped.append(col)
            mappings.append({
                "source_column": col,
                "target_column": None,
                "confidence": 0.0,
                "reasoning": f"Could not confidently map '{col}' to any canonical field",
                "warnings": warnings,
            })

    # Check required fields
    missing_required = [f for f in REQUIRED_FIELDS if f not in mapped_targets]

    # Add missing required as null mappings
    for req in missing_required:
        mappings.append({
            "source_column": None,
            "target_column": req,
            "confidence": 0.0,
            "reasoning": f"Required field '{req}' was not found in the input",
            "warnings": ["Missing required field"],
        })

    summary = f"Rule-based fallback mapping: {len([m for m in mappings if m['target_column']])} of {len(ingestion.headers)} columns mapped."
    if missing_required:
        summary += f" Missing required: {', '.join(missing_required)}."

    return {
        "mappings": mappings,
        "unmapped_columns": unmapped,
        "missing_required_fields": missing_required,
        "summary": summary,
    }


def _call_gemini(prompt: str) -> str:
    """Call the Gemini API and return the text response."""
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not configured")

    model = genai.GenerativeModel(GEMINI_MODEL)
    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(
            temperature=0.2,
            max_output_tokens=4096,
        ),
    )
    return response.text


def _confidence_to_level(score: float) -> ConfidenceLevel:
    if score >= 0.85:
        return ConfidenceLevel.HIGH
    elif score >= 0.6:
        return ConfidenceLevel.MEDIUM
    elif score >= 0.3:
        return ConfidenceLevel.LOW
    return ConfidenceLevel.UNCERTAIN


def run_mapping_agent(ingestion: IngestionResult, session_id: str, file_name: str) -> MappingProposal:
    """
    Multi-step AI agent that:
      1. Proposes mappings via Gemini (or fallback)
      2. Validates mappings for conflicts and coverage
      3. Enriches with confidence levels and explanations
    """

    # Step 2: Generate candidate mappings
    if GEMINI_API_KEY:
        try:
            prompt = _build_mapping_prompt(ingestion)
            raw_response = _call_gemini(prompt)
            parsed = _parse_gemini_response(raw_response)
        except Exception as e:
            # Fallback to mock on any Gemini failure
            parsed = _fallback_mock_mapping(ingestion)
            parsed["warnings"] = [f"Gemini failed ({e}), using fallback mapping"]
    else:
        parsed = _fallback_mock_mapping(ingestion)

    # Step 3: Validate mappings
    mappings_raw: List[Dict[str, Any]] = parsed.get("mappings", [])
    target_to_sources: Dict[str, List[str]] = {}
    source_to_targets: Dict[str, List[str]] = {}
    validated_mappings: List[ColumnMapping] = []

    for m in mappings_raw:
        src = m.get("source_column")
        tgt = m.get("target_column")
        conf = m.get("confidence", 0.0)
        reasoning = m.get("reasoning", "")
        warnings = list(m.get("warnings", []))

        if tgt:
            target_to_sources.setdefault(tgt, []).append(src)
        if src:
            source_to_targets.setdefault(src, []).append(tgt)

        validated_mappings.append(
            ColumnMapping(
                source_column=src or "",
                target_column=tgt,
                confidence=conf,
                confidence_level=_confidence_to_level(conf),
                reasoning=reasoning,
                warnings=warnings,
                sample_values=ingestion.column_stats.get(src or "", {}).get("sample_values", [])[:3],
            )
        )

    # Post-validation: flag conflicts
    for m in validated_mappings:
        tgt = m.target_column
        src = m.source_column
        if tgt and tgt in target_to_sources and len(target_to_sources[tgt]) > 1:
            m.warnings.append(
                f"Conflict: '{tgt}' is mapped by multiple sources: {target_to_sources[tgt]}"
            )
            m.confidence = max(0.3, m.confidence - 0.2)
            m.confidence_level = _confidence_to_level(m.confidence)
        if src and src in source_to_targets and len(source_to_targets[src]) > 1:
            m.warnings.append(
                f"Conflict: '{src}' maps to multiple targets: {source_to_targets[src]}"
            )
            m.confidence = max(0.3, m.confidence - 0.2)
            m.confidence_level = _confidence_to_level(m.confidence)

    # Calculate overall confidence
    mapped_scores = [m.confidence for m in validated_mappings if m.target_column]
    overall_confidence = round(sum(mapped_scores) / len(mapped_scores), 2) if mapped_scores else 0.0

    unmapped = parsed.get("unmapped_columns", [])
    missing_required = parsed.get("missing_required_fields", [])

    # If Gemini didn't explicitly list missing required, compute it
    mapped_targets = {m.target_column for m in validated_mappings if m.target_column}
    missing_required = missing_required or [f for f in REQUIRED_FIELDS if f not in mapped_targets]

    summary = parsed.get("summary", "")
    if not summary:
        summary = (
            f"Mapped {len([m for m in validated_mappings if m.target_column])} columns "
            f"with average confidence {overall_confidence:.0%}."
        )
        if missing_required:
            summary += f" Warning: missing required fields: {', '.join(missing_required)}."

    return MappingProposal(
        session_id=session_id,
        file_name=file_name,
        ingestion=ingestion,
        mappings=validated_mappings,
        unmapped_columns=unmapped,
        missing_required_fields=missing_required,
        overall_confidence=overall_confidence,
        summary=summary,
        status="proposed",
    )

export interface IngestionResult {
  headers: string[];
  sample_rows: Record<string, any>[];
  row_count: number;
  column_stats: Record<string, any>;
  parsing_warnings: string[];
}

export interface ColumnMapping {
  source_column: string;
  target_column: string | null;
  confidence: number;
  confidence_level: 'high' | 'medium' | 'low' | 'uncertain';
  reasoning: string;
  suggested_alternative?: string | null;
  sample_values: string[];
  warnings: string[];
}

export interface MappingProposal {
  session_id: string;
  file_name: string;
  ingestion: IngestionResult;
  mappings: ColumnMapping[];
  unmapped_columns: string[];
  missing_required_fields: string[];
  overall_confidence: number;
  summary: string;
  status: string;
}

export interface PublishResult {
  session_id: string;
  download_url: string;
  row_count: number;
  column_count: number;
  mapped_fields: string[];
  unmapped_fields: string[];
}

export interface Project {
  id: string
  name: string
  project_code: string
  aks_regex: string
  room_code_pattern: string
  room_format: string
  geraet_type_map: Record<string, string>
  created_at: string
  updated_at: string
}

export interface ProjectListItem {
  id: string
  name: string
  project_code: string
  created_at: string
  updated_at: string
  upload_count: number
}

export interface ProjectCreateRequest {
  name: string
  project_code: string
  aks_regex: string
  room_code_pattern?: string
  room_format?: string
  geraet_type_map: Record<string, string>
}

export interface ProjectUpdateRequest {
  name?: string
  project_code?: string
  aks_regex?: string
  room_code_pattern?: string
  room_format?: string
  geraet_type_map?: Record<string, string>
}

export interface Upload {
  id: string
  filename: string
  file_type: "schema_pdf" | "grundriss_pdf" | "revit_excel"
  file_size: number
  created_at: string
}

export interface ProjectDetail extends Project {
  uploads: Upload[]
}

export interface Task {
  id: string
  project_id: string
  task_type: string
  status: "pending" | "running" | "completed" | "failed"
  progress: number
  message: string | null
  result_path: string | null
  error: string | null
  created_at: string
  updated_at: string
}

export interface MatchResults {
  metadata: {
    equipment_filter: string
    total_matched: number
    total_unmatched_aks: number
    total_unmatched_revit: number
    rooms_processed: number
  }
  matches: Array<{
    room: string
    aks: string
    revit_guid: string
    revit_type: string
    confidence: "HIGH" | "MEDIUM" | "LOW"
    sort_axis: string
    sort_rank: number
    revit_x?: number
    revit_y?: number
    pdf_x?: number
    pdf_y?: number
    tables_id?: string
  }>
  unmatched_aks: Array<{ room: string; aks: string; reason: string }>
  unmatched_revit: Array<{ room: string; guid: string; reason: string }>
  room_summary: Record<
    string,
    {
      matched: number
      aks_count: number
      revit_count: number
      status: "MATCHED" | "NO_AKS" | "NO_REVIT" | "COUNT_MISMATCH"
      method?: string
      confidence?: string
    }
  >
}

// --- Review / Correction Types ---

export interface MatchEntry {
  room: string
  aks: string
  revit_guid: string
  revit_type: string
  confidence: "HIGH" | "MEDIUM" | "LOW" | "CORRECTED"
  sort_axis: string
  sort_rank: number
  revit_x?: number
  revit_y?: number
  pdf_x?: number
  pdf_y?: number
  tables_id?: string
}

export interface UnmatchedAks {
  room: string
  aks: string
  reason: string
}

export interface UnmatchedRevit {
  room: string
  guid: string
  reason: string
}

export interface RoomSummary {
  matched: number
  aks_count: number
  revit_count: number
  status: "MATCHED" | "NO_AKS" | "NO_REVIT" | "COUNT_MISMATCH"
  method?: string
  confidence?: string
}

export interface Correction {
  id: string
  project_id: string
  task_id: string
  room: string
  revit_guid: string
  original_aks: string | null
  corrected_aks: string | null
  correction_type: "swap" | "unmatch" | "manual_match"
  created_at: string
}

export interface CorrectionCreate {
  room: string
  revit_guid: string
  original_aks?: string
  corrected_aks?: string
  correction_type: "swap" | "unmatch" | "manual_match"
}

export interface ReviewData {
  matches: MatchEntry[]
  unmatched_aks: UnmatchedAks[]
  unmatched_revit: UnmatchedRevit[]
  room_summary: Record<string, RoomSummary>
  corrections: Correction[]
}

export interface RegistrySummary {
  metadata: {
    total_equipment: number
    with_schema: number
    orphans: number
    total_schema_aks: number
    total_cross_refs: number
    resolved_cross_refs: number
  }
  room_index: Record<string, string[]>
  equipment_count: number
  schema_aks_count: number
  cross_ref_count: number
}

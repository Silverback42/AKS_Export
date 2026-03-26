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

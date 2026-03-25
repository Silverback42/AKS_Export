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

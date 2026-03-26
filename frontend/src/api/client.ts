import axios from "axios"
import type {
  Correction,
  CorrectionCreate,
  MatchResults,
  Project,
  ProjectCreateRequest,
  ProjectDetail,
  ProjectListItem,
  ProjectUpdateRequest,
  RegistrySummary,
  ReviewData,
  Task,
  Upload,
} from "@/types"

const api = axios.create({
  baseURL: "/api",
  headers: { "Content-Type": "application/json" },
})

// Projects
export async function listProjects(): Promise<ProjectListItem[]> {
  const res = await api.get<{ projects: ProjectListItem[] }>("/projects")
  return res.data.projects
}

export async function createProject(data: ProjectCreateRequest): Promise<Project> {
  const res = await api.post<Project>("/projects", data)
  return res.data
}

export async function getProject(id: string): Promise<ProjectDetail> {
  const res = await api.get<ProjectDetail>(`/projects/${id}`)
  return res.data
}

export async function updateProject(id: string, data: ProjectUpdateRequest): Promise<Project> {
  const res = await api.put<Project>(`/projects/${id}`, data)
  return res.data
}

export async function deleteProject(id: string): Promise<void> {
  await api.delete(`/projects/${id}`)
}

// Uploads
export async function uploadFile(projectId: string, file: File, fileType?: string): Promise<Upload> {
  const formData = new FormData()
  formData.append("file", file)
  const params = fileType ? `?file_type=${fileType}` : ""
  const res = await api.post<Upload>(`/projects/${projectId}/uploads${params}`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
  })
  return res.data
}

export async function listUploads(projectId: string): Promise<Upload[]> {
  const res = await api.get<{ uploads: Upload[] }>(`/projects/${projectId}/uploads`)
  return res.data.uploads
}

export async function deleteUpload(projectId: string, uploadId: string): Promise<void> {
  await api.delete(`/projects/${projectId}/uploads/${uploadId}`)
}

// Extraction
export async function runExtraction(projectId: string): Promise<Task> {
  const res = await api.post<Task>(`/projects/${projectId}/extract`)
  return res.data
}

/** @deprecated Verwende runExtraction() */
export async function extractSchema(projectId: string): Promise<Task> {
  const res = await api.post<Task>(`/projects/${projectId}/extract/schema`)
  return res.data
}

/** @deprecated Verwende runExtraction() */
export async function extractGrundriss(projectId: string): Promise<Task> {
  const res = await api.post<Task>(`/projects/${projectId}/extract/grundriss`)
  return res.data
}

/** @deprecated Verwende runExtraction() */
export async function buildRegistry(projectId: string): Promise<Task> {
  const res = await api.post<Task>(`/projects/${projectId}/registry/build`)
  return res.data
}

export async function getRegistry(projectId: string): Promise<RegistrySummary> {
  const res = await api.get<RegistrySummary>(`/projects/${projectId}/registry`)
  return res.data
}

// Tasks
export async function getTask(taskId: string): Promise<Task> {
  const res = await api.get<Task>(`/tasks/${taskId}`)
  return res.data
}

export async function listProjectTasks(projectId: string): Promise<Task[]> {
  const res = await api.get<{ tasks: Task[] }>(`/projects/${projectId}/tasks`)
  return res.data.tasks
}

// Export
export async function exportAksRegistry(projectId: string): Promise<Task> {
  const res = await api.post<Task>(`/projects/${projectId}/export/aks-registry`)
  return res.data
}

export function getExportDownloadUrl(projectId: string, taskId: string): string {
  return `/api/projects/${projectId}/export/${taskId}/download`
}

// Matching
export async function parseRevit(projectId: string, equipmentType = "unknown"): Promise<Task> {
  const res = await api.post<Task>(`/projects/${projectId}/revit/parse`, {
    equipment_type: equipmentType,
  })
  return res.data
}

export async function runMatch(projectId: string, equipmentFilter: string): Promise<Task> {
  const res = await api.post<Task>(`/projects/${projectId}/match`, {
    equipment_filter: equipmentFilter,
  })
  return res.data
}

export async function getMatchResults(projectId: string, taskId: string): Promise<MatchResults> {
  const res = await api.get<MatchResults>(`/projects/${projectId}/match/${taskId}/results`)
  return res.data
}

export async function exportRevitImport(
  projectId: string,
  opts?: { withCorrections?: boolean; matchTaskId?: string },
): Promise<Task> {
  const params = new URLSearchParams()
  if (opts?.withCorrections) params.set("with_corrections", "true")
  if (opts?.matchTaskId) params.set("match_task_id", opts.matchTaskId)
  const qs = params.toString() ? `?${params.toString()}` : ""
  const res = await api.post<Task>(`/projects/${projectId}/export/revit-import${qs}`)
  return res.data
}

// Review / Corrections
export async function getReviewData(projectId: string, taskId: string): Promise<ReviewData> {
  const res = await api.get<ReviewData>(`/projects/${projectId}/match/${taskId}/review`)
  return res.data
}

export async function createCorrection(
  projectId: string,
  taskId: string,
  data: CorrectionCreate,
): Promise<Correction> {
  const res = await api.post<Correction>(
    `/projects/${projectId}/match/${taskId}/corrections`,
    data,
  )
  return res.data
}

export async function listCorrections(
  projectId: string,
  taskId: string,
): Promise<Correction[]> {
  const res = await api.get<{ corrections: Correction[] }>(
    `/projects/${projectId}/match/${taskId}/corrections`,
  )
  return res.data.corrections
}

export async function deleteCorrection(
  projectId: string,
  taskId: string,
  correctionId: string,
): Promise<void> {
  await api.delete(`/projects/${projectId}/match/${taskId}/corrections/${correctionId}`)
}

export async function applyCorrections(
  projectId: string,
  taskId: string,
): Promise<ReviewData> {
  const res = await api.post<ReviewData>(
    `/projects/${projectId}/match/${taskId}/apply-corrections`,
  )
  return res.data
}

import axios from "axios"
import type {
  Project,
  ProjectCreateRequest,
  ProjectDetail,
  ProjectListItem,
  ProjectUpdateRequest,
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

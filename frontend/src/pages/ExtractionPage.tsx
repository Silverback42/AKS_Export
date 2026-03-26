import { useCallback, useState } from "react"
import { useParams } from "react-router-dom"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { useDropzone } from "react-dropzone"
import { toast } from "sonner"
import {
  Upload,
  FileText,
  FileSpreadsheet,
  Trash2,
  Play,
  Download,
  CheckCircle2,
  XCircle,
  Loader2,
  ChevronRight,
} from "lucide-react"

import {
  getProject,
  uploadFile,
  deleteUpload,
  extractSchema,
  extractGrundriss,
  buildRegistry,
  getRegistry,
  exportAksRegistry,
  getExportDownloadUrl,
} from "@/api/client"
import { useTaskPolling } from "@/hooks/useTaskPolling"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Breadcrumbs } from "@/components/layout/Breadcrumbs"
import type { Task as TaskType, RegistrySummary } from "@/types"

const FILE_TYPE_LABELS: Record<string, string> = {
  schema_pdf: "Schema-PDF",
  grundriss_pdf: "Grundriss-PDF",
  revit_excel: "Revit-Excel",
}

const FILE_TYPE_OPTIONS = [
  { value: "schema_pdf", label: "Schema-PDF" },
  { value: "grundriss_pdf", label: "Grundriss-PDF" },
  { value: "revit_excel", label: "Revit-Excel" },
]

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

interface PipelineState {
  schemaTaskId: string | null
  grundrissTaskId: string | null
  registryTaskId: string | null
  exportTaskId: string | null
}

function TaskStatusBadge({ task }: { task: TaskType | null }) {
  if (!task) return <Badge variant="outline">Ausstehend</Badge>

  switch (task.status) {
    case "pending":
      return <Badge variant="outline">Wartend</Badge>
    case "running":
      return (
        <Badge variant="secondary" className="gap-1">
          <Loader2 className="h-3 w-3 animate-spin" />
          {task.progress}%
        </Badge>
      )
    case "completed":
      return (
        <Badge className="gap-1 bg-green-600">
          <CheckCircle2 className="h-3 w-3" />
          Fertig
        </Badge>
      )
    case "failed":
      return (
        <Badge variant="destructive" className="gap-1">
          <XCircle className="h-3 w-3" />
          Fehler
        </Badge>
      )
  }
}

export function ExtractionPage() {
  const { id: projectId } = useParams<{ id: string }>()
  const queryClient = useQueryClient()

  const [pipeline, setPipeline] = useState<PipelineState>({
    schemaTaskId: null,
    grundrissTaskId: null,
    registryTaskId: null,
    exportTaskId: null,
  })

  const [fileTypeOverride, setFileTypeOverride] = useState<string | null>(null)

  // Projekt laden
  const { data: project, isLoading } = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => getProject(projectId!),
    enabled: !!projectId,
  })

  // Registry laden (wenn vorhanden)
  const { data: registry } = useQuery<RegistrySummary>({
    queryKey: ["registry", projectId],
    queryFn: () => getRegistry(projectId!),
    enabled: !!projectId,
    retry: false,
  })

  // Task Polling
  const schemaTask = useTaskPolling(pipeline.schemaTaskId)
  const grundrissTask = useTaskPolling(pipeline.grundrissTaskId)
  const registryTask = useTaskPolling(pipeline.registryTaskId)
  const exportTask = useTaskPolling(pipeline.exportTaskId)

  // Registry nach erfolgreichem Build neu laden
  if (registryTask?.status === "completed") {
    queryClient.invalidateQueries({ queryKey: ["registry", projectId] })
  }

  // Upload
  const uploadMutation = useMutation({
    mutationFn: ({ file, fileType }: { file: File; fileType?: string }) =>
      uploadFile(projectId!, file, fileType || undefined),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["project", projectId] })
      toast.success("Datei hochgeladen")
    },
    onError: () => toast.error("Fehler beim Hochladen"),
  })

  const deleteUploadMutation = useMutation({
    mutationFn: (uploadId: string) => deleteUpload(projectId!, uploadId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["project", projectId] })
      toast.success("Datei geloescht")
    },
  })

  // Dropzone
  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      for (const file of acceptedFiles) {
        uploadMutation.mutate({
          file,
          fileType: fileTypeOverride || undefined,
        })
      }
      setFileTypeOverride(null)
    },
    [uploadMutation, fileTypeOverride]
  )

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/pdf": [".pdf"],
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
      "application/vnd.ms-excel": [".xls"],
    },
  })

  // Pipeline-Aktionen
  const startSchema = async () => {
    try {
      const task = await extractSchema(projectId!)
      setPipeline((prev) => ({ ...prev, schemaTaskId: task.id }))
      toast.success("Schema-Extraktion gestartet")
    } catch {
      toast.error("Fehler beim Starten der Schema-Extraktion")
    }
  }

  const startGrundriss = async () => {
    try {
      const task = await extractGrundriss(projectId!)
      setPipeline((prev) => ({ ...prev, grundrissTaskId: task.id }))
      toast.success("Grundriss-Extraktion gestartet")
    } catch {
      toast.error("Fehler beim Starten der Grundriss-Extraktion")
    }
  }

  const startRegistry = async () => {
    try {
      const task = await buildRegistry(projectId!)
      setPipeline((prev) => ({ ...prev, registryTaskId: task.id }))
      toast.success("Registry-Build gestartet")
    } catch {
      toast.error("Fehler beim Starten des Registry-Builds")
    }
  }

  const startExport = async () => {
    try {
      const task = await exportAksRegistry(projectId!)
      setPipeline((prev) => ({ ...prev, exportTaskId: task.id }))
      toast.success("Excel-Export gestartet")
    } catch {
      toast.error("Fehler beim Starten des Exports")
    }
  }

  // Hilfsfunktionen
  const hasUploadType = (type: string) =>
    project?.uploads.some((u) => u.file_type === type) ?? false

  const canStartSchema = hasUploadType("schema_pdf") && schemaTask?.status !== "running"
  const canStartGrundriss = hasUploadType("grundriss_pdf") && grundrissTask?.status !== "running"
  const canStartRegistry =
    (schemaTask?.status === "completed" || hasUploadType("schema_pdf")) &&
    (grundrissTask?.status === "completed" || hasUploadType("grundriss_pdf")) &&
    registryTask?.status !== "running"
  const canExport =
    (registryTask?.status === "completed" || registry !== undefined) &&
    exportTask?.status !== "running"

  if (isLoading) return <p className="text-muted-foreground">Laden...</p>
  if (!project) return <p className="text-destructive">Projekt nicht gefunden</p>

  return (
    <div>
      <Breadcrumbs
        items={[
          { label: "Projekte", href: "/projects" },
          { label: project.name, href: `/projects/${projectId}` },
          { label: "Extraktion" },
        ]}
      />

      <h1 className="mb-6 text-2xl font-bold">Extraktion &amp; Registry</h1>

      {/* File Upload Dropzone */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>Dateien hochladen</span>
            <select
              className="rounded border px-2 py-1 text-sm font-normal"
              value={fileTypeOverride || ""}
              onChange={(e) => setFileTypeOverride(e.target.value || null)}
            >
              <option value="">Typ auto-erkennen</option>
              {FILE_TYPE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div
            {...getRootProps()}
            className={`cursor-pointer rounded-lg border-2 border-dashed p-8 text-center transition-colors ${
              isDragActive
                ? "border-primary bg-primary/5"
                : "border-muted-foreground/25 hover:border-primary/50"
            }`}
          >
            <input {...getInputProps()} />
            <Upload className="mx-auto mb-3 h-10 w-10 text-muted-foreground" />
            {isDragActive ? (
              <p className="text-primary">Dateien hier ablegen...</p>
            ) : (
              <div>
                <p className="text-sm text-muted-foreground">
                  PDF- oder Excel-Dateien hierher ziehen oder klicken
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Schema-PDF, Grundriss-PDF, oder Revit-Excel
                </p>
              </div>
            )}
          </div>

          {/* Hochgeladene Dateien */}
          {project.uploads.length > 0 && (
            <div className="mt-4 space-y-2">
              {project.uploads.map((upload) => (
                <div
                  key={upload.id}
                  className="flex items-center justify-between rounded border p-3"
                >
                  <div className="flex items-center gap-3">
                    {upload.file_type === "revit_excel" ? (
                      <FileSpreadsheet className="h-5 w-5 text-green-600" />
                    ) : (
                      <FileText className="h-5 w-5 text-red-600" />
                    )}
                    <div>
                      <p className="text-sm font-medium">{upload.filename}</p>
                      <p className="text-xs text-muted-foreground">
                        {FILE_TYPE_LABELS[upload.file_type] ?? upload.file_type} &middot;{" "}
                        {formatFileSize(upload.file_size)}
                      </p>
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => deleteUploadMutation.mutate(upload.id)}
                  >
                    <Trash2 className="h-4 w-4 text-muted-foreground" />
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Pipeline */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Extraktions-Pipeline</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {/* Schritt 1: Schema */}
            <PipelineStepCard
              step="1"
              title="Schema-AKS extrahieren"
              description="AKS-Identifier aus Schema-PDF lesen"
              task={schemaTask}
              canStart={canStartSchema}
              onStart={startSchema}
              disabled={!hasUploadType("schema_pdf")}
              disabledReason="Schema-PDF hochladen"
            />

            <div className="flex justify-center">
              <ChevronRight className="h-5 w-5 rotate-90 text-muted-foreground" />
            </div>

            {/* Schritt 2: Grundriss */}
            <PipelineStepCard
              step="2"
              title="Grundriss-AKS extrahieren"
              description="AKS + Positionen aus Grundriss-PDF lesen"
              task={grundrissTask}
              canStart={canStartGrundriss}
              onStart={startGrundriss}
              disabled={!hasUploadType("grundriss_pdf")}
              disabledReason="Grundriss-PDF hochladen"
            />

            <div className="flex justify-center">
              <ChevronRight className="h-5 w-5 rotate-90 text-muted-foreground" />
            </div>

            {/* Schritt 3: Registry */}
            <PipelineStepCard
              step="3"
              title="AKS-Registry bauen"
              description="Schema + Grundriss zusammenfuehren"
              task={registryTask}
              canStart={canStartRegistry}
              onStart={startRegistry}
              disabled={
                schemaTask?.status !== "completed" && grundrissTask?.status !== "completed"
              }
              disabledReason="Erst Schema + Grundriss extrahieren"
            />
          </div>
        </CardContent>
      </Card>

      {/* Registry Summary */}
      {registry && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle>AKS-Registry Summary</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 sm:grid-cols-3">
              <div className="rounded-lg bg-muted p-4 text-center">
                <p className="text-3xl font-bold">{registry.equipment_count}</p>
                <p className="text-sm text-muted-foreground">Equipment</p>
              </div>
              <div className="rounded-lg bg-muted p-4 text-center">
                <p className="text-3xl font-bold">{registry.schema_aks_count}</p>
                <p className="text-sm text-muted-foreground">Schema-AKS</p>
              </div>
              <div className="rounded-lg bg-muted p-4 text-center">
                <p className="text-3xl font-bold">{registry.cross_ref_count}</p>
                <p className="text-sm text-muted-foreground">Querverweise</p>
              </div>
            </div>

            <div className="mt-4">
              <h4 className="mb-2 text-sm font-medium">Raeume</h4>
              <div className="flex flex-wrap gap-2">
                {Object.entries(registry.room_index)
                  .sort(([a], [b]) => a.localeCompare(b))
                  .map(([room, aksList]) => (
                    <Badge key={room} variant="outline">
                      {room}: {aksList.length} AKS
                    </Badge>
                  ))}
              </div>
            </div>

            <div className="mt-4 flex gap-2">
              <Button onClick={startExport} disabled={!canExport}>
                <Download className="mr-2 h-4 w-4" />
                AKS-Excel exportieren
              </Button>
              {exportTask?.status === "completed" && exportTask.id && (
                <Button variant="outline" asChild>
                  <a href={getExportDownloadUrl(projectId!, exportTask.id)} download>
                    <Download className="mr-2 h-4 w-4" />
                    Excel herunterladen
                  </a>
                </Button>
              )}
            </div>

            {exportTask && exportTask.status !== "completed" && (
              <div className="mt-3">
                <div className="flex items-center gap-2">
                  <TaskStatusBadge task={exportTask} />
                  <span className="text-sm text-muted-foreground">
                    {exportTask.message}
                  </span>
                </div>
                {exportTask.status === "running" && (
                  <Progress value={exportTask.progress} className="mt-2" />
                )}
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}

function PipelineStepCard({
  step,
  title,
  description,
  task,
  canStart,
  onStart,
  disabled,
  disabledReason,
}: {
  step: string
  title: string
  description: string
  task: TaskType | null
  canStart: boolean
  onStart: () => void
  disabled: boolean
  disabledReason: string
}) {
  return (
    <div className="flex items-center gap-4 rounded-lg border p-4">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-bold text-primary-foreground">
        {step}
      </div>
      <div className="flex-1">
        <p className="font-medium">{title}</p>
        <p className="text-sm text-muted-foreground">{description}</p>
        {task?.status === "running" && (
          <Progress value={task.progress} className="mt-2" />
        )}
        {task?.message && (
          <p className="mt-1 text-xs text-muted-foreground">{task.message}</p>
        )}
        {task?.status === "failed" && task.error && (
          <p className="mt-1 text-xs text-destructive">
            {task.error.split("\n").pop()}
          </p>
        )}
      </div>
      <div className="flex items-center gap-2">
        <TaskStatusBadge task={task} />
        {disabled ? (
          <Button size="sm" disabled>
            {disabledReason}
          </Button>
        ) : task?.status === "failed" ? (
          <Button size="sm" variant="destructive" onClick={onStart}>
            <Play className="mr-1 h-3 w-3" />
            Erneut
          </Button>
        ) : (
          <Button size="sm" onClick={onStart} disabled={!canStart}>
            <Play className="mr-1 h-3 w-3" />
            Starten
          </Button>
        )}
      </div>
    </div>
  )
}

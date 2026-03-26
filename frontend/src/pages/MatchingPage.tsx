import { useCallback, useState } from "react"
import { useParams } from "react-router-dom"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { useDropzone } from "react-dropzone"
import { toast } from "sonner"
import {
  FileSpreadsheet,
  Trash2,
  Play,
  Download,
  CheckCircle2,
  XCircle,
  Loader2,
  AlertTriangle,
} from "lucide-react"

import {
  getProject,
  uploadFile,
  deleteUpload,
  parseRevit,
  runMatch,
  getMatchResults,
  exportRevitImport,
  getExportDownloadUrl,
} from "@/api/client"
import { useTaskPolling } from "@/hooks/useTaskPolling"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Breadcrumbs } from "@/components/layout/Breadcrumbs"
import type { Task as TaskType, MatchResults } from "@/types"

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
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

const ROOM_STATUS_COLORS: Record<string, string> = {
  MATCHED: "bg-green-100 border-green-300 text-green-800",
  COUNT_MISMATCH: "bg-red-100 border-red-300 text-red-800",
  NO_AKS: "bg-red-100 border-red-300 text-red-800",
  NO_REVIT: "bg-red-100 border-red-300 text-red-800",
}

const CONFIDENCE_COLORS: Record<string, string> = {
  HIGH: "bg-green-100 text-green-800",
  MEDIUM: "bg-yellow-100 text-yellow-800",
  LOW: "bg-red-100 text-red-800",
}

export function MatchingPage() {
  const { id: projectId } = useParams<{ id: string }>()
  const queryClient = useQueryClient()

  const [equipmentFilter, setEquipmentFilter] = useState("Leuchte")
  const [parseTaskId, setParseTaskId] = useState<string | null>(null)
  const [matchTaskId, setMatchTaskId] = useState<string | null>(null)
  const [exportTaskId, setExportTaskId] = useState<string | null>(null)
  const [matchResults, setMatchResults] = useState<MatchResults | null>(null)

  // Projekt laden
  const { data: project, isLoading } = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => getProject(projectId!),
    enabled: !!projectId,
  })

  // Task Polling
  const parseTask = useTaskPolling(parseTaskId)
  const matchTask = useTaskPolling(matchTaskId)
  const exportTask = useTaskPolling(exportTaskId)

  // Match-Ergebnisse laden wenn Matching fertig
  if (matchTask?.status === "completed" && !matchResults && matchTaskId) {
    getMatchResults(projectId!, matchTaskId).then(setMatchResults).catch(() => {})
  }

  // Upload
  const uploadMutation = useMutation({
    mutationFn: (file: File) => uploadFile(projectId!, file, "revit_excel"),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["project", projectId] })
      toast.success("Revit-Excel hochgeladen")
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

  // Dropzone (nur Excel)
  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      for (const file of acceptedFiles) {
        uploadMutation.mutate(file)
      }
    },
    [uploadMutation]
  )

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
      "application/vnd.ms-excel": [".xls"],
    },
  })

  // Aktionen
  const startParse = async () => {
    try {
      const task = await parseRevit(projectId!, equipmentFilter)
      setParseTaskId(task.id)
      toast.success("Revit-Parse gestartet")
    } catch {
      toast.error("Fehler beim Starten")
    }
  }

  const startMatch = async () => {
    try {
      setMatchResults(null)
      const task = await runMatch(projectId!, equipmentFilter)
      setMatchTaskId(task.id)
      toast.success("Matching gestartet")
    } catch {
      toast.error("Fehler beim Starten")
    }
  }

  const startExport = async () => {
    try {
      const task = await exportRevitImport(projectId!)
      setExportTaskId(task.id)
      toast.success("Export gestartet")
    } catch {
      toast.error("Fehler beim Starten")
    }
  }

  // Equipment-Typen aus Projekt-Config
  const equipmentTypes = project
    ? [...new Set(Object.values(project.geraet_type_map))]
    : []

  const hasRevitExcel = project?.uploads.some((u) => u.file_type === "revit_excel") ?? false
  const canParse = hasRevitExcel && parseTask?.status !== "running"
  const canMatch = parseTask?.status === "completed" && matchTask?.status !== "running"
  const canExport = matchTask?.status === "completed" && exportTask?.status !== "running"

  if (isLoading) return <p className="text-muted-foreground">Laden...</p>
  if (!project) return <p className="text-destructive">Projekt nicht gefunden</p>

  return (
    <div>
      <Breadcrumbs
        items={[
          { label: "Projekte", href: "/projects" },
          { label: project.name, href: `/projects/${projectId}` },
          { label: "Matching" },
        ]}
      />

      <h1 className="mb-6 text-2xl font-bold">Revit Matching</h1>

      {/* Revit-Excel Upload */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Revit-Excel hochladen</CardTitle>
        </CardHeader>
        <CardContent>
          <div
            {...getRootProps()}
            className={`cursor-pointer rounded-lg border-2 border-dashed p-6 text-center transition-colors ${
              isDragActive
                ? "border-primary bg-primary/5"
                : "border-muted-foreground/25 hover:border-primary/50"
            }`}
          >
            <input {...getInputProps()} />
            <FileSpreadsheet className="mx-auto mb-2 h-8 w-8 text-green-600" />
            {isDragActive ? (
              <p className="text-primary">Excel hier ablegen...</p>
            ) : (
              <p className="text-sm text-muted-foreground">
                Revit-Export Excel (.xlsx) hierher ziehen oder klicken
              </p>
            )}
          </div>

          {/* Hochgeladene Revit-Excels */}
          {project.uploads
            .filter((u) => u.file_type === "revit_excel")
            .map((upload) => (
              <div
                key={upload.id}
                className="mt-3 flex items-center justify-between rounded border p-3"
              >
                <div className="flex items-center gap-3">
                  <FileSpreadsheet className="h-5 w-5 text-green-600" />
                  <div>
                    <p className="text-sm font-medium">{upload.filename}</p>
                    <p className="text-xs text-muted-foreground">
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
        </CardContent>
      </Card>

      {/* Equipment-Typ + Matching-Pipeline */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Matching-Pipeline</CardTitle>
        </CardHeader>
        <CardContent>
          {/* Equipment-Typ-Auswahl */}
          <div className="mb-4">
            <label className="mb-1 block text-sm font-medium">Equipment-Typ</label>
            <select
              className="rounded border px-3 py-2 text-sm"
              value={equipmentFilter}
              onChange={(e) => setEquipmentFilter(e.target.value)}
            >
              {equipmentTypes.map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-3">
            {/* Schritt 1: Parse */}
            <div className="flex items-center gap-4 rounded border p-3">
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-bold text-primary-foreground">
                1
              </div>
              <div className="flex-1">
                <p className="text-sm font-medium">Revit-Excel parsen</p>
                {parseTask?.message && (
                  <p className="text-xs text-muted-foreground">{parseTask.message}</p>
                )}
                {parseTask?.status === "running" && (
                  <Progress value={parseTask.progress} className="mt-1" />
                )}
              </div>
              <TaskStatusBadge task={parseTask} />
              <Button size="sm" onClick={startParse} disabled={!canParse}>
                <Play className="mr-1 h-3 w-3" />
                Parsen
              </Button>
            </div>

            {/* Schritt 2: Match */}
            <div className="flex items-center gap-4 rounded border p-3">
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-bold text-primary-foreground">
                2
              </div>
              <div className="flex-1">
                <p className="text-sm font-medium">
                  Matching ausfuehren ({equipmentFilter})
                </p>
                {matchTask?.message && (
                  <p className="text-xs text-muted-foreground">{matchTask.message}</p>
                )}
                {matchTask?.status === "running" && (
                  <Progress value={matchTask.progress} className="mt-1" />
                )}
                {matchTask?.status === "failed" && matchTask.error && (
                  <p className="text-xs text-destructive">
                    {matchTask.error.split("\n").pop()}
                  </p>
                )}
              </div>
              <TaskStatusBadge task={matchTask} />
              <Button size="sm" onClick={startMatch} disabled={!canMatch}>
                <Play className="mr-1 h-3 w-3" />
                Matchen
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Match-Ergebnisse */}
      {matchResults && (
        <>
          {/* Statistik-Summary */}
          <Card className="mb-6">
            <CardHeader>
              <CardTitle>Matching-Ergebnisse</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="mb-4 grid gap-4 sm:grid-cols-4">
                <div className="rounded-lg bg-green-50 p-4 text-center">
                  <p className="text-3xl font-bold text-green-700">
                    {matchResults.metadata.total_matched}
                  </p>
                  <p className="text-sm text-green-600">Zugeordnet</p>
                </div>
                <div className="rounded-lg bg-red-50 p-4 text-center">
                  <p className="text-3xl font-bold text-red-700">
                    {matchResults.metadata.total_unmatched_aks}
                  </p>
                  <p className="text-sm text-red-600">Unmatched AKS</p>
                </div>
                <div className="rounded-lg bg-yellow-50 p-4 text-center">
                  <p className="text-3xl font-bold text-yellow-700">
                    {matchResults.metadata.total_unmatched_revit}
                  </p>
                  <p className="text-sm text-yellow-600">Unmatched Revit</p>
                </div>
                <div className="rounded-lg bg-blue-50 p-4 text-center">
                  <p className="text-3xl font-bold text-blue-700">
                    {matchResults.metadata.rooms_processed}
                  </p>
                  <p className="text-sm text-blue-600">Raeume</p>
                </div>
              </div>

              {/* Raum-Uebersicht */}
              <h4 className="mb-2 text-sm font-medium">Raum-Uebersicht</h4>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {Object.entries(matchResults.room_summary)
                  .sort(([a], [b]) => a.localeCompare(b))
                  .map(([room, summary]) => (
                    <div
                      key={room}
                      className={`rounded-lg border p-3 ${
                        ROOM_STATUS_COLORS[summary.status] || "bg-gray-50"
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-medium">{room}</span>
                        {summary.status === "MATCHED" ? (
                          <Badge
                            className={
                              CONFIDENCE_COLORS[summary.confidence || "HIGH"]
                            }
                          >
                            {summary.confidence}
                          </Badge>
                        ) : (
                          <Badge variant="destructive" className="gap-1">
                            <AlertTriangle className="h-3 w-3" />
                            {summary.status.replace("_", " ")}
                          </Badge>
                        )}
                      </div>
                      <p className="mt-1 text-xs">
                        AKS: {summary.aks_count} | Revit: {summary.revit_count}
                        {summary.matched > 0 && ` | Matched: ${summary.matched}`}
                        {summary.method && ` (${summary.method})`}
                      </p>
                    </div>
                  ))}
              </div>

              {/* Export-Buttons */}
              <div className="mt-6 flex gap-2">
                <Button onClick={startExport} disabled={!canExport}>
                  <Download className="mr-2 h-4 w-4" />
                  Excel herunterladen
                </Button>
                {exportTask?.status === "completed" && exportTask.id && (
                  <Button variant="outline" asChild>
                    <a
                      href={getExportDownloadUrl(projectId!, exportTask.id)}
                      download
                    >
                      <Download className="mr-2 h-4 w-4" />
                      Download
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
        </>
      )}
    </div>
  )
}

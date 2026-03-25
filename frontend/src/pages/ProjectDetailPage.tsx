import { useParams, useNavigate } from "react-router-dom"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { Trash2, Upload, FileText, FileSpreadsheet } from "lucide-react"
import { getProject, deleteProject, uploadFile, deleteUpload } from "@/api/client"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { Breadcrumbs } from "@/components/layout/Breadcrumbs"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { useRef } from "react"

const FILE_TYPE_LABELS: Record<string, string> = {
  schema_pdf: "Schema-PDF",
  grundriss_pdf: "Grundriss-PDF",
  revit_excel: "Revit-Excel",
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const { data: project, isLoading } = useQuery({
    queryKey: ["project", id],
    queryFn: () => getProject(id!),
    enabled: !!id,
  })

  const deleteMutation = useMutation({
    mutationFn: () => deleteProject(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] })
      toast.success("Projekt geloescht")
      navigate("/projects")
    },
  })

  const uploadMutation = useMutation({
    mutationFn: (file: File) => uploadFile(id!, file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["project", id] })
      toast.success("Datei hochgeladen")
    },
    onError: () => {
      toast.error("Fehler beim Hochladen")
    },
  })

  const deleteUploadMutation = useMutation({
    mutationFn: (uploadId: string) => deleteUpload(id!, uploadId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["project", id] })
      toast.success("Datei geloescht")
    },
  })

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (files) {
      Array.from(files).forEach((file) => uploadMutation.mutate(file))
    }
    e.target.value = ""
  }

  if (isLoading) return <p className="text-muted-foreground">Laden...</p>
  if (!project) return <p className="text-destructive">Projekt nicht gefunden</p>

  return (
    <div>
      <Breadcrumbs
        items={[
          { label: "Projekte", href: "/projects" },
          { label: project.name },
        ]}
      />

      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{project.name}</h1>
          <p className="text-muted-foreground">Code: {project.project_code}</p>
        </div>
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button variant="destructive" size="sm">
              <Trash2 className="mr-2 h-4 w-4" />
              Loeschen
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Projekt loeschen?</AlertDialogTitle>
              <AlertDialogDescription>
                Das Projekt &quot;{project.name}&quot; und alle zugehoerigen Dateien werden
                unwiderruflich geloescht.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Abbrechen</AlertDialogCancel>
              <AlertDialogAction onClick={() => deleteMutation.mutate()}>
                Loeschen
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>

      {/* Project Config */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Konfiguration</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 text-sm sm:grid-cols-2">
            <div>
              <span className="font-medium">AKS-Regex:</span>{" "}
              <code className="rounded bg-muted px-1 py-0.5 text-xs">{project.aks_regex}</code>
            </div>
            <div>
              <span className="font-medium">Raum-Pattern:</span>{" "}
              <code className="rounded bg-muted px-1 py-0.5 text-xs">{project.room_code_pattern}</code>
            </div>
            <div>
              <span className="font-medium">Raum-Format:</span>{" "}
              <code className="rounded bg-muted px-1 py-0.5 text-xs">{project.room_format}</code>
            </div>
            <div>
              <span className="font-medium">Geraet-Typen:</span>{" "}
              {Object.entries(project.geraet_type_map).map(([k, v]) => (
                <Badge key={k} variant="secondary" className="ml-1">
                  {k}={v}
                </Badge>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      <Separator className="my-6" />

      {/* File Uploads */}
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-xl font-semibold">Dateien</h2>
        <div>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf,.xlsx,.xls"
            onChange={handleFileChange}
            className="hidden"
          />
          <Button
            variant="outline"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploadMutation.isPending}
          >
            <Upload className="mr-2 h-4 w-4" />
            {uploadMutation.isPending ? "Lade hoch..." : "Dateien hochladen"}
          </Button>
        </div>
      </div>

      {project.uploads.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="flex flex-col items-center justify-center py-8">
            <Upload className="mb-2 h-8 w-8 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">
              Noch keine Dateien hochgeladen
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-2">
          {project.uploads.map((upload) => (
            <Card key={upload.id}>
              <CardContent className="flex items-center justify-between p-4">
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
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}

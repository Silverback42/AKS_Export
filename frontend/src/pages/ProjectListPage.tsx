import { useQuery } from "@tanstack/react-query"
import { useNavigate } from "react-router-dom"
import { Plus, FolderOpen } from "lucide-react"
import { listProjects } from "@/api/client"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Breadcrumbs } from "@/components/layout/Breadcrumbs"
import { ProjectCreateDialog } from "./ProjectCreateDialog"
import { useState } from "react"

export function ProjectListPage() {
  const navigate = useNavigate()
  const [createOpen, setCreateOpen] = useState(false)
  const { data: projects, isLoading } = useQuery({
    queryKey: ["projects"],
    queryFn: listProjects,
  })

  return (
    <div>
      <Breadcrumbs items={[{ label: "Projekte" }]} />
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold">Projekte</h1>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Neues Projekt
        </Button>
      </div>

      {isLoading && <p className="text-muted-foreground">Laden...</p>}

      {!isLoading && projects?.length === 0 && (
        <Card className="border-dashed">
          <CardContent className="flex flex-col items-center justify-center py-12">
            <FolderOpen className="mb-4 h-12 w-12 text-muted-foreground" />
            <p className="mb-2 text-lg font-medium">Keine Projekte vorhanden</p>
            <p className="mb-4 text-sm text-muted-foreground">
              Erstelle ein neues Projekt, um loszulegen.
            </p>
            <Button onClick={() => setCreateOpen(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Neues Projekt
            </Button>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {projects?.map((project) => (
          <Card
            key={project.id}
            className="cursor-pointer transition-shadow hover:shadow-md"
            onClick={() => navigate(`/projects/${project.id}`)}
          >
            <CardHeader>
              <div className="flex items-start justify-between">
                <CardTitle className="text-lg">{project.name}</CardTitle>
                <Badge variant="secondary">{project.project_code}</Badge>
              </div>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between text-sm text-muted-foreground">
                <span>{project.upload_count} Dateien</span>
                <span>
                  {new Date(project.created_at).toLocaleDateString("de-DE")}
                </span>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <ProjectCreateDialog open={createOpen} onOpenChange={setCreateOpen} />
    </div>
  )
}

import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "react-router-dom"
import { toast } from "sonner"
import { createProject } from "@/api/client"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { ProjectForm } from "./ProjectForm"
import type { ProjectCreateRequest } from "@/types"

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function ProjectCreateDialog({ open, onOpenChange }: Props) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const mutation = useMutation({
    mutationFn: createProject,
    onSuccess: (project) => {
      queryClient.invalidateQueries({ queryKey: ["projects"] })
      toast.success("Projekt erstellt")
      onOpenChange(false)
      navigate(`/projects/${project.id}`)
    },
    onError: (error: unknown) => {
      const msg = error instanceof Error ? error.message : "Fehler beim Erstellen"
      toast.error(msg)
    },
  })

  const handleSubmit = (data: ProjectCreateRequest) => {
    mutation.mutate(data)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Neues Projekt erstellen</DialogTitle>
          <DialogDescription>
            Konfiguriere die Projekt-Parameter fuer die AKS-Extraktion.
          </DialogDescription>
        </DialogHeader>
        <ProjectForm onSubmit={handleSubmit} isLoading={mutation.isPending} />
      </DialogContent>
    </Dialog>
  )
}

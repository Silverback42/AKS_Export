import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import type { ProjectCreateRequest } from "@/types"

interface Props {
  onSubmit: (data: ProjectCreateRequest) => void
  isLoading?: boolean
  initialValues?: Partial<ProjectCreateRequest>
}

export function ProjectForm({ onSubmit, isLoading, initialValues }: Props) {
  const [name, setName] = useState(initialValues?.name ?? "")
  const [projectCode, setProjectCode] = useState(initialValues?.project_code ?? "")

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSubmit({
      name,
      project_code: projectCode.toUpperCase(),
    })
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="name">Projektname *</Label>
        <Input
          id="name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="z.B. Wunstorf Kaserne"
          required
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="code">Liegenschaftskuerzel *</Label>
        <Input
          id="code"
          value={projectCode}
          onChange={(e) => setProjectCode(e.target.value)}
          placeholder="z.B. WUN"
          maxLength={10}
          required
        />
        <p className="text-xs text-muted-foreground">
          Das Kuerzel der Liegenschaft (z.B. WUN). Alle Gebaeude (WUN001x, WUN002x, ...) werden automatisch erkannt.
        </p>
      </div>

      <div className="flex justify-end">
        <Button type="submit" disabled={isLoading}>
          {isLoading ? "Erstelle..." : "Projekt erstellen"}
        </Button>
      </div>
    </form>
  )
}

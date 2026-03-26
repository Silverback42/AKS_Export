import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import type { ProjectCreateRequest } from "@/types"

const DEFAULT_GERAET_TYPE_MAP: Record<string, string> = {
  E: "Leuchte",
  M: "Motor/Ventil",
  S: "Sensor/Schalter",
  B: "Sensor",
  A: "Aktor",
  U: "Zaehler",
  PF: "Pruefeinrichtung",
  F: "Sicherheit/Frost",
}

interface Props {
  onSubmit: (data: ProjectCreateRequest) => void
  isLoading?: boolean
  initialValues?: Partial<ProjectCreateRequest>
}

export function ProjectForm({ onSubmit, isLoading, initialValues }: Props) {
  const [name, setName] = useState(initialValues?.name ?? "")
  const [projectCode, setProjectCode] = useState(initialValues?.project_code ?? "")
  const [aksRegex, setAksRegex] = useState(
    initialValues?.aks_regex ?? String.raw`WUN005[xX]?_\w+(?:_\w+)*`
  )
  const [roomCodePattern, setRoomCodePattern] = useState(
    initialValues?.room_code_pattern ?? String.raw`EG(\d{3})`
  )
  const [roomFormat, setRoomFormat] = useState(initialValues?.room_format ?? "E.{0}")
  const [geraetMapJson, setGeraetMapJson] = useState(
    JSON.stringify(initialValues?.geraet_type_map ?? DEFAULT_GERAET_TYPE_MAP, null, 2)
  )
  const [jsonError, setJsonError] = useState("")
  const [regexError, setRegexError] = useState("")

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()

    // Regex validieren
    try {
      new RegExp(aksRegex)
      setRegexError("")
    } catch {
      setRegexError("Ungueltiger regulaerer Ausdruck")
      return
    }

    let geraetTypeMap: Record<string, string>
    try {
      geraetTypeMap = JSON.parse(geraetMapJson)
      setJsonError("")
    } catch {
      setJsonError("Ungueltiges JSON-Format")
      return
    }

    onSubmit({
      name,
      project_code: projectCode,
      aks_regex: aksRegex,
      room_code_pattern: roomCodePattern,
      room_format: roomFormat,
      geraet_type_map: geraetTypeMap,
    })
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="name">Projektname *</Label>
          <Input
            id="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="z.B. WUN005x Wunstorf"
            required
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="code">Projektcode *</Label>
          <Input
            id="code"
            value={projectCode}
            onChange={(e) => setProjectCode(e.target.value)}
            placeholder="z.B. WUN005x"
            required
          />
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="regex">AKS-Regex *</Label>
        <Input
          id="regex"
          value={aksRegex}
          onChange={(e) => {
            setAksRegex(e.target.value)
            setRegexError("")
          }}
          placeholder={String.raw`z.B. WUN005[xX]?_\w+(?:_\w+)*`}
          className="font-mono text-sm"
          required
        />
        {regexError && <p className="text-sm text-destructive">{regexError}</p>}
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="roomPattern">Raum-Code-Pattern</Label>
          <Input
            id="roomPattern"
            value={roomCodePattern}
            onChange={(e) => setRoomCodePattern(e.target.value)}
            className="font-mono text-sm"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="roomFormat">Raum-Format</Label>
          <Input
            id="roomFormat"
            value={roomFormat}
            onChange={(e) => setRoomFormat(e.target.value)}
            className="font-mono text-sm"
          />
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="geraetMap">Geraet-Type-Map (JSON)</Label>
        <Textarea
          id="geraetMap"
          value={geraetMapJson}
          onChange={(e) => {
            setGeraetMapJson(e.target.value)
            setJsonError("")
          }}
          rows={8}
          className="font-mono text-sm"
        />
        {jsonError && <p className="text-sm text-destructive">{jsonError}</p>}
      </div>

      <div className="flex justify-end">
        <Button type="submit" disabled={isLoading}>
          {isLoading ? "Erstelle..." : "Projekt erstellen"}
        </Button>
      </div>
    </form>
  )
}

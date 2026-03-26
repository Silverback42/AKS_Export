import { useEffect, useCallback, useMemo, useRef, useState } from "react"
import { useParams } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { toast } from "sonner"
import {
  ArrowLeftRight,
  ChevronDown,
  ChevronRight,
  Download,
  Redo2,
  RotateCcw,
  Save,
  Unlink,
  Undo2,
  X,
  Link2,
  Filter,
} from "lucide-react"

import {
  getProject,
  getReviewData,
  createCorrection,
  applyCorrections,
  exportRevitImport,
  getExportDownloadUrl,
} from "@/api/client"
import { useReviewStore } from "@/stores/reviewStore"
import { useTaskPolling } from "@/hooks/useTaskPolling"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { ConfidenceBadge } from "@/components/review/ConfidenceBadge"
import { Breadcrumbs } from "@/components/layout/Breadcrumbs"
import type { MatchEntry, UnmatchedAks, UnmatchedRevit } from "@/types"

export function ReviewPage() {
  const { id: projectId, taskId } = useParams<{ id: string; taskId: string }>()

  const store = useReviewStore()
  const [collapsedRooms, setCollapsedRooms] = useState<Set<string>>(new Set())
  const [swapSource, setSwapSource] = useState<string | null>(null)
  const [exportTaskId, setExportTaskId] = useState<string | null>(null)
  const [isSaving, setIsSaving] = useState(false)
  const roomRefs = useRef<Record<string, HTMLDivElement | null>>({})

  const exportTask = useTaskPolling(exportTaskId)

  const { data: project } = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => getProject(projectId!),
    enabled: !!projectId,
  })

  // Review-Daten laden
  const { data: reviewData, isLoading, error: reviewError } = useQuery({
    queryKey: ["review", projectId, taskId],
    queryFn: () => getReviewData(projectId!, taskId!),
    enabled: !!projectId && !!taskId,
    refetchOnWindowFocus: false,
  })

  // Review-Daten in Store laden wenn Query erfolgreich
  useEffect(() => {
    if (reviewData) store.loadReviewData(reviewData)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reviewData])

  useEffect(() => {
    if (reviewError) toast.error("Fehler beim Laden der Review-Daten")
  }, [reviewError])

  // Leave-Guard bei ungespeicherten Aenderungen
  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (store.hasUnsavedChanges) {
        e.preventDefault()
      }
    }
    window.addEventListener("beforeunload", handler)
    return () => window.removeEventListener("beforeunload", handler)
  }, [store.hasUnsavedChanges])

  // Keyboard Shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.key === "z" && !e.shiftKey) {
        e.preventDefault()
        store.undoCorrection()
      } else if (e.ctrlKey && (e.key === "y" || (e.key === "z" && e.shiftKey))) {
        e.preventDefault()
        store.redoCorrection()
      }
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [store])

  // Raum-Gruppierung
  const groupedMatches = useMemo(() => {
    const groups: Record<string, MatchEntry[]> = {}
    for (const m of store.matches) {
      if (!groups[m.room]) groups[m.room] = []
      groups[m.room]!.push(m)
    }
    return groups
  }, [store.matches])

  const sortedRooms = useMemo(
    () => Object.keys(groupedMatches).sort(),
    [groupedMatches],
  )

  // Gefilterte Raeume
  const filteredRooms = useMemo(() => {
    if (store.filter === "all") return sortedRooms
    if (store.filter === "problems") {
      return sortedRooms.filter((room) => {
        const summary = store.roomSummary[room]
        if (!summary) return false
        return summary.status !== "MATCHED" || summary.confidence === "MEDIUM" || summary.confidence === "LOW"
      })
    }
    // "corrected"
    return sortedRooms.filter((room) =>
      groupedMatches[room]?.some((m) => m.confidence === "CORRECTED"),
    )
  }, [store.filter, sortedRooms, store.roomSummary, groupedMatches])

  const toggleRoom = useCallback((room: string) => {
    setCollapsedRooms((prev) => {
      const next = new Set(prev)
      if (next.has(room)) next.delete(room)
      else next.add(room)
      return next
    })
  }, [])

  const scrollToRoom = useCallback((room: string) => {
    // Aufklappen falls zugeklappt
    setCollapsedRooms((prev) => {
      const next = new Set(prev)
      next.delete(room)
      return next
    })
    setTimeout(() => {
      roomRefs.current[room]?.scrollIntoView({ behavior: "smooth", block: "start" })
    }, 50)
  }, [])

  // Swap-Logik
  const handleSwapClick = useCallback(
    (revitGuid: string) => {
      if (!swapSource) {
        setSwapSource(revitGuid)
      } else if (swapSource !== revitGuid) {
        store.swapMatches(swapSource, revitGuid)
        setSwapSource(null)
        toast.success("AKS getauscht")
      } else {
        setSwapSource(null)
      }
    },
    [swapSource, store],
  )

  // Click-to-Pair: AKS aus Unmatched auswaehlen, dann Revit-Element
  const handleUnmatchedAksClick = useCallback(
    (aks: UnmatchedAks) => {
      if (store.selectedRevitGuid) {
        // Revit ist schon ausgewaehlt — pairen
        store.manualMatch(aks.aks, store.selectedRevitGuid, aks.room)
        toast.success("Manuell gepaart")
      } else {
        store.setSelectedAks(aks.aks)
      }
    },
    [store],
  )

  const handleUnmatchedRevitClick = useCallback(
    (revit: UnmatchedRevit) => {
      if (store.selectedAksId) {
        // AKS ist schon ausgewaehlt — pairen
        store.manualMatch(store.selectedAksId, revit.guid, revit.room)
        toast.success("Manuell gepaart")
      } else {
        store.setSelectedRevitGuid(revit.guid)
      }
    },
    [store],
  )

  // Speichern
  const handleSave = async () => {
    if (!projectId || !taskId) return
    setIsSaving(true)
    try {
      for (const correction of store.pendingCorrections) {
        await createCorrection(projectId, taskId, correction)
      }
      // Korrekturen anwenden und korrigierte JSON speichern
      const result = await applyCorrections(projectId, taskId)
      store.markSaved(result)
      toast.success("Korrekturen gespeichert")
    } catch {
      toast.error("Fehler beim Speichern")
    } finally {
      setIsSaving(false)
    }
  }

  // Export mit Korrekturen
  const handleExport = async () => {
    if (!projectId || !taskId) return
    try {
      const task = await exportRevitImport(projectId, {
        withCorrections: true,
        matchTaskId: taskId,
      })
      setExportTaskId(task.id)
      toast.success("Export gestartet")
    } catch {
      toast.error("Fehler beim Export")
    }
  }

  if (isLoading) return <p className="text-muted-foreground">Laden...</p>
  if (!project) return <p className="text-destructive">Projekt nicht gefunden</p>

  return (
    <div className="flex h-full gap-4">
      {/* Hauptbereich */}
      <div className="flex-1 min-w-0">
        <Breadcrumbs
          items={[
            { label: "Projekte", href: "/projects" },
            { label: project.name, href: `/projects/${projectId}` },
            { label: "Matching", href: `/projects/${projectId}/matching` },
            { label: "Review" },
          ]}
        />

        {/* Toolbar */}
        <div className="mb-4 flex items-center justify-between">
          <h1 className="text-2xl font-bold">Match Review</h1>
          <div className="flex items-center gap-2">
            {store.pendingCorrections.length > 0 && (
              <Badge variant="secondary">
                {store.pendingCorrections.length} Korrekturen
              </Badge>
            )}

            {/* Filter */}
            <div className="flex items-center gap-1 rounded border px-2 py-1">
              <Filter className="h-3 w-3 text-muted-foreground" />
              <select
                className="bg-transparent text-sm outline-none"
                value={store.filter}
                onChange={(e) => store.setFilter(e.target.value as "all" | "problems" | "corrected")}
              >
                <option value="all">Alle</option>
                <option value="problems">Nur Probleme</option>
                <option value="corrected">Nur korrigierte</option>
              </select>
            </div>

            <Button
              variant="outline"
              size="sm"
              onClick={() => store.undoCorrection()}
              disabled={store.undoStack.length === 0}
              title="Rueckgaengig (Ctrl+Z)"
            >
              <Undo2 className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => store.redoCorrection()}
              disabled={store.redoStack.length === 0}
              title="Wiederholen (Ctrl+Y)"
            >
              <Redo2 className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => store.resetAllCorrections()}
              disabled={store.undoStack.length === 0}
              title="Alle zuruecksetzen"
            >
              <RotateCcw className="h-4 w-4" />
            </Button>

            <Button
              size="sm"
              onClick={handleSave}
              disabled={!store.hasUnsavedChanges || isSaving}
            >
              <Save className="mr-1 h-4 w-4" />
              {isSaving ? "Speichern..." : "Speichern"}
            </Button>
            <Button size="sm" variant="outline" onClick={handleExport}>
              <Download className="mr-1 h-4 w-4" />
              Export
            </Button>
            {exportTask?.status === "completed" && exportTask.id && (
              <Button variant="outline" size="sm" asChild>
                <a href={getExportDownloadUrl(projectId!, exportTask.id)} download>
                  <Download className="mr-1 h-4 w-4" />
                  Download
                </a>
              </Button>
            )}
          </div>
        </div>

        {/* Swap-Hinweis */}
        {swapSource && (
          <div className="mb-3 flex items-center gap-2 rounded border border-blue-300 bg-blue-50 px-3 py-2 text-sm">
            <ArrowLeftRight className="h-4 w-4 text-blue-600" />
            <span>Klicke auf eine zweite Zeile im selben Raum zum Tauschen</span>
            <Button variant="ghost" size="sm" onClick={() => setSwapSource(null)}>
              <X className="h-3 w-3" /> Abbrechen
            </Button>
          </div>
        )}

        {/* Raum-Schnellnavigation */}
        <div className="mb-4 flex flex-wrap gap-1">
          {filteredRooms.map((room) => {
            const summary = store.roomSummary[room]
            const statusColor =
              summary?.status === "MATCHED"
                ? summary.confidence === "CORRECTED"
                  ? "bg-blue-100 hover:bg-blue-200 text-blue-800"
                  : "bg-green-100 hover:bg-green-200 text-green-800"
                : "bg-red-100 hover:bg-red-200 text-red-800"
            return (
              <button
                key={room}
                onClick={() => scrollToRoom(room)}
                className={`rounded px-2 py-0.5 text-xs font-medium transition-colors ${statusColor}`}
              >
                {room}
              </button>
            )
          })}
        </div>

        {/* Match-Tabelle nach Raum gruppiert */}
        <div className="space-y-3">
          {filteredRooms.map((room) => {
            const matches = groupedMatches[room] || []
            const isCollapsed = collapsedRooms.has(room)
            const summary = store.roomSummary[room]

            return (
              <div
                key={room}
                ref={(el) => { roomRefs.current[room] = el }}
                className="rounded-lg border"
              >
                {/* Raum-Header */}
                <button
                  className="flex w-full items-center gap-2 px-4 py-2 text-left hover:bg-muted/50"
                  onClick={() => toggleRoom(room)}
                >
                  {isCollapsed ? (
                    <ChevronRight className="h-4 w-4 shrink-0" />
                  ) : (
                    <ChevronDown className="h-4 w-4 shrink-0" />
                  )}
                  <span className="font-semibold">{room}</span>
                  <span className="text-xs text-muted-foreground">
                    ({matches.length} Matches)
                  </span>
                  {summary && (
                    <ConfidenceBadge
                      confidence={
                        summary.status !== "MATCHED"
                          ? summary.status
                          : summary.confidence || "HIGH"
                      }
                    />
                  )}
                </button>

                {/* Zeilen */}
                {!isCollapsed && (
                  <div className="border-t">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b bg-muted/30 text-xs text-muted-foreground">
                          <th className="px-3 py-1.5 text-left">AKS</th>
                          <th className="px-3 py-1.5 text-left">Revit GUID</th>
                          <th className="px-3 py-1.5 text-left">Revit Type</th>
                          <th className="px-3 py-1.5 text-center">Konfidenz</th>
                          <th className="px-3 py-1.5 text-right">Aktionen</th>
                        </tr>
                      </thead>
                      <tbody>
                        {matches.map((match) => {
                          const isCorrected = match.confidence === "CORRECTED"
                          const isSwapTarget = swapSource === match.revit_guid
                          const isSwapCandidate =
                            swapSource !== null &&
                            swapSource !== match.revit_guid &&
                            matches.some((m) => m.revit_guid === swapSource)

                          return (
                            <tr
                              key={match.revit_guid}
                              className={`border-b last:border-b-0 transition-colors ${
                                isCorrected ? "bg-blue-50 border-l-2 border-l-blue-400" : ""
                              } ${isSwapTarget ? "bg-blue-100" : ""} ${
                                isSwapCandidate ? "cursor-pointer hover:bg-blue-50" : ""
                              }`}
                              onClick={isSwapCandidate ? () => handleSwapClick(match.revit_guid) : undefined}
                            >
                              <td className="px-3 py-2 font-mono text-xs">
                                {match.aks}
                              </td>
                              <td className="px-3 py-2 font-mono text-xs truncate max-w-[200px]">
                                {match.revit_guid}
                              </td>
                              <td className="px-3 py-2 text-xs truncate max-w-[150px]">
                                {match.revit_type}
                              </td>
                              <td className="px-3 py-2 text-center">
                                <ConfidenceBadge confidence={match.confidence} />
                              </td>
                              <td className="px-3 py-2 text-right">
                                <div className="flex justify-end gap-1">
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-7 px-2"
                                    onClick={(e) => {
                                      e.stopPropagation()
                                      handleSwapClick(match.revit_guid)
                                    }}
                                    title="AKS tauschen"
                                  >
                                    <ArrowLeftRight className="h-3 w-3" />
                                  </Button>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-7 px-2"
                                    onClick={(e) => {
                                      e.stopPropagation()
                                      store.unmatchEntry(match.revit_guid)
                                      toast.success("Match aufgeloest")
                                    }}
                                    title="Match aufloesen"
                                  >
                                    <Unlink className="h-3 w-3" />
                                  </Button>
                                </div>
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )
          })}
        </div>

        {filteredRooms.length === 0 && (
          <p className="py-8 text-center text-muted-foreground">
            Keine Matches fuer den ausgewaehlten Filter
          </p>
        )}
      </div>

      {/* Unmatched-Sidebar */}
      <UnmatchedSidebar
        unmatchedAks={store.unmatchedAks}
        unmatchedRevit={store.unmatchedRevit}
        selectedAksId={store.selectedAksId}
        selectedRevitGuid={store.selectedRevitGuid}
        onAksClick={handleUnmatchedAksClick}
        onRevitClick={handleUnmatchedRevitClick}
        onClearSelection={store.clearSelection}
      />
    </div>
  )
}


// --- Unmatched-Sidebar ---

function UnmatchedSidebar({
  unmatchedAks,
  unmatchedRevit,
  selectedAksId,
  selectedRevitGuid,
  onAksClick,
  onRevitClick,
  onClearSelection,
}: {
  unmatchedAks: UnmatchedAks[]
  unmatchedRevit: UnmatchedRevit[]
  selectedAksId: string | null
  selectedRevitGuid: string | null
  onAksClick: (aks: UnmatchedAks) => void
  onRevitClick: (revit: UnmatchedRevit) => void
  onClearSelection: () => void
}) {
  const [collapsed, setCollapsed] = useState(false)
  const totalUnmatched = unmatchedAks.length + unmatchedRevit.length

  if (totalUnmatched === 0 && !selectedAksId && !selectedRevitGuid) return null

  return (
    <div className={`shrink-0 border-l ${collapsed ? "w-10" : "w-72"}`}>
      <button
        className="flex w-full items-center justify-between border-b px-3 py-2 text-sm font-medium hover:bg-muted/50"
        onClick={() => setCollapsed(!collapsed)}
      >
        {!collapsed && <span>Nicht zugeordnet ({totalUnmatched})</span>}
        {collapsed ? <ChevronRight className="h-4 w-4" /> : <X className="h-4 w-4" />}
      </button>

      {!collapsed && (
        <div className="overflow-y-auto p-3" style={{ maxHeight: "calc(100vh - 200px)" }}>
          {/* Hinweis bei Auswahl */}
          {(selectedAksId || selectedRevitGuid) && (
            <div className="mb-3 rounded border border-blue-300 bg-blue-50 p-2 text-xs">
              <div className="flex items-center justify-between">
                <span>
                  {selectedAksId
                    ? `AKS "${selectedAksId}" ausgewaehlt — klicke auf ein Revit-Element`
                    : `GUID ausgewaehlt — klicke auf ein AKS`}
                </span>
                <button onClick={onClearSelection}>
                  <X className="h-3 w-3" />
                </button>
              </div>
            </div>
          )}

          {/* Unmatched AKS */}
          {unmatchedAks.length > 0 && (
            <Card className="mb-3">
              <CardHeader className="px-3 py-2">
                <CardTitle className="text-xs font-medium">
                  Unmatched AKS ({unmatchedAks.length})
                </CardTitle>
              </CardHeader>
              <CardContent className="px-3 pb-3 pt-0">
                <div className="space-y-1">
                  {unmatchedAks.map((um, i) => (
                    <button
                      key={`${um.aks}-${i}`}
                      className={`w-full rounded px-2 py-1.5 text-left text-xs transition-colors ${
                        selectedAksId === um.aks
                          ? "bg-blue-100 border border-blue-300"
                          : "hover:bg-muted/50 border border-transparent"
                      }`}
                      onClick={() => onAksClick(um)}
                    >
                      <div className="flex items-center gap-1">
                        <Link2 className="h-3 w-3 shrink-0 text-muted-foreground" />
                        <span className="truncate font-mono">{um.aks}</span>
                      </div>
                      <span className="text-muted-foreground">{um.room}</span>
                    </button>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Unmatched Revit */}
          {unmatchedRevit.length > 0 && (
            <Card>
              <CardHeader className="px-3 py-2">
                <CardTitle className="text-xs font-medium">
                  Unmatched Revit ({unmatchedRevit.length})
                </CardTitle>
              </CardHeader>
              <CardContent className="px-3 pb-3 pt-0">
                <div className="space-y-1">
                  {unmatchedRevit.map((um, i) => (
                    <button
                      key={`${um.guid}-${i}`}
                      className={`w-full rounded px-2 py-1.5 text-left text-xs transition-colors ${
                        selectedRevitGuid === um.guid
                          ? "bg-blue-100 border border-blue-300"
                          : "hover:bg-muted/50 border border-transparent"
                      }`}
                      onClick={() => onRevitClick(um)}
                    >
                      <div className="flex items-center gap-1">
                        <Link2 className="h-3 w-3 shrink-0 text-muted-foreground" />
                        <span className="truncate font-mono">{um.guid}</span>
                      </div>
                      <span className="text-muted-foreground">{um.room}</span>
                    </button>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  )
}

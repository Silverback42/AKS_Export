import { create } from "zustand"
import type {
  MatchEntry,
  UnmatchedAks,
  UnmatchedRevit,
  RoomSummary,
  Correction,
  CorrectionCreate,
  ReviewData,
} from "@/types"

interface ReviewSnapshot {
  matches: MatchEntry[]
  unmatchedAks: UnmatchedAks[]
  unmatchedRevit: UnmatchedRevit[]
  pendingCorrections: CorrectionCreate[]
}

interface ReviewState {
  // Daten
  matches: MatchEntry[]
  unmatchedAks: UnmatchedAks[]
  unmatchedRevit: UnmatchedRevit[]
  roomSummary: Record<string, RoomSummary>
  savedCorrections: Correction[]

  // Lokale Korrekturen (noch nicht gespeichert)
  pendingCorrections: CorrectionCreate[]

  // Undo/Redo
  undoStack: ReviewSnapshot[]
  redoStack: ReviewSnapshot[]

  // UI-State
  selectedAksId: string | null
  selectedRevitGuid: string | null
  filter: "all" | "problems" | "corrected"
  hasUnsavedChanges: boolean

  // Aktionen
  loadReviewData: (data: {
    matches: MatchEntry[]
    unmatched_aks: UnmatchedAks[]
    unmatched_revit: UnmatchedRevit[]
    room_summary: Record<string, RoomSummary>
    corrections: Correction[]
  }) => void

  swapMatches: (guidA: string, guidB: string) => void
  unmatchEntry: (revitGuid: string) => void
  manualMatch: (aks: string, revitGuid: string, room: string) => void

  undoCorrection: () => void
  redoCorrection: () => void
  resetAllCorrections: () => void

  setFilter: (filter: "all" | "problems" | "corrected") => void
  setSelectedAks: (aks: string | null) => void
  setSelectedRevitGuid: (guid: string | null) => void
  clearSelection: () => void

  markSaved: (data: ReviewData) => void
}

function takeSnapshot(state: ReviewState): ReviewSnapshot {
  return {
    matches: structuredClone(state.matches),
    unmatchedAks: structuredClone(state.unmatchedAks),
    unmatchedRevit: structuredClone(state.unmatchedRevit),
    pendingCorrections: structuredClone(state.pendingCorrections),
  }
}

function recalcRoomSummary(
  matches: MatchEntry[],
  unmatchedAks: UnmatchedAks[],
  unmatchedRevit: UnmatchedRevit[],
): Record<string, RoomSummary> {
  const summary: Record<string, RoomSummary> = {}

  for (const m of matches) {
    if (!summary[m.room]) {
      summary[m.room] = { matched: 0, aks_count: 0, revit_count: 0, status: "MATCHED" }
    }
    const rs = summary[m.room]!
    rs.matched += 1
    rs.aks_count += 1
    rs.revit_count += 1
  }

  for (const um of unmatchedAks) {
    if (!summary[um.room]) {
      summary[um.room] = { matched: 0, aks_count: 0, revit_count: 0, status: "NO_REVIT" }
    }
    summary[um.room]!.aks_count += 1
  }

  for (const um of unmatchedRevit) {
    if (!summary[um.room]) {
      summary[um.room] = { matched: 0, aks_count: 0, revit_count: 0, status: "NO_AKS" }
    }
    summary[um.room]!.revit_count += 1
  }

  for (const [, s] of Object.entries(summary)) {
    if (s.matched > 0 && s.aks_count === s.revit_count && s.aks_count === s.matched) {
      s.status = "MATCHED"
    } else if (s.aks_count !== s.revit_count) {
      s.status = "COUNT_MISMATCH"
    }
  }

  return summary
}

export const useReviewStore = create<ReviewState>((set, get) => ({
  matches: [],
  unmatchedAks: [],
  unmatchedRevit: [],
  roomSummary: {},
  savedCorrections: [],
  pendingCorrections: [],
  undoStack: [],
  redoStack: [],
  selectedAksId: null,
  selectedRevitGuid: null,
  filter: "all",
  hasUnsavedChanges: false,

  loadReviewData: (data) => {
    set({
      matches: data.matches,
      unmatchedAks: data.unmatched_aks,
      unmatchedRevit: data.unmatched_revit,
      roomSummary: data.room_summary,
      savedCorrections: data.corrections,
      pendingCorrections: [],
      undoStack: [],
      redoStack: [],
      hasUnsavedChanges: false,
      selectedAksId: null,
      selectedRevitGuid: null,
    })
  },

  swapMatches: (guidA, guidB) => {
    const state = get()
    const snapshot = takeSnapshot(state)

    const matches = structuredClone(state.matches)
    const matchA = matches.find((m) => m.revit_guid === guidA)
    const matchB = matches.find((m) => m.revit_guid === guidB)

    if (!matchA || !matchB) return

    const correction: CorrectionCreate = {
      room: matchA.room,
      revit_guid: guidA,
      original_aks: matchA.aks,
      corrected_aks: matchB.aks,
      correction_type: "swap",
    }

    // AKS tauschen
    const tmpAks = matchA.aks
    matchA.aks = matchB.aks
    matchB.aks = tmpAks
    matchA.confidence = "CORRECTED"
    matchB.confidence = "CORRECTED"

    set({
      matches,
      roomSummary: recalcRoomSummary(matches, state.unmatchedAks, state.unmatchedRevit),
      pendingCorrections: [...state.pendingCorrections, correction],
      undoStack: [...state.undoStack, snapshot],
      redoStack: [],
      hasUnsavedChanges: true,
      selectedAksId: null,
      selectedRevitGuid: null,
    })
  },

  unmatchEntry: (revitGuid) => {
    const state = get()
    const snapshot = takeSnapshot(state)

    const matches = structuredClone(state.matches)
    const idx = matches.findIndex((m) => m.revit_guid === revitGuid)
    if (idx === -1) return

    const match = matches.splice(idx, 1)[0]!
    const unmatchedAks = [...state.unmatchedAks, { room: match.room, aks: match.aks, reason: "manually_unmatched" }]
    const unmatchedRevit = [...state.unmatchedRevit, { room: match.room, guid: match.revit_guid, reason: "manually_unmatched" }]

    const correction: CorrectionCreate = {
      room: match.room,
      revit_guid: revitGuid,
      original_aks: match.aks,
      correction_type: "unmatch",
    }

    set({
      matches,
      unmatchedAks,
      unmatchedRevit,
      roomSummary: recalcRoomSummary(matches, unmatchedAks, unmatchedRevit),
      pendingCorrections: [...state.pendingCorrections, correction],
      undoStack: [...state.undoStack, snapshot],
      redoStack: [],
      hasUnsavedChanges: true,
    })
  },

  manualMatch: (aks, revitGuid, room) => {
    const state = get()
    const snapshot = takeSnapshot(state)

    const unmatchedAks = state.unmatchedAks.filter((u) => !(u.aks === aks && u.room === room))
    const unmatchedRevit = state.unmatchedRevit.filter((u) => u.guid !== revitGuid)

    const newMatch: MatchEntry = {
      room,
      aks,
      revit_guid: revitGuid,
      revit_type: "",
      confidence: "CORRECTED",
      sort_axis: "MANUAL",
      sort_rank: 0,
    }

    const matches = [...state.matches, newMatch]

    const correction: CorrectionCreate = {
      room,
      revit_guid: revitGuid,
      corrected_aks: aks,
      correction_type: "manual_match",
    }

    set({
      matches,
      unmatchedAks,
      unmatchedRevit,
      roomSummary: recalcRoomSummary(matches, unmatchedAks, unmatchedRevit),
      pendingCorrections: [...state.pendingCorrections, correction],
      undoStack: [...state.undoStack, snapshot],
      redoStack: [],
      hasUnsavedChanges: true,
      selectedAksId: null,
      selectedRevitGuid: null,
    })
  },

  undoCorrection: () => {
    const state = get()
    if (state.undoStack.length === 0) return

    const currentSnapshot = takeSnapshot(state)
    const previous = state.undoStack[state.undoStack.length - 1]!
    const newPending = state.pendingCorrections.slice(0, -1)

    set({
      matches: previous.matches,
      unmatchedAks: previous.unmatchedAks,
      unmatchedRevit: previous.unmatchedRevit,
      roomSummary: recalcRoomSummary(previous.matches, previous.unmatchedAks, previous.unmatchedRevit),
      pendingCorrections: newPending,
      undoStack: state.undoStack.slice(0, -1),
      redoStack: [...state.redoStack, currentSnapshot],
      hasUnsavedChanges: newPending.length > 0,
    })
  },

  redoCorrection: () => {
    const state = get()
    if (state.redoStack.length === 0) return

    const currentSnapshot = takeSnapshot(state)
    const next = state.redoStack[state.redoStack.length - 1]!

    set({
      matches: next.matches,
      unmatchedAks: next.unmatchedAks,
      unmatchedRevit: next.unmatchedRevit,
      pendingCorrections: next.pendingCorrections,
      roomSummary: recalcRoomSummary(next.matches, next.unmatchedAks, next.unmatchedRevit),
      undoStack: [...state.undoStack, currentSnapshot],
      redoStack: state.redoStack.slice(0, -1),
      hasUnsavedChanges: next.pendingCorrections.length > 0,
    })
  },

  resetAllCorrections: () => {
    const state = get()
    if (state.undoStack.length === 0) return

    const first = state.undoStack[0]!
    set({
      matches: first.matches,
      unmatchedAks: first.unmatchedAks,
      unmatchedRevit: first.unmatchedRevit,
      roomSummary: recalcRoomSummary(first.matches, first.unmatchedAks, first.unmatchedRevit),
      pendingCorrections: [],
      undoStack: [],
      redoStack: [],
      hasUnsavedChanges: false,
      selectedAksId: null,
      selectedRevitGuid: null,
    })
  },

  setFilter: (filter) => set({ filter }),
  setSelectedAks: (aks) => set({ selectedAksId: aks }),
  setSelectedRevitGuid: (guid) => set({ selectedRevitGuid: guid }),
  clearSelection: () => set({ selectedAksId: null, selectedRevitGuid: null }),

  markSaved: (data) => {
    set({
      matches: data.matches,
      unmatchedAks: data.unmatched_aks,
      unmatchedRevit: data.unmatched_revit,
      roomSummary: data.room_summary,
      savedCorrections: data.corrections,
      pendingCorrections: [],
      undoStack: [],
      redoStack: [],
      hasUnsavedChanges: false,
    })
  },
}))

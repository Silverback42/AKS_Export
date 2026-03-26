import { useEffect, useRef, useState } from "react"
import { getTask } from "@/api/client"
import type { Task } from "@/types"

/**
 * Pollt den Task-Status alle `intervalMs` Millisekunden.
 * Stoppt automatisch wenn der Task completed oder failed ist.
 */
export function useTaskPolling(taskId: string | null, intervalMs = 1500) {
  const [task, setTask] = useState<Task | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (!taskId) {
      setTask(null)
      return
    }

    let cancelled = false

    const poll = async () => {
      try {
        const t = await getTask(taskId)
        if (!cancelled) {
          setTask(t)
          if (t.status === "completed" || t.status === "failed") {
            if (intervalRef.current) {
              clearInterval(intervalRef.current)
              intervalRef.current = null
            }
          }
        }
      } catch {
        // Ignoriere Polling-Fehler
      }
    }

    // Sofort einmal abfragen
    poll()
    intervalRef.current = setInterval(poll, intervalMs)

    return () => {
      cancelled = true
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
    }
  }, [taskId, intervalMs])

  return task
}

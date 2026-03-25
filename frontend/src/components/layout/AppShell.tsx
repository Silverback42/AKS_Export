import { Outlet } from "react-router-dom"
import { Sidebar } from "./Sidebar"

export function AppShell() {
  return (
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 overflow-auto bg-muted/30 p-6">
        <Outlet />
      </main>
    </div>
  )
}

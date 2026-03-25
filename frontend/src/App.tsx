import { Navigate, Route, Routes } from "react-router-dom"
import { AppShell } from "./components/layout/AppShell"
import { ProjectListPage } from "./pages/ProjectListPage"
import { ProjectDetailPage } from "./pages/ProjectDetailPage"

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/projects" element={<ProjectListPage />} />
        <Route path="/projects/:id" element={<ProjectDetailPage />} />
      </Route>
      <Route path="/" element={<Navigate to="/projects" replace />} />
    </Routes>
  )
}

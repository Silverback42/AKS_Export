import { Navigate, Route, Routes } from "react-router-dom"
import { ErrorBoundary } from "./components/layout/ErrorBoundary"
import { AppShell } from "./components/layout/AppShell"
import { ProjectListPage } from "./pages/ProjectListPage"
import { ProjectDetailPage } from "./pages/ProjectDetailPage"
import { ExtractionPage } from "./pages/ExtractionPage"
import { MatchingPage } from "./pages/MatchingPage"
import { ReviewPage } from "./pages/ReviewPage"

export default function App() {
  return (
    <ErrorBoundary>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/projects" element={<ProjectListPage />} />
          <Route path="/projects/:id" element={<ProjectDetailPage />} />
          <Route path="/projects/:id/extraction" element={<ExtractionPage />} />
          <Route path="/projects/:id/matching" element={<MatchingPage />} />
          <Route path="/projects/:id/matching/:taskId/review" element={<ReviewPage />} />
        </Route>
        <Route path="/" element={<Navigate to="/projects" replace />} />
      </Routes>
    </ErrorBoundary>
  )
}

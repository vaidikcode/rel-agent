import { Link, Route, Routes } from "react-router-dom"
import { EvaluatePage } from "@/pages/EvaluatePage"
import { RankingPage } from "@/pages/RankingPage"
import { AdminPage } from "@/pages/AdminPage"

function App() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b border-border px-6 py-4">
        <nav className="flex gap-6">
          <Link to="/" className="text-primary font-medium hover:underline">
            Evaluate
          </Link>
          <Link to="/ranking" className="text-muted-foreground hover:text-foreground">
            Ranking
          </Link>
          <Link to="/admin" className="text-muted-foreground hover:text-foreground">
            Admin
          </Link>
        </nav>
      </header>
      <main className="container mx-auto max-w-4xl px-6 py-8">
        <Routes>
          <Route path="/" element={<EvaluatePage />} />
          <Route path="/ranking" element={<RankingPage />} />
          <Route path="/admin" element={<AdminPage />} />
        </Routes>
      </main>
    </div>
  )
}

export default App

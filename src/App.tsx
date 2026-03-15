import { Link, Route, Routes } from "react-router-dom"
import { BucketListPage } from "@/pages/BucketListPage"
import { CreateBucketPage } from "@/pages/CreateBucketPage"
import { BucketDetailPage } from "@/pages/BucketDetailPage"
import { CandidateDetailPage } from "@/pages/CandidateDetailPage"

function App() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b border-border px-6 py-4">
        <div className="flex items-center justify-between gap-6">
          <Link to="/" className="flex items-center shrink-0">
            <img src="/logo-dark.png" alt="Mirelo AI" className="h-8 w-auto" />
          </Link>
          <nav className="flex items-center gap-6">
            <Link to="/" className="text-muted-foreground hover:text-foreground font-medium">
              Buckets
            </Link>
          </nav>
        </div>
      </header>
      <main className="container mx-auto max-w-4xl px-6 py-8">
        <Routes>
          <Route path="/" element={<BucketListPage />} />
          <Route path="/buckets/new" element={<CreateBucketPage />} />
          <Route path="/buckets/:id" element={<BucketDetailPage />} />
          <Route path="/buckets/:id/candidates/:candidateId" element={<CandidateDetailPage />} />
        </Routes>
      </main>
    </div>
  )
}

export default App

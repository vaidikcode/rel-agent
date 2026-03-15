import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Badge } from "@/components/ui/badge"
import { Plus, Briefcase, Loader2 } from "lucide-react"

const API = "/api"

type Bucket = {
  id: string
  title: string
  job_description: string
  candidate_count: number
  created_at: string
}

export function BucketListPage() {
  const [buckets, setBuckets] = useState<Bucket[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    fetch(`${API}/buckets`)
      .then((r) => { if (!r.ok) throw new Error(r.statusText); return r.json() })
      .then((data) => { if (!cancelled) setBuckets(data) })
      .catch((e) => { if (!cancelled) setError(e.message) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-48" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-32 w-full" />
      </div>
    )
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Job Buckets</h1>
          <p className="text-muted-foreground mt-1">Create a bucket per role, discover candidates, and evaluate them.</p>
        </div>
        <Link to="/buckets/new">
          <Button>
            <Plus className="mr-2 h-4 w-4" />
            New bucket
          </Button>
        </Link>
      </div>

      {error && <p className="text-destructive">{error}</p>}

      {buckets.length === 0 && !error && (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            <Briefcase className="mx-auto h-10 w-10 mb-3 opacity-50" />
            <p>No job buckets yet. Create one to get started.</p>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        {buckets.map((b) => (
          <Link key={b.id} to={`/buckets/${b.id}`} className="block">
            <Card className="h-full hover:border-primary/50 transition-colors cursor-pointer">
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between gap-2">
                  <CardTitle className="text-lg">{b.title}</CardTitle>
                  <Badge variant="secondary" className="shrink-0">{b.candidate_count} candidates</Badge>
                </div>
                <CardDescription className="line-clamp-2">
                  {b.job_description || "No description"}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-xs text-muted-foreground">
                  Created {new Date(b.created_at).toLocaleDateString()}
                </p>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  )
}

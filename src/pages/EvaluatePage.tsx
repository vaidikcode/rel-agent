import { useState, useRef } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { FileUp, Loader2, CheckCircle2 } from "lucide-react"
import { cn } from "@/lib/utils"

const API_BASE = "/api"

type Verdict = { passed: boolean; reason: string }
type EvalResult = {
  name: string
  email: string
  results: Record<string, Verdict>
  score: number
  max_score: number
  relevance_percentage?: number
  save_error?: string
  candidate_id?: string
}

export function EvaluatePage() {
  const inputRef = useRef<HTMLInputElement>(null)
  const [files, setFiles] = useState<File[]>([])
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState({ current: 0, total: 0 })
  const [error, setError] = useState<string | null>(null)
  const [results, setResults] = useState<EvalResult[]>([])

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const list = e.target.files ? Array.from(e.target.files) : []
    const valid = list.filter((f) => /\.(pdf|docx?)$/i.test(f.name))
    setFiles(valid)
    setError(null)
    setResults([])
  }

  async function processOne(file: File): Promise<EvalResult> {
    const form = new FormData()
    form.append("file", file)
    form.append("save_to_db", "true")
    const res = await fetch(`${API_BASE}/evaluate`, { method: "POST", body: form })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      const message = err.detail || err.message || res.statusText
      const isQuota = res.status === 429 || /quota|rate limit|resource exhausted/i.test(String(message))
      throw new Error(isQuota ? `QUOTA_EXCEEDED:${message}` : message)
    }
    return res.json()
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (files.length === 0) {
      setError("Select one or more resumes (PDF or DOCX)")
      return
    }
    setError(null)
    setResults([])
    setLoading(true)
    const out: EvalResult[] = []
    setProgress({ current: 0, total: files.length })
    for (let i = 0; i < files.length; i++) {
      setProgress({ current: i + 1, total: files.length })
      try {
        const one = await processOne(files[i])
        out.push(one)
        setResults([...out])
      } catch (err) {
        const message = err instanceof Error ? err.message : "Evaluation failed"
        const isQuota = message.startsWith("QUOTA_EXCEEDED:")
        setError(
          isQuota
            ? "API quota or rate limit reached. Please wait about a minute and try again (free tier has limited requests per minute)."
            : message
        )
        setResults([...out])
        break
      }
    }
    setLoading(false)
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Evaluate candidates</h1>
        <p className="text-muted-foreground mt-1">
          Upload one or more resumes (PDF or DOCX). Name and email are extracted from each resume. The agent checks each requirement and saves results to the ranking.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Upload resumes</CardTitle>
          <CardDescription>Select multiple files to process them one by one.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="flex flex-wrap items-center gap-3">
              <input
                ref={inputRef}
                type="file"
                accept=".pdf,.docx,.doc"
                multiple
                onChange={handleFileChange}
                className="hidden"
              />
              <Button
                type="button"
                variant="outline"
                onClick={() => inputRef.current?.click()}
                disabled={loading}
              >
                <FileUp className="mr-2 h-4 w-4" />
                Choose files
              </Button>
              {files.length > 0 && (
                <span className="text-muted-foreground text-sm">
                  {files.length} file{files.length !== 1 ? "s" : ""} selected
                </span>
              )}
            </div>
            {error && (
              <div
                className={
                  error.includes("quota or rate limit")
                    ? "rounded-lg border border-amber-500/50 bg-amber-950/20 px-3 py-2 text-sm text-amber-200"
                    : "text-destructive text-sm"
                }
              >
                {error}
                {error.includes("quota or rate limit") && (
                  <p className="mt-1.5 text-xs text-muted-foreground">
                    Free tier allows a few requests per minute. Try again in 1–2 minutes.
                  </p>
                )}
              </div>
            )}
            <Button type="submit" disabled={loading || files.length === 0}>
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Processing {progress.current} of {progress.total}…
                </>
              ) : (
                <>
                  <FileUp className="mr-2 h-4 w-4" />
                  Evaluate all
                </>
              )}
            </Button>
          </form>
        </CardContent>
      </Card>

      {loading && results.length < progress.total && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Processing…</CardTitle>
            <CardDescription>Evaluating resume {progress.current} of {progress.total}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-3/4" />
            <Skeleton className="h-8 w-1/2" />
          </CardContent>
        </Card>
      )}

      {results.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold">Results ({results.length})</h2>
          {results.map((result, idx) => (
            <Card key={idx}>
              <CardHeader className="pb-2">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="h-5 w-5 text-primary" />
                  <CardTitle className="text-base">{result.name}</CardTitle>
                  {result.email && (
                    <span className="text-muted-foreground text-sm">{result.email}</span>
                  )}
                </div>
                <CardDescription>
                  Relevance: {result.relevance_percentage ?? (result.max_score ? Math.round((result.score / result.max_score) * 100) : 0)}%
                  {result.candidate_id && " · Saved to ranking"}
                  {result.save_error && ` · ${result.save_error}`}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(result.results).map(([reqId, v]) => (
                    <Badge
                      key={reqId}
                      variant="outline"
                      className={cn(
                        "font-normal",
                        v.passed
                          ? "border-emerald-500 text-white border-2 bg-transparent hover:bg-emerald-500/10"
                          : "border-red-500 text-red-200 border-2 bg-transparent hover:bg-red-500/10"
                      )}
                    >
                      {reqId.replace(/_/g, " ")}: {v.passed ? "Yes" : "No"}
                    </Badge>
                  ))}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}

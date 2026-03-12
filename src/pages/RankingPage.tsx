import { useEffect, useState } from "react"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { Loader2, ChevronDown, ChevronRight, FileText } from "lucide-react"
import { cn } from "@/lib/utils"

const API_BASE = "/api"

type EvalRow = { requirement_id: string; passed: boolean; reason?: string }

type RankRow = {
  id: string
  name: string
  email: string
  resume_url?: string | null
  created_at: string
  score: number
  relevance_percentage: number
  evaluations: EvalRow[]
}

export function RankingPage() {
  const [rows, setRows] = useState<RankRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedCandidate, setSelectedCandidate] = useState<RankRow | null>(null)
  const [reasonOpen, setReasonOpen] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    async function fetchRanking() {
      try {
        const res = await fetch(`${API_BASE}/ranking`)
        if (!res.ok) throw new Error(res.statusText)
        const data = await res.json()
        if (!cancelled) setRows(data)
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load ranking")
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    fetchRanking()
    return () => { cancelled = true }
  }, [])

  function openDetail(row: RankRow) {
    setSelectedCandidate(row)
    setReasonOpen(null)
  }

  function closeDetail() {
    setSelectedCandidate(null)
    setReasonOpen(null)
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin" />
        Loading ranking…
      </div>
    )
  }

  return (
    <div className="space-y-8 min-w-0 overflow-hidden">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Ranking</h1>
        <p className="text-muted-foreground mt-1">
          Relevance % = weighted requirements met. Click a row to open details in a popup.
        </p>
      </div>

      {error && <p className="text-destructive">{error}</p>}

      <Card className="min-w-0 overflow-hidden">
        <CardHeader>
          <CardTitle>Candidates</CardTitle>
          <CardDescription>Sorted by relevance % (highest first). Resume column links to the stored file.</CardDescription>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          {rows.length === 0 ? (
            <p className="text-muted-foreground">No candidates yet. Evaluate resumes on the Evaluate page.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-8 shrink-0" />
                  <TableHead className="w-10 shrink-0">#</TableHead>
                  <TableHead className="min-w-0">Name</TableHead>
                  <TableHead className="min-w-0 max-w-[180px]">Email</TableHead>
                  <TableHead className="w-24 shrink-0 text-center">Resume</TableHead>
                  <TableHead className="w-16 shrink-0 text-right">Relevance %</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row, idx) => (
                  <TableRow
                    key={row.id}
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => openDetail(row)}
                  >
                    <TableCell className="w-8 py-2 shrink-0">
                      <ChevronRight className="h-4 w-4 text-muted-foreground" />
                    </TableCell>
                    <TableCell className="font-medium py-2 shrink-0">{idx + 1}</TableCell>
                    <TableCell className="py-2 min-w-0 max-w-[200px] truncate" title={row.name}>{row.name}</TableCell>
                    <TableCell className="py-2 text-muted-foreground min-w-0 max-w-[180px] truncate" title={row.email}>{row.email}</TableCell>
                      <TableCell className="py-2 shrink-0 text-center" onClick={(ev) => ev.stopPropagation()}>
                        {row.resume_url ? (
                          <a
                            href={row.resume_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center justify-center rounded-lg border border-input h-7 px-2.5 text-xs font-medium hover:bg-muted/50"
                          >
                            <FileText className="h-3 w-3 mr-1" />
                            View
                          </a>
                        ) : (
                        <span className="text-muted-foreground text-xs">—</span>
                      )}
                    </TableCell>
                    <TableCell className="py-2 text-right shrink-0">
                      <Badge variant="secondary">{row.relevance_percentage}%</Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Dialog open={!!selectedCandidate} onOpenChange={(open) => !open && closeDetail()}>
        <DialogContent
          className="max-w-[min(calc(100vw-2rem),28rem)] max-h-[85vh] flex flex-col overflow-hidden"
          showCloseButton
        >
          {selectedCandidate && (
            <>
              <DialogHeader>
                <DialogTitle>{selectedCandidate.name}</DialogTitle>
                <DialogDescription>{selectedCandidate.email}</DialogDescription>
              </DialogHeader>
              <div className="flex flex-col gap-4 overflow-hidden min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  {selectedCandidate.resume_url ? (
                    <a
                      href={selectedCandidate.resume_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-2 rounded-lg border border-input bg-transparent px-2.5 py-1.5 text-sm font-medium hover:bg-muted/50"
                    >
                      <FileText className="h-4 w-4" />
                      Open resume
                    </a>
                  ) : (
                    <span className="text-muted-foreground text-sm">No resume file</span>
                  )}
                  <Badge variant="secondary" className="font-mono">
                    Relevance {selectedCandidate.relevance_percentage}%
                  </Badge>
                </div>
                <Card data-size="sm" className="rounded-lg border flex-1 min-h-0 overflow-hidden">
                  <CardHeader className="py-3">
                    <CardTitle className="text-sm font-medium">Verdicts</CardTitle>
                    <CardDescription className="text-xs">
                      Expand a requirement to see the evaluator’s reason.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="pt-0 overflow-y-auto max-h-[50vh] min-w-0">
                    <div className="rounded-md border border-border divide-y divide-border">
                      {(selectedCandidate.evaluations || []).map((e) => {
                        const isOpen = reasonOpen === e.requirement_id
                        return (
                          <Collapsible
                            key={e.requirement_id}
                            open={isOpen}
                            onOpenChange={(open) =>
                              setReasonOpen(open ? e.requirement_id : null)
                            }
                          >
                            <CollapsibleTrigger
                              className={cn(
                                "flex w-full items-center gap-3 px-3 py-2.5 text-left text-sm font-medium transition-colors hover:bg-muted/50 data-[state=open]:bg-muted/30",
                                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-none first:rounded-t-md last:rounded-b-md min-h-[2.5rem]"
                              )}
                            >
                              <span className="capitalize text-foreground min-w-0 flex-1 truncate">
                                {e.requirement_id.replace(/_/g, " ")}
                              </span>
                              <span className="flex shrink-0 items-center gap-2">
                                <Badge
                                  variant="outline"
                                  className={cn(
                                    "h-6 min-w-[2.25rem] justify-center border-2 font-normal text-xs leading-none",
                                    e.passed
                                      ? "border-emerald-500 text-emerald-400 bg-transparent"
                                      : "border-red-500 text-red-400 bg-transparent"
                                  )}
                                >
                                  {e.passed ? "Yes" : "No"}
                                </Badge>
                                <ChevronDown
                                  className={cn(
                                    "h-4 w-4 text-muted-foreground transition-transform duration-200",
                                    isOpen && "rotate-180"
                                  )}
                                />
                              </span>
                            </CollapsibleTrigger>
                            <CollapsibleContent>
                              <div className="px-3 pb-3 pt-0 min-w-0">
                                <p className="text-muted-foreground text-sm leading-relaxed break-words">
                                  {e.reason || "—"}
                                </p>
                              </div>
                            </CollapsibleContent>
                          </Collapsible>
                        )
                      })}
                    </div>
                  </CardContent>
                </Card>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}

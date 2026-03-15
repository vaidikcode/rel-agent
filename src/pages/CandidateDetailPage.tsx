import { useEffect, useState, useCallback } from "react"
import { useParams, useNavigate } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { ArrowLeft, ExternalLink, Loader2, Play, ChevronDown, Pencil, Save, Trash2, Github, Globe, FileText, Linkedin } from "lucide-react"
import { cn } from "@/lib/utils"

const API = "/api"

function LinkTypeIcon({ type }: { type: string }) {
  const cls = "h-4 w-4 shrink-0 text-muted-foreground"
  switch (type) {
    case "github": return <Github className={cls} />
    case "linkedin": return <Linkedin className={cls} />
    case "paper": return <FileText className={cls} />
    case "blog": return <Globe className={cls} />
    default: return <Globe className={cls} />
  }
}

type CandidateLink = { id: string; url: string; label: string; source: string; link_type?: string }
type Evaluation = { requirement_id: string; requirement_label?: string; passed: boolean; reason: string }
type FetchedDetail = {
  link_id: string; url: string; label: string; link_type: string
  content_type: string; content_preview: string
  metadata: Record<string, any>; fetched_at: string | null
}
type Candidate = {
  id: string; bucket_id: string; name: string; headline: string; location: string
  summary: string; skills: string[] | string; status: string
  relevance_percentage: number | null; created_at: string
  links: CandidateLink[]; evaluations: Evaluation[]
  fetched_details?: FetchedDetail[]
}

export function CandidateDetailPage() {
  const { id: bucketId, candidateId } = useParams<{ id: string; candidateId: string }>()
  const navigate = useNavigate()
  const [candidate, setCandidate] = useState<Candidate | null>(null)
  const [loading, setLoading] = useState(true)
  const [evaluating, setEvaluating] = useState(false)
  const [evalError, setEvalError] = useState<string | null>(null)
  const [openReason, setOpenReason] = useState<string | null>(null)
  const [openDetail, setOpenDetail] = useState<string | null>(null)
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [editName, setEditName] = useState("")
  const [editHeadline, setEditHeadline] = useState("")
  const [editLocation, setEditLocation] = useState("")
  const [editSummary, setEditSummary] = useState("")
  const [editSkillsStr, setEditSkillsStr] = useState("")

  const fetchCandidate = useCallback(async () => {
    try {
      const r = await fetch(`${API}/buckets/${bucketId}/candidates/${candidateId}`)
      if (!r.ok) throw new Error("Not found")
      setCandidate(await r.json())
    } catch {}
  }, [bucketId, candidateId])

  useEffect(() => {
    fetchCandidate().finally(() => setLoading(false))
  }, [fetchCandidate])

  useEffect(() => {
    if (candidate) {
      setEditName(candidate.name)
      setEditHeadline(candidate.headline || "")
      setEditLocation(candidate.location || "")
      setEditSummary(candidate.summary || "")
      const sk = Array.isArray(candidate.skills) ? candidate.skills : (() => { try { return JSON.parse(candidate.skills as string) } catch { return [] } })()
      setEditSkillsStr(sk.join(", "))
    }
  }, [candidate])

  async function handleSaveProfile() {
    if (!candidateId || !bucketId) return
    setSaving(true)
    try {
      const r = await fetch(`${API}/buckets/${bucketId}/candidates/${candidateId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: editName.trim() || "Unnamed",
          headline: editHeadline.trim(),
          location: editLocation.trim() || "Unknown",
          summary: editSummary.trim(),
          skills: editSkillsStr.split(",").map((s) => s.trim()).filter(Boolean),
        }),
      })
      if (r.ok) {
        await fetchCandidate()
        setEditing(false)
      }
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    if (!candidateId || !bucketId || !confirm("Remove this candidate from the bucket?")) return
    setDeleting(true)
    try {
      const r = await fetch(`${API}/buckets/${bucketId}/candidates/${candidateId}`, { method: "DELETE" })
      if (r.ok) navigate(`/buckets/${bucketId}`)
    } finally {
      setDeleting(false)
    }
  }

  async function handleEvaluate() {
    setEvaluating(true)
    setEvalError(null)
    try {
      const r = await fetch(`${API}/buckets/${bucketId}/candidates/${candidateId}/evaluate`, { method: "POST" })
      if (!r.ok) {
        const err = await r.json().catch(() => ({ detail: r.statusText }))
        throw new Error(err.detail || r.statusText)
      }
      await fetchCandidate()
    } catch (e) {
      setEvalError(e instanceof Error ? e.message : "Evaluation failed")
    } finally {
      setEvaluating(false)
    }
  }

  if (loading) {
    return <div className="space-y-4"><Skeleton className="h-8 w-64" /><Skeleton className="h-48 w-full" /></div>
  }
  if (!candidate) {
    return <p className="text-destructive">Candidate not found</p>
  }

  const skills: string[] = Array.isArray(candidate.skills)
    ? candidate.skills
    : (() => { try { return JSON.parse(candidate.skills as string) } catch { return [] } })()

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => navigate(bucketId ? `/buckets/${bucketId}` : "/")}><ArrowLeft className="h-4 w-4" /></Button>
        <div className="flex-1 min-w-0">
          <h1 className="text-2xl font-semibold tracking-tight truncate">{candidate.name}</h1>
          {candidate.headline && <p className="text-muted-foreground text-sm">{candidate.headline}</p>}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <Badge variant={candidate.status === "evaluated" ? "default" : "outline"}>{candidate.status}</Badge>
          {candidate.relevance_percentage != null && (
            <Badge variant="secondary" className="font-mono">{candidate.relevance_percentage}%</Badge>
          )}
          <Button variant="ghost" size="icon" className="text-muted-foreground hover:text-destructive" onClick={handleDelete} disabled={deleting}>
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Profile card */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <CardTitle className="text-base">Profile</CardTitle>
          {!editing && <Button variant="ghost" size="sm" onClick={() => setEditing(true)}><Pencil className="h-3 w-3 mr-1" />Edit</Button>}
        </CardHeader>
        <CardContent className="space-y-3">
          {editing ? (
            <>
              <div className="space-y-1"><Label>Name</Label><Input value={editName} onChange={(e) => setEditName(e.target.value)} /></div>
              <div className="space-y-1"><Label>Headline</Label><Input value={editHeadline} onChange={(e) => setEditHeadline(e.target.value)} /></div>
              <div className="space-y-1"><Label>Location</Label><Input value={editLocation} onChange={(e) => setEditLocation(e.target.value)} /></div>
              <div className="space-y-1"><Label>Summary</Label><Textarea value={editSummary} onChange={(e) => setEditSummary(e.target.value)} rows={3} className="resize-y" /></div>
              <div className="space-y-1"><Label>Skills (comma-separated)</Label><Input value={editSkillsStr} onChange={(e) => setEditSkillsStr(e.target.value)} /></div>
              <div className="flex gap-2">
                <Button size="sm" onClick={handleSaveProfile} disabled={saving}>{saving ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <Save className="h-3 w-3 mr-1" />}Save</Button>
                <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>Cancel</Button>
              </div>
            </>
          ) : (
            <>
              {candidate.location && candidate.location !== "Unknown" && (
                <p className="text-sm"><span className="text-muted-foreground">Location:</span> {candidate.location}</p>
              )}
              {candidate.summary && <p className="text-sm">{candidate.summary}</p>}
              {skills.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {skills.map((s) => <Badge key={s} variant="outline" className="text-xs font-normal">{s}</Badge>)}
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {/* Links card – show all profile links */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Links</CardTitle>
          <CardDescription>Profile links (e.g. LinkedIn, GitHub). All are used by the evaluation agent.</CardDescription>
        </CardHeader>
        <CardContent>
          {candidate.links.length === 0 ? (
            <p className="text-muted-foreground text-sm">No links yet.</p>
          ) : (
            <div className="space-y-2">
              {candidate.links.map((l) => (
                <a
                  key={l.id}
                  href={l.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 rounded-lg border p-2.5 hover:bg-muted/50 transition-colors text-sm"
                >
                  <ExternalLink className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                  <span className="truncate flex-1">{l.label || l.url}</span>
                  <Badge variant="outline" className="text-xs shrink-0">{l.source}</Badge>
                </a>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Fetched Profile Details */}
      {candidate.fetched_details && candidate.fetched_details.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Profile details</CardTitle>
            <CardDescription>Fetched content from each link, used by the evaluation agent.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="rounded-md border divide-y">
              {candidate.fetched_details.map((fd) => {
                const isOpen = openDetail === fd.link_id
                return (
                  <Collapsible key={fd.link_id} open={isOpen} onOpenChange={(open) => setOpenDetail(open ? fd.link_id : null)}>
                    <CollapsibleTrigger className="flex w-full items-center gap-3 px-3 py-2.5 text-sm text-left hover:bg-muted/50 transition-colors">
                      <LinkTypeIcon type={fd.link_type} />
                      <span className="flex-1 min-w-0 truncate">{fd.label || fd.url}</span>
                      <Badge variant="outline" className="text-xs shrink-0">{fd.link_type}</Badge>
                      {fd.fetched_at && <span className="text-xs text-muted-foreground shrink-0">{new Date(fd.fetched_at).toLocaleDateString()}</span>}
                      <ChevronDown className={cn("h-4 w-4 text-muted-foreground transition-transform", isOpen && "rotate-180")} />
                    </CollapsibleTrigger>
                    <CollapsibleContent>
                      <div className="px-3 pb-3 space-y-2">
                        {fd.link_type === "github" && fd.metadata?.languages && (
                          <div className="flex flex-wrap gap-1">
                            {(fd.metadata.languages as string[]).map((lang: string) => <Badge key={lang} variant="outline" className="text-xs">{lang}</Badge>)}
                          </div>
                        )}
                        {fd.link_type === "github" && fd.metadata?.total_stars != null && (
                          <p className="text-xs text-muted-foreground">{fd.metadata.public_repos ?? 0} repos, {fd.metadata.total_stars}★, {fd.metadata.followers ?? 0} followers</p>
                        )}
                        <p className="text-sm text-muted-foreground whitespace-pre-wrap">{fd.content_preview || "No content fetched."}</p>
                      </div>
                    </CollapsibleContent>
                  </Collapsible>
                )
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Evaluate / Results */}
      {candidate.status !== "evaluated" ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Evaluate</CardTitle>
            <CardDescription>The agent will scrape this candidate's links and score them against the bucket requirements.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Button onClick={handleEvaluate} disabled={evaluating}>
              {evaluating
                ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Evaluating…</>
                : <><Play className="mr-2 h-4 w-4" />Evaluate candidate</>}
            </Button>
            {evalError && <p className="text-destructive text-sm">{evalError}</p>}
            {evaluating && (
              <div className="space-y-2"><Skeleton className="h-6 w-full" /><Skeleton className="h-6 w-5/6" /><Skeleton className="h-6 w-4/6" /></div>
            )}
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Evaluation results</CardTitle>
            <CardDescription>Relevance: {candidate.relevance_percentage ?? 0}%</CardDescription>
          </CardHeader>
          <CardContent>
            {candidate.evaluations.length === 0 ? (
              <p className="text-muted-foreground text-sm">No evaluation data.</p>
            ) : (
              <div className="rounded-md border divide-y">
                {candidate.evaluations.map((ev) => {
                  const isOpen = openReason === ev.requirement_id
                  return (
                    <Collapsible key={ev.requirement_id} open={isOpen} onOpenChange={(open) => setOpenReason(open ? ev.requirement_id : null)}>
                      <CollapsibleTrigger className="flex w-full items-center gap-3 px-3 py-2.5 text-sm text-left hover:bg-muted/50 transition-colors">
                        <span className="flex-1 min-w-0 truncate">{ev.requirement_label ?? ev.requirement_id}</span>
                        <Badge variant="outline" className={cn("text-xs border-2", ev.passed ? "border-emerald-500 text-emerald-400" : "border-red-500 text-red-400")}>
                          {ev.passed ? "Yes" : "No"}
                        </Badge>
                        <ChevronDown className={cn("h-4 w-4 text-muted-foreground transition-transform", isOpen && "rotate-180")} />
                      </CollapsibleTrigger>
                      <CollapsibleContent>
                        <p className="px-3 pb-3 text-sm text-muted-foreground">{ev.reason || "—"}</p>
                      </CollapsibleContent>
                    </Collapsible>
                  )
                })}
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}

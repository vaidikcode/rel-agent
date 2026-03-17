import { useEffect, useState, useCallback } from "react"
import { useParams, useNavigate } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import {
  ArrowLeft, ExternalLink, Loader2, Play, ChevronDown, Pencil, Save, Trash2,
  Github, Globe, FileText, Linkedin, MapPin, Briefcase, GraduationCap,
  ThumbsUp, AlertCircle, CheckCircle2, XCircle, Search,
} from "lucide-react"
import { cn } from "@/lib/utils"

const API = "/api"

function LinkTypeIcon({ type, className }: { type: string; className?: string }) {
  const cls = className || "h-4 w-4 shrink-0 text-muted-foreground"
  switch (type) {
    case "github": return <Github className={cls} />
    case "linkedin": return <Linkedin className={cls} />
    case "paper": return <FileText className={cls} />
    case "blog": return <Globe className={cls} />
    default: return <Globe className={cls} />
  }
}

function ScoreRing({ score }: { score: number }) {
  const r = 28, stroke = 5, circ = 2 * Math.PI * r
  const offset = circ - (score / 100) * circ
  const color = score >= 70 ? "text-emerald-500" : score >= 40 ? "text-amber-500" : "text-red-500"
  return (
    <div className="relative h-[72px] w-[72px] shrink-0">
      <svg viewBox="0 0 66 66" className="h-full w-full -rotate-90">
        <circle cx="33" cy="33" r={r} fill="none" stroke="currentColor" strokeWidth={stroke} className="text-muted/30" />
        <circle cx="33" cy="33" r={r} fill="none" stroke="currentColor" strokeWidth={stroke}
          strokeDasharray={circ} strokeDashoffset={offset} strokeLinecap="round" className={color} />
      </svg>
      <span className={cn("absolute inset-0 flex items-center justify-center text-lg font-bold", color)}>{score}%</span>
    </div>
  )
}

type CandidateLink = { id: string; url: string; label: string; source: string; link_type?: string }
type Evaluation = { requirement_id: string; requirement_label?: string; passed: boolean; reason: string }
type FetchedDetail = {
  link_id: string; url: string; label: string; link_type: string
  content_type: string; content_preview: string
  metadata: Record<string, any>; fetched_at: string | null
}
type EvaluationDetails = {
  experience_summary?: string | null
  education?: string | null
  key_skills_evidence?: string | null
  strengths?: string[]
  concerns?: string[]
  fit_summary?: string | null
}
type Candidate = {
  id: string; bucket_id: string; name: string; headline: string; location: string
  summary: string; skills: string[] | string; status: string
  relevance_percentage: number | null; created_at: string
  links: CandidateLink[]; evaluations: Evaluation[]
  fetched_details?: FetchedDetail[]
  evaluation_details?: EvaluationDetails | string | null
}

export function CandidateDetailPage() {
  const { id: bucketId, candidateId } = useParams<{ id: string; candidateId: string }>()
  const navigate = useNavigate()
  const [candidate, setCandidate] = useState<Candidate | null>(null)
  const [loading, setLoading] = useState(true)
  const [evaluating, setEvaluating] = useState(false)
  const [evalError, setEvalError] = useState<string | null>(null)
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

  useEffect(() => { fetchCandidate().finally(() => setLoading(false)) }, [fetchCandidate])

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
        method: "PATCH", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: editName.trim() || "Unnamed", headline: editHeadline.trim(),
          location: editLocation.trim() || "Unknown", summary: editSummary.trim(),
          skills: editSkillsStr.split(",").map((s) => s.trim()).filter(Boolean),
        }),
      })
      if (r.ok) { await fetchCandidate(); setEditing(false) }
    } finally { setSaving(false) }
  }

  async function handleDelete() {
    if (!candidateId || !bucketId || !confirm("Remove this candidate from the bucket?")) return
    setDeleting(true)
    try {
      const r = await fetch(`${API}/buckets/${bucketId}/candidates/${candidateId}`, { method: "DELETE" })
      if (r.ok) navigate(`/buckets/${bucketId}`)
    } finally { setDeleting(false) }
  }

  async function handleEvaluate() {
    setEvaluating(true); setEvalError(null)
    try {
      const r = await fetch(`${API}/buckets/${bucketId}/candidates/${candidateId}/evaluate`, { method: "POST" })
      if (!r.ok) {
        const err = await r.json().catch(() => ({ detail: r.statusText }))
        throw new Error(err.detail || r.statusText)
      }
      await fetchCandidate()
    } catch (e) { setEvalError(e instanceof Error ? e.message : "Evaluation failed") }
    finally { setEvaluating(false) }
  }

  if (loading) return <div className="space-y-4 max-w-4xl"><Skeleton className="h-10 w-64" /><Skeleton className="h-48 w-full" /></div>
  if (!candidate) return <p className="text-destructive">Candidate not found</p>

  const skills: string[] = Array.isArray(candidate.skills)
    ? candidate.skills
    : (() => { try { return JSON.parse(candidate.skills as string) } catch { return [] } })()

  const details: EvaluationDetails | null = (() => {
    const raw = candidate.evaluation_details
    if (!raw) return null
    if (typeof raw === "string") { try { return JSON.parse(raw) as EvaluationDetails } catch { return null } }
    return raw as EvaluationDetails
  })()

  const isEvaluated = candidate.status === "evaluated"
  const score = candidate.relevance_percentage ?? 0
  const passCount = candidate.evaluations.filter(e => e.passed).length
  const totalReqs = candidate.evaluations.length

  return (
    <div className="space-y-6 max-w-4xl">
      {/* ─── Header ─── */}
      <div className="flex items-start gap-4">
        <Button variant="ghost" size="icon" className="shrink-0 mt-1" onClick={() => navigate(bucketId ? `/buckets/${bucketId}` : "/")}>
          <ArrowLeft className="h-4 w-4" />
        </Button>

        <div className="flex-1 min-w-0 space-y-2">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold tracking-tight truncate">{candidate.name}</h1>
            <Badge variant={isEvaluated ? "default" : "outline"} className="shrink-0">{candidate.status}</Badge>
          </div>
          {candidate.headline && <p className="text-muted-foreground text-sm">{candidate.headline}</p>}
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
            {candidate.location && candidate.location !== "Unknown" && (
              <span className="inline-flex items-center gap-1"><MapPin className="h-3 w-3" />{candidate.location}</span>
            )}
            {candidate.summary && <span className="line-clamp-1 max-w-md">{candidate.summary}</span>}
          </div>
          {skills.length > 0 && (
            <div className="flex flex-wrap gap-1 pt-1">
              {skills.slice(0, 10).map((s) => <Badge key={s} variant="secondary" className="text-[11px] font-normal">{s}</Badge>)}
              {skills.length > 10 && <Badge variant="outline" className="text-[11px]">+{skills.length - 10}</Badge>}
            </div>
          )}
        </div>

        {isEvaluated && <ScoreRing score={score} />}

        <div className="flex items-center gap-1 shrink-0">
          {!editing && (
            <Button variant="ghost" size="icon" className="text-muted-foreground" onClick={() => setEditing(true)}>
              <Pencil className="h-4 w-4" />
            </Button>
          )}
          <Button variant="ghost" size="icon" className="text-muted-foreground hover:text-destructive" onClick={handleDelete} disabled={deleting}>
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* ─── Edit form (inline, shown when editing) ─── */}
      {editing && (
        <Card>
          <CardContent className="pt-4 space-y-3">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1"><Label className="text-xs">Name</Label><Input value={editName} onChange={(e) => setEditName(e.target.value)} className="h-8 text-sm" /></div>
              <div className="space-y-1"><Label className="text-xs">Headline</Label><Input value={editHeadline} onChange={(e) => setEditHeadline(e.target.value)} className="h-8 text-sm" /></div>
              <div className="space-y-1"><Label className="text-xs">Location</Label><Input value={editLocation} onChange={(e) => setEditLocation(e.target.value)} className="h-8 text-sm" /></div>
              <div className="space-y-1"><Label className="text-xs">Skills (comma-separated)</Label><Input value={editSkillsStr} onChange={(e) => setEditSkillsStr(e.target.value)} className="h-8 text-sm" /></div>
            </div>
            <div className="space-y-1"><Label className="text-xs">Summary</Label><Textarea value={editSummary} onChange={(e) => setEditSummary(e.target.value)} rows={2} className="resize-y text-sm" /></div>
            <div className="flex gap-2">
              <Button size="sm" onClick={handleSaveProfile} disabled={saving}>{saving ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" /> : <Save className="h-3.5 w-3.5 mr-1.5" />}Save</Button>
              <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>Cancel</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* ─── Evaluate CTA ─── */}
      {!isEvaluated && (
        <Card className="border-dashed">
          <CardContent className="flex items-center gap-4 py-4">
            <Search className="h-5 w-5 text-muted-foreground shrink-0" />
            <div className="flex-1">
              <p className="text-sm font-medium">Ready to evaluate</p>
              <p className="text-xs text-muted-foreground">The agent will fetch links, research the candidate, and score against requirements.</p>
            </div>
            <Button onClick={handleEvaluate} disabled={evaluating} size="sm">
              {evaluating ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Evaluating…</> : <><Play className="mr-2 h-4 w-4" />Evaluate</>}
            </Button>
          </CardContent>
          {evalError && <p className="text-destructive text-xs px-4 pb-3">{evalError}</p>}
        </Card>
      )}

      {/* ─── Fit Summary (hero card after evaluation) ─── */}
      {details?.fit_summary && (
        <Card className="bg-muted/30">
          <CardContent className="py-4">
            <p className="text-sm leading-relaxed">{details.fit_summary}</p>
          </CardContent>
        </Card>
      )}

      {/* ─── Requirements verdicts ─── */}
      {totalReqs > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-medium">Requirements</CardTitle>
              <span className="text-xs text-muted-foreground">{passCount}/{totalReqs} passed</span>
            </div>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="space-y-1.5">
              {candidate.evaluations.map((ev) => (
                <div key={ev.requirement_id} className="flex items-start gap-2.5 rounded-md border px-3 py-2">
                  {ev.passed
                    ? <CheckCircle2 className="h-4 w-4 text-emerald-500 mt-0.5 shrink-0" />
                    : <XCircle className="h-4 w-4 text-red-500 mt-0.5 shrink-0" />}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium">{ev.requirement_label ?? ev.requirement_id}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">{ev.reason || "—"}</p>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* ─── Structured details (experience, education, strengths, concerns) ─── */}
      {details && (details.experience_summary || details.education || details.key_skills_evidence || (details.strengths?.length) || (details.concerns?.length)) && (
        <div className="grid gap-4 sm:grid-cols-2">
          {/* Left column: experience + education + skills */}
          <div className="space-y-4">
            {details.experience_summary && (
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium flex items-center gap-1.5"><Briefcase className="h-3.5 w-3.5" />Experience</CardTitle>
                </CardHeader>
                <CardContent className="pt-0">
                  <p className="text-sm text-muted-foreground leading-relaxed">{details.experience_summary}</p>
                </CardContent>
              </Card>
            )}
            {details.education && (
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium flex items-center gap-1.5"><GraduationCap className="h-3.5 w-3.5" />Education</CardTitle>
                </CardHeader>
                <CardContent className="pt-0">
                  <p className="text-sm text-muted-foreground leading-relaxed">{details.education}</p>
                </CardContent>
              </Card>
            )}
            {details.key_skills_evidence && (
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium">Skills evidence</CardTitle>
                </CardHeader>
                <CardContent className="pt-0">
                  <p className="text-sm text-muted-foreground leading-relaxed">{details.key_skills_evidence}</p>
                </CardContent>
              </Card>
            )}
          </div>
          {/* Right column: strengths + concerns */}
          <div className="space-y-4">
            {details.strengths && details.strengths.length > 0 && (
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium flex items-center gap-1.5"><ThumbsUp className="h-3.5 w-3.5 text-emerald-500" />Strengths</CardTitle>
                </CardHeader>
                <CardContent className="pt-0">
                  <ul className="space-y-1.5">
                    {details.strengths.map((s, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-muted-foreground">
                        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 mt-0.5 shrink-0" />
                        <span>{s}</span>
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            )}
            {details.concerns && details.concerns.length > 0 && (
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium flex items-center gap-1.5"><AlertCircle className="h-3.5 w-3.5 text-amber-500" />Concerns</CardTitle>
                </CardHeader>
                <CardContent className="pt-0">
                  <ul className="space-y-1.5">
                    {details.concerns.map((c, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-muted-foreground">
                        <AlertCircle className="h-3.5 w-3.5 text-amber-500 mt-0.5 shrink-0" />
                        <span>{c}</span>
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      )}

      {/* ─── Links ─── */}
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-medium">Links</CardTitle>
            <span className="text-xs text-muted-foreground">{candidate.links.length} total</span>
          </div>
        </CardHeader>
        <CardContent className="pt-0">
          {candidate.links.length === 0 ? (
            <p className="text-muted-foreground text-xs py-2">No links discovered yet.</p>
          ) : (
            <div className="grid gap-1.5 sm:grid-cols-2">
              {candidate.links.map((l) => (
                <a key={l.id} href={l.url} target="_blank" rel="noopener noreferrer"
                  className="flex items-center gap-2 rounded-md border px-3 py-2 hover:bg-muted/50 transition-colors text-xs group">
                  <LinkTypeIcon type={l.link_type || "web"} />
                  <span className="truncate flex-1 group-hover:text-primary transition-colors">{l.label || l.url}</span>
                  <Badge variant="outline" className={cn("text-[10px] shrink-0",
                    l.source === "eval_agent" && "border-blue-400 text-blue-500 dark:border-blue-500 dark:text-blue-400"
                  )}>{l.source === "eval_agent" ? "agent" : l.source}</Badge>
                  <ExternalLink className="h-3 w-3 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity shrink-0" />
                </a>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* ─── Fetched content (collapsible per link) ─── */}
      {candidate.fetched_details && candidate.fetched_details.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-medium">Fetched content</CardTitle>
              <span className="text-xs text-muted-foreground">{candidate.fetched_details.length} sources</span>
            </div>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="rounded-md border divide-y">
              {candidate.fetched_details.map((fd) => {
                const isOpen = openDetail === fd.link_id
                return (
                  <Collapsible key={fd.link_id} open={isOpen} onOpenChange={(open) => setOpenDetail(open ? fd.link_id : null)}>
                    <CollapsibleTrigger className="flex w-full items-center gap-2 px-3 py-2.5 text-xs text-left hover:bg-muted/50 transition-colors">
                      <LinkTypeIcon type={fd.link_type} className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                      <span className="flex-1 min-w-0 truncate font-medium">{fd.label || fd.url}</span>
                      <Badge variant="outline" className="text-[10px] shrink-0">{fd.link_type}</Badge>
                      {fd.fetched_at && <span className="text-[10px] text-muted-foreground shrink-0">{new Date(fd.fetched_at).toLocaleDateString()}</span>}
                      <ChevronDown className={cn("h-3 w-3 text-muted-foreground shrink-0 transition-transform", isOpen && "rotate-180")} />
                    </CollapsibleTrigger>
                    <CollapsibleContent>
                      <div className="px-3 pb-3 space-y-2 border-t bg-muted/20">
                        {fd.link_type === "github" && fd.metadata?.languages && (
                          <div className="flex flex-wrap gap-1 pt-2">
                            {(fd.metadata.languages as string[]).map((lang: string) => <Badge key={lang} variant="secondary" className="text-[10px]">{lang}</Badge>)}
                          </div>
                        )}
                        {fd.link_type === "github" && fd.metadata?.total_stars != null && (
                          <p className="text-[11px] text-muted-foreground pt-1">{fd.metadata.public_repos ?? 0} repos · {fd.metadata.total_stars}★ · {fd.metadata.followers ?? 0} followers</p>
                        )}
                        {fd.metadata?.owner_profile && (
                          <div className="rounded-md border bg-background p-2 space-y-1 mt-1">
                            <p className="text-[11px] font-medium flex items-center gap-1"><Github className="h-3 w-3" />Repo owner</p>
                            <p className="text-[11px]">{fd.metadata.owner_profile.name ?? fd.metadata.owner_profile.username}{fd.metadata.owner_profile.username && <span className="text-muted-foreground ml-1">@{String(fd.metadata.owner_profile.username)}</span>}</p>
                            {fd.metadata.owner_profile.bio && <p className="text-[11px] text-muted-foreground">{String(fd.metadata.owner_profile.bio)}</p>}
                            <p className="text-[11px] text-muted-foreground">{Number(fd.metadata.owner_profile.public_repos ?? 0)} repos · {Number(fd.metadata.owner_profile.total_stars ?? 0)}★ · {Number(fd.metadata.owner_profile.followers ?? 0)} followers</p>
                            {fd.metadata.owner_profile.languages?.length > 0 && (
                              <div className="flex flex-wrap gap-1">{(fd.metadata.owner_profile.languages as string[]).map((lang: string) => <Badge key={lang} variant="secondary" className="text-[10px]">{lang}</Badge>)}</div>
                            )}
                          </div>
                        )}
                        <p className="text-xs text-muted-foreground whitespace-pre-wrap line-clamp-8 pt-1">{fd.content_preview || "No content."}</p>
                      </div>
                    </CollapsibleContent>
                  </Collapsible>
                )
              })}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

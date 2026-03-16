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
import { ArrowLeft, ExternalLink, Loader2, Play, ChevronDown, Pencil, Save, Trash2, Github, Globe, FileText, Linkedin, MapPin, Briefcase, GraduationCap, ThumbsUp, AlertCircle } from "lucide-react"
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

  const details: EvaluationDetails | null = (() => {
    const raw = candidate.evaluation_details
    if (!raw) return null
    if (typeof raw === "string") {
      try { return JSON.parse(raw) as EvaluationDetails } catch { return null }
    }
    return raw as EvaluationDetails
  })()

  return (
    <div className="space-y-5 max-w-3xl">
      {/* Compact header */}
      <div className="flex items-start gap-3">
        <Button variant="ghost" size="icon" className="shrink-0 mt-0.5" onClick={() => navigate(bucketId ? `/buckets/${bucketId}` : "/")}><ArrowLeft className="h-4 w-4" /></Button>
        <div className="flex-1 min-w-0">
          <h1 className="text-xl font-semibold tracking-tight truncate">{candidate.name}</h1>
          {candidate.headline && <p className="text-muted-foreground text-sm mt-0.5">{candidate.headline}</p>}
          <div className="flex flex-wrap items-center gap-2 mt-2">
            {candidate.location && candidate.location !== "Unknown" && (
              <span className="inline-flex items-center gap-1 text-xs text-muted-foreground"><MapPin className="h-3 w-3" />{candidate.location}</span>
            )}
            {skills.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {skills.slice(0, 8).map((s) => <Badge key={s} variant="secondary" className="text-[10px] font-normal py-0">{s}</Badge>)}
                {skills.length > 8 && <Badge variant="outline" className="text-[10px] py-0">+{skills.length - 8}</Badge>}
              </div>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <Badge variant={candidate.status === "evaluated" ? "default" : "outline"}>{candidate.status}</Badge>
          {candidate.relevance_percentage != null && (
            <Badge variant="secondary" className="font-mono text-sm">{candidate.relevance_percentage}%</Badge>
          )}
          <Button variant="ghost" size="icon" className="text-muted-foreground hover:text-destructive" onClick={handleDelete} disabled={deleting}><Trash2 className="h-4 w-4" /></Button>
        </div>
      </div>

      {/* Structured details (after evaluation) */}
      {details && (details.experience_summary || details.education || details.fit_summary || (details.strengths && details.strengths.length) || (details.concerns && details.concerns.length) || details.key_skills_evidence) && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Structured evaluation</CardTitle>
            <CardDescription>Details extracted from profiles and requirements.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            {(details.experience_summary || details.education) && (
              <div className="grid gap-3 sm:grid-cols-2">
                {details.experience_summary && (
                  <div>
                    <p className="font-medium text-muted-foreground flex items-center gap-1.5 mb-1"><Briefcase className="h-3.5 w-3.5" />Experience</p>
                    <p className="text-foreground">{details.experience_summary}</p>
                  </div>
                )}
                {details.education && (
                  <div>
                    <p className="font-medium text-muted-foreground flex items-center gap-1.5 mb-1"><GraduationCap className="h-3.5 w-3.5" />Education</p>
                    <p className="text-foreground">{details.education}</p>
                  </div>
                )}
              </div>
            )}
            {details.fit_summary && (
              <div>
                <p className="font-medium text-muted-foreground mb-1">Fit summary</p>
                <p className="text-foreground">{details.fit_summary}</p>
              </div>
            )}
            {details.key_skills_evidence && (
              <div>
                <p className="font-medium text-muted-foreground mb-1">Key skills evidence</p>
                <p className="text-foreground">{details.key_skills_evidence}</p>
              </div>
            )}
            <div className="grid gap-3 sm:grid-cols-2">
              {details.strengths && details.strengths.length > 0 && (
                <div>
                  <p className="font-medium text-muted-foreground flex items-center gap-1.5 mb-1.5"><ThumbsUp className="h-3.5 w-3.5 text-emerald-500" />Strengths</p>
                  <ul className="space-y-1 list-disc list-inside text-muted-foreground">
                    {details.strengths.map((s, i) => <li key={i}>{s}</li>)}
                  </ul>
                </div>
              )}
              {details.concerns && details.concerns.length > 0 && (
                <div>
                  <p className="font-medium text-muted-foreground flex items-center gap-1.5 mb-1.5"><AlertCircle className="h-3.5 w-3.5 text-amber-500" />Concerns</p>
                  <ul className="space-y-1 list-disc list-inside text-muted-foreground">
                    {details.concerns.map((c, i) => <li key={i}>{c}</li>)}
                  </ul>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Requirements verdicts – compact */}
      {candidate.evaluations.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Requirements</CardTitle>
            <CardDescription>{candidate.relevance_percentage ?? 0}% match</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="rounded-md border divide-y">
              {candidate.evaluations.map((ev) => {
                const isOpen = openReason === ev.requirement_id
                return (
                  <Collapsible key={ev.requirement_id} open={isOpen} onOpenChange={(open) => setOpenReason(open ? ev.requirement_id : null)}>
                    <CollapsibleTrigger className="flex w-full items-center gap-3 px-3 py-2 text-sm text-left hover:bg-muted/50 transition-colors">
                      <span className="flex-1 min-w-0 truncate">{ev.requirement_label ?? ev.requirement_id}</span>
                      <Badge variant="outline" className={cn("text-xs shrink-0", ev.passed ? "border-emerald-500 text-emerald-600 dark:text-emerald-400" : "border-red-500 text-red-600 dark:text-red-400")}>
                        {ev.passed ? "Pass" : "Fail"}
                      </Badge>
                      <ChevronDown className={cn("h-4 w-4 text-muted-foreground shrink-0 transition-transform", isOpen && "rotate-180")} />
                    </CollapsibleTrigger>
                    <CollapsibleContent>
                      <p className="px-3 pb-2 pt-0 text-xs text-muted-foreground">{ev.reason || "—"}</p>
                    </CollapsibleContent>
                  </Collapsible>
                )
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Evaluate CTA or placeholder */}
      {candidate.status !== "evaluated" && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Evaluate</CardTitle>
            <CardDescription>Score this candidate against bucket requirements and get structured details.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            <Button onClick={handleEvaluate} disabled={evaluating} size="sm">
              {evaluating ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Evaluating…</> : <><Play className="mr-2 h-4 w-4" />Evaluate candidate</>}
            </Button>
            {evalError && <p className="text-destructive text-xs">{evalError}</p>}
          </CardContent>
        </Card>
      )}

      {/* Profile + Links – compact row */}
      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 py-2">
            <CardTitle className="text-sm font-medium">Profile</CardTitle>
            {!editing && <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={() => setEditing(true)}><Pencil className="h-3 w-3 mr-1" />Edit</Button>}
          </CardHeader>
          <CardContent className="space-y-2 pt-0">
            {editing ? (
              <>
                <div className="space-y-1"><Label className="text-xs">Name</Label><Input value={editName} onChange={(e) => setEditName(e.target.value)} className="h-8 text-sm" /></div>
                <div className="space-y-1"><Label className="text-xs">Headline</Label><Input value={editHeadline} onChange={(e) => setEditHeadline(e.target.value)} className="h-8 text-sm" /></div>
                <div className="space-y-1"><Label className="text-xs">Location</Label><Input value={editLocation} onChange={(e) => setEditLocation(e.target.value)} className="h-8 text-sm" /></div>
                <div className="space-y-1"><Label className="text-xs">Summary</Label><Textarea value={editSummary} onChange={(e) => setEditSummary(e.target.value)} rows={2} className="resize-y text-sm" /></div>
                <div className="space-y-1"><Label className="text-xs">Skills (comma)</Label><Input value={editSkillsStr} onChange={(e) => setEditSkillsStr(e.target.value)} className="h-8 text-sm" /></div>
                <div className="flex gap-2">
                  <Button size="sm" className="h-7 text-xs" onClick={handleSaveProfile} disabled={saving}>{saving ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <Save className="h-3 w-3 mr-1" />}Save</Button>
                  <Button size="sm" variant="ghost" className="h-7 text-xs" onClick={() => setEditing(false)}>Cancel</Button>
                </div>
              </>
            ) : (
              <>
                {candidate.summary ? <p className="text-xs text-muted-foreground line-clamp-3">{candidate.summary}</p> : <p className="text-xs text-muted-foreground italic">No summary</p>}
              </>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="py-2">
            <CardTitle className="text-sm font-medium">Links</CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            {candidate.links.length === 0 ? (
              <p className="text-muted-foreground text-xs">No links.</p>
            ) : (
              <div className="space-y-1">
                {candidate.links.map((l) => (
                  <a key={l.id} href={l.url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 rounded border px-2 py-1.5 hover:bg-muted/50 text-xs">
                    <ExternalLink className="h-3 w-3 shrink-0 text-muted-foreground" />
                    <span className="truncate flex-1">{l.label || l.url}</span>
                    <Badge variant="outline" className="text-[10px] shrink-0">{l.source}</Badge>
                  </a>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Fetched Profile Details */}
      {/* Fetched content (collapsible) */}
      {candidate.fetched_details && candidate.fetched_details.length > 0 && (
        <Card>
          <CardHeader className="py-2">
            <CardTitle className="text-sm font-medium">Fetched profile content</CardTitle>
            <CardDescription className="text-xs">Content from each link used by the evaluator.</CardDescription>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="rounded-md border divide-y">
              {candidate.fetched_details.map((fd) => {
                const isOpen = openDetail === fd.link_id
                return (
                  <Collapsible key={fd.link_id} open={isOpen} onOpenChange={(open) => setOpenDetail(open ? fd.link_id : null)}>
                    <CollapsibleTrigger className="flex w-full items-center gap-2 px-2 py-2 text-xs text-left hover:bg-muted/50 transition-colors">
                      <LinkTypeIcon type={fd.link_type} />
                      <span className="flex-1 min-w-0 truncate">{fd.label || fd.url}</span>
                      <Badge variant="outline" className="text-[10px] shrink-0">{fd.link_type}</Badge>
                      {fd.fetched_at && <span className="text-[10px] text-muted-foreground shrink-0">{new Date(fd.fetched_at).toLocaleDateString()}</span>}
                      <ChevronDown className={cn("h-3 w-3 text-muted-foreground shrink-0 transition-transform", isOpen && "rotate-180")} />
                    </CollapsibleTrigger>
                    <CollapsibleContent>
                      <div className="px-2 pb-2 space-y-2">
                        {fd.link_type === "github" && fd.metadata?.languages && (
                          <div className="flex flex-wrap gap-1">
                            {(fd.metadata.languages as string[]).map((lang: string) => <Badge key={lang} variant="outline" className="text-[10px]">{lang}</Badge>)}
                          </div>
                        )}
                        {fd.link_type === "github" && fd.metadata?.total_stars != null && (
                          <p className="text-[10px] text-muted-foreground">{fd.metadata.public_repos ?? 0} repos, {fd.metadata.total_stars}★, {fd.metadata.followers ?? 0} followers</p>
                        )}
                        {fd.metadata?.owner_profile && (
                          <div className="rounded border bg-muted/30 p-1.5 space-y-0.5">
                            <p className="text-[10px] font-medium text-muted-foreground flex items-center gap-1"><Github className="h-2.5 w-2.5" />Repo owner</p>
                            <p className="text-[10px]">{fd.metadata.owner_profile.name ?? fd.metadata.owner_profile.username}{fd.metadata.owner_profile.username && <span className="text-muted-foreground ml-1">@{String(fd.metadata.owner_profile.username)}</span>}</p>
                            {fd.metadata.owner_profile.bio && <p className="text-[10px] text-muted-foreground">{String(fd.metadata.owner_profile.bio)}</p>}
                            <p className="text-[10px] text-muted-foreground">{Number(fd.metadata.owner_profile.public_repos ?? 0)} repos, {Number(fd.metadata.owner_profile.total_stars ?? 0)}★, {Number(fd.metadata.owner_profile.followers ?? 0)} followers</p>
                            {fd.metadata.owner_profile.languages?.length > 0 && (
                              <div className="flex flex-wrap gap-1">{(fd.metadata.owner_profile.languages as string[]).map((lang: string) => <Badge key={lang} variant="outline" className="text-[10px]">{lang}</Badge>)}</div>
                            )}
                          </div>
                        )}
                        {fd.metadata?.discovered_links?.length > 0 && (
                          <div className="space-y-1 rounded border bg-muted/30 p-1.5">
                            <p className="text-[10px] font-medium text-muted-foreground">Discovered ({(fd.metadata.discovered_links as unknown[]).length})</p>
                            {(fd.metadata.discovered_links as { url: string; link_type: string; metadata?: Record<string, unknown> }[]).slice(0, 5).map((dl, idx) => (
                              <div key={idx} className="text-[10px] flex items-center gap-1.5">
                                <LinkTypeIcon type={dl.link_type} />
                                <a href={dl.url} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline truncate">{dl.url}</a>
                              </div>
                            ))}
                            {(fd.metadata.discovered_links as unknown[]).length > 5 && <p className="text-[10px] text-muted-foreground">+{(fd.metadata.discovered_links as unknown[]).length - 5} more</p>}
                          </div>
                        )}
                        {fd.metadata?.discovered_github?.length > 0 && !fd.metadata?.discovered_links && (
                          <div className="space-y-1 rounded border bg-muted/30 p-1.5">
                            <p className="text-[10px] font-medium text-muted-foreground">GitHub</p>
                            {(fd.metadata.discovered_github as { url: string }[]).slice(0, 5).map((dg, idx) => (
                              <a key={idx} href={dg.url} target="_blank" rel="noopener noreferrer" className="text-[10px] text-primary hover:underline block truncate">{dg.url}</a>
                            ))}
                          </div>
                        )}
                        <p className="text-xs text-muted-foreground whitespace-pre-wrap line-clamp-6">{fd.content_preview || "No content."}</p>
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

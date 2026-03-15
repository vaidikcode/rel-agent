import { useEffect, useState, useCallback } from "react"
import { useParams, Link, useNavigate } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Loader2, Search, Trash2, Plus, ArrowLeft, ChevronRight, Pencil, Save } from "lucide-react"

const API = "/api"

type Req = { id: string; label: string; prompt: string; weight: number; sort_order: number }
type Candidate = {
  id: string; name: string; headline: string; location: string; summary: string
  skills: string[] | string; status: string; relevance_percentage: number | null; created_at: string
}
type Bucket = {
  id: string; title: string; job_description: string; requirements: Req[]
  candidate_count: number; created_at: string
}

export function BucketDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [bucket, setBucket] = useState<Bucket | null>(null)
  const [candidates, setCandidates] = useState<Candidate[]>([])
  const [loading, setLoading] = useState(true)
  const [discovering, setDiscovering] = useState(false)
  const [discoverError, setDiscoverError] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const fetchBucket = useCallback(async () => {
    try {
      const r = await fetch(`${API}/buckets/${id}`)
      if (!r.ok) throw new Error("Bucket not found")
      setBucket(await r.json())
    } catch (e) { setError(e instanceof Error ? e.message : "Failed") }
  }, [id])

  const fetchCandidates = useCallback(async () => {
    try {
      const r = await fetch(`${API}/buckets/${id}/candidates`)
      if (!r.ok) return
      const data = await r.json()
      setCandidates(data)
    } catch {}
  }, [id])

  useEffect(() => {
    Promise.all([fetchBucket(), fetchCandidates()]).finally(() => setLoading(false))
  }, [fetchBucket, fetchCandidates])

  async function handleDiscover() {
    setDiscovering(true)
    setDiscoverError(null)
    try {
      const r = await fetch(`${API}/buckets/${id}/discover`, { method: "POST" })
      if (!r.ok) {
        const err = await r.json().catch(() => ({ detail: r.statusText }))
        throw new Error(err.detail || r.statusText)
      }
      await fetchCandidates()
      await fetchBucket()
    } catch (e) {
      setDiscoverError(e instanceof Error ? e.message : "Discovery failed")
    } finally {
      setDiscovering(false)
    }
  }

  async function handleDeleteCandidate(candidateId: string) {
    if (!confirm("Remove this candidate from the bucket?")) return
    try {
      const r = await fetch(`${API}/buckets/${id}/candidates/${candidateId}`, { method: "DELETE" })
      if (r.ok) await fetchCandidates()
    } catch {}
  }

  if (loading) {
    return <div className="space-y-4"><Skeleton className="h-10 w-64" /><Skeleton className="h-64 w-full" /></div>
  }
  if (error || !bucket) {
    return <p className="text-destructive">{error || "Bucket not found"}</p>
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link to="/"><Button variant="ghost" size="icon"><ArrowLeft className="h-4 w-4" /></Button></Link>
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{bucket.title}</h1>
          <p className="text-muted-foreground text-sm line-clamp-1">{bucket.job_description || "No description"}</p>
        </div>
      </div>

      <Tabs defaultValue="discover">
        <TabsList>
          <TabsTrigger value="discover">Discover</TabsTrigger>
          <TabsTrigger value="candidates">Candidates ({candidates.length})</TabsTrigger>
          <TabsTrigger value="admin">Admin</TabsTrigger>
        </TabsList>

        {/* --- Discover Tab --- */}
        <TabsContent value="discover" className="space-y-4 mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Discover</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <Button onClick={handleDiscover} disabled={discovering}>
                {discovering
                  ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Searching…</>
                  : <><Search className="mr-2 h-4 w-4" />Discover candidates</>}
              </Button>
              {discoverError && <p className="text-destructive text-sm">{discoverError}</p>}
              {discovering && (
                <div className="space-y-2 pt-2">
                  <Skeleton className="h-8 w-full" /><Skeleton className="h-8 w-5/6" /><Skeleton className="h-8 w-4/6" />
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* --- Candidates Tab --- */}
        <TabsContent value="candidates" className="mt-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0">
              <div>
                <CardTitle>Candidates</CardTitle>
                <CardDescription>Click a candidate to see details and evaluate.</CardDescription>
              </div>
              <AddCandidateDialog bucketId={id!} onAdded={fetchCandidates} />
            </CardHeader>
            <CardContent className="overflow-x-auto">
              {candidates.length === 0 ? (
                <p className="text-muted-foreground text-sm py-4">No candidates yet. Add one or run discovery.</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-8" />
                      <TableHead>Name</TableHead>
                      <TableHead className="hidden sm:table-cell">Headline</TableHead>
                      <TableHead className="w-28">Status</TableHead>
                      <TableHead className="w-24 text-right">Relevance</TableHead>
                      <TableHead className="w-10" />
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {candidates.map((c) => (
                      <TableRow key={c.id} className="cursor-pointer hover:bg-muted/50" onClick={() => navigate(`/buckets/${id}/candidates/${c.id}`)}>
                        <TableCell><ChevronRight className="h-4 w-4 text-muted-foreground" /></TableCell>
                        <TableCell className="font-medium truncate max-w-[200px]">{c.name}</TableCell>
                        <TableCell className="hidden sm:table-cell text-muted-foreground truncate max-w-[250px]">{c.headline}</TableCell>
                        <TableCell>
                          <Badge variant={c.status === "evaluated" ? "default" : "outline"} className="text-xs">
                            {c.status}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          {c.relevance_percentage != null ? <Badge variant="secondary">{c.relevance_percentage}%</Badge> : <span className="text-muted-foreground text-xs">—</span>}
                        </TableCell>
                        <TableCell onClick={(e) => e.stopPropagation()}>
                          <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-destructive" onClick={() => handleDeleteCandidate(c.id)}>
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* --- Admin Tab --- */}
        <TabsContent value="admin" className="space-y-4 mt-4">
          <BucketAdmin bucket={bucket} onUpdate={fetchBucket} />
          <RequirementsAdmin bucketId={bucket.id} requirements={bucket.requirements} onUpdate={fetchBucket} />
          <DangerZone bucketId={bucket.id} />
        </TabsContent>
      </Tabs>
    </div>
  )
}


/* ---------- Add candidate dialog ---------- */

function AddCandidateDialog({ bucketId, onAdded }: { bucketId: string; onAdded: () => void }) {
  const [open, setOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [name, setName] = useState("")
  const [headline, setHeadline] = useState("")
  const [location, setLocation] = useState("")
  const [summary, setSummary] = useState("")
  const [skillsStr, setSkillsStr] = useState("")

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    try {
      const r = await fetch(`${API}/buckets/${bucketId}/candidates`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim() || "Unnamed",
          headline: headline.trim(),
          location: location.trim() || "Unknown",
          summary: summary.trim(),
          skills: skillsStr.split(",").map((s) => s.trim()).filter(Boolean),
        }),
      })
      if (!r.ok) throw new Error("Failed to add")
      setOpen(false)
      setName("")
      setHeadline("")
      setLocation("")
      setSummary("")
      setSkillsStr("")
      onAdded()
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger>
        <Button size="sm"><Plus className="h-3.5 w-3.5 mr-1" />Add candidate</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add candidate</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-3">
          <div className="space-y-1"><Label>Name</Label><Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Full name" /></div>
          <div className="space-y-1"><Label>Headline</Label><Input value={headline} onChange={(e) => setHeadline(e.target.value)} placeholder="Job title or tagline" /></div>
          <div className="space-y-1"><Label>Location</Label><Input value={location} onChange={(e) => setLocation(e.target.value)} placeholder="City, Country" /></div>
          <div className="space-y-1"><Label>Summary</Label><Textarea value={summary} onChange={(e) => setSummary(e.target.value)} placeholder="Short bio" rows={3} className="resize-y" /></div>
          <div className="space-y-1"><Label>Skills (comma-separated)</Label><Input value={skillsStr} onChange={(e) => setSkillsStr(e.target.value)} placeholder="React, TypeScript, ..." /></div>
          <div className="flex gap-2 pt-2">
            <Button type="submit" disabled={saving}>{saving ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" /> : null}Save</Button>
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

/* ---------- Admin sub-components ---------- */

function BucketAdmin({ bucket, onUpdate }: { bucket: Bucket; onUpdate: () => void }) {
  const [editing, setEditing] = useState(false)
  const [title, setTitle] = useState(bucket.title)
  const [jd, setJd] = useState(bucket.job_description)
  const [saving, setSaving] = useState(false)

  async function save() {
    setSaving(true)
    await fetch(`${API}/buckets/${bucket.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, job_description: jd }),
    })
    setSaving(false)
    setEditing(false)
    onUpdate()
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Bucket settings</CardTitle>
          {!editing && <Button variant="ghost" size="sm" onClick={() => setEditing(true)}><Pencil className="h-3 w-3 mr-1" />Edit</Button>}
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {editing ? (
          <>
            <div className="space-y-1"><Label>Title</Label><Input value={title} onChange={(e) => setTitle(e.target.value)} /></div>
            <div className="space-y-1"><Label>Job description</Label><Textarea value={jd} onChange={(e) => setJd(e.target.value)} rows={4} className="resize-y" /></div>
            <div className="flex gap-2">
              <Button size="sm" onClick={save} disabled={saving}>{saving ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <Save className="h-3 w-3 mr-1" />}Save</Button>
              <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>Cancel</Button>
            </div>
          </>
        ) : (
          <>
            <p className="font-medium">{bucket.title}</p>
            <p className="text-sm text-muted-foreground whitespace-pre-wrap">{bucket.job_description || "No description"}</p>
          </>
        )}
      </CardContent>
    </Card>
  )
}


function RequirementsAdmin({ bucketId, requirements, onUpdate }: { bucketId: string; requirements: Req[]; onUpdate: () => void }) {
  const [label, setLabel] = useState("")
  const [prompt, setPrompt] = useState("")
  const [weight, setWeight] = useState(1)
  const [adding, setAdding] = useState(false)

  async function addReq() {
    if (!label.trim() || !prompt.trim()) return
    setAdding(true)
    await fetch(`${API}/buckets/${bucketId}/requirements`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ label: label.trim(), prompt: prompt.trim(), weight }),
    })
    setLabel("")
    setPrompt("")
    setWeight(1)
    setAdding(false)
    onUpdate()
  }

  async function deleteReq(reqId: string) {
    await fetch(`${API}/buckets/${bucketId}/requirements/${reqId}`, { method: "DELETE" })
    onUpdate()
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Requirements</CardTitle>
        <CardDescription>Evaluation criteria for candidates in this bucket.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {requirements.length === 0 && <p className="text-muted-foreground text-sm">No requirements yet.</p>}
        {requirements.map((r) => (
          <div key={r.id} className="flex items-start gap-2 rounded-lg border p-3">
            <div className="flex-1 min-w-0">
              <p className="font-medium text-sm">{r.label}</p>
              <p className="text-xs text-muted-foreground truncate">{r.prompt}</p>
            </div>
            <Badge variant="outline" className="shrink-0">w{r.weight}</Badge>
            <Button variant="ghost" size="icon" className="shrink-0 h-7 w-7" onClick={() => deleteReq(r.id)}><Trash2 className="h-3 w-3" /></Button>
          </div>
        ))}
        <div className="border-t pt-3 space-y-2">
          <Input placeholder="Label" value={label} onChange={(e) => setLabel(e.target.value)} />
          <Input placeholder="Prompt (what to check)" value={prompt} onChange={(e) => setPrompt(e.target.value)} />
          <div className="flex gap-2 items-center">
            <Input type="number" className="w-20" min={1} max={10} value={weight} onChange={(e) => setWeight(parseInt(e.target.value) || 1)} />
            <Button size="sm" onClick={addReq} disabled={adding || !label.trim() || !prompt.trim()}>
              {adding ? <Loader2 className="h-3 w-3 animate-spin" /> : <><Plus className="h-3 w-3 mr-1" />Add</>}
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}


function DangerZone({ bucketId }: { bucketId: string }) {
  const navigate = useNavigate()
  const [confirming, setConfirming] = useState(false)

  async function handleDelete() {
    await fetch(`${API}/buckets/${bucketId}`, { method: "DELETE" })
    navigate("/")
  }

  return (
    <Card className="border-destructive/30">
      <CardHeader><CardTitle className="text-destructive">Danger zone</CardTitle></CardHeader>
      <CardContent>
        {confirming ? (
          <div className="flex gap-2">
            <Button variant="destructive" size="sm" onClick={handleDelete}>Yes, delete bucket</Button>
            <Button variant="ghost" size="sm" onClick={() => setConfirming(false)}>Cancel</Button>
          </div>
        ) : (
          <Button variant="outline" size="sm" onClick={() => setConfirming(true)}>
            <Trash2 className="h-3 w-3 mr-1" />Delete this bucket
          </Button>
        )}
      </CardContent>
    </Card>
  )
}

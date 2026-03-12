import { useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Loader2, Plus, Pencil, Trash2, Users } from "lucide-react"

const API_BASE = "/api"

type Requirement = {
  id: string
  label: string
  prompt: string
  weight: number
  sort_order?: number
}

type Candidate = {
  id: string
  name: string
  email: string
  resume_url?: string | null
  created_at: string
}

const EXAMPLE = {
  id: "phd_ml",
  label: "PhD or PhD-level experience with machine learning",
  prompt: "Does the candidate have a PhD or PhD-level experience with machine learning? Consider equivalent research experience (e.g. first-author top-tier ML papers, years in research).",
  weight: 1,
}

export function AdminPage() {
  const [reqs, setReqs] = useState<Requirement[]>([])
  const [candidates, setCandidates] = useState<Candidate[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editForm, setEditForm] = useState<{ label: string; prompt: string; weight: number } | null>(null)
  const [addForm, setAddForm] = useState({ id: "", label: "", prompt: "", weight: 1 })
  const [saving, setSaving] = useState(false)
  const [editingCandidateId, setEditingCandidateId] = useState<string | null>(null)
  const [candidateForm, setCandidateForm] = useState<{ name: string; email: string } | null>(null)

  async function fetchReqs() {
    try {
      const res = await fetch(`${API_BASE}/requirements`)
      if (!res.ok) throw new Error(res.statusText)
      const data = await res.json()
      setReqs(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load requirements")
    } finally {
      setLoading(false)
    }
  }

  async function fetchCandidates() {
    try {
      const res = await fetch(`${API_BASE}/candidates`)
      if (!res.ok) throw new Error(res.statusText)
      const data = await res.json()
      setCandidates(data)
    } catch {
      setCandidates([])
    }
  }

  useEffect(() => {
    fetchReqs()
    fetchCandidates()
  }, [])

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault()
    if (!addForm.id.trim() || !addForm.label.trim() || !addForm.prompt.trim()) {
      setError("ID, label, and prompt are required")
      return
    }
    setSaving(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/requirements`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          id: addForm.id.trim().toLowerCase().replace(/\s+/g, "_"),
          label: addForm.label.trim(),
          prompt: addForm.prompt.trim(),
          weight: addForm.weight,
        }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || res.statusText)
      }
      setAddForm({ id: "", label: "", prompt: "", weight: 1 })
      await fetchReqs()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to add")
    } finally {
      setSaving(false)
    }
  }

  async function handleUpdate(id: string) {
    if (!editForm) return
    setSaving(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/requirements/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          label: editForm.label.trim(),
          prompt: editForm.prompt.trim(),
          weight: editForm.weight,
        }),
      })
      if (!res.ok) throw new Error(res.statusText)
      setEditingId(null)
      setEditForm(null)
      await fetchReqs()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update")
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this requirement? Evaluations referencing it will keep the requirement_id but the requirement will be removed from the list.")) return
    setSaving(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/requirements/${id}`, { method: "DELETE" })
      if (!res.ok) throw new Error(res.statusText)
      setEditingId(null)
      setEditForm(null)
      await fetchReqs()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete")
    } finally {
      setSaving(false)
    }
  }

  async function handleUpdateCandidate(candidateId: string) {
    if (!candidateForm) return
    setSaving(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/candidates/${candidateId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: candidateForm.name.trim(), email: candidateForm.email.trim() }),
      })
      if (!res.ok) throw new Error(res.statusText)
      setEditingCandidateId(null)
      setCandidateForm(null)
      await fetchCandidates()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update candidate")
    } finally {
      setSaving(false)
    }
  }

  async function handleDeleteCandidate(candidateId: string) {
    if (!confirm("Delete this candidate? All their evaluations will be removed.")) return
    setSaving(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/candidates/${candidateId}`, { method: "DELETE" })
      if (!res.ok) throw new Error(res.statusText)
      setEditingCandidateId(null)
      setCandidateForm(null)
      await fetchCandidates()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete candidate")
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin" />
        Loading…
      </div>
    )
  }

  return (
    <div className="space-y-8 min-w-0 overflow-hidden">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Admin</h1>
        <p className="text-muted-foreground mt-1">
          Manage requirements and candidates (edit extracted name/email, or delete).
        </p>
      </div>

      {error && <p className="text-destructive">{error}</p>}

      <Tabs defaultValue="requirements" className="min-w-0">
        <TabsList>
          <TabsTrigger value="requirements">Requirements</TabsTrigger>
          <TabsTrigger value="candidates">
            <Users className="h-4 w-4 mr-1.5" />
            Candidates
          </TabsTrigger>
        </TabsList>
        <TabsContent value="requirements" className="space-y-8 mt-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Example requirement</CardTitle>
          <CardDescription>Use this format: short id, clear label, and a prompt that tells the evaluator what to check.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <p><span className="text-muted-foreground">ID:</span> {EXAMPLE.id}</p>
          <p><span className="text-muted-foreground">Label:</span> {EXAMPLE.label}</p>
          <p><span className="text-muted-foreground">Prompt:</span> {EXAMPLE.prompt}</p>
          <p><span className="text-muted-foreground">Weight:</span> {EXAMPLE.weight}</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Add requirement</CardTitle>
          <CardDescription>ID will be normalized to lowercase with underscores (e.g. my_requirement).</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleAdd} className="space-y-3">
            <div className="grid gap-2 max-w-md">
              <Label htmlFor="new-id">ID</Label>
              <Input
                id="new-id"
                value={addForm.id}
                onChange={(e) => setAddForm((f) => ({ ...f, id: e.target.value }))}
                placeholder="e.g. phd_ml"
              />
            </div>
            <div className="grid gap-2 max-w-md">
              <Label htmlFor="new-label">Label</Label>
              <Input
                id="new-label"
                value={addForm.label}
                onChange={(e) => setAddForm((f) => ({ ...f, label: e.target.value }))}
                placeholder="Short label shown in UI"
              />
            </div>
            <div className="grid gap-2 max-w-2xl">
              <Label htmlFor="new-prompt">Prompt</Label>
              <Textarea
                id="new-prompt"
                value={addForm.prompt}
                onChange={(e) => setAddForm((f) => ({ ...f, prompt: e.target.value }))}
                placeholder="Instruction for the evaluator (what to check in the resume)"
                rows={3}
              />
            </div>
            <div className="grid gap-2 w-24">
              <Label htmlFor="new-weight">Weight</Label>
              <Input
                id="new-weight"
                type="number"
                min={1}
                value={addForm.weight}
                onChange={(e) => setAddForm((f) => ({ ...f, weight: parseInt(e.target.value, 10) || 1 }))}
              />
            </div>
            <Button type="submit" disabled={saving}>
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <><Plus className="h-4 w-4 mr-2" /> Add</>}
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Requirements</CardTitle>
          <CardDescription>Click Edit to change label, prompt, or weight; Delete to remove.</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ID</TableHead>
                <TableHead>Label</TableHead>
                <TableHead className="w-20">Weight</TableHead>
                <TableHead className="w-28">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {reqs.map((r) => (
                <TableRow key={r.id}>
                  <TableCell className="font-mono text-sm">{r.id}</TableCell>
                  <TableCell>
                    {editingId === r.id && editForm ? (
                      <div className="space-y-2">
                        <Input
                          value={editForm.label}
                          onChange={(e) => setEditForm((f) => f ? { ...f, label: e.target.value } : null)}
                          className="max-w-md"
                        />
                        <Textarea
                          value={editForm.prompt}
                          onChange={(e) => setEditForm((f) => f ? { ...f, prompt: e.target.value } : null)}
                          rows={2}
                          className="max-w-xl"
                        />
                      </div>
                    ) : (
                      <span className="text-sm">{r.label}</span>
                    )}
                  </TableCell>
                  <TableCell>
                    {editingId === r.id && editForm ? (
                      <Input
                        type="number"
                        min={1}
                        value={editForm.weight}
                        onChange={(e) => setEditForm((f) => f ? { ...f, weight: parseInt(e.target.value, 10) || 1 } : null)}
                        className="w-20"
                      />
                    ) : (
                      r.weight
                    )}
                  </TableCell>
                  <TableCell>
                    {editingId === r.id && editForm ? (
                      <div className="flex gap-1">
                        <Button size="sm" onClick={() => handleUpdate(r.id)} disabled={saving}>
                          Save
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => { setEditingId(null); setEditForm(null) }}>
                          Cancel
                        </Button>
                      </div>
                    ) : (
                      <div className="flex gap-1">
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => {
                            setEditingId(r.id)
                            setEditForm({ label: r.label, prompt: r.prompt, weight: r.weight })
                          }}
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </Button>
                        <Button size="sm" variant="ghost" className="text-destructive" onClick={() => handleDelete(r.id)} disabled={saving}>
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
        </TabsContent>
        <TabsContent value="candidates" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Candidates</CardTitle>
              <CardDescription>Edit extracted name/email or delete. Evaluations are removed when a candidate is deleted.</CardDescription>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              {candidates.length === 0 ? (
                <p className="text-muted-foreground">No candidates yet.</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Email</TableHead>
                      <TableHead className="w-28">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {candidates.map((c) => (
                      <TableRow key={c.id}>
                        <TableCell>
                          {editingCandidateId === c.id && candidateForm ? (
                            <Input
                              value={candidateForm.name}
                              onChange={(e) => setCandidateForm((f) => f ? { ...f, name: e.target.value } : null)}
                              className="max-w-[200px]"
                              placeholder="Name"
                            />
                          ) : (
                            c.name
                          )}
                        </TableCell>
                        <TableCell>
                          {editingCandidateId === c.id && candidateForm ? (
                            <Input
                              value={candidateForm.email}
                              onChange={(e) => setCandidateForm((f) => f ? { ...f, email: e.target.value } : null)}
                              className="max-w-[220px]"
                              placeholder="Email"
                            />
                          ) : (
                            c.email
                          )}
                        </TableCell>
                        <TableCell>
                          {editingCandidateId === c.id && candidateForm ? (
                            <div className="flex gap-1">
                              <Button size="sm" onClick={() => handleUpdateCandidate(c.id)} disabled={saving}>
                                Save
                              </Button>
                              <Button size="sm" variant="ghost" onClick={() => { setEditingCandidateId(null); setCandidateForm(null) }}>
                                Cancel
                              </Button>
                            </div>
                          ) : (
                            <div className="flex gap-1">
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => {
                                  setEditingCandidateId(c.id)
                                  setCandidateForm({ name: c.name, email: c.email })
                                }}
                              >
                                <Pencil className="h-3.5 w-3.5" />
                              </Button>
                              <Button size="sm" variant="ghost" className="text-destructive" onClick={() => handleDeleteCandidate(c.id)} disabled={saving}>
                                <Trash2 className="h-3.5 w-3.5" />
                              </Button>
                            </div>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}

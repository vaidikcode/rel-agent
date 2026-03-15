import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { Loader2, Plus, Trash2 } from "lucide-react"

const API = "/api"

type ReqRow = { label: string; prompt: string; weight: number }

export function CreateBucketPage() {
  const navigate = useNavigate()
  const [title, setTitle] = useState("")
  const [jobDescription, setJobDescription] = useState("")
  const [requirements, setRequirements] = useState<ReqRow[]>([
    { label: "", prompt: "", weight: 1 },
  ])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function addReq() {
    setRequirements([...requirements, { label: "", prompt: "", weight: 1 }])
  }

  function removeReq(idx: number) {
    setRequirements(requirements.filter((_, i) => i !== idx))
  }

  function updateReq(idx: number, field: keyof ReqRow, value: string | number) {
    const copy = [...requirements]
    copy[idx] = { ...copy[idx], [field]: value }
    setRequirements(copy)
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!title.trim()) { setError("Title is required"); return }
    setError(null)
    setLoading(true)

    const validReqs = requirements.filter((r) => r.label.trim() && r.prompt.trim())

    try {
      const res = await fetch(`${API}/buckets`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: title.trim(),
          job_description: jobDescription.trim(),
          requirements: validReqs.length > 0 ? validReqs : null,
        }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }))
        throw new Error(err.detail || res.statusText)
      }
      const bucket = await res.json()
      navigate(`/buckets/${bucket.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create bucket")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-8 max-w-2xl">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Create job bucket</h1>
        <p className="text-muted-foreground mt-1">
          Define the role, describe who to search for, and set requirements for evaluation.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Role details</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="title">Title</Label>
              <Input id="title" placeholder="e.g. Senior React Engineer" value={title} onChange={(e) => setTitle(e.target.value)} disabled={loading} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="jd">Job description</Label>
              <Textarea id="jd" placeholder="Describe the role, responsibilities, skills needed..." value={jobDescription} onChange={(e) => setJobDescription(e.target.value)} rows={6} disabled={loading} className="resize-y" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Requirements</CardTitle>
            <CardDescription>Define what the evaluation agent should check for each candidate.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {requirements.map((req, idx) => (
              <div key={idx} className="flex gap-3 items-start">
                <div className="flex-1 space-y-2">
                  <Input placeholder="Label (e.g. 5+ years React)" value={req.label} onChange={(e) => updateReq(idx, "label", e.target.value)} disabled={loading} />
                  <Input placeholder="Prompt (what to check for)" value={req.prompt} onChange={(e) => updateReq(idx, "prompt", e.target.value)} disabled={loading} />
                </div>
                <div className="w-16 space-y-2">
                  <Input type="number" min={1} max={10} value={req.weight} onChange={(e) => updateReq(idx, "weight", parseInt(e.target.value) || 1)} disabled={loading} />
                </div>
                <Button type="button" variant="ghost" size="icon" onClick={() => removeReq(idx)} disabled={loading || requirements.length <= 1} className="mt-0.5 shrink-0">
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ))}
            <Button type="button" variant="outline" size="sm" onClick={addReq} disabled={loading}>
              <Plus className="mr-1 h-3 w-3" />
              Add requirement
            </Button>
          </CardContent>
        </Card>

        {error && <p className="text-destructive text-sm">{error}</p>}

        <Button type="submit" disabled={loading} className="w-full">
          {loading ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Creating…</> : "Create bucket"}
        </Button>
      </form>
    </div>
  )
}

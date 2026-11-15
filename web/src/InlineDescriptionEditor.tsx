import { useState } from 'react'

export default function InlineDescriptionEditor({ jobId, title, hasDescription, savedDescription, onSaved }: {
  jobId: string; title: string; hasDescription: boolean; savedDescription?: string; onSaved: () => Promise<void>
}) {
  const [description, setDescription] = useState(savedDescription || '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const save = async () => {
    setBusy(true)
    setError('')
    try {
      const response = await fetch(`/api/jobs/${encodeURIComponent(jobId)}/description`, {
        method: 'PUT', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ description }),
      })
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}))
        throw new Error(typeof payload.detail === 'string' ? payload.detail : `Could not save (${response.status})`)
      }
      await onSaved()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save the description')
    } finally {
      setBusy(false)
    }
  }

  return <details className="job-description inline-jd">
    <summary>{savedDescription ? 'Edit your pasted description' : hasDescription ? 'Correct this description' : 'Have the full description? Paste it here'}</summary>
    <p className="hint">This updates {title} in your account and reruns its quick match. Interested will use the same description for the full review.</p>
    <label>Job description<textarea rows={8} maxLength={20000} value={description} onChange={event => setDescription(event.target.value)} placeholder="Paste the responsibilities and qualifications from the original posting..." /></label>
    <button className="secondary" onClick={save} disabled={busy || description.trim().length < 40}>{busy ? 'Saving...' : 'Save description and update match →'}</button>
    {error && <div className="error" role="alert">{error}</div>}
  </details>
}

import { useState } from 'react'

type Draft = { track: string; inferred_track: string; title: string; company: string; description: string; required_skills: string[]; preferred_skills: string[]; parsing_note: string }

async function post<T>(path: string, body: object): Promise<T> {
  const response = await fetch(path, { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  if (!response.ok) { const error = await response.json().catch(() => ({})); throw new Error(error.detail || `Request failed (${response.status})`) }
  return response.json()
}

export default function JobDescriptionPage({ onSaved }: { onSaved: () => Promise<void> }) {
  const [description, setDescription] = useState('')
  const [title, setTitle] = useState('')
  const [company, setCompany] = useState('')
  const [track, setTrack] = useState('')
  const [draft, setDraft] = useState<Draft | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const parse = async () => {
    setBusy(true); setError('')
    try { const next = await post<Draft>('/api/jobs/parse', { description, title, company, track: track || null }); setDraft(next); setTrack(next.track); setTitle(next.title); setCompany(next.company) }
    catch (err) { setError(err instanceof Error ? err.message : 'Could not parse the job') }
    finally { setBusy(false) }
  }
  const save = async () => {
    setBusy(true); setError('')
    try { await post('/api/jobs/pasted', { description, title, company, track }); await onSaved() }
    catch (err) { setError(err instanceof Error ? err.message : 'Could not save the job') }
    finally { setBusy(false) }
  }
  return <section className="panel pasted-job-panel"><span className="eyebrow">YOUR OWN ROLE ✦</span><h2>Paste a job description.</h2><p className="muted">We’ll pull out a first draft of the role. You can correct the path before matching. Your pasted job stays in this local account.</p>
    <label>Job description<textarea rows={13} value={description} onChange={e => { setDescription(e.target.value); setDraft(null) }} placeholder="Paste the full role, responsibilities, and qualifications here..." /></label>
    <div className="actions"><button className="secondary" onClick={parse} disabled={busy || description.trim().length < 40}>{busy ? 'Reading...' : 'Parse description →'}</button></div>
    {draft && <div className="parsed-job"><div className="section-label">REVIEW THE PARSE</div><div className="two-col"><label>Role title<input value={title} onChange={e => setTitle(e.target.value)} /></label><label>Company<input value={company} onChange={e => setCompany(e.target.value)} /></label></div><label>Path<select value={track} onChange={e => setTrack(e.target.value)}><option value="hardware">Hardware</option><option value="software">Computer science</option><option value="product">Product</option></select></label><p className="hint">Suggested path: {draft.inferred_track}. Changing this path will reparse the skill list when you save.</p><div className="parsed-tags"><strong>Required terms found</strong><div>{draft.required_skills.length ? draft.required_skills.map(term => <span className="match-tag" key={term}>{term}</span>) : <span className="muted">No exact skill terms found; the full description still goes to review.</span>}</div></div><div className="parsed-tags"><strong>Preferred terms found</strong><div>{draft.preferred_skills.length ? draft.preferred_skills.map(term => <span className="tag" key={term}>{term}</span>) : <span className="muted">None identified.</span>}</div></div><p className="hint">{draft.parsing_note}</p><button className="primary" onClick={save} disabled={busy || !title.trim()}>Save and see matches →</button></div>}
    {error && <div className="error" role="alert">{error}</div>}
  </section>
}

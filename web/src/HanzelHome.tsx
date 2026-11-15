import { useState } from 'react'

type Draft = { title: string; company: string; track: string; inferred_track: string; description: string }

export default function HanzelHome({ name, resumeName, hasProjects, onResume, onAnalyze, onFindJobs, onEditProfile }: {
  name: string
  resumeName: string
  hasProjects: boolean
  onResume: (file: File) => Promise<void>
  onAnalyze: (draft: Draft) => Promise<void>
  onFindJobs: () => void
  onEditProfile: () => void
}) {
  const [description, setDescription] = useState('')
  const [draft, setDraft] = useState<Draft | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const parse = async () => {
    setBusy(true); setError('')
    try {
      const response = await fetch('/api/jobs/parse', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ description }) })
      const result = await response.json()
      if (!response.ok) throw new Error(result.detail || 'Could not read the job description')
      setDraft(result)
    } catch (error) { setError(error instanceof Error ? error.message : 'Could not read the role') }
    finally { setBusy(false) }
  }
  const upload = async (file?: File) => {
    if (!file) return
    setBusy(true); setError('')
    try { await onResume(file) }
    catch (error) { setError(error instanceof Error ? error.message : 'Could not update résumé') }
    finally { setBusy(false) }
  }
  const run = async () => {
    if (!draft) return
    setBusy(true); setError('')
    try { await onAnalyze(draft) }
    catch (error) { setError(error instanceof Error ? error.message : 'Could not start the review') }
    finally { setBusy(false) }
  }

  return <div className="hanzel-home">
    <div className="hanzel-hero"><span className="hanzel-kicker">CLEAR FEEDBACK, NOT FLUFF</span><h1>Know where you stand<br />before you apply.</h1><p>Compare your résumé to any job description. See your strongest matches, honest gaps, and what to prepare next.</p></div>
    <div className="hanzel-check-grid">
      <section className="hanzel-check-cell"><div className="hanzel-section-title"><span>1</span><div><h2>Your résumé</h2><p>PDF, DOCX or TXT · max 10MB</p></div></div><label className="hanzel-upload"><span className="hanzel-file-icon">▤</span><strong>{resumeName || 'Choose your résumé'}</strong><small>{resumeName ? `Ready to analyze for ${name}` : 'Upload the version you plan to send'}</small><span className="hanzel-outline-button">{resumeName ? 'Replace' : 'Upload résumé'}</span><input type="file" accept=".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain" onChange={event => upload(event.target.files?.[0])} disabled={busy} /></label></section>
      <section className="hanzel-check-cell"><div className="hanzel-section-title"><span>2</span><div><h2>The job description</h2><p>Paste the full listing for a better match</p></div></div><textarea aria-label="The job description" rows={9} maxLength={20000} value={description} onChange={event => { setDescription(event.target.value); setDraft(null) }} placeholder="Paste the job description here..." /><div className="hanzel-field-meta"><span>{description.length.toLocaleString()} characters</span><span>Saved when you run the full review.</span></div></section>
    </div>
    {draft && <section className="hanzel-draft"><div><span className="hanzel-kicker">REVIEW THE ROLE</span><h2>Does this look right?</h2><p>We detected a path from the listing. Edit it before the full review.</p></div><div className="hanzel-draft-fields"><label>Role title<input value={draft.title} onChange={event => setDraft({ ...draft, title: event.target.value })} /></label><label>Company<input value={draft.company} onChange={event => setDraft({ ...draft, company: event.target.value })} /></label><label>Path<select value={draft.track} onChange={event => setDraft({ ...draft, track: event.target.value })}><option value="hardware">Hardware</option><option value="software">Software engineering</option><option value="product">Product management</option></select></label></div><button className="hanzel-accent-button" disabled={busy || !draft.title.trim() || !hasProjects} onClick={run}>{busy ? 'Starting review…' : 'Run the full review →'}</button>{!hasProjects && <button className="hanzel-link-button" onClick={onEditProfile}>Add a GitHub repository or select a project to run Depth →</button>}</section>}
    {error && <div className="error" role="alert">{error}</div>}
    <div className="hanzel-home-actions">{!draft && <button className="hanzel-accent-button" disabled={busy || !resumeName || description.trim().length < 40} onClick={parse}>{busy ? 'Reading the role…' : 'Check my fit →'}</button>}<button className="hanzel-link-button" onClick={onFindJobs}>Explore Simplify internships →</button></div>
    <div className="hanzel-steps" id="how-it-works"><div><b>01</b><h3>Add your résumé</h3><p>Upload the version you plan to send.</p></div><div><b>02</b><h3>Paste the role</h3><p>Use the complete listing, not just the title.</p></div><div><b>03</b><h3>Make your move</h3><p>Review documented strengths and specific gaps.</p></div></div>
  </div>
}

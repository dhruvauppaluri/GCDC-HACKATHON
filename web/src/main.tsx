import React, { useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import JobDescriptionPage from './JobDescriptionPage'
import InlineDescriptionEditor from './InlineDescriptionEditor'
import ReviewPanel from './ReviewPanel'
import DepthAssessmentPanel from './DepthAssessmentPanel'
import JobPreparationPanel from './JobPreparationPanel'
import HanzelHome from './HanzelHome'
import HanzelJobs from './HanzelJobs'
import HanzelSaved from './HanzelSaved'
import type { ReviewState, ReviewPreview } from './ReviewPanel'
import './style.css'

type Track = 'HW' | 'CS' | 'PM'
type Project = { id: string; source: string; title: string; url: string; summary: string; contribution?: string; selected: boolean }
type Profile = { first_name: string; last_name: string; resume_name: string; interests: string; target_tracks: Track[]; skills: Record<string, Record<string, number>>; linkedin_url: string; github_url: string; website_url: string; projects: Project[]; completed: boolean }
type User = { id: string; email: string; profile: Profile }
type Job = { description?: string; description_status?: string; description_fetch_status?: string; description_source?: string; job_id: string; track: string; title: string; company: string; required_skills: string[]; preferred_skills: string[]; matched_skills: string[]; skill_gaps: string[]; project_context: string[]; source: string; source_url?: string; locations?: string[]; terms?: string[]; research_note?: string; requirements_note?: string; screening: { advocate: string[]; skeptic: string[]; verdict: string; note: string } }
type FeedStatus = { count?: number; error?: string | null; refresh_interval_hours?: number; description_ready?: number; description_pending?: number; description_failed?: number }
type CaseItem = { case_id: string; job: { title: string; company: string; track: string; source: string }; created_at: string; review_status: string; match_score: number | null }
type SavedJob = { job_id: string; title: string; company: string; track: string; source_url?: string; saved_at: string }
type Options = { tracks: Record<Track, string>; skill_options: Record<Track, string[]> }
type DepthResult = { depth_score: number | null; confidence: string; project_summary: string; dimensions: Record<string, { score: number; evidence_ids: string[] } | null>; criteria: Record<string, string>; demonstrated_skills: { skill: string; evidence_ids: string[] }[]; limitations: string[]; evaluation_mode: string }
type CaseBundle = { case_id: string; status: string; job: Job; project_assessments: { project: Project; status: string; result: DepthResult | null; error: string | null }[]; preparation: { required_skills_with_project_evidence: string[]; required_skills_without_project_evidence: string[]; questions: { project_id: string; id: string; question: string }[] } }

async function api<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch(path, { method, credentials: 'same-origin', headers: body instanceof FormData ? undefined : body === undefined ? undefined : { 'Content-Type': 'application/json' }, body: body instanceof FormData ? body : body === undefined ? undefined : JSON.stringify(body) })
  if (!response.ok) { const error = await response.json().catch(() => ({})); throw new Error(typeof error.detail === 'string' ? error.detail : `Request failed (${response.status})`) }
  return response.status === 204 ? undefined as T : response.json()
}

const labels: Record<Track, string> = { HW: 'Hardware', CS: 'Computer science', PM: 'Product' }
const descriptions: Record<Track, string> = { HW: 'Circuits, chips & things you can touch', CS: 'Code, systems & digital experiences', PM: 'People, products & what comes next' }
const steps = ['Name', 'Resume', 'Direction', 'Skills']

function stepFor(p: Profile) { if (!p.first_name || !p.last_name) return 0; if (!p.resume_name) return 1; if (!p.target_tracks.length || !p.interests) return 2; return 3 }

function App() {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const [mode, setMode] = useState<'signup' | 'login'>('signup')
  const [view, setView] = useState<'onboarding' | 'dashboard' | 'edit' | 'matches' | 'paste' | 'case' | 'saved'>('onboarding')
  const [step, setStep] = useState(0)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [first, setFirst] = useState('')
  const [last, setLast] = useState('')
  const [resume, setResume] = useState<File | null>(null)
  const [interests, setInterests] = useState('')
  const [tracks, setTracks] = useState<Track[]>([])
  const [suggested, setSuggested] = useState<Track[]>([])
  const [skills, setSkills] = useState<Record<string, Record<string, number>>>({})
  const [customSkill, setCustomSkill] = useState<Record<string, string>>({})
  const [links, setLinks] = useState({ linkedin_url: '', github_url: '', website_url: '' })
  const [projects, setProjects] = useState<Project[]>([])
  const [resumeProjectTitle, setResumeProjectTitle] = useState('')
  const [resumeProjectSummary, setResumeProjectSummary] = useState('')
  const [importErrors, setImportErrors] = useState<string[]>([])
  const [jobs, setJobs] = useState<Job[]>([])
  const [jobQuery, setJobQuery] = useState('')
  const [savedJobs, setSavedJobs] = useState<SavedJob[]>([])
  const [caseHistory, setCaseHistory] = useState<CaseItem[]>([])
  const [feedStatus, setFeedStatus] = useState<FeedStatus | null>(null)
  const [totalAvailable, setTotalAvailable] = useState(0)
  const [caseBundle, setCaseBundle] = useState<CaseBundle | null>(null)
  const [reviewState, setReviewState] = useState<ReviewState | null>(null)
  const [reviewPreview, setReviewPreview] = useState<ReviewPreview | null>(null)
  const [reviewRequested, setReviewRequested] = useState('')
  const [options, setOptions] = useState<Options | null>(null)

  const sync = (next: User) => {
    setUser(next); const p = next.profile
    setFirst(p.first_name); setLast(p.last_name); setInterests(p.interests); setTracks(p.target_tracks)
    setSkills(p.skills || {}); setLinks({ linkedin_url: p.linkedin_url, github_url: p.github_url, website_url: p.website_url }); setProjects(p.projects || [])
    setStep(stepFor(p)); setView(p.completed ? 'dashboard' : 'onboarding')
  }
  const refresh = async () => sync(await api<User>('/api/me'))
  useEffect(() => { api<User>('/api/me').then(async next => {
    sync(next)
    const caseId = new URLSearchParams(window.location.search).get('case')
    if (!caseId) return
    const savedCase = await api<CaseBundle>(`/api/cases/${encodeURIComponent(caseId)}`)
    setCaseBundle(savedCase)
    setView('case')
    if (savedCase.status !== 'pending') {
      setReviewRequested(caseId)
      api<ReviewPreview>(`/api/cases/${encodeURIComponent(caseId)}/review-preview`).then(setReviewPreview).catch(() => {})
      api<ReviewState>(`/api/cases/${encodeURIComponent(caseId)}/review`).then(setReviewState).catch(() => {})
    }
  }).catch(() => {}).finally(() => setLoading(false)) }, [])
  useEffect(() => { if (user) api<Options>('/api/onboarding/options').then(setOptions).catch(() => {}) }, [user?.id])
  useEffect(() => {
    if (!interests.trim() || !user) { setSuggested([]); return }
    const timeout = window.setTimeout(() => api<{ suggested_tracks: Track[] }>(`/api/onboarding/suggest?interests=${encodeURIComponent(interests)}`).then(r => setSuggested(r.suggested_tracks)).catch(() => {}), 250)
    return () => window.clearTimeout(timeout)
  }, [interests, user?.id])
  useEffect(() => {
    if (view !== 'case' || !caseBundle || caseBundle.status !== 'pending') return
    const timer = window.setInterval(() => api<CaseBundle>(`/api/cases/${caseBundle.case_id}`).then(setCaseBundle).catch(err => setError(err instanceof Error ? err.message : 'Could not refresh assessment')), 2000)
    return () => window.clearInterval(timer)
  }, [view, caseBundle?.case_id, caseBundle?.status])
  useEffect(() => {
    if (view !== 'case' || !caseBundle || caseBundle.status === 'pending' || reviewRequested === caseBundle.case_id) return
    setReviewRequested(caseBundle.case_id)
    api<ReviewPreview>(`/api/cases/${caseBundle.case_id}/review-preview`).then(setReviewPreview).catch(err => setError(err instanceof Error ? err.message : 'Could not preview review inputs'))
    api(`/api/cases/${caseBundle.case_id}/review`, 'POST').then(() => api<ReviewState>(`/api/cases/${caseBundle.case_id}/review`)).then(setReviewState).catch(err => setError(err instanceof Error ? err.message : 'Could not start review'))
  }, [view, caseBundle?.case_id, caseBundle?.status, reviewRequested])
  useEffect(() => {
    if (view !== 'case' || !caseBundle || reviewState?.status !== 'pending') return
    const timer = window.setInterval(() => api<ReviewState>(`/api/cases/${caseBundle.case_id}/review`).then(setReviewState).catch(err => setError(err instanceof Error ? err.message : 'Could not refresh review')), 2000)
    return () => window.clearInterval(timer)
  }, [view, caseBundle?.case_id, reviewState?.status])

  const run = async (action: () => Promise<void>) => { setError(''); setBusy(true); try { await action() } catch (err) { setError(err instanceof Error ? err.message : 'Something went wrong') } finally { setBusy(false) } }
  const auth = (event: React.FormEvent) => { event.preventDefault(); run(async () => { const next = await api<User>(`/api/auth/${mode}`, 'POST', { email, password }); sync(next); setPassword('') }) }
  const saveName = () => run(async () => { await api('/api/onboarding/name', 'PATCH', { first_name: first, last_name: last }); if (links.linkedin_url) await api('/api/profile/links', 'PATCH', links); await refresh(); setStep(1) })
  const saveResume = () => run(async () => { if (resume) { const data = new FormData(); data.append('file', resume); await api('/api/onboarding/resume', 'POST', data); await refresh() } else if (!user?.profile.resume_name) throw new Error('Choose a PDF, DOCX, or TXT résumé'); setStep(2) })
  const saveInterests = () => run(async () => { await api('/api/onboarding/interests', 'PATCH', { interests, target_tracks: tracks }); await refresh(); setStep(3) })
  const saveSkills = () => run(async () => { await api('/api/onboarding/skills', 'PATCH', { skills: Object.fromEntries(tracks.map(t => [t, skills[t] || {}])) }); await api('/api/onboarding/complete', 'POST'); await refresh() })
  const saveLinks = () => run(async () => { await api('/api/profile/links', 'PATCH', links); await refresh(); setView('edit') })
  const importProjects = () => run(async () => { const result = await api<{ projects: Project[]; errors: string[] }>('/api/profile/import', 'POST'); setProjects(result.projects); setImportErrors(result.errors); await refresh(); setView('edit') })
  const saveProjects = () => run(async () => { await api('/api/profile/projects', 'PATCH', { selected_ids: projects.filter(p => p.selected).map(p => p.id), contributions: Object.fromEntries(projects.map(p => [p.id, p.contribution || ''])) }); await refresh(); setView('edit') })
  const addResumeProject = () => run(async () => { await api('/api/profile/resume-project', 'POST', { title: resumeProjectTitle, summary: resumeProjectSummary }); setResumeProjectTitle(''); setResumeProjectSummary(''); await refresh(); setView('edit') })
  const showMatches = () => run(async () => { const result = await api<{ jobs: Job[]; feed: FeedStatus; total_available: number }>(`/api/jobs/matches?q=${encodeURIComponent(jobQuery)}`); setJobs(result.jobs); setFeedStatus(result.feed); setTotalAvailable(result.total_available); window.history.replaceState({}, '', window.location.pathname); setView('matches'); const saved = await api<{ jobs: SavedJob[] }>('/api/saved-jobs'); setSavedJobs(saved.jobs) })
  useEffect(() => {
    if (view !== 'matches') return
    const update = () => api<{ jobs: Job[]; feed: FeedStatus; total_available: number }>(`/api/jobs/matches?q=${encodeURIComponent(jobQuery)}`).then(result => { setJobs(result.jobs); setFeedStatus(result.feed); setTotalAvailable(result.total_available) }).catch(() => {})
    const debounce = window.setTimeout(update, 250)
    const timer = window.setInterval(update, 30000)
    return () => { window.clearTimeout(debounce); window.clearInterval(timer) }
  }, [view, jobQuery])
  const openCase = async (caseId: string, existing = false) => { setReviewState(null); setReviewPreview(null); setReviewRequested(''); const bundle = await api<CaseBundle>(`/api/cases/${encodeURIComponent(caseId)}`); setCaseBundle(bundle); window.history.replaceState({}, '', `?case=${encodeURIComponent(caseId)}`); setView('case'); if (existing) { api<ReviewPreview>(`/api/cases/${encodeURIComponent(caseId)}/review-preview`).then(setReviewPreview).catch(() => {}); const savedReview = await api<ReviewState>(`/api/cases/${encodeURIComponent(caseId)}/review`); setReviewState(savedReview); if (savedReview.status !== 'not_started') setReviewRequested(caseId) } }
  const assessJob = (job: Job) => run(async () => { const started = await api<{ case_id: string }>('/api/cases', 'POST', { job_id: job.job_id }); await openCase(started.case_id) })
  const analyzeDescription = async (draft: { description: string; title: string; company: string; track: string }) => { const saved = await api<{ job: Job }>('/api/jobs/pasted', 'POST', draft); const started = await api<{ case_id: string }>('/api/cases', 'POST', { job_id: saved.job.job_id }); await openCase(started.case_id) }
  const uploadDashboardResume = async (file: File) => { const data = new FormData(); data.append('file', file); await api('/api/onboarding/resume', 'POST', data); await refresh() }
  const showSaved = () => run(async () => { const [history, bookmarks] = await Promise.all([api<{ cases: CaseItem[] }>('/api/cases'), api<{ jobs: SavedJob[] }>('/api/saved-jobs')]); setCaseHistory(history.cases); setSavedJobs(bookmarks.jobs); window.history.replaceState({}, '', window.location.pathname); setView('saved') })
  const toggleSavedJob = (job: Job) => run(async () => { const exists = savedJobs.some(item => item.job_id === job.job_id); await api(`/api/saved-jobs/${encodeURIComponent(job.job_id)}`, exists ? 'DELETE' : 'PUT'); setSavedJobs((await api<{ jobs: SavedJob[] }>('/api/saved-jobs')).jobs) })
  const removeSavedJob = (jobId: string) => run(async () => { await api(`/api/saved-jobs/${encodeURIComponent(jobId)}`, 'DELETE'); setSavedJobs((await api<{ jobs: SavedJob[] }>('/api/saved-jobs')).jobs) })
  const retryDepth = () => run(async () => { if (!caseBundle) return; await api(`/api/cases/${encodeURIComponent(caseBundle.case_id)}/retry-depth`, 'POST'); setReviewState(null); setReviewPreview(null); setReviewRequested(''); setCaseBundle(await api<CaseBundle>(`/api/cases/${encodeURIComponent(caseBundle.case_id)}`)) })
  const logout = () => run(async () => { await api('/api/auth/logout', 'POST'); setUser(null); setMode('login'); setView('onboarding'); setStep(0) })
  const toggleTrack = (track: Track) => setTracks(current => current.includes(track) ? current.filter(t => t !== track) : [...current, track])
  const setSkill = (track: Track, name: string, level: number | null) => setSkills(current => { const next = { ...(current[track] || {}) }; if (level === null) delete next[name]; else next[name] = level; return { ...current, [track]: next } })
  const addSkill = (track: Track) => { const name = (customSkill[track] || '').trim(); if (name) { setSkill(track, name, 3); setCustomSkill(c => ({ ...c, [track]: '' })) } }
  const searchLinkedIn = () => window.open(`https://www.linkedin.com/search/results/people/?keywords=${encodeURIComponent(`${first} ${last}`.trim())}`, '_blank', 'noopener,noreferrer')

  if (loading) return <div className="loading">Opening Hanzel<span className="dots">...</span></div>
  return <div className="app-shell hanzel-app"><header className="topbar hanzel-topbar"><button className="brand" onClick={() => { window.history.replaceState({}, '', window.location.pathname); setView(user?.profile.completed ? 'dashboard' : 'onboarding') }}><span className="brand-mark">✳</span> hanzel<span className="brand-dot">.</span></button><div className="top-right">{user?.profile.completed ? <><button className="hanzel-nav-link" onClick={() => { window.history.replaceState({}, '', window.location.pathname); setView('dashboard'); window.setTimeout(() => document.getElementById('how-it-works')?.scrollIntoView({ behavior: 'smooth' }), 20) }}>How it works</button><button className="hanzel-nav-link" onClick={() => { if (caseBundle) void openCase(caseBundle.case_id, true); else void showSaved() }}>Your analysis</button><button className="hanzel-nav-link" onClick={showMatches}>Find jobs</button><button className="hanzel-nav-link" onClick={showSaved}>Saved checks</button><button className="hanzel-nav-link" onClick={() => setView('edit')}>Profile</button><button className="text-button" onClick={logout}>Log out</button></> : user ? <button className="text-button" onClick={logout}>Log out</button> : <span className="top-tag">know where you stand</span>}</div></header>
    <main>
    {!user ? <div className="auth-layout"><section className="hero-panel"><div className="tiny-label"><span className="pulse" /> A BETTER START</div><h1>Know where you stand<br /><em>before you apply.</em></h1><p>Build your profile once. Hanzel checks your résumé and project evidence against real internship requirements.</p><div className="orbit-art" aria-hidden="true"><div className="ring ring-one" /><div className="ring ring-two" /><div className="planet planet-one">✦</div><div className="planet planet-two">★</div><div className="planet planet-three">●</div><div className="orbit-center">you<br /><span>↗</span></div></div><div className="hero-foot">HONEST FIT FEEDBACK AHEAD <span>↗</span></div></section><section className="auth-card"><div className="guide"><div className="guide-face">✳</div><span>hey, future you!</span></div><div className="eyebrow">{mode === 'signup' ? 'LET’S GET ACQUAINTED' : 'WELCOME BACK'}</div><h2>{mode === 'signup' ? 'Create your account' : 'Pick up where you left off'}</h2><p className="muted">{mode === 'signup' ? 'Add your résumé and the paths you want to explore.' : 'Your progress is right where you left it.'}</p><form onSubmit={auth}><label>Email address<input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="you@example.com" required /></label><label>Password<input type="password" minLength={8} value={password} onChange={e => setPassword(e.target.value)} placeholder="At least 8 characters" required /></label>{error && <div className="error" role="alert">{error}</div>}<button className="primary full" disabled={busy}>{busy ? 'One sec...' : mode === 'signup' ? 'Create account →' : 'Log in →'}</button></form><p className="switch">{mode === 'signup' ? 'Already have an account?' : 'New around here?'} <button onClick={() => { setError(''); setMode(mode === 'signup' ? 'login' : 'signup') }}>{mode === 'signup' ? 'Log in' : 'Sign up'}</button></p></section></div> :
    view === 'onboarding' ? <div className="onboard-layout"><aside className="onboard-side"><div className="tiny-label"><span className="pulse" /> WELCOME TO HANZEL</div><h1>Let’s make this<br /><em>about you.</em></h1><p>Four steps to a profile Hanzel can compare with real roles.</p><div className="step-list">{steps.map((name, index) => <button key={name} className={`step-item ${step === index ? 'active' : ''} ${index < step ? 'done' : ''}`} onClick={() => index < step && setStep(index)}><span className="step-number">{index < step ? '✓' : `0${index + 1}`}</span><span>{name}</span><span className="step-line" /></button>)}</div><div className="side-note">✳ <span>Your details are saved as you go. Take your time.</span></div></aside><section className="step-card" key={step}><div className="step-top"><span>STEP 0{step + 1} / 04</span><div className="progress"><i style={{ width: `${(step + 1) * 25}%` }} /></div></div><div className="guide"><div className="guide-face">✳</div><span>{['nice to meet you!', 'show me your story', 'follow your curiosity', 'the details matter'][step]}</span></div>
      {step === 0 && <><div className="eyebrow">FIRST THINGS FIRST</div><h2>What should we call you?</h2><p className="muted">Your name makes this space yours—and helps you find your LinkedIn profile.</p><div className="two-col"><label>First name<input value={first} onChange={e => setFirst(e.target.value)} placeholder="Your first name" /></label><label>Last name<input value={last} onChange={e => setLast(e.target.value)} placeholder="Your last name" /></label></div><div className="soft-panel"><div><strong>Find your LinkedIn</strong><p>We’ll open a people search. Confirm the right profile, then paste its link here or add it later.</p></div><button className="secondary small" onClick={searchLinkedIn} disabled={!first.trim() || !last.trim()}>Search ↗</button></div><label className="optional">LinkedIn profile URL <span>OPTIONAL</span><input value={links.linkedin_url} onChange={e => setLinks({ ...links, linkedin_url: e.target.value })} placeholder="https://www.linkedin.com/in/..." /></label><button className="primary" onClick={saveName} disabled={busy || !first.trim() || !last.trim()}>That’s me →</button></>}
      {step === 1 && <><div className="eyebrow">YOUR STORY SO FAR</div><h2>Let’s meet your resume.</h2><p className="muted">PDF, DOCX or TXT works. We’ll read the text to compare your experience with roles.</p><label className="upload-zone"><span className="upload-icon">↥</span><strong>{resume?.name || user.profile.resume_name || 'Choose a resume'}</strong><small>PDF, DOCX or TXT · up to 10 MB</small><input type="file" accept=".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain" onChange={e => setResume(e.target.files?.[0] || null)} /></label><div className="helper">✦ Your resume stays in your local demo profile.</div><div className="actions"><button className="secondary" onClick={() => setStep(0)}>← Back</button><button className="primary" onClick={saveResume} disabled={busy || (!resume && !user.profile.resume_name)}>Continue →</button></div></>}
      {step === 2 && <><div className="eyebrow">THE FUN PART</div><h2>What pulls you in?</h2><p className="muted">Tell us what you like building, exploring, or working on. Pick every path that interests you.</p><label>Your interests<textarea rows={4} value={interests} onChange={e => setInterests(e.target.value)} placeholder="e.g. FPGA and chip design, embedded systems, PCB design..." /></label><div className="section-label">{suggested.length ? 'SUGGESTED FOR YOU ✦' : 'CHOOSE YOUR PATHS'}</div><div className="track-grid">{(['HW', 'CS', 'PM'] as Track[]).map(track => <button key={track} className={`track-card ${tracks.includes(track) ? 'selected' : ''}`} onClick={() => toggleTrack(track)}><span className="track-symbol">{track === 'HW' ? '⌁' : track === 'CS' ? '</>' : '◈'}</span><strong>{labels[track]}</strong><small>{descriptions[track]}</small>{suggested.includes(track) && <span className="suggestion">SUGGESTED</span>}<span className="check">{tracks.includes(track) ? '✓' : '+'}</span></button>)}</div>{!suggested.length && interests.trim() && <p className="hint">No obvious match yet—choose the paths that feel right to you.</p>}<div className="actions"><button className="secondary" onClick={() => setStep(1)}>← Back</button><button className="primary" onClick={saveInterests} disabled={busy || !interests.trim() || !tracks.length}>Continue →</button></div></>}
      {step === 3 && <><div className="eyebrow">LAST LITTLE PIECE</div><h2>What’s in your toolkit?</h2><p className="muted">Pick what you know, then rate how comfortable you feel from 1 (learning) to 5 (confident). You can always edit this later.</p>{tracks.map(track => <div className="skill-group" key={track}><div className="skill-heading"><span className="track-symbol">{track === 'HW' ? '⌁' : track === 'CS' ? '</>' : '◈'}</span><h3>{labels[track]}</h3></div><div className="skill-chips">{Array.from(new Set([...(options?.skill_options[track] || []), ...Object.keys(skills[track] || {})])).map(name => <button key={name} className={`chip ${skills[track]?.[name] ? 'picked' : ''}`} onClick={() => setSkill(track, name, skills[track]?.[name] ? null : 3)}>{skills[track]?.[name] ? '✓ ' : '+ '}{name}</button>)}</div>{Object.entries(skills[track] || {}).map(([name, level]) => <div className="rating-row" key={name}><span>{name}</span><div className="ratings" aria-label={`${name} comfort level`}>{[1, 2, 3, 4, 5].map(n => <button key={n} aria-label={`${name}: ${n} of 5`} className={n <= level ? 'filled' : ''} onClick={() => setSkill(track, name, n)}>{n}</button>)}</div></div>)}<div className="add-skill"><input value={customSkill[track] || ''} onChange={e => setCustomSkill({ ...customSkill, [track]: e.target.value })} onKeyDown={e => { if (e.key === 'Enter') addSkill(track) }} placeholder="Add another skill or tool" /><button onClick={() => addSkill(track)}>Add +</button></div></div>)}<div className="actions"><button className="secondary" onClick={() => setStep(2)}>← Back</button><button className="primary" onClick={saveSkills} disabled={busy || tracks.some(t => !Object.keys(skills[t] || {}).length)}>Finish my profile →</button></div></>}
      {error && <div className="error" role="alert">{error}</div>}</section></div> :
    <div className="workspace hanzel-workspace">{error && view !== 'case' && <div className="error" role="alert">{error}</div>}
      {view === 'dashboard' && <HanzelHome name={user.profile.first_name} resumeName={user.profile.resume_name} hasProjects={user.profile.projects.some(p => p.source === 'github' || p.selected)} onResume={uploadDashboardResume} onAnalyze={analyzeDescription} onFindJobs={showMatches} onEditProfile={() => setView('edit')} />}
      {view === 'edit' && <div className="hanzel-subheading"><span className="hanzel-kicker">YOUR PROFILE</span><h1>Show the work behind your résumé.</h1><p>Your links and selected projects power the full review.</p></div>}
      {view === 'edit' && <div className="edit-grid"><section className="panel"><span className="eyebrow">PROFILE LINKS</span><h2>Show the work behind the work.</h2><p className="muted">Your links are optional. Import public context and choose what belongs in your profile.</p><label>LinkedIn profile<input value={links.linkedin_url} onChange={e => setLinks({ ...links, linkedin_url: e.target.value })} placeholder="https://www.linkedin.com/in/..." /></label><button className="link-button search-link" onClick={searchLinkedIn}>Find my profile ↗</button><label>GitHub profile or repository<input value={links.github_url} onChange={e => setLinks({ ...links, github_url: e.target.value })} placeholder="https://github.com/you" /></label><label>Personal website<input value={links.website_url} onChange={e => setLinks({ ...links, website_url: e.target.value })} placeholder="https://your-site.com" /></label><div className="actions"><button className="primary" onClick={saveLinks} disabled={busy}>Save links →</button><button className="secondary" onClick={importProjects} disabled={busy || (!user.profile.github_url && !user.profile.website_url)}>Import public context ↗</button></div><p className="hint">Save links before importing. We only read public pages you provide.</p>{importErrors.map((item, i) => <div className="error" key={i}>{item}</div>)}</section><section className="panel"><span className="eyebrow">YOUR PROJECTS</span><h2>Pick what represents you.</h2><p className="muted">Every imported GitHub repository is assessed when you choose Interested. Select website or résumé projects to include them too; selected GitHub projects are highlighted in quick matches.</p><div className="resume-project-form"><h3>Add a project from your resume</h3><label>Project name<input value={resumeProjectTitle} onChange={e => setResumeProjectTitle(e.target.value)} placeholder="Project name" /></label><label>What did you build?<textarea rows={3} value={resumeProjectSummary} onChange={e => setResumeProjectSummary(e.target.value)} placeholder="Describe your contribution and any results" /></label><button className="secondary" onClick={addResumeProject} disabled={busy || !resumeProjectTitle.trim() || !resumeProjectSummary.trim()}>Add project</button></div>{projects.length ? projects.map((project, index) => <label className="project-item" key={project.id}><input type="checkbox" checked={project.selected} onChange={e => setProjects(items => items.map((p, i) => i === index ? { ...p, selected: e.target.checked } : p))} /><span><strong>{project.title}</strong><small>{project.source.toUpperCase()} · {project.summary.slice(0, 180)}</small><small>{project.source === 'github' ? 'Included in full reviews; select to highlight in quick matches.' : 'Select to include in full reviews.'}</small><textarea aria-label={`Your contribution to ${project.title}`} rows={2} value={project.contribution || ""} onChange={e => setProjects(items => items.map((p, i) => i === index ? { ...p, contribution: e.target.value } : p))} placeholder="What did you personally build or decide?" />{project.url && <a href={project.url} target="_blank" rel="noreferrer" onClick={e => e.stopPropagation()}>View source ↗</a>}</span></label>) : <div className="empty-project">✳<p>Add a GitHub or website link, then import your public work.</p></div>}{projects.length > 0 && <button className="primary" onClick={saveProjects} disabled={busy}>Save selected projects →</button>}<div className="divider" /><button className="link-button" onClick={() => { setStep(0); setView('onboarding') }}>Revisit onboarding details →</button></section></div>}
      {view === 'paste' && <JobDescriptionPage onSaved={showMatches} />}
      {view === 'matches' && <HanzelJobs jobs={jobs} total={totalAvailable} query={jobQuery} onQuery={setJobQuery} savedIds={new Set(savedJobs.map(item => item.job_id))} onToggleSave={toggleSavedJob} onAssess={assessJob} onPaste={() => setView('dashboard')} onDescriptionSaved={async () => { const result = await api<{ jobs: Job[]; feed: FeedStatus; total_available: number }>(`/api/jobs/matches?q=${encodeURIComponent(jobQuery)}`); setJobs(result.jobs); setFeedStatus(result.feed); setTotalAvailable(result.total_available) }} hasProjects={user.profile.projects.some(p => p.source === 'github' || p.selected)} busy={busy} feedError={feedStatus?.error} />}
      {view === 'saved' && <HanzelSaved cases={caseHistory} jobs={savedJobs} onOpenCase={id => void openCase(id, true)} onRemoveJob={removeSavedJob} onFindJobs={showMatches} />}
      {view === 'case' && caseBundle && <div className="matches hanzel-report"><div className="matches-intro"><span className="eyebrow">YOUR FIT REPORT · {caseBundle.job.company.toUpperCase()}</span><h2>{caseBundle.job.title}</h2>{caseBundle.job.source_url && <p><a className="source-link" href={caseBundle.job.source_url} target="_blank" rel="noreferrer">View original posting ↗</a></p>}{caseBundle.job.research_note && <p className="hint">{caseBundle.job.research_note}</p>}{caseBundle.job.requirements_note && <p className="hint">{caseBundle.job.requirements_note}</p>}<p>{caseBundle.status === 'pending' ? 'Project assessment is running. This page refreshes automatically.' : caseBundle.status === 'partial' ? 'Some project assessments could not finish.' : 'Project evidence is ready.'} This is not a hiring verdict.</p></div>{caseBundle.project_assessments.some(assessment => assessment.status === 'failed') && <div className="hanzel-retry"><p>Some project checks failed. Retry them after the GitHub fix or model quota becomes available. This will run the project agents again, then refresh the fit report.</p><button className="hanzel-outline-button" onClick={retryDepth} disabled={busy}>{busy ? 'Starting retry…' : 'Retry failed checks and fit review (uses model credits)'}</button></div>}<ReviewPanel review={reviewState} preview={reviewPreview} />{caseBundle.project_assessments.map(assessment => <DepthAssessmentPanel key={assessment.project.id} assessment={assessment} />)}<JobPreparationPanel preparation={caseBundle.preparation} />{error && <div className="error" role="alert">{error}</div>}<button className="secondary" onClick={showMatches}>← Back to roles</button></div>}
    </div>}
    </main><footer><span>✳ hanzel.</span><span>Know where you stand before you apply.</span></footer></div>
}

createRoot(document.getElementById('root')!).render(<App />)

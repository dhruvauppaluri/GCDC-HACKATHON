type ReviewPoint = { text: string; evidence_ids: string[]; kind: string }
type JudgeRequirement = { id: string; text: string; kind: string; status: string; evidence_ids: string[]; coverage: number; alternatives?: string[] }
type JudgeFinding = { text: string; requirement_id: string; evidence_ids: string[] }
type JudgeAgent = { status: string; recommendation?: string; reasoning?: string; strengths?: JudgeFinding[]; concerns?: JudgeFinding[]; eligibility_note?: string; error?: string }
export type ReviewState = { status: string; error: string | null; result: { lawyer_execution?: string; lawyer_errors?: Record<string, string>; categories: Record<string, { pluses: ReviewPoint[]; minuses: ReviewPoint[] }>; judge: { verdict: string; match_score: number | null; eligibility: string; confidence: string; note: string; requirements: JudgeRequirement[]; score_breakdown: { requirement_coverage: number; cited_support_quality: number | null; method?: string } | null; agent?: JudgeAgent } } | null }
export type ReviewPreview = { paralegal: { source: string; evidence: { signal: string; quote: string }[] } | null; synthetic_comparisons: { application_id: string; shared_claim_signals: string[]; example_project: string }[]; requirements: { text: string; kind: string }[] }

const statusLabels: Record<string, string> = { 'inspected artifact': 'Shown in project', 'candidate claim': 'Reported by candidate', not_shown: 'Not shown in evidence' }
const verdictLabels: Record<string, string> = { strong_documented_match: 'Strong match in available evidence', promising_documented_match: 'Promising match in available evidence', partial_documented_match: 'Partial match in available evidence', limited_documented_match: 'Limited match in available evidence' }
const cleanAgentText = (value: string) => value
  .replace(/\b(?:depth:[0-9a-f-]+:E\d+|profile:(?:skill:\d+|project:\d+|resume)|paralegal:\d+|E\d+)\b/gi, '')
  .replace(/\b(?:per|at|see)\s+(?=[,.;]|$)/gi, '')
  .replace(/\s+([,.;])/g, '$1')
  .replace(/(?:,\s*){2,}/g, ', ')
  .replace(/\s{2,}/g, ' ')
  .trim()

export default function ReviewPanel({ review, preview }: { review: ReviewState | null; preview: ReviewPreview | null }) {
  const result = review?.result
  const argumentsBySide = result ? {
    advocate: Object.values(result.categories).flatMap(category => category.pluses),
    skeptic: Object.values(result.categories).flatMap(category => category.minuses),
  } : null
  const agent = result?.judge.agent
  return <section className="panel depth-panel review-panel">
    <span className="eyebrow">ROLE REVIEW</span><h2>How well does your evidence match?</h2>
    {review?.status === 'pending' && <p className="hint">The two Lawyers are reviewing the same evidence, then the Judge will weigh their arguments.</p>}
    {review?.status === 'failed' && <div className="error" role="alert">Review could not finish: {review.error}</div>}
    {result && <>
      {result.lawyer_execution && ['partial_model_failure', 'model_unavailable'].includes(result.lawyer_execution) && <div className="error" role="alert">{result.lawyer_execution === 'model_unavailable' ? 'Both Lawyers' : 'One Lawyer'} could not complete. The score below uses documented requirement coverage.</div>}
      <div className="trial-verdict"><strong>{result.judge.match_score === null ? 'Match score unavailable' : `${result.judge.match_score}/100 documented match`}</strong><span>{verdictLabels[result.judge.verdict] || result.judge.verdict.replaceAll('_', ' ')} · {result.judge.confidence} confidence</span><p>A measure of qualifications shown in your evidence, not a hiring prediction.</p></div>
      {agent?.status === 'complete' && <div className="review-category judge-summary"><h3>Judge’s assessment</h3>
        <div className="review-columns"><div><strong>Strengths</strong>{agent.strengths?.length ? agent.strengths.slice(0, 3).map((item, index) => <p key={index}>{cleanAgentText(item.text)}</p>) : <p className="muted">No clear strengths identified.</p>}</div><div><strong>Gaps to check</strong>{agent.concerns?.length ? agent.concerns.slice(0, 3).map((item, index) => <p key={index}>{cleanAgentText(item.text)}</p>) : <p className="muted">No specific gaps identified.</p>}</div></div>
        <p className="hint">Eligibility: {result.judge.eligibility === 'unknown' ? 'Not yet verified against the posting.' : agent.eligibility_note || result.judge.eligibility.replaceAll('_', ' ')}</p>
        {agent.reasoning && <details className="review-details"><summary>Read the Judge’s full reasoning</summary><p>{cleanAgentText(agent.reasoning)}</p></details>}
      </div>}
      {agent && agent.status !== 'complete' && <p className="hint">Judge assessment unavailable. The documented match score is still based on the job requirements and cited evidence.</p>}
      {result.judge.requirements.length > 0 && <div className="review-category"><h3>Job requirements</h3><div className="requirement-list">{result.judge.requirements.map(item => <div className="requirement-row" key={item.id}><div className="requirement-meta"><span>{item.kind === 'required' ? 'Required' : item.kind === 'preferred' ? 'Preferred' : 'Eligibility'}</span><span className={`requirement-status ${item.coverage === 1 ? 'shown' : item.coverage > 0 ? 'claimed' : 'missing'}`}>{statusLabels[item.status] || item.status.replaceAll('_', ' ')}</span></div><p>{item.text}</p>{item.alternatives && item.alternatives.length > 1 && <small>Any one of: {item.alternatives.join(', ')}</small>}</div>)}</div></div>}
      {argumentsBySide && <details className="review-details review-debate"><summary>See both Lawyers’ arguments ({argumentsBySide.advocate.length} strengths, {argumentsBySide.skeptic.length} concerns)</summary><div className="review-columns"><div><strong>Advocate</strong>{argumentsBySide.advocate.length ? argumentsBySide.advocate.map((point, index) => <p key={index}>{cleanAgentText(point.text)}</p>) : <p className="muted">No stated strengths.</p>}</div><div><strong>Skeptic</strong>{argumentsBySide.skeptic.length ? argumentsBySide.skeptic.map((point, index) => <p key={index}>{cleanAgentText(point.text)}</p>) : <p className="muted">No specific concerns.</p>}</div></div></details>}
      {preview?.paralegal?.evidence.length ? <details className="review-details"><summary>Résumé signals the Paralegal found</summary><div className="parsed-tags"><div>{Array.from(new Set(preview.paralegal.evidence.map(item => item.signal))).map(signal => <span className="tag" key={signal}>{signal}</span>)}</div></div></details> : null}
    </>}
  </section>
}

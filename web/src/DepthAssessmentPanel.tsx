export type DepthAssessment = {
  project: { id: string; title: string }
  status: string
  error: string | null
  result: {
    depth_score: number | null
    confidence: string
    project_summary: string
    dimensions: Record<string, { score: number; evidence_ids: string[] } | null>
    demonstrated_skills: { skill: string; evidence_ids: string[] }[]
  } | null
}

const criterionLabels: Record<string, string> = {
  verification: 'Verification',
  system_understanding: 'System understanding',
  engineering_tradeoffs: 'Engineering tradeoffs',
  scalability: 'Scalability',
  skill_depth: 'Skills used',
  scenario_applicability: 'Relevant scenarios',
}

export default function DepthAssessmentPanel({ assessment }: { assessment: DepthAssessment }) {
  const result = assessment.result
  return <section className="panel depth-panel">
    <div className="panel-head"><h2>{assessment.project.title}</h2><span className="badge">{assessment.status === 'complete' ? 'ASSESSED' : assessment.status.toUpperCase()}</span></div>
    {result ? <>
      <p className="depth-score"><strong>{result.depth_score === null ? 'Depth not scored' : `Project depth: ${result.depth_score}/10`}</strong><span> · {result.confidence} confidence</span></p>
      <div className="depth-criteria">{Object.entries(result.dimensions).map(([name, rating]) => <div key={name}><strong>{criterionLabels[name] || name.replaceAll('_', ' ')}</strong><span>{rating ? `${rating.score}/4` : 'Not enough evidence'}</span></div>)}</div>
      {result.demonstrated_skills.length > 0 && <div className="depth-concepts"><strong>Concepts shown</strong><div className="parsed-tags"><div>{result.demonstrated_skills.map(item => <span className="tag" key={item.skill}>{item.skill}</span>)}</div></div></div>}
      {result.project_summary && <details className="review-details"><summary>Project summary</summary><p>{result.project_summary}</p></details>}
    </> : <p className="muted">{assessment.error || 'Waiting for project assessment.'}</p>}
  </section>
}

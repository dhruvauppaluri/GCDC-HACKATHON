export type JobPreparation = {
  questions: { project_id: string; id: string; question: string }[]
  required_skills_with_project_evidence: string[]
  required_skills_without_project_evidence: string[]
}

export default function JobPreparationPanel({ preparation }: { preparation: JobPreparation }) {
  if (!preparation.questions.length) return null
  return <details className="panel depth-panel preparation-panel"><summary>Interview prep questions</summary><p className="muted">Use these to explain the decisions and tradeoffs in your projects.</p><ul>{preparation.questions.slice(0, 5).map(item => <li key={`${item.project_id}:${item.id}`}>{item.question}</li>)}</ul></details>
}

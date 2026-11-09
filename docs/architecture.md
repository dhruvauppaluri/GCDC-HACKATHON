# Architecture

Candidate profile (resume, interests, projects) feeds Research and Depth independently. Research emits structured job requirements. Depth emits project evidence and an interview-updated assessment. Judge/Jury consumes those outputs, applies eligibility separately from fit, and produces a career dashboard verdict. No component calls another upstream component.

Depth boundaries: ingestion resolves a public GitHub commit and extracts bounded source/doc/test text or parses candidate uploads; evaluator emits evidence-backed findings; interview answers append a new assessment revision. API and persistence are inside `backend/depth`. Shared schema changes require integration review.

The demo caps a public repository at 30 eligible text files and 180,000 source characters, each upload at 2 MB, uploads at five files, and evaluation evidence at 100 excerpts or 60,000 characters. It never runs repository code. Candidate-provided text is tagged as a claim; uploaded artifacts are inspectable but remain candidate-provided.

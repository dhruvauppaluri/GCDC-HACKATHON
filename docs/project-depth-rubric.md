# Project depth rubric

Five shared dimensions: conceptual understanding, implementation depth, systems integration, tradeoffs, and validation rigor. Score each 0–4 only with attributable evidence. `null` means there is too little evidence to assess; zero means inspectable evidence shows the relevant capability was absent or incorrect. Do not infer lack of competence from absent documentation.

| Score | Meaning |
|---|---|
| 0 | Evidence shows incorrect or nonfunctional handling of the dimension |
| 1 | Basic concept or isolated implementation |
| 2 | Working application with some relevant context |
| 3 | Integrated application with explained constraints and validation |
| 4 | Strong, independently supported understanding and decisions under realistic constraints |

Track examples are guidance, not separate scoring systems: hardware uses RTL, timing, verification, physical constraints; software uses architecture, reliability, security, tests; business uses assumptions, quantitative logic, competitive and outcome evidence; product uses discovery, prioritization, experiments, and outcome measurement. Project complexity, line counts, technology counts, and polished writing are not direct measures of depth.

Normalize the average of assessed dimensions to 0–10 using `mean(score) × 2.5`, rounded to one decimal. Preserve the denominator, evidence, and confidence. Candidate answers may change conceptual, systems, and tradeoff ratings; implementation or validation changes require independently inspectable implementation or validation evidence. Keep every revision. Mock results are labeled.

# Project depth rubric

The demo supports software, hardware, and product. Score each track criterion 0–4 only with attributable evidence. `null` means there is too little evidence to assess; zero means inspectable evidence shows the relevant capability was absent or incorrect. Do not infer lack of competence from absent documentation.

| Score | Meaning |
|---|---|
| 0 | Evidence shows incorrect or nonfunctional handling of the dimension |
| 1 | Basic concept or isolated implementation |
| 2 | Working application with some relevant context |
| 3 | Integrated application with explained constraints and validation |
| 4 | Strong, independently supported understanding and decisions under realistic constraints |

Software criteria: **scalability** (reasoning about load, bottlenecks, growth, and limits), **skill execution** (inspectable implementation rather than a technology count), and **scenario robustness** (how well the design handles conditions relevant to its intended purpose). A specialized project is assessed against its actual scope, not penalized for unrelated uses.

Hardware criteria: **verification** (simulation, tests, timing, physical evidence and their limits), **system understanding** (end-to-end interfaces and candidate contribution), and **engineering tradeoffs** (design choices, including power, performance, and area when relevant).

Product retains the provisional five dimensions of conceptual understanding, implementation, systems, tradeoffs, and validation until a PM-specific rubric is reviewed. Project complexity, line counts, technology counts, and polished writing are not direct measures of depth.

Normalize the average of assessed criteria to 0–10 using `mean(score) × 2.5`, rounded to one decimal. Preserve evidence and confidence; a score based on one criterion has low confidence, and confidence cannot rise above low until an artifact-backed criterion is assessed. Candidate answers can revise software scalability and scenario reasoning, hardware system understanding and tradeoffs, or product conceptual/systems/tradeoff ratings. Software skill execution, hardware verification, and product implementation/validation require inspectable artifact evidence. Keep every revision. Mock results are labeled. Job relevance is reported separately from project depth.

"""Track-specific, evidence-gated criteria for the depth prototype."""

RUBRICS = {
    "software": {
        "scalability": "Reasoning about load, growth, bottlenecks, and measured or explicitly unmeasured limits.",
        "skill_execution": "Inspectably implemented software skills, not a count of technologies named.",
        "scenario_robustness": "Execution across conditions relevant to the project's intended scope; specialized projects are not penalized for unrelated uses.",
    },
    "hardware": {
        "verification": "Simulation, testing, timing, or physical validation with its limits stated.",
        "system_understanding": "How components connect end to end and how the candidate explains their contribution.",
        "engineering_tradeoffs": "Explained design choices, including power, performance, and area when relevant.",
    },
    "product": {
        "conceptual": "Understanding of users, problem, and goals.",
        "implementation": "Inspectably executed product work, rather than a plan alone.",
        "systems": "How discovery, delivery, and measurement connect.",
        "tradeoffs": "Prioritization choices and alternatives.",
        "validation": "User or outcome evidence and its limits.",
    },
}

# Answers can show reasoning, but cannot establish that work was implemented or verified.
ANSWER_CRITERIA = {
    "software": {"scalability", "scenario_robustness"},
    "hardware": {"system_understanding", "engineering_tradeoffs"},
    "product": {"conceptual", "systems", "tradeoffs"},
}

ARTIFACT_CRITERIA = {
    "software": {"skill_execution"},
    "hardware": {"verification"},
    "product": {"implementation", "validation"},
}

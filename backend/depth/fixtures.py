"""Synthetic mock-only scenarios. These are not human-reviewed calibration labels."""

SCENARIOS = {
    "hardware": {
        "text": "SC-HACK-FIXTURE-hardware: I built a parameterized streaming buffer in SystemVerilog. The write and read controllers exchange full and empty signals with upstream and downstream modules. I ran a self-checking simulation for simultaneous read and write, but did not test on FPGA hardware.",
        "summary": "Synthetic streaming-buffer design with simulated control behavior.",
        "architecture": "Read and write controllers connect the buffer to upstream and downstream modules.",
        "skills": ["SystemVerilog", "simulation"],
        "answer": "I chose backpressure because downstream stalls must not drop data; an alternative is a larger buffer, but that only delays overflow.",
    },
    "software": {
        "text": "SC-HACK-FIXTURE-software: I built an API with a database-backed job queue. The API validates requests and a worker processes jobs. Integration tests cover retries and duplicate submissions; I have not load-tested production traffic.",
        "summary": "Synthetic API and worker with integration tests.",
        "architecture": "The API stores jobs; a worker processes them and reports results.",
        "skills": ["API design", "integration testing"],
        "answer": "I separated the worker to keep slow jobs from blocking API requests; under higher load I would add idempotency keys and monitor queue latency.",
    },
    "product": {
        "text": "SC-HACK-FIXTURE-product: I interviewed users, prioritized onboarding friction, and wrote an experiment plan. A prototype reduced task steps in usability sessions, but retention impact has not been measured.",
        "summary": "Synthetic onboarding discovery and prototype experiment.",
        "architecture": "User interviews informed prioritization, prototype design, and an experiment plan.",
        "skills": ["user research", "prioritization"],
        "answer": "I chose onboarding friction because interviews showed repeated drop-off; I would compare activation and retention before calling the change successful.",
    },
}


def fixture_for(track: str, evidence: list[dict]):
    scenario = SCENARIOS[track]
    return scenario if any(item["excerpt"].startswith(scenario["text"]) for item in evidence) else None

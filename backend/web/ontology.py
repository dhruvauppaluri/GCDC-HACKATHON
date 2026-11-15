"""Small, reviewable skill ontology shared by the matcher and the paralegal.

Each concept lists surface aliases (same skill, different words) and optional
``related`` concepts (transferable but not equivalent, for example Verilog for a
SystemVerilog requirement). It exists so semantically equivalent evidence is not
missed by exact-term matching, especially for PM work whose vocabulary varies.
It is a recall aid only: the verifier in ``matching.py`` still has to quote
evidence before any credit is given.
"""
import re

# concept id -> (aliases, related concept ids)
CONCEPTS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    # --- hardware
    "systemverilog": (("systemverilog", "system verilog", "sv testbench", "uvm"), ("verilog", "vhdl", "hdl")),
    "verilog": (("verilog", "verilog hdl"), ("systemverilog", "vhdl", "hdl")),
    "vhdl": (("vhdl",), ("verilog", "systemverilog", "hdl")),
    "hdl": (("hdl", "hardware description language", "rtl", "register transfer"), ("verilog", "systemverilog", "vhdl")),
    "fpga": (("fpga", "field programmable gate array", "field-programmable", "vivado", "quartus", "xilinx", "intel fpga", "de10", "cyclone", "artix"), ("hdl", "digital design")),
    "digital design": (("digital design", "digital logic", "logic design", "state machine", "fsm", "pipeline stage", "datapath", "rtl design"), ("hdl", "fpga")),
    "asic": (("asic", "physical design", "openroad", "sky130", "synthesis", "place and route", "tape-out", "tapeout"), ("digital design",)),
    "embedded systems": (("embedded", "microcontroller", "mcu", "firmware", "stm32", "arduino", "esp32", "rtos", "bare-metal", "bare metal"), ("c",)),
    "pcb design": (("pcb", "printed circuit board", "board layout", "altium", "kicad", "eagle", "gerber"), ("schematics", "electronics")),
    "schematics": (("schematic", "schematics", "circuit diagram"), ("pcb design", "electronics")),
    "electronics": (("electronics", "analog circuit", "circuit design", "op-amp", "op amp", "oscilloscope", "soldering", "breadboard"), ("pcb design", "schematics")),
    "simulation": (("simulation", "simulated", "spice", "ltspice", "modelsim", "verilator", "testbench", "waveform", "cocotb"), ("testing",)),
    "hardware verification": (("verification", "formal verification", "constrained random", "assertions", "sva", "scoreboard", "golden model", "reference model"), ("testing", "simulation")),
    "timing analysis": (("timing closure", "static timing", "setup slack", "clock domain", "sta "), ("fpga", "asic")),
    # --- software
    "python": (("python", "pytest", "numpy", "pandas", "fastapi", "flask", "django"), ()),
    "typescript": (("typescript", "tsx"), ("javascript",)),
    "javascript": (("javascript", "node.js", "nodejs", "ecmascript"), ("typescript",)),
    "react": (("react", "react.js", "reactjs", "next.js", "nextjs", "jsx"), ("javascript", "typescript", "frontend")),
    "frontend": (("frontend", "front-end", "front end", "ui development", "web ui", "css", "html"), ("react",)),
    "c": (("c programming", "ansi c", "c99", "c11", " in c ", "written in c"), ("c++", "embedded systems")),
    "c++": (("c++", "cpp", "c plus plus", "stl"), ("c",)),
    "java": (("java", "spring boot", "jvm"), ()),
    "sql": (("sql", "postgres", "postgresql", "mysql", "sqlite", "database queries", "relational database"), ("databases",)),
    "databases": (("database", "databases", "datastore", "nosql", "mongodb", "redis"), ("sql",)),
    "apis": (("api", "apis", "rest", "restful", "graphql", "endpoint", "endpoints", "web service", "microservice"), ()),
    "testing": (("testing", "unit test", "unit tests", "integration test", "integration tests", "pytest", "test suite", "regression test", "test coverage", "qa", "automated tests", "ci pipeline", "continuous integration"), ("hardware verification",)),
    "algorithms": (("algorithm", "algorithms", "data structure", "data structures", "dynamic programming", "graph traversal", "complexity analysis"), ()),
    "linux": (("linux", "unix", "bash", "shell scripting", "command line", "ubuntu", "posix"), ()),
    "distributed systems": (("distributed system", "distributed systems", "consensus", "replication", "sharding", "message queue", "kafka", "microservices", "fault tolerance"), ("cloud",)),
    "cloud": (("cloud", "aws", "gcp", "azure", "kubernetes", "docker", "terraform", "serverless", "deployed"), ("devops",)),
    "devops": (("devops", "ci/cd", "github actions", "deployment pipeline", "docker", "infrastructure as code"), ("cloud",)),
    "machine learning": (("machine learning", "ml model", "deep learning", "neural network", "scikit-learn", "pytorch", "tensorflow", "classifier"), ("data analysis",)),
    "version control": (("git", "github", "pull request", "code review", "version control"), ()),
    # --- product
    "user research": (("user research", "user interview", "user interviews", "customer interview", "customer interviews", "customer discovery", "usability test", "usability testing", "user testing", "surveys", "voice of customer", "ux research"), ("customer empathy",)),
    "customer empathy": (("customer empathy", "customer needs", "pain points", "user needs", "voice of the customer", "jobs to be done", "personas", "user stories"), ("user research",)),
    "prioritization": (("prioritization", "prioritisation", "prioritize", "prioritized", "rice score", "moscow", "impact vs effort", "trade-off", "tradeoffs", "backlog grooming", "ranked features", "cut scope"), ("roadmapping",)),
    "roadmapping": (("roadmap", "roadmapping", "product roadmap", "release plan", "milestones", "product planning", "quarterly planning"), ("prioritization", "product strategy")),
    "product strategy": (("product strategy", "go-to-market", "go to market", "gtm", "positioning", "competitive analysis", "market analysis", "business case", "vision", "market sizing"), ("roadmapping",)),
    "analytics": (("analytics", "data analysis", "dashboard", "dashboards", "funnel", "retention", "cohort", "mixpanel", "amplitude", "google analytics", "tableau", "looker", "kpi"), ("metrics", "sql")),
    "data analysis": (("data analysis", "analyzed data", "analysed data", "exploratory analysis", "statistical analysis", "excel", "pivot table"), ("analytics",)),
    "metrics": (("metrics", "kpi", "kpis", "okr", "okrs", "north star", "success metric", "success metrics", "conversion rate", "engagement", "nps", "growth of"), ("analytics", "experimentation")),
    "experimentation": (("experimentation", "a/b test", "a/b testing", "ab test", "split test", "hypothesis", "experiment", "experiments", "pilot", "mvp", "prototype test"), ("metrics",)),
    "stakeholder management": (("stakeholder", "stakeholders", "cross-functional", "cross functional", "aligned with", "coordinated", "partnered with", "collaborated with engineering", "collaborated with design", "managed expectations", "executive presentation"), ("technical communication", "leadership")),
    "technical communication": (("technical communication", "technical writing", "documentation", "wrote docs", "spec", "prd", "product requirements", "requirements document", "presented", "presentation", "wrote up", "design doc", "readme"), ("stakeholder management",)),
    "project management": (("project management", "scrum", "agile", "sprint", "kanban", "jira", "led a team", "managed a team", "timeline", "delivered on schedule", "project plan"), ("leadership",)),
    "leadership": (("leadership", "led", "president of", "founded", "captain", "team lead", "mentored", "organized"), ("project management", "stakeholder management")),
    "product sense": (("product sense", "product thinking", "shipped", "launched", "feature", "product launch", "user-facing", "built a product", "side project with users"), ("user research",)),
}

_TOKEN = re.compile(r"[a-z0-9+#/.]+")


def _norm(text: str) -> str:
    return " " + " ".join(text.casefold().split()) + " "


def _alias_hit(alias: str, padded: str) -> bool:
    alias = alias.casefold()
    if alias != alias.strip():  # explicit boundary markers such as " in c "
        return alias in padded
    return re.search(r"(?<![a-z0-9+#])" + re.escape(alias) + r"(?![a-z0-9+#])", padded) is not None


def concepts_in(text: str) -> set[str]:
    padded = _norm(text)
    return {concept for concept, (aliases, _) in CONCEPTS.items()
            if any(_alias_hit(alias, padded) for alias in aliases)}


def related_to(concept_ids: set[str]) -> set[str]:
    out: set[str] = set()
    for concept in concept_ids:
        out.update(CONCEPTS.get(concept, ((), ()))[1])
    return out - concept_ids


def equivalent_terms(term: str) -> tuple[str, ...]:
    """Aliases of every concept the term names (used by the legacy matcher)."""
    found = concepts_in(term)
    return tuple(dict.fromkeys(alias.strip() for concept in found for alias in CONCEPTS[concept][0]))


def vocabulary(track: str | None = None) -> list[str]:
    """Concept names the paralegal may normalize extracted skills to."""
    return sorted(CONCEPTS)

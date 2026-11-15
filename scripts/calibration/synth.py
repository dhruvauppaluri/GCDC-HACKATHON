"""Synthetic early-career résumés (graded by construction) and intern job descriptions.

Levels are *intended* quality, assigned by construction, not human labels. They
let us test monotonicity, keyword-stuffing resistance, negation handling and
paraphrase stability. They cannot establish that scores agree with recruiters.
"""
import random

LEVELS = {7: "cracked", 6: "strong", 5: "solid", 4: "average", 3: "weak", 2: "stuffed", 1: "learning_only", 0: "irrelevant"}

# skill -> (jd phrase, strong evidence variants, ok variants, generic skill-list token, planned variants)
SKILLS = {
    "HW": {
        "SystemVerilog": ("SystemVerilog or Verilog",
            ["Wrote a SystemVerilog UART transmitter and a self-checking testbench; 40 directed tests passed on Verilator and timing met at 50 MHz",
             "Implemented a pipelined 5-stage RISC-V core in Verilog, verified against a Python golden model across 10,000 random programs"],
            ["Built a Verilog traffic-light state machine for a digital design course lab",
             "Wrote SystemVerilog modules for an FIR filter in a class project"],
            "SystemVerilog", ["Learning Verilog this semester", "Hope to use SystemVerilog in future projects"]),
        "FPGA": ("FPGA development",
            ["Deployed a camera pipeline on a Cyclone V FPGA using Quartus, closing timing at 100 MHz and driving a VGA display",
             "Synthesized and programmed a Xilinx Artix-7 board with Vivado to run a 32-channel spike detector"],
            ["Programmed a DE10-Nano FPGA board to blink LEDs and read switches for a lab",
             "Used Vivado to synthesize a counter design in the digital logic course"],
            "FPGA", ["Planning to try FPGA boards", "No FPGA experience yet but interested"]),
        "hardware verification": ("simulation and verification",
            ["Built a scoreboard-based testbench with constrained-random stimulus and SVA assertions, reaching 95 percent functional coverage",
             "Created a golden-model comparison harness that caught three off-by-one pipeline bugs before tape-out"],
            ["Wrote a testbench with waveform checks for an adder in simulation",
             "Used ModelSim to simulate and debug a class project design"],
            "simulation", ["Hope to learn verification methodology", "Learning about testbenches"]),
        "embedded C": ("C or C++ for embedded systems",
            ["Wrote bare-metal C firmware for an STM32 motor controller with interrupt-driven ADC sampling and a PID loop that held speed within 2 percent",
             "Built an RTOS-based sensor logger in C on an ESP32 with SPI and I2C drivers"],
            ["Programmed an Arduino in C++ to read a temperature sensor and display it",
             "Wrote C code for a microcontroller course assignment on timers"],
            "C", ["Currently learning embedded C", "No embedded experience yet"]),
        "PCB design": ("PCB design tools such as Altium or KiCad",
            ["Designed a 4-layer PCB in KiCad with a buck converter and impedance-controlled USB; board fabricated and booted first try",
             "Laid out and assembled a sensor board in Altium for a robotics team, fixing two schematic errors found at bring-up"],
            ["Drew schematics and a simple 2-layer board in KiCad for a class project",
             "Made a breadboard-to-PCB conversion of a LED circuit in Eagle"],
            "PCB design", ["Interested in learning PCB layout", "Hope to learn Altium"]),
        "lab debugging": ("hands-on debugging with oscilloscopes and logic analyzers",
            ["Used an oscilloscope and logic analyzer to find a clock-glitch bug in an SPI link, cutting error rate from 3 percent to zero",
             "Debugged a power-supply ripple problem with a scope and added filtering, passing the team's validation"],
            ["Used an oscilloscope in the circuits lab to measure signals",
             "Soldered and tested a few small kits in a hardware club"],
            "electronics", ["Never used a logic analyzer", "Hope to get lab experience"]),
        "Python": ("Python scripting for test automation",
            ["Wrote Python scripts with pytest to automate regression runs of 200 simulation vectors and generate coverage reports",
             "Built a Python tool that parsed logic analyzer captures and flagged protocol violations"],
            ["Used Python to plot data from lab experiments", "Wrote small Python scripts for a course"],
            "Python", ["Learning Python", "No Python experience yet"]),
    },
    "CS": {
        "Python": ("Python",
            ["Built a FastAPI service in Python handling 500 requests per second in load tests, with pytest coverage above 90 percent",
             "Wrote a Python data pipeline that processed 2 million records nightly and cut runtime from 40 to 9 minutes"],
            ["Built a Flask app in Python for a class project", "Wrote Python scripts for homework and a small web scraper"],
            "Python", ["Learning Python", "Planning to learn Python"]),
        "SQL": ("SQL and relational databases",
            ["Designed a PostgreSQL schema with indexes and rewrote slow queries, reducing p95 latency from 800 ms to 90 ms",
             "Wrote complex SQL joins and window functions for an analytics dashboard used by 300 students"],
            ["Used SQLite and basic SQL queries in a database course project", "Created tables and queries in MySQL for a class assignment"],
            "SQL", ["Hope to learn SQL", "No database experience yet"]),
        "React": ("React or a modern frontend framework",
            ["Built a React and TypeScript dashboard with 20 components, deployed to production, and used by 150 users",
             "Developed a Next.js web app with server-side rendering and accessibility fixes that raised Lighthouse score to 98"],
            ["Made a small React to-do app following a tutorial", "Built a personal website with React for a web course"],
            "React", ["Learning React", "Interested in frontend but no experience"]),
        "algorithms": ("data structures and algorithms",
            ["Implemented Dijkstra, tries and a priority queue from scratch and used them to speed up a route planner 12x in benchmarks",
             "Solved 300 algorithm problems and won second place in a university programming contest"],
            ["Completed a data structures course with projects on hash tables and trees", "Implemented sorting algorithms for coursework"],
            "algorithms", ["Hope to study algorithms", "Have not taken algorithms yet"]),
        "testing": ("software testing",
            ["Added unit and integration tests with pytest and CI via GitHub Actions, catching 14 regressions before release",
             "Built a regression suite for an open source project that raised coverage from 40 to 85 percent"],
            ["Wrote unit tests for homework assignments", "Used JUnit for tests in a software engineering course"],
            "testing", ["Learning about testing", "No testing experience"]),
        "Git and collaboration": ("Git and collaborative development",
            ["Contributed 12 merged pull requests to an open source library and reviewed code from four contributors",
             "Led a team of five using Git branching, code review and sprints to ship a mobile app to 1,000 users"],
            ["Used Git and GitHub in a team class project", "Worked in a group of three with GitHub for a course"],
            "Git", ["Learning Git", "Never used Git in a team"]),
        "Linux": ("Linux command line",
            ["Administered a Linux home server with bash automation, cron backups and Docker containers running five services",
             "Wrote bash scripts and systemd units to deploy a research cluster job pipeline on Ubuntu"],
            ["Used the Linux command line in an operating systems course", "Set up Ubuntu on a laptop and used basic shell commands"],
            "Linux", ["Hope to learn Linux", "No Linux experience"]),
    },
    "PM": {
        "user research": ("user research",
            ["Ran 15 customer discovery interviews with campus club leaders, synthesized pain points into three personas, and used them to cut scope",
             "Conducted usability tests with 8 students on a prototype and found the onboarding drop-off that led to a redesign"],
            ["Interviewed a few student users for a class project and summarized feedback", "Sent a survey to 30 classmates about a campus app idea"],
            "user research", ["Hope to learn user research", "Interested in user interviews but no experience"]),
        "prioritization": ("prioritization and roadmapping",
            ["Built a RICE-scored backlog of 40 items for a student startup and cut the roadmap to a 6-week MVP that shipped on time",
             "Prioritized features with an impact-effort matrix, dropped 5 low-value requests, and presented the quarterly roadmap to advisors"],
            ["Made a simple feature list and ordered it for a class project", "Helped decide what to build first in a hackathon team"],
            "prioritization", ["Learning prioritization frameworks", "Planning to learn roadmapping"]),
        "analytics": ("analytics and metrics",
            ["Built a SQL and Tableau dashboard tracking activation and weekly retention; found a 20 percent funnel drop and fixed it",
             "Defined success metrics and analyzed cohort retention for a campus marketplace with 2,000 users"],
            ["Made charts in Excel from survey results for a class", "Looked at Google Analytics for a club website"],
            "analytics", ["Hope to learn analytics", "No analytics experience yet"]),
        "experimentation": ("experimentation or A/B testing",
            ["Ran an A/B test on a signup flow with 1,200 users; the variant lifted conversion 8 percent and we shipped it",
             "Designed and ran three onboarding experiments for a student app, documenting hypotheses and results"],
            ["Tried two versions of a flyer to see which got more signups", "Compared two prototype designs in a class assignment"],
            "experimentation", ["Interested in A/B testing", "Have not run experiments"]),
        "stakeholder communication": ("cross-functional collaboration and stakeholder communication",
            ["Coordinated engineers, a designer and two advisors on a launch, writing the PRD and running weekly syncs that kept the team aligned",
             "Presented product updates to executives and partnered with engineering to resolve scope conflicts, shipping on schedule"],
            ["Worked with a team of four on a class project and gave a presentation", "Gave status updates to a club advisor"],
            "stakeholder management", ["Learning to work with stakeholders", "No cross-functional experience"]),
        "technical communication": ("clear written and technical communication",
            ["Wrote a 6-page product requirements document and API usage guide adopted by two engineering teams",
             "Authored documentation and user stories for a campus app, reducing support questions by a third"],
            ["Wrote a product brief for a class assignment", "Wrote meeting notes and short specs for a club"],
            "technical communication", ["Hope to improve technical writing", "No writing samples yet"]),
        "SQL": ("SQL",
            ["Wrote SQL queries to segment 50,000 users and measure feature adoption for a capstone analytics project",
             "Built SQL reports that the team used weekly to decide what to prioritize"],
            ["Used basic SQL in a data course", "Wrote simple SELECT queries for class"],
            "SQL", ["Learning SQL", "Hope to learn SQL"]),
    },
}

EXTRAS = {
    "HW": ["Treasurer of the IEEE student chapter", "Teaching assistant for digital logic lab", "Rock climbing and chess club member"],
    "CS": ["Teaching assistant for introductory programming", "Hackathon participant, finalist at campus hackathon", "Volunteer tutor for high school students"],
    "PM": ["President of the entrepreneurship club", "Teaching assistant for microeconomics", "Barista at a campus cafe for two years"],
}
IRRELEVANT = ["Lifeguard at the city pool for two summers, certified in CPR", "Barista at a campus cafe; handled 200 customers per shift",
              "Member of the hiking club and intramural volleyball team", "Volunteer at an animal shelter on weekends"]
NAMES = ["Alex Rivera", "Priya Shah", "Jordan Lee", "Maya Chen", "Sam Okafor", "Leo Martins", "Noah Kim", "Riley Park", "Casey Ng", "Devon Hart"]
SCHOOLS = ["State University", "Tech Institute", "Lakeside College", "Northern University", "City Polytechnic"]
MAJORS = {"HW": ["Electrical Engineering", "Computer Engineering"], "CS": ["Computer Science", "Software Engineering"], "PM": ["Economics", "Information Science", "Business Analytics"]}

# intended share of JD skills at each evidence strength: (strong, ok, generic, planned)
LEVEL_MIX = {
    7: (1.0, 0.0, 0.0, 0.0), 6: (0.8, 0.2, 0.0, 0.0), 5: (0.35, 0.5, 0.15, 0.0), 4: (0.0, 0.45, 0.3, 0.0),
    3: (0.0, 0.1, 0.35, 0.0),
}


def _bullets(rng, items):
    return "\n".join("- " + item for item in items)


def make_resume(track: str, level: int, seed: int, jd_skills: list[str]) -> dict:
    """Return {text, level, artifacts}. ``jd_skills`` are the skills the target job asks for."""
    rng = random.Random(f"{track}-{level}-{seed}")
    skills = SKILLS[track]
    name = rng.choice(NAMES)
    major = rng.choice(MAJORS[track])
    head = [f"{name}", f"Education: B.S. {major}, {rng.choice(SCHOOLS)}, expected graduation May 2027. GPA 3.{rng.randint(2, 9)}"]
    body, listed, artifacts = [], [], []
    target = [s for s in jd_skills if s in skills]
    rng.shuffle(target)

    if level in LEVEL_MIX:
        strong, ok, generic, _ = LEVEL_MIX[level]
        n = len(target)
        k_strong, k_ok, k_gen = round(strong * n), round(ok * n), round(generic * n)
        for i, skill in enumerate(target):
            _, strong_v, ok_v, token, _ = skills[skill]
            if i < k_strong:
                text = rng.choice(strong_v)
                body.append(text)
                if level >= 6 and track != "PM":
                    artifacts.append(text)
            elif i < k_strong + k_ok:
                body.append(rng.choice(ok_v))
            elif i < k_strong + k_ok + k_gen:
                listed.append(token)
        body += rng.sample(EXTRAS[track], k=2 if level >= 5 else 1)
    elif level == 2:  # stuffed: every JD skill named, nothing done
        listed = [skills[s][3] for s in target] + [skills[s][3] for s in skills if s not in target]
        body += rng.sample(EXTRAS[track], k=1)
    elif level == 1:  # learning only: every JD skill planned or absent
        for skill in target:
            body.append(rng.choice(skills[skill][4]))
        body += rng.sample(EXTRAS[track], k=1)
    else:  # irrelevant
        body += rng.sample(IRRELEVANT, k=3)

    lines = head + ["Experience and projects:", _bullets(rng, body)]
    if listed:
        lines.append("Skills: " + ", ".join(dict.fromkeys(listed)))
    return {"text": "\n".join(lines), "level": level, "label": LEVELS[level], "seed": seed, "track": track,
            "artifacts": artifacts}


JD_TEMPLATES = {
    "HW": "{title} Intern\n\nAbout the role: Join our hardware team for a summer internship working on {area}.\n\n"
          "Responsibilities:\n- Support design and bring-up work on {area}\n- Document results for the team\n\n"
          "Minimum qualifications:\n{required}\n\nPreferred qualifications:\n{preferred}\n\n"
          "Eligibility: Currently pursuing a Bachelor's or Master's degree with graduation in 2027 or 2028. Must be authorized to work in the United States.\n",
    "CS": "{title} Intern\n\nAbout the role: Join our engineering team for a summer internship building {area}.\n\n"
          "Responsibilities:\n- Build and ship features on {area}\n- Participate in code review and sprint planning\n\n"
          "Minimum qualifications:\n{required}\n\nPreferred qualifications:\n{preferred}\n\n"
          "Eligibility: Currently pursuing a degree with graduation in 2027 or 2028. Must be authorized to work in the United States.\n",
    "PM": "{title} Intern\n\nAbout the role: Join our product team for a summer internship on {area}.\n\n"
          "Responsibilities:\n- Partner with engineering and design on {area}\n- Present findings to leadership\n\n"
          "Minimum qualifications:\n{required}\n\nPreferred qualifications:\n{preferred}\n\n"
          "Eligibility: Currently pursuing a degree with graduation in 2027 or 2028. Must be authorized to work in the United States.\n",
}

JD_SPECS = {
    "HW": [
        ("FPGA Design Engineer", "FPGA-based signal processing", ["SystemVerilog", "FPGA", "hardware verification"], ["Python", "lab debugging"]),
        ("Embedded Hardware Engineer", "embedded sensor boards", ["embedded C", "PCB design", "lab debugging"], ["Python", "hardware verification"]),
    ],
    "CS": [
        ("Software Engineer", "backend services", ["Python", "SQL", "algorithms"], ["testing", "Git and collaboration"]),
        ("Full Stack Engineer", "customer-facing web apps", ["React", "Python", "Git and collaboration"], ["SQL", "Linux"]),
    ],
    "PM": [
        ("Associate Product Manager", "a consumer app", ["user research", "prioritization", "analytics"], ["experimentation", "SQL"]),
        ("Technical Product Manager", "a developer platform", ["stakeholder communication", "technical communication", "analytics"], ["SQL", "user research"]),
    ],
}


def make_jd(track: str, index: int) -> dict:
    title, area, required, preferred = JD_SPECS[track][index]
    phrases = lambda names: "\n".join(f"- Experience with {SKILLS[track][n][0]}" for n in names)
    text = JD_TEMPLATES[track].format(title=title, area=area, required=phrases(required), preferred=phrases(preferred))
    return {"track": track, "title": title, "company": "Synthetic Labs", "description": text,
            "required": required, "preferred": preferred}

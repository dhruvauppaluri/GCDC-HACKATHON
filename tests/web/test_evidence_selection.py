from backend.web.evidence_selection import select_lawyer_evidence


def test_lawyer_evidence_keeps_each_project_anchor_and_bounds_extra_excerpts():
    bundle = {"job": {"title": "FPGA Intern"}, "project_assessments": [
        {"evaluation_id": "one", "result": {"summary_evidence_ids": ["A1"]}},
        {"evaluation_id": "two", "result": {"summary_evidence_ids": ["B1"]}},
    ]}
    requirements = [{"kind": "required", "text": "SystemVerilog FPGA verification"}]
    evidence = [{"id": "profile:resume", "source": "resume_claim", "excerpt": "SystemVerilog"}]
    for project, prefix in (("one", "A"), ("two", "B")):
        evidence.extend({"id": f"depth:{project}:{prefix}{n}", "source": "depth_repository",
                         "project_id": project, "excerpt": text}
                        for n, text in ((1, "SystemVerilog module"), (2, "FPGA verification test"),
                                        (3, "generic notes"), (4, "unrelated file")))
    contexts = [{"project_id": "one", "dimensions": {"verification": {"evidence_ids": ["depth:one:A2"]}},
                 "demonstrated_skills": []},
                {"project_id": "two", "dimensions": {},
                 "demonstrated_skills": [{"skill": "SystemVerilog", "evidence_ids": ["depth:two:B2"]}]}]
    selected = select_lawyer_evidence(bundle, requirements, evidence, contexts, extras_per_project=0)
    ids = {item["id"] for item in selected}
    assert ids == {"profile:resume", "depth:one:A1", "depth:one:A2", "depth:two:B1", "depth:two:B2"}

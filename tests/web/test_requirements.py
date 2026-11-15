import pytest

from backend.web import requirements


DESCRIPTION = """Basic Success Criteria
Experience developing digital logic either in VHDL, Verilog, or SystemVerilog
Hands on experience with lab equipment: Power supplies, oscilloscopes, logic analyzers, multimeters
Proficient in C, C++, or Python
Preferred Success Criteria
Previous industry experience with FPGAs and aerospace hardware
If you require reasonable accommodation, contact recruiting.
"""


def test_source_checked_extraction_preserves_alternatives_and_ignores_boilerplate(monkeypatch):
    requirements.extract_requirements.cache_clear()
    monkeypatch.setattr(requirements, "generate_json", lambda *args, **kwargs: {"requirements": [
        {"kind": "required", "text": "Digital logic language", "source_quote": "Experience developing digital logic either in VHDL, Verilog, or SystemVerilog", "alternatives": ["VHDL", "Verilog", "SystemVerilog"]},
        {"kind": "required", "text": "Lab equipment", "source_quote": "Hands on experience with lab equipment: Power supplies, oscilloscopes, logic analyzers, multimeters", "alternatives": ["oscilloscopes", "multimeters"]},
        {"kind": "required", "text": "Programming language", "source_quote": "Proficient in C, C++, or Python", "alternatives": ["C", "C++", "Python"]},
        {"kind": "preferred", "text": "Industry experience", "source_quote": "Previous industry experience with FPGAs and aerospace hardware", "alternatives": []},
    ]})
    groups = requirements.extract_requirements(DESCRIPTION, "FPGA Intern", "Example", "test-model")
    assert [item["kind"] for item in groups] == ["required", "required", "required", "preferred"]
    assert groups[0]["alternatives"] == ["VHDL", "Verilog", "SystemVerilog"]
    assert groups[1]["alternatives"] == []
    assert all("accommodation" not in item["text"] for item in groups)


def test_rejects_requirement_without_exact_source_quote(monkeypatch):
    requirements.extract_requirements.cache_clear()
    monkeypatch.setattr(requirements, "generate_json", lambda *args, **kwargs: {"requirements": [
        {"kind": "required", "text": "Five years of ASIC experience", "source_quote": "Five years of ASIC experience", "alternatives": []},
    ]})
    with pytest.raises(ValueError, match="source quote"):
        requirements.extract_requirements(DESCRIPTION, "FPGA Intern", "Example", "test-model")


def test_retries_once_when_an_alternative_is_not_in_its_quote(monkeypatch):
    requirements.extract_requirements.cache_clear()
    calls = []
    def fake_generate(system, *_args, **_kwargs):
        calls.append(system)
        alternative = "Rust" if len(calls) == 1 else "Python"
        return {"requirements": [{"kind": "required", "text": "Programming language",
                 "source_quote": "Proficient in C, C++, or Python", "alternatives": [alternative]}]}
    monkeypatch.setattr(requirements, "generate_json", fake_generate)
    groups = requirements.extract_requirements(DESCRIPTION, "FPGA Intern", "Example", "test-model")
    assert groups[0]["alternatives"] == ["Python"]
    assert len(calls) == 2

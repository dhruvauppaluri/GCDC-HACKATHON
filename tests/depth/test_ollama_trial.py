from backend.depth import evaluation, ollama_adapter
from backend.depth.rubrics import RUBRICS


def test_ollama_mode_uses_local_structured_evaluator(monkeypatch):
    calls = []
    def fake_ollama(system, content, **kwargs):
        calls.append(kwargs)
        return {"dimensions": {name: None for name in RUBRICS["hardware"]}}
    monkeypatch.setattr(evaluation, "ollama_json", fake_ollama)
    result = evaluation.initial_assessment("demo", "hardware", None, None,
        [{"id": "E1", "source_type": "claim", "location": "resume", "excerpt": "Built an FPGA"}], [], "ollama")
    assert result["evaluation_mode"] == "ollama"
    assert calls == [{"dimensions": tuple(RUBRICS["hardware"])}]
    assert result["depth_score"] is None


def test_ollama_adapter_sends_schema_to_local_chat(monkeypatch):
    class Response:
        def raise_for_status(self): pass
        def json(self): return {"message": {"content": '{"dimensions": {"verification": null}}'}}
    def fake_post(url, **kwargs):
        assert url == "http://127.0.0.1:11434/api/chat"
        assert kwargs["json"]["format"]["properties"]["dimensions"]["required"] == ["verification"]
        return Response()
    monkeypatch.setattr(ollama_adapter.httpx, "post", fake_post)
    assert ollama_adapter.ollama_json("Assess", {"evidence": []}, answer_only=True, dimensions=("verification",))["dimensions"] == {"verification": None}

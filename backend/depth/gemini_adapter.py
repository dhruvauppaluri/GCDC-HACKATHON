"""Gemini evaluator entry point with the same contract as local Ollama Depth."""

from backend.web.gemini_client import generate_json

from .codex_adapter import schema


def gemini_json(system: str, content: dict, *, answer_only: bool = False, dimensions: tuple[str, ...] | None = None) -> dict:
    names = dimensions or (("conceptual", "systems", "tradeoffs") if answer_only else ("conceptual", "implementation", "systems", "tradeoffs", "validation"))
    return generate_json(system, content, schema(answer_only, names), model_env="DEPTH_GEMINI_MODEL", timeout=300)

"""Standalone Project Depth Intelligence HTTP service."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
import os
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from .evaluation import initial_assessment, revise_assessment
from .ingestion import MAX_UPLOAD, extract_upload, make_evidence, parse_github_url, public_repository_evidence
from .storage import JobStore


DATA_DIR = Path(os.getenv("DEPTH_DATA_DIR", ".depth-data"))
store = JobStore(DATA_DIR / "jobs.sqlite3")
executor = ThreadPoolExecutor(max_workers=2)


def process_job(job_id: str):
    job = store.get(job_id)
    if not job or job["status"] not in {"queued", "running"}:
        return
    payload = job["payload"]
    old_result = job["result"]
    store.set(job_id, "running", result=old_result)
    try:
        if payload.get("pending_answers"):
            result = revise_assessment(old_result, payload["pending_answers"])
            payload.pop("pending_answers")
            store.update_payload(job_id, payload)
        else:
            sources = []
            limitations = []
            commit_sha = None
            if payload.get("repository_url"):
                commit_sha, repository_sources, repository_limits = public_repository_evidence(payload["repository_url"])
                sources.extend(repository_sources)
                limitations.extend(repository_limits)
            if payload.get("project_text"):
                sources.append({"source_type": "claim", "location": "project_text", "text": payload["project_text"][:180_000]})
            for file in payload.get("files", []):
                path = Path(file["path"])
                try:
                    text = extract_upload(file["name"], path.read_bytes())
                    if text.strip():
                        sources.append({"source_type": "document", "location": file["name"], "text": text})
                    else:
                        limitations.append(f"No extractable text in {file['name']}")
                finally:
                    path.unlink(missing_ok=True)
            if payload.get("files"):
                limitations.append("Uploaded artifacts are candidate-provided and have not been independently validated")
            evidence = make_evidence(sources)
            if sum((len(s["text"].splitlines()) + 34) // 35 for s in sources) > len(evidence):
                limitations.append("Evidence excerpt budget reached (100 excerpts or 60000 characters)")
            result = initial_assessment(payload["project_id"], payload["career_track"], payload.get("repository_url"), commit_sha, evidence, limitations, payload["mode"])
        store.set(job_id, "complete", result=result)
    except Exception as exc:
        store.set(job_id, "failed", result=old_result, error=f"{type(exc).__name__}: {exc}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    for job_id in store.unfinished():
        executor.submit(process_job, job_id)
    yield


app = FastAPI(title="SC-HACK Project Depth Intelligence", lifespan=lifespan)


class Answer(BaseModel):
    question_id: str
    answer: str = Field(min_length=1, max_length=8000)


class Answers(BaseModel):
    answers: list[Answer] = Field(min_length=1, max_length=5)


@app.post("/depth/evaluations", status_code=202)
async def create_evaluation(
    project_id: str = Form(...),
    career_track: str = Form(...),
    repository_url: str | None = Form(None),
    project_text: str | None = Form(None),
    mode: str = Form("mock"),
    files: list[UploadFile] | None = File(None),
):
    if career_track not in {"hardware", "software", "business", "product"} or mode not in {"mock", "live", "codex"}:
        raise HTTPException(422, "Invalid track or mode")
    if not project_id.strip() or len(project_id) > 120:
        raise HTTPException(422, "Invalid project_id")
    if not repository_url and not project_text and not files:
        raise HTTPException(422, "Provide a repository, project text, or file")
    if repository_url:
        try:
            parse_github_url(repository_url)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
    if project_text and len(project_text) > 180_000:
        raise HTTPException(413, "Project text exceeds 180000 characters")
    if files and len(files) > 5:
        raise HTTPException(413, "At most five files are accepted")
    job_id = str(uuid4())
    uploaded = []
    upload_dir = DATA_DIR / "uploads" / job_id
    for index, file in enumerate(files or []):
        name = Path(file.filename or "").name
        if not name or "." not in name or name.rsplit(".", 1)[-1].lower() not in {"pdf", "docx", "md", "txt"}:
            raise HTTPException(422, "Allowed uploads: PDF, DOCX, Markdown, plain text")
        data = await file.read(MAX_UPLOAD + 1)
        if len(data) > MAX_UPLOAD:
            raise HTTPException(413, f"Upload exceeds {MAX_UPLOAD} bytes")
        upload_dir.mkdir(parents=True, exist_ok=True)
        path = upload_dir / f"{index}-{name}"
        path.write_bytes(data)
        uploaded.append({"name": name, "path": str(path)})
    payload = {"project_id": project_id, "career_track": career_track, "repository_url": repository_url, "project_text": project_text, "mode": mode, "files": uploaded}
    store.put(job_id, payload)
    executor.submit(process_job, job_id)
    return {"evaluation_id": job_id, "status": "queued"}


@app.get("/depth/evaluations/{evaluation_id}")
def get_evaluation(evaluation_id: str):
    job = store.get(evaluation_id)
    if not job:
        raise HTTPException(404, "Evaluation not found")
    return {k: job[k] for k in ("evaluation_id", "status", "result", "error", "updated_at")}


@app.post("/depth/evaluations/{evaluation_id}/answers", status_code=202)
def submit_answers(evaluation_id: str, body: Answers):
    job = store.get(evaluation_id)
    if not job:
        raise HTTPException(404, "Evaluation not found")
    if job["status"] != "complete":
        raise HTTPException(409, "Evaluation must be complete before submitting answers")
    ids = {q["id"] for q in job["result"]["follow_up_questions"]}
    if any(a.question_id not in ids for a in body.answers):
        raise HTTPException(422, "Unknown question ID")
    payload = job["payload"]
    payload["pending_answers"] = [a.model_dump() for a in body.answers]
    store.update_payload(evaluation_id, payload)
    store.set(evaluation_id, "queued", result=job["result"])
    executor.submit(process_job, evaluation_id)
    return {"evaluation_id": evaluation_id, "status": "queued"}

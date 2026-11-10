"""Accounts, onboarding, profiles, and local demo jobs API."""
import io
import os
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from pypdf import PdfReader
import httpx

from .imports import import_github, import_website, validate_public_url
from .jobs import SKILL_OPTIONS, TRACKS, load_jobs, match_jobs, suggest_tracks
from .storage import Store

DATA_DIR = Path(os.getenv("WEB_DATA_DIR", ".web-data"))
store = Store(DATA_DIR / "app.sqlite3")
app = FastAPI(title="SC-HACK Candidate Experience")


def current_user(request: Request):
    user = store.user_for_session(request.cookies.get("sc_session"))
    if not user:
        raise HTTPException(401, "Please sign in")
    return user


def profile_response(user):
    profile = user["profile"].copy()
    profile["resume_text"] = profile["resume_text"][:300] if profile["resume_text"] else ""
    return {"id": user["id"], "email": user["email"], "profile": profile}


def set_session(response: Response, user_id: str):
    response.set_cookie("sc_session", store.new_session(user_id), httponly=True, samesite="lax", secure=os.getenv("WEB_SECURE_COOKIE") == "1", max_age=30 * 86400, path="/")


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)


class Name(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)


class Interests(BaseModel):
    interests: str = Field(min_length=1, max_length=2000)
    target_tracks: list[str] = Field(min_length=1, max_length=3)


class Skills(BaseModel):
    skills: dict[str, dict[str, int]]


class Links(BaseModel):
    linkedin_url: str = ""
    github_url: str = ""
    website_url: str = ""


class Selection(BaseModel):
    selected_ids: list[str]


@app.middleware("http")
async def same_origin_writes(request: Request, call_next):
    if request.method in {"POST", "PATCH", "PUT", "DELETE"}:
        origin = request.headers.get("origin")
        if origin and origin.rstrip("/") != str(request.base_url).rstrip("/"):
            return Response("Cross-origin request rejected", status_code=403)
    return await call_next(request)


@app.post("/api/auth/signup")
def signup(body: Credentials, response: Response):
    email = body.email.strip().lower()
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        raise HTTPException(422, "Enter a valid email")
    try:
        user_id = store.create_user(email, body.password)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    set_session(response, user_id)
    return profile_response(store.get_user(user_id))


@app.post("/api/auth/login")
def login(body: Credentials, response: Response):
    user_id = store.authenticate(body.email.strip().lower(), body.password)
    if not user_id:
        raise HTTPException(401, "Email or password is incorrect")
    set_session(response, user_id)
    return profile_response(store.get_user(user_id))


@app.post("/api/auth/logout", status_code=204)
def logout(request: Request, response: Response):
    store.delete_session(request.cookies.get("sc_session"))
    response.delete_cookie("sc_session", path="/")


@app.get("/api/me")
def me(user=Depends(current_user)):
    return profile_response(user)


@app.patch("/api/onboarding/name")
def save_name(body: Name, user=Depends(current_user)):
    first, last = body.first_name.strip(), body.last_name.strip()
    if not first or not last:
        raise HTTPException(422, "First and last name are required")
    store.update_profile(user["id"], {"first_name": first, "last_name": last})
    return profile_response(store.get_user(user["id"]))


@app.post("/api/onboarding/resume")
async def upload_resume(file: UploadFile = File(...), user=Depends(current_user)):
    name = Path(file.filename or "").name
    if not name.lower().endswith((".pdf", ".txt")):
        raise HTTPException(422, "Upload a PDF or TXT resume")
    raw = await file.read(2_000_001)
    if len(raw) > 2_000_000:
        raise HTTPException(413, "Resume must be 2 MB or smaller")
    try:
        if name.lower().endswith(".pdf"):
            if not raw.startswith(b"%PDF"):
                raise ValueError("File is not a PDF")
            text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(raw)).pages[:20])
        else:
            text = raw.decode("utf-8-sig")
    except Exception as exc:
        raise HTTPException(422, "Could not read resume") from exc
    if not text.strip():
        raise HTTPException(422, "Resume has no readable text")
    store.update_profile(user["id"], {"resume_name": name, "resume_text": text[:100_000]})
    return {"resume_name": name, "preview": text[:300]}


@app.get("/api/onboarding/options")
def options(user=Depends(current_user)):
    return {"tracks": TRACKS, "skill_options": SKILL_OPTIONS}


@app.get("/api/onboarding/suggest")
def suggest(interests: str, user=Depends(current_user)):
    return {"suggested_tracks": suggest_tracks(interests)}


@app.patch("/api/onboarding/interests")
def save_interests(body: Interests, user=Depends(current_user)):
    tracks = list(dict.fromkeys(body.target_tracks))
    if len(tracks) != len(body.target_tracks) or any(t not in TRACKS for t in tracks) or not body.interests.strip():
        raise HTTPException(422, "Choose at least one valid track and describe your interests")
    skills = {t: user["profile"]["skills"].get(t, {}) for t in tracks}
    complete = user["profile"]["completed"] and all(skills.get(t) for t in tracks)
    profile = store.update_profile(user["id"], {"interests": body.interests.strip(), "target_tracks": tracks, "skills": skills, "completed": complete})
    return {"profile": profile}


@app.patch("/api/onboarding/skills")
def save_skills(body: Skills, user=Depends(current_user)):
    tracks = user["profile"]["target_tracks"]
    if set(body.skills) != set(tracks) or any(not values for values in body.skills.values()):
        raise HTTPException(422, "Rate at least one skill for every selected track")
    if any(not name.strip() or len(name) > 80 or type(level) is not int or level < 1 or level > 5 for values in body.skills.values() for name, level in values.items()):
        raise HTTPException(422, "Skill ratings must be 1–5")
    store.update_profile(user["id"], {"skills": body.skills})
    return {"saved": True}


@app.post("/api/onboarding/complete")
def complete(user=Depends(current_user)):
    p = user["profile"]
    if not p["first_name"] or not p["last_name"] or not p["resume_text"] or not p["interests"] or not p["target_tracks"] or any(not p["skills"].get(t) for t in p["target_tracks"]):
        raise HTTPException(409, "Finish every setup step first")
    store.update_profile(user["id"], {"completed": True})
    return {"completed": True}


@app.patch("/api/profile/links")
def save_links(body: Links, user=Depends(current_user)):
    values = {key: getattr(body, key).strip() for key in ("linkedin_url", "github_url", "website_url")}
    try:
        if values["linkedin_url"]:
            validate_public_url(values["linkedin_url"], {"linkedin.com", "www.linkedin.com"})
        if values["github_url"]:
            validate_public_url(values["github_url"], {"github.com"})
        if values["website_url"]:
            validate_public_url(values["website_url"])
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    previous = user["profile"]
    projects = [item for item in previous["projects"] if not (
        (item["source"] == "github" and values["github_url"] != previous["github_url"])
        or (item["source"] == "website" and values["website_url"] != previous["website_url"])
    )]
    store.update_profile(user["id"], {**values, "projects": projects})
    return {"saved": True}


@app.post("/api/profile/import")
def import_projects(user=Depends(current_user)):
    p = user["profile"]
    if not p["github_url"] and not p["website_url"]:
        raise HTTPException(422, "Add a GitHub or website link first")
    projects, errors = [], []
    for field, importer in (("github_url", import_github), ("website_url", import_website)):
        if p[field]:
            try:
                projects.extend(importer(p[field]))
            except (ValueError, httpx.HTTPError, KeyError) as exc:
                errors.append(f"{field}: {exc}")
    if projects:
        previous = {item["id"]: item["selected"] for item in p["projects"]}
        for item in projects:
            item["selected"] = previous.get(item["id"], False)
        store.update_profile(user["id"], {"projects": projects})
    return {"projects": projects if projects else p["projects"], "errors": errors}


@app.patch("/api/profile/projects")
def select_projects(body: Selection, user=Depends(current_user)):
    valid = {item["id"] for item in user["profile"]["projects"]}
    if any(id not in valid for id in body.selected_ids):
        raise HTTPException(422, "Unknown project")
    projects = [{**item, "selected": item["id"] in body.selected_ids} for item in user["profile"]["projects"]]
    store.update_profile(user["id"], {"projects": projects})
    return {"projects": projects}


@app.get("/api/profile/export")
def export_profile(user=Depends(current_user)):
    """Authenticated candidate payload for Research/Judge integration."""
    p = user["profile"]
    return {
        "candidate_id": user["id"], "first_name": p["first_name"], "last_name": p["last_name"],
        "target_tracks": [TRACKS[t] for t in p["target_tracks"] if t in TRACKS],
        "interests": p["interests"], "resume_text": p["resume_text"],
        "skills": {TRACKS[t]: values for t, values in p["skills"].items() if t in TRACKS},
        "projects": [{key: value for key, value in item.items() if key in {"source", "url", "summary", "title"}} for item in p["projects"] if item.get("selected")],
        "links": {key: p[key] for key in ("linkedin_url", "github_url", "website_url")},
    }


@app.get("/api/jobs/matches")
def matches(user=Depends(current_user)):
    if not user["profile"]["completed"]:
        raise HTTPException(409, "Complete your profile first")
    source = os.getenv("RESEARCH_JOBS_FILE")
    try:
        jobs = load_jobs(Path(source) if source else None)
    except (ValueError, OSError) as exc:
        raise HTTPException(503, f"Research jobs unavailable: {exc}") from exc
    return {"jobs": match_jobs(user["profile"], jobs)}


DIST = Path(__file__).resolve().parents[2] / "web" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/")
    def index():
        return FileResponse(DIST / "index.html")

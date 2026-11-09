"""Bounded, read-only public evidence extraction. Never executes repository code."""
import base64
from io import BytesIO
import re
from zipfile import ZipFile
from urllib.parse import quote, urlparse

import httpx
from docx import Document
from pypdf import PdfReader

MAX_UPLOAD = 2_000_000
MAX_REPO_FILES = 30
MAX_SOURCE_CHARS = 180_000
MAX_EVIDENCE_CHARS = 60_000
ALLOWED_SUFFIXES = (".py", ".js", ".ts", ".tsx", ".swift", ".sv", ".v", ".c", ".cpp", ".h", ".rs", ".go", ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".sh", ".sql", ".csv")


def parse_github_url(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "github.com" or parsed.port or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Only public https://github.com/owner/repo URLs are supported")
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) != 2 or not all(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", p) for p in parts):
        raise ValueError("Use a repository root URL, not a file or branch URL")
    repo = parts[1].removesuffix(".git")
    if not repo:
        raise ValueError("Invalid repository name")
    return parts[0], repo


def extract_upload(filename: str, data: bytes) -> str:
    if len(data) > MAX_UPLOAD:
        raise ValueError(f"Upload exceeds {MAX_UPLOAD} bytes")
    suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix in {".txt", ".md"}:
        return data.decode("utf-8", errors="replace")[:MAX_SOURCE_CHARS]
    if suffix == ".pdf":
        reader = PdfReader(BytesIO(data))
        if len(reader.pages) > 30:
            raise ValueError("PDF exceeds 30 pages")
        return "\n".join(page.extract_text() or "" for page in reader.pages)[:MAX_SOURCE_CHARS]
    if suffix == ".docx":
        with ZipFile(BytesIO(data)) as archive:
            if sum(item.file_size for item in archive.infolist()) > 10_000_000:
                raise ValueError("DOCX expands beyond 10 MB")
        doc = Document(BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs)[:MAX_SOURCE_CHARS]
    raise ValueError("Allowed uploads: PDF, DOCX, Markdown, and plain text")


def public_repository_evidence(url: str) -> tuple[str, list[dict], list[str]]:
    owner, repo = parse_github_url(url)
    base = f"https://api.github.com/repos/{quote(owner)}/{quote(repo)}"
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "SC-HACK-depth-prototype"}
    limitations = []
    with httpx.Client(timeout=20, follow_redirects=False, headers=headers) as client:
        metadata = client.get(base)
        metadata.raise_for_status()
        if metadata.json().get("private") is not False:
            raise ValueError("Repository must be public")
        branch = metadata.json()["default_branch"]
        commit_response = client.get(f"{base}/commits/{quote(branch)}")
        commit_response.raise_for_status()
        sha = commit_response.json()["sha"]
        tree_response = client.get(f"{base}/git/trees/{sha}", params={"recursive": "1"})
        tree_response.raise_for_status()
        tree = tree_response.json()
        if tree.get("truncated"):
            limitations.append("GitHub tree was truncated")
        candidates = [item for item in tree.get("tree", []) if item.get("type") == "blob" and item.get("path", "").lower().endswith(ALLOWED_SUFFIXES) and item.get("size", 0) <= 50_000]
        candidates.sort(key=lambda item: (0 if re.search(r"readme|test|spec|architecture|design", item["path"], re.I) else 1, item["path"]))
        if len(candidates) > MAX_REPO_FILES:
            limitations.append(f"Only the first {MAX_REPO_FILES} eligible files were inspected")
        sources = []
        used = 0
        for item in candidates[:MAX_REPO_FILES]:
            if used >= MAX_SOURCE_CHARS:
                limitations.append("Repository text budget reached")
                break
            blob = client.get(f"{base}/git/blobs/{item['sha']}")
            blob.raise_for_status()
            body = blob.json()
            if body.get("encoding") != "base64":
                continue
            content = base64.b64decode(body["content"]).decode("utf-8", errors="replace")
            content = content[: min(12_000, MAX_SOURCE_CHARS - used)]
            used += len(content)
            if content.strip():
                sources.append({"source_type": "repository", "location": f"{item['path']}@{sha}", "text": content})
    return sha, sources, limitations


def make_evidence(sources: list[dict]) -> list[dict]:
    evidence = []
    used = 0
    for source in sources:
        lines = source["text"].splitlines()
        for start in range(0, len(lines), 35):
            if len(evidence) >= 100 or used >= MAX_EVIDENCE_CHARS:
                return evidence
            excerpt = "\n".join(lines[start:start + 35]).strip()
            if excerpt:
                excerpt = excerpt[:min(4000, MAX_EVIDENCE_CHARS - used)]
                used += len(excerpt)
                evidence.append({"id": f"E{len(evidence)+1}", "source_type": source["source_type"], "location": f"{source['location']}:L{start+1}-L{min(start+35, len(lines))}", "excerpt": excerpt[:4000]})
    return evidence

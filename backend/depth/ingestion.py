"""Bounded, read-only public evidence extraction. Never executes repository code."""
import base64
from html.parser import HTMLParser
import ipaddress
from io import BytesIO
import os
import re
import socket
import stat
import subprocess
import tempfile
from zipfile import ZipFile
from urllib.parse import quote, urlparse

import httpx
from docx import Document
from pypdf import PdfReader

MAX_UPLOAD = 2_000_000
MAX_REPO_FILES = 30
MAX_SOURCE_CHARS = 180_000
MAX_EVIDENCE_CHARS = 60_000
MAX_ARCHIVE_BYTES = 20_000_000
MAX_ARCHIVE_ENTRIES = 10_000
ALLOWED_SUFFIXES = (".py", ".js", ".ts", ".tsx", ".swift", ".sv", ".v", ".c", ".cpp", ".h", ".rs", ".go", ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".sh", ".sql", ".csv")


def _rate_limited(response) -> bool:
    return getattr(response, "status_code", None) in {403, 429} and getattr(response, "headers", {}).get("x-ratelimit-remaining") == "0"


def validate_public_website_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.port or parsed.fragment:
        raise ValueError("Use a public HTTPS website URL")
    if parsed.hostname.lower() in {"github.com", "api.github.com", "linkedin.com", "www.linkedin.com"}:
        raise ValueError("Use the repository field for GitHub; LinkedIn is not project evidence")
    try:
        addresses = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError("Website could not be found") from exc
    if not addresses or any(not ipaddress.ip_address(address[4][0]).is_global for address in addresses):
        raise ValueError("Website must resolve to a public address")


class PageText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"} and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.parts.append(data.strip())


def public_website_evidence(url: str) -> tuple[list[dict], list[str]]:
    validate_public_website_url(url)
    with httpx.Client(timeout=8, follow_redirects=False, trust_env=False) as client:
        with client.stream("GET", url, headers={"User-Agent": "SC-HACK-depth-prototype"}) as response:
            response.raise_for_status()
            if not 200 <= response.status_code < 300 or "text/html" not in response.headers.get("content-type", ""):
                raise ValueError("Website must return an HTML page without redirects")
            chunks, total = [], 0
            for chunk in response.iter_bytes():
                total += len(chunk)
                if total > 100_000:
                    break
                chunks.append(chunk)
    parser = PageText()
    parser.feed(b"".join(chunks).decode("utf-8", errors="replace"))
    text = "\n".join(parser.parts)[:MAX_SOURCE_CHARS]
    if not text.strip():
        return [], ["No readable website text was found"]
    return [{"source_type": "website", "location": url, "text": text}], (["Website text was truncated at 100 KB"] if total > 100_000 else [])


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
    if not (os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")):
        return _public_repository_archive(owner, repo)
    base = f"https://api.github.com/repos/{quote(owner)}/{quote(repo)}"
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "SC-HACK-depth-prototype"}
    if token := os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    limitations = []
    with httpx.Client(timeout=20, follow_redirects=False, headers=headers) as client:
        metadata = client.get(base)
        if _rate_limited(metadata):
            return _public_repository_archive(owner, repo)
        metadata.raise_for_status()
        if metadata.json().get("private") is not False:
            raise ValueError("Repository must be public")
        branch = metadata.json()["default_branch"]
        commit_response = client.get(f"{base}/commits/{quote(branch)}")
        if _rate_limited(commit_response):
            return _public_repository_archive(owner, repo)
        commit_response.raise_for_status()
        sha = commit_response.json()["sha"]
        tree_response = client.get(f"{base}/git/trees/{sha}", params={"recursive": "1"})
        if _rate_limited(tree_response):
            return _public_repository_archive(owner, repo, sha)
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
            if _rate_limited(blob):
                return _public_repository_archive(owner, repo, sha)
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


def _public_repository_archive(owner: str, repo: str, sha: str | None = None) -> tuple[str, list[dict], list[str]]:
    """Read a pinned public archive without spending GitHub REST API quota."""
    if sha is None:
        remote = f"https://github.com/{owner}/{repo}.git"
        try:
            refs = subprocess.run(
                ["git", "-c", "credential.helper=", "ls-remote", "--symref", remote, "HEAD"],
                capture_output=True, text=True, timeout=25, check=True,
                env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_GLOBAL": os.devnull,
                     "GIT_CONFIG_NOSYSTEM": "1"},
            ).stdout
        except (OSError, subprocess.SubprocessError) as exc:
            raise RuntimeError("Could not read the public repository HEAD") from exc
        match = re.search(r"^([0-9a-f]{40,64})\tHEAD$", refs, re.M)
        if not match:
            raise ValueError("Public repository has no readable HEAD commit")
        sha = match.group(1)
    archive_url = f"https://codeload.github.com/{quote(owner)}/{quote(repo)}/zip/{sha}"
    chunks, total = [], 0
    with httpx.Client(timeout=25, follow_redirects=False, trust_env=False) as client:
        with client.stream("GET", archive_url, headers={"User-Agent": "SC-HACK-depth-prototype"}) as response:
            response.raise_for_status()
            if response.status_code != 200:
                raise ValueError("Public repository archive is unavailable")
            for chunk in response.iter_bytes():
                total += len(chunk)
                if total > MAX_ARCHIVE_BYTES:
                    return _public_repository_git(owner, repo)
                chunks.append(chunk)
    with ZipFile(BytesIO(b"".join(chunks))) as archive:
        infos = archive.infolist()
        if len(infos) > MAX_ARCHIVE_ENTRIES:
            raise ValueError("Repository archive has too many entries to inspect")
        candidates = []
        for item in infos:
            parts = item.filename.split("/", 1)
            path = parts[1] if len(parts) == 2 else ""
            if (not path or item.is_dir() or ".." in path.split("/") or
                    stat.S_ISLNK(item.external_attr >> 16) or
                    not path.lower().endswith(ALLOWED_SUFFIXES) or item.file_size > 50_000):
                continue
            candidates.append((path, item))
        candidates.sort(key=lambda pair: (0 if re.search(r"readme|test|spec|architecture|design", pair[0], re.I) else 1, pair[0]))
        limitations = [f"Only the first {MAX_REPO_FILES} eligible files were inspected"] if len(candidates) > MAX_REPO_FILES else []
        sources, used = [], 0
        for path, item in candidates[:MAX_REPO_FILES]:
            if used >= MAX_SOURCE_CHARS:
                limitations.append("Repository text budget reached")
                break
            content = archive.read(item).decode("utf-8", errors="replace")
            content = content[:min(12_000, MAX_SOURCE_CHARS - used)]
            used += len(content)
            if content.strip():
                sources.append({"source_type": "repository", "location": f"{path}@{sha}", "text": content})
    return sha, sources, limitations


def _public_repository_git(owner: str, repo: str) -> tuple[str, list[dict], list[str]]:
    """Inspect a large public repo through a blobless clone, never checking out code."""
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_GLOBAL": os.devnull,
           "GIT_CONFIG_NOSYSTEM": "1"}
    remote = f"https://github.com/{owner}/{repo}.git"
    with tempfile.TemporaryDirectory(prefix="gcdc-depth-") as directory:
        try:
            subprocess.run(["git", "-c", "credential.helper=", "clone", "--filter=blob:none",
                            "--depth=1", "--no-checkout", "--quiet", remote, directory],
                           capture_output=True, timeout=45, check=True, env=env)
            sha = subprocess.run(["git", "-C", directory, "rev-parse", "HEAD"],
                                 capture_output=True, text=True, timeout=10, check=True, env=env).stdout.strip()
            tree = subprocess.run(["git", "-C", directory, "ls-tree", "-r", "-z", "HEAD"],
                                  capture_output=True, timeout=15, check=True, env=env).stdout
        except (OSError, subprocess.SubprocessError) as exc:
            raise RuntimeError("Could not inspect the public repository tree") from exc
        if not re.fullmatch(r"[0-9a-f]{40,64}", sha):
            raise ValueError("Public repository has no valid HEAD commit")
        entries = tree.split(b"\0")
        if len(entries) > MAX_ARCHIVE_ENTRIES:
            raise ValueError("Repository tree has too many entries to inspect")
        candidates = []
        for entry in entries:
            if not entry or b"\t" not in entry:
                continue
            metadata, path_bytes = entry.split(b"\t", 1)
            fields = metadata.split()
            path = path_bytes.decode("utf-8", errors="replace")
            if (len(fields) != 3 or fields[1] != b"blob" or
                    not path.lower().endswith(ALLOWED_SUFFIXES) or ".." in path.split("/")):
                continue
            candidates.append((path, fields[2].decode("ascii")))
        candidates.sort(key=lambda pair: (0 if re.search(r"readme|test|spec|architecture|design", pair[0], re.I) else 1, pair[0]))
        limitations = [f"Only the first {MAX_REPO_FILES} eligible files were inspected"] if len(candidates) > MAX_REPO_FILES else []
        sources, used = [], 0
        for path, blob in candidates[:MAX_REPO_FILES]:
            if used >= MAX_SOURCE_CHARS:
                limitations.append("Repository text budget reached")
                break
            try:
                size = subprocess.run(["git", "-C", directory, "cat-file", "-s", blob],
                                      capture_output=True, text=True, timeout=15, check=True, env=env)
                if int(size.stdout.strip()) > 50_000:
                    continue
                file = subprocess.run(["git", "-C", directory, "cat-file", "blob", blob],
                                      capture_output=True, timeout=10, check=True, env=env)
            except (OSError, ValueError, subprocess.SubprocessError):
                limitations.append(f"Could not read {path} from the public repository")
                continue
            content = file.stdout.decode("utf-8", errors="replace")[:min(12_000, MAX_SOURCE_CHARS - used)]
            used += len(content)
            if content.strip():
                sources.append({"source_type": "repository", "location": f"{path}@{sha}", "text": content})
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

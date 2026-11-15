"""Bounded import of user-supplied public project links."""
import ipaddress
import re
import socket
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx


def validate_public_url(value: str, hosts: set[str] | None = None):
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.port or parsed.fragment:
        raise ValueError("Enter a public HTTPS URL")
    host = parsed.hostname.lower()
    if hosts and host not in hosts:
        raise ValueError("Enter a URL from the expected site")
    if not hosts:
        try:
            addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise ValueError("Website could not be found") from exc
        if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
            raise ValueError("Website must resolve to a public address")
    return parsed


class TextExtractor(HTMLParser):
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


class GitHubRepositoryList(HTMLParser):
    """Read only public repository cards from a GitHub profile page."""
    def __init__(self, owner: str):
        super().__init__()
        self.owner = owner.casefold()
        self.repositories = []
        self.current = None
        self.capture = None

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "li" and values.get("itemprop") == "owns" and "public" in values.get("class", "").split():
            self.current = {"path": "", "name": "", "description": ""}
        elif self.current is not None and tag == "a" and "codeRepository" in values.get("itemprop", "").split():
            self.current["path"] = values.get("href", "")
            self.capture = "name"
        elif self.current is not None and values.get("itemprop") == "description":
            self.capture = "description"

    def handle_endtag(self, tag):
        if self.current is not None and tag == "li":
            path = self.current["path"]
            parts = path.strip("/").split("/")
            if len(parts) == 2 and parts[0].casefold() == self.owner and re.fullmatch(r"[A-Za-z0-9_.-]+", parts[1]):
                self.repositories.append({
                    "id": f"github:{parts[0]}/{parts[1]}", "source": "github",
                    "title": self.current["name"].strip()[:120] or parts[1],
                    "url": f"https://github.com/{parts[0]}/{parts[1]}",
                    "summary": self.current["description"].strip()[:500] or "Public GitHub repository",
                    "selected": False,
                })
            self.current = None
            self.capture = None
        elif tag in {"a", "p"}:
            self.capture = None

    def handle_data(self, data):
        if self.current is not None and self.capture:
            self.current[self.capture] += data


def import_github(url: str):
    parsed = validate_public_url(url, {"github.com"})
    segments = [part for part in parsed.path.split("/") if part]
    if not segments or len(segments) > 2 or any(not re.fullmatch(r"[A-Za-z0-9_.-]+", part) for part in segments):
        raise ValueError("Use a GitHub profile or repository URL")
    owner = segments[0]
    page = f"https://github.com/{owner}" + (f"/{segments[1]}" if len(segments) == 2 else "?tab=repositories")
    with httpx.Client(timeout=15, follow_redirects=False, trust_env=False, headers={"User-Agent": "Mozilla/5.0"}) as client:
        with client.stream("GET", page) as response:
            response.raise_for_status()
            if "text/html" not in response.headers.get("content-type", ""):
                raise ValueError("GitHub did not return a public page")
            chunks, size = [], 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > 1_000_000:
                    raise ValueError("GitHub profile page is too large to inspect")
                chunks.append(chunk)
    if len(segments) == 2:
        name = segments[1]
        return [{"id": f"github:{owner}/{name}", "source": "github", "title": name,
                 "url": f"https://github.com/{owner}/{name}", "summary": "Public GitHub repository", "selected": False}]
    parser = GitHubRepositoryList(owner)
    parser.feed(b"".join(chunks).decode("utf-8", errors="replace"))
    if not parser.repositories:
        raise ValueError("No public repositories found on this GitHub profile")
    return parser.repositories[:8]


def import_website(url: str):
    parsed = validate_public_url(url)
    if parsed.hostname in {"github.com", "api.github.com", "linkedin.com", "www.linkedin.com"}:
        raise ValueError("Use the matching profile field for this site")
    with httpx.Client(timeout=8, follow_redirects=False) as client:
        with client.stream("GET", url, headers={"User-Agent": "SC-HACK-onboarding"}) as response:
            response.raise_for_status()
            if "text/html" not in response.headers.get("content-type", ""):
                raise ValueError("Website must return an HTML page")
            chunks = []
            total = 0
            for chunk in response.iter_bytes():
                total += len(chunk)
                if total > 100_000:
                    break
                chunks.append(chunk)
    parser = TextExtractor()
    parser.feed(b"".join(chunks).decode("utf-8", errors="replace"))
    summary = " ".join(parser.parts)[:4000]
    if not summary:
        raise ValueError("No readable text found on website")
    return [{"id": f"website:{parsed.hostname}", "source": "website", "title": parsed.hostname, "url": url, "summary": summary, "selected": False}]

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


def import_github(url: str):
    parsed = validate_public_url(url, {"github.com"})
    segments = [part for part in parsed.path.split("/") if part]
    if not segments or len(segments) > 2 or any(not re.fullmatch(r"[A-Za-z0-9_.-]+", part) for part in segments):
        raise ValueError("Use a GitHub profile or repository URL")
    owner = segments[0]
    endpoint = f"https://api.github.com/repos/{owner}/{segments[1]}" if len(segments) == 2 else f"https://api.github.com/users/{owner}/repos"
    with httpx.Client(timeout=8, follow_redirects=False, headers={"Accept": "application/vnd.github+json", "User-Agent": "SC-HACK-onboarding"}) as client:
        response = client.get(endpoint, params={"per_page": 30, "sort": "updated"} if len(segments) == 1 else None)
        response.raise_for_status()
        raw = response.json()
    repos = raw if isinstance(raw, list) else [raw]
    return [{"id": f"github:{r['full_name']}", "source": "github", "title": r["name"][:120], "url": r["html_url"], "summary": (r.get("description") or "Public GitHub repository")[:500], "selected": False} for r in repos if isinstance(r, dict) and not r.get("private")][:8]


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

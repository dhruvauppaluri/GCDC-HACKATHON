"""Validate PR changed-file manifests against trusted base-branch ownership."""
import argparse
import json
from pathlib import Path


def validate(config: dict, actor: str, changes: list[dict]) -> list[str]:
    errors = []
    owners = config.get("owners")
    identities = config.get("github_identities")
    restricted = config.get("restricted")
    if config.get("version") != 1 or not isinstance(owners, dict) or not isinstance(identities, dict) or not isinstance(restricted, list):
        return ["Malformed trusted ownership configuration"]
    if not actor or actor not in identities or identities[actor] not in owners:
        return ["Unknown GitHub identity"]
    developer = identities[actor]
    owner = owners[developer]
    if not isinstance(owner, dict) or not isinstance(owner.get("paths"), list):
        return ["Malformed owner paths"]
    all_paths = []
    for name, entry in owners.items():
        if not isinstance(entry, dict) or not isinstance(entry.get("paths"), list):
            return [f"Malformed paths for {name}"]
        for p in entry["paths"]:
            if not isinstance(p, str) or not p or p.startswith("/") or ".." in Path(p).parts:
                return ["Malformed owner path"]
            all_paths.append((name, p))
    for i, (name, path) in enumerate(all_paths):
        for other_name, other_path in all_paths[i + 1:]:
            if name != other_name and (path == other_path or (path.endswith("/") and other_path.startswith(path)) or (other_path.endswith("/") and path.startswith(other_path))):
                return ["Ambiguous ownership configuration"]
    if not all(isinstance(p, str) and p and not p.startswith("/") for p in restricted):
        return ["Malformed restricted paths"]

    def matches(path: str, rule: str) -> bool:
        return path.startswith(rule) if rule.endswith("/") else path == rule

    integration = config.get("integration_maintainer")
    for change in changes:
        status = change.get("status")
        paths = [change.get("filename")]
        if status == "renamed":
            paths.append(change.get("previous_filename"))
        if status not in {"added", "modified", "removed", "renamed", "copied", "changed"} or any(not isinstance(p, str) or not p or p.startswith("/") or ".." in Path(p).parts for p in paths):
            errors.append("Malformed changed-file entry")
            continue
        for path in paths:
            if path == f".agents/{developer}.md":
                continue
            if any(matches(path, p) for p in restricted):
                if developer != integration:
                    errors.append(f"Restricted shared path: {path}")
                continue
            if owner.get("assignment") != "confirmed" or not any(matches(path, p) for p in owner["paths"]):
                errors.append(f"Unauthorized path: {path}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--actor", required=True, help="Authenticated PR author login")
    parser.add_argument("--changes", type=Path, required=True, help="GitHub files API JSON manifest")
    parser.add_argument("--config", type=Path, default=Path(".agents/ownership.json"), help="Trusted base checkout config")
    args = parser.parse_args()
    try:
        errors = validate(json.loads(args.config.read_text()), args.actor, json.loads(args.changes.read_text()))
    except (OSError, ValueError, TypeError) as exc:
        errors = [f"Invalid validator input: {exc}"]
    for error in errors:
        print(error)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

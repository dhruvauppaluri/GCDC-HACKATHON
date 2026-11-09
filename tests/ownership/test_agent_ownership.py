from scripts.check_agent_ownership import validate


BASE = {
    "version": 1,
    "github_identities": {"dhruva-gh": "dhruva", "maintainer-gh": "maintainer"},
    "integration_maintainer": "maintainer",
    "owners": {
        "dhruva": {"assignment": "confirmed", "paths": ["backend/depth/", ".agents/dhruva.md"]},
        "maintainer": {"assignment": "confirmed", "paths": [".agents/maintainer.md"]},
    },
    "restricted": ["AGENTS.md", ".agents/ownership.json", ".github/", "backend/shared/"],
}


def check(path, status="modified", **extra):
    return validate(BASE, "dhruva-gh", [{"filename": path, "status": status, **extra}])


def test_authorized_and_personal():
    assert not check("backend/depth/service.py")
    assert not check(".agents/dhruva.md")


def test_cross_component_shared_and_enforcement():
    for path in ["backend/research/service.py", "backend/shared/schema.py", ".agents/ownership.json", ".github/workflows/agent-ownership.yml"]:
        assert check(path)


def test_rename_and_deletion():
    assert check("backend/depth/new.py", "renamed", previous_filename="backend/research/old.py")
    assert check("backend/research/old.py", "removed")


def test_identity_spoof_and_untrusted_head_config():
    assert validate(BASE, "unknown", [{"filename": "backend/depth/a.py", "status": "modified"}])
    assert check("backend/research/a.py")  # branch name and PR body are deliberately absent from inputs
    assert check(".agents/ownership.json")  # PR-head changes cannot alter BASE


def test_fail_closed_ambiguous():
    config = {**BASE, "owners": {**BASE["owners"], "other": {"assignment": "confirmed", "paths": ["backend/depth/"]}}}
    assert validate(config, "dhruva-gh", [{"filename": "backend/depth/a.py", "status": "modified"}])


def test_unassigned_agent_can_update_only_personal_status():
    config = {**BASE, "github_identities": {**BASE["github_identities"], "harsh-gh": "harsh"}, "owners": {**BASE["owners"], "harsh": {"assignment": "unconfirmed", "paths": [".agents/harsh.md"]}}}
    assert not validate(config, "harsh-gh", [{"filename": ".agents/harsh.md", "status": "modified"}])
    assert validate(config, "harsh-gh", [{"filename": "backend/research/app.py", "status": "modified"}])

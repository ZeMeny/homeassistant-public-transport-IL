"""Test domain, manifest, and HACS metadata."""

import json
from pathlib import Path

from custom_components.public_transport_il.const import DOMAIN

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = (
    REPO_ROOT / "custom_components" / "public_transport_il" / "manifest.json"
)
HACS_PATH = REPO_ROOT / "hacs.json"
GITHUB_REPO = "https://github.com/ZeMeny/homeassistant-public-transport-IL"


def test_domain_and_hacs_metadata() -> None:
    """Domain, manifest, and hacs.json match the HACS layout."""
    assert DOMAIN == "public_transport_il"

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert list(manifest) == [
        "domain",
        "name",
        "codeowners",
        "config_flow",
        "documentation",
        "iot_class",
        "issue_tracker",
        "requirements",
        "version",
    ]
    assert manifest == {
        "domain": "public_transport_il",
        "name": "Public Transport IL",
        "codeowners": ["@ZeMeny"],
        "config_flow": True,
        "documentation": GITHUB_REPO,
        "iot_class": "cloud_polling",
        "issue_tracker": f"{GITHUB_REPO}/issues",
        "requirements": [],
        "version": "0.1.0",
    }
    assert "integration_type" not in manifest

    hacs = json.loads(HACS_PATH.read_text(encoding="utf-8"))
    assert list(hacs) == ["name", "render_readme", "homeassistant"]
    assert hacs == {
        "name": "Public Transport IL",
        "render_readme": True,
        "homeassistant": "2025.1.4",
    }
    assert "iot_class" not in hacs

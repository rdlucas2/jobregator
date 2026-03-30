import pytest

from src.notify import should_notify, build_discord_payload


def test_should_notify_above_threshold():
    assert should_notify(0.85, threshold=0.7) is True


def test_should_notify_at_threshold():
    assert should_notify(0.7, threshold=0.7) is True


def test_should_notify_below_threshold():
    assert should_notify(0.5, threshold=0.7) is False


def test_should_notify_zero_score():
    assert should_notify(0.0, threshold=0.7) is False


def test_should_notify_default_threshold():
    # Default threshold should be 0.7
    assert should_notify(0.8) is True
    assert should_notify(0.5) is False


def test_build_discord_payload_contains_required_fields():
    listing = {
        "title": "Senior DevOps Engineer",
        "company": "Acme Corp",
        "url": "https://example.com/jobs/123",
        "salary": "$150000-$200000",
        "location": "Remote, USA",
        "enrichment": {
            "fit_score": 0.85,
            "scoring": {
                "reasoning": "Strong match for K8s and Terraform experience.",
            },
        },
    }

    payload = build_discord_payload(listing)

    # Discord webhook expects embeds
    assert "embeds" in payload
    embed = payload["embeds"][0]
    assert "Senior DevOps Engineer" in embed["title"]
    assert "Acme Corp" in embed["description"]
    assert "0.85" in embed["description"]
    assert "https://example.com/jobs/123" in embed["url"]
    assert "Strong match" in embed["description"]


def test_build_discord_payload_handles_missing_fields():
    listing = {
        "title": "Some Job",
        "enrichment": {
            "fit_score": 0.6,
        },
    }

    payload = build_discord_payload(listing)

    embed = payload["embeds"][0]
    assert "Some Job" in embed["title"]
    # Should not crash on missing company/url/reasoning

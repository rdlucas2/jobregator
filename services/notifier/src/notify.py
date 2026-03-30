DEFAULT_THRESHOLD = 0.7


def should_notify(score: float, threshold: float = DEFAULT_THRESHOLD) -> bool:
    """Return True if the fit score meets or exceeds the threshold."""
    return score >= threshold


def build_discord_payload(listing: dict) -> dict:
    """Build a Discord webhook payload from an enriched listing."""
    title = listing.get("title", "Unknown Title")
    company = listing.get("company", "Unknown Company")
    url = listing.get("url", "")
    salary = listing.get("salary", "")
    location = listing.get("location", "")

    enrichment = listing.get("enrichment", {})
    fit_score = enrichment.get("fit_score", 0.0)
    scoring = enrichment.get("scoring", {})
    reasoning = scoring.get("reasoning", "")

    description_parts = [
        f"**Company:** {company}",
        f"**Score:** {fit_score:.2f}",
    ]
    if location:
        description_parts.append(f"**Location:** {location}")
    if salary:
        description_parts.append(f"**Salary:** {salary}")
    if reasoning:
        description_parts.append(f"\n{reasoning}")

    color = _score_to_color(fit_score)

    embed = {
        "title": title,
        "description": "\n".join(description_parts),
        "color": color,
    }
    if url:
        embed["url"] = url

    return {"embeds": [embed]}


def _score_to_color(score: float) -> int:
    """Map fit score to a Discord embed color."""
    if score >= 0.8:
        return 0x2ECC71  # green
    elif score >= 0.6:
        return 0xF1C40F  # yellow
    else:
        return 0xE74C3C  # red

import anthropic

# Claude Sonnet 5. Enrichment is bounded classification over a high volume of
# listings, which does not need Opus-tier reasoning. The earlier pin,
# claude-sonnet-4-20250514, was retired and returned 404 on every request.
DEFAULT_MODEL = "claude-sonnet-5"

# A ceiling, not a spend — only generated tokens are billed. Low enough to stay
# inside the SDK's non-streaming HTTP timeout.
MAX_TOKENS = 16000


class ClaudeLLM:
    """Wraps the Anthropic Claude API."""

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model

    async def complete(self, prompt: str) -> str:
        message = await self.client.messages.create(
            model=self.model,
            max_tokens=MAX_TOKENS,
            # Enrichment is bounded classification and extraction, not open-ended
            # reasoning, and it runs on every listing — low effort keeps
            # per-listing cost and latency down.
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": prompt}],
        )
        return _first_text(message)


def _first_text(message) -> str:
    """Return the first text block's content.

    `content` is a list of blocks, and on models where thinking is on by default
    the first one is a thinking block. Indexing content[0].text assumes a shape
    the API does not promise.
    """
    for block in message.content:
        if getattr(block, "type", None) == "text":
            return block.text
    raise RuntimeError(
        f"no text block in response from {getattr(message, 'model', 'unknown')}"
    )

"""Response shape handling for the Anthropic client wrapper."""

import pytest

from src.llm import _first_text


class Block:
    def __init__(self, type_, text=None, thinking=None):
        self.type = type_
        if text is not None:
            self.text = text
        if thinking is not None:
            self.thinking = thinking


class Message:
    def __init__(self, content, model="claude-opus-5"):
        self.content = content
        self.model = model


def test_reads_the_text_block_when_it_is_first():
    assert _first_text(Message([Block("text", text='{"ok": true}')])) == '{"ok": true}'


def test_skips_a_leading_thinking_block():
    """Regression: the old code took content[0].text. On models where thinking
    is on by default, content[0] is a thinking block with no .text at all."""
    message = Message([
        Block("thinking", thinking="considering the listing"),
        Block("text", text='{"fit_score": 0.8}'),
    ])

    assert _first_text(message) == '{"fit_score": 0.8}'


def test_raises_when_no_text_block_is_present():
    with pytest.raises(RuntimeError, match="no text block"):
        _first_text(Message([Block("thinking", thinking="...")]))

"""Split page/slide text into ~500-token chunks with 50-token overlap.

Tokens are approximated as words * 1.3 (close enough for English lecture
notes, and avoids shipping a tokenizer). A page or slide that already fits is
never split, so a citation always points at one page or slide.
"""
from dataclasses import dataclass

from app.config import get_settings

settings = get_settings()
WORDS_PER_TOKEN = 1 / 1.3


@dataclass
class TextChunk:
    page_or_slide: int
    content: str


def chunk_pages(pages: list[tuple[int, str]], filename: str) -> list[TextChunk]:
    max_words = int(settings.CHUNK_TOKENS * WORDS_PER_TOKEN)
    overlap = int(settings.CHUNK_OVERLAP * WORDS_PER_TOKEN)
    step = max(1, max_words - overlap)
    chunks: list[TextChunk] = []
    for number, text in pages:
        words = text.split()
        if not words:
            continue
        if len(words) <= max_words:
            pieces = [" ".join(words)]
        else:
            pieces = [" ".join(words[i:i + max_words]) for i in range(0, len(words), step)]
            # drop a trailing piece that is fully inside the previous overlap
            if len(pieces) > 1 and len(words) - (len(pieces) - 1) * step <= overlap:
                pieces.pop()
        for piece in pieces:
            # filename prefix gives the embedding some document context
            chunks.append(TextChunk(number, f"[{filename}]\n{piece}"))
    return chunks

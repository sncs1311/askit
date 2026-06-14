import re
from bm25_index import tokenize

# Words that carry no topical signal — filtered before keyword overlap
STOP_WORDS = {
    'what', 'is', 'the', 'of', 'a', 'an', 'in', 'on', 'at', 'to',
    'for', 'with', 'by', 'from', 'up', 'about', 'into', 'through',
    'how', 'who', 'where', 'when', 'why', 'which', 'that', 'this',
    'was', 'are', 'be', 'been', 'being', 'have', 'has', 'had',
    'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may',
    'can', 'me', 'my', 'we', 'our', 'you', 'your', 'it', 'its',
    'and', 'or', 'but', 'not', 'no', 'so', 'if', 'then', 'than'
}

# Weights for combining the two relevance signals
VECTOR_WEIGHT = 0.7
KEYWORD_WEIGHT = 0.3

# Chunks below this score are dropped before reaching the LLM
DEFAULT_THRESHOLD = 0.20


def extract_content_words(text: str) -> set[str]:
    """
    Extract meaningful words from text — strip stop words and short tokens.
    These are the words we check for overlap between query and chunk.
    """
    tokens = tokenize(text)  # lowercase, alphanumeric only
    return {t for t in tokens if t not in STOP_WORDS and len(t) > 2}


def score_chunk(chunk: dict, query: str) -> float:
    """
    Score one retrieved chunk for relevance to the query.
    Returns a float between 0.0 (irrelevant) and 1.0 (highly relevant).

    Two signals:
    1. Vector similarity — from ChromaDB distance (already computed)
    2. Keyword overlap — fraction of query content words in chunk text
    """
    # ── Signal 1: vector similarity ───────────────────────────────────────
    if 'distance' in chunk:
        # ChromaDB distance: 0.0 = identical, 2.0 = opposite
        # Clamp to 0-1 range for safety (distance can slightly exceed 1)
        vector_score = max(0.0, min(1.0, 1.0 - chunk['distance']))
    else:
        # BM25-only result — no distance available
        # Use neutral baseline; keyword overlap will differentiate
        vector_score = 0.5

    # ── Signal 2: keyword overlap ─────────────────────────────────────────
    query_words = extract_content_words(query)
    chunk_words = extract_content_words(chunk['text'])

    if not query_words:
        # Query has no content words (e.g. "what is it?")
        # Can't compute overlap — rely entirely on vector score
        keyword_overlap = 0.5
    else:
        # What fraction of query's content words appear in the chunk?
        matches = query_words & chunk_words
        keyword_overlap = len(matches) / len(query_words)

    # ── NEW: boost for section header match ──────────────────────────
    # If query mentions a section name that appears in chunk header,
    # boost the score — "summary section" should find SUMMARY chunk
    section_boost = 0.0
    section_keywords = {
        'summary', 'project', 'skill', 'education', 'experience',
        'language', 'framework', 'tool', 'achievement', 'certification'
    }
    query_lower = query.lower()
    chunk_lower = chunk['text'].lower()

    for kw in section_keywords:
        if kw in query_lower and kw in chunk_lower[:50]:
            # Keyword appears in query AND near start of chunk (header area)
            section_boost = 0.2
            break
    # ── END boost ────────────────────────────────────────────────────

    # ── Combined score ────────────────────────────────────────────────────
    final_score = (VECTOR_WEIGHT * vector_score) + (KEYWORD_WEIGHT * keyword_overlap) + section_boost

    return round(min(1.0, final_score), 4)


def filter_chunks(
    chunks: list[dict],
    query: str,
    threshold: float = DEFAULT_THRESHOLD
) -> list[dict]:
    """
    Score all retrieved chunks. Drop those below threshold.
    Sort survivors by relevance score — best chunks first.

    Returns empty list if nothing passes threshold.
    Caller must handle empty list as abstention signal.
    """
    scored = []

    for chunk in chunks:
        score = score_chunk(chunk, query)
        chunk_with_score = chunk.copy()
        chunk_with_score['relevance_score'] = score
        scored.append(chunk_with_score)

    # Filter — only keep chunks above threshold
    passing = [c for c in scored if c['relevance_score'] >= threshold]

    # Sort by score descending — best chunks go first in LLM context
    # LLMs pay more attention to early context in the prompt
    passing.sort(key=lambda c: c['relevance_score'], reverse=True)

    return passing


def compute_confidence(chunks: list[dict]) -> float:
    """
    Mean relevance score of all passing chunks.
    Represents how well the documents support the answer.

    0.0  → abstention (no chunks passed)
    0.35-0.59 → low confidence (answer may be incomplete)
    0.60-0.79 → medium confidence
    0.80+     → high confidence
    """
    if not chunks:
        return 0.0

    scores = [c.get('relevance_score', 0.0) for c in chunks]
    return round(sum(scores) / len(scores), 3)


def confidence_label(score: float) -> str:
    """Human-readable confidence label for the response."""
    if score == 0.0:
        return "no_support"
    elif score < 0.5:
        return "low"
    elif score < 0.7:
        return "medium"
    else:
        return "high"
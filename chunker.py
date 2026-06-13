from sentence_transformers import SentenceTransformer
import numpy as np
import re

model = SentenceTransformer("all-MiniLM-L6-v2")


# ── Utility: cosine similarity between two vectors ────────────────────────

def cosine_similarity(a: list, b: list) -> float:
    """
    Measures how similar two embedding vectors are.
    Returns 0.0 (completely different) to 1.0 (identical meaning).
    
    We use this to decide: did the topic just change between
    sentence[i] and sentence[i+1]?
    """
    a = np.array(a)
    b = np.array(b)
    
    dot_product = np.dot(a, b)
    magnitude = np.linalg.norm(a) * np.linalg.norm(b)
    
    # Guard against division by zero (empty vectors)
    if magnitude == 0:
        return 0.0
    
    return float(dot_product / magnitude)


# ── Step 1: Split text into sentences ────────────────────────────────────

def split_into_sentences(text: str) -> list[str]:
    """
    Split a block of text into individual sentences.
    Sentences are the unit we compare — not words, not paragraphs.
    
    A sentence carries one complete thought.
    That's the right granularity for detecting topic shifts.
    """
    # Split after sentence-ending punctuation followed by whitespace
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    
    # Remove empty strings and very short fragments (likely noise)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
    
    return sentences


# ── Step 2: Detect structural hard boundaries ─────────────────────────────

def find_hard_boundaries(text: str) -> list[str]:
    """
    Split text at structural markers BEFORE semantic analysis.
    These are always chunk boundaries regardless of semantic similarity.
    
    Hard boundaries:
    - [Page N] markers we added during ingestion
    - Lines that look like headings (ALL CAPS or Title Case short lines)
    - Code blocks (``` markers)
    - Double newlines (paragraph breaks)
    """
    # Split on page markers first
    sections = re.split(r'\[Page \d+\]', text)
    
    result = []
    for section in sections:
        if not section.strip():
            continue
            
        # Further split on double newlines (paragraph breaks)
        paragraphs = re.split(r'\n\s*\n', section)
        
        for para in paragraphs:
            para = para.strip()
            if para:
                result.append(para)
    
    return result


# ── Step 3: Core semantic chunking ────────────────────────────────────────

def semantic_chunk(text: str, threshold: float = 0.3, min_chunk_size: int = 2) -> list[str]:
    """
    Main chunking function. Two-pass approach:
    
    Pass 1: Split at hard structural boundaries (pages, paragraphs)
    Pass 2: Within each section, split further at semantic topic changes
    
    threshold: cosine similarity below this = new chunk
        Lower (0.2) = more, smaller chunks
        Higher (0.5) = fewer, larger chunks
        0.3 is a good default for academic/business documents
    
    min_chunk_size: minimum sentences per chunk
        Prevents single-sentence orphan chunks with no context
    """
    
    # Pass 1 — structural splits
    sections = find_hard_boundaries(text)
    
    all_chunks = []
    
    for section in sections:
        # Split section into sentences
        sentences = split_into_sentences(section)
        
        # Skip sections too short to meaningfully chunk
        if len(sentences) <= min_chunk_size:
            if section.strip():
                all_chunks.append(section.strip())
            continue
        
        # Embed all sentences at once (batching = faster)
        embeddings = model.encode(sentences).tolist()
        
        # Pass 2 — semantic splits within this section
        current_chunk = [sentences[0]]
        
        for i in range(1, len(sentences)):
            # Compare this sentence with the previous one
            similarity = cosine_similarity(embeddings[i-1], embeddings[i])
            
            if similarity < threshold:
                # Topic changed — close current chunk, start new one
                # But only if current chunk meets minimum size
                if len(current_chunk) >= min_chunk_size:
                    all_chunks.append(' '.join(current_chunk))
                    current_chunk = [sentences[i]]
                else:
                    # Chunk too small — absorb this sentence anyway
                    # Better a slightly off-topic sentence than an orphan chunk
                    current_chunk.append(sentences[i])
            else:
                # Same topic — keep building this chunk
                current_chunk.append(sentences[i])
        
        # Don't forget the last chunk
        if current_chunk:
            all_chunks.append(' '.join(current_chunk))
    
    # Final cleanup — remove any empty chunks
    all_chunks = [c.strip() for c in all_chunks if len(c.strip()) > 20]
    
    return all_chunks


# ── Fallback: original fixed chunking ────────────────────────────────────
# Kept for documents where semantic chunking fails (very short text, etc.)

def fixed_chunk(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """
    Original Phase 1 chunker. Used as fallback only.
    """
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if end < len(text):
            last_space = chunk.rfind(' ')
            if last_space != -1:
                end = start + last_space
                chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk.strip())
        start = end - overlap
    return chunks
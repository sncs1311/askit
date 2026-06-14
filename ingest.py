from entity_graph import entity_graph, extract_entities
from structured_parser import parse_excel, parse_csv, parse_json, parse_xml
from bm25_index import bm25_index
from chunker import semantic_chunk, fixed_chunk
import pdfplumber
import uuid
from sentence_transformers import SentenceTransformer
import chromadb
import os
import re

model = SentenceTransformer("all-MiniLM-L6-v2")

client = chromadb.PersistentClient(path="./chroma_store")
collection = client.get_or_create_collection(name="documents")

def ingest_pdf(file_path: str, filename: str) -> dict:
    all_text = ""
    page_count = 0

    with pdfplumber.open(file_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text:
                all_text += f"\n[Page {page_num + 1}]\n{text}"
                page_count += 1

    if not all_text.strip():
        return {"error": "No text could be extracted. PDF may be scanned — OCR coming in Phase 10."}

    # Detect if this looks like a resume/structured doc
    # If so, use section-aware chunking instead of semantic
    if is_structured_document(all_text):
        chunks = section_aware_chunk(all_text)
        chunking_method = "section_aware"
    else:
        try:
            chunks = semantic_chunk(all_text)
            chunking_method = "semantic" if len(chunks) >= 3 else "fixed_fallback"
            if len(chunks) < 3:
                chunks = fixed_chunk(all_text)
        except Exception as e:
            print(f"Semantic chunking failed: {e}")
            chunks = fixed_chunk(all_text)
            chunking_method = "fixed_fallback"

    # NEW — Phase 2: semantic chunking with fixed fallback
    try:
        chunks = semantic_chunk(all_text)

        # Safety net: if semantic chunking returns too few chunks
        # (can happen with very short or poorly formatted PDFs)
        if len(chunks) < 3:
            chunks = fixed_chunk(all_text)
            chunking_method = "fixed_fallback"
        else:
            chunking_method = "semantic"

    except Exception as e:
        # If semantic chunking crashes on weird input, fall back gracefully
        print(f"Semantic chunking failed: {e}. Using fixed chunking.")
        chunks = fixed_chunk(all_text)
        chunking_method = "fixed_fallback"
    embeddings = model.encode(chunks).tolist()

    ids = [str(uuid.uuid4()) for _ in chunks]
    metadatas = [
        {"filename": filename, "chunk_index": i, "total_chunks": len(chunks)}
        for i, _ in enumerate(chunks)
    ]

    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=chunks,
        metadatas=metadatas
    )

    # Index the same chunks in BM25 for keyword search
    bm25_index.add(chunks, metadatas)

    # ── Phase 6: entity extraction → graph ───────────────────────
    # Extract entities from each chunk and add to knowledge graph
    for i, (chunk, chunk_id) in enumerate(zip(chunks, ids)):
        entities = extract_entities(chunk, chunk_id, filename)
        entity_graph.add_chunk_entities(entities)

    return {
        "filename": filename,
        "pages_processed": page_count,
        "chunks_stored": len(chunks),
        "chunking_method": chunking_method
    }

# File extension → parser mapping
STRUCTURED_EXTENSIONS = {
    '.xlsx': parse_excel,
    '.xls': parse_excel,
    '.csv': parse_csv,
    '.json': parse_json,
    '.xml': parse_xml,
}

def ingest_structured(file_path: str, filename: str) -> dict:
    """
    Route structured files to their correct parser.
    Returns ingestion summary — no ChromaDB involved.
    """
    ext = os.path.splitext(filename)[1].lower()
    parser = STRUCTURED_EXTENSIONS.get(ext)

    if not parser:
        return {"error": f"Unsupported structured format: {ext}"}

    return parser(file_path, filename)

def is_structured_document(text: str) -> bool:
    """
    Detect if document is structured (resume, report with sections)
    rather than flowing prose (research paper, book chapter).
    
    Structured docs have short lines, section headers, bullet points.
    These need section-aware chunking, not semantic chunking.
    """
    lines = text.split('\n')
    if not lines:
        return False

    # Count short lines (typical of resumes, structured docs)
    short_lines = sum(1 for l in lines if 0 < len(l.strip()) < 60)
    short_line_ratio = short_lines / len(lines)

    # Count bullet indicators
    bullet_lines = sum(1 for l in lines if l.strip().startswith(('•', '-', '*', '·')))

    # Count ALL CAPS lines (section headers)
    caps_lines = sum(1 for l in lines if l.strip().isupper() and len(l.strip()) > 2)

    # If >40% short lines OR many bullets OR caps headers → structured doc
    return short_line_ratio > 0.4 or bullet_lines > 5 or caps_lines > 2


def section_aware_chunk(text: str) -> list[str]:
    """
    Chunk by detecting section headers rather than semantic similarity.
    
    Detects headers by:
    - ALL CAPS lines (SUMMARY, PROJECTS, EDUCATION)
    - Title Case short lines followed by content
    - Lines ending with colon
    
    Each section becomes one or more chunks.
    Content within a section stays together.
    """
    lines = text.split('\n')
    chunks = []
    current_section_lines = []
    current_header = ""

    # Common resume/report section header patterns
    header_pattern = re.compile(
        r'^(SUMMARY|EXPERIENCE|EDUCATION|SKILLS|PROJECTS|TECHNICAL|'
        r'ACHIEVEMENTS|CERTIFICATIONS|AWARDS|PUBLICATIONS|REFERENCES|'
        r'OBJECTIVE|PROFILE|WORK EXPERIENCE|TECHNICAL SKILLS|'
        r'PERSONAL PROJECTS|INTERNSHIP|EXTRA.CURRICULAR)',
        re.IGNORECASE
    )

    def flush_section():
        """Save current section as chunk(s)."""
        if not current_section_lines:
            return

        section_text = '\n'.join(current_section_lines).strip()
        if not section_text:
            return

        # If section is short enough, keep as one chunk
        if len(section_text) <= 800:
            if current_header:
                chunks.append(f"{current_header}\n{section_text}")
            else:
                chunks.append(section_text)
        else:
            # Long section — split into sub-chunks of ~400 chars
            # but never split mid-bullet-point
            sub_chunks = split_section_into_subchunks(
                section_text, current_header
            )
            chunks.extend(sub_chunks)

    for line in lines:
        stripped = line.strip()

        # Detect section header
        is_header = (
            header_pattern.match(stripped) or
            (stripped.isupper() and 3 < len(stripped) < 40) or
            (stripped.endswith(':') and len(stripped) < 40 and stripped[0].isupper())
        )

        if is_header:
            # Save previous section
            flush_section()
            # Start new section
            current_header = stripped
            current_section_lines = []
        else:
            current_section_lines.append(line)

    # Don't forget the last section
    flush_section()

    # Filter empty chunks
    chunks = [c.strip() for c in chunks if len(c.strip()) > 20]
    return chunks


def split_section_into_subchunks(text: str, header: str, max_size: int = 400) -> list[str]:
    """
    Split a long section into sub-chunks at bullet point boundaries.
    Never splits in the middle of a bullet point.
    """
    # Split at bullet points
    bullet_pattern = re.compile(r'\n(?=\s*[•\-\*·])')
    parts = bullet_pattern.split(text)

    sub_chunks = []
    current = f"{header}\n" if header else ""

    for part in parts:
        if len(current) + len(part) <= max_size:
            current += part + '\n'
        else:
            if current.strip():
                sub_chunks.append(current.strip())
            current = f"{header} (continued)\n{part}\n"

    if current.strip():
        sub_chunks.append(current.strip())

    return sub_chunks
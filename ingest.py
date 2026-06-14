from structured_parser import parse_excel, parse_csv, parse_json, parse_xml
from bm25_index import bm25_index
from chunker import semantic_chunk, fixed_chunk
import pdfplumber
import uuid
from sentence_transformers import SentenceTransformer
import chromadb
import os

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
import pdfplumber
import uuid
from sentence_transformers import SentenceTransformer
import chromadb

model = SentenceTransformer("all-MiniLM-L6-v2")

client = chromadb.PersistentClient(path="./chroma_store")
collection = client.get_or_create_collection(name="documents")


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
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

    chunks = chunk_text(all_text)
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

    return {
        "filename": filename,
        "pages_processed": page_count,
        "chunks_stored": len(chunks)
    }
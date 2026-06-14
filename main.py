from entity_graph import entity_graph
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bm25_index import bm25_index
import shutil
import os
import chromadb

from ingest import (
    ingest_pdf,
    ingest_structured,
    ingest_document,
    ingest_pptx,
    STRUCTURED_EXTENSIONS,
    DOCUMENT_EXTENSIONS,
    PPTX_EXTENSIONS
)
from retriever import retrieve_with_routing
from generator import generate_answer

client = chromadb.PersistentClient(path="./chroma_store")
collection = client.get_or_create_collection("documents")

app = FastAPI(title="OmniRAG", version="0.1.0 — Phase 1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("uploads", exist_ok=True)

# All supported extensions
PDF_EXTENSIONS = {'.pdf'}
STRUCTURED_EXTS = set(STRUCTURED_EXTENSIONS.keys())
DOCUMENT_EXTS = set(DOCUMENT_EXTENSIONS.keys())
PPTX_EXTS = PPTX_EXTENSIONS

@app.get("/")
def health_check():
    return {"status": "OmniRAG is running", "phase": 1}


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    Accepts PDF and structured data files.
    Routes each to the correct ingestion pipeline.
    """
    filename = file.filename
    ext = os.path.splitext(filename)[1].lower()

    # Validate extension
    all_supported = PDF_EXTENSIONS | STRUCTURED_EXTS | DOCUMENT_EXTS | PPTX_EXTS
    if ext not in all_supported:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Supported: {sorted(all_supported)}"
        )

    # Save temporarily
    file_path = f"uploads/{filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Route to correct pipeline
    try:
        if ext == '.pdf':
            result = ingest_pdf(file_path, filename)
        elif ext in STRUCTURED_EXTS:
            result = ingest_structured(file_path, filename)
        elif ext in PPTX_EXTS:
            result = ingest_pptx(file_path, filename)
        else:
            result = ingest_document(file_path, filename)
    finally:
        # Always clean up — even if ingestion fails
        if os.path.exists(file_path):
            os.remove(file_path)

    return result


class QueryRequest(BaseModel):
    question: str
    n_results: int = 5


@app.post("/query")
def query_documents(request: QueryRequest):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    # retrieve_with_routing handles both SQL and vector paths
    return retrieve_with_routing(request.question, request.n_results)

@app.get("/graph")
def get_graph():
    """
    Returns the full entity knowledge graph.
    Used by the React UI to visualise entity relationships.
    """
    return entity_graph.get_entity_summary()

@app.delete("/clear/documents")
def clear_documents_only():
    import os
    from bm25_index import BM25_INDEX_PATH

    global collection, client

    try:
        # Delete and immediately recreate
        client.delete_collection("documents")
        collection = client.get_or_create_collection("documents")
        
        # Also update the collection reference in retriever and ingest
        import retriever
        import ingest
        retriever.collection = collection
        ingest.collection = collection

    except Exception as e:
        return {"error": f"ChromaDB clear failed: {e}"}

    if os.path.exists(BM25_INDEX_PATH):
        os.remove(BM25_INDEX_PATH)
    bm25_index.corpus = []
    bm25_index.chunks = []
    bm25_index.bm25 = None

    return {"message": "Document data cleared. Structured data untouched."}


@app.delete("/clear")
def clear_all_data():
    import os
    from bm25_index import BM25_INDEX_PATH
    from entity_graph import GRAPH_PATH
    from structured_parser import SQLITE_DB_PATH

    global collection, client

    results = {}

    try:
        client.delete_collection("documents")
        collection = client.get_or_create_collection("documents")

        import retriever
        import ingest
        retriever.collection = collection
        ingest.collection = collection
        results["chromadb"] = "cleared"
    except Exception as e:
        results["chromadb"] = f"error: {e}"

    try:
        if os.path.exists(BM25_INDEX_PATH):
            os.remove(BM25_INDEX_PATH)
        bm25_index.corpus = []
        bm25_index.chunks = []
        bm25_index.bm25 = None
        results["bm25"] = "cleared"
    except Exception as e:
        results["bm25"] = f"error: {e}"

    try:
        if os.path.exists(SQLITE_DB_PATH):
            os.remove(SQLITE_DB_PATH)
        results["sqlite"] = "cleared"
    except Exception as e:
        results["sqlite"] = f"error: {e}"

    try:
        if os.path.exists(GRAPH_PATH):
            os.remove(GRAPH_PATH)
        entity_graph.graph.clear()
        results["entity_graph"] = "cleared"
    except Exception as e:
        results["entity_graph"] = f"error: {e}"

    return {"message": "All data cleared.", "details": results}

@app.delete("/clear/structured")
def clear_structured_only():
    """Clear only CSV/Excel data from SQLite."""
    import os
    from structured_parser import SQLITE_DB_PATH
    
    if os.path.exists(SQLITE_DB_PATH):
        os.remove(SQLITE_DB_PATH)
        return {"message": "Structured data cleared. PDF/text data untouched."}
    return {"message": "No structured data found."}

@app.get("/debug/chunks")
def debug_chunks():
    """Show what's actually stored in ChromaDB — first 5 chunks."""
    results = collection.get(
        limit=5,
        include=["documents", "metadatas"]
    )
    return {
        "total_chunks": collection.count(),
        "sample_chunks": [
            {
                "text": doc[:300],
                "metadata": meta
            }
            for doc, meta in zip(
                results["documents"],
                results["metadatas"]
            )
        ]
    }

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    filename = file.filename
    ext = os.path.splitext(filename)[1].lower()

    all_supported = PDF_EXTENSIONS | STRUCTURED_EXTS | DOCUMENT_EXTS

    if ext not in all_supported:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Supported: {sorted(all_supported)}"
        )

    file_path = f"uploads/{filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        if ext == '.pdf':
            result = ingest_pdf(file_path, filename)
        elif ext in STRUCTURED_EXTS:
            result = ingest_structured(file_path, filename)
        else:
            result = ingest_document(file_path, filename)
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

    return result
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import shutil
import os

from ingest import ingest_pdf, ingest_structured, STRUCTURED_EXTENSIONS
from retriever import retrieve_with_routing
from generator import generate_answer

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
    all_supported = PDF_EXTENSIONS | STRUCTURED_EXTS
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
        else:
            result = ingest_structured(file_path, filename)
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
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import shutil
import os

from ingest import ingest_pdf
from retriever import retrieve
from generator import generate_answer

app = FastAPI(title="OmniRAG", version="0.1.0 — Phase 1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("uploads", exist_ok=True)


@app.get("/")
def health_check():
    return {"status": "OmniRAG is running", "phase": 1}


@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files accepted in Phase 1")

    file_path = f"uploads/{file.filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    result = ingest_pdf(file_path, file.filename)
    os.remove(file_path)
    return result


class QueryRequest(BaseModel):
    question: str
    n_results: int = 5


@app.post("/query")
def query_documents(request: QueryRequest):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    chunks = retrieve(request.question, request.n_results)

    if not chunks:
        return {"answer": "No documents uploaded yet.", "sources": []}

    return generate_answer(request.question, chunks)
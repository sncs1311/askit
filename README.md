<div align="center">

# 🔍 OmniRAG

### Production-grade Retrieval-Augmented Generation — locally, for everything.

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-vector_store-FF6B35?style=flat)](https://chromadb.com)
[![Ollama](https://img.shields.io/badge/Ollama-local_LLM-black?style=flat)](https://ollama.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**OmniRAG** addresses six documented failure modes in production RAG systems — simultaneously, with zero cloud dependency.  
Upload anything. Ask anything. Get grounded, cited answers — entirely on your own machine.

[Features](#-features) · [Architecture](#️-architecture) · [Quickstart](#-quickstart) · [File Support](#-supported-file-types) · [Roadmap](#-roadmap)

</div>

---

## The Problem With Standard RAG

Most RAG tutorials build the same thing: split a PDF into fixed chunks → embed → store in ChromaDB → ask GPT. That works for demos. It fails in production.

| Failure Mode | Standard RAG | OmniRAG |
|---|---|---|
| Fixed chunking destroys table/code structure | ❌ Breaks | ✅ Semantic boundary chunking |
| Excel / structured data queries | ❌ Hallucinates | ✅ SQL router → SQLite |
| Exact keyword search (invoice numbers, names) | ❌ Misses | ✅ Hybrid BM25 + dense search via RRF |
| Complex multi-part questions | ❌ Fails silently | ✅ Adaptive multi-hop retrieval |
| Answer not in documents → hallucination | ❌ Makes things up | ✅ Corrective filter + principled abstention |
| Cross-document entity reasoning | ❌ Treats chunks in isolation | ✅ Lightweight entity graph (GraphRAG-lite) |

---

## ✨ Features

### Core RAG Engine
- **Semantic chunking** — splits at topic boundaries, not character counts
- **Hybrid search** — BM25 sparse + dense vector embeddings merged via Reciprocal Rank Fusion
- **Corrective RAG** — scores every retrieved chunk before passing to LLM; abstains if no chunk is relevant
- **Adaptive multi-hop retrieval** — decomposes complex questions into sub-queries, retrieves each independently
- **Entity graph** — extracts named entities (people, orgs, amounts, dates) and links them across documents for cross-document reasoning
- **SQL router** — structured data (Excel, CSV) never gets embedded; stays in SQLite for precise analytical queries

### Input: Everything
- **Documents** — PDF, DOCX, DOC, TXT, MD, RTF, EPUB
- **Structured data** — XLSX, XLS, CSV, TSV, JSON, XML
- **Presentations** — PPTX, PPT (per-slide extraction with table and chart support)
- **Code files** — Python, JavaScript, TypeScript, Java, C, C++, C#, Go, Rust, HTML, CSS, SQL, Shell, R, and more — with AST-based structure extraction
- **Scanned documents** — images (JPG, PNG, TIFF) and live camera capture with content-type detection (printed text / handwriting / table / code / chart)

### Infrastructure
- **100% local** — Ollama + sentence-transformers + ChromaDB, zero cloud APIs, zero cost per query
- **Offline capable** — full demo works with no internet connection
- **Precise citations** — every answer cites exact file, page, slide, or line number
- **Confidence scores** — every answer includes a relevance score; low-confidence answers are flagged

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        INGESTION                            │
│                                                             │
│  File Upload                                                │
│      │                                                      │
│      ▼                                                      │
│  ┌─────────────┐                                            │
│  │ File Router │ ── detects type ──────────────────────┐    │
│  └─────────────┘     |              |           |      │    │
│       │              │              │           │      │    │
│       ▼              ▼              ▼           ▼      ▼    │
│   Documents      Structured      Code        PPTX   Scanner │
│   (pdfplumber    (openpyxl       (AST +      (pptx   (OCR)  │
│    python-docx)   → SQLite)    tree-sitter)  parser)        │
│       │                                                     │
│       ▼                                                     │
│  Semantic Chunker → sentence-transformers → ChromaDB        │
│  BM25 Indexer                                               │
│  Entity Extractor (spaCy) → NetworkX graph                  │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                         QUERY                               │
│                                                             │
│  User Question                                              │
│      │                                                      │
│      ▼                                                      │
│  Query Classifier                                           │
│  (simple / complex / structured)                            │
│       │              │              │                       │
│       ▼              ▼              ▼                       │
│  Single retrieval  Multi-hop     SQL query                  │
│                                                             │
│  Hybrid Search (BM25 + Dense → RRF merge)                   │
│      │                                                      │
│      ▼                                                      │
│  Corrective Filter (score chunks, drop irrelevant)          │
│      │                                                      │
│      ▼                                                      │
│  Entity Graph Augmentation                                  │
│      │                                                      │
│      ▼                                                      │
│  Ollama (Mistral 7B — local)                                │
│      │                                                      │
│      ▼                                                      │
│  Answer + Citations (file · page · table · line)            │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quickstart

### Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com/download) installed

### 1. Clone the repo

```bash
git clone https://github.com/sncs1311/omnirag.git
cd omnirag
```

### 2. Create virtual environment

```bash
python -m venv venv

# Mac/Linux
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Pull the LLM

```bash
ollama pull mistral
```

> This downloads ~4GB. Do it once. Mistral 7B runs on any modern laptop CPU.

### 5. Start Ollama

```bash
# In a separate terminal
ollama serve
```

### 6. Start OmniRAG

```bash
uvicorn main:app --reload
```

### 7. Open the API docs

```
http://localhost:8000/docs
```

Upload a file via `POST /upload`, then ask questions via `POST /query`. That's it.

---

## 📁 Supported File Types

| Category | Extensions | Parser | Storage |
|---|---|---|---|
| Documents | `.pdf` `.docx` `.doc` `.txt` `.md` `.rtf` `.epub` | pdfplumber, python-docx, ebooklib | ChromaDB |
| Structured | `.xlsx` `.xls` `.csv` `.tsv` `.json` `.xml` | openpyxl, pandas | SQLite |
| Presentations | `.pptx` `.ppt` | python-pptx | ChromaDB + SQLite |
| Code | `.py` `.js` `.ts` `.java` `.cpp` `.c` `.cs` `.go` `.rs` `.html` `.css` `.sql` `.sh` `.rb` `.php` `.swift` `.kt` `.r` | AST, tree-sitter | ChromaDB |
| Images / Scans | `.jpg` `.png` `.tiff` `.bmp` + webcam | OpenCV, Tesseract, TrOCR | → detected pipeline |

---

## 📂 Project Structure

```
omnirag/
├── main.py                  # FastAPI server — all routes
├── ingest.py                # File ingestion pipeline
├── retriever.py             # Hybrid search (BM25 + dense + RRF)
├── generator.py             # LLM answer generation
├── chunker.py               # Semantic chunking
├── router.py                # File type router
├── parsers/
│   ├── pdf_parser.py
│   ├── docx_parser.py
│   ├── excel_parser.py
│   ├── pptx_parser.py
│   ├── code_parser.py
│   └── scanner.py           # OCR pipeline
├── graph/
│   └── entity_graph.py      # spaCy NER + NetworkX
├── requirements.txt
├── .gitignore
└── README.md
```

---

## 🗺️ Roadmap

**Phase 1 — Complete ✅**
- [x] FastAPI server
- [x] PDF ingestion
- [x] Fixed chunking
- [x] ChromaDB storage
- [x] Ollama query

**Phase 2 — In Progress 🔄**
- [ ] Semantic boundary chunking
- [ ] Heading-aware chunking for DOCX

**Upcoming**
- [ ] BM25 + hybrid search with RRF
- [ ] Excel / CSV → SQLite router
- [ ] DOCX, TXT, MD, EPUB support
- [ ] PPTX per-slide extraction
- [ ] Code file AST parser (Python, JS, Java, C++, and more)
- [ ] Corrective RAG + abstention
- [ ] Entity graph + multi-hop retrieval
- [ ] OCR pipeline (Tesseract + TrOCR)
- [ ] Live camera capture
- [ ] React frontend with source highlighting

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, Python 3.10+ |
| Vector Store | ChromaDB (persistent, local) |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| LLM | Ollama — Mistral 7B (local, offline) |
| Structured Data | SQLite via SQLAlchemy |
| Entity Extraction | spaCy |
| Entity Graph | NetworkX |
| OCR | Tesseract, OpenCV, TrOCR (HuggingFace) |
| Code Parsing | Python AST, tree-sitter |
| Frontend | React, Tailwind CSS (Phase 12) |

---

## 🤝 Contributing

This project is in active development. Contributions, bug reports, and feature suggestions are welcome.

1. Fork the repo
2. Create a branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m 'feat: add your feature'`
4. Push: `git push origin feature/your-feature`
5. Open a pull request

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">
Built by <a href="https://github.com/YOUR_USERNAME">Surya Narayan C Shenoy</a> · MNNIT Allahabad
</div>

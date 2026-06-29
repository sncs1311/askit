import time
import pdfplumber
from chunker import semantic_chunk

file_path = "C:/Users/mesur/test_pdf/Practical MLOps_ Operationalizing Machine Learning Models.pdf"

all_text = ""
with pdfplumber.open(file_path) as pdf:
    for i, page in enumerate(pdf.pages):
        text = page.extract_text()
        if text:
            all_text += f"\n[Page {i+1}]\n{text}"

print(f"Extracted {len(all_text)} characters")

t0 = time.time()
chunks = semantic_chunk(all_text)
elapsed = time.time() - t0

print(f"Chunked {len(all_text)} chars into {len(chunks)} chunks in {elapsed:.2f}s")
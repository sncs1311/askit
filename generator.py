import requests


def generate_answer(query: str, context_chunks: list[dict]) -> dict:
    context = ""
    for i, chunk in enumerate(context_chunks):
        context += f"\n[Source {i+1} — {chunk['filename']}]\n{chunk['text']}\n"

    prompt = f"""You are a precise document assistant. Answer the question using ONLY the provided context below.
If the answer is not present in the context, say exactly: "This information is not in the uploaded documents."
Do not use any knowledge outside the provided context.

CONTEXT:
{context}

QUESTION: {query}

ANSWER:"""

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "mistral",
            "prompt": prompt,
            "stream": False
        }
    )

    result = response.json()

    return {
        "answer": result["response"].strip(),
        "sources": [
            {
                "filename": chunk["filename"],
                "relevance_score": round(1 - chunk["distance"], 3)
            }
            for chunk in context_chunks
        ]
    }
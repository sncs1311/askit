import requests
from corrective_filter import compute_confidence, confidence_label

OLLAMA_URL = "http://localhost:11434/api/generate"


def generate_answer(query: str, context_chunks: list[dict]) -> dict:
    """
    Generate an answer from pre-filtered, scored chunks.

    Chunks arrive already filtered by corrective_filter.py.
    Confidence level affects how the prompt frames the answer.
    """

    # Compute confidence from chunk scores
    confidence = compute_confidence(context_chunks)
    conf_label = confidence_label(confidence)

    # Build context string — scored chunks sorted best-first
    context = ""
    for i, chunk in enumerate(context_chunks):
        score = chunk.get('relevance_score', 0.0)
        context += f"\n[Source {i+1} — {chunk['filename']} | relevance: {score}]\n{chunk['text']}\n"

    # Confidence-aware system instruction
    if conf_label == "high":
        confidence_instruction = "The context below strongly supports answering this question. Answer confidently."
    elif conf_label == "medium":
        confidence_instruction = "The context below partially addresses this question. Answer based on what is available and note if anything seems incomplete."
    else:
        confidence_instruction = "The context below may only partially address this question. Answer carefully, and clearly note any uncertainty."

    prompt = f"""You are a precise document assistant.
{confidence_instruction}

Answer using ONLY the provided context. Do not use outside knowledge.
If the answer is not present, say exactly: "This information is not in the uploaded documents."

CONTEXT:
{context}

QUESTION: {query}

ANSWER:"""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": "mistral", "prompt": prompt, "stream": False},
            timeout=60
        )
        answer = response.json()["response"].strip()

    except requests.exceptions.ConnectionError:
        answer = "Ollama is not running. Start it with: ollama serve"
    except Exception as e:
        answer = f"Generation failed: {str(e)}"

    return {
        "answer": answer,
        "confidence": confidence,
        "confidence_label": conf_label,
        "sources": [
            {
                "filename": chunk["filename"],
                "chunk_index": chunk.get("chunk_index", 0),
                "relevance_score": chunk.get("relevance_score", 0.0)
            }
            for chunk in context_chunks
        ]
    }
from entity_graph import entity_graph
from corrective_filter import filter_chunks, compute_confidence
from sql_router import try_sql_route
from sentence_transformers import SentenceTransformer
import chromadb
from bm25_index import bm25_index

model = SentenceTransformer("all-MiniLM-L6-v2")

client = chromadb.PersistentClient(path="./chroma_store")
collection = client.get_or_create_collection(name="documents")


# ── Reciprocal Rank Fusion ────────────────────────────────────────────────

def reciprocal_rank_fusion(
    vector_results: list[dict],
    bm25_results: list[dict],
    k: int = 60
) -> list[dict]:
    """
    Merge two ranked result lists without needing comparable scores.

    RRF formula: score += 1 / (k + rank)
    
    k=60 is the empirically optimal constant from the original paper
    (Cormack, Clarke, Buettcher 2009). It prevents very high-ranked
    results from dominating — smooths the influence of rank position.
    
    A chunk appearing at rank 1 in both lists scores higher than
    one appearing at rank 1 in one list and rank 50 in another.
    """
    rrf_scores = {}   # chunk_text → accumulated RRF score
    chunk_data = {}   # chunk_text → full chunk dict (for returning results)

    # Process vector search results
    for rank, chunk in enumerate(vector_results):
        key = chunk["text"]
        rrf_scores[key] = rrf_scores.get(key, 0) + 1 / (k + rank + 1)
        chunk_data[key] = chunk

    # Process BM25 results — accumulate into same scores dict
    for rank, chunk in enumerate(bm25_results):
        key = chunk["text"]
        rrf_scores[key] = rrf_scores.get(key, 0) + 1 / (k + rank + 1)
        # If this chunk also appeared in vector results, keep that version
        # (it has distance metadata). Otherwise use BM25 version.
        if key not in chunk_data:
            chunk_data[key] = chunk

    # Sort by accumulated RRF score — highest first
    sorted_keys = sorted(rrf_scores.keys(), key=lambda k: rrf_scores[k], reverse=True)

    # Build final result list with RRF scores attached
    merged = []
    for key in sorted_keys:
        chunk = chunk_data[key].copy()
        chunk["rrf_score"] = round(rrf_scores[key], 5)
        merged.append(chunk)

    return merged


# ── Vector search ─────────────────────────────────────────────────────────

def vector_search(query: str, n_results: int = 10) -> list[dict]:
    """
    Dense embedding search via ChromaDB.
    Finds chunks that are semantically similar to the query.
    """
    query_embedding = model.encode(query).tolist()

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(n_results, collection.count()),
        include=["documents", "metadatas", "distances"]
    )

    # collection.count() == 0 means no documents ingested yet
    if not results["documents"][0]:
        return []

    chunks = []
    for i, doc in enumerate(results["documents"][0]):
        chunks.append({
            "text": doc,
            "filename": results["metadatas"][0][i]["filename"],
            "chunk_index": results["metadatas"][0][i]["chunk_index"],
            "distance": results["distances"][0][i],
            # Convert distance to relevance score: 0 distance = 1.0 score
            "relevance_score": round(1 - results["distances"][0][i], 3)
        })

    return chunks


# ── Main retrieve function ────────────────────────────────────────────────

def retrieve(query: str, n_results: int = 5) -> list[dict]:
    """
    Hybrid retrieval: vector search + BM25, merged via RRF.
    
    We fetch 2x n_results from each search before merging.
    More candidates = RRF has better material to work with.
    After merging and deduplication, we trim to n_results.
    
    Falls back to vector-only if BM25 index is empty.
    """
    # Fetch more than needed from each — RRF needs candidates
    fetch_n = n_results * 2

    # Run both searches
    vec_results = vector_search(query, fetch_n)
    bm25_results = bm25_index.search(query, fetch_n)

    # If BM25 has nothing (no documents ingested yet) — vector only
    if not bm25_results:
        return vec_results[:n_results]

    # If ChromaDB has nothing — BM25 only (shouldn't happen but be safe)
    if not vec_results:
        return bm25_results[:n_results]

    # Merge with Reciprocal Rank Fusion
    merged = reciprocal_rank_fusion(vec_results, bm25_results)

    # Return top n_results after merging
    return merged[:n_results]

def retrieve_with_routing(query: str, n_results: int = 5) -> dict:

    # Step 0: document-level questions
    from sql_router import describe_structured_data
    desc_result = describe_structured_data(query)
    if desc_result:
        return desc_result

    # Step 1: SQL route
    sql_result = try_sql_route(query)
    if sql_result:
        return sql_result

    # Step 2: empty collection check
    if collection.count() == 0:
        return {
            "answer": "This information is not in the uploaded documents.",
            "confidence": 0.0,
            "confidence_label": "no_support",
            "sources": [],
            "route": "vector_abstained"
        }

    # Step 3: hybrid retrieval
    raw_chunks = retrieve(query, max(n_results*3, 15))

    # ── Step 4: graph augmentation (NEW) ─────────────────────────────────
    # Find chunk_ids connected to query entities in the knowledge graph
    graph_chunk_ids = entity_graph.query_graph(query)

    if graph_chunk_ids:
        # Fetch those chunks from ChromaDB
        graph_chunks = fetch_chunks_by_ids(graph_chunk_ids)

        # Merge with hybrid results — deduplicate by text
        seen_texts = {c["text"] for c in raw_chunks}
        for gc in graph_chunks:
            if gc["text"] not in seen_texts:
                raw_chunks.append(gc)
                seen_texts.add(gc["text"])
    # ── End graph augmentation ────────────────────────────────────────────

    # Step 5: corrective filter
    filtered_chunks = filter_chunks(raw_chunks, query)

    # Step 6: abstention
    if not filtered_chunks:
        return {
            "answer": "This information is not in the uploaded documents.",
            "confidence": 0.0,
            "confidence_label": "no_support",
            "sources": [],
            "route": "vector_abstained"
        }

    # Step 7: trim + generate
    filtered_chunks = filtered_chunks[:n_results]
    from generator import generate_answer
    result = generate_answer(query, filtered_chunks)
    result["route"] = "vector+graph"
    return result

def fetch_chunks_by_ids(chunk_ids: list[str]) -> list[dict]:
    """
    Fetch specific chunks from ChromaDB by their IDs.
    Used to retrieve graph-recommended chunks.
    """
    if not chunk_ids:
        return []

    try:
        results = collection.get(
            ids=chunk_ids,
            include=["documents", "metadatas"]
        )
    except Exception:
        return []

    chunks = []
    for i, doc in enumerate(results["documents"]):
        chunks.append({
            "text": doc,
            "filename": results["metadatas"][i]["filename"],
            "chunk_index": results["metadatas"][i]["chunk_index"],
            # Graph-retrieved chunks get a neutral distance
            # Corrective filter will score them properly
            "distance": 0.4,
            "source": "entity_graph"
        })

    return chunks
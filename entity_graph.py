import spacy
import networkx as nx
import json
import os
from itertools import combinations

GRAPH_PATH = "./entity_graph.json"

# Entity types worth tracking for business/academic documents
USEFUL_ENTITY_TYPES = {
    'PERSON', 'ORG', 'GPE', 'MONEY', 'DATE',
    'EVENT', 'PRODUCT', 'LAW', 'NORP'
}

# Load spaCy — once at module level
nlp = spacy.load("en_core_web_sm")


# ── Entity extraction ─────────────────────────────────────────────────────

def normalise_entity(text: str) -> str:
    """
    Normalise entity text for consistent graph nodes.
    'Apple Inc.', 'APPLE', 'Apple' → 'apple inc' / 'apple'
    Lowercase + strip punctuation + collapse whitespace.
    """
    text = text.lower().strip()
    text = text.rstrip('.,;:')
    text = ' '.join(text.split())
    return text


def extract_entities(text: str, chunk_id: str, filename: str) -> list[dict]:
    """
    Run spaCy NER on chunk text.
    Returns list of entity dicts with normalised text, type, and source info.

    Cap at 10 entities per chunk to prevent combinatorial explosion
    when building edges.
    """
    doc = nlp(text[:5000])  # spaCy has a token limit — truncate long chunks

    seen = set()
    entities = []

    for ent in doc.ents:
        if ent.label_ not in USEFUL_ENTITY_TYPES:
            continue

        normalised = normalise_entity(ent.text)

        # Skip very short entities — usually noise
        if len(normalised) < 2:
            continue

        # Deduplicate within this chunk
        if normalised in seen:
            continue

        seen.add(normalised)
        entities.append({
            "text": normalised,
            "original": ent.text,
            "type": ent.label_,
            "chunk_id": chunk_id,
            "filename": filename
        })

        # Cap at 10 entities per chunk
        if len(entities) >= 10:
            break

    return entities


# ── Graph class ───────────────────────────────────────────────────────────

class EntityGraph:
    """
    Wraps a NetworkX undirected graph with persistence.

    Nodes: entities (normalised text)
    Node attributes: type, chunk_ids (list), filenames (list)

    Edges: co-occurrence in same chunk
    Edge attributes: weight (number of shared chunks)
    """

    def __init__(self):
        self.graph = nx.Graph()

    def add_chunk_entities(self, entities: list[dict]):
        """
        Add entities from one chunk to the graph.
        Creates nodes if new, updates existing nodes.
        Creates edges between all entity pairs in this chunk.
        """
        if not entities:
            return

        for ent in entities:
            node_id = ent["text"]

            if node_id not in self.graph:
                # New entity — create node
                self.graph.add_node(
                    node_id,
                    type=ent["type"],
                    chunk_ids=[ent["chunk_id"]],
                    filenames=[ent["filename"]]
                )
            else:
                # Existing entity — append source info
                node_data = self.graph.nodes[node_id]

                if ent["chunk_id"] not in node_data["chunk_ids"]:
                    node_data["chunk_ids"].append(ent["chunk_id"])

                if ent["filename"] not in node_data["filenames"]:
                    node_data["filenames"].append(ent["filename"])

        # Create edges between every pair of entities in this chunk
        # They co-occurred → they're related
        entity_texts = [e["text"] for e in entities]

        for text_a, text_b in combinations(entity_texts, 2):
            if self.graph.has_edge(text_a, text_b):
                # Strengthen existing edge
                self.graph[text_a][text_b]["weight"] += 1
            else:
                # New relationship
                self.graph.add_edge(text_a, text_b, weight=1)

        self.save()

    def query_graph(self, query_text: str, max_depth: int = 2) -> list[str]:
        """
        Extract entities from query.
        Find them in graph.
        Return chunk_ids reachable within max_depth hops.

        These chunk_ids supplement hybrid search results —
        they find relevant chunks that share entities with the query.
        """
        # Extract entities from the query itself
        query_doc = nlp(query_text[:1000])
        query_entities = set()

        for ent in query_doc.ents:
            if ent.label_ in USEFUL_ENTITY_TYPES:
                normalised = normalise_entity(ent.text)
                if len(normalised) >= 2:
                    query_entities.add(normalised)

        if not query_entities:
            return []  # No entities in query — graph can't help

        # Collect chunk_ids from graph traversal
        relevant_chunk_ids = set()
        visited_nodes = set()

        # BFS up to max_depth hops
        current_frontier = set()

        for entity in query_entities:
            if entity in self.graph:
                current_frontier.add(entity)
                # Collect chunks from directly matched entities
                for chunk_id in self.graph.nodes[entity]["chunk_ids"]:
                    relevant_chunk_ids.add(chunk_id)

        # Expand to neighbours up to max_depth
        for depth in range(max_depth):
            if not current_frontier:
                break

            next_frontier = set()
            for node in current_frontier:
                if node in visited_nodes:
                    continue
                visited_nodes.add(node)

                # Get neighbours sorted by edge weight (strongest first)
                neighbours = sorted(
                    self.graph.neighbors(node),
                    key=lambda n: self.graph[node][n]["weight"],
                    reverse=True
                )

                # Take top 5 neighbours per node to keep focus
                for neighbour in neighbours[:5]:
                    if neighbour not in visited_nodes:
                        next_frontier.add(neighbour)
                        for chunk_id in self.graph.nodes[neighbour]["chunk_ids"]:
                            relevant_chunk_ids.add(chunk_id)

            current_frontier = next_frontier

        return list(relevant_chunk_ids)

    def get_entity_summary(self) -> dict:
        """
        Returns a summary of the graph for the /graph endpoint.
        Used by the React UI (Phase 12) to visualise the knowledge graph.
        """
        return {
            "total_entities": self.graph.number_of_nodes(),
            "total_relationships": self.graph.number_of_edges(),
            "entity_types": self._count_entity_types(),
            "most_connected": self._most_connected_entities(10),
            "nodes": [
                {
                    "id": node,
                    "type": data.get("type", "UNKNOWN"),
                    "filenames": data.get("filenames", []),
                    "chunk_count": len(data.get("chunk_ids", []))
                }
                for node, data in self.graph.nodes(data=True)
            ],
            "edges": [
                {"source": u, "target": v, "weight": d.get("weight", 1)}
                for u, v, d in self.graph.edges(data=True)
            ]
        }

    def _count_entity_types(self) -> dict:
        counts = {}
        for _, data in self.graph.nodes(data=True):
            t = data.get("type", "UNKNOWN")
            counts[t] = counts.get(t, 0) + 1
        return counts

    def _most_connected_entities(self, n: int) -> list[dict]:
        if self.graph.number_of_nodes() == 0:
            return []
        degrees = sorted(
            self.graph.degree(),
            key=lambda x: x[1],
            reverse=True
        )
        return [{"entity": node, "connections": deg} for node, deg in degrees[:n]]

    def save(self):
        """Persist graph to JSON."""
        data = nx.node_link_data(self.graph)
        with open(GRAPH_PATH, "w") as f:
            json.dump(data, f)

    def load(self):
        """Load graph from JSON if it exists."""
        if not os.path.exists(GRAPH_PATH):
            return
        with open(GRAPH_PATH, "r") as f:
            data = json.load(f)
        self.graph = nx.node_link_graph(data)


# ── Module-level singleton ────────────────────────────────────────────────
entity_graph = EntityGraph()
entity_graph.load()
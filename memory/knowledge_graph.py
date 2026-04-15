"""
L3 memory: entities, relationships, and facts as a graph.
"Manu → works_on → AERIS"
"RTX 4080 → has → 12GB VRAM"
This enables reasoning about facts, not just retrieving similar text.
"""

import json
from datetime import datetime

import networkx as nx
from loguru import logger

import config


GRAPH_PATH = config.DATA_DIR / "identity" / "knowledge_graph.json"


class KnowledgeGraph:
    def __init__(self):
        self.graph = nx.DiGraph()
        self._load()

    def add(self, subject: str, predicate: str, obj: str, confidence: float = 1.0):
        subject = subject.lower().strip()
        obj = obj.lower().strip()
        self.graph.add_edge(
            subject,
            obj,
            predicate=predicate,
            confidence=confidence,
            timestamp=datetime.now().isoformat(),
        )
        self._save()
        logger.debug(f"Graph: {subject} --[{predicate}]--> {obj}")

    def query(self, subject: str) -> list[dict]:
        subject = subject.lower().strip()
        if subject not in self.graph:
            return []
        results = []
        for _, target, data in self.graph.out_edges(subject, data=True):
            results.append({"subject": subject, "predicate": data["predicate"], "object": target})
        return results

    def find_path(self, source: str, target: str) -> list:
        try:
            return nx.shortest_path(self.graph, source.lower(), target.lower())
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []

    def as_context_string(self, entity: str) -> str:
        facts = self.query(entity)
        if not facts:
            return ""
        return "\n".join([f"{f['subject']} {f['predicate']} {f['object']}" for f in facts])

    def _save(self):
        GRAPH_PATH.parent.mkdir(parents=True, exist_ok=True)
        data = nx.node_link_data(self.graph)
        with open(GRAPH_PATH, "w") as f:
            json.dump(data, f, indent=2)

    def _load(self):
        if GRAPH_PATH.exists():
            with open(GRAPH_PATH) as f:
                data = json.load(f)
            self.graph = nx.node_link_graph(data)
            logger.info(f"Knowledge graph loaded: {self.graph.number_of_edges()} facts")


knowledge_graph = KnowledgeGraph()
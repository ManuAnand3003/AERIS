import chromadb
from chromadb.config import Settings
from datetime import datetime

from loguru import logger

import config
from memory.embeddings import get_embedding_function


class EpisodicMemory:
    """L2 memory — every conversation, semantically searchable, forever."""

    def __init__(self):
        backend = config.MEMORY_CONFIG.get("embedding_backend", "hash_local")
        embedding_fn = get_embedding_function(backend, config.MEMORY_CONFIG.get("embedding_model", ""))
        convo_collection_name = "conversations_local" if backend == "hash_local" else "conversations"
        facts_collection_name = "user_facts_local" if backend == "hash_local" else "user_facts"

        self.client = chromadb.PersistentClient(
            path=str(config.MEMORY_DB_DIR),
            settings=Settings(anonymized_telemetry=False),
        )
        self.conversations = self.client.get_or_create_collection(
            name=convo_collection_name,
            embedding_function=embedding_fn,
        )
        self.facts = self.client.get_or_create_collection(
            name=facts_collection_name,
            embedding_function=embedding_fn,
        )
        logger.info(f"Episodic memory embedding backend: {backend}")
        logger.info(f"Episodic memory: {self.conversations.count()} conversations, {self.facts.count()} facts")

    def store(self, role: str, content: str, metadata: dict = None):
        timestamp = datetime.now().isoformat()
        meta = {"role": role, "timestamp": timestamp, **(metadata or {})}
        self.conversations.add(
            documents=[content],
            metadatas=[meta],
            ids=[f"{role}_{timestamp}_{hash(content) % 10000}"],
        )

    def recall(self, query: str, n: int = 5) -> list[dict]:
        if self.conversations.count() == 0:
            return []
        try:
            results = self.conversations.query(query_texts=[query], n_results=min(n, self.conversations.count()))
            return [
                {"content": doc, "metadata": meta, "relevance": 1 - dist}
                for doc, meta, dist in zip(
                    results["documents"][0],
                    results["metadatas"][0],
                    results["distances"][0],
                )
            ]
        except Exception as e:
            logger.error(f"Memory recall error: {e}")
            return []

    def store_fact(self, fact: str, category: str = "general", importance: int = 5):
        timestamp = datetime.now().isoformat()
        self.facts.add(
            documents=[fact],
            metadatas=[{"category": category, "importance": importance, "timestamp": timestamp}],
            ids=[f"fact_{timestamp}_{hash(fact) % 10000}"],
        )
        logger.info(f"Fact stored [{category}]: {fact[:60]}")

    def recall_facts(self, query: str = None, n: int = 10) -> list[dict]:
        if self.facts.count() == 0:
            return []
        try:
            if query:
                results = self.facts.query(query_texts=[query], n_results=min(n, self.facts.count()))
                docs = results["documents"][0]
                metas = results["metadatas"][0]
            else:
                results = self.facts.get(limit=n)
                docs = results["documents"]
                metas = results["metadatas"]
            return [{"content": d, "metadata": m} for d, m in zip(docs, metas)]
        except Exception as e:
            logger.error(f"Fact recall error: {e}")
            return []

    def get_context_string(self, query: str) -> str:
        memories = self.recall(query, n=4)
        facts = self.recall_facts(query, n=3)
        parts = []
        if memories:
            parts.append("Relevant past:")
            for m in memories:
                parts.append(f"  [{m['metadata'].get('role','?')}] {m['content'][:150]}")
        if facts:
            parts.append("Known about Manu:")
            for f in facts:
                parts.append(f"  - {f['content']}")
        return "\n".join(parts)

    @property
    def stats(self):
        return {"conversations": self.conversations.count(), "facts": self.facts.count()}


episodic = EpisodicMemory()
"""
AERIS Memory System
Forever memory using ChromaDB vector database and semantic search
"""

import chromadb
from chromadb.config import Settings
from datetime import datetime
import json
from pathlib import Path
import config

class MemorySystem:
    def __init__(self):
        """Initialize AERIS's forever memory system"""
        
        # Initialize ChromaDB with persistent storage
        self.client = chromadb.PersistentClient(
            path=str(config.MEMORY_DB_DIR),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Create or get collection for conversations
        self.conversations = self.client.get_or_create_collection(
            name="conversations",
            metadata={"description": "All conversations with user"}
        )
        
        # Create or get collection for important facts/preferences
        self.facts = self.client.get_or_create_collection(
            name="user_facts",
            metadata={"description": "User preferences, habits, important info"}
        )
        
        print("[Memory system initialized]")
        print(f"  Conversations stored: {self.conversations.count()}")
        print(f"  Facts remembered: {self.facts.count()}")
    
    def store_message(self, role: str, content: str, metadata: dict = None):
        """Store a single message in memory"""
        
        timestamp = datetime.now().isoformat()
        message_id = f"{role}_{timestamp}"
        
        # Prepare metadata
        meta = {
            "role": role,
            "timestamp": timestamp,
            "mode": metadata.get("mode", "personal") if metadata else "personal"
        }
        
        if metadata:
            meta.update(metadata)
        
        # Store in vector database
        self.conversations.add(
            documents=[content],
            metadatas=[meta],
            ids=[message_id]
        )
    
    def store_conversation(self, messages: list, session_metadata: dict = None):
        """Store entire conversation session"""
        
        timestamp = datetime.now().isoformat()
        
        for i, msg in enumerate(messages):
            meta = {
                "session_id": session_metadata.get("session_id", timestamp) if session_metadata else timestamp,
                "message_index": i,
                **msg.get("metadata", {})
            }
            
            self.store_message(
                role=msg["role"],
                content=msg["content"],
                metadata=meta
            )
    
    def remember(self, query: str, n_results: int = 5):
        """Retrieve relevant memories based on query"""
        
        try:
            results = self.conversations.query(
                query_texts=[query],
                n_results=n_results
            )
            
            if not results["documents"] or not results["documents"][0]:
                return []
            
            memories = []
            for i, doc in enumerate(results["documents"][0]):
                memory = {
                    "content": doc,
                    "metadata": results["metadatas"][0][i],
                    "relevance": 1 - results["distances"][0][i]  # Convert distance to similarity
                }
                memories.append(memory)
            
            return memories
            
        except Exception as e:
            print(f"[Error retrieving memories: {e}]")
            return []
    
    def store_fact(self, fact: str, category: str = "general", importance: int = 5):
        """Store an important fact about the user"""
        
        timestamp = datetime.now().isoformat()
        fact_id = f"fact_{timestamp}"
        
        metadata = {
            "category": category,
            "importance": importance,
            "timestamp": timestamp
        }
        
        self.facts.add(
            documents=[fact],
            metadatas=[metadata],
            ids=[fact_id]
        )
        
        print(f"[✓ Remembered: {fact[:50]}...]")
    
    def recall_facts(self, query: str = None, category: str = None, n_results: int = 10):
        """Recall facts about the user"""
        
        try:
            if query:
                # Semantic search
                results = self.facts.query(
                    query_texts=[query],
                    n_results=n_results,
                    where={"category": category} if category else None
                )
            else:
                # Get all facts in category
                results = self.facts.get(
                    where={"category": category} if category else None,
                    limit=n_results
                )
            
            if not results["documents"]:
                return []
            
            facts = []
            docs = results["documents"][0] if query else results["documents"]
            metas = results["metadatas"][0] if query else results["metadatas"]
            
            for i, doc in enumerate(docs):
                fact = {
                    "content": doc,
                    "metadata": metas[i]
                }
                facts.append(fact)
            
            return facts
            
        except Exception as e:
            print(f"[Error recalling facts: {e}]")
            return []
    
    def get_context_for_query(self, query: str, mode: str = "personal"):
        """Get relevant context from memory for a query"""
        
        context = {
            "recent_memories": [],
            "relevant_facts": [],
            "context_string": ""
        }
        
        # Get relevant conversation memories
        memories = self.remember(query, n_results=3)
        context["recent_memories"] = memories
        
        # Get relevant facts
        facts = self.recall_facts(query, n_results=3)
        context["relevant_facts"] = facts
        
        # Build context string for model
        context_parts = []
        
        if memories:
            context_parts.append("Relevant past conversations:")
            for mem in memories:
                role = mem["metadata"].get("role", "unknown")
                content = mem["content"][:200]  # Truncate long messages
                context_parts.append(f"  [{role}]: {content}")
        
        if facts:
            context_parts.append("\nThings I know about you:")
            for fact in facts:
                context_parts.append(f"  - {fact['content']}")
        
        context["context_string"] = "\n".join(context_parts)
        
        return context
    
    def get_stats(self):
        """Get memory system statistics"""
        return {
            "total_conversations": self.conversations.count(),
            "total_facts": self.facts.count(),
            "storage_path": str(config.MEMORY_DB_DIR)
        }
    
    def export_conversations(self, output_file: Path = None):
        """Export all conversations to JSON file"""
        
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = config.CONVERSATIONS_DIR / f"export_{timestamp}.json"
        
        try:
            # Get all conversations
            all_convos = self.conversations.get()
            
            data = {
                "exported_at": datetime.now().isoformat(),
                "total_messages": len(all_convos["documents"]),
                "conversations": []
            }
            
            for i, doc in enumerate(all_convos["documents"]):
                data["conversations"].append({
                    "content": doc,
                    "metadata": all_convos["metadatas"][i]
                })
            
            # Save to file
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            print(f"[✓ Exported {len(all_convos['documents'])} messages to {output_file}]")
            return str(output_file)
            
        except Exception as e:
            print(f"[✗ Error exporting: {e}]")
            return None
    
    def clear_memory(self, confirm: bool = False):
        """Clear all memory (use with caution!)"""
        
        if not confirm:
            print("[! Use clear_memory(confirm=True) to actually clear memory]")
            return False
        
        try:
            self.client.delete_collection("conversations")
            self.client.delete_collection("user_facts")
            
            # Recreate collections
            self.conversations = self.client.get_or_create_collection(name="conversations")
            self.facts = self.client.get_or_create_collection(name="user_facts")
            
            print("[✓ Memory cleared]")
            return True
            
        except Exception as e:
            print(f"[✗ Error clearing memory: {e}]")
            return False


# Singleton instance
_memory_system = None

def get_memory_system():
    """Get the global MemorySystem instance"""
    global _memory_system
    if _memory_system is None:
        _memory_system = MemorySystem()
    return _memory_system

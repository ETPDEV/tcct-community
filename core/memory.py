#!/usr/bin/env python3
# =========================================================
# Edwards Tech Innovation
# ---------------------------------------------------------
# Business Unit : TCCT
# Project       : TCCT Core v1.0.0
# File          : memory.py
# Author        : Andrew 'Dru' Edwards
# Description   : Persistent memory system with session context management
# ---------------------------------------------------------
# Notice        : (c) 2025 Edwards Tech Innovation.
#                 Unauthorized copying, distribution, or use
#                 is prohibited unless explicitly authorized.
# Signature     : ETI-TCCT-0507D7BF5B27
# =========================================================

"""
TCCT Memory System
Persistent knowledge storage with semantic search capabilities.
Works offline with keyword matching, upgrades to embeddings when available.
"""

import os
import json
import time
import hashlib
import re
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum

# Configuration
MEMORY_DIR = Path.home() / "tcct" / "memory"
KNOWLEDGE_DIR = MEMORY_DIR / "knowledge"
CONTEXT_DIR = MEMORY_DIR / "context"
SESSIONS_DIR = MEMORY_DIR / "sessions"

class MemoryType(Enum):
    """Types of memory entries"""
    FACT = "fact"           # Discrete facts (e.g., "Python is interpreted")
    CONTEXT = "context"     # Situational context (e.g., current project)
    EPISODE = "episode"     # Past events/conversations
    SKILL = "skill"         # Learned procedures
    PREFERENCE = "preference"  # User preferences

@dataclass
class MemoryEntry:
    """A single memory entry"""
    id: str
    content: str
    memory_type: str
    tags: List[str] = field(default_factory=list)
    source: str = ""
    timestamp: float = field(default_factory=time.time)
    relevance_score: float = 1.0
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "MemoryEntry":
        return cls(**data)

class MemoryStore:
    """
    Persistent memory storage with keyword-based retrieval.
    Designed to work offline without embedding models.
    """

    def __init__(self, store_path: Optional[Path] = None):
        self.store_path = store_path or KNOWLEDGE_DIR
        self.store_path.mkdir(parents=True, exist_ok=True)
        self.index_path = self.store_path / "_index.json"
        self.entries: Dict[str, MemoryEntry] = {}
        self._load_index()

    def _load_index(self):
        """Load memory index from disk"""
        if self.index_path.exists():
            try:
                with open(self.index_path) as f:
                    data = json.load(f)
                    for entry_id, entry_data in data.items():
                        self.entries[entry_id] = MemoryEntry.from_dict(entry_data)
            except Exception as e:
                print(f"Warning: Could not load memory index: {e}")

    def _save_index(self):
        """Save memory index to disk"""
        data = {eid: entry.to_dict() for eid, entry in self.entries.items()}
        with open(self.index_path, 'w') as f:
            json.dump(data, f, indent=2)

    def _generate_id(self, content: str) -> str:
        """Generate unique ID for content"""
        hash_input = f"{content}{time.time()}"
        return hashlib.sha256(hash_input.encode()).hexdigest()[:12]

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text for indexing"""
        # Remove special characters, lowercase
        text = re.sub(r'[^\w\s]', ' ', text.lower())
        words = text.split()

        # Remove common stop words
        stop_words = {
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
            'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
            'would', 'could', 'should', 'may', 'might', 'can', 'to', 'of',
            'in', 'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into',
            'through', 'during', 'before', 'after', 'above', 'below', 'up',
            'down', 'out', 'off', 'over', 'under', 'again', 'further',
            'then', 'once', 'here', 'there', 'when', 'where', 'why', 'how',
            'all', 'each', 'few', 'more', 'most', 'other', 'some', 'such',
            'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too',
            'very', 'just', 'and', 'but', 'if', 'or', 'because', 'until',
            'while', 'this', 'that', 'these', 'those', 'i', 'you', 'he',
            'she', 'it', 'we', 'they', 'what', 'which', 'who', 'whom'
        }

        keywords = [w for w in words if len(w) > 2 and w not in stop_words]
        return list(set(keywords))

    def _score_match(self, query_keywords: List[str], entry: MemoryEntry) -> float:
        """Score how well an entry matches query keywords"""
        entry_text = f"{entry.content} {' '.join(entry.tags)}".lower()
        entry_keywords = set(self._extract_keywords(entry_text))

        if not query_keywords:
            return 0.0

        # Count matching keywords
        matches = sum(1 for kw in query_keywords if kw in entry_keywords)

        # Bonus for exact phrase match
        query_str = ' '.join(query_keywords)
        if query_str in entry_text:
            matches += len(query_keywords)

        # Normalize by query length
        score = matches / len(query_keywords)

        # Recency boost (memories accessed recently score higher)
        age_days = (time.time() - entry.last_accessed) / 86400
        recency_factor = 1.0 / (1.0 + age_days * 0.1)
        score *= (0.8 + 0.2 * recency_factor)

        # Access frequency boost
        frequency_factor = min(1.0, entry.access_count / 10.0)
        score *= (0.9 + 0.1 * frequency_factor)

        return score

    def store(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.FACT,
        tags: Optional[List[str]] = None,
        source: str = "",
        metadata: Optional[Dict] = None
    ) -> str:
        """Store a new memory entry"""
        entry_id = self._generate_id(content)

        # Auto-generate tags from content
        auto_tags = self._extract_keywords(content)[:5]
        all_tags = list(set((tags or []) + auto_tags))

        entry = MemoryEntry(
            id=entry_id,
            content=content,
            memory_type=memory_type.value,
            tags=all_tags,
            source=source,
            metadata=metadata or {}
        )

        self.entries[entry_id] = entry
        self._save_index()

        return entry_id

    def recall(
        self,
        query: str,
        limit: int = 5,
        memory_type: Optional[MemoryType] = None,
        min_score: float = 0.1
    ) -> List[Tuple[MemoryEntry, float]]:
        """Recall memories matching the query"""
        query_keywords = self._extract_keywords(query)

        if not query_keywords:
            return []

        results = []

        for entry in self.entries.values():
            # Filter by type if specified
            if memory_type and entry.memory_type != memory_type.value:
                continue

            score = self._score_match(query_keywords, entry)

            if score >= min_score:
                results.append((entry, score))

        # Sort by score descending
        results.sort(key=lambda x: x[1], reverse=True)

        # Update access stats for returned entries
        for entry, _ in results[:limit]:
            entry.access_count += 1
            entry.last_accessed = time.time()

        self._save_index()

        return results[:limit]

    def get(self, entry_id: str) -> Optional[MemoryEntry]:
        """Get a specific memory by ID"""
        entry = self.entries.get(entry_id)
        if entry:
            entry.access_count += 1
            entry.last_accessed = time.time()
            self._save_index()
        return entry

    def delete(self, entry_id: str) -> bool:
        """Delete a memory entry"""
        if entry_id in self.entries:
            del self.entries[entry_id]
            self._save_index()
            return True
        return False

    def list_all(
        self,
        memory_type: Optional[MemoryType] = None,
        limit: int = 100
    ) -> List[MemoryEntry]:
        """List all memories, optionally filtered by type"""
        entries = list(self.entries.values())

        if memory_type:
            entries = [e for e in entries if e.memory_type == memory_type.value]

        # Sort by last accessed
        entries.sort(key=lambda x: x.last_accessed, reverse=True)

        return entries[:limit]

    def stats(self) -> Dict[str, Any]:
        """Get memory statistics"""
        by_type = {}
        for entry in self.entries.values():
            t = entry.memory_type
            by_type[t] = by_type.get(t, 0) + 1

        return {
            "total_entries": len(self.entries),
            "by_type": by_type,
            "store_path": str(self.store_path),
        }


class ContextManager:
    """
    Manages current context (active project, session state, etc.)
    Short-term memory that informs responses.
    """

    def __init__(self):
        self.context_path = CONTEXT_DIR
        self.context_path.mkdir(parents=True, exist_ok=True)
        self.current_context: Dict[str, Any] = {}
        self._load_context()

    def _load_context(self):
        """Load current context from disk"""
        context_file = self.context_path / "current.json"
        if context_file.exists():
            try:
                with open(context_file) as f:
                    self.current_context = json.load(f)
            except:
                self.current_context = {}

    def _save_context(self):
        """Save current context to disk"""
        context_file = self.context_path / "current.json"
        with open(context_file, 'w') as f:
            json.dump(self.current_context, f, indent=2)

    def set(self, key: str, value: Any):
        """Set a context value"""
        self.current_context[key] = value
        self.current_context["_updated"] = time.time()
        self._save_context()

    def get(self, key: str, default: Any = None) -> Any:
        """Get a context value"""
        return self.current_context.get(key, default)

    def clear(self, key: Optional[str] = None):
        """Clear context (specific key or all)"""
        if key:
            self.current_context.pop(key, None)
        else:
            self.current_context = {}
        self._save_context()

    def get_all(self) -> Dict[str, Any]:
        """Get all current context"""
        return self.current_context.copy()

    def set_project(self, path: str, name: Optional[str] = None):
        """Set current project context"""
        self.set("project_path", path)
        self.set("project_name", name or Path(path).name)

    def set_task(self, task: str):
        """Set current task"""
        self.set("current_task", task)
        self.set("task_started", time.time())


class SessionMemory:
    """
    Session-based memory for conversation history.
    Persists across restarts but separate per session.
    """

    def __init__(self, session_id: Optional[str] = None):
        self.sessions_path = SESSIONS_DIR
        self.sessions_path.mkdir(parents=True, exist_ok=True)

        self.session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_file = self.sessions_path / f"{self.session_id}.json"
        self.messages: List[Dict] = []
        self._load_session()

    def _load_session(self):
        """Load session from disk"""
        if self.session_file.exists():
            try:
                with open(self.session_file) as f:
                    data = json.load(f)
                    self.messages = data.get("messages", [])
            except:
                self.messages = []

    def _save_session(self):
        """Save session to disk"""
        data = {
            "session_id": self.session_id,
            "messages": self.messages,
            "updated": time.time()
        }
        with open(self.session_file, 'w') as f:
            json.dump(data, f, indent=2)

    def add_message(self, role: str, content: str, metadata: Optional[Dict] = None):
        """Add a message to session history"""
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": time.time(),
            "metadata": metadata or {}
        })
        self._save_session()

    def get_history(self, limit: int = 20) -> List[Dict]:
        """Get recent conversation history"""
        return self.messages[-limit:]

    def clear(self):
        """Clear session history"""
        self.messages = []
        self._save_session()


class UnifiedMemory:
    """
    Unified interface to all memory systems.
    Combines knowledge store, context, and session memory.
    """

    def __init__(self, session_id: Optional[str] = None):
        self.knowledge = MemoryStore()
        self.context = ContextManager()
        self.session = SessionMemory(session_id)

    def remember(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.FACT,
        tags: Optional[List[str]] = None
    ) -> str:
        """Store something to long-term memory"""
        return self.knowledge.store(content, memory_type, tags)

    def recall(self, query: str, limit: int = 5) -> List[Tuple[MemoryEntry, float]]:
        """Recall from long-term memory"""
        return self.knowledge.recall(query, limit)

    def get_context_for_query(self, query: str) -> Dict[str, Any]:
        """Get relevant context for a query"""
        # Get current context
        ctx = self.context.get_all()

        # Get relevant memories
        memories = self.recall(query, limit=3)

        # Get recent session history
        history = self.session.get_history(limit=5)

        return {
            "current_context": ctx,
            "relevant_memories": [
                {"content": m.content, "score": s, "type": m.memory_type}
                for m, s in memories
            ],
            "recent_history": history
        }

    def build_system_context(self, query: str) -> str:
        """Build a context string to prepend to queries"""
        ctx = self.get_context_for_query(query)

        parts = []

        # Current project
        if ctx["current_context"].get("project_name"):
            parts.append(f"Current project: {ctx['current_context']['project_name']}")

        # Current task
        if ctx["current_context"].get("current_task"):
            parts.append(f"Current task: {ctx['current_context']['current_task']}")

        # Relevant memories
        if ctx["relevant_memories"]:
            mem_str = "\n".join(
                f"- {m['content']}" for m in ctx["relevant_memories"][:3]
            )
            parts.append(f"Relevant knowledge:\n{mem_str}")

        return "\n".join(parts) if parts else ""


# CLI for testing
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="TCCT Memory System")
    subparsers = parser.add_subparsers(dest="command")

    # Store command
    store_p = subparsers.add_parser("store", help="Store a memory")
    store_p.add_argument("content", help="Content to store")
    store_p.add_argument("--type", choices=["fact", "context", "episode", "skill", "preference"], default="fact")
    store_p.add_argument("--tags", nargs="+", default=[])

    # Recall command
    recall_p = subparsers.add_parser("recall", help="Recall memories")
    recall_p.add_argument("query", help="Search query")
    recall_p.add_argument("--limit", type=int, default=5)

    # List command
    list_p = subparsers.add_parser("list", help="List memories")
    list_p.add_argument("--type", choices=["fact", "context", "episode", "skill", "preference"])

    # Stats command
    subparsers.add_parser("stats", help="Show memory stats")

    # Context commands
    ctx_p = subparsers.add_parser("context", help="Manage context")
    ctx_p.add_argument("action", choices=["show", "set", "clear"])
    ctx_p.add_argument("--key", default=None)
    ctx_p.add_argument("--value", default=None)

    args = parser.parse_args()

    memory = UnifiedMemory()

    if args.command == "store":
        mem_type = MemoryType(args.type)
        entry_id = memory.remember(args.content, mem_type, args.tags)
        print(f"Stored with ID: {entry_id}")

    elif args.command == "recall":
        results = memory.recall(args.query, args.limit)
        if results:
            for entry, score in results:
                print(f"[{score:.2f}] {entry.content[:100]}")
                print(f"       Type: {entry.memory_type}, Tags: {entry.tags}")
        else:
            print("No matching memories found.")

    elif args.command == "list":
        mem_type = MemoryType(args.type) if args.type else None
        entries = memory.knowledge.list_all(mem_type)
        for entry in entries:
            print(f"[{entry.id}] {entry.content[:60]}...")

    elif args.command == "stats":
        stats = memory.knowledge.stats()
        print(f"Total entries: {stats['total_entries']}")
        print(f"By type: {stats['by_type']}")
        print(f"Store path: {stats['store_path']}")

    elif args.command == "context":
        if args.action == "show":
            ctx = memory.context.get_all()
            print(json.dumps(ctx, indent=2))
        elif args.action == "set" and args.key and args.value:
            memory.context.set(args.key, args.value)
            print(f"Set {args.key} = {args.value}")
        elif args.action == "clear":
            memory.context.clear(args.key)
            print("Context cleared.")

    else:
        parser.print_help()

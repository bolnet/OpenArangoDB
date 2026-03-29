"""Core ArgonDB client — wraps python-arango with Enterprise-equivalent features."""

from __future__ import annotations

import logging
from typing import Any

from arango import ArangoClient

from open_argondb.audit.logger import AuditLogger
from open_argondb.cdc.engine import CDCEngine
from open_argondb.events.bus import EventBus, InProcessBus
from open_argondb.models import AgentScope, AuditEntry, ChangeEvent, Memory
from open_argondb.scoping.manager import ScopeManager
from open_argondb.store.document_store import DocumentStore
from open_argondb.vector.search import VectorSearch

logger = logging.getLogger("open_argondb")


class ArgonDB:
    """Enterprise-equivalent ArangoDB wrapper.

    All writes go through this gateway to ensure audit, CDC, and event
    propagation are applied consistently.

    Usage:
        db = ArgonDB(host="http://localhost:8529", database="mydb")
        db.insert(memory, scope=AgentScope(agent_id="agent-1"))
        results = db.search("what happened yesterday?", limit=10)
        db.close()
    """

    def __init__(
        self,
        host: str = "http://localhost:8529",
        database: str = "argondb",
        username: str = "root",
        password: str = "",
        event_bus: EventBus | None = None,
        audit_enabled: bool = True,
        cdc_enabled: bool = True,
        embedding_model: str = "BAAI/bge-m3",
    ) -> None:
        self._client = ArangoClient(hosts=host)
        self._sys_db = self._client.db("_system", username=username, password=password)

        if not self._sys_db.has_database(database):
            self._sys_db.create_database(database)

        self._db = self._client.db(database, username=username, password=password)
        self._embedding_model = embedding_model

        # Core components
        self._store = DocumentStore(self._db)
        self._vector = VectorSearch(self._db, model_name=embedding_model)
        self._scope = ScopeManager(self._db)
        self._events = event_bus or InProcessBus()
        self._audit = AuditLogger(self._db) if audit_enabled else None
        self._cdc = CDCEngine(self._db, self._events) if cdc_enabled else None

    @property
    def db(self):
        """Direct access to the underlying ArangoDB database."""
        return self._db

    @property
    def events(self) -> EventBus:
        return self._events

    # ── Write Operations (all audited + CDC tracked) ──

    def insert(self, memory: Memory, scope: AgentScope | None = None) -> Memory:
        """Insert a memory. Audited, CDC-tracked, event-emitted."""
        scoped = self._scope.apply(memory, scope) if scope else memory
        result = self._store.insert(scoped)

        if self._audit:
            self._audit.log("insert", "memories", result.id, scope)
        if self._cdc:
            self._cdc.record_change("insert", result.id, after=result)
        self._events.publish("memory.created", {"memory_id": result.id})

        return result

    def update(self, memory: Memory, scope: AgentScope | None = None) -> Memory:
        """Update a memory. Audited, CDC-tracked."""
        old = self._store.get(memory.id)
        scoped = self._scope.apply(memory, scope) if scope else memory
        result = self._store.update(scoped)

        if self._audit:
            self._audit.log("update", "memories", result.id, scope)
        if self._cdc:
            self._cdc.record_change("update", result.id, before=old, after=result)
        self._events.publish("memory.updated", {"memory_id": result.id})

        return result

    def delete(self, memory_id: str, scope: AgentScope | None = None) -> None:
        """Soft-delete a memory. Audited, CDC-tracked."""
        old = self._store.get(memory_id)
        self._store.soft_delete(memory_id)

        if self._audit:
            self._audit.log("delete", "memories", memory_id, scope)
        if self._cdc:
            self._cdc.record_change("delete", memory_id, before=old)
        self._events.publish("memory.deleted", {"memory_id": memory_id})

    def supersede(self, old_id: str, new: Memory, scope: AgentScope | None = None) -> Memory:
        """Supersede an old memory with a new one. Atomic."""
        old = self._store.get(old_id)
        self._store.mark_superseded(old_id, new.id)
        result = self.insert(new, scope)

        if self._cdc:
            self._cdc.record_change("supersede", old_id, before=old, after=result)
        self._events.publish("memory.superseded", {
            "old_id": old_id, "new_id": result.id,
        })

        return result

    # ── Read Operations ──

    def get(self, memory_id: str) -> Memory | None:
        return self._store.get(memory_id)

    def search(
        self,
        query: str,
        limit: int = 20,
        scope: AgentScope | None = None,
        tier: int = 3,
    ) -> list[dict[str, Any]]:
        """Vector similarity search with optional scope filtering."""
        results = self._vector.search(query, limit=limit)
        if scope:
            results = self._scope.filter_results(results, scope)
        return results

    def list_memories(
        self,
        entity: str | None = None,
        scope: AgentScope | None = None,
        limit: int = 50,
    ) -> list[Memory]:
        return self._store.list_memories(entity=entity, scope=scope, limit=limit)

    # ── Embedding ──

    def embed(self, memory_id: str, content: str) -> None:
        """Generate and store embedding for a memory."""
        self._vector.add(memory_id, content)

    def batch_embed(self) -> int:
        """Embed all memories that don't have embeddings yet."""
        return self._vector.batch_embed()

    # ── CDC ──

    def get_changes(self, since_rev: str | None = None) -> list[ChangeEvent]:
        """Get changes since a checkpoint revision."""
        if not self._cdc:
            raise RuntimeError("CDC is not enabled")
        return self._cdc.get_changes(since_rev)

    # ── Lifecycle ──

    def reset(self) -> None:
        """Reset all collections. Use with caution."""
        self._store.reset()
        self._vector.reset()
        if self._cdc:
            self._cdc.reset()
        if self._audit:
            self._audit.reset()

    def close(self) -> None:
        """Clean shutdown."""
        if self._cdc:
            self._cdc.stop()
        self._events.close()

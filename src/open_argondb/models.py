"""Core data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class Visibility(str, Enum):
    PRIVATE = "private"
    WORKFLOW = "workflow"
    GLOBAL = "global"


class ChangeOp(str, Enum):
    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"
    SUPERSEDE = "supersede"


@dataclass(frozen=True)
class AgentScope:
    """Identifies who owns and can access a memory."""

    agent_id: str
    session_id: str | None = None
    workflow_id: str | None = None
    visibility: Visibility = Visibility.GLOBAL


@dataclass(frozen=True)
class Memory:
    """A single memory record."""

    id: str
    content: str
    tags: list[str] = field(default_factory=list)
    category: str = "general"
    entity: str | None = None
    created_at: str = ""
    event_date: str | None = None
    valid_from: str = ""
    valid_until: str | None = None
    superseded_by: str | None = None
    confidence: float = 1.0
    status: str = "active"
    scope: AgentScope | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RetrievalResult:
    """A scored memory from retrieval."""

    memory: Memory
    score: float
    match_source: str = "unknown"
    tier: int = 3  # 1=ids, 2=summary, 3=full


@dataclass(frozen=True)
class ChangeEvent:
    """A change event from the CDC engine."""

    op: ChangeOp
    memory_id: str
    rev: str
    timestamp: str
    agent_scope: AgentScope | None = None
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None


@dataclass(frozen=True)
class AuditEntry:
    """An audit log entry."""

    id: str
    op: str
    collection: str
    document_key: str
    agent_id: str | None = None
    session_id: str | None = None
    timestamp: str = ""
    content_hash: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

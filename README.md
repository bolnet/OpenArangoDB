# Open ArgonDB

Enterprise-equivalent features for ArangoDB Community Edition — as a Python layer.

## What It Does

Wraps `python-arango` to add features that ArangoDB reserves for Enterprise Edition:

| Feature | Enterprise | Open ArgonDB |
|---------|-----------|-------------|
| **CDC / Change Streams** | WAL-based (if they had it) | Changelog collection + rev tracking |
| **Audit Logging** | Built-in | Service-layer audit with TTL retention |
| **Event Propagation** | N/A | In-process, Redis, or NATS pub/sub |
| **Agent Scoping** | N/A | Private/workflow/global visibility |
| **Vector Search** | Experimental IVF | numpy cosine + auto-upgrade to native |
| **Encryption at Rest** | AES-256 native | OS-level (LUKS/FileVault/EBS) |
| **Hot Backups** | RocksDB checkpoint | LVM/ZFS/cloud disk snapshots |

Plus agent memory features neither edition has: multi-agent scoping, progressive disclosure, temporal supersession.

## Install

```bash
pip install open-argondb

# With embeddings support
pip install open-argondb[embeddings]

# With Redis event bus
pip install open-argondb[events-redis]

# Everything
pip install open-argondb[all]
```

## Quick Start

```python
from open_argondb import ArgonDB
from open_argondb.models import AgentScope, Memory

db = ArgonDB(host="http://localhost:8529", database="myproject")

# Insert with agent scoping
scope = AgentScope(agent_id="agent-1", workflow_id="wf-123")
mem = Memory(id="m1", content="User prefers dark mode", tags=["preference"])
db.insert(mem, scope=scope)

# Embed and search
db.batch_embed()
results = db.search("what does the user prefer?", scope=scope)

# CDC — get changes since last checkpoint
changes = db.get_changes(since_timestamp="2026-03-29T00:00:00Z")

# Audit — query operation history
db._audit.query(agent_id="agent-1", op="insert", limit=10)
```

## Architecture

```
Agents (Python/any)
       │
       ▼
┌──────────────────────────┐
│   ArgonDB Gateway        │  ← All writes go through here
├──────────────────────────┤
│ Audit    │ CDC Engine    │
│ Scoping  │ Event Bus     │
│ Vector   │ Store         │
└──────────┬───────────────┘
           │
     ArangoDB Community 3.12+
```

## Modules

- `store/` — Document storage with soft-delete and scoping
- `vector/` — Embedding search (numpy fallback + native auto-upgrade)
- `cdc/` — Change data capture via changelog collection
- `events/` — Pub/sub (in-process, Redis, NATS)
- `audit/` — Operation audit logging with TTL
- `scoping/` — Agent/session/workflow visibility control
- `graph/` — Native ArangoDB graph traversal (TODO)
- `retrieval/` — Multi-layer retrieval with RRF fusion (TODO)
- `temporal/` — Supersession and contradiction detection (TODO)
- `backup/` — Snapshot helpers for LVM/ZFS/cloud (TODO)
- `encryption/` — Disk encryption setup guides and validation (TODO)
- `mcp/` — MCP server for Claude Code integration (TODO)

## Requirements

- Python 3.10+
- ArangoDB 3.12+ (Community Edition)

## License

Apache 2.0

---
name: openarangodb
description: Agent memory and enterprise features for ArangoDB Community Edition. Use when storing, searching, or managing agent memories in ArangoDB, or when the user asks about CDC, audit logging, vector search, graph traversals, encryption validation, or backup for ArangoDB.
---

# OpenArangoDB Skill

Enterprise-equivalent features for ArangoDB Community Edition — CDC, audit, encryption, agent memory, vector search, graph traversals, and more.

## When to Use

- Storing or retrieving agent memories
- Setting up ArangoDB with enterprise features (audit, CDC, encryption)
- Vector similarity search on stored memories
- Multi-layer retrieval (exact, tag, semantic, temporal) with RRF fusion
- Graph traversals and SmartGraph-like partitioning
- Change data capture and audit logging
- Backup, replication, or encryption validation

## Installation

```bash
# Library only
pip install OpenArangoDB

# With MCP server support
pip install "OpenArangoDB[mcp]"

# All optional features
pip install "OpenArangoDB[all]"
```

## MCP Server Configuration

Add to Claude Code settings (`~/.claude/settings.json`):

```json
{
  "mcpServers": {
    "openarangodb": {
      "command": "openarangodb",
      "args": ["serve"],
      "env": {
        "ARANGODB_HOST": "http://localhost:8529",
        "ARANGODB_DATABASE": "argondb",
        "ARANGODB_USERNAME": "root",
        "ARANGODB_PASSWORD": ""
      }
    }
  }
}
```

Or with Docker:

```json
{
  "mcpServers": {
    "openarangodb": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "openarangodb:latest"],
      "env": {
        "ARANGODB_HOST": "http://host.docker.internal:8529"
      }
    }
  }
}
```

## Available MCP Tools

| Tool | Description |
|------|-------------|
| `memory_insert` | Insert a new memory (content, tags, entity, category, agent_id) |
| `memory_get` | Retrieve a memory by ID |
| `memory_search` | Vector similarity search |
| `memory_update` | Update an existing memory |
| `memory_delete` | Soft-delete a memory |
| `memory_supersede` | Replace a memory with a newer version (creates supersession chain) |
| `retrieval_search` | Multi-layer search with RRF fusion (exact + tag + semantic + temporal) |
| `audit_query` | Query audit logs (by agent, operation, time range) |
| `changes_since` | Get CDC change events since a revision |
| `encryption_check` | Check encryption at rest status |

## Python API Quick Reference

```python
from open_arangodb import ArangoDB, Memory, AgentScope

# Connect
db = ArangoDB(
    host="http://localhost:8529",
    database="argondb",
    audit_enabled=True,
    cdc_enabled=True,
)

# Insert
memory = Memory(id="m1", content="The user prefers dark mode", tags=["preference"])
scope = AgentScope(agent_id="agent-1")
db.insert(memory, scope=scope)

# Search
results = db.search("dark mode", limit=5)

# Supersede (version a memory)
db.supersede("m1", Memory(id="m2", content="The user switched to light mode"))

# Get CDC changes
changes = db.get_changes(since_rev="12345")

# Multi-layer retrieval
from open_arangodb import RetrievalRequest
results = db.retrieve(RetrievalRequest(query="user preferences", entity="user-1"))
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ARANGODB_HOST` | `http://localhost:8529` | ArangoDB URL |
| `ARANGODB_DATABASE` | `argondb` | Database name |
| `ARANGODB_USERNAME` | `root` | Username |
| `ARANGODB_PASSWORD` | (empty) | Password |
| `ARANGODB_AUDIT` | `true` | Enable audit logging |
| `ARANGODB_CDC` | `true` | Enable CDC |
| `ARANGODB_RETRIEVAL` | `false` | Enable multi-layer retrieval |
| `ARANGODB_TEMPORAL` | `false` | Enable temporal engine |
| `ARANGODB_GRAPH` | `false` | Enable graph features |

## CLI Commands

```bash
openarangodb serve          # Start MCP server (stdio)
openarangodb health         # Check ArangoDB connection
openarangodb version        # Show version
openarangodb encrypt-check  # Check encryption status
```

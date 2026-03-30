"""Stdio entry point for the OpenArangoDB MCP server.

Usage:
    python -m open_arangodb.mcp
    openarangodb-mcp

Environment variables:
    ARANGODB_HOST       ArangoDB URL (default: http://localhost:8529)
    ARANGODB_DATABASE   Database name (default: argondb)
    ARANGODB_USERNAME   Username (default: root)
    ARANGODB_PASSWORD   Password (default: empty)
    ARANGODB_AUDIT      Enable audit logging (default: true)
    ARANGODB_CDC        Enable CDC (default: true)
    ARANGODB_RETRIEVAL  Enable multi-layer retrieval (default: false)
    ARANGODB_TEMPORAL   Enable temporal engine (default: false)
    ARANGODB_GRAPH      Enable graph features (default: false)
"""

from __future__ import annotations

import json
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("open_arangodb.mcp")


def _bool_env(key: str, default: bool = False) -> bool:
    return os.environ.get(key, str(default)).lower() in ("true", "1", "yes")


def create_server() -> "ArangoDBMCPServer":
    from open_arangodb.core import ArangoDB
    from open_arangodb.mcp.server import ArangoDBMCPServer

    db = ArangoDB(
        host=os.environ.get("ARANGODB_HOST", "http://localhost:8529"),
        database=os.environ.get("ARANGODB_DATABASE", "argondb"),
        username=os.environ.get("ARANGODB_USERNAME", "root"),
        password=os.environ.get("ARANGODB_PASSWORD", ""),
        audit_enabled=_bool_env("ARANGODB_AUDIT", True),
        cdc_enabled=_bool_env("ARANGODB_CDC", True),
        retrieval_enabled=_bool_env("ARANGODB_RETRIEVAL"),
        temporal_enabled=_bool_env("ARANGODB_TEMPORAL"),
        graph_enabled=_bool_env("ARANGODB_GRAPH"),
    )
    return ArangoDBMCPServer(db)


def main() -> None:
    """Run the MCP server over stdio (JSON-RPC)."""
    server = create_server()
    logger.info("OpenArangoDB MCP server started (stdio)")

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            _respond({"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}, "id": None})
            continue

        req_id = request.get("id")
        method = request.get("method", "")
        params = request.get("params", {})

        if method == "initialize":
            _respond({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": "openarangodb", "version": "0.1.0"},
                    "capabilities": {"tools": {}},
                },
            })
        elif method == "tools/list":
            tools = server.get_tools()
            mcp_tools = []
            for tool in tools:
                input_schema = {
                    "type": "object",
                    "properties": {
                        k: {pk: pv for pk, pv in v.items() if pk != "required"}
                        for k, v in tool.get("parameters", {}).items()
                    },
                    "required": [
                        k for k, v in tool.get("parameters", {}).items()
                        if v.get("required")
                    ],
                }
                mcp_tools.append({
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "inputSchema": input_schema,
                })
            _respond({"jsonrpc": "2.0", "id": req_id, "result": {"tools": mcp_tools}})
        elif method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})
            result = server.call_tool(tool_name, arguments)
            if "error" in result:
                _respond({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"content": [{"type": "text", "text": json.dumps(result)}], "isError": True},
                })
            else:
                _respond({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"content": [{"type": "text", "text": json.dumps(result)}]},
                })
        elif method == "notifications/initialized":
            pass  # No response needed for notifications
        else:
            _respond({
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            })


def _respond(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()

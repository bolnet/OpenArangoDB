"""OpenArangoDB CLI — command-line interface for server and utilities.

Usage:
    openarangodb serve          Start the MCP server (stdio)
    openarangodb health         Check ArangoDB connection
    openarangodb version        Show version
    openarangodb encrypt-check  Check encryption at rest status
"""

from __future__ import annotations

import json
import os
import sys


def main(argv: list[str] | None = None) -> None:
    args = argv if argv is not None else sys.argv[1:]
    command = args[0] if args else "help"

    commands = {
        "serve": _cmd_serve,
        "health": _cmd_health,
        "version": _cmd_version,
        "encrypt-check": _cmd_encrypt_check,
        "help": _cmd_help,
        "--help": _cmd_help,
        "-h": _cmd_help,
    }

    handler = commands.get(command, _cmd_help)
    handler()


def _cmd_serve() -> None:
    from open_arangodb.mcp.__main__ import main as mcp_main
    mcp_main()


def _cmd_health() -> None:
    from arango import ArangoClient

    host = os.environ.get("ARANGODB_HOST", "http://localhost:8529")
    username = os.environ.get("ARANGODB_USERNAME", "root")
    password = os.environ.get("ARANGODB_PASSWORD", "")
    database = os.environ.get("ARANGODB_DATABASE", "argondb")

    try:
        client = ArangoClient(hosts=host)
        db = client.db(database, username=username, password=password)
        version = db.version()
        print(json.dumps({
            "status": "healthy",
            "host": host,
            "database": database,
            "arangodb_version": version,
        }, indent=2))
    except Exception as exc:
        print(json.dumps({
            "status": "unhealthy",
            "host": host,
            "database": database,
            "error": str(exc),
        }, indent=2))
        sys.exit(1)


def _cmd_version() -> None:
    from open_arangodb import __version__
    print(f"OpenArangoDB {__version__}")


def _cmd_encrypt_check() -> None:
    from open_arangodb.encryption.validator import EncryptionValidator

    validator = EncryptionValidator()
    status = validator.check()
    print(json.dumps({
        "encrypted": status.encrypted,
        "method": status.method,
        "details": status.details,
        "checked_at": status.checked_at,
    }, indent=2))


def _cmd_help() -> None:
    print("""OpenArangoDB — Enterprise-equivalent features for ArangoDB Community Edition

Commands:
  serve          Start the MCP server over stdio
  health         Check ArangoDB connection health
  version        Show version
  encrypt-check  Check encryption at rest status
  help           Show this help message

Environment variables:
  ARANGODB_HOST       ArangoDB URL (default: http://localhost:8529)
  ARANGODB_DATABASE   Database name (default: argondb)
  ARANGODB_USERNAME   Username (default: root)
  ARANGODB_PASSWORD   Password (default: empty)
""")


if __name__ == "__main__":
    main()

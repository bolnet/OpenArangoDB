"""OpenArangoDBCore — the core engine adapter for ArangoDB connections.

Wraps the low-level connection layer to an ArangoDB server. The gateway
(open_arangodb.core.ArangoDB) delegates raw database access to an
OpenArangoDBCore instance so that the engine can be swapped (e.g. the
arangodb-core fork, an embedded binding, or a mock) without touching
the business-logic modules.
"""

from __future__ import annotations

import logging
from typing import Any

from arango import ArangoClient

logger = logging.getLogger("open_arangodb.engine")


class OpenArangoDBCore:
    """Core engine adapter — owns the ArangoDB client + database handle.

    The default backend is python-arango over HTTP, pointed at either the
    upstream ArangoDB server or the local arangodb-core fork (they speak
    the same wire protocol). An already-constructed client may be passed
    in to support tests and alternate transports.
    """

    def __init__(
        self,
        host: str = "http://localhost:8529",
        database: str = "argondb",
        username: str = "root",
        password: str = "",
        client: Any | None = None,
    ) -> None:
        self._host = host
        self._database_name = database
        self._username = username
        self._password = password
        self._client = client if client is not None else ArangoClient(hosts=host)

        sys_db = self._client.db("_system", username=username, password=password)
        if not sys_db.has_database(database):
            sys_db.create_database(database)
        self._sys_db = sys_db
        self._db = self._client.db(database, username=username, password=password)

    @property
    def db(self) -> Any:
        """The bound (non-system) database handle."""
        return self._db

    @property
    def sys_db(self) -> Any:
        """The `_system` database handle (admin operations)."""
        return self._sys_db

    @property
    def client(self) -> Any:
        """Raw ArangoDB client — escape hatch for advanced callers."""
        return self._client

    @property
    def host(self) -> str:
        return self._host

    @property
    def database_name(self) -> str:
        return self._database_name

    @property
    def username(self) -> str:
        return self._username

    @property
    def password(self) -> str:
        return self._password

    def close(self) -> None:
        """Best-effort shutdown of the underlying client."""
        close = getattr(self._client, "close", None)
        if callable(close):
            try:
                close()
            except Exception:  # noqa: BLE001 — best-effort cleanup
                logger.debug("client close raised; ignoring", exc_info=True)

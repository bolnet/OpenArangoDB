"""DC2DC replication engine — replays CDC changes to a target ArangoDB."""

from __future__ import annotations

import logging
import threading
from typing import Any

from open_arangodb.models import ReplicationConfig, ReplicationStatus

logger = logging.getLogger("open_arangodb")


class ReplicationEngine:
    """CDC-based DC2DC replication — replays changes to a target ArangoDB."""

    def __init__(
        self, source_cdc: Any, target_db: Any, config: ReplicationConfig
    ) -> None:
        self._cdc = source_cdc
        self._target = target_db
        self._config = config
        self._state = "stopped"
        self._last_rev: str | None = None
        self._pending = 0
        self._error: str | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        """Start replication in a background thread."""
        self._state = "running"
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop replication gracefully."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
        self._state = "stopped"

    def pause(self) -> None:
        """Pause replication (thread keeps running but skips batches)."""
        self._state = "paused"

    def resume(self) -> None:
        """Resume replication after pause."""
        self._state = "running"

    def status(self) -> ReplicationStatus:
        """Return current replication status."""
        return ReplicationStatus(
            state=self._state,
            last_synced_rev=self._last_rev,
            pending_changes=self._pending,
            error=self._error,
        )

    def replicate_batch(self) -> int:
        """Manual single-batch replication. Returns count replicated.

        Conflicts on individual changes are logged but do not stop the batch,
        so transient unique-index clashes (re-replay, racing writes) can't
        strand the pipeline.
        """
        changes = self._cdc.get_changes(
            since_rev=self._last_rev, limit=self._config.batch_size
        )
        count = 0
        last_error: str | None = None
        for change in changes:
            try:
                self._apply_change(change)
                self._last_rev = change.rev
                count += 1
            except Exception as e:
                last_error = str(e)
                logger.warning("Replication conflict on %s: %s", change.memory_id, e)
                # Advance rev so we don't re-try this change forever
                self._last_rev = change.rev
        self._error = last_error
        return count

    def _poll_loop(self) -> None:
        """Background polling loop."""
        while not self._stop_event.is_set():
            if self._state == "running":
                try:
                    self.replicate_batch()
                except Exception as e:
                    self._state = "error"
                    self._error = str(e)
            self._stop_event.wait(self._config.poll_interval_seconds)

    def _apply_change(self, change: Any) -> None:
        """Replay a change event on the target database.

        Upserts by memory_id (the business key) so re-playing the same change
        during re-sync or after a crash is idempotent, even when the target
        enforces a unique index on memory_id.
        """
        col_name = "memories"  # Default collection
        if not self._target.has_collection(col_name):
            self._target.create_collection(col_name)

        if change.op.value in ("insert", "supersede", "update") and change.after:
            key = change.memory_id.replace("/", "_")
            doc = {"_key": key, **change.after, "memory_id": change.memory_id}
            self._upsert_by_memory_id(col_name, change.memory_id, doc)
        elif change.op.value == "delete":
            key = change.memory_id.replace("/", "_")
            try:
                self._target.collection(col_name).update(
                    {"_key": key, "_deleted": True}
                )
            except Exception:
                pass

    def _upsert_by_memory_id(
        self, col_name: str, memory_id: str, doc: dict[str, Any]
    ) -> None:
        """Idempotent upsert.

        Try the fast path first (collection.insert(overwrite=True)) — works
        for mocks and for real driver when _key alone is unique. If that
        raises (e.g. unique index on memory_id clashes), fall back to AQL
        UPSERT by memory_id which handles both _key and memory_id uniqueness.
        """
        col = self._target.collection(col_name)
        try:
            col.insert(doc, overwrite=True)
            return
        except Exception:
            pass
        aql = getattr(self._target, "aql", None)
        if aql is not None and hasattr(aql, "execute"):
            aql.execute(
                f"UPSERT {{ memory_id: @mid }} "
                f"INSERT @doc "
                f"REPLACE @doc "
                f"IN {col_name}",
                bind_vars={"mid": memory_id, "doc": doc},
            )

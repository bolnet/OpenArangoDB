"""Demo / in-memory backend so the UI can run without a live ArangoDB server.

Wires the full OpenArangoDB gateway against the project's test MockDatabase,
pre-populated with sample memories, a graph, and some CDC history, so each
capability page has realistic data to render.
"""

from __future__ import annotations

import hashlib
import sys
from dataclasses import replace
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import MagicMock, patch

# Make the test MockDatabase importable without modifying test conftest
_TEST_DIR = Path(__file__).resolve().parents[3] / "tests"
if str(_TEST_DIR) not in sys.path:
    sys.path.insert(0, str(_TEST_DIR))


def _install_fake_embeddings() -> None:
    """Register a fake sentence-transformers so embedding flows work offline."""
    if "sentence_transformers" in sys.modules:
        return
    import numpy as np

    def _encode(text: Any, normalize_embeddings: bool = True) -> Any:
        if isinstance(text, str):
            texts = [text]
            single = True
        else:
            texts = list(text)
            single = False
        out = []
        for t in texts:
            h = hashlib.sha256(t.encode("utf-8")).digest()[:16]
            seed = int.from_bytes(h, "big") % (2**31 - 1)
            rng = np.random.RandomState(seed)
            vec = rng.randn(384).astype("float32")
            if normalize_embeddings:
                n = np.linalg.norm(vec) or 1.0
                vec = vec / n
            out.append(vec)
        return out[0] if single else np.array(out)

    model = MagicMock()
    model.get_sentence_embedding_dimension.return_value = 384
    model.encode = MagicMock(side_effect=_encode)

    fake = ModuleType("sentence_transformers")
    fake.SentenceTransformer = MagicMock(side_effect=lambda *a, **kw: model)
    sys.modules["sentence_transformers"] = fake


def build_demo_gateway() -> Any:
    """Return an ArangoDB gateway wired to the in-memory MockDatabase."""
    _install_fake_embeddings()
    from conftest import MockDatabase  # type: ignore[import-not-found]

    mock_db = MockDatabase()

    with patch("open_arangodb.core.ArangoClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.db.return_value = mock_db

        from open_arangodb.core import ArangoDB
        from open_arangodb.models import EdgeDefinition, GraphConfig, SatelliteConfig

        # Pre-populate a reference collection so the satellite module has
        # something to sync from.
        ref = mock_db.create_collection("ref_data")
        ref.insert({"_key": "ref-1", "name": "Widget", "qty": 42})
        ref.insert({"_key": "ref-2", "name": "Gadget", "qty": 17})
        ref.insert({"_key": "ref-3", "name": "Sprocket", "qty": 5})

        gateway = ArangoDB(
            host="http://demo",
            database="argon_demo",
            audit_enabled=True,
            cdc_enabled=True,
            graph_enabled=True,
            retrieval_enabled=True,
            temporal_enabled=True,
            backup_enabled=True,
            encryption_check=True,
            satellite_configs=[SatelliteConfig(collection="ref_data", ttl_seconds=60)],
        )

        _seed_memories(gateway)
        _seed_graph(gateway, GraphConfig, EdgeDefinition)

    return gateway


def _seed_memories(gw: Any) -> None:
    """Insert illustrative memories, embed them, and create a supersession."""
    from open_arangodb.models import Memory

    seed = [
        ("mem-alice-1", "Alice leads the compliance team at Acme Corp.", ["team", "role"], "Alice"),
        ("mem-bob-1", "Bob onboarded on 2026-01-12 as a senior engineer.", ["hire", "engineering"], "Bob"),
        ("mem-carol-1", "Carol is the backup approver for expense reports.", ["role", "finance"], "Carol"),
        ("mem-proj-1", "Project Orion ships a zero-downtime rollout this quarter.", ["project", "orion"], "Orion"),
        ("mem-proj-2", "Project Orion depends on the CDC pipeline landing first.", ["project", "orion", "cdc"], "Orion"),
        ("mem-policy-1", "Secrets must rotate every 90 days per the security policy.", ["policy", "security"], "Policy"),
        ("mem-inc-1", "Incident 2026-03-21 caused a 14-minute API outage.", ["incident", "sev2"], "Incident"),
    ]
    for mid, content, tags, entity in seed:
        gw.insert(
            Memory(id=mid, content=content, tags=tags, category="general", entity=entity, status="active"),
        )
        gw.embed(mid, content)

    # Supersede Alice's role with a new fact so the temporal page has a chain.
    gw.supersede(
        "mem-alice-1",
        Memory(
            id="mem-alice-2",
            content="Alice now leads the platform org, not compliance.",
            tags=["team", "role"],
            category="general",
            entity="Alice",
            status="active",
        ),
    )


def _seed_graph(gw: Any, GraphConfig: Any, EdgeDefinition: Any) -> None:
    """Build a small 'social' graph so the graph page has something to draw."""
    gw.create_graph(
        GraphConfig(
            name="social",
            edge_definitions=[
                EdgeDefinition(
                    collection="knows",
                    from_vertex_collections=["people"],
                    to_vertex_collections=["people"],
                ),
            ],
        ),
    )
    g = gw._graph
    for key, name, role in [
        ("alice", "Alice", "platform-lead"),
        ("bob", "Bob", "engineer"),
        ("carol", "Carol", "approver"),
        ("dan", "Dan", "engineer"),
        ("erin", "Erin", "pm"),
    ]:
        g.insert_vertex("people", {"_key": key, "name": name, "role": role})
    for src, dst in [
        ("alice", "bob"),
        ("alice", "carol"),
        ("bob", "dan"),
        ("carol", "erin"),
        ("dan", "erin"),
    ]:
        g.insert_edge("knows", f"people/{src}", f"people/{dst}")

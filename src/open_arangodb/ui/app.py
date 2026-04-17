"""OpenArangoDB read-only web UI — Starlette sub-app.

Surfaces every capability exposed by the gateway: document storage,
retrieval (exact/tag/semantic/temporal with RRF fusion), vector search,
graph traversal, temporal supersession, CDC, audit log, and the ops
panel (satellite cache, encryption check, replication, backup).

Defaults to an in-memory demo backend so the UI runs without a live
ArangoDB server; set OPENARANGODB_UI_DEMO=0 to wire a real gateway.
"""

from __future__ import annotations

import logging
import os
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

logger = logging.getLogger("open_arangodb.ui")

_UI_DIR = Path(__file__).parent
_TEMPLATES = Jinja2Templates(directory=str(_UI_DIR / "templates"))


# ── Gateway loader ──────────────────────────────────────────────────


def _get_gateway(request: Request) -> Any:
    app = request.app
    gw = getattr(app.state, "gateway", None)
    if gw is not None:
        return gw
    if os.environ.get("OPENARANGODB_UI_DEMO", "1") != "0":
        from open_arangodb.ui.demo import build_demo_gateway

        app.state.gateway = build_demo_gateway()
        return app.state.gateway
    from open_arangodb.core import ArangoDB

    gw = ArangoDB(
        host=os.environ.get("ARANGODB_HOST", "http://localhost:8529"),
        database=os.environ.get("ARANGODB_DATABASE", "argondb"),
        username=os.environ.get("ARANGODB_USERNAME", "root"),
        password=os.environ.get("ARANGODB_PASSWORD", ""),
        audit_enabled=True,
        cdc_enabled=True,
        graph_enabled=True,
        retrieval_enabled=True,
        temporal_enabled=True,
        backup_enabled=True,
        encryption_check=True,
    )
    app.state.gateway = gw
    return gw


# ── Serialization helpers ───────────────────────────────────────────


def _memory_to_dict(m: Any) -> dict[str, Any]:
    if m is None:
        return {}
    data = asdict(m) if is_dataclass(m) else dict(m)
    content = data.get("content") or ""
    data["excerpt"] = (content[:220] + "…") if len(content) > 220 else content
    data["short_id"] = (data.get("id") or "")[:12]
    data["tags"] = list(data.get("tags") or [])
    return data


def _common_context(request: Request, gw: Any) -> dict[str, Any]:
    stats = _gateway_stats(gw)
    return {
        "request": request,
        "stats": stats,
        "database": getattr(gw.engine, "database_name", "argondb"),
        "host": getattr(gw.engine, "host", "local"),
        "capabilities": _capabilities(gw),
    }


def _gateway_stats(gw: Any) -> dict[str, Any]:
    active = 0
    superseded = 0
    deleted = 0
    try:
        for doc in gw._db.collection("memories").all():
            if doc.get("_deleted"):
                deleted += 1
            elif doc.get("status") == "superseded":
                superseded += 1
            else:
                active += 1
    except Exception:
        pass

    cdc_count = 0
    try:
        cdc_count = len(list(gw.get_changes()))
    except Exception:
        pass

    audit_count = 0
    try:
        audit_col = gw._db.collection("_arangodb_audit")
        audit_count = len(audit_col.all())
    except Exception:
        pass

    graph_count = 0
    try:
        graph_count = len(getattr(gw._graph, "_graph_configs", {}) or {})
    except Exception:
        pass

    return {
        "memories_total": active + superseded + deleted,
        "memories_active": active,
        "memories_superseded": superseded,
        "memories_deleted": deleted,
        "cdc_events": cdc_count,
        "audit_events": audit_count,
        "graphs": graph_count,
        "satellites": len(getattr(gw, "_satellites", {}) or {}),
    }


def _capabilities(gw: Any) -> list[dict[str, Any]]:
    return [
        {"key": "store", "name": "Document Store", "enabled": True,
         "blurb": "AQL collections with soft-delete + revisions"},
        {"key": "vector", "name": "Vector Search", "enabled": True,
         "blurb": "Dense embeddings via BGE-M3 by default"},
        {"key": "graph", "name": "Graph Traversal", "enabled": gw._graph is not None,
         "blurb": "Named graphs, edges, parallel AQL traversal"},
        {"key": "retrieval", "name": "Multi-Layer Retrieval", "enabled": gw._retrieval is not None,
         "blurb": "Exact / tag / semantic / temporal fused with RRF"},
        {"key": "temporal", "name": "Temporal & Supersession", "enabled": gw._temporal is not None,
         "blurb": "Supersession chains and contradiction detection"},
        {"key": "cdc", "name": "Change Data Capture", "enabled": gw._cdc is not None,
         "blurb": "Append-only change log with replay from revision"},
        {"key": "audit", "name": "Audit Log", "enabled": gw._audit is not None,
         "blurb": "Every write captured for compliance"},
        {"key": "satellite", "name": "Satellite Cache", "enabled": bool(getattr(gw, "_satellites", {})),
         "blurb": "Edge-cached reference collections with TTL"},
        {"key": "backup", "name": "Backup / Restore", "enabled": gw._backup is not None,
         "blurb": "arangodump/arangorestore orchestration"},
        {"key": "encryption", "name": "Encryption at Rest", "enabled": gw._encryption is not None,
         "blurb": "Validates OS-level full-disk encryption"},
        {"key": "replication", "name": "Replication Engine", "enabled": False,
         "blurb": "Configurable via set_replication_target()"},
        {"key": "ldap", "name": "LDAP Auth", "enabled": getattr(gw, "_ldap", None) is not None,
         "blurb": "Optional enterprise auth integration"},
    ]


# ── Routes ──────────────────────────────────────────────────────────


async def index(request: Request) -> RedirectResponse:
    return RedirectResponse(url="/ui/overview", status_code=302)


async def overview(request: Request) -> HTMLResponse:
    gw = _get_gateway(request)
    return _TEMPLATES.TemplateResponse(request, "overview.html", _common_context(request, gw))


async def memories(request: Request) -> HTMLResponse:
    gw = _get_gateway(request)
    q = (request.query_params.get("q") or "").strip().lower()
    entity = request.query_params.get("entity") or None
    status = request.query_params.get("status") or None
    include_deleted = status == "deleted"
    rows = gw.list_memories(entity=entity, limit=200, include_deleted=include_deleted)
    if status and status != "deleted":
        rows = [m for m in rows if getattr(m, "status", "active") == status]
    if q:
        rows = [m for m in rows if q in (m.content or "").lower() or q in (m.id or "").lower()]
    ctx = _common_context(request, gw)
    ctx.update({
        "memories": [_memory_to_dict(m) for m in rows],
        "filters": {"q": q, "entity": entity or "", "status": status or ""},
    })
    return _TEMPLATES.TemplateResponse(request, "memories.html", ctx)


async def memory_detail(request: Request) -> HTMLResponse:
    gw = _get_gateway(request)
    mem_id = request.path_params["memory_id"]
    m = gw.get(mem_id, include_deleted=True)
    if m is None:
        return HTMLResponse("<h1>Not found</h1>", status_code=404)
    chain: list[dict[str, Any]] = []
    try:
        c = gw.get_supersession_chain(mem_id)
        chain = [
            _memory_to_dict(gw.get(mid, include_deleted=True)) for mid in c.memory_ids
        ]
    except Exception:
        pass
    ctx = _common_context(request, gw)
    ctx.update({"m": _memory_to_dict(m), "chain": chain})
    return _TEMPLATES.TemplateResponse(request, "memory_detail.html", ctx)


async def retrieval(request: Request) -> HTMLResponse:
    gw = _get_gateway(request)
    from open_arangodb.models import RetrievalConfig, RetrievalRequest

    query = (request.query_params.get("q") or "").strip()
    entity = request.query_params.get("entity") or None
    tags = [t for t in (request.query_params.get("tags") or "").split(",") if t.strip()]
    layers = request.query_params.getlist("layer") or ["exact", "tag", "semantic", "temporal"]
    results: list[dict[str, Any]] = []
    if query:
        req = RetrievalRequest(
            query=query,
            entity=entity,
            tags=tags or None,
            config=RetrievalConfig(layers=layers, max_results=25),
        )
        try:
            for r in gw.retrieve(req):
                results.append({
                    "score": round(float(getattr(r, "score", 0.0) or 0.0), 4),
                    "layer": getattr(r, "source_layer", "?"),
                    "memory": _memory_to_dict(getattr(r, "memory", None)),
                })
        except Exception as exc:  # noqa: BLE001 — surface to UI
            logger.warning("retrieve failed: %s", exc)

    ctx = _common_context(request, gw)
    ctx.update({
        "query": query,
        "entity": entity or "",
        "tags": ",".join(tags),
        "layers": layers,
        "all_layers": ["exact", "tag", "semantic", "temporal"],
        "results": results,
    })
    return _TEMPLATES.TemplateResponse(request, "retrieval.html", ctx)


async def vector(request: Request) -> HTMLResponse:
    gw = _get_gateway(request)
    query = (request.query_params.get("q") or "").strip()
    limit = int(request.query_params.get("limit") or 10)
    results: list[dict[str, Any]] = []
    if query:
        try:
            raw = gw.search(query, limit=limit)
            for r in raw:
                results.append({
                    "score": round(float(r.get("score", 0.0) or 0.0), 4),
                    "memory_id": r.get("memory_id"),
                    "content": r.get("content", ""),
                })
        except Exception as exc:  # noqa: BLE001
            logger.warning("vector search failed: %s", exc)

    ctx = _common_context(request, gw)
    ctx.update({"query": query, "limit": limit, "results": results})
    return _TEMPLATES.TemplateResponse(request, "vector.html", ctx)


async def graph_page(request: Request) -> HTMLResponse:
    gw = _get_gateway(request)
    ctx = _common_context(request, gw)
    graphs = list((getattr(gw._graph, "_graph_configs", {}) or {}).keys()) if gw._graph else []
    ctx.update({"graphs": graphs})
    return _TEMPLATES.TemplateResponse(request, "graph.html", ctx)


async def graph_json(request: Request) -> JSONResponse:
    gw = _get_gateway(request)
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    try:
        for col_name in ["people", "nodes"]:
            col = gw._db.collection(col_name) if gw._db.has_collection(col_name) else None
            if col is None:
                continue
            for doc in col.all():
                nodes.append({
                    "id": f"{col_name}/{doc.get('_key')}",
                    "label": doc.get("name") or doc.get("_key"),
                    "collection": col_name,
                })
        for col_name in ["knows", "links"]:
            if not gw._db.has_collection(col_name):
                continue
            for doc in gw._db.collection(col_name).all():
                edges.append({
                    "id": doc.get("_id") or doc.get("_key"),
                    "source": doc.get("_from"),
                    "target": doc.get("_to"),
                    "kind": col_name,
                })
    except Exception as exc:  # noqa: BLE001
        logger.warning("graph_json failed: %s", exc)
    return JSONResponse({"nodes": nodes, "edges": edges})


async def temporal(request: Request) -> HTMLResponse:
    gw = _get_gateway(request)
    entity_q = request.query_params.get("entity") or ""
    chains: list[dict[str, Any]] = []
    contradictions: list[dict[str, Any]] = []
    try:
        all_mem = gw.list_memories(limit=500, include_deleted=True)
        seen: set[str] = set()
        for m in all_mem:
            if m.id in seen:
                continue
            try:
                chain = gw.get_supersession_chain(m.id)
            except Exception:
                continue
            if len(chain.memory_ids) < 2:
                continue
            for mid in chain.memory_ids:
                seen.add(mid)
            chains.append({
                "current_id": chain.current_id,
                "ids": list(chain.memory_ids),
                "entity": getattr(m, "entity", None),
            })
        if entity_q:
            contradictions = [
                {
                    "a": c.memory_a_id,
                    "b": c.memory_b_id,
                    "reason": getattr(c, "reason", ""),
                }
                for c in gw.detect_contradictions(entity_q)
            ]
    except Exception as exc:  # noqa: BLE001
        logger.warning("temporal failed: %s", exc)
    ctx = _common_context(request, gw)
    ctx.update({"chains": chains, "entity_q": entity_q, "contradictions": contradictions})
    return _TEMPLATES.TemplateResponse(request, "temporal.html", ctx)


async def cdc(request: Request) -> HTMLResponse:
    gw = _get_gateway(request)
    events: list[dict[str, Any]] = []
    try:
        for e in gw.get_changes():
            op_raw = getattr(e, "op", "")
            op = getattr(op_raw, "value", op_raw)
            events.append({
                "rev": getattr(e, "rev", ""),
                "op": op,
                "memory_id": getattr(e, "memory_id", ""),
                "timestamp": getattr(e, "timestamp", ""),
            })
    except Exception:
        pass
    events.sort(key=lambda r: r.get("timestamp") or "", reverse=True)
    ctx = _common_context(request, gw)
    ctx.update({"events": events[:200]})
    return _TEMPLATES.TemplateResponse(request, "cdc.html", ctx)


async def audit(request: Request) -> HTMLResponse:
    gw = _get_gateway(request)
    events: list[dict[str, Any]] = []
    try:
        col = gw._db.collection("_arangodb_audit")
        for doc in col.all():
            events.append({
                "op": doc.get("op"),
                "collection": doc.get("collection"),
                "document_id": doc.get("document_key") or doc.get("document_id"),
                "agent_id": doc.get("agent_id"),
                "timestamp": doc.get("timestamp"),
            })
    except Exception:
        pass
    events.sort(key=lambda r: r.get("timestamp") or "", reverse=True)
    ctx = _common_context(request, gw)
    ctx.update({"events": events[:200]})
    return _TEMPLATES.TemplateResponse(request, "audit.html", ctx)


async def ops(request: Request) -> HTMLResponse:
    gw = _get_gateway(request)
    satellites: list[dict[str, Any]] = []
    for name, sat in (getattr(gw, "_satellites", {}) or {}).items():
        try:
            s = sat.stats()
            satellites.append({
                "name": name,
                "cached": getattr(s, "cached_count", 0),
                "hits": getattr(s, "hit_count", 0),
                "misses": getattr(s, "miss_count", 0),
            })
        except Exception:
            satellites.append({"name": name, "cached": 0, "hits": 0, "misses": 0})

    encryption = None
    try:
        enc = gw.check_encryption()
        encryption = {
            "encrypted": getattr(enc, "encrypted", False),
            "method": getattr(enc, "method", None),
            "note": getattr(enc, "note", None),
        }
    except Exception:
        pass

    ctx = _common_context(request, gw)
    ctx.update({
        "satellites": satellites,
        "encryption": encryption,
        "replication_enabled": gw._replication is not None,
        "backup_enabled": gw._backup is not None,
    })
    return _TEMPLATES.TemplateResponse(request, "ops.html", ctx)


# ── App factory ─────────────────────────────────────────────────────


def build_app(gateway: Any | None = None) -> Starlette:
    """Return a Starlette app mounting the UI at /ui."""
    routes = [
        Route("/", index),
        Route("/ui", index),
        Route("/ui/", index),
        Route("/ui/overview", overview, name="overview"),
        Route("/ui/memories", memories, name="memories"),
        Route("/ui/memories/{memory_id}", memory_detail, name="memory_detail"),
        Route("/ui/retrieval", retrieval, name="retrieval"),
        Route("/ui/vector", vector, name="vector"),
        Route("/ui/graph", graph_page, name="graph"),
        Route("/ui/graph.json", graph_json, name="graph_json"),
        Route("/ui/temporal", temporal, name="temporal"),
        Route("/ui/cdc", cdc, name="cdc"),
        Route("/ui/audit", audit, name="audit"),
        Route("/ui/ops", ops, name="ops"),
        Mount(
            "/ui/static",
            app=StaticFiles(directory=str(_UI_DIR / "static")),
            name="static",
        ),
    ]
    app = Starlette(routes=routes)
    if gateway is not None:
        app.state.gateway = gateway
    return app

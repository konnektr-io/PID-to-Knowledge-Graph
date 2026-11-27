"""Map a P&ID ``KnowledgeGraph`` to Konnektr Graph payloads.

This module is deliberately SDK-free: it turns ``graph.json`` into plain JSON dicts
that can be written for review (dry-run) or handed to the SDK by ``publish()``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import dtdl
from .models import Edge, KnowledgeGraph, Node


def twin_id(plant_id: str, node_id: str) -> str:
    """Scope an upstream node id so several plants can share one graph."""
    return f"{plant_id}:{node_id}"


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def _snake(name: str) -> str:
    out = []
    for ch in name:
        if ch.isupper():
            out.append("_")
            out.append(ch.lower())
        else:
            out.append(ch)
    return "".join(out)


def _promoted_attributes(node: Node) -> dict[str, Any]:
    """Promote only DTDL-declared properties; everything else stays in attributesJson."""
    values: dict[str, Any] = {}
    for prop, _ in dtdl.NODE_PROPS.get(node.type, []):
        for key in (prop, _snake(prop)):
            value = node.attributes.get(key)
            if isinstance(value, (str, int, float, bool)):
                values[prop] = value
                break
    return values


def node_payload(node: Node, plant_id: str, generated_at: str) -> dict[str, Any]:
    contents: dict[str, Any] = {
        "plantId": plant_id,
        "pidId": node.id,
        "type": node.type,
        "label": node.label,
        "confidence": node.confidence,
        "sheets": list(node.sheets),
        "attributesJson": _json(node.attributes),
        "provenanceJson": _json(
            [p.model_dump(exclude_none=True) for p in node.provenance]
        ),
        "generatedAt": generated_at,
    }
    direct = {
        "tag": node.tag,
        "kind": node.kind,
        "name": node.name,
        "status": node.status,
        "dexpiClass": node.dexpi_class,
    }
    contents.update({k: v for k, v in direct.items() if v is not None})
    contents.update(_promoted_attributes(node))
    return {
        "$dtId": twin_id(plant_id, node.id),
        "$metadata": {"$model": dtdl.dtmi(node.type)},
        **contents,
    }


def edge_payload(edge: Edge, plant_id: str) -> dict[str, Any]:
    props: dict[str, Any] = {
        "pidEdgeId": edge.id,
        "confidence": edge.confidence,
        "derived": edge.derived,
        "attributesJson": _json(edge.attributes),
    }
    if edge.sheet:
        props["sheet"] = edge.sheet
    for key in ("flow_direction", "off_page", "signal_type", "purpose", "drawing_type"):
        if key in edge.attributes:
            value = edge.attributes[key]
            if isinstance(value, (str, int, float, bool)):
                camel = "".join(
                    part.capitalize() if i else part
                    for i, part in enumerate(key.split("_"))
                )
                props[camel] = value
    return {
        "$relationshipId": twin_id(plant_id, edge.id),
        "$sourceId": twin_id(plant_id, edge.source),
        "$targetId": twin_id(plant_id, edge.target),
        "$relationshipName": edge.type,
        **props,
    }


def build_payloads(
    kg: KnowledgeGraph, plant_id: str | None = None
) -> tuple[list[dict], list[dict], list[dict]]:
    """Return (models, twins, relationships) for the whole graph."""
    plant = plant_id or kg.plant.id
    seen: set[str] = set()
    for node in kg.nodes:
        if node.id in seen:
            raise ValueError(f"duplicate node id {node.id}")
        seen.add(node.id)
    models = dtdl.build_models()
    twins = [node_payload(n, plant, kg.generated_at) for n in kg.nodes]
    rels = [edge_payload(e, plant) for e in kg.edges]
    return models, twins, rels


def make_client(endpoint: str | None = None, token: str | None = None):
    """Build an SDK client from environment configuration (no secrets in files)."""
    import os

    from konnektr_graph import KonnektrGraphClient
    from konnektr_graph.auth import StaticTokenCredential

    endpoint = endpoint or os.environ.get("KONNEKTR_ENDPOINT")
    token = token or os.environ.get("KONNEKTR_TOKEN")
    if not endpoint or not token:
        raise RuntimeError("KONNEKTR_ENDPOINT and KONNEKTR_TOKEN are required")
    return KonnektrGraphClient(endpoint, StaticTokenCredential(token))


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def publish(
    kg: KnowledgeGraph,
    *,
    plant_id: str | None = None,
    dry_run: bool = False,
    out_dir: Path | None = None,
    batch_size: int = 500,
    client: Any = None,
    report_path: Path | None = None,
) -> dict[str, Any]:
    """Publish (or dry-run) all models, twins and relationships for one plant."""
    if batch_size < 1:
        raise ValueError("batch_size must be >= 1")
    models, twins, rels = build_payloads(kg, plant_id)
    if dry_run:
        out = Path(out_dir) if out_dir else Path("konnektr")
        out.mkdir(parents=True, exist_ok=True)
        for name, data in (("models", models), ("twins", twins), ("relationships", rels)):
            _write_json(out / f"{name}.json", data)
    else:
        # SDK types are imported here so dry-run needs no SDK installation.
        from konnektr_graph.types import (
            BasicDigitalTwin,
            BasicRelationship,
            DigitalTwinMetadata,
            DtdlInterface,
        )

        client = client or make_client()
        existing = {m.id for m in client.list_models()}
        missing = [DtdlInterface.from_dict(m) for m in models if m["@id"] not in existing]
        if missing:
            client.create_models(missing)
        for i in range(0, len(twins), batch_size):
            for twin_data in twins[i:i + batch_size]:
                twin = BasicDigitalTwin(
                    dtId=twin_data["$dtId"],
                    metadata=DigitalTwinMetadata(
                        model=twin_data["$metadata"]["$model"]
                    ),
                    contents={
                        k: v for k, v in twin_data.items() if not k.startswith("$")
                    },
                )
                client.upsert_digital_twin(twin.dtId, twin)
        for i in range(0, len(rels), batch_size):
            for rel_data in rels[i:i + batch_size]:
                rel = BasicRelationship(
                    relationshipId=rel_data["$relationshipId"],
                    sourceId=rel_data["$sourceId"],
                    targetId=rel_data["$targetId"],
                    relationshipName=rel_data["$relationshipName"],
                    properties={
                        k: v for k, v in rel_data.items() if not k.startswith("$")
                    },
                )
                client.upsert_relationship(rel.sourceId, rel.relationshipId, rel)

    report: dict[str, Any] = {
        "models": len(models),
        "twins": len(twins),
        "relationships": len(rels),
        "batches": (len(twins) + batch_size - 1) // batch_size,
        "dry_run": dry_run,
        "plant": plant_id or kg.plant.id,
    }
    if report_path:
        Path(report_path).write_text(
            "# Konnektr publish report\n\n"
            f"- plant: {report['plant']}\n"
            f"- models: {report['models']}\n"
            f"- twins: {report['twins']}\n"
            f"- relationships: {report['relationships']}\n"
            f"- batches: {report['batches']}\n"
            f"- dry run: {dry_run}\n",
            encoding="utf-8",
        )
    return report

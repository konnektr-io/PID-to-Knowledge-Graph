"""Map a P&ID ``KnowledgeGraph`` to Konnektr Graph payloads.

This module is deliberately SDK-free: it turns ``graph.json`` into plain JSON dicts
that can be written for review (dry-run) or handed to the SDK by ``publish()``.
"""

from __future__ import annotations

import json
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
    for key in ("flow_direction", "off_page", "signal_type", "purpose"):
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

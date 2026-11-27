import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "pid-to-kg" / "scripts"))


def test_every_node_and_edge_maps(mini_kg):
    from pidkg.konnektr import build_payloads

    models, twins, rels = build_payloads(mini_kg, plant_id="mini")
    assert len(models) == 11
    assert len(twins) == len(mini_kg.nodes)
    assert len(rels) == len(mini_kg.edges)
    assert all(t["$dtId"].startswith("mini:") for t in twins)
    assert all(t["$metadata"]["$model"].startswith("dtmi:konnektr:pidkg:") for t in twins)
    assert all(r["$relationshipId"].startswith("mini:") for r in rels)


def test_attributes_and_provenance_survive(mini_kg):
    from pidkg.konnektr import build_payloads

    _, twins, rels = build_payloads(mini_kg, plant_id="mini")
    assert all("attributesJson" in t and "provenanceJson" in t for t in twins)
    assert all("attributesJson" in r for r in rels)
    source = mini_kg.nodes[0]
    twin = next(t for t in twins if t["pidId"] == source.id)
    assert twin["pidId"] == source.id
    assert twin["label"] == source.label
    assert twin["confidence"] == source.confidence


def test_relationship_endpoints_are_scoped(mini_kg):
    from pidkg.konnektr import build_payloads

    _, _, rels = build_payloads(mini_kg, plant_id="p")
    ids = {n.id for n in mini_kg.nodes}
    for edge, rel in zip(mini_kg.edges, rels):
        assert rel["$sourceId"] == f"p:{edge.source}"
        assert rel["$targetId"] == f"p:{edge.target}"
        assert rel["$relationshipName"] == edge.type
        assert edge.source in ids and edge.target in ids


def test_duplicate_node_ids_are_rejected(mini_kg):
    import pytest

    from pidkg.konnektr import build_payloads

    dup = mini_kg.model_copy(deep=True)
    dup.nodes.append(dup.nodes[0].model_copy(deep=True))
    with pytest.raises(ValueError, match="duplicate node id"):
        build_payloads(dup, plant_id="mini")


def test_undeclared_attributes_stay_json_encoded(mini_kg):
    from pidkg.konnektr import build_payloads

    kg = mini_kg.model_copy(deep=True)
    kg.nodes[0].attributes = {"a_strange_field": {"nested": 1}}
    _, twins, _ = build_payloads(kg, plant_id="mini")
    twin = next(t for t in twins if t["pidId"] == kg.nodes[0].id)
    assert "a_strange_field" not in twin
    assert "a_strange_field" in twin["attributesJson"]

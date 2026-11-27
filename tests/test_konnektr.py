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


def test_dry_run_writes_payloads_and_never_calls_make_client(mini_kg, tmp_path, monkeypatch):
    import pidkg.konnektr as k

    monkeypatch.setattr(
        k, "make_client",
        lambda: (_ for _ in ()).throw(AssertionError("network called in dry run")),
    )
    report = k.publish(mini_kg, plant_id="mini", dry_run=True, out_dir=tmp_path)
    assert (tmp_path / "models.json").exists()
    assert (tmp_path / "twins.json").exists()
    assert (tmp_path / "relationships.json").exists()
    assert report["twins"] == len(mini_kg.nodes)
    assert report["dry_run"] is True


def test_publish_uploads_only_missing_models(mini_kg, monkeypatch):
    import pidkg.konnektr as k

    class Existing:
        id = "dtmi:konnektr:pidkg:PidNode;1"

    class Fake:
        def __init__(self):
            self.created = []
            self.twins = []
            self.rels = []

        def list_models(self):
            return [Existing()]

        def create_models(self, models):
            self.created.extend(models)

        def upsert_digital_twin(self, _id, twin):
            self.twins.append(twin)

        def upsert_relationship(self, _src, _rid, rel):
            self.rels.append(rel)

    fake = Fake()
    monkeypatch.setattr(k, "make_client", lambda: fake)
    report = k.publish(mini_kg, plant_id="mini", batch_size=3, client=fake)
    assert len(fake.created) == 10  # PidNode already existed
    assert len(fake.twins) == len(mini_kg.nodes)
    assert len(fake.rels) == len(mini_kg.edges)
    assert report["batches"] == (len(mini_kg.nodes) + 2) // 3
    assert all(t.metadata.model.startswith("dtmi:") for t in fake.twins)
    assert all(r.relationshipName in {"FLOWS_TO", "FEEDS", "MEASURES", "SIGNAL_TO",
                                      "MEMBER_OF", "ACTUATES", "CASCADES_TO", "TRIPS",
                                      "PART_OF"} for r in fake.rels)


def test_report_file_is_written(mini_kg, tmp_path, monkeypatch):
    import pidkg.konnektr as k

    monkeypatch.setattr(k, "make_client", lambda: (_ for _ in ()).throw(AssertionError()))
    report_path = tmp_path / "konnektr_report.md"
    k.publish(mini_kg, plant_id="mini", dry_run=True, out_dir=tmp_path,
              report_path=report_path)
    text = report_path.read_text(encoding="utf-8")
    assert "Konnektr publish report" in text
    assert "dry run: True" in text


def test_cli_dry_run_on_a_kg_directory(mini_kg, tmp_path, capsys):
    import publish_konnektr

    kg_dir = tmp_path / "kg"
    kg_dir.mkdir()
    (kg_dir / "graph.json").write_text(
        mini_kg.model_dump_json(indent=1, exclude_none=True), encoding="utf-8"
    )
    rc = publish_konnektr.main([str(kg_dir), "--dry-run", "--plant-id", "cli"])
    assert rc == 0
    payloads = kg_dir / "konnektr"
    assert (payloads / "models.json").exists()
    assert (payloads / "twins.json").exists()
    assert (kg_dir / "konnektr_report.md").exists()
    out = capsys.readouterr().out
    assert "cli:" in out and "dry-run payloads" in out


def test_generated_models_roundtrip_through_sdk(mini_kg):
    from konnektr_graph.types import DtdlInterface

    from pidkg.konnektr import build_payloads

    models, _, _ = build_payloads(mini_kg, plant_id="mini")
    for model in models:
        sdk_model = DtdlInterface.from_dict(model)
        out = sdk_model.to_dict()
        assert out["@id"] == model["@id"]
        assert out["@context"] == "dtmi:dtdl:context;4"
        assert out["contents"] == model["contents"]
        assert out.get("extends") == model.get("extends")

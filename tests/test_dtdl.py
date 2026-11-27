import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "pid-to-kg" / "scripts"))


def test_generated_models_are_dtdl_v4():
    from pidkg.dtdl import build_models

    models = build_models()
    assert len(models) == 11
    assert all(m["@context"] == "dtmi:dtdl:context;4" for m in models)
    assert all(m["@type"] == "Interface" for m in models)
    ids = [m["@id"] for m in models]
    assert len(ids) == len(set(ids))
    base = next(m for m in models if m["@id"] == "dtmi:konnektr:pidkg:PidNode;1")
    names = {c["name"] for c in base["contents"]}
    assert names >= {"FLOWS_TO", "FEEDS", "MEASURES", "SIGNAL_TO", "ACTUATES",
                     "MEMBER_OF", "CASCADES_TO", "TRIPS", "PART_OF"}


def test_live_signal_has_telemetry_and_writable_properties():
    from pidkg.dtdl import build_models

    live = next(m for m in build_models() if m["@id"].endswith(":LiveSignal;1"))
    telemetry = [c for c in live["contents"] if c["@type"] == "Telemetry"]
    properties = [c for c in live["contents"] if c["@type"] == "Property"]
    assert {c["name"] for c in telemetry} == {"value", "quality", "timestamp", "source"}
    assert {c["name"] for c in properties} == {
        "lastValue", "lastQuality", "lastTimestamp", "lastSource"
    }
    assert all(p.get("writable") is True for p in properties)


def test_node_interfaces_extend_base_and_live_signal():
    from pidkg.dtdl import NODE_TYPES, build_models, dtmi

    by_id = {m["@id"]: m for m in build_models()}
    assert set(NODE_TYPES) == {
        "Plant", "Sheet", "Equipment", "PipeSegment", "Component",
        "Instrument", "ControlLoop", "OffPageConnector", "Boundary"
    }
    for node_type in NODE_TYPES:
        extends = set(by_id[dtmi(node_type)]["extends"])
        assert dtmi("PidNode") in extends
        assert (dtmi("LiveSignal") in extends) == (node_type in ("Instrument", "Equipment"))


def test_relationship_properties_and_target():
    from pidkg.dtdl import build_models, dtmi

    base = next(m for m in build_models() if m["@id"] == dtmi("PidNode"))
    rels = [c for c in base["contents"] if c["@type"] == "Relationship"]
    assert all(r["target"] == dtmi("PidNode") for r in rels)
    assert all({"pidEdgeId", "confidence", "derived", "sheet", "attributesJson"}
               <= {p["name"] for p in r["properties"]} for r in rels)

"""DTDL v4 interfaces for the P&ID knowledge-graph ontology.

The vocabulary mirrors ``references/ontology.md``. Interfaces are generated from
these tables so there is one source of truth; ``pidkg.konnektr`` writes the result
alongside ``graph.json`` for review.
"""

from __future__ import annotations

CONTEXT = "dtmi:dtdl:context;4"
NS = "dtmi:konnektr:pidkg"

# Keep in sync with references/ontology.md (9 node types, 9 edge types).
NODE_TYPES = (
    "Plant", "Sheet", "Equipment", "PipeSegment", "Component", "Instrument",
    "ControlLoop", "OffPageConnector", "Boundary",
)
EDGE_TYPES = (
    "FLOWS_TO", "FEEDS", "MEASURES", "SIGNAL_TO", "ACTUATES",
    "MEMBER_OF", "CASCADES_TO", "TRIPS", "PART_OF",
)

BASE_PROPS = [
    ("plantId", "string"), ("pidId", "string"), ("type", "string"),
    ("label", "string"), ("tag", "string"), ("kind", "string"), ("name", "string"),
    ("status", "string"), ("dexpiClass", "string"), ("sheets", "Array"),
    ("confidence", "double"), ("provenanceJson", "string"),
    ("attributesJson", "string"), ("sourceFile", "string"),
    ("generatedAt", "dateTime"),
]
REL_PROPS = [
    ("pidEdgeId", "string"), ("confidence", "double"), ("derived", "boolean"),
    ("sheet", "string"), ("attributesJson", "string"),
    ("flowDirection", "string"), ("offPage", "boolean"),
    ("signalType", "string"), ("purpose", "string"),
    ("drawingType", "string"),
]
NODE_PROPS = {
    "Sheet": [("drawingNumber", "string"), ("revision", "string"), ("drawingType", "string")],
    "PipeSegment": [("lineNumber", "string"), ("size", "string"), ("service", "string")],
    "Component": [
        ("actuator", "string"), ("failPosition", "string"), ("normalPosition", "string"),
        ("size", "string"), ("role", "string"), ("loopKey", "string"),
    ],
    "Instrument": [
        ("variable", "string"), ("role", "string"), ("location", "string"),
        ("loopKey", "string"), ("inline", "boolean"),
    ],
    "ControlLoop": [
        ("loopType", "string"), ("variable", "string"),
        ("description", "string"), ("cascadeMaster", "string"),
    ],
    "OffPageConnector": [
        ("direction", "string"), ("otherDrawing", "string"), ("otherItem", "string"),
    ],
    "Boundary": [("direction", "string")],
}
LIVE_TELEMETRY = [
    ("value", "double"), ("quality", "string"),
    ("timestamp", "dateTime"), ("source", "string"),
]
LIVE_PROPERTIES = [
    ("lastValue", "double"), ("lastQuality", "string"),
    ("lastTimestamp", "dateTime"), ("lastSource", "string"),
]


def dtmi(name: str) -> str:
    """DTMI for a name in this ontology's namespace."""
    return f"{NS}:{name};1"


def _prop(name: str, schema: str | dict, writable: bool = False) -> dict:
    if schema == "Array":
        schema = {"@type": "Array", "elementSchema": "string"}
    prop: dict[str, object] = {"@type": "Property", "name": name, "schema": schema}
    if writable:
        prop["writable"] = True
    return prop


def _interface(name: str, contents: list[dict], extends: list[str] | None = None) -> dict:
    model = {
        "@context": CONTEXT,
        "@id": dtmi(name),
        "@type": "Interface",
        "displayName": name,
        "contents": contents,
    }
    if extends:
        model["extends"] = extends
    return model


def build_models() -> list[dict]:
    """Return the 11 DTDL v4 interfaces: base, LiveSignal, and 9 node types."""
    base = [_prop(name, schema) for name, schema in BASE_PROPS]
    base += [
        {
            "@type": "Relationship",
            "name": edge,
            "target": dtmi("PidNode"),
            "properties": [_prop(name, schema) for name, schema in REL_PROPS],
        }
        for edge in EDGE_TYPES
    ]

    live = [
        {"@type": "Telemetry", "name": name, "schema": schema}
        for name, schema in LIVE_TELEMETRY
    ]
    live += [_prop(name, schema, writable=True) for name, schema in LIVE_PROPERTIES]

    models = [_interface("PidNode", base), _interface("LiveSignal", live)]
    for node_type in NODE_TYPES:
        extends = [dtmi("PidNode")]
        if node_type in ("Instrument", "Equipment"):
            extends.append(dtmi("LiveSignal"))
        models.append(
            _interface(
                node_type,
                [_prop(name, schema) for name, schema in NODE_PROPS.get(node_type, [])],
                extends,
            )
        )
    return models

# DTDL v4 mapping for Konnektr Graph

This fork publishes the P&ID graph from [`ontology.md`](ontology.md) as DTDL v4
interfaces (`@context: "dtmi:dtdl:context;4"`). The generator is
`scripts/pidkg/dtdl.py`; the publisher is `scripts/pidkg/konnektr.py`.

## Interfaces

| DTMI | Extends | Purpose |
| --- | --- | --- |
| `dtmi:konnektr:pidkg:PidNode;1` | — | Shared properties and all 9 relationships |
| `dtmi:konnektr:pidkg:LiveSignal;1` | — | Telemetry and writable properties for live values |
| `...:Plant;1`, `...:Sheet;1`, `...:Equipment;1`, `...:PipeSegment;1`, `...:Component;1`, `...:Instrument;1`, `...:ControlLoop;1`, `...:OffPageConnector;1`, `...:Boundary;1` | `PidNode` (+ `LiveSignal` for `Instrument` and `Equipment`) | One interface per upstream node type |

`PidNode` properties: `plantId`, `pidId`, `type`, `label`, `tag`, `kind`, `name`,
`status`, `dexpiClass`, `sheets` (array of string), `confidence`, `provenanceJson`,
`attributesJson`, `sourceFile`, `generatedAt`.

Relationships (all declared on `PidNode`, target is the base interface by reference):
`FLOWS_TO`, `FEEDS`, `MEASURES`, `SIGNAL_TO`, `ACTUATES`, `MEMBER_OF`, `CASCADES_TO`,
`TRIPS`, `PART_OF`. Each carries `pidEdgeId`, `confidence`, `derived`, `sheet`,
`attributesJson`, `flowDirection`, `offPage`, `signalType`, `purpose`, `drawingType`.

Type-specific properties are declared per node interface (for example `Instrument`:
`variable`, `role`, `location`, `loopKey`, `inline`; `ControlLoop`: `loopType`,
`description`). Any upstream attribute without a declared DTDL property is kept as
JSON in `attributesJson`; provenance is kept in `provenanceJson`. Nothing is lost.

## Ids and scoping

- Twin id: `{plantId}:{nodeId}`; the unscoped upstream id is `pidId`.
- Relationship id: `{plantId}:{edgeId}`; source/target are scoped twin ids.
- Relationship name (Cypher label): the uppercase upstream edge type.

Scoping lets several plants share one Konnektr Graph without tag collisions.

## Live values: declaration only

`LiveSignal` declares:

- Telemetry: `value` (double), `quality` (string), `timestamp` (dateTime), `source` (string).
- Writable properties: `lastValue`, `lastQuality`, `lastTimestamp`, `lastSource`.

`Instrument` and `Equipment` extend this interface. That makes it possible for an
external ingestion pipeline (for example Arcadis Flows) to map a live tag to the twin
id and either patch the current-value properties or publish telemetry to the twin.
**This fork never writes these fields and contains no MQTT/OPC-UA/webhook client.**
Streaming, buffering, security and retention belong to that pipeline.

Konnektr Graph validates models on upload and twins on create/replace, but not after
a JSON Patch. That is another reason to keep the live writes outside this skill and
to test model upload before relying on the ontology.

## Queries

See [`cypher-queries.md`](cypher-queries.md) for downstream/upstream traversal,
instruments, loops, equipment flow and reading current values. No ADT-SQL query
dialect is used by this fork.

# P&ID → Konnektr Graph sink (DTDL v4)

Date: 2026-11-27
Status: draft for review

## 1. Context and goals

`ScottDuncanAI/PID-to-Knowledge-Graph` is a Claude skill that reads P&ID/PFD PDFs and
builds a typed property graph. Its canonical output is `graph.json`; DuckDB, Neo4j,
GraphML and DEXPI are downstream outputs. We fork it into the Konnektr org and **add
Konnektr Graph as one more sink**, leaving the extraction pipeline and the existing
sinks untouched.

Goals:

- Publish the P&ID graph as DTDL **v4** models, twins and relationships in Konnektr Graph.
- Keep `graph.json` as the canonical, reviewable artifact; every published node and
  edge is traceable to it.
- Document **Cypher** queries for the graph (no ADT-SQL query dialect work).
- Make the DTDL ready for live values: declare telemetry and writable properties so an
  external ingestion pipeline (e.g. Arcadis Flows) can attach live data by patching a
  twin or publishing telemetry to it. **No live-feed bridge code is in scope.**

Non-goals:

- MQTT/OPC-UA/webhook ingest, telemetry forwarding, or a feed CLI.
- Removing or replacing DuckDB.
- Changing PDF probing, rendering, extraction, graph building, QA or DEXPI.
- Deploying or configuring a Konnektr Graph cluster.

## 2. Verified ground truth

- Upstream ontology (`skills/pid-to-kg/references/ontology.md`, `pidkg/models.py`):
  9 node types — Plant, Sheet, Equipment, PipeSegment, Component, Instrument,
  ControlLoop, OffPageConnector, Boundary — and 9 edge types — FLOWS_TO, FEEDS,
  MEASURES, SIGNAL_TO, ACTUATES, MEMBER_OF, CASCADES_TO, TRIPS, PART_OF.
  `graph.json` carries ids, labels, tags, kinds, attributes, provenance, confidence,
  derived flags and sheet references for every node/edge.
- Upstream `build_kg.py` writes `graph.json`, `graph.duckdb`, `summary.md`,
  `qa_report.md` and DEXPI files from the same `KnowledgeGraph` object.
- Konnektr Graph (source and docs): DTDL v2–v4 models; models validated with
  DTDLParser on upload; twins validated on create/replace, **not** after a PATCH;
  batch endpoints capped by `MaxBatchSize` (default 2000).
- Python SDK `konnektr-graph`: `create_models`, `upsert_digital_twin`,
  `upsert_relationship`, `query_twins` (returns raw result dicts, accepts Cypher
  with `$parameters`), `update_digital_twin` (JSON Patch), `publish_telemetry`.
  Only the first four are used by this fork.
- DTDL v4 spec (`DTDL.v4.md`): `@context` is exactly `dtmi:dtdl:context;4`;
  `@id` is a DTMI; `extends` is a set of DTMIs; `Relationship.target` is an optional
  by-reference DTMI; Relationship supports `properties`; Telemetry and writable
  Property are standard contents.

## 3. Architecture

Unchanged: `probe_pdf.py` → `render_pages.py` → `make_hints.py` → Claude extracts each
sheet → `build_kg.py` → `graph.json` + summaries + QA + DEXPI.

Added:

| Path | Purpose |
| --- | --- |
| `skills/pid-to-kg/scripts/pidkg/dtdl.py` | Generate DTDL v4 interfaces from the existing ontology vocabulary |
| `skills/pid-to-kg/scripts/pidkg/konnektr.py` | Map `KnowledgeGraph` → models/twins/relationships; publish through the SDK |
| `skills/pid-to-kg/scripts/publish_konnektr.py` | Standalone publish/dry-run CLI over an existing `graph.json` |
| `skills/pid-to-kg/references/ontology-dtdl.md` | Node/edge → DTDL mapping table, twin-id scheme, live-value contract |
| `skills/pid-to-kg/references/cypher-queries.md` | Cypher equivalents of the existing traversal queries |
| `tests/test_konnektr.py` | Offline tests for generation, mapping, dry-run and idempotency |

`build_kg.py` gains an optional `--publish-konnektr` flag that calls the same publish
function after the existing outputs are written. Without the flag, behaviour is exactly
as upstream. DuckDB stays.

Configuration is environmental only: `KONNEKTR_ENDPOINT` and `KONNEKTR_TOKEN` (used
through the SDK's `StaticTokenCredential`); `KONNEKTR_PLANT_ID` overrides the `plant.id`
read from `graph.json`; `KONNEKTR_BATCH_SIZE` defaults to 500. Missing endpoint or token
is a hard error before any API call. No credentials in the repo or in `SKILL.md`.

## 4. DTDL v4 ontology

All DTMIs use `dtmi:konnektr:pidkg:…;1` and `@context: "dtmi:dtdl:context;4"`.

- `PidNode` (base interface): common properties `plantId`, `pidId`, `label`, `tag`,
  `kind`, `name`, `status`, `dexpiClass`, `sheets` (array of string), `confidence`
  (double), `provenanceJson` (string), `attributesJson` (string), `sourceFile`,
  `generatedAt`. It declares all 9 relationships with `target` = the `PidNode` DTMI
  (by reference, so no cross-interface dependency) and relationship properties
  `pidEdgeId`, `confidence`, `derived`, `sheet`, `attributesJson`, `flowDirection`,
  `offPage`, `signalType`, `purpose`.
- One derived interface per node type, each `extends` `PidNode` and adds its
  type-specific fields (e.g. Instrument: `variable`, `functions`, `role`, `location`,
  `loopKey`, `inline`; ControlLoop: `loopType`, `variable`, `sensors`, `controllers`,
  `finalElements`, `cascadeMaster`, `cascadeSlaves`, `description`).
- `LiveSignal` interface, extended by `Instrument` and `Equipment`: Telemetry
  `value` (double), `quality` (string), `timestamp` (dateTime), `source` (string),
  and writable Properties `lastValue` (double), `lastQuality` (string),
  `lastTimestamp` (dateTime), `lastSource` (string). This is the **only** live-data
  concession: an external ingester can map a tag to a twin id and patch/publish these
  fields. This fork never writes them.
- Nested or type-specific values that have no promoted DTDL property stay as
  JSON-encoded strings in `attributesJson` / `provenanceJson`, so no P&ID information
  is lost.
- Twin id is `{plantId}:{nodeId}`; the unscoped upstream id is kept in `pidId`.
  Relationship id is `{plantId}:{edgeId}`. This lets several plants share one Graph
  without tag collisions.

## 5. Publication semantics

`publish_konnektr.py <work>/<plant>/kg` (or `build_kg.py --publish-konnektr`):

1. Read `graph.json` through the existing `KnowledgeGraph` model.
2. Generate the DTDL v4 interfaces and upload them with `create_models`; a model that
   already exists is accepted as-is (idempotent re-publish).
3. Upsert twins, then relationships, in batches of at most `KONNEKTR_BATCH_SIZE`
   (default 500, safely under the documented 2000 ceiling).
4. `--dry-run` writes models, twins and relationships as reviewable JSON under
   `<work>/kg/konnektr/` and makes no API calls.
5. No deletion by default; a rebuild upserts the same ids. Optional `--replace` deletes
   twins and relationships for that plant before publishing.
6. Write `konnektr_report.md` with counts, skipped items and errors.
7. Fail loudly on authentication, validation and batch errors; never silently drop a
   node or edge.

## 6. Cypher queries

`references/cypher-queries.md` gives parameterised Cypher for the existing questions:
downstream/upstream traversal over `FLOWS_TO` (variable-length paths, with the PFD
filter where applicable), instruments and what they measure, control loops and final
elements, and equipment-level `FEEDS`. Examples use `query_twins(query,
query_parameters={...})`. `kg_query.py --konnektr --query "<cypher>"` executes a single
query and prints raw result rows. No ADT-SQL equivalents are written.

## 7. Tests and verification

- Offline pytest suite (fake SDK client, no credentials): generated models are valid
  DTDL v4 shape (`@context`, DTMIs, `extends`, 9 relationships, LiveSignal contents);
  every node and edge in a synthetic two-sheet graph maps to exactly one twin and one
  relationship; ids and provenance survive; dry-run writes payloads and performs no
  network calls; re-publish is idempotent; batching respects the configured size.
- Existing upstream tests must stay green.
- Integration check against a real Konnektr Graph instance: upload the generated
  models, publish the synthetic plant, run the documented Cypher traversals and
  confirm results. If no instance is available at implementation time, say so plainly
  and leave the integration check as a documented manual step — do not claim it ran.

## 8. Risks and decisions taken

- **Live data**: declaration only. Ingest belongs to the stream pipeline; no bridge,
  no broker client, no HTTP feed endpoint.
- **Sink selection**: additive. DuckDB and the other exporters remain available.
- **Relationship targets**: DTDL v4 `target` is by reference and optional; targeting
  the base interface is sufficient and avoids a hard dependency on every derived
  interface. If upload validation rejects it, omit `target` rather than inventing a
  new interface.
- **Patch validation**: Konnektr validates twins at create/replace, not after PATCH.
  That is why live fields are declared in the model but are never written by this fork.
- **Repo home**: fork under `konnektr-io` (product-specific fork); branch + PR, never
  commit to main. Preserve upstream MIT license.

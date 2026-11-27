# Cypher queries for a published P&ID graph

Twins are published with `$dtId = {plantId}:{nodeId}` and a `type` property holding
the upstream node type (`Equipment`, `Instrument`, …). Relationships use the uppercase
edge type as their label and carry `confidence`, `derived`, `sheet`, `attributesJson`
and any promoted edge attributes. Property names containing `$` need backticks.

Run a single query with:

```bash
python skills/pid-to-kg/scripts/kg_query.py --konnektr --query "<cypher>" --json
```

Credentials come from `KONNEKTR_ENDPOINT` and `KONNEKTR_TOKEN`. All queries below use
parameters (`$...`) supplied through the SDK's `query_parameters` mechanism; quote the
`$` in your shell or use the CLI with literal values.

> The relationship labels below use the uppercase `$relationshipName` written by this
> fork (`FLOWS_TO`, `FEEDS`, …). Confirm the label case against your instance once
> before relying on these queries; ADT-style lowercase labels would need adjusting.

## downstream

Everything reachable downstream of an item, shortest hop count first. The `drawingType`
filter keeps P&ID detail when both P&IDs and PFDs are present (same rule as the local
`kg_query.py`).

```cypher
MATCH p = (a:Twin)-[:FLOWS_TO*1..12]->(b:Twin)
WHERE a.`$dtId` = $id
  AND all(r IN relationships(p) WHERE coalesce(r.drawingType, '') <> 'pfd')
RETURN b.`$dtId` AS id, b.type AS type, b.label AS label, min(length(p)) AS hops
ORDER BY hops, id
```

Parameters: `id`, e.g. `mini:660-TK-001`. Pass `$equipment=true` and add
`AND b.type IN ['Equipment','Boundary']` to get equipment-level results.

## upstream

The same walk with the arrow reversed.

```cypher
MATCH p = (b:Twin)-[:FLOWS_TO*1..12]->(a:Twin)
WHERE b.`$dtId` = $id
  AND all(r IN relationships(p) WHERE coalesce(r.drawingType, '') <> 'pfd')
RETURN a.`$dtId` AS id, a.type AS type, a.label AS label, min(length(p)) AS hops
ORDER BY hops, id
```

## instruments

Where each instrument senses the process, with its loop membership.

```cypher
MATCH (i:Twin)-[:MEASURES]->(m:Twin)
OPTIONAL MATCH (i)-[:MEMBER_OF]->(l:Twin)
WHERE i.type = 'Instrument'
RETURN i.`$dtId` AS id, i.tag AS tag, i.variable AS variable, i.role AS role,
       i.location AS location, m.`$dtId` AS measuresId, m.label AS measuresLabel,
       l.`$dtId` AS loopId
ORDER BY id
```

Add `AND i.variable = $variable` (in the `MATCH` clause) to filter by variable, e.g.
`flow`.

## loops

Members of one inferred control loop and the role each plays.

```cypher
MATCH (member:Twin)-[r:MEMBER_OF]->(l:Twin)
WHERE l.`$dtId` = $id
RETURN member.`$dtId` AS id, member.type AS type, member.tag AS tag,
       r.role AS role, r.confidence AS confidence
ORDER BY role, id
```

To list loops and their final elements:

```cypher
MATCH (l:Twin)-[:ACTUATES]->(final:Twin)
WHERE l.type = 'ControlLoop'
RETURN l.`$dtId` AS loop, l.description AS description,
       collect(final.`$dtId`) AS finalElements
ORDER BY loop
```

## equipment_flow

The equipment-level `FEEDS` sheet, with the pipes and in-line items between two units.

```cypher
MATCH (a:Twin)-[r:FEEDS]->(b:Twin)
WHERE a.type IN ['Equipment','Boundary'] AND b.type IN ['Equipment','Boundary']
RETURN a.`$dtId` AS fromId, a.label AS fromLabel,
       b.`$dtId` AS toId, b.label AS toLabel,
       r.attributesJson AS attributes
ORDER BY fromLabel, toLabel
```

## Live values

`Instrument` and `Equipment` twins extend the `LiveSignal` DTDL interface, so an
external ingestion pipeline can patch `lastValue`, `lastQuality`, `lastTimestamp` and
`lastSource`, or publish `value`, `quality`, `timestamp` and `source` as telemetry.
This skill never writes those fields. To read current state:

```cypher
MATCH (i:Twin)
WHERE i.type = 'Instrument' AND i.lastTimestamp IS NOT NULL
RETURN i.`$dtId` AS id, i.lastValue AS value, i.lastQuality AS quality,
       i.lastTimestamp AS timestamp
ORDER BY timestamp DESC
```

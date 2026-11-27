#!/usr/bin/env python3
"""Publish a P&ID knowledge graph to Konnektr Graph (or dry-run it).

    python publish_konnektr.py work/my-plant/kg --dry-run
    python publish_konnektr.py work/my-plant/kg

Reads graph.json and writes models/twins/relationships to Konnektr Graph.
Credentials come from KONNEKTR_ENDPOINT and KONNEKTR_TOKEN, never from files.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pidkg.konnektr import publish  # noqa: E402
from pidkg.models import KnowledgeGraph  # noqa: E402


def _graph_path(kg: Path) -> Path:
    return kg / "graph.json" if kg.is_dir() else kg


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("kg", type=Path, help="kg/ directory or graph.json")
    ap.add_argument("--dry-run", action="store_true", help="write payloads, make no API calls")
    ap.add_argument("--plant-id", help="override the plant id from graph.json")
    ap.add_argument("--batch-size", type=int, default=500)
    ap.add_argument("--out", type=Path, help="payload directory for --dry-run (default: <kg>/konnektr)")
    ap.add_argument("--report", type=Path, help="report path (default: <kg>/konnektr_report.md)")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    graph_path = _graph_path(a.kg)
    if not graph_path.exists():
        print(f"error: no such file: {graph_path}", file=sys.stderr)
        return 2
    kg = KnowledgeGraph.model_validate_json(graph_path.read_text(encoding="utf-8"))
    out = a.out or (graph_path.parent / "konnektr")
    report = a.report or (graph_path.parent / "konnektr_report.md")

    try:
        result = publish(
            kg, plant_id=a.plant_id, dry_run=a.dry_run, out_dir=out,
            batch_size=a.batch_size, report_path=report,
        )
    except (RuntimeError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    print(f"{result['plant']}: {result['models']} models, {result['twins']} twins, "
          f"{result['relationships']} relationships -> "
          f"{'dry-run payloads' if a.dry_run else 'Konnektr Graph'}")
    print(f"  report: {report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

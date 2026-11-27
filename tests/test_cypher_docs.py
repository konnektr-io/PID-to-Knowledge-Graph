import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "skills" / "pid-to-kg" / "references" / "cypher-queries.md"
sys.path.insert(0, str(ROOT / "skills" / "pid-to-kg" / "scripts"))


def test_cypher_doc_has_all_queries_as_fenced_blocks():
    text = DOC.read_text(encoding="utf-8")
    blocks = re.findall(r"```cypher\n(.*?)```", text, re.S)
    assert len(blocks) >= 5
    assert all("MATCH" in block for block in blocks)
    for name in ("downstream", "upstream", "instruments", "loops", "equipment_flow"):
        assert f"## {name}" in text


def test_cypher_doc_is_cypher_only():
    text = DOC.read_text(encoding="utf-8").upper()
    assert "FROM DIGITALTWINS" not in text
    assert "SELECT *" not in text


def test_konnektr_query_mode(monkeypatch, capsys):
    import kg_query

    class Fake:
        def query_twins(self, query, query_parameters=None):
            self.query = query
            return [{"id": "mini:TK-1", "hops": 2}]

    fake = Fake()
    monkeypatch.setattr("pidkg.konnektr.make_client", lambda: fake)
    rc = kg_query.main(["--konnektr", "--query", "MATCH (n) RETURN n", "--json"])
    assert rc == 0
    out = capsys.readouterr().out
    assert '"id": "mini:TK-1"' in out
    assert fake.query == "MATCH (n) RETURN n"

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
sys.path.insert(0, str(ROOT / "skills" / "pid-to-kg" / "scripts"))


def test_build_kg_can_publish_dry_run(tmp_path, monkeypatch):
    import build_kg

    work = tmp_path / "work"
    shutil.copytree(FIXTURES / "mini_plant", work)
    calls = []

    def fake_publish(kg, **kwargs):
        calls.append((kg, kwargs))
        return {"models": 11, "twins": len(kg.nodes),
                "relationships": len(kg.edges), "dry_run": kwargs["dry_run"]}

    monkeypatch.setattr(build_kg, "publish", fake_publish)
    build_kg.main([str(work), "--publish-konnektr", "--dry-run", "--plant-id", "x"])
    assert len(calls) == 1
    kg, kwargs = calls[0]
    assert kwargs["plant_id"] == "x"
    assert kwargs["dry_run"] is True
    assert kwargs["report_path"] == work / "kg" / "konnektr_report.md"
    assert kwargs["out_dir"] == work / "kg" / "konnektr"


def test_build_kg_does_not_publish_without_flag(tmp_path, monkeypatch):
    import build_kg

    work = tmp_path / "work"
    shutil.copytree(FIXTURES / "mini_plant", work)
    monkeypatch.setattr(
        build_kg, "publish",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("publish called without flag")),
    )
    build_kg.main([str(work)])

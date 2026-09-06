import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("claim_verifier", ROOT / "scripts/verify_claims.py")
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


def test_committed_claims_match_numeric_artifacts():
    assert checker.verify(ROOT, ROOT / "results")["status"] == "PASS"


def test_changed_numeric_artifact_fails_even_when_readme_is_unchanged(monkeypatch):
    original = checker.read_json

    def changed(path):
        value = original(path)
        if path.parent.name == "chronological_vm":
            for row in value["family_macro_comparison"]:
                if row["family"] == "pls":
                    row["chronological_mae"] = 99.0
        return value

    monkeypatch.setattr(checker, "read_json", changed)
    result = checker.verify(ROOT, ROOT / "results")
    assert result["status"] == "FAIL"
    assert any(c["id"] == "chronological_mae" and c["status"] == "FAIL"
               for c in result["checks"])

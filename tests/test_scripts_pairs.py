"""The Phase 5 scripts, on a hand-made miniature of HierText and of GLYPHARIS output."""

import gzip
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

SCRIPTS = Path(__file__).parent.parent / "scripts"


def script(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


pairs = script("build_hiertext_pairs")
taxonomy = script("error_taxonomy")


def quad(y: float, x1: float = 400) -> list[list[float]]:
    return [[0, y], [x1, y], [x1, y + 30], [0, y + 30]]


def record(image_id: str, lines: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "image_id": image_id,
        "image_width": 800,
        "image_height": 600,
        "paragraphs": [{"vertices": quad(0), "legible": True, "lines": lines}],
    }


def line(text: str, y: float, **flags: bool) -> dict[str, Any]:
    return {"text": text, "vertices": quad(y), "legible": True, "words": []} | flags


def engine_page(*lines: tuple[str, float]) -> dict[str, Any]:
    return {
        "glypharis_version": "1.0.0",
        "model_version": "glypharis_v1",
        "width": 800,
        "height": 600,
        "lines": [
            {"text": text, "confidence": 0.9, "det_score": 0.9, "bbox": [0, y, 400, y + 30]}
            for text, y in lines
        ],
    }


@pytest.fixture
def built(tmp_path: Path) -> Path:
    records = [
        record("p1", [line("They counted 105 hives.", 0), line("", 50, legible=False)]),
        record("p2", [line("Bees came late.", 0), line("scrawl", 50, handwritten=True)]),
        record("p3", [line("A quiet year.", 0)]),
        record("p4", [line("Spring rain.", 0)]),
    ]
    gt = tmp_path / "validation.jsonl.gz"
    with gzip.open(gt, "wt", encoding="utf-8") as handle:
        json.dump({"info": {"version": "test"}, "annotations": records}, handle)
    engine = tmp_path / "engine"
    engine.mkdir()
    outputs = {
        "p1": engine_page(("They counted 1O5 hives.", 0), ("~~", 50)),
        "p2": engine_page(("Bees carne late.", 0)),
        "p3": engine_page(("A quietyear.", 0), ("speck", 300)),
        "p4": engine_page(),
    }
    for page, data in outputs.items():
        (engine / f"{page}.json").write_text(json.dumps(data), encoding="utf-8")
    status = pairs.main(
        [
            "--gt", str(gt), "--engine-dir", str(engine), "--truth-dir", str(tmp_path / "truth"),
            "--manifests", str(tmp_path / "manifests"), "--name", "mini",
            "--engine", "glypharis", "--model", "glypharis_v1",
        ]
    )  # fmt: skip
    assert status == 0
    return tmp_path


class TestBuildPairs:
    def test_the_care_rule(self) -> None:
        assert pairs.counts(line("ok", 0))
        assert not pairs.counts(line("", 0))
        assert not pairs.counts(line("x", 0, legible=False))
        assert not pairs.counts(line("x", 0, handwritten=True))
        assert not pairs.counts(line("x", 0, vertical=True))

    def test_splits_are_disjoint_complete_and_stratified(self, built: Path) -> None:
        summary = json.loads((built / "manifests" / "mini.json").read_text(encoding="utf-8"))
        assert summary["splits"]["fit"]["pages"] == 2
        assert summary["splits"]["cal"]["pages"] == 1
        assert summary["splits"]["dev"]["pages"] == 1
        seen = []
        for split in ("fit", "cal", "dev"):
            manifest = json.loads(
                (built / "manifests" / f"mini_{split}.json").read_text(encoding="utf-8")
            )
            assert manifest["split"] == split
            seen += [entry["page"] for entry in manifest["pages"]]
            for entry in manifest["pages"]:
                assert (built / "manifests" / entry["engine"]).resolve().is_file()
                assert len(entry["truth_sha256"]) == 64
        assert sorted(seen) == ["p1", "p2", "p3", "p4"]

    def test_the_assignment_is_deterministic_and_salted(self) -> None:
        pages = [pairs.TruthPage(f"page{i}", ()) for i in range(40)]
        first = pairs.assign(pages, "lectris-v1")
        assert first == pairs.assign(list(reversed(pages)), "lectris-v1")
        assert sorted(first.values()).count("fit") == 20
        assert sorted(first.values()).count("cal") == 10
        assert first != pairs.assign(pages, "another salt")

    def test_a_missing_engine_output_is_refused(self, built: Path) -> None:
        (built / "engine" / "p4.json").unlink()
        status = pairs.main(
            [
                "--gt", str(built / "validation.jsonl.gz"), "--engine-dir", str(built / "engine"),
                "--truth-dir", str(built / "truth"), "--manifests", str(built / "m2"),
                "--name", "mini", "--engine", "glypharis", "--model", "glypharis_v1",
            ]
        )  # fmt: skip
        assert status == 1

    def test_the_manifests_hold_no_text(self, built: Path) -> None:
        for path in (built / "manifests").iterdir():
            content = path.read_text(encoding="utf-8")
            assert "hives" not in content
            assert "Bees" not in content


class TestTaxonomy:
    def test_errors_by_kind(self, built: Path) -> None:
        manifests = sorted((built / "manifests").glob("mini_*.json"))
        merged: dict[str, list[Any]] = {"pages": []}
        for path in manifests:
            merged["pages"] += json.loads(path.read_text(encoding="utf-8"))["pages"]
        everything = built / "manifests" / "all.json"
        everything.write_text(json.dumps(merged), encoding="utf-8")
        assert taxonomy.main([str(everything), "--out", str(built / "report")]) == 0
        result = json.loads((built / "report" / "taxonomy.json").read_text(encoding="utf-8"))
        counts = result["all"]["counts"]
        # p1: O for 0 (in a token), the "~~" line dropped as don't care;
        # p2: "rn" for "m" (2 in a token); p3: a lost space (spacing), "speck" (extra line);
        # p4: its line missed
        assert counts == {"in_token": 3, "spacing": 1, "missed_line": 12, "extra_line": 5}
        assert result["all"]["pages"] == 4
        assert (built / "report" / "taxonomy.md").read_text(encoding="utf-8").startswith("#")

    def test_classify(self) -> None:
        assert taxonomy.classify("a b", "ab") == {"spacing": 1}
        assert taxonomy.classify("modem", "rnodem") == {"in_token": 2}

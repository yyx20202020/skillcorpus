import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MD = ROOT / "fixtures" / "queue_primer" / "bounded_queues.md"


def test_cli_pack_validate_query(tmp_path: Path):
    out = tmp_path / "skill"
    pack = subprocess.run(
        [
            sys.executable,
            "-m",
            "skillcorpus",
            "pack",
            str(MD),
            "-o",
            str(out),
            "--name",
            "Queue Primer",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert pack.returncode == 0, pack.stderr
    payload = json.loads(pack.stdout)
    assert payload["chunk_count"] >= 5

    val = subprocess.run(
        [sys.executable, "-m", "skillcorpus", "validate", str(out)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert val.returncode == 0, val.stderr

    query = subprocess.run(
        [
            sys.executable,
            "-m",
            "skillcorpus",
            "query",
            "--skill",
            str(out),
            "backpressure",
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert query.returncode == 0, query.stderr
    data = json.loads(query.stdout)
    assert data["hits"]


def test_cli_doctor():
    proc = subprocess.run(
        [sys.executable, "-m", "skillcorpus", "doctor"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert "ocr_pipeline" in data

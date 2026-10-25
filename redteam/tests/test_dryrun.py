"""Local dry-run mode: the file-backed store, the coordinator's write ordering, and the dry-run driver on a tiny
snapshot. No MongoDB, no Bitdeer (fake client), stub Gate for speed."""
import json
import os
import subprocess
import sys

import pytest

from redteam import mcp_server, scrape_map, store
from redteam.config import REPO

from test_scrape_map import doc

AS_OF = "2026-10-24"


@pytest.fixture
def snapshot(tmp_path):
    docs = [doc(i, mkt=("ebay", "depop", "amazon")[i % 3], seller=f"s{i % 45}", price=15 + (i * 7) % 90,
                reviews=(i % 45) * 9, cond=("new", "good", "like_new")[i % 3]) for i in range(180)]
    snap = scrape_map.build(docs, AS_OF)
    out = tmp_path / "snap"
    scrape_map.write(snap, scrape_map.summarize(snap, len(docs), AS_OF, []), out)
    return out


def run_py(code: str, env: dict) -> str:
    proc = subprocess.run([sys.executable, "-c", code], cwd=REPO, env={**os.environ, **env}, capture_output=True,
                          text=True, encoding="utf-8", timeout=120)
    assert proc.returncode == 0, proc.stderr[-2000:]
    return proc.stdout.strip()


def test_local_store_round_trip_across_processes(tmp_path, monkeypatch):
    d = tmp_path / "store"
    monkeypatch.setenv("REDTEAM_LOCAL_STORE", str(d))
    store.reload()
    r = store.repo()
    r.db.rounds.insert_one({"_id": 1, "x": 1})
    store.flush()
    assert (d / "rounds.jsonl").exists()
    # another process (like the MCP server) loads, writes and flushes
    run_py("from redteam import store; r = store.repo(); store.save_round(r, 1, generation={'tokens': 5}); "
           "r.db.specs.insert_one({'_id': 'S1', 'round': 1}); store.flush()", {"REDTEAM_LOCAL_STORE": str(d)})
    store.reload()
    doc_ = store.get_round(store.repo(), 1)
    assert doc_["x"] == 1 and doc_["generation"] == {"tokens": 5}
    assert store.repo().db.specs.count_documents({}) == 1
    store.set_repo(None)


def test_coordinator_style_write_after_reload_keeps_server_writes(tmp_path, monkeypatch):
    d = tmp_path / "store"
    monkeypatch.setenv("REDTEAM_LOCAL_STORE", str(d))
    store.reload()
    store.repo()  # the coordinator process loaded the store before the session
    store.flush()
    run_py("from redteam import store; store.save_round(store.repo(), 2, promotions=['p']); store.flush()",
           {"REDTEAM_LOCAL_STORE": str(d)})
    # after the session: reload, then write the buffered start fields and the report
    store.reload()
    store.save_round(store.repo(), 2, session_id="sess")
    store.save_round(store.repo(), 2, report={"ok": True})
    store.flush()
    store.reload()
    got = store.get_round(store.repo(), 2)
    assert got["promotions"] == ["p"] and got["session_id"] == "sess" and got["report"] == {"ok": True}
    store.set_repo(None)


def test_init_seeds_train_side_only(tmp_path, snapshot):
    run = tmp_path / "dry-t"
    out = json.loads(run_py(f"from redteam import dryrun; import json; from pathlib import Path; "
                            f"print(json.dumps(dryrun.init(Path(r'{run}'), Path(r'{snapshot}'), 3, 'white_box', False)))",
                            {}))
    assert out["listings"] > 0 and out["known_sellers"] > 0
    cfg = json.loads((run / "run.json").read_text())
    assert cfg["seed"] == 3 and cfg["knowledge"] == "white_box" and cfg["as_of"] == AS_OF
    listed = {json.loads(l)["_id"] for l in (run / "store" / "listings.jsonl").read_text().splitlines()}
    locked = {json.loads(l)["listing_id"] for l in (snapshot / "locked_test" / "listings.jsonl").read_text().splitlines()}
    assert listed and not listed & locked  # locked-test listings never enter the training store
    keys = [json.loads(l) for l in (run / "store" / "answer_keys.jsonl").read_text().splitlines()]
    assert {k["family"] for k in keys} == {"real"}
    with pytest.raises(subprocess.CalledProcessError):
        subprocess.run([sys.executable, "-m", "redteam.dryrun", "init", "--run", str(run), "--snapshot", str(snapshot)],
                       cwd=REPO, check=True, capture_output=True)


def test_local_round_flow_and_summary(tmp_path, snapshot, monkeypatch, fake_client):
    run = tmp_path / "dry-s"
    run_py(f"from redteam import dryrun; from pathlib import Path; "
           f"dryrun.init(Path(r'{run}'), Path(r'{snapshot}'), 1, None, False)", {})
    monkeypatch.setenv("REDTEAM_LOCAL_STORE", str(run / "store"))
    monkeypatch.setenv("REDTEAM_ROUND", "1")
    monkeypatch.setenv("REDTEAM_SEED", "1")
    from redteam import bitdeer
    monkeypatch.setattr(bitdeer, "make_client", lambda: fake_client())
    store.reload()
    # call the tools through the same wrapper the MCP server registers (it flushes the store after every call)
    tool = {f.__name__: (lambda f: lambda *a, **k: json.loads(mcp_server._jsonify(f)(*a, **k)))(f)
            for f in mcp_server.TOOLS}
    for fam in ("too_cheap", "payment_mismatch", "hidden_text", "unknown_seller"):
        g = tool["generate_attacks"]({"family": fam, "n": 20, "legit_ratio": 0.4})
        assert g.get("kept", 0) > 0, g
    t = tool["train_gate"]()
    assert "error" not in t, t
    p = tool["promote_model"](t["model_id"])
    assert "decision" in p
    s = tool["score_round"]()
    assert "attack_success" in s
    # everything above was flushed to disk after each tool call; a fresh process sees it
    out = json.loads(run_py(f"from redteam import dryrun; from pathlib import Path; import json; "
                            f"s = dryrun.summary(Path(r'{run}')); print(json.dumps(s['rounds'], default=str))", {}))
    assert out and out[0]["round"] == 1 and out[0]["attack_success"] is not None
    assert (run / "summary.md").read_text().startswith("# Dry run")
    store.set_repo(None)

# redteam

The red-team loop from `docs/plans/redteam-gate.md` (Part 4): Bitdeer attack generation, the sealed holdout, the MCP
tools the Factory coordinator uses, the guard hook, and the coordinator itself.

Keys go in `<repo>/.env` (gitignored): `BITDEER_API_KEY`, `BITDEER_KEY_GLM` (may be the same key).

## Commands

All commands run from the repo root.

| What | Command | Needs keys |
|---|---|---|
| Tests (offline) | `uv run --project redteam pytest -q redteam/tests` | no |
| Seed batch, templated | `uv run --project redteam python -m redteam.generate --round 0 --family mixed --n 300 --offline --batch-id b01-seed` | no |
| Live batch | `uv run --project redteam python -m redteam.generate --round 0 --family mixed --n 60 --batch-id b02-live-mixed` | yes |
| Holdout, templated placeholder | `uv run --project redteam python -m redteam.holdout build --offline` | no |
| Holdout, real (Nemotron) | `uv run --project redteam python -m redteam.holdout build --force` | yes |
| Holdout totals for a model | `uv run --project redteam python -m redteam.holdout totals --model promoted` | no |
| MCP server (droid spawns it) | `uv run --project redteam python -m redteam.mcp_server` | — |
| One coordinator round | `uv run --project redteam python -m redteam.coordinator --round 1` | yes |
| Cheap dry run | `... redteam.coordinator --round 1 --offline-gen --max-listings 120` | yes (coordinator model) |
| Resume a round | `... redteam.coordinator --round 1 --resume <session_id>` | yes |
| Canary isolation test | `REDTEAM_LIVE=1 uv run --project redteam pytest -s redteam/tests/test_isolation.py` | yes |
| Rounds table | `uv run --project redteam python -m redteam.report` | no |

## Where things go

- `data/rounds/R{n}/b*.jsonl`: Snapshot batches (+ `.meta.json`). Also per round: `calls.jsonl` (every MCP call),
  `budget.json`, `score.json`, `promotion.json`, `session.json`, `usage.json`, `events.jsonl`, `report.json`.
- `data/guard.log`: every guard-hook decision.
- `../calhacks-holdout/`: `holdout.jsonl.enc`, `holdout.key`, `holdout.meta.json`. Outside the repo; only the MCP
  server process gets the key.
- `gate/models/`: model files and `promoted.json` (written by `promote_model`).

## Gate backend

`redteam/src/redteam/gate_client.py` has a single switch, `GATE_BACKEND` (env `REDTEAM_GATE=stub|real`). Until
`feat/gate` is merged it uses `gate_stub.py`, which prints the same JSON as the real `gate-train`/`gate-eval` but
ignores `gate/features/*`. In stub mode the coordinator isn't allowed to edit features; it lists the changes it
would make in its report instead.

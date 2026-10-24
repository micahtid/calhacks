import json

import pytest

from gatepy import GATE_DIR
from gatepy.context import load_ctx
from gatepy.contracts import examples
from gatepy.fixtures import build
from gatepy.registry import discover
from gatepy.train import train


@pytest.fixture(scope="session")
def ctx():
    return load_ctx()


@pytest.fixture(scope="session")
def ex():
    return {s.id: s for s in examples()}


@pytest.fixture(scope="session")
def fixture_file(tmp_path_factory):
    path = tmp_path_factory.mktemp("data") / "fixture.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in build(n=300, seed=1)), encoding="utf-8")
    return path


@pytest.fixture(scope="session")
def models_dir(tmp_path_factory):
    return tmp_path_factory.mktemp("models")


@pytest.fixture(scope="session")
def trained(fixture_file, models_dir):
    return train([str(fixture_file)], 1, GATE_DIR / "train_config.yaml", models_dir)


@pytest.fixture(scope="session")
def baseline(fixture_file, models_dir):
    return train([str(fixture_file)], 0, GATE_DIR / "configs" / "r0_baseline.yaml", models_dir)


@pytest.fixture(autouse=True)
def _fresh_registry():
    discover()
    yield
    discover()

import math
import socket

import pytest

from gatepy.contracts import examples
from gatepy.registry import REGISTRY, discover, feature, feature_code_hash, select, self_test


def test_discover_finds_all_feature_modules():
    reg = discover()
    assert len(reg) >= 20
    assert {"price_ratio", "seller_age_years", "review_dup_max", "injection_hits", "payto_known",
            "urgency_hits", "store_name_similarity_to_known"} <= set(reg)
    assert reg["price_ratio"].monotone == -1
    assert reg["seller_age_years"].monotone == -1


def test_builtin_features_pass_self_test(ctx):
    assert self_test(select("all"), examples(), ctx) == []


def test_self_test_rejects_bad_features(ctx):
    calls = {"n": 0}

    @feature("t_nan")
    def t_nan(s, c):
        return math.nan

    @feature("t_flaky")
    def t_flaky(s, c):
        calls["n"] += 1
        return float(calls["n"])

    @feature("t_network")
    def t_network(s, c):
        socket.create_connection(("example.com", 80))
        return 0.0

    @feature("t_file")
    def t_file(s, c):
        with open(__file__) as f:
            return float(len(f.read()))

    @feature("t_type")
    def t_type(s, c):
        return "high"

    errors = self_test([REGISTRY[n] for n in ("t_nan", "t_flaky", "t_network", "t_file", "t_type")], examples(), ctx)
    for name in ("t_nan", "t_flaky", "t_network", "t_file", "t_type"):
        assert any(e.startswith(name + ":") for e in errors), name


def test_feature_decorator_validates_monotone():
    with pytest.raises(ValueError):
        feature("bad", monotone=2)


def test_select_and_hash():
    assert [f.name for f in select(["price_ratio", "injection_hits"])] == ["price_ratio", "injection_hits"]
    assert "injection_hits" not in [f.name for f in select("all", exclude=["injection_hits"])]
    with pytest.raises(KeyError):
        select(["no_such_feature"])
    assert feature_code_hash() == feature_code_hash()

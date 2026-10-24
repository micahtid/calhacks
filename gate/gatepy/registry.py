"""Feature plugin registry. Modules in gate/features/ register pure functions with @feature(name, monotone=...)."""
import builtins
import hashlib
import importlib
import math
import pkgutil
import socket
import sys
from collections.abc import Callable
from dataclasses import dataclass

import features as features_pkg
from gatepy import GATE_DIR
from gatepy.contracts import Snapshot
from gatepy.context import Ctx

FeatureFn = Callable[[Snapshot, Ctx], float]


@dataclass(frozen=True)
class Feature:
    name: str
    fn: FeatureFn
    monotone: int
    module: str


REGISTRY: dict[str, Feature] = {}


def feature(name: str, monotone: int = 0):
    """Register a feature. monotone=-1: risk must not rise as the value rises; +1: must not fall; 0: free."""
    if monotone not in (-1, 0, 1):
        raise ValueError(f"monotone must be -1, 0 or 1, not {monotone!r}")

    def wrap(fn: FeatureFn) -> FeatureFn:
        if name in REGISTRY and REGISTRY[name].module != fn.__module__:
            raise ValueError(f"feature {name!r} registered twice ({REGISTRY[name].module}, {fn.__module__})")
        REGISTRY[name] = Feature(name, fn, monotone, fn.__module__)
        return fn

    return wrap


def discover() -> dict[str, Feature]:
    """Import (or re-import) every module in gate/features/ and return the registry."""
    REGISTRY.clear()
    for info in sorted(pkgutil.iter_modules(features_pkg.__path__), key=lambda m: m.name):
        mod = f"features.{info.name}"
        if mod in sys.modules:
            importlib.reload(sys.modules[mod])
        else:
            importlib.import_module(mod)
    return dict(REGISTRY)


def select(names: list[str] | str, exclude: list[str] = ()) -> list[Feature]:
    reg = REGISTRY or discover()
    chosen = sorted(reg) if names == "all" else list(names)
    missing = [n for n in chosen if n not in reg]
    if missing:
        raise KeyError(f"unknown features: {missing}")
    return [reg[n] for n in chosen if n not in exclude]


def compute(s: Snapshot, ctx: Ctx, feats: list[Feature]) -> list[float]:
    return [float(f.fn(s, ctx)) for f in feats]


def feature_code_hash() -> str:
    h = hashlib.sha256()
    for p in sorted((GATE_DIR / "features").glob("*.py")):
        h.update(p.name.encode())
        h.update(p.read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()


class _Forbidden(RuntimeError):
    pass


def _forbid(*_a, **_k):
    raise _Forbidden("features must not do I/O or use the network")


def self_test(feats: list[Feature], snapshots: list[Snapshot], ctx: Ctx) -> list[str]:
    """Every feature must return the same finite float twice, without opening files or sockets."""
    errors = []
    saved = builtins.open, socket.socket, socket.create_connection
    builtins.open, socket.socket, socket.create_connection = _forbid, _forbid, _forbid
    try:
        for f in feats:
            for s in snapshots:
                try:
                    a, b = f.fn(s, ctx), f.fn(s, ctx)
                    if isinstance(a, bool) or not isinstance(a, (int, float)):
                        errors.append(f"{f.name}: returned {type(a).__name__} on {s.id}")
                    elif not math.isfinite(a):
                        errors.append(f"{f.name}: non-finite {a!r} on {s.id}")
                    elif a != b:
                        errors.append(f"{f.name}: not deterministic on {s.id} ({a} vs {b})")
                except Exception as e:  # noqa: BLE001 - any failure fails the self-test
                    errors.append(f"{f.name}: {type(e).__name__}: {e} on {s.id}")
                    break
    finally:
        builtins.open, socket.socket, socket.create_connection = saved
    return errors

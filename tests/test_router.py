import tempfile
from pathlib import Path

from moe.config import get_settings
from moe.models import Expert
from moe.retrieval.router import cosine, route
from moe.store.db import Registry


def _registry() -> Registry:
    reg = Registry(Path(tempfile.mkdtemp()) / "moe.db")
    for name, cen in {
        "cardiology": [1.0, 0.0, 0.0],
        "law": [0.0, 1.0, 0.0],
        "cooking": [0.0, 0.0, 1.0],
    }.items():
        reg.upsert_expert(Expert(name=name, description=name))
        reg.set_routing_profile(name, centroid=cen, desc_embedding=cen)
    return reg


def test_cosine_bounds():
    assert cosine([1, 2, 3], [1, 2, 3]) == 1.0
    assert cosine([1, 0], [0, 1]) == 0.0


def test_routes_to_nearest_expert():
    reg = _registry()
    assert route([0.95, 0.1, 0.0], reg, get_settings())[0] == "cardiology"


def test_override_is_respected():
    reg = _registry()
    assert route([0.95, 0.1, 0.0], reg, get_settings(), override=["law"]) == ["law"]


def test_fallback_when_below_threshold():
    reg = _registry()
    s = get_settings()
    # a vector orthogonal-ish to all → below threshold → fallback to top-k
    selected = route([0.0, 0.0, 0.0], reg, s)
    assert 1 <= len(selected) <= max(1, s.route_fallback_k)

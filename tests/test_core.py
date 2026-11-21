import datetime as dt
import importlib.util
import json
from pathlib import Path

import pytest

from agent.catalog import MAX_TTL_HOURS, TEMPLATES, clamp_ttl, get_template
from agent.core import estimate_cost, function_name, is_expired
from agent.handlers import build_source


def load_handler(template_id, monkeypatch, expires, demo_id="abc123"):
    monkeypatch.setenv("DAP_EXPIRES_AT", expires)
    monkeypatch.setenv("DAP_DEMO_ID", demo_id)
    ns: dict = {}
    exec(build_source(template_id), ns)  # noqa: S102 - the exact source shipped to Lambda
    return ns["handler"]


def event(method="GET", path="/", body=None):
    return {"requestContext": {"http": {"method": method}}, "rawPath": path,
            "body": json.dumps(body) if body is not None else None}


FUTURE = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1)).isoformat()
PAST = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)).isoformat()


def test_unknown_template_rejected():
    with pytest.raises(ValueError):
        get_template("ec2-bitcoin-miner")


@pytest.mark.parametrize("given,want", [(None, 8), (0, 1), (5, 5), (9999, MAX_TTL_HOURS)])
def test_ttl_clamped(given, want):
    assert clamp_ttl(given) == want


def test_estimate_uses_clamped_ttl():
    assert estimate_cost("hello-api", 9999)["ttl_hours"] == MAX_TTL_HOURS


def test_function_name():
    assert function_name("abc123", "text-toolkit") == "dap-abc123-text-toolkit"


def test_is_expired():
    now = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    assert is_expired("2025-12-31T00:00:00+00:00", now)
    assert not is_expired("2026-01-02T00:00:00+00:00", now)


def test_hello_api_live(monkeypatch):
    r = load_handler("hello-api", monkeypatch, FUTURE)(event(), None)
    assert r["statusCode"] == 200 and json.loads(r["body"])["demo_id"] == "abc123"


def test_expired_demo_returns_410(monkeypatch):
    for tid in TEMPLATES:
        assert load_handler(tid, monkeypatch, PAST)(event(), None)["statusCode"] == 410


def test_unit_converter(monkeypatch):
    h = load_handler("unit-converter", monkeypatch, FUTURE)
    call = lambda p, b: json.loads(h(event("POST", p, b), None)["body"])  # noqa: E731
    assert call("/temperature", {"value": 100, "from": "C", "to": "F"})["result"] == 212.0
    assert call("/temperature", {"value": 0, "from": "c", "to": "k"})["result"] == 273.15
    assert call("/length", {"value": 5, "from": "km", "to": "mi"})["result"] == pytest.approx(3.106856, rel=1e-5)


def test_text_toolkit_endpoints(monkeypatch):
    h = load_handler("text-toolkit", monkeypatch, FUTURE)
    call = lambda p, t: json.loads(h(event("POST", p, {"text": t}), None)["body"])  # noqa: E731
    assert call("/wordcount", "one two three")["words"] == 3
    assert call("/slugify", "Hello, World!")["slug"] == "hello-world"
    assert call("/base64", "hi")["base64"] == "aGk="
    assert h(event("POST", "/nope", {"text": "x"}), None)["statusCode"] == 404

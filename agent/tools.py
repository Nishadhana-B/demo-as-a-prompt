"""Strands tools: thin wrappers over core.py. Docstrings are what the model reads."""
from strands import tool

from . import core
from .catalog import TEMPLATES


@tool
def list_templates() -> list[dict]:
    """List the vetted demo templates that can be deployed (the only allowed options)."""
    return [{"id": t.id, "title": t.title, "description": t.description} for t in TEMPLATES.values()]


@tool
def estimate_cost(template_id: str, ttl_hours: int = 8) -> dict:
    """Estimate the cost of a template for a given lifetime in hours. Call before deploying."""
    return core.estimate_cost(template_id, ttl_hours)


@tool
def deploy_demo(template_id: str, ttl_hours: int = 8) -> dict:
    """Deploy a vetted template as a public URL. The demo stops answering after ttl_hours (max 72)."""
    return core.deploy(template_id, ttl_hours)


@tool
def validate_demo(url: str, template_id: str) -> dict:
    """Smoke-test a deployed demo URL for the given template id."""
    return core.validate(url, template_id)


@tool
def list_demos() -> list[dict]:
    """List running demos with their expiry times."""
    return core.list_demos()


@tool
def teardown_demo(demo_id: str) -> dict:
    """Delete a demo by id right now (before its TTL)."""
    return core.teardown(demo_id)


@tool
def reap_expired() -> dict:
    """Delete every demo whose TTL has passed."""
    return core.reap_expired()

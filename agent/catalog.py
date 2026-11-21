"""Vetted demo templates. The agent may ONLY deploy what is listed here.

Safety model: the LLM picks a template id and a TTL. It never writes code or infrastructure,
so a bad prompt cannot create arbitrary resources.
"""
from dataclasses import dataclass

MAX_TTL_HOURS = 72
DEFAULT_TTL_HOURS = 8


@dataclass(frozen=True)
class Template:
    id: str
    title: str
    description: str
    est_usd_per_million_requests: float  # Lambda has no idle cost, so cost scales with traffic


TEMPLATES: dict[str, Template] = {
    "hello-api": Template(
        id="hello-api",
        title="Hello API",
        description="A tiny public JSON API on AWS Lambda with a Function URL. Good for a quick live demo.",
        est_usd_per_million_requests=0.20,
    ),
    "text-toolkit": Template(
        id="text-toolkit",
        title="Text Toolkit API",
        description="Public API on AWS Lambda: POST /wordcount, /slugify and /base64 with a JSON {text}.",
        est_usd_per_million_requests=0.20,
    ),
    "unit-converter": Template(
        id="unit-converter",
        title="Unit Converter API",
        description="Public API on AWS Lambda: POST /temperature (C/F/K) and /length (m, km, cm, mi, ft, in).",
        est_usd_per_million_requests=0.20,
    ),
}


def get_template(template_id: str) -> Template:
    try:
        return TEMPLATES[template_id]
    except KeyError:
        raise ValueError(f"Unknown template '{template_id}'. Allowed: {sorted(TEMPLATES)}") from None


def clamp_ttl(hours: float | int | None) -> int:
    """Every demo gets a TTL. Missing -> default, too big -> capped, <1 -> 1."""
    if hours is None:
        return DEFAULT_TTL_HOURS
    return max(1, min(int(hours), MAX_TTL_HOURS))

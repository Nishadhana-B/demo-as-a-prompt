"""CLI: python -m agent.main "spin up a text toolkit demo for 2 hours" """
import os
import sys

from strands import Agent
from strands.models import BedrockModel

from .tools import (deploy_demo, estimate_cost, list_demos, list_templates, reap_expired,
                    teardown_demo, validate_demo)

SYSTEM = """You provision short-lived AWS demo environments (public Lambda URLs).
Rules: only use options from list_templates; always call estimate_cost first and state the cost;
always set a TTL; after deploy_demo, call validate_demo with the returned url and template id and
report the URL, expiry time and validation result; deploy at most one demo per request;
ask before tearing down a demo you did not just create."""

MODEL_ID = os.environ.get("DAP_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0")
BEDROCK_REGION = os.environ.get("DAP_BEDROCK_REGION", "us-east-1")


def build_agent() -> Agent:
    return Agent(
        model=BedrockModel(model_id=MODEL_ID, region_name=BEDROCK_REGION),
        system_prompt=SYSTEM,
        tools=[list_templates, estimate_cost, deploy_demo, validate_demo, list_demos,
               teardown_demo, reap_expired],
    )


if __name__ == "__main__":
    build_agent()(" ".join(sys.argv[1:]) or "What demos can you build?")
